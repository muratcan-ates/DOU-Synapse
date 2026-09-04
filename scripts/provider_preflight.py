"""Print secret-free provider readiness. Default/offline never contacts a provider."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--offline",
        action="store_true",
        help="Check config only; no network (default).",
    )
    mode.add_argument(
        "--probe", action="store_true", help="One bounded JSON request per target."
    )
    parser.add_argument("--timeout-seconds", type=float, default=10)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument(
        "--output", type=Path, help="Optional secret-free JSON report path."
    )
    args = parser.parse_args()
    from app.core.config import Settings
    from app.modules.generation.preflight import provider_preflight

    try:
        settings = Settings()
        report = asyncio.run(
            provider_preflight(
                settings,
                probe=args.probe,
                timeout_seconds=args.timeout_seconds,
                max_tokens=args.max_tokens,
            )
        )
    except Exception:  # noqa: BLE001 — configuration errors can contain secret input values
        # Never serialize Pydantic/provider exceptions: input values can be credentials.
        report = {
            "schema_version": 1,
            "kind": "provider_preflight",
            "status": "blocked",
            "quality_status": "not_evaluated",
            "blockers": ["invalid_configuration"],
            "provider_calls": 0,
        }
    encoded = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
