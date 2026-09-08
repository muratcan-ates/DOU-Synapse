"""İki yerel HTTP süreci deneyi için dar, çevrimdışı yapılandırma sözleşmesi."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from db_guard import TargetGuardError, expected_target, numeric_loopback, require

REPOSITORY = Path("/Users/muratates/code/dou-synapse-018-codex-production-line")
SOURCE_PATHS = (
    "apps/api/app/api/chat.py",
    "apps/api/app/api/questions.py",
    "apps/api/app/api/deps.py",
    "apps/api/app/core/request_quota.py",
    "apps/api/app/core/db.py",
    "apps/api/app/core/security.py",
    "apps/api/app/core/config.py",
    "apps/api/app/main.py",
    "apps/api/app/modules/agent/pipeline.py",
    "apps/api/app/modules/agent/answers.py",
    "apps/api/app/modules/assessment/question_gen.py",
    "apps/api/app/modules/generation/service.py",
    "apps/api/app/modules/generation/fake.py",
    "apps/api/app/api/health.py",
    "supabase/migrations/0025_shared_request_quota.sql",
)


def source_hashes():
    return {
        name: hashlib.sha256((REPOSITORY / name).read_bytes()).hexdigest() for name in SOURCE_PATHS
    }


def runtime_tree_hashes():
    return {
        str(path.relative_to(REPOSITORY)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((REPOSITORY / "apps/api/app").rglob("*.py"))
    }


def verify_sources(environment):
    try:
        expected = json.loads(environment.get("D1_HTTP_SOURCE_MANIFEST_JSON", ""))
    except (TypeError, ValueError):
        raise TargetGuardError("ROOT_SOURCE_MANIFEST_REQUIRED") from None
    require(
        isinstance(expected, dict) and set(expected) == set(SOURCE_PATHS),
        "ROOT_SOURCE_MANIFEST_REQUIRED",
    )
    require(
        all(
            isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value)
            for value in expected.values()
        ),
        "ROOT_SOURCE_MANIFEST_REQUIRED",
    )
    require(source_hashes() == expected, "SOURCE_HASH_MISMATCH")
    # Kaynak hash'i tek başına eski yerel deque davranışını yeni kabul ettirmesin.
    for path in SOURCE_PATHS[:2]:
        source = (REPOSITORY / path).read_text()
        require(
            "from app.core.request_quota import take_request_slot" in source
            and "admission = await take_request_slot(" in source,
            "QUOTA_PATCH_NOT_INTEGRATED",
        )
    return expected


def application_dsn(environment):
    database = environment.get("D1_TEST_DB_NAME", "")
    require(
        bool(re.fullmatch(r"dou_synapse_d1_[a-z0-9_]{1,30}", database)),
        "EXPLICIT_D1_DATABASE_REQUIRED",
    )
    expected = expected_target(environment, database)
    raw = environment.get("D1_HTTP_APP_DSN", "")
    try:
        value = urlsplit(raw)
        require(value.scheme == "postgresql+psycopg", "PSYCOPG_DSN_REQUIRED")
        require(
            "?" not in raw and "#" not in raw and not any(c.isspace() for c in raw),
            "DSN_ROUTING_OPTIONS_REFUSED",
        )
        host = numeric_loopback(value.hostname)
        require(
            value.port == expected.server_port and host == expected.server_address,
            "ROOT_EXPECTED_ENDPOINT_MISMATCH",
        )
        require(
            value.path == "/" + database and unquote(value.username or "") == "dou_app",
            "EXACT_APP_ROLE_AND_DATABASE_REQUIRED",
        )
        password = None if value.password is None else unquote(value.password)
        require(password is None or "\x00" not in password, "INVALID_CONNECTION_INPUT")
    except (ValueError, TypeError):
        raise TargetGuardError("INVALID_CONNECTION_INPUT") from None
    credential = "dou_app" + ("" if password is None else ":" + quote(password, safe=""))
    address = "[" + host + "]" if ":" in host else host
    return (
        f"postgresql+psycopg://{credential}@{address}:{expected.server_port}/{database}"
        f"?hostaddr={quote(host, safe='')}"
    )


def validate_app_identity(row, expected):
    for key in ("database", "database_oid", "server_version_num", "server_port"):
        require(row[key] == getattr(expected, key), "APP_CONNECTED_TARGET_MISMATCH")
    require(
        numeric_loopback(row["server_address"]) == expected.server_address,
        "APP_CONNECTED_TARGET_MISMATCH",
    )
    numeric_loopback(row["client_address"])
    require(row["role"] == row["session_role"] == "dou_app", "APP_ROLE_MISMATCH")
    require(row["rolsuper"] is False and row["rolbypassrls"] is False, "APP_RLS_FLAGS_INVALID")
    require(row["row_security"] == "on", "APP_RLS_DISABLED")


APP_IDENTITY_SQL = """SELECT pg_catalog.current_database() AS database,
    current_user AS role, session_user AS session_role, r.rolsuper, r.rolbypassrls,
    d.oid::bigint AS database_oid, pg_catalog.host(pg_catalog.inet_server_addr()) AS server_address,
    pg_catalog.inet_server_port() AS server_port,
    pg_catalog.host(pg_catalog.inet_client_addr()) AS client_address,
    pg_catalog.current_setting('server_version_num')::integer AS server_version_num,
    pg_catalog.current_setting('row_security') AS row_security
    FROM pg_catalog.pg_roles r CROSS JOIN pg_catalog.pg_database d
    WHERE r.rolname=current_user AND d.datname=pg_catalog.current_database()"""


def private_passfile(path):
    value = Path(path)
    require(
        value.is_absolute() and value.parent.resolve().is_relative_to(Path("/private/tmp")),
        "PRIVATE_PASSFILE_REQUIRED",
    )
    info = value.lstat()
    require(
        stat.S_ISREG(info.st_mode)
        and info.st_uid == os.getuid()
        and stat.S_IMODE(info.st_mode) == 0o600
        and info.st_size == 0,
        "PRIVATE_PASSFILE_REQUIRED",
    )
    return str(value)


def child_environment(environment, output, process_index, socket_fd):
    dsn = application_dsn(environment)
    verify_sources(environment)
    # Allowlist: provider/admin/worker sırrı, PG service veya .env mirası yok.
    result = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": str(REPOSITORY / "apps/api") + os.pathsep + str(Path(__file__).parent),
        "PYTHONDONTWRITEBYTECODE": "1",
        "ENVIRONMENT": "local",
        "DEV_AUTH_ENABLED": "true",
        "DATABASE_URL": dsn,
        "WORKER_DATABASE_URL": dsn,
        "EMBEDDING_PROVIDER": "hashing",
        "EMBEDDING_WARMUP_ENABLED": "false",
        "LLM_FAKE_PROVIDER": "true",
        "COURSE_AGENT_ENABLED": "true",
        "DB_POOL_SIZE": "5",
        "DB_MAX_OVERFLOW": "0",
        "CHAT_RATE_LIMIT_REQUESTS": "20",
        "CHAT_RATE_LIMIT_WINDOW_SECONDS": "60",
        "QUESTION_GEN_RATE_LIMIT_REQUESTS": "5",
        "QUESTION_GEN_RATE_LIMIT_WINDOW_SECONDS": "300",
        "STORAGE_BACKEND": "local",
        "STORAGE_ROOT": str(output / "storage"),
        "D1_TEST_DB_NAME": environment["D1_TEST_DB_NAME"],
        "D1_EXPECTED_TARGET_JSON": environment["D1_EXPECTED_TARGET_JSON"],
        "D1_HTTP_SOURCE_MANIFEST_JSON": environment["D1_HTTP_SOURCE_MANIFEST_JSON"],
        "D1_HTTP_APP_DSN": environment["D1_HTTP_APP_DSN"],
        "D1_HTTP_OUTPUT": str(output),
        "D1_HTTP_INDEX": str(process_index),
        "D1_HTTP_SOCKET_FD": str(socket_fd),
        # Doğrulanmış özel boş dosya; örtük ~/.pgpass yüklemesi yok.
        "PGPASSFILE": private_passfile(output / "empty.pgpass"),
        "HF_HUB_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HTTP_PROXY": "http://127.0.0.1:9",
        "HTTPS_PROXY": "http://127.0.0.1:9",
        "ALL_PROXY": "http://127.0.0.1:9",
        "NO_PROXY": "127.0.0.1,::1",
    }
    return result
