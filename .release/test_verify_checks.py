from __future__ import annotations

import copy
import json
import re
import unittest
from pathlib import Path

from verify_checks import (
    REQUIRED_CHECKS,
    REQUIRED_WORKFLOWS,
    CheckVerificationError,
    verify_workflow_runs,
)

SOURCE_SHA = "a" * 40


def passing_payload() -> dict[str, object]:
    entries: list[dict[str, object]] = []
    next_id = 1
    for workflow_path, job_names in REQUIRED_WORKFLOWS.items():
        run_id = next_id
        next_id += 1
        run = {
            "id": run_id,
            "path": workflow_path,
            "event": "push",
            "head_sha": SOURCE_SHA,
            "head_branch": "main",
            "status": "completed",
            "conclusion": "success",
            "run_attempt": 1,
            "html_url": f"https://github.com/example/project/actions/runs/{run_id}",
        }
        jobs: list[dict[str, object]] = []
        for job_name in job_names:
            job_id = next_id
            next_id += 1
            jobs.append(
                {
                    "id": job_id,
                    "run_id": run_id,
                    "name": job_name,
                    "head_sha": SOURCE_SHA,
                    "status": "completed",
                    "conclusion": "success",
                    "html_url": (
                        f"https://github.com/example/project/actions/runs/"
                        f"{run_id}/job/{job_id}"
                    ),
                }
            )
        entries.append(
            {
                "workflow_path": workflow_path,
                "runs_total_count": 1,
                "workflow_runs": [run],
                "jobs_total_count": len(jobs),
                "jobs": jobs,
            }
        )
    return {"source_sha": SOURCE_SHA, "workflows": entries}


def workflow_entry(payload: dict[str, object], path: str) -> dict[str, object]:
    return next(
        entry
        for entry in payload["workflows"]  # type: ignore[union-attr]
        if entry["workflow_path"] == path
    )


class VerifyWorkflowRunsTests(unittest.TestCase):
    def test_all_required_workflow_jobs_pass(self) -> None:
        evidence = verify_workflow_runs(passing_payload())
        self.assertEqual([item["name"] for item in evidence], list(REQUIRED_CHECKS))
        self.assertTrue(all(item["event"] == "push" for item in evidence))
        self.assertTrue(all(item["head_sha"] == SOURCE_SHA for item in evidence))

    def test_wrong_workflow_path_fails_closed(self) -> None:
        payload = passing_payload()
        entry = payload["workflows"][0]  # type: ignore[index]
        entry["workflow_runs"][0]["path"] = ".github/workflows/fake.yml"  # type: ignore[index]
        with self.assertRaisesRegex(CheckVerificationError, "exactly one push run"):
            verify_workflow_runs(payload)

    def test_manual_run_cannot_satisfy_admission(self) -> None:
        payload = passing_payload()
        entry = payload["workflows"][0]  # type: ignore[index]
        entry["workflow_runs"][0]["event"] = "workflow_dispatch"  # type: ignore[index]
        with self.assertRaisesRegex(CheckVerificationError, "exactly one push run"):
            verify_workflow_runs(payload)

    def test_wrong_head_sha_fails_closed(self) -> None:
        payload = passing_payload()
        entry = payload["workflows"][0]  # type: ignore[index]
        entry["workflow_runs"][0]["head_sha"] = "b" * 40  # type: ignore[index]
        with self.assertRaisesRegex(CheckVerificationError, "exactly one push run"):
            verify_workflow_runs(payload)

    def test_duplicate_push_run_fails_closed(self) -> None:
        payload = passing_payload()
        entry = payload["workflows"][0]  # type: ignore[index]
        duplicate = copy.deepcopy(entry["workflow_runs"][0])  # type: ignore[index]
        duplicate["id"] = 99_999
        entry["workflow_runs"].append(duplicate)  # type: ignore[union-attr]
        entry["runs_total_count"] = 2
        with self.assertRaisesRegex(CheckVerificationError, "found 2"):
            verify_workflow_runs(payload)

    def test_newer_same_name_job_cannot_hide_duplicate(self) -> None:
        payload = passing_payload()
        entry = payload["workflows"][0]  # type: ignore[index]
        duplicate = copy.deepcopy(entry["jobs"][0])  # type: ignore[index]
        duplicate["id"] = 99_999
        entry["jobs"].append(duplicate)  # type: ignore[union-attr]
        entry["jobs_total_count"] = len(entry["jobs"])  # type: ignore[arg-type]
        with self.assertRaisesRegex(CheckVerificationError, "found 2"):
            verify_workflow_runs(payload)

    def test_failed_or_in_progress_job_fails_closed(self) -> None:
        for status, conclusion in (("completed", "failure"), ("in_progress", None)):
            with self.subTest(status=status, conclusion=conclusion):
                payload = passing_payload()
                entry = payload["workflows"][0]  # type: ignore[index]
                entry["jobs"][0]["status"] = status  # type: ignore[index]
                entry["jobs"][0]["conclusion"] = conclusion  # type: ignore[index]
                with self.assertRaises(CheckVerificationError):
                    verify_workflow_runs(payload)

    def test_truncated_run_pagination_fails_closed(self) -> None:
        payload = passing_payload()
        entry = payload["workflows"][0]  # type: ignore[index]
        entry["runs_total_count"] = 2
        with self.assertRaisesRegex(CheckVerificationError, "pagination is incomplete"):
            verify_workflow_runs(payload)

    def test_truncated_job_pagination_fails_closed(self) -> None:
        payload = passing_payload()
        entry = payload["workflows"][0]  # type: ignore[index]
        entry["jobs_total_count"] = len(entry["jobs"]) + 1  # type: ignore[arg-type]
        with self.assertRaisesRegex(CheckVerificationError, "pagination is incomplete"):
            verify_workflow_runs(payload)

    def test_extra_or_missing_workflow_payload_fails_closed(self) -> None:
        payload = passing_payload()
        payload["workflows"] = payload["workflows"][:-1]  # type: ignore[index]
        with self.assertRaisesRegex(CheckVerificationError, "missing trusted"):
            verify_workflow_runs(payload)
        payload = passing_payload()
        payload["workflows"].append(  # type: ignore[union-attr]
            {"workflow_path": ".github/workflows/other.yml"}
        )
        with self.assertRaisesRegex(CheckVerificationError, "untrusted workflow"):
            verify_workflow_runs(payload)


class ReleaseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[1]
        cls.workflow = (
            cls.repo_root / ".github/workflows/release-candidate.yml"
        ).read_text(encoding="utf-8")
        cls.schema = json.loads(
            (cls.repo_root / ".release/evidence.schema.json").read_text(
                encoding="utf-8"
            )
        )

    def test_candidate_depends_on_identity_bound_verifier(self) -> None:
        self.assertIn("needs: verify_required_checks", self.workflow)
        self.assertIn("python3 .release/verify_checks.py", self.workflow)
        self.assertIn("/actions/workflows/", self.workflow)
        self.assertIn("/actions/runs/${run_id}/jobs", self.workflow)
        self.assertIn("--paginate", self.workflow)
        self.assertIn("--slurp", self.workflow)
        self.assertNotIn("/commits/${SOURCE_SHA}/check-runs", self.workflow)
        self.assertNotIn("workflow_dispatch", self.workflow)
        self.assertRegex(self.workflow, r'tags:\s*\n\s+-\s+"v\*"')

    def test_tag_source_must_equal_current_main_head(self) -> None:
        self.assertIn('main_head="$(git rev-parse origin/main)"', self.workflow)
        self.assertIn('if [[ "$SOURCE_SHA" != "$main_head" ]]', self.workflow)
        self.assertNotIn("merge-base --is-ancestor", self.workflow)

    def test_candidate_uses_quarantine_and_exact_digest_only(self) -> None:
        self.assertIn(":quarantine-", self.workflow)
        self.assertNotIn(":sha-${{", self.workflow)
        self.assertIn(
            'immutable_reference="${IMAGE_NAME}@${IMAGE_DIGEST}"', self.workflow
        )
        self.assertIn("environment: release-candidate", self.workflow)

    def test_all_release_actions_use_immutable_commit_ids(self) -> None:
        action_refs = re.findall(r"^\s*uses:\s*([^#\s]+)", self.workflow, re.MULTILINE)
        self.assertGreater(len(action_refs), 0)
        for action_ref in action_refs:
            with self.subTest(action_ref=action_ref):
                self.assertRegex(action_ref, r"^[^@]+@[0-9a-f]{40}$")

    def test_evidence_schema_requires_all_identity_bound_checks(self) -> None:
        checks = self.schema["properties"]["checks"]
        self.assertEqual(checks["minItems"], len(REQUIRED_CHECKS))
        self.assertEqual(checks["maxItems"], len(REQUIRED_CHECKS))
        properties = checks["items"]["properties"]
        for field in (
            "workflow_path",
            "workflow_run_id",
            "workflow_run_attempt",
            "job_id",
            "event",
            "head_sha",
            "run_url",
            "job_url",
        ):
            self.assertIn(field, properties)


if __name__ == "__main__":
    unittest.main()
