"""Hazır açıklamalarla B9 API/kayıt sınırları; anlamsal kalite iddiası yoktur."""

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

from app.api import exams as exam_api
from app.core.config import get_settings
from app.models.assessment import QuestionType
from app.modules.assessment import question_gen
from tests.conftest import UserFactory
from tests.factories import (
    DEADLOCK_TEXTS,
    ESSAY_PAYLOAD,
    ExamFixture,
    FakeCompletion,
    build_course,
    create_course,
    enroll_student,
    seed_document,
    seed_question,
    short_answer_payload,
    start,
)

QUOTE = DEADLOCK_TEXTS[0]
NEXT_HINT = "Alıntıdaki koşulları kendi cevabınla tek tek karşılaştır."
KINDS = ("essay", "short_answer", "code_trace", "bug_hunt")


@pytest.fixture(autouse=True)
def workspace_enabled(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("STUDENT_ASSESSMENT_WORKSPACE_ENABLED", "true")
    get_settings.cache_clear()
    yield
    question_gen.reset_providers()
    get_settings.cache_clear()


def _payload(kind: str) -> dict[str, Any]:
    if kind == "essay":
        return deepcopy(ESSAY_PAYLOAD)
    if kind == "short_answer":
        return short_answer_payload()
    return {
        "language": "pseudocode",
        "code": "T1: lock(A); lock(B)\nT2: lock(B); lock(A)",
        "prompt": "Kilit sırasının beklemeye etkisini inceleyin.",
        "answer_key": "Döngüsel bekleme oluşabilir."
        if kind == "code_trace"
        else {
            "line": 2,
            "bug_type": "Kilit sırası",
            "fix_summary": "Aynı sırayı kullanın.",
        },
    }


def _wrong_given(kind: str) -> str:
    if kind == "bug_hunt":
        # Geçerli ve kesin yanlış satır; serbest metinden tahmin edilmez.
        return json.dumps(
            {"version": 1, "line": 1, "bug_type": "Kilit sırası", "fix_summary": "Düzelt."}
        )
    return "Kaynakların aynı anda beklenmesi gerekmez."


def _verdict(chunk_id: UUID) -> str:
    return json.dumps(
        {
            "score": 80,
            "eksik_noktalar": ["Dört koşulun birlikte gerçekleşmesini açıklayın."],
            "dayanak_chunk_id": str(chunk_id),
            "rubrik": [{"olcut": "Dört koşulu sayar", "puan": 80}],
            "grounded_feedback": {
                "chunk_id": str(chunk_id),
                "quote": QUOTE,
                "next_hint": NEXT_HINT,
            },
        },
        ensure_ascii=False,
    )


async def _pool(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine, kind: str
) -> tuple[ExamFixture, UUID]:
    pool = await build_course(client, users, admin_engine, approved=0)
    question = await _question(admin_engine, pool, kind, pool.chunk_ids[0])
    return pool, question


async def _question(
    admin_engine: AsyncEngine, pool: ExamFixture, kind: str, source_id: UUID
) -> UUID:
    return await seed_question(
        admin_engine,
        course_id=UUID(pool.course_id),
        topic_id=pool.topic_id,
        source_chunk_id=source_id,
        payload=_payload(kind),
        question_type=QuestionType.OPEN
        if kind in ("essay", "short_answer")
        else QuestionType(kind),
        status="approved",
        reviewed_by=pool.instructor_id,
    )


def _hidden(body: dict[str, Any]) -> None:
    assert body["graded"] is False
    for field in (
        "score",
        "is_correct",
        "solution",
        "why_wrong",
        "evidence",
        "next_hint",
    ):
        assert body[field] is None, field
    assert body["grounded_missing_criterion"] is None
    assert body["missing_points"] == [] and body["rubric_breakdown"] == []


def _grounded(body: dict[str, Any], pool: ExamFixture) -> None:
    assert body["graded"] is True
    source = body["why_wrong"]
    assert source["chunk_id"] == str(pool.chunk_ids[0])
    assert source["file_name"] == "isletim-sistemleri.pdf"
    assert source["location"] == "Sayfa 1"
    assert source["snippet"].strip() and source["snippet"] in QUOTE
    assert body["next_hint"]["text"].strip()
    assert body["next_hint"]["source"] == source
    assert body["solution"] is not None


async def _answer_snapshot(admin_engine: AsyncEngine, identity: str) -> dict[str, Any]:
    async with admin_engine.connect() as conn:
        row = (
            (
                await conn.execute(
                    text(
                        "SELECT score, is_correct, hint_level, feedback "
                        "FROM answers WHERE session_id = :id"
                    ),
                    {"id": UUID(identity)},
                )
            )
            .mappings()
            .one()
        )
    return dict(row)


@pytest.mark.parametrize("kind", KINDS)
async def test_wrong_feedback_reopens_with_literal_source_and_next_hint_without_regrading(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine, kind: str
) -> None:
    pool, question = await _pool(client, users, admin_engine, kind)
    completion = FakeCompletion(_verdict(pool.chunk_ids[0]))
    question_gen.set_providers(completion=completion)
    identity = (await start(client, pool, "practice"))["id"]
    base = f"/courses/{pool.course_id}/exams/{identity}"
    response = await client.post(
        base + "/answers",
        headers=pool.student,
        json={"question_id": str(question), "given": _wrong_given(kind)},
    )
    assert response.status_code == 201, response.text
    immediate = response.json()
    _grounded(immediate, pool)
    assert immediate["score"] == (80 if kind == "essay" else 0)
    if kind != "essay":
        assert immediate["rubric_breakdown"] == []
    calls = 0 if kind == "short_answer" else 1
    assert completion.calls == calls
    before = await _answer_snapshot(admin_engine, identity)
    assert before["feedback"]["feedback_version"] == 1
    assert before["feedback"]["grounded_feedback"]["quote"] == immediate["why_wrong"]["snippet"]
    assert before["hint_level"] == 0  # Geri bildirim, cevap öncesi ipucu kullanımı sayılmaz.
    reopened = await client.get(base + f"/answers/{question}", headers=pool.student)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json() == immediate
    finished = await client.post(base + "/finish", headers=pool.student)
    assert finished.status_code == 200, finished.text
    assert finished.json()["results"] == [immediate]
    again = await client.get(base + "/results", headers=pool.student)
    assert again.status_code == 200, again.text
    assert again.json() == finished.json()
    assert completion.calls == calls
    assert await _answer_snapshot(admin_engine, identity) == before
    denied = await client.get(base + f"/answers/{question}", headers=pool.instructor)
    assert denied.status_code == 404, denied.text
    assert NEXT_HINT not in denied.text and QUOTE not in denied.text


@pytest.mark.parametrize("source_change", ["quote_changed", "blank", "unreadable"])
async def test_changed_source_hides_new_feedback_in_detail_totals_and_history(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    source_change: str,
) -> None:
    pool, question = await _pool(client, users, admin_engine, "essay")
    completion = FakeCompletion(_verdict(pool.chunk_ids[0]))
    question_gen.set_providers(completion=completion)
    identity = (await start(client, pool, "practice"))["id"]
    base = f"/courses/{pool.course_id}/exams"
    response = await client.post(
        f"{base}/{identity}/answers",
        headers=pool.student,
        json={"question_id": str(question), "given": _wrong_given("essay")},
    )
    assert response.status_code == 201, response.text
    _grounded(response.json(), pool)
    finished = await client.post(f"{base}/{identity}/finish", headers=pool.student)
    assert finished.status_code == 200, finished.text
    before = await _answer_snapshot(admin_engine, identity)
    if source_change == "unreadable":

        async def unavailable(*args: Any, **kwargs: Any) -> dict[Any, Any]:
            return {}

        monkeypatch.setattr(exam_api, "load_source_material", unavailable)
    else:
        async with admin_engine.begin() as conn:
            await conn.execute(
                text("UPDATE chunks SET text = :body WHERE id = :id"),
                {
                    "id": pool.chunk_ids[0],
                    "body": "Yeni kaynak metni." if source_change == "quote_changed" else " \n\t",
                },
            )
    saved = await client.get(f"{base}/{identity}/answers/{question}", headers=pool.student)
    assert saved.status_code == 200, saved.text
    _hidden(saved.json())
    results = await client.get(f"{base}/{identity}/results", headers=pool.student)
    assert results.status_code == 200, results.text
    assert results.json()["score"] is None and results.json()["ungraded_count"] == 1
    _hidden(results.json()["results"][0])
    for suffix in ("", "/history", f"/{identity}"):
        response = await client.get(base + suffix, headers=pool.student)
        assert response.status_code == 200, response.text
        body = response.json()
        rows = body["items"] if suffix == "/history" else [body] if suffix else body
        assert next(row for row in rows if row["id"] == identity)["score"] is None
    assert completion.calls == 1
    assert await _answer_snapshot(admin_engine, identity) == before


@pytest.mark.parametrize("kind", KINDS)
async def test_blank_source_records_ungraded_answer_without_provider_or_mastery(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine, kind: str
) -> None:
    pool, question = await _pool(client, users, admin_engine, kind)
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE chunks SET text = ' ' WHERE id = :id"),
            {"id": pool.chunk_ids[0]},
        )
    completion = FakeCompletion(_verdict(pool.chunk_ids[0]))
    question_gen.set_providers(completion=completion)
    identity = (await start(client, pool, "practice"))["id"]
    response = await client.post(
        f"/courses/{pool.course_id}/exams/{identity}/answers",
        headers=pool.student,
        json={"question_id": str(question), "given": _wrong_given(kind)},
    )
    assert response.status_code == 201, response.text
    _hidden(response.json())
    assert completion.calls == 0
    async with admin_engine.connect() as conn:
        assert (
            await conn.scalar(
                text("SELECT count(*) FROM mastery WHERE course_id = :id"),
                {"id": UUID(pool.course_id)},
            )
            == 0
        )
    snapshot = await _answer_snapshot(admin_engine, identity)
    assert snapshot["score"] is None and snapshot["is_correct"] is None


async def test_exam_reveal_and_other_exam_lock_withhold_next_hint_and_all_evidence(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
) -> None:
    pool, question = await _pool(client, users, admin_engine, "essay")
    completion = FakeCompletion(_verdict(pool.chunk_ids[0]))
    question_gen.set_providers(completion=completion)
    identity = (await start(client, pool, "exam"))["id"]
    base = f"/courses/{pool.course_id}/exams"
    response = await client.post(
        f"{base}/{identity}/answers",
        headers=pool.student,
        json={"question_id": str(question), "given": _wrong_given("essay")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["graded"] is True
    for field in (
        "score",
        "is_correct",
        "solution",
        "evidence",
        "why_wrong",
        "next_hint",
    ):
        assert body[field] is None, field
    assert body["missing_points"] == [] and body["rubric_breakdown"] == []
    other = (await start(client, pool, "exam"))["id"]
    finished = await client.post(f"{base}/{identity}/finish", headers=pool.student)
    assert finished.status_code == 200, finished.text
    assert finished.json()["results_locked"] is True
    assert finished.json()["results"] == [] and finished.json()["score"] is None
    blocked = await client.get(f"{base}/{identity}/results", headers=pool.student)
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "exam_in_progress"
    assert NEXT_HINT not in blocked.text and QUOTE not in blocked.text
    assert (await client.post(f"{base}/{other}/finish", headers=pool.student)).status_code == 200
    reopened = await client.get(f"{base}/{identity}/results", headers=pool.student)
    assert reopened.status_code == 200, reopened.text
    _grounded(reopened.json()["results"][0], pool)
    assert completion.calls == 1


async def test_malformed_saved_new_evidence_cannot_fall_back_to_legacy_display(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
) -> None:
    pool, question = await _pool(client, users, admin_engine, "essay")
    completion = FakeCompletion(_verdict(pool.chunk_ids[0]))
    question_gen.set_providers(completion=completion)
    identity = (await start(client, pool, "practice"))["id"]
    base = f"/courses/{pool.course_id}/exams/{identity}"
    response = await client.post(
        base + "/answers",
        headers=pool.student,
        json={"question_id": str(question), "given": _wrong_given("essay")},
    )
    assert response.status_code == 201, response.text
    original = (await _answer_snapshot(admin_engine, identity))["feedback"]
    for case in (
        "missing_claim",
        "missing_version",
        "unknown_version",
        "bool_version",
        "blank_hint",
        "quote_changed",
        "other_chunk",
        "malformed_rubric",
    ):
        broken = deepcopy(original)
        if case == "missing_claim":
            broken.pop("grounded_feedback")
        elif case == "missing_version":
            broken.pop("feedback_version")
        elif case == "unknown_version":
            broken["feedback_version"] = 99
        elif case == "bool_version":
            broken["feedback_version"] = True
        elif case == "blank_hint":
            broken["grounded_feedback"]["next_hint"] = " "
        elif case == "quote_changed":
            broken["grounded_feedback"]["quote"] = "Kaynakta bulunmayan iddia."
        elif case == "other_chunk":
            broken["grounded_feedback"]["chunk_id"] = str(pool.chunk_ids[1])
        else:
            broken["rubrik_kirilimi"] = [{"score": "invalid"}]
        async with admin_engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE answers SET feedback = CAST(:feedback AS jsonb) WHERE session_id = :id"
                ),
                {"id": UUID(identity), "feedback": json.dumps(broken)},
            )
        before = await _answer_snapshot(admin_engine, identity)
        saved = await client.get(base + f"/answers/{question}", headers=pool.student)
        assert saved.status_code == 200, (case, saved.text)
        _hidden(saved.json())
        assert await _answer_snapshot(admin_engine, identity) == before
    assert completion.calls == 1


async def test_readable_other_course_source_cannot_grade_or_reveal_new_feedback(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
) -> None:
    pool = await build_course(client, users, admin_engine, approved=0)
    other_course = await create_course(client, pool.instructor, "COME399")
    await enroll_student(client, pool.instructor, other_course, "burak@dogus.edu.tr")
    document = await seed_document(
        admin_engine,
        course_id=other_course,
        uploaded_by=pool.instructor_id,
        passages=[QUOTE],
    )
    foreign_source = document.chunk_ids[0]
    question = await _question(admin_engine, pool, "essay", foreign_source)
    completion = FakeCompletion(_verdict(foreign_source))
    question_gen.set_providers(completion=completion)
    identity = (await start(client, pool, "practice"))["id"]
    base = f"/courses/{pool.course_id}/exams/{identity}"
    response = await client.post(
        base + "/answers",
        headers=pool.student,
        json={"question_id": str(question), "given": _wrong_given("essay")},
    )
    assert response.status_code == 201, response.text
    _hidden(response.json())
    assert completion.calls == 0
    # Sentetik bozuk eski kayıt, kayıtlı cevabın ders kontrolünü ayrı sınar:
    # tüm kimlikler ve alıntı eşleşir; öğrenci iki dersi de okuyabilir.
    feedback = {
        "durum": "degerlendirildi",
        "feedback_version": 1,
        "dayanak_chunk_id": str(foreign_source),
        "grounded_feedback": {
            "chunk_id": str(foreign_source),
            "quote": QUOTE,
            "next_hint": NEXT_HINT,
        },
    }
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE answers SET score = 80, is_correct = true, "
                "feedback = CAST(:feedback AS jsonb) WHERE session_id = :id"
            ),
            {"id": UUID(identity), "feedback": json.dumps(feedback)},
        )
    before = await _answer_snapshot(admin_engine, identity)
    saved = await client.get(base + f"/answers/{question}", headers=pool.student)
    assert saved.status_code == 200, saved.text
    _hidden(saved.json())
    assert await _answer_snapshot(admin_engine, identity) == before
    assert completion.calls == 0


async def test_after_answer_feedback_does_not_reopen_disabled_pre_answer_hints(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
) -> None:
    pool, question = await _pool(client, users, admin_engine, "essay")
    policy = await client.put(
        f"/courses/{pool.course_id}/ai-policy",
        headers=pool.instructor,
        json={
            "allowed_modes": ["qa"],
            "hint_limit": 0,
            "evidence_threshold": 0.72,
            "daily_llm_budget": 500,
            "source_document_ids": None,
        },
    )
    assert policy.status_code == 200, policy.text
    completion = FakeCompletion(_verdict(pool.chunk_ids[0]))
    question_gen.set_providers(completion=completion)
    identity = (await start(client, pool, "practice"))["id"]
    base = f"/courses/{pool.course_id}/exams/{identity}"
    denied = await client.post(
        base + "/hint",
        headers=pool.student,
        json={"question_id": str(question), "hint_level": 1},
    )
    assert denied.status_code == 403, denied.text
    assert NEXT_HINT not in denied.text and QUOTE not in denied.text
    answered = await client.post(
        base + "/answers",
        headers=pool.student,
        json={"question_id": str(question), "given": _wrong_given("essay")},
    )
    assert answered.status_code == 201, answered.text
    _grounded(answered.json(), pool)
    assert (await _answer_snapshot(admin_engine, identity))["hint_level"] == 0
    async with admin_engine.connect() as conn:
        assert (
            await conn.scalar(
                text(
                    "SELECT count(*) FROM learning_events "
                    "WHERE course_id = :id AND event_type = 'hint_requested'"
                ),
                {"id": UUID(pool.course_id)},
            )
            == 0
        )


async def test_correct_code_oracle_needs_no_explanation_but_saved_score_needs_current_source(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
) -> None:
    pool, question = await _pool(client, users, admin_engine, "code_trace")
    completion = FakeCompletion("Deterministik doğru cevap bu sağlayıcıyı çağırmamalı.")
    question_gen.set_providers(completion=completion)
    identity = (await start(client, pool, "practice"))["id"]
    base = f"/courses/{pool.course_id}/exams/{identity}"
    response = await client.post(
        base + "/answers",
        headers=pool.student,
        json={"question_id": str(question), "given": _payload("code_trace")["answer_key"]},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["graded"] is True and body["score"] == 100
    assert body["why_wrong"] is None and body["next_hint"] is None
    assert body["rubric_breakdown"] == [] and body["solution"] is not None
    assert completion.calls == 0
    before = await _answer_snapshot(admin_engine, identity)
    assert before["feedback"]["feedback_version"] == 1
    assert before["feedback"]["grounded_feedback"] is None
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE chunks SET text = '' WHERE id = :id"), {"id": pool.chunk_ids[0]}
        )
    saved = await client.get(base + f"/answers/{question}", headers=pool.student)
    assert saved.status_code == 200, saved.text
    _hidden(saved.json())
    assert completion.calls == 0
    assert await _answer_snapshot(admin_engine, identity) == before


@pytest.mark.parametrize("answer_kind", ["wrong", "correct"])
async def test_wrong_course_document_link_blocks_grading_and_saved_feedback_before_side_effects(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    answer_kind: str,
) -> None:
    pool, question = await _pool(client, users, admin_engine, "code_trace")
    other_course = await create_course(client, pool.instructor, "COME398")
    await enroll_student(client, pool.instructor, other_course, "burak@dogus.edu.tr")
    other_document = await seed_document(
        admin_engine,
        course_id=other_course,
        uploaded_by=pool.instructor_id,
        passages=[QUOTE],
        file_name="diger-ders.pdf",
    )
    # İki dersin kaynaklarına gerçekten erişilir; ret eksik üyelikten kaynaklanamaz.
    for course_id, chunk_id in (
        (UUID(pool.course_id), pool.chunk_ids[0]),
        (other_course, other_document.chunk_ids[0]),
    ):
        readable = await client.get(
            f"/courses/{course_id}/sources/{chunk_id}", headers=pool.student
        )
        assert readable.status_code == 200, readable.text
    async with admin_engine.begin() as conn:
        # Sentetik bozuk bağlantı: parça A dersinde kalır, belge B dersine aittir.
        # B belgesinin mevcut 0 indisli parçasına çarpmamak için 1 indisi kullanılır.
        changed = await conn.scalar(
            text(
                "UPDATE chunks SET document_id = :document, chunk_index = 1 "
                "WHERE id = :id AND course_id = :course RETURNING id"
            ),
            {
                "id": pool.chunk_ids[0],
                "course": UUID(pool.course_id),
                "document": other_document.document_id,
            },
        )
        assert changed == pool.chunk_ids[0]
        relation = (
            (
                await conn.execute(
                    text(
                        "SELECT ch.course_id AS chunk_course, d.course_id AS document_course "
                        "FROM chunks ch JOIN documents d ON d.id = ch.document_id WHERE ch.id = :id"
                    ),
                    {"id": pool.chunk_ids[0]},
                )
            )
            .mappings()
            .one()
        )
        assert relation["chunk_course"] == UUID(pool.course_id)
        assert relation["document_course"] == other_course
    completion = FakeCompletion(_verdict(pool.chunk_ids[0]))
    question_gen.set_providers(completion=completion)
    identity = (await start(client, pool, "practice"))["id"]
    base = f"/courses/{pool.course_id}/exams/{identity}"
    given = (
        _payload("code_trace")["answer_key"]
        if answer_kind == "correct"
        else _wrong_given("code_trace")
    )
    response = await client.post(
        base + "/answers",
        headers=pool.student,
        json={"question_id": str(question), "given": given},
    )
    assert response.status_code == 201, response.text
    _hidden(response.json())
    assert completion.calls == 0
    original = await _answer_snapshot(admin_engine, identity)
    assert original["score"] is None and original["is_correct"] is None
    async with admin_engine.connect() as conn:
        assert (
            await conn.scalar(
                text("SELECT count(*) FROM mastery WHERE course_id = :id"),
                {"id": UUID(pool.course_id)},
            )
            == 0
        )
    # Eski bozuk bir notu taklit eder; okuma kontrolü notlandırma reddinden ayrı sınanır.
    synthetic_feedback = {
        "durum": "degerlendirildi",
        "feedback_version": 1,
        "dayanak_chunk_id": str(pool.chunk_ids[0]),
        "grounded_feedback": None
        if answer_kind == "correct"
        else {"chunk_id": str(pool.chunk_ids[0]), "quote": QUOTE, "next_hint": NEXT_HINT},
    }
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE answers SET score = :score, is_correct = :correct, "
                "feedback = CAST(:feedback AS jsonb) WHERE session_id = :id"
            ),
            {
                "id": UUID(identity),
                "score": 100 if answer_kind == "correct" else 0,
                "correct": answer_kind == "correct",
                "feedback": json.dumps(synthetic_feedback),
            },
        )
    before = await _answer_snapshot(admin_engine, identity)
    saved = await client.get(base + f"/answers/{question}", headers=pool.student)
    assert saved.status_code == 200, saved.text
    _hidden(saved.json())
    finished = await client.post(base + "/finish", headers=pool.student)
    assert finished.status_code == 200, finished.text
    assert finished.json()["score"] is None and finished.json()["ungraded_count"] == 1
    _hidden(finished.json()["results"][0])
    assert await _answer_snapshot(admin_engine, identity) == before
    assert completion.calls == 0
    async with admin_engine.connect() as conn:
        assert (
            await conn.scalar(
                text("SELECT count(*) FROM mastery WHERE course_id = :id"),
                {"id": UUID(pool.course_id)},
            )
            == 0
        )
