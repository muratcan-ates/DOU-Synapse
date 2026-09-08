"""Real-role admission, rollback, readiness and expiry contracts on the isolated test DB."""

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from app import worker
from app.core.config import get_settings
from app.core.db import rls_session
from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.request_quota import RequestQuotaUnavailableError, take_request_slot
from app.core.request_quota_maintenance import purge_expired_request_windows
from tests.conftest import UserFactory
from tests.factories import create_course, enroll_student


async def context(client: AsyncClient, users: UserFactory) -> tuple[UUID, UUID]:
    actor = await users.create(f"quota-{uuid4()}@example.com")
    course = await create_course(client, users.auth(actor), "QUOTA")
    return actor, course


async def add_student(client, users, owner, course):
    email = f"student-{uuid4()}@example.com"
    actor = await users.create(email)
    await enroll_student(client, users.auth(owner), course, email)
    return actor


async def take(actor: UUID, course: UUID):
    return await take_request_slot(
        user_id=actor, course_id=course, scope="chat", limit=20, window_seconds=60
    )


async def window(engine: AsyncEngine, actor: UUID, course: UUID):
    async with engine.connect() as connection:
        return (
            (
                await connection.execute(
                    text(
                        "SELECT accepted_at,expires_at,policy_fingerprint FROM app.rate_lim"
                        "it_windows "
                        "WHERE scope='chat' AND user_id=:actor AND course_id=:course"
                    ),
                    {"actor": actor, "course": course},
                )
            )
            .mappings()
            .one_or_none()
        )


async def test_independent_committed_slot_survives_main_rollback(client, users, admin_engine):
    actor, course = await context(client, users)
    with pytest.raises(RuntimeError, match="synthetic main rollback"):
        async with rls_session(actor) as main:
            await main.execute(
                text("UPDATE courses SET title='Synthetic rolled back' WHERE id=:id"),
                {"id": course},
            )
            assert (await take(actor, course)).allowed
            raise RuntimeError("synthetic main rollback")
    assert len((await window(admin_engine, actor, course))["accepted_at"]) == 1
    response = await client.get(f"/courses/{course}", headers=users.auth(actor))
    assert response.status_code == 200
    assert response.json()["title"] != "Synthetic rolled back"


async def test_denial_preserves_window_and_expired_hits_are_replaced(client, users, admin_engine):
    actor, course = await context(client, users)
    for _ in range(20):
        assert (await take(actor, course)).allowed
    before = dict(await window(admin_engine, actor, course))
    denied = await take(actor, course)
    assert not denied.allowed and 1 <= denied.retry_after_seconds <= 60
    assert dict(await window(admin_engine, actor, course)) == before
    async with admin_engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE app.rate_limit_windows SET accepted_at=ARRAY[clock_timestam"
                "p()-interval '61 seconds'], "
                "expires_at=clock_timestamp()-interval '1 second' WHERE user_id=:ac"
                "tor AND course_id=:course"
            ),
            {"actor": actor, "course": course},
        )
    assert (await take(actor, course)).allowed
    assert len((await window(admin_engine, actor, course))["accepted_at"]) == 1


async def test_mismatched_worker_policy_fails_closed_and_readiness_recovers(
    client, users, admin_engine, monkeypatch
):
    actor, course = await context(client, users)
    with monkeypatch.context() as patch:
        patch.setattr(get_settings(), "chat_rate_limit_requests", 21)
        response = await client.post(
            f"/courses/{course}/chat",
            headers=users.auth(actor),
            json={"question": "Synthetic policy mismatch"},
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "rate_limit_unavailable"
        assert response.headers["Retry-After"] == "1"
        assert await window(admin_engine, actor, course) is None
        ready = await client.get("/health/ready")
        assert ready.status_code == 503
        assert ready.json()["checks"]["request_quota"] == "error"
        assert (await client.get("/health/live")).status_code == 200
    ready = await client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["checks"]["request_quota"] == "ok"
    assert await window(admin_engine, actor, course) is None  # readiness never admits
    assert (await take(actor, course)).allowed


async def test_sql_rechecks_membership_and_instructor_and_denies_direct_table_access(
    client, users, admin_engine
):
    actor, course = await context(client, users)
    student = await add_student(client, users, actor, course)
    with pytest.raises(PermissionDeniedError):
        await take_request_slot(
            user_id=student, course_id=course, scope="qgen", limit=5, window_seconds=300
        )
    with pytest.raises(NotFoundError):
        await take(uuid4(), course)
    assert await window(admin_engine, student, course) is None
    assert (await take(student, course)).allowed
    before = dict(await window(admin_engine, student, course))
    async with admin_engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE course_memberships SET status='revoked' WHERE user_id=:acto"
                "r AND course_id=:course"
            ),
            {"actor": student, "course": course},
        )
    with pytest.raises(NotFoundError):
        await take(student, course)
    assert dict(await window(admin_engine, student, course)) == before
    for statement in [
        "SELECT * FROM app.rate_limit_windows",
        "UPDATE app.request_rate_policies SET request_limit=100",
        "SELECT app.purge_expired_request_windows(1)",
    ]:
        with pytest.raises(DBAPIError) as caught:
            async with rls_session(actor) as session:
                await session.execute(text(statement))
        assert caught.value.orig.sqlstate == "42501"


async def test_locked_admission_fails_closed_without_blocking_other_actor(
    client, users, admin_engine
):
    actor, course = await context(client, users)
    other = await add_student(client, users, actor, course)
    async with admin_engine.begin() as blocker:
        await blocker.execute(
            text("SELECT pg_advisory_xact_lock(15023,hashtext(:key))"),
            {"key": f"chat:{actor}:{course}"},
        )
        with pytest.raises(RequestQuotaUnavailableError) as caught:
            await take(actor, course)
        assert caught.value.headers == {"Retry-After": "1"}
        assert await window(admin_engine, actor, course) is None
        assert (await take(other, course)).allowed
    assert (await take(actor, course)).allowed


async def test_worker_purge_skips_locked_and_live_windows_then_cascade_cleans(
    client, users, admin_engine
):
    actor, course = await context(client, users)
    others = [await add_student(client, users, actor, course) for _ in range(2)]
    for user_id in [actor, *others]:
        assert (await take(user_id, course)).allowed
    async with admin_engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE app.rate_limit_windows SET accepted_at=ARRAY[clock_timestam"
                "p()-interval '120 seconds'], expires_at=clock_timestamp()-interval"
                " '60 seconds' WHERE user_id=ANY(:actors) AND course_id=:course"
            ),
            {"actors": [actor, others[0]], "course": course},
        )
    factory = worker._get_session_factory()
    async with admin_engine.begin() as blocker:
        await blocker.execute(
            text(
                "SELECT 1 FROM app.rate_limit_windows WHERE user_id=:actor AND cour"
                "se_id=:course FOR UPDATE"
            ),
            {"actor": actor, "course": course},
        )
        assert await purge_expired_request_windows(factory, batch_size=1) == 1
        assert await window(admin_engine, actor, course) is not None
        assert await window(admin_engine, others[0], course) is None
        assert await window(admin_engine, others[1], course) is not None
    assert await purge_expired_request_windows(factory, batch_size=1) == 1
    assert await window(admin_engine, others[1], course) is not None
    async with admin_engine.begin() as connection:
        await connection.execute(text("DELETE FROM courses WHERE id=:course"), {"course": course})
    assert await window(admin_engine, others[1], course) is None
