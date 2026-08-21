"""Iceriksiz, yanit yolundan ayrik API olay kolektoru.

Bu modul ham URL, sorgu, govde, kullanici kimligi, IP, user-agent veya istisna
metni kabul etmez. Middleware yalniz sabit route sablonu ve kategorik sonuc kodu
verir; yazim basarisizligi kullanici yanitini asla degistirmez.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Final, cast

from fastapi import Request
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import get_observability_session_factory
from app.core.logging import get_logger

logger = get_logger("app.observability")

_QUEUE_CAPACITY: Final = 1000
_BATCH_SIZE: Final = 100
_PERSIST_TIMEOUT_SECONDS: Final = 2.0
_SHUTDOWN_TIMEOUT_SECONDS: Final = 2.0
_PURGE_INTERVAL_SECONDS: Final = 60.0
_PURGE_CATCHUP_SECONDS: Final = 1.0
_PURGE_RETRY_SECONDS: Final = 5.0
_PURGE_BATCH_SIZE: Final = 1000
_WARNING_INTERVAL_SECONDS: Final = 60.0
_SAFE_REQUEST_ID = re.compile(r"^[a-f0-9]{32}$")
_SAFE_OUTCOME = re.compile(r"^[a-z0-9_:-]{1,64}$")
_SAFE_ROUTE = re.compile(r"^(?:/[A-Za-z0-9_{}./-]{0,255}|UNMATCHED)$")
_RAW_UUID_SEGMENT = re.compile(
    r"(?:^|/)[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?:$|/)"
)
_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"})
_STOP: Final = object()


@dataclass(frozen=True, slots=True)
class _RequestEvent:
    request_id: str
    service: str
    environment: str
    release_revision: str
    method: str
    route_template: str
    status_code: int
    outcome_code: str | None
    duration_ms: int


@dataclass(slots=True)
class _ObserverState:
    status: str = "disabled"
    write_healthy: bool = True
    purge_healthy: bool = True
    persisted_total: int = 0
    dropped_total: int = 0
    failure_total: int = 0
    last_persisted_at: datetime | None = None
    last_error_at: datetime | None = None
    last_warning_at: float = 0.0


_queue: asyncio.Queue[_RequestEvent | object] | None = None
_task: asyncio.Task[None] | None = None
_maintenance_task: asyncio.Task[None] | None = None
_state = _ObserverState()


def _refresh_observer_status() -> None:
    """Yaşam döngüsünü koruyup yazma/retention sağlığını birlikte türetir."""

    if _state.status in {"disabled", "stopped"}:
        return
    _state.status = "healthy" if _state.write_healthy and _state.purge_healthy else "degraded"


def should_observe_request(method: str, route_template: str) -> bool:
    """Yonetim/saglik/docs ve preflight trafigini kalici telemetriden dislar."""
    normal_method = method.upper()
    return (
        normal_method != "OPTIONS"
        and normal_method in _METHODS
        and not route_template.startswith("/admin")
        and not route_template.startswith("/health")
        and route_template != "/docs"
        and not route_template.startswith("/docs/")
        and route_template not in {"/redoc", "/openapi.json"}
    )


def route_template_of(request: Request) -> str:
    """Starlette'in eslesen sablonunu dondurur; ham URL'ye asla geri dusmez."""
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if not isinstance(template, str) or not _SAFE_ROUTE.fullmatch(template):
        return "UNMATCHED"
    return template


def observer_snapshot() -> dict[str, object]:
    """Yalniz bu prosesin kolektor durumunu guvenli DTO olarak dondurur."""
    queue = _queue
    return {
        "scope": "process",
        "status": _state.status,
        "retention_status": "healthy" if _state.purge_healthy else "degraded",
        "queue_depth": queue.qsize() if queue is not None else 0,
        "queue_capacity": _QUEUE_CAPACITY if queue is not None else 0,
        "persisted_total": _state.persisted_total,
        "dropped_total": _state.dropped_total,
        "failure_total": _state.failure_total,
        "last_persisted_at": _state.last_persisted_at,
        "last_error_at": _state.last_error_at,
    }


async def start_request_observer() -> None:
    """Retention bakımını daima, olay kolektörünü yalnız flag açıkken başlatır."""
    global _maintenance_task, _queue, _state, _task
    settings = get_settings()

    if _maintenance_task is None or _maintenance_task.done():
        _maintenance_task = asyncio.create_task(
            _maintenance_loop(),
            name="api-request-observability-retention",
        )

    if not settings.api_observability_enabled:
        if _task is not None:
            await _stop_collector_task()
        _queue = None
        _task = None
        _state = _ObserverState(status="disabled")
        return
    if _task is not None and not _task.done():
        return

    _queue = asyncio.Queue(maxsize=_QUEUE_CAPACITY)
    _state = _ObserverState(status="healthy")
    _task = asyncio.create_task(_collector_loop(), name="api-request-observer")


async def stop_request_observer() -> None:
    """Kolektör ve retention görevlerini ayrı iki saniyelik tavanlarla kapatır."""
    await asyncio.gather(_stop_collector_task(), _stop_maintenance_task())


async def _stop_collector_task() -> None:
    """Kuyruğu bounded biçimde boşaltıp olay yazıcısını kapatır."""
    global _queue, _task
    task = _task
    queue = _queue
    if task is None:
        if not get_settings().api_observability_enabled:
            _state.status = "disabled"
        return

    async def _drain_and_join() -> None:
        assert queue is not None
        await queue.put(_STOP)
        await task

    shutdown = asyncio.create_task(_drain_and_join(), name="api-request-observer-shutdown")
    done, _pending = await asyncio.wait({shutdown}, timeout=_SHUTDOWN_TIMEOUT_SECONDS)
    timed_out = shutdown not in done
    if timed_out:
        pending = queue.qsize() if queue is not None else 0
        _state.dropped_total += pending
        _state.status = "degraded"
        shutdown.cancel()
        task.cancel()
        shutdown.add_done_callback(_consume_task_outcome)
        task.add_done_callback(_consume_task_outcome)
        _warn_rate_limited("api olay yazıcısı bounded sürede kapanmadı", "TimeoutError")
    else:
        await shutdown

    _task = None
    _queue = None
    if not timed_out and _state.status != "disabled":
        _state.status = "stopped"


def _consume_task_outcome(task: asyncio.Future[None]) -> None:
    """Detached bounded-shutdown görevlerinin sonucunu event-loop uyarısız tüketir."""

    if task.cancelled():
        return
    try:
        task.exception()
    except (asyncio.CancelledError, Exception):
        return


async def _stop_maintenance_task() -> None:
    global _maintenance_task
    task = _maintenance_task
    if task is None:
        return
    task.cancel()
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=_SHUTDOWN_TIMEOUT_SECONDS)
    except asyncio.CancelledError:
        pass
    except TimeoutError:
        _state.failure_total += 1
        _state.last_error_at = datetime.now(UTC)
        _state.purge_healthy = False
        _refresh_observer_status()
        task.add_done_callback(_consume_task_outcome)
        _warn_rate_limited("api olay saklama görevi bounded sürede kapanmadı", "TimeoutError")
    finally:
        _maintenance_task = None


def enqueue_request_event(
    *,
    request_id: str,
    method: str,
    route_template: str,
    status_code: int,
    outcome_code: str | None,
    duration_ms: float | int,
) -> None:
    """Olayi beklemeden kuyruga koyar; doluluk ve kapali durum no-op'tur."""
    settings = get_settings()
    queue = _queue
    if not settings.api_observability_enabled or queue is None:
        return

    method = method.upper()
    route_template = (
        route_template
        if _SAFE_ROUTE.fullmatch(route_template) and not _RAW_UUID_SEGMENT.search(route_template)
        else "UNMATCHED"
    )
    if not should_observe_request(method, route_template):
        return

    safe_request_id = request_id if _SAFE_REQUEST_ID.fullmatch(request_id) else uuid.uuid4().hex
    safe_outcome = (
        outcome_code if outcome_code is not None and _SAFE_OUTCOME.fullmatch(outcome_code) else None
    )
    event = _RequestEvent(
        request_id=safe_request_id,
        service="api",
        environment=settings.environment.value,
        release_revision=settings.release_revision,
        method=method,
        route_template=route_template,
        status_code=min(599, max(100, int(status_code))),
        outcome_code=safe_outcome,
        duration_ms=min(3_600_000, max(0, round(float(duration_ms)))),
    )
    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        _state.dropped_total += 1
        _state.write_healthy = False
        _refresh_observer_status()
        _warn_rate_limited("api olay kuyrugu dolu", "QueueFull")


async def _collector_loop() -> None:
    assert _queue is not None
    queue = _queue
    while True:
        item = await queue.get()
        if item is _STOP:
            queue.task_done()
            return

        batch: list[_RequestEvent] = [cast(_RequestEvent, item)]
        stop_after_batch = False
        while len(batch) < _BATCH_SIZE:
            try:
                candidate = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if candidate is _STOP:
                queue.task_done()
                stop_after_batch = True
                break
            batch.append(cast(_RequestEvent, candidate))

        await _persist_with_one_retry(batch)
        for _ in batch:
            queue.task_done()
        if stop_after_batch:
            return


async def _maintenance_loop() -> None:
    """Collection durumundan bağımsız expiry invariantını bounded turlarla korur."""

    while True:
        purged = await _purge_expired()
        await asyncio.sleep(_next_purge_delay(purged))


async def _persist_with_one_retry(batch: list[_RequestEvent]) -> None:
    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            inserted = await asyncio.wait_for(
                _persist_batch(batch), timeout=_PERSIST_TIMEOUT_SECONDS
            )
        except Exception as exc:
            last_error = exc
            _state.failure_total += 1
            _state.last_error_at = datetime.now(UTC)
            continue
        _state.persisted_total += inserted
        _state.last_persisted_at = datetime.now(UTC)
        _state.write_healthy = True
        _refresh_observer_status()
        return

    _state.dropped_total += len(batch)
    _state.write_healthy = False
    _refresh_observer_status()
    _warn_rate_limited(
        "api olaylari kalici depoya yazilamadi",
        type(last_error).__name__ if last_error is not None else "UnknownError",
    )


async def _persist_batch(batch: list[_RequestEvent]) -> int:
    settings = get_settings()
    payload = json.dumps([asdict(event) for event in batch], separators=(",", ":"))
    factory = get_observability_session_factory()
    async with factory() as session, session.begin():
        inserted = await session.scalar(
            text("SELECT app.record_api_request_events(CAST(:events AS jsonb), :retention_days)"),
            {
                "events": payload,
                "retention_days": settings.api_event_retention_days,
            },
        )
    if isinstance(inserted, bool) or not isinstance(inserted, int):
        raise RuntimeError("api olay yazicisi gecersiz sonuc dondurdu")
    if inserted < 0 or inserted > len(batch):
        raise RuntimeError("api olay yazicisi batch sinirini asti")
    return inserted


def _next_purge_delay(purged: int | None) -> float:
    """Normal, backlog ve hata turlarını bounded sıklıkta zamanlar."""

    if purged is None:
        return _PURGE_RETRY_SECONDS
    if purged >= _PURGE_BATCH_SIZE:
        return _PURGE_CATCHUP_SECONDS
    return _PURGE_INTERVAL_SECONDS


async def _purge_expired() -> int | None:
    """Tek bounded batch siler; dolu batch bir saniye sonra yeni tur ister."""
    try:
        value = await asyncio.wait_for(
            _purge_batch(),
            timeout=_PERSIST_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        _state.failure_total += 1
        _state.last_error_at = datetime.now(UTC)
        _state.purge_healthy = False
        _refresh_observer_status()
        _warn_rate_limited("api olay saklama temizligi basarisiz", type(exc).__name__)
        return None
    _state.purge_healthy = True
    _refresh_observer_status()
    return int(value or 0)


async def _purge_batch() -> int:
    """Transaction başlangıcı, sorgu ve commit'i tek timeout kapsamına alır."""

    factory = get_observability_session_factory()
    async with factory() as session, session.begin():
        value = await session.scalar(
            text("SELECT app.purge_expired_api_request_events(:limit)"),
            {"limit": _PURGE_BATCH_SIZE},
        )
    return int(value or 0)


def _warn_rate_limited(message: str, error_type: str) -> None:
    now = time.monotonic()
    if now - _state.last_warning_at < _WARNING_INTERVAL_SECONDS:
        return
    _state.last_warning_at = now
    logger.warning(
        message,
        extra={
            "context": {
                "error_type": error_type,
                "dropped_total": _state.dropped_total,
                "failure_total": _state.failure_total,
            }
        },
    )
