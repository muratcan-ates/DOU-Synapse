"""Reopened practice feedback and affected-paper privacy boundaries."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api import exams as exam_api
from app.core.config import get_settings
from app.core.db import rls_session
from app.modules.assessment.exam_state import acquire_user_assessment_lock
from tests.conftest import UserFactory
from tests.factories import ExamFixture, build_course, create_course, enroll_student, start
from tests.test_blueprint import (
    build,
    cell,
    make_blueprint,
    make_outcome,
    make_question,
    make_version,
    publish,
    set_items,
)
from tests.test_exam_workspace import _answer, _finish, _legacy_answer, _snapshot


@pytest.fixture(autouse=True)
def enabled(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("STUDENT_ASSESSMENT_WORKSPACE_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def pool(client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine) -> ExamFixture:
    return await build_course(client, users, admin_engine)


def feedback_url(pool: ExamFixture, identity: str, question: UUID | None = None) -> str:
    return f"/courses/{pool.course_id}/exams/{identity}/answers/{question or pool.question_ids[0]}"


async def test_reopen_practice_feedback_is_read_only_before_and_after_finish(
    client: AsyncClient,
    pool: ExamFixture,
    admin_engine: AsyncEngine,
) -> None:
    practice = await start(client, pool, "practice")
    url = feedback_url(pool, practice["id"])
    assert (await client.get(url, headers=pool.student)).status_code == 404
    expected = await _answer(client, pool, practice["id"])
    assert expected.status_code == 201
    for finished in (False, True):
        if finished:
            await _finish(client, pool, practice["id"])
        before = await _snapshot(admin_engine, practice["id"])
        response = await client.get(url, headers=pool.student)
        assert response.status_code == 200, response.text
        assert response.json() == expected.json()
        assert response.json()["solution"] is not None
        assert await _snapshot(admin_engine, practice["id"]) == before


@pytest.mark.parametrize("identity", ["instructor", "peer", "foreign_course"])
async def test_feedback_owner_and_course_boundaries(
    client: AsyncClient,
    pool: ExamFixture,
    users: UserFactory,
    identity: str,
) -> None:
    practice = await start(client, pool, "practice")
    await _answer(client, pool, practice["id"])
    url = feedback_url(pool, practice["id"])
    headers = pool.instructor
    if identity == "peer":
        user_id = await users.create("feedback-peer@dogus.edu.tr")
        await enroll_student(
            client, pool.instructor, UUID(pool.course_id), "feedback-peer@dogus.edu.tr"
        )
        headers = users.auth(user_id)
    elif identity == "foreign_course":
        course = await create_course(client, pool.instructor, "FOREIGN-FEEDBACK")
        await enroll_student(client, pool.instructor, course, "burak@dogus.edu.tr")
        url = url.replace(pool.course_id, str(course))
        headers = pool.student
    assert (await client.get(url, headers=headers)).status_code == 404


async def test_wrong_question_timed_session_and_disabled_feature_are_closed(
    client: AsyncClient,
    pool: ExamFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    practice = await start(client, pool, "practice")
    assert (
        await client.get(feedback_url(pool, practice["id"], uuid4()), headers=pool.student)
    ).status_code == 404
    timed = await start(client, pool, "exam")
    await _answer(client, pool, timed["id"])
    for finished in (False, True):
        if finished:
            await _finish(client, pool, timed["id"])
        assert (
            await client.get(feedback_url(pool, timed["id"]), headers=pool.student)
        ).status_code == 403
    monkeypatch.setenv("STUDENT_ASSESSMENT_WORKSPACE_ENABLED", "false")
    get_settings.cache_clear()
    response = await client.get(feedback_url(pool, practice["id"]), headers=pool.student)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "student_assessment_workspace_disabled"


async def test_feedback_exam_lock_and_removed_guard_detection(
    client: AsyncClient,
    pool: ExamFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    practice = await start(client, pool, "practice")
    await _answer(client, pool, practice["id"])
    await start(client, pool, "exam")
    url = feedback_url(pool, practice["id"])
    assert (await client.get(url, headers=pool.student)).status_code == 403

    async def removed_guard(*args: Any, **kwargs: Any) -> bool:
        return False

    monkeypatch.setattr(exam_api, "_results_locked", removed_guard)
    mutated = await client.get(url, headers=pool.student)
    assert mutated.status_code == 200
    assert mutated.json()["solution"] is not None
    with pytest.raises(AssertionError):
        assert mutated.status_code == 403


async def test_feedback_read_waits_for_assessment_lock(
    client: AsyncClient,
    pool: ExamFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    practice = await start(client, pool, "practice")
    await _answer(client, pool, practice["id"])
    waiting = asyncio.Event()
    original = exam_api.acquire_user_assessment_lock

    async def observed(*args: Any, **kwargs: Any) -> None:
        waiting.set()
        await original(*args, **kwargs)

    monkeypatch.setattr(exam_api, "acquire_user_assessment_lock", observed)
    async with rls_session(pool.student_id) as blocker:
        await acquire_user_assessment_lock(blocker, user_id=pool.student_id)
        pending = asyncio.create_task(
            client.get(feedback_url(pool, practice["id"]), headers=pool.student)
        )
        try:
            await asyncio.wait_for(waiting.wait(), timeout=3)
            await asyncio.sleep(0.03)
            assert not pending.done()
            await blocker.commit()
            assert (await asyncio.wait_for(pending, timeout=3)).status_code == 200
        finally:
            if not pending.done():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)


@pytest.mark.parametrize("kind", ["essay", "code_trace", "bug_hunt"])
async def test_reopened_ai_feedback_revalidates_sources_without_regrading(
    client: AsyncClient,
    pool: ExamFixture,
    admin_engine: AsyncEngine,
    kind: str,
) -> None:
    identity, question = await _legacy_answer(
        client,
        pool,
        admin_engine,
        question_type=kind,
        evidence=str(pool.chunk_ids[0]),
    )
    url = feedback_url(pool, identity, question)
    assert (await client.get(url, headers=pool.student)).json()["score"] == 80
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE chunks SET text = ' ' WHERE id = :id"), {"id": pool.chunk_ids[0]}
        )
    before = await _snapshot(admin_engine, identity)
    response = await client.get(url, headers=pool.student)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["graded"] is False and body["score"] is None
    assert body["solution"] is None and body["evidence"] is None
    assert body["missing_points"] == [] and body["rubric_breakdown"] == []
    assert await _snapshot(admin_engine, identity) == before
    assert before[1][0]["score"] == 80


async def test_usage_pages_versions_without_student_data(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    fixture = await build(client, users, admin_engine, code="USAGE")
    outcome = await make_outcome(client, fixture, code="U1")
    question = await make_question(admin_engine, fixture, outcome_id=outcome, difficulty="easy")
    blueprint = await make_blueprint(client, fixture, cells=[cell(outcome, count=1)])
    versions = []
    for _ in range(3):
        version = await make_version(client, fixture, blueprint)
        assert (await set_items(client, fixture, blueprint, version, [question])).status_code == 200
        if len(versions) < 2:
            assert (await publish(client, fixture, blueprint, version)).status_code == 200
        versions.append(str(version))
    # Equal timestamps force the UUID tiebreaker, not accidental insertion order.
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE exam_versions SET created_at = '2026-01-01T00:00:00Z' "
                "WHERE blueprint_id = :id"
            ),
            {"id": blueprint},
        )
    url = f"/courses/{fixture.course_id}/questions/{question}/exam-usage"
    rows = []
    params = {"limit": "1"}
    for _ in range(4):
        response = await client.get(url, headers=fixture.instructor, params=params)
        assert response.status_code == 200, response.text
        body = response.json()
        rows.extend(body["items"])
        if body["next_cursor"] is None:
            break
        params["cursor"] = body["next_cursor"]
    assert [row["id"] for row in rows] == sorted(versions, reverse=True)
    assert {row["status"] for row in rows} == {"draft", "published", "superseded"}
    for row in rows:
        assert set(row) == {"id", "blueprint_id", "title", "version_id", "version_no", "status"}
        assert row["id"] == row["version_id"] and row["blueprint_id"] == str(blueprint)
    assert (await client.get(url, headers=fixture.student)).status_code == 403
    assert (
        await client.get(url, headers=fixture.instructor, params={"cursor": "bad"})
    ).status_code == 422


async def test_usage_explicit_course_filter_and_missing_question(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    fixture = await build(client, users, admin_engine, code="USAGE-A")
    other = await build(client, users, admin_engine, code="USAGE-B")
    outcome = await make_outcome(client, other, code="U2")
    question = await make_question(admin_engine, other, outcome_id=outcome, difficulty="easy")
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO course_memberships (course_id,user_id,role) "
                "VALUES (:course,:user,'instructor')"
            ),
            {"course": UUID(other.course_id), "user": fixture.instructor_id},
        )
    for qid in (question, uuid4()):
        response = await client.get(
            f"/courses/{fixture.course_id}/questions/{qid}/exam-usage", headers=fixture.instructor
        )
        assert response.status_code == 404
    own = await client.get(
        f"/courses/{other.course_id}/questions/{question}/exam-usage", headers=fixture.instructor
    )
    assert own.status_code == 200 and own.json() == {"items": [], "next_cursor": None}
