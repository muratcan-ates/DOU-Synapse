#!/bin/sh
# Yedek/geri yükleme tatbikatı — gerçek yerel PostgreSQL 16 üstünde uçtan uca.
#
# Neden var: Supabase Free planında PITR YOKTUR; kurtarma planı haftalık mantıksal
# export'a dayanır. "Export alınıyor" tek başına kurtarma kanıtı değildir — kanıt,
# yedekten gerçekten dönülebildiğini ölçen bir tatbikattır. Bu betik onu üretir:
# küçük bir kaynak veritabanı kurar, yedekler, kaynağı DÜŞÜRÜR, yeni ve boş bir
# hedefe geri yükler ve üç şeyi ölçer:
#   (a) public şemadaki tabloların satır sayıları birebir aynı,
#   (b) arşiv TOC'unda `EXTENSION ... vector` var (pgvector arşive girdi),
#   (c) aynı dense arama aynı sırayı döndürüyor (vektörler gerçekten geri geldi).
#
# TEK BAŞINA KOŞ. Geri yükleme, hedefi bakım bağlantısından kısa kilit/ifade
# zaman aşımlarıyla (5 s / 15 s) çitler ve yeniden açar; aynı sunucuda başka
# ağır iş (ör. paralel pytest, conftest'in DROP/CREATE DATABASE'i) koşarken
# yeniden açma adımı zaman aşımına düşebilir ve betik
# RESTORE_COMMITTED_FENCE_REOPEN_UNCONFIRMED ile kırmızı yanar (14 Eylül'de
# ölçüldü: yük altında kırmızı, tek başına yeşil). Bu bir kusur değil, çitin
# tasarımı: yarım açılmış hedef sessizce kabul edilmez.
#
# Kapsam sınırı: bu bir YEREL tatbikattır. Dosya deposu, kimlik sağlayıcısı,
# şifreleme, korunan dış kopya ve saklama/imha politikası kapsam dışıdır; hosted
# hedefte kabul ayrıca gerekir (bkz. docs/recovery.md).
#
# Çıkış kodları: 0 tatbikat geçti · 2 tatbikat düştü · 3 ön koşul yok (not-run).
# Betik kendi kurduğu veritabanlarını ve özel paketi siler. DOU_DRILL_KEEP=1
# verilirse paket incelenmek üzere bırakılır — içinde kişisel veri olabilir.
set -eu

REPO=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
HOST=${DOU_DRILL_HOST:-127.0.0.1}
PORT=${DOU_DRILL_PORT:-5432}
PGBIN=${DOU_DRILL_PG_BIN:-/opt/homebrew/opt/postgresql@16/bin}
RECOVERY_PYTHON=${DOU_RECOVERY_PYTHON:-$REPO/apps/api/.venv/bin/python}
DBUSER=${DOU_DRILL_PGUSER:-$(id -un)}
MAINTENANCE_DB=${DOU_DRILL_MAINTENANCE_DB:-postgres}
PREFIX=${DOU_DRILL_PREFIX:-dou_drill}
SOURCE_DB="${PREFIX}_src_$$"
TARGET_DB="${PREFIX}_tgt_$$"
WORK=""

skip() { printf 'drill: not-run — %s\n' "$1" >&2; exit 3; }
fail() { printf 'drill: FAILED — %s\n' "$1" >&2; exit 2; }

psql_run() {
    db=$1
    shift
    "$PGBIN/psql" -X -q -v ON_ERROR_STOP=1 -h "$HOST" -p "$PORT" -U "$DBUSER" -d "$db" "$@"
}

psql_value() {
    db=$1
    shift
    "$PGBIN/psql" -X -q -tA -v ON_ERROR_STOP=1 -h "$HOST" -p "$PORT" -U "$DBUSER" -d "$db" "$@"
}

# Aynı ölçüm iki veritabanında da AYNI sorguyla alınır; farklı sorgu farklı
# sonucu "eşit" gösterebilirdi.
row_counts() {
    psql_value "$1" -c "SELECT coalesce(string_agg(t.relname || '=' || t.rows::text, ',' ORDER BY t.relname), '') FROM (SELECT c.relname, (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM %I.%I', n.nspname, c.relname), false, true, '')))[1]::text::bigint AS rows FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relkind = 'r' AND n.nspname = 'public') t"
}

dense_probe() {
    psql_value "$1" -c "SELECT string_agg(rank || ':' || id || ':' || label, ',' ORDER BY rank) FROM (SELECT row_number() OVER (ORDER BY embedding <-> '[1,0,0]', id) AS rank, id, label FROM drill_chunks ORDER BY embedding <-> '[1,0,0]', id LIMIT 3) d"
}

drop_database() {
    "$PGBIN/psql" -X -q -h "$HOST" -p "$PORT" -U "$DBUSER" -d "$MAINTENANCE_DB" \
        -c "ALTER DATABASE \"$1\" ALLOW_CONNECTIONS true" >/dev/null 2>&1 || true
    "$PGBIN/psql" -X -q -h "$HOST" -p "$PORT" -U "$DBUSER" -d "$MAINTENANCE_DB" \
        -c "DROP DATABASE IF EXISTS \"$1\"" >/dev/null 2>&1 || true
}

cleanup() {
    status=$?
    drop_database "$TARGET_DB"
    drop_database "$SOURCE_DB"
    if [ -n "$WORK" ]; then
        if [ "${DOU_DRILL_KEEP:-0}" = "1" ]; then
            printf 'drill: paket bırakıldı (kişisel veri içerebilir): %s\n' "$WORK" >&2
        else
            rm -rf "$WORK"
        fi
    fi
    exit "$status"
}

# --- Ön koşullar: eksikse tatbikat "geçti" demez, not-run der -----------------

for tool in psql pg_dump pg_restore; do
    [ -x "$PGBIN/$tool" ] || skip "PostgreSQL 16 istemci aracı yok: $PGBIN/$tool"
done
case "$("$PGBIN/psql" --version 2>/dev/null || true)" in
    *" 16."*) ;;
    *) skip "PostgreSQL 16 istemcisi gerekli: $PGBIN/psql" ;;
esac
[ -x "$RECOVERY_PYTHON" ] || skip "psycopg çalışma zamanı yok: $RECOVERY_PYTHON"
"$RECOVERY_PYTHON" -c 'import psycopg' >/dev/null 2>&1 || skip "psycopg içe aktarılamadı"
SUPERUSER=$("$PGBIN/psql" -X -q -tA -h "$HOST" -p "$PORT" -U "$DBUSER" -d "$MAINTENANCE_DB" \
    -c "SELECT rolsuper FROM pg_roles WHERE rolname = current_user" 2>/dev/null || true)
[ "$SUPERUSER" = "t" ] || skip "$HOST:$PORT üstünde DBA superuser bağlantısı gerekli"
VECTOR=$(psql_value "$MAINTENANCE_DB" -c "SELECT count(*) FROM pg_available_extensions WHERE name = 'vector'")
[ "$VECTOR" = "1" ] || skip "sunucuda pgvector eklentisi yok"

trap cleanup EXIT
WORK=$(mktemp -d)
# macOS'ta /var bir sembolik bağdır; paket yolunda sembolik bağ bileşeni olursa
# recovery.py paketi haklı olarak reddeder.
WORK=$(CDPATH= cd -- "$WORK" && pwd -P)
chmod 700 "$WORK"
BUNDLE="$WORK/bundle"

# --- 1. Küçük kaynak veritabanı ----------------------------------------------

psql_run "$MAINTENANCE_DB" -c "CREATE DATABASE \"$SOURCE_DB\" TEMPLATE template0"
psql_run "$SOURCE_DB" <<'SQL'
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE drill_chunks (
    id        integer PRIMARY KEY,
    label     text NOT NULL,
    embedding vector(3) NOT NULL
);

CREATE TABLE drill_notes (
    id      integer PRIMARY KEY,
    chunk_id integer NOT NULL REFERENCES drill_chunks(id),
    body    text NOT NULL
);

INSERT INTO drill_chunks (id, label, embedding) VALUES
    (1, 'kanit-bir',  '[1,0,0]'),
    (2, 'kanit-iki',  '[0.9,0.1,0]'),
    (3, 'kanit-uc',   '[0,1,0]'),
    (4, 'kanit-dort', '[0,0,1]');

INSERT INTO drill_notes (id, chunk_id, body) VALUES
    (1, 1, 'birinci not'),
    (2, 3, 'ikinci not');

CREATE INDEX drill_chunks_embedding_idx ON drill_chunks USING hnsw (embedding vector_l2_ops);
ANALYZE drill_chunks;
SQL

BEFORE_COUNTS=$(row_counts "$SOURCE_DB")
BEFORE_DENSE=$(dense_probe "$SOURCE_DB")
[ -n "$BEFORE_DENSE" ] || fail "kaynak dense araması boş döndü"

# --- 2. Yedek ----------------------------------------------------------------

DOU_RECOVERY_PYTHON="$RECOVERY_PYTHON" \
DOU_RECOVERY_PG_BIN="$PGBIN" \
DOU_BACKUP_PGHOST="$HOST" \
DOU_BACKUP_PGPORT="$PORT" \
DOU_BACKUP_PGDATABASE="$SOURCE_DB" \
DOU_BACKUP_PGUSER="$DBUSER" \
    "$REPO/scripts/backup.sh" --bundle "$BUNDLE" --repository "$REPO" --execute \
    > "$WORK/backup.json" || fail "yedek alınamadı"

SOURCE_SHA=$("$RECOVERY_PYTHON" -c \
    'import json,sys;print(json.load(open(sys.argv[1]))["source_identity_sha256"])' \
    "$WORK/backup.json") || fail "yedek makbuzu okunamadı"
[ -n "$SOURCE_SHA" ] || fail "kaynak kimliği makbuzda yok"

# (b) pgvector arşivin kendisinde mi — geri yüklemeden önce okunur.
"$PGBIN/pg_restore" --list "$BUNDLE/database.dump" > "$WORK/toc.txt" || fail "arşiv TOC'u okunamadı"
grep -q 'EXTENSION.*vector' "$WORK/toc.txt" || fail "arşivde EXTENSION vector girdisi yok"

# --- 3. Kaynağı düşür (kayıp benzetimi) --------------------------------------

psql_run "$MAINTENANCE_DB" -c "DROP DATABASE \"$SOURCE_DB\""

# --- 4. Yeni, boş hedefe geri yükle ------------------------------------------

psql_run "$MAINTENANCE_DB" -c "CREATE DATABASE \"$TARGET_DB\" TEMPLATE template0"
DOU_RECOVERY_PYTHON="$RECOVERY_PYTHON" \
DOU_RECOVERY_PG_BIN="$PGBIN" \
DOU_RESTORE_PGHOST="$HOST" \
DOU_RESTORE_PGPORT="$PORT" \
DOU_RESTORE_PGDATABASE="$TARGET_DB" \
DOU_RESTORE_PGUSER="$DBUSER" \
DOU_MAINTENANCE_PGHOST="$HOST" \
DOU_MAINTENANCE_PGPORT="$PORT" \
DOU_MAINTENANCE_PGDATABASE="$MAINTENANCE_DB" \
DOU_MAINTENANCE_PGUSER="$DBUSER" \
    "$REPO/scripts/restore.sh" --bundle "$BUNDLE" --expected-source "$SOURCE_SHA" \
    --trust-own-backup --fence-empty-target --execute \
    > "$WORK/restore.json" || fail "geri yükleme tamamlanmadı"

# --- 5. Ölçüm ----------------------------------------------------------------

AFTER_COUNTS=$(row_counts "$TARGET_DB")
[ "$AFTER_COUNTS" = "$BEFORE_COUNTS" ] || fail "satır sayıları eşleşmedi ($BEFORE_COUNTS -> $AFTER_COUNTS)"

AFTER_DENSE=$(dense_probe "$TARGET_DB")
[ "$AFTER_DENSE" = "$BEFORE_DENSE" ] || fail "dense arama sonucu değişti ($BEFORE_DENSE -> $AFTER_DENSE)"

INSTALLED=$(psql_value "$TARGET_DB" -c "SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
[ "$INSTALLED" = "1" ] || fail "geri yüklenen veritabanında pgvector kurulu değil"

printf 'drill: OK — satır sayıları eşit · arşivde EXTENSION vector · dense arama aynı\n'
