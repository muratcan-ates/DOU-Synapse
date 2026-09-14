#!/bin/sh
set -eu
# Tek PostgreSQL oturumu kilidi, göçleri ve başarı defterini birlikte yönetir.
exec "${DOU_MIGRATE_PYTHON:-python3}" - "$0" "$@" <<'PY'
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from urllib.parse import parse_qsl, unquote, urlsplit


def fail(message):
    print(f"HATA: {message}", file=sys.stderr)
    raise SystemExit(1)


def literal(value):
    return "'" + value.replace("'", "''") + "'"


script = Path(sys.argv[1]).resolve()
parser = argparse.ArgumentParser(
    description="Göçleri sırasıyla uygular; DATABASE_URL veya libpq PG* ortamını kullanır."
)
parser.add_argument(
    "--dry-run", action="store_true", help="Veritabanını değiştirmeden yalnız bekleyen dosyaları listeler."
)
parser.add_argument(
    "--migrations-dir", type=Path,
    default=script.parent.parent / "supabase" / "migrations",
    help="Göç dizini (varsayılan: depodaki supabase/migrations).",
)
args = parser.parse_args(sys.argv[2:])
psql = shutil.which("psql")
if psql is None:
    fail("psql bulunamadı; PostgreSQL istemcisini PATH içine ekleyin.")
if not args.migrations_dir.is_dir():
    fail("Göç dizini bulunamadı.")
paths = sorted(args.migrations_dir.glob("*.sql"))
if not paths:
    fail("Göç dizininde SQL dosyası yok.")
seen = set()
for path in paths:
    if not re.fullmatch(r"[0-9]{4}_[A-Za-z0-9][A-Za-z0-9_.-]*\.sql", path.name):
        fail(f"Geçersiz göç dosyası adı: {path.name}")
    version = path.name[:4]
    if version in seen:
        fail(f"Tekrarlanan göç sürümü: {version}")
    seen.add(version)

# URL komut satırına taşınmaz. Sırlar psql süreç argümanlarında görünmez.
env = os.environ.copy()
if env.get("DATABASE_URL"):
    if not env["DATABASE_URL"].startswith(("postgresql://", "postgres://")):
        fail("DATABASE_URL doğrudan PostgreSQL URL biçiminde olmalıdır.")
    # libpq, PGDATABASE içindeki URL'yi veritabanı ADI sanır ("database
    # 'postgresql://…' does not exist") — ilk gerçek koşuda böyle düştü
    # (14 Eylül 2026, dou_demo). URL, parçalarına ayrılıp libpq'nun kendi
    # PG* değişkenlerine dağıtılır; sırlar yine yalnız ortamda kalır, argv'ye çıkmaz.
    parts = urlsplit(env.pop("DATABASE_URL"))
    if parts.hostname:
        env["PGHOST"] = parts.hostname
    if parts.port:
        env["PGPORT"] = str(parts.port)
    if parts.username:
        env["PGUSER"] = unquote(parts.username)
    if parts.password:
        env["PGPASSWORD"] = unquote(parts.password)
    database = unquote(parts.path.lstrip("/"))
    if not database:
        fail("DATABASE_URL veritabanı adı içermeli (…/<veritabanı>).")
    env["PGDATABASE"] = database
    for key, value in parse_qsl(parts.query):
        if key in {"sslmode", "sslrootcert", "options", "application_name", "connect_timeout"}:
            env["PG" + key.upper()] = value
env.setdefault("PGCONNECT_TIMEOUT", "15")

with tempfile.TemporaryDirectory(prefix="dou-migrate-") as directory:
    root = Path(directory)
    inventory = []
    try:
        for path in paths:
            # Bir kez okunan aynı baytlar hem özeti hem uygulanacak dosyayı üretir.
            content = path.read_bytes()
            snapshot = root / path.name
            snapshot.write_bytes(content)
            snapshot.chmod(0o400)
            inventory.append((path.name[:4], hashlib.sha256(content).hexdigest(), path.name))
    except OSError:
        fail("Göçlerin değişmez geçici kopyası oluşturulamadı.")
    manifest = ",\n".join(
        f"({literal(version)}, {literal(digest)})" for version, digest, _ in inventory
    )
    commands = [
        r"\set ON_ERROR_STOP on",
        "SET client_min_messages = warning;",
        "SET standard_conforming_strings = on;",
    ]
    if args.dry_run:
        commands.append("SET default_transaction_read_only = on;")
    commands += [
        # Session kilidi COMMIT ile düşmez; psql kapanınca hata halinde de bırakılır.
        "SELECT pg_advisory_lock(17372799124499562) \\g /dev/null",
        "SELECT to_regclass('app.schema_migrations') IS NOT NULL AS has_ledger \\gset",
    ]
    if not args.dry_run:
        commands += [
            "CREATE SCHEMA IF NOT EXISTS app;",
            "CREATE TABLE IF NOT EXISTS app.schema_migrations (",
            "  version text PRIMARY KEY CHECK (version ~ '^[0-9]{4}$'),",
            "  applied_at timestamptz NOT NULL DEFAULT clock_timestamp(),",
            "  sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$')",
            ");",
            r"\set has_ledger true",
        ]
    commands += [
        r"\if :has_ledger",
        "DO $migration_inventory$",
        "DECLARE invalid_version text;",
        "BEGIN",
        f"  WITH files(version, sha256) AS (VALUES {manifest})",
        "  SELECT ledger.version INTO invalid_version",
        "  FROM app.schema_migrations AS ledger LEFT JOIN files USING (version)",
        "  WHERE files.version IS NULL OR files.sha256 IS DISTINCT FROM ledger.sha256",
        "  ORDER BY ledger.version LIMIT 1;",
        "  IF invalid_version IS NOT NULL THEN",
        "    RAISE EXCEPTION 'Uygulanmış göç eksik veya SHA-256 değişmiş: %', invalid_version;",
        "  END IF;",
        "END $migration_inventory$;",
        r"\endif",
        r"\set any_pending false",
    ]
    for version, digest, name in inventory:
        commands += [
            r"\if :has_ledger",
            f"SELECT NOT EXISTS (SELECT 1 FROM app.schema_migrations WHERE version = {literal(version)}) AS pending \\gset",
            r"\else",
            r"\set pending true",
            r"\endif",
            r"\if :pending",
            r"\set any_pending true",
        ]
        if args.dry_run:
            commands.append(r"\echo " + name)
        else:
            commands += [
                r"\echo Uygulanıyor: " + name,
                r"\ir " + literal(name),
                # Açık başarılı işlem varsa önce kalıcılaştırılır. -1 sarmalı yoktur;
                # CREATE INDEX CONCURRENTLY gibi işlem dışı SQL aynen çalışabilir.
                "COMMIT;",
                f"INSERT INTO app.schema_migrations (version, sha256) VALUES ({literal(version)}, {literal(digest)});",
                r"\echo Uygulandı: " + name,
            ]
        commands.append(r"\endif")
    if not args.dry_run:
        commands += [r"\if :any_pending", r"\else", r"\echo Bekleyen göç yok.", r"\endif"]
    driver = root / "runner.sql"
    driver.write_text("\n".join(commands) + "\n", encoding="utf-8")
    child = None

    def interrupt(signum, _frame):
        if child is not None and child.poll() is None:
            child.send_signal(signum)
            child.wait()
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    try:
        child = subprocess.Popen(
            [psql, "-X", "-w", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "--file", str(driver)],
            env=env,
        )
        code = child.wait()
    except OSError:
        fail("psql başlatılamadı.")
    raise SystemExit(code if code >= 0 else 128 - code)
PY
