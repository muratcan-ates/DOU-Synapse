"""Deterministic acceptance evidence for P3 score validation."""

from __future__ import annotations

import json
from uuid import UUID

import pytest
from app.models.assessment import QuestionType
from app.modules.assessment.grading import grade_mcq, grade_short_answer, grade_with_llm
from app.schemas.assessment import parse_payload

from evaluation.acceptance.code_oracle import (
    BUG_HUNT_ORACLE_CASES,
    CODE_TRACE_ORACLE_CASES,
    OracleAnswer,
    OracleCase,
)
from tests.factories import FakeCompletion


MCQ_PAYLOAD = {
    "stem": "fork() çağrısından sonra child süreç hangi pid değeri alır?",
    "options": [
        {"key": "A", "text": "Hem ebeveyn hem çocuk aynı pid döner"},
        {"key": "B", "text": "Çocuk 0, ebeveyn çocuk pid'sini döner"},
        {"key": "C", "text": "Çocuk ebeveyn pid'sini döner"},
    ],
    "answer_key": "B",
    "distractor_sources": {
        "A": "f9f4f6ad-6b16-4a55-9ef7-8f8abac7d5ab",
        "C": "2a5e4f74-58e7-4ecf-b6d7-4b0bf4f8ec4e",
    },
}


SHORT_ANSWER_PAYLOAD = {
    "prompt": "Deadlock için gerekli koşullardan hangisi yanlış bir koşuldur?",
    "answer_key": "kesme zorunluluğu",
    "accepted_answers": ["preemption", "preemption (önceliksiz alma)", "preemptive"],
    "format": "short_answer",
}

SHORT_SOURCE_ID = UUID("e7be1f3e-5c7d-4eb8-a0fd-fdf9f5dff6dd")


def _build_oracle_verdict(answer: OracleAnswer, source_id: str) -> str:
    return json.dumps(
        {
            "score": answer.expected_score,
            "eksik_noktalar": answer.expected_missing_points,
            "dayanak_chunk_id": source_id,
            "rubrik": [
                {"olcut": "Deterministik kontrol", "puan": answer.expected_score},
            ],
        }
    )


@pytest.mark.parametrize(
    "given, expected_score, expected_is_correct",
    [
        ("B", 100, True),
        ("A", 0, False),
        ("X", 0, False),
    ],
)
def test_mcq_deterministic_scoring_and_rejected_options(given: str, expected_score: int, expected_is_correct: bool | None) -> None:
    payload = parse_payload(QuestionType.MCQ, MCQ_PAYLOAD)
    outcome = grade_mcq(payload, given)
    assert outcome.graded is True
    assert outcome.score == expected_score
    assert outcome.is_correct is expected_is_correct


@pytest.mark.parametrize(
    "given, expected_score, expected_is_correct",
    [
        ("preemption", 100, True),
        (" preemptive ", 100, True),
        ("öncelikle kesme", 0, False),
    ],
)
def test_short_answer_deterministic_normalization(given: str, expected_score: int, expected_is_correct: bool | None) -> None:
    payload = parse_payload(QuestionType.OPEN, SHORT_ANSWER_PAYLOAD)
    outcome = grade_short_answer(payload, given, source_chunk_id=SHORT_SOURCE_ID)
    assert outcome.graded is True
    assert outcome.score == expected_score
    assert outcome.is_correct is expected_is_correct


@pytest.mark.parametrize("case", CODE_TRACE_ORACLE_CASES)
@pytest.mark.asyncio
async def test_code_trace_oracle_cases_are_deterministic(case: OracleCase) -> None:
    payload = parse_payload(case.question_type, case.payload)
    for answer in case.answers:
        completion = FakeCompletion(_build_oracle_verdict(answer, str(case.source_id)))
        result = await grade_with_llm(
            completion,
            payload=payload,
            given=answer.answer,
            sources=[(case.source_id, case.source_text)],
        )
        assert completion.calls == 1
        assert result.graded is True
        assert result.score == answer.expected_score
        assert result.missing_points == answer.expected_missing_points
        assert result.evidence_chunk_id == case.source_id


@pytest.mark.parametrize("case", BUG_HUNT_ORACLE_CASES)
@pytest.mark.asyncio
async def test_bug_hunt_oracle_cases_are_deterministic(case: OracleCase) -> None:
    payload = parse_payload(case.question_type, case.payload)
    for answer in case.answers:
        completion = FakeCompletion(_build_oracle_verdict(answer, str(case.source_id)))
        result = await grade_with_llm(
            completion,
            payload=payload,
            given=answer.answer,
            sources=[(case.source_id, case.source_text)],
        )
        assert completion.calls == 1
        assert result.graded is True
        assert result.score == answer.expected_score
        assert result.missing_points == answer.expected_missing_points
        assert result.evidence_chunk_id == case.source_id
