#!/usr/bin/env bash
# 0016 backfill'inin eski mutable takvimdeki en geç cohort süresini koruduğunu kanıtlar.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PSQL="${PG_BIN:+${PG_BIN}/}psql"
CREATEDB="${PG_BIN:+${PG_BIN}/}createdb"
DROPDB="${PG_BIN:+${PG_BIN}/}dropdb"
DATABASE="${1:-assessment_integrity_upgrade_$$}"

if [[ ! "$DATABASE" =~ ^assessment_integrity_upgrade_[A-Za-z0-9_]+$ ]]; then
    echo "HATA: güvenli ve benzersiz bir assessment_integrity_upgrade_* DB adı gerekli." >&2
    exit 2
fi
if ((${#DATABASE} > 63)); then
    echo "HATA: PostgreSQL DB adı 63 karakteri geçemez." >&2
    exit 2
fi
if "$PSQL" -X -At -d postgres -c "SELECT datname FROM pg_database" | grep -Fxq "$DATABASE"; then
    echo "HATA: mevcut veritabanına dokunulmayacak: $DATABASE" >&2
    exit 2
fi

cleanup() {
    "$DROPDB" --if-exists "$DATABASE" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

"$CREATEDB" "$DATABASE"
for migration in "$REPO_ROOT"/supabase/migrations/*.sql; do
    [[ "$(basename "$migration")" == "0016_assessment_integrity.sql" ]] && break
    "$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$DATABASE" -f "$migration"
done

"$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$DATABASE" <<'SQL'
INSERT INTO profiles (id, email) VALUES
    ('a1000000-0000-0000-0000-000000000001', 'upgrade-instructor@example.invalid'),
    ('a1000000-0000-0000-0000-000000000002', 'upgrade-student-a@example.invalid'),
    ('a1000000-0000-0000-0000-000000000003', 'upgrade-student-b@example.invalid'),
    ('a1000000-0000-0000-0000-000000000004', 'upgrade-legacy@example.invalid'),
    ('a1000000-0000-0000-0000-000000000005', 'upgrade-new-student@example.invalid');

INSERT INTO courses (id, code, title, created_by) VALUES (
    'a2000000-0000-0000-0000-000000000001', 'UPGRADE009', 'Upgrade cohort',
    'a1000000-0000-0000-0000-000000000001'
);

INSERT INTO course_memberships (course_id, user_id, role) VALUES
    ('a2000000-0000-0000-0000-000000000001',
     'a1000000-0000-0000-0000-000000000001', 'instructor'),
    ('a2000000-0000-0000-0000-000000000001',
     'a1000000-0000-0000-0000-000000000002', 'student'),
    ('a2000000-0000-0000-0000-000000000001',
     'a1000000-0000-0000-0000-000000000003', 'student');
INSERT INTO course_memberships (course_id, user_id, role) VALUES
    ('a2000000-0000-0000-0000-000000000001',
     'a1000000-0000-0000-0000-000000000004', 'student'),
    ('a2000000-0000-0000-0000-000000000001',
     'a1000000-0000-0000-0000-000000000005', 'student');

INSERT INTO documents (
    id, course_id, uploaded_by, file_name, file_type, storage_path,
    file_hash, byte_size, status
) VALUES (
    'a6000000-0000-0000-0000-000000000001',
    'a2000000-0000-0000-0000-000000000001',
    'a1000000-0000-0000-0000-000000000001',
    'mixed-use.pdf', 'pdf', 'upgrade/mixed-use.pdf', 'mixed-use-hash', 128, 'completed'
);

INSERT INTO chunks (
    id, course_id, document_id, chunk_index, page_number, text, token_count
) VALUES (
    'a6100000-0000-0000-0000-000000000001',
    'a2000000-0000-0000-0000-000000000001',
    'a6000000-0000-0000-0000-000000000001', 0, 1,
    'Ayni eski soru legacy ve blueprint kagidinda kullanildi.', 9
);

INSERT INTO topics (id, course_id, name, created_by) VALUES (
    'a6200000-0000-0000-0000-000000000001',
    'a2000000-0000-0000-0000-000000000001', 'Mixed use',
    'a1000000-0000-0000-0000-000000000001'
);

INSERT INTO learning_outcomes (
    id, course_id, code, description, topic_id, created_by
) VALUES (
    'a6300000-0000-0000-0000-000000000001',
    'a2000000-0000-0000-0000-000000000001', 'UP-LO1',
    'Legacy ve resmi kagidi ayirir.',
    'a6200000-0000-0000-0000-000000000001',
    'a1000000-0000-0000-0000-000000000001'
);

INSERT INTO questions (
    id, course_id, topic_id, type, payload, source_chunk_id, status,
    created_by, reviewed_by, reviewed_at, learning_outcome_id, difficulty
) VALUES (
    'a6400000-0000-0000-0000-000000000001',
    'a2000000-0000-0000-0000-000000000001',
    'a6200000-0000-0000-0000-000000000001', 'open',
    '{"prompt":"Mixed use soru","answer_key":"guvenli cevap","key_points":["guven"]}',
    'a6100000-0000-0000-0000-000000000001', 'approved',
    'a1000000-0000-0000-0000-000000000001',
    'a1000000-0000-0000-0000-000000000001', now(),
    'a6300000-0000-0000-0000-000000000001', 'easy'
);

INSERT INTO exam_blueprints (
    id, course_id, title, duration_minutes, max_attempts, opens_at, closes_at, created_by
) VALUES (
    'a3000000-0000-0000-0000-000000000001',
    'a2000000-0000-0000-0000-000000000001', 'Mutable legacy schedule', 60, 1,
    now() - interval '1 hour', now() + interval '2 hours',
    'a1000000-0000-0000-0000-000000000001'
);

INSERT INTO exam_versions (
    id, course_id, blueprint_id, version_no, status, published_at, published_by,
    blueprint_snapshot
) VALUES (
    'a4000000-0000-0000-0000-000000000001',
    'a2000000-0000-0000-0000-000000000001',
    'a3000000-0000-0000-0000-000000000001', 1, 'published', now(),
    'a1000000-0000-0000-0000-000000000001', '[]'
);

INSERT INTO exam_sessions (
    id, course_id, user_id, mode, started_at, expires_at, question_ids,
    exam_version_id, exam_blueprint_id, attempt_no
) VALUES
    ('a5000000-0000-0000-0000-000000000001',
     'a2000000-0000-0000-0000-000000000001',
     'a1000000-0000-0000-0000-000000000002', 'exam', now(),
     now() + interval '10 minutes', NULL,
     'a4000000-0000-0000-0000-000000000001',
     'a3000000-0000-0000-0000-000000000001', 1),
    ('a5000000-0000-0000-0000-000000000002',
     'a2000000-0000-0000-0000-000000000001',
     'a1000000-0000-0000-0000-000000000003', 'exam', now(),
     now() + interval '50 minutes', NULL,
     'a4000000-0000-0000-0000-000000000001',
     'a3000000-0000-0000-0000-000000000001', 1);

INSERT INTO exam_items (
    id, course_id, exam_version_id, position, question_id, points
) VALUES (
    'a6500000-0000-0000-0000-000000000001',
    'a2000000-0000-0000-0000-000000000001',
    'a4000000-0000-0000-0000-000000000001', 1,
    'a6400000-0000-0000-0000-000000000001', 100
);

INSERT INTO exam_sessions (
    id, course_id, user_id, mode, started_at, question_ids
) VALUES (
    'a6600000-0000-0000-0000-000000000001',
    'a2000000-0000-0000-0000-000000000001',
    'a1000000-0000-0000-0000-000000000004', 'practice', now(),
    ARRAY['a6400000-0000-0000-0000-000000000001'::uuid]
);

INSERT INTO answers (
    id, session_id, question_id, course_id, given, score, is_correct, feedback
) VALUES (
    'a6700000-0000-0000-0000-000000000001',
    'a6600000-0000-0000-0000-000000000001',
    'a6400000-0000-0000-0000-000000000001',
    'a2000000-0000-0000-0000-000000000001', 'guvenli cevap', 100, true,
    '{"durum":"degerlendirildi"}'
);

-- 0008 bunu ilk oturumdan sonra da kabul ediyordu. Satır-bazlı backfill kısa
-- oturumu deploy+1 dakika içinde açar ve uzun oturum sürerken cevap sızdırırdı.
UPDATE exam_blueprints
SET duration_minutes = 1, closes_at = now() - interval '1 hour'
WHERE id = 'a3000000-0000-0000-0000-000000000001';

-- 0001'i farklı bir migration owner'ı çalıştırmış gibi ikinci bir default ACL
-- kaydı bırak. 0016 yalnız current_user'ı düzeltirse bu blanket grant yaşayacaktır.
ALTER DEFAULT PRIVILEGES FOR ROLE dou_worker IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO dou_app;
ALTER DEFAULT PRIVILEGES FOR ROLE dou_worker IN SCHEMA app
    GRANT EXECUTE ON FUNCTIONS TO PUBLIC;

-- Farklı migration owner'ın app fonksiyonu, owner keşif kümesine gerçek bir satır
-- ekler. PostgreSQL'in global PUBLIC EXECUTE varsayılanı 0016'da kaldırılmalıdır.
GRANT CREATE ON SCHEMA app TO dou_worker;
SET ROLE dou_worker;
CREATE FUNCTION app.upgrade_owner_probe_pre() RETURNS integer
LANGUAGE sql AS 'SELECT 1';
RESET ROLE;
REVOKE CREATE ON SCHEMA app FROM dou_worker;
SQL

"$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$DATABASE" \
    -f "$REPO_ROOT/supabase/migrations/0016_assessment_integrity.sql"

result=$("$PSQL" -X -At -v ON_ERROR_STOP=1 -d "$DATABASE" <<'SQL'
WITH cohort AS (
    SELECT max(expires_at) AS max_expires_at
    FROM exam_sessions
    WHERE exam_blueprint_id = 'a3000000-0000-0000-0000-000000000001'
), unsafe AS (
    SELECT 1
    FROM exam_sessions, cohort
    WHERE exam_blueprint_id = 'a3000000-0000-0000-0000-000000000001'
      AND feedback_available_at < cohort.max_expires_at
)
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM unsafe)
                 AND count(DISTINCT feedback_available_at) = 1
            THEN 'PASS  upgrade_backfill__tum_cohort_en_gec_expiry_sinirinda'
            ELSE 'FAIL  upgrade_backfill__tum_cohort_en_gec_expiry_sinirinda'
       END
FROM exam_sessions
WHERE exam_blueprint_id = 'a3000000-0000-0000-0000-000000000001';
SQL
)

printf '%s\n' "$result"
if grep -Fq 'FAIL  ' <<<"$result"; then
    exit 1
fi

mixed_result=$("$PSQL" -X -At -v ON_ERROR_STOP=1 -d "$DATABASE" <<'SQL'
SET SESSION AUTHORIZATION dou_api_runtime;
SET app.current_user_id = 'a1000000-0000-0000-0000-000000000004';

WITH legacy_state AS (
    SELECT
        session_row.question_ids,
        answer.question_id AS answer_question_id
    FROM exam_sessions session_row
    JOIN answers answer ON answer.session_id = session_row.id
    WHERE session_row.id = 'a6600000-0000-0000-0000-000000000001'
)
SELECT CASE WHEN
           (SELECT count(*) FROM questions
            WHERE id = 'a6400000-0000-0000-0000-000000000001'
              AND purpose = 'assessment') = 1
           AND (SELECT question_ids[1] = 'a6400000-0000-0000-0000-000000000001'
                FROM legacy_state)
           AND (SELECT answer_question_id = 'a6400000-0000-0000-0000-000000000001'
                FROM legacy_state)
       THEN 'PASS  upgrade_mixed_use__yalniz_legacy_oturum_sahibi_devam_eder'
       ELSE 'FAIL  upgrade_mixed_use__yalniz_legacy_oturum_sahibi_devam_eder'
       END;

SET app.current_user_id = 'a1000000-0000-0000-0000-000000000005';
SELECT CASE WHEN count(*) = 0
       THEN 'PASS  upgrade_mixed_use__yeni_ogrenci_resmi_soruyu_goremez'
       ELSE 'FAIL  upgrade_mixed_use__yeni_ogrenci_resmi_soruyu_goremez'
       END
FROM questions
WHERE id = 'a6400000-0000-0000-0000-000000000001';
SQL
)

printf '%s\n' "$mixed_result"
if grep -Fq 'FAIL  ' <<<"$mixed_result"; then
    exit 1
fi

"$PSQL" -X -v ON_ERROR_STOP=1 -q -d "$DATABASE" <<'SQL'
GRANT CREATE ON SCHEMA app TO dou_worker;
SET ROLE dou_worker;
CREATE FUNCTION app.upgrade_default_acl_probe_post() RETURNS integer
LANGUAGE sql AS 'SELECT 1';
RESET ROLE;
REVOKE CREATE ON SCHEMA app FROM dou_worker;
SQL

defaults_result=$("$PSQL" -X -At -v ON_ERROR_STOP=1 -d "$DATABASE" <<'SQL'
SELECT CASE WHEN NOT EXISTS (
           SELECT 1
           FROM pg_default_acl defaults
           CROSS JOIN LATERAL aclexplode(defaults.defaclacl) privilege
           JOIN pg_roles grantee ON grantee.oid = privilege.grantee
           WHERE defaults.defaclnamespace = 'public'::regnamespace
             AND defaults.defaclobjtype = 'r'
             AND grantee.rolname IN ('dou_app', 'dou_worker')
             AND privilege.privilege_type IN ('SELECT', 'INSERT', 'UPDATE', 'DELETE')
       ) AND NOT EXISTS (
           SELECT 1
           FROM pg_default_acl defaults
           CROSS JOIN LATERAL aclexplode(defaults.defaclacl) privilege
           WHERE defaults.defaclnamespace = 'app'::regnamespace
             AND defaults.defaclobjtype = 'f'
             AND privilege.grantee = 0
             AND privilege.privilege_type = 'EXECUTE'
       ) AND NOT EXISTS (
           SELECT 1
           FROM pg_proc proc
           CROSS JOIN LATERAL aclexplode(
               COALESCE(proc.proacl, acldefault('f', proc.proowner))
           ) privilege
           WHERE proc.pronamespace = 'app'::regnamespace
             AND proc.proname = 'upgrade_default_acl_probe_post'
             AND privilege.grantee = 0
             AND privilege.privilege_type = 'EXECUTE'
       ) THEN 'PASS  upgrade_defaults__tum_owner_grantleri_ve_public_execute_temiz'
       ELSE 'FAIL  upgrade_defaults__tum_owner_grantleri_ve_public_execute_temiz'
       END;
SQL
)

printf '%s\n' "$defaults_result"
if grep -Fq 'FAIL  ' <<<"$defaults_result"; then
    exit 1
fi
