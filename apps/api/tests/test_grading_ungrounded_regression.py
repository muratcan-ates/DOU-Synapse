"""Ungrounded grading regression path for public demo safety.

When LLM evidence cannot be validated, grading stays ungraded and the exam flow
stores that result without a score, explanation, or source.
"""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.db import rls_session
from app.models.assessment import QuestionType
from app.modules.assessment import question_gen
from app.modules.assessment.grading import GradingOutcome, grade_with_llm
from app.schemas.assessment import OpenPayload
from tests.factories import (
    ESSAY_PAYLOAD,
    FakeCompletion,
    build_course,
    seed_question,
    start,
)


def _verdict(evidence: str | None = None, *, missing_field: bool = False) -> str:
    value: dict[str, object] = {
        "score": 88,
        "eksik_noktalar": ["Dayanaksız iddia güvenilmez."],
        "rubrik": [{"olcut": "Ana kavram", "puan": 88}],
    }
    if not missing_field:
        value["dayanak_chunk_id"] = evidence
    return json.dumps(value)


def _assert_ungrounded(outcome: GradingOutcome) -> None:
    assert outcome.graded is False
    assert outcome.score is None
    assert outcome.evidence_chunk_id is None
    assert outcome.why_wrong_chunk_id is None
    assert outcome.message is not None
    assert "tamamlanamadı" in (outcome.message or "")


@pytest.mark.parametrize("evidence_case", ["invented", "null", "missing"])
async def test_grade_with_invalid_dayanak_stays_ungrounded(
    evidence_case: str,
) -> None:
    completion = FakeCompletion(
        _verdict(
            str(uuid4()) if evidence_case == "invented" else None,
            missing_field=evidence_case == "missing",
        )
    )
    outcome = await grade_with_llm(
        completion,
        payload=OpenPayload.model_validate(ESSAY_PAYLOAD),
        given="Çözüm: 1+1=2.",
        sources=[(uuid4(), "Kaynağa bağlı bir metin.")],
    )
    assert completion.calls == 2
    _assert_ungrounded(outcome)


@pytest.mark.parametrize("mode", ["practice", "exam"])
async def test_posting_answer_with_invalid_dayanak_is_recorded_without_score(
    client: AsyncClient,
    admin_engine,
    users,
    mode: str,
) -> None:
    fixture = await build_course(client, users, admin_engine, approved=0)
    question_id = await seed_question(
        admin_engine,
        course_id=UUID(fixture.course_id),
        topic_id=fixture.topic_id,
        source_chunk_id=fixture.chunk_ids[0],
        payload=ESSAY_PAYLOAD,
        question_type=QuestionType.OPEN,
        status="approved",
        reviewed_by=fixture.instructor_id,
    )
    completion = FakeCompletion(_verdict(str(uuid4())))
    question_gen.set_providers(completion=completion)
    try:
        session_id = (await start(client, fixture, mode))["id"]
        response = await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/answers",
            json={"question_id": str(question_id), "given": "Dört koşul vardır."},
            headers=fixture.student,
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["graded"] is False
        assert body["score"] is None
        assert body["solution"] is None
        assert body["evidence"] is None
        assert body["message"] is not None and "tamamlanamadı" in body["message"]
        assert body["missing_points"] == []
        assert body["rubric_breakdown"] == []

        async with rls_session(user_id=fixture.student_id) as database:
            stored = await database.execute(
                text(
                    "SELECT feedback->>'dayanak_chunk_id' AS dayanak_chunk_id "
                    "FROM answers "
                    "WHERE session_id = :session_id AND question_id = :question_id"
                ),
                {"session_id": str(session_id), "question_id": str(question_id)},
            )
            row = stored.fetchone()
            assert row is not None
            assert row[0] is None
    finally:
        question_gen.reset_providers()
