#!/usr/bin/env bash
# Her mutasyon ayrı kopyada denenir; bozulmamış referans önce yeşil olmalıdır.
set -euo pipefail
TEMPLATE_DB="${1:-dou_l2_learning_events_template}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEST_SQL="${REPO_ROOT}/supabase/tests/rls_learning_events.sql"
PSQL="${PG_BIN:+${PG_BIN}/}psql"
CREATEDB="${PG_BIN:+${PG_BIN}/}createdb"
DROPDB="${PG_BIN:+${PG_BIN}/}dropdb"
SCRATCH=""
cleanup() { if [ -n "$SCRATCH" ]; then "$DROPDB" --if-exists "$SCRATCH"; fi; }
trap cleanup EXIT

if ! "$PSQL" -lqtA -d postgres | cut -d'|' -f1 | grep -qx "$TEMPLATE_DB"; then
    "$CREATEDB" "$TEMPLATE_DB"
    for migration in "${REPO_ROOT}"/supabase/migrations/*.sql; do
        "$PSQL" -v ON_ERROR_STOP=1 -q -d "$TEMPLATE_DB" -f "$migration"
    done
fi
baseline=$("$PSQL" -v ON_ERROR_STOP=1 -d "$TEMPLATE_DB" -f "$TEST_SQL" 2>&1)
if grep -q 'FAIL  ' <<<"$baseline" || ! grep -q 'PASS  ' <<<"$baseline"; then
    echo "HATA: referans koşu yeşil değil"
    exit 1
fi
echo "Referans RLS koşusu yeşil."
MUTATIONS=(
"öğrenci satır politikası açılır|ALTER POLICY learning_events_self_read ON public.learning_events USING (true);|student_cannot_read_peer"
"öğrenci satır politikası kaldırılır|DROP POLICY learning_events_self_read ON public.learning_events;|student_reads_own_events"
"eğitmene ham satır politikası eklenir|CREATE POLICY learning_events_instructor_leak ON public.learning_events FOR SELECT TO dou_app USING (app.is_instructor(course_id));|instructor_cannot_read_raw_events"
"API INSERT yetkisi açılır|GRANT INSERT ON public.learning_events TO dou_app;|app_has_no_insert_grant"
"özet eğitmen kontrolü kaldırılır|DO \$m\$ BEGIN EXECUTE replace(pg_get_functiondef('app.learning_summary(uuid,integer)'::regprocedure), 'OR NOT app.is_instructor(p_course_id)', ''); END \$m\$;|student_cannot_read_aggregate"
"pseudo gerçek kullanıcıya döner|DO \$m\$ BEGIN EXECUTE replace(pg_get_functiondef('app.learning_actor_pseudo_id(uuid)'::regprocedure), 'RETURN result;', 'RETURN app.current_user_id();'); END \$m\$;|pseudo_is_not_user_id"
"ham içerik kısıtı kaldırılır|ALTER TABLE public.learning_events DROP CONSTRAINT learning_events_outcome_shape;|writer_rejects_raw_content"
)
total=0
for entry in "${MUTATIONS[@]}"; do
    IFS='|' read -r name mutation expected <<<"$entry"
    total=$((total + 1))
    SCRATCH="dou_l2_learning_mut_$$_${total}"
    "$CREATEDB" -T "$TEMPLATE_DB" "$SCRATCH"
    "$PSQL" -v ON_ERROR_STOP=1 -q -d "$SCRATCH" -c "$mutation"
    result=0
    output=$("$PSQL" -v ON_ERROR_STOP=1 -d "$SCRATCH" -f "$TEST_SQL" 2>&1) || result=$?
    "$DROPDB" "$SCRATCH"
    SCRATCH=""
    if [ "$result" -eq 0 ] || ! grep -q "FAIL  ${expected}" <<<"$output"; then
        printf 'KAÇIRILDI %s (%s)\n%s\n' "$name" "$expected" "$output"
        exit 1
    fi
    printf 'YAKALANDI %s -> %s\n' "$name" "$expected"
done
printf '%s mutasyonun tamamı ilgili iddiayı kırmızıya çevirdi.\n' "$total"
