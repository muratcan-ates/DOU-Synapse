-- Blueprint ailesinin RLS kanıtı — 0008'in 18 politikası + iki yetki kısıtı.
--
-- NEDEN VAR: `rls_assessment.sql`'in başındaki gerekçe burada birebir geçerli.
-- 0008'in politikaları olmadan da bütün pytest paketi yeşil kalır, çünkü uygulama
-- katmanı zaten doğru filtreliyor. "Politika var" demek kanıt değildir; "politika
-- bozulduğunda testim bunu yakalar" demek kanıttır (Anayasa II).
--
-- 0008'e ÖZGÜ iki ek risk var ve ikisi de burada sınanıyor:
--
-- (a) `blueprint_cells` ve `exam_items` için UPDATE politikası HİÇ YOK ve yetki de
--     çekildi. Politikasızlık fail-closed'dır ama yalnız yetki çekilmemişse test
--     yanlış sebeple yeşil yanar; o yüzden ikisi ayrı ayrı sınanır.
-- (b) `exam_versions`'ın okuma politikasında ÜÇ dal var ve üçüncüsü (kendi oturumu)
--     FR-115'in okuma ayağıdır. Pencere kapandıktan sonra yürüyen oturumun sahibi
--     sürümünü görmeye devam etmeli; bu dal düşerse sınav ortasında kâğıt kaybolur
--     ve hiçbir uygulama testi bunu yakalamaz.
--
-- Çalıştırma:
--     psql -d dou_synapse -f supabase/tests/rls_blueprint.sql
--
-- Beklenen çıktı: her satırda PASS.
-- Kırmızı yanabildiği `rls_blueprint_mutation_check.sh` ile kanıtlanır.
--
-- UYARI: `docker-compose.yml` veritabanına `postgres` superuser'ıyla bağlanır, yani
-- Compose yığınında RLS ATLANIR. Bu dosyayı Compose'da koşturup yeşil görmek hiçbir
-- şey kanıtlamaz — gerçek `dou_api_runtime` session_user olmadan tamamı boşuna yanar.

\set ON_ERROR_STOP on
\pset format unaligned
\pset tuples_only on

BEGIN;

-- ---------------------------------------------------------------------------
-- Kurulum: sahip/superuser olarak seed (RLS'i atlar)
-- ---------------------------------------------------------------------------
--
-- Ayşe eğitmen, Burak aynı dersin öğrencisi ve YÜRÜYEN bir oturumu var,
-- Deniz aynı dersin öğrencisi ama oturumu YOK (üçüncü dalı ayırt etmek için şart),
-- Ceren başka dersin öğrencisi (ders-ders izolasyonu).

INSERT INTO profiles (id, email, full_name) VALUES
    ('11111111-1111-1111-1111-111111111111', 'ayse@dogus.edu.tr',  'Ayşe Eğitmen'),
    ('22222222-2222-2222-2222-222222222222', 'burak@dogus.edu.tr', 'Burak Öğrenci'),
    ('33333333-3333-3333-3333-333333333333', 'ceren@dogus.edu.tr', 'Ceren Öğrenci'),
    ('44444444-4444-4444-4444-444444444444', 'deniz@dogus.edu.tr', 'Deniz Öğrenci');

INSERT INTO courses (id, code, title, created_by) VALUES
    ('aaaaaaaa-0000-0000-0000-000000000001', 'COME301', 'İşletim Sistemleri',
     '11111111-1111-1111-1111-111111111111'),
    ('bbbbbbbb-0000-0000-0000-000000000002', 'COME302', 'Veri Yapıları',
     '11111111-1111-1111-1111-111111111111');

INSERT INTO course_memberships (course_id, user_id, role) VALUES
    ('aaaaaaaa-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 'instructor'),
    ('aaaaaaaa-0000-0000-0000-000000000001', '22222222-2222-2222-2222-222222222222', 'student'),
    ('aaaaaaaa-0000-0000-0000-000000000001', '44444444-4444-4444-4444-444444444444', 'student'),
    ('bbbbbbbb-0000-0000-0000-000000000002', '33333333-3333-3333-3333-333333333333', 'student');

INSERT INTO documents (id, course_id, uploaded_by, file_name, file_type,
                       storage_path, file_hash, byte_size, status) VALUES
    ('dddddddd-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001',
     '11111111-1111-1111-1111-111111111111', '05-deadlock.pdf', 'pdf',
     'courses/a/deadlock.pdf', 'bp-hash-a', 1024, 'completed');

INSERT INTO chunks (id, course_id, document_id, chunk_index, text, token_count) VALUES
    ('cccccccc-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001',
     'dddddddd-0000-0000-0000-000000000001', 0, 'Kilitlenme dört koşul.', 5);

INSERT INTO topics (id, course_id, name, created_by) VALUES
    ('77777777-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001',
     'Kilitlenme', '11111111-1111-1111-1111-111111111111');

INSERT INTO learning_outcomes (id, course_id, code, description, topic_id, created_by) VALUES
    ('11110000-0000-0000-0000-00000000000a', 'aaaaaaaa-0000-0000-0000-000000000001',
     'CO1', 'Kilitlenme koşullarını sayar', '77777777-0000-0000-0000-000000000001',
     '11111111-1111-1111-1111-111111111111'),
    ('11110000-0000-0000-0000-00000000000b', 'bbbbbbbb-0000-0000-0000-000000000002',
     'CO1', 'Başka dersin çıktısı', NULL, '11111111-1111-1111-1111-111111111111'),
    -- Hiçbir hücrede KULLANILMAYAN çıktı. Silme politikası bununla sınanır: hücrede
    -- kullanılan bir çıktıyı silmeye çalışmak `blueprint_cells`'in ON DELETE RESTRICT
    -- kısıtına takılır ve FK ihlali, politikayı MASKELER — mutasyon testi bu kusuru
    -- yakaladı (politika tamamen açılsa bile iddia yeşil kalıyordu).
    ('11110000-0000-0000-0000-00000000000c', 'aaaaaaaa-0000-0000-0000-000000000001',
     'CO2', 'Hücrede kullanılmayan çıktı', NULL,
     '11111111-1111-1111-1111-111111111111');

INSERT INTO questions (id, course_id, topic_id, type, payload, source_chunk_id, status,
                       purpose, learning_outcome_id, difficulty, reviewed_by, reviewed_at) VALUES
    ('99990000-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001',
     '77777777-0000-0000-0000-000000000001', 'mcq', '{"stem":"S1"}',
     'cccccccc-0000-0000-0000-000000000001', 'approved', 'assessment',
     '11110000-0000-0000-0000-00000000000a', 'easy',
     '11111111-1111-1111-1111-111111111111', now()),
    ('99990000-0000-0000-0000-000000000002', 'aaaaaaaa-0000-0000-0000-000000000001',
     '77777777-0000-0000-0000-000000000001', 'mcq', '{"stem":"S2"}',
     'cccccccc-0000-0000-0000-000000000001', 'approved', 'assessment',
     '11110000-0000-0000-0000-00000000000a', 'easy',
     '11111111-1111-1111-1111-111111111111', now());

-- Üç blueprint: (1) yayında ve penceresi açık, (2) yalnız taslak sürümü var,
-- (3) yayında ama penceresi KAPANMIŞ. Üçü birlikte olmadan `blueprint_open_to_students`
-- ve `is_exam_open` ayırt edilemez.
INSERT INTO exam_blueprints (id, course_id, title, duration_minutes, max_attempts,
                             opens_at, closes_at, created_by) VALUES
    ('bbbb0000-0000-0000-0000-00000000000a', 'aaaaaaaa-0000-0000-0000-000000000001',
     'Vize (yayında)', 60, 3, now() - interval '1 hour', now() + interval '1 day',
     '11111111-1111-1111-1111-111111111111'),
    ('bbbb0000-0000-0000-0000-00000000000b', 'aaaaaaaa-0000-0000-0000-000000000001',
     'Final (taslak)', 60, 1, NULL, NULL,
     '11111111-1111-1111-1111-111111111111'),
    ('bbbb0000-0000-0000-0000-00000000000c', 'aaaaaaaa-0000-0000-0000-000000000001',
     'Kapanmis sinav', 60, 1, now() - interval '2 day', now() - interval '1 day',
     '11111111-1111-1111-1111-111111111111');

INSERT INTO blueprint_cells (course_id, blueprint_id, learning_outcome_id, difficulty,
                             question_type, question_count, points_per_question) VALUES
    ('aaaaaaaa-0000-0000-0000-000000000001', 'bbbb0000-0000-0000-0000-00000000000a',
     '11110000-0000-0000-0000-00000000000a', 'easy', 'mcq', 1, 10),
    ('aaaaaaaa-0000-0000-0000-000000000001', 'bbbb0000-0000-0000-0000-00000000000b',
     '11110000-0000-0000-0000-00000000000a', 'hard', 'mcq', 1, 10);

INSERT INTO exam_versions (id, course_id, blueprint_id, version_no, status,
                           published_at, published_by, blueprint_snapshot) VALUES
    ('eeee0000-0000-0000-0000-00000000000a', 'aaaaaaaa-0000-0000-0000-000000000001',
     'bbbb0000-0000-0000-0000-00000000000a', 1, 'draft', NULL, NULL, NULL),
    ('eeee0000-0000-0000-0000-00000000000b', 'aaaaaaaa-0000-0000-0000-000000000001',
     'bbbb0000-0000-0000-0000-00000000000b', 1, 'draft', NULL, NULL, NULL),
    ('eeee0000-0000-0000-0000-00000000000c', 'aaaaaaaa-0000-0000-0000-000000000001',
     'bbbb0000-0000-0000-0000-00000000000c', 1, 'draft', NULL, NULL, NULL);

INSERT INTO exam_items (id, course_id, exam_version_id, position, question_id, points) VALUES
    ('ffff0000-0000-0000-0000-00000000000a', 'aaaaaaaa-0000-0000-0000-000000000001',
     'eeee0000-0000-0000-0000-00000000000a', 1, '99990000-0000-0000-0000-000000000001', 10),
    ('ffff0000-0000-0000-0000-00000000000b', 'aaaaaaaa-0000-0000-0000-000000000001',
     'eeee0000-0000-0000-0000-00000000000b', 1, '99990000-0000-0000-0000-000000000002', 10);

UPDATE exam_versions
SET status = 'published', published_at = now(),
    published_by = '11111111-1111-1111-1111-111111111111',
    blueprint_snapshot = '[{"question_count":1}]'
WHERE id IN (
    'eeee0000-0000-0000-0000-00000000000a',
    'eeee0000-0000-0000-0000-00000000000c'
);

-- Burak'ın YÜRÜYEN oturumu, kapanmış sınavın sürümüne bağlı: üçüncü OR dalının
-- pencereden bağımsız çalıştığını göstermenin tek yolu bu.
INSERT INTO exam_sessions (id, course_id, user_id, mode, expires_at, question_ids,
                           exam_version_id, exam_blueprint_id, attempt_no,
                           feedback_available_at) VALUES
    ('a5e50000-0000-0000-0000-00000000000c', 'aaaaaaaa-0000-0000-0000-000000000001',
     '22222222-2222-2222-2222-222222222222', 'exam', now() + interval '30 min', NULL,
     'eeee0000-0000-0000-0000-00000000000c', 'bbbb0000-0000-0000-0000-00000000000c', 1,
     now() - interval '22 hours');

-- ---------------------------------------------------------------------------
-- Testler: uygulama rolüyle. Superuser'la koşulsa RLS sessizce atlanır ve bu
-- dosyanın tamamı hiçbir şey kanıtlamadan yeşil yanardı.
-- ---------------------------------------------------------------------------

SET LOCAL SESSION AUTHORIZATION dou_api_runtime;

-- ===========================================================================
-- learning_outcomes
-- ===========================================================================

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
SELECT CASE WHEN count(*) = 2 THEN 'PASS' ELSE 'FAIL' END
       || '  learning_outcomes_read__uye_kendi_dersinin_ciktisini_gorur (beklenen 2, gelen '
       || count(*) || ')'
FROM learning_outcomes;

SET LOCAL app.current_user_id = '33333333-3333-3333-3333-333333333333';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  learning_outcomes_read__baska_dersin_ciktisi_gorunmez (beklenen 0, gelen '
       || count(*) || ')'
FROM learning_outcomes WHERE course_id = 'aaaaaaaa-0000-0000-0000-000000000001';

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
DO $$
BEGIN
    INSERT INTO learning_outcomes (course_id, code, description, created_by)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001', 'CO9', 'Öğrencinin yazdığı',
            '22222222-2222-2222-2222-222222222222');
    RAISE NOTICE 'FAIL  learning_outcomes_write__ogrenci_cikti_ekleyemez (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  learning_outcomes_write__ogrenci_cikti_ekleyemez';
    WHEN others THEN
        RAISE NOTICE 'FAIL  learning_outcomes_write__ogrenci_cikti_ekleyemez (beklenmedik hata: %)', SQLERRM;
END
$$;

-- UPDATE'te politika hata vermez, satır görünmez: etkilenen satır sayısı 0 olmalı.
DO $$
DECLARE etkilenen integer;
BEGIN
    UPDATE learning_outcomes SET description = 'ele geçirildi'
     WHERE id = '11110000-0000-0000-0000-00000000000a';
    GET DIAGNOSTICS etkilenen = ROW_COUNT;
    IF etkilenen = 0 THEN
        RAISE NOTICE 'PASS  learning_outcomes_update__ogrenci_cikti_guncelleyemez';
    ELSE
        RAISE NOTICE 'FAIL  learning_outcomes_update__ogrenci_cikti_guncelleyemez (% satır)',
            etkilenen;
    END IF;
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  learning_outcomes_update__ogrenci_cikti_guncelleyemez';
    WHEN others THEN
        RAISE NOTICE 'FAIL  learning_outcomes_update__ogrenci_cikti_guncelleyemez (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
DECLARE etkilenen integer;
BEGIN
    DELETE FROM learning_outcomes WHERE id = '11110000-0000-0000-0000-00000000000c';
    GET DIAGNOSTICS etkilenen = ROW_COUNT;
    IF etkilenen = 0 THEN
        RAISE NOTICE 'PASS  learning_outcomes_delete__ogrenci_cikti_silemez';
    ELSE
        RAISE NOTICE 'FAIL  learning_outcomes_delete__ogrenci_cikti_silemez (% satır)', etkilenen;
    END IF;
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  learning_outcomes_delete__ogrenci_cikti_silemez';
    WHEN others THEN
        RAISE NOTICE 'FAIL  learning_outcomes_delete__ogrenci_cikti_silemez (beklenmedik hata: %)', SQLERRM;
END
$$;

-- Eğitmen yazabilmeli: olumsuz iddia tek başına yanlış sebeple yeşil yanabilir
-- (tablo düzeyi GRANT eksik olsaydı her şey reddedilirdi).
SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
DO $$
BEGIN
    INSERT INTO learning_outcomes (course_id, code, description, created_by)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001', 'CO8', 'Eğitmenin yazdığı',
            '11111111-1111-1111-1111-111111111111');
    RAISE NOTICE 'PASS  learning_outcomes_write__egitmen_cikti_ekler';
EXCEPTION WHEN others THEN
    RAISE NOTICE 'FAIL  learning_outcomes_write__egitmen_cikti_ekler (%)', SQLERRM;
END
$$;

-- ===========================================================================
-- exam_blueprints — "eğitmen hepsini, üye yalnız açık olanı"
-- ===========================================================================

SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
SELECT CASE WHEN count(*) = 3 THEN 'PASS' ELSE 'FAIL' END
       || '  exam_blueprints_read__egitmen_taslak_dahil_hepsini_gorur (beklenen 3, gelen '
       || count(*) || ')'
FROM exam_blueprints;

SET LOCAL app.current_user_id = '44444444-4444-4444-4444-444444444444';
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  exam_blueprints_read__uye_yalniz_yayinda_ve_acik_olani_gorur (beklenen 1, gelen '
       || count(*) || ')'
FROM exam_blueprints;

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  exam_blueprints_read__uye_taslak_sinavi_goremez (beklenen 0, gelen '
       || count(*) || ')'
FROM exam_blueprints WHERE id = 'bbbb0000-0000-0000-0000-00000000000b';

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  exam_blueprints_read__uye_penceresi_kapanmis_sinavi_goremez (beklenen 0, gelen '
       || count(*) || ')'
FROM exam_blueprints WHERE id = 'bbbb0000-0000-0000-0000-00000000000c';

SET LOCAL app.current_user_id = '33333333-3333-3333-3333-333333333333';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  exam_blueprints_read__baska_dersin_ogrencisi_goremez (beklenen 0, gelen '
       || count(*) || ')'
FROM exam_blueprints;

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
DO $$
BEGIN
    INSERT INTO exam_blueprints (course_id, title, duration_minutes, created_by)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001', 'Öğrencinin sınavı', 10,
            '22222222-2222-2222-2222-222222222222');
    RAISE NOTICE 'FAIL  exam_blueprints_insert__ogrenci_sinav_kuramaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  exam_blueprints_insert__ogrenci_sinav_kuramaz';
    WHEN others THEN
        RAISE NOTICE 'FAIL  exam_blueprints_insert__ogrenci_sinav_kuramaz (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
DECLARE etkilenen integer;
BEGIN
    UPDATE exam_blueprints SET duration_minutes = 599
     WHERE id = 'bbbb0000-0000-0000-0000-00000000000a';
    GET DIAGNOSTICS etkilenen = ROW_COUNT;
    IF etkilenen = 0 THEN
        RAISE NOTICE 'PASS  exam_blueprints_update__ogrenci_sureyi_uzatamaz';
    ELSE
        RAISE NOTICE 'FAIL  exam_blueprints_update__ogrenci_sureyi_uzatamaz (% satır)', etkilenen;
    END IF;
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  exam_blueprints_update__ogrenci_sureyi_uzatamaz';
    WHEN others THEN
        RAISE NOTICE 'FAIL  exam_blueprints_update__ogrenci_sureyi_uzatamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
DECLARE etkilenen integer;
BEGIN
    DELETE FROM exam_blueprints WHERE id = 'bbbb0000-0000-0000-0000-00000000000a';
    GET DIAGNOSTICS etkilenen = ROW_COUNT;
    IF etkilenen = 0 THEN
        RAISE NOTICE 'PASS  exam_blueprints_delete__ogrenci_sinav_silemez';
    ELSE
        RAISE NOTICE 'FAIL  exam_blueprints_delete__ogrenci_sinav_silemez (% satır)', etkilenen;
    END IF;
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  exam_blueprints_delete__ogrenci_sinav_silemez';
    WHEN others THEN
        RAISE NOTICE 'FAIL  exam_blueprints_delete__ogrenci_sinav_silemez (beklenmedik hata: %)', SQLERRM;
END
$$;

-- ===========================================================================
-- blueprint_cells — öğrenciye SELECT politikası BİLEREK YOK (sınav öncesi istihbarat)
-- ===========================================================================

SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
SELECT CASE WHEN count(*) = 2 THEN 'PASS' ELSE 'FAIL' END
       || '  blueprint_cells_read__egitmen_hucreleri_gorur (beklenen 2, gelen '
       || count(*) || ')'
FROM blueprint_cells;

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  blueprint_cells_read__ogrenci_dagilimi_GOREMEZ (beklenen 0, gelen '
       || count(*) || ')'
FROM blueprint_cells;

DO $$
BEGIN
    INSERT INTO blueprint_cells (course_id, blueprint_id, learning_outcome_id, difficulty,
                                 question_type, question_count, points_per_question)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001', 'bbbb0000-0000-0000-0000-00000000000a',
            '11110000-0000-0000-0000-00000000000a', 'medium', 'open', 1, 1);
    RAISE NOTICE 'FAIL  blueprint_cells_insert__ogrenci_hucre_ekleyemez (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  blueprint_cells_insert__ogrenci_hucre_ekleyemez';
    WHEN others THEN
        RAISE NOTICE 'FAIL  blueprint_cells_insert__ogrenci_hucre_ekleyemez (beklenmedik hata: %)', SQLERRM;
END
$$;

-- YETKİ KISITI: UPDATE politikası yok VE tablo yetkisi çekili. Eğitmen bile
-- güncelleyemez; hücre kümesi bütün olarak sil+yaz ile değişir.
SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
DO $$
BEGIN
    UPDATE blueprint_cells SET question_count = 99;
    RAISE NOTICE 'FAIL  blueprint_cells_update__YETKI_CEKILI_egitmen_bile_guncelleyemez (geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  blueprint_cells_update__YETKI_CEKILI_egitmen_bile_guncelleyemez';
    WHEN others THEN
        RAISE NOTICE 'FAIL  blueprint_cells_update__YETKI_CEKILI_egitmen_bile_guncelleyemez (beklenmedik hata: %)', SQLERRM;
END
$$;

-- ===========================================================================
-- exam_versions — üç dallı okuma politikası
-- ===========================================================================

SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
SELECT CASE WHEN count(*) = 3 THEN 'PASS' ELSE 'FAIL' END
       || '  exam_versions_read__egitmen_taslak_dahil_hepsini_gorur (beklenen 3, gelen '
       || count(*) || ')'
FROM exam_versions;

-- Deniz: aynı dersin öğrencisi, HİÇ oturumu yok. Yalnız açık pencerelinin sürümünü
-- görmeli — üçüncü dal onun için çalışmamalı.
SET LOCAL app.current_user_id = '44444444-4444-4444-4444-444444444444';
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  exam_versions_read__oturumsuz_uye_yalniz_acik_sinavin_surumunu_gorur '
       || '(beklenen 1, gelen ' || count(*) || ')'
FROM exam_versions;

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  exam_versions_read__oturumsuz_uye_kapanmis_surumu_goremez (beklenen 0, gelen '
       || count(*) || ')'
FROM exam_versions WHERE id = 'eeee0000-0000-0000-0000-00000000000c';

-- Burak: penceresi KAPANMIŞ sınavda yürüyen oturumu var. FR-115'in okuma ayağı —
-- zil çaldı diye kâğıdı elinden alınmamalı.
SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  exam_versions_read__YURUYEN_OTURUM_pencere_kapansa_da_surumunu_gorur '
       || '(beklenen 1, gelen ' || count(*) || ')'
FROM exam_versions WHERE id = 'eeee0000-0000-0000-0000-00000000000c';

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  exam_versions_read__uye_taslak_surumu_goremez (beklenen 0, gelen '
       || count(*) || ')'
FROM exam_versions WHERE id = 'eeee0000-0000-0000-0000-00000000000b';

DO $$
BEGIN
    INSERT INTO exam_versions (course_id, blueprint_id, version_no)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            'bbbb0000-0000-0000-0000-00000000000a', 9);
    RAISE NOTICE 'FAIL  exam_versions_insert__ogrenci_surum_acamaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  exam_versions_insert__ogrenci_surum_acamaz';
    WHEN others THEN
        RAISE NOTICE 'FAIL  exam_versions_insert__ogrenci_surum_acamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

-- YETKİ KISITI: kolon bazlı GRANT. `version_no` hiçbir rolden yazılamaz.
SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
DO $$
BEGIN
    UPDATE exam_versions SET version_no = 99;
    RAISE NOTICE 'FAIL  exam_versions_update__KOLON_GRANT_version_no_yazilamaz (geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  exam_versions_update__KOLON_GRANT_version_no_yazilamaz';
    WHEN others THEN
        RAISE NOTICE 'FAIL  exam_versions_update__KOLON_GRANT_version_no_yazilamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

-- Ama yayın akışının yazdığı kolonlar yazılabilmeli (yanlış sebeple yeşil yanmasın).
DO $$
BEGIN
    UPDATE exam_versions SET status = 'superseded', superseded_at = now()
     WHERE id = 'eeee0000-0000-0000-0000-00000000000c';
    RAISE NOTICE 'PASS  exam_versions_update__egitmen_yayin_kolonlarini_yazar';
EXCEPTION WHEN others THEN
    RAISE NOTICE 'FAIL  exam_versions_update__egitmen_yayin_kolonlarini_yazar (%)', SQLERRM;
END
$$;

-- Yayınlanmış sürüm silinemez (politikada status='draft' koşulu).
DO $$
DECLARE etkilenen integer;
BEGIN
    DELETE FROM exam_versions WHERE id = 'eeee0000-0000-0000-0000-00000000000a';
    GET DIAGNOSTICS etkilenen = ROW_COUNT;
    IF etkilenen = 0 THEN
        RAISE NOTICE 'PASS  exam_versions_delete__yayinlanmis_surum_silinemez';
    ELSE
        RAISE NOTICE 'FAIL  exam_versions_delete__yayinlanmis_surum_silinemez (% satır)',
            etkilenen;
    END IF;
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  exam_versions_delete__yayinlanmis_surum_silinemez';
    WHEN others THEN
        RAISE NOTICE 'FAIL  exam_versions_delete__yayinlanmis_surum_silinemez (beklenmedik hata: %)', SQLERRM;
END
$$;

-- ===========================================================================
-- exam_items — kâğıt, yalnız o sürümde oturumu olana açık
-- ===========================================================================

SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
SELECT CASE WHEN count(*) = 2 THEN 'PASS' ELSE 'FAIL' END
       || '  exam_items_read__egitmen_kagidi_gorur (beklenen 2, gelen ' || count(*) || ')'
FROM exam_items;

SET LOCAL app.current_user_id = '44444444-4444-4444-4444-444444444444';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  exam_items_read__oturumsuz_uye_kagidi_GOREMEZ (beklenen 0, gelen '
       || count(*) || ')'
FROM exam_items;

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  exam_items_read__oturumu_olmayan_surumun_kagidi_gorunmez (beklenen 0, gelen '
       || count(*) || ')'
FROM exam_items WHERE exam_version_id = 'eeee0000-0000-0000-0000-00000000000a';

-- YETKİ KISITI: exam_items'a UPDATE yetkisi yok. FR-115'in yapısal ayağı.
SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
DO $$
BEGIN
    UPDATE exam_items SET points = 99;
    RAISE NOTICE 'FAIL  exam_items_update__YETKI_CEKILI_puan_degistirilemez (geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  exam_items_update__YETKI_CEKILI_puan_degistirilemez';
    WHEN others THEN
        RAISE NOTICE 'FAIL  exam_items_update__YETKI_CEKILI_puan_degistirilemez (beklenmedik hata: %)', SQLERRM;
END
$$;

-- Yayınlanmış sürüme kalem eklenemez (politikada status='draft').
DO $$
DECLARE v_constraint text;
BEGIN
    INSERT INTO exam_items (course_id, exam_version_id, position, question_id, points)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            'eeee0000-0000-0000-0000-00000000000a', 5,
            '99990000-0000-0000-0000-000000000002', 10);
    RAISE NOTICE 'FAIL  exam_items_insert__yayinlanmis_kagida_soru_eklenemez (insert geçti)';
EXCEPTION
    WHEN check_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'exam_items_version_draft' THEN
            RAISE NOTICE 'PASS  exam_items_insert__yayinlanmis_kagida_soru_eklenemez';
        ELSE
            RAISE NOTICE 'FAIL  exam_items_insert__yayinlanmis_kagida_soru_eklenemez (yanlis constraint: %)', v_constraint;
        END IF;
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  exam_items_insert__yayinlanmis_kagida_soru_eklenemez';
    WHEN others THEN
        RAISE NOTICE 'FAIL  exam_items_insert__yayinlanmis_kagida_soru_eklenemez (beklenmedik hata: %)', SQLERRM;
END
$$;

-- Taslak sürüme eklenebilmeli (olumlu kontrol).
DO $$
BEGIN
    INSERT INTO exam_items (course_id, exam_version_id, position, question_id, points)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            'eeee0000-0000-0000-0000-00000000000b', 5,
            '99990000-0000-0000-0000-000000000001', 10);
    RAISE NOTICE 'PASS  exam_items_insert__taslak_kagida_soru_eklenir';
EXCEPTION WHEN others THEN
    RAISE NOTICE 'FAIL  exam_items_insert__taslak_kagida_soru_eklenir (%)', SQLERRM;
END
$$;

-- ===========================================================================
-- exam_sessions_self_insert — FR-116'nın ikinci katmanı (0008 politikayı yeniden kurdu)
-- ===========================================================================

SET LOCAL app.current_user_id = '44444444-4444-4444-4444-444444444444';
DO $$
DECLARE
    v_constraint text;
BEGIN
    INSERT INTO exam_sessions (course_id, user_id, mode, expires_at, question_ids,
                               exam_version_id, exam_blueprint_id, attempt_no,
                               feedback_available_at)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            '44444444-4444-4444-4444-444444444444', 'exam', now() + interval '30 min',
            NULL, 'eeee0000-0000-0000-0000-00000000000c',
            'bbbb0000-0000-0000-0000-00000000000c', 1,
            now() - interval '22 hours');
    RAISE NOTICE 'FAIL  exam_sessions_insert__PENCERE_KAPALI_oturum_acilamaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  exam_sessions_insert__PENCERE_KAPALI_oturum_acilamaz';
    WHEN check_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'exam_sessions_blueprint_window' THEN
            RAISE NOTICE 'PASS  exam_sessions_insert__PENCERE_KAPALI_oturum_acilamaz';
        ELSE
            RAISE NOTICE 'FAIL  exam_sessions_insert__PENCERE_KAPALI_oturum_acilamaz (yanlis constraint: %)', v_constraint;
        END IF;
    WHEN others THEN
        RAISE NOTICE 'FAIL  exam_sessions_insert__PENCERE_KAPALI_oturum_acilamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
BEGIN
    INSERT INTO exam_sessions (course_id, user_id, mode, expires_at, question_ids,
                               exam_version_id, exam_blueprint_id, attempt_no,
                               feedback_available_at)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            '44444444-4444-4444-4444-444444444444', 'exam', now() + interval '30 min',
            NULL, 'eeee0000-0000-0000-0000-00000000000a',
            'bbbb0000-0000-0000-0000-00000000000a', 1,
            now() + interval '25 hours');
    RAISE NOTICE 'PASS  exam_sessions_insert__PENCERE_ACIK_oturum_acilir';
EXCEPTION WHEN others THEN
    RAISE NOTICE 'FAIL  exam_sessions_insert__PENCERE_ACIK_oturum_acilir (%)', SQLERRM;
END
$$;

-- 0004'ün iki koşulu AYNEN korunmuş olmalı: başkası adına oturum açılamaz.
DO $$
BEGIN
    INSERT INTO exam_sessions (course_id, user_id, mode, expires_at, question_ids,
                               exam_version_id, exam_blueprint_id, attempt_no,
                               feedback_available_at)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            '22222222-2222-2222-2222-222222222222', 'exam', now() + interval '30 min',
            NULL, 'eeee0000-0000-0000-0000-00000000000a',
            'bbbb0000-0000-0000-0000-00000000000a', 2,
            now() + interval '25 hours');
    RAISE NOTICE 'FAIL  exam_sessions_insert__baskasi_adina_oturum_acilamaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  exam_sessions_insert__baskasi_adina_oturum_acilamaz';
    WHEN others THEN
        RAISE NOTICE 'FAIL  exam_sessions_insert__baskasi_adina_oturum_acilamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

-- Prova akışı KORUNMUŞ olmalı: sürümsüz oturum hâlâ açılabilir (regresyon).
DO $$
BEGIN
    INSERT INTO exam_sessions (course_id, user_id, mode, expires_at, question_ids)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            '44444444-4444-4444-4444-444444444444', 'practice', NULL,
            ARRAY['99990000-0000-0000-0000-000000000001']::uuid[]);
    RAISE NOTICE 'PASS  exam_sessions_insert__ESKI_AKIS_prova_oturumu_acilir';
EXCEPTION WHEN others THEN
    RAISE NOTICE 'FAIL  exam_sessions_insert__ESKI_AKIS_prova_oturumu_acilir (%)', SQLERRM;
END
$$;

ROLLBACK;
