-- Assessment integrity'nin veritabani guvenlik kaniti (0016).
--
-- Bu dosya API'yi bilerek atlar. Soru amaci, donmus kagit erisimi, terminal
-- degismezlik ve worker yetkileri gercek dou_app/dou_worker rolleriyle sinanir.
-- Beklenen cikti: her iddia PASS. Herhangi bir FAIL CI kapisini kapatmalidir.
--
-- Calistirma:
--   psql -d dou_synapse -f supabase/tests/rls_assessment_integrity.sql

\set ON_ERROR_STOP on
\pset format unaligned
\pset tuples_only on

BEGIN;

-- ---------------------------------------------------------------------------
-- Seed: tablo sahibi olarak gercekci, kapanmis iki kagit ve bir taslak surum.
-- ---------------------------------------------------------------------------

INSERT INTO profiles (id, email, full_name) VALUES
    ('91000000-0000-0000-0000-000000000001', 'egitmen-009@dogus.edu.tr', '009 Egitmen'),
    ('91000000-0000-0000-0000-000000000002', 'ogrenci-a-009@dogus.edu.tr', '009 Ogrenci A'),
    ('91000000-0000-0000-0000-000000000003', 'ogrenci-b-009@dogus.edu.tr', '009 Ogrenci B'),
    ('91000000-0000-0000-0000-000000000004', 'uye-olmayan-009@dogus.edu.tr', '009 Uye Olmayan');

INSERT INTO courses (id, code, title, created_by) VALUES
    ('92000000-0000-0000-0000-000000000001', 'SEC009', 'Assessment Integrity',
     '91000000-0000-0000-0000-000000000001');

INSERT INTO course_memberships (course_id, user_id, role) VALUES
    ('92000000-0000-0000-0000-000000000001',
     '91000000-0000-0000-0000-000000000001', 'instructor'),
    ('92000000-0000-0000-0000-000000000001',
     '91000000-0000-0000-0000-000000000002', 'student'),
    ('92000000-0000-0000-0000-000000000001',
     '91000000-0000-0000-0000-000000000003', 'student');

INSERT INTO documents (
    id, course_id, uploaded_by, file_name, file_type, storage_path,
    file_hash, byte_size, status
) VALUES (
    '93000000-0000-0000-0000-000000000001',
    '92000000-0000-0000-0000-000000000001',
    '91000000-0000-0000-0000-000000000001',
    'assessment-integrity-009.pdf', 'pdf', 'courses/sec009/source.pdf',
    'assessment-integrity-009-hash', 1024, 'completed'
);

INSERT INTO chunks (
    id, course_id, document_id, chunk_index, page_number, text, token_count
) VALUES (
    '93100000-0000-0000-0000-000000000001',
    '92000000-0000-0000-0000-000000000001',
    '93000000-0000-0000-0000-000000000001',
    0, 1, 'Assessment sorulari yalniz donmus kagit sahibine acilir.', 9
);

INSERT INTO topics (id, course_id, name, created_by) VALUES (
    '93200000-0000-0000-0000-000000000001',
    '92000000-0000-0000-0000-000000000001',
    'Sinav Guvenligi',
    '91000000-0000-0000-0000-000000000001'
);

-- 1 practice, 3 approved assessment, 1 draft assessment, 1 rejected assessment.
INSERT INTO questions (
    id, course_id, topic_id, type, payload, source_chunk_id, status, purpose,
    created_by, reviewed_by, reviewed_at
) VALUES
    ('94000000-0000-0000-0000-000000000001',
     '92000000-0000-0000-0000-000000000001',
     '93200000-0000-0000-0000-000000000001', 'open',
     '{"stem":"Practice","answer_key":"practice-key"}',
     '93100000-0000-0000-0000-000000000001', 'approved', 'practice',
     '91000000-0000-0000-0000-000000000001',
     '91000000-0000-0000-0000-000000000001', now()),
    ('94000000-0000-0000-0000-000000000002',
     '92000000-0000-0000-0000-000000000001',
     '93200000-0000-0000-0000-000000000001', 'open',
     '{"stem":"Ogrenci A kagidi","answer_key":"a-key"}',
     '93100000-0000-0000-0000-000000000001', 'approved', 'assessment',
     '91000000-0000-0000-0000-000000000001',
     '91000000-0000-0000-0000-000000000001', now()),
    ('94000000-0000-0000-0000-000000000003',
     '92000000-0000-0000-0000-000000000001',
     '93200000-0000-0000-0000-000000000001', 'open',
     '{"stem":"Ogrenci B kagidi","answer_key":"b-key"}',
     '93100000-0000-0000-0000-000000000001', 'approved', 'assessment',
     '91000000-0000-0000-0000-000000000001',
     '91000000-0000-0000-0000-000000000001', now()),
    ('94000000-0000-0000-0000-000000000004',
     '92000000-0000-0000-0000-000000000001',
     '93200000-0000-0000-0000-000000000001', 'open',
     '{"stem":"Oturumsuz assessment","answer_key":"hidden-key"}',
     '93100000-0000-0000-0000-000000000001', 'approved', 'assessment',
     '91000000-0000-0000-0000-000000000001',
     '91000000-0000-0000-0000-000000000001', now()),
    ('94000000-0000-0000-0000-000000000005',
     '92000000-0000-0000-0000-000000000001',
     '93200000-0000-0000-0000-000000000001', 'open',
     '{"stem":"Taslak assessment","answer_key":"draft-key"}',
     '93100000-0000-0000-0000-000000000001', 'draft', 'assessment',
     '91000000-0000-0000-0000-000000000001', NULL, NULL),
    ('94000000-0000-0000-0000-000000000006',
     '92000000-0000-0000-0000-000000000001',
     '93200000-0000-0000-0000-000000000001', 'open',
     '{"stem":"Reddedilmis assessment","answer_key":"rejected-key"}',
     '93100000-0000-0000-0000-000000000001', 'rejected', 'assessment',
     '91000000-0000-0000-0000-000000000001',
     '91000000-0000-0000-0000-000000000001', now());

INSERT INTO exam_blueprints (
    id, course_id, title, duration_minutes, max_attempts,
    opens_at, closes_at, created_by
) VALUES
    ('95000000-0000-0000-0000-000000000001',
     '92000000-0000-0000-0000-000000000001', 'A kapanmis kagidi', 60, 1,
     now() - interval '4 hours', now() - interval '2 hours',
     '91000000-0000-0000-0000-000000000001'),
    ('95000000-0000-0000-0000-000000000002',
     '92000000-0000-0000-0000-000000000001', 'B kapanmis kagidi', 60, 1,
     now() - interval '4 hours', now() - interval '2 hours',
     '91000000-0000-0000-0000-000000000001'),
    ('95000000-0000-0000-0000-000000000003',
     '92000000-0000-0000-0000-000000000001', 'Taslak kagit', 60, 1,
     NULL, NULL, '91000000-0000-0000-0000-000000000001');

INSERT INTO exam_versions (id, course_id, blueprint_id, version_no) VALUES
    ('95100000-0000-0000-0000-000000000001',
     '92000000-0000-0000-0000-000000000001',
     '95000000-0000-0000-0000-000000000001', 1),
    ('95100000-0000-0000-0000-000000000002',
     '92000000-0000-0000-0000-000000000001',
     '95000000-0000-0000-0000-000000000002', 1),
    ('95100000-0000-0000-0000-000000000003',
     '92000000-0000-0000-0000-000000000001',
     '95000000-0000-0000-0000-000000000003', 1);

INSERT INTO exam_items (
    id, course_id, exam_version_id, position, question_id, points
) VALUES
    ('95200000-0000-0000-0000-000000000001',
     '92000000-0000-0000-0000-000000000001',
     '95100000-0000-0000-0000-000000000001', 1,
     '94000000-0000-0000-0000-000000000002', 50),
    ('95200000-0000-0000-0000-000000000002',
     '92000000-0000-0000-0000-000000000001',
     '95100000-0000-0000-0000-000000000002', 1,
     '94000000-0000-0000-0000-000000000003', 50);

-- Gecerli durum gecisleri seed'in bir parcasidir; invalid gecisler asagida
-- dou_app ile ayrica saldiri olarak sinanir.
UPDATE exam_versions
SET status = 'published', published_at = now(),
    published_by = '91000000-0000-0000-0000-000000000001',
    blueprint_snapshot = '[{"question_count":1,"points":50}]'
WHERE id = '95100000-0000-0000-0000-000000000001';

UPDATE exam_versions
SET status = 'superseded', superseded_at = now()
WHERE id = '95100000-0000-0000-0000-000000000001';

UPDATE exam_versions
SET status = 'published', published_at = now(),
    published_by = '91000000-0000-0000-0000-000000000001',
    blueprint_snapshot = '[{"question_count":1,"points":50}]'
WHERE id = '95100000-0000-0000-0000-000000000002';

INSERT INTO exam_sessions (
    id, course_id, user_id, mode, started_at, expires_at, finished_at,
    question_ids, exam_version_id, exam_blueprint_id, attempt_no,
    feedback_available_at
) VALUES
    ('95300000-0000-0000-0000-000000000001',
     '92000000-0000-0000-0000-000000000001',
     '91000000-0000-0000-0000-000000000002', 'exam',
     now() - interval '4 hours', now() - interval '3 hours', now() - interval '3 hours',
     NULL, '95100000-0000-0000-0000-000000000001',
     '95000000-0000-0000-0000-000000000001', 1, now() - interval '1 hour'),
    ('95300000-0000-0000-0000-000000000002',
     '92000000-0000-0000-0000-000000000001',
     '91000000-0000-0000-0000-000000000003', 'exam',
     now() - interval '4 hours', now() - interval '3 hours', now() - interval '3 hours',
     NULL, '95100000-0000-0000-0000-000000000002',
     '95000000-0000-0000-0000-000000000002', 1, now() - interval '1 hour');

-- ---------------------------------------------------------------------------
-- Soru gorunurlugu: gercek dou_app + ogrenci baglami.
-- ---------------------------------------------------------------------------

SET LOCAL ROLE dou_app;
SET LOCAL app.current_user_id = '91000000-0000-0000-0000-000000000002';

SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  question_purpose__approved_practice_ogrenciye_acik (beklenen 1, gelen '
       || count(*) || ')'
FROM questions
WHERE id = '94000000-0000-0000-0000-000000000001';

SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  question_purpose__kendi_superseded_kagit_sorusu_acik (beklenen 1, gelen '
       || count(*) || ')'
FROM questions
WHERE id = '94000000-0000-0000-0000-000000000002';

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  question_purpose__baska_ogrencinin_kagit_sorusu_kapali (beklenen 0, gelen '
       || count(*) || ')'
FROM questions
WHERE id = '94000000-0000-0000-0000-000000000003';

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  question_purpose__oturumsuz_assessment_kapali (beklenen 0, gelen '
       || count(*) || ')'
FROM questions
WHERE id = '94000000-0000-0000-0000-000000000004';

SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  blueprint_read__kapanistan_sonra_kendi_oturum_blueprinti_acik (beklenen 1, gelen '
       || count(*) || ')'
FROM exam_blueprints
WHERE id = '95000000-0000-0000-0000-000000000001';

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  blueprint_read__kapanistan_sonra_baskasinin_blueprinti_kapali (beklenen 0, gelen '
       || count(*) || ')'
FROM exam_blueprints
WHERE id = '95000000-0000-0000-0000-000000000002';

SET LOCAL app.current_user_id = '91000000-0000-0000-0000-000000000004';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  question_purpose__uye_olmayan_practice_sorusunu_goremez (beklenen 0, gelen '
       || count(*) || ')'
FROM questions
WHERE id = '94000000-0000-0000-0000-000000000001';

SET LOCAL app.current_user_id = '91000000-0000-0000-0000-000000000001';
SELECT CASE WHEN count(*) = 6 THEN 'PASS' ELSE 'FAIL' END
       || '  question_purpose__egitmen_tum_ders_havuzunu_gorur (beklenen 6, gelen '
       || count(*) || ')'
FROM questions
WHERE course_id = '92000000-0000-0000-0000-000000000001';

-- ---------------------------------------------------------------------------
-- exam_items: uygulama rolunden practice ve unapproved kalem enjeksiyonu.
-- ---------------------------------------------------------------------------

DO $$
DECLARE
    v_constraint text;
BEGIN
    INSERT INTO exam_items (
        id, course_id, exam_version_id, position, question_id, points
    ) VALUES (
        '95200000-0000-0000-0000-000000000010',
        '92000000-0000-0000-0000-000000000001',
        '95100000-0000-0000-0000-000000000003', 10,
        '94000000-0000-0000-0000-000000000001', 10
    );
    RAISE NOTICE 'FAIL  exam_items__practice_soru_kagida_enjekte_edilemez (insert gecti)';
EXCEPTION
    WHEN check_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'exam_items_assessment_question' THEN
            RAISE NOTICE 'PASS  exam_items__practice_soru_kagida_enjekte_edilemez';
        ELSE
            RAISE NOTICE 'FAIL  exam_items__practice_soru_kagida_enjekte_edilemez (yanlis constraint: %)', v_constraint;
        END IF;
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  exam_items__practice_soru_kagida_enjekte_edilemez (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
DECLARE
    v_constraint text;
BEGIN
    INSERT INTO exam_items (
        id, course_id, exam_version_id, position, question_id, points
    ) VALUES (
        '95200000-0000-0000-0000-000000000011',
        '92000000-0000-0000-0000-000000000001',
        '95100000-0000-0000-0000-000000000003', 11,
        '94000000-0000-0000-0000-000000000005', 10
    );
    RAISE NOTICE 'FAIL  exam_items__unapproved_assessment_kagida_enjekte_edilemez (insert gecti)';
EXCEPTION
    WHEN check_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'exam_items_assessment_question' THEN
            RAISE NOTICE 'PASS  exam_items__unapproved_assessment_kagida_enjekte_edilemez';
        ELSE
            RAISE NOTICE 'FAIL  exam_items__unapproved_assessment_kagida_enjekte_edilemez (yanlis constraint: %)', v_constraint;
        END IF;
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  exam_items__unapproved_assessment_kagida_enjekte_edilemez (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
BEGIN
    INSERT INTO exam_items (
        id, course_id, exam_version_id, position, question_id, points
    ) VALUES (
        '95200000-0000-0000-0000-000000000012',
        '92000000-0000-0000-0000-000000000001',
        '95100000-0000-0000-0000-000000000003', 12,
        '94000000-0000-0000-0000-000000000004', 10
    );
    RAISE NOTICE 'PASS  exam_items__approved_assessment_taslak_kagida_eklenebilir';
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  exam_items__approved_assessment_taslak_kagida_eklenebilir (%)', SQLERRM;
END
$$;

-- ---------------------------------------------------------------------------
-- Uygulama rolu: terminal satir RLS ile gorunmez; taslak siniflandirma aciktir.
-- ---------------------------------------------------------------------------

WITH changed AS (
    UPDATE questions
    SET purpose = 'practice'
    WHERE id = '94000000-0000-0000-0000-000000000002'
    RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  question_immutability__dou_app_terminal_soruyu_guncelleyemez (beklenen 0, gelen '
       || count(*) || ')'
FROM changed;

WITH changed AS (
    UPDATE questions
    SET difficulty = 'medium'
    WHERE id = '94000000-0000-0000-0000-000000000005'
    RETURNING 1
)
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  question_immutability__dou_app_taslagi_siniflandirabilir (beklenen 1, gelen '
       || count(*) || ')'
FROM changed;

DO $$
DECLARE
    v_constraint text;
BEGIN
    DELETE FROM questions
    WHERE id = '94000000-0000-0000-0000-000000000002';
    RAISE NOTICE 'FAIL  question_immutability__superseded_kagit_sorusu_silinemez (delete gecti)';
EXCEPTION
    WHEN foreign_key_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'exam_items_question_id_fkey' THEN
            RAISE NOTICE 'PASS  question_immutability__superseded_kagit_sorusu_silinemez';
        ELSE
            RAISE NOTICE 'FAIL  question_immutability__superseded_kagit_sorusu_silinemez (yanlis constraint: %)', v_constraint;
        END IF;
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  question_immutability__superseded_kagit_sorusu_silinemez (beklenmedik hata: %)', SQLERRM;
END
$$;

-- ---------------------------------------------------------------------------
-- Surum gecisleri: RLS/grant yolu acik olsa bile trigger invalid kenarlari kapatir.
-- ---------------------------------------------------------------------------

DO $$
DECLARE
    v_constraint text;
BEGIN
    UPDATE exam_versions
    SET status = 'superseded', published_at = now(),
        published_by = '91000000-0000-0000-0000-000000000001',
        superseded_at = now(), blueprint_snapshot = '[]'
    WHERE id = '95100000-0000-0000-0000-000000000003';
    RAISE NOTICE 'FAIL  exam_version_transition__draft_superseded_atlayamaz (update gecti)';
EXCEPTION
    WHEN check_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'exam_versions_status_transition' THEN
            RAISE NOTICE 'PASS  exam_version_transition__draft_superseded_atlayamaz';
        ELSE
            RAISE NOTICE 'FAIL  exam_version_transition__draft_superseded_atlayamaz (yanlis constraint: %)', v_constraint;
        END IF;
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  exam_version_transition__draft_superseded_atlayamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
DECLARE
    v_constraint text;
BEGIN
    UPDATE exam_versions
    SET status = 'published', superseded_at = NULL
    WHERE id = '95100000-0000-0000-0000-000000000001';
    RAISE NOTICE 'FAIL  exam_version_transition__superseded_yeniden_published_olamaz (update gecti)';
EXCEPTION
    WHEN check_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'exam_versions_status_transition' THEN
            RAISE NOTICE 'PASS  exam_version_transition__superseded_yeniden_published_olamaz';
        ELSE
            RAISE NOTICE 'FAIL  exam_version_transition__superseded_yeniden_published_olamaz (yanlis constraint: %)', v_constraint;
        END IF;
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  exam_version_transition__superseded_yeniden_published_olamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

-- ---------------------------------------------------------------------------
-- Trigger savunmasi: tablo sahibi/RLS bypass girisimi de terminal icerigi bozmaz.
-- ---------------------------------------------------------------------------

RESET ROLE;

DO $$
DECLARE
    v_constraint text;
BEGIN
    UPDATE questions
    SET payload = '{"stem":"degistirildi","answer_key":"forged"}'
    WHERE id = '94000000-0000-0000-0000-000000000002';
    RAISE NOTICE 'FAIL  question_trigger__published_kagit_icerigi_degistirilemez (update gecti)';
EXCEPTION
    WHEN check_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'questions_terminal_immutable' THEN
            RAISE NOTICE 'PASS  question_trigger__published_kagit_icerigi_degistirilemez';
        ELSE
            RAISE NOTICE 'FAIL  question_trigger__published_kagit_icerigi_degistirilemez (yanlis constraint: %)', v_constraint;
        END IF;
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  question_trigger__published_kagit_icerigi_degistirilemez (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
DECLARE
    v_constraint text;
BEGIN
    UPDATE questions
    SET purpose = 'practice'
    WHERE id = '94000000-0000-0000-0000-000000000006';
    RAISE NOTICE 'FAIL  question_trigger__rejected_terminal_soru_degistirilemez (update gecti)';
EXCEPTION
    WHEN check_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'questions_terminal_immutable' THEN
            RAISE NOTICE 'PASS  question_trigger__rejected_terminal_soru_degistirilemez';
        ELSE
            RAISE NOTICE 'FAIL  question_trigger__rejected_terminal_soru_degistirilemez (yanlis constraint: %)', v_constraint;
        END IF;
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  question_trigger__rejected_terminal_soru_degistirilemez (beklenmedik hata: %)', SQLERRM;
END
$$;

-- ---------------------------------------------------------------------------
-- Worker: izin matrisi ve gercek sorgu birlikte fail-closed olmali.
-- ---------------------------------------------------------------------------

WITH assessment_tables(table_name) AS (
    VALUES
        ('public.topics'),
        ('public.questions'),
        ('public.exam_sessions'),
        ('public.answers'),
        ('public.mastery'),
        ('public.learning_outcomes'),
        ('public.exam_blueprints'),
        ('public.blueprint_cells'),
        ('public.exam_versions'),
        ('public.exam_items')
), leaked AS (
    SELECT table_name
    FROM assessment_tables
    WHERE has_table_privilege('dou_worker', table_name, 'SELECT')
       OR has_table_privilege('dou_worker', table_name, 'INSERT')
       OR has_table_privilege('dou_worker', table_name, 'UPDATE')
       OR has_table_privilege('dou_worker', table_name, 'DELETE')
       OR has_any_column_privilege('dou_worker', table_name, 'SELECT')
       OR has_any_column_privilege('dou_worker', table_name, 'INSERT')
       OR has_any_column_privilege('dou_worker', table_name, 'UPDATE')
       OR has_any_column_privilege('dou_worker', table_name, 'REFERENCES')
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  worker_grants__assessment_tablolarinda_yetki_yok (sizinti '
       || count(*) || ')'
FROM leaked;

SELECT CASE WHEN
           NOT has_function_privilege(
               'dou_worker', 'app.has_own_exam_question(uuid,uuid)', 'EXECUTE'
           )
           AND NOT has_function_privilege(
               'dou_worker', 'app.has_own_blueprint_session(uuid,uuid)', 'EXECUTE'
           )
       THEN 'PASS' ELSE 'FAIL' END
       || '  worker_grants__own_session_helper_execute_kapali';

SET LOCAL ROLE dou_worker;

DO $$
BEGIN
    PERFORM id FROM public.questions LIMIT 1;
    RAISE NOTICE 'FAIL  worker_attack__questions_select_reddedilir (select gecti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  worker_attack__questions_select_reddedilir';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  worker_attack__questions_select_reddedilir (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
BEGIN
    PERFORM app.has_own_exam_question(
        '94000000-0000-0000-0000-000000000002',
        '92000000-0000-0000-0000-000000000001'
    );
    RAISE NOTICE 'FAIL  worker_attack__own_question_helper_cagrilamaz (execute gecti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  worker_attack__own_question_helper_cagrilamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  worker_attack__own_question_helper_cagrilamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

RESET ROLE;
ROLLBACK;
