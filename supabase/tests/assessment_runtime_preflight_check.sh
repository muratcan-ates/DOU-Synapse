#!/usr/bin/env bash
#
# 0016 runtime-role contract kesiminin iki operasyon preflight'ini gercek
# baglantilarla kanitlar:
#   1. dou_app LOGIN onceden kapatilmadiysa migration fail-closed olur;
#   2. NOLOGIN sonrasi eski dou_app oturumu hala yasiyorsa migration yine durur.
#
# Rol cluster-genel oldugu icin script yalniz acik opt-in ile calisir. Her cikista
# dou_app'i NOLOGIN/PASSWORD NULL durumuna getirir ve benzersiz test DB'sini siler.

set -euo pipefail

if [[ "${ASSESSMENT_PREFLIGHT_ALLOW_ROLE_MUTATION:-}" != "1" ]]; then
    echo "HATA: cluster rol mutasyonu icin ASSESSMENT_PREFLIGHT_ALLOW_ROLE_MUTATION=1 gerekli." >&2
    exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PSQL="${PG_BIN:+${PG_BIN}/}psql"
CREATEDB="${PG_BIN:+${PG_BIN}/}createdb"
DROPDB="${PG_BIN:+${PG_BIN}/}dropdb"
TEST_DB="${1:-assessment_runtime_preflight_$$}"
PG_TEST_HOST="${PGHOST:-localhost}"
PG_TEST_PORT="${PGPORT:-5432}"
TEMP_PASSWORD="dou_app_preflight_only"
OUTPUT_DIR="$(mktemp -d)"
SLEEP_PID=""

if [[ ! "$TEST_DB" =~ ^assessment_runtime_preflight_[A-Za-z0-9_]+$ ]]; then
    echo "HATA: DB adi assessment_runtime_preflight_ ile baslamali." >&2
    exit 2
fi

cleanup() {
    if [[ -n "$SLEEP_PID" ]]; then
        kill "$SLEEP_PID" >/dev/null 2>&1 || true
        wait "$SLEEP_PID" >/dev/null 2>&1 || true
    fi
    "$PSQL" -X -q -d postgres \
        -c "ALTER ROLE dou_app NOLOGIN PASSWORD NULL" >/dev/null 2>&1 || true
    "$DROPDB" --if-exists --force "$TEST_DB" >/dev/null 2>&1 || true
    rm -rf "$OUTPUT_DIR"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

database_names=$("$PSQL" -X -lqtA -d postgres | cut -d'|' -f1)
if grep -Fxq "$TEST_DB" <<<"$database_names"; then
    echo "HATA: $TEST_DB zaten var; mevcut veritabanina dokunulmayacak." >&2
    exit 2
fi

"$CREATEDB" "$TEST_DB"
for migration in "${REPO_ROOT}"/supabase/migrations/*.sql; do
    if [[ "$(basename "$migration")" == 0016_* ]]; then
        break
    fi
    "$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$TEST_DB" -f "$migration"
done

# Vaka 1: migration, LOGIN kapatma gorevini kendi transaction'ina ertelemez.
"$PSQL" -X -q -d postgres \
    -c "ALTER ROLE dou_app LOGIN PASSWORD '${TEMP_PASSWORD}'"
if "$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$TEST_DB" \
    -f "${REPO_ROOT}/supabase/migrations/0016_assessment_integrity.sql" \
    >"${OUTPUT_DIR}/login.out" 2>&1; then
    echo "FAIL  runtime_preflight__login_onceden_kapatilmali" >&2
    exit 1
fi
if ! grep -Fq "dou_app must already be NOLOGIN before 0016" "${OUTPUT_DIR}/login.out"; then
    echo "FAIL  runtime_preflight__login_yanlis_nedenle_durdu" >&2
    sed -n '1,12p' "${OUTPUT_DIR}/login.out" >&2
    exit 1
fi
echo "PASS  runtime_preflight__login_onceden_kapatilmali"

# Vaka 2: gercek eski pool baglantisi acikken NOLOGIN'i ayri transaction'da
# commit et. Bu baglanti yasamaya devam eder ve migration onu pg_stat_activity'de
# gorerek durur.
PGPASSWORD="$TEMP_PASSWORD" "$PSQL" -X \
    -h "$PG_TEST_HOST" -p "$PG_TEST_PORT" -U dou_app -d "$TEST_DB" \
    -c "SELECT pg_sleep(30)" >"${OUTPUT_DIR}/old-pool.out" 2>&1 &
SLEEP_PID=$!

active_count=0
for _ in $(seq 1 50); do
    active_count=$("$PSQL" -X -At -d postgres -c \
        "SELECT count(*) FROM pg_stat_activity WHERE usename='dou_app' AND datname='${TEST_DB}'")
    if [[ "$active_count" -ge 1 ]]; then
        break
    fi
    sleep 0.1
done
if [[ "$active_count" -lt 1 ]]; then
    echo "FAIL  runtime_preflight__eski_pool_baglantisi_kurulamadi" >&2
    sed -n '1,12p' "${OUTPUT_DIR}/old-pool.out" >&2
    exit 1
fi

"$PSQL" -X -q -d postgres \
    -c "ALTER ROLE dou_app NOLOGIN PASSWORD NULL"
if "$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$TEST_DB" \
    -f "${REPO_ROOT}/supabase/migrations/0016_assessment_integrity.sql" \
    >"${OUTPUT_DIR}/active.out" 2>&1; then
    echo "FAIL  runtime_preflight__aktif_eski_pool_drain_edilmeli" >&2
    exit 1
fi
if ! grep -Fq "active dou_app sessions exist" "${OUTPUT_DIR}/active.out"; then
    echo "FAIL  runtime_preflight__aktif_pool_yanlis_nedenle_durdu" >&2
    sed -n '1,12p' "${OUTPUT_DIR}/active.out" >&2
    exit 1
fi
echo "PASS  runtime_preflight__aktif_eski_pool_drain_edilmeli"
