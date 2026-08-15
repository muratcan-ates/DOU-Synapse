from __future__ import annotations

from pathlib import Path

import pytest

from scripts import role_agent_application_mutation_check as target


class BaselineExplosion(RuntimeError):
    pass


@pytest.mark.parametrize("value", ["SELF", "a" * 40])
def test_candidate_identity_accepts_review_bound_values(value: str) -> None:
    assert target._candidate_identity(value) == value


@pytest.mark.parametrize("value", ["main", "A" * 40, "a" * 39])
def test_candidate_identity_rejects_mutable_or_malformed_values(value: str) -> None:
    with pytest.raises(ValueError, match="candidate identity"):
        target._candidate_identity(value)


def test_baseline_exception_is_preserved_and_cleanup_still_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cleanup_calls: list[str] = []

    monkeypatch.setattr(target, "_copy_candidate", lambda _source, _destination: None)

    def explode(**_kwargs: object) -> target.PytestResult:
        raise BaselineExplosion("original baseline failure")

    monkeypatch.setattr(target, "_pytest", explode)
    monkeypatch.setattr(
        target,
        "_drop_database",
        lambda database_name: cleanup_calls.append(database_name) or 0,
    )

    with pytest.raises(BaselineExplosion, match="original baseline failure"):
        target._run_mutation_matrix(
            source=tmp_path,
            pytest_executable=tmp_path / "pytest",
            database_name="dou_appmut_exception_test",
            baseline_tests=("tests/example.py::test_guard",),
            timeout_seconds=1,
        )

    assert cleanup_calls == ["dou_appmut_exception_test"]


def test_cleanup_exception_is_a_note_not_a_replacement_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(target, "_copy_candidate", lambda _source, _destination: None)

    def explode(**_kwargs: object) -> target.PytestResult:
        raise BaselineExplosion("primary failure")

    def cleanup_explode(_database_name: str) -> int:
        raise RuntimeError("cleanup failure")

    monkeypatch.setattr(target, "_pytest", explode)
    monkeypatch.setattr(target, "_drop_database", cleanup_explode)

    with pytest.raises(BaselineExplosion, match="primary failure") as captured:
        target._run_mutation_matrix(
            source=tmp_path,
            pytest_executable=tmp_path / "pytest",
            database_name="dou_appmut_cleanup_test",
            baseline_tests=("tests/example.py::test_guard",),
            timeout_seconds=1,
        )

    assert any("cleanup failure" in note for note in captured.value.__notes__)
