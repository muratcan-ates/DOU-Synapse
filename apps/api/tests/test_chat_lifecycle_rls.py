"""Real dou_app RLS and direct-SQL boundaries for deletion revisions."""

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.db import rls_session
from app.modules.chat import lifecycle
from tests.conftest import WORKER_DSN, UserFactory
from tests.factories import create_course


async def _seed(client: AsyncClient, users: UserFactory) -> tuple[UUID, UUID, UUID]:
    owner = await users.create("revision-owner@example.invalid")
    peer = await users.create("revision-peer@example.invalid")
    course = await create_course(client, users.auth(owner), "REVISION-RLS")
    return owner, peer, course


async def test_revision_scope_is_unique_and_monotonic_with_null_global_scope(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    owner, peer, course = await _seed(client, users)
    async with rls_session(owner) as db:
        await lifecycle.acquire_user_chat_lock(db, user_id=owner)
        assert await lifecycle.read_revision(db, user_id=owner, course_id=course) == (
            lifecycle.PrivacyRevision(0, 0)
        )
        for scope in [None, course, None, course]:
            await lifecycle.advance_revision(db, user_id=owner, course_id=scope)
        assert await lifecycle.read_revision(db, user_id=owner, course_id=course) == (
            lifecycle.PrivacyRevision(2, 2)
        )
    async with admin_engine.connect() as conn:
        assert await conn.scalar(text("SELECT count(*) FROM chat_privacy_revisions")) == 2
    async with rls_session(peer) as db:
        assert await db.scalar(text("SELECT count(*) FROM chat_privacy_revisions")) == 0
        result = await db.execute(
            text("UPDATE chat_privacy_revisions SET revision=revision+1 WHERE user_id=:owner"),
            {"owner": owner},
        )
        assert result.rowcount == 0


@pytest.mark.parametrize("attack", ["cross_user", "nonmember_course", "initial_revision"])
async def test_direct_insert_cannot_create_foreign_or_chosen_revision(
    client: AsyncClient,
    users: UserFactory,
    attack: str,
) -> None:
    owner, peer, course = await _seed(client, users)
    with pytest.raises(DBAPIError):
        async with rls_session(peer) as db:
            await db.execute(
                text(
                    "INSERT INTO chat_privacy_revisions (user_id,course_id,revision) "
                    "VALUES (:user_id,:course_id,:revision)"
                ),
                {
                    "user_id": owner if attack == "cross_user" else peer,
                    "course_id": course if attack == "nonmember_course" else None,
                    "revision": 2 if attack == "initial_revision" else 1,
                },
            )


@pytest.mark.parametrize("attack", ["lower", "skip", "delete", "move_scope", "truncate"])
async def test_direct_sql_cannot_reset_remove_or_move_own_revision(
    client: AsyncClient,
    users: UserFactory,
    attack: str,
) -> None:
    owner, _, course = await _seed(client, users)
    async with rls_session(owner) as db:
        await lifecycle.advance_revision(db, user_id=owner, course_id=None)
    statements = {
        "lower": "UPDATE chat_privacy_revisions SET revision=0",
        "skip": "UPDATE chat_privacy_revisions SET revision=revision+2",
        "delete": "DELETE FROM chat_privacy_revisions",
        "move_scope": "UPDATE chat_privacy_revisions SET course_id=:course_id",
        "truncate": "TRUNCATE chat_privacy_revisions",
    }
    with pytest.raises(DBAPIError):
        async with rls_session(owner) as db:
            await db.execute(text(statements[attack]), {"course_id": course})
    async with rls_session(owner) as db:
        assert await lifecycle.read_revision(db, user_id=owner, course_id=course) == (
            lifecycle.PrivacyRevision(1, 0)
        )


async def test_revoked_member_can_advance_global_marker_but_not_course_marker(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    owner, _, course = await _seed(client, users)
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE course_memberships SET status='revoked' WHERE user_id=:owner"),
            {"owner": owner},
        )
    async with rls_session(owner) as db:
        await lifecycle.advance_revision(db, user_id=owner, course_id=None)
    with pytest.raises(DBAPIError):
        async with rls_session(owner) as db:
            await lifecycle.advance_revision(db, user_id=owner, course_id=course)


async def test_worker_has_no_revision_table_rights_despite_bypass_rls(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    await _seed(client, users)
    worker_engine = create_async_engine(WORKER_DSN)
    try:
        async with worker_engine.connect() as conn:
            assert await conn.scalar(text("SELECT current_user")) == "dou_worker"
            assert await conn.scalar(
                text("SELECT rolbypassrls FROM pg_roles WHERE rolname=current_user")
            )
            with pytest.raises(DBAPIError):
                await conn.execute(text("SELECT * FROM chat_privacy_revisions"))
    finally:
        await worker_engine.dispose()
    async with admin_engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                    "WHERE oid='public.chat_privacy_revisions'::regclass"
                )
            )
        ).one()
        assert row.relrowsecurity and row.relforcerowsecurity
        for privilege in ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"]:
            assert not await conn.scalar(
                text(
                    "SELECT has_table_privilege('dou_worker', "
                    "'public.chat_privacy_revisions', :privilege)"
                ),
                {"privilege": privilege},
            )
