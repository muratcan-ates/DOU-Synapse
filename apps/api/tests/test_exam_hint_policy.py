"""Instructor hint limits apply to practice HTTP requests, including disabled hints."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import get_settings
from tests.conftest import UserFactory
from tests.factories import build_course, start


@pytest.fixture(autouse=True)
def settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.parametrize("workspace_enabled", ["false", "true"])
@pytest.mark.parametrize("requested_level", [1, 4])
async def test_disabled_hints_return_no_source_even_without_workspace(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    workspace_enabled: str,
    requested_level: int,
) -> None:
    monkeypatch.setenv("STUDENT_ASSESSMENT_WORKSPACE_ENABLED", workspace_enabled)
    get_settings.cache_clear()
    pool = await build_course(client, users, admin_engine, approved=1)
    practice = await start(client, pool, "practice")
    base = f"/courses/{pool.course_id}"
    policy = await client.put(f"{base}/ai-policy", headers=pool.instructor, json={"hint_limit": 0})
    assert policy.status_code == 200, policy.text
    assert policy.json()["effective"]["hint_limit"] == 0

    response = await client.post(
        f"{base}/exams/{practice['id']}/hint",
        headers=pool.student,
        json={"question_id": str(pool.question_ids[0]), "hint_level": requested_level},
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "permission_denied"
    assert set(response.json()) == {"error"}
    assert "eğitmeniniz tarafından kapatıldı" in response.json()["error"]["message"]


@pytest.mark.parametrize("limit", [1, 2, 3])
async def test_positive_hint_limit_keeps_existing_source_and_clamps_level(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    limit: int,
) -> None:
    pool = await build_course(client, users, admin_engine, approved=1)
    practice = await start(client, pool, "practice")
    base = f"/courses/{pool.course_id}"
    policy = await client.put(
        f"{base}/ai-policy", headers=pool.instructor, json={"hint_limit": limit}
    )
    assert policy.status_code == 200, policy.text
    response = await client.post(
        f"{base}/exams/{practice['id']}/hint",
        headers=pool.student,
        json={"question_id": str(pool.question_ids[0]), "hint_level": 4},
    )
    assert response.status_code == 200, response.text
    assert response.json()["hint_level"] == limit
    assert response.json()["source"]["chunk_id"] == str(pool.chunk_ids[0])
