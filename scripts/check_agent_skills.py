"""Read-only validation of the repository's Claude-to-Codex skill package.

Run with the locked API Python environment (PyYAML is already a dependency).
This checks packaging, not instruction quality, installation or tool authority.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

MAX_FILE_BYTES = 1_000_000
SUPPORTED_FIELDS = {"name", "description", "license", "allowed-tools", "metadata"}
PORTABLE_DOU = {"dou-kurulum", "dou-entegrasyon", "dou-kanit"}
LINK = re.compile(r"(?<!!)\[[^\]\n]+\]\((<[^>]+>|[^\s)]+)(?:\s+\"[^\"]*\")?\)")
DEFINITION = re.compile(r"^[ \t]{0,3}\[([^\]\n]+)\]:\s*(<[^>]+>|[^\s]+)", re.MULTILINE)
REFERENCE = re.compile(r"(?<!!)\[([^\]\n]+)\]\[([^\]\n]*)\]")


class UniqueSafeLoader(yaml.SafeLoader):
    """Reject ambiguous duplicate keys instead of silently taking the last one."""


def unique_mapping(loader: UniqueSafeLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise ValueError("non-string or duplicate mapping key")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def read_text(path: Path, repo: Path) -> str:
    resolved = path.resolve()
    if not resolved.is_relative_to(repo) or not path.is_file():
        raise ValueError("file missing or outside repository")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("file too large")
    return path.read_text(encoding="utf-8")


def load_mapping(text: str) -> dict:
    loader = UniqueSafeLoader(text)
    try:
        value = loader.get_single_data()
    finally:
        loader.dispose()
    if not isinstance(value, dict):
        raise ValueError("mapping required")
    return value


def frontmatter(text: str) -> tuple[dict, str]:
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.DOTALL)
    if match is None:
        raise ValueError("frontmatter missing")
    return load_mapping(match.group(1)), text[match.end() :]


def link_targets(body: str, folder: str, errors: list[str]) -> list[str]:
    """Cover inline and reference-style links without loading their destinations."""
    definitions = {" ".join(m[1].lower().split()): m[2] for m in DEFINITION.finditer(body)}
    for match in REFERENCE.finditer(body):
        key = " ".join((match[2] or match[1]).lower().split())
        if key not in definitions:
            errors.append(f"UNDEFINED_REFERENCE:{folder}:{key}")
    return [m[1] for m in LINK.finditer(body)] + list(definitions.values())


def skill_dirs(root: Path, repo: Path, errors: list[str]) -> dict[str, Path]:
    if not root.is_dir() or not root.resolve().is_relative_to(repo):
        errors.append(f"SKILL_ROOT:{root.relative_to(repo)}")
        return {}
    directories = {}
    for child in sorted(root.iterdir()):
        if child.is_dir():
            if not child.resolve().is_relative_to(repo):
                errors.append(f"SKILL_OUTSIDE_REPO:{child.name}")
            else:
                directories[child.name] = child
    return directories


def validate(repo: Path) -> dict:
    repo = repo.resolve()
    errors: list[str] = []
    sources = skill_dirs(repo / ".claude/skills", repo, errors)
    targets = skill_dirs(repo / ".agents/skills", repo, errors)
    if not sources or not targets:
        errors.append("EMPTY_PACKAGE")
    for name in sorted(sources.keys() - targets.keys()):
        errors.append(f"MISSING_CODEX_SKILL:{name}")
    for name in sorted(targets.keys() - sources.keys()):
        errors.append(f"MISSING_SOURCE_SKILL:{name}")
    seen_names: set[str] = set()
    local_links = 0
    for folder, directory in targets.items():
        try:
            text = read_text(directory / "SKILL.md", repo)
            metadata, body = frontmatter(text)
        except (OSError, ValueError, RuntimeError, UnicodeError, yaml.YAMLError):
            errors.append(f"SKILL_PARSE:{folder}")
            continue
        name = metadata.get("name")
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
            or len(name) > 64
        ):
            errors.append(f"SKILL_NAME:{folder}")
        elif name in seen_names:
            errors.append(f"DUPLICATE_SKILL_NAME:{name}")
        else:
            seen_names.add(name)
        if name != folder:
            errors.append(f"FOLDER_NAME:{folder}")
        description = metadata.get("description")
        if (
            not isinstance(description, str)
            or not description.strip()
            or len(description) > 1024
            or any(c in description for c in "<>")
        ):
            errors.append(f"DESCRIPTION:{folder}")
        if set(metadata) - SUPPORTED_FIELDS:
            errors.append(f"UNSUPPORTED_METADATA:{folder}")
        for field in ("license", "allowed-tools"):
            if field in metadata and not isinstance(metadata[field], str):
                errors.append(f"METADATA_TYPE:{folder}:{field}")
        if "metadata" in metadata and (
            not isinstance(metadata["metadata"], dict)
            or any(not isinstance(v, str) for v in metadata["metadata"].values())
        ):
            errors.append(f"METADATA_TYPE:{folder}:metadata")
        if not body.strip():
            errors.append(f"EMPTY_INSTRUCTIONS:{folder}")
        if re.search(r"\[TODO:|\$ARGUMENTS|\$\{ARGS\}", text):
            errors.append(f"UNFINISHED_TEMPLATE:{folder}")
        for raw_target in link_targets(body, folder, errors):
            raw = raw_target.strip("<>")
            try:
                url = urlsplit(raw)
            except ValueError:
                errors.append(f"MALFORMED_REFERENCE:{folder}")
                continue
            if url.scheme == "file":
                errors.append(f"LOCAL_REFERENCE:{folder}:{raw}")
                continue
            if url.scheme or url.netloc or not url.path:
                continue
            local_links += 1
            try:
                path = Path(unquote(url.path))
                target = (directory / path).resolve()
                valid = not path.is_absolute() and target.is_relative_to(repo) and target.exists()
            except (OSError, ValueError, RuntimeError):
                valid = False
            if not valid:
                errors.append(f"LOCAL_REFERENCE:{folder}:{raw}")
        try:
            config = load_mapping(read_text(directory / "agents/openai.yaml", repo))
            interface = config.get("interface")
            if not isinstance(interface, dict):
                raise ValueError("interface required")
            display = interface.get("display_name")
            short = interface.get("short_description")
            prompt = interface.get("default_prompt")
            if not isinstance(display, str) or not display.strip():
                errors.append(f"DISPLAY_NAME:{folder}")
            if not isinstance(short, str) or not 25 <= len(short) <= 64:
                errors.append(f"SHORT_DESCRIPTION:{folder}")
            invocation = rf"(?<![\w$-])\${re.escape(folder)}(?![\w-])"
            if not isinstance(prompt, str) or not re.search(invocation, prompt):
                errors.append(f"DEFAULT_PROMPT:{folder}")
        except (OSError, ValueError, RuntimeError, UnicodeError, yaml.YAMLError):
            errors.append(f"UI_METADATA:{folder}")
        if folder in sources:
            try:
                source_text = read_text(sources[folder] / "SKILL.md", repo)
                source_meta, _ = frontmatter(source_text)
                if source_meta.get("name") != folder:
                    errors.append(f"SOURCE_NAME:{folder}")
                if folder in PORTABLE_DOU and source_text != text:
                    errors.append(f"DOU_RUNTIME_DRIFT:{folder}")
            except (OSError, ValueError, RuntimeError, UnicodeError, yaml.YAMLError):
                errors.append(f"SOURCE_PARSE:{folder}")
    return {
        "status": "pass" if not errors else "fail",
        "claude_skills": len(sources),
        "codex_skills": len(targets),
        "local_references_checked": local_links,
        "errors": sorted(set(errors)),
        "scope": "Packaging only; behavior and runtime discovery need separate verification.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate(args.repo_root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"AGENT_SKILLS_CHECK={result['status'].upper()}")
        print(
            f"Claude: {result['claude_skills']}; Codex: {result['codex_skills']}; "
            f"yerel bağlantı: {result['local_references_checked']}"
        )
        for error in result["errors"]:
            print(error)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
