-- Assessment integrity'nin veritabani guvenlik kaniti (0016).
--
-- Bu dosya API'yi bilerek atlar. Soru amaci, donmus kagit erisimi, terminal
-- degismezlik, runtime kimligi ve worker yetkileri gercek rollerle sinanir.
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

INSERT INTO learning_outcomes (
    id, course_id, code, description, topic_id, created_by
) VALUES (
    '93300000-0000-0000-0000-000000000001',
    '92000000-0000-0000-0000-000000000001',
    'SEC-LO1', 'Sinav guvenligi sinirlarini uygular.',
    '93200000-0000-0000-0000-000000000001',
    '91000000-0000-0000-0000-000000000001'
);

-- 1 practice, 3 approved assessment, 1 draft assessment, 1 rejected assessment.
INSERT INTO questions (
    id, course_id, topic_id, type, payload, source_chunk_id, status, purpose,
    learning_outcome_id, difficulty, created_by, reviewed_by, reviewed_at
) VALUES
    ('94000000-0000-0000-0000-000000000001',
     '92000000-0000-0000-0000-000000000001',
     '93200000-0000-0000-0000-000000000001', 'open',
     '{"stem":"Practice","answer_key":"practice-key"}',
     '93100000-0000-0000-0000-000000000001', 'approved', 'practice',
     NULL, NULL,
     '91000000-0000-0000-0000-000000000001',
     '91000000-0000-0000-0000-000000000001', now()),
    ('94000000-0000-0000-0000-000000000002',
     '92000000-0000-0000-0000-000000000001',
     '93200000-0000-0000-0000-000000000001', 'open',
     '{"stem":"Ogrenci A kagidi","answer_key":"a-key"}',
     '93100000-0000-0000-0000-000000000001', 'approved', 'assessment',
     '93300000-0000-0000-0000-000000000001', 'easy',
     '91000000-0000-0000-0000-000000000001',
     '91000000-0000-0000-0000-000000000001', now()),
    ('94000000-0000-0000-0000-000000000003',
     '92000000-0000-0000-0000-000000000001',
     '93200000-0000-0000-0000-000000000001', 'open',
     '{"stem":"Ogrenci B kagidi","answer_key":"b-key"}',
     '93100000-0000-0000-0000-000000000001', 'approved', 'assessment',
     '93300000-0000-0000-0000-000000000001', 'easy',
     '91000000-0000-0000-0000-000000000001',
     '91000000-0000-0000-0000-000000000001', now()),
    ('94000000-0000-0000-0000-000000000004',
     '92000000-0000-0000-0000-000000000001',
     '93200000-0000-0000-0000-000000000001', 'open',
     '{"stem":"Oturumsuz assessment","answer_key":"hidden-key"}',
     '93100000-0000-0000-0000-000000000001', 'approved', 'assessment',
     '93300000-0000-0000-0000-000000000001', 'easy',
     '91000000-0000-0000-0000-000000000001',
     '91000000-0000-0000-0000-000000000001', now()),
    ('94000000-0000-0000-0000-000000000005',
     '92000000-0000-0000-0000-000000000001',
     '93200000-0000-0000-0000-000000000001', 'open',
     '{"stem":"Taslak assessment","answer_key":"draft-key"}',
     '93100000-0000-0000-0000-000000000001', 'draft', 'assessment',
     NULL, NULL,
     '91000000-0000-0000-0000-000000000001', NULL, NULL),
    ('94000000-0000-0000-0000-000000000006',
     '92000000-0000-0000-0000-000000000001',
     '93200000-0000-0000-0000-000000000001', 'open',
     '{"stem":"Reddedilmis assessment","answer_key":"rejected-key"}',
     '93100000-0000-0000-0000-000000000001', 'rejected', 'assessment',
     NULL, NULL,
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
     NULL, NULL, '91000000-0000-0000-0000-000000000001'),
    ('95000000-0000-0000-0000-000000000004',
     '92000000-0000-0000-0000-000000000001', 'Acik guvenli kagit', 60, 2,
     now() - interval '1 hour', now() + interval '2 hours',
     '91000000-0000-0000-0000-000000000001');

INSERT INTO exam_versions (id, course_id, blueprint_id, version_no) VALUES
    ('95100000-0000-0000-0000-000000000001',
     '92000000-0000-0000-0000-000000000001',
     '95000000-0000-0000-0000-000000000001', 1),
    ('95100000-0000-0000-0000-000000000002',
     '92000000-0000-0000-0000-000000000001',
     '95000000-0000-0000-0000-000000000002', 1),
    ('95100000-0000-0000-0000-000000000003',
     '92000000-0000-0000-0000-000000000001',
     '95000000-0000-0000-0000-000000000003', 1),
    ('95100000-0000-0000-0000-000000000004',
     '92000000-0000-0000-0000-000000000001',
     '95000000-0000-0000-0000-000000000004', 1);

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
     '94000000-0000-0000-0000-000000000003', 50),
    ('95200000-0000-0000-0000-000000000003',
     '92000000-0000-0000-0000-000000000001',
     '95100000-0000-0000-0000-000000000004', 1,
     '94000000-0000-0000-0000-000000000004', 100);

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

UPDATE exam_versions
SET status = 'published', published_at = now(),
    published_by = '91000000-0000-0000-0000-000000000001',
    blueprint_snapshot = '[{"question_count":1,"points":100}]'
WHERE id = '95100000-0000-0000-0000-000000000004';

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
     '95000000-0000-0000-0000-000000000002', 1, now() - interval '1 hour'),
    ('95300000-0000-0000-0000-000000000003',
     '92000000-0000-0000-0000-000000000001',
     '91000000-0000-0000-0000-000000000002', 'practice',
     now(), NULL, NULL,
     ARRAY['94000000-0000-0000-0000-000000000001'::uuid],
     NULL, NULL, NULL, NULL),
    ('95300000-0000-0000-0000-000000000004',
     '92000000-0000-0000-0000-000000000001',
     '91000000-0000-0000-0000-000000000002', 'exam',
     now() - interval '2 hours', now() - interval '1 hour', NULL,
     ARRAY['94000000-0000-0000-0000-000000000001'::uuid],
     NULL, NULL, NULL, NULL),
    ('95300000-0000-0000-0000-000000000005',
     '92000000-0000-0000-0000-000000000001',
     '91000000-0000-0000-0000-000000000002', 'exam',
     now(), now() + interval '1 hour', NULL,
     ARRAY['94000000-0000-0000-0000-000000000001'::uuid],
     NULL, NULL, NULL, NULL);

-- ---------------------------------------------------------------------------
-- Soru gorunurlugu: gercek API LOGIN'i + ogrenci baglami.
-- ---------------------------------------------------------------------------

SET LOCAL SESSION AUTHORIZATION dou_api_runtime;
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

-- Blueprint oturumu raw INSERT ile practice'e çevrilemez; sunucu saati, süre,
-- deneme sırası ve feedback sınırı trigger tarafından kanonik yazılır.
DO $$
DECLARE
    v_constraint text;
BEGIN
    INSERT INTO exam_sessions (
        id, course_id, user_id, mode, started_at, expires_at, question_ids,
        exam_version_id, exam_blueprint_id, attempt_no, feedback_available_at
    ) VALUES (
        '95300000-0000-0000-0000-000000000006',
        '92000000-0000-0000-0000-000000000001',
        '91000000-0000-0000-0000-000000000002', 'practice',
        now(), NULL, NULL,
        '95100000-0000-0000-0000-000000000004',
        '95000000-0000-0000-0000-000000000004', 1, now() + interval '3 hours'
    );
    RAISE NOTICE 'FAIL  session_integrity__blueprint_practice_olarak_baslatilamaz (insert gecti)';
EXCEPTION
    WHEN check_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'exam_sessions_blueprint_mode' THEN
            RAISE NOTICE 'PASS  session_integrity__blueprint_practice_olarak_baslatilamaz';
        ELSE
            RAISE NOTICE 'FAIL  session_integrity__blueprint_practice_olarak_baslatilamaz (yanlis constraint: %)', v_constraint;
        END IF;
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  session_integrity__blueprint_practice_olarak_baslatilamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

INSERT INTO exam_sessions (
    id, course_id, user_id, mode, started_at, expires_at, question_ids,
    exam_version_id, exam_blueprint_id, attempt_no, feedback_available_at
) VALUES (
    '95300000-0000-0000-0000-000000000007',
    '92000000-0000-0000-0000-000000000001',
    '91000000-0000-0000-0000-000000000002', 'exam',
    now() - interval '1 day', now() + interval '1 day', NULL,
    '95100000-0000-0000-0000-000000000004',
    '95000000-0000-0000-0000-000000000004', 2, now() + interval '10 days'
);

SELECT CASE WHEN
           mode = 'exam'
           AND abs(extract(epoch FROM (started_at - statement_timestamp()))) < 5
           AND expires_at = started_at + interval '60 minutes'
           AND attempt_no = 1
           AND feedback_available_at = (
               SELECT closes_at + interval '60 minutes'
               FROM exam_blueprints
               WHERE id = '95000000-0000-0000-0000-000000000004'
           )
       THEN 'PASS' ELSE 'FAIL' END
       || '  session_integrity__blueprint_baslangici_kanonik_yazilir'
FROM exam_sessions
WHERE id = '95300000-0000-0000-0000-000000000007';

-- Cevap satırı yalnız açık oturumun gerçek kâğıdına girebilir. Bu kontroller
-- API yarış kilidinin veritabanı dışından atlanamadığını da kanıtlar.
DO $$
DECLARE
    v_constraint text;
BEGIN
    INSERT INTO answers (
        id, session_id, question_id, course_id, given, score, hint_level, feedback
    ) VALUES (
        '95400000-0000-0000-0000-000000000001',
        '95300000-0000-0000-0000-000000000001',
        '94000000-0000-0000-0000-000000000002',
        '92000000-0000-0000-0000-000000000001', 'gec cevap', 100, 0, '{}'
    );
    RAISE NOTICE 'FAIL  answer_integrity__bitmis_oturuma_cevap_enjekte_edilemez (insert gecti)';
EXCEPTION
    WHEN check_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'answers_session_finished' THEN
            RAISE NOTICE 'PASS  answer_integrity__bitmis_oturuma_cevap_enjekte_edilemez';
        ELSE
            RAISE NOTICE 'FAIL  answer_integrity__bitmis_oturuma_cevap_enjekte_edilemez (yanlis constraint: %)', v_constraint;
        END IF;
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  answer_integrity__bitmis_oturuma_cevap_enjekte_edilemez (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
DECLARE
    v_constraint text;
BEGIN
    INSERT INTO answers (
        id, session_id, question_id, course_id, given, score, hint_level, feedback
    ) VALUES (
        '95400000-0000-0000-0000-000000000002',
        '95300000-0000-0000-0000-000000000003',
        '94000000-0000-0000-0000-000000000004',
        '92000000-0000-0000-0000-000000000001', 'kagit disi', 100, 0, '{}'
    );
    RAISE NOTICE 'FAIL  answer_integrity__kagit_disi_soruya_cevap_enjekte_edilemez (insert gecti)';
EXCEPTION
    WHEN check_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'answers_question_not_in_paper' THEN
            RAISE NOTICE 'PASS  answer_integrity__kagit_disi_soruya_cevap_enjekte_edilemez';
        ELSE
            RAISE NOTICE 'FAIL  answer_integrity__kagit_disi_soruya_cevap_enjekte_edilemez (yanlis constraint: %)', v_constraint;
        END IF;
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  answer_integrity__kagit_disi_soruya_cevap_enjekte_edilemez (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
DECLARE
    v_constraint text;
BEGIN
    INSERT INTO answers (
        id, session_id, question_id, course_id, given, score, hint_level, feedback
    ) VALUES (
        '95400000-0000-0000-0000-000000000003',
        '95300000-0000-0000-0000-000000000004',
        '94000000-0000-0000-0000-000000000001',
        '92000000-0000-0000-0000-000000000001', 'suresi doldu', 100, 0, '{}'
    );
    RAISE NOTICE 'FAIL  answer_integrity__suresi_dolmus_oturuma_cevap_enjekte_edilemez (insert gecti)';
EXCEPTION
    WHEN check_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'answers_session_expired' THEN
            RAISE NOTICE 'PASS  answer_integrity__suresi_dolmus_oturuma_cevap_enjekte_edilemez';
        ELSE
            RAISE NOTICE 'FAIL  answer_integrity__suresi_dolmus_oturuma_cevap_enjekte_edilemez (yanlis constraint: %)', v_constraint;
        END IF;
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  answer_integrity__suresi_dolmus_oturuma_cevap_enjekte_edilemez (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
DECLARE
    v_constraint text;
BEGIN
    INSERT INTO answers (
        id, session_id, question_id, course_id, given, score, hint_level, feedback
    ) VALUES (
        '95400000-0000-0000-0000-000000000004',
        '95300000-0000-0000-0000-000000000005',
        '94000000-0000-0000-0000-000000000001',
        '92000000-0000-0000-0000-000000000001', 'ipucu kullandim', 100, 1, '{}'
    );
    RAISE NOTICE 'FAIL  answer_integrity__resmi_sinavda_ipucu_beyani_reddedilir (insert gecti)';
EXCEPTION
    WHEN check_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'answers_exam_hint_forbidden' THEN
            RAISE NOTICE 'PASS  answer_integrity__resmi_sinavda_ipucu_beyani_reddedilir';
        ELSE
            RAISE NOTICE 'FAIL  answer_integrity__resmi_sinavda_ipucu_beyani_reddedilir (yanlis constraint: %)', v_constraint;
        END IF;
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  answer_integrity__resmi_sinavda_ipucu_beyani_reddedilir (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
BEGIN
    INSERT INTO answers (
        id, session_id, question_id, course_id, given, score, hint_level, feedback
    ) VALUES (
        '95400000-0000-0000-0000-000000000005',
        '95300000-0000-0000-0000-000000000005',
        '94000000-0000-0000-0000-000000000001',
        '92000000-0000-0000-0000-000000000001', 'gecerli cevap', 100, 0, '{}'
    );
    RAISE NOTICE 'PASS  answer_integrity__acik_oturumun_kagit_sorusu_kabul_edilir';
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  answer_integrity__acik_oturumun_kagit_sorusu_kabul_edilir (%)', SQLERRM;
END
$$;

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

DO $$
DECLARE
    v_constraint text;
BEGIN
    UPDATE questions
    SET status = 'approved',
        reviewed_by = '91000000-0000-0000-0000-000000000001',
        reviewed_at = now()
    WHERE id = '94000000-0000-0000-0000-000000000005';
    RAISE NOTICE 'FAIL  question_classification__siniflandirilmamis_assessment_onaylanamaz (update gecti)';
EXCEPTION
    WHEN check_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'questions_assessment_classification' THEN
            RAISE NOTICE 'PASS  question_classification__siniflandirilmamis_assessment_onaylanamaz';
        ELSE
            RAISE NOTICE 'FAIL  question_classification__siniflandirilmamis_assessment_onaylanamaz (yanlis constraint: %)', v_constraint;
        END IF;
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  question_classification__siniflandirilmamis_assessment_onaylanamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

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
    SET learning_outcome_id = '93300000-0000-0000-0000-000000000001',
        difficulty = 'medium',
        status = 'approved',
        reviewed_by = '91000000-0000-0000-0000-000000000001',
        reviewed_at = now()
    WHERE id = '94000000-0000-0000-0000-000000000005'
    RETURNING 1
)
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  question_classification__siniflandirilmis_assessment_onaylanabilir (beklenen 1, gelen '
       || count(*) || ')'
FROM changed;

DO $$
DECLARE
    v_constraint text;
BEGIN
    INSERT INTO questions (
        id, course_id, topic_id, type, payload, source_chunk_id, status, purpose,
        learning_outcome_id, difficulty, created_by, reviewed_by, reviewed_at
    ) VALUES (
        '94000000-0000-0000-0000-000000000009',
        '92000000-0000-0000-0000-000000000001',
        '93200000-0000-0000-0000-000000000001', 'open',
        '{"stem":"Siniflandirmasiz dogrudan insert","answer_key":"gizli"}',
        '93100000-0000-0000-0000-000000000001', 'approved', 'assessment',
        NULL, NULL,
        '91000000-0000-0000-0000-000000000001',
        '91000000-0000-0000-0000-000000000001', now()
    );
    RAISE NOTICE 'FAIL  question_classification__approved_direct_insert_siniflandirmasiz_olamaz (insert gecti)';
EXCEPTION
    WHEN check_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'questions_assessment_classification' THEN
            RAISE NOTICE 'PASS  question_classification__approved_direct_insert_siniflandirmasiz_olamaz';
        ELSE
            RAISE NOTICE 'FAIL  question_classification__approved_direct_insert_siniflandirmasiz_olamaz (yanlis constraint: %)', v_constraint;
        END IF;
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  question_classification__approved_direct_insert_siniflandirmasiz_olamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

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
    SET blueprint_snapshot = '[{"forged":true}]'
    WHERE id = '95100000-0000-0000-0000-000000000002';
    RAISE NOTICE 'FAIL  exam_version_immutability__published_snapshot_degistirilemez (update gecti)';
EXCEPTION
    WHEN check_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'exam_versions_terminal_immutable' THEN
            RAISE NOTICE 'PASS  exam_version_immutability__published_snapshot_degistirilemez';
        ELSE
            RAISE NOTICE 'FAIL  exam_version_immutability__published_snapshot_degistirilemez (yanlis constraint: %)', v_constraint;
        END IF;
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  exam_version_immutability__published_snapshot_degistirilemez (beklenmedik hata: %)', SQLERRM;
END
$$;

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
-- Ham permission-carrier rolu soru anahtari / sonuc okuyamaz ve puan yazamaz.
-- ---------------------------------------------------------------------------

RESET SESSION AUTHORIZATION;

SELECT CASE WHEN EXISTS (
           SELECT 1
           FROM pg_roles runtime
           WHERE runtime.rolname = 'dou_api_runtime'
             AND runtime.rolinherit
             AND NOT runtime.rolsuper
             AND NOT runtime.rolcreatedb
             AND NOT runtime.rolcreaterole
             AND NOT runtime.rolreplication
             AND NOT runtime.rolbypassrls
       ) AND EXISTS (
           SELECT 1
           FROM pg_auth_members membership
           JOIN pg_roles parent ON parent.oid = membership.roleid
           JOIN pg_roles member ON member.oid = membership.member
           WHERE parent.rolname = 'dou_app'
             AND member.rolname = 'dou_api_runtime'
             AND membership.inherit_option
             AND NOT membership.set_option
             AND NOT membership.admin_option
       ) AND NOT EXISTS (
           SELECT 1
           FROM pg_auth_members membership
           JOIN pg_roles parent ON parent.oid = membership.roleid
           WHERE parent.rolname = 'dou_api_runtime'
       ) AND NOT EXISTS (
           SELECT 1
           FROM pg_auth_members membership
           JOIN pg_roles parent ON parent.oid = membership.roleid
           JOIN pg_roles member ON member.oid = membership.member
           WHERE member.rolname = 'dou_api_runtime'
             AND parent.rolname <> 'dou_app'
       ) AND NOT EXISTS (
           SELECT 1
           FROM pg_auth_members membership
           JOIN pg_roles member ON member.oid = membership.member
           WHERE member.rolname = 'dou_app'
       ) AND EXISTS (
           SELECT 1
           FROM pg_roles carrier
           WHERE carrier.rolname = 'dou_app'
             AND NOT carrier.rolcanlogin
             AND NOT carrier.rolsuper
             AND NOT carrier.rolcreatedb
             AND NOT carrier.rolcreaterole
             AND NOT carrier.rolreplication
             AND NOT carrier.rolbypassrls
       )
       THEN 'PASS' ELSE 'FAIL' END
       || '  runtime_role__dar_nobypass_uyelik_yonu_dogru';

SELECT CASE WHEN
           NOT has_table_privilege('dou_app', 'public.questions', 'SELECT')
           AND NOT has_table_privilege('dou_app', 'public.answers', 'SELECT')
           AND NOT has_table_privilege('dou_app', 'public.answers', 'INSERT')
           AND NOT has_table_privilege('dou_app', 'public.exam_sessions', 'SELECT')
           AND NOT has_table_privilege('dou_app', 'public.exam_sessions', 'INSERT')
           AND NOT has_table_privilege('dou_app', 'public.exam_versions', 'SELECT')
           AND NOT has_table_privilege('dou_app', 'public.exam_items', 'SELECT')
           AND NOT has_any_column_privilege(
               'dou_app', 'public.exam_sessions', 'UPDATE'
           )
           AND has_table_privilege('dou_api_runtime', 'public.questions', 'SELECT')
           AND has_table_privilege('dou_api_runtime', 'public.answers', 'SELECT')
           AND has_table_privilege('dou_api_runtime', 'public.answers', 'INSERT')
           AND has_table_privilege(
               'dou_api_runtime', 'public.exam_sessions', 'SELECT'
           )
           AND has_table_privilege(
               'dou_api_runtime', 'public.exam_sessions', 'INSERT'
           )
           AND has_column_privilege(
               'dou_api_runtime', 'public.exam_sessions', 'finished_at', 'UPDATE'
           )
           AND has_table_privilege(
               'dou_api_runtime', 'public.exam_versions', 'SELECT'
           )
           AND has_table_privilege(
               'dou_api_runtime', 'public.exam_items', 'SELECT'
           )
       THEN 'PASS' ELSE 'FAIL' END
       || '  runtime_grants__hassas_yetki_yalniz_api_logininde';

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
           WITH relevant_owner AS (
               SELECT DISTINCT owner_role.oid
               FROM pg_roles owner_role
               WHERE owner_role.oid = (
                         SELECT nspowner FROM pg_namespace WHERE nspname = 'app'
                     )
                  OR owner_role.oid IN (
                       SELECT proc.proowner
                       FROM pg_proc proc
                       WHERE proc.pronamespace = 'app'::regnamespace
                  )
                  OR owner_role.rolname = current_user
           ), effective_global_default AS (
               SELECT
                   owner.oid,
                   COALESCE(defaults.defaclacl, acldefault('f', owner.oid)) AS acl
               FROM relevant_owner owner
               LEFT JOIN pg_default_acl defaults
                 ON defaults.defaclrole = owner.oid
                AND defaults.defaclnamespace = 0
                AND defaults.defaclobjtype = 'f'
           )
           SELECT 1
           FROM effective_global_default defaults
           CROSS JOIN LATERAL aclexplode(defaults.acl) privilege
           WHERE privilege.grantee = 0
             AND privilege.privilege_type = 'EXECUTE'
       ) AND NOT EXISTS (
           SELECT 1
           FROM pg_default_acl defaults
           CROSS JOIN LATERAL aclexplode(defaults.defaclacl) privilege
           WHERE defaults.defaclnamespace = 'app'::regnamespace
             AND defaults.defaclobjtype = 'f'
             AND privilege.grantee = 0
             AND privilege.privilege_type = 'EXECUTE'
       ) THEN 'PASS' ELSE 'FAIL' END
       || '  runtime_defaults__gelecek_nesneler_blanket_yetki_almaz';

SET LOCAL SESSION AUTHORIZATION dou_app;
SET LOCAL app.current_user_id = '91000000-0000-0000-0000-000000000002';

DO $$
BEGIN
    PERFORM payload
    FROM public.questions
    WHERE id = '94000000-0000-0000-0000-000000000002';
    RAISE NOTICE 'FAIL  runtime_attack__ham_cevap_anahtari_okunamaz (select gecti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  runtime_attack__ham_cevap_anahtari_okunamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  runtime_attack__ham_cevap_anahtari_okunamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
BEGIN
    PERFORM blueprint_snapshot
    FROM public.exam_versions
    WHERE id = '95100000-0000-0000-0000-000000000004';
    RAISE NOTICE 'FAIL  runtime_attack__ham_blueprint_snapshot_okunamaz (select gecti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  runtime_attack__ham_blueprint_snapshot_okunamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  runtime_attack__ham_blueprint_snapshot_okunamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
BEGIN
    PERFORM question_id, points
    FROM public.exam_items
    WHERE exam_version_id = '95100000-0000-0000-0000-000000000004';
    RAISE NOTICE 'FAIL  runtime_attack__ham_kagit_kalemleri_okunamaz (select gecti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  runtime_attack__ham_kagit_kalemleri_okunamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  runtime_attack__ham_kagit_kalemleri_okunamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
BEGIN
    PERFORM score, is_correct, feedback
    FROM public.answers
    WHERE session_id = '95300000-0000-0000-0000-000000000005';
    RAISE NOTICE 'FAIL  runtime_attack__ham_yayinlanmamis_puan_okunamaz (select gecti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  runtime_attack__ham_yayinlanmamis_puan_okunamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  runtime_attack__ham_yayinlanmamis_puan_okunamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
BEGIN
    INSERT INTO public.answers (
        id, session_id, question_id, course_id, given, score, is_correct,
        hint_level, feedback
    ) VALUES (
        '95400000-0000-0000-0000-000000000099',
        '95300000-0000-0000-0000-000000000005',
        '94000000-0000-0000-0000-000000000001',
        '92000000-0000-0000-0000-000000000001',
        'sahte cevap', 100, true, 0, '{"forged":true}'
    );
    RAISE NOTICE 'FAIL  runtime_attack__sahte_puan_satiri_yazilamaz (insert gecti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  runtime_attack__sahte_puan_satiri_yazilamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  runtime_attack__sahte_puan_satiri_yazilamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
BEGIN
    INSERT INTO public.exam_sessions (
        id, course_id, user_id, mode, question_ids, exam_version_id,
        exam_blueprint_id, attempt_no, feedback_available_at
    ) VALUES (
        '95300000-0000-0000-0000-000000000008',
        '92000000-0000-0000-0000-000000000001',
        '91000000-0000-0000-0000-000000000002', 'practice', NULL,
        '95100000-0000-0000-0000-000000000004',
        '95000000-0000-0000-0000-000000000004', 2, now() + interval '3 hours'
    );
    RAISE NOTICE 'FAIL  runtime_attack__resmi_oturum_practice_olarak_yazilamaz (insert gecti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  runtime_attack__resmi_oturum_practice_olarak_yazilamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  runtime_attack__resmi_oturum_practice_olarak_yazilamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

RESET SESSION AUTHORIZATION;

-- Object grant'leri test icinde gecici geri verilse bile restrictive runtime
-- policy'leri ikinci, bagimsiz katman olarak fail-closed kalir.
GRANT SELECT ON public.questions, public.answers, public.exam_sessions,
    public.exam_versions, public.exam_items TO dou_app;
GRANT INSERT ON public.answers, public.exam_sessions TO dou_app;

SET LOCAL SESSION AUTHORIZATION dou_app;
SET LOCAL app.current_user_id = '91000000-0000-0000-0000-000000000002';

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  runtime_policy__gecici_grantle_cevap_anahtari_acilmaz (beklenen 0, gelen '
       || count(*) || ')'
FROM public.questions
WHERE id = '94000000-0000-0000-0000-000000000002';

-- Carrier GUC'u egitmen kimligine de taklit edebilir. Runtime kapisi bu nedenle
-- yalniz ogrenci dalina guvenemez; instructor OR dali altinda da kapali kalmalidir.
SET LOCAL app.current_user_id = '91000000-0000-0000-0000-000000000001';

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  runtime_policy__gecici_grantle_ham_puan_acilmaz (beklenen 0, gelen '
       || count(*) || ')'
FROM public.answers
WHERE id = '95400000-0000-0000-0000-000000000005';

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  runtime_policy__gecici_grantle_oturum_satiri_acilmaz (beklenen 0, gelen '
       || count(*) || ')'
FROM public.exam_sessions
WHERE id = '95300000-0000-0000-0000-000000000005';

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  runtime_policy__gecici_grantle_blueprint_snapshot_acilmaz (beklenen 0, gelen '
       || count(*) || ')'
FROM public.exam_versions
WHERE id = '95100000-0000-0000-0000-000000000004';

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  runtime_policy__gecici_grantle_kagit_kalemleri_acilmaz (beklenen 0, gelen '
       || count(*) || ')'
FROM public.exam_items
WHERE exam_version_id = '95100000-0000-0000-0000-000000000004';

SET LOCAL app.current_user_id = '91000000-0000-0000-0000-000000000002';

DO $$
BEGIN
    INSERT INTO public.answers (
        id, session_id, question_id, course_id, given, score, is_correct,
        hint_level, feedback
    ) VALUES (
        '95400000-0000-0000-0000-000000000098',
        '95300000-0000-0000-0000-000000000007',
        '94000000-0000-0000-0000-000000000004',
        '92000000-0000-0000-0000-000000000001',
        'sahte runtime bypass', 100, true, 0, '{"forged":true}'
    );
    RAISE NOTICE 'FAIL  runtime_policy__gecici_grantle_sahte_puan_yazilamaz (insert gecti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  runtime_policy__gecici_grantle_sahte_puan_yazilamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  runtime_policy__gecici_grantle_sahte_puan_yazilamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
BEGIN
    INSERT INTO public.exam_sessions (
        id, course_id, user_id, mode, question_ids, exam_version_id,
        exam_blueprint_id, attempt_no, feedback_available_at
    ) VALUES (
        '95300000-0000-0000-0000-000000000008',
        '92000000-0000-0000-0000-000000000001',
        '91000000-0000-0000-0000-000000000002', 'practice', NULL,
        '95100000-0000-0000-0000-000000000004',
        '95000000-0000-0000-0000-000000000004', 2, now() + interval '3 hours'
    );
    RAISE NOTICE 'FAIL  runtime_policy__gecici_grantle_resmi_oturum_practice_olamaz (insert gecti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  runtime_policy__gecici_grantle_resmi_oturum_practice_olamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  runtime_policy__gecici_grantle_resmi_oturum_practice_olamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

RESET SESSION AUTHORIZATION;
REVOKE SELECT ON public.questions, public.answers, public.exam_sessions,
    public.exam_versions, public.exam_items FROM dou_app;
REVOKE INSERT ON public.answers, public.exam_sessions FROM dou_app;

-- Trigger savunmasi: tablo sahibi/RLS bypass girisimi de terminal icerigi bozmaz.

DO $$
DECLARE
    v_constraint text;
BEGIN
    INSERT INTO exam_sessions (
        id, course_id, user_id, mode, started_at, expires_at,
        question_ids, exam_version_id, exam_blueprint_id, attempt_no,
        feedback_available_at
    ) VALUES (
        '95300000-0000-0000-0000-000000000009',
        '92000000-0000-0000-0000-000000000001',
        '91000000-0000-0000-0000-000000000002', 'exam',
        now() - interval '3 hours', now() - interval '2 hours',
        NULL, '95100000-0000-0000-0000-000000000002',
        '95000000-0000-0000-0000-000000000002', 1,
        now() - interval '2 hours'
    );
    RAISE NOTICE 'FAIL  feedback_schedule__erken_snapshot_insert_edilemez (insert gecti)';
EXCEPTION
    WHEN check_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'exam_sessions_feedback_safe_boundary' THEN
            RAISE NOTICE 'PASS  feedback_schedule__erken_snapshot_insert_edilemez';
        ELSE
            RAISE NOTICE 'FAIL  feedback_schedule__erken_snapshot_insert_edilemez (yanlis constraint: %)', v_constraint;
        END IF;
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  feedback_schedule__erken_snapshot_insert_edilemez (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
DECLARE
    v_constraint text;
BEGIN
    UPDATE exam_sessions
    SET feedback_available_at = now() - interval '2 hours'
    WHERE id = '95300000-0000-0000-0000-000000000002';
    RAISE NOTICE 'FAIL  feedback_schedule__snapshot_sonradan_one_cekilemez (update gecti)';
EXCEPTION
    WHEN check_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'exam_sessions_feedback_immutable' THEN
            RAISE NOTICE 'PASS  feedback_schedule__snapshot_sonradan_one_cekilemez';
        ELSE
            RAISE NOTICE 'FAIL  feedback_schedule__snapshot_sonradan_one_cekilemez (yanlis constraint: %)', v_constraint;
        END IF;
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  feedback_schedule__snapshot_sonradan_one_cekilemez (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
DECLARE
    v_constraint text;
BEGIN
    UPDATE exam_blueprints
    SET closes_at = closes_at + interval '1 hour'
    WHERE id = '95000000-0000-0000-0000-000000000002';
    RAISE NOTICE 'FAIL  feedback_schedule__ilk_oturumdan_sonra_takvim_uzatilamaz (update gecti)';
EXCEPTION
    WHEN check_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'exam_blueprints_schedule_after_session' THEN
            RAISE NOTICE 'PASS  feedback_schedule__ilk_oturumdan_sonra_takvim_uzatilamaz';
        ELSE
            RAISE NOTICE 'FAIL  feedback_schedule__ilk_oturumdan_sonra_takvim_uzatilamaz (yanlis constraint: %)', v_constraint;
        END IF;
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  feedback_schedule__ilk_oturumdan_sonra_takvim_uzatilamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
DECLARE
    v_constraint text;
BEGIN
    INSERT INTO exam_items (
        id, course_id, exam_version_id, position, question_id, points
    ) VALUES (
        '95200000-0000-0000-0000-000000000020',
        '92000000-0000-0000-0000-000000000001',
        '95100000-0000-0000-0000-000000000002', 20,
        '94000000-0000-0000-0000-000000000002', 10
    );
    RAISE NOTICE 'FAIL  exam_item_immutability__published_surume_kalem_eklenemez (insert gecti)';
EXCEPTION
    WHEN check_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'exam_items_version_draft' THEN
            RAISE NOTICE 'PASS  exam_item_immutability__published_surume_kalem_eklenemez';
        ELSE
            RAISE NOTICE 'FAIL  exam_item_immutability__published_surume_kalem_eklenemez (yanlis constraint: %)', v_constraint;
        END IF;
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  exam_item_immutability__published_surume_kalem_eklenemez (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
DECLARE
    v_constraint text;
BEGIN
    DELETE FROM exam_items
    WHERE id = '95200000-0000-0000-0000-000000000002';
    RAISE NOTICE 'FAIL  exam_item_immutability__published_surumden_kalem_silinemez (delete gecti)';
EXCEPTION
    WHEN check_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'exam_items_version_draft' THEN
            RAISE NOTICE 'PASS  exam_item_immutability__published_surumden_kalem_silinemez';
        ELSE
            RAISE NOTICE 'FAIL  exam_item_immutability__published_surumden_kalem_silinemez (yanlis constraint: %)', v_constraint;
        END IF;
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  exam_item_immutability__published_surumden_kalem_silinemez (beklenmedik hata: %)', SQLERRM;
END
$$;

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
