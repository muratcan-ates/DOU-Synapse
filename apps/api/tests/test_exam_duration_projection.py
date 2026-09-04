"""A closed entry window must not shorten an owned exam or open its privacy lock.

The SECURITY DEFINER projection is tested through dou_app and direct SQL. The
ownership mutation is transaction-local and its rollback is verified explicitly.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db import rls_session
from tests.conftest import UserFactory
from tests.factories import enroll_student
from tests.test_blueprint import (
    BlueprintFixture,
    build,
    cell,
    make_blueprint,
    make_outcome,
    make_question,
    make_version,
    publish,
    set_items,
)


@pytest.fixture
async def closed_window_exam(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
) -> tuple[BlueprintFixture, UUID, UUID]:
    fixture = await build(client, users, admin_engine, code="DURATION 014")
    outcome = await make_outcome(client, fixture, code="OUT1")
    blueprint_id = await make_blueprint(
        client, fixture, cells=[cell(outcome, count=1)], duration=60
    )
    question_id = await make_question(admin_engine, fixture, outcome_id=outcome, difficulty="easy")
    version_id = await make_version(client, fixture, blueprint_id)
    assert (
        await set_items(client, fixture, blueprint_id, version_id, [question_id])
    ).status_code == 200
    assert (await publish(client, fixture, blueprint_id, version_id)).status_code == 200
    started = await client.post(
        f"/courses/{fixture.course_id}/exams",
        json={"blueprint_id": str(blueprint_id)},
        headers=fixture.student,
    )
    assert started.status_code == 201, started.text
    session_id = UUID(started.json()["id"])
    async with admin_engine.begin() as connection:
        # Shift the whole session, not just expiry; the effective cap remains 60 min.
        await connection.execute(
            text(
                "UPDATE exam_sessions SET started_at = now() - interval '25 min', "
                "expires_at = now() + interval '35 min' WHERE id = :id"
            ),
            {"id": session_id},
        )
        await connection.execute(
            text(
                "UPDATE exam_blueprints SET opens_at = now() - interval '1 hour', "
                "closes_at = now() - interval '1 min' WHERE id = :id"
            ),
            {"id": blueprint_id},
        )
    return fixture, blueprint_id, session_id


async def test_closed_entry_window_preserves_remaining_time_and_assistant_lock(
    client: AsyncClient, closed_window_exam: tuple[BlueprintFixture, UUID, UUID]
) -> None:
    fixture, blueprint_id, session_id = closed_window_exam
    async with rls_session(user_id=fixture.student_id) as session:
        # A normal blueprint read is hidden; the new projection must still work.
        assert (
            await session.scalar(
                text("SELECT duration_minutes FROM exam_blueprints WHERE id = :id"),
                {"id": blueprint_id},
            )
            is None
        )
        assert (
            await session.scalar(text("SELECT app.own_exam_duration(:id)"), {"id": session_id})
            == 60
        )
    response = await client.get(
        f"/courses/{fixture.course_id}/exams/{session_id}", headers=fixture.student
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["expired"] is False
    assert 2090 <= body["remaining_seconds"] <= 2100
    availability = await client.get(
        f"/courses/{fixture.course_id}/chat/availability", headers=fixture.student
    )
    assert availability.status_code == 200, availability.text
    assert availability.json()["available"] is False
    assert availability.json()["reason"] == "exam_in_progress"
    blocked = await client.post(
        f"/courses/{fixture.course_id}/chat",
        json={"question": "Kilitlenme nedir?", "mode": "qa"},
        headers=fixture.student,
    )
    assert blocked.status_code == 403, blocked.text
    assert blocked.json()["error"]["code"] == "exam_in_progress"


@pytest.mark.parametrize("caller", ["other_student", "instructor", "anonymous"])
async def test_duration_is_null_for_nonowners_even_when_role_can_read_exam(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    closed_window_exam: tuple[BlueprintFixture, UUID, UUID],
    caller: str,
) -> None:
    fixture, _, session_id = closed_window_exam
    if caller == "other_student":
        user_id = await users.create("duration-other@dogus.edu.tr")
        await enroll_student(
            client, fixture.instructor, fixture.course_id, "duration-other@dogus.edu.tr"
        )
    elif caller == "instructor":
        user_id = fixture.instructor_id
    else:
        user_id = None
    async with admin_engine.begin() as connection:
        await connection.execute(text("SET LOCAL ROLE dou_app"))
        await connection.execute(
            text("SELECT set_config('app.current_user_id', :user_id, true)"),
            {"user_id": str(user_id) if user_id else ""},
        )
        duration = await connection.scalar(
            text("SELECT app.own_exam_duration(:id)"), {"id": session_id}
        )
        assert duration is None, "Nonowner learned an exam duration"


@pytest.mark.parametrize("unknown_id", [None, UUID(int=0)])
async def test_duration_is_null_for_absent_or_null_session(
    closed_window_exam: tuple[BlueprintFixture, UUID, UUID],
    unknown_id: UUID | None,
) -> None:
    fixture, _, _ = closed_window_exam
    async with rls_session(user_id=fixture.student_id) as session:
        assert (
            await session.scalar(text("SELECT app.own_exam_duration(:id)"), {"id": unknown_id})
            is None
        )


async def test_revoked_owner_keeps_duration_and_export_privacy_lock(
    client: AsyncClient,
    admin_engine: AsyncEngine,
    closed_window_exam: tuple[BlueprintFixture, UUID, UUID],
) -> None:
    fixture, _, session_id = closed_window_exam
    async with admin_engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE course_memberships SET status = 'revoked' "
                "WHERE course_id = :course AND user_id = :user"
            ),
            {"course": UUID(fixture.course_id), "user": fixture.student_id},
        )
    async with rls_session(user_id=fixture.student_id) as session:
        assert (
            await session.scalar(text("SELECT app.own_exam_duration(:id)"), {"id": session_id})
            == 60
        )
    # Course access is still rejected; duration is only a privacy-lock input.
    inaccessible = await client.get(
        f"/courses/{fixture.course_id}/exams/{session_id}", headers=fixture.student
    )
    assert inaccessible.status_code == 404, inaccessible.text
    export = await client.get("/me/export", headers=fixture.student)
    assert export.status_code == 423, export.text
    assert export.json()["error"]["code"] == "exam_export_locked"


async def test_projection_has_fixed_path_scalar_type_and_narrow_grants(
    admin_engine: AsyncEngine,
) -> None:
    async with admin_engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    "SELECT prosecdef, provolatile, prorettype::regtype::text, proconfig, "
                    "has_function_privilege('dou_app', oid, 'EXECUTE'), "
                    "has_function_privilege('dou_worker', oid, 'EXECUTE'), "
                    "EXISTS (SELECT 1 FROM aclexplode("
                    "coalesce(proacl, acldefault('f', proowner))) a "
                    "WHERE a.grantee = 0 AND a.privilege_type = 'EXECUTE') "
                    "FROM pg_proc WHERE oid = 'app.own_exam_duration(uuid)'::regprocedure"
                )
            )
        ).one()
    assert row == (
        True,
        "s",
        "integer",
        ["search_path=pg_catalog, public, app"],
        True,
        False,
        False,
    )


async def test_worker_cannot_execute_projection(admin_engine: AsyncEngine) -> None:
    with pytest.raises(ProgrammingError, match="permission denied for function own_exam_duration"):
        async with admin_engine.begin() as connection:
            await connection.execute(text("SET LOCAL ROLE dou_worker"))
            await connection.execute(text("SELECT app.own_exam_duration(NULL)"))


async def test_public_only_role_cannot_execute_projection(admin_engine: AsyncEngine) -> None:
    async with admin_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.execute(text("CREATE ROLE dou014_duration_public_probe NOLOGIN"))
            # Give schema access so rejection tests EXECUTE, not hidden schema access.
            await connection.execute(
                text("GRANT USAGE ON SCHEMA app TO dou014_duration_public_probe")
            )
            await connection.execute(text("SET LOCAL ROLE dou014_duration_public_probe"))
            with pytest.raises(
                ProgrammingError, match="permission denied for function own_exam_duration"
            ):
                await connection.execute(text("SELECT app.own_exam_duration(NULL)"))
        finally:
            await transaction.rollback()


async def test_owner_predicate_mutation_breaks_isolation_and_rolls_back(
    admin_engine: AsyncEngine, closed_window_exam: tuple[BlueprintFixture, UUID, UUID]
) -> None:
    fixture, _, session_id = closed_window_exam
    async with admin_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            original = await connection.scalar(
                text("SELECT pg_get_functiondef('app.own_exam_duration(uuid)'::regprocedure)")
            )
            predicate = "AND s.user_id = app.current_user_id()"
            assert predicate in original
            await connection.execute(text(original.replace(predicate, "", 1)))
            await connection.execute(text("SET LOCAL ROLE dou_app"))
            await connection.execute(
                text("SELECT set_config('app.current_user_id', :user_id, true)"),
                {"user_id": str(fixture.instructor_id)},
            )
            duration = await connection.scalar(
                text("SELECT app.own_exam_duration(:id)"), {"id": session_id}
            )
            # The exact nonowner assertion above turns red without its SQL guard.
            with pytest.raises(AssertionError, match="Nonowner learned an exam duration"):
                assert duration is None, "Nonowner learned an exam duration"
            assert duration == 60
        finally:
            await transaction.rollback()
    async with admin_engine.connect() as connection:
        restored = await connection.scalar(
            text("SELECT pg_get_functiondef('app.own_exam_duration(uuid)'::regprocedure)")
        )
        assert restored == original
    async with rls_session(user_id=fixture.instructor_id) as session:
        assert (
            await session.scalar(text("SELECT app.own_exam_duration(:id)"), {"id": session_id})
            is None
        )
    async with rls_session(user_id=fixture.student_id) as session:
        assert (
            await session.scalar(text("SELECT app.own_exam_duration(:id)"), {"id": session_id})
            == 60
        )
