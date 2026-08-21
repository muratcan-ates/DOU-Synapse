"""Persistent, content-free token reservation for the course agent.

Reservations run in short independent transactions. This keeps the database
lock out of slow provider I/O while still making concurrent quota decisions
atomic across API workers.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import text

from app.contracts import AssistantAudience
from app.core.db import control_rls_session as rls_session
from app.core.logging import get_logger

logger = get_logger("app.agent.quota")

_EVENT_DEDUP_LIMIT = 10_000
_event_buckets: dict[tuple[UUID, UUID, str], int] = {}


@dataclass(frozen=True, slots=True)
class TokenReservation:
    allowed: bool
    reason: str | None
    audience: AssistantAudience
    retry_after_seconds: int
    reservation_id: UUID | None


async def reserve(
    *,
    user_id: UUID,
    course_id: UUID,
    requested_tokens: int,
    lease_seconds: int,
    user_hard_limit: int,
    course_hard_limit: int,
    platform_hard_limit: int,
) -> TokenReservation:
    reservation_id = uuid4()
    async with rls_session(user_id) as session:
        row = (
            await session.execute(
                text(
                    "SELECT * FROM app.reserve_course_agent_tokens("
                    ":course_id, :reservation_id, :requested_tokens, :lease_seconds, "
                    ":user_hard_limit, :course_hard_limit, :platform_hard_limit)"
                ),
                {
                    "course_id": course_id,
                    "reservation_id": reservation_id,
                    "requested_tokens": requested_tokens,
                    "lease_seconds": lease_seconds,
                    "user_hard_limit": user_hard_limit,
                    "course_hard_limit": course_hard_limit,
                    "platform_hard_limit": platform_hard_limit,
                },
            )
        ).one()
    return TokenReservation(
        allowed=bool(row.allowed),
        reason=row.reason,
        audience=AssistantAudience(row.audience),
        retry_after_seconds=int(row.retry_after_seconds or 0),
        reservation_id=row.reservation_id,
    )


async def reconcile(*, user_id: UUID, reservation_id: UUID, actual_tokens: int) -> None:
    try:
        async with rls_session(user_id) as session:
            await session.execute(
                text("SELECT app.reconcile_course_agent_tokens(:reservation_id, :actual_tokens)"),
                {"reservation_id": reservation_id, "actual_tokens": max(0, actual_tokens)},
            )
    except Exception as exc:
        # Reservations are precharged at their conservative maximum. A refund
        # failure therefore retains the safe charge, but it must not discard a
        # successful answer or mask the original provider error with a DB 500.
        logger.warning(
            "course agent token reservation could not be reconciled",
            extra={"context": {"error": type(exc).__name__}},
        )


async def record_guard_event(*, user_id: UUID, course_id: UUID, event_type: str) -> None:
    bucket = int(time.monotonic() // 60)
    key = (user_id, course_id, event_type)
    if _event_buckets.get(key) == bucket:
        return
    _event_buckets[key] = bucket
    if len(_event_buckets) > _EVENT_DEDUP_LIMIT:
        stale_before = bucket - 1
        for stale_key, seen_bucket in list(_event_buckets.items()):
            if seen_bucket < stale_before:
                del _event_buckets[stale_key]
    try:
        async with rls_session(user_id) as session:
            await session.execute(
                text("SELECT app.record_course_agent_guard_event(:course_id, :event_type)"),
                {"course_id": course_id, "event_type": event_type},
            )
    except Exception as exc:
        # Telemetry is deliberately best-effort: a logging database incident
        # must never turn an otherwise deterministic abuse refusal into a 500.
        logger.warning(
            "course agent guard event could not be recorded",
            extra={"context": {"event_type": event_type, "error": type(exc).__name__}},
        )


__all__ = ["TokenReservation", "reconcile", "record_guard_event", "reserve"]
