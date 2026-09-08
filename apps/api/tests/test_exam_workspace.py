"""Student workspace: published discovery, owner history and guarded saved results."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api import exams as exam_api
from app.core.config import Settings, get_settings
from app.core.db import rls_session
from app.models.assessment import QuestionType
from tests.conftest import UserFactory
from tests.factories import (
    ESSAY_PAYLOAD,
    ExamFixture,
    build_course,
    create_course,
    create_topic,
    enroll_student,
    rewind,
    seed_question,
    start,
)
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


@pytest.fixture(autouse=True)
def enabled(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("STUDENT_ASSESSMENT_WORKSPACE_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def pool(client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine) -> ExamFixture:
    return await build_course(client, users, admin_engine)


async def _publish_exam(
    client: AsyncClient,
    admin_engine: AsyncEngine,
    fixture: BlueprintFixture,
    *,
    title: str,
    opens_at: str | None = None,
    closes_at: str | None = None,
    published: bool = True,
    max_attempts: int = 1,
) -> str:
    outcome = await make_outcome(client, fixture, code=f"OUT-{uuid4().hex[:8]}")
    question = await make_question(admin_engine, fixture, outcome_id=outcome, difficulty="easy")
    blueprint = await make_blueprint(
        client,
        fixture,
        cells=[cell(outcome, count=1)],
        duration=60,
        max_attempts=max_attempts,
        opens_at=opens_at,
        closes_at=closes_at,
    )
    update = await client.post(
        f"/courses/{fixture.course_id}/blueprints/{blueprint}",
        json={"title": title, "description": "Kaynaklı sınav"},
        headers=fixture.instructor,
    )
    assert update.status_code == 200, update.text
    version = await make_version(client, fixture, blueprint)
    response = await set_items(client, fixture, blueprint, version, [question])
    assert response.status_code == 200, response.text
    if published:
        response = await publish(client, fixture, blueprint, version)
        assert response.status_code == 200, response.text
    return str(blueprint)


async def _answer(client: AsyncClient, pool: ExamFixture, session_id: str) -> Any:
    return await client.post(
        f"/courses/{pool.course_id}/exams/{session_id}/answers",
        headers=pool.student,
        json={"question_id": str(pool.question_ids[0]), "given": "C"},
    )


async def _finish(client: AsyncClient, pool: ExamFixture, session_id: str) -> Any:
    return await client.post(
        f"/courses/{pool.course_id}/exams/{session_id}/finish", headers=pool.student
    )


async def _snapshot(admin_engine: AsyncEngine, session_id: str) -> list[Any]:
    async with admin_engine.connect() as connection:
        return [
            (
                await connection.execute(
                    text("SELECT to_jsonb(s) FROM exam_sessions s WHERE id = :id"),
                    {"id": UUID(session_id)},
                )
            ).scalar_one(),
            (
                await connection.execute(
                    text(
                        "SELECT coalesce(jsonb_agg(to_jsonb(a) ORDER BY a.id), '[]') "
                        "FROM answers a WHERE session_id = :id"
                    ),
                    {"id": UUID(session_id)},
                )
            ).scalar_one(),
            (
                await connection.execute(
                    text(
                        "SELECT coalesce(jsonb_agg(to_jsonb(m) ORDER BY m.user_id, m.topic_id), "
                        "'[]') FROM mastery m"
                    )
                )
            ).scalar_one(),
        ]


async def test_feature_defaults_closed_and_legacy_sessions_still_work(
    client: AsyncClient, pool: ExamFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("STUDENT_ASSESSMENT_WORKSPACE_ENABLED")
    get_settings.cache_clear()
    assert Settings(_env_file=None).student_assessment_workspace_enabled is False
    base = f"/courses/{pool.course_id}/exams"
    catalog = await client.get(f"{base}/catalog", headers=pool.student)
    assert catalog.json() == {"enabled": False, "items": []}
    for path in ("history", f"{uuid4()}/results"):
        response = await client.get(f"{base}/{path}", headers=pool.student)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "student_assessment_workspace_disabled"
    session = await start(client, pool, "practice")
    assert (await client.get(base, headers=pool.student)).status_code == 200
    assert (await client.get(f"{base}/{session['id']}", headers=pool.student)).status_code == 200


@pytest.mark.parametrize("role", ["student", "instructor"])
async def test_catalog_only_open_published_projection(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine, role: str
) -> None:
    fixture = await build(client, users, admin_engine, code="WORKSPACE")
    now = datetime.now(UTC)
    visible = await _publish_exam(client, admin_engine, fixture, title="Açık sınav")
    await _publish_exam(
        client,
        admin_engine,
        fixture,
        title="Gelecek",
        opens_at=(now + timedelta(days=1)).isoformat(),
    )
    await _publish_exam(
        client,
        admin_engine,
        fixture,
        title="Kapalı",
        closes_at=(now - timedelta(days=1)).isoformat(),
    )
    await _publish_exam(client, admin_engine, fixture, title="Taslak", published=False)
    other = await build(client, users, admin_engine, code="OTHER")
    await _publish_exam(client, admin_engine, other, title="Başka ders")
    # Give the caller another course role: the explicit catalog course filter still applies.
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO course_memberships (course_id, user_id, role) "
                "VALUES (:course, :user, 'instructor')"
            ),
            {"course": UUID(other.course_id), "user": fixture.instructor_id},
        )
    response = await client.get(
        f"/courses/{fixture.course_id}/exams/catalog", headers=getattr(fixture, role)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["enabled"] is True
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["blueprint_id"] == visible
    assert set(item) == {
        "blueprint_id",
        "title",
        "description",
        "duration_minutes",
        "opens_at",
        "closes_at",
        "max_attempts",
        "used_attempts",
        "remaining_attempts",
        "can_start",
    }
    assert item["can_start"] is True


async def test_catalog_attempts_count_all_versions_for_only_the_owner(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
) -> None:
    fixture = await build(client, users, admin_engine, code="ATTEMPT")
    blueprint = await _publish_exam(client, admin_engine, fixture, title="İki hak", max_attempts=2)
    base = f"/courses/{fixture.course_id}/exams"
    opened = await client.post(base, json={"blueprint_id": blueprint}, headers=fixture.student)
    assert opened.status_code == 201, opened.text
    item = (await client.get(f"{base}/catalog", headers=fixture.student)).json()["items"][0]
    assert (item["used_attempts"], item["remaining_attempts"], item["can_start"]) == (1, 1, False)
    done = await client.post(f"{base}/{opened.json()['id']}/finish", headers=fixture.student)
    assert done.status_code == 200, done.text
    item = (await client.get(f"{base}/catalog", headers=fixture.student)).json()["items"][0]
    assert item["can_start"] is True

    # Publish a replacement version; a new paper must not reset the student's attempts.
    question = UUID(opened.json()["questions"][0]["id"])
    version = await make_version(client, fixture, UUID(blueprint))
    assert (
        await set_items(client, fixture, UUID(blueprint), version, [question])
    ).status_code == 200
    assert (await publish(client, fixture, UUID(blueprint), version)).status_code == 200
    second = await client.post(base, json={"blueprint_id": blueprint}, headers=fixture.student)
    assert second.status_code == 201, second.text
    item = (await client.get(f"{base}/catalog", headers=fixture.student)).json()["items"][0]
    assert (item["used_attempts"], item["remaining_attempts"], item["can_start"]) == (2, 0, False)
    rejected = await client.post(base, json={"blueprint_id": blueprint}, headers=fixture.student)
    assert rejected.status_code == 409
    instructor = (await client.get(f"{base}/catalog", headers=fixture.instructor)).json()["items"][
        0
    ]
    assert instructor["used_attempts"] == 0
    assert instructor["can_start"] is True


@pytest.mark.parametrize("suffix", ["", "/history"])
async def test_session_lists_are_owner_only_even_for_course_instructor(
    client: AsyncClient, pool: ExamFixture, suffix: str
) -> None:
    await start(client, pool, "practice")
    instructor = await client.post(
        f"/courses/{pool.course_id}/exams", headers=pool.instructor, json={"mode": "practice"}
    )
    assert instructor.status_code == 201, instructor.text
    response = await client.get(f"/courses/{pool.course_id}/exams{suffix}", headers=pool.instructor)
    assert response.status_code == 200, response.text
    rows = response.json()["items"] if suffix else response.json()
    assert [row["id"] for row in rows] == [instructor.json()["id"]]
    assert rows[0]["questions"] == []


async def test_history_pages_same_timestamp_without_duplicates_and_preserves_time(
    client: AsyncClient, pool: ExamFixture, admin_engine: AsyncEngine
) -> None:
    identities = [(await start(client, pool, "exam"))["id"] for _ in range(3)]
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE exam_sessions SET started_at = now() - interval '5 minutes', "
                "expires_at = now() + interval '15 minutes' WHERE user_id = :user"
            ),
            {"user": pool.student_id},
        )
    base = f"/courses/{pool.course_id}/exams/history"
    response = await client.get(base, params={"limit": 2}, headers=pool.student)
    assert response.status_code == 200, response.text
    first = response.json()
    assert len(first["items"]) == 2
    assert first["next_cursor"]
    second = (
        await client.get(
            base, params={"limit": 2, "cursor": first["next_cursor"]}, headers=pool.student
        )
    ).json()
    rows = first["items"] + second["items"]
    assert [row["id"] for row in rows] == sorted(identities, reverse=True)
    assert second["next_cursor"] is None
    assert all(row["questions"] == [] and row["score"] is None for row in rows)
    assert all(890 <= row["remaining_seconds"] <= 900 for row in rows)
    assert "given" not in str(rows) and "answer_key" not in str(rows)
    assert (
        await client.get(base, params={"cursor": "invalid"}, headers=pool.student)
    ).status_code == 422
    assert (await client.get(base, params={"limit": 0}, headers=pool.student)).status_code == 422
    assert (
        await client.get(base, params={"limit": 100000}, headers=pool.student)
    ).status_code == 200


@pytest.mark.parametrize("admin", [False, True])
async def test_nonmembers_and_platform_admin_cannot_read_workspace(
    client: AsyncClient,
    pool: ExamFixture,
    users: UserFactory,
    admin_engine: AsyncEngine,
    admin: bool,
) -> None:
    outsider = await users.create("outside@dogus.edu.tr")
    if admin:
        async with admin_engine.begin() as conn:
            await conn.execute(
                text("INSERT INTO platform_admins (user_id) VALUES (:id)"), {"id": outsider}
            )
    for suffix in ("catalog", "history", f"{uuid4()}/results"):
        response = await client.get(
            f"/courses/{pool.course_id}/exams/{suffix}", headers=users.auth(outsider)
        )
        assert response.status_code == 404, response.text


async def test_topic_practice_uses_selected_topic_and_rejects_foreign_topic(
    client: AsyncClient, pool: ExamFixture
) -> None:
    base = f"/courses/{pool.course_id}/exams"
    response = await client.post(
        base, json={"mode": "practice", "topic_id": str(pool.topic_id)}, headers=pool.student
    )
    assert response.status_code == 201, response.text
    assert set(row["id"] for row in response.json()["questions"]) == set(
        map(str, pool.question_ids)
    )
    empty = await create_topic(client, pool.instructor, UUID(pool.course_id), "Başka konu")
    response = await client.post(
        base, json={"mode": "practice", "topic_id": str(empty)}, headers=pool.student
    )
    assert response.status_code == 409
    foreign_course = await create_course(client, pool.instructor, "FOREIGN")
    foreign = await create_topic(client, pool.instructor, foreign_course, "Dış konu")
    response = await client.post(
        base, json={"mode": "practice", "topic_id": str(foreign)}, headers=pool.student
    )
    assert response.status_code == 404


async def test_completed_results_can_reopen_without_any_database_or_mastery_change(
    client: AsyncClient, pool: ExamFixture, admin_engine: AsyncEngine
) -> None:
    session = await start(client, pool, "exam")
    assert (await _answer(client, pool, session["id"])).status_code == 201
    finish = await _finish(client, pool, session["id"])
    assert finish.status_code == 200, finish.text
    expected = finish.json()
    assert expected["results_locked"] is False
    assert expected["results"][0]["solution"] is not None
    before = await _snapshot(admin_engine, session["id"])
    for _ in range(2):
        response = await client.get(
            f"/courses/{pool.course_id}/exams/{session['id']}/results", headers=pool.student
        )
        assert response.status_code == 200, response.text
        assert response.json() == expected
    assert await _snapshot(admin_engine, session["id"]) == before


@pytest.mark.parametrize("mode,expired", [("practice", False), ("exam", False), ("exam", True)])
async def test_unfinished_results_never_finish_or_reveal(
    client: AsyncClient, pool: ExamFixture, admin_engine: AsyncEngine, mode: str, expired: bool
) -> None:
    session = await start(client, pool, mode)
    await _answer(client, pool, session["id"])
    if expired:
        await rewind(admin_engine, session["id"], minutes=25)
    before = await _snapshot(admin_engine, session["id"])
    response = await client.get(
        f"/courses/{pool.course_id}/exams/{session['id']}/results", headers=pool.student
    )
    assert response.status_code == 409, response.text
    assert await _snapshot(admin_engine, session["id"]) == before


@pytest.mark.parametrize("identity", ["student_peer", "instructor"])
async def test_results_owner_boundary_survives_instructor_rls(
    client: AsyncClient, pool: ExamFixture, users: UserFactory, identity: str
) -> None:
    session = await start(client, pool, "practice")
    await _finish(client, pool, session["id"])
    headers = pool.instructor
    if identity == "student_peer":
        peer = await users.create("peer@dogus.edu.tr")
        await enroll_student(client, pool.instructor, UUID(pool.course_id), "peer@dogus.edu.tr")
        headers = users.auth(peer)
    response = await client.get(
        f"/courses/{pool.course_id}/exams/{session['id']}/results", headers=headers
    )
    assert response.status_code == 404


@pytest.mark.parametrize("operation", ["start", "answer", "hint", "results"])
async def test_active_exam_blocks_all_answer_bearing_practice_and_history(
    client: AsyncClient, pool: ExamFixture, operation: str
) -> None:
    practice = await start(client, pool, "practice")
    finished = await start(client, pool, "practice")
    await _answer(client, pool, finished["id"])
    await _finish(client, pool, finished["id"])
    await start(client, pool, "exam")
    base = f"/courses/{pool.course_id}/exams"
    if operation == "start":
        response = await client.post(base, headers=pool.student, json={"mode": "practice"})
    elif operation == "answer":
        response = await _answer(client, pool, practice["id"])
    elif operation == "hint":
        response = await client.post(
            f"{base}/{practice['id']}/hint",
            headers=pool.student,
            json={"question_id": str(pool.question_ids[0]), "hint_level": 1},
        )
    else:
        response = await client.get(f"{base}/{finished['id']}/results", headers=pool.student)
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "exam_in_progress"
    assert "answer_key" not in response.text


@pytest.mark.parametrize("first_mode", ["practice", "exam"])
async def test_finish_closes_but_withholds_when_other_exam_is_running(
    client: AsyncClient, pool: ExamFixture, first_mode: str
) -> None:
    first = await start(client, pool, first_mode)
    await _answer(client, pool, first["id"])
    other = await start(client, pool, "exam")
    response = await _finish(client, pool, first["id"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["results_locked"] is True
    assert body["results"] == [] and body["score"] is None
    assert body["answered_count"] == 1
    assert "diğer sınavın" in body["message"]
    state = await client.get(f"/courses/{pool.course_id}/exams/{first['id']}", headers=pool.student)
    assert state.json()["finished_at"] is not None
    assert (await _finish(client, pool, other["id"])).json()["results_locked"] is False
    unlocked = await client.get(
        f"/courses/{pool.course_id}/exams/{first['id']}/results", headers=pool.student
    )
    assert unlocked.status_code == 200, unlocked.text
    assert unlocked.json()["results"][0]["solution"] is not None


async def test_help_lock_is_course_scoped_and_instructor_exempt(
    client: AsyncClient, pool: ExamFixture
) -> None:
    await start(client, pool, "exam")
    other_course = await create_course(client, pool.instructor, "SECOND")
    await enroll_student(client, pool.instructor, other_course, "burak@dogus.edu.tr")
    # A different course reaches its ordinary empty-pool check, rather than the exam lock.
    response = await client.post(
        f"/courses/{other_course}/exams", headers=pool.student, json={"mode": "practice"}
    )
    assert response.status_code == 409, response.text
    base = f"/courses/{pool.course_id}/exams"
    timed = await client.post(base, headers=pool.instructor, json={"mode": "exam"})
    assert timed.status_code == 201
    practice = await client.post(base, headers=pool.instructor, json={"mode": "practice"})
    assert practice.status_code == 201, practice.text
    hint = await client.post(
        f"{base}/{practice.json()['id']}/hint",
        headers=pool.instructor,
        json={"question_id": str(pool.question_ids[0]), "hint_level": 1},
    )
    assert hint.status_code == 200, hint.text


async def test_saved_results_are_locked_until_other_exam_finishes(
    client: AsyncClient, pool: ExamFixture
) -> None:
    """Önceden bitmiş çalışmanın sonucu, yeni sınav bitene kadar açılmaz."""
    finished = await start(client, pool, "practice")
    await _answer(client, pool, finished["id"])
    await _finish(client, pool, finished["id"])
    active = await start(client, pool, "exam")
    url = f"/courses/{pool.course_id}/exams/{finished['id']}/results"
    locked = await client.get(url, headers=pool.student)
    assert locked.status_code == 403, locked.text
    assert locked.json()["error"]["code"] == "exam_in_progress"
    assert "solution" not in locked.text and "answer_key" not in locked.text

    completed = await _finish(client, pool, active["id"])
    assert completed.status_code == 200, completed.text
    unlocked = await client.get(url, headers=pool.student)
    assert unlocked.status_code == 200, unlocked.text
    assert unlocked.json()["results"][0]["solution"] is not None


async def test_results_read_serializes_with_competing_exam_start(
    client: AsyncClient, pool: ExamFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    finished = await start(client, pool, "practice")
    await _answer(client, pool, finished["id"])
    await _finish(client, pool, finished["id"])
    entered = asyncio.Event()
    release = asyncio.Event()
    original = exam_api._completed_results_out

    async def held_results(*args: Any, **kwargs: Any) -> Any:
        entered.set()
        await release.wait()
        return await original(*args, **kwargs)

    monkeypatch.setattr(exam_api, "_completed_results_out", held_results)
    read = asyncio.create_task(
        client.get(
            f"/courses/{pool.course_id}/exams/{finished['id']}/results", headers=pool.student
        )
    )
    pending: asyncio.Task[Any] | None = None
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        pending = asyncio.create_task(start(client, pool, "exam"))
        await asyncio.sleep(0.1)
        assert not pending.done(), "exam start must await the answer-bearing result transaction"
        release.set()
        assert (await asyncio.wait_for(read, timeout=5)).status_code == 200
        await asyncio.wait_for(pending, timeout=5)
    finally:
        release.set()
        await asyncio.gather(read, *([pending] if pending else []), return_exceptions=True)


async def test_rls_history_owner_and_course_isolation(
    client: AsyncClient, pool: ExamFixture, users: UserFactory
) -> None:
    opened = await start(client, pool, "practice")
    peer = await users.create("rls-peer@dogus.edu.tr")
    await enroll_student(client, pool.instructor, UUID(pool.course_id), "rls-peer@dogus.edu.tr")
    async with rls_session(peer) as session:
        assert (await session.execute(text("SELECT id FROM exam_sessions"))).all() == []
    async with rls_session(pool.student_id) as session:
        assert [
            str(row.id) for row in await session.execute(text("SELECT id FROM exam_sessions"))
        ] == [opened["id"]]


async def test_completed_scores_are_withheld_on_every_session_projection(
    client: AsyncClient, pool: ExamFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    finished = await start(client, pool, "practice")
    await _answer(client, pool, finished["id"])
    await _finish(client, pool, finished["id"])
    await start(client, pool, "exam")
    base = f"/courses/{pool.course_id}/exams"
    for suffix in ("", "/history", f"/{finished['id']}"):
        response = await client.get(f"{base}{suffix}", headers=pool.student)
        assert response.status_code == 200, response.text
        body = response.json()
        rows = body["items"] if suffix == "/history" else body if suffix == "" else [body]
        row = next(item for item in rows if item["id"] == finished["id"])
        assert row["score"] is None
    # Turning off a feature must not re-open existing assistance paths.
    monkeypatch.setenv("STUDENT_ASSESSMENT_WORKSPACE_ENABLED", "false")
    get_settings.cache_clear()
    legacy = await client.get(f"{base}/{finished['id']}", headers=pool.student)
    assert legacy.json()["score"] is None
    assert (
        await client.post(base, json={"mode": "practice"}, headers=pool.student)
    ).status_code == 403


async def test_expired_other_exam_releases_saved_results(
    client: AsyncClient, pool: ExamFixture, admin_engine: AsyncEngine
) -> None:
    finished = await start(client, pool, "practice")
    await _answer(client, pool, finished["id"])
    await _finish(client, pool, finished["id"])
    other = await start(client, pool, "exam")
    await rewind(admin_engine, other["id"], minutes=25)
    response = await client.get(
        f"/courses/{pool.course_id}/exams/{finished['id']}/results", headers=pool.student
    )
    assert response.status_code == 200, response.text
    assert response.json()["results_locked"] is False
    assert response.json()["results"][0]["solution"] is not None


async def _legacy_answer(
    client: AsyncClient,
    pool: ExamFixture,
    admin_engine: AsyncEngine,
    *,
    question_type: str,
    evidence: str | None,
    mode: str = "practice",
) -> tuple[str, UUID]:
    payload = ESSAY_PAYLOAD
    if question_type == "code_trace":
        payload = {
            "language": "Python",
            "code": "print(1)",
            "prompt": "Çıktı nedir?",
            "answer_key": "1",
        }
    elif question_type == "bug_hunt":
        payload = {
            "language": "Python",
            "code": "print(total)",
            "prompt": "Hata nedir?",
            "answer_key": {"line": 1, "bug_type": "NameError", "fix_summary": "total tanımla"},
        }
    question = await seed_question(
        admin_engine,
        course_id=UUID(pool.course_id),
        topic_id=pool.topic_id,
        source_chunk_id=pool.chunk_ids[0],
        payload=payload,
        question_type=QuestionType.OPEN
        if question_type == "essay"
        else QuestionType(question_type),
        status="approved",
        reviewed_by=pool.instructor_id,
    )
    session = await start(client, pool, mode)
    async with admin_engine.begin() as conn:
        # Deliberately reproduce a pre-014 answer: scoring used to survive invalid evidence.
        await conn.execute(
            text(
                "INSERT INTO answers (session_id, question_id, course_id, given, score, "
                "is_correct, feedback) VALUES (:session, :question, :course, 'Eski yanıt', "
                "80, true, CAST(:feedback AS jsonb))"
            ),
            {
                "session": UUID(session["id"]),
                "question": question,
                "course": UUID(pool.course_id),
                "feedback": json.dumps(
                    {
                        "durum": "degerlendirildi",
                        "dayanak_chunk_id": evidence,
                        "eksik_noktalar": ["Kaynağı doğrulanmayan model iddiası"],
                        "rubrik_kirilimi": [
                            {"point": "Dört koşul", "weight": 100, "score": 80, "earned": 80}
                        ],
                    }
                ),
            },
        )
    return session["id"], question


@pytest.mark.parametrize("question_type", ["essay", "code_trace", "bug_hunt"])
@pytest.mark.parametrize(
    "source_case", ["missing", "invented", "malformed", "blank", "unreadable", "hidden_question"]
)
async def test_legacy_ai_claims_are_revalidated_on_all_read_projections(
    client: AsyncClient,
    pool: ExamFixture,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    question_type: str,
    source_case: str,
) -> None:
    evidence = str(pool.chunk_ids[0])
    if source_case == "missing":
        evidence = None
    elif source_case == "invented":
        evidence = str(uuid4())
    elif source_case == "malformed":
        evidence = "legacy-malformed-identity"
    identity, question = await _legacy_answer(
        client, pool, admin_engine, question_type=question_type, evidence=evidence
    )
    if source_case == "blank":
        async with admin_engine.begin() as conn:
            await conn.execute(
                text("UPDATE chunks SET text = ' ' WHERE id = :id"), {"id": pool.chunk_ids[0]}
            )
    elif source_case == "unreadable":

        async def no_readable_sources(*args: Any, **kwargs: Any) -> dict[Any, Any]:
            return {}

        monkeypatch.setattr(exam_api, "load_source_material", no_readable_sources)
    elif source_case == "hidden_question":
        rejected = await client.post(
            f"/courses/{pool.course_id}/questions/{question}/reject", headers=pool.instructor
        )
        assert rejected.status_code == 200, rejected.text

    done = await _finish(client, pool, identity)
    assert done.status_code == 200, done.text
    result = done.json()
    assert result["score"] is None
    assert result["ungraded_count"] == 1
    detail = result["results"][0]
    assert detail["graded"] is False
    assert detail["score"] is None and detail["solution"] is None
    assert detail["evidence"] is None
    assert detail["missing_points"] == [] and detail["rubric_breakdown"] == []
    before = await _snapshot(admin_engine, identity)
    base = f"/courses/{pool.course_id}/exams"
    for suffix in ("", "/history", f"/{identity}"):
        response = await client.get(f"{base}{suffix}", headers=pool.student)
        assert response.status_code == 200, response.text
        value = response.json()
        rows = value["items"] if suffix == "/history" else value if suffix == "" else [value]
        assert next(row for row in rows if row["id"] == identity)["score"] is None
    reopened = await client.get(f"{base}/{identity}/results", headers=pool.student)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json() == result
    assert await _snapshot(admin_engine, identity) == before
    # Historical storage is evidence; display filtering must not rewrite it.
    assert before[1][0]["score"] == 80
    assert before[1][0]["feedback"]["durum"] == "degerlendirildi"


async def test_legacy_ungrounded_exam_finish_does_not_apply_mastery(
    client: AsyncClient, pool: ExamFixture, admin_engine: AsyncEngine
) -> None:
    identity, _ = await _legacy_answer(
        client, pool, admin_engine, question_type="essay", evidence=None, mode="exam"
    )
    response = await _finish(client, pool, identity)
    assert response.status_code == 200, response.text
    snapshot = await _snapshot(admin_engine, identity)
    assert snapshot[2] == []
    assert snapshot[1][0]["score"] == 80


async def test_mixed_saved_results_total_uses_only_displayable_grades(
    client: AsyncClient, pool: ExamFixture, admin_engine: AsyncEngine
) -> None:
    identity, _ = await _legacy_answer(
        client, pool, admin_engine, question_type="essay", evidence=None
    )
    assert (await _answer(client, pool, identity)).status_code == 201
    done = await _finish(client, pool, identity)
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["score"] == 100
    assert body["answered_count"] == 2 and body["ungraded_count"] == 1
    valid = next(row for row in body["results"] if row["graded"])
    assert valid["score"] == 100 and valid["solution"] is not None
    state = await client.get(f"/courses/{pool.course_id}/exams/{identity}", headers=pool.student)
    assert state.json()["score"] == 100


async def test_hint_load_waits_for_finish_commit_before_checking_session(
    client: AsyncClient, pool: ExamFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    practice = await start(client, pool, "practice")
    held = asyncio.Event()
    release = asyncio.Event()
    original = exam_api._completed_results_out

    async def held_finish(*args: Any, **kwargs: Any) -> Any:
        held.set()
        await release.wait()
        return await original(*args, **kwargs)

    monkeypatch.setattr(exam_api, "_completed_results_out", held_finish)
    finish_task = asyncio.create_task(_finish(client, pool, practice["id"]))
    hint_task: asyncio.Task[Any] | None = None
    try:
        await asyncio.wait_for(held.wait(), timeout=5)
        hint_task = asyncio.create_task(
            client.post(
                f"/courses/{pool.course_id}/exams/{practice['id']}/hint",
                headers=pool.student,
                json={"question_id": str(pool.question_ids[0]), "hint_level": 1},
            )
        )
        await asyncio.sleep(0.1)
        assert not hint_task.done()
        release.set()
        assert (await asyncio.wait_for(finish_task, timeout=5)).status_code == 200
        hint = await asyncio.wait_for(hint_task, timeout=5)
        assert hint.status_code == 409, hint.text
    finally:
        release.set()
        await asyncio.gather(
            finish_task, *([hint_task] if hint_task else []), return_exceptions=True
        )


@pytest.mark.parametrize("question_type", ["essay", "code_trace", "bug_hunt"])
async def test_saved_valid_ai_grade_survives_then_hides_if_source_becomes_empty(
    client: AsyncClient, pool: ExamFixture, admin_engine: AsyncEngine, question_type: str
) -> None:
    identity, _ = await _legacy_answer(
        client, pool, admin_engine, question_type=question_type, evidence=str(pool.chunk_ids[0])
    )
    done = await _finish(client, pool, identity)
    assert done.status_code == 200, done.text
    assert done.json()["score"] == 80
    assert done.json()["results"][0]["evidence"] is not None
    before = await _snapshot(admin_engine, identity)
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE chunks SET text = '' WHERE id = :id"), {"id": pool.chunk_ids[0]}
        )
    reopened = await client.get(
        f"/courses/{pool.course_id}/exams/{identity}/results", headers=pool.student
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["score"] is None
    assert reopened.json()["ungraded_count"] == 1
    assert reopened.json()["results"][0]["solution"] is None
    assert await _snapshot(admin_engine, identity) == before


@pytest.mark.parametrize("operation", ["answer", "timed_start", "blueprint_start"])
async def test_post_lock_clock_controls_deadlines_and_new_start_time(
    client: AsyncClient,
    pool: ExamFixture,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    """A queued request must not retain the transaction's pre-wait clock."""
    from app.modules.assessment import exam_state

    existing = await start(client, pool, "exam") if operation == "answer" else None
    blueprint = None
    if operation == "blueprint_start":
        fixture = BlueprintFixture(
            course_id=pool.course_id,
            instructor=pool.instructor,
            instructor_id=pool.instructor_id,
            student=pool.student,
            student_id=pool.student_id,
            topic_id=pool.topic_id,
            chunk_ids=pool.chunk_ids,
        )
        blueprint = await _publish_exam(client, admin_engine, fixture, title="Kapanan pencere")
    attempted = asyncio.Event()
    original = exam_api.acquire_user_assessment_lock

    async def observed_lock(*args: Any, **kwargs: Any) -> None:
        attempted.set()
        await original(*args, **kwargs)

    monkeypatch.setattr(exam_api, "acquire_user_assessment_lock", observed_lock)
    pending: asyncio.Task[Any] | None = None
    after_wait_started: datetime | None = None
    try:
        async with rls_session(pool.student_id) as blocker:
            await exam_state.acquire_user_assessment_lock(blocker, user_id=pool.student_id)
            if existing:
                pending = asyncio.create_task(_answer(client, pool, existing["id"]))
            else:
                pending = asyncio.create_task(
                    client.post(
                        f"/courses/{pool.course_id}/exams",
                        headers=pool.student,
                        json={"blueprint_id": blueprint} if blueprint else {"mode": "exam"},
                    )
                )
            await asyncio.wait_for(attempted.wait(), timeout=5)
            async with admin_engine.begin() as conn:
                # Place the cutoff after the request's transaction began but before its lock ends.
                after_wait_started = await conn.scalar(text("SELECT clock_timestamp()"))
                if existing:
                    await conn.execute(
                        text("UPDATE exam_sessions SET expires_at = :cutoff WHERE id = :id"),
                        {"id": UUID(existing["id"]), "cutoff": after_wait_started},
                    )
                elif blueprint:
                    await conn.execute(
                        text("UPDATE exam_blueprints SET closes_at = :cutoff WHERE id = :id"),
                        {"id": UUID(blueprint), "cutoff": after_wait_started},
                    )
            assert not pending.done(), "request must still wait for the assessment lock"
        response = await asyncio.wait_for(pending, timeout=5)
        if operation == "timed_start":
            assert response.status_code == 201, response.text
            assert after_wait_started is not None
            assert datetime.fromisoformat(response.json()["started_at"]) >= after_wait_started
        else:
            assert response.status_code == 409, response.text
            if existing:
                async with admin_engine.connect() as conn:
                    assert (
                        await conn.scalar(
                            text("SELECT count(*) FROM answers WHERE session_id = :id"),
                            {"id": UUID(existing["id"])},
                        )
                        == 0
                    )
    finally:
        if pending is not None:
            await asyncio.gather(pending, return_exceptions=True)
