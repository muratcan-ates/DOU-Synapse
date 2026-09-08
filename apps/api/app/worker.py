"""Ingestion worker with finite claims, graceful stop and bounded maintenance.

A continuous worker polls expired leases. Scale-to-zero deployments need an
external authenticated scheduled wake-up; expiry alone does not start a process.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.request_quota_maintenance import purge_expired_request_windows
from app.modules.ingestion.pipeline import run_pending_jobs
from app.modules.ingestion.storage import get_storage

logger = get_logger("app.worker")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
POLL_INTERVAL_SECONDS = 2.0
QUOTA_PURGE_INTERVAL_SECONDS = 60.0
QUOTA_PURGE_BATCH_SIZE = 500


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _engine, _session_factory
    if _session_factory is None:
        settings = get_settings()
        dsn = str(settings.worker_database_url or settings.database_url)
        _engine = create_async_engine(
            dsn, pool_size=2, max_overflow=2, pool_pre_ping=True, hide_parameters=True
        )
        _session_factory = async_sessionmaker(bind=_engine, expire_on_commit=False)
    return _session_factory


async def dispose() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


async def drain(limit: int | None = None, *, stop_event: asyncio.Event | None = None) -> int:
    settings = get_settings()
    return await run_pending_jobs(
        _get_session_factory(),
        get_storage(),
        limit=limit if limit is not None else settings.worker_batch_size,
        stop_event=stop_event,
    )


async def _wait_for_stop(stop: asyncio.Event, seconds: float) -> None:
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(stop.wait(), timeout=seconds)


async def _quota_maintenance(stop: asyncio.Event) -> None:
    """Separate task; not per request/drain and never on a claim transaction."""
    while not stop.is_set():
        try:
            await purge_expired_request_windows(
                _get_session_factory(), batch_size=QUOTA_PURGE_BATCH_SIZE
            )
        except Exception:
            logger.warning("kota bakımı başarısız", extra={"context": {"stage": "quota_purge"}})
        await _wait_for_stop(stop, QUOTA_PURGE_INTERVAL_SECONDS)


async def _cancel_and_join(task: asyncio.Task[object]) -> None:
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await task


async def run_forever(
    poll_interval: float = POLL_INTERVAL_SECONDS, *, stop_event: asyncio.Event | None = None
) -> None:
    configure_logging()
    logger.info("worker başlatıldı")
    stop = stop_event if stop_event is not None else asyncio.Event()
    maintenance = asyncio.create_task(_quota_maintenance(stop))
    stop_waiter = asyncio.create_task(stop.wait())
    batch: asyncio.Task[int] | None = None
    try:
        while not stop.is_set():
            batch = asyncio.create_task(drain(stop_event=stop))
            await asyncio.wait({batch, stop_waiter}, return_when=asyncio.FIRST_COMPLETED)
            if stop.is_set():
                try:
                    await asyncio.wait_for(
                        asyncio.shield(batch), timeout=get_settings().worker_shutdown_grace_seconds
                    )
                except TimeoutError:
                    await _cancel_and_join(batch)
                except Exception:
                    logger.warning("worker turu başarısız", extra={"context": {"stage": "drain"}})
                break
            try:
                processed = await batch
            except Exception:
                logger.warning("worker turu başarısız", extra={"context": {"stage": "drain"}})
                processed = 0
            if processed == 0:
                await _wait_for_stop(stop, poll_interval)
    finally:
        stop.set()
        if batch is not None:
            await _cancel_and_join(batch)
        await _cancel_and_join(stop_waiter)
        await _cancel_and_join(maintenance)
        await dispose()


async def _run_signal_worker() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    # Only the standalone process owns signals; API-local drain must not replace
    # Uvicorn's lifecycle handlers. Hard process loss is covered by lease expiry.
    loop.add_signal_handler(signal.SIGTERM, stop.set)
    try:
        await run_forever(stop_event=stop)
    finally:
        loop.remove_signal_handler(signal.SIGTERM)


def main() -> None:
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_run_signal_worker())


if __name__ == "__main__":
    main()
