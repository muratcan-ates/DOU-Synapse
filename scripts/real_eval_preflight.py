"""Preflight checks for P4 real-eval dry-run readiness."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REQUIRED_ENV = {
    "EVAL_ADMIN_DSN": "postgresql admin bağlantısı",
    "EVAL_APP_DSN": "postgresql uygulama bağlantısı",
    "EVAL_WORKER_DSN": "postgresql işçi bağlantısı",
    "EVAL_LLM_API_KEY": "gerçek model anahtarı",
    "EVAL_RUNTIME_SECRET": "runtime sır değeri",
}


@dataclass
class PreflightResult:
    status: str
    environment_ready: bool
    database_ready: bool
    dsn_ok: list[str]
    warnings: list[str]
    failures: list[str]
    corpus_sha256: str | None
    corpus_path: str | None


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def _parse_dsn(name: str, dsn: str) -> dict[str, Any]:
    parsed = urlparse(dsn)
    if parsed.scheme.split("+")[0] != "postgresql":
        raise ValueError(f"{name}: postgresql şeması beklenir")
    if parsed.query:
        raise ValueError(f"{name}: DSN sorgu parametresi taşımamalı")

    database = (parsed.path or "/").lstrip("/")
    if not database:
        raise ValueError(f"{name}: veritabanı adı eksik")
    if not database.startswith("dou"):
        raise ValueError(f"{name}: veritabanı adı `dou` ile başlamalı")
    if not any(token in database for token in ("eval", "inject", "acceptance")):
        raise ValueError(f"{name}: izole veritabanı adı `eval`/`inject`/`acceptance` içermeli")

    return {
        "name": name,
        "host": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 5432,
        "database": database,
        "username": parsed.username or "",
    }


def _socket_alive(host: str, port: int, *, skip_db_connect: bool) -> str | None:
    if skip_db_connect:
        return None
    try:
        with socket.create_connection((host, port), timeout=1):
            return None
    except OSError as exc:
        return f"{host}:{port} bağlantısı kurulamadı ({exc})"


def _corpus_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _clean_tree(repo: Path) -> str | None:
    try:
        status = _run_git(repo, "status", "--porcelain")
    except RuntimeError as exc:
        return str(exc)
    return "working tree dirty" if status.strip() else None


def _run(
    *,
    repo: Path,
    corpus: Path | None,
    required_db_name: str,
    skip_db_connect: bool,
) -> PreflightResult:
    failures: list[str] = []
    warnings: list[str] = []
    dsn_ok: list[str] = []

    env: dict[str, str] = {}
    for key in REQUIRED_ENV:
        value = os.environ.get(key)
        if not value:
            failures.append(f"Missing environment variable: {key}")
        else:
            env[key] = value

    if missing := [key for key in REQUIRED_ENV if key not in env]:
        warnings.append(
            "İşletim sırları hazır değil; gerçek model koşusu için sadece isimleri kaydetmeden bekliyor."
        )
    else:
        dsn_ok.append("Required environment variable names are set")

    admin = app = worker = None
    if {"EVAL_ADMIN_DSN", "EVAL_APP_DSN", "EVAL_WORKER_DSN"} <= set(env):
        try:
            admin = _parse_dsn("EVAL_ADMIN_DSN", env["EVAL_ADMIN_DSN"])
            app = _parse_dsn("EVAL_APP_DSN", env["EVAL_APP_DSN"])
            worker = _parse_dsn("EVAL_WORKER_DSN", env["EVAL_WORKER_DSN"])
        except ValueError as exc:
            failures.append(str(exc))

    if admin is not None and app is not None and worker is not None:
        for label, parsed, expected_user in (
            ("EVAL_APP_DSN", app, "dou_app"),
            ("EVAL_WORKER_DSN", worker, "dou_worker"),
        ):
            if parsed["username"] != expected_user:
                failures.append(f"{label}: kullanıcı adı {expected_user} olmalı")
        if admin["username"] in {"dou_app", "dou_worker"}:
            failures.append("EVAL_ADMIN_DSN: kullanıcı adı dou_app veya dou_worker olamaz")

        for item in (admin, app, worker):
            if item["database"] != required_db_name:
                failures.append(
                    f"{item['name']}: veritabanı adı '{required_db_name}' beklenirken '{item['database']}' geldi"
                )
            if item["database"] != app["database"] or item["database"] != worker["database"]:
                failures.append("EVAL_*_DSN: host/port/veritabanı birebir eşleşmeli")

        if admin["host"] == app["host"] == worker["host"] and admin["port"] == app["port"] == worker["port"]:
            dsn_ok.append("Admin / app / worker aynı host ve porta bağlı")
        else:
            failures.append("EVAL_*_DSN: host/port eşleşmesi tutarsız")

        for item in (admin, app, worker):
            if app is not None:
                connect_error = _socket_alive(item["host"], item["port"], skip_db_connect=skip_db_connect)
                if connect_error:
                    failures.append(f"{item['name']}: {connect_error}")

    if not _safe_bool(os.environ.get("EVAL_RUNTIME_ENABLED", "")):
        warnings.append("EVAL_RUNTIME_ENABLED true olarak işaretlenmeli.")

    corpus_sha = None
    corpus_path = None
    if corpus is None:
        failures.append("Corpus path belirtilmedi.")
    else:
        corpus_path = str(corpus)
        if not corpus.exists():
            failures.append(f"Corpus dosyası bulunamadı: {corpus_path}")
        else:
            try:
                payload = json.loads(corpus.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    failures.append("Corpus JSON dict olmalı.")
                corpus_sha = _corpus_sha256(corpus)
                dsn_ok.append("Corpus JSON dosyası okunabiliyor")
            except Exception as exc:
                failures.append(f"Corpus okunamadı: {exc}")

    if issue := _clean_tree(repo):
        failures.append(issue)

    if failures:
        status = "blocked"
    elif warnings:
        status = "warn"
    else:
        status = "pass"

    return PreflightResult(
        status=status,
        environment_ready=all(key in env for key in REQUIRED_ENV),
        database_ready=admin is not None and app is not None and worker is not None and not failures,
        dsn_ok=dsn_ok,
        warnings=warnings,
        failures=failures,
        corpus_sha256=corpus_sha,
        corpus_path=corpus_path,
    )


def _safe_bool(value: str | None) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--corpus", type=Path, default=Path("/tmp/dou-corpus.json"))
    parser.add_argument("--required-db-name", default="dou_eval")
    parser.add_argument("--skip-db-connect", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = _run(
        repo=args.repo.resolve(),
        corpus=args.corpus,
        required_db_name=args.required_db_name,
        skip_db_connect=args.skip_db_connect,
    )

    report = {
        "schema_version": 1,
        "tool": "real_eval_preflight",
        "status": result.status,
        "required_db_name": args.required_db_name,
        "environment_ready": result.environment_ready,
        "database_ready": result.database_ready,
        "checkpoints": result.dsn_ok,
        "warnings": result.warnings,
        "failures": result.failures,
        "corpus_path": result.corpus_path,
        "corpus_sha256": result.corpus_sha256,
    }
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")

    if result.status != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
