#!/usr/bin/env python3
"""Prepare immutable source/gold hashes and human-review forms, with zero API calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EVALUATION = HERE.parent
REPO_ROOT = EVALUATION.parent
sys.path.insert(0, str(EVALUATION))
from _paths import ensure_api_on_path
from goldset import SourceSpec
from provenance import EvidenceError, require_sample_evidence, utc_now, validate_runtime


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(output: Path, *, sample: Path | None = None) -> dict[str, Any]:
    # Validate first: do not leave a purported acceptance packet on invalid input.
    draft = json.loads((HERE / "assessment_cases.json").read_text(encoding="utf-8"))
    ensure_api_on_path()
    from app.schemas.assessment import RubricItem

    for case in draft["cases"]:
        case["source"] = asdict(SourceSpec(**case["source"]))
        case["rubric"] = [RubricItem.model_validate(item).model_dump() for item in case["rubric"]]
    draft_bytes = json.dumps(draft, ensure_ascii=False, indent=2).encode("utf-8")
    sample_bytes = sample.read_bytes() if sample else None
    payload = None
    if sample_bytes is not None:
        try:
            payload = json.loads(sample_bytes)
        except (ValueError, UnicodeDecodeError) as exc:
            raise EvidenceError("Örneklem geçerli UTF-8 JSON olmalı.") from exc
        if not isinstance(payload, dict):
            raise EvidenceError("Örneklem bir JSON nesnesi olmalı.")
        require_sample_evidence(payload)
    material = REPO_ROOT / "sample_data" / "isletim-sistemleri"
    sources = [
        {"path": str(path.relative_to(REPO_ROOT)), "sha256": sha256_file(path)}
        for path in sorted(material.iterdir())
        if path.suffix in {".pdf", ".pptx", ".py", ".c"}
    ]
    candidate = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "-C", str(REPO_ROOT), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    if payload is not None:
        if dirty:
            raise EvidenceError("Kaydedilmemiş aday değişikliklerine gerçek örneklem bağlanamaz.")
        validate_runtime(payload.get("runtime_manifest"), candidate_sha=candidate)
    manifest = {
        "schema_version": 1,
        "kind": "acceptance_packet",
        "prepared_at": utc_now(),
        "candidate_sha": candidate,
        "candidate_dirty": dirty,
        "source_approval": "pending_instructor_review",
        "source_origin": "repository_team_samples",
        "sources": sources,
        "gold_sets": [
            {"path": str(path.relative_to(REPO_ROOT)), "sha256": sha256_file(path)}
            for path in [
                EVALUATION / "gold_set" / "calibration.json",
                EVALUATION / "gold_set" / "holdout.json",
                EVALUATION / "injection" / "cases.json",
            ]
        ],
        "assessment_cases_sha256": hashlib.sha256(draft_bytes).hexdigest(),
        "assessment_cases_source_sha256": sha256_file(HERE / "assessment_cases.json"),
        "real_provider_quality": "pending",
        "independent_human_review": "pending",
        "grading_run": "not_run",
        "ocr": "not_required_for_current_text_samples",
        "faithfulness_sample_sha256": (
            hashlib.sha256(sample_bytes).hexdigest() if sample_bytes is not None else None
        ),
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "assessment_cases.json").write_bytes(draft_bytes)
    shutil.copyfile(HERE / "README.md", output / "README.md")
    if payload is not None and sample_bytes is not None:
        from faithfulness.pull_sample import write_label_file

        (output / "sample.json").write_bytes(sample_bytes)
        for labeller in ("1", "2"):
            write_label_file(output / f"labels_etiketleyici_{labeller}.md", payload, labeller)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample", type=Path)
    args = parser.parse_args(argv)
    prepare(args.output_dir, sample=args.sample)
    print(f"Hazırlık paketi: {args.output_dir}; gerçek kalite/insan kabulü bekliyor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
