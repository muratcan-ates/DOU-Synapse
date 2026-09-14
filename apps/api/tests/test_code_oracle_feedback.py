"""Kod puanı oracle'dan, açıklama gerçek kaynak kesitinden; hiçbir kod çalıştırılmaz."""

from __future__ import annotations

import json
from copy import deepcopy
from uuid import uuid4

import pytest

from app.modules.assessment.code_oracle import code_oracle
from app.modules.assessment.grading import grade_short_answer, grade_with_llm
from app.schemas.assessment import BugHuntPayload, CodeTracePayload, OpenPayload
from tests.factories import FakeCompletion

SOURCE = "Döngü 0, 1 ve 2 değerlerini sırayla yazdırır. Bitiş koşulu sağlanmazsa durur."
QUOTE = "Döngü 0, 1 ve 2 değerlerini sırayla yazdırır."
HINT = "Döngünün her adımını kaynak cümlesiyle karşılaştırıp çıktıyı satır satır yaz."


def trace(key: str = "0\n1\n2") -> CodeTracePayload:
    return CodeTracePayload(
        language="Python",
        code="for i in range(3):\n    print(i)",
        prompt="Kodun çıktısını satır satır yazın.",
        answer_key=key,
        rubric=[{"point": "Çıktı sırası", "weight": 100}],
    )


def bug() -> BugHuntPayload:
    return BugHuntPayload(
        language="Python",
        code="def ortalama(xs):\n    return sum(xs) / len(xs) + 1",
        prompt="Fazladan eklenen değerin hatalı satırını bulun.",
        answer_key={"line": 2, "bug_type": "yanlış aritmetik", "fix_summary": "+ 1 kaldırılmalı."},
        rubric=[{"point": "Hatalı satır", "weight": 100}],
    )


def bug_given(**updates: object) -> str:
    value: dict[str, object] = {
        "version": 1,
        "line": 2,
        "bug_type": "yanlış aritmetik",
        "fix_summary": "+ 1 kaldırılmalı.",
    }
    value.update(updates)
    return json.dumps(value, ensure_ascii=False)


def verdict(source_id, **updates: object) -> str:
    value: dict[str, object] = {
        "score": 100,
        "rubrik": [{"olcut": "İcat edilen ölçüt", "puan": 100}],
        "dayanak_chunk_id": str(source_id),
        "grounded_feedback": {"chunk_id": str(source_id), "quote": QUOTE, "next_hint": HINT},
    }
    value.update(updates)
    return json.dumps(value, ensure_ascii=False)


@pytest.mark.parametrize("given", ["0\n1\n2", "0\n1\n2\n", "0\r\n1\r\n2\r\n"])
def test_code_trace_oracle_accepts_only_line_ending_equivalence(given: str) -> None:
    assert code_oracle(trace(), given) == 100


@pytest.mark.parametrize(
    "key,given",
    [
        ("A", "a"),
        ("a b", "a  b"),
        ("0\n1\n2", "2\n1\n0"),
        ("0\n1\n2", " 0\n1\n2"),
        ("0\n1\n2", "0\n1\n2 "),
        ("0\n1\n2", "0\n1\n2\n\n"),
        ("0\n1", "0\r1"),
    ],
)
def test_code_trace_oracle_preserves_case_spaces_order_and_blank_lines(
    key: str, given: str
) -> None:
    assert code_oracle(trace(key), given) == 0


def test_bug_hunt_oracle_exact_key_is_correct_and_other_valid_line_is_wrong() -> None:
    assert code_oracle(bug(), bug_given()) == 100
    assert code_oracle(bug(), bug_given(line=1)) == 0


@pytest.mark.parametrize(
    "given",
    [
        "Satır 2 hatalı.",
        bug_given(line=True),
        bug_given(line="2"),
        bug_given(line=2.0),
        bug_given(line=0),
        bug_given(line=3),
        bug_given(version=True),
        bug_given(version="1"),
        bug_given(version=2),
        bug_given(extra="alan"),
        bug_given(bug_type=" "),
        bug_given(fix_summary=""),
        bug_given(bug_type="Yanlış aritmetik"),
        bug_given(fix_summary="Fazla biri çıkar."),
        '{"version":1,"version":1}',
        "NaN",
        "[]",
    ],
)
def test_bug_hunt_ambiguous_or_invalid_submission_abstains(given: str) -> None:
    assert code_oracle(bug(), given) is None


@pytest.mark.parametrize("payload,given", [(trace(), "0\n1\n2"), (bug(), bug_given())])
async def test_correct_code_never_calls_model_and_cannot_be_overruled(payload, given) -> None:
    source_id = uuid4()
    completion = FakeCompletion('{"score":0}')
    result = await grade_with_llm(
        completion, payload=payload, given=given, sources=[(source_id, SOURCE)]
    )
    assert result.graded and result.score == 100 and result.is_correct
    assert result.evidence_chunk_id == source_id
    assert result.rubric_breakdown == [] and result.grounded_feedback is None
    assert result.feedback_version == 1 and completion.calls == 0


@pytest.mark.parametrize("payload,given", [(trace(), "3\n2\n1"), (bug(), bug_given(line=1))])
async def test_wrong_code_ignores_model_score_and_rubric_but_requires_quote_hint(
    payload, given
) -> None:
    source_id = uuid4()
    completion = FakeCompletion(verdict(source_id))
    result = await grade_with_llm(
        completion, payload=payload, given=given, sources=[(source_id, SOURCE)]
    )
    assert result.graded and result.score == 0 and result.is_correct is False
    assert result.rubric_breakdown == [] and result.grounded_missing_criterion is None
    assert result.why_wrong_chunk_id == source_id and result.evidence_chunk_id == source_id
    assert result.grounded_feedback.quote == QUOTE and result.grounded_feedback.next_hint == HINT
    assert result.feedback_version == 1 and completion.calls == 1


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "invented",
        "blank",
        "long",
        "hint_missing",
        "hint_blank",
        "hint_long",
        "other_chunk",
        "extra",
    ],
)
async def test_wrong_code_unverified_feedback_has_no_score_or_explanation(case: str) -> None:
    source_id = uuid4()
    value = json.loads(verdict(source_id))
    claim = value["grounded_feedback"]
    if case == "missing":
        value.pop("grounded_feedback")
    elif case == "invented":
        claim["quote"] = "Kaynakta bulunmayan açıklama."
    elif case == "blank":
        claim["quote"] = " "
    elif case == "long":
        claim["quote"] = "a" * 321
    elif case == "hint_missing":
        claim.pop("next_hint")
    elif case == "hint_blank":
        claim["next_hint"] = "\t "
    elif case == "hint_long":
        claim["next_hint"] = "a" * 1001
    elif case == "other_chunk":
        claim["chunk_id"] = str(uuid4())
    else:
        claim["file_name"] = "invented.pdf"
    completion = FakeCompletion(json.dumps(value))
    result = await grade_with_llm(
        completion, payload=trace(), given="4", sources=[(source_id, SOURCE)]
    )
    assert not result.graded and result.score is None and result.grounded_feedback is None
    assert result.rubric_breakdown == [] and result.missing_points == []
    assert completion.calls == 2


@pytest.mark.parametrize(
    "payload,given",
    [(trace(), "0\n1\n2"), (trace(), "9"), (bug(), bug_given()), (bug(), bug_given(line=1))],
)
async def test_no_source_cannot_license_any_code_score_or_provider_call(payload, given) -> None:
    completion = FakeCompletion(verdict(uuid4()))
    result = await grade_with_llm(completion, payload=payload, given=given, sources=[])
    assert not result.graded and result.score is None and completion.calls == 0


async def test_ambiguous_bug_never_requests_semantic_score_from_model() -> None:
    completion = FakeCompletion(verdict(uuid4()))
    result = await grade_with_llm(
        completion,
        payload=bug(),
        given=bug_given(fix_summary="eş anlamlı"),
        sources=[(uuid4(), SOURCE)],
    )
    assert not result.graded and completion.calls == 0


async def test_bad_code_feedback_then_valid_uses_shared_two_attempt_budget() -> None:
    source_id = uuid4()
    valid = json.loads(verdict(source_id))
    invalid = deepcopy(valid)
    invalid["grounded_feedback"]["quote"] = "Uydurma."
    completion = FakeCompletion(json.dumps(invalid), json.dumps(valid))
    result = await grade_with_llm(
        completion, payload=trace(), given="9", sources=[(source_id, SOURCE)]
    )
    assert result.score == 0 and result.graded and completion.calls == 2


def test_short_answer_requires_source_and_wrong_answer_gets_literal_hint() -> None:
    payload = OpenPayload(
        prompt="Döngü hangi değerleri yazar?",
        answer_key="0,1,2",
        format="short_answer",
        accepted_answers=["0,1,2"],
    )
    source_id = uuid4()
    assert not grade_short_answer(payload, "0,1,2", source_chunk_id=source_id).graded
    wrong = grade_short_answer(payload, "3,2,1", source_chunk_id=source_id, source_text=SOURCE)
    assert wrong.score == 0 and wrong.why_wrong_chunk_id == source_id
    assert wrong.grounded_feedback.quote in SOURCE and wrong.grounded_feedback.next_hint.strip()
    correct = grade_short_answer(payload, "0,1,2", source_chunk_id=source_id, source_text=SOURCE)
    assert correct.score == 100 and correct.feedback_version == 1


@pytest.mark.parametrize("score", [0, 49, 50, 80, 99])
async def test_partial_essay_requires_feedback_without_changing_score_threshold(score: int) -> None:
    source_id = uuid4()
    payload = OpenPayload(
        prompt="Döngüyü kaynakla açıklayın.", answer_key="Sıralı çıktı", key_points=["Çıktı sırası"]
    )
    missing = FakeCompletion(json.dumps({"score": score, "dayanak_chunk_id": str(source_id)}))
    rejected = await grade_with_llm(
        missing, payload=payload, given="Cevap", sources=[(source_id, SOURCE)]
    )
    assert not rejected.graded and missing.calls == 2
    valid = json.loads(verdict(source_id))
    valid["score"] = score
    valid.pop("rubrik")
    result = await grade_with_llm(
        FakeCompletion(json.dumps(valid)),
        payload=payload,
        given="Cevap",
        sources=[(source_id, SOURCE)],
    )
    assert result.score == score and result.is_correct is (score >= 50)
    assert result.grounded_feedback.quote == QUOTE


def test_deeply_nested_bug_submission_abstains_instead_of_raising() -> None:
    given = "[" * 2000 + "0" + "]" * 2000
    assert len(given) < 8000
    assert code_oracle(bug(), given) is None


async def test_grounded_fake_fixture_requires_explicit_local_environment_flag(monkeypatch) -> None:
    from app.modules.assessment import question_gen
    from app.modules.assessment.local_grading_fixture import LocalGradingFixture
    from app.modules.generation.fake import FakeLlmClient

    source_id = uuid4()
    payload = OpenPayload(
        prompt="Döngüyü kaynakla açıklayın.", answer_key="Sıralı çıktı", key_points=["Çıktı sırası"]
    )
    client = FakeLlmClient()
    monkeypatch.setattr(question_gen, "build_llm_client", lambda: client)
    monkeypatch.setattr(question_gen, "_completion", None)
    monkeypatch.delenv("LLM_SIMULATE_GROUNDED_FEEDBACK", raising=False)
    ordinary = question_gen.resolve_grading_completion(
        payload=payload, given="Yanlış", sources=[(source_id, SOURCE)]
    )
    assert not isinstance(ordinary, LocalGradingFixture)
    old = await grade_with_llm(
        ordinary, payload=payload, given="Yanlış", sources=[(source_id, SOURCE)]
    )
    assert not old.graded
    monkeypatch.setenv("LLM_SIMULATE_GROUNDED_FEEDBACK", "1")
    fixture = question_gen.resolve_grading_completion(
        payload=payload, given="Yanlış", sources=[(source_id, SOURCE)]
    )
    assert isinstance(fixture, LocalGradingFixture)
    result = await grade_with_llm(
        fixture, payload=payload, given="Yanlış", sources=[(source_id, SOURCE)]
    )
    assert result.score == 0 and result.grounded_feedback.quote in SOURCE
    assert "Yerel demo geri bildirimi" in result.grounded_feedback.next_hint
    assert fixture.calls == 1


@pytest.mark.parametrize(
    "environment,eval_enabled", [("production", False), ("demo", False), ("local", True)]
)
def test_grounded_fixture_rejects_nonlocal_and_evaluation_runtime(
    monkeypatch, environment, eval_enabled
) -> None:
    from app.core import config
    from app.core.config import Environment
    from app.modules.assessment import question_gen
    from app.modules.assessment.local_grading_fixture import GroundedSimulationForbidden

    settings = config.get_settings().model_copy(
        update={"environment": Environment(environment), "eval_runtime_enabled": eval_enabled}
    )
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    monkeypatch.setenv("LLM_SIMULATE_GROUNDED_FEEDBACK", "1")
    with pytest.raises(GroundedSimulationForbidden):
        question_gen.resolve_grading_completion(
            payload=trace(), given="9", sources=[(uuid4(), SOURCE)]
        )


@pytest.mark.parametrize("missing", [True, False])
async def test_grade_entry_requires_shared_readable_material_from_question_course(
    monkeypatch, missing
) -> None:
    from app.models.assessment import Question, QuestionType
    from app.modules.assessment import grading

    source_id, course_id = uuid4(), uuid4()
    question = Question(
        id=uuid4(),
        course_id=course_id,
        source_chunk_id=source_id,
        type=QuestionType.CODE_TRACE,
        payload=trace().model_dump(mode="json"),
    )
    calls = []

    async def readable_material(session, chunk_ids):
        calls.append(chunk_ids)
        if missing:
            return {}
        return {
            source_id: grading.SourceMaterial(
                source_id, "other-course.pdf", "Sayfa 1", SOURCE, course_id=uuid4()
            )
        }

    monkeypatch.setattr(grading, "load_source_material", readable_material)
    completion = FakeCompletion(verdict(source_id))
    result = await grading.grade_answer(object(), question, "9", completion=completion)
    assert not result.graded and result.score is None
    assert completion.calls == 0 and calls == [[source_id]]
