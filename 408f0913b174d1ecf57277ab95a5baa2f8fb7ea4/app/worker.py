"""Ingestion worker'ı.

İki çalışma biçimi vardır:

* `python -m app.worker` — yerel geliştirme ve Docker Compose için sürekli döngü.
* `drain()` — API tarafından tetiklenen tek tur. Azure Container Apps'te worker
  scale-to-zero ile uyuduğu için sürekli poll eden bir döngü çalışmaz; yükleme
  tamamlandığında worker HTTP ile uyandırılır (ARCHITECTURE.md §1, arka plan işleri).

Worker `dou_worker` rolüyle bağlanır: bu rol RLS'i atlar, çünkü `chunks` tablosunda
hiçbir INSERT politikası yoktur ve yazma yetkisi yalnızca ona aittir.
"""

from __future__ import annotations

import asyncio
import contextlib

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.modules.ingestion.pipeline import run_pending_jobs
from app.modules.ingestion.storage import get_storage

logger = get_logger("app.worker")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None

POLL_INTERVAL_SECONDS = 2.0


def _get_session_factory() -> async_sessionmaker:
    global _engine, _session_factory
    if _session_factory is None:
        settings = get_settings()
        # Worker URL'i tanımlı değilse API bağlantısına düşeriz; bu durumda chunks
        # yazımı RLS'e takılır ve hata açıkça görünür — sessizce yanlış çalışmaz.
        dsn = str(settings.worker_database_url or settings.database_url)
        _engine = create_async_engine(dsn, pool_size=2, max_overflow=2, pool_pre_ping=True)
        _session_factory = async_sessionmaker(bind=_engine, expire_on_commit=False)
    return _session_factory


async def dispose() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


async def drain(limit: int | None = None) -> int:
    """Bekleyen işleri bir tur işler; işlenen iş sayısını döndürür."""
    settings = get_settings()
    return await run_pending_jobs(
        _get_session_factory(),
        get_storage(),
        limit=limit if limit is not None else settings.worker_batch_size,
    )


async def run_forever(poll_interval: float = POLL_INTERVAL_SECONDS) -> None:
    configure_logging()
    logger.info("worker başlatıldı")
    try:
        while True:
            try:
                processed = await drain()
            except Exception:
                logger.exception("worker turu başarısız")
                processed = 0
            if processed == 0:
                await asyncio.sleep(poll_interval)
    finally:
        await dispose()


def main() -> None:
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run_forever())


if __name__ == "__main__":
    main()
