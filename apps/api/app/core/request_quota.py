"""PostgreSQL request admission; independent of provider/token accounting.

The control transaction has finished committing before this module returns an
accepted slot. The caller must not move its provider work inside this context.
Policy fingerprints are comparisons, never new budget keys. No local fallback.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import control_rls_session
from app.core.errors import AppError, NotFoundError, PermissionDeniedError

Scope = Literal["chat", "qgen"]
CONTROL_TIMEOUT_SECONDS = 1.0
LOCK_TIMEOUT_MS = 250
STATEMENT_TIMEOUT_MS = 500
UNAVAILABLE_RETRY_SECONDS = 1


class RequestQuotaUnavailableError(AppError):
    status_code = 503
    code = "rate_limit_unavailable"

    def __init__(self) -> None:
        super().__init__(
            "İstek kotası şu anda doğrulanamıyor. Kısa bir süre sonra tekrar deneyebilirsin.",
            headers={"Retry-After": str(UNAVAILABLE_RETRY_SECONDS)},
        )


@dataclass(frozen=True)
class RequestPolicy:
    scope: Scope
    limit: int
    window_ms: int
    fingerprint: str

    @classmethod
    def from_seconds(cls, scope: Scope, limit: int, seconds: float) -> RequestPolicy:
        # Millisecond precision is explicit, not binary-float string hashing.
        # Rejecting unsupported inputs must not silently create a new budget.
        if scope not in ("chat", "qgen") or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("invalid request policy")
        try:
            milliseconds = Decimal(str(seconds)) * 1000
        except (InvalidOperation, ValueError):
            raise ValueError("invalid request policy") from None
        if (
            not milliseconds.is_finite()
            or not 1 <= milliseconds <= 3_600_000
            or milliseconds != milliseconds.to_integral_value()
        ):
            raise ValueError("invalid request policy")
        window_ms = int(milliseconds)
        fingerprint = hashlib.sha256(f"{scope}:{limit}:{window_ms}".encode("ascii")).hexdigest()
        return cls(scope, limit, window_ms, fingerprint)


@dataclass(frozen=True)
class RequestAdmission:
    allowed: bool
    retry_after_seconds: int


async def _timeouts(session: AsyncSession) -> None:
    await session.execute(
        text(
            "SELECT pg_catalog.set_config('lock_timeout', :lock_timeout, true), "
            "pg_catalog.set_config('statement_timeout', :statement_timeout, true)"
        ),
        {
            "lock_timeout": f"{LOCK_TIMEOUT_MS}ms",
            "statement_timeout": f"{STATEMENT_TIMEOUT_MS}ms",
        },
    )


async def take_request_slot(
    *, user_id: UUID, course_id: UUID, scope: Scope, limit: int, window_seconds: float
) -> RequestAdmission:
    """Return only after commit. Failures reveal no DB error/identity/credential.

    Cancellation propagates; a possibly committed request is never blindly
    retried. The outer timeout covers pool acquisition, GUC setup and commit,
    while SQL's local timeouts bound lock/statement work. Cancellation cleanup
    can take additional driver time; 1s is a deadline, not a measured hard SLA.
    """
    try:
        policy = RequestPolicy.from_seconds(scope, limit, window_seconds)
        async with asyncio.timeout(CONTROL_TIMEOUT_SECONDS):
            async with control_rls_session(user_id) as session:
                await _timeouts(session)
                result = await session.execute(
                    text(
                        "SELECT allowed, reason, retry_after_seconds "
                        "FROM app.take_request_slot("
                        ":course_id, :scope, :limit, :window_ms, :fingerprint)"
                    ),
                    {
                        "course_id": course_id,
                        "scope": policy.scope,
                        "limit": policy.limit,
                        "window_ms": policy.window_ms,
                        "fingerprint": policy.fingerprint,
                    },
                )
                row = result.mappings().one()
                allowed = row["allowed"]
                reason = row["reason"]
                retry = row["retry_after_seconds"]
                # Validate before committing; no malformed truthy value grants access.
                if type(allowed) is not bool or type(retry) is not int:
                    raise ValueError("invalid request admission")
                if (allowed, reason, retry) == (True, "accepted", 0):
                    decision = RequestAdmission(True, 0)
                elif allowed is False and reason == "rate_limited" and 1 <= retry <= 3600:
                    decision = RequestAdmission(False, retry)
                elif allowed is False and retry == 0 and reason in ("not_member", "not_instructor"):
                    decision = None
                else:
                    # Includes policy_mismatch; a control problem is not quota exhaustion.
                    raise ValueError("request quota not ready")
        # This is intentionally AFTER the independent transaction's __aexit__.
    except Exception:
        raise RequestQuotaUnavailableError() from None
    if decision is not None:
        return decision
    if reason == "not_instructor":
        raise PermissionDeniedError("Bu işlem için derste eğitmen olmalısın.")
    raise NotFoundError("Ders bulunamadı.")


async def request_quota_is_ready(settings: Settings) -> bool:
    """Read canonical policies without consuming a slot or fabricating a user row."""
    try:
        expected = {
            "chat": RequestPolicy.from_seconds(
                "chat",
                settings.chat_rate_limit_requests,
                settings.chat_rate_limit_window_seconds,
            ).fingerprint,
            "qgen": RequestPolicy.from_seconds(
                "qgen",
                settings.question_gen_rate_limit_requests,
                settings.question_gen_rate_limit_window_seconds,
            ).fingerprint,
        }
        async with asyncio.timeout(CONTROL_TIMEOUT_SECONDS):
            # No user is required by the read-only, non-personal policy projection.
            async with control_rls_session(UUID(int=0)) as session:
                await _timeouts(session)
                result = await session.execute(text("SELECT * FROM app.request_quota_policies()"))
                rows = result.mappings().all()
                observed = {row["scope"]: row["fingerprint"] for row in rows}
                return len(rows) == 2 and observed == expected
    except Exception:
        return False
