"""Bounded expired-row maintenance, to be called by the existing worker lifecycle.

There is no schedule in this module. Expiry is logical; physical deletion occurs
only when this function runs successfully. Zero replicas require an external
scheduled wakeup. Do not report a maximum physical retention time without one.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.request_quota import CONTROL_TIMEOUT_SECONDS, _timeouts


class RequestQuotaMaintenanceError(Exception):
    """Fixed, content-free failure; no raw DB exception reaches worker logging."""


async def purge_expired_request_windows(
    factory: async_sessionmaker[AsyncSession], *, batch_size: int = 500
) -> int:
    if type(batch_size) is not int or not 1 <= batch_size <= 1000:
        raise ValueError("invalid quota maintenance batch")
    try:
        async with asyncio.timeout(CONTROL_TIMEOUT_SECONDS):
            async with factory() as session, session.begin():
                await _timeouts(session)
                count = await session.scalar(
                    text("SELECT app.purge_expired_request_windows(:batch_size)"),
                    {"batch_size": batch_size},
                )
                if type(count) is not int or not 0 <= count <= batch_size:
                    raise ValueError("invalid quota maintenance result")
        return count
    except Exception:
        raise RequestQuotaMaintenanceError("request quota maintenance unavailable") from None
