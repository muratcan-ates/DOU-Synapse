#!/usr/bin/env bash
# Mutate only disposable clones; the supplied migrated test template is untouched.
# PGHOST/PGPORT/PGUSER must address an isolated test cluster.
set -euo pipefail
TEMPLATE_DB="${1:?Pass an empty migrated test database name}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PSQL="${PG_BIN:+${PG_BIN}/}psql"
CREATEDB="${PG_BIN:+${PG_BIN}/}createdb"
DROPDB="${PG_BIN:+${PG_BIN}/}dropdb"
TEST_SQL="$REPO_ROOT/supabase/tests/rls_question_authoring.sql"
scratch=""
cleanup() { if [[ -n "$scratch" ]]; then "$DROPDB" --if-exists --force "$scratch" >/dev/null; fi; }
trap cleanup EXIT

baseline=$("$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$TEMPLATE_DB" -f "$TEST_SQL" 2>&1)
if [[ "$baseline" == *FAIL* ]] || [[ "$baseline" != *'PASS  question_authoring_all'* ]]; then
    printf '%s\n' "$baseline"
    exit 1
fi
printf 'PASS  baseline_question_authoring\n'

MUTATIONS=(
"guard_removed|DROP TRIGGER questions_authoring_guard ON public.questions;|approved_payload_immutable"
"rls_update_open|DROP POLICY questions_instructor_update ON questions; CREATE POLICY questions_instructor_update ON questions FOR UPDATE USING (true) WITH CHECK (true);|student_cannot_edit_visible_question"
"worker_update_granted|GRANT UPDATE ON public.questions TO dou_worker;|worker_cannot_author_questions"
"identity_update_granted|GRANT UPDATE ON public.questions TO dou_app;|identity_column_grant_denied"
)
index=0
for entry in "${MUTATIONS[@]}"; do
    IFS='|' read -r label sql expected <<<"$entry"
    index=$((index + 1))
    scratch="dou013_sql_mut_$$_$index"
    "$CREATEDB" -T "$TEMPLATE_DB" "$scratch"
    "$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$scratch" -c "$sql"
    result=$("$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$scratch" -f "$TEST_SQL" 2>&1)
    if [[ "$result" != *"FAIL  $expected"* ]]; then
        printf 'FAIL  missed_%s\n%s\n' "$label" "$result"
        exit 1
    fi
    printf 'PASS  caught_%s -> %s\n' "$label" "$expected"
    "$DROPDB" "$scratch"
    scratch=""
done

# The array reference has no FK: removing its explicit row lock must turn the
# concurrent-edit check red, independently of the content guard after commit.
python3 "$REPO_ROOT/supabase/tests/question_authoring_concurrency_check.py" "$TEMPLATE_DB"
scratch="dou013_sql_mut_$$_references"
"$CREATEDB" -T "$TEMPLATE_DB" "$scratch"
"$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$scratch" -c 'DROP TRIGGER exam_sessions_authoring_reference_lock ON public.exam_sessions;'
set +e
result=$(python3 "$REPO_ROOT/supabase/tests/question_authoring_concurrency_check.py" "$scratch" exam_sessions 2>&1)
exit_code=$?
set -e
if [[ "$exit_code" -eq 0 ]] || [[ "$result" != *'FAIL  concurrent_exam_sessions_blocks_raw_edit'* ]]; then
    printf 'FAIL  missed_reference_lock_mutation\n%s\n' "$result"
    exit 1
fi
printf 'PASS  caught_reference_lock_removed\n'
