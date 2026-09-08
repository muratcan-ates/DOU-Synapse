"""Real PostgreSQL lease tests; use only the existing isolated test-DB harness.

These are candidates, not executed by the authoring lane. OS-signal/crash proof
is a separate root-controlled process run; asyncio cancellation is not SIGKILL.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from uuid import UUID

import pytest
from sqlalchemy import text

from app import worker
from app.api import documents as documents_api
from app.core.config import get_settings
from app.modules.ingestion import claims, pipeline
from app.modules.ingestion.storage import get_storage
from tests.factories import create_course

CONTENT = b"# Synthetic source\n\nA process has its own address space."


@pytest.fixture
async def pending_source(client, users, monkeypatch):
    async def do_not_trigger():
        return None

    monkeypatch.setattr(documents_api, "_trigger_worker", do_not_trigger)
    headers = users.auth(await users.create("worker-recovery-synthetic@dogus.edu.tr"))
    course_id = await create_course(client, headers, "D2LEASE")
    response = await client.post(
        f"/courses/{course_id}/documents",
        headers=headers,
        files={"file": ("synthetic.md", CONTENT, "text/markdown")},
    )
    assert response.status_code == 202, response.text
    factory = worker._get_session_factory()
    async with factory() as session, session.begin():
        role = (
            await session.execute(
                text(
                    "SELECT current_user, rolsuper, rolbypassrls FROM pg_catalog.pg_roles "
                    "WHERE rolname = current_user"
                )
            )
        ).one()
        assert tuple(role) == ("dou_worker", False, True)
    return factory, UUID(response.json()["document"]["id"]), headers, course_id


async def take(factory):
    async with claims.transaction(factory) as session:
        return await claims.claim_next_job(session)


async def job_state(admin_engine, document_id):
    async with admin_engine.connect() as connection:
        return dict(
            (
                await connection.execute(
                    text(
                        "SELECT j.status::text, j.attempt_count, j.claim_token, "
                        "j.lease_expires_at, j.next_attempt_at, "
                        "j.last_error, d.status::text AS document_status, d.error_message, "
                        "d.ingestion_revision, (SELECT count(*) FROM chunks c "
                        "WHERE c.document_id = d.id) AS chunk_count "
                        "FROM ingestion_jobs j JOIN documents d ON d.id = j.document_id "
                        "WHERE d.id = :id"
                    ),
                    {"id": document_id},
                )
            )
            .mappings()
            .one()
        )


async def expire(admin_engine, job_id):
    # Controlled DB fixture for stale-token tests, not proof of real clock expiry.
    async with admin_engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE ingestion_jobs SET lease_expires_at = clock_timestamp() "
                "- interval '4 seconds' WHERE id = :id"
            ),
            {"id": job_id},
        )


class BarrierStorage:
    def __init__(self):
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.inner = get_storage()

    async def load(self, key):
        self.entered.set()
        await self.release.wait()
        return await self.inner.load(key)

    async def save(self, key, content):
        await self.inner.save(key, content)

    async def delete(self, key):
        await self.inner.delete(key)


async def test_two_connections_take_one_committed_claim(pending_source, admin_engine):
    factory, document_id, _, _ = pending_source
    results = await asyncio.gather(take(factory), take(factory))
    owners = [result for result in results if result is not None]
    assert len(owners) == 1
    state = await job_state(admin_engine, document_id)
    assert state["status"] == "processing"
    assert state["attempt_count"] == 1
    assert state["claim_token"] == owners[0].token
    assert state["document_status"] == "processing"


async def test_storage_wait_holds_no_document_or_job_lock(pending_source, admin_engine):
    factory, document_id, _, _ = pending_source
    storage = BarrierStorage()
    task = asyncio.create_task(pipeline.run_pending_jobs(factory, storage, limit=1))
    try:
        await asyncio.wait_for(storage.entered.wait(), 5)
        async with admin_engine.begin() as connection:
            await connection.execute(
                text("SELECT id FROM documents WHERE id = :id FOR UPDATE NOWAIT"),
                {"id": document_id},
            )
            await connection.execute(
                text("SELECT id FROM ingestion_jobs WHERE document_id = :id FOR UPDATE NOWAIT"),
                {"id": document_id},
            )
        storage.release.set()
        assert await asyncio.wait_for(task, 10) == 1
        state = await job_state(admin_engine, document_id)
        assert state["status"] == "completed" and state["chunk_count"] > 0
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


async def test_heartbeat_renews_past_original_deadline(pending_source, admin_engine, monkeypatch):
    factory, document_id, _, _ = pending_source
    settings = get_settings()
    monkeypatch.setattr(settings, "ingestion_lease_seconds", 2.0)
    monkeypatch.setattr(settings, "ingestion_heartbeat_seconds", 0.2)
    monkeypatch.setattr(settings, "ingestion_control_timeout_seconds", 0.5)
    storage = BarrierStorage()
    task = asyncio.create_task(pipeline.run_pending_jobs(factory, storage, limit=1))
    try:
        await asyncio.wait_for(storage.entered.wait(), 5)
        first = await job_state(admin_engine, document_id)
        # Observe actual PostgreSQL time crossing the original deadline; no time patch.
        async with admin_engine.connect() as connection:
            remaining = await connection.scalar(
                text("SELECT GREATEST(0, extract(epoch FROM (:deadline - clock_timestamp())))"),
                {"deadline": first["lease_expires_at"]},
            )
        await asyncio.sleep(float(remaining) + 0.15)
        renewed = await job_state(admin_engine, document_id)
        assert renewed["lease_expires_at"] > first["lease_expires_at"]
        assert renewed["claim_token"] == first["claim_token"]
        assert await take(factory) is None
        storage.release.set()
        assert await asyncio.wait_for(task, 10) == 1
        assert (await job_state(admin_engine, document_id))["status"] == "completed"
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


async def test_real_expiry_reclaims_consumed_attempt(pending_source, admin_engine, monkeypatch):
    factory, document_id, _, _ = pending_source
    settings = get_settings()
    monkeypatch.setattr(settings, "ingestion_lease_seconds", 2.0)
    monkeypatch.setattr(settings, "ingestion_heartbeat_seconds", 0.2)
    monkeypatch.setattr(settings, "ingestion_control_timeout_seconds", 0.5)
    first = await take(factory)
    assert first is not None
    assert await take(factory) is None
    before = await job_state(admin_engine, document_id)
    async with admin_engine.connect() as connection:
        remaining = await connection.scalar(
            text("SELECT GREATEST(0, extract(epoch FROM (:deadline - clock_timestamp())))"),
            {"deadline": before["lease_expires_at"]},
        )
    await asyncio.sleep(float(remaining) + 1.05)  # existing attempt1 backoff is1s
    second = await take(factory)
    assert second is not None and second.token != first.token and second.attempt == 2
    prepared = await pipeline.process_document(get_storage(), second)
    await pipeline.finalize_document(factory, second, prepared)
    after = await job_state(admin_engine, document_id)
    assert after["status"] == "completed" and after["attempt_count"] == 2
    assert after["claim_token"] is None


async def test_takeover_fences_old_success_failure_and_heartbeat(pending_source, admin_engine):
    factory, document_id, _, _ = pending_source
    first = await take(factory)
    old_output = await pipeline.process_document(get_storage(), first)
    await expire(admin_engine, first.job_id)
    second = await take(factory)
    assert second is not None and second.attempt == 2 and second.token != first.token
    before = await job_state(admin_engine, document_id)
    for stale_write in (
        pipeline.finalize_document(factory, first, old_output),
        claims.fail_claim(factory, first, claims.FailureReason.COMPUTE_FAILED),
        claims.heartbeat(factory, first),
    ):
        with pytest.raises(claims.LostClaim):
            await stale_write
        assert await job_state(admin_engine, document_id) == before
    fresh_output = await pipeline.process_document(get_storage(), second)
    await pipeline.finalize_document(factory, second, fresh_output)
    assert (await job_state(admin_engine, document_id))["status"] == "completed"


async def test_source_aba_revision_cannot_be_forged_or_written_by_old_claim(
    pending_source,
    admin_engine,
):
    factory, document_id, _, _ = pending_source
    first = await take(factory)
    output = await pipeline.process_document(get_storage(), first)
    async with admin_engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE documents SET ingestion_revision = 1, "
                "file_name = 'temporary.md' WHERE id = :id"
            ),
            {"id": document_id},
        )
        await connection.execute(
            text(
                "UPDATE documents SET ingestion_revision = 1, "
                "file_name = 'synthetic.md' WHERE id = :id"
            ),
            {"id": document_id},
        )
    before = await job_state(admin_engine, document_id)
    assert before["ingestion_revision"] == first.revision + 2
    for stale_write in (
        pipeline.finalize_document(factory, first, output),
        claims.fail_claim(factory, first, claims.FailureReason.COMPUTE_FAILED),
        claims.heartbeat(factory, first),
    ):
        with pytest.raises(claims.LostClaim):
            await stale_write
        assert await job_state(admin_engine, document_id) == before


async def test_replacement_keeps_new_document_and_old_source_intact(
    pending_source,
    admin_engine,
    client,
):
    factory, document_id, headers, course_id = pending_source
    first = await take(factory)
    output = await pipeline.process_document(get_storage(), first)
    replacement = await client.post(
        f"/courses/{course_id}/documents",
        headers=headers,
        files={
            "file": (
                "replacement.md",
                b"# Replacement\n\nDifferent course source.",
                "text/markdown",
            )
        },
        data={"replaces_document_id": str(document_id)},
    )
    assert replacement.status_code == 202, replacement.text
    for stale_write in (
        pipeline.finalize_document(factory, first, output),
        claims.fail_claim(factory, first, claims.FailureReason.COMPUTE_FAILED),
    ):
        with pytest.raises(claims.LostClaim):
            await stale_write
    new_id = UUID(replacement.json()["document"]["id"])
    await worker.drain()
    assert (await job_state(admin_engine, new_id))["status"] == "completed"
    assert (await job_state(admin_engine, document_id))["chunk_count"] == 0


async def test_cancelled_task_requeues_and_new_worker_succeeds(pending_source, admin_engine):
    factory, document_id, _, _ = pending_source
    storage = BarrierStorage()
    task = asyncio.create_task(pipeline.run_pending_jobs(factory, storage, limit=1))
    await asyncio.wait_for(storage.entered.wait(), 5)
    before = await job_state(admin_engine, document_id)
    assert before["status"] == "processing" and before["attempt_count"] == 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 5)
    cancelled = await job_state(admin_engine, document_id)
    assert cancelled["status"] == "pending" and cancelled["attempt_count"] == 1
    assert cancelled["claim_token"] is None and cancelled["last_error"] == "cancelled"
    await asyncio.sleep(1.05)
    assert await worker.drain() == 1
    completed = await job_state(admin_engine, document_id)
    assert completed["status"] == "completed" and completed["attempt_count"] == 2


async def test_three_expired_claims_stop_without_fourth_attempt(pending_source, admin_engine):
    factory, document_id, _, _ = pending_source
    for attempt in (1, 2, 3):
        claim = await take(factory)
        assert claim is not None and claim.attempt == attempt
        await expire(admin_engine, claim.job_id)
        if attempt < 3:
            # Next iteration claims the previous attempt after expiry+backoff.
            continue
    assert await take(factory) is None
    state = await job_state(admin_engine, document_id)
    assert state["status"] == state["document_status"] == "failed"
    assert state["attempt_count"] == 3 and state["claim_token"] is None
    assert state["last_error"] == "lease_expired"
    assert await worker.drain() == 0


async def test_failure_waiting_for_job_lock_cannot_release_an_expired_claim(
    pending_source,
    admin_engine,
):
    factory, document_id, _, _ = pending_source
    claim = await take(factory)
    # The shortened deadline is an explicit clock fixture; the lock wait and
    # expiry are real PostgreSQL behavior, not a mocked projection/boolean.
    async with admin_engine.begin() as connection:
        deadline = await connection.scalar(
            text(
                "UPDATE ingestion_jobs SET lease_expires_at = clock_timestamp() "
                "+ interval '400 milliseconds' WHERE id = :id RETURNING lease_expires_at"
            ),
            {"id": claim.job_id},
        )
    before = await job_state(admin_engine, document_id)
    task = None
    try:
        async with admin_engine.begin() as blocker:
            await blocker.execute(
                text("SELECT id FROM ingestion_jobs WHERE id = :id FOR UPDATE"),
                {"id": claim.job_id},
            )
            waiting_query = text(
                "SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_stat_activity a "
                "WHERE a.datname = current_database() AND a.usename = 'dou_worker' "
                "AND a.wait_event_type = 'Lock' AND a.query LIKE '%FOR UPDATE%' "
                "AND pg_catalog.pg_backend_pid() = ANY(pg_catalog.pg_blocking_pids(a.pid)))"
            )
            # Prime the observer before the worker starts. Reusing this cached
            # activity snapshot would otherwise hide a waiter that appears later.
            assert await blocker.scalar(waiting_query) is False
            task = asyncio.create_task(
                claims.fail_claim(factory, claim, claims.FailureReason.CANCELLED)
            )
            async with asyncio.timeout(0.8):
                while True:
                    # Same transaction retains the job lock; only refresh the
                    # statistics observer, not the source/job snapshot or clock.
                    await blocker.execute(text("SELECT pg_catalog.pg_stat_clear_snapshot()"))
                    waiting = await blocker.scalar(waiting_query)
                    if waiting:
                        break
                    await asyncio.sleep(0.005)
                assert (
                    await blocker.scalar(
                        text("SELECT clock_timestamp() < :deadline"), {"deadline": deadline}
                    )
                    is True
                )
                while not await blocker.scalar(  # noqa: ASYNC110 - observing external DB clock
                    text("SELECT clock_timestamp() > :deadline"), {"deadline": deadline}
                ):
                    await asyncio.sleep(0.005)
        # Releasing the blocker must not recycle the pre-wait live projection.
        with pytest.raises(claims.LostClaim):
            await asyncio.wait_for(task, 2)
        assert await job_state(admin_engine, document_id) == before
    finally:
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError, claims.LostClaim):
                await task
