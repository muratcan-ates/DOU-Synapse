#!/usr/bin/env python3
"""Verify reference inserts block raw draft edits; clone an empty migrated test DB.

PGHOST/PGPORT/PGUSER select the isolated test cluster; PG_BIN locates its tools.
Usage: python3 question_authoring_concurrency_check.py dou013_sql [exam_sessions]
The provided template is not written to. Every generated database is dropped.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PG_BIN = Path(os.environ.get("PG_BIN", ""))
PSQL = str(PG_BIN / "psql") if os.environ.get("PG_BIN") else "psql"
CREATEDB = str(PG_BIN / "createdb") if os.environ.get("PG_BIN") else "createdb"
DROPDB = str(PG_BIN / "dropdb") if os.environ.get("PG_BIN") else "dropdb"
PREFIX = "13000000-0000-0000-0000-"


def uuid(number: int) -> str:
    return "'" + PREFIX + f"{number:012d}" + "'"


def command(database: str) -> list[str]:
    return [PSQL, "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-v", "VERBOSITY=verbose", "-d", database]


def execute(database: str, sql: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command(database), input=sql, text=True, capture_output=True, timeout=15)


def main() -> int:
    template = sys.argv[1]
    selected = sys.argv[2] if len(sys.argv) > 2 else None
    scratch = f"dou013_sql_conc_{os.getpid()}"
    subprocess.run([CREATEDB, "-T", template, scratch], check=True)
    holder = None
    try:
        fixture = (ROOT / "supabase/tests/rls_question_authoring.sql").read_text().split("SET LOCAL ROLE dou_app;")[0]
        seeded = execute(scratch, fixture + "\nCOMMIT;\n")
        if seeded.returncode:
            raise RuntimeError(seeded.stderr)
        reference_inserts = {
            "exam_items": f"INSERT INTO exam_items(id,course_id,exam_version_id,position,question_id,points) VALUES ({uuid(70)},{uuid(10)},{uuid(61)},2,{uuid(56)},1);",
            "answers": f"INSERT INTO answers(id,session_id,question_id,course_id,given) VALUES ({uuid(70)},{uuid(64)},{uuid(56)},{uuid(10)},'Concurrent answer');",
            "exam_sessions": f"INSERT INTO exam_sessions(id,course_id,user_id,mode,question_ids) VALUES ({uuid(70)},{uuid(10)},{uuid(2)},'practice',ARRAY[{uuid(56)}::uuid]);",
        }
        failed = 0
        for table, insert in reference_inserts.items():
            if selected is not None and table != selected:
                continue
            holder = subprocess.Popen(command(scratch), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            assert holder.stdin is not None and holder.stdout is not None
            holder.stdin.write("BEGIN;\n" + insert + "\nSELECT 'reference-held';\n")
            holder.stdin.flush()
            if holder.stdout.readline().strip() != "reference-held":
                raise RuntimeError("Reference transaction did not reach its barrier")
            update = f"UPDATE questions SET payload=jsonb_set(payload,'{{prompt}}','\"Concurrent edit\"') WHERE id={uuid(56)};"
            editing = execute(scratch, "SET lock_timeout='400ms';\n" + update)
            blocked = editing.returncode != 0 and "55P03" in editing.stderr
            print(f"{'PASS' if blocked else 'FAIL'}  concurrent_{table}_blocks_raw_edit", flush=True)
            failed += not blocked
            holder.stdin.write("COMMIT;\n")
            holder.stdin.close()
            holder.wait(timeout=5)
            if holder.returncode:
                raise RuntimeError(holder.stderr.read() if holder.stderr else "Reference commit failed")
            holder = None
            immutable = execute(scratch, update)
            protected = immutable.returncode != 0 and "questions_authoring_immutable" in immutable.stderr
            print(f"{'PASS' if protected else 'FAIL'}  committed_{table}_freezes_draft", flush=True)
            failed += not protected
            cleanup = execute(scratch, f"DELETE FROM {table} WHERE id={uuid(70)};")
            if cleanup.returncode:
                raise RuntimeError(cleanup.stderr)
        return int(failed != 0)
    finally:
        if holder is not None:
            holder.kill()
            holder.wait(timeout=5)
        subprocess.run([DROPDB, "--force", scratch], check=True)


if __name__ == "__main__":
    raise SystemExit(main())
