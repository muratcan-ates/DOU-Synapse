"""B3 sözleşmeleri; hazır model yanıtları pedagojik kalite kanıtı değildir."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.exams import _answer_feedback, _feedback_payload
from app.core.errors import ValidationError as DraftValidationError
from app.models.assessment import Answer, Question, QuestionType
from app.modules.assessment.authoring import validate_draft_payload
from app.modules.assessment.grading import GradingOutcome, SourceMaterial, grade_with_llm
from app.modules.assessment.question_gen import _drafts_from_response, _payload_from_draft
from app.modules.generation.fake import _draft_for
from app.schemas.assessment import GroundedCriterionEvidence, parse_payload, public_payload
from tests.factories import FakeCompletion

SOURCE = "Döngü her adımda sayacı yazdırır. Son koşul sağlanmadığında döngü biter."
QUOTE = "Son koşul sağlanmadığında döngü biter."
CRITERION = "Bitiş koşulunu açıklar"
RUBRIC = [
    {"point": "Adımları sırayla açıklar", "weight": 60},
    {"point": CRITERION, "weight": 40},
]


def _payload(kind: QuestionType, *, rubric: bool = True) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "language": "Python",
        "code": "for i in range(3):\n    print(i)",
        "prompt": "Bu döngünün davranışını açıklayın.",
        "answer_key": "0, 1, 2",
    }
    if kind is QuestionType.BUG_HUNT:
        raw["code"] = "while True:\n    print(1)"
        raw["answer_key"] = {
            "line": 1,
            "bug_type": "Sonsuz döngü",
            "fix_summary": "Bitiş koşulu ekleyin.",
        }
    elif kind is QuestionType.OPEN:
        raw = {"prompt": raw["prompt"], "answer_key": "Döngü sonlanır.", "key_points": [CRITERION]}
    if rubric:
        raw["rubric"] = deepcopy(RUBRIC)
    return raw


def _verdict(source_id: UUID, *, claim: bool = True) -> dict[str, Any]:
    value: dict[str, Any] = {
        "score": 99,
        "eksik_noktalar": [CRITERION],
        "dayanak_chunk_id": str(source_id),
        "rubrik": [
            {"olcut": RUBRIC[0]["point"], "puan": 100},
            {"olcut": CRITERION, "puan": 50},
        ],
    }
    if claim:
        value["grounded_missing_criterion"] = {
            "criterion": CRITERION,
            "chunk_id": str(source_id),
            "quote": QUOTE,
        }
    return value


async def _grade(kind: QuestionType, value: dict[str, Any], *, raw: dict[str, Any] | None = None):
    source_id = UUID(value["dayanak_chunk_id"])
    completion = FakeCompletion(json.dumps(value, ensure_ascii=False))
    outcome = await grade_with_llm(
        completion,
        payload=parse_payload(kind, raw or _payload(kind)),
        given="Sayaç artar.",
        sources=[(source_id, SOURCE)],
    )
    return outcome, completion


def _ungraded(outcome: GradingOutcome) -> None:
    assert outcome.graded is False
    assert outcome.score is None
    assert outcome.is_correct is None
    assert outcome.missing_points == []
    assert outcome.rubric_breakdown == []
    assert outcome.grounded_missing_criterion is None
    assert outcome.evidence_chunk_id is None


@pytest.mark.parametrize(
    "kind", [QuestionType.CODE_TRACE, QuestionType.BUG_HUNT, QuestionType.OPEN]
)
async def test_explicit_criterion_score_and_literal_quote_are_linked(kind: QuestionType) -> None:
    source_id = uuid4()
    outcome, completion = await _grade(kind, _verdict(source_id))
    assert completion.calls == 1
    assert outcome.graded is True
    assert outcome.score == 80  # 60*100% + 40*50%; modelin 99 puanı kullanılmaz.
    assert [row.earned for row in outcome.rubric_breakdown] == [60, 20]
    assert outcome.evidence_chunk_id == source_id
    assert outcome.why_wrong_chunk_id is None  # Çoktan seçmeli/kısa cevap anlamı ayrı tutulur.
    assert outcome.grounded_missing_criterion == GroundedCriterionEvidence(
        criterion=CRITERION, chunk_id=source_id, quote=QUOTE
    )


@pytest.mark.parametrize("kind", [QuestionType.CODE_TRACE, QuestionType.BUG_HUNT])
@pytest.mark.parametrize("case", ["missing", "partial", "duplicate", "foreign", "renamed", "case"])
async def test_code_criteria_must_be_complete_unique_and_exact(
    kind: QuestionType, case: str
) -> None:
    value = _verdict(uuid4(), claim=False)
    if case == "missing":
        value.pop("rubrik")
    elif case == "partial":
        value["rubrik"].pop()
    elif case == "duplicate":
        value["rubrik"].append(value["rubrik"][0])
    elif case == "foreign":
        value["rubrik"].append({"olcut": "İcat edilen ölçüt", "puan": 100})
    elif case == "renamed":
        value["rubrik"][1]["olcut"] = "İcat edilen ölçüt"
    else:
        value["rubrik"][1]["olcut"] = CRITERION.upper()
    outcome, completion = await _grade(kind, value)
    assert completion.calls == 2
    _ungraded(outcome)


@pytest.mark.parametrize("kind", [QuestionType.CODE_TRACE, QuestionType.BUG_HUNT])
async def test_legacy_code_without_rubric_keeps_existing_score(kind: QuestionType) -> None:
    value = _verdict(uuid4(), claim=False)
    value.pop("rubrik")
    outcome, completion = await _grade(kind, value, raw=_payload(kind, rubric=False))
    assert completion.calls == 1
    assert outcome.graded is True
    assert outcome.score == 99
    assert outcome.rubric_breakdown == []
    assert outcome.grounded_missing_criterion is None


@pytest.mark.parametrize("kind", [QuestionType.CODE_TRACE, QuestionType.BUG_HUNT])
async def test_valid_code_rubric_can_grade_without_optional_explanation(kind: QuestionType) -> None:
    outcome, completion = await _grade(kind, _verdict(uuid4(), claim=False))
    assert completion.calls == 1
    assert outcome.score == 80
    assert outcome.grounded_missing_criterion is None


@pytest.mark.parametrize("case", ["missing", "partial"])
async def test_open_rubric_fallback_and_partial_scoring_are_unchanged(case: str) -> None:
    value = _verdict(uuid4(), claim=False)
    if case == "missing":
        value.pop("rubrik")
    else:
        value["rubrik"].pop()
    outcome, completion = await _grade(QuestionType.OPEN, value)
    assert completion.calls == 1
    assert outcome.score == (99 if case == "missing" else 60)
    assert outcome.grounded_missing_criterion is None


@pytest.mark.parametrize(
    "kind", [QuestionType.CODE_TRACE, QuestionType.BUG_HUNT, QuestionType.OPEN]
)
@pytest.mark.parametrize(
    "case",
    [
        "invented_quote",
        "whitespace",
        "empty",
        "long",
        "other_chunk",
        "undefined",
        "full_score",
        "extra_metadata",
    ],
)
async def test_valid_source_id_cannot_license_unverified_claim(
    kind: QuestionType, case: str
) -> None:
    value = _verdict(uuid4())
    claim = value["grounded_missing_criterion"]
    if case == "invented_quote":
        claim["quote"] = "Bu cümle kaynakta yer almıyor."
    elif case == "whitespace":
        claim["quote"] = " "
    elif case == "empty":
        claim["quote"] = ""
    elif case == "long":
        claim["quote"] = "a" * 321
    elif case == "other_chunk":
        claim["chunk_id"] = str(uuid4())
    elif case == "undefined":
        claim["criterion"] = "Başka ölçüt"
    elif case == "full_score":
        value["rubrik"][1]["puan"] = 100
    else:
        claim["file_name"] = "model-invented.pdf"
    outcome, completion = await _grade(kind, value)
    assert completion.calls == 2
    _ungraded(outcome)


@pytest.mark.parametrize("case", ["omitted", "alias_duplicate", "renamed", "whitespace_criterion"])
async def test_open_claim_needs_one_explicit_exact_scored_criterion(case: str) -> None:
    value = _verdict(uuid4())
    raw = _payload(QuestionType.OPEN)
    if case == "omitted":
        value["rubrik"].pop()
    elif case == "alias_duplicate":
        value["rubrik"].append({"olcut": f" {CRITERION} ", "puan": 20})
    elif case == "renamed":
        value["rubrik"][1]["olcut"] = f" {CRITERION} "
    else:
        raw["rubric"][1]["point"] = " "
        value["rubrik"][1]["olcut"] = " "
        value["grounded_missing_criterion"]["criterion"] = " "
    outcome, completion = await _grade(QuestionType.OPEN, value, raw=raw)
    assert completion.calls == 2
    _ungraded(outcome)


async def test_valid_but_different_allowlisted_chunk_does_not_match_grading_evidence() -> None:
    source_id, other_id = uuid4(), uuid4()
    value = _verdict(source_id)
    value["grounded_missing_criterion"]["chunk_id"] = str(other_id)
    completion = FakeCompletion(json.dumps(value))
    result = await grade_with_llm(
        completion,
        payload=parse_payload(QuestionType.CODE_TRACE, _payload(QuestionType.CODE_TRACE)),
        given="Yanıt",
        sources=[(source_id, SOURCE), (other_id, SOURCE)],
    )
    assert completion.calls == 2
    _ungraded(result)


async def test_bad_quote_then_valid_recovers_with_shared_two_attempt_budget() -> None:
    source_id = uuid4()
    valid = _verdict(source_id)
    invalid = deepcopy(valid)
    invalid["grounded_missing_criterion"]["quote"] = "Kaynakta yok."
    completion = FakeCompletion(json.dumps(invalid), json.dumps(valid))
    result = await grade_with_llm(
        completion,
        payload=parse_payload(QuestionType.CODE_TRACE, _payload(QuestionType.CODE_TRACE)),
        given="Yanıt",
        sources=[(source_id, SOURCE)],
    )
    assert completion.calls == 2
    assert result.score == 80
    assert result.grounded_missing_criterion is not None


async def test_no_readable_source_means_no_provider_call() -> None:
    completion = FakeCompletion(json.dumps(_verdict(uuid4())))
    result = await grade_with_llm(
        completion,
        payload=parse_payload(QuestionType.CODE_TRACE, _payload(QuestionType.CODE_TRACE)),
        given="Yanıt",
        sources=[(uuid4(), " \n ")],
    )
    assert completion.calls == 0
    _ungraded(result)


@pytest.mark.parametrize("kind", [QuestionType.CODE_TRACE, QuestionType.BUG_HUNT])
@pytest.mark.parametrize("case", ["missing", "empty", "bad_sum", "duplicate", "blank"])
def test_new_generated_code_requires_reviewable_rubric(kind: QuestionType, case: str) -> None:
    raw = _payload(kind)
    raw["source_chunk_id"] = str(uuid4())
    if case == "missing":
        raw.pop("rubric")
    elif case == "empty":
        raw["rubric"] = []
    elif case == "bad_sum":
        raw["rubric"][0]["weight"] = 30
    elif case == "duplicate":
        raw["rubric"][1]["point"] = f" {raw['rubric'][0]['point']} "
    else:
        raw["rubric"][1]["point"] = " \t "
    result = _drafts_from_response(json.dumps({"questions": [raw]}), kind)
    assert result.drafts == []
    assert result.returned == 1
    assert len(result.item_reasons) == 1


@pytest.mark.parametrize("kind", [QuestionType.CODE_TRACE, QuestionType.BUG_HUNT])
def test_fake_generated_code_obeys_schema_without_semantic_quality_claim(
    kind: QuestionType,
) -> None:
    source_id = uuid4()
    raw = _draft_for(kind.value, str(source_id), SOURCE, "")
    result = _drafts_from_response(json.dumps({"questions": [raw]}), kind)
    assert len(result.drafts) == 1
    assert result.item_reasons == []
    payload = _payload_from_draft(
        result.drafts[0], question_type=kind, chunks=[], answer_format=None
    )
    assert payload["rubric"] == raw["rubric"]
    assert "rubric" not in public_payload(kind, payload)


@pytest.mark.parametrize("kind", [QuestionType.CODE_TRACE, QuestionType.BUG_HUNT])
@pytest.mark.parametrize("case", ["valid", "empty", "omitted", "bad_sum", "duplicate", "blank"])
async def test_instructor_code_rubric_write_validation(kind: QuestionType, case: str) -> None:
    raw = _payload(kind, rubric=case != "omitted")
    if case == "empty":
        raw["rubric"] = []
    elif case == "bad_sum":
        raw["rubric"][0]["weight"] = 30
    elif case == "duplicate":
        raw["rubric"][1]["point"] = raw["rubric"][0]["point"]
    elif case == "blank":
        raw["rubric"][1]["point"] = " "
    # Kod taslağı doğrulaması DB sorgulamaz; yanlış bir sorgu bu nesnede hata verir.
    operation = validate_draft_payload(
        cast(AsyncSession, object()), question_type=kind, raw=raw, original=raw, course_id=uuid4()
    )
    if case == "valid":
        result = await operation
        assert result["rubric"] == raw.get("rubric", [])
    else:
        with pytest.raises(DraftValidationError):
            await operation


@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "hidden",
        "unreadable",
        "altered_quote",
        "altered_weight",
        "wrong_source",
        "legacy",
        "malformed",
        "unknown_criterion",
    ],
)
async def test_saved_feedback_revalidates_quote_and_never_uses_model_source_metadata(
    case: str,
) -> None:
    source_id = uuid4()
    outcome, _ = await _grade(QuestionType.CODE_TRACE, _verdict(source_id))
    feedback = _feedback_payload(outcome)
    question = Question(
        id=uuid4(),
        source_chunk_id=source_id,
        type=QuestionType.CODE_TRACE,
        payload=_payload(QuestionType.CODE_TRACE),
    )
    answer = Answer(question_id=question.id, feedback=feedback, score=80, is_correct=True)
    sources = {source_id: SourceMaterial(source_id, "instructor-source.pdf", "Sayfa 7", SOURCE)}
    if case == "unreadable":
        sources.clear()
    elif case == "altered_quote":
        sources[source_id] = SourceMaterial(
            source_id, "instructor-source.pdf", "Sayfa 7", "Yeni metin"
        )
    elif case == "altered_weight":
        question.payload["rubric"][1]["weight"] = 50
    elif case == "wrong_source":
        question.source_chunk_id = uuid4()
    elif case == "legacy":
        feedback.pop("kaynakli_eksik_olcut")
    elif case == "malformed":
        feedback["kaynakli_eksik_olcut"] = {"chunk_id": "not-a-uuid"}
    elif case == "unknown_criterion":
        question.payload["rubric"][1]["point"] = "Başka ölçüt"
    result = _answer_feedback(answer, question=question, sources=sources, reveal=case != "hidden")
    if case == "valid":
        assert result.grounded_missing_criterion is not None
        assert result.grounded_missing_criterion.criterion == CRITERION
        source = result.grounded_missing_criterion.source
        assert (source.file_name, source.location, source.snippet) == (
            "instructor-source.pdf",
            "Sayfa 7",
            QUOTE,
        )
        assert result.solution is not None and result.solution["rubric"] == RUBRIC
    else:
        assert result.grounded_missing_criterion is None
    assert result.why_wrong is None
    if case in {"hidden", "unreadable", "wrong_source"}:
        assert result.score is None
        assert result.solution is None
        assert result.rubric_breakdown == []


async def test_arbitrary_code_remains_text_and_is_never_executed(tmp_path) -> None:
    marker = tmp_path / "must-not-exist"
    raw = _payload(QuestionType.CODE_TRACE)
    raw["code"] = f"from pathlib import Path; Path({str(marker)!r}).write_text('executed')"
    result, completion = await _grade(QuestionType.CODE_TRACE, _verdict(uuid4()), raw=raw)
    assert completion.calls == 1
    assert result.score == 80
    assert not marker.exists()


def test_quote_schema_rejects_overlong_even_if_source_could_contain_it() -> None:
    with pytest.raises(ValidationError):
        GroundedCriterionEvidence(criterion=CRITERION, chunk_id=uuid4(), quote="a" * 321)
