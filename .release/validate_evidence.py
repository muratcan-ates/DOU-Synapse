"""Validate release evidence against the repository's fail-closed schema.

Only the JSON Schema keywords used by ``evidence.schema.json`` are implemented.
Unknown schema keywords fail closed so the contract cannot silently grow beyond
what this dependency-free validator actually enforces.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SUPPORTED_ANNOTATIONS = {"$schema", "$id", "title"}
SUPPORTED_ASSERTIONS = {
    "type",
    "const",
    "enum",
    "required",
    "properties",
    "additionalProperties",
    "minLength",
    "minimum",
    "pattern",
    "format",
    "minItems",
    "maxItems",
    "uniqueItems",
    "items",
    "x-exact-item-key-set",
    "x-exact-image-reference",
    "x-check-workflow-map",
    "x-release-record-semantics",
}


class EvidenceValidationError(ValueError):
    """Raised when an evidence document or its schema is invalid."""


def _fail(path: str, message: str) -> None:
    raise EvidenceValidationError(f"{path}: {message}")


def _json_equal(left: Any, right: Any) -> bool:
    """Compare JSON values without Python's ``True == 1`` coercion."""

    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    return left == right


def _validate_datetime(value: str, path: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        _fail(path, f"invalid date-time: {exc}")
    if parsed.tzinfo is None:
        _fail(path, "date-time must include a timezone")


def _validate_release_record(instance: dict[str, Any], path: str) -> None:
    """Enforce relationships that JSON field shape alone cannot express."""

    source = instance.get("source")
    image = instance.get("image")
    supply_chain = instance.get("supply_chain")
    artifact = instance.get("artifact_verification")
    environments = instance.get("environments")
    checks = instance.get("checks")
    if not all(
        isinstance(value, dict)
        for value in (source, image, supply_chain, artifact, environments)
    ) or not isinstance(checks, list):
        return

    image_name = image.get("name")
    image_digest = image.get("digest")
    immutable_reference = image.get("immutable_reference")
    quarantine_reference = image.get("quarantine_reference")
    if artifact.get("image_reference") != immutable_reference:
        _fail(path, "artifact verification must target image.immutable_reference")
    if not isinstance(quarantine_reference, str) or not quarantine_reference.startswith(
        f"{image_name}:quarantine-"
    ):
        _fail(path, "quarantine_reference must belong to image.name")

    for predicate in ("sbom", "provenance"):
        record = supply_chain.get(predicate)
        if not isinstance(record, dict):
            continue
        expected = f"oci://{image_name}@{record.get('digest')}"
        if record.get("reference") != expected:
            _fail(
                path, f"supply_chain.{predicate}.reference must equal OCI name@digest"
            )

    source_sha = source.get("sha")
    for index, check in enumerate(checks):
        if isinstance(check, dict) and check.get("head_sha") != source_sha:
            _fail(f"{path}.checks[{index}]", "head_sha must equal source.sha")

    record_type = instance.get("record_type")
    promotion = instance.get("promotion")
    if record_type == "candidate":
        if "promotion" in instance:
            _fail(path, "candidate evidence cannot claim promotion or deployment")
        if environments != {
            "staging": "not-configured",
            "production": "not-configured",
        }:
            _fail(path, "candidate evidence cannot claim an environment is verified")
        return
    if record_type != "promotion":
        return
    if not isinstance(promotion, dict):
        _fail(path, "promotion evidence requires the promotion object")
    if promotion.get("source_digest") != image_digest:
        _fail(path, "promotion.source_digest must equal image.digest")

    target = promotion.get("target")
    if target == "production":
        if environments != {"staging": "verified", "production": "verified"}:
            _fail(
                path, "production verification requires verified staging and production"
            )
    elif target == "staging" and environments.get("staging") != "verified":
        _fail(path, "staging promotion requires staging=verified")

    for section_name in ("approval", "smoke", "migration", "backup", "rollback"):
        section = promotion.get(section_name)
        if not isinstance(section, dict):
            continue
        if section.get("source_sha") != source_sha:
            _fail(path, f"promotion.{section_name}.source_sha must equal source.sha")
        if section.get("digest") != image_digest:
            _fail(path, f"promotion.{section_name}.digest must equal image.digest")
    rollback = promotion.get("rollback")
    if isinstance(rollback, dict) and rollback.get("previous_digest") == image_digest:
        _fail(path, "rollback.previous_digest must differ from the promoted digest")


def _validate(instance: Any, schema: dict[str, Any], path: str) -> None:
    unknown = set(schema) - SUPPORTED_ANNOTATIONS - SUPPORTED_ASSERTIONS
    if unknown:
        _fail(path, f"unsupported schema keyword(s): {sorted(unknown)}")

    if "const" in schema and not _json_equal(instance, schema["const"]):
        _fail(path, f"must equal {schema['const']!r}")
    if "enum" in schema and not any(
        _json_equal(instance, option) for option in schema["enum"]
    ):
        _fail(path, f"must be one of {schema['enum']!r}")

    expected_type = schema.get("type")
    type_matches = {
        "object": isinstance(instance, dict),
        "array": isinstance(instance, list),
        "string": isinstance(instance, str),
        "integer": isinstance(instance, int) and not isinstance(instance, bool),
    }
    if expected_type is not None:
        if expected_type not in type_matches:
            _fail(path, f"unsupported schema type {expected_type!r}")
        if not type_matches[expected_type]:
            _fail(path, f"must be {expected_type}")

    if isinstance(instance, dict):
        required = schema.get("required", [])
        missing = [key for key in required if key not in instance]
        if missing:
            _fail(path, f"missing required field(s): {missing}")

        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extras = sorted(set(instance) - set(properties))
            if extras:
                _fail(path, f"unknown field(s): {extras}")
        for key, child_schema in properties.items():
            if key in instance:
                _validate(instance[key], child_schema, f"{path}.{key}")

        image_reference = schema.get("x-exact-image-reference")
        if image_reference is not None:
            if not isinstance(image_reference, dict):
                _fail(path, "x-exact-image-reference schema is malformed")
            name_key = image_reference.get("name")
            digest_key = image_reference.get("digest")
            reference_key = image_reference.get("reference")
            if not all(
                isinstance(key, str) for key in (name_key, digest_key, reference_key)
            ):
                _fail(path, "x-exact-image-reference schema is malformed")
            expected_reference = f"{instance.get(name_key)}@{instance.get(digest_key)}"
            if instance.get(reference_key) != expected_reference:
                _fail(
                    path,
                    f"{reference_key!r} must equal name@digest exactly",
                )

        if schema.get("x-release-record-semantics") is not None:
            if schema.get("x-release-record-semantics") is not True:
                _fail(path, "x-release-record-semantics schema is malformed")
            _validate_release_record(instance, path)

    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            _fail(path, f"must contain at least {schema['minItems']} items")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            _fail(path, f"must contain at most {schema['maxItems']} items")
        if schema.get("uniqueItems"):
            encoded = [
                json.dumps(item, sort_keys=True, separators=(",", ":"))
                for item in instance
            ]
            if len(encoded) != len(set(encoded)):
                _fail(path, "items must be unique")
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(instance):
                _validate(item, item_schema, f"{path}[{index}]")

        exact_key_set = schema.get("x-exact-item-key-set")
        if exact_key_set is not None:
            key = exact_key_set.get("key")
            expected = exact_key_set.get("values")
            if not isinstance(key, str) or not isinstance(expected, list):
                _fail(path, "x-exact-item-key-set schema is malformed")
            actual = [
                item.get(key) if isinstance(item, dict) else None for item in instance
            ]
            if actual != expected:
                _fail(
                    path, f"{key!r} values must exactly match the required ordered set"
                )

        workflow_map = schema.get("x-check-workflow-map")
        if workflow_map is not None:
            if not isinstance(workflow_map, dict) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in workflow_map.items()
            ):
                _fail(path, "x-check-workflow-map schema is malformed")
            for index, item in enumerate(instance):
                if not isinstance(item, dict):
                    continue
                expected_path = workflow_map.get(item.get("name"))
                if item.get("workflow_path") != expected_path:
                    _fail(
                        f"{path}[{index}]",
                        "workflow_path does not match the required job identity",
                    )

    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            _fail(path, f"must have length >= {schema['minLength']}")
        pattern = schema.get("pattern")
        # JSON Schema's ``pattern`` keyword uses search semantics, not an
        # implicit full match. Anchors in the repository schema still express
        # whole-value constraints where needed.
        if pattern is not None and re.search(pattern, instance) is None:
            _fail(path, f"does not match pattern {pattern!r}")
        value_format = schema.get("format")
        if value_format == "date-time":
            _validate_datetime(instance, path)
        elif value_format is not None:
            _fail(path, f"unsupported string format {value_format!r}")

    if isinstance(instance, int) and not isinstance(instance, bool):
        minimum = schema.get("minimum")
        if minimum is not None and instance < minimum:
            _fail(path, f"must be >= {minimum}")


def validate_document(document: Any, schema: Any) -> None:
    if not isinstance(schema, dict):
        raise EvidenceValidationError("$: schema must be an object")
    _validate(document, schema, "$")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    try:
        schema = json.loads(args.schema.read_text(encoding="utf-8"))
        document = json.loads(args.input.read_text(encoding="utf-8"))
        validate_document(document, schema)
    except (OSError, json.JSONDecodeError, EvidenceValidationError) as exc:
        print(f"release evidence validation failed: {exc}", file=sys.stderr)
        return 1
    print("RELEASE_EVIDENCE_VALIDATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
