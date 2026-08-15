from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from validate_evidence import EvidenceValidationError, validate_document
from verify_checks import REQUIRED_CHECKS, REQUIRED_WORKFLOWS

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (ROOT / ".release/evidence.schema.json").read_text(encoding="utf-8")
)
SOURCE_SHA = "a" * 40
IMAGE_DIGEST = "sha256:" + "b" * 64
ATTESTATION_DIGEST = "sha256:" + "c" * 64
PREVIOUS_DIGEST = "sha256:" + "d" * 64


def _workflow_for_job(job_name: str) -> str:
    return next(path for path, jobs in REQUIRED_WORKFLOWS.items() if job_name in jobs)


def passing_candidate() -> dict[str, object]:
    image_name = "ghcr.io/example/project/api"
    immutable_reference = f"{image_name}@{IMAGE_DIGEST}"
    return {
        "schema_version": 2,
        "record_type": "candidate",
        "source": {
            "repository": "example/project",
            "sha": SOURCE_SHA,
            "tag_ref": "refs/tags/v1.0.0",
            "workflow": {
                "path": ".github/workflows/release-candidate.yml",
                "event": "push",
                "run_id": 9001,
                "run_attempt": 1,
                "run_url": "https://github.com/example/project/actions/runs/9001",
            },
        },
        "image": {
            "name": image_name,
            "digest": IMAGE_DIGEST,
            "immutable_reference": immutable_reference,
            "quarantine_reference": f"{image_name}:quarantine-{SOURCE_SHA}-9001-1",
        },
        "supply_chain": {
            "sbom": {
                "predicate_type": "https://spdx.dev/Document",
                "reference": f"oci://{image_name}@{ATTESTATION_DIGEST}",
                "digest": ATTESTATION_DIGEST,
            },
            "provenance": {
                "predicate_type": "https://slsa.dev/provenance/v0.2",
                "reference": f"oci://{image_name}@{ATTESTATION_DIGEST}",
                "digest": ATTESTATION_DIGEST,
            },
            "github_attestation": {
                "reference": "https://github.com/example/project/attestations/1",
                "bundle_digest": "sha256:" + "e" * 64,
            },
        },
        "artifact_verification": {
            "image_reference": immutable_reference,
            "offline_embedding": "passed",
            "bake_report": {"status": "passed", "digest": "sha256:" + "f" * 64},
            "rss": {
                "status": "passed",
                "peak_bytes": 2_147_483_648,
                "limit_bytes": 4_294_967_296,
            },
        },
        "admission": {
            "status": "admitted",
            "mechanism": "immutable-evidence-record",
            "evidence_artifact": "release-evidence-aaaaaaaaaaaa",
            "admitted_at": "2026-08-11T00:00:00Z",
        },
        "environments": {
            "staging": "not-configured",
            "production": "not-configured",
        },
        "checks": [
            {
                "name": name,
                "status": "passed",
                "workflow_path": _workflow_for_job(name),
                "workflow_run_id": index,
                "workflow_run_attempt": 1,
                "job_id": index + 100,
                "event": "push",
                "head_sha": SOURCE_SHA,
                "run_url": f"https://github.com/example/project/actions/runs/{index}",
                "job_url": (
                    f"https://github.com/example/project/actions/runs/{index}/job/"
                    f"{index + 100}"
                ),
            }
            for index, name in enumerate(REQUIRED_CHECKS, start=1)
        ],
        "created_at": "2026-08-11T00:00:00Z",
    }


def passing_promotion() -> dict[str, object]:
    document = passing_candidate()
    document["record_type"] = "promotion"
    document["environments"] = {"staging": "verified", "production": "verified"}
    common = {
        "status": "passed",
        "evidence_ref": "https://github.com/example/project/actions/runs/9100",
        "checked_at": "2026-08-11T01:00:00Z",
        "source_sha": SOURCE_SHA,
        "digest": IMAGE_DIGEST,
    }
    document["promotion"] = {
        "target": "production",
        "status": "verified",
        "source_digest": IMAGE_DIGEST,
        "approval": {
            "name": "Release Owner",
            "identity_ref": "github-user:123456",
            "evidence_ref": "https://github.com/example/project/actions/runs/9100",
            "approved_at": "2026-08-11T01:00:00Z",
            "source_sha": SOURCE_SHA,
            "digest": IMAGE_DIGEST,
        },
        "smoke": copy.deepcopy(common),
        "migration": {
            **copy.deepcopy(common),
            "decision": "none",
        },
        "backup": copy.deepcopy(common),
        "rollback": {
            "status": "ready",
            "previous_digest": PREVIOUS_DIGEST,
            "evidence_ref": "https://github.com/example/project/actions/runs/9100",
            "checked_at": "2026-08-11T01:00:00Z",
            "source_sha": SOURCE_SHA,
            "digest": IMAGE_DIGEST,
        },
    }
    return document


class EvidenceSchemaTests(unittest.TestCase):
    def test_candidate_document_passes(self) -> None:
        validate_document(passing_candidate(), SCHEMA)

    def test_promotion_document_passes(self) -> None:
        validate_document(passing_promotion(), SCHEMA)

    def test_candidate_cannot_self_claim_promotion(self) -> None:
        document = passing_candidate()
        document["promotion"] = passing_promotion()["promotion"]
        with self.assertRaisesRegex(EvidenceValidationError, "cannot claim promotion"):
            validate_document(document, SCHEMA)

    def test_candidate_cannot_claim_environment_verification(self) -> None:
        document = passing_candidate()
        document["environments"]["production"] = "verified"  # type: ignore[index]
        with self.assertRaisesRegex(EvidenceValidationError, "cannot claim"):
            validate_document(document, SCHEMA)

    def test_promotion_requires_same_digest_everywhere(self) -> None:
        for section in ("approval", "smoke", "migration", "backup", "rollback"):
            with self.subTest(section=section):
                document = passing_promotion()
                document["promotion"][section]["digest"] = "sha256:" + "9" * 64  # type: ignore[index]
                with self.assertRaisesRegex(
                    EvidenceValidationError, "must equal image"
                ):
                    validate_document(document, SCHEMA)

    def test_production_requires_named_immutable_approval(self) -> None:
        document = passing_promotion()
        document["promotion"]["approval"]["identity_ref"] = "@release-owner"  # type: ignore[index]
        with self.assertRaisesRegex(EvidenceValidationError, "pattern"):
            validate_document(document, SCHEMA)

    def test_promotion_requires_verified_staging_and_production(self) -> None:
        document = passing_promotion()
        document["environments"]["staging"] = "not-configured"  # type: ignore[index]
        with self.assertRaisesRegex(EvidenceValidationError, "verified staging"):
            validate_document(document, SCHEMA)

    def test_supply_chain_reference_must_bind_its_digest(self) -> None:
        document = passing_candidate()
        document["supply_chain"]["sbom"]["reference"] = (  # type: ignore[index]
            "oci://ghcr.io/example/project/api@sha256:" + "0" * 64
        )
        with self.assertRaisesRegex(EvidenceValidationError, "OCI name@digest"):
            validate_document(document, SCHEMA)

    def test_artifact_checks_must_target_exact_image(self) -> None:
        document = passing_candidate()
        document["artifact_verification"]["image_reference"] = (  # type: ignore[index]
            "ghcr.io/example/project/api@sha256:" + "0" * 64
        )
        with self.assertRaisesRegex(EvidenceValidationError, "must target"):
            validate_document(document, SCHEMA)

    def test_check_workflow_and_head_are_identity_bound(self) -> None:
        document = passing_candidate()
        document["checks"][0]["workflow_path"] = ".github/workflows/security.yml"  # type: ignore[index]
        with self.assertRaisesRegex(EvidenceValidationError, "job identity"):
            validate_document(document, SCHEMA)
        document = passing_candidate()
        document["checks"][0]["head_sha"] = "9" * 40  # type: ignore[index]
        with self.assertRaisesRegex(EvidenceValidationError, "source.sha"):
            validate_document(document, SCHEMA)

    def test_unknown_field_and_bad_timestamp_fail_closed(self) -> None:
        document = passing_candidate()
        document["unreviewed"] = True
        with self.assertRaisesRegex(EvidenceValidationError, "unknown field"):
            validate_document(document, SCHEMA)
        document = passing_candidate()
        document["created_at"] = "today"
        with self.assertRaisesRegex(EvidenceValidationError, "date-time"):
            validate_document(document, SCHEMA)


if __name__ == "__main__":
    unittest.main()
