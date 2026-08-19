from __future__ import annotations

import json
import tempfile
import unittest
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from staging_preflight import (
    CommandResult,
    HttpResponse,
    PreflightOptions,
    exit_code,
    migration_inventory,
    run_preflight,
    write_report,
)
from test_validate_evidence import IMAGE_DIGEST, SOURCE_SHA, passing_candidate

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.example.test"
WEB = "https://web.example.test"
SUPABASE = "https://project.supabase.co"
COURSE_ID = "11111111-1111-1111-1111-111111111111"
JWT = "secret-staging-jwt-sentinel"
SERVICE_KEY = "secret-service-role-sentinel"
DATABASE_URL = "postgresql://secret-db-sentinel@example.test/postgres"


class FakeHttp:
    def __init__(self) -> None:
        self.overrides: dict[tuple[str, str], HttpResponse] = {}
        self.accept_dev_auth = False

    def __call__(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        payload: object | None = None,
        timeout: float = 10,
    ) -> HttpResponse:
        key = (method, url)
        if key in self.overrides:
            return self.overrides[key]

        authorization = (headers or {}).get("Authorization", "")
        if key == ("GET", f"{API}/health/live"):
            return HttpResponse(200, {"status": "ok", "environment": "production"})
        if key == ("GET", f"{API}/health/ready"):
            return HttpResponse(
                200,
                {
                    "status": "ok",
                    "checks": {
                        "database": "ok",
                        "pgvector": "ok",
                        "embedding": "ready",
                    },
                },
            )
        if key == ("GET", f"{API}/courses"):
            if authorization == f"Bearer {JWT}":
                return HttpResponse(200, {"items": []})
            if authorization.startswith("Bearer dev:") and self.accept_dev_auth:
                return HttpResponse(200, {"items": []})
            return HttpResponse(401, {"error": {"code": "unauthorized"}})
        if key == ("GET", f"{API}/courses/{COURSE_ID}/chat/availability"):
            return HttpResponse(
                200,
                {
                    "available": True,
                    "reason": None,
                    "allowed_modes": ["qa", "socratic"],
                },
            )
        if key == ("POST", f"{API}/courses/{COURSE_ID}/chat"):
            return HttpResponse(
                200,
                {
                    "status": "answered",
                    "cached": False,
                    "citations": [{"chunk_id": "22222222-2222-2222-2222-222222222222"}],
                },
            )
        if key == ("GET", f"{SUPABASE}/storage/v1/bucket/course-materials"):
            return HttpResponse(200, {"id": "course-materials", "public": False})
        if key == ("GET", WEB):
            return HttpResponse(200, None)
        raise AssertionError(f"Beklenmeyen HTTP çağrısı: {method} {url}")


class FakeRunner:
    def __init__(
        self,
        *,
        remote_versions: list[str] | None = None,
        remote_sha: str = SOURCE_SHA,
    ) -> None:
        local_versions = [item.version for item in migration_inventory(ROOT)]
        self.remote_versions = remote_versions if remote_versions is not None else local_versions
        self.remote_sha = remote_sha

    def __call__(
        self, command: list[str], *, env: Mapping[str, str] | None = None
    ) -> CommandResult:
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return CommandResult(0, f"{SOURCE_SHA}\n")
        if command[:3] == ["git", "ls-remote", "origin"]:
            return CommandResult(0, f"{self.remote_sha}\trefs/heads/main\n")
        if command and command[0] == "psql":
            return CommandResult(0, "\n".join(self.remote_versions) + "\n")
        raise AssertionError(f"Beklenmeyen komut: {command}")


def passing_env() -> dict[str, str]:
    return {
        "STAGING_SMOKE_JWT": JWT,
        "STAGING_SMOKE_QUESTION": "Ders kaynağındaki kilit kavramı açıkla.",
        "DATABASE_URL": DATABASE_URL,
        "SUPABASE_URL": SUPABASE,
        "SUPABASE_SERVICE_ROLE_KEY": SERVICE_KEY,
        "SUPABASE_STORAGE_BUCKET": "course-materials",
    }


class StagingPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        root = Path(self.tempdir.name)
        self.candidate = root / "candidate.json"
        self.candidate.write_text(json.dumps(passing_candidate()), encoding="utf-8")
        self.options = PreflightOptions(
            candidate=self.candidate,
            api_url=API,
            web_url=WEB,
            course_id=COURSE_ID,
            migration_decision="none",
            backup_evidence_ref="https://evidence.example.test/backup/42",
            rollback_evidence_ref="https://evidence.example.test/rollback/42",
            previous_digest="sha256:" + "9" * 64,
            timeout=1,
        )

    def run_report(
        self,
        *,
        env: Mapping[str, str] | None = None,
        http: FakeHttp | None = None,
        runner: FakeRunner | None = None,
    ):
        return run_preflight(
            self.options,
            env=env or passing_env(),
            repo_root=ROOT,
            http=(http or FakeHttp()),
            run_command=(runner or FakeRunner()),
            now=lambda: datetime(2026, 8, 20, tzinfo=UTC),
        )

    def test_full_success_is_passed(self) -> None:
        report = self.run_report()

        self.assertEqual(report.overall, "passed")
        self.assertEqual(exit_code(report), 0)
        self.assertEqual(report.source_sha, SOURCE_SHA)
        self.assertEqual(report.image_digest, IMAGE_DIGEST)
        self.assertFalse(report.unrun)

    def test_missing_secret_is_blocked_and_reports_are_still_written(self) -> None:
        environment = passing_env()
        environment.pop("STAGING_SMOKE_JWT")
        report = self.run_report(env=environment)
        output_root = Path(self.tempdir.name)
        json_out = output_root / "preflight.json"
        markdown_out = output_root / "preflight.md"

        write_report(
            report,
            json_out=json_out,
            markdown_out=markdown_out,
            secrets=environment.values(),
        )

        self.assertEqual(report.overall, "blocked")
        self.assertEqual(exit_code(report), 2)
        self.assertTrue(json_out.is_file())
        self.assertTrue(markdown_out.is_file())

    def test_readiness_503_is_failed(self) -> None:
        http = FakeHttp()
        http.overrides[("GET", f"{API}/health/ready")] = HttpResponse(
            503,
            {"status": "degraded", "checks": {"database": "error"}},
        )

        report = self.run_report(http=http)

        self.assertEqual(report.overall, "failed")
        self.assertEqual(exit_code(report), 1)
        self.assertEqual(report.by_name("readiness").status, "failed")

    def test_secret_sentinels_never_reach_json_or_markdown(self) -> None:
        report = self.run_report()
        output_root = Path(self.tempdir.name)
        json_out = output_root / "preflight.json"
        markdown_out = output_root / "preflight.md"
        environment = passing_env()

        write_report(
            report,
            json_out=json_out,
            markdown_out=markdown_out,
            secrets=environment.values(),
        )

        combined = json_out.read_text() + markdown_out.read_text()
        for value in environment.values():
            self.assertNotIn(value, combined)
        self.assertNotIn("staging-verified", combined)

    def test_remote_migration_mismatch_fails(self) -> None:
        report = self.run_report(runner=FakeRunner(remote_versions=["0001"]))

        self.assertEqual(report.overall, "failed")
        self.assertEqual(report.by_name("migrations").status, "failed")

    def test_cached_or_uncited_llm_answer_fails(self) -> None:
        http = FakeHttp()
        http.overrides[("POST", f"{API}/courses/{COURSE_ID}/chat")] = HttpResponse(
            200,
            {"status": "answered", "cached": True, "citations": []},
        )

        report = self.run_report(http=http)

        self.assertEqual(report.overall, "failed")
        self.assertEqual(report.by_name("real_provider_smoke").status, "failed")

    def test_candidate_must_equal_current_remote_main(self) -> None:
        report = self.run_report(runner=FakeRunner(remote_sha="f" * 40))

        self.assertEqual(report.overall, "failed")
        self.assertEqual(report.by_name("source_main").status, "failed")

    def test_dev_auth_being_accepted_is_a_failure(self) -> None:
        http = FakeHttp()
        http.accept_dev_auth = True

        report = self.run_report(http=http)

        self.assertEqual(report.overall, "failed")
        self.assertEqual(report.by_name("auth").status, "failed")

    def test_public_bucket_is_a_failure(self) -> None:
        http = FakeHttp()
        http.overrides[("GET", f"{SUPABASE}/storage/v1/bucket/course-materials")] = (
            HttpResponse(200, {"id": "course-materials", "public": True})
        )

        report = self.run_report(http=http)

        self.assertEqual(report.overall, "failed")
        self.assertEqual(report.by_name("storage").status, "failed")

    def test_missing_recovery_reference_is_blocked(self) -> None:
        self.options = PreflightOptions(
            **{
                **self.options.__dict__,
                "backup_evidence_ref": "",
            }
        )

        report = self.run_report()

        self.assertEqual(report.overall, "blocked")
        self.assertEqual(report.by_name("recovery_evidence").status, "blocked")


if __name__ == "__main__":
    unittest.main()
