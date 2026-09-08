"""OPS1: real authorized overview and SQL-backed readiness, no provider calls.

Run only through the root-owned isolated test DB harness. Policy mismatch uses
client settings against the actual canonical SQL policy; no policy row is edited.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core import readiness
from app.core.config import get_settings
from tests.conftest import UserFactory
from tests.factories import create_course


async def _admin(users: UserFactory, engine: AsyncEngine) -> UUID:
    user_id = await users.create("ops-readiness@example.com", "Synthetic Operator")
    async with engine.begin() as connection:
        await connection.execute(
            text("INSERT INTO platform_admins (user_id) VALUES (:user_id)"),
            {"user_id": user_id},
        )
    return user_id


@pytest.mark.parametrize(
    "setting_name", ["chat_rate_limit_requests", "question_gen_rate_limit_requests"]
)
async def test_admin_matches_actual_quota_readiness_failure_and_recovery(
    setting_name: str,
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = await _admin(users, admin_engine)
    headers = users.auth(actor)
    monkeypatch.setattr(readiness, "warmup_state", lambda: "disabled")
    async with admin_engine.connect() as connection:
        before = await connection.scalar(text("SELECT count(*) FROM app.rate_limit_windows"))

    async def observe(expected_quota: str, expected_status: str) -> None:
        probe = await client.get("/health/ready")
        overview = await client.get("/admin/overview", headers=headers)
        assert probe.status_code == (200 if expected_status == "ok" else 503)
        assert overview.status_code == 200, overview.text
        public = probe.json()
        private = overview.json()
        assert public["status"] == private["status"] == expected_status
        assert public["checks"]["request_quota"] == expected_quota
        assert private["request_quota_status"] == expected_quota
        assert private["database_status"] == public["checks"]["database"] == "ok"
        assert private["pgvector_status"] == public["checks"]["pgvector"] == "ok"
        assert private["embedding_status"] == public["checks"]["embedding"] == "disabled"
        # Aggregate admin fields do not leak into the public dependency surface.
        assert set(public) == {"status", "checks"}
        assert set(public["checks"]) == {"database", "pgvector", "request_quota", "embedding"}
        assert str(actor) not in overview.text + probe.text
        assert "ops-readiness@example.com" not in overview.text + probe.text

    await observe("ok", "ok")
    with monkeypatch.context() as mismatch:
        settings = get_settings()
        mismatch.setattr(settings, setting_name, getattr(settings, setting_name) + 1)
        await observe("error", "degraded")
        assert (await client.get("/health/live")).status_code == 200
    await observe("ok", "ok")
    async with admin_engine.connect() as connection:
        after = await connection.scalar(text("SELECT count(*) FROM app.rate_limit_windows"))
    assert after == before  # Neither health view admits a synthetic quota request.


@pytest.mark.parametrize("actor_kind", ["anonymous", "user", "instructor"])
async def test_admin_authorization_precedes_dependency_probe(
    actor_kind: str,
    client: AsyncClient,
    users: UserFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers: dict[str, str] = {}
    if actor_kind != "anonymous":
        actor = await users.create("ops-nonadmin@example.com")
        headers = users.auth(actor)
        if actor_kind == "instructor":
            await create_course(client, headers, "OPS-AUTH")

    async def forbidden_probe(*args: object, **kwargs: object) -> None:
        raise AssertionError("admin probe ran before platform authorization")

    monkeypatch.setattr("app.api.admin.check_readiness", forbidden_probe)
    response = await client.get("/admin/overview", headers=headers)
    assert response.status_code == (401 if actor_kind == "anonymous" else 403)
    assert "checks" not in response.json()
    assert "users_total" not in response.json()


async def test_admin_p95_denominator_is_committed_successful_chat_only(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    actor = await _admin(users, admin_engine)
    headers = users.auth(actor)
    course_id = await create_course(client, headers, "OPS-P95")
    empty = await client.get("/admin/overview", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["chat_turns_24h"] == 0
    assert empty.json()["p95_latency_ms"] is None

    async with admin_engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO request_logs "
                "(course_id,user_id,route,mode,status,http_status,latency_ms,"
                "token_count,created_at) "
                "VALUES "
                "(:course,:actor,'POST /courses/{course_id}/chat','qa','answered',"
                "200,100,10,now()),"
                "(:course,:actor,'POST /courses/{course_id}/chat','qa','out_of_scope',"
                "200,300,20,now()),"
                "(:course,:actor,'POST /courses/{course_id}/chat','qa',NULL,503,9000,NULL,now()),"
                "(:course,:actor,'POST /courses/{course_id}/chat','qa',NULL,429,8000,NULL,now()),"
                "(:course,:actor,'GET /health/ready','qa','answered',200,7000,90,now()),"
                "(:course,:actor,'POST /courses/{course_id}/chat','qa','answered',200,6000,80,"
                "now()-interval '25 hours')"
            ),
            {"course": course_id, "actor": actor},
        )
    # A prepared successful row that rolls back must not inflate the denominator.
    with pytest.raises(RuntimeError, match="synthetic rollback"):
        async with admin_engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO request_logs "
                    "(course_id,user_id,route,mode,status,http_status,latency_ms,token_count) "
                    "VALUES (:course,:actor,'POST /courses/{course_id}/chat',"
                    "'qa','answered',200,10000,100)"
                ),
                {"course": course_id, "actor": actor},
            )
            raise RuntimeError("synthetic rollback")

    response = await client.get("/admin/overview", headers=headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["chat_turns_24h"] == 2
    assert result["p95_latency_ms"] == pytest.approx(290.0)
    assert result["tokens_24h"] == 30
    assert "failed_requests_24h" not in result


async def test_shared_probe_reuses_authorized_session_without_second_pool_borrow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock(spec=AsyncSession)
    session.scalar.return_value = 1

    def no_second_pool() -> None:
        raise AssertionError("borrowed a second application connection")

    monkeypatch.setattr(readiness, "get_session_factory", no_second_pool)
    monkeypatch.setattr(readiness, "request_quota_is_ready", AsyncMock(return_value=True))
    monkeypatch.setattr(readiness, "warmup_state", lambda: "disabled")
    result = await readiness.check_readiness(session)
    assert result["status"] == "ok"
    session.scalar.assert_awaited_once()
    # This is a session-ownership contract, not a simulated database readiness proof.
