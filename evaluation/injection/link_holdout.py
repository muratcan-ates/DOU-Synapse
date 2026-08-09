#!/usr/bin/env python3
"""holdout.json'daki injection/socratic_leak kayıtlarını cases.json'a bağlar (T046).

`SCHEMA.md`: "`r2_case_ref` — R2'nin `evaluation/injection/cases.json` kaydına
referans; birleştirmede doldurulur." v1'in 21 kaydı `null` ile duruyordu; bağlama
işi bu şeride bırakılmıştı (12_R2_OLCUM.md İş 2).

Bağ TEK YÖNLÜ kurulmaz: `cases.json` her vakada `holdout_refs` listesini, holdout ise
`r2_case_ref` alanını taşır. Betik ikisinin tutarlı olduğunu da denetler — bir vaka
holdout'ta olmayan bir kayda işaret ediyorsa ya da holdout'ta bağsız bir injection
kaydı kalmışsa hata verir. Tek yönlü bir bağ zamanla sessizce kopardı.

    cd apps/api && uv run python ../../evaluation/injection/link_holdout.py
    cd apps/api && uv run python ../../evaluation/injection/link_holdout.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES_PATH = HERE / "cases.json"
HOLDOUT_PATH = HERE.parent / "gold_set" / "holdout.json"

LINKED_CATEGORIES = {"injection", "socratic_leak"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="holdout <-> cases bağlarını kurar")
    parser.add_argument("--check", action="store_true", help="Yazma, yalnız denetle.")
    args = parser.parse_args(argv)

    registry = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    holdout = json.loads(HOLDOUT_PATH.read_text(encoding="utf-8"))

    holdout_ids = {item["id"] for item in holdout["items"]}
    mapping: dict[str, str] = {}
    problems: list[str] = []

    for case in registry["cases"]:
        for ref in case.get("holdout_refs", []):
            if ref not in holdout_ids:
                problems.append(f"{case['id']}: holdout'ta olmayan kayda işaret ediyor ({ref})")
                continue
            if ref in mapping:
                problems.append(f"{ref}: iki vakaya birden bağlı ({mapping[ref]}, {case['id']})")
                continue
            mapping[ref] = case["id"]

    changed = 0
    for item in holdout["items"]:
        if item["category"] not in LINKED_CATEGORIES:
            continue
        expected = mapping.get(item["id"])
        if expected is None:
            problems.append(f"{item['id']}: hiçbir vakaya bağlı değil (cases.json eksik)")
            continue
        if item.get("r2_case_ref") != expected:
            item["r2_case_ref"] = expected
            changed += 1

    for problem in problems:
        print(f"  SORUN {problem}", file=sys.stderr)

    if args.check:
        print(f"{len(mapping)} bağ · {changed} kayıt bayat · {len(problems)} sorun")
        return 1 if (problems or changed) else 0

    if problems:
        print("Sorunlar var; hiçbir şey yazılmadı (fail-closed).", file=sys.stderr)
        return 1

    HOLDOUT_PATH.write_text(
        json.dumps(holdout, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{changed} kaydın r2_case_ref alanı dolduruldu ({len(mapping)} bağ).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
