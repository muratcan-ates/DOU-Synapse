#!/usr/bin/env bash
# Önce gerçek çekirdek göçleri uygulanmış ayrı dou_l5* veritabanını verin.
# Her deneme aynı gerçek 0029'u transaction içinde kurar ve ROLLBACK ile bırakır.
set -euo pipefail

TEST_DB="${1:?Kullanım: rls_storage_mutation_check.sh dou_l5_storage_test}"
TEST_HOST="${PGHOST:-localhost}"
TEST_PORT="${PGPORT:-5432}"
case "$TEST_DB" in dou_l5*) ;; *) echo 'L5 test veritabanı adı gerekli.' >&2; exit 2 ;; esac
if [[ ! "$TEST_DB" =~ ^dou_l5[a-z0-9_]*$ ]]; then
    echo 'Geçersiz L5 test veritabanı adı.' >&2; exit 2
fi
case "$TEST_HOST" in localhost|127.0.0.1|::1) ;; *) echo 'Yalnız localhost test hedefi kabul edilir.' >&2; exit 2 ;; esac
if [[ ! "$TEST_PORT" =~ ^[0-9]+$ ]]; then echo 'Geçersiz test portu.' >&2; exit 2; fi
if [[ -n "${PGSERVICE:-}" || -n "${PGHOSTADDR:-}" ]]; then
    echo 'PGSERVICE veya PGHOSTADDR ile hedef değiştirme kabul edilmez.' >&2; exit 2
fi
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PSQL="${PG_BIN:+${PG_BIN}/}psql"
TEST_SQL="${REPO_ROOT}/supabase/tests/rls_storage.sql"
LOG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/dou-l5-storage.XXXXXX")"
trap 'rm -rf "$LOG_DIR"' EXIT
PSQL_ARGS=(-X -v ON_ERROR_STOP=1 -h "$TEST_HOST" -p "$TEST_PORT" -d "$TEST_DB")

run_baseline() {
    "$PSQL" "${PSQL_ARGS[@]}" -v storage_mutation=none -f "$TEST_SQL" > "$LOG_DIR/baseline.log" 2>&1 || return 1
    if ! grep -q '^L5_STORAGE_BASELINE_PASS$' "$LOG_DIR/baseline.log"; then
        cat "$LOG_DIR/baseline.log" >&2; return 1
    fi
}
if ! run_baseline; then cat "$LOG_DIR/baseline.log" >&2; exit 1; fi
for mutation in read insert delete update; do
    case "$mutation" in
        read) expected=read_nonmember ;;
        insert) expected=insert_student ;;
        delete) expected=delete_nonowner ;;
        update) expected=update_student ;;
    esac
    if "$PSQL" "${PSQL_ARGS[@]}" -v "storage_mutation=$mutation" -f "$TEST_SQL" > "$LOG_DIR/$mutation.log" 2>&1; then
        echo "Mutasyon yakalanmadı: $mutation" >&2; exit 1
    fi
    if ! grep -q "ERROR:.*L5_ASSERT:$expected$" "$LOG_DIR/$mutation.log"; then
        echo "Mutasyon beklenen iddiada düşmedi: $mutation" >&2
        cat "$LOG_DIR/$mutation.log" >&2; exit 1
    fi
    if ! run_baseline; then cat "$LOG_DIR/baseline.log" >&2; exit 1; fi
    echo "L5_STORAGE_MUTATION_KILLED:$mutation"
done
echo 'L5_STORAGE_MUTATIONS_PASS'
