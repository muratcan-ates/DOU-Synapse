#!/usr/bin/env python3
"""Deterministic, stdlib-only AI change governance for DOU-Synapse."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import math
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

RISK_TIERS = ("R1", "R2", "R3")
SHA40 = frozenset("0123456789abcdef")
SHA64 = SHA40
ALLOWED_EVIDENCE_LABELS = frozenset(
    {
        "fake-provider",
        "offline-replay",
        "real-provider",
        "staging",
        "canary",
        "production",
        "rollback",
    }
)
ALLOWED_STATUSES = frozenset(
    {
        "draft",
        "evidence-ready",
        "awaiting-approval",
        "canary",
        "expanded",
        "rolled-back",
        "closed",
    }
)
MINIMUM_RISK_REQUIREMENTS = {
    "R1": {
        "required_approval_roles": frozenset({"peer"}),
        "require_independent_approval": True,
        "require_feature_flag": False,
        "require_kill_switch": True,
        "require_sticky_assignment": False,
    },
    "R2": {
        "required_approval_roles": frozenset({"engineering", "course_or_product"}),
        "require_independent_approval": True,
        "require_feature_flag": True,
        "require_kill_switch": True,
        "require_sticky_assignment": True,
    },
    "R3": {
        "required_approval_roles": frozenset(
            {"engineering", "domain", "security_or_privacy"}
        ),
        "require_independent_approval": True,
        "require_feature_flag": True,
        "require_kill_switch": True,
        "require_sticky_assignment": True,
    },
}
BOOTSTRAP_R3_PATHS = frozenset(
    {
        ".ai/policy.json",
        ".ai/schema.json",
        ".ai/README.md",
        "scripts/ai_sdlc_check.py",
        "scripts/test_ai_sdlc_check.py",
        ".github/workflows/ai-quality.yml",
    }
)
CHANGE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
EXPECTED_SCHEMA_SHA256 = (
    "90f5f2e516a51ab4d148ffacb6a322311a3dad9cf6c47a25d20a4d0c8f373606"
)
DOSSIER_FIELDS = frozenset(
    {
        "schema_version",
        "change_id",
        "lineage_id",
        "revision",
        "supersedes",
        "previous_status",
        "governance_record_risk",
        "title",
        "summary",
        "owner",
        "created_at",
        "review_by",
        "base_sha",
        "candidate_sha",
        "risk_tier",
        "status",
        "behavior",
        "data",
        "artifacts",
        "evidence",
        "evaluation",
        "approval_requirements",
        "deployment",
        "rollout",
        "rollback",
        "privacy",
        "promotion",
    }
)
NESTED_FIELDS = {
    "supersedes": frozenset({"path", "sha256"}),
    "behavior": frozenset(
        {
            "provider_revision",
            "model_revision",
            "prompt_revision",
            "tool_schema_revision",
            "guardrail_revision",
            "retrieval_revision",
            "embedding_revision",
            "evaluator_revision",
        }
    ),
    "data": frozenset({"corpus_digest", "eval_set_digest", "privacy_classification"}),
    "artifact": frozenset({"path", "state", "sha256"}),
    "evidence": frozenset(
        {"label", "result", "report_path", "report_sha256", "candidate_sha"}
    ),
    "evaluation": frozenset(
        {
            "calibration_ref",
            "holdout_ref",
            "thresholds_declared_before_scoring",
            "human_anchor_ref",
            "metrics",
            "exact_command",
        }
    ),
    "metric": frozenset(
        {"name", "baseline", "candidate", "operator", "threshold", "sample_size"}
    ),
    "approval": frozenset(
        {
            "role",
            "actor",
            "decision",
            "approval_ref",
            "approved_at",
            "candidate_sha",
            "independent_of_author",
        }
    ),
    "deployment": frozenset(
        {"feature_flag", "flag_state", "candidate_sha", "deployment_id", "environment"}
    ),
    "rollout": frozenset(
        {
            "feature_flag",
            "kill_switch",
            "assignment",
            "initial_exposure",
            "stop_conditions",
            "expand_conditions",
            "active_exam_policy",
        }
    ),
    "rollback": frozenset(
        {
            "previous_compatible_artifact",
            "procedure",
            "max_minutes",
            "verification",
            "state",
            "evidence_report_path",
            "evidence_report_sha256",
            "evidence_candidate_sha",
            "evidence_deployment_id",
        }
    ),
    "privacy": frozenset(
        {"contains_identifiable_student_content", "handling", "retention"}
    ),
    "promotion": frozenset({"claim", "target", "human_approval_refs"}),
}
AUDIT_DOSSIER_PREFIX = ".ai/changes/"
AUDIT_EVIDENCE_PREFIX = ".ai/evidence/"
AUDIT_QUARANTINE_PREFIX = ".ai/quarantine/"
QUARANTINE_FIELDS = frozenset(
    {
        "schema_version",
        "quarantine_id",
        "title",
        "owner",
        "created_at",
        "base_sha",
        "candidate_sha",
        "replacement_dossier",
        "records",
    }
)
QUARANTINE_RECORD_FIELDS = frozenset(
    {
        "path",
        "introduced_sha",
        "final_blob_sha256",
        "reason",
        "contaminated_by",
    }
)
EXTERNAL_EVIDENCE_LABELS = frozenset(
    {"real-provider", "staging", "canary", "production"}
)
ALLOWED_TRANSITIONS = {
    "draft": frozenset({"draft", "evidence-ready", "rolled-back"}),
    "evidence-ready": frozenset({"evidence-ready", "awaiting-approval", "rolled-back"}),
    "awaiting-approval": frozenset({"awaiting-approval", "canary", "rolled-back"}),
    "canary": frozenset({"canary", "expanded", "rolled-back"}),
    "expanded": frozenset({"expanded", "closed", "rolled-back"}),
    "rolled-back": frozenset({"rolled-back", "closed"}),
    "closed": frozenset({"closed"}),
}
EXTERNAL_RUN_URL_PATTERN = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/[1-9][0-9]*"
    r"(?:/attempts/[1-9][0-9]*)?$"
)
EXTERNAL_APPROVAL_REF_PATTERN = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/[1-9][0-9]*"
    r"#pullrequestreview-[1-9][0-9]*$"
)


@dataclass(frozen=True)
class ChangedPath:
    path: str
    state: str
    related_path: str | None = None
    kind: str = "modified"


class ValidationFailure(RuntimeError):
    """A repository or policy precondition prevented deterministic validation."""


def _git(repo: Path, *args: str, text: bool = True) -> str | bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=text,
    )
    if completed.returncode != 0:
        raise ValidationFailure(f"GIT_COMMAND_FAILED:{args[0] if args else 'git'}")
    return completed.stdout


def _resolve_commit(repo: Path, reference: str) -> str:
    value = str(_git(repo, "rev-parse", "--verify", f"{reference}^{{commit}}"))
    return value.strip()


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    """Return whether both immutable commits belong to the same reviewed chain."""

    completed = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, descendant],
        check=False,
        capture_output=True,
    )
    if completed.returncode not in {0, 1}:
        raise ValidationFailure("GIT_COMMAND_FAILED:merge-base")
    return completed.returncode == 0


def _introduction_commit(
    repo: Path, merge_base: str, head: str, path: str
) -> str | None:
    """Find the sole commit that introduced an append-only audit record.

    A stacked feature branch may contain immutable dossiers for earlier review
    slices.  ``SELF`` in such a record is bound to the commit that first added
    the record, never to a later branch tip.  Re-additions or ambiguous history
    fail closed because there must be exactly one introduction commit in the
    reviewed ancestry.
    """

    raw = str(
        _git(
            repo,
            "log",
            "--format=%H",
            "--diff-filter=A",
            "--reverse",
            f"{merge_base}..{head}",
            "--",
            path,
        )
    )
    commits = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(commits) != 1:
        return None
    return commits[0]


def _path_touch_commits(repo: Path, merge_base: str, head: str, path: str) -> list[str]:
    """Return commits that changed an audit path inside the reviewed history."""

    raw = str(
        _git(
            repo,
            "log",
            "--format=%H",
            "--reverse",
            f"{merge_base}..{head}",
            "--",
            path,
        )
    )
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _is_sha(value: Any, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in SHA40 for character in value)
    )


def _safe_relative_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if "\\" in value or any(
        ord(character) < 32 or ord(character) == 127 for character in value
    ):
        return None
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or ".." in candidate.parts or value.startswith("./"):
        return None
    return candidate.as_posix()


def _json_from_commit(repo: Path, commit: str, path: str) -> dict[str, Any]:
    raw = _blob(repo, commit, path)
    if raw is None:
        raise ValidationFailure(f"MISSING_JSON:{path}")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationFailure(f"INVALID_JSON:{path}") from exc
    if not isinstance(parsed, dict):
        raise ValidationFailure(f"INVALID_JSON_ROOT:{path}")
    return parsed


def _blob(repo: Path, commit: str, path: str) -> bytes | None:
    completed = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "blob", f"{commit}:{path}"],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout


def _tree_paths(repo: Path, commit: str, pattern: str) -> list[str]:
    raw = bytes(_git(repo, "ls-tree", "-rz", "--name-only", commit, text=False))
    try:
        paths = raw.decode("utf-8").split("\0")
    except UnicodeDecodeError as exc:
        raise ValidationFailure("INVALID_GIT_PATH_ENCODING") from exc
    selected: list[str] = []
    for path in paths:
        if not path:
            continue
        if _safe_relative_path(path) is None:
            raise ValidationFailure("INVALID_GIT_PATH")
        if fnmatch.fnmatchcase(path, pattern):
            selected.append(path)
    return sorted(selected)


def _reviewed_changes(repo: Path, merge_base: str, head: str) -> list[ChangedPath]:
    raw = bytes(
        _git(
            repo,
            "diff",
            "--name-status",
            "-z",
            "--find-renames",
            merge_base,
            head,
            text=False,
        )
    )
    try:
        tokens = raw.decode("utf-8").split("\0")
    except UnicodeDecodeError as exc:
        raise ValidationFailure("INVALID_GIT_PATH_ENCODING") from exc
    if tokens and tokens[-1] == "":
        tokens.pop()
    changes: list[ChangedPath] = []
    index = 0
    while index < len(tokens):
        status = tokens[index]
        index += 1
        if status.startswith(("R", "C")):
            if index + 1 >= len(tokens):
                raise ValidationFailure("INVALID_GIT_DIFF")
            old_path, new_path = tokens[index], tokens[index + 1]
            index += 2
            if (
                _safe_relative_path(old_path) is None
                or _safe_relative_path(new_path) is None
            ):
                raise ValidationFailure("INVALID_GIT_PATH")
            if status.startswith("R"):
                changes.extend(
                    [
                        ChangedPath(old_path, "deleted", new_path, "renamed"),
                        ChangedPath(new_path, "present", old_path, "renamed"),
                    ]
                )
            else:
                changes.append(ChangedPath(new_path, "present", old_path, "copied"))
            continue
        if index >= len(tokens):
            raise ValidationFailure("INVALID_GIT_DIFF")
        path = tokens[index]
        index += 1
        if _safe_relative_path(path) is None:
            raise ValidationFailure("INVALID_GIT_PATH")
        state = "deleted" if status.startswith("D") else "present"
        kind = {
            "A": "added",
            "D": "deleted",
            "M": "modified",
            "T": "modified",
        }.get(status[:1], "modified")
        changes.append(ChangedPath(path, state, kind=kind))
    return changes


def _policy_errors(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_version",
        "dossier_schema",
        "dossier_glob",
        "risk_order",
        "allowed_evidence_labels",
        "allowed_statuses",
        "risk_requirements",
        "privacy",
        "production_claim",
        "sensitive_paths",
    }
    missing = sorted(required - policy.keys())
    for field in missing:
        errors.append(f"POLICY_REQUIRED:{field}")
    if policy.get("schema_version") != 1:
        errors.append("POLICY_VERSION:schema_version")
    risk_order = policy.get("risk_order")
    if risk_order != {"R1": 1, "R2": 2, "R3": 3}:
        errors.append("POLICY_RISK_ORDER:risk_order")
    for field in ("dossier_schema", "dossier_glob"):
        if _safe_relative_path(policy.get(field)) is None:
            errors.append(f"POLICY_PATH:{field}")
    labels = policy.get("allowed_evidence_labels")
    if (
        not isinstance(labels, list)
        or not all(isinstance(label, str) for label in labels)
        or set(labels) != ALLOWED_EVIDENCE_LABELS
        or len(labels) != len(set(labels))
    ):
        errors.append("POLICY_EVIDENCE_LABELS:allowed_evidence_labels")
    statuses = policy.get("allowed_statuses")
    if (
        not isinstance(statuses, list)
        or not all(isinstance(status, str) for status in statuses)
        or set(statuses) != ALLOWED_STATUSES
        or len(statuses) != len(set(statuses))
    ):
        errors.append("POLICY_STATUSES:allowed_statuses")
    rules = policy.get("sensitive_paths")
    if not isinstance(rules, list) or not rules:
        errors.append("POLICY_RULES:sensitive_paths")
    else:
        for index, rule in enumerate(rules):
            if not isinstance(rule, dict):
                errors.append(f"POLICY_RULE:{index}")
                continue
            if _safe_relative_path(rule.get("pattern")) is None:
                errors.append(f"POLICY_RULE_PATTERN:{index}")
            if rule.get("minimum_risk") not in RISK_TIERS:
                errors.append(f"POLICY_RULE_RISK:{index}")
    requirements = policy.get("risk_requirements")
    if not isinstance(requirements, dict):
        errors.append("POLICY_RISK_REQUIREMENTS:risk_requirements")
    else:
        for tier in RISK_TIERS:
            requirement = requirements.get(tier)
            if not isinstance(requirement, dict):
                errors.append(f"POLICY_RISK_REQUIREMENT:{tier}")
                continue
            roles = requirement.get("required_approval_roles")
            minimum = MINIMUM_RISK_REQUIREMENTS[tier]
            if (
                not isinstance(roles, list)
                or not all(isinstance(role, str) for role in roles)
                or not minimum["required_approval_roles"].issubset(set(roles))
            ):
                errors.append(f"POLICY_APPROVAL_ROLES:{tier}")
            for field in (
                "require_independent_approval",
                "require_kill_switch",
            ):
                if minimum[field] and requirement.get(field) is not True:
                    errors.append(f"POLICY_MINIMUM:{tier}:{field}")
            for field in ("require_feature_flag", "require_sticky_assignment"):
                if minimum[field] and requirement.get(field) is not True:
                    errors.append(f"POLICY_MINIMUM:{tier}:{field}")
    privacy = policy.get("privacy")
    if (
        not isinstance(privacy, dict)
        or privacy.get("allow_identifiable_student_content") is not False
    ):
        errors.append("POLICY_PRIVACY:allow_identifiable_student_content")
    production = policy.get("production_claim")
    if not isinstance(production, dict):
        errors.append("POLICY_PRODUCTION:production_claim")
    else:
        required_labels = production.get("required_passing_labels")
        environment_labels = production.get("required_environment_labels_any_of")
        minimum_humans = production.get("minimum_named_human_approval_refs")
        if (
            not isinstance(required_labels, list)
            or not all(isinstance(label, str) for label in required_labels)
            or "real-provider" not in required_labels
        ):
            errors.append("POLICY_PRODUCTION:required_passing_labels")
        if (
            not isinstance(environment_labels, list)
            or not all(isinstance(label, str) for label in environment_labels)
            or not ({"staging", "canary", "production"} & set(environment_labels))
        ):
            errors.append("POLICY_PRODUCTION:required_environment_labels_any_of")
        if (
            not isinstance(minimum_humans, int)
            or isinstance(minimum_humans, bool)
            or minimum_humans < 2
        ):
            errors.append("POLICY_PRODUCTION:minimum_named_human_approval_refs")
    return errors


def _schema_errors(schema: dict[str, Any], raw_schema: bytes) -> list[str]:
    errors: list[str] = []
    if hashlib.sha256(raw_schema).hexdigest() != EXPECTED_SCHEMA_SHA256:
        errors.append("SCHEMA_DIGEST:.ai/schema.json")
    if schema.get("type") != "object":
        errors.append("SCHEMA_ROOT:type")
    required = schema.get("required")
    if not isinstance(required, list) or set(required) != DOSSIER_FIELDS:
        errors.append("SCHEMA_REQUIRED:required")
    properties = schema.get("properties")
    if not isinstance(properties, dict) or set(properties) != DOSSIER_FIELDS:
        errors.append("SCHEMA_PROPERTIES:properties")
    if schema.get("additionalProperties") is not False:
        errors.append("SCHEMA_ADDITIONAL:root")
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict):
        errors.append("SCHEMA_DEFS:$defs")
    else:
        for name, expected in NESTED_FIELDS.items():
            definition = definitions.get(name)
            if not isinstance(definition, dict):
                errors.append(f"SCHEMA_DEF:{name}")
                continue
            if definition.get("additionalProperties") is not False:
                errors.append(f"SCHEMA_ADDITIONAL:{name}")
            if set(definition.get("required", [])) != expected:
                errors.append(f"SCHEMA_REQUIRED:{name}")
            nested_properties = definition.get("properties")
            if (
                not isinstance(nested_properties, dict)
                or set(nested_properties) != expected
            ):
                errors.append(f"SCHEMA_PROPERTIES:{name}")
    return errors


def _shape_errors(
    value: dict[str, Any], expected: frozenset[str], prefix: str
) -> list[str]:
    errors: list[str] = []
    for field in sorted(expected - value.keys()):
        errors.append(f"SHAPE_REQUIRED:{prefix}{field}")
    for field in sorted(value.keys() - expected):
        errors.append(f"SHAPE_UNKNOWN:{prefix}{field}")
    return errors


def _is_dossier_path(path: str) -> bool:
    return path.startswith(AUDIT_DOSSIER_PREFIX) and path.endswith(".json")


def _is_evidence_path(path: str) -> bool:
    return path.startswith(AUDIT_EVIDENCE_PREFIX) and path.endswith(".json")


def _is_quarantine_path(path: str) -> bool:
    return path.startswith(AUDIT_QUARANTINE_PREFIX) and path.endswith(".json")


def _risk_for_path(
    path: str, policy: dict[str, Any]
) -> tuple[str | None, dict[str, Any]]:
    order = policy["risk_order"]
    matched: list[dict[str, Any]] = [
        rule
        for rule in policy["sensitive_paths"]
        if fnmatch.fnmatchcase(path, rule["pattern"])
    ]
    if path in BOOTSTRAP_R3_PATHS:
        matched.append({"minimum_risk": "R3"})
    if not matched:
        return None, {}
    highest = max(matched, key=lambda item: order[item["minimum_risk"]])
    combined = {
        "requires_evaluation_split": any(
            bool(rule.get("requires_evaluation_split")) for rule in matched
        ),
        "requires_human_anchor": any(
            bool(rule.get("requires_human_anchor")) for rule in matched
        ),
    }
    return highest["minimum_risk"], combined


def _risk_for_change(
    change: ChangedPath, policy: dict[str, Any]
) -> tuple[str | None, dict[str, bool], bool]:
    """Classify renames without allowing a sensitive path to escape policy."""

    own_risk, own_requirements = _risk_for_path(change.path, policy)
    if change.related_path is None:
        return own_risk, own_requirements, False
    related_risk, related_requirements = _risk_for_path(change.related_path, policy)
    if own_risk is None:
        if change.state == "present" and related_risk is not None:
            return related_risk, related_requirements, True
        return None, {}, False
    if related_risk is None:
        return own_risk, own_requirements, False
    order = policy["risk_order"]
    highest = own_risk if order[own_risk] >= order[related_risk] else related_risk
    combined = {
        key: bool(own_requirements.get(key)) or bool(related_requirements.get(key))
        for key in ("requires_evaluation_split", "requires_human_anchor")
    }
    return highest, combined, False


def _is_runtime_path(path: str) -> bool:
    return path.startswith(
        (
            "apps/api/app/",
            "apps/web/app/",
            "apps/web/components/",
            "apps/web/lib/",
        )
    )


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _parse_datetime(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _safe_dossier_id(value: Any, fallback: str) -> str:
    if isinstance(value, str) and CHANGE_ID_PATTERN.fullmatch(value):
        return value
    digest = hashlib.sha256(str(value).encode("utf-8", errors="replace")).hexdigest()[
        :12
    ]
    return f"invalid-{digest}-{fallback}"


def _identity_matches(value: Any, head: str) -> bool:
    return value == "SELF" or value == head


def _validate_dossier(
    *,
    repo: Path,
    path: str,
    dossier: dict[str, Any],
    policy: dict[str, Any],
    merge_base: str,
    head: str,
    required_risk: str,
    requirements: dict[str, bool],
) -> list[str]:
    errors: list[str] = []
    dossier_id = dossier.get("change_id")
    safe_id = _safe_dossier_id(dossier_id, Path(path).stem)
    prefix = f"{safe_id}:"
    errors.extend(_shape_errors(dossier, DOSSIER_FIELDS, prefix))
    if dossier.get("schema_version") != 1:
        errors.append(f"DOSSIER_VERSION:{prefix}schema_version")
    if not isinstance(dossier_id, str) or not CHANGE_ID_PATTERN.fullmatch(dossier_id):
        errors.append(f"DOSSIER_ID_FORMAT:{prefix}change_id")
    if dossier_id != Path(path).stem:
        errors.append(f"DOSSIER_ID:{prefix}change_id")
    lineage_id = dossier.get("lineage_id")
    if not isinstance(lineage_id, str) or not CHANGE_ID_PATTERN.fullmatch(lineage_id):
        errors.append(f"LINEAGE_ID:{prefix}lineage_id")
    revision = dossier.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        errors.append(f"LINEAGE_REVISION:{prefix}revision")
    supersedes = dossier.get("supersedes")
    if supersedes is not None:
        if not isinstance(supersedes, dict):
            errors.append(f"LINEAGE_SUPERSEDES:{prefix}supersedes")
        else:
            errors.extend(
                _shape_errors(
                    supersedes, NESTED_FIELDS["supersedes"], f"{prefix}supersedes:"
                )
            )
            if _safe_relative_path(supersedes.get("path")) is None or not _is_sha(
                supersedes.get("sha256"), 64
            ):
                errors.append(f"LINEAGE_SUPERSEDES:{prefix}supersedes")
    previous_status = dossier.get("previous_status")
    if previous_status is not None and previous_status not in ALLOWED_STATUSES:
        errors.append(f"LINEAGE_PREVIOUS_STATUS:{prefix}previous_status")
    if dossier.get("governance_record_risk") != "R3":
        errors.append(f"AUDIT_RISK:{prefix}governance_record_risk")
    for field in ("title", "summary", "owner"):
        if not _is_nonempty_string(dossier.get(field)):
            errors.append(f"DOSSIER_FIELD:{prefix}{field}")
    for field in ("created_at", "review_by"):
        if not _parse_datetime(dossier.get(field)):
            errors.append(f"DOSSIER_DATE:{prefix}{field}")
    if dossier.get("base_sha") != merge_base:
        errors.append(f"BASE_SHA:{prefix}base_sha")
    if not _identity_matches(dossier.get("candidate_sha"), head):
        errors.append(f"CANDIDATE_SHA:{prefix}candidate_sha")
    risk_tier = dossier.get("risk_tier")
    if risk_tier not in RISK_TIERS:
        errors.append(f"RISK:{prefix}risk_tier")
        risk_tier = "R1"
    if policy["risk_order"].get(risk_tier, 0) < policy["risk_order"][required_risk]:
        errors.append(f"RISK:{prefix}minimum_{required_risk}")
    status = dossier.get("status")
    status_is_valid = isinstance(status, str) and status in ALLOWED_STATUSES
    if not status_is_valid:
        errors.append(f"STATUS:{prefix}status")

    behavior = dossier.get("behavior")
    if not isinstance(behavior, dict):
        errors.append(f"BEHAVIOR:{prefix}behavior")
    else:
        errors.extend(_shape_errors(behavior, NESTED_FIELDS["behavior"], prefix))
        for field in NESTED_FIELDS["behavior"]:
            if not _is_nonempty_string(behavior.get(field)):
                errors.append(f"BEHAVIOR_REVISION:{prefix}{field}")

    data = dossier.get("data")
    if not isinstance(data, dict):
        errors.append(f"DATA:{prefix}data")
    else:
        errors.extend(_shape_errors(data, NESTED_FIELDS["data"], prefix))
        for field in ("corpus_digest", "eval_set_digest"):
            if not _is_sha(data.get(field), 64):
                errors.append(f"DATA_DIGEST:{prefix}{field}")
        if data.get("privacy_classification") not in {
            "synthetic-non-personal",
            "deidentified-educational",
            "restricted-educational",
        }:
            errors.append(f"DATA_PRIVACY:{prefix}privacy_classification")

    artifacts = dossier.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append(f"ARTIFACTS:{prefix}artifacts")
        artifacts = []
    seen_artifacts: set[str] = set()
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            errors.append(f"ARTIFACT:{prefix}{index}")
            continue
        errors.extend(
            _shape_errors(artifact, NESTED_FIELDS["artifact"], f"{prefix}{index}:")
        )
        artifact_path = _safe_relative_path(artifact.get("path"))
        state = artifact.get("state")
        digest = artifact.get("sha256")
        if artifact_path is None or artifact_path in seen_artifacts:
            errors.append(f"ARTIFACT_PATH:{prefix}{index}")
            continue
        seen_artifacts.add(artifact_path)
        content = _blob(repo, head, artifact_path)
        if state == "present":
            if content is None:
                errors.append(f"ARTIFACT_MISSING:{prefix}{artifact_path}")
            elif (
                not _is_sha(digest, 64) or hashlib.sha256(content).hexdigest() != digest
            ):
                errors.append(f"HASH_MISMATCH:{prefix}{artifact_path}")
        elif state == "deleted":
            if digest is not None or content is not None:
                errors.append(f"DELETION_STATE:{prefix}{artifact_path}")
        else:
            errors.append(f"ARTIFACT_STATE:{prefix}{artifact_path}")

    evidence = dossier.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append(f"EVIDENCE:{prefix}evidence")
        evidence = []
    passing_labels: set[str] = set()
    passing_evidence: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            errors.append(f"EVIDENCE:{prefix}{index}")
            continue
        errors.extend(
            _shape_errors(item, NESTED_FIELDS["evidence"], f"{prefix}{index}:")
        )
        item_valid = True
        label = item.get("label")
        if label not in policy["allowed_evidence_labels"]:
            errors.append(f"EVIDENCE_LABEL:{prefix}{index}")
            item_valid = False
        result = item.get("result")
        if not isinstance(result, str) or result not in {
            "pass",
            "fail",
            "blocked",
            "not-run",
        }:
            errors.append(f"EVIDENCE_RESULT:{prefix}{index}")
            item_valid = False
        report_path = _safe_relative_path(item.get("report_path"))
        report_content = None if report_path is None else _blob(repo, head, report_path)
        if report_path is None or report_content is None:
            errors.append(f"EVIDENCE_REF:{prefix}{index}")
            item_valid = False
        report_digest = item.get("report_sha256")
        if (
            report_content is None
            or not _is_sha(report_digest, 64)
            or hashlib.sha256(report_content).hexdigest() != report_digest
        ):
            errors.append(f"EVIDENCE_HASH:{prefix}{index}")
            item_valid = False
        report: dict[str, Any] | None = None
        if report_content is not None:
            try:
                parsed_report = json.loads(report_content.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                parsed_report = None
            if isinstance(parsed_report, dict):
                report = parsed_report
            else:
                errors.append(f"EVIDENCE_REPORT:{prefix}{index}")
                item_valid = False
        if report is not None:
            if not _identity_matches(report.get("candidate_sha"), head):
                errors.append(f"EVIDENCE_REPORT_SHA:{prefix}{index}")
                item_valid = False
            if report.get("evidence_label") != label:
                errors.append(f"EVIDENCE_REPORT_LABEL:{prefix}{index}")
                item_valid = False
            if report.get("result") != result:
                errors.append(f"EVIDENCE_REPORT_RESULT:{prefix}{index}")
                item_valid = False
            if result == "pass" and label in EXTERNAL_EVIDENCE_LABELS:
                verification_url = report.get("verification_url")
                if not isinstance(
                    verification_url, str
                ) or not EXTERNAL_RUN_URL_PATTERN.fullmatch(verification_url):
                    errors.append(f"EVIDENCE_EXTERNAL_VERIFICATION:{prefix}{index}")
                    item_valid = False
        if not _identity_matches(item.get("candidate_sha"), head):
            errors.append(f"EVIDENCE_SHA:{prefix}{index}")
            item_valid = False
        if (
            item_valid
            and result == "pass"
            and isinstance(label, str)
            and report is not None
        ):
            passing_labels.add(label)
            passing_evidence[label] = (item, report)
    if (
        status_is_valid
        and status in {"evidence-ready", "awaiting-approval"}
        and not passing_labels
    ):
        errors.append(f"STATUS_EVIDENCE:{prefix}{status}")
    if (
        status_is_valid
        and status == "canary"
        and not {"real-provider", "canary"}.issubset(passing_labels)
    ):
        errors.append(f"STATUS_EVIDENCE:{prefix}canary")
    if (
        status_is_valid
        and status == "expanded"
        and not ({"real-provider", "production"}.issubset(passing_labels))
    ):
        errors.append(f"STATUS_EVIDENCE:{prefix}expanded")
    if status_is_valid and status == "rolled-back" and "rollback" not in passing_labels:
        errors.append(f"STATUS_EVIDENCE:{prefix}rolled-back")

    evaluation = dossier.get("evaluation")
    if not isinstance(evaluation, dict):
        errors.append(f"EVALUATION:{prefix}evaluation")
        evaluation = {}
    else:
        errors.extend(_shape_errors(evaluation, NESTED_FIELDS["evaluation"], prefix))
    for field in ("calibration_ref", "holdout_ref", "human_anchor_ref"):
        if not _is_nonempty_string(evaluation.get(field)):
            errors.append(f"EVALUATION_REF:{prefix}{field}")
    if not _is_nonempty_string(evaluation.get("exact_command")):
        errors.append(f"EVALUATION_COMMAND:{prefix}exact_command")
    metrics = evaluation.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        errors.append(f"EVALUATION_METRICS:{prefix}metrics")
        metrics = []
    seen_metrics: set[str] = set()
    for index, metric in enumerate(metrics):
        if not isinstance(metric, dict):
            errors.append(f"EVALUATION_METRIC:{prefix}{index}")
            continue
        errors.extend(
            _shape_errors(metric, NESTED_FIELDS["metric"], f"{prefix}{index}:")
        )
        name = metric.get("name")
        if not _is_nonempty_string(name) or name in seen_metrics:
            errors.append(f"EVALUATION_METRIC_NAME:{prefix}{index}")
        elif isinstance(name, str):
            seen_metrics.add(name)
        for field in ("baseline", "candidate", "threshold"):
            if not _is_finite_number(metric.get(field)):
                errors.append(f"EVALUATION_METRIC_VALUE:{prefix}{index}:{field}")
        if metric.get("operator") not in {">=", "<=", ">", "<", "=="}:
            errors.append(f"EVALUATION_METRIC_OPERATOR:{prefix}{index}")
        sample_size = metric.get("sample_size")
        if (
            not isinstance(sample_size, int)
            or isinstance(sample_size, bool)
            or sample_size < 1
        ):
            errors.append(f"EVALUATION_SAMPLE_SIZE:{prefix}{index}")
    if evaluation.get("thresholds_declared_before_scoring") is not True:
        errors.append(
            f"EVALUATION_THRESHOLD:{prefix}thresholds_declared_before_scoring"
        )
    if requirements.get("requires_evaluation_split"):
        if evaluation.get("calibration_ref") == evaluation.get("holdout_ref"):
            errors.append(f"EVALUATION_SPLIT:{prefix}calibration_holdout")
        for field in ("calibration_ref", "holdout_ref"):
            reference = _safe_relative_path(evaluation.get(field))
            if reference is None or _blob(repo, head, reference) is None:
                errors.append(f"EVALUATION_REF:{prefix}{field}")
    if requirements.get("requires_human_anchor"):
        human_anchor = _safe_relative_path(evaluation.get("human_anchor_ref"))
        if human_anchor is None or _blob(repo, head, human_anchor) is None:
            errors.append(f"HUMAN_ANCHOR:{prefix}human_anchor_ref")

    approvals = dossier.get("approval_requirements")
    if not isinstance(approvals, list):
        errors.append(f"APPROVALS:{prefix}approval_requirements")
        approvals = []
    approvals_by_role: dict[str, dict[str, Any]] = {}
    approved_refs: set[str] = set()
    for index, approval in enumerate(approvals):
        if not isinstance(approval, dict) or not _is_nonempty_string(
            approval.get("role")
        ):
            errors.append(f"APPROVAL:{prefix}{index}")
            continue
        errors.extend(
            _shape_errors(approval, NESTED_FIELDS["approval"], f"{prefix}{index}:")
        )
        approvals_by_role[approval["role"]] = approval
        actor = approval.get("actor")
        if not _is_nonempty_string(actor):
            errors.append(f"APPROVAL_ACTOR:{prefix}{index}")
        if not _identity_matches(approval.get("candidate_sha"), head):
            errors.append(f"APPROVAL_SHA:{prefix}{index}")
        decision = approval.get("decision")
        approval_ref = approval.get("approval_ref")
        approved_at = approval.get("approved_at")
        if decision == "pending":
            if approval_ref is not None or approved_at is not None:
                errors.append(f"APPROVAL_PENDING:{prefix}{index}")
        elif decision in {"approved", "rejected"}:
            if not isinstance(
                approval_ref, str
            ) or not EXTERNAL_APPROVAL_REF_PATTERN.fullmatch(approval_ref):
                errors.append(f"APPROVAL_REF:{prefix}{index}")
            elif decision == "approved":
                approved_refs.add(approval_ref)
            if not _parse_datetime(approved_at):
                errors.append(f"APPROVAL_TIME:{prefix}{index}")
        else:
            errors.append(f"APPROVAL_DECISION:{prefix}{index}")
    tier_requirement = policy["risk_requirements"].get(risk_tier, {})
    for role in tier_requirement.get("required_approval_roles", []):
        approval = approvals_by_role.get(role)
        if approval is None:
            errors.append(f"APPROVAL_ROLE:{prefix}{role}")
            continue
        if tier_requirement.get("require_independent_approval") and (
            approval.get("independent_of_author") is not True
            or approval.get("actor") == dossier.get("owner")
        ):
            errors.append(f"APPROVAL_INDEPENDENCE:{prefix}{role}")
        if (
            status_is_valid
            and status in {"canary", "expanded"}
            and approval.get("decision") != "approved"
        ):
            errors.append(f"APPROVAL_REQUIRED:{prefix}{role}")

    deployment = dossier.get("deployment")
    if not isinstance(deployment, dict):
        errors.append(f"DEPLOYMENT:{prefix}deployment")
        deployment = {}
    else:
        errors.extend(_shape_errors(deployment, NESTED_FIELDS["deployment"], prefix))
    if not _is_nonempty_string(deployment.get("feature_flag")):
        errors.append(f"DEPLOYMENT:{prefix}feature_flag")
    if deployment.get("flag_state") not in {
        "disabled",
        "shadow",
        "canary",
        "enabled",
        "not-applicable",
    }:
        errors.append(f"DEPLOYMENT:{prefix}flag_state")
    if not _identity_matches(deployment.get("candidate_sha"), head):
        errors.append(f"DEPLOYMENT_SHA:{prefix}candidate_sha")
    if not _is_nonempty_string(deployment.get("deployment_id")):
        errors.append(f"DEPLOYMENT:{prefix}deployment_id")
    if deployment.get("environment") not in {
        "not-deployed",
        "development",
        "staging",
        "canary",
        "production",
    }:
        errors.append(f"DEPLOYMENT:{prefix}environment")

    rollout = dossier.get("rollout")
    if not isinstance(rollout, dict):
        errors.append(f"ROLLOUT:{prefix}rollout")
        rollout = {}
    else:
        errors.extend(_shape_errors(rollout, NESTED_FIELDS["rollout"], prefix))
    if tier_requirement.get("require_feature_flag") and not _is_nonempty_string(
        rollout.get("feature_flag")
    ):
        errors.append(f"ROLLOUT:{prefix}feature_flag")
    if rollout.get("feature_flag") != deployment.get("feature_flag"):
        errors.append(f"DEPLOYMENT_FLAG:{prefix}feature_flag")
    if tier_requirement.get("require_kill_switch") and not _is_nonempty_string(
        rollout.get("kill_switch")
    ):
        errors.append(f"ROLLOUT:{prefix}kill_switch")
    if tier_requirement.get("require_sticky_assignment"):
        assignment = rollout.get("assignment")
        if not _is_nonempty_string(assignment) or "sticky" not in assignment.lower():
            errors.append(f"ROLLOUT:{prefix}assignment")
    for field in ("initial_exposure", "active_exam_policy"):
        if not _is_nonempty_string(rollout.get(field)):
            errors.append(f"ROLLOUT:{prefix}{field}")
    for field in ("stop_conditions", "expand_conditions"):
        values = rollout.get(field)
        if (
            not isinstance(values, list)
            or not values
            or not all(_is_nonempty_string(value) for value in values)
        ):
            errors.append(f"ROLLOUT:{prefix}{field}")

    rollback = dossier.get("rollback")
    if not isinstance(rollback, dict):
        errors.append(f"ROLLBACK:{prefix}rollback")
        rollback = {}
    else:
        errors.extend(_shape_errors(rollback, NESTED_FIELDS["rollback"], prefix))
    for field in ("previous_compatible_artifact", "procedure", "verification"):
        if not _is_nonempty_string(rollback.get(field)):
            errors.append(f"ROLLBACK:{prefix}{field}")
    max_minutes = rollback.get("max_minutes")
    if (
        not isinstance(max_minutes, int)
        or isinstance(max_minutes, bool)
        or max_minutes < 1
    ):
        errors.append(f"ROLLBACK:{prefix}max_minutes")
    rollback_state = rollback.get("state")
    rollback_ref_fields = (
        "evidence_report_path",
        "evidence_report_sha256",
        "evidence_candidate_sha",
        "evidence_deployment_id",
    )
    if rollback_state == "planned":
        if any(rollback.get(field) is not None for field in rollback_ref_fields):
            errors.append(f"ROLLBACK_PLANNED:{prefix}evidence")
    elif rollback_state in {
        "verified-before-production",
        "verified-after-production",
    }:
        rollback_evidence = passing_evidence.get("rollback")
        if rollback_evidence is None:
            errors.append(f"ROLLBACK_EVIDENCE:{prefix}evidence")
        else:
            rollback_item, rollback_report = rollback_evidence
            if (
                rollback.get("evidence_report_path") != rollback_item.get("report_path")
                or rollback.get("evidence_report_sha256")
                != rollback_item.get("report_sha256")
                or not _identity_matches(rollback.get("evidence_candidate_sha"), head)
                or rollback_report.get("rollback_verified") is not True
                or rollback_report.get("deployment_id")
                != rollback.get("evidence_deployment_id")
                or rollback.get("evidence_deployment_id")
                != deployment.get("deployment_id")
            ):
                errors.append(f"ROLLBACK_BINDING:{prefix}evidence")
    else:
        errors.append(f"ROLLBACK_STATE:{prefix}state")
    if status == "rolled-back" and rollback_state not in {
        "verified-before-production",
        "verified-after-production",
    }:
        errors.append(f"ROLLBACK_STATUS:{prefix}rolled-back")

    privacy = dossier.get("privacy")
    if not isinstance(privacy, dict):
        errors.append(f"PRIVACY:{prefix}privacy")
        privacy = {}
    else:
        errors.extend(_shape_errors(privacy, NESTED_FIELDS["privacy"], prefix))
    if (
        policy.get("privacy", {}).get("allow_identifiable_student_content") is False
        and privacy.get("contains_identifiable_student_content") is not False
    ):
        errors.append(f"PRIVACY:{prefix}identifiable_student_content")
    for field in ("handling", "retention"):
        if not _is_nonempty_string(privacy.get(field)):
            errors.append(f"PRIVACY:{prefix}{field}")

    promotion = dossier.get("promotion")
    if not isinstance(promotion, dict):
        errors.append(f"PROMOTION:{prefix}promotion")
        promotion = {}
    else:
        errors.extend(_shape_errors(promotion, NESTED_FIELDS["promotion"], prefix))
    claim = promotion.get("claim")
    if not isinstance(claim, str) or claim not in {
        "none",
        "development",
        "production-ready",
    }:
        errors.append(f"PROMOTION:{prefix}claim")
    target = promotion.get("target")
    if not isinstance(target, str) or target not in {
        "none",
        "internal",
        "staging",
        "canary",
        "production",
    }:
        errors.append(f"PROMOTION:{prefix}target")
    human_refs = promotion.get("human_approval_refs")
    if not isinstance(human_refs, list) or not all(
        _is_nonempty_string(item) for item in human_refs
    ):
        errors.append(f"PROMOTION:{prefix}human_approval_refs")
        human_refs = []
    if any(reference not in approved_refs for reference in human_refs):
        errors.append(f"PROMOTION_APPROVAL_BINDING:{prefix}human_approval_refs")
    required_roles = set(tier_requirement.get("required_approval_roles", []))
    required_role_refs = {
        approval.get("approval_ref")
        for role in required_roles
        if (approval := approvals_by_role.get(role)) is not None
        and approval.get("decision") == "approved"
        and isinstance(approval.get("approval_ref"), str)
    }
    if (
        status_is_valid
        and status in {"canary", "expanded"}
        and (
            len(required_role_refs) != len(required_roles)
            or not required_role_refs.issubset(set(human_refs))
        )
    ):
        errors.append(f"APPROVAL_PROMOTION:{prefix}{status}")
    if claim == "production-ready":
        production = policy["production_claim"]
        required_labels = set(production["required_passing_labels"])
        environment_labels = set(production["required_environment_labels_any_of"])
        if not required_labels.issubset(passing_labels) or not (
            environment_labels & passing_labels
        ):
            errors.append(f"PRODUCTION_EVIDENCE:{prefix}evidence")
        if len(set(human_refs)) < production["minimum_named_human_approval_refs"]:
            errors.append(f"PRODUCTION_APPROVAL:{prefix}human_approval_refs")
        if any(
            not EXTERNAL_APPROVAL_REF_PATTERN.fullmatch(reference)
            for reference in human_refs
        ):
            errors.append(f"PRODUCTION_APPROVAL_REF:{prefix}human_approval_refs")
        if any(
            approval.get("decision") != "approved"
            for role in tier_requirement.get("required_approval_roles", [])
            if (approval := approvals_by_role.get(role)) is not None
        ):
            errors.append(f"PRODUCTION_APPROVAL_DECISION:{prefix}approval_requirements")

    compatible = {
        "draft": {("none", "none")},
        "evidence-ready": {("none", "none"), ("development", "internal")},
        "awaiting-approval": {
            ("development", "internal"),
            ("development", "staging"),
        },
        "canary": {("development", "canary")},
        "expanded": {("production-ready", "production")},
        "rolled-back": {("none", "none")},
    }
    if (
        status_is_valid
        and status in compatible
        and (claim, target) not in compatible[status]
    ):
        errors.append(f"STATUS_PROMOTION:{prefix}{status}")
    if status == "canary" and (
        deployment.get("environment") != "canary"
        or deployment.get("flag_state") != "canary"
    ):
        errors.append(f"STATUS_DEPLOYMENT:{prefix}canary")
    if status == "expanded" and (
        deployment.get("environment") != "production"
        or deployment.get("flag_state") != "enabled"
    ):
        errors.append(f"STATUS_DEPLOYMENT:{prefix}expanded")
    if status == "rolled-back" and deployment.get("flag_state") != "disabled":
        errors.append(f"STATUS_DEPLOYMENT:{prefix}rolled-back")
    if status == "closed":
        production_closed = (
            claim == "production-ready"
            and target == "production"
            and {"real-provider", "production"}.issubset(passing_labels)
            and len(required_role_refs) == len(required_roles)
            and required_role_refs.issubset(set(human_refs))
            and deployment.get("environment") == "production"
            and deployment.get("flag_state") == "enabled"
        )
        rollback_closed = (
            claim == "none"
            and target == "none"
            and rollback_state == "verified-before-production"
            and "rollback" in passing_labels
            and deployment.get("flag_state") == "disabled"
        )
        if not (production_closed or rollback_closed):
            errors.append(f"STATUS_CLOSED_PATH:{prefix}closed")

    return errors


def _quarantine_errors(
    *,
    repo: Path,
    merge_base: str,
    head: str,
    changed_dossier_paths: set[str],
    changed_quarantine_paths: set[str],
    parsed_dossiers: dict[str, dict[str, Any]],
) -> tuple[list[str], set[str], set[str]]:
    """Validate explicit quarantine for rewritten, therefore untrusted, history.

    A quarantined dossier is never made valid retroactively.  The record only
    names exact contaminated blobs so a new main-to-HEAD root can replace them.
    Rewritten records and every descendant that trusts one must be quarantined;
    a valid record cannot be hidden this way.
    """

    errors: list[str] = []
    rewritten = {
        path
        for path in changed_dossier_paths
        if len(_path_touch_commits(repo, merge_base, head, path)) > 1
    }
    contaminated = set(rewritten)
    contaminated_by: dict[str, str] = {}
    changed = True
    while changed:
        changed = False
        for dossier_path in changed_dossier_paths - contaminated:
            dossier = parsed_dossiers.get(dossier_path, {})
            supersedes = dossier.get("supersedes")
            if not isinstance(supersedes, dict):
                continue
            parent_path = _safe_relative_path(supersedes.get("path"))
            if parent_path in contaminated:
                contaminated.add(dossier_path)
                contaminated_by[dossier_path] = parent_path
                changed = True

    declared: set[str] = set()
    replacement_dossiers: set[str] = set()
    for quarantine_path in sorted(changed_quarantine_paths):
        quarantine = _json_from_commit(repo, head, quarantine_path)
        fallback_id = Path(quarantine_path).stem
        quarantine_id = quarantine.get("quarantine_id")
        safe_id = _safe_dossier_id(quarantine_id, fallback_id)
        prefix = f"{safe_id}:"
        errors.extend(_shape_errors(quarantine, QUARANTINE_FIELDS, prefix))
        if quarantine.get("schema_version") != 1:
            errors.append(f"QUARANTINE_VERSION:{prefix}schema_version")
        if (
            not isinstance(quarantine_id, str)
            or not CHANGE_ID_PATTERN.fullmatch(quarantine_id)
            or quarantine_id != fallback_id
        ):
            errors.append(f"QUARANTINE_ID:{prefix}quarantine_id")
        for field in ("title", "owner"):
            if not _is_nonempty_string(quarantine.get(field)):
                errors.append(f"QUARANTINE_FIELD:{prefix}{field}")
        if not _parse_datetime(quarantine.get("created_at")):
            errors.append(f"QUARANTINE_DATE:{prefix}created_at")
        if quarantine.get("base_sha") != merge_base:
            errors.append(f"QUARANTINE_BASE:{prefix}base_sha")
        if not _identity_matches(quarantine.get("candidate_sha"), head):
            errors.append(f"QUARANTINE_CANDIDATE:{prefix}candidate_sha")
        if len(_path_touch_commits(repo, merge_base, head, quarantine_path)) != 1:
            errors.append(f"AUDIT_APPEND_ONLY:{quarantine_path}")

        replacement = _safe_relative_path(quarantine.get("replacement_dossier"))
        if replacement is None or not _is_dossier_path(replacement):
            errors.append(f"QUARANTINE_REPLACEMENT:{prefix}replacement_dossier")
        else:
            replacement_dossiers.add(replacement)

        records = quarantine.get("records")
        if not isinstance(records, list) or not records:
            errors.append(f"QUARANTINE_RECORDS:{prefix}records")
            records = []
        for index, record in enumerate(records):
            record_prefix = f"{prefix}{index}:"
            if not isinstance(record, dict):
                errors.append(f"QUARANTINE_RECORD:{record_prefix}record")
                continue
            errors.extend(
                _shape_errors(record, QUARANTINE_RECORD_FIELDS, record_prefix)
            )
            dossier_path = _safe_relative_path(record.get("path"))
            if dossier_path is None or not _is_dossier_path(dossier_path):
                errors.append(f"QUARANTINE_PATH:{record_prefix}path")
                continue
            if dossier_path in declared:
                errors.append(f"QUARANTINE_DUPLICATE:{dossier_path}")
            declared.add(dossier_path)
            if dossier_path not in changed_dossier_paths:
                errors.append(f"QUARANTINE_SCOPE:{dossier_path}")
                continue

            introduction = _introduction_commit(repo, merge_base, head, dossier_path)
            if introduction is None or record.get("introduced_sha") != introduction:
                errors.append(f"QUARANTINE_INTRODUCTION:{dossier_path}")
            final_blob = _blob(repo, head, dossier_path)
            final_digest = (
                hashlib.sha256(final_blob).hexdigest()
                if final_blob is not None
                else None
            )
            if (
                not _is_sha(record.get("final_blob_sha256"), 64)
                or record.get("final_blob_sha256") != final_digest
            ):
                errors.append(f"QUARANTINE_HASH:{dossier_path}")

            reason = record.get("reason")
            parent = _safe_relative_path(record.get("contaminated_by"))
            if dossier_path in rewritten:
                if (
                    reason != "history-rewritten"
                    or record.get("contaminated_by") is not None
                ):
                    errors.append(f"QUARANTINE_REASON:{dossier_path}")
            elif dossier_path in contaminated:
                if (
                    reason != "descends-from-quarantined"
                    or parent != contaminated_by.get(dossier_path)
                ):
                    errors.append(f"QUARANTINE_REASON:{dossier_path}")
            else:
                errors.append(f"QUARANTINE_UNJUSTIFIED:{dossier_path}")

    for dossier_path in sorted(contaminated - declared):
        error_class = (
            "AUDIT_HISTORY_REWRITE"
            if dossier_path in rewritten
            else "AUDIT_LINEAGE_CONTAMINATED"
        )
        errors.append(f"{error_class}:{dossier_path}")
        if dossier_path in rewritten:
            errors.append(f"AUDIT_APPEND_ONLY:{dossier_path}")
    for dossier_path in sorted(declared - contaminated):
        errors.append(f"QUARANTINE_UNJUSTIFIED:{dossier_path}")
    # Every rewritten record and every descendant that trusted it is untrusted,
    # even when the quarantine declaration is missing or malformed.  Returning
    # the complete contaminated set prevents a failing candidate from also
    # using the bad record for artifact coverage, evidence references or
    # lifecycle authority.
    return errors, contaminated, replacement_dossiers


def _lifecycle_errors(
    *,
    repo: Path,
    merge_base: str,
    head: str,
    dossier_glob: str,
    parsed_dossiers: dict[str, dict[str, Any]],
    changed_dossier_paths: set[str],
    dossier_contexts: dict[str, tuple[str, str]],
    policy: dict[str, Any],
) -> list[str]:
    """Validate immutable revision chains without trusting the new revision."""

    errors: list[str] = []
    base_dossier_cache: dict[str, dict[str, dict[str, Any]]] = {}

    def dossiers_at(commit: str) -> dict[str, dict[str, Any]]:
        cached = base_dossier_cache.get(commit)
        if cached is not None:
            return cached
        paths = _tree_paths(repo, commit, dossier_glob)
        parsed = {path: _json_from_commit(repo, commit, path) for path in paths}
        base_dossier_cache[commit] = parsed
        return parsed

    children: dict[str, list[str]] = {}
    revisions: dict[tuple[str, int], list[str]] = {}
    for dossier_path, dossier in parsed_dossiers.items():
        lineage_id = dossier.get("lineage_id")
        revision = dossier.get("revision")
        if isinstance(lineage_id, str) and isinstance(revision, int):
            revisions.setdefault((lineage_id, revision), []).append(dossier_path)
        supersedes = dossier.get("supersedes")
        if isinstance(supersedes, dict):
            parent_path = _safe_relative_path(supersedes.get("path"))
            if parent_path is not None:
                children.setdefault(parent_path, []).append(dossier_path)
    for child_paths in children.values():
        if len(child_paths) > 1:
            errors.append(f"LINEAGE_FORK:{child_paths[0]}")
    for revision_paths in revisions.values():
        if len(revision_paths) > 1:
            errors.append(f"LINEAGE_DUPLICATE_REVISION:{revision_paths[0]}")

    for dossier_path in changed_dossier_paths:
        dossier = parsed_dossiers.get(dossier_path)
        if not isinstance(dossier, dict):
            continue
        safe_id = _safe_dossier_id(dossier.get("change_id"), Path(dossier_path).stem)
        prefix = f"{safe_id}:"
        revision = dossier.get("revision")
        supersedes = dossier.get("supersedes")
        previous_status = dossier.get("previous_status")
        context_base, _ = dossier_contexts.get(dossier_path, (merge_base, head))
        base_dossiers = dossiers_at(context_base)
        if supersedes is None:
            if revision != 1 or previous_status is not None:
                errors.append(f"LINEAGE_ROOT:{prefix}revision")
            if any(
                previous.get("lineage_id") == dossier.get("lineage_id")
                for previous in base_dossiers.values()
            ):
                errors.append(f"LINEAGE_FORK:{prefix}lineage_id")
            continue
        if not isinstance(supersedes, dict):
            continue
        previous_path = _safe_relative_path(supersedes.get("path"))
        if previous_path is None:
            continue
        previous_blob = _blob(repo, context_base, previous_path)
        previous = base_dossiers.get(previous_path)
        if previous_blob is None or previous is None:
            errors.append(f"LINEAGE_BASE:{prefix}supersedes")
            continue
        if not _is_sha(supersedes.get("sha256"), 64) or hashlib.sha256(
            previous_blob
        ).hexdigest() != supersedes.get("sha256"):
            errors.append(f"LINEAGE_HASH:{prefix}supersedes")
        if previous.get("lineage_id") != dossier.get("lineage_id"):
            errors.append(f"LINEAGE_STABLE:{prefix}lineage_id")
        previous_revision = previous.get("revision")
        if (
            not isinstance(previous_revision, int)
            or not isinstance(revision, int)
            or revision != previous_revision + 1
        ):
            errors.append(f"LINEAGE_SEQUENCE:{prefix}revision")
        previous_dossier_status = previous.get("status")
        if previous_status != previous_dossier_status:
            errors.append(f"LINEAGE_PREVIOUS_STATUS:{prefix}previous_status")
        previous_risk = previous.get("risk_tier")
        current_risk = dossier.get("risk_tier")
        if (
            previous_risk in RISK_TIERS
            and current_risk in RISK_TIERS
            and policy["risk_order"][current_risk] < policy["risk_order"][previous_risk]
        ):
            errors.append(f"LINEAGE_RISK_DOWNGRADE:{prefix}risk_tier")
        current_status = dossier.get("status")
        if (
            previous_dossier_status in ALLOWED_TRANSITIONS
            and current_status not in ALLOWED_TRANSITIONS[previous_dossier_status]
        ):
            errors.append(f"LINEAGE_TRANSITION:{prefix}status")

    return errors


def validate_repository(
    *,
    repo_root: Path,
    policy_path: str,
    base_sha: str,
    head_sha: str,
) -> list[str]:
    """Return stable, privacy-safe errors for the reviewed candidate."""

    repo = repo_root.resolve()
    errors: list[str] = []
    if not _is_sha(base_sha, 40):
        errors.append("BASE_REF_NOT_IMMUTABLE:base_sha")
    if not _is_sha(head_sha, 40):
        errors.append("HEAD_REF_NOT_IMMUTABLE:head_sha")
    if errors:
        return errors
    try:
        base = _resolve_commit(repo, base_sha)
        head = _resolve_commit(repo, head_sha)
        checkout_head = _resolve_commit(repo, "HEAD")
        if checkout_head != head:
            errors.append("CHECKOUT_SHA:HEAD")
        merge_base = str(_git(repo, "merge-base", base, head)).strip()
        relative_policy = _safe_relative_path(policy_path)
        if relative_policy is None:
            return ["POLICY_PATH:policy"]
        policy = _json_from_commit(repo, head, relative_policy)
        errors.extend(_policy_errors(policy))
        if errors:
            return sorted(set(errors))
        schema_path = _safe_relative_path(policy["dossier_schema"])
        if schema_path is None:
            return ["SCHEMA_PATH:dossier_schema"]
        raw_schema = _blob(repo, head, schema_path)
        if raw_schema is None:
            return ["MISSING_JSON:.ai/schema.json"]
        schema = _json_from_commit(repo, head, schema_path)
        errors.extend(_schema_errors(schema, raw_schema))

        changes = _reviewed_changes(repo, merge_base, head)
        sensitive: dict[str, tuple[ChangedPath, str, dict[str, bool]]] = {}
        added_evidence_paths: set[str] = set()
        for change in changes:
            if _is_dossier_path(change.path) or _is_evidence_path(change.path):
                # A modified dossier can only be acknowledged through the
                # explicit, fail-closed quarantine flow below. Deletions,
                # renames and evidence rewrites remain unconditionally barred.
                if change.kind != "added" and not (
                    _is_dossier_path(change.path) and change.kind == "modified"
                ):
                    errors.append(f"AUDIT_APPEND_ONLY:{change.path}")
                elif _is_evidence_path(change.path):
                    added_evidence_paths.add(change.path)
                # New dossiers validate themselves and new evidence must be
                # hash-bound from such a dossier. Treating either as a normal
                # artifact would require an impossible self-hash for dossiers.
                continue
            if _is_quarantine_path(change.path) and change.kind != "added":
                errors.append(f"AUDIT_APPEND_ONLY:{change.path}")
            risk, requirements, escaped_rename = _risk_for_change(change, policy)
            if escaped_rename:
                errors.append(f"SENSITIVE_RENAME_ESCAPE:{change.path}")
            if risk is not None:
                sensitive[change.path] = (change, risk, requirements)

        deleted_sensitive = [
            item for item in sensitive.values() if item[0].state == "deleted"
        ]
        if deleted_sensitive:
            highest_deleted_risk = max(
                (item[1] for item in deleted_sensitive),
                key=lambda tier: policy["risk_order"][tier],
            )
            inherited_requirements = {
                key: any(bool(item[2].get(key)) for item in deleted_sensitive)
                for key in ("requires_evaluation_split", "requires_human_anchor")
            }
            for change in changes:
                own_risk, _ = _risk_for_path(change.path, policy)
                if (
                    change.state == "present"
                    and change.related_path is None
                    and own_risk is None
                    and _is_runtime_path(change.path)
                ):
                    errors.append(f"SENSITIVE_MOVE_AMBIGUOUS:{change.path}")
                    sensitive[change.path] = (
                        change,
                        highest_deleted_risk,
                        inherited_requirements,
                    )

        dossier_glob = policy["dossier_glob"]
        dossier_paths = _tree_paths(repo, head, dossier_glob)
        changed_dossier_paths = {
            change.path
            for change in changes
            if fnmatch.fnmatchcase(change.path, dossier_glob)
            and change.state == "present"
        }
        changed_quarantine_paths = {
            change.path
            for change in changes
            if _is_quarantine_path(change.path) and change.state == "present"
        }
        parsed_dossiers: dict[str, dict[str, Any]] = {}
        eligible_dossiers: dict[str, dict[str, Any]] = {}
        dossier_contexts: dict[str, tuple[str, str]] = {}
        for dossier_path in dossier_paths:
            dossier = _json_from_commit(repo, head, dossier_path)
            parsed_dossiers[dossier_path] = dossier

        quarantine_errors, untrusted_dossiers, replacement_dossiers = (
            _quarantine_errors(
                repo=repo,
                merge_base=merge_base,
                head=head,
                changed_dossier_paths=changed_dossier_paths,
                changed_quarantine_paths=changed_quarantine_paths,
                parsed_dossiers=parsed_dossiers,
            )
        )
        errors.extend(quarantine_errors)
        trusted_changed_dossiers = changed_dossier_paths - untrusted_dossiers
        trusted_parsed_dossiers = {
            path: dossier
            for path, dossier in parsed_dossiers.items()
            if path not in untrusted_dossiers
        }

        # SELF is permanently bound to the commit that introduced an immutable
        # dossier.  A later child, integration commit or branch tip can never
        # move that snapshot forward.  Rewritten paths were removed from the
        # trusted sets above and can only be replaced by a fresh exact root.
        for dossier_path in trusted_changed_dossiers:
            dossier = parsed_dossiers.get(dossier_path, {})
            dossier_id = _safe_dossier_id(
                dossier.get("change_id"), Path(dossier_path).stem
            )
            introduction = _introduction_commit(repo, merge_base, head, dossier_path)
            context_head = introduction
            context_is_valid = introduction is not None
            declared_base = dossier.get("base_sha")
            candidate = dossier.get("candidate_sha")
            base_is_valid = _is_sha(declared_base, 40)
            if base_is_valid:
                try:
                    base_is_valid = (
                        _resolve_commit(repo, declared_base) == declared_base
                    )
                except ValidationFailure:
                    base_is_valid = False
            if base_is_valid and context_is_valid and context_head is not None:
                base_is_valid = (
                    declared_base != context_head
                    and _is_ancestor(repo, merge_base, declared_base)
                    and introduction is not None
                    and _is_ancestor(repo, declared_base, introduction)
                    and _is_ancestor(repo, introduction, context_head)
                )
            candidate_is_valid = context_is_valid and _identity_matches(
                candidate, context_head
            )
            if context_is_valid and base_is_valid and candidate_is_valid:
                dossier_contexts[dossier_path] = (declared_base, context_head)
            else:
                if not context_is_valid:
                    errors.append(f"STACK_CONTEXT:{dossier_id}:history")
                if not base_is_valid:
                    errors.append(f"BASE_SHA:{dossier_id}:base_sha")
                if context_is_valid and not candidate_is_valid:
                    errors.append(f"CANDIDATE_SHA:{dossier_id}:candidate_sha")

        eligible_dossiers = {
            dossier_path: parsed_dossiers[dossier_path]
            for dossier_path, context in dossier_contexts.items()
            if context == (merge_base, head)
        }

        # A quarantine does not repair history.  It must point to a new exact
        # main-to-HEAD root that, by itself, hash-binds the quarantine record and
        # every sensitive artifact in the reviewed diff.
        for replacement_path in sorted(replacement_dossiers):
            replacement = eligible_dossiers.get(replacement_path)
            replacement_id = Path(replacement_path).stem
            if not isinstance(replacement, dict):
                errors.append(
                    f"QUARANTINE_REPLACEMENT_CONTEXT:{replacement_id}:base-head"
                )
                continue
            if (
                replacement.get("revision") != 1
                or replacement.get("supersedes") is not None
                or replacement.get("previous_status") is not None
            ):
                errors.append(f"QUARANTINE_REPLACEMENT_ROOT:{replacement_id}:lineage")
            replacement_artifacts = replacement.get("artifacts")
            replacement_artifact_paths = (
                {
                    artifact.get("path")
                    for artifact in replacement_artifacts
                    if isinstance(artifact, dict)
                    and isinstance(artifact.get("path"), str)
                }
                if isinstance(replacement_artifacts, list)
                else set()
            )
            for sensitive_path in sorted(sensitive):
                if sensitive_path not in replacement_artifact_paths:
                    errors.append(
                        "QUARANTINE_REPLACEMENT_COVERAGE:"
                        f"{replacement_id}:{sensitive_path}"
                    )

        errors.extend(
            _lifecycle_errors(
                repo=repo,
                merge_base=merge_base,
                head=head,
                dossier_glob=dossier_glob,
                parsed_dossiers=trusted_parsed_dossiers,
                changed_dossier_paths=trusted_changed_dossiers,
                dossier_contexts=dossier_contexts,
                policy=policy,
            )
        )

        evidence_referenced_by_changed_dossiers: set[str] = set()
        for dossier_path in trusted_changed_dossiers:
            dossier_evidence = parsed_dossiers.get(dossier_path, {}).get("evidence")
            if not isinstance(dossier_evidence, list):
                continue
            for item in dossier_evidence:
                if not isinstance(item, dict):
                    continue
                report_path = _safe_relative_path(item.get("report_path"))
                if report_path is not None:
                    evidence_referenced_by_changed_dossiers.add(report_path)
        for evidence_path in sorted(
            added_evidence_paths - evidence_referenced_by_changed_dossiers
        ):
            errors.append(f"UNREFERENCED_EVIDENCE:{evidence_path}")

        # Historical stacked records still validate their own immutable
        # artifact/evidence snapshot.  They never authorize the aggregate
        # current diff; only eligible_dossiers below can do that.
        for dossier_path in sorted(trusted_changed_dossiers - eligible_dossiers.keys()):
            context = dossier_contexts.get(dossier_path)
            dossier = parsed_dossiers.get(dossier_path)
            if context is None or not isinstance(dossier, dict):
                continue
            required_risk = "R1"
            requirements = {
                "requires_evaluation_split": False,
                "requires_human_anchor": False,
            }
            artifacts = dossier.get("artifacts")
            if isinstance(artifacts, list):
                for artifact in artifacts:
                    if not isinstance(artifact, dict):
                        continue
                    artifact_path = _safe_relative_path(artifact.get("path"))
                    if artifact_path is None:
                        continue
                    artifact_risk, artifact_requirements = _risk_for_path(
                        artifact_path, policy
                    )
                    if (
                        artifact_risk is not None
                        and policy["risk_order"][artifact_risk]
                        > policy["risk_order"][required_risk]
                    ):
                        required_risk = artifact_risk
                    for key in requirements:
                        requirements[key] = requirements[key] or bool(
                            artifact_requirements.get(key)
                        )
            context_base, context_head = context
            errors.extend(
                _validate_dossier(
                    repo=repo,
                    path=dossier_path,
                    dossier=dossier,
                    policy=policy,
                    merge_base=context_base,
                    head=context_head,
                    required_risk=required_risk,
                    requirements=requirements,
                )
            )

        coverage: dict[str, list[tuple[str, dict[str, Any]]]] = {
            path: [] for path in sensitive
        }
        for dossier_path, dossier in eligible_dossiers.items():
            artifacts = dossier.get("artifacts")
            if not isinstance(artifacts, list):
                continue
            artifact_paths = {
                artifact.get("path")
                for artifact in artifacts
                if isinstance(artifact, dict) and isinstance(artifact.get("path"), str)
            }
            for changed_path, covering_dossiers in coverage.items():
                if changed_path in artifact_paths:
                    covering_dossiers.append((dossier_path, dossier))

        dossiers_to_validate: dict[
            str, tuple[dict[str, Any], str, dict[str, bool]]
        ] = {}
        for changed_path, covering in coverage.items():
            if not covering:
                errors.append(f"UNCOVERED:{changed_path}")
                continue
            risks = {
                dossier.get("risk_tier")
                if isinstance(dossier.get("risk_tier"), str)
                else "<invalid>"
                for _, dossier in covering
            }
            if len(risks) > 1:
                errors.append(f"RISK_DISAGREEMENT:{changed_path}")
            _, required_risk, requirements = sensitive[changed_path]
            for dossier_path, dossier in covering:
                existing = dossiers_to_validate.get(dossier_path)
                if (
                    existing is None
                    or policy["risk_order"][required_risk]
                    > policy["risk_order"][existing[1]]
                ):
                    combined = {
                        key: bool(requirements.get(key))
                        or bool(existing is not None and existing[2].get(key))
                        for key in (
                            "requires_evaluation_split",
                            "requires_human_anchor",
                        )
                    }
                    dossiers_to_validate[dossier_path] = (
                        dossier,
                        required_risk,
                        combined,
                    )
                elif existing is not None:
                    combined = {
                        key: bool(existing[2].get(key)) or bool(requirements.get(key))
                        for key in (
                            "requires_evaluation_split",
                            "requires_human_anchor",
                        )
                    }
                    dossiers_to_validate[dossier_path] = (
                        existing[0],
                        existing[1],
                        combined,
                    )

        for dossier_path in trusted_changed_dossiers & eligible_dossiers.keys():
            if dossier_path not in dossiers_to_validate:
                dossier = eligible_dossiers[dossier_path]
                dossier_risk = dossier.get("risk_tier")
                required_risk = dossier_risk if dossier_risk in RISK_TIERS else "R1"
                dossiers_to_validate[dossier_path] = (dossier, required_risk, {})

        for dossier_path, (
            dossier,
            required_risk,
            requirements,
        ) in dossiers_to_validate.items():
            errors.extend(
                _validate_dossier(
                    repo=repo,
                    path=dossier_path,
                    dossier=dossier,
                    policy=policy,
                    merge_base=merge_base,
                    head=head,
                    required_risk=required_risk,
                    requirements=requirements,
                )
            )
    except ValidationFailure as exc:
        errors.append(str(exc))
    return sorted(set(errors))


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default=".ai/policy.json")
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    errors = validate_repository(
        repo_root=Path(args.repo_root),
        policy_path=args.policy,
        base_sha=args.base_sha,
        head_sha=args.head_sha,
    )
    if errors:
        print("AI_SDLC_CHECK=FAIL")
        for error in errors:
            print(error)
        return 1
    print("AI_SDLC_CHECK=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
