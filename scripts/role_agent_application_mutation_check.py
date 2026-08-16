"""Prove the 005 application guard matrix by red/restore/green mutation.

The runner copies only the API source, API tests, pytest configuration, and SQL
migrations into a temporary directory. It never mutates the candidate tree and
reuses the candidate's existing virtual environment instead of copying or
installing dependencies.

Every mutation must make its named focused test fail (red). The runner then
restores the exact source bytes and requires the same test to pass (green).
Aggregate output contains synthetic labels and counts only; prompt text, answer
text, email addresses, secrets, and provider payloads are not retained.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final


@dataclass(frozen=True, slots=True)
class Mutation:
    mutation_id: str
    boundary: str
    relative_path: str
    original: str
    replacement: str
    expected_occurrences: int
    tests: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PytestResult:
    returncode: int
    passed: int
    failed: int
    summary: str


APPLICATION_GUARD_TEST: Final = "tests/test_role_aware_agent_application_guards.py"

MUTATIONS: Final[tuple[Mutation, ...]] = (
    Mutation(
        "persona_payload_forbid",
        "ChatRequest rejects client-selected audience/profile fields",
        "apps/api/app/schemas/chat.py",
        '    model_config = ConfigDict(extra="forbid")\n',
        '    model_config = ConfigDict(extra="ignore")\n',
        1,
        (
            (
                "tests/test_role_aware_agent.py::TestServerDerivedIdentity::"
                "test_client_cannot_select_persona"
            ),
        ),
    ),
    Mutation(
        "membership_to_audience",
        "course membership remains the sole audience projection",
        "apps/api/app/api/chat.py",
        (
            "def _audience(context: CourseContext) -> AssistantAudience:\n"
            "    return AssistantAudience.INSTRUCTOR if context.is_instructor "
            "else AssistantAudience.STUDENT\n"
        ),
        (
            "def _audience(context: CourseContext) -> AssistantAudience:\n"
            "    return AssistantAudience.STUDENT\n"
        ),
        1,
        (
            (
                "tests/test_role_aware_agent.py::TestServerDerivedIdentity::"
                "test_availability_exposes_only_server_resolved_persona"
            ),
        ),
    ),
    Mutation(
        "session_audience_mismatch",
        "a role-changed user cannot continue a session from the old audience",
        "apps/api/app/api/chat.py",
        "    if existing.audience is not _audience(context):\n",
        "    if False and existing.audience is not _audience(context):\n",
        1,
        (
            (
                "tests/test_role_aware_agent.py::TestServerDerivedIdentity::"
                "test_role_change_makes_existing_session_conflict"
            ),
        ),
    ),
    Mutation(
        "cache_audience_and_revisions",
        "audience plus policy/prompt/corpus revisions partition the cache key",
        "apps/api/app/api/chat.py",
        (
            "            audience.value,\n"
            "            mode.value,\n"
            "            policy_revision,\n"
            "            prompt_revision,\n"
            "            corpus_revision,\n"
        ),
        "            mode.value,\n",
        1,
        (
            (
                f"{APPLICATION_GUARD_TEST}::"
                "test_cache_identity_changes_with_audience_and_every_revision"
            ),
        ),
    ),
    Mutation(
        "reservation_before_provider",
        "the durable quota reservation callback runs before provider generation",
        "apps/api/app/api/chat.py",
        (
            "    if before_generation is not None:\n"
            "        quota_request = generation_prompts.build_request(\n"
        ),
        (
            "    if False and before_generation is not None:\n"
            "        quota_request = generation_prompts.build_request(\n"
        ),
        1,
        (
            f"{APPLICATION_GUARD_TEST}::test_provider_budget_is_reserved_before_generation",
        ),
    ),
    Mutation(
        "process_concurrency_limit",
        "the process-local gate rejects a second same-user provider request",
        "apps/api/app/api/chat.py",
        "                limit=policy.max_concurrent_requests,\n",
        "                limit=policy.max_concurrent_requests + 1,\n",
        1,
        (
            (
                f"{APPLICATION_GUARD_TEST}::"
                "test_process_concurrency_gate_rejects_second_same_user_request"
            ),
        ),
    ),
    Mutation(
        "provider_output_cap",
        "course policy cannot raise the deployment/provider output ceiling",
        "apps/api/app/modules/generation/service.py",
        (
            "            max_tokens=min(\n"
            "                max_output_tokens or self._settings.llm_chat_max_tokens,\n"
            "                self._settings.llm_chat_max_tokens,\n"
            "            ),\n"
        ),
        "            max_tokens=max_output_tokens or self._settings.llm_chat_max_tokens,\n",
        1,
        (f"{APPLICATION_GUARD_TEST}::test_global_output_ceiling_is_sent_to_provider",),
    ),
    Mutation(
        "exam_dependency_paths",
        "chat creation and history paths all use the exam-unlocked dependency",
        "apps/api/app/api/chat.py",
        "    context: UnlockedCourseMemberDep,\n",
        "    context: CourseMemberDep,\n",
        3,
        (
            (
                f"{APPLICATION_GUARD_TEST}::"
                "test_exam_dependency_blocks_chat_and_history_before_provider"
            ),
            "tests/test_exam_lock.py::TestKilitYururken::test_qa_modu_reddedilir",
            "tests/test_exam_lock.py::TestKilitYururken::test_gecmis_okuma_yuzeyleri_de_kapali",
        ),
    ),
    Mutation(
        "guard_event_privacy_schema",
        "guard-event storage has no free-text or request-identity column",
        "supabase/migrations/0015_role_aware_course_agent.sql",
        (
            "CREATE TABLE ai_guard_events (\n"
            "    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),\n"
            "    course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,\n"
            "    user_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,\n"
            "    audience assistant_audience NOT NULL,\n"
        ),
        (
            "CREATE TABLE ai_guard_events (\n"
            "    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),\n"
            "    course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,\n"
            "    user_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,\n"
            "    prompt_text text,\n"
            "    audience assistant_audience NOT NULL,\n"
        ),
        1,
        (
            (
                f"{APPLICATION_GUARD_TEST}::"
                "test_guard_event_schema_has_no_free_text_or_request_identity"
            ),
        ),
    ),
    Mutation(
        "operational_kill_switch",
        "the global switch closes both availability and direct chat POST",
        "apps/api/app/api/chat.py",
        "    if not settings.course_agent_enabled:\n",
        "    if False and not settings.course_agent_enabled:\n",
        2,
        (
            (
                "tests/test_role_aware_agent.py::TestOperationalKillSwitch::"
                "test_disabled_switch_creates_no_agent_artifact"
            ),
        ),
    ),
    Mutation(
        "chat_finalization_user_lock",
        "chat finalization and exam start serialize on the same user lock",
        "apps/api/app/api/chat.py",
        (
            "        await exam_state.acquire_user_assessment_lock("
            "session, user_id=context.user_id)\n"
        ),
        "        pass\n",
        1,
        (
            f"{APPLICATION_GUARD_TEST}::test_chat_finalization_and_exam_start_share_user_lock",
        ),
    ),
    Mutation(
        "export_user_lock",
        "data export and exam start serialize on the same user lock",
        "apps/api/app/api/privacy.py",
        "    await exam_state.acquire_user_assessment_lock(session, user_id=user_id)\n",
        "    pass\n",
        1,
        (f"{APPLICATION_GUARD_TEST}::test_export_and_exam_start_share_user_lock",),
    ),
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence",
        type=Path,
        help="Optional JSON evidence path. Prefer a temporary path during review.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=180,
        help="Per-pytest-process timeout (default: 180).",
    )
    parser.add_argument(
        "--candidate-sha",
        default="SELF",
        help=(
            "Immutable candidate identity recorded in evidence. Use SELF for an "
            "append-only report committed with the reviewed dossier."
        ),
    )
    return parser.parse_args()


def _repo_root() -> Path:
    root = Path(__file__).resolve().parents[1]
    if not (root / "apps/api/app").is_dir() or not (root / ".git").exists():
        raise RuntimeError(f"not a DOU-Synapse repository: {root}")
    return root


def _copy_candidate(source: Path, destination: Path) -> None:
    ignore = shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache"
    )
    (destination / "apps/api").mkdir(parents=True)
    shutil.copytree(
        source / "apps/api/app", destination / "apps/api/app", ignore=ignore
    )
    shutil.copytree(
        source / "apps/api/tests", destination / "apps/api/tests", ignore=ignore
    )
    shutil.copy2(
        source / "apps/api/pyproject.toml", destination / "apps/api/pyproject.toml"
    )
    (destination / "supabase").mkdir(parents=True)
    shutil.copytree(
        source / "supabase/migrations",
        destination / "supabase/migrations",
        ignore=ignore,
    )


def _replace_exact(path: Path, mutation: Mutation) -> str:
    original_text = path.read_text(encoding="utf-8")
    occurrences = original_text.count(mutation.original)
    if occurrences != mutation.expected_occurrences:
        raise RuntimeError(
            f"{mutation.mutation_id}: expected {mutation.expected_occurrences} replacement "
            f"site(s), found {occurrences} in {mutation.relative_path}"
        )
    path.write_text(
        original_text.replace(mutation.original, mutation.replacement),
        encoding="utf-8",
    )
    return original_text


def _summarize_pytest(output: str, returncode: int) -> PytestResult:
    passed_match = re.search(r"(?P<count>\d+) passed\b", output)
    failed_match = re.search(r"(?P<count>\d+) failed\b", output)
    summary_lines = [line.strip() for line in output.splitlines() if " in " in line]
    return PytestResult(
        returncode=returncode,
        passed=int(passed_match.group("count")) if passed_match else 0,
        failed=int(failed_match.group("count")) if failed_match else 0,
        summary=summary_lines[-1] if summary_lines else "no pytest summary",
    )


def _pytest(
    *,
    pytest_executable: Path,
    api_root: Path,
    database_name: str,
    tests: tuple[str, ...],
    timeout_seconds: int,
) -> PytestResult:
    environment = os.environ.copy()
    environment.update(
        {
            "DATABASE_URL": (
                f"postgresql+psycopg://dou_app:dou_app_local@localhost/{database_name}"
            ),
            "DEV_AUTH_ENABLED": "true",
            "ENVIRONMENT": "local",
            "PYTHONDONTWRITEBYTECODE": "1",
            "TEST_ADMIN_DSN": f"postgresql+psycopg://localhost/{database_name}",
            "TEST_APP_DSN": (
                f"postgresql+psycopg://dou_app:dou_app_local@localhost/{database_name}"
            ),
            "TEST_DB_NAME": database_name,
            "TEST_WORKER_DSN": (
                f"postgresql+psycopg://dou_worker:dou_worker_local@localhost/{database_name}"
            ),
            "WORKER_DATABASE_URL": (
                f"postgresql+psycopg://dou_worker:dou_worker_local@localhost/{database_name}"
            ),
        }
    )
    command = [
        str(pytest_executable),
        "-q",
        "-p",
        "no:cacheprovider",
        *tests,
    ]
    completed = subprocess.run(
        command,
        cwd=api_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    return _summarize_pytest(completed.stdout + completed.stderr, completed.returncode)


def _drop_database(database_name: str) -> int:
    if re.fullmatch(r"dou_appmut_[a-z0-9_]+", database_name) is None:
        raise RuntimeError(
            f"refusing to drop unexpected database name: {database_name}"
        )
    pg_bin = Path(os.environ.get("PG_BIN", "/opt/homebrew/opt/postgresql@16/bin"))
    drop = subprocess.run(
        [
            str(pg_bin / "psql"),
            "-v",
            "ON_ERROR_STOP=1",
            "-q",
            "-d",
            "postgres",
            "-c",
            f'DROP DATABASE IF EXISTS "{database_name}"',
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if drop.returncode != 0:
        return -1
    residue = subprocess.run(
        [
            str(pg_bin / "psql"),
            "-Atq",
            "-d",
            "postgres",
            "-c",
            f"SELECT count(*) FROM pg_database WHERE datname='{database_name}'",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if residue.returncode != 0 or not residue.stdout.strip().isdigit():
        return -1
    return int(residue.stdout.strip())


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate_identity(value: str) -> str:
    if value == "SELF" or re.fullmatch(r"[0-9a-f]{40}", value):
        return value
    raise ValueError("candidate identity must be SELF or a full lowercase Git SHA")


def _evidence_payload(
    *,
    source: Path,
    command: str,
    baseline: PytestResult,
    mutation_results: list[dict[str, object]],
    database_residue: int,
    candidate_sha: str,
) -> dict[str, object]:
    tracked_inputs = {mutation.relative_path for mutation in MUTATIONS} | {
        "apps/api/tests/test_role_aware_agent_application_guards.py",
        "scripts/role_agent_application_mutation_check.py",
    }
    passed = sum(1 for result in mutation_results if result["result"] == "pass")
    return {
        "schema_version": 1,
        "change_id": "005-role-aware-course-agent-application-mutations",
        "candidate_sha": _candidate_identity(candidate_sha),
        "captured_at": datetime.now(UTC).isoformat(),
        "command": command,
        "environment": (
            "temporary source copy; existing Python environment; local PostgreSQL 16; "
            "synthetic fixtures; deterministic fake provider"
        ),
        "evidence_label": "fake-provider",
        "result": (
            "pass"
            if passed == len(MUTATIONS)
            and baseline.returncode == 0
            and database_residue == 0
            else "fail"
        ),
        "privacy": (
            "stable mutation labels and aggregate pytest counts only; no prompt/answer text, "
            "emails, secrets, raw database rows, request identifiers, or provider payloads retained"
        ),
        "source_sha256": {
            relative: _sha256(source / relative) for relative in sorted(tracked_inputs)
        },
        "baseline": asdict(baseline),
        "results": {
            "mutations_attempted": len(MUTATIONS),
            "mutations_caught": passed,
            "mutations_missed": len(MUTATIONS) - passed,
            "restored_green": sum(
                1 for result in mutation_results if result["green"]["returncode"] == 0
            ),
            "temporary_database_residue": database_residue,
            "mutations": mutation_results,
        },
        "limitations": (
            "This proves deterministic application guard mechanics with a fake provider and a "
            "local disposable database. It is not real-model, multi-worker, staging, rollout, "
            "pedagogical-quality, or production evidence. Durable quota races remain covered by "
            "the separate PostgreSQL/RLS mutation package."
        ),
    }


def _write_evidence(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _run_mutation_matrix(
    *,
    source: Path,
    pytest_executable: Path,
    database_name: str,
    baseline_tests: tuple[str, ...],
    timeout_seconds: int,
) -> tuple[PytestResult, list[dict[str, object]], int]:
    """Run the disposable mutation matrix without masking setup/test failures.

    `baseline` has a defined sentinel before any filesystem copy or subprocess
    can fail. More importantly, exceptions are re-raised unchanged after the
    exact disposable database cleanup attempt. Evidence is therefore never
    written from an unassigned local, and a cleanup problem is attached as a
    note instead of replacing the original failure with a secondary exception.
    """

    baseline = PytestResult(
        returncode=2,
        passed=0,
        failed=0,
        summary="baseline did not complete",
    )
    mutation_results: list[dict[str, object]] = []
    database_residue = -1
    active_error: BaseException | None = None

    with tempfile.TemporaryDirectory(prefix="dou-synapse-app-mutations-") as temp_name:
        temporary_root = Path(temp_name)
        try:
            _copy_candidate(source, temporary_root)
            api_root = temporary_root / "apps/api"
            print(f"[baseline] {len(baseline_tests)} focused test nodes")
            baseline = _pytest(
                pytest_executable=pytest_executable,
                api_root=api_root,
                database_name=database_name,
                tests=baseline_tests,
                timeout_seconds=timeout_seconds,
            )
            print(f"[baseline] {baseline.summary}")
            if baseline.returncode != 0:
                print(
                    "baseline is not green; mutations were not attempted",
                    file=sys.stderr,
                )
            else:
                for index, mutation in enumerate(MUTATIONS, start=1):
                    target = temporary_root / mutation.relative_path
                    original_text = _replace_exact(target, mutation)
                    try:
                        red = _pytest(
                            pytest_executable=pytest_executable,
                            api_root=api_root,
                            database_name=database_name,
                            tests=mutation.tests,
                            timeout_seconds=timeout_seconds,
                        )
                    finally:
                        target.write_text(original_text, encoding="utf-8")

                    green = _pytest(
                        pytest_executable=pytest_executable,
                        api_root=api_root,
                        database_name=database_name,
                        tests=mutation.tests,
                        timeout_seconds=timeout_seconds,
                    )
                    caught = red.returncode == 1 and red.failed > 0
                    restored = green.returncode == 0 and green.passed > 0
                    result = "pass" if caught and restored else "fail"
                    mutation_results.append(
                        {
                            "id": mutation.mutation_id,
                            "boundary": mutation.boundary,
                            "target_file": mutation.relative_path,
                            "replacement_sites": mutation.expected_occurrences,
                            "test_nodes": list(mutation.tests),
                            "red": asdict(red),
                            "green": asdict(green),
                            "result": result,
                        }
                    )
                    print(
                        f"[{index:02d}/{len(MUTATIONS)}] {mutation.mutation_id}: "
                        f"red={red.summary}; green={green.summary}; {result.upper()}"
                    )
        except BaseException as error:
            active_error = error
            raise
        finally:
            try:
                database_residue = _drop_database(database_name)
            except Exception as cleanup_error:
                if active_error is None:
                    raise
                active_error.add_note(
                    "disposable database cleanup also failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )

    return baseline, mutation_results, database_residue


def main() -> int:
    args = _parse_args()
    source = _repo_root()
    pytest_executable = source / "apps/api/.venv/bin/pytest"
    if not pytest_executable.is_file():
        raise RuntimeError(
            "apps/api/.venv is missing; install the existing project dev environment"
        )

    database_name = f"dou_appmut_{os.getpid()}"
    baseline_tests = tuple(
        dict.fromkeys(test for mutation in MUTATIONS for test in mutation.tests)
    )
    command_parts = [
        sys.executable,
        str(Path(__file__).resolve().relative_to(source)),
    ]
    if args.evidence is not None:
        command_parts.extend(("--evidence", str(args.evidence)))
    command_parts.extend(("--candidate-sha", args.candidate_sha))
    if args.timeout_seconds != 180:
        command_parts.extend(("--timeout-seconds", str(args.timeout_seconds)))
    command = shlex.join(command_parts)
    if pg_bin := os.environ.get("PG_BIN"):
        command = f"PG_BIN={shlex.quote(pg_bin)} {command}"

    baseline, mutation_results, database_residue = _run_mutation_matrix(
        source=source,
        pytest_executable=pytest_executable,
        database_name=database_name,
        baseline_tests=baseline_tests,
        timeout_seconds=args.timeout_seconds,
    )

    payload = _evidence_payload(
        source=source,
        command=command,
        baseline=baseline,
        mutation_results=mutation_results,
        database_residue=database_residue,
        candidate_sha=args.candidate_sha,
    )
    if args.evidence is not None:
        _write_evidence(args.evidence, payload)
        print(f"evidence: {args.evidence}")
    if baseline.returncode != 0:
        return 2
    return 0 if payload["result"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
