"""B3 gerçek API/RLS/kayıt kontrolleri; sentetik, hazır model yanıtları kullanılır."""

from __future__ import annotations

import json
from collections.abc import Iterator
from copy import deepcopy
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import get_settings
from app.core.db import rls_session
from app.models.assessment import QuestionType
from app.modules.assessment import question_gen
from tests.conftest import UserFactory
from tests.factories import (
    DEADLOCK_TEXTS,
    FakeCompletion,
    build_course,
    enroll_student,
    seed_question,
    start,
)


@pytest.fixture(autouse=True)
def workspace_enabled(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Sonuç okuma ucunu yalnız bu test paketinde etkinleştirir."""
    monkeypatch.setenv("STUDENT_ASSESSMENT_WORKSPACE_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


CRITERION = "Döngüsel bekleme koşulunu açıklar"
RUBRIC = [
    {"point": "Karşılıklı dışlama koşulunu açıklar", "weight": 60},
    {"point": CRITERION, "weight": 40},
]


def _payload(kind: QuestionType) -> dict[str, Any]:
    return {
        "language": "pseudocode",
        "code": "T1: lock(A); lock(B)\nT2: lock(B); lock(A)",
        "prompt": "İki iş parçacığının kilit bekleme durumunu açıklayın.",
        "answer_key": "Döngüsel bekleme oluşabilir."
        if kind is QuestionType.CODE_TRACE
        else {
            "line": 2,
            "bug_type": "Kilit sırası",
            "fix_summary": "Aynı kilit sırasını kullanın.",
        },
        "rubric": deepcopy(RUBRIC),
    }


def _verdict(source_id: UUID, *, invalid: bool = False) -> str:
    return json.dumps(
        {
            "score": 99,
            "dayanak_chunk_id": str(source_id),
            "eksik_noktalar": [CRITERION],
            "rubrik": [
                {"olcut": RUBRIC[0]["point"], "puan": 100},
                {"olcut": CRITERION, "puan": 50},
            ],
            "grounded_missing_criterion": {
                "criterion": CRITERION,
                "chunk_id": str(source_id),
                "quote": "Bu cümle kaynakta yok." if invalid else DEADLOCK_TEXTS[0],
            },
        },
        ensure_ascii=False,
    )


@pytest.mark.parametrize("kind", [QuestionType.CODE_TRACE, QuestionType.BUG_HUNT])
@pytest.mark.parametrize("mode", ["practice", "exam"])
async def test_code_feedback_persists_and_respects_exam_and_owner_boundaries(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    kind: QuestionType,
    mode: str,
) -> None:
    pool = await build_course(client, users, admin_engine, approved=0)
    question_id = await seed_question(
        admin_engine,
        course_id=UUID(pool.course_id),
        topic_id=pool.topic_id,
        source_chunk_id=pool.chunk_ids[0],
        payload=_payload(kind),
        question_type=kind,
        status="approved",
        reviewed_by=pool.instructor_id,
    )
    question_list = await client.get(f"/courses/{pool.course_id}/questions", headers=pool.student)
    assert question_list.status_code == 200, question_list.text
    question = question_list.json()["items"][0]
    assert "rubric" not in question["payload"]
    assert "answer_key" not in question["payload"]
    source = question["source"]
    assert source is not None
    completion = FakeCompletion(_verdict(pool.chunk_ids[0]))
    question_gen.set_providers(completion=completion)
    try:
        identity = (await start(client, pool, mode))["id"]
        base = f"/courses/{pool.course_id}/exams/{identity}"
        saved = await client.post(
            base + "/answers",
            headers=pool.student,
            json={"question_id": str(question_id), "given": "İş parçacıkları kilit bekler."},
        )
        assert saved.status_code == 201, saved.text
        immediate = saved.json()
        assert immediate["graded"] is True
        assert completion.calls == 1
        if mode == "exam":
            assert immediate["score"] is None
            assert immediate["solution"] is None
            assert immediate["rubric_breakdown"] == []
            assert immediate["grounded_missing_criterion"] is None
        else:
            assert immediate["score"] == 80
            assert immediate["grounded_missing_criterion"]["criterion"] == CRITERION
        finished = await client.post(base + "/finish", headers=pool.student)
        assert finished.status_code == 200, finished.text
        detail = finished.json()["results"][0]
        assert detail["score"] == 80
        assert detail["is_correct"] is True
        assert [row["earned"] for row in detail["rubric_breakdown"]] == [60, 20]
        assert detail["why_wrong"] is None
        claim = detail["grounded_missing_criterion"]
        assert claim["criterion"] == CRITERION
        assert claim["source"] == {
            "chunk_id": str(pool.chunk_ids[0]),
            "file_name": source["file_name"],
            "location": source["location"],
            "snippet": DEADLOCK_TEXTS[0],
        }
        assert detail["solution"]["rubric"] == RUBRIC
        read_path = base + (f"/answers/{question_id}" if mode == "practice" else "/results")
        reopened = await client.get(read_path, headers=pool.student)
        assert reopened.status_code == 200, reopened.text
        if mode == "practice":
            assert reopened.json() == detail
        else:
            reopened_detail = next(
                row for row in reopened.json()["results"] if row["question_id"] == str(question_id)
            )
            assert reopened_detail == detail
            forbidden = await client.get(base + f"/answers/{question_id}", headers=pool.student)
            assert forbidden.status_code == 403, forbidden.text
            assert forbidden.json()["error"]["code"] == "permission_denied"
        assert completion.calls == 1  # Kaydedilmiş sonuç okunurken model yeniden çağrılmaz.
        async with admin_engine.connect() as conn:
            feedback = await conn.scalar(
                text("SELECT feedback FROM answers WHERE session_id = :session"),
                {"session": UUID(identity)},
            )
        assert feedback["kaynakli_eksik_olcut"] == {
            "criterion": CRITERION,
            "chunk_id": str(pool.chunk_ids[0]),
            "quote": DEADLOCK_TEXTS[0],
        }
        outsider = await users.create("b3-outsider@example.com")
        denied = await client.get(read_path, headers=users.auth(outsider))
        assert denied.status_code == 404, denied.text
        assert denied.json()["error"]["code"] == "not_found"
        assert CRITERION not in denied.text and DEADLOCK_TEXTS[0] not in denied.text
        other_email = "b3-other-student@example.com"
        other_student = await users.create(other_email)
        await enroll_student(client, pool.instructor, pool.course_id, other_email)
        denied_owner = await client.get(read_path, headers=users.auth(other_student))
        assert denied_owner.status_code == 404, denied_owner.text
        assert denied_owner.json()["error"]["code"] == "not_found"
        assert CRITERION not in denied_owner.text and DEADLOCK_TEXTS[0] not in denied_owner.text
    finally:
        question_gen.reset_providers()


@pytest.mark.parametrize("mode", ["practice", "exam"])
async def test_fabricated_quote_with_valid_chunk_never_records_grade_or_mastery(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    mode: str,
) -> None:
    pool = await build_course(client, users, admin_engine, approved=0)
    question = await seed_question(
        admin_engine,
        course_id=UUID(pool.course_id),
        topic_id=pool.topic_id,
        source_chunk_id=pool.chunk_ids[0],
        payload=_payload(QuestionType.CODE_TRACE),
        question_type=QuestionType.CODE_TRACE,
        status="approved",
        reviewed_by=pool.instructor_id,
    )
    completion = FakeCompletion(_verdict(pool.chunk_ids[0], invalid=True))
    question_gen.set_providers(completion=completion)
    try:
        identity = (await start(client, pool, mode))["id"]
        base = f"/courses/{pool.course_id}/exams/{identity}"
        saved = await client.post(
            base + "/answers",
            headers=pool.student,
            json={"question_id": str(question), "given": "Kilitleri bekler."},
        )
        assert saved.status_code == 201, saved.text
        assert completion.calls == 2
        finished = await client.post(base + "/finish", headers=pool.student)
        assert finished.status_code == 200, finished.text
        assert finished.json()["ungraded_count"] == 1
        for result in (saved.json(), finished.json()["results"][0]):
            assert result["graded"] is False
            assert result["score"] is None
            assert result["solution"] is None
            assert result["evidence"] is None
            assert result["grounded_missing_criterion"] is None
            assert result["missing_points"] == [] and result["rubric_breakdown"] == []
        async with rls_session(user_id=pool.student_id) as session:
            assert await session.scalar(text("SELECT count(*) FROM mastery")) == 0
    finally:
        question_gen.reset_providers()


@pytest.mark.parametrize("kind", [QuestionType.CODE_TRACE, QuestionType.BUG_HUNT])
async def test_code_rubric_is_instructor_editable_and_rejects_invalid_write_atomically(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    kind: QuestionType,
) -> None:
    monkeypatch.setenv("QUESTION_AUTHORING_ENABLED", "true")
    get_settings.cache_clear()
    try:
        pool = await build_course(client, users, admin_engine, approved=0)
        raw = _payload(kind)
        raw.pop("rubric")  # Eski kod taslağına eğitmen ölçütleri eklenir.
        question = await seed_question(
            admin_engine,
            course_id=UUID(pool.course_id),
            topic_id=pool.topic_id,
            source_chunk_id=pool.chunk_ids[0],
            payload=raw,
            question_type=kind,
        )
        path = f"/courses/{pool.course_id}/questions/{question}/draft"
        edit = {"payload": _payload(kind), "learning_outcome_id": None, "difficulty": None}
        denied = await client.post(path, headers=pool.student, json=edit)
        assert denied.status_code == 403, denied.text
        saved = await client.post(path, headers=pool.instructor, json=edit)
        assert saved.status_code == 200, saved.text
        assert saved.json()["payload"]["rubric"] == RUBRIC
        for case in ("duplicate", "empty", "omitted"):
            invalid = deepcopy(edit)
            if case == "duplicate":
                invalid["payload"]["rubric"][1]["point"] = RUBRIC[0]["point"]
            elif case == "empty":
                invalid["payload"]["rubric"] = []
            else:
                invalid["payload"].pop("rubric")
            rejected = await client.post(path, headers=pool.instructor, json=invalid)
            assert rejected.status_code == 422, (case, rejected.text)
            assert rejected.json()["error"]["code"] == "validation_error"
            async with admin_engine.connect() as conn:
                persisted = await conn.scalar(
                    text("SELECT payload FROM questions WHERE id = :id"), {"id": question}
                )
            assert persisted == saved.json()["payload"], case
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("kind", [QuestionType.CODE_TRACE, QuestionType.BUG_HUNT])
async def test_legacy_rubricless_code_remains_readable_without_new_write(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    kind: QuestionType,
) -> None:
    pool = await build_course(client, users, admin_engine, approved=0)
    legacy = _payload(kind)
    legacy.pop("rubric")
    identity = await seed_question(
        admin_engine,
        course_id=UUID(pool.course_id),
        topic_id=pool.topic_id,
        source_chunk_id=pool.chunk_ids[0],
        payload=legacy,
        question_type=kind,
        status="approved",
        reviewed_by=pool.instructor_id,
    )
    path = f"/courses/{pool.course_id}/questions"
    instructor = await client.get(path, headers=pool.instructor)
    assert instructor.status_code == 200, instructor.text
    item = next(row for row in instructor.json()["items"] if row["id"] == str(identity))
    assert item["payload"] == legacy
    student = await client.get(path, headers=pool.student)
    assert student.status_code == 200, student.text
    public = next(row for row in student.json()["items"] if row["id"] == str(identity))
    assert public["payload"]["code"] == legacy["code"]
    assert "answer_key" not in public["payload"] and "rubric" not in public["payload"]
