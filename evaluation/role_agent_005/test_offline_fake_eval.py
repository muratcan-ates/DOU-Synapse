from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.role_agent_005 import offline_fake_eval as target


@pytest.mark.parametrize("value", ["SELF", "a" * 40])
def test_record_candidate_identity_accepts_review_bound_values(value: str) -> None:
    assert target._record_candidate_identity(value) == value


@pytest.mark.parametrize("value", ["main", "A" * 40, "a" * 39])
def test_record_candidate_identity_rejects_mutable_or_malformed_values(
    value: str,
) -> None:
    with pytest.raises(ValueError, match="record candidate identity"):
        target._record_candidate_identity(value)


def test_production_behavior_dependencies_match_checked_out_head() -> None:
    candidate_sha = target._git(["rev-parse", "HEAD"])

    binding = target._artifact_binding(
        candidate_sha,
        evaluator_path=Path(target.__file__),
        fixture_path=target.REPO_ROOT / "evaluation/role_agent_005/holdout_v1.json",
    )

    assert binding["production_behavior_exact_candidate"] is True
    assert len(binding["production_behavior_dependencies"]) == len(
        target.PRODUCTION_BEHAVIOR_DEPENDENCIES
    )
    assert all(
        item["matches_candidate_blob"]
        for item in binding["production_behavior_dependencies"]
    )


def test_production_binding_rejects_a_mismatched_candidate_blob(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_sha = target._git(["rev-parse", "HEAD"])
    real_git_blob = target._git_blob

    def mismatched_blob(sha: str, relative_path: str) -> bytes | None:
        if relative_path == target.PRODUCTION_BEHAVIOR_DEPENDENCIES[0]:
            return b"not the checked-out production behavior"
        return real_git_blob(sha, relative_path)

    monkeypatch.setattr(target, "_git_blob", mismatched_blob)

    with pytest.raises(RuntimeError, match="production behavior differs"):
        target._artifact_binding(
            candidate_sha,
            evaluator_path=Path(target.__file__),
            fixture_path=target.REPO_ROOT / "evaluation/role_agent_005/holdout_v1.json",
        )


def test_role_sensitive_cases_are_labeled_as_low_evidence_not_authorization() -> None:
    fixture = target._load_json(
        target.REPO_ROOT / "evaluation/role_agent_005/holdout_v1.json"
    )
    contracts = {str(case["contract"]) for case in fixture["cases"]}
    thresholds = fixture["thresholds"]

    assert "role_sensitive_low_evidence_abstention" in contracts
    assert "cross_role_refusal" not in contracts
    assert "role_sensitive_low_evidence_abstention_rate" in thresholds
    assert "cross_role_refusal_rate" not in thresholds
