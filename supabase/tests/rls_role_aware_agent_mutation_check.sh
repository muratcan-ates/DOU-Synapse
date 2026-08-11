#!/usr/bin/env bash
#
# 005 role-aware course agent veritabani sinirlarinin KIRMIZI yanabildiginin kaniti.
#
# Bu betik gercek/ortak `dou_synapse` veritabanina HIC BAGLANMAZ. Her kosuda PID ile
# adlandirilmis yeni bir sablon DB kurar, tum migrasyonlari uygular, referans davranisi
# ayri bir klonda dogrular ve her gevsetmeyi sablonun yeni bir klonunda sinar. Basari,
# hata veya sinyal durumunda olusturdugu tum DB'leri EXIT trap'i ile temizler.
#
# Mutasyon kapsami:
#   1. chat_sessions.audience hem degistirilemez trigger'i hem RLS persona eslesmesi,
#   2. answer_cache icin ayni ders icinde cross-audience SELECT ve INSERT,
#   3. function-only kota tablolarinin dogrudan GRANT siniri,
#   4. SECURITY DEFINER kota yardimcisinin PUBLIC/dou_worker EXECUTE siniri,
#   5. kalici token on-odemesinin birlikte gevsetilen kota/eszamanlilik tavanlarini
#      asamamasi,
#   6. KVKK sohbet gecmisinin yalniz satir sahibine gorunmesi.
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
COURSE="aaaaaaaa-0000-0000-0000-000000000005"
STUDENT_SESSION="51515151-0000-0000-0000-000000000001"
OTHER_SESSION="51515151-0000-0000-0000-000000000002"

if [[ ! "$TEMPLATE_DB" =~ ^rls_role_agent_[A-Za-z0-9_]+$ ]]; then
    echo "HATA: sablon DB adi rls_role_agent_ ile baslayan guvenli bir ad olmali." >&2
    exit 2
fi

if "$PSQL" -lqtA -d postgres 2>/dev/null | cut -d'|' -f1 | grep -qx "$TEMPLATE_DB"; then
    echo "HATA: $TEMPLATE_DB zaten var; mevcut bir DB'ye dokunulmayacak." >&2
    exit 2
fi

created_databases=()
cleanup() {
    local db
    local db_index
    for ((db_index=${#created_databases[@]} - 1; db_index >= 0; db_index--)); do
        db="${created_databases[$db_index]}"
        "$DROPDB" --if-exists "$db" >/dev/null 2>&1 || true
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
    ('$OTHER_STUDENT', 'agent.other.005@dogus.edu.tr', '005 Diger Ogrenci');

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

INSERT INTO public.answer_cache (
    id, course_id, audience, policy_revision, prompt_revision, corpus_revision,
    question_hash, answer
) VALUES
    ('acacacac-0000-0000-0000-000000000001', '$COURSE', 'student',
     'p1', 'r1', 'c1', 'student-only', '{"text":"student"}'::jsonb),
    ('acacacac-0000-0000-0000-000000000002', '$COURSE', 'instructor',
     'p1', 'r1', 'c1', 'instructor-only', '{"text":"instructor"}'::jsonb);
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

echo "referans kosu temiz (7 kapali sinir + 3 kalici kota iddiasi)"
drop_database_now "$REFERENCE_DB"
echo

QUOTA_BYPASS_SQL=$(cat <<'SQL'
CREATE OR REPLACE FUNCTION app.reserve_course_agent_tokens(
    p_course_id uuid,
    p_reservation_id uuid,
    p_requested_tokens integer,
    p_lease_seconds integer,
    p_user_hard_limit integer,
    p_course_hard_limit integer,
    p_platform_hard_limit integer
)
RETURNS TABLE (
    allowed boolean,
    reason text,
    audience assistant_audience,
    retry_after_seconds integer,
    reservation_id uuid
)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public, app
AS $function$
DECLARE
    v_user_id uuid := app.current_user_id();
    v_audience assistant_audience;
BEGIN
    SELECT CASE m.role WHEN 'instructor' THEN 'instructor'::assistant_audience
                      ELSE 'student'::assistant_audience END
    INTO v_audience
    FROM public.course_memberships AS m
    WHERE m.course_id=p_course_id AND m.user_id=v_user_id AND m.status='active';
    INSERT INTO public.ai_token_reservations(
        id, course_id, user_id, audience, reserved_tokens, charged_tokens, expires_at
    ) VALUES (
        p_reservation_id, p_course_id, v_user_id, v_audience,
        p_requested_tokens, p_requested_tokens, now()+make_interval(secs=>p_lease_seconds)
    );
    RETURN QUERY SELECT true, NULL::text, v_audience, 0, p_reservation_id;
END
$function$;
SQL
)

failures=0

run_mutation 1 \
    "audience immutability trigger dusurulurse" \
    "DROP TRIGGER chat_session_audience_immutable ON public.chat_sessions;" \
    "UPDATE public.chat_sessions SET audience='instructor' WHERE id='$STUDENT_SESSION'; SELECT CASE WHEN audience='instructor' THEN 'LEAK__AUDIENCE_MUTATED' ELSE 'SAFE' END FROM public.chat_sessions WHERE id='$STUDENT_SESSION';" \
    "LEAK__AUDIENCE_MUTATED" || failures=$((failures + 1))

run_mutation 2 \
    "session audience RLS eslesmesi dusurulurse" \
    "DROP POLICY chat_sessions_self_insert ON public.chat_sessions; CREATE POLICY chat_sessions_self_insert ON public.chat_sessions FOR INSERT WITH CHECK (user_id=app.current_user_id() AND app.is_member(course_id));" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; INSERT INTO public.chat_sessions (course_id,user_id,mode,audience) VALUES ('$COURSE','$STUDENT','qa','instructor'); RESET ROLE; SELECT CASE WHEN count(*)=1 THEN 'LEAK__FORGED_INSTRUCTOR_SESSION' ELSE 'SAFE' END FROM public.chat_sessions WHERE user_id='$STUDENT' AND audience='instructor';" \
    "LEAK__FORGED_INSTRUCTOR_SESSION" || failures=$((failures + 1))

run_mutation 3 \
    "cache SELECT audience sarti dusurulurse" \
    "DROP POLICY answer_cache_member_read ON public.answer_cache; CREATE POLICY answer_cache_member_read ON public.answer_cache FOR SELECT USING (app.is_member(course_id));" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; SELECT CASE WHEN count(*)=1 THEN 'LEAK__CROSS_AUDIENCE_CACHE_READ' ELSE 'SAFE' END FROM public.answer_cache WHERE audience='instructor';" \
    "LEAK__CROSS_AUDIENCE_CACHE_READ" || failures=$((failures + 1))

run_mutation 4 \
    "cache INSERT audience sarti dusurulurse" \
    "DROP POLICY answer_cache_member_insert ON public.answer_cache; CREATE POLICY answer_cache_member_insert ON public.answer_cache FOR INSERT WITH CHECK (app.is_member(course_id));" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; INSERT INTO public.answer_cache (course_id,audience,policy_revision,prompt_revision,corpus_revision,question_hash,answer) VALUES ('$COURSE','instructor','p2','r2','c2','forged-instructor','{}'::jsonb); RESET ROLE; SELECT CASE WHEN count(*)=1 THEN 'LEAK__CROSS_AUDIENCE_CACHE_INSERT' ELSE 'SAFE' END FROM public.answer_cache WHERE question_hash='forged-instructor';" \
    "LEAK__CROSS_AUDIENCE_CACHE_INSERT" || failures=$((failures + 1))

run_mutation 5 \
    "function-only tablo worker'a GRANT edilirse" \
    "INSERT INTO public.ai_token_reservations(id,course_id,user_id,audience,reserved_tokens,charged_tokens,expires_at) VALUES ('50505050-0000-0000-0000-000000000020','$COURSE','$STUDENT','student',10,10,now()+interval '1 minute'); GRANT SELECT ON public.ai_token_reservations TO dou_worker;" \
    "SET ROLE dou_worker; SELECT CASE WHEN count(*)=1 THEN 'LEAK__DIRECT_QUOTA_TABLE_GRANT' ELSE 'SAFE' END FROM public.ai_token_reservations;" \
    "LEAK__DIRECT_QUOTA_TABLE_GRANT" || failures=$((failures + 1))

run_mutation 6 \
    "SECURITY DEFINER PUBLIC EXECUTE geri verilirse" \
    "GRANT EXECUTE ON FUNCTION app.reserve_course_agent_tokens(uuid,uuid,integer,integer,integer,integer,integer) TO PUBLIC;" \
    "SET ROLE dou_worker; SET app.current_user_id='$STUDENT'; SELECT CASE WHEN allowed THEN 'LEAK__PUBLIC_EXECUTE_RESERVATION' ELSE 'SAFE' END FROM app.reserve_course_agent_tokens('$COURSE','50505050-0000-0000-0000-000000000021',10,60,50000,500000,5000000);" \
    "LEAK__PUBLIC_EXECUTE_RESERVATION" || failures=$((failures + 1))

run_mutation 7 \
    "kota ve eszamanlilik kontrolleri kaldirilirsa" \
    "$QUOTA_BYPASS_SQL" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; SELECT allowed FROM app.reserve_course_agent_tokens('$COURSE','50505050-0000-0000-0000-000000000030',60,60,50000,500000,5000000); SELECT allowed FROM app.reserve_course_agent_tokens('$COURSE','50505050-0000-0000-0000-000000000031',60,60,50000,500000,5000000); RESET ROLE; SELECT CASE WHEN count(*)=2 AND sum(charged_tokens)=120 THEN 'LEAK__QUOTA_AND_CONCURRENCY_OVERSHOOT' ELSE 'SAFE' END FROM public.ai_token_reservations;" \
    "LEAK__QUOTA_AND_CONCURRENCY_OVERSHOOT" || failures=$((failures + 1))

run_mutation 8 \
    "KVKK privacy okuma politikalari acilirsa" \
    "DROP POLICY chat_sessions_self_read ON public.chat_sessions; DROP POLICY chat_sessions_privacy_self_read ON public.chat_sessions; CREATE POLICY chat_sessions_privacy_read_leak ON public.chat_sessions FOR SELECT USING (true);" \
    "SET ROLE dou_app; SET app.current_user_id='$STUDENT'; SELECT CASE WHEN count(*)=1 THEN 'LEAK__PRIVACY_OTHER_SESSION_READ' ELSE 'SAFE' END FROM public.chat_sessions WHERE id='$OTHER_SESSION';" \
    "LEAK__PRIVACY_OTHER_SESSION_READ" || failures=$((failures + 1))

echo
echo "HARIC: /me/export aktif-sinav 423 + advisory lock HTTP/uygulama katmanidir; SQL mutasyonu uydurulmadi."
if ((failures > 0)); then
    echo "$failures mutasyon beklenen kesin sizintiyi uretmedi."
    exit 1
fi

echo "8 mutasyon denendi, 8 kesin sizinti yakalandi."
echo "Gecici mutasyon DB'leri temizlendi; sablon cikista temizlenecek."
