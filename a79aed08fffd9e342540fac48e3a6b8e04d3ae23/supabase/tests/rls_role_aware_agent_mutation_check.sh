#!/usr/bin/env bash
#
# 005 role-aware course agent veritabani sinirlarinin KIRMIZI yanabildiginin kaniti.
#
# Bu betik gercek/ortak `dou_synapse` veritabanina HIC BAGLANMAZ. Her kosuda PID ile
# adlandirilmis yeni bir sablon DB kurar, tum migrasyonlari uygular, referans davranisi
# ayri bir klonda dogrular ve her gevsetmeyi sablonun yeni bir klonunda sinar. Basari,
# hata veya sinyal durumunda olusturdugu tum DB'leri EXIT trap'i ile temizler.
#
# Mutasyon kapsami (her satir ayri bir gevsetme ve ayri bir sizinti sondasidir):
#   1. rezervasyon yardimcisinin aktif ders uyeligi,
#   2. chat_sessions.audience degistirilemez trigger'i,
#   3. chat_sessions INSERT persona eslesmesi,
#   4. answer_cache cross-audience SELECT,
#   5. answer_cache cross-audience INSERT,
#   6. function-only kota tablosunun dogrudan GRANT siniri,
#   7. SECURITY DEFINER kota yardimcisinin PUBLIC/dou_worker EXECUTE siniri,
#   8. atomik rezervasyonun platform/course transaction advisory lock'lari,
#   9. gunluk token kotasi,
#  10. aktif reservation eszamanlilik tavani,
#  11. KVKK sohbet gecmisinin yalniz satir sahibine gorunmesi,
#  12. uyelik sonlandiktan sonra sahibin kendi mesajlarini disa aktarabilmesi,
#  13. uyelik sonlandiktan sonra sahibin kendi geri bildirimini disa aktarabilmesi,
#  14. KVKK mesaj politikasinin baska kullaniciya acilmamasi,
#  15. KVKK geri bildirim politikasinin baska kullaniciya acilmamasi,
#  16. audience backfill'in revoked/inactive uyelik rolunu kullanmamasi.
#
# Bilincli dislama: `/me/export` aktif-sinav kilidi, kullanici-bazli advisory lock ve
# HTTP 423 zarfi FastAPI katmaninda tanimlidir; 0015 migrasyonunda cagrilabilir bir SQL
# export yardimcisi yoktur. Bu nedenle o kapinin mutasyonu burada sahte bir SQL kaniti
# olarak sunulmaz; apps/api/tests/test_user_rights.py ve browser/E2E kapisinda sinanir.
#
# Kullanim:
#     supabase/tests/rls_role_aware_agent_mutation_check.sh
#     supabase/tests/rls_role_aware_agent_mutation_check.sh rls_role_agent_ozel_123
#
# Ikinci bicimde ad `rls_role_agent_` ile baslamali ve mevcut olmamalidir.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PSQL="${PG_BIN:+${PG_BIN}/}psql"
CREATEDB="${PG_BIN:+${PG_BIN}/}createdb"
DROPDB="${PG_BIN:+${PG_BIN}/}dropdb"
TEMPLATE_DB="${1:-rls_role_agent_template_$$}"

INSTRUCTOR="11111111-1111-1111-1111-111111111111"
STUDENT="22222222-2222-2222-2222-222222222222"
OTHER_STUDENT="33333333-3333-3333-3333-333333333333"
NON_MEMBER="44444444-4444-4444-4444-444444444444"
COURSE="aaaaaaaa-0000-0000-0000-000000000005"
STUDENT_SESSION="51515151-0000-0000-0000-000000000001"
OTHER_SESSION="51515151-0000-0000-0000-000000000002"
STUDENT_MESSAGE="52525252-0000-0000-0000-000000000001"
OTHER_MESSAGE="52525252-0000-0000-0000-000000000002"
STUDENT_FEEDBACK="53535353-0000-0000-0000-000000000001"
OTHER_FEEDBACK="53535353-0000-0000-0000-000000000002"

if [[ ! "$TEMPLATE_DB" =~ ^rls_role_agent_[A-Za-z0-9_]+$ ]]; then
    echo "HATA: sablon DB adi rls_role_agent_ ile baslayan guvenli bir ad olmali." >&2
    exit 2
fi

if "$PSQL" -lqtA -d postgres 2>/dev/null | cut -d'|' -f1 | grep -qx "$TEMPLATE_DB"; then
    echo "HATA: $TEMPLATE_DB zaten var; mevcut bir DB'ye dokunulmayacak." >&2
    exit 2
fi

created_databases=()
created_temp_files=()
cleanup() {
    local db
    local db_index
    local temp_file
    for ((db_index=${#created_databases[@]} - 1; db_index >= 0; db_index--)); do
        db="${created_databases[$db_index]}"
        "$DROPDB" --if-exists "$db" >/dev/null 2>&1 || true
    done
    for temp_file in "${created_temp_files[@]}"; do
        rm -f "$temp_file"
    done
}
trap cleanup EXIT INT TERM

create_database() {
    local db="$1"
    shift
    "$CREATEDB" "$@" "$db"
    created_databases+=("$db")
}

drop_database_now() {
    local db="$1"
    # DB dizide bilerek kalir: trap --if-exists ile ikinci temizligi zararsizca
    # dener; bu sayede tam bu satirda kesinti olsa bile kalinti kalmaz.
    "$DROPDB" "$db"
}

seed_fixture() {
    local db="$1"
    "$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$db" <<SQL
INSERT INTO public.profiles (id, email, full_name) VALUES
    ('$INSTRUCTOR', 'agent.teacher.005@dogus.edu.tr', '005 Egitmen'),
    ('$STUDENT', 'agent.student.005@dogus.edu.tr', '005 Ogrenci'),
    ('$OTHER_STUDENT', 'agent.other.005@dogus.edu.tr', '005 Diger Ogrenci'),
    ('$NON_MEMBER', 'agent.outsider.005@dogus.edu.tr', '005 Uye Olmayan');

INSERT INTO public.courses (id, code, title, created_by)
VALUES ('$COURSE', 'RLS-AGENT-005', 'Role-aware agent mutation fixture', '$INSTRUCTOR');

INSERT INTO public.course_memberships (course_id, user_id, role, status) VALUES
    ('$COURSE', '$INSTRUCTOR', 'instructor', 'active'),
    ('$COURSE', '$STUDENT', 'student', 'active'),
    ('$COURSE', '$OTHER_STUDENT', 'student', 'active');

INSERT INTO public.course_ai_policies (
    course_id, daily_token_budget, student_daily_token_budget,
    instructor_daily_token_budget, max_output_tokens, max_concurrent_requests,
    updated_by
) VALUES ('$COURSE', 100, 100, 100, 700, 1, '$INSTRUCTOR');

INSERT INTO public.chat_sessions (id, course_id, user_id, mode, audience) VALUES
    ('$STUDENT_SESSION', '$COURSE', '$STUDENT', 'qa', 'student'),
    ('$OTHER_SESSION', '$COURSE', '$OTHER_STUDENT', 'qa', 'student');

INSERT INTO public.chat_messages (
    id, session_id, course_id, role, content, citations, status, seq
) VALUES
    ('$STUDENT_MESSAGE', '$STUDENT_SESSION', '$COURSE', 'assistant',
     'student answer', '[]'::jsonb, 'answered', 1),
    ('$OTHER_MESSAGE', '$OTHER_SESSION', '$COURSE', 'assistant',
     'other answer', '[]'::jsonb, 'answered', 1);

SET app.current_user_id='$STUDENT';
INSERT INTO public.chat_message_feedback (
    id, course_id, message_id, user_id, rating, reason, comment
) VALUES (
    '$STUDENT_FEEDBACK', '$COURSE', '$STUDENT_MESSAGE', '$STUDENT',
    'unhelpful', 'citation_problem', 'private export fixture'
);
SET app.current_user_id='$OTHER_STUDENT';
INSERT INTO public.chat_message_feedback (
    id, course_id, message_id, user_id, rating, reason, comment
) VALUES (
    '$OTHER_FEEDBACK', '$COURSE', '$OTHER_MESSAGE', '$OTHER_STUDENT',
    'unhelpful', 'citation_problem', 'other private export fixture'
);
RESET app.current_user_id;

INSERT INTO public.answer_cache (
    id, course_id, audience, policy_revision, prompt_revision, corpus_revision,
    question_hash, answer
) VALUES
    ('acacacac-0000-0000-0000-000000000001', '$COURSE', 'student',
     'p1', 'r1', 'c1', 'student-only', '{"text":"student"}'::jsonb),
    ('acacacac-0000-0000-0000-000000000002', '$COURSE', 'instructor',
     'p1', 'r1', 'c1', 'instructor-only', '{"text":"instructor"}'::jsonb);

-- Yalniz gecici klonlarda kullanilan test yardimcisi. Gercek migrasyona veya ortak
-- DB'ye yazilmaz. pg_get_functiondef uzerinden tam bir kontrol blogunu degistirir;
-- eslesen kaynak yoksa mutasyonu sessizce "uygulanmis" saymak yerine kirmizi olur.
CREATE OR REPLACE FUNCTION app.__test_replace_reservation_definition(
    p_needle text,
    p_replacement text
) RETURNS void
LANGUAGE plpgsql
SET search_path = pg_catalog, public, app
AS \$test_mutator\$
DECLARE
    v_before text;
    v_after text;
BEGIN
    SELECT pg_get_functiondef(
        'app.reserve_course_agent_tokens(uuid,uuid,integer,integer,integer,integer,integer)'
            ::regprocedure
    ) INTO v_before;
    v_after := replace(v_before, p_needle, p_replacement);
    IF v_after = v_before THEN
        RAISE EXCEPTION 'requested reservation mutation did not match function source';
    END IF;
    EXECUTE v_after;
END
\$test_mutator\$;
SQL
}

expect_denied() {
    local db="$1"
    local name="$2"
    local expected="$3"
    local sql="$4"
    local output

    if output=$("$PSQL" -X -v ON_ERROR_STOP=1 -qAt -d "$db" -c "$sql" 2>&1); then
        echo "HATA: referans kosuda $name reddedilmedi." >&2
        echo "$output" >&2
        exit 1
    fi
    if ! grep -Fq "$expected" <<<"$output"; then
        echo "HATA: $name yanlis nedenle reddedildi; '$expected' bekleniyordu." >&2
        echo "$output" >&2
        exit 1
    fi
    printf 'REFERANS   %-48s -> dogru nedenle kapali\n' "$name"
}

expect_marker() {
    local db="$1"
    local name="$2"
    local marker="$3"
    local sql="$4"
    local output

    output=$("$PSQL" -X -v ON_ERROR_STOP=1 -qAt -d "$db" -c "$sql" 2>&1)
    if ! grep -Fxq "$marker" <<<"$output"; then
        echo "HATA: referans kosuda $name icin '$marker' gelmedi." >&2
        echo "$output" >&2
        exit 1
    fi
    printf 'REFERANS   %-48s -> %s\n' "$name" "$marker"
}

run_mutation() {
    local sequence="$1"
    local name="$2"
    local mutation_sql="$3"
    local probe_sql="$4"
    local expected_marker="$5"
    local scratch="rls_role_agent_mut_$$_${sequence}"
    local output

    create_database "$scratch" -T "$TEMPLATE_DB"
    "$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$scratch" -c "$mutation_sql"
    output=$("$PSQL" -X -v ON_ERROR_STOP=1 -qAt -d "$scratch" -c "$probe_sql" 2>&1 || true)

    if ! grep -Fxq "$expected_marker" <<<"$output"; then
        printf 'KACIRILDI  %-48s -> %s gelmedi\n' "$name" "$expected_marker" >&2
        echo "$output" >&2
        return 1
    fi
    printf 'YAKALANDI  %-48s -> %s\n' "$name" "$expected_marker"
    drop_database_now "$scratch"
}

run_lock_race_mutation() {
    local sequence="$1"
    local name="$2"
    local scratch="rls_role_agent_mut_$$_${sequence}"
    local output_a
    local output_b
    local pid_a
    local pid_b
    local status_a=0
    local status_b=0
    local summary
    local call_a
    local call_b

    output_a="$(mktemp "${TMPDIR:-/tmp}/rls-role-agent-lock-a.XXXXXX")"
    output_b="$(mktemp "${TMPDIR:-/tmp}/rls-role-agent-lock-b.XXXXXX")"
    created_temp_files+=("$output_a" "$output_b")
    create_database "$scratch" -T "$TEMPLATE_DB"
    "$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$scratch" -c "$LOCK_BYPASS_SQL"

    call_a="SET ROLE dou_app; SET app.current_user_id='$STUDENT'; SELECT allowed FROM app.reserve_course_agent_tokens('$COURSE','50505050-0000-0000-0000-000000000050',60,60,50000,500000,5000000);"
    call_b="SET ROLE dou_app; SET app.current_user_id='$STUDENT'; SELECT allowed FROM app.reserve_course_agent_tokens('$COURSE','50505050-0000-0000-0000-000000000051',60,60,50000,500000,5000000);"

    "$PSQL" -X -v ON_ERROR_STOP=1 -qAt -d "$scratch" -c "$call_a" >"$output_a" 2>&1 &
    pid_a=$!
    "$PSQL" -X -v ON_ERROR_STOP=1 -qAt -d "$scratch" -c "$call_b" >"$output_b" 2>&1 &
    pid_b=$!

    wait "$pid_a" || status_a=$?
    wait "$pid_b" || status_b=$?
    if ((status_a != 0 || status_b != 0)); then
        printf 'KACIRILDI  %-48s -> paralel sonda SQL hatasi\n' "$name" >&2
        cat "$output_a" "$output_b" >&2
        rm -f "$output_a" "$output_b"
        return 1
    fi

    summary=$("$PSQL" -X -v ON_ERROR_STOP=1 -qAt -d "$scratch" -c \
        "SELECT CASE WHEN count(*)=2 AND sum(charged_tokens)=120 THEN 'LEAK__UNLOCKED_ATOMIC_OVERSHOOT' ELSE 'SAFE' END FROM public.ai_token_reservations WHERE id IN ('50505050-0000-0000-0000-000000000050','50505050-0000-0000-0000-000000000051');")
    rm -f "$output_a" "$output_b"

    if [[ "$summary" != "LEAK__UNLOCKED_ATOMIC_OVERSHOOT" ]]; then
        printf 'KACIRILDI  %-48s -> LEAK__UNLOCKED_ATOMIC_OVERSHOOT gelmedi\n' "$name" >&2
        echo "$summary" >&2
        return 1
    fi
    printf 'YAKALANDI  %-48s -> %s\n' "$name" "$summary"
    drop_database_now "$scratch"
}

run_inactive_backfill_mutation() {
    local base="rls_role_agent_backfill_base_$$"
    local reference="rls_role_agent_backfill_ref_$$"
    local mutant="rls_role_agent_backfill_mut_$$"
    local mutated_migration
    local migration
    local summary

    mutated_migration="$(mktemp "${TMPDIR:-/tmp}/role-agent-0015-mutated.XXXXXX.sql")"
    created_temp_files+=("$mutated_migration")
    create_database "$base"
    for migration in "$REPO_ROOT"/supabase/migrations/*.sql; do
        if [[ "$(basename "$migration")" == "0015_role_aware_course_agent.sql" ]]; then
            break
        fi
        "$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$base" -f "$migration"
    done
    "$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$base" <<SQL
INSERT INTO public.profiles (id, email, full_name)
VALUES ('$INSTRUCTOR', 'revoked.backfill@dogus.edu.tr', 'Revoked Instructor');
INSERT INTO public.courses (id, code, title, created_by)
VALUES ('$COURSE', 'RLS-BACKFILL-005', 'Inactive backfill fixture', '$INSTRUCTOR');
INSERT INTO public.course_memberships (course_id, user_id, role, status)
VALUES ('$COURSE', '$INSTRUCTOR', 'instructor', 'revoked');
INSERT INTO public.chat_sessions (id, course_id, user_id, mode)
VALUES ('$STUDENT_SESSION', '$COURSE', '$INSTRUCTOR', 'qa');
INSERT INTO public.request_logs (
    id, course_id, user_id, route, mode, http_status, latency_ms
) VALUES (
    '54545454-0000-0000-0000-000000000001', '$COURSE', '$INSTRUCTOR',
    '/courses/backfill/chat', 'qa', 200, 1
);
SQL

    create_database "$reference" -T "$base"
    "$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$reference" \
        -f "$REPO_ROOT/supabase/migrations/0015_role_aware_course_agent.sql"
    summary=$("$PSQL" -X -v ON_ERROR_STOP=1 -qAt -d "$reference" -c \
        "SELECT CASE WHEN (SELECT audience='student' FROM public.chat_sessions WHERE id='$STUDENT_SESSION') AND (SELECT audience='student' FROM public.request_logs WHERE id='54545454-0000-0000-0000-000000000001') THEN 'REFERENCE__INACTIVE_BACKFILL_STUDENT' ELSE 'WRONG' END;")
    if [[ "$summary" != "REFERENCE__INACTIVE_BACKFILL_STUDENT" ]]; then
        echo "HATA: inactive membership backfill referans kosusu guvenli degil." >&2
        echo "$summary" >&2
        return 1
    fi
    printf 'REFERANS   %-48s -> %s\n' \
        "inactive uyelik audience backfill'e katilmaz" "$summary"
    drop_database_now "$reference"

    sed \
        -e '/UPDATE chat_sessions AS s/,/UPDATE chat_sessions SET audience/ { s/AND m.status = '\''active'\''::membership_status;/AND TRUE;/; }' \
        -e '/UPDATE request_logs AS l/,/DROP POLICY request_logs_self_insert/ { s/AND m.status = '\''active'\''::membership_status;/AND TRUE;/; }' \
        "$REPO_ROOT/supabase/migrations/0015_role_aware_course_agent.sql" \
        >"$mutated_migration"
    create_database "$mutant" -T "$base"
    "$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$mutant" -f "$mutated_migration"
    summary=$("$PSQL" -X -v ON_ERROR_STOP=1 -qAt -d "$mutant" -c \
        "SELECT CASE WHEN (SELECT audience='instructor' FROM public.chat_sessions WHERE id='$STUDENT_SESSION') AND (SELECT audience='instructor' FROM public.request_logs WHERE id='54545454-0000-0000-0000-000000000001') THEN 'LEAK__INACTIVE_ROLE_STAMPED' ELSE 'SAFE' END;")
    if [[ "$summary" != "LEAK__INACTIVE_ROLE_STAMPED" ]]; then
        echo "KACIRILDI  inactive uyelik backfill filtresi -> LEAK__INACTIVE_ROLE_STAMPED gelmedi" >&2
        echo "$summary" >&2
        return 1
    fi
    printf 'YAKALANDI  %-48s -> %s\n' \
        "inactive uyelik backfill filtresi kaldirilirsa" "$summary"
    drop_database_now "$mutant"
    drop_database_now "$base"
}

echo "gecici sablon kuruluyor: $TEMPLATE_DB"
create_database "$TEMPLATE_DB"
for migration in "$REPO_ROOT"/supabase/migrations/*.sql; do
    "$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$TEMPLATE_DB" -f "$migration"
done
seed_fixture "$TEMPLATE_DB"

# Referans kosu da sablonu kirletmez. Kota rezervasyonu yazan kontroller ayri klonda
# kosar; tum mutasyonlar ayni temiz fixture'dan baslar.
REFERENCE_DB="rls_role_agent_reference_$$"
create_database "$REFERENCE_DB" -T "$TEMPLATE_DB"

expect_denied "$REFERENCE_DB" \
    "audience trigger ile degistirilemez" \
    "chat session audience is immutable" \
    "UPDATE public.chat_sessions SET audience='instructor' WHERE id='$STUDENT_SESSION';"

expect_denied "$REFERENCE_DB" \
    "ogrenci instructor oturumu ekleyemez" \
    "row-level security policy" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; INSERT INTO public.chat_sessions (course_id,user_id,mode,audience) VALUES ('$COURSE','$STUDENT','qa','instructor');"

expect_denied "$REFERENCE_DB" \
    "uye olmayan token rezervasyonu acamaz" \
    "course membership required" \
    "SET ROLE dou_app; SET app.current_user_id='$NON_MEMBER'; SELECT * FROM app.reserve_course_agent_tokens('$COURSE','50505050-0000-0000-0000-000000000002',10,60,50000,500000,5000000);"

expect_marker "$REFERENCE_DB" \
    "ogrenci instructor cache okuyamaz" \
    "SAFE__CROSS_AUDIENCE_CACHE_READ" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; SELECT CASE WHEN count(*)=0 THEN 'SAFE__CROSS_AUDIENCE_CACHE_READ' ELSE 'LEAK' END FROM public.answer_cache WHERE audience='instructor';"

expect_denied "$REFERENCE_DB" \
    "ogrenci instructor cache yazamaz" \
    "row-level security policy" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; INSERT INTO public.answer_cache (course_id,audience,policy_revision,prompt_revision,corpus_revision,question_hash,answer) VALUES ('$COURSE','instructor','p2','r2','c2','forged-instructor','{}'::jsonb);"

expect_denied "$REFERENCE_DB" \
    "worker kota tablosunu dogrudan okuyamaz" \
    "permission denied for table ai_token_reservations" \
    "SET ROLE dou_worker; SELECT count(*) FROM public.ai_token_reservations;"

expect_denied "$REFERENCE_DB" \
    "worker SECURITY DEFINER rezervasyonu cagiramaz" \
    "permission denied for function reserve_course_agent_tokens" \
    "SET ROLE dou_worker; SET app.current_user_id='$STUDENT'; SELECT * FROM app.reserve_course_agent_tokens('$COURSE','50505050-0000-0000-0000-000000000001',10,60,50000,500000,5000000);"

expect_marker "$REFERENCE_DB" \
    "KVKK sohbet gecmisi baska ogrenciye kapali" \
    "SAFE__PRIVACY_OTHER_SESSION_HIDDEN" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; SELECT CASE WHEN count(*)=0 THEN 'SAFE__PRIVACY_OTHER_SESSION_HIDDEN' ELSE 'LEAK' END FROM public.chat_sessions WHERE id='$OTHER_SESSION';"

expect_marker "$REFERENCE_DB" \
    "KVKK mesajlari baska ogrenciye kapali" \
    "SAFE__PRIVACY_OTHER_MESSAGE_HIDDEN" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; SELECT CASE WHEN count(*)=0 THEN 'SAFE__PRIVACY_OTHER_MESSAGE_HIDDEN' ELSE 'LEAK' END FROM public.chat_messages WHERE id='$OTHER_MESSAGE';"

expect_marker "$REFERENCE_DB" \
    "KVKK geri bildirimi baska ogrenciye kapali" \
    "SAFE__PRIVACY_OTHER_FEEDBACK_HIDDEN" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; SELECT CASE WHEN count(*)=0 THEN 'SAFE__PRIVACY_OTHER_FEEDBACK_HIDDEN' ELSE 'LEAK' END FROM public.chat_message_feedback WHERE id='$OTHER_FEEDBACK';"

expect_marker "$REFERENCE_DB" \
    "ilk kota on-odemesi kalici yazilir" \
    "REFERENCE__FIRST_RESERVATION_ALLOWED" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; SELECT CASE WHEN allowed THEN 'REFERENCE__FIRST_RESERVATION_ALLOWED' ELSE 'WRONG' END FROM app.reserve_course_agent_tokens('$COURSE','50505050-0000-0000-0000-000000000010',60,60,50000,500000,5000000);"

expect_marker "$REFERENCE_DB" \
    "ikinci aktif istek eszamanlilikta durur" \
    "REFERENCE__CONCURRENCY_BLOCKED" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; SELECT CASE WHEN NOT allowed AND reason='concurrency_limited' THEN 'REFERENCE__CONCURRENCY_BLOCKED' ELSE 'WRONG' END FROM app.reserve_course_agent_tokens('$COURSE','50505050-0000-0000-0000-000000000011',60,60,50000,500000,5000000);"

"$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$REFERENCE_DB" <<'SQL'
DO $$
DECLARE
    v_day_start timestamptz := date_trunc(
        'day', clock_timestamp() AT TIME ZONE 'Europe/Istanbul'
    ) AT TIME ZONE 'Europe/Istanbul';
    v_ready_at timestamptz;
BEGIN
    -- Kaydi her zaman bugunun Istanbul kota penceresinde tut. Gece yarisinin
    -- ilk saniyesinde kosulursa gecerli created_at < expires_at < simdi araligi
    -- olusana kadar en fazla bir saniye bekle; onceki gune kayan flake uretme.
    v_ready_at := v_day_start + interval '1 second';
    IF clock_timestamp() <= v_ready_at THEN
        PERFORM pg_sleep(
            GREATEST(EXTRACT(EPOCH FROM (v_ready_at - clock_timestamp())), 0) + 0.01
        );
    END IF;
    UPDATE public.ai_token_reservations
    SET created_at = v_day_start,
        expires_at = v_day_start + interval '500 milliseconds'
    WHERE id = '50505050-0000-0000-0000-000000000010';
END
$$;
SQL

expect_marker "$REFERENCE_DB" \
    "suresi dolan on-odeme gunluk kotada kalir" \
    "REFERENCE__EXPIRED_PRECHARGE_BLOCKED" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; SELECT CASE WHEN NOT allowed AND reason='quota_exhausted' THEN 'REFERENCE__EXPIRED_PRECHARGE_BLOCKED' ELSE 'WRONG' END FROM app.reserve_course_agent_tokens('$COURSE','50505050-0000-0000-0000-000000000012',60,60,50000,500000,5000000);"

expect_marker "$REFERENCE_DB" \
    "revoked kullanici kendi mesaj ve feedback'ini export eder" \
    "REFERENCE__REVOKED_EXPORT_COMPLETE" \
    "UPDATE public.course_memberships SET status='revoked' WHERE course_id='$COURSE' AND user_id='$STUDENT'; SET ROLE dou_app; SET app.current_user_id='$STUDENT'; SELECT CASE WHEN (SELECT count(*) FROM public.chat_sessions WHERE id='$STUDENT_SESSION')=1 AND (SELECT count(*) FROM public.chat_messages WHERE id='$STUDENT_MESSAGE')=1 AND (SELECT count(*) FROM public.chat_message_feedback WHERE id='$STUDENT_FEEDBACK')=1 THEN 'REFERENCE__REVOKED_EXPORT_COMPLETE' ELSE 'WRONG' END;"

echo "referans kosu temiz (10 kapali sinir + 4 kalici gizlilik/kota iddiasi)"
drop_database_now "$REFERENCE_DB"
echo

MEMBERSHIP_BYPASS_SQL=$(cat <<'SQL'
SELECT app.__test_replace_reservation_definition(
$needle$
    SELECT m.role INTO v_role
    FROM public.course_memberships AS m
    WHERE m.course_id = p_course_id AND m.user_id = v_user_id
      AND m.status = 'active'::membership_status;
    IF v_role IS NULL THEN
        RAISE EXCEPTION 'course membership required' USING ERRCODE = '42501';
    END IF;
$needle$,
$replacement$
    v_role := 'student'::membership_role;
$replacement$
);
SQL
)

LOCK_BYPASS_SQL=$(cat <<'SQL'
SELECT app.__test_replace_reservation_definition(
$needle$
    PERFORM pg_advisory_xact_lock(hashtextextended('course-agent-platform-daily', 15015));
    PERFORM pg_advisory_xact_lock(hashtextextended(p_course_id::text, 15016));
$needle$,
$replacement$
    NULL; -- MUTATION: platform/course reservation locks removed.
$replacement$
);
SELECT app.__test_replace_reservation_definition(
$needle$
    IF v_user_used + p_requested_tokens > v_user_budget
$needle$,
$replacement$
    -- Deterministic race window only: this adds no permission or bypass. Both
    -- unlocked transactions pause after reading the same aggregate snapshot.
    PERFORM pg_sleep(0.5);
    IF v_user_used + p_requested_tokens > v_user_budget
$replacement$
);
SQL
)

QUOTA_BYPASS_SQL=$(cat <<'SQL'
DO $quota_seed$
DECLARE
    v_day_start timestamptz := date_trunc(
        'day', clock_timestamp() AT TIME ZONE 'Europe/Istanbul'
    ) AT TIME ZONE 'Europe/Istanbul';
    v_ready_at timestamptz;
BEGIN
    -- Expired fakat bugunun kotasinda kalan tam 100 tokenlik on-odeme. Gece
    -- yarisinin ilk saniyesinde onceki gun penceresine kaymamak icin en fazla
    -- bir saniye bekler; ayni flake korumasi referans kosusunda da kullanilir.
    v_ready_at := v_day_start + interval '1 second';
    IF clock_timestamp() <= v_ready_at THEN
        PERFORM pg_sleep(
            GREATEST(EXTRACT(EPOCH FROM (v_ready_at - clock_timestamp())), 0) + 0.01
        );
    END IF;
    INSERT INTO public.ai_token_reservations(
        id, course_id, user_id, audience, reserved_tokens, charged_tokens,
        created_at, expires_at
    ) VALUES (
        '50505050-0000-0000-0000-000000000040',
        'aaaaaaaa-0000-0000-0000-000000000005',
        '22222222-2222-2222-2222-222222222222',
        'student', 100, 100, v_day_start, v_day_start + interval '500 milliseconds'
    );
END
$quota_seed$;

SELECT app.__test_replace_reservation_definition(
$needle$
    IF v_user_used + p_requested_tokens > v_user_budget
       OR v_global_user_used + p_requested_tokens > p_user_hard_limit
       OR v_course_used + p_requested_tokens > v_course_budget
       OR v_platform_used + p_requested_tokens > p_platform_hard_limit THEN
        INSERT INTO public.ai_guard_events(course_id, user_id, audience, event_type)
        VALUES (p_course_id, v_user_id, v_audience, 'quota_exhausted')
        ON CONFLICT (course_id, user_id, event_type, bucket_start) DO NOTHING;
        v_retry := GREATEST(1, EXTRACT(EPOCH FROM v_day_end - now())::integer);
        RETURN QUERY SELECT false, 'quota_exhausted', v_audience, v_retry, NULL::uuid;
        RETURN;
    END IF;
$needle$,
$replacement$
    NULL; -- MUTATION: daily user/course/platform quota decision removed.
$replacement$
);
SQL
)

CONCURRENCY_BYPASS_SQL=$(cat <<'SQL'
SELECT app.__test_replace_reservation_definition(
$needle$
    IF v_active >= v_max_concurrent THEN
        INSERT INTO public.ai_guard_events(course_id, user_id, audience, event_type)
        VALUES (p_course_id, v_user_id, v_audience, 'concurrency_limited')
        ON CONFLICT (course_id, user_id, event_type, bucket_start) DO NOTHING;
        RETURN QUERY SELECT false, 'concurrency_limited', v_audience, GREATEST(v_retry, 1), NULL::uuid;
        RETURN;
    END IF;
$needle$,
$replacement$
    NULL; -- MUTATION: active reservation concurrency decision removed.
$replacement$
);
SQL
)

failures=0

run_mutation 1 \
    "aktif ders uyeligi kontrolu kaldirilirsa" \
    "$MEMBERSHIP_BYPASS_SQL" \
    "SET ROLE dou_app; SET app.current_user_id='$NON_MEMBER'; SELECT CASE WHEN allowed THEN 'LEAK__NON_MEMBER_RESERVATION' ELSE 'SAFE' END FROM app.reserve_course_agent_tokens('$COURSE','50505050-0000-0000-0000-000000000060',10,60,50000,500000,5000000);" \
    "LEAK__NON_MEMBER_RESERVATION" || failures=$((failures + 1))

run_mutation 2 \
    "audience immutability trigger dusurulurse" \
    "DROP TRIGGER chat_session_audience_immutable ON public.chat_sessions;" \
    "UPDATE public.chat_sessions SET audience='instructor' WHERE id='$STUDENT_SESSION'; SELECT CASE WHEN audience='instructor' THEN 'LEAK__AUDIENCE_MUTATED' ELSE 'SAFE' END FROM public.chat_sessions WHERE id='$STUDENT_SESSION';" \
    "LEAK__AUDIENCE_MUTATED" || failures=$((failures + 1))

run_mutation 3 \
    "session audience RLS eslesmesi dusurulurse" \
    "DROP POLICY chat_sessions_self_insert ON public.chat_sessions; CREATE POLICY chat_sessions_self_insert ON public.chat_sessions FOR INSERT WITH CHECK (user_id=app.current_user_id() AND app.is_member(course_id));" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; INSERT INTO public.chat_sessions (course_id,user_id,mode,audience) VALUES ('$COURSE','$STUDENT','qa','instructor'); RESET ROLE; SELECT CASE WHEN count(*)=1 THEN 'LEAK__FORGED_INSTRUCTOR_SESSION' ELSE 'SAFE' END FROM public.chat_sessions WHERE user_id='$STUDENT' AND audience='instructor';" \
    "LEAK__FORGED_INSTRUCTOR_SESSION" || failures=$((failures + 1))

run_mutation 4 \
    "cache SELECT audience sarti dusurulurse" \
    "DROP POLICY answer_cache_member_read ON public.answer_cache; CREATE POLICY answer_cache_member_read ON public.answer_cache FOR SELECT USING (app.is_member(course_id));" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; SELECT CASE WHEN count(*)=1 THEN 'LEAK__CROSS_AUDIENCE_CACHE_READ' ELSE 'SAFE' END FROM public.answer_cache WHERE audience='instructor';" \
    "LEAK__CROSS_AUDIENCE_CACHE_READ" || failures=$((failures + 1))

run_mutation 5 \
    "cache INSERT audience sarti dusurulurse" \
    "DROP POLICY answer_cache_member_insert ON public.answer_cache; CREATE POLICY answer_cache_member_insert ON public.answer_cache FOR INSERT WITH CHECK (app.is_member(course_id));" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; INSERT INTO public.answer_cache (course_id,audience,policy_revision,prompt_revision,corpus_revision,question_hash,answer) VALUES ('$COURSE','instructor','p2','r2','c2','forged-instructor','{}'::jsonb); RESET ROLE; SELECT CASE WHEN count(*)=1 THEN 'LEAK__CROSS_AUDIENCE_CACHE_INSERT' ELSE 'SAFE' END FROM public.answer_cache WHERE question_hash='forged-instructor';" \
    "LEAK__CROSS_AUDIENCE_CACHE_INSERT" || failures=$((failures + 1))

run_mutation 6 \
    "function-only tablo worker'a GRANT edilirse" \
    "INSERT INTO public.ai_token_reservations(id,course_id,user_id,audience,reserved_tokens,charged_tokens,expires_at) VALUES ('50505050-0000-0000-0000-000000000020','$COURSE','$STUDENT','student',10,10,now()+interval '1 minute'); GRANT SELECT ON public.ai_token_reservations TO dou_worker;" \
    "SET ROLE dou_worker; SELECT CASE WHEN count(*)=1 THEN 'LEAK__DIRECT_QUOTA_TABLE_GRANT' ELSE 'SAFE' END FROM public.ai_token_reservations;" \
    "LEAK__DIRECT_QUOTA_TABLE_GRANT" || failures=$((failures + 1))

run_mutation 7 \
    "SECURITY DEFINER PUBLIC EXECUTE geri verilirse" \
    "GRANT EXECUTE ON FUNCTION app.reserve_course_agent_tokens(uuid,uuid,integer,integer,integer,integer,integer) TO PUBLIC;" \
    "SET ROLE dou_worker; SET app.current_user_id='$STUDENT'; SELECT CASE WHEN allowed THEN 'LEAK__PUBLIC_EXECUTE_RESERVATION' ELSE 'SAFE' END FROM app.reserve_course_agent_tokens('$COURSE','50505050-0000-0000-0000-000000000021',10,60,50000,500000,5000000);" \
    "LEAK__PUBLIC_EXECUTE_RESERVATION" || failures=$((failures + 1))

run_lock_race_mutation 8 \
    "atomik rezervasyon advisory lock'lari kaldirilirsa" || failures=$((failures + 1))

run_mutation 9 \
    "yalniz gunluk token kota karari kaldirilirsa" \
    "$QUOTA_BYPASS_SQL" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; SELECT CASE WHEN allowed THEN 'LEAK__DAILY_QUOTA_OVERSHOOT' ELSE 'SAFE' END FROM app.reserve_course_agent_tokens('$COURSE','50505050-0000-0000-0000-000000000041',1,60,50000,500000,5000000);" \
    "LEAK__DAILY_QUOTA_OVERSHOOT" || failures=$((failures + 1))

run_mutation 10 \
    "yalniz aktif reservation tavani kaldirilirsa" \
    "$CONCURRENCY_BYPASS_SQL" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; SELECT allowed FROM app.reserve_course_agent_tokens('$COURSE','50505050-0000-0000-0000-000000000070',10,60,50000,500000,5000000); SELECT allowed FROM app.reserve_course_agent_tokens('$COURSE','50505050-0000-0000-0000-000000000071',10,60,50000,500000,5000000); RESET ROLE; SELECT CASE WHEN count(*)=2 AND sum(charged_tokens)=20 THEN 'LEAK__CONCURRENCY_OVERSHOOT' ELSE 'SAFE' END FROM public.ai_token_reservations WHERE id IN ('50505050-0000-0000-0000-000000000070','50505050-0000-0000-0000-000000000071');" \
    "LEAK__CONCURRENCY_OVERSHOOT" || failures=$((failures + 1))

run_mutation 11 \
    "KVKK privacy okuma politikalari acilirsa" \
    "DROP POLICY chat_sessions_self_read ON public.chat_sessions; DROP POLICY chat_sessions_privacy_self_read ON public.chat_sessions; CREATE POLICY chat_sessions_privacy_read_leak ON public.chat_sessions FOR SELECT USING (true);" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; SELECT CASE WHEN count(*)=1 THEN 'LEAK__PRIVACY_OTHER_SESSION_READ' ELSE 'SAFE' END FROM public.chat_sessions WHERE id='$OTHER_SESSION';" \
    "LEAK__PRIVACY_OTHER_SESSION_READ" || failures=$((failures + 1))

run_mutation 12 \
    "KVKK message self-read kaldirilirsa" \
    "DROP POLICY chat_messages_privacy_self_read ON public.chat_messages; UPDATE public.course_memberships SET status='revoked' WHERE course_id='$COURSE' AND user_id='$STUDENT';" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; SELECT CASE WHEN count(*)=0 THEN 'LEAK__REVOKED_MESSAGES_TRUNCATED' ELSE 'SAFE' END FROM public.chat_messages WHERE id='$STUDENT_MESSAGE';" \
    "LEAK__REVOKED_MESSAGES_TRUNCATED" || failures=$((failures + 1))

run_mutation 13 \
    "KVKK feedback self-read kaldirilirsa" \
    "DROP POLICY chat_feedback_privacy_self_read ON public.chat_message_feedback; UPDATE public.course_memberships SET status='revoked' WHERE course_id='$COURSE' AND user_id='$STUDENT';" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; SELECT CASE WHEN count(*)=0 THEN 'LEAK__REVOKED_FEEDBACK_TRUNCATED' ELSE 'SAFE' END FROM public.chat_message_feedback WHERE id='$STUDENT_FEEDBACK';" \
    "LEAK__REVOKED_FEEDBACK_TRUNCATED" || failures=$((failures + 1))

run_mutation 14 \
    "KVKK message self-read baska kullaniciya acilirsa" \
    "DROP POLICY chat_messages_privacy_self_read ON public.chat_messages; CREATE POLICY chat_messages_privacy_self_read ON public.chat_messages FOR SELECT USING (true);" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; SELECT CASE WHEN count(*)=1 THEN 'LEAK__PRIVACY_OTHER_MESSAGE_READ' ELSE 'SAFE' END FROM public.chat_messages WHERE id='$OTHER_MESSAGE';" \
    "LEAK__PRIVACY_OTHER_MESSAGE_READ" || failures=$((failures + 1))

run_mutation 15 \
    "KVKK feedback self-read baska kullaniciya acilirsa" \
    "DROP POLICY chat_feedback_privacy_self_read ON public.chat_message_feedback; CREATE POLICY chat_feedback_privacy_self_read ON public.chat_message_feedback FOR SELECT USING (true);" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; SELECT CASE WHEN count(*)=1 THEN 'LEAK__PRIVACY_OTHER_FEEDBACK_READ' ELSE 'SAFE' END FROM public.chat_message_feedback WHERE id='$OTHER_FEEDBACK';" \
    "LEAK__PRIVACY_OTHER_FEEDBACK_READ" || failures=$((failures + 1))

run_inactive_backfill_mutation || failures=$((failures + 1))

echo
echo "HARIC: /me/export aktif-sinav 423 + advisory lock HTTP/uygulama katmanidir; SQL mutasyonu uydurulmadi."
if ((failures > 0)); then
    echo "$failures mutasyon beklenen kesin sizintiyi uretmedi."
    exit 1
fi

echo "16 mutasyon denendi, 16 kesin sizinti yakalandi."
echo "Gecici mutasyon DB'leri temizlendi; sablon cikista temizlenecek."
