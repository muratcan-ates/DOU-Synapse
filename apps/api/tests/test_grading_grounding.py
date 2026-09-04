"""Mail acceptance: AI assessment needs a readable course source before scoring.

Scripted providers prove fail-closed control flow, not semantic grading quality.
"""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db import rls_session
from app.models.assessment import QuestionType
from app.modules.assessment import question_gen
from app.modules.assessment.grading import GradingOutcome, grade_with_llm
from app.schemas.assessment import BugHuntPayload, CodeTracePayload, OpenPayload
from tests.conftest import UserFactory
from tests.factories import (
    DEADLOCK_TEXTS,
    ESSAY_PAYLOAD,
    FakeCompletion,
    build_course,
    seed_question,
    start,
)


def _verdict(evidence: str | None = None, *, missing_field: bool = False) -> str:
    value: dict[str, object] = {
        "score": 80,
        "eksik_noktalar": ["Modelin doğrulanmamış iddiası"],
        "rubrik": [{"olcut": "Dört koşulu sayar", "puan": 80}],
    }
    if not missing_field:
        value["dayanak_chunk_id"] = evidence
    return json.dumps(value)


@pytest.fixture(params=["essay", "code_trace", "bug_hunt"])
def payload(request: pytest.FixtureRequest) -> BaseModel:
    if request.param == "code_trace":
        return CodeTracePayload(
            language="Python", code="print(1)", prompt="Kodun çıktısı nedir?", answer_key="1"
        )
    if request.param == "bug_hunt":
        return BugHuntPayload(
            language="Python",
            code="print(total)",
            prompt="Koddaki hatayı bulun.",
            answer_key={"line": 1, "bug_type": "NameError", "fix_summary": "total tanımlanmalı"},
        )
    return OpenPayload.model_validate(ESSAY_PAYLOAD)


def _assert_ungraded(outcome: GradingOutcome) -> None:
    assert outcome.graded is False
    assert outcome.score is None
    assert outcome.is_correct is None
    assert outcome.evidence_chunk_id is None
    assert outcome.why_wrong_chunk_id is None
    assert outcome.missing_points == []
    assert outcome.rubric_breakdown == []
    assert outcome.focus is None
    assert "tamamlanamadı" in (outcome.message or "")


@pytest.mark.parametrize("evidence_case", ["invented", "null", "missing"])
async def test_invalid_evidence_exhausts_shared_two_attempt_budget(
    payload: BaseModel, evidence_case: str
) -> None:
    completion = FakeCompletion(
        _verdict(
            str(uuid4()) if evidence_case == "invented" else None,
            missing_field=evidence_case == "missing",
        )
    )
    outcome = await grade_with_llm(
        completion, payload=payload, given="Cevabım.", sources=[(uuid4(), DEADLOCK_TEXTS[0])]
    )
    assert completion.calls == 2
    _assert_ungraded(outcome)


async def test_invalid_evidence_then_valid_recovers_without_extra_calls(payload: BaseModel) -> None:
    source_id = uuid4()
    completion = FakeCompletion(_verdict(str(uuid4())), _verdict(str(source_id)))
    outcome = await grade_with_llm(
        completion, payload=payload, given="Cevabım.", sources=[(source_id, DEADLOCK_TEXTS[0])]
    )
    assert completion.calls == 2
    assert outcome.graded is True
    assert outcome.score == 80
    assert outcome.evidence_chunk_id == source_id


async def test_valid_evidence_first_attempt_is_unchanged(payload: BaseModel) -> None:
    source_id = uuid4()
    completion = FakeCompletion(_verdict(str(source_id)))
    outcome = await grade_with_llm(
        completion, payload=payload, given="Cevabım.", sources=[(source_id, DEADLOCK_TEXTS[0])]
    )
    assert completion.calls == 1
    assert outcome.graded is True
    assert outcome.score == 80
    assert outcome.evidence_chunk_id == source_id


@pytest.mark.parametrize("source_text", [None, "", " \n\t "])
async def test_no_readable_sources_never_calls_provider(
    payload: BaseModel, source_text: str | None
) -> None:
    source_id = uuid4()
    completion = FakeCompletion(_verdict(str(source_id)))
    sources = [] if source_text is None else [(source_id, source_text)]
    outcome = await grade_with_llm(completion, payload=payload, given="Cevabım.", sources=sources)
    assert completion.calls == 0
    _assert_ungraded(outcome)


async def test_empty_source_is_not_valid_even_when_another_source_is_readable() -> None:
    empty_id, valid_id = uuid4(), uuid4()
    completion = FakeCompletion(_verdict(str(empty_id)))
    outcome = await grade_with_llm(
        completion,
        payload=OpenPayload.model_validate(ESSAY_PAYLOAD),
        given="Cevabım.",
        sources=[(empty_id, " "), (valid_id, DEADLOCK_TEXTS[0])],
    )
    assert completion.calls == 2
    _assert_ungraded(outcome)


async def test_schema_and_evidence_failures_share_one_retry_budget() -> None:
    completion = FakeCompletion("not json", _verdict(str(uuid4())), _verdict(str(uuid4())))
    outcome = await grade_with_llm(
        completion,
        payload=OpenPayload.model_validate(ESSAY_PAYLOAD),
        given="Cevabım.",
        sources=[(uuid4(), DEADLOCK_TEXTS[0])],
    )
    assert completion.calls == 2
    _assert_ungraded(outcome)


@pytest.mark.parametrize("mode", ["practice", "exam"])
async def test_unverified_grading_is_recorded_without_score_solution_or_mastery(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine, mode: str
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
        assert body["recorded"] is True
        assert body["graded"] is False
        assert body["score"] is None
        assert body["solution"] is None
        assert body["evidence"] is None
        assert body["missing_points"] == []
        assert body["rubric_breakdown"] == []
        assert completion.calls == 2

        finished = await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/finish", headers=fixture.student
        )
        assert finished.status_code == 200, finished.text
        result = finished.json()
        assert result["score"] is None
        assert result["ungraded_count"] == 1
        assert result["results"][0]["solution"] is None
        assert result["results"][0]["missing_points"] == []
        assert result["results"][0]["rubric_breakdown"] == []
        async with rls_session(user_id=fixture.student_id) as session:
            count = await session.scalar(text("SELECT count(*) FROM mastery"))
            assert count == 0
    finally:
        question_gen.reset_providers()
