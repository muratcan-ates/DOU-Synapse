"""Finite ingestion claims. No storage/provider I/O belongs in these transactions."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings

MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS: tuple[float, ...] = (1.0, 3.0)
CANDIDATE_SCAN_LIMIT = 32
DOCUMENT_FAILURE_MESSAGE = "Belge işlenemedi. Lütfen yeniden deneyin."


class FailureReason(StrEnum):
    COMPUTE_FAILED = "compute_failed"
    SOURCE_HASH_MISMATCH = "source_hash_mismatch"
    SOURCE_CHANGED = "source_changed"
    LEASE_EXPIRED = "lease_expired"
    CANCELLED = "cancelled"


class LostClaim(Exception):
    """Current job/document authority is unavailable; never carries source data."""


@dataclass(frozen=True, slots=True)
class Claim:
    job_id: UUID
    document_id: UUID
    token: UUID
    attempt: int
    revision: int
    course_id: UUID
    file_type: str
    storage_path: str
    file_hash: str
    byte_size: int


def retry_delay(attempt: int) -> float | None:
    if not 1 <= attempt <= MAX_ATTEMPTS:
        raise ValueError("invalid ingestion attempt")
    return None if attempt == MAX_ATTEMPTS else RETRY_BACKOFF_SECONDS[attempt - 1]


@asynccontextmanager
async def transaction(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Includes pool acquisition and commit in a finite control budget."""
    seconds = get_settings().ingestion_control_timeout_seconds
    async with asyncio.timeout(seconds):
        async with factory() as session, session.begin():
            await session.execute(
                text(
                    "SELECT pg_catalog.set_config('lock_timeout', :lock, true), "
                    "pg_catalog.set_config('statement_timeout', :statement, true)"
                ),
                {"lock": f"{int(seconds * 200)}ms", "statement": f"{int(seconds * 800)}ms"},
            )
            yield session


async def _lock_document(
    session: AsyncSession, document_id: UUID, *, skip_locked: bool = False
) -> Any:
    suffix = " SKIP LOCKED" if skip_locked else ""
    return (
        (
            await session.execute(
                text(
                    "SELECT id, course_id, file_type, storage_path, file_hash, byte_size, "  # noqa: S608 - fixed SQL suffix
                    "ingestion_revision, superseded_at FROM public.documents "
                    "WHERE id = :id FOR UPDATE" + suffix
                ),
                {"id": document_id},
            )
        )
        .mappings()
        .one_or_none()
    )


async def _lock_job(
    session: AsyncSession, job_id: UUID, document_id: UUID, *, skip_locked: bool = False
) -> Any:
    suffix = " SKIP LOCKED" if skip_locked else ""
    row = (
        (
            await session.execute(
                text(
                    "SELECT * FROM public.ingestion_jobs WHERE id = :id "  # noqa: S608 - fixed SQL suffix
                    "AND document_id = :document_id FOR UPDATE" + suffix
                ),
                {"id": job_id, "document_id": document_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    # SELECT projections can run before LockRows waits. A separate statement
    # here reads DB time only after this transaction actually owns the row lock.
    locked_at = await session.scalar(text("SELECT pg_catalog.clock_timestamp()"))
    return {
        **row,
        "lease_live": row["lease_expires_at"] is not None and row["lease_expires_at"] > locked_at,
        "due": row["next_attempt_at"] <= locked_at,
    }


async def lock_claim(session: AsyncSession, claim: Claim) -> None:
    """Document→job lock order also serializes deletion and supersession."""
    document = await _lock_document(session, claim.document_id)
    if document is None:
        raise LostClaim()
    job = await _lock_job(session, claim.job_id, claim.document_id)
    if (
        job is None
        or job["status"] != "processing"
        or job["claim_token"] != claim.token
        or not job["lease_live"]
        or job["claim_document_revision"] != claim.revision
        or document["ingestion_revision"] != claim.revision
        or document["course_id"] != claim.course_id
        or document["superseded_at"] is not None
    ):
        raise LostClaim()


async def assert_live_token(session: AsyncSession, claim: Claim) -> None:
    """After chunk writes, expiry causes their transaction to roll back as well."""
    live = await session.scalar(
        text(
            "SELECT EXISTS (SELECT 1 FROM public.ingestion_jobs WHERE id = :id "
            "AND status = 'processing' AND claim_token = :token "
            "AND claim_document_revision = :revision "
            "AND lease_expires_at > pg_catalog.clock_timestamp())"
        ),
        {"id": claim.job_id, "token": claim.token, "revision": claim.revision},
    )
    if live is not True:
        raise LostClaim()


async def _retire_changed_job(session: AsyncSession, job_id: UUID) -> None:
    # Caller holds document+job locks. This must never touch a changed document.
    await session.execute(
        text(
            "UPDATE public.ingestion_jobs SET status = 'failed', "
            "last_error = :reason, completed_at = pg_catalog.clock_timestamp(), "
            "claim_token = NULL, claim_document_revision = NULL, lease_expires_at = NULL "
            "WHERE id = :id"
        ),
        {"id": job_id, "reason": FailureReason.SOURCE_CHANGED.value},
    )


async def _record_failure(
    session: AsyncSession,
    *,
    job_id: UUID,
    document_id: UUID,
    attempt: int,
    reason: FailureReason,
    expired: bool = False,
    token: UUID | None = None,
) -> float | None:
    # Only called while current authority locks are held. No raw exception input.
    delay = retry_delay(attempt)
    released = await session.scalar(
        text(
            "UPDATE public.ingestion_jobs SET status = CAST(:status AS public.job_status), "
            "last_error = :reason, completed_at = CASE WHEN :exhausted "
            "THEN pg_catalog.clock_timestamp() END, "
            "next_attempt_at = CASE WHEN :exhausted THEN next_attempt_at ELSE "
            "(CASE WHEN :expired THEN lease_expires_at ELSE pg_catalog.clock_timestamp() END) "
            "+ pg_catalog.make_interval(secs => :delay_seconds) END, "
            "claim_token = NULL, claim_document_revision = NULL, lease_expires_at = NULL "
            "WHERE id = :id AND (CAST(:token AS uuid) IS NULL OR "
            "(status = 'processing' AND claim_token = CAST(:token AS uuid) "
            "AND lease_expires_at > pg_catalog.clock_timestamp())) RETURNING id"
        ),
        {
            "id": job_id,
            "token": token,
            "status": "failed" if delay is None else "pending",
            "reason": reason.value,
            "exhausted": delay is None,
            "expired": expired,
            "delay_seconds": delay or 0,
        },
    )
    if released is None:
        raise LostClaim()
    await session.execute(
        text(
            "UPDATE public.documents SET status = CAST(:status AS public.document_status), "
            "error_message = :error, updated_at = pg_catalog.clock_timestamp() WHERE id = :id"
        ),
        {
            "id": document_id,
            "status": "failed" if delay is None else "uploaded",
            "error": DOCUMENT_FAILURE_MESSAGE if delay is None else None,
        },
    )
    return delay


async def claim_next_job(session: AsyncSession) -> Claim | None:
    """Reclaim expired work and take one due job without waiting for busy rows."""
    candidates = (
        (
            await session.execute(
                text(
                    "SELECT id, document_id FROM public.ingestion_jobs WHERE "
                    "(status = 'pending' AND next_attempt_at <= pg_catalog.clock_timestamp()) "
                    "OR (status = 'processing' "
                    "AND lease_expires_at <= pg_catalog.clock_timestamp()) "
                    "ORDER BY CASE WHEN status = 'processing' THEN lease_expires_at "
                    "ELSE next_attempt_at END, created_at, id LIMIT :scan_limit"
                ),
                {"scan_limit": CANDIDATE_SCAN_LIMIT},
            )
        )
        .mappings()
        .all()
    )
    for candidate in candidates:
        document = await _lock_document(session, candidate["document_id"], skip_locked=True)
        if document is None:
            continue
        job = await _lock_job(session, candidate["id"], candidate["document_id"], skip_locked=True)
        if job is None or job["status"] not in {"pending", "processing"}:
            continue
        if job["status"] == "processing" and job["lease_live"]:
            continue
        if job["status"] == "pending" and not job["due"]:
            continue
        if document["superseded_at"] is not None or (
            job["status"] == "processing"
            and job["claim_document_revision"] != document["ingestion_revision"]
        ):
            await _retire_changed_job(session, job["id"])
            continue
        if job["status"] == "processing":
            delay = await _record_failure(
                session,
                job_id=job["id"],
                document_id=job["document_id"],
                attempt=job["attempt_count"],
                reason=FailureReason.LEASE_EXPIRED,
                expired=True,
            )
            if delay is None:
                continue
            # Re-read due using DB time. Expiry+backoff may already be in the past.
            job = await _lock_job(session, job["id"], job["document_id"])
            if not job["due"]:
                continue
        if job["attempt_count"] >= MAX_ATTEMPTS:
            # Defensive legacy pending row, never grant a fourth automatic attempt.
            await _record_failure(
                session,
                job_id=job["id"],
                document_id=job["document_id"],
                attempt=MAX_ATTEMPTS,
                reason=FailureReason.LEASE_EXPIRED,
            )
            continue
        token = uuid4()
        attempt = job["attempt_count"] + 1
        await session.execute(
            text(
                "UPDATE public.ingestion_jobs SET status = 'processing', "
                "attempt_count = :attempt, started_at = pg_catalog.clock_timestamp(), "
                "completed_at = NULL, claim_token = :token, claim_document_revision = :revision, "
                "lease_expires_at = pg_catalog.clock_timestamp() "
                "+ pg_catalog.make_interval(secs => :lease) WHERE id = :id"
            ),
            {
                "id": job["id"],
                "attempt": attempt,
                "token": token,
                "revision": document["ingestion_revision"],
                "lease": get_settings().ingestion_lease_seconds,
            },
        )
        await session.execute(
            text(
                "UPDATE public.documents SET status = 'processing', error_message = NULL, "
                "updated_at = pg_catalog.clock_timestamp() WHERE id = :id"
            ),
            {"id": document["id"]},
        )
        return Claim(
            job["id"],
            document["id"],
            token,
            attempt,
            document["ingestion_revision"],
            document["course_id"],
            document["file_type"],
            document["storage_path"],
            document["file_hash"],
            document["byte_size"],
        )
    return None


async def verify_claim(factory: async_sessionmaker[AsyncSession], claim: Claim) -> None:
    async with transaction(factory) as session:
        await lock_claim(session, claim)


async def heartbeat(factory: async_sessionmaker[AsyncSession], claim: Claim) -> None:
    async with transaction(factory) as session:
        await lock_claim(session, claim)
        # A delayed heartbeat must not resurrect an already-expired token.
        renewed = await session.scalar(
            text(
                "UPDATE public.ingestion_jobs SET lease_expires_at = "
                "pg_catalog.clock_timestamp() + pg_catalog.make_interval(secs => :lease) "
                "WHERE id = :id AND claim_token = :token AND status = 'processing' "
                "AND lease_expires_at > pg_catalog.clock_timestamp() RETURNING id"
            ),
            {
                "id": claim.job_id,
                "token": claim.token,
                "lease": get_settings().ingestion_lease_seconds,
            },
        )
        if renewed is None:
            raise LostClaim()


async def fail_claim(
    factory: async_sessionmaker[AsyncSession], claim: Claim, reason: FailureReason
) -> float | None:
    if not isinstance(reason, FailureReason):
        raise ValueError("invalid ingestion failure reason")
    async with transaction(factory) as session:
        await lock_claim(session, claim)
        return await _record_failure(
            session,
            job_id=claim.job_id,
            document_id=claim.document_id,
            attempt=claim.attempt,
            reason=reason,
            token=claim.token,
        )
