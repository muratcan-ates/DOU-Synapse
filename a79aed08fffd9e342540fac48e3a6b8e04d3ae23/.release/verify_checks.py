"""Verify release admission against exact GitHub workflow-run identities.

Check-run names are not identities: another workflow or manual run can publish
the same display name.  Admission therefore binds every required job to one
trusted workflow path, a ``push`` event, the exact source SHA and one completed
successful workflow run.  Paginated run and job counts are also fail-closed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REQUIRED_WORKFLOWS: dict[str, tuple[str, ...]] = {
    ".github/workflows/ci.yml": (
        "API — lint, tip, test",
        "API imajı — build + ağsız embedding kanıtı",
        "Web — lint, tip",
        "Belgeler — canlı sayı kapısı",
        "Uçtan uca — gerçek API + tarayıcı",
    ),
    ".github/workflows/ai-quality.yml": (
        "Govern reviewed AI diff",
        "Verify gold-set integrity",
    ),
    ".github/workflows/security.yml": (
        "Workflow dependency policy",
        "CodeQL (javascript-typescript)",
        "CodeQL (python)",
    ),
}
REQUIRED_CHECKS = tuple(
    job_name
    for required_jobs in REQUIRED_WORKFLOWS.values()
    for job_name in required_jobs
)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class CheckVerificationError(ValueError):
    """Raised when trusted workflow evidence is incomplete or ambiguous."""


def _integer(value: Any, label: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise CheckVerificationError(f"{label} must be an integer >= {minimum}")
    return value


def _complete_page(
    entry: dict[str, Any],
    *,
    count_key: str,
    items_key: str,
    label: str,
) -> list[dict[str, Any]]:
    count = entry.get(count_key)
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise CheckVerificationError(f"{label} is missing integer {count_key}")
    items = entry.get(items_key)
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise CheckVerificationError(f"{label} is missing object array {items_key}")
    if count != len(items):
        raise CheckVerificationError(
            f"{label} pagination is incomplete: {count_key}={count}, "
            f"received={len(items)}"
        )
    return items


def verify_workflow_runs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return ordered evidence for jobs from exact trusted workflow runs."""

    source_sha = payload.get("source_sha")
    if not isinstance(source_sha, str) or SHA_RE.fullmatch(source_sha) is None:
        raise CheckVerificationError("source_sha must be a lowercase 40-character SHA")
    entries = payload.get("workflows")
    if not isinstance(entries, list) or not all(
        isinstance(entry, dict) for entry in entries
    ):
        raise CheckVerificationError("payload is missing workflows object array")

    indexed: dict[str, dict[str, Any]] = {}
    for entry in entries:
        path = entry.get("workflow_path")
        if not isinstance(path, str) or path not in REQUIRED_WORKFLOWS:
            raise CheckVerificationError(f"untrusted workflow path: {path!r}")
        if path in indexed:
            raise CheckVerificationError(f"duplicate workflow payload: {path}")
        indexed[path] = entry
    missing_paths = [path for path in REQUIRED_WORKFLOWS if path not in indexed]
    if missing_paths:
        raise CheckVerificationError(
            f"missing trusted workflow payload(s): {missing_paths}"
        )

    evidence: list[dict[str, Any]] = []
    failures: list[str] = []
    for workflow_path, required_jobs in REQUIRED_WORKFLOWS.items():
        entry = indexed[workflow_path]
        runs = _complete_page(
            entry,
            count_key="runs_total_count",
            items_key="workflow_runs",
            label=workflow_path,
        )
        matching_runs = [
            run
            for run in runs
            if run.get("path") == workflow_path
            and run.get("event") == "push"
            and run.get("head_sha") == source_sha
        ]
        if len(matching_runs) != 1:
            failures.append(
                f"{workflow_path}: expected exactly one push run for {source_sha}, "
                f"found {len(matching_runs)}"
            )
            continue
        run = matching_runs[0]
        try:
            run_id = _integer(run.get("id"), f"{workflow_path} run id")
            run_attempt = _integer(
                run.get("run_attempt"), f"{workflow_path} run attempt"
            )
        except CheckVerificationError as exc:
            failures.append(str(exc))
            continue
        if run.get("head_branch") != "main":
            failures.append(f"{workflow_path}: head_branch must be 'main'")
            continue
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            failures.append(
                f"{workflow_path}: status={run.get('status')!r}, "
                f"conclusion={run.get('conclusion')!r}"
            )
            continue
        run_url = run.get("html_url")
        if not isinstance(run_url, str) or not run_url:
            failures.append(f"{workflow_path}: successful run has no immutable URL")
            continue

        jobs = _complete_page(
            entry,
            count_key="jobs_total_count",
            items_key="jobs",
            label=f"{workflow_path} run {run_id}",
        )
        bound_jobs = [job for job in jobs if job.get("run_id") == run_id]
        for job_name in required_jobs:
            matching_jobs = [job for job in bound_jobs if job.get("name") == job_name]
            if len(matching_jobs) != 1:
                failures.append(
                    f"{workflow_path} / {job_name}: expected exactly one job, "
                    f"found {len(matching_jobs)}"
                )
                continue
            job = matching_jobs[0]
            try:
                job_id = _integer(job.get("id"), f"{job_name} job id")
            except CheckVerificationError as exc:
                failures.append(str(exc))
                continue
            job_head_sha = job.get("head_sha")
            if job_head_sha is not None and job_head_sha != source_sha:
                failures.append(f"{job_name}: job head_sha does not match source_sha")
                continue
            if job.get("status") != "completed" or job.get("conclusion") != "success":
                failures.append(
                    f"{job_name}: status={job.get('status')!r}, "
                    f"conclusion={job.get('conclusion')!r}"
                )
                continue
            job_url = job.get("html_url")
            if not isinstance(job_url, str) or not job_url:
                failures.append(f"{job_name}: successful job has no immutable URL")
                continue
            evidence.append(
                {
                    "name": job_name,
                    "status": "passed",
                    "workflow_path": workflow_path,
                    "workflow_run_id": run_id,
                    "workflow_run_attempt": run_attempt,
                    "job_id": job_id,
                    "event": "push",
                    "head_sha": source_sha,
                    "run_url": run_url,
                    "job_url": job_url,
                }
            )

    if failures:
        raise CheckVerificationError("; ".join(failures))
    if [item["name"] for item in evidence] != list(REQUIRED_CHECKS):
        raise CheckVerificationError(
            "verified jobs are not the exact required ordered set"
        )
    return evidence


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise CheckVerificationError("GitHub response must be an object")
        evidence = verify_workflow_runs(payload)
    except (OSError, json.JSONDecodeError, CheckVerificationError) as exc:
        print(f"required-workflow verification failed: {exc}", file=sys.stderr)
        return 1

    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"verified {len(evidence)} jobs from {len(REQUIRED_WORKFLOWS)} workflows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
