from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts.ai_sdlc_check import _risk_for_path, validate_repository

SOURCE_ROOT = Path(__file__).resolve().parents[1]


class RepositoryFixture:
    def __init__(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self._git("init", "-q")
        self._git("config", "user.name", "AI SDLC Test")
        self._git("config", "user.email", "ai-sdlc@example.invalid")
        self.write_json(".ai/policy.json", self.policy())
        self.write(
            ".ai/schema.json",
            (SOURCE_ROOT / ".ai/schema.json").read_text(encoding="utf-8"),
        )
        self.write_json(
            "evidence/report.json",
            {
                "candidate_sha": "SELF",
                "evidence_label": "fake-provider",
                "result": "pass",
            },
        )
        self.write("evaluation/calibration.json", "{}\n")
        self.write("evaluation/holdout.json", "{}\n")
        self.write("review/human-anchor.md", "human-reviewed anchor\n")
        self.write("README.md", "base\n")
        self.write("apps/api/app/modules/generation/prompts.py", "PROMPT = 'base'\n")
        self.write("evaluation/gold.json", "{}\n")
        self.commit("base")
        self.base = self.head

    @staticmethod
    def policy() -> dict[str, Any]:
        return {
            "schema_version": 1,
            "dossier_schema": ".ai/schema.json",
            "dossier_glob": ".ai/changes/*.json",
            "risk_order": {"R1": 1, "R2": 2, "R3": 3},
            "allowed_evidence_labels": [
                "fake-provider",
                "offline-replay",
                "real-provider",
                "staging",
                "canary",
                "production",
                "rollback",
            ],
            "allowed_statuses": [
                "draft",
                "evidence-ready",
                "awaiting-approval",
                "canary",
                "expanded",
                "rolled-back",
                "closed",
            ],
            "risk_requirements": {
                "R1": {
                    "required_approval_roles": ["peer"],
                    "require_independent_approval": True,
                    "require_feature_flag": False,
                    "require_kill_switch": True,
                    "require_sticky_assignment": False,
                },
                "R2": {
                    "required_approval_roles": ["engineering", "course_or_product"],
                    "require_independent_approval": True,
                    "require_feature_flag": True,
                    "require_kill_switch": True,
                    "require_sticky_assignment": True,
                },
                "R3": {
                    "required_approval_roles": [
                        "engineering",
                        "domain",
                        "security_or_privacy",
                    ],
                    "require_independent_approval": True,
                    "require_feature_flag": True,
                    "require_kill_switch": True,
                    "require_sticky_assignment": True,
                },
            },
            "privacy": {"allow_identifiable_student_content": False},
            "production_claim": {
                "required_passing_labels": ["real-provider"],
                "required_environment_labels_any_of": [
                    "staging",
                    "canary",
                    "production",
                ],
                "minimum_named_human_approval_refs": 2,
            },
            "sensitive_paths": [
                {"pattern": ".ai/changes/**", "minimum_risk": "R3"},
                {"pattern": ".ai/evidence/**", "minimum_risk": "R3"},
                {"pattern": ".ai/quarantine/**", "minimum_risk": "R3"},
                {
                    "pattern": "apps/api/app/modules/generation/**",
                    "minimum_risk": "R2",
                },
                {"pattern": "apps/api/app/api/chat.py", "minimum_risk": "R3"},
                {"pattern": "apps/api/app/modules/policy/**", "minimum_risk": "R3"},
                {
                    "pattern": "evaluation/**",
                    "minimum_risk": "R3",
                    "requires_evaluation_split": True,
                    "requires_human_anchor": True,
                },
            ],
        }

    @property
    def head(self) -> str:
        return self._git("rev-parse", "HEAD").strip()

    def _git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    def write(self, relative: str, content: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def write_json(self, relative: str, content: dict[str, Any]) -> None:
        self.write(relative, json.dumps(content, indent=2, sort_keys=True) + "\n")

    def commit(self, message: str) -> None:
        self._git("add", ".")
        self._git("commit", "-q", "-m", message)

    def close(self) -> None:
        self.temporary.cleanup()

    def artifact(self, path: str) -> dict[str, Any]:
        content = (self.root / path).read_bytes()
        return {
            "path": path,
            "state": "present",
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    def evidence(
        self,
        *,
        path: str = "evidence/report.json",
        label: str = "fake-provider",
        result: str = "pass",
        verification_url: str | None = None,
        report_extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        report: dict[str, Any] = {
            "candidate_sha": "SELF",
            "evidence_label": label,
            "result": result,
        }
        if verification_url is not None:
            report["verification_url"] = verification_url
        if report_extra is not None:
            report.update(report_extra)
        self.write_json(path, report)
        return {
            "label": label,
            "result": result,
            "report_path": path,
            "report_sha256": hashlib.sha256(
                (self.root / path).read_bytes()
            ).hexdigest(),
            "candidate_sha": "SELF",
        }

    def dossier(self, *, path: str, risk: str = "R2") -> dict[str, Any]:
        roles = {
            "R1": ["peer"],
            "R2": ["engineering", "course_or_product"],
            "R3": ["engineering", "domain", "security_or_privacy"],
        }[risk]
        return {
            "schema_version": 1,
            "change_id": "change",
            "lineage_id": "lineage",
            "revision": 1,
            "supersedes": None,
            "previous_status": None,
            "governance_record_risk": "R3",
            "title": "Test change",
            "summary": "Synthetic governance fixture",
            "owner": "author",
            "created_at": "2026-08-11T00:00:00+03:00",
            "review_by": "2026-09-11T00:00:00+03:00",
            "base_sha": self.base,
            "candidate_sha": "SELF",
            "risk_tier": risk,
            "status": "evidence-ready",
            "behavior": {
                "provider_revision": "fake-provider:v1",
                "model_revision": "deterministic:v1",
                "prompt_revision": "sha256:fixture",
                "tool_schema_revision": "none:v1",
                "guardrail_revision": "fixture:v1",
                "retrieval_revision": "none:v1",
                "embedding_revision": "none:v1",
                "evaluator_revision": "validator:v1",
            },
            "data": {
                "corpus_digest": hashlib.sha256(b"").hexdigest(),
                "eval_set_digest": hashlib.sha256(b"fixture").hexdigest(),
                "privacy_classification": "synthetic-non-personal",
            },
            "artifacts": [self.artifact(path)],
            "evidence": [self.evidence()],
            "evaluation": {
                "calibration_ref": "evaluation/calibration.json",
                "holdout_ref": "evaluation/holdout.json",
                "thresholds_declared_before_scoring": True,
                "human_anchor_ref": "review/human-anchor.md",
                "metrics": [
                    {
                        "name": "validator_pass",
                        "baseline": 1,
                        "candidate": 1,
                        "operator": ">=",
                        "threshold": 1,
                        "sample_size": 1,
                    }
                ],
                "exact_command": "python3 scripts/ai_sdlc_check.py --base-sha BASE --head-sha HEAD",
            },
            "approval_requirements": [
                {
                    "role": role,
                    "actor": f"Pending {role} reviewer",
                    "decision": "pending",
                    "approval_ref": None,
                    "approved_at": None,
                    "candidate_sha": "SELF",
                    "independent_of_author": True,
                }
                for role in roles
            ],
            "deployment": {
                "feature_flag": "AI_TEST_FLAG" if risk != "R1" else "NOT_APPLICABLE",
                "flag_state": "disabled" if risk != "R1" else "not-applicable",
                "candidate_sha": "SELF",
                "deployment_id": "not-deployed:test-fixture",
                "environment": "not-deployed",
            },
            "rollout": {
                "feature_flag": "AI_TEST_FLAG" if risk != "R1" else "NOT_APPLICABLE",
                "kill_switch": "Disable AI_TEST_FLAG",
                "assignment": "Sticky assignment by user id"
                if risk != "R1"
                else "Not applicable",
                "initial_exposure": "Internal only",
                "stop_conditions": ["Any safety regression"],
                "expand_conditions": ["All declared thresholds pass"],
                "active_exam_policy": "Exclude active exams",
            },
            "rollback": {
                "previous_compatible_artifact": f"base:{self.base}",
                "procedure": "Revert the candidate commit",
                "max_minutes": 15,
                "verification": "Run deterministic gate",
                "state": "planned",
                "evidence_report_path": None,
                "evidence_report_sha256": None,
                "evidence_candidate_sha": None,
                "evidence_deployment_id": None,
            },
            "privacy": {
                "contains_identifiable_student_content": False,
                "handling": "Synthetic identifiers only",
                "retention": "Repository lifetime",
            },
            "promotion": {"claim": "none", "target": "none", "human_approval_refs": []},
        }

    @staticmethod
    def approve_required(dossier: dict[str, Any]) -> list[str]:
        actors = {
            "peer": "Ada Peer",
            "engineering": "Deniz Engineer",
            "course_or_product": "Ece Product",
            "domain": "Yasemin Domain",
            "security_or_privacy": "Selin Security",
        }
        references: list[str] = []
        for index, approval in enumerate(dossier["approval_requirements"], start=1):
            reference = (
                "https://github.com/muratcan-ates/DOU-Synapse/"
                f"pull/42#pullrequestreview-{1000 + index}"
            )
            approval.update(
                {
                    "actor": actors[approval["role"]],
                    "decision": "approved",
                    "approval_ref": reference,
                    "approved_at": "2026-08-11T01:00:00+03:00",
                    "candidate_sha": "SELF",
                }
            )
            references.append(reference)
        return references

    def bind_verified_rollback(self, dossier: dict[str, Any]) -> None:
        deployment_id = dossier["deployment"]["deployment_id"]
        rollback_evidence = self.evidence(
            path="evidence/rollback.json",
            label="rollback",
            report_extra={
                "rollback_verified": True,
                "deployment_id": deployment_id,
            },
        )
        dossier["evidence"].append(rollback_evidence)
        dossier["rollback"].update(
            {
                "state": "verified-before-production",
                "evidence_report_path": rollback_evidence["report_path"],
                "evidence_report_sha256": rollback_evidence["report_sha256"],
                "evidence_candidate_sha": "SELF",
                "evidence_deployment_id": deployment_id,
            }
        )

    def commit_ai_change(self, dossier: dict[str, Any] | None = None) -> None:
        self.write(
            "apps/api/app/modules/generation/prompts.py", "PROMPT = 'candidate'\n"
        )
        if dossier is not None:
            dossier = copy.deepcopy(dossier)
            dossier["artifacts"] = [
                self.artifact("apps/api/app/modules/generation/prompts.py")
            ]
            self.write_json(".ai/changes/change.json", dossier)
        self.commit("candidate")

    def validate(self) -> list[str]:
        return validate_repository(
            repo_root=self.root,
            policy_path=".ai/policy.json",
            base_sha=self.base,
            head_sha=self.head,
        )


class AiSdlcValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = RepositoryFixture()

    def tearDown(self) -> None:
        self.repo.close()

    def _valid_change(self) -> dict[str, Any]:
        self.repo.write(
            "apps/api/app/modules/generation/prompts.py", "PROMPT = 'candidate'\n"
        )
        return self.repo.dossier(path="apps/api/app/modules/generation/prompts.py")

    def _mutate_committed_dossier(self, mutation: Any) -> None:
        path = self.repo.root / ".ai/changes/change.json"
        dossier = json.loads(path.read_text(encoding="utf-8"))
        mutation(dossier)
        self.repo.write_json(".ai/changes/change.json", dossier)
        self.repo.commit("mutate dossier")

    def test_non_ai_diff_needs_no_dossier(self) -> None:
        self.repo.write("README.md", "documentation only\n")
        self.repo.commit("docs")
        self.assertEqual([], self.repo.validate())

    def test_mutable_review_refs_are_rejected(self) -> None:
        errors = validate_repository(
            repo_root=self.repo.root,
            policy_path=".ai/policy.json",
            base_sha="main",
            head_sha="HEAD",
        )
        self.assertEqual(
            [
                "BASE_REF_NOT_IMMUTABLE:base_sha",
                "HEAD_REF_NOT_IMMUTABLE:head_sha",
            ],
            errors,
        )

    def test_uncovered_ai_diff_fails(self) -> None:
        self.repo.commit_ai_change()
        self.assertIn(
            "UNCOVERED:apps/api/app/modules/generation/prompts.py",
            self.repo.validate(),
        )

    def test_chat_orchestration_is_r3_and_needs_a_dossier(self) -> None:
        self.repo.write(
            "apps/api/app/api/chat.py", "SYSTEM_PROMPT = 'answer anything'\n"
        )
        self.repo.commit("change chat orchestration")
        self.assertIn("UNCOVERED:apps/api/app/api/chat.py", self.repo.validate())

    def test_governance_bootstrap_is_r3_even_when_policy_omits_it(self) -> None:
        self.repo.write("scripts/ai_sdlc_check.py", "# governance mutation\n")
        self.repo.commit("mutate governance gate")
        self.assertIn("UNCOVERED:scripts/ai_sdlc_check.py", self.repo.validate())

    def test_policy_cannot_weaken_hardcoded_minimums(self) -> None:
        policy = self.repo.policy()
        policy["allowed_evidence_labels"].append("unreviewed-production")
        policy["risk_requirements"]["R3"]["required_approval_roles"] = []
        policy["risk_requirements"]["R3"]["require_kill_switch"] = False
        policy["privacy"]["allow_identifiable_student_content"] = True
        policy["production_claim"]["minimum_named_human_approval_refs"] = 0
        self.repo.write_json(".ai/policy.json", policy)
        self.repo.commit("weaken policy")
        errors = self.repo.validate()
        self.assertIn("POLICY_EVIDENCE_LABELS:allowed_evidence_labels", errors)
        self.assertIn("POLICY_APPROVAL_ROLES:R3", errors)
        self.assertIn("POLICY_MINIMUM:R3:require_kill_switch", errors)
        self.assertIn("POLICY_PRIVACY:allow_identifiable_student_content", errors)
        self.assertIn("POLICY_PRODUCTION:minimum_named_human_approval_refs", errors)

    def test_sensitive_rename_cannot_escape_policy(self) -> None:
        old_path = "apps/api/app/modules/generation/prompts.py"
        new_path = "apps/api/app/modules/unclassified/prompts.py"
        (self.repo.root / new_path).parent.mkdir(parents=True, exist_ok=True)
        self.repo._git("mv", old_path, new_path)
        self.repo.commit("move governed behavior outside policy")
        errors = self.repo.validate()
        self.assertIn(f"SENSITIVE_RENAME_ESCAPE:{new_path}", errors)
        self.assertIn(f"UNCOVERED:{new_path}", errors)

    def test_low_similarity_move_cannot_escape_rename_detection(self) -> None:
        old_path = self.repo.root / "apps/api/app/modules/generation/prompts.py"
        new_relative = "apps/api/app/modules/unclassified/runtime_policy.py"
        old_path.unlink()
        self.repo.write(
            new_relative,
            "def runtime_policy(value: object) -> bool:\n"
            "    return value is not None\n",
        )
        self.repo.commit("move and rewrite governed behavior")
        errors = self.repo.validate()
        self.assertIn(f"SENSITIVE_MOVE_AMBIGUOUS:{new_relative}", errors)
        self.assertIn(f"UNCOVERED:{new_relative}", errors)

    def test_self_candidate_and_current_sha256_pass(self) -> None:
        self.repo.commit_ai_change(self._valid_change())
        self.assertEqual([], self.repo.validate())

    def test_hash_mutation_is_rejected_as_rewritten_history(self) -> None:
        self.repo.commit_ai_change(self._valid_change())
        self._mutate_committed_dossier(
            lambda dossier: dossier["artifacts"][0].update({"sha256": "0" * 64})
        )
        self.assertIn(
            "AUDIT_HISTORY_REWRITE:.ai/changes/change.json", self.repo.validate()
        )

    def test_evidence_hash_mutation_is_rejected_as_rewritten_history(self) -> None:
        self.repo.commit_ai_change(self._valid_change())
        self._mutate_committed_dossier(
            lambda dossier: dossier["evidence"][0].update({"report_sha256": "0" * 64})
        )
        self.assertIn(
            "AUDIT_HISTORY_REWRITE:.ai/changes/change.json", self.repo.validate()
        )

    def test_risk_downgrade_fails(self) -> None:
        dossier = self._valid_change()
        dossier["risk_tier"] = "R1"
        dossier["approval_requirements"] = [
            {"role": "peer", "owner": "peer-reviewer", "independent_of_author": True}
        ]
        self.repo.commit_ai_change(dossier)
        self.assertTrue(
            any(error.startswith("RISK:") for error in self.repo.validate())
        )

    def test_unknown_evidence_label_fails_without_echoing_payload(self) -> None:
        dossier = self._valid_change()
        dossier["evidence"][0]["label"] = "student-answer-secret"
        self.repo.commit_ai_change(dossier)
        errors = self.repo.validate()
        self.assertTrue(any(error.startswith("EVIDENCE_LABEL:") for error in errors))
        self.assertNotIn("student-answer-secret", "\n".join(errors))

    def test_invalid_nested_types_fail_with_stable_codes(self) -> None:
        dossier = self._valid_change()
        dossier["status"] = {"unexpected": "mapping"}
        dossier["evidence"][0]["result"] = ["pass"]
        dossier["promotion"]["claim"] = {"unexpected": "mapping"}
        self.repo.commit_ai_change(dossier)
        errors = self.repo.validate()
        self.assertTrue(any(error.startswith("STATUS:") for error in errors))
        self.assertTrue(any(error.startswith("EVIDENCE_RESULT:") for error in errors))
        self.assertTrue(any(error.startswith("PROMOTION:") for error in errors))

    def test_control_character_artifact_path_is_rejected_without_log_forgery(
        self,
    ) -> None:
        self.repo.commit_ai_change(self._valid_change())
        self._mutate_committed_dossier(
            lambda dossier: dossier.update(
                {
                    "artifacts": [
                        {
                            "path": "secret\nAI_SDLC_CHECK=PASS",
                            "state": "present",
                            "sha256": "0" * 64,
                        }
                    ]
                }
            )
        )
        errors = self.repo.validate()
        self.assertIn("AUDIT_HISTORY_REWRITE:.ai/changes/change.json", errors)
        self.assertNotIn("AI_SDLC_CHECK=PASS", "\n".join(errors))

    def test_control_character_git_path_fails_closed_without_log_forgery(self) -> None:
        self.repo.write(
            "apps/api/app/modules/generation/bad\nAI_SDLC_CHECK=PASS.py",
            "PROMPT = 'unsafe path'\n",
        )
        self.repo.commit("unsafe git path")
        errors = self.repo.validate()
        self.assertEqual(["INVALID_GIT_PATH"], errors)

    def test_identifiable_student_content_fails_without_echoing_handling(self) -> None:
        dossier = self._valid_change()
        dossier["privacy"]["contains_identifiable_student_content"] = True
        dossier["privacy"]["handling"] = "private-student-payload"
        self.repo.commit_ai_change(dossier)
        errors = self.repo.validate()
        self.assertTrue(any(error.startswith("PRIVACY:") for error in errors))
        self.assertNotIn("private-student-payload", "\n".join(errors))

    def test_missing_kill_switch_fails(self) -> None:
        dossier = self._valid_change()
        dossier["rollout"]["kill_switch"] = ""
        self.repo.commit_ai_change(dossier)
        self.assertTrue(
            any(error.endswith(":kill_switch") for error in self.repo.validate())
        )

    def test_missing_rollback_procedure_fails(self) -> None:
        dossier = self._valid_change()
        dossier["rollback"]["procedure"] = ""
        self.repo.commit_ai_change(dossier)
        self.assertTrue(
            any(error.endswith(":procedure") for error in self.repo.validate())
        )

    def test_machine_contract_rejects_missing_behavior_data_metrics_and_deployment(
        self,
    ) -> None:
        dossier = self._valid_change()
        dossier.pop("behavior")
        dossier["data"]["corpus_digest"] = "mutable-alias"
        dossier["evaluation"]["metrics"] = []
        dossier["deployment"]["candidate_sha"] = "0" * 40
        self.repo.commit_ai_change(dossier)
        errors = self.repo.validate()
        self.assertTrue(any(error.startswith("BEHAVIOR:") for error in errors))
        self.assertTrue(any(error.startswith("DATA_DIGEST:") for error in errors))
        self.assertTrue(
            any(error.startswith("EVALUATION_METRICS:") for error in errors)
        )
        self.assertTrue(any(error.startswith("DEPLOYMENT_SHA:") for error in errors))

    def test_governance_record_risk_is_always_r3(self) -> None:
        dossier = self._valid_change()
        dossier["governance_record_risk"] = "R2"
        self.repo.commit_ai_change(dossier)
        self.assertTrue(
            any(error.startswith("AUDIT_RISK:") for error in self.repo.validate())
        )

    def test_required_approval_must_be_independent(self) -> None:
        dossier = self._valid_change()
        dossier["approval_requirements"][0]["actor"] = dossier["owner"]
        dossier["approval_requirements"][0]["independent_of_author"] = False
        self.repo.commit_ai_change(dossier)
        self.assertTrue(
            any(
                error.startswith("APPROVAL_INDEPENDENCE:")
                for error in self.repo.validate()
            )
        )

    def test_fake_only_cannot_support_production_ready_claim(self) -> None:
        dossier = self._valid_change()
        dossier["promotion"] = {
            "claim": "production-ready",
            "target": "production",
            "human_approval_refs": ["review/ENG-1", "review/COURSE-1"],
        }
        self.repo.commit_ai_change(dossier)
        self.assertTrue(
            any(
                error.startswith("PRODUCTION_EVIDENCE:")
                for error in self.repo.validate()
            )
        )

    def test_production_ready_rejects_self_asserted_reports_and_approval_names(
        self,
    ) -> None:
        dossier = self._valid_change()
        dossier["status"] = "closed"
        dossier["evidence"] = [
            self.repo.evidence(path="evidence/real.json", label="real-provider"),
            self.repo.evidence(path="evidence/production.json", label="production"),
        ]
        dossier["promotion"] = {
            "claim": "production-ready",
            "target": "production",
            "human_approval_refs": ["made-up/one", "made-up/two"],
        }
        self.repo.commit_ai_change(dossier)
        errors = self.repo.validate()
        self.assertTrue(
            any(error.startswith("EVIDENCE_EXTERNAL_VERIFICATION:") for error in errors)
        )
        self.assertTrue(
            any(error.startswith("PRODUCTION_APPROVAL_REF:") for error in errors)
        )

    def test_production_ready_accepts_hash_bound_external_run_and_review_refs(
        self,
    ) -> None:
        dossier = self._valid_change()
        dossier["status"] = "closed"
        dossier["evidence"] = [
            self.repo.evidence(
                path="evidence/real.json",
                label="real-provider",
                verification_url="https://github.com/muratcan-ates/DOU-Synapse/actions/runs/123",
            ),
            self.repo.evidence(
                path="evidence/production.json",
                label="production",
                verification_url=(
                    "https://github.com/muratcan-ates/DOU-Synapse/actions/runs/124/attempts/1"
                ),
            ),
        ]
        approval_refs = self.repo.approve_required(dossier)
        dossier["deployment"].update(
            {
                "flag_state": "enabled",
                "environment": "production",
                "deployment_id": "production:fixture-42",
            }
        )
        dossier["promotion"] = {
            "claim": "production-ready",
            "target": "production",
            "human_approval_refs": approval_refs,
        }
        self.repo.commit_ai_change(dossier)
        self.assertEqual([], self.repo.validate())

    def test_canary_requires_immutable_named_approvals(self) -> None:
        dossier = self._valid_change()
        dossier["status"] = "canary"
        dossier["evidence"] = [
            self.repo.evidence(
                path="evidence/real.json",
                label="real-provider",
                verification_url="https://github.com/muratcan-ates/DOU-Synapse/actions/runs/123",
            ),
            self.repo.evidence(
                path="evidence/canary.json",
                label="canary",
                verification_url="https://github.com/muratcan-ates/DOU-Synapse/actions/runs/124",
            ),
        ]
        dossier["deployment"].update({"flag_state": "canary", "environment": "canary"})
        dossier["promotion"] = {
            "claim": "development",
            "target": "canary",
            "human_approval_refs": [],
        }
        self.repo.commit_ai_change(dossier)
        errors = self.repo.validate()
        self.assertTrue(any(error.startswith("APPROVAL_REQUIRED:") for error in errors))
        self.assertTrue(
            any(error.startswith("APPROVAL_PROMOTION:") for error in errors)
        )

    def test_canary_accepts_candidate_bound_named_approvals(self) -> None:
        dossier = self._valid_change()
        dossier["status"] = "canary"
        dossier["evidence"] = [
            self.repo.evidence(
                path="evidence/real.json",
                label="real-provider",
                verification_url="https://github.com/muratcan-ates/DOU-Synapse/actions/runs/123",
            ),
            self.repo.evidence(
                path="evidence/canary.json",
                label="canary",
                verification_url="https://github.com/muratcan-ates/DOU-Synapse/actions/runs/124",
            ),
        ]
        dossier["deployment"].update({"flag_state": "canary", "environment": "canary"})
        dossier["promotion"] = {
            "claim": "development",
            "target": "canary",
            "human_approval_refs": self.repo.approve_required(dossier),
        }
        self.repo.commit_ai_change(dossier)
        self.assertEqual([], self.repo.validate())

    def test_rolled_back_requires_hash_bound_rollback_evidence(self) -> None:
        dossier = self._valid_change()
        dossier["status"] = "rolled-back"
        self.repo.commit_ai_change(dossier)
        errors = self.repo.validate()
        self.assertTrue(any(error.startswith("STATUS_EVIDENCE:") for error in errors))
        self.assertTrue(any(error.startswith("ROLLBACK_STATUS:") for error in errors))

    def test_closed_accepts_verified_rollback_before_production(self) -> None:
        dossier = self._valid_change()
        dossier["status"] = "closed"
        self.repo.bind_verified_rollback(dossier)
        self.repo.commit_ai_change(dossier)
        self.assertEqual([], self.repo.validate())

    def test_status_and_promotion_semantics_cannot_conflict(self) -> None:
        dossier = self._valid_change()
        dossier["promotion"] = {
            "claim": "development",
            "target": "canary",
            "human_approval_refs": [],
        }
        self.repo.commit_ai_change(dossier)
        self.assertTrue(
            any(error.startswith("STATUS_PROMOTION:") for error in self.repo.validate())
        )

    def test_expanded_status_cannot_be_supported_by_fake_only_evidence(self) -> None:
        dossier = self._valid_change()
        dossier["status"] = "expanded"
        self.repo.commit_ai_change(dossier)
        self.assertTrue(
            any(error.startswith("STATUS_EVIDENCE:") for error in self.repo.validate())
        )

    def test_wrong_candidate_sha_is_not_eligible(self) -> None:
        dossier = self._valid_change()
        dossier["candidate_sha"] = "0" * 40
        self.repo.commit_ai_change(dossier)
        errors = self.repo.validate()
        self.assertTrue(any(error.startswith("CANDIDATE_SHA:") for error in errors))
        self.assertIn("UNCOVERED:apps/api/app/modules/generation/prompts.py", errors)

    def test_evaluator_change_requires_separate_split(self) -> None:
        self.repo.write("evaluation/gold.json", '{"changed": true}\n')
        dossier = self.repo.dossier(path="evaluation/gold.json", risk="R3")
        dossier["evaluation"]["holdout_ref"] = dossier["evaluation"]["calibration_ref"]
        self.repo.write_json(".ai/changes/change.json", dossier)
        self.repo.commit("evaluation candidate")
        self.assertTrue(
            any(error.startswith("EVALUATION_SPLIT:") for error in self.repo.validate())
        )

    def test_deleted_ai_artifact_can_be_covered_explicitly(self) -> None:
        target = "apps/api/app/modules/generation/prompts.py"
        (self.repo.root / target).unlink()
        dossier = self.repo.dossier(path="README.md")
        dossier["artifacts"] = [{"path": target, "state": "deleted", "sha256": None}]
        self.repo.write_json(".ai/changes/change.json", dossier)
        self.repo.commit("delete governed artifact")
        self.assertEqual([], self.repo.validate())

    def _commit_audited_evidence(self) -> str:
        self.repo.write(
            "apps/api/app/modules/generation/prompts.py", "PROMPT = 'candidate'\n"
        )
        dossier = self.repo.dossier(path="apps/api/app/modules/generation/prompts.py")
        dossier["evidence"] = [
            self.repo.evidence(path=".ai/evidence/run.json", label="fake-provider")
        ]
        self.repo.write_json(".ai/changes/change.json", dossier)
        self.repo.commit("governed candidate with evidence")
        self.assertEqual([], self.repo.validate())
        self.repo.base = self.repo.head
        return ".ai/evidence/run.json"

    def _prepare_second_revision(self) -> dict[str, Any]:
        previous_path = ".ai/changes/change.json"
        previous_digest = hashlib.sha256(
            (self.repo.root / previous_path).read_bytes()
        ).hexdigest()
        self.repo.write(
            "apps/api/app/modules/generation/prompts.py", "PROMPT = 'candidate-2'\n"
        )
        dossier = self.repo.dossier(path="apps/api/app/modules/generation/prompts.py")
        dossier.update(
            {
                "change_id": "change-r2",
                "lineage_id": "lineage",
                "revision": 2,
                "supersedes": {
                    "path": previous_path,
                    "sha256": previous_digest,
                },
                "previous_status": "evidence-ready",
            }
        )
        return dossier

    def _prepare_rewritten_lineage(
        self, *, quarantine_only_evidence: bool = False
    ) -> dict[str, str]:
        """Create one rewritten dossier and one descendant that trusts it."""

        target = "apps/api/app/modules/generation/prompts.py"
        parent_path = ".ai/changes/quarantine-parent.json"
        child_path = ".ai/changes/quarantine-child.json"
        self.repo.write(target, "PROMPT = 'quarantine-candidate'\n")
        parent = self.repo.dossier(path=target, risk="R3")
        parent.update(
            {"change_id": "quarantine-parent", "lineage_id": "quarantine-lineage"}
        )
        if quarantine_only_evidence:
            parent["evidence"] = [
                self.repo.evidence(path=".ai/evidence/quarantine-only.json")
            ]
        self.repo.write_json(parent_path, parent)
        self.repo.commit("introduce immutable parent")
        parent_introduction = self.repo.head

        parent["summary"] = "This forbidden rewrite must never gain authority"
        self.repo.write_json(parent_path, parent)
        self.repo.commit("rewrite parent history")
        rewritten_head = self.repo.head
        parent_digest = hashlib.sha256(
            (self.repo.root / parent_path).read_bytes()
        ).hexdigest()

        child = self.repo.dossier(path=target, risk="R3")
        child.update(
            {
                "change_id": "quarantine-child",
                "lineage_id": "quarantine-lineage",
                "revision": 2,
                "supersedes": {"path": parent_path, "sha256": parent_digest},
                "previous_status": "evidence-ready",
                "base_sha": rewritten_head,
            }
        )
        self.repo.write_json(child_path, child)
        self.repo.commit("introduce descendant of rewritten parent")
        return {
            "target": target,
            "parent_path": parent_path,
            "parent_introduction": parent_introduction,
            "parent_digest": parent_digest,
            "child_path": child_path,
            "child_introduction": self.repo.head,
        }

    def _commit_quarantine_replacement(
        self,
        lineage: dict[str, str],
        *,
        include_target: bool = True,
        replacement_base: str | None = None,
    ) -> tuple[str, str]:
        quarantine_path = ".ai/quarantine/quarantine-lineage-legacy.json"
        replacement_path = ".ai/changes/quarantine-replacement.json"
        quarantine = {
            "schema_version": 1,
            "quarantine_id": "quarantine-lineage-legacy",
            "title": "Quarantine rewritten synthetic lineage",
            "owner": "AI SDLC Test",
            "created_at": "2026-08-11T02:00:00+03:00",
            "base_sha": self.repo.base,
            "candidate_sha": "SELF",
            "replacement_dossier": replacement_path,
            "records": [
                {
                    "path": lineage["parent_path"],
                    "introduced_sha": lineage["parent_introduction"],
                    "final_blob_sha256": hashlib.sha256(
                        (self.repo.root / lineage["parent_path"]).read_bytes()
                    ).hexdigest(),
                    "reason": "history-rewritten",
                    "contaminated_by": None,
                },
                {
                    "path": lineage["child_path"],
                    "introduced_sha": lineage["child_introduction"],
                    "final_blob_sha256": hashlib.sha256(
                        (self.repo.root / lineage["child_path"]).read_bytes()
                    ).hexdigest(),
                    "reason": "descends-from-quarantined",
                    "contaminated_by": lineage["parent_path"],
                },
            ],
        }
        self.repo.write_json(quarantine_path, quarantine)
        replacement = self.repo.dossier(path=lineage["target"], risk="R3")
        replacement.update(
            {
                "change_id": "quarantine-replacement",
                "lineage_id": "quarantine-replacement",
                "base_sha": replacement_base or self.repo.base,
            }
        )
        replacement["artifacts"] = [self.repo.artifact(quarantine_path)]
        if include_target:
            replacement["artifacts"].append(self.repo.artifact(lineage["target"]))
        self.repo.write_json(replacement_path, replacement)
        self.repo.commit("quarantine rewritten lineage with exact replacement")
        return quarantine_path, replacement_path

    def _commit_quarantine_successors(
        self,
        lineage: dict[str, str],
        *,
        count: int = 1,
        include_replacement: bool = True,
        include_target: bool = True,
        non_root: bool = False,
        wrong_replacement_hash: bool = False,
    ) -> tuple[str, str, list[str]]:
        quarantine_path, replacement_path = self._commit_quarantine_replacement(lineage)
        successor_paths: list[str] = []
        for index in range(count):
            suffix = "" if index == 0 else f"-{index + 1}"
            successor_path = f".ai/changes/quarantine-successor{suffix}.json"
            successor_id = f"quarantine-successor{suffix}"
            successor = self.repo.dossier(path=lineage["target"], risk="R3")
            successor.update(
                {
                    "change_id": successor_id,
                    "lineage_id": successor_id,
                }
            )
            artifacts = [self.repo.artifact(quarantine_path)]
            if include_replacement:
                replacement_artifact = self.repo.artifact(replacement_path)
                if wrong_replacement_hash:
                    replacement_artifact["sha256"] = "0" * 64
                artifacts.append(replacement_artifact)
            if include_target:
                artifacts.append(self.repo.artifact(lineage["target"]))
            successor["artifacts"] = artifacts
            if non_root:
                successor.update(
                    {
                        "revision": 2,
                        "supersedes": {
                            "path": replacement_path,
                            "sha256": hashlib.sha256(
                                (self.repo.root / replacement_path).read_bytes()
                            ).hexdigest(),
                        },
                        "previous_status": "evidence-ready",
                    }
                )
            self.repo.write_json(successor_path, successor)
            successor_paths.append(successor_path)
        self.repo.commit("bind historical quarantine replacement from final root")
        return quarantine_path, replacement_path, successor_paths

    def test_valid_hash_bound_revision_chain_passes(self) -> None:
        self._commit_audited_evidence()
        dossier = self._prepare_second_revision()
        self.repo.write_json(".ai/changes/change-r2.json", dossier)
        self.repo.commit("valid second revision")
        self.assertEqual([], self.repo.validate())

    def test_stacked_dossiers_are_bound_to_their_introduction_commits(self) -> None:
        original_base = self.repo.base
        target = "apps/api/app/modules/generation/prompts.py"

        self.repo.write(target, "PROMPT = 'stack-one'\n")
        first = self.repo.dossier(path=target)
        first.update({"change_id": "stack-one", "lineage_id": "stacked"})
        first["evidence"] = [self.repo.evidence(path=".ai/evidence/stack-one.json")]
        self.repo.write_json(".ai/changes/stack-one.json", first)
        self.repo.commit("first reviewed stack slice")
        first_head = self.repo.head
        first_digest = hashlib.sha256(
            (self.repo.root / ".ai/changes/stack-one.json").read_bytes()
        ).hexdigest()

        self.repo.write(target, "PROMPT = 'stack-two'\n")
        second = self.repo.dossier(path=target)
        second.update(
            {
                "change_id": "stack-two",
                "lineage_id": "stacked",
                "revision": 2,
                "supersedes": {
                    "path": ".ai/changes/stack-one.json",
                    "sha256": first_digest,
                },
                "previous_status": "evidence-ready",
                "base_sha": first_head,
            }
        )
        second["evidence"] = [self.repo.evidence(path=".ai/evidence/stack-two.json")]
        self.repo.write_json(".ai/changes/stack-two.json", second)
        self.repo.commit("second reviewed stack slice")

        self.repo.write(target, "PROMPT = 'integrated'\n")
        integration = self.repo.dossier(path=target)
        integration.update(
            {
                "change_id": "stack-integration",
                "lineage_id": "stack-integration",
                "base_sha": original_base,
            }
        )
        integration["evidence"] = [
            self.repo.evidence(path=".ai/evidence/stack-integration.json")
        ]
        self.repo.write_json(".ai/changes/stack-integration.json", integration)
        self.repo.commit("bind the whole reviewed stack")

        self.assertEqual([], self.repo.validate())

    def test_superseded_child_cannot_retroactively_validate_future_artifact(
        self,
    ) -> None:
        target = "apps/api/app/modules/generation/prompts.py"
        settled_content = "PROMPT = 'settled-before-child-review'\n"

        self.repo.write(target, "PROMPT = 'working-tree-not-yet-settled'\n")
        first = self.repo.dossier(path=target)
        first.update({"change_id": "stack-parent", "lineage_id": "stacked"})
        first["artifacts"][0]["sha256"] = hashlib.sha256(
            settled_content.encode("utf-8")
        ).hexdigest()
        first["evidence"] = [self.repo.evidence(path=".ai/evidence/stack-parent.json")]
        self.repo.write_json(".ai/changes/stack-parent.json", first)
        self.repo.commit("introduce parent before its branch snapshot settles")

        self.repo.write(target, settled_content)
        self.repo.commit("settle the parent branch snapshot")
        settled_base = self.repo.head
        parent_digest = hashlib.sha256(
            (self.repo.root / ".ai/changes/stack-parent.json").read_bytes()
        ).hexdigest()

        second = self.repo.dossier(path=target)
        second.update(
            {
                "change_id": "stack-child",
                "lineage_id": "stacked",
                "revision": 2,
                "supersedes": {
                    "path": ".ai/changes/stack-parent.json",
                    "sha256": parent_digest,
                },
                "previous_status": "evidence-ready",
                "base_sha": settled_base,
            }
        )
        second["evidence"] = [self.repo.evidence(path=".ai/evidence/stack-child.json")]
        self.repo.write_json(".ai/changes/stack-child.json", second)
        self.repo.commit("review child against the settled parent snapshot")

        errors = self.repo.validate()
        self.assertTrue(
            any(error.startswith("HASH_MISMATCH:stack-parent:") for error in errors)
        )

    def test_rewritten_dossier_without_quarantine_fails_closed(self) -> None:
        lineage = self._prepare_rewritten_lineage()
        errors = self.repo.validate()
        self.assertIn(f"AUDIT_HISTORY_REWRITE:{lineage['parent_path']}", errors)
        self.assertIn(f"AUDIT_APPEND_ONLY:{lineage['parent_path']}", errors)
        self.assertIn(f"UNCOVERED:{lineage['target']}", errors)

    def test_justified_quarantine_with_full_exact_root_passes(self) -> None:
        lineage = self._prepare_rewritten_lineage()
        self._commit_quarantine_replacement(lineage)
        self.assertEqual([], self.repo.validate())

    def test_valid_dossier_cannot_be_quarantined_without_cause(self) -> None:
        target = "apps/api/app/modules/generation/prompts.py"
        dossier_path = ".ai/changes/valid-parent.json"
        self.repo.write(target, "PROMPT = 'valid-parent'\n")
        dossier = self.repo.dossier(path=target, risk="R3")
        dossier.update({"change_id": "valid-parent", "lineage_id": "valid-parent"})
        self.repo.write_json(dossier_path, dossier)
        self.repo.commit("introduce valid immutable parent")
        introduction = self.repo.head

        quarantine_path = ".ai/quarantine/valid-parent-legacy.json"
        replacement_path = ".ai/changes/valid-parent-replacement.json"
        self.repo.write_json(
            quarantine_path,
            {
                "schema_version": 1,
                "quarantine_id": "valid-parent-legacy",
                "title": "Invalid attempt to hide a valid record",
                "owner": "AI SDLC Test",
                "created_at": "2026-08-11T02:00:00+03:00",
                "base_sha": self.repo.base,
                "candidate_sha": "SELF",
                "replacement_dossier": replacement_path,
                "records": [
                    {
                        "path": dossier_path,
                        "introduced_sha": introduction,
                        "final_blob_sha256": hashlib.sha256(
                            (self.repo.root / dossier_path).read_bytes()
                        ).hexdigest(),
                        "reason": "history-rewritten",
                        "contaminated_by": None,
                    }
                ],
            },
        )
        replacement = self.repo.dossier(path=target, risk="R3")
        replacement.update(
            {
                "change_id": "valid-parent-replacement",
                "lineage_id": "valid-parent-replacement",
            }
        )
        replacement["artifacts"] = [
            self.repo.artifact(target),
            self.repo.artifact(quarantine_path),
        ]
        self.repo.write_json(replacement_path, replacement)
        self.repo.commit("attempt unjustified quarantine")

        self.assertIn(f"QUARANTINE_UNJUSTIFIED:{dossier_path}", self.repo.validate())

    def test_quarantined_dossier_cannot_supply_artifact_coverage(self) -> None:
        lineage = self._prepare_rewritten_lineage()
        self._commit_quarantine_replacement(lineage, include_target=False)
        errors = self.repo.validate()
        self.assertIn(f"UNCOVERED:{lineage['target']}", errors)
        self.assertTrue(
            any(
                error.startswith("QUARANTINE_REPLACEMENT_COVERAGE:")
                and error.endswith(lineage["target"])
                for error in errors
            )
        )

    def test_quarantine_only_evidence_is_unreferenced(self) -> None:
        lineage = self._prepare_rewritten_lineage(quarantine_only_evidence=True)
        self._commit_quarantine_replacement(lineage)
        self.assertIn(
            "UNREFERENCED_EVIDENCE:.ai/evidence/quarantine-only.json",
            self.repo.validate(),
        )

    def test_quarantine_replacement_must_bind_exact_base_and_head(self) -> None:
        lineage = self._prepare_rewritten_lineage()
        self._commit_quarantine_replacement(
            lineage, replacement_base=lineage["parent_introduction"]
        )
        errors = self.repo.validate()
        self.assertIn(
            "QUARANTINE_REPLACEMENT_CONTEXT:quarantine-replacement:base-head",
            errors,
        )

    def test_historical_quarantine_replacement_has_one_exact_successor(self) -> None:
        lineage = self._prepare_rewritten_lineage()
        self._commit_quarantine_successors(lineage)
        self.assertEqual([], self.repo.validate())

    def test_quarantine_successor_must_bind_historical_replacement(self) -> None:
        lineage = self._prepare_rewritten_lineage()
        self._commit_quarantine_successors(lineage, include_replacement=False)
        self.assertIn(
            "QUARANTINE_REPLACEMENT_CONTEXT:quarantine-replacement:base-head",
            self.repo.validate(),
        )

    def test_quarantine_successor_must_be_unique(self) -> None:
        lineage = self._prepare_rewritten_lineage()
        self._commit_quarantine_successors(lineage, count=2)
        self.assertIn(
            "QUARANTINE_REPLACEMENT_SUCCESSOR_AMBIGUOUS:quarantine-replacement",
            self.repo.validate(),
        )

    def test_quarantine_successor_must_be_a_root(self) -> None:
        lineage = self._prepare_rewritten_lineage()
        self._commit_quarantine_successors(lineage, non_root=True)
        self.assertIn(
            "QUARANTINE_REPLACEMENT_ROOT:quarantine-successor:lineage",
            self.repo.validate(),
        )

    def test_quarantine_successor_must_cover_every_sensitive_path(self) -> None:
        lineage = self._prepare_rewritten_lineage()
        self._commit_quarantine_successors(lineage, include_target=False)
        errors = self.repo.validate()
        self.assertIn(f"UNCOVERED:{lineage['target']}", errors)
        self.assertIn(
            f"QUARANTINE_REPLACEMENT_COVERAGE:quarantine-successor:{lineage['target']}",
            errors,
        )

    def test_quarantine_successor_must_hash_bind_historical_replacement(self) -> None:
        lineage = self._prepare_rewritten_lineage()
        _, replacement_path, _ = self._commit_quarantine_successors(
            lineage, wrong_replacement_hash=True
        )
        self.assertIn(
            f"HASH_MISMATCH:quarantine-successor:{replacement_path}",
            self.repo.validate(),
        )

    def test_historical_stack_does_not_authorize_the_final_diff(self) -> None:
        target = "apps/api/app/modules/generation/prompts.py"
        self.repo.write(target, "PROMPT = 'reviewed-slice'\n")
        historical = self.repo.dossier(path=target)
        historical.update({"change_id": "historical", "lineage_id": "historical"})
        historical["evidence"] = [
            self.repo.evidence(path=".ai/evidence/historical.json")
        ]
        self.repo.write_json(".ai/changes/historical.json", historical)
        self.repo.commit("reviewed historical slice")

        self.repo.write(target, "PROMPT = 'unreviewed-tip'\n")
        self.repo.commit("unreviewed final change")

        self.assertIn(f"UNCOVERED:{target}", self.repo.validate())

    def test_stacked_dossier_base_must_be_in_the_reviewed_ancestry(self) -> None:
        target = "apps/api/app/modules/generation/prompts.py"
        self.repo.write(target, "PROMPT = 'candidate'\n")
        dossier = self.repo.dossier(path=target)
        dossier.update({"change_id": "bad-stack", "lineage_id": "bad-stack"})
        dossier["base_sha"] = "f" * 40
        dossier["evidence"] = [self.repo.evidence(path=".ai/evidence/bad-stack.json")]
        self.repo.write_json(".ai/changes/bad-stack.json", dossier)
        self.repo.commit("invalid stacked base")

        errors = self.repo.validate()
        self.assertIn("BASE_SHA:bad-stack:base_sha", errors)

    def test_revision_cannot_fork_a_superseded_parent(self) -> None:
        self._commit_audited_evidence()
        first = self._prepare_second_revision()
        second = copy.deepcopy(first)
        second["change_id"] = "change-r2-fork"
        self.repo.write_json(".ai/changes/change-r2.json", first)
        self.repo.write_json(".ai/changes/change-r2-fork.json", second)
        self.repo.commit("fork immutable lineage")
        self.assertTrue(
            any(error.startswith("LINEAGE_FORK:") for error in self.repo.validate())
        )

    def test_revision_cannot_rewrite_parent_hash_or_lineage(self) -> None:
        self._commit_audited_evidence()
        dossier = self._prepare_second_revision()
        dossier["supersedes"]["sha256"] = "0" * 64
        dossier["lineage_id"] = "different-lineage"
        self.repo.write_json(".ai/changes/change-r2.json", dossier)
        self.repo.commit("rewrite lineage identity")
        errors = self.repo.validate()
        self.assertTrue(any(error.startswith("LINEAGE_HASH:") for error in errors))
        self.assertTrue(any(error.startswith("LINEAGE_STABLE:") for error in errors))

    def test_revision_cannot_downgrade_risk_or_skip_status_transition(self) -> None:
        self._commit_audited_evidence()
        dossier = self._prepare_second_revision()
        dossier["risk_tier"] = "R1"
        dossier["status"] = "expanded"
        self.repo.write_json(".ai/changes/change-r2.json", dossier)
        self.repo.commit("downgrade and skip lifecycle")
        errors = self.repo.validate()
        self.assertTrue(
            any(error.startswith("LINEAGE_RISK_DOWNGRADE:") for error in errors)
        )
        self.assertTrue(
            any(error.startswith("LINEAGE_TRANSITION:") for error in errors)
        )

    def test_existing_evidence_is_append_only(self) -> None:
        report = self._commit_audited_evidence()
        self.repo.write_json(
            report,
            {
                "candidate_sha": "SELF",
                "evidence_label": "fake-provider",
                "result": "fail",
            },
        )
        self.repo.commit("rewrite historical evidence")
        self.assertIn(f"AUDIT_APPEND_ONLY:{report}", self.repo.validate())

    def test_existing_evidence_cannot_be_deleted(self) -> None:
        report = self._commit_audited_evidence()
        (self.repo.root / report).unlink()
        self.repo.commit("delete historical evidence")
        self.assertIn(f"AUDIT_APPEND_ONLY:{report}", self.repo.validate())

    def test_existing_dossier_cannot_be_deleted(self) -> None:
        self._commit_audited_evidence()
        dossier = ".ai/changes/change.json"
        (self.repo.root / dossier).unlink()
        self.repo.commit("delete historical dossier")
        self.assertIn(f"AUDIT_APPEND_ONLY:{dossier}", self.repo.validate())

    def test_new_evidence_must_be_referenced_by_a_new_dossier(self) -> None:
        report = ".ai/evidence/orphan.json"
        self.repo.evidence(path=report)
        self.repo.commit("orphan evidence")
        self.assertIn(f"UNREFERENCED_EVIDENCE:{report}", self.repo.validate())

    def test_schema_cannot_be_reduced_to_a_decorative_shell(self) -> None:
        self.repo.write_json(
            ".ai/schema.json",
            {"type": "object", "required": [], "properties": {}, "$defs": {}},
        )
        dossier = self.repo.dossier(path=".ai/schema.json", risk="R3")
        self.repo.write_json(".ai/changes/change.json", dossier)
        self.repo.commit("weaken published schema")
        self.assertIn("SCHEMA_DIGEST:.ai/schema.json", self.repo.validate())


class AppendOnlyTransitionTests(unittest.TestCase):
    """Aralık içi ekle-sil, sil-yeniden-ekle ve rename ihlallerinin regresyonu.

    Bu sınıf gerçek bir olayın anıtıdır: bir kök dossier bu depoda ekle-sil-ekle
    dizisiyle net diff'ten düşüp doğrulamadan kaçtı ve taşındığı taze yolda
    yeniden yetki kazandı. Geçiş-düzeyi tarama o deliği kapatır; buradaki
    testler birinin taramayı geri sökmesini kırmızıya çevirir.
    """

    def setUp(self) -> None:
        self.repo = RepositoryFixture()

    def tearDown(self) -> None:
        self.repo.close()

    def _ghost(self, path: str = ".ai/changes/ghost.json") -> str:
        self.repo.write("apps/api/app/modules/generation/prompts.py", "PROMPT = 'x'\n")
        dossier = self.repo.dossier(path="apps/api/app/modules/generation/prompts.py")
        dossier.update({"change_id": "ghost", "lineage_id": "ghost-lineage"})
        self.repo.write_json(path, dossier)
        self.repo.commit("introduce ghost dossier")
        return path

    def test_dossier_added_then_deleted_goes_red(self) -> None:
        path = self._ghost()
        (self.repo.root / path).unlink()
        self.repo.commit("delete ghost dossier")

        errors = self.repo.validate()
        self.assertIn(f"AUDIT_HISTORY_REWRITE:{path}", errors)
        self.assertIn(f"AUDIT_APPEND_ONLY:{path}", errors)

    def test_delete_then_readd_goes_red(self) -> None:
        path = self._ghost()
        content = (self.repo.root / path).read_text(encoding="utf-8")
        (self.repo.root / path).unlink()
        self.repo.commit("delete ghost dossier")
        self.repo.write(path, content)
        self.repo.commit("re-add ghost dossier")

        errors = self.repo.validate()
        self.assertIn(f"AUDIT_HISTORY_REWRITE:{path}", errors)

    def test_rename_contaminates_destination(self) -> None:
        source = self._ghost(".ai/changes/moved-source.json")
        dest = ".ai/changes/moved-dest.json"
        (self.repo.root / source).rename(self.repo.root / dest)
        self.repo.commit("launder the root to a fresh path")

        errors = self.repo.validate()
        self.assertIn(f"AUDIT_HISTORY_REWRITE:{source}", errors)
        self.assertIn(f"AUDIT_LINEAGE_CONTAMINATED:{dest}", errors)

    def test_evidence_added_then_deleted_goes_red(self) -> None:
        evidence_path = ".ai/evidence/ghost-report.json"
        self.repo.write_json(evidence_path, {"candidate_sha": "SELF"})
        self.repo.commit("introduce ghost evidence")
        (self.repo.root / evidence_path).unlink()
        self.repo.commit("delete ghost evidence")

        errors = self.repo.validate()
        self.assertIn(f"AUDIT_HISTORY_REWRITE:{evidence_path}", errors)

    def test_quarantine_record_deletion_is_unforgivable(self) -> None:
        quarantine_path = ".ai/quarantine/ghost-quarantine.json"
        self.repo.write_json(quarantine_path, {"quarantine_id": "ghost-quarantine"})
        self.repo.commit("introduce quarantine record")
        (self.repo.root / quarantine_path).unlink()
        self.repo.commit("delete quarantine record")

        errors = self.repo.validate()
        self.assertIn(f"AUDIT_QUARANTINE_REWRITE:{quarantine_path}", errors)

    def test_declared_ghost_clears_the_audit_errors(self) -> None:
        path = self._ghost()
        introduction = self.repo.head
        final_digest = hashlib.sha256((self.repo.root / path).read_bytes()).hexdigest()
        (self.repo.root / path).unlink()
        self.repo.commit("delete ghost dossier")

        self.repo.write_json(
            ".ai/quarantine/ghost.json",
            {
                "schema_version": 1,
                "quarantine_id": "ghost",
                "title": "Quarantine the in-range deleted ghost dossier",
                "owner": "Test Owner",
                "created_at": "2026-08-16T00:00:00+03:00",
                "base_sha": self.repo.base,
                "candidate_sha": "SELF",
                "replacement_dossier": ".ai/changes/replacement.json",
                "records": [
                    {
                        "path": path,
                        "introduced_sha": introduction,
                        "final_blob_sha256": final_digest,
                        "reason": "history-rewritten",
                        "contaminated_by": None,
                    }
                ],
            },
        )
        self.repo.commit("declare ghost quarantine")

        errors = self.repo.validate()
        self.assertNotIn(f"AUDIT_HISTORY_REWRITE:{path}", errors)
        self.assertNotIn(f"QUARANTINE_SCOPE:{path}", errors)
        self.assertNotIn(f"QUARANTINE_INTRODUCTION:{path}", errors)
        self.assertNotIn(f"QUARANTINE_HASH:{path}", errors)


class ProductionPolicyCoverageTests(unittest.TestCase):
    def test_runtime_ai_control_planes_are_classified(self) -> None:
        policy = json.loads(
            (SOURCE_ROOT / ".ai/policy.json").read_text(encoding="utf-8")
        )
        expected = {
            "apps/api/app/api/chat.py": "R3",
            "apps/api/app/modules/policy/service.py": "R3",
            "apps/api/app/schemas/chat.py": "R3",
            "apps/api/app/contracts.py": "R3",
            "apps/api/app/modules/ingestion/pipeline.py": "R3",
            "apps/api/app/modules/assessment/blueprint.py": "R3",
            "apps/api/app/modules/assessment/question_gen.py": "R3",
            "apps/api/app/modules/mastery/service.py": "R3",
            "apps/api/app/core/text_tr.py": "R3",
            "apps/api/app/core/rate_limit.py": "R2",
            "apps/api/app/main.py": "R3",
            "apps/api/Dockerfile": "R3",
            "apps/api/scripts/bake_embedding_model.py": "R3",
            "apps/api/pyproject.toml": "R2",
            "apps/api/uv.lock": "R2",
            "docker-compose.yml": "R2",
            ".env.example": "R2",
            "supabase/migrations/0015_future_ai_change.sql": "R3",
            "supabase/migrations/0003_chat.sql": "R3",
            "supabase/migrations/0004_assessment.sql": "R3",
            "supabase/migrations/0006_embedding_provenance.sql": "R3",
            "supabase/migrations/0008_exam_blueprint.sql": "R3",
            "supabase/migrations/0009_course_ai_policy.sql": "R3",
            "supabase/migrations/0010_ingestion_retry.sql": "R3",
            "supabase/migrations/0013_chat_feedback.sql": "R3",
            "evaluation/gold.json": "R3",
        }
        for path, minimum in expected.items():
            with self.subTest(path=path):
                risk, _ = _risk_for_path(path, policy)
                self.assertEqual(minimum, risk)


class WorkflowBindingTests(unittest.TestCase):
    def test_workflow_binds_self_to_exact_pull_request_head(self) -> None:
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/ai-quality.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("github.event.pull_request.head.sha", workflow)
        self.assertIn("ref: ${{ env.HEAD_SHA }}", workflow)
        self.assertEqual(
            2,
            workflow.count('test "$(git rev-parse HEAD)" = "$HEAD_SHA"'),
        )
        self.assertIn('--head-sha "$HEAD_SHA"', workflow)

    def test_workflow_binds_main_push_to_exact_before_and_after_shas(self) -> None:
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/ai-quality.yml").read_text(
            encoding="utf-8"
        )
        self.assertRegex(workflow, r"(?m)^\s+push:\s*$")
        self.assertRegex(workflow, r"(?m)^\s+- main\s*$")
        self.assertIn("|| github.event.before", workflow)
        self.assertIn("|| github.sha", workflow)
        self.assertNotIn("workflow_dispatch", workflow)
        self.assertNotIn("inputs.base_sha", workflow)

    def test_all_actions_are_immutable_and_checkout_drops_credentials(self) -> None:
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/ai-quality.yml").read_text(
            encoding="utf-8"
        )
        action_refs = re.findall(r"^\s*-?\s*uses:\s*([^\s#]+)", workflow, re.MULTILINE)
        self.assertEqual(3, len(action_refs))
        for action_ref in action_refs:
            self.assertRegex(
                action_ref, r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$"
            )
        self.assertEqual(2, workflow.count("persist-credentials: false"))
        self.assertIn(
            "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
            action_refs,
        )
        self.assertIn(
            "astral-sh/setup-uv@d0cc045d04ccac9d8b7881df0226f9e82c39688e",
            action_refs,
        )


if __name__ == "__main__":
    unittest.main()
