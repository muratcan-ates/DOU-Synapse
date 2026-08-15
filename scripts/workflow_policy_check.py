"""Fail closed on unsafe workflow triggers and mutable action dependencies.

The policy parses YAML structurally.  Text/regex scanning is intentionally not
used: flow mappings, quoted keys, anchors and aliases must have the same
meaning here that they have to GitHub Actions.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode
from yaml.resolver import BaseResolver

IMMUTABLE_REMOTE_RE = re.compile(r"^[^/@\s]+/[^@\s]+@[0-9a-f]{40}$")
TRUE_FALSE_RE = re.compile(r"^(?:true|false)$", re.IGNORECASE)


class MarkedDict(dict[Any, Any]):
    """Mapping that retains the source line for every YAML key."""

    def __init__(self) -> None:
        super().__init__()
        self.key_lines: dict[Any, int] = {}


class PolicyLoader(yaml.SafeLoader):
    """Safe loader with YAML 1.2-style booleans and duplicate-key rejection."""


# PyYAML follows YAML 1.1 and would turn the GitHub key ``on`` into ``True``.
# Copy the resolver table before narrowing boolean recognition to true/false.
PolicyLoader.yaml_implicit_resolvers = {
    key: list(resolvers)
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
for first_character, resolvers in PolicyLoader.yaml_implicit_resolvers.items():
    PolicyLoader.yaml_implicit_resolvers[first_character] = [
        resolver for resolver in resolvers if resolver[0] != "tag:yaml.org,2002:bool"
    ]
PolicyLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    TRUE_FALSE_RE,
    list("tTfF"),
)


def _construct_mapping(
    loader: PolicyLoader,
    node: MappingNode,
    deep: bool = False,
) -> MarkedDict:
    """Construct a mapping while rejecting written duplicate keys.

    Merge keys are flattened after the raw-key check.  This accepts a normal
    explicit override of an anchored default, while a duplicate key written in
    the same mapping remains a fail-closed parse error.
    """

    raw_keys: set[Any] = set()
    for key_node, _ in node.value:
        if key_node.tag == "tag:yaml.org,2002:merge":
            continue
        key = loader.construct_object(key_node, deep=deep)
        try:
            if key in raw_keys:
                raise ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"duplicate key {key!r}",
                    key_node.start_mark,
                )
            raw_keys.add(key)
        except TypeError as exc:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "mapping key is not hashable",
                key_node.start_mark,
            ) from exc

    loader.flatten_mapping(node)
    mapping = MarkedDict()
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        value = loader.construct_object(value_node, deep=deep)
        try:
            mapping[key] = value
            mapping.key_lines[key] = key_node.start_mark.line + 1
        except TypeError as exc:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "mapping key is not hashable",
                key_node.start_mark,
            ) from exc
    return mapping


PolicyLoader.add_constructor(BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


@dataclass(frozen=True)
class Violation:
    code: str
    path: Path
    line: int
    value: str


def _policy_files(root: Path) -> list[Path]:
    workflow_dir = root / ".github" / "workflows"
    action_dir = root / ".github" / "actions"
    return sorted(
        {
            *workflow_dir.glob("*.yml"),
            *workflow_dir.glob("*.yaml"),
            *action_dir.rglob("action.yml"),
            *action_dir.rglob("action.yaml"),
        }
    )


def _local_manifest(root: Path, target: str) -> Path | None:
    candidate = (root / target.removeprefix("./")).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None

    if candidate.is_file() and candidate.suffix in {".yml", ".yaml"}:
        return candidate
    for name in ("action.yml", "action.yaml"):
        manifest = candidate / name
        if manifest.is_file():
            return manifest
    return None


def _contains_trigger(value: Any, trigger: str, seen: set[int] | None = None) -> bool:
    seen = seen or set()
    if isinstance(value, (dict, list)):
        identity = id(value)
        if identity in seen:
            return False
        seen.add(identity)
    if isinstance(value, str):
        return value == trigger
    if isinstance(value, list):
        return any(_contains_trigger(item, trigger, seen) for item in value)
    if isinstance(value, dict):
        return any(key == trigger for key in value)
    return False


def _walk_uses(
    value: Any,
    *,
    root: Path,
    relative: Path,
    queue: list[Path],
    violations: list[Violation],
    seen: set[int] | None = None,
) -> None:
    seen = seen or set()
    if isinstance(value, (dict, list)):
        identity = id(value)
        if identity in seen:
            return
        seen.add(identity)

    if isinstance(value, MarkedDict):
        if "uses" in value:
            line = value.key_lines.get("uses", 1)
            target = value["uses"]
            if not isinstance(target, str) or not target.strip():
                violations.append(
                    Violation("INVALID_ACTION_REF", relative, line, repr(target))
                )
            else:
                target = target.strip()
                if target.startswith("./"):
                    manifest = _local_manifest(root, target)
                    if manifest is None:
                        violations.append(
                            Violation(
                                "LOCAL_ACTION_UNRESOLVED",
                                relative,
                                line,
                                target,
                            )
                        )
                    else:
                        queue.append(manifest)
                elif not IMMUTABLE_REMOTE_RE.fullmatch(target):
                    violations.append(
                        Violation("MUTABLE_ACTION_REF", relative, line, target)
                    )
        for child in value.values():
            _walk_uses(
                child,
                root=root,
                relative=relative,
                queue=queue,
                violations=violations,
                seen=seen,
            )
    elif isinstance(value, list):
        for child in value:
            _walk_uses(
                child,
                root=root,
                relative=relative,
                queue=queue,
                violations=violations,
                seen=seen,
            )


def inspect_workflows(root: Path) -> list[Violation]:
    """Inspect workflows plus every recursively referenced local action."""

    root = root.resolve()
    workflow_dir = root / ".github" / "workflows"
    violations: list[Violation] = []
    queue = _policy_files(root)
    visited: set[Path] = set()

    while queue:
        path = queue.pop(0).resolve()
        if path in visited:
            continue
        visited.add(path)
        try:
            relative = path.relative_to(root)
        except ValueError:
            violations.append(
                Violation("LOCAL_ACTION_ESCAPES_REPO", path, 1, str(path))
            )
            continue

        try:
            document = yaml.load(path.read_text(encoding="utf-8"), Loader=PolicyLoader)
        except (OSError, yaml.YAMLError) as exc:
            mark = getattr(exc, "problem_mark", None)
            line = mark.line + 1 if mark is not None else 1
            violations.append(Violation("INVALID_YAML", relative, line, str(exc)))
            continue
        if not isinstance(document, MarkedDict):
            violations.append(
                Violation("INVALID_YAML_ROOT", relative, 1, type(document).__name__)
            )
            continue

        if path.parent == workflow_dir:
            if "on" not in document:
                violations.append(Violation("MISSING_TRIGGER", relative, 1, "on"))
            elif _contains_trigger(document["on"], "pull_request_target"):
                violations.append(
                    Violation(
                        "UNSAFE_TRIGGER",
                        relative,
                        document.key_lines.get("on", 1),
                        "pull_request_target",
                    )
                )

        _walk_uses(
            document,
            root=root,
            relative=relative,
            queue=queue,
            violations=violations,
        )

    return sorted(
        violations,
        key=lambda violation: (
            violation.path.as_posix(),
            violation.line,
            violation.code,
            violation.value,
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    violations = inspect_workflows(args.repo_root.resolve())
    for violation in violations:
        print(f"{violation.code} {violation.path}:{violation.line} {violation.value}")
    if violations:
        return 1
    print("WORKFLOW_POLICY_CHECK=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
