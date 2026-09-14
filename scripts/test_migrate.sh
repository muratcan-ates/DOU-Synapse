#!/bin/sh
set -eu
# Yalnız bu koşumun yarattığı dou_l3_migrate_* veritabanları kaldırılır.
exec "${DOU_MIGRATE_PYTHON:-python3}" - "$0" "$@" <<'PY'
import hashlib
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import time


script = Path(sys.argv[1]).resolve()
repository = script.parent.parent
runner = repository / "scripts" / "migrate.sh"
migrations = repository / "supabase" / "migrations"
psql = shutil.which("psql")
if psql is None:
    sys.exit("HATA: psql bulunamadı; PostgreSQL 16 ve vector uzantısı gerekir.")
if len(sys.argv) > 2:
    sys.exit("HATA: Test argüman almaz; bağlantı için libpq PG* ortamını kullanın.")
environment = os.environ.copy()
environment.pop("DATABASE_URL", None)
environment["PGDATABASE"] = environment.get("TEST_MIGRATE_ADMIN_DATABASE", "postgres")
environment.setdefault("PGCONNECT_TIMEOUT", "15")
prefix = f"dou_l3_migrate_{os.getpid()}_{secrets.token_hex(3)}"
created = []
children = []


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def sql(statement, database=None):
    env = environment.copy()
    if database:
        env["PGDATABASE"] = database
    result = subprocess.run(
        [psql, "-X", "-w", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1"],
        input=statement, text=True, capture_output=True, env=env, check=False,
    )
    if result.returncode:
        raise AssertionError(f"SQL doğrulaması başarısız: {result.stderr}")
    return result.stdout.strip()


def create_database(label):
    name = f"{prefix}_{label}"
    sql(f'CREATE DATABASE "{name}" TEMPLATE template0;')
    created.append(name)
    return name


def start(database, directory=migrations, dry_run=False):
    env = environment.copy()
    env["PGDATABASE"] = database
    env["PGAPPNAME"] = f"{prefix}_runner"
    command = [str(runner), "--migrations-dir", str(directory)]
    if dry_run:
        command.append("--dry-run")
    child = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    children.append(child)
    return child


def finish(child, success=True):
    out, err = child.communicate(timeout=90)
    require((child.returncode == 0) == success, f"Beklenmeyen runner sonucu {child.returncode}: {out}\n{err}")
    return out.strip()


def run(database, directory=migrations, dry_run=False, success=True):
    return finish(start(database, directory, dry_run), success)


def ledger(database):
    return sql("SELECT version || ':' || sha256 || ':' || applied_at::text FROM app.schema_migrations ORDER BY version;", database)


def report(message):
    print(f"PASS: {message}", flush=True)


def write(directory, name, content):
    path = directory / name
    path.write_text(content, encoding="utf-8")
    return path


try:
    require(int(sql("SHOW server_version_num;")) >= 160000, "PostgreSQL 16 veya üzeri gerekir.")
    require(sql("SELECT count(*) FROM pg_available_extensions WHERE name = 'vector';") == "1", "vector uzantısı kurulu değil.")
    originals = sorted(migrations.glob("*.sql"))
    require(len(originals) > 1, "N-1 testi için birden çok göç gerekir.")
    full = create_database("full")
    out = run(full, dry_run=True)
    require(out.splitlines() == [path.name for path in originals], "Temiz kuru koşu tüm bekleyenleri sırayla listelemeli.")
    require(sql("SELECT count(*) FROM pg_namespace WHERE nspname = 'app';", full) == "0", "Kuru koşu app şemasını oluşturmamalı.")
    report("Temiz veritabanında kuru koşu salt okunur ve yalnız bekleyen dosyaları listeler.")

    run(full)
    expected = "\n".join(f"{path.name[:4]}:{hashlib.sha256(path.read_bytes()).hexdigest()}" for path in originals)
    actual = sql("SELECT version || ':' || sha256 FROM app.schema_migrations ORDER BY version;", full)
    require(actual == expected, "Temiz kurulumun sürüm ve SHA-256 kayıtları dosyalarla eşleşmeli.")
    require(sql("SELECT extname FROM pg_extension WHERE extname = 'vector';", full) == "vector", "Gerçek depo göçleri vector uzantısını kurmalı.")
    report("Temiz veritabanına depodaki tüm göçler uygulanır ve gerçek özetleri kaydedilir.")

    previous = ledger(full)
    require(run(full) == "Bekleyen göç yok.", "İkinci koşum no-op olmalı.")
    require(run(full, dry_run=True) == "", "Güncel kuru koşu boş olmalı.")
    require(ledger(full) == previous, "No-op ve kuru koşu başarı zamanlarını değiştirmemeli.")
    report("İkinci koşum no-op; güncel kuru koşu boş ve defter değişmez.")

    with tempfile.TemporaryDirectory(prefix="dou-migrate-tests-") as temporary:
        root = Path(temporary)
        copied = root / "upgrade"
        copied.mkdir()
        for path in originals[:-1]:
            shutil.copyfile(path, copied / path.name)
        upgrade = create_database("upgrade")
        run(upgrade, copied)
        before = ledger(upgrade)
        require(len(before.splitlines()) == len(originals) - 1, "N-1 kurulumu eksik son göçü kaydetmemeli.")
        shutil.copyfile(originals[-1], copied / originals[-1].name)
        require(run(upgrade, copied, dry_run=True) == originals[-1].name, "Kuru koşu yalnız N göçünü göstermeli.")
        require(ledger(upgrade) == before, "Bekleyen göç kuru koşuda uygulanmamalı.")
        out = run(upgrade, copied)
        require(out.splitlines() == [f"Uygulanıyor: {originals[-1].name}", f"Uygulandı: {originals[-1].name}"], "Yükseltme yalnız son dosyayı uygulamalı.")
        require(len(ledger(upgrade).splitlines()) == len(originals), "N-1 yükseltmesi son göçü kaydetmeli.")
        require(ledger(upgrade).startswith(before + "\n"), "Önceki göç kayıtları korunmalı.")
        report("N-1 → N yükseltmesi ve bekleyen tek göç için salt okunur kuru koşu.")

        changed = copied / originals[0].name
        original_content = changed.read_bytes()
        changed.write_bytes(original_content + b"\n-- Degisim sinamasi\n")
        baseline = ledger(upgrade)
        run(upgrade, copied, success=False)
        run(upgrade, copied, dry_run=True, success=False)
        require(ledger(upgrade) == baseline, "Özet sapmasında defter değişmemeli.")
        changed.write_bytes(original_content)
        changed.unlink()
        run(upgrade, copied, success=False)
        run(upgrade, copied, dry_run=True, success=False)
        require(ledger(upgrade) == baseline, "Eksik geçmiş dosyada defter değişmemeli.")
        report("Uygulanmış dosyanın değişmesi veya kaybolması normal ve kuru koşuyu durdurur.")

        broken_dir = root / "broken"
        broken_dir.mkdir()
        write(broken_dir, "0001_probe.sql", "CREATE TABLE probe (id integer PRIMARY KEY);\n")
        bad = write(broken_dir, "0002_failure.sql", "BEGIN; INSERT INTO probe VALUES (1); SELECT missing_migration_function(); COMMIT;\n")
        write(broken_dir, "0003_later.sql", "INSERT INTO probe VALUES (3);\n")
        broken = create_database("broken")
        run(broken, broken_dir, success=False)
        require(sql("SELECT string_agg(version, ',' ORDER BY version) FROM app.schema_migrations;", broken) == "0001", "Başarısız ve sonraki göçler kaydedilmemeli.")
        require(sql("SELECT count(*) FROM probe;", broken) == "0", "Başarısız açık işlem geri alınmalı; sonraki dosya koşmamalı.")
        bad.write_text("INSERT INTO probe VALUES (2);\n", encoding="utf-8")
        run(broken, broken_dir)
        require(sql("SELECT string_agg(id::text, ',' ORDER BY id) FROM probe;", broken) == "2,3", "Hata sonrasında kilit bırakılmalı ve düzeltilen bekleyen göç çalışmalı.")
        report("Bozuk SQL rc≠0 döndürür, başarı kaydı oluşturmaz ve kilidi bırakır.")

        outside_dir = root / "outside"
        outside_dir.mkdir()
        write(outside_dir, "0001_outside.sql", "CREATE TABLE outside_probe (id integer); CREATE INDEX CONCURRENTLY outside_probe_idx ON outside_probe (id);\n")
        outside = create_database("outside")
        run(outside, outside_dir)
        require(sql("SELECT indisvalid FROM pg_index WHERE indexrelid = 'outside_probe_idx'::regclass;", outside) == "t", "İşlem dışı indeks kurulumu geçerli olmalı.")
        report("CREATE INDEX CONCURRENTLY tek işlem sarmalı olmadan çalışır.")

        concurrent_dir = root / "concurrent"
        concurrent_dir.mkdir()
        write(concurrent_dir, "0001_concurrent.sql", "CREATE TABLE concurrent_probe (id integer PRIMARY KEY); SELECT pg_sleep(1); INSERT INTO concurrent_probe VALUES (1);\n")
        concurrent = create_database("concurrent")
        first = start(concurrent, concurrent_dir)
        # İlk runner kilidi tutana kadar ölçülen durumu bekle; zamanlama varsayımı yok.
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            held = sql(f"SELECT count(*) FROM pg_locks l JOIN pg_stat_activity a ON a.pid = l.pid WHERE l.locktype = 'advisory' AND l.granted AND a.datname = '{concurrent}';")
            if held == "1":
                break
            require(first.poll() is None, "İlk eşzamanlı runner kilit gözlenmeden kapandı.")
            time.sleep(0.02)
        else:
            raise AssertionError("İlk runner advisory kilidi süre içinde gözlenmedi.")
        second = start(concurrent, concurrent_dir)
        first_output = finish(first)
        second_output = finish(second)
        require("Uygulandı:" in first_output and second_output == "Bekleyen göç yok.", "İkinci runner bekleyip güncel defteri okumalı.")
        require(sql("SELECT count(*) FROM concurrent_probe;", concurrent) == "1", "Eşzamanlı koşum göçü bir kez uygulamalı.")
        require(len(ledger(concurrent).splitlines()) == 1, "Eşzamanlı koşum tek başarı kaydı üretmeli.")
        report("İki gerçek runner tek oturum advisory kilidiyle seri çalışır.")
    print("PASS: Göç runner kabul kontrolleri tamamlandı.", flush=True)
except (AssertionError, OSError, subprocess.TimeoutExpired) as error:
    print(f"FAIL: {error}", file=sys.stderr)
    sys.exit(1)
finally:
    for child in children:
        if child.poll() is None:
            child.terminate()
            try:
                child.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.communicate()
    for database in reversed(created):
        # İsimler yalnız yerel rastgele koşum önekinden üretilir; mevcut DB seçilmez.
        try:
            sql(f'DROP DATABASE "{database}" WITH (FORCE);')
        except AssertionError as error:
            print(f"HATA: Test veritabanı temizlenemedi: {database}: {error}", file=sys.stderr)
            raise
PY
