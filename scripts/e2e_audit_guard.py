"""Önceden güvenilmiş sentetik hedefte salt okunur E2E audit muhasebesi.

Bu hazırlık çalıştırılmadı. Hedef keşfetmez/provision etmez; pins üreticisinin
yetkisini dosya hash'inden çıkarmaz. DELETE, göç, rol değişimi veya süreç durdurma
içermez. Son evreden önce kendi API sürecini durdurmak çağıranın sorumluluğudur.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

MAX_ROWS = 20_000
MAX_JSON_BYTES = 4 * 1024 * 1024
HEX = re.compile(r"[0-9a-f]{64}\Z")
RUN = re.compile(r"[a-z0-9]{6,20}\Z")
PIN_KEYS = {
    "version",
    "issuer",
    "ownership",
    "provisionSha256",
    "host",
    "port",
    "databaseName",
    "databaseOid",
    "cluster",
    "dbaRole",
    "apiOrigin",
}


class GuardError(Exception):
    """Yalnız sabit, özel değer taşımayan hata kodu."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise GuardError(code)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()


def private_read(path: Path) -> bytes:
    require(path.is_absolute() and path.resolve() == path, "PRIVATE_PATH_REQUIRED")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and not info.st_mode & 0o077, "PRIVATE_FILE_REQUIRED")
        require(info.st_size <= MAX_JSON_BYTES, "INPUT_TOO_LARGE")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(MAX_JSON_BYTES + 1)
        require(len(data) <= MAX_JSON_BYTES, "INPUT_TOO_LARGE")
        return data
    finally:
        os.close(fd)


def private_write(path: Path, value: Any) -> bytes:
    data = canonical(value)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
    return data


def read_pins(path: Path, expected: str) -> dict[str, Any]:
    raw = private_read(path)
    require(bool(HEX.fullmatch(expected)) and digest(raw) == expected, "PINS_HASH_MISMATCH")
    pins = json.loads(raw)
    require(type(pins) is dict and set(pins) == PIN_KEYS, "PINS_SCHEMA")
    require(
        type(pins["version"]) is int
        and pins["version"] == 1
        and pins["ownership"] == "exclusive-synthetic",
        "OWNERSHIP_SCOPE",
    )
    require(pins["issuer"] in {"root-owned-fresh-database", "github-owned-service"}, "PINS_ISSUER")
    require(
        type(pins["provisionSha256"]) is str and bool(HEX.fullmatch(pins["provisionSha256"])),
        "PROVISION_BINDING",
    )
    require(pins["host"] == "127.0.0.1", "NUMERIC_LOOPBACK_REQUIRED")
    require(type(pins["port"]) is int and 0 < pins["port"] < 65536, "PORT_REQUIRED")
    require(
        type(pins["databaseName"]) is str
        and bool(re.fullmatch(r"[a-z][a-z0-9_]{0,62}", pins["databaseName"])),
        "DATABASE_NAME",
    )
    require(pins["databaseName"] not in {"postgres", "template0", "template1"}, "SYSTEM_DATABASE")
    require(
        type(pins["dbaRole"]) is str
        and bool(re.fullmatch(r"[a-z][a-z0-9_]{0,62}", pins["dbaRole"])),
        "DBA_ROLE",
    )
    require(pins["dbaRole"] not in {"dou_app", "dou_worker"}, "PRIVILEGED_REVIEW_ROLE_REQUIRED")
    require(
        all(
            type(pins[k]) is str and bool(re.fullmatch(r"[1-9][0-9]*", pins[k]))
            for k in ["databaseOid", "cluster"]
        ),
        "NUMERIC_IDENTITY",
    )
    api = urlsplit(pins["apiOrigin"])
    require(
        api.scheme == "http" and api.hostname == "127.0.0.1" and api.port is not None, "API_ORIGIN"
    )
    require(
        not api.username
        and not api.password
        and not api.query
        and not api.fragment
        and api.path == "",
        "API_ORIGIN",
    )
    return pins


def snapshot(pins: dict[str, Any], passfile: Path) -> dict[str, str]:
    # Kimlik verisi yalnız açık pinlerden, kimlik doğrulama yalnız açık passfile'dan.
    # CLI ayrı süreçtir; ortam yönlendirmesini temizlemek üst süreci değiştirmez.
    require(passfile.is_absolute() and passfile.resolve() == passfile, "PASSFILE_PATH")
    info = passfile.lstat()
    require(stat.S_ISREG(info.st_mode) and not info.st_mode & 0o077, "PRIVATE_PASSFILE")
    for name in list(os.environ):
        if name.startswith("PG"):
            del os.environ[name]
    import psycopg

    with psycopg.connect(
        host=pins["host"],
        hostaddr=pins["host"],
        port=pins["port"],
        dbname=pins["databaseName"],
        user=pins["dbaRole"],
        passfile=str(passfile),
        connect_timeout=3,
        sslmode="disable",
        options=(
            "-c statement_timeout=5000 -c lock_timeout=2000 -c default_transaction_read_only=on"
        ),
    ) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        connection.execute("SET LOCAL search_path = pg_catalog")
        connection.execute("SET LOCAL TIME ZONE 'UTC'")
        actual = connection.execute("""
            SELECT current_database(), d.oid::text, c.system_identifier::text,
                   current_user, session_user, r.rolsuper, pg_is_in_recovery()
              FROM pg_database AS d CROSS JOIN pg_control_system() AS c
              JOIN pg_roles AS r ON r.rolname = current_user
             WHERE d.datname = current_database()
        """).fetchone()
        require(
            actual
            == (
                pins["databaseName"],
                pins["databaseOid"],
                pins["cluster"],
                pins["dbaRole"],
                pins["dbaRole"],
                True,
                False,
            ),
            "TARGET_IDENTITY_MISMATCH",
        )
        values = connection.execute("""
            SELECT id::text, to_jsonb(a)::text
              FROM public.platform_admin_access_audit AS a
             ORDER BY id LIMIT 20001
        """).fetchall()
        require(len(values) <= MAX_ROWS, "AUDIT_ROW_LIMIT")
        # Tam satır yalnız bellekte kanonikleştirilir; artefakta kimlik+SHA girer.
        return {row_id: digest(canonical(json.loads(body))) for row_id, body in values}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["begin", "finish"], required=True)
    parser.add_argument("--pins", type=Path, required=True)
    parser.add_argument("--pins-sha256", required=True)
    parser.add_argument("--passfile", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--quiescence-receipt", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"status": "PLAN", "phase": args.phase, "database_calls": 0}))
        return 0
    try:
        require(bool(RUN.fullmatch(args.run_id)), "RUN_ID")
        pins = read_pins(args.pins, args.pins_sha256)
        directory = args.directory
        require(directory.is_absolute() and directory.resolve() == directory, "DIRECTORY_PATH")
        target = {"version": 1, "trustedPinsSha256": args.pins_sha256, "pins": pins}
        target_id = digest(canonical(target))
        scope = {
            "version": 1,
            "runId": args.run_id,
            "databaseName": pins["databaseName"],
            "apiOrigin": pins["apiOrigin"],
            "targetId": target_id,
        }
        if args.phase == "begin":
            # Hedef uyuşmazlığında baseline/scope başarı makbuzu yazılmaz.
            rows = snapshot(pins, args.passfile)
            directory.mkdir(mode=0o700, parents=False, exist_ok=False)
            private_write(directory / "target.json", target)
            private_write(directory / "baseline.json", {"scope": scope, "rows": rows})
            capture = directory / "capture"
            capture.mkdir(mode=0o700)
            (capture / "sessions").mkdir(mode=0o700)
            (capture / "receipts").mkdir(mode=0o700)
            private_write(capture / "scope.json", scope)
            environment = {
                "E2E_RUN_ID": args.run_id,
                "E2E_DATABASE_NAME": pins["databaseName"],
                "E2E_API_URL": pins["apiOrigin"],
                "E2E_AUDIT_TARGET_ID": target_id,
                "E2E_AUDIT_DIR": str(capture),
            }
            private_write(directory / "environment.json", environment)
            print(
                json.dumps(
                    {"status": "BEGIN_RECORDED", "targetId": target_id, "baselineCount": len(rows)}
                )
            )
            return 0
        info = directory.lstat()
        require(stat.S_ISDIR(info.st_mode) and not info.st_mode & 0o077, "PRIVATE_DIRECTORY")
        require(
            private_read(directory / "target.json") == canonical(target), "TARGET_RECEIPT_MISMATCH"
        )
        baseline_raw = private_read(directory / "baseline.json")
        baseline = json.loads(baseline_raw)
        require(
            type(baseline) is dict
            and set(baseline) == {"scope", "rows"}
            and baseline["scope"] == scope,
            "BASELINE_SCOPE",
        )
        require(
            type(baseline["rows"]) is dict and len(baseline["rows"]) <= MAX_ROWS, "BASELINE_ROWS"
        )
        require(
            all(
                type(key) is str
                and bool(re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", key))
                and type(value) is str
                and bool(HEX.fullmatch(value))
                for key, value in baseline["rows"].items()
            ),
            "BASELINE_ROW_FORMAT",
        )
        require(args.quiescence_receipt is not None, "OWNED_API_QUIESCENCE_REQUIRED")
        quiescence_raw = private_read(args.quiescence_receipt)
        quiescence = json.loads(quiescence_raw)
        require(
            type(quiescence) is dict
            and set(quiescence)
            == {
                "version",
                "runId",
                "targetId",
                "ownedApiPid",
                "ownedApiExitCode",
                "playwrightExitCode",
                "state",
            },
            "QUIESCENCE_SCHEMA",
        )
        require(
            type(quiescence["version"]) is int
            and quiescence["version"] == 1
            and quiescence["runId"] == args.run_id
            and quiescence["targetId"] == target_id,
            "QUIESCENCE_SCOPE",
        )
        require(
            type(quiescence["ownedApiPid"]) is int and quiescence["ownedApiPid"] > 0,
            "OWNED_API_PID",
        )
        require(
            quiescence["state"] == "stopped"
            and type(quiescence["ownedApiExitCode"]) is int
            and quiescence["ownedApiExitCode"] == 0,
            "OWNED_API_NOT_CLEANLY_STOPPED",
        )
        require(type(quiescence["playwrightExitCode"]) is int, "PLAYWRIGHT_RESULT")
        after = snapshot(pins, args.passfile)
        before = baseline["rows"]
        missing = sorted(set(before) - set(after))
        changed = sorted(key for key in before.keys() & after.keys() if before[key] != after[key])
        extra = sorted(set(after) - set(before))
        clean = not missing and not changed and not extra
        result = {
            "scope": scope,
            "status": "PASS" if clean and quiescence["playwrightExitCode"] == 0 else "FAIL",
            "baselineSha256": digest(baseline_raw),
            "quiescenceSha256": digest(quiescence_raw),
            "beforeCount": len(before),
            "afterCount": len(after),
            "missingBaselineIds": missing,
            "changedBaselineIds": changed,
            "unexpectedNewRows": {key: after[key] for key in extra},
            "afterRows": after,
            "playwrightExitCode": quiescence["playwrightExitCode"],
            "deleteExecuted": False,
        }
        private_write(directory / "final-accounting.json", result)
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "missing": len(missing),
                    "changed": len(changed),
                    "unexpected": len(extra),
                }
            )
        )
        return 0 if result["status"] == "PASS" else 1
    except GuardError as error:
        print(json.dumps({"status": "FAIL", "code": str(error)}))
        return 2
    except Exception:
        # Bağlantı hatasının host/credential/metnini bu kanala kopyalama.
        print(json.dumps({"status": "FAIL", "code": "AUDIT_GUARD_FAILED"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
