"""009 assessment-integrity: frozen exam-item weights and score aggregation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import ExamSession
from app.modules.assessment.exam_paper import paper_question_weights
from app.modules.assessment.grading import GradingOutcome
from app.modules.assessment.scoring import score_of


def test_blueprint_10_90_weights_produce_10_and_90() -> None:
    light = uuid4()
    heavy = uuid4()
    weights = {light: 10, heavy: 90}

    assert score_of(
        {
            light: GradingOutcome(graded=True, score=100),
            heavy: GradingOutcome(graded=True, score=0),
        },
        weights,
    ) == 10.0
    assert score_of(
        {
            light: GradingOutcome(graded=True, score=0),
            heavy: GradingOutcome(graded=True, score=100),
        },
        weights,
    ) == 90.0


def test_blueprint_answer_order_does_not_change_weight_mapping() -> None:
    light = uuid4()
    heavy = uuid4()
    weights = {light: 10, heavy: 90}
    forward = {
        light: GradingOutcome(graded=True, score=100),
        heavy: GradingOutcome(graded=True, score=0),
    }
    reversed_answers = dict(reversed(tuple(forward.items())))

    assert score_of(forward, weights) == 10.0
    assert score_of(reversed_answers, weights) == 10.0


def test_ungraded_and_unanswered_questions_are_excluded() -> None:
    graded = uuid4()
    ungraded = uuid4()
    unanswered = uuid4()

    assert score_of(
        {
            graded: GradingOutcome(graded=True, score=100),
            ungraded: GradingOutcome(graded=False, score=0),
        },
        {graded: 10, ungraded: 90, unanswered: 100},
    ) == 100.0


def test_missing_weight_for_included_answer_fails_closed() -> None:
    question_id = uuid4()

    with pytest.raises(ValueError, match="ağırlık eksik"):
        score_of({question_id: GradingOutcome(graded=True, score=75)}, {})


@pytest.mark.parametrize("invalid_weight", [0, -1, True, 1.5])
def test_invalid_weight_for_included_answer_fails_closed(invalid_weight: object) -> None:
    question_id = uuid4()

    with pytest.raises(ValueError, match="pozitif tam sayı"):
        score_of(
            {question_id: GradingOutcome(graded=True, score=75)},
            {question_id: invalid_weight},  # type: ignore[dict-item]
        )


def test_legacy_flow_preserves_equal_one_decimal_mean() -> None:
    first = uuid4()
    second = uuid4()
    third = uuid4()

    assert score_of(
        {
            first: GradingOutcome(graded=True, score=100),
            second: GradingOutcome(graded=True, score=0),
            third: GradingOutcome(graded=True, score=0),
        }
    ) == 33.3


def test_no_graded_non_null_answer_has_no_score() -> None:
    assert (
        score_of(
            {
                uuid4(): GradingOutcome(graded=False, score=10),
                uuid4(): GradingOutcome(graded=True, score=None),
            },
            {},
        )
        is None
    )


@pytest.mark.asyncio
async def test_legacy_paper_has_no_weight_map_and_runs_no_query() -> None:
    db = AsyncMock(spec=AsyncSession)
    exam = ExamSession(exam_version_id=None)

    assert await paper_question_weights(db, exam) is None
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_blueprint_paper_maps_frozen_points_by_question_id() -> None:
    db = AsyncMock(spec=AsyncSession)
    rows = MagicMock()
    light = uuid4()
    heavy = uuid4()
    rows.all.return_value = [(heavy, 90), (light, 10)]
    db.execute.return_value = rows

    weights = await paper_question_weights(db, ExamSession(exam_version_id=uuid4()))

    assert weights == {light: 10, heavy: 90}
    db.execute.assert_awaited_once()
