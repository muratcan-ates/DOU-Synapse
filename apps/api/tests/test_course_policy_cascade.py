"""Policy changes stay audited; parent course deletion creates no orphan audit row."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db import rls_session
from tests.conftest import UserFactory

# Sayım sorguları sabit yazılır; tablo ve sütun adı asla girdiden gelmez.
# Önceki hâli f-string ile kuruluyordu ve ruff S608'i haklı olarak tetikliyordu:
# testte zararsız olsa da "SQL'i dizeyle kurma" alışkanlığını depoya sokuyordu.
_SATIR_SAYIMLARI: tuple[tuple[str, str], ...] = (
    ("courses", "SELECT count(*) FROM courses WHERE id = :id"),
    (
        "course_ai_policies",
        "SELECT count(*) FROM course_ai_policies WHERE course_id = :id",
    ),
    (
        "course_ai_policy_audit",
        "SELECT count(*) FROM course_ai_policy_audit WHERE course_id = :id",
    ),
)


async def create_policy_course(client: AsyncClient, users: UserFactory) -> tuple[UUID, UUID]:
    instructor_id = await users.create(f"policy-cascade-{uuid4().hex}@dogus.edu.tr")
    response = await client.post(
        "/courses",
        headers=users.auth(instructor_id),
        json={"code": f"CASCADE-{uuid4().hex[:8]}", "title": "Politika silme sınırı"},
    )
    assert response.status_code == 201, response.text
    course_id = UUID(response.json()["id"])
    async with rls_session(instructor_id) as session:
        assert await session.scalar(text("SELECT current_user")) == "dou_app"
        await session.execute(
            text("INSERT INTO course_ai_policies (course_id, max_hints) VALUES (:id, 2)"),
            {"id": course_id},
        )
    return course_id, instructor_id


async def test_parent_course_delete_cascades_policy_and_audit_without_orphans(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
) -> None:
    course_id, _ = await create_policy_course(client, users)
    retained_course, _ = await create_policy_course(client, users)
    async with admin_engine.begin() as connection:
        deleted = await connection.scalar(
            text("DELETE FROM courses WHERE id = :id RETURNING id"), {"id": course_id}
        )
        assert deleted == course_id
    async with admin_engine.connect() as connection:
        for table, query in _SATIR_SAYIMLARI:
            count = await connection.scalar(text(query), {"id": course_id})
            assert count == 0, table
            retained = await connection.scalar(text(query), {"id": retained_course})
            assert retained == 1, table


async def test_direct_instructor_policy_delete_preserves_complete_audit(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
) -> None:
    course_id, instructor_id = await create_policy_course(client, users)
    async with rls_session(instructor_id) as session:
        await session.execute(
            text("UPDATE course_ai_policies SET max_hints = 1 WHERE course_id = :id"),
            {"id": course_id},
        )
        deleted = await session.scalar(
            text("DELETE FROM course_ai_policies WHERE course_id = :id RETURNING course_id"),
            {"id": course_id},
        )
        assert deleted == course_id
    async with admin_engine.connect() as connection:
        history = (
            (
                await connection.execute(
                    text(
                        "SELECT changed_by, before, after FROM course_ai_policy_audit"
                        " WHERE course_id = :id"
                    ),
                    {"id": course_id},
                )
            )
            .mappings()
            .all()
        )
        assert len(history) == 3
        assert all(row["changed_by"] == instructor_id for row in history)
        assert any(row["before"] is None and row["after"]["max_hints"] == 2 for row in history)
        assert any(
            row["before"] is not None
            and row["before"]["max_hints"] == 2
            and row["after"] is not None
            and row["after"]["max_hints"] == 1
            for row in history
        )
        assert any(row["after"] is None and row["before"]["max_hints"] == 1 for row in history)
        assert (
            await connection.scalar(
                text("SELECT count(*) FROM courses WHERE id=:id"), {"id": course_id}
            )
            == 1
        )


@pytest.mark.parametrize("role", ["student", "peer_instructor"])
async def test_student_and_other_course_instructor_cannot_delete_policy_or_audit(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine, role: str
) -> None:
    course_id, instructor_id = await create_policy_course(client, users)
    actor_id = await users.create(f"policy-delete-{uuid4().hex}@dogus.edu.tr")
    if role == "student":
        async with admin_engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO course_memberships (course_id, user_id, role)"
                    " VALUES (:course, :actor, 'student')"
                ),
                {"course": course_id, "actor": actor_id},
            )
    else:
        created = await client.post(
            "/courses",
            headers=users.auth(actor_id),
            json={"code": f"PEER-{uuid4().hex[:8]}", "title": "Başka ders"},
        )
        assert created.status_code == 201
    async with rls_session(actor_id) as session:
        deleted = await session.scalar(
            text("DELETE FROM course_ai_policies WHERE course_id=:id RETURNING course_id"),
            {"id": course_id},
        )
        assert deleted is None
    with pytest.raises(DBAPIError, match="permission denied"):
        async with rls_session(actor_id) as session:
            await session.execute(
                text("DELETE FROM course_ai_policy_audit WHERE course_id=:id"), {"id": course_id}
            )
    async with rls_session(instructor_id) as session:
        assert (
            await session.scalar(
                text("SELECT count(*) FROM course_ai_policies WHERE course_id=:id"),
                {"id": course_id},
            )
            == 1
        )
        assert (
            await session.scalar(
                text("SELECT count(*) FROM course_ai_policy_audit WHERE course_id=:id"),
                {"id": course_id},
            )
            == 1
        )


async def test_policy_audit_trigger_retains_invoker_and_restricted_table_privileges(
    admin_engine: AsyncEngine,
) -> None:
    async with admin_engine.connect() as connection:
        function = (
            await connection.execute(
                text(
                    "SELECT prosecdef, proconfig FROM pg_proc"
                    " WHERE oid = 'app.audit_course_ai_policy()'::regprocedure"
                )
            )
        ).one()
        assert function.prosecdef is False
        assert "search_path=public, app" in function.proconfig
        assert (
            await connection.scalar(
                text("SELECT has_table_privilege('dou_app', 'course_ai_policy_audit', 'DELETE')")
            )
            is False
        )
        assert (
            await connection.scalar(
                text("SELECT has_table_privilege('dou_app', 'course_ai_policy_audit', 'UPDATE')")
            )
            is False
        )
        assert (
            await connection.scalar(
                text("SELECT has_table_privilege('dou_worker', 'course_ai_policies', 'DELETE')")
            )
            is False
        )
