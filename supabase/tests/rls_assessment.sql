-- Ölçme ve analitik katmanının RLS kanıtı — 0004'ün 15 politikası + 0005'in biri.
--
-- NEDEN VAR: 6 Ağustos PR incelemesinde ölçüldü ki `0004`'ün on beş politikasının
-- hiçbirinin otomatik kanıtı yoktu. `questions_read` politikasından
-- `AND status = 'approved'` düşürüldüğünde 92 test yeşil kalıyor, `rls_isolation.sql`
-- 8/8 PASS veriyor ve CI'daki `grep -q FAIL` kapısı geçiyordu — aynı anda psql'de
-- öğrenci taslak sınav sorusunu görüyordu. Yani ölçme katmanının TÜM politikaları
-- `USING (true)` yapılsa bile CI yeşil kalıyordu. Projenin tezi "iki katmanlı
-- izolasyon, kanıtlı" iken bu, tezin en zayıf noktasıydı.
--
-- KAPSAM: 0004'ün on beş politikasının her biri en az bir OLUMLU ve bir OLUMSUZ
-- iddiayla sınanır. Olumlu kontrol ihmal edilemez: `dou_app` rolünün tablo düzeyi
-- GRANT'i eksik olsaydı her şey reddedilirdi ve yalnız olumsuz iddia yazan bir test
-- YANLIŞ SEBEPLE yeşil yanardı. Ayrıca politikası hiç olmayan üç işlem
-- (questions DELETE, answers UPDATE, mastery DELETE) fail-closed olarak sınanır.
--
-- Çalıştırma:
--     psql -d dou_synapse -f supabase/tests/rls_assessment.sql
--
-- Beklenen çıktı: her satırda PASS. Politikalar bozulursa ilgili satır FAIL'e döner.
-- Testin kırmızı yanabildiği ayrıca `rls_assessment_mutation_check.sh` ile kanıtlanır:
-- o betik politikaları teker teker bozar ve her birinde FAIL çıktığını doğrular.
--
-- CI (bu ekleme liderin işidir — .github/workflows/ci.yml, "RLS izolasyon kanıtı"
-- adımının hemen ardına):
--     psql -d rls_check -f supabase/tests/rls_assessment.sql 2>&1 | tee /tmp/rls_a.out
--     if grep -q FAIL /tmp/rls_a.out; then echo "assessment RLS bozuk"; exit 1; fi
--     supabase/tests/rls_assessment_mutation_check.sh rls_check

\set ON_ERROR_STOP on
\pset format unaligned
\pset tuples_only on

BEGIN;

-- ---------------------------------------------------------------------------
-- Kurulum: sahip/superuser olarak seed (RLS'i atlar)
-- ---------------------------------------------------------------------------
--
-- Dört kişi: bir eğitmen, aynı dersten iki öğrenci (öğrenci-öğrenci izolasyonu için
-- ikincisi şart) ve başka dersten bir öğrenci (ders-ders izolasyonu için).

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
     '11111111-1111-1111-1111-111111111111', '05-deadlock-demo.pdf', 'pdf',
     'courses/a/deadlock.pdf', 'hash-a', 1024, 'completed'),
    ('dddddddd-0000-0000-0000-000000000002', 'bbbbbbbb-0000-0000-0000-000000000002',
     '11111111-1111-1111-1111-111111111111', 'ds_hafta1.pdf', 'pdf',
     'courses/b/ds.pdf', 'hash-b', 2048, 'completed');

-- questions.source_chunk_id NOT NULL'dur: soru üretiminin kaynağı olmadan soru yazılamaz.
INSERT INTO chunks (id, course_id, document_id, chunk_index, page_number, text, token_count) VALUES
    ('cccccccc-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001',
     'dddddddd-0000-0000-0000-000000000001', 0, 1,
     'Deadlock için dört Coffman koşulu birlikte sağlanmalıdır.', 42),
    ('cccccccc-0000-0000-0000-000000000002', 'bbbbbbbb-0000-0000-0000-000000000002',
     'dddddddd-0000-0000-0000-000000000002', 0, 5,
     'Stack LIFO, queue FIFO prensibiyle çalışır.', 31);

INSERT INTO topics (id, course_id, name, created_by) VALUES
    -- A dersinin konuları. İkincisi silme testinde harcanır, üçüncüsü mastery
    -- yazma testinde kullanılır (mastery PK'sı (user_id, topic_id) olduğundan her
    -- olumlu yazma testi kendi konusunu ister).
    ('77777777-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001',
     'Deadlock', '11111111-1111-1111-1111-111111111111'),
    ('77777777-0000-0000-0000-000000000002', 'aaaaaaaa-0000-0000-0000-000000000001',
     'Silinecek konu', '11111111-1111-1111-1111-111111111111'),
    ('77777777-0000-0000-0000-000000000003', 'aaaaaaaa-0000-0000-0000-000000000001',
     'Senkronizasyon', '11111111-1111-1111-1111-111111111111'),
    ('77777777-0000-0000-0000-0000000000b1', 'bbbbbbbb-0000-0000-0000-000000000002',
     'Yığın ve kuyruk', '11111111-1111-1111-1111-111111111111');

INSERT INTO questions (id, course_id, topic_id, type, payload, source_chunk_id, status,
                       created_by, reviewed_by, reviewed_at) VALUES
    ('99999999-0000-0000-0000-00000000000d', 'aaaaaaaa-0000-0000-0000-000000000001',
     '77777777-0000-0000-0000-000000000001', 'open',
     '{"stem": "Taslak soru — öğrenci GÖRMEMELİ", "answer_key": "gizli"}',
     'cccccccc-0000-0000-0000-000000000001', 'draft',
     '11111111-1111-1111-1111-111111111111', NULL, NULL),
    ('99999999-0000-0000-0000-00000000000a', 'aaaaaaaa-0000-0000-0000-000000000001',
     '77777777-0000-0000-0000-000000000001', 'open',
     '{"stem": "Onaylı soru", "answer_key": "dört koşul"}',
     'cccccccc-0000-0000-0000-000000000001', 'approved',
     '11111111-1111-1111-1111-111111111111',
     '11111111-1111-1111-1111-111111111111', now()),
    -- Seed'deki cevap BU soruya bağlanır. Gerekçe: cevap yazma testleri
    -- `99999999-...-0a` sorusunu kullanıyor ve answers'ta UNIQUE(session_id,
    -- question_id) var. İkisi aynı soruyu kullansaydı politika gevşetildiğinde
    -- INSERT, RLS'e takılmadan önce unique_violation'a takılır ve testin ölçtüğü
    -- şey politika olmaktan çıkardı.
    ('99999999-0000-0000-0000-00000000000b', 'aaaaaaaa-0000-0000-0000-000000000001',
     '77777777-0000-0000-0000-000000000001', 'open',
     '{"stem": "Cevaplanmış soru", "answer_key": "dört koşul"}',
     'cccccccc-0000-0000-0000-000000000001', 'approved',
     '11111111-1111-1111-1111-111111111111',
     '11111111-1111-1111-1111-111111111111', now()),
    -- Silme testinin harcanabilir sorusu: hiçbir cevap buna referans vermez.
    -- Referanslı bir soru seçilseydi silme, politika izin verse bile
    -- answers.question_id'nin ON DELETE RESTRICT'ine takılırdı ve test yine 0 satır
    -- görüp YANLIŞ SEBEPLE yeşil yanardı.
    ('99999999-0000-0000-0000-00000000000e', 'aaaaaaaa-0000-0000-0000-000000000001',
     '77777777-0000-0000-0000-000000000001', 'open',
     '{"stem": "Silinebilir soru", "answer_key": "x"}',
     'cccccccc-0000-0000-0000-000000000001', 'approved',
     '11111111-1111-1111-1111-111111111111',
     '11111111-1111-1111-1111-111111111111', now()),
    ('99999999-0000-0000-0000-0000000000b1', 'bbbbbbbb-0000-0000-0000-000000000002',
     '77777777-0000-0000-0000-0000000000b1', 'open',
     '{"stem": "Diğer dersin sorusu", "answer_key": "LIFO"}',
     'cccccccc-0000-0000-0000-000000000002', 'approved',
     '11111111-1111-1111-1111-111111111111',
     '11111111-1111-1111-1111-111111111111', now());

INSERT INTO exam_sessions (id, course_id, user_id, mode, question_ids) VALUES
    ('55555555-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001',
     '22222222-2222-2222-2222-222222222222', 'practice',
     ARRAY['99999999-0000-0000-0000-00000000000a']::uuid[]),
    ('55555555-0000-0000-0000-000000000002', 'aaaaaaaa-0000-0000-0000-000000000001',
     '44444444-4444-4444-4444-444444444444', 'practice',
     ARRAY['99999999-0000-0000-0000-00000000000a']::uuid[]),
    ('55555555-0000-0000-0000-0000000000b1', 'bbbbbbbb-0000-0000-0000-000000000002',
     '33333333-3333-3333-3333-333333333333', 'practice',
     ARRAY['99999999-0000-0000-0000-0000000000b1']::uuid[]);

INSERT INTO answers (id, session_id, question_id, course_id, given, is_correct, score) VALUES
    ('66666666-0000-0000-0000-000000000001', '55555555-0000-0000-0000-000000000001',
     '99999999-0000-0000-0000-00000000000b', 'aaaaaaaa-0000-0000-0000-000000000001',
     'dört koşul', true, 100);

-- Analitik kaynakları (0003 + 0005). Sohbet mesajı ile ölçüm kaydı BİLE BİLE ayrı
-- ele alınır: eğitmen ölçüm kaydını okuyabilmeli, sohbet mesajını okuyamamalı.
INSERT INTO chat_sessions (id, course_id, user_id) VALUES
    ('eeeeeeee-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001',
     '22222222-2222-2222-2222-222222222222');

INSERT INTO chat_messages (session_id, course_id, role, content, status, seq) VALUES
    ('eeeeeeee-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001',
     'user', 'utanarak sordugum soru', NULL, 0),
    ('eeeeeeee-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001',
     'assistant', 'cevap', 'out_of_scope', 1);

INSERT INTO request_logs (course_id, user_id, route, mode, status, http_status, latency_ms) VALUES
    ('aaaaaaaa-0000-0000-0000-000000000001', '22222222-2222-2222-2222-222222222222',
     '/chat', 'qa', 'out_of_scope', 200, 120),
    ('aaaaaaaa-0000-0000-0000-000000000001', '22222222-2222-2222-2222-222222222222',
     '/chat', 'qa', 'answered', 200, 340),
    ('bbbbbbbb-0000-0000-0000-000000000002', '33333333-3333-3333-3333-333333333333',
     '/chat', 'qa', 'answered', 200, 210);

INSERT INTO mastery (user_id, topic_id, course_id, score, answer_count) VALUES
    ('22222222-2222-2222-2222-222222222222', '77777777-0000-0000-0000-000000000001',
     'aaaaaaaa-0000-0000-0000-000000000001', 0.80, 3),
    ('44444444-4444-4444-4444-444444444444', '77777777-0000-0000-0000-000000000001',
     'aaaaaaaa-0000-0000-0000-000000000001', 0.30, 2),
    ('33333333-3333-3333-3333-333333333333', '77777777-0000-0000-0000-0000000000b1',
     'bbbbbbbb-0000-0000-0000-000000000002', 0.55, 4);

-- ---------------------------------------------------------------------------
-- Testler: uygulama rolüyle. Superuser'la koşulsa RLS sessizce atlanır ve bu
-- dosyanın tamamı hiçbir şey kanıtlamadan yeşil yanardı.
-- ---------------------------------------------------------------------------

SET LOCAL ROLE dou_app;

-- ===========================================================================
-- topics_member_read
-- ===========================================================================

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
SELECT CASE WHEN count(*) = 3 THEN 'PASS' ELSE 'FAIL' END
       || '  topics_read__ogrenci_kendi_dersinin_konularini_gorur (beklenen 3, gelen '
       || count(*) || ')'
FROM topics;

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  topics_read__baska_dersin_konusu_gorunmez (beklenen 0, gelen ' || count(*) || ')'
FROM topics WHERE course_id = 'bbbbbbbb-0000-0000-0000-000000000002';

-- ===========================================================================
-- topics_instructor_write / _update / _delete
-- ===========================================================================

-- Öğrenci konu açamaz.
DO $$
BEGIN
    INSERT INTO topics (course_id, name, created_by)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001', 'Öğrencinin açtığı konu',
            '22222222-2222-2222-2222-222222222222');
    RAISE NOTICE 'FAIL  topics_write__ogrenci_konu_acamaz (insert beklenmedik şekilde geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  topics_write__ogrenci_konu_acamaz';
END
$$;

-- Öğrenci konu adını değiştiremez. UPDATE'te politika HATA vermez, satırı görünmez
-- kılar; bu yüzden iddia etkilenen satır sayısı üzerinden kurulur.
WITH changed AS (
    UPDATE topics SET name = 'Öğrenci değiştirdi'
    WHERE id = '77777777-0000-0000-0000-000000000001'
    RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  topics_update__ogrenci_konu_guncelleyemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM changed;

WITH removed AS (
    DELETE FROM topics WHERE id = '77777777-0000-0000-0000-000000000002' RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  topics_delete__ogrenci_konu_silemez (beklenen 0 satır, gelen ' || count(*) || ')'
FROM removed;

SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';

-- Olumlu kontrol: eğitmen gerçekten yazabiliyor. Bu satır olmadan yukarıdaki üç
-- reddin GRANT eksikliğinden mi politikadan mı geldiği bilinemez.
DO $$
BEGIN
    INSERT INTO topics (course_id, name, created_by)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001', 'Eğitmenin açtığı konu',
            '11111111-1111-1111-1111-111111111111');
    RAISE NOTICE 'PASS  topics_write__egitmen_konu_acabilir';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'FAIL  topics_write__egitmen_konu_acabilir (insert reddedildi)';
END
$$;

WITH changed AS (
    UPDATE topics SET name = 'Deadlock (güncellendi)'
    WHERE id = '77777777-0000-0000-0000-000000000001'
    RETURNING 1
)
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  topics_update__egitmen_konu_guncelleyebilir (beklenen 1 satır, gelen '
       || count(*) || ')'
FROM changed;

WITH removed AS (
    DELETE FROM topics WHERE id = '77777777-0000-0000-0000-000000000002' RETURNING 1
)
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  topics_delete__egitmen_konu_silebilir (beklenen 1 satır, gelen '
       || count(*) || ')'
FROM removed;

-- ===========================================================================
-- questions_read — 0004'ün EN KRİTİK politikası
-- ===========================================================================

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';

SELECT CASE WHEN count(*) = 3 THEN 'PASS' ELSE 'FAIL' END
       || '  questions_read__ogrenci_yalniz_onayli_gorur (beklenen 3, gelen ' || count(*) || ')'
FROM questions;

-- Aynı iddianın doğrudan biçimi: taslak soru öğrenciye HİÇ görünmemeli. Politikadan
-- `AND status = 'approved'` düşürüldüğünde kırmızıya dönen satır budur.
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  questions_read__ogrenci_taslak_soruyu_goremez (beklenen 0, gelen '
       || count(*) || ')'
FROM questions WHERE status = 'draft';

-- Cevap anahtarı sızıntısı ayrıca sınanır: satır görünmüyorsa payload da görünmez.
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  questions_read__ogrenci_taslak_cevap_anahtarini_goremez (beklenen 0, gelen '
       || count(*) || ')'
FROM questions WHERE payload->>'answer_key' = 'gizli';

SET LOCAL app.current_user_id = '33333333-3333-3333-3333-333333333333';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  questions_read__baska_dersin_ogrencisi_goremez (beklenen 0, gelen '
       || count(*) || ')'
FROM questions WHERE course_id = 'aaaaaaaa-0000-0000-0000-000000000001';

SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
SELECT CASE WHEN count(*) = 4 THEN 'PASS' ELSE 'FAIL' END
       || '  questions_read__egitmen_taslagi_da_gorur (beklenen 4, gelen ' || count(*) || ')'
FROM questions WHERE course_id = 'aaaaaaaa-0000-0000-0000-000000000001';

-- ===========================================================================
-- questions_instructor_write / _update  (+ DELETE politikası YOK: fail-closed)
-- ===========================================================================

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
DO $$
BEGIN
    INSERT INTO questions (course_id, topic_id, type, payload, source_chunk_id, status,
                           created_by)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            '77777777-0000-0000-0000-000000000001', 'open',
            '{"stem": "öğrenci sorusu", "answer_key": "x"}',
            'cccccccc-0000-0000-0000-000000000001', 'draft',
            '22222222-2222-2222-2222-222222222222');
    RAISE NOTICE 'FAIL  questions_write__ogrenci_soru_ekleyemez (insert beklenmedik şekilde geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  questions_write__ogrenci_soru_ekleyemez';
END
$$;

-- Öğrenci kendi kendine soru onaylayamaz: onay eğitmenin kararıdır (FR-023).
-- Bu iddiayı iki katman birden korur — taslak satır okuma politikası yüzünden
-- zaten görünmez. Aşağıdaki ikinci iddia UPDATE politikasını YALNIZ BAŞINA sınar.
WITH changed AS (
    UPDATE questions
    SET status = 'approved',
        reviewed_by = '22222222-2222-2222-2222-222222222222',
        reviewed_at = now()
    WHERE id = '99999999-0000-0000-0000-00000000000d'
    RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  questions_update__ogrenci_taslagi_onaylayamaz (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM changed;

-- UPDATE politikasının yalıtılmış sınavı: hedef satır öğrenciye GÖRÜNÜR (onaylı
-- soru), yani reddin tek kaynağı `questions_instructor_update` olabilir. Bu ayrım
-- mutasyon testiyle ortaya çıktı: yalnız taslak üzerinden yazılan iddia, UPDATE
-- politikası tamamen açıldığında bile yeşil kalıyordu — çünkü onu okuma politikası
-- kurtarıyordu ve test aslında UPDATE'i hiç ölçmüyordu.
WITH changed AS (
    UPDATE questions
    SET payload = '{"stem": "öğrenci değiştirdi", "answer_key": "x"}'
    WHERE id = '99999999-0000-0000-0000-00000000000a'
    RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  questions_update__ogrenci_onayli_soruyu_degistiremez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM changed;

SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
DO $$
BEGIN
    INSERT INTO questions (course_id, topic_id, type, payload, source_chunk_id, status,
                           created_by)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            '77777777-0000-0000-0000-000000000001', 'open',
            '{"stem": "eğitmen sorusu", "answer_key": "x"}',
            'cccccccc-0000-0000-0000-000000000001', 'draft',
            '11111111-1111-1111-1111-111111111111');
    RAISE NOTICE 'PASS  questions_write__egitmen_soru_ekleyebilir';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'FAIL  questions_write__egitmen_soru_ekleyebilir (insert reddedildi)';
END
$$;

WITH changed AS (
    UPDATE questions
    SET status = 'approved',
        reviewed_by = '11111111-1111-1111-1111-111111111111',
        reviewed_at = now()
    WHERE id = '99999999-0000-0000-0000-00000000000d'
    RETURNING 1
)
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  questions_update__egitmen_soru_onaylayabilir (beklenen 1 satır, gelen '
       || count(*) || ')'
FROM changed;

-- Öğrenci, okuyabildiği onaylı bir soruyu bile silemez. Okunabilir bir satır
-- seçmek önemlidir: aksi hâlde SELECT politikası DELETE politikasını maskeler.
SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
WITH removed AS (
    DELETE FROM questions WHERE id = '99999999-0000-0000-0000-00000000000d' RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  questions_delete__ogrenci_soru_silemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM removed;

-- Eğitmen, hiçbir cevabın referans vermediği kendi ders sorusunu silebilir. Bu
-- çıkış yolu kaynak belgenin daha sonra silinebilmesi için gereklidir.
SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
WITH removed AS (
    DELETE FROM questions WHERE id = '99999999-0000-0000-0000-00000000000e' RETURNING 1
)
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  questions_delete__egitmen_kendi_sorusunu_silebilir (beklenen 1 satır, gelen '
       || count(*) || ')'
FROM removed;

-- ===========================================================================
-- exam_sessions_self_read
-- ===========================================================================

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  exam_sessions_read__ogrenci_yalniz_kendi_oturumunu_gorur (beklenen 1, gelen '
       || count(*) || ')'
FROM exam_sessions;

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  exam_sessions_read__baska_ogrencinin_oturumu_gorunmez (beklenen 0, gelen '
       || count(*) || ')'
FROM exam_sessions WHERE user_id = '44444444-4444-4444-4444-444444444444';

SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
SELECT CASE WHEN count(*) = 2 THEN 'PASS' ELSE 'FAIL' END
       || '  exam_sessions_read__egitmen_dersinin_oturumlarini_gorur (beklenen 2, gelen '
       || count(*) || ')'
FROM exam_sessions WHERE course_id = 'aaaaaaaa-0000-0000-0000-000000000001';

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  exam_sessions_read__egitmen_baska_dersi_goremez (beklenen 0, gelen '
       || count(*) || ')'
FROM exam_sessions WHERE course_id = 'bbbbbbbb-0000-0000-0000-000000000002';

-- ===========================================================================
-- exam_sessions_self_insert
-- ===========================================================================

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
DO $$
BEGIN
    INSERT INTO exam_sessions (course_id, user_id, mode, question_ids)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            '44444444-4444-4444-4444-444444444444', 'practice', '{}'::uuid[]);
    RAISE NOTICE 'FAIL  exam_sessions_insert__baskasi_adina_oturum_acilamaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  exam_sessions_insert__baskasi_adina_oturum_acilamaz';
END
$$;

-- Üye olunmayan derste oturum açılamaz: istemciden gelen course_id yetki değildir.
SET LOCAL app.current_user_id = '33333333-3333-3333-3333-333333333333';
DO $$
BEGIN
    INSERT INTO exam_sessions (course_id, user_id, mode, question_ids)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            '33333333-3333-3333-3333-333333333333', 'practice', '{}'::uuid[]);
    RAISE NOTICE 'FAIL  exam_sessions_insert__uye_olunmayan_derste_oturum_acilamaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  exam_sessions_insert__uye_olunmayan_derste_oturum_acilamaz';
END
$$;

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
DO $$
BEGIN
    INSERT INTO exam_sessions (id, course_id, user_id, mode, question_ids)
    VALUES ('55555555-0000-0000-0000-00000000000f',
            'aaaaaaaa-0000-0000-0000-000000000001',
            '22222222-2222-2222-2222-222222222222', 'practice', '{}'::uuid[]);
    RAISE NOTICE 'PASS  exam_sessions_insert__ogrenci_kendi_oturumunu_acabilir';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'FAIL  exam_sessions_insert__ogrenci_kendi_oturumunu_acabilir (reddedildi)';
END
$$;

-- ===========================================================================
-- exam_sessions_self_update
-- ===========================================================================

-- Oturum yabancı bir derse TAŞINAMAZ. WITH CHECK olmasaydı Postgres güncellenen satır
-- için USING'i kullanırdı; USING yalnız user_id'ye bakar ve bu taşıma sessizce geçerdi
-- (PR incelemesi kalem 2 ile aynı sınıf açık). Hata `insufficient_privilege`'dır:
-- politika ihlali, görünmezlik değil.
DO $$
BEGIN
    UPDATE exam_sessions
    SET course_id = 'bbbbbbbb-0000-0000-0000-000000000002'
    WHERE id = '55555555-0000-0000-0000-000000000001';
    RAISE NOTICE 'FAIL  exam_sessions_update__oturum_yabanci_derse_tasinamaz (update geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  exam_sessions_update__oturum_yabanci_derse_tasinamaz';
END
$$;

WITH changed AS (
    -- 0007 tablo UPDATE'ini çekti, yalnız `finished_at` kolonunu verdi. Politika
    -- katmanını ölçmek için izinli kolonu kullan; `score` seçilirse red RLS'ten
    -- önce kolon yetkisinden gelir ve test yanlış sebeple yeşil olur.
    UPDATE exam_sessions SET finished_at = now()
    WHERE id = '55555555-0000-0000-0000-000000000002'
    RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  exam_sessions_update__baskasinin_oturumu_guncellenemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM changed;

-- UPDATE politikasının yalıtılmış sınavı. Yukarıdaki iddiada hedef satır zaten
-- OKUMA politikasıyla görünmez olduğu için, UPDATE politikası tamamen açılsa bile
-- iddia yeşil kalıyordu. Eğitmen ise dersinin bütün oturumlarını GÖRÜR — 0004'ün
-- kendi ifadesiyle "yalnız OKUR, yazamaz". Yani burada reddin tek kaynağı
-- `exam_sessions_self_update` olabilir.
--
-- Hedef Deniz'in oturumu: Burak'ınki bir üstteki iddiada BAŞKA BİR DERSE TAŞINMAYA
-- çalışılıyor ve politika gevşetildiğinde taşıma gerçekten oluyor. O satır üzerinden
-- yazılan bir iddia, eğitmen taşınmış dersin üyesi olmadığı için yanlışlıkla yeşil
-- kalırdı — mutasyon testinin yakaladığı üçüncü kusur.
SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
WITH changed AS (
    UPDATE exam_sessions SET finished_at = now()
    WHERE id = '55555555-0000-0000-0000-000000000002'
    RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  exam_sessions_update__egitmen_ogrenci_oturumunu_guncelleyemez '
       || '(beklenen 0 satır, gelen ' || count(*) || ')'
FROM changed;

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
WITH changed AS (
    UPDATE exam_sessions SET finished_at = now()
    WHERE id = '55555555-0000-0000-0000-000000000001'
    RETURNING 1
)
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  exam_sessions_update__kendi_oturumu_guncellenebilir (beklenen 1 satır, gelen '
       || count(*) || ')'
FROM changed;

-- ===========================================================================
-- answers_self_read
-- ===========================================================================

SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  answers_read__ogrenci_kendi_cevabini_gorur (beklenen 1, gelen ' || count(*) || ')'
FROM answers;

SET LOCAL app.current_user_id = '44444444-4444-4444-4444-444444444444';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  answers_read__baska_ogrencinin_cevabi_gorunmez (beklenen 0, gelen '
       || count(*) || ')'
FROM answers;

SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  answers_read__egitmen_dersinin_cevaplarini_gorur (beklenen 1, gelen '
       || count(*) || ')'
FROM answers;

-- ===========================================================================
-- answers_self_insert  (+ UPDATE politikası YOK: cevap değiştirilemez)
-- ===========================================================================

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';

-- Sahte course_id: satır kendi oturumuna ait ama başka dersin course_id'siyle
-- yazılmaya çalışılıyor. Geçseydi başka dersin eğitmen analitiğine satır enjekte
-- edilebilirdi (PR incelemesi kalem 2).
DO $$
BEGIN
    INSERT INTO answers (session_id, question_id, course_id, given, is_correct, score)
    VALUES ('55555555-0000-0000-0000-000000000001',
            '99999999-0000-0000-0000-00000000000a',
            'bbbbbbbb-0000-0000-0000-000000000002', 'sahte', true, 100);
    RAISE NOTICE 'FAIL  answers_insert__sahte_course_id_ile_yazilamaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  answers_insert__sahte_course_id_ile_yazilamaz';
END
$$;

DO $$
BEGIN
    INSERT INTO answers (session_id, question_id, course_id, given, is_correct, score)
    VALUES ('55555555-0000-0000-0000-000000000002',
            '99999999-0000-0000-0000-00000000000a',
            'aaaaaaaa-0000-0000-0000-000000000001', 'başkasının oturumu', true, 100);
    RAISE NOTICE 'FAIL  answers_insert__baskasinin_oturumuna_yazilamaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  answers_insert__baskasinin_oturumuna_yazilamaz';
END
$$;

DO $$
BEGIN
    INSERT INTO answers (session_id, question_id, course_id, given, is_correct, score)
    VALUES ('55555555-0000-0000-0000-00000000000f',
            '99999999-0000-0000-0000-00000000000a',
            'aaaaaaaa-0000-0000-0000-000000000001', 'kendi oturumum', true, 100);
    RAISE NOTICE 'PASS  answers_insert__kendi_oturumuna_yazabilir';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'FAIL  answers_insert__kendi_oturumuna_yazabilir (insert reddedildi)';
END
$$;

-- answers için UPDATE politikası bilinçli olarak YOKTUR: verilen cevap sonradan
-- düzeltilemez, yoksa "tek deneme" kuralı anlamını yitirir.
WITH changed AS (
    UPDATE answers SET given = 'sonradan düzelttim', score = 100
    WHERE id = '66666666-0000-0000-0000-000000000001'
    RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  answers_update__politika_yok_cevap_degistirilemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM changed;

-- ===========================================================================
-- mastery_self_read
-- ===========================================================================

SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  mastery_read__ogrenci_kendi_satirini_gorur (beklenen 1, gelen ' || count(*) || ')'
FROM mastery;

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  mastery_read__baska_ogrencinin_skoru_gorunmez (beklenen 0, gelen '
       || count(*) || ')'
FROM mastery WHERE user_id = '44444444-4444-4444-4444-444444444444';

SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
SELECT CASE WHEN count(*) = 2 THEN 'PASS' ELSE 'FAIL' END
       || '  mastery_read__egitmen_sinifin_skorlarini_gorur (beklenen 2, gelen '
       || count(*) || ')'
FROM mastery WHERE course_id = 'aaaaaaaa-0000-0000-0000-000000000001';

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  mastery_read__egitmen_baska_dersin_skorunu_goremez (beklenen 0, gelen '
       || count(*) || ')'
FROM mastery WHERE course_id = 'bbbbbbbb-0000-0000-0000-000000000002';

-- ===========================================================================
-- mastery_self_insert / _update
-- ===========================================================================

-- Üye olunmayan derse mastery yazılamaz. Politikada `app.is_member(course_id)`
-- eksikken bu geçiyordu ve üye olmayan biri, o dersin eğitmeninin analitiğine
-- sahte satır enjekte edebiliyordu (PR incelemesi kalem 2, canlı doğrulandı).
SET LOCAL app.current_user_id = '33333333-3333-3333-3333-333333333333';
DO $$
BEGIN
    INSERT INTO mastery (user_id, topic_id, course_id, score, answer_count)
    VALUES ('33333333-3333-3333-3333-333333333333',
            '77777777-0000-0000-0000-000000000003',
            'aaaaaaaa-0000-0000-0000-000000000001', 0.99, 1);
    RAISE NOTICE 'FAIL  mastery_insert__uye_olunmayan_derse_yazilamaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  mastery_insert__uye_olunmayan_derse_yazilamaz';
END
$$;

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
DO $$
BEGIN
    INSERT INTO mastery (user_id, topic_id, course_id, score, answer_count)
    VALUES ('44444444-4444-4444-4444-444444444444',
            '77777777-0000-0000-0000-000000000003',
            'aaaaaaaa-0000-0000-0000-000000000001', 0.10, 1);
    RAISE NOTICE 'FAIL  mastery_insert__baskasi_adina_yazilamaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  mastery_insert__baskasi_adina_yazilamaz';
END
$$;

DO $$
BEGIN
    INSERT INTO mastery (user_id, topic_id, course_id, score, answer_count)
    VALUES ('22222222-2222-2222-2222-222222222222',
            '77777777-0000-0000-0000-000000000003',
            'aaaaaaaa-0000-0000-0000-000000000001', 0.65, 1);
    RAISE NOTICE 'PASS  mastery_insert__kendi_satirini_yazabilir';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'FAIL  mastery_insert__kendi_satirini_yazabilir (insert reddedildi)';
END
$$;

WITH changed AS (
    UPDATE mastery SET score = 0.99
    WHERE user_id = '44444444-4444-4444-4444-444444444444'
      AND topic_id = '77777777-0000-0000-0000-000000000001'
    RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  mastery_update__baskasinin_skoru_guncellenemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM changed;

-- UPDATE politikasının yalıtılmış sınavı (yukarıdakiyle aynı gerekçe): eğitmen
-- sınıfın bütün mastery satırlarını okur, ama hiçbirini yazamaz. Not resmî değil
-- ama yine de öğrencinin verisidir; eğitmenin elle düzeltmesi göstergenin anlamını
-- bozardı.
SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
WITH changed AS (
    UPDATE mastery SET score = 0.99
    WHERE user_id = '22222222-2222-2222-2222-222222222222'
      AND topic_id = '77777777-0000-0000-0000-000000000001'
    RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  mastery_update__egitmen_ogrenci_skorunu_guncelleyemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM changed;

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
WITH changed AS (
    UPDATE mastery SET score = 0.85, answer_count = 4
    WHERE user_id = '22222222-2222-2222-2222-222222222222'
      AND topic_id = '77777777-0000-0000-0000-000000000001'
    RETURNING 1
)
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  mastery_update__kendi_skorunu_guncelleyebilir (beklenen 1 satır, gelen '
       || count(*) || ')'
FROM changed;

-- mastery için DELETE politikası YOKTUR: geçmiş silinemez.
WITH removed AS (
    DELETE FROM mastery
    WHERE user_id = '22222222-2222-2222-2222-222222222222'
      AND topic_id = '77777777-0000-0000-0000-000000000001'
    RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  mastery_delete__politika_yok_gecmis_silinemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM removed;

-- ===========================================================================
-- request_logs_instructor_read (0005) — analitiğin okuma yetkisi
-- ===========================================================================
--
-- 0003 bu tabloyu istemciye tamamen kapalı bıraktı ve eğitmen kapsamlı SELECT
-- politikasını 0005'e devretti. Aşağıdaki dört iddia o politikanın SINIRINI çizer:
-- eğitmen ölçüm kaydını okur, öğrenci okumaz, başka ders görünmez ve en önemlisi —
-- sohbet mesajları eğitmene KAPALI KALIR.

SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
SELECT CASE WHEN count(*) = 2 THEN 'PASS' ELSE 'FAIL' END
       || '  request_logs_read__egitmen_dersinin_kaydini_gorur (beklenen 2, gelen '
       || count(*) || ')'
FROM request_logs;

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  request_logs_read__egitmen_baska_dersi_goremez (beklenen 0, gelen '
       || count(*) || ')'
FROM request_logs WHERE course_id = 'bbbbbbbb-0000-0000-0000-000000000002';

-- 0005 YALNIZ request_logs'u açtı. Sohbet mesajları eğitmene kapalı kalmalı:
-- öğrencinin hocasına sormaya çekindiği soruyu sisteme sorabilmesi ürünün
-- gerekçelerinden biri (0003'ün gizlilik kararı). Bu iddia, analitik uğruna o
-- kararın sessizce delinmediğinin kanıtıdır.
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  chat_messages_read__egitmen_ogrenci_sohbetini_OKUYAMAZ (beklenen 0, gelen '
       || count(*) || ')'
FROM chat_messages;

-- Öğrenci kendi satırını bile okuyamaz: tablo uygulama rolü için yazma-yalnız.
SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  request_logs_read__ogrenci_hicbir_kaydi_goremez (beklenen 0, gelen '
       || count(*) || ')'
FROM request_logs;

-- ===========================================================================
-- Fail-closed: oturum bağlamı yoksa hiçbir satır görünmez (Anayasa IV)
-- ===========================================================================

SET LOCAL app.current_user_id = '';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  baglamsiz__topics_gorunmez (beklenen 0, gelen ' || count(*) || ')'
FROM topics;
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  baglamsiz__questions_gorunmez (beklenen 0, gelen ' || count(*) || ')'
FROM questions;
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  baglamsiz__exam_sessions_gorunmez (beklenen 0, gelen ' || count(*) || ')'
FROM exam_sessions;
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  baglamsiz__answers_gorunmez (beklenen 0, gelen ' || count(*) || ')'
FROM answers;
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  baglamsiz__mastery_gorunmez (beklenen 0, gelen ' || count(*) || ')'
FROM mastery;
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  baglamsiz__request_logs_gorunmez (beklenen 0, gelen ' || count(*) || ')'
FROM request_logs;

ROLLBACK;
