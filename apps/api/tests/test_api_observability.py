"""Privacy-safe API olay kolektoru ve platform-admin sorgu sozlesmesi."""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Request
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core import request_observability as observer
from app.core.config import Settings
from app.core.db import dispose_engine
from app.core.request_observability import (
    _next_purge_delay,
    _purge_expired,
    enqueue_request_event,
    observer_snapshot,
    route_template_of,
    should_observe_request,
    start_request_observer,
    stop_request_observer,
)
from tests.conftest import UserFactory

REQUEST_500 = "a" * 32
REQUEST_200 = "b" * 32
REQUEST_404 = "c" * 32


async def _grant_admin(engine: AsyncEngine, user_id: object) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text("INSERT INTO platform_admins (user_id) VALUES (:user_id)"),
            {"user_id": user_id},
        )


async def _wait_for_counter(name: str, minimum: int) -> dict[str, object]:
    for _ in range(100):
        snapshot = observer_snapshot()
        value = snapshot[name]
        if isinstance(value, int) and value >= minimum:
            return snapshot
        await asyncio.sleep(0.02)
    pytest.fail(f"collector {name} sayaci {minimum} degerine ulasmadi: {observer_snapshot()}")


def test_config_kill_switch_docs_ve_production_retention_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("API_EVENT_RETENTION_DAYS", raising=False)
    monkeypatch.delenv("API_DOCS_ENABLED", raising=False)
    local = Settings(_env_file=None, dev_auth_enabled=True, api_observability_enabled=False)
    assert local.api_docs_enabled is True
    assert local.api_observability_enabled is False

    production = {
        "environment": "production",
        "dev_auth_enabled": False,
        "api_observability_enabled": False,
        "supabase_jwt_secret": "test-secret",
        "storage_backend": "supabase",
        "supabase_url": "https://example.supabase.co",
        "supabase_service_role_key": "test-service-key",
    }
    assert Settings(_env_file=None, **production).api_docs_enabled is False  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="API_DOCS_ENABLED"):
        Settings(_env_file=None, api_docs_enabled=True, **production)  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="API_EVENT_RETENTION_DAYS"):
        Settings(
            _env_file=None,
            **{**production, "api_observability_enabled": True},  # type: ignore[arg-type]
        )

    configured = Settings(
        _env_file=None,
        api_event_retention_days=3,
        **{**production, "api_observability_enabled": True},  # type: ignore[arg-type]
    )
    assert configured.api_event_retention_days == 3


def test_route_helper_ham_path_kullanmaz_ve_operasyon_yuzeylerini_dislar() -> None:
    raw_id = "550e8400-e29b-41d4-a716-446655440000"
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"/courses/{raw_id}",
            "query_string": b"prompt=gizli",
            "headers": [],
            "route": SimpleNamespace(path="/courses/{course_id}"),
        }
    )
    assert route_template_of(request) == "/courses/{course_id}"

    unmatched = Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"/unknown/{raw_id}",
            "query_string": b"",
            "headers": [],
        }
    )
    assert route_template_of(unmatched) == "UNMATCHED"
    assert should_observe_request("POST", "/courses/{course_id}/chat") is True
    assert should_observe_request("GET", "/admin/overview") is False
    assert should_observe_request("GET", "/health/ready") is False
    assert should_observe_request("GET", "/openapi.json") is False
    assert should_observe_request("OPTIONS", "/courses/{course_id}") is False


def test_purge_takvimi_normal_backlog_ve_hata_turlarini_ayirir() -> None:
    assert _next_purge_delay(0) == 60.0
    assert _next_purge_delay(999) == 60.0
    assert _next_purge_delay(1000) == 1.0
    assert _next_purge_delay(None) == 5.0


def test_writer_basarisi_retention_hatasini_gizlemez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = observer._ObserverState(status="healthy", write_healthy=True, purge_healthy=False)
    monkeypatch.setattr(observer, "_state", state)

    observer._refresh_observer_status()
    assert state.status == "degraded"
    state.purge_healthy = True
    observer._refresh_observer_status()
    assert state.status == "healthy"


async def test_purge_yalniz_kendi_basarisi_ile_toparlanir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = observer._ObserverState(status="healthy")
    monkeypatch.setattr(observer, "_state", state)

    async def failed_batch() -> int:
        raise TimeoutError

    async def successful_batch() -> int:
        return 0

    monkeypatch.setattr(observer, "_purge_batch", failed_batch)
    assert await _purge_expired() is None
    assert state.purge_healthy is False
    assert state.status == "degraded"

    monkeypatch.setattr(observer, "_purge_batch", successful_batch)
    assert await _purge_expired() == 0
    assert state.purge_healthy is True
    assert state.status == "healthy"


async def test_flag_kapaliyken_retention_arizasi_ve_toparlanma_gozlenir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = observer._ObserverState(status="disabled")
    monkeypatch.setattr(observer, "_state", state)

    async def failed_batch() -> int:
        raise TimeoutError

    async def successful_batch() -> int:
        return 0

    monkeypatch.setattr(observer, "_purge_batch", failed_batch)
    assert await _purge_expired() is None
    assert observer_snapshot()["status"] == "disabled"
    assert observer_snapshot()["retention_status"] == "degraded"

    monkeypatch.setattr(observer, "_purge_batch", successful_batch)
    assert await _purge_expired() == 0
    assert observer_snapshot()["status"] == "disabled"
    assert observer_snapshot()["retention_status"] == "healthy"


async def test_expired_backlog_tekrar_eden_bounded_batchlerle_biter(
    admin_engine: AsyncEngine,
) -> None:
    try:
        async with admin_engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO api_request_events ("
                    "request_id, service, environment, release_revision, method, "
                    "route_template, status_code, duration_ms, created_at, expires_at"
                    ") SELECT lpad(to_hex(value), 32, '0'), 'api', 'demo', '010-load', "
                    "'GET', '/dashboard', 200, 1, now() - interval '2 days', "
                    "now() - interval '1 day' FROM generate_series(1, 2501) AS value"
                )
            )

        assert await _purge_expired() == 1000
        assert await _purge_expired() == 1000
        assert await _purge_expired() == 501
        async with admin_engine.connect() as connection:
            remaining = await connection.scalar(
                text("SELECT count(*) FROM api_request_events WHERE release_revision = '010-load'")
            )
        assert remaining == 0
    finally:
        await dispose_engine()


async def test_collection_flag_false_iken_expired_satir_temizlenir(
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await stop_request_observer()
    async with admin_engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO api_request_events ("
                "request_id, service, environment, release_revision, method, "
                "route_template, status_code, duration_ms, created_at, expires_at"
                ") VALUES ('dddddddddddddddddddddddddddddddd', 'api', 'local', "
                "'010-test', 'GET', '/dashboard', 200, 1, "
                "now() - interval '2 days', now() - interval '1 day')"
            )
        )
    monkeypatch.setattr(
        observer,
        "get_settings",
        lambda: SimpleNamespace(api_observability_enabled=False),
    )

    await start_request_observer()
    try:
        for _ in range(100):
            async with admin_engine.connect() as connection:
                remaining = await connection.scalar(
                    text(
                        "SELECT count(*) FROM api_request_events "
                        "WHERE request_id = 'dddddddddddddddddddddddddddddddd'"
                    )
                )
            if remaining == 0:
                break
            await asyncio.sleep(0.02)
        assert remaining == 0
        assert observer_snapshot()["status"] == "disabled"
    finally:
        await stop_request_observer()
        await dispose_engine()


@pytest.mark.usefixtures("environment")
async def test_disabled_kill_switch_event_kuyrugu_acmaz_retention_surur(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await stop_request_observer()
    monkeypatch.setattr(
        "app.core.request_observability.get_settings",
        lambda: SimpleNamespace(api_observability_enabled=False),
    )

    await start_request_observer()
    try:
        enqueue_request_event(
            request_id=uuid4().hex,
            method="GET",
            route_template="/dashboard",
            status_code=200,
            outcome_code=None,
            duration_ms=1,
        )

        assert observer._maintenance_task is not None
        assert observer_snapshot() == {
            "scope": "process",
            "status": "disabled",
            "retention_status": "healthy",
            "queue_depth": 0,
            "queue_capacity": 0,
            "persisted_total": 0,
            "dropped_total": 0,
            "failure_total": 0,
            "last_persisted_at": None,
            "last_error_at": None,
        }
    finally:
        await stop_request_observer()


def test_dolu_kuyruk_cagirani_etkilemez_ve_uyariyi_sinirlar(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    queue: asyncio.Queue[object] = asyncio.Queue(maxsize=1)
    queue.put_nowait(object())
    state = observer._ObserverState(status="healthy")
    monkeypatch.setattr(observer, "_queue", queue)
    monkeypatch.setattr(observer, "_state", state)
    monkeypatch.setattr(
        observer,
        "get_settings",
        lambda: SimpleNamespace(
            api_observability_enabled=True,
            environment=SimpleNamespace(value="local"),
            release_revision="queue-test",
        ),
    )

    with caplog.at_level(logging.WARNING, logger="app.observability"):
        for request_id in ("d" * 32, "e" * 32):
            enqueue_request_event(
                request_id=request_id,
                method="GET",
                route_template="/dashboard",
                status_code=200,
                outcome_code=None,
                duration_ms=1,
            )

    assert state.dropped_total == 2
    assert state.status == "degraded"
    assert state.write_healthy is False
    assert len([record for record in caplog.records if record.name == "app.observability"]) == 1


async def test_collector_batch_yazar_ve_hassas_yuzeyleri_toplamaz(
    admin_engine: AsyncEngine,
) -> None:
    await start_request_observer()
    try:
        enqueue_request_event(
            request_id=REQUEST_500,
            method="post",
            route_template="/courses/{course_id}/chat",
            status_code=500,
            outcome_code="internal_error",
            duration_ms=42.4,
        )
        # ACK kaybi sonrasi ayni batch tekrarlandiginda destek kodu tekil kalir;
        # process sayaci da yalniz gercek INSERT sayisini izler.
        enqueue_request_event(
            request_id=REQUEST_500,
            method="post",
            route_template="/courses/{course_id}/chat",
            status_code=500,
            outcome_code="internal_error",
            duration_ms=42.4,
        )
        for method, route in (
            ("GET", "/admin/overview"),
            ("GET", "/health/ready"),
            ("OPTIONS", "/courses/{course_id}"),
        ):
            enqueue_request_event(
                request_id=uuid4().hex,
                method=method,
                route_template=route,
                status_code=200,
                outcome_code=None,
                duration_ms=1,
            )

        snapshot = await _wait_for_counter("persisted_total", 1)
        assert snapshot["status"] == "healthy"
        async with admin_engine.connect() as connection:
            rows = (
                (
                    await connection.execute(
                        text(
                            "SELECT request_id, method, route_template, status_code, "
                            "outcome_code, duration_ms FROM api_request_events"
                        )
                    )
                )
                .mappings()
                .all()
            )
        assert [dict(row) for row in rows] == [
            {
                "request_id": REQUEST_500,
                "method": "POST",
                "route_template": "/courses/{course_id}/chat",
                "status_code": 500,
                "outcome_code": "internal_error",
                "duration_ms": 42,
            }
        ]
    finally:
        await stop_request_observer()


async def test_persistence_failure_retry_sonrasi_drop_olur_ve_cagirani_etkilemez(
    environment: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def successful_purge() -> int:
        return 0

    async def failed_persist(_batch: object) -> None:
        raise TimeoutError("ham-veritabani-hatasi-loglanmamali")

    monkeypatch.setattr("app.core.request_observability._purge_expired", successful_purge)
    monkeypatch.setattr("app.core.request_observability._persist_batch", failed_persist)
    await start_request_observer()
    try:
        # Senkron enqueue hata firlatmaz; HTTP middleware bu cagrinin sonucunu beklemez.
        enqueue_request_event(
            request_id=uuid4().hex,
            method="GET",
            route_template="/dashboard",
            status_code=200,
            outcome_code=None,
            duration_ms=2,
        )
        snapshot = await _wait_for_counter("dropped_total", 1)
        assert snapshot["status"] == "degraded"
        assert snapshot["failure_total"] == 2
        assert snapshot["last_error_at"] is not None
    finally:
        await stop_request_observer()


@pytest.mark.usefixtures("environment")
async def test_collector_shutdown_takilan_iptalde_bile_hard_bound_korur(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Driver cancellation cleanup'i takılsa bile lifespan sonsuza dek beklemez."""

    persist_started = asyncio.Event()
    release_cleanup = asyncio.Event()

    async def stuck_persist(_batch: object) -> int:
        persist_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            await release_cleanup.wait()
        return 0

    async def no_purge() -> int:
        return 0

    await stop_request_observer()
    monkeypatch.setattr(observer, "_SHUTDOWN_TIMEOUT_SECONDS", 0.02)
    monkeypatch.setattr(observer, "_persist_batch", stuck_persist)
    monkeypatch.setattr(observer, "_purge_expired", no_purge)
    await start_request_observer()
    enqueue_request_event(
        request_id=uuid4().hex,
        method="GET",
        route_template="/dashboard",
        status_code=200,
        outcome_code=None,
        duration_ms=1,
    )
    await asyncio.wait_for(persist_started.wait(), timeout=1)
    collector_task = observer._task

    started = asyncio.get_running_loop().time()
    await stop_request_observer()
    elapsed = asyncio.get_running_loop().time() - started

    assert elapsed < 0.2
    assert observer_snapshot()["status"] == "degraded"
    release_cleanup.set()
    if collector_task is not None and not collector_task.done():
        await asyncio.wait_for(collector_task, timeout=1)


@pytest.mark.usefixtures("environment")
async def test_retention_shutdown_takilan_iptalde_bile_hard_bound_korur(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    maintenance_started = asyncio.Event()
    release_cleanup = asyncio.Event()

    async def stuck_maintenance() -> None:
        maintenance_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            await release_cleanup.wait()

    await stop_request_observer()
    monkeypatch.setattr(observer, "_SHUTDOWN_TIMEOUT_SECONDS", 0.02)
    monkeypatch.setattr(observer, "_maintenance_loop", stuck_maintenance)
    monkeypatch.setattr(
        observer,
        "get_settings",
        lambda: SimpleNamespace(api_observability_enabled=False),
    )
    await start_request_observer()
    await asyncio.wait_for(maintenance_started.wait(), timeout=1)
    maintenance_task = observer._maintenance_task

    started = asyncio.get_running_loop().time()
    await stop_request_observer()
    elapsed = asyncio.get_running_loop().time() - started

    assert elapsed < 0.2
    assert observer_snapshot()["retention_status"] == "degraded"
    release_cleanup.set()
    if maintenance_task is not None and not maintenance_task.done():
        await asyncio.wait_for(maintenance_task, timeout=1)


async def test_admin_api_event_query_exact_contract_filter_and_audit(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    admin_id = await users.create("ops-admin@dogus.edu.tr")
    normal_id = await users.create("normal@dogus.edu.tr")
    await _grant_admin(admin_engine, admin_id)
    async with admin_engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO api_request_events ("
                "request_id, service, environment, release_revision, method, "
                "route_template, status_code, outcome_code, duration_ms, expires_at"
                ") VALUES "
                "(:request_500, 'api', 'demo', 'rev-a', 'POST', "
                "'/courses/{course_id}/chat', 500, 'internal_error', 100, now()+interval '1 day'),"
                "(:request_200, 'api', 'demo', 'rev-a', 'POST', "
                "'/courses/{course_id}/chat', 200, NULL, 20, now()+interval '1 day'),"
                "(:request_404, 'api', 'demo', 'rev-a', 'GET', "
                "'UNMATCHED', 404, 'not_found', 10, now()+interval '1 day')"
            ),
            {
                "request_500": REQUEST_500,
                "request_200": REQUEST_200,
                "request_404": REQUEST_404,
            },
        )

    denied = await client.post(
        "/admin/api-events/query",
        headers=users.auth(normal_id),
        json={"window_minutes": 60},
    )
    response = await client.post(
        "/admin/api-events/query",
        headers=users.auth(admin_id),
        json={
            "window_minutes": 60,
            "method": "post",
            "status_class": "5xx",
            "request_id": REQUEST_500,
            "limit": 25,
            "offset": 0,
        },
    )

    assert denied.status_code == 403
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "measured_at",
        "window_minutes",
        "summary",
        "routes",
        "items",
        "total",
        "limit",
        "offset",
        "collector",
    }
    assert body["summary"] == {
        "requests_total": 1,
        "successful_total": 0,
        "redirect_total": 0,
        "client_error_total": 0,
        "server_error_total": 1,
        "p50_latency_ms": 100.0,
        "p95_latency_ms": 100.0,
    }
    assert set(body["routes"][0]) == {
        "method",
        "route_template",
        "requests_total",
        "error_total",
        "p95_latency_ms",
        "last_seen_at",
    }
    assert set(body["items"][0]) == {
        "request_id",
        "service",
        "environment",
        "release_revision",
        "method",
        "route_template",
        "status_code",
        "outcome_code",
        "duration_ms",
        "created_at",
    }
    assert "id" not in body["items"][0]
    assert body["items"][0]["request_id"] == REQUEST_500

    async with admin_engine.connect() as connection:
        audit = (
            await connection.execute(
                text(
                    "SELECT actor_user_id, result FROM platform_admin_access_audit "
                    "WHERE action = 'POST /admin/api-events/query' ORDER BY created_at, id"
                )
            )
        ).all()
    assert [(row.actor_user_id, row.result) for row in audit] == [
        (normal_id, "denied"),
        (admin_id, "allowed"),
    ]


async def test_admin_api_event_query_strict_body_validation(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    admin_id = await users.create("ops-admin@dogus.edu.tr")
    await _grant_admin(admin_engine, admin_id)
    headers = users.auth(admin_id)
    for body in (
        {"window_minutes": 30},
        {"limit": 101},
        {"offset": -1},
        {"offset": 2_147_483_648},
        {"status_class": "500"},
        {"request_id": "email@example.test/private"},
        {"unknown": "field"},
    ):
        response = await client.post("/admin/api-events/query", headers=headers, json=body)
        assert response.status_code == 422, (body, response.text)
