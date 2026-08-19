#!/usr/bin/env bash
#
# 009 assessment-integrity veritabani sinirlarinin KIRMIZI yanabildiginin kaniti.
#
# Her kosu yeni bir sablon DB kurar, tum migrasyonlari uygular, bozulmamis referans
# davranisini ayri bir klonda dogrular; runtime ACL/policy kapilari ile terminal
# degismezlik ve feedback guard'larini birer klonda gevsetir. Basari, hata veya
# sinyal durumunda olusturulan butun DB'ler EXIT
# trap'iyle temizlenir; ortak gelistirme DB'sine baglanilmaz.
#
# Kullanim:
#   supabase/tests/rls_assessment_integrity_mutation_check.sh \
#     rls_assessment_integrity_<benzersiz_ad>

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEST_SQL="${REPO_ROOT}/supabase/tests/rls_assessment_integrity.sql"
PSQL="${PG_BIN:+${PG_BIN}/}psql"
CREATEDB="${PG_BIN:+${PG_BIN}/}createdb"
DROPDB="${PG_BIN:+${PG_BIN}/}dropdb"
TEMPLATE_DB="${1:-rls_assessment_integrity_local_$$}"

if [[ ! "$TEMPLATE_DB" =~ ^rls_assessment_integrity_[A-Za-z0-9_]+$ ]]; then
    echo "HATA: DB adi rls_assessment_integrity_ ile baslayan guvenli bir ad olmali." >&2
    exit 2
fi

if ((${#TEMPLATE_DB} > 63)); then
    echo "HATA: PostgreSQL DB adi 63 karakteri gecemez." >&2
    exit 2
fi

database_names=$("$PSQL" -X -lqtA -d postgres | cut -d'|' -f1)
if grep -Fxq "$TEMPLATE_DB" <<<"$database_names"; then
    echo "HATA: $TEMPLATE_DB zaten var; mevcut bir DB'ye dokunulmayacak." >&2
    exit 2
fi

created_databases=()
cleanup() {
    local db_index
    local cleanup_db
    for ((db_index=${#created_databases[@]} - 1; db_index >= 0; db_index--)); do
        cleanup_db="${created_databases[$db_index]}"
        "$DROPDB" --if-exists "$cleanup_db" >/dev/null 2>&1 || true
    done
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

create_database() {
    local target_db="$1"
    shift
    "$CREATEDB" "$@" "$target_db"
    created_databases+=("$target_db")
}

drop_database_now() {
    local target_db="$1"
    # Ad dizide kalir; EXIT trap'indeki --if-exists ikinci denemeyi zararsiz yapar.
    "$DROPDB" "$target_db"
}

run_proof() {
    local target_db="$1"
    local proof_output

    if ! proof_output=$("$PSQL" -X -v ON_ERROR_STOP=1 -d "$target_db" -f "$TEST_SQL" 2>&1); then
        echo "HATA: $target_db uzerindeki SQL kaniti tamamlanamadi." >&2
        echo "$proof_output" >&2
        return 1
    fi

    printf '%s' "$proof_output"
}

run_mutation() {
    local sequence="$1"
    local mutation_name="$2"
    local mutation_sql="$3"
    local expected_assertion="$4"
    local scratch_db="rls_ai_mut_$$_${sequence}"
    local mutation_output

    create_database "$scratch_db" -T "$TEMPLATE_DB"
    "$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$scratch_db" -c "$mutation_sql"
    if ! mutation_output=$(run_proof "$scratch_db"); then
        drop_database_now "$scratch_db"
        return 1
    fi
    drop_database_now "$scratch_db"

    if grep -Fq "FAIL  ${expected_assertion}" <<<"$mutation_output"; then
        printf 'YAKALANDI  %-42s -> %s\n' "$mutation_name" "$expected_assertion"
        return 0
    fi

    printf 'KACIRILDI  %-42s -> %s FAIL olmadi\n' \
        "$mutation_name" "$expected_assertion" >&2
    grep -F 'FAIL  ' <<<"$mutation_output" >&2 || true
    return 1
}

echo "sablon veritabani kuruluyor: $TEMPLATE_DB"
create_database "$TEMPLATE_DB"
for migration in "${REPO_ROOT}"/supabase/migrations/*.sql; do
    "$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$TEMPLATE_DB" -f "$migration"
done

baseline_db="rls_ai_baseline_$$_1"
create_database "$baseline_db" -T "$TEMPLATE_DB"
baseline_output=$(run_proof "$baseline_db")
drop_database_now "$baseline_db"

if grep -Fq 'FAIL  ' <<<"$baseline_output"; then
    echo "HATA: bozulmamis semada assessment-integrity FAIL verdi." >&2
    grep -F 'FAIL  ' <<<"$baseline_output" >&2
    exit 1
fi
echo "referans kosu temiz (bozulmamis semada FAIL yok)"

mutation_failures=0

run_mutation 1 \
    "assessment soru okumasi acilirsa" \
    "DROP POLICY questions_read ON public.questions;
     CREATE POLICY questions_read ON public.questions FOR SELECT
     USING (app.is_member(course_id) AND status = 'approved');" \
    "question_purpose__baska_ogrencinin_kagit_sorusu_kapali" \
    || mutation_failures=$((mutation_failures + 1))

run_mutation 2 \
    "question runtime gate duserse" \
    "DROP POLICY questions_api_runtime ON public.questions;" \
    "runtime_policy__gecici_grantle_cevap_anahtari_acilmaz" \
    || mutation_failures=$((mutation_failures + 1))

run_mutation 3 \
    "answer read runtime gate duserse" \
    "DROP POLICY answers_api_runtime_read ON public.answers;" \
    "runtime_policy__gecici_grantle_ham_puan_acilmaz" \
    || mutation_failures=$((mutation_failures + 1))

run_mutation 4 \
    "answer/session insert runtime zinciri duserse" \
    "DROP POLICY answers_api_runtime_insert ON public.answers;
     DROP POLICY exam_sessions_api_runtime_read ON public.exam_sessions;" \
    "runtime_policy__gecici_grantle_sahte_puan_yazilamaz" \
    || mutation_failures=$((mutation_failures + 1))

run_mutation 5 \
    "session insert runtime gate duserse" \
    "DROP POLICY exam_sessions_api_runtime_insert ON public.exam_sessions;" \
    "runtime_policy__gecici_grantle_resmi_oturum_practice_olamaz" \
    || mutation_failures=$((mutation_failures + 1))

run_mutation 6 \
    "exam version runtime gate duserse" \
    "DROP POLICY exam_versions_api_runtime_read ON public.exam_versions;" \
    "runtime_policy__gecici_grantle_blueprint_snapshot_acilmaz" \
    || mutation_failures=$((mutation_failures + 1))

run_mutation 7 \
    "exam item runtime gate duserse" \
    "DROP POLICY exam_items_api_runtime_read ON public.exam_items;" \
    "runtime_policy__gecici_grantle_kagit_kalemleri_acilmaz" \
    || mutation_failures=$((mutation_failures + 1))

run_mutation 8 \
    "session read runtime gate duserse" \
    "DROP POLICY exam_sessions_api_runtime_read ON public.exam_sessions;" \
    "runtime_policy__gecici_grantle_oturum_satiri_acilmaz" \
    || mutation_failures=$((mutation_failures + 1))

run_mutation 9 \
    "carrier question grant geri verilirse" \
    "GRANT SELECT ON public.questions TO dou_app;" \
    "runtime_grants__hassas_yetki_yalniz_api_logininde" \
    || mutation_failures=$((mutation_failures + 1))

run_mutation 10 \
    "terminal soru guard'i duserse" \
    "DROP TRIGGER questions_assessment_integrity_guard ON public.questions;" \
    "question_trigger__published_kagit_icerigi_degistirilemez" \
    || mutation_failures=$((mutation_failures + 1))

run_mutation 11 \
    "feedback zaman guard'i duserse" \
    "DROP TRIGGER exam_sessions_feedback_schedule_guard ON public.exam_sessions;" \
    "feedback_schedule__erken_snapshot_insert_edilemez" \
    || mutation_failures=$((mutation_failures + 1))

run_mutation 12 \
    "surum snapshot guard'i duserse" \
    "DROP TRIGGER exam_versions_assessment_integrity_guard ON public.exam_versions;" \
    "exam_version_immutability__published_snapshot_degistirilemez" \
    || mutation_failures=$((mutation_failures + 1))

if ((mutation_failures > 0)); then
    echo "$mutation_failures assessment-integrity mutasyonu kacirildi." >&2
    exit 1
fi

echo "12/12 hedefli mutasyon ilgili iddiayi kirmiziya cevirdi."
