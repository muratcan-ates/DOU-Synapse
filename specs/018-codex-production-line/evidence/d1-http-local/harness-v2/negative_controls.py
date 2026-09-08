"""Ayrı geçici kopyalarda aynı çevrimdışı oracles; DB/sunucu çağrısı yoktur."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).parent
MUTANTS = (
    (
        "app_query_accepted",
        "common.py",
        '"?" not in raw and "#" not in raw and not any(c.isspace() for c in raw)',
        "True",
        "GuardContracts.test_application_route_must_be_exact_loopback_role_database_and_no_options",
    ),
    (
        "ambient_credentials_inherited",
        "common.py",
        "    return result\n",
        "    return environment | result\n",
        "GuardContracts.test_child_environment_cannot_inherit_credentials_or_libpq_routes",
    ),
    (
        "source_mismatch_ignored",
        "common.py",
        "source_hashes() == expected",
        "True",
        "GuardContracts.test_source_manifest_requires_exact_root_values_and_integrated_quota",
    ),
    (
        "rls_flags_ignored",
        "common.py",
        'row["rolsuper"] is False and row["rolbypassrls"] is False',
        "True",
        "GuardContracts.test_app_pool_identity_is_non_superuser_non_bypass_and_rls_on",
    ),
    (
        "provider_failure_injection_removed",
        "serve.py",
        "            if failure:\n",
        "            if False:\n",
        "ProviderContracts.test_actual_generation_service_fake_answers_and_injected_failure_propagates",
    ),
)


def main():
    records = []
    before = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in BASE.glob("*.py")
    }
    for name, filename, old, new, oracle in MUTANTS:
        with tempfile.TemporaryDirectory(prefix="d1-http-mutant-", dir="/private/tmp") as directory:
            directory = Path(directory)
            for path in BASE.glob("*.py"):
                shutil.copyfile(path, directory / path.name)
            target = directory / filename
            source = target.read_text()
            assert source.count(old) == 1, (name, source.count(old))
            target.write_text(source.replace(old, new))
            result = subprocess.run(  # noqa: S603 — sabit kendi test dosyası ve oracle
                [sys.executable, str(directory / "test_offline.py"), oracle],
                env={
                    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
                cwd=directory,
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
            (BASE / "evidence" / f"negative-{name}.log").write_text(result.stdout + result.stderr)
            assert result.returncode == 1 and (
                "FAIL:" in result.stderr or "ERROR:" in result.stderr
            ), (name, result.returncode)
            records.append(
                {
                    "name": name,
                    "oracle": oracle,
                    "exit_code": result.returncode,
                    "rejected": True,
                    "mutated_source_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                }
            )
    after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in BASE.glob("*.py")}
    assert before == after
    (BASE / "evidence/negative-controls.json").write_text(
        json.dumps(
            {"mutants": records, "candidate_source_unchanged": True, "db_or_server_calls": 0},
            indent=2,
        )
        + "\n"
    )
    print(json.dumps({"mutants_rejected": len(records), "db_or_server_calls": 0}))


if __name__ == "__main__":
    main()
