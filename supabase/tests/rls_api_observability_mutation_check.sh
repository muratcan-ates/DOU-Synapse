#!/usr/bin/env bash
#
# 010 API observability guvenlik kanitinin kirmizi yanabildigini gosterir.
# Her mutasyon ayri gecici DB klonunda kosar; ortak gelistirme DB'sine dokunmaz.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEST_SQL="${REPO_ROOT}/supabase/tests/rls_api_observability.sql"
PSQL="${PG_BIN:+${PG_BIN}/}psql"
CREATEDB="${PG_BIN:+${PG_BIN}/}createdb"
DROPDB="${PG_BIN:+${PG_BIN}/}dropdb"
TEMPLATE_DB="${1:-rls_api_observability_local_$$}"

if [[ ! "$TEMPLATE_DB" =~ ^rls_api_observability_[A-Za-z0-9_]+$ ]]; then
    echo "HATA: DB adi rls_api_observability_ ile baslayan guvenli bir ad olmali." >&2
    exit 2
fi
if ((${#TEMPLATE_DB} > 63)); then
    echo "HATA: PostgreSQL DB adi 63 karakteri gecemez." >&2
    exit 2
fi
if "$PSQL" -X -lqtA -d postgres | cut -d'|' -f1 | grep -Fxq "$TEMPLATE_DB"; then
    echo "HATA: $TEMPLATE_DB zaten var; mevcut bir DB'ye dokunulmayacak." >&2
    exit 2
fi

created_databases=()
cleanup() {
    local index
    local database_name
    for ((index=${#created_databases[@]} - 1; index >= 0; index--)); do
        database_name="${created_databases[$index]}"
        "$DROPDB" --if-exists "$database_name" >/dev/null 2>&1 || true
    done
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

create_database() {
    local database_name="$1"
    shift
    "$CREATEDB" "$@" "$database_name"
    created_databases+=("$database_name")
}

drop_database_now() {
    "$DROPDB" "$1"
}

run_proof() {
    local database_name="$1"
    "$PSQL" -X -v ON_ERROR_STOP=1 -d "$database_name" -f "$TEST_SQL" 2>&1
}

run_mutation() {
    local sequence="$1"
    local mutation_name="$2"
    local mutation_sql="$3"
    local expected_assertion="$4"
    local scratch_db="rls_api_obs_mut_$$_${sequence}"
    local output

    create_database "$scratch_db" -T "$TEMPLATE_DB"
    "$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$scratch_db" -c "$mutation_sql"
    output="$(run_proof "$scratch_db")"
    drop_database_now "$scratch_db"

    if grep -Fq "FAIL  ${expected_assertion}" <<<"$output"; then
        printf 'YAKALANDI  %-45s -> %s\n' "$mutation_name" "$expected_assertion"
        return 0
    fi
    printf 'KACIRILDI  %-45s -> %s FAIL olmadi\n' \
        "$mutation_name" "$expected_assertion" >&2
    grep -F 'FAIL  ' <<<"$output" >&2 || true
    return 1
}

echo "sablon veritabani kuruluyor: $TEMPLATE_DB"
create_database "$TEMPLATE_DB"
for migration in "${REPO_ROOT}"/supabase/migrations/*.sql; do
    "$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$TEMPLATE_DB" -f "$migration"
done

baseline_db="rls_api_obs_base_$$_1"
create_database "$baseline_db" -T "$TEMPLATE_DB"
baseline_output="$(run_proof "$baseline_db")"
drop_database_now "$baseline_db"
if grep -Fq 'FAIL  ' <<<"$baseline_output"; then
    echo "HATA: bozulmamis semada API observability kaniti FAIL verdi." >&2
    grep -F 'FAIL  ' <<<"$baseline_output" >&2
    exit 1
fi
echo "referans kosu temiz (bozulmamis semada FAIL yok)"

failures=0

run_mutation 1 \
    "runtime tablo SELECT acilirsa" \
    "GRANT SELECT ON public.api_request_events TO dou_api_runtime;
     CREATE POLICY api_request_events_runtime_leak ON public.api_request_events
       FOR SELECT TO dou_api_runtime USING (true);" \
    "rls__runtime_dogrudan_tablo_okuyamaz" \
    || failures=$((failures + 1))

run_mutation 2 \
    "runtime tablo INSERT acilirsa" \
    "GRANT INSERT ON public.api_request_events TO dou_api_runtime;
     CREATE POLICY api_request_events_runtime_insert ON public.api_request_events
       FOR INSERT TO dou_api_runtime WITH CHECK (true);" \
    "rls__runtime_dogrudan_tabloya_insert_yapamaz" \
    || failures=$((failures + 1))

run_mutation 3 \
    "runtime tablo UPDATE acilirsa" \
    "GRANT UPDATE ON public.api_request_events TO dou_api_runtime;
     CREATE POLICY api_request_events_runtime_update ON public.api_request_events
       FOR UPDATE TO dou_api_runtime USING (true) WITH CHECK (true);" \
    "rls__runtime_dogrudan_tabloyu_update_edemez" \
    || failures=$((failures + 1))

run_mutation 4 \
    "runtime tablo DELETE acilirsa" \
    "GRANT DELETE ON public.api_request_events TO dou_api_runtime;
     CREATE POLICY api_request_events_runtime_delete ON public.api_request_events
       FOR DELETE TO dou_api_runtime USING (true);" \
    "rls__runtime_dogrudan_tablodan_delete_yapamaz" \
    || failures=$((failures + 1))

run_mutation 5 \
    "admin SQL recheck fail-open olursa" \
    "CREATE OR REPLACE FUNCTION app.is_platform_admin() RETURNS boolean
       LANGUAGE sql STABLE SECURITY DEFINER
       SET search_path = pg_catalog, public, app AS \$\$ SELECT true \$\$;" \
    "admin_query__normal_kullanici_sql_yardimcisindan_reddedilir" \
    || failures=$((failures + 1))

run_mutation 6 \
    "writer session_user kapisi duserse" \
    "DO \$mutation\$
     DECLARE
         definition text;
     BEGIN
         SELECT pg_get_functiondef(
             'app.record_api_request_events(jsonb,integer)'::regprocedure
         ) INTO definition;
         IF position('IF session_user <> ''dou_api_runtime'' THEN' IN definition) = 0 THEN
             RAISE EXCEPTION 'writer session_user kapisi bulunamadi';
         END IF;
         definition := replace(
             definition,
             'IF session_user <> ''dou_api_runtime'' THEN',
             'IF false THEN'
         );
         EXECUTE definition;
     END
     \$mutation\$;
     GRANT EXECUTE ON FUNCTION app.record_api_request_events(jsonb, integer) TO dou_app;" \
    "runtime_writer__carrier_session_user_yazamaz" \
    || failures=$((failures + 1))

run_mutation 7 \
    "telemetri semasina kimlik kolonu eklenirse" \
    "ALTER TABLE public.api_request_events ADD COLUMN user_id uuid;" \
    "schema__exact_iceriksiz_kolon_kumesi" \
    || failures=$((failures + 1))

run_mutation 8 \
    "worker writer EXECUTE alirsa" \
    "GRANT EXECUTE ON FUNCTION app.record_api_request_events(jsonb, integer) TO dou_worker;" \
    "acl__fonksiyon_yuzeyleri_exact_rol_allowlist" \
    || failures=$((failures + 1))

run_mutation 9 \
    "carrier tablo SELECT alirsa" \
    "GRANT SELECT ON public.api_request_events TO dou_app;" \
    "rls__carrier_dogrudan_tablo_okuyamaz" \
    || failures=$((failures + 1))

run_mutation 10 \
    "worker tablo INSERT alirsa" \
    "GRANT INSERT ON public.api_request_events TO dou_worker;
     CREATE POLICY api_request_events_worker_insert ON public.api_request_events
       FOR INSERT TO dou_worker WITH CHECK (true);" \
    "rls__worker_dogrudan_tabloya_insert_yapamaz" \
    || failures=$((failures + 1))

run_mutation 11 \
    "PUBLIC writer EXECUTE alirsa" \
    "GRANT EXECUTE ON FUNCTION app.record_api_request_events(jsonb, integer) TO PUBLIC;" \
    "acl__fonksiyon_yuzeyleri_exact_rol_allowlist" \
    || failures=$((failures + 1))

run_mutation 12 \
    "worker purge EXECUTE alirsa" \
    "GRANT EXECUTE ON FUNCTION app.purge_expired_api_request_events(integer) TO dou_worker;" \
    "acl__fonksiyon_yuzeyleri_exact_rol_allowlist" \
    || failures=$((failures + 1))

if ((failures > 0)); then
    echo "$failures API observability mutasyonu ilgili kaniti kirmiziya cevirmedi." >&2
    exit 1
fi

echo "12/12 hedefli mutasyon ilgili iddiayi kirmiziya cevirdi."
