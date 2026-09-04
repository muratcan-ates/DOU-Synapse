"""Local candidate identity. Unknown or dirty code cannot attest a release."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]


def candidate_identity(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    git = shutil.which("git")
    unknown = {"candidate_sha": None, "candidate_dirty": None}
    if git is None:
        return unknown
    try:
        sha = subprocess.run(  # noqa: S603
            [git, "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
        ).stdout.strip()
        dirty = subprocess.run(  # noqa: S603
            [git, "status", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return unknown
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        return unknown
    return {"candidate_sha": sha, "candidate_dirty": bool(dirty.strip())}
