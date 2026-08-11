"""005 role-aware course agent: identity, RLS and atomic quota evidence."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import get_settings
from app.core.db import rls_session
from app.modules.agent import quota as agent_quota
from tests.conftest import REPO_ROOT, UserFactory
from tests.factories import create_course, enroll_student


@dataclass(frozen=True, slots=True)
class RoleFixture:
    course_id: UUID
    instructor_id: UUID
    instructor: dict[str, str]
    student_id: UUID
    student: dict[str, str]


async def _role_fixture(client: AsyncClient, users: UserFactory, *, suffix: str) -> RoleFixture:
    instructor_id = await users.create(f"agent.teacher.{suffix}@dogus.edu.tr")
    student_id = await users.create(f"agent.student.{suffix}@dogus.edu.tr")
    instructor = users.auth(instructor_id)
    student = users.auth(student_id)
    course_id = await create_course(client, instructor, f"AG-{suffix[:8]}")
    await enroll_student(
        client,
        instructor,
        course_id,
        f"agent.student.{suffix}@dogus.edu.tr",
    )
    return RoleFixture(course_id, instructor_id, instructor, student_id, student)


class TestServerDerivedIdentity:
    async def test_availability_exposes_only_server_resolved_persona(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        fixture = await _role_fixture(client, users, suffix="availability")

        student = await client.get(
            f"/courses/{fixture.course_id}/chat/availability", headers=fixture.student
        )
        instructor = await client.get(
            f"/courses/{fixture.course_id}/chat/availability", headers=fixture.instructor
        )

        assert student.status_code == 200, student.text
        assert student.json()["audience"] == "student"
        assert student.json()["agent_profile"] == "student_coach"
        assert instructor.status_code == 200, instructor.text
        assert instructor.json()["audience"] == "instructor"
        assert instructor.json()["agent_profile"] == "instructor_assistant"

    @pytest.mark.parametrize("field", ["audience", "agent_profile"])
    async def test_client_cannot_select_persona(
        self, client: AsyncClient, users: UserFactory, field: str
    ) -> None:
        fixture = await _role_fixture(client, users, suffix=f"spoof-{field}")

        response = await client.post(
            f"/courses/{fixture.course_id}/chat",
            json={"question": "Deadlock nedir?", field: "instructor"},
            headers=fixture.student,
        )

        assert response.status_code == 422, response.text

    async def test_platform_admin_without_membership_stays_not_found(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await _role_fixture(client, users, suffix="platform-admin")
        platform_admin_id = await users.create("agent.platform.admin@dogus.edu.tr")
        async with admin_engine.begin() as connection:
            await connection.execute(
                text("INSERT INTO platform_admins (user_id) VALUES (:user_id)"),
                {"user_id": platform_admin_id},
            )

        response = await client.get(
            f"/courses/{fixture.course_id}/chat/availability",
            headers=users.auth(platform_admin_id),
        )

        assert response.status_code == 404, response.text

    async def test_role_change_makes_existing_session_conflict(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await _role_fixture(client, users, suffix="role-change")
        session_id = uuid4()
        async with admin_engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO chat_sessions "
                    "(id, course_id, user_id, mode, audience) "
                    "VALUES (:id, :course_id, :user_id, 'qa', 'student')"
                ),
                {
                    "id": session_id,
                    "course_id": fixture.course_id,
                    "user_id": fixture.student_id,
                },
            )
            await connection.execute(
                text(
                    "UPDATE course_memberships SET role='instructor' "
                    "WHERE course_id=:course_id AND user_id=:user_id"
                ),
                {"course_id": fixture.course_id, "user_id": fixture.student_id},
            )

        response = await client.post(
            f"/courses/{fixture.course_id}/chat",
            json={
                "question": "Deadlock nedir?",
                "mode": "qa",
                "session_id": str(session_id),
            },
            headers=fixture.student,
        )

        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "session_audience_changed"


class TestOperationalKillSwitch:
    async def test_disabled_switch_creates_no_agent_artifact(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fixture = await _role_fixture(client, users, suffix="disabled")
        monkeypatch.setattr(get_settings(), "course_agent_enabled", False)

        availability = await client.get(
            f"/courses/{fixture.course_id}/chat/availability", headers=fixture.student
        )
        response = await client.post(
            f"/courses/{fixture.course_id}/chat",
            json={"question": "Deadlock nedir?"},
            headers=fixture.student,
        )

        assert availability.status_code == 200, availability.text
        assert availability.json()["reason"] == "globally_disabled"
        assert response.status_code == 503, response.text
        assert response.json()["error"]["code"] == "course_agent_disabled"
        async with admin_engine.connect() as connection:
            counts = (
                await connection.execute(
                    text(
                        "SELECT "
                        "(SELECT count(*) FROM chat_sessions WHERE course_id=:course_id), "
                        "(SELECT count(*) FROM ai_token_reservations WHERE course_id=:course_id), "
                        "(SELECT count(*) FROM request_logs WHERE course_id=:course_id)"
                    ),
                    {"course_id": fixture.course_id},
                )
            ).one()
        assert tuple(counts) == (0, 0, 0)


class TestDatabaseRoleBoundary:
    async def test_student_cannot_forge_instructor_session_cache_or_log(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        fixture = await _role_fixture(client, users, suffix="forge")

        statements = [
            text(
                "INSERT INTO chat_sessions (course_id,user_id,mode,audience) "
                "VALUES (:course_id,:user_id,'qa','instructor')"
            ),
            text(
                "INSERT INTO answer_cache "
                "(course_id,audience,policy_revision,prompt_revision,corpus_revision,"
                "question_hash,answer) VALUES "
                "(:course_id,'instructor','p','r','c','forged','{}'::jsonb)"
            ),
            text(
                "INSERT INTO request_logs "
                "(course_id,user_id,route,mode,audience,status,http_status,latency_ms,"
                "token_count,cache_hit) VALUES "
                "(:course_id,:user_id,'forged','qa','instructor','answered',200,1,1,false)"
            ),
        ]
        for statement in statements:
            with pytest.raises(DBAPIError):
                async with rls_session(fixture.student_id) as session:
                    await session.execute(
                        statement,
                        {
                            "course_id": fixture.course_id,
                            "user_id": fixture.student_id,
                        },
                    )

    async def test_cache_select_is_audience_scoped(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await _role_fixture(client, users, suffix="cache-read")
        async with admin_engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO answer_cache "
                    "(course_id,audience,policy_revision,prompt_revision,corpus_revision,"
                    "question_hash,answer) VALUES "
                    "(:course_id,'instructor','p','r','c','instructor-only','{}'::jsonb)"
                ),
                {"course_id": fixture.course_id},
            )

        async with rls_session(fixture.student_id) as session:
            student_count = await session.scalar(
                text("SELECT count(*) FROM answer_cache WHERE course_id=:course_id"),
                {"course_id": fixture.course_id},
            )
        async with rls_session(fixture.instructor_id) as session:
            instructor_count = await session.scalar(
                text("SELECT count(*) FROM answer_cache WHERE course_id=:course_id"),
                {"course_id": fixture.course_id},
            )

        assert student_count == 0
        assert instructor_count == 1

    async def test_quota_tables_are_function_only(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        fixture = await _role_fixture(client, users, suffix="function-only")
        reservation = await agent_quota.reserve(
            user_id=fixture.student_id,
            course_id=fixture.course_id,
            requested_tokens=100,
            lease_seconds=60,
            user_hard_limit=50_000,
            course_hard_limit=500_000,
            platform_hard_limit=5_000_000,
        )
        assert reservation.allowed is True

        for statement, parameters in (
            ("SELECT count(*) FROM ai_token_reservations", {}),
            (
                "INSERT INTO ai_guard_events(course_id,user_id,audience,event_type) "
                "VALUES (:course_id,:user_id,'student','rate_limited')",
                {"course_id": fixture.course_id, "user_id": fixture.student_id},
            ),
        ):
            with pytest.raises(DBAPIError):
                async with rls_session(fixture.student_id) as session:
                    await session.execute(text(statement), parameters)

    async def test_oversized_function_limit_is_rejected_by_database(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        fixture = await _role_fixture(client, users, suffix="db-ceiling")
        with pytest.raises(DBAPIError):
            async with rls_session(fixture.student_id) as session:
                await session.execute(
                    text(
                        "SELECT * FROM app.reserve_course_agent_tokens("
                        ":course_id,:reservation_id,100,60,50001,500000,5000000)"
                    ),
                    {"course_id": fixture.course_id, "reservation_id": uuid4()},
                )

    async def test_expired_unreconciled_charge_stays_in_daily_budget(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await _role_fixture(client, users, suffix="expired-charge")
        first = await agent_quota.reserve(
            user_id=fixture.student_id,
            course_id=fixture.course_id,
            requested_tokens=100,
            lease_seconds=60,
            user_hard_limit=50_000,
            course_hard_limit=500_000,
            platform_hard_limit=5_000_000,
        )
        assert first.allowed and first.reservation_id is not None
        async with admin_engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE ai_token_reservations SET "
                    "created_at=now()-interval '2 minutes', "
                    "expires_at=now()-interval '1 minute' WHERE id=:id"
                ),
                {"id": first.reservation_id},
            )

        second = await agent_quota.reserve(
            user_id=fixture.student_id,
            course_id=fixture.course_id,
            requested_tokens=11_950,
            lease_seconds=60,
            user_hard_limit=50_000,
            course_hard_limit=500_000,
            platform_hard_limit=5_000_000,
        )

        assert second.allowed is False
        assert second.reason == "quota_exhausted", "expiry releases concurrency, not spend"

    async def test_provider_error_precharge_is_visible_in_tokens_today(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        fixture = await _role_fixture(client, users, suffix="provider-error-charge")
        reservation = await agent_quota.reserve(
            user_id=fixture.student_id,
            course_id=fixture.course_id,
            requested_tokens=321,
            lease_seconds=60,
            user_hard_limit=50_000,
            course_hard_limit=500_000,
            platform_hard_limit=5_000_000,
        )
        assert reservation.allowed is True

        # A provider error has no trustworthy usage, so no refund/reconcile is
        # performed. The user-facing daily counter must expose the durable full
        # precharge rather than the legacy request_logs total (which is zero).
        async with rls_session(fixture.student_id) as session:
            used = await session.scalar(
                text("SELECT app.course_tokens_today(:course_id)"),
                {"course_id": fixture.course_id},
            )

        assert used == 321

    async def test_cross_course_global_user_cap_is_atomic(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        instructor_id = await users.create("agent.atomic.user@dogus.edu.tr")
        headers = users.auth(instructor_id)
        course_a = await create_course(client, headers, "AG-ATOMIC-A")
        course_b = await create_course(client, headers, "AG-ATOMIC-B")
        async with admin_engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO course_ai_policies "
                    "(course_id,instructor_daily_token_budget) VALUES "
                    "(:a,100000),(:b,100000)"
                ),
                {"a": course_a, "b": course_b},
            )

        async def reserve(course_id: UUID) -> agent_quota.TokenReservation:
            return await agent_quota.reserve(
                user_id=instructor_id,
                course_id=course_id,
                requested_tokens=70_000,
                lease_seconds=60,
                user_hard_limit=100_000,
                course_hard_limit=500_000,
                platform_hard_limit=5_000_000,
            )

        results = await asyncio.gather(reserve(course_a), reserve(course_b))

        assert sum(result.allowed for result in results) == 1
        assert {result.reason for result in results if not result.allowed} == {"quota_exhausted"}

    async def test_cross_course_platform_cap_is_atomic(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        first_user = await users.create("agent.atomic.platform.a@dogus.edu.tr")
        second_user = await users.create("agent.atomic.platform.b@dogus.edu.tr")
        course_a = await create_course(client, users.auth(first_user), "AG-PLATFORM-A")
        course_b = await create_course(client, users.auth(second_user), "AG-PLATFORM-B")
        async with admin_engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO course_ai_policies "
                    "(course_id,instructor_daily_token_budget) VALUES "
                    "(:a,100000),(:b,100000)"
                ),
                {"a": course_a, "b": course_b},
            )

        async def reserve(user_id: UUID, course_id: UUID) -> agent_quota.TokenReservation:
            return await agent_quota.reserve(
                user_id=user_id,
                course_id=course_id,
                requested_tokens=70_000,
                lease_seconds=60,
                user_hard_limit=200_000,
                course_hard_limit=500_000,
                platform_hard_limit=100_000,
            )

        results = await asyncio.gather(
            reserve(first_user, course_a), reserve(second_user, course_b)
        )

        assert sum(result.allowed for result in results) == 1
        assert {result.reason for result in results if not result.allowed} == {"quota_exhausted"}

    def test_migration_is_single_transaction(self) -> None:
        migration = (REPO_ROOT / "supabase/migrations/0015_role_aware_course_agent.sql").read_text()
        statements = migration.strip().splitlines()
        assert statements[2] == "BEGIN;"
        assert statements[-1] == "COMMIT;"
        assert "ai_token_reservations_global_user_day_idx" in migration
        assert "ai_token_reservations_platform_day_idx" in migration


async def test_reconcile_failure_prechargei_korur_ve_cagiranin_sonucunu_maskelemez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def broken_session(_user_id: UUID) -> AsyncIterator[None]:
        raise RuntimeError("database unavailable")
        yield None  # pragma: no cover - async context manager shape

    monkeypatch.setattr(agent_quota, "rls_session", broken_session)

    async def successful_caller() -> str:
        await agent_quota.reconcile(
            user_id=uuid4(),
            reservation_id=uuid4(),
            actual_tokens=10,
        )
        return "answer"

    async def failed_provider_caller() -> None:
        try:
            raise LookupError("provider unavailable")
        finally:
            await agent_quota.reconcile(
                user_id=uuid4(),
                reservation_id=uuid4(),
                actual_tokens=100,
            )

    assert await successful_caller() == "answer"
    with pytest.raises(LookupError, match="provider unavailable"):
        await failed_provider_caller()
