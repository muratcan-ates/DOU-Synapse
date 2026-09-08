"""Shared, read-only dependency snapshot for public readiness and admin status.

Admin callers reuse their authorized session. This avoids borrowing another
application connection while holding the overview transaction open. No user,
course, admission, provider or storage operation is performed here.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.core.logging import get_logger
from app.core.request_quota import request_quota_is_ready
from app.core.warmup import warmup_is_ready, warmup_state

logger = get_logger("app.health")


class ReadinessSnapshot(TypedDict):
    status: Literal["ok", "degraded"]
    checks: dict[str, str]


async def _database_checks(session: AsyncSession) -> dict[str, str]:
    # A successful extension-catalog query also proves this DB is reachable.
    vector_ready = await session.scalar(
        text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
    )
    return {"database": "ok", "pgvector": "ok" if vector_ready else "missing"}


async def check_readiness(session: AsyncSession | None = None) -> ReadinessSnapshot:
    """Observe current dependencies without admitting work or exposing data.

    This is a current observation, not an atomic service-availability promise.
    Admin authentication/overview SQL may fail before reaching this function;
    that failure must not be replaced with fabricated empty admin totals.
    """
    try:
        if session is None:
            factory = get_session_factory()
            async with factory() as probe_session:
                checks = await _database_checks(probe_session)
        else:
            checks = await _database_checks(session)
    except Exception as exc:
        logger.warning(
            "hazırlık kontrolü başarısız",
            extra={"context": {"error_type": type(exc).__name__, "stage": "database_probe"}},
        )
        checks = {"database": "error"}

    checks["request_quota"] = "ok" if await request_quota_is_ready(get_settings()) else "error"
    embedding_status = warmup_state()
    checks["embedding"] = embedding_status
    healthy = (
        checks.get("database") == "ok"
        and checks.get("pgvector") == "ok"
        and checks.get("request_quota") == "ok"
        and warmup_is_ready(embedding_status)
    )
    return {"status": "ok" if healthy else "degraded", "checks": checks}
