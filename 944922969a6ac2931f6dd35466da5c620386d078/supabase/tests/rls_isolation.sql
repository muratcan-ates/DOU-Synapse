-- Çekirdek şemanın RLS kanıtı — 0001'in on beş, 0003'ün dokuz politikası (T051).
--
-- NEDEN BU HÂLE GELDİ: bu dosya sekiz iddiayla başladı ve `chunks` ile `documents`
-- dışındaki hiçbir politikanın otomatik kanıtı yoktu. Ölçme katmanı için aynı boşluk
-- 6 Ağustos'ta ölçülmüştü (bkz. rls_assessment.sql başlığı): on beş politikanın tamamı
-- `USING (true)` yapılsa bile CI yeşil kalıyordu. Çekirdek şemada durum daha ağırdı,
-- çünkü izolasyon tezinin taşıyıcı tabloları burada: `courses`, `course_memberships`,
-- `chat_sessions`, `chat_messages`, `request_logs`.
--
-- KAPSAM: çekirdek ve sonraki hardening politikalarının her biri en az bir OLUMLU ve bir
-- OLUMSUZ iddiayla sınanır. Olumlu kontrol ihmal edilemez: `dou_app` rolünün tablo
-- düzeyi GRANT'i eksik olsaydı her şey reddedilirdi ve yalnız olumsuz iddia yazan bir
-- test YANLIŞ SEBEPLE yeşil yanardı. Ayrıca politikası bilinçli olarak OLMAYAN on üç
-- işlem (courses INSERT/DELETE, profiles INSERT/DELETE, chunks yazma, ingestion_jobs
-- UPDATE/DELETE, chat_messages UPDATE/DELETE, answer_cache UPDATE,
-- request_logs SELECT/UPDATE/DELETE) fail-closed olarak sınanır.
--
-- Çalıştırma:
--     psql -d dou_synapse -f supabase/tests/rls_isolation.sql
--
-- Beklenen çıktı: her satırda PASS. Testin KIRMIZI YANABİLDİĞİ ayrıca
-- `rls_isolation_mutation_check.sh` ile kanıtlanır: o betik politikaları teker teker
-- bozar ve her birinde HANGİ iddianın FAIL'e döndüğünü doğrular.
--
-- OKUMA NOTU 1 — iki iddia biçimi ve neden ikisi de gerekli:
--   * INSERT'te RLS ihlali HATA verir (42501) → `DO $$ ... EXCEPTION`
--   * UPDATE/DELETE'te RLS satırı GÖRÜNMEZ kılar, hata vermez → etkilenen satır sayısı
-- İkisi karıştırılırsa test sessizce anlamsızlaşır: hata beklenen yerde satır sayısı
-- saymak her zaman 0 verir ve politika tamamen açılsa bile yeşil kalır.
--
-- OKUMA NOTU 2 — SELECT politikası, UPDATE/DELETE politikasını MASKELER.
-- Mutasyon testi yazılırken ölçüldü (psql, 9 Ağustos): PostgreSQL bir UPDATE/DELETE'te
-- satırı bulmak için SELECT politikalarını da uygular ve UPDATE'te GÜNCELLENMİŞ satırın
-- da SELECT politikasından geçmesini ister. İki sonucu var:
--   1. "Başkasının satırını değiştiremez" biçimindeki iddialar, hedef satır zaten
--      görünmüyorsa UPDATE politikasını HİÇ ölçmez. Bu yüzden UPDATE/DELETE iddiaları
--      mümkün olduğunca aktörün GÖREBİLDİĞİ bir satır üzerinden kurulmuştur.
--   2. Bir satır, sahibinin göremeyeceği bir hâle güncellenemez. `chat_sessions`'ın
--      başka derse taşınamaması bu yüzden iki politikanın ortak sonucudur, yalnız
--      `chat_sessions_self_update`'in WITH CHECK'inin değil.
-- Bu, kodda bir kusur değil; testin neyi kanıtladığının doğru yazılması meselesidir.

\set ON_ERROR_STOP on
\pset format unaligned
\pset tuples_only on

BEGIN;

-- ---------------------------------------------------------------------------
-- Kurulum: sahip/superuser olarak seed (RLS'i atlar)
-- ---------------------------------------------------------------------------
--
-- Kadro, sınanacak izolasyon eksenlerinden türetildi:
--   ayşe   — A dersinin eğitmeni
--   burak  — A dersinin öğrencisi (çoğu iddianın öznesi)
--   deniz  — A dersinin İKİNCİ öğrencisi (öğrenci-öğrenci izolasyonu için şart)
--   ceren  — B dersinin öğrencisi (ders-ders izolasyonu)
--   emre   — hiçbir derse üye değil (bağlamsız kullanıcı)
--   gizem  — A dersinde üyeliği İPTAL EDİLMİŞ (status='revoked')
--   hakan  — A dersinin öğrencisi; üyelik güncelleme/silme testlerinde harcanır
--   irem   — üyeliği yok; ÖĞRENCİNİN üye ekleme denemesinde hedeftir
--   jale   — üyeliği yok; EĞİTMENİN üye ekleme testinde hedeftir
--
-- İrem ile Jale'nin ayrı olması bir zarafet değil, mutasyon testinin gereği: politika
-- açıldığında öğrencinin denemesi de geçer ve iki test aynı kişiyi eklemeye çalışırsa
-- ikincisi RLS'e değil birincil anahtar çakışmasına takılır. O hata `insufficient_privilege`
-- olmadığı için yakalanmaz, betiği düşürür ve mutasyon "kaçırıldı" görünür.

INSERT INTO profiles (id, email, full_name) VALUES
    ('11111111-1111-1111-1111-111111111111', 'ayse@dogus.edu.tr',  'Ayşe Eğitmen'),
    ('22222222-2222-2222-2222-222222222222', 'burak@dogus.edu.tr', 'Burak Öğrenci'),
    ('33333333-3333-3333-3333-333333333333', 'ceren@dogus.edu.tr', 'Ceren Öğrenci'),
    ('44444444-4444-4444-4444-444444444444', 'deniz@dogus.edu.tr', 'Deniz Öğrenci'),
    ('55555555-5555-5555-5555-555555555555', 'emre@dogus.edu.tr',  'Emre Dışarıdan'),
    ('77777777-7777-7777-7777-777777777777', 'gizem@dogus.edu.tr', 'Gizem İptal'),
    ('88888888-8888-8888-8888-888888888888', 'hakan@dogus.edu.tr', 'Hakan Öğrenci'),
    ('99999999-9999-9999-9999-999999999999', 'irem@dogus.edu.tr',  'İrem Eklenecek'),
    ('10101010-1010-1010-1010-101010101010', 'jale@dogus.edu.tr',  'Jale Eklenecek');

INSERT INTO courses (id, code, title, created_by) VALUES
    ('aaaaaaaa-0000-0000-0000-000000000001', 'COME301', 'İşletim Sistemleri',
     '11111111-1111-1111-1111-111111111111'),
    ('bbbbbbbb-0000-0000-0000-000000000002', 'COME302', 'Veri Yapıları',
     '11111111-1111-1111-1111-111111111111');

INSERT INTO course_memberships (course_id, user_id, role, status) VALUES
    ('aaaaaaaa-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111',
     'instructor', 'active'),
    ('aaaaaaaa-0000-0000-0000-000000000001', '22222222-2222-2222-2222-222222222222',
     'student', 'active'),
    ('aaaaaaaa-0000-0000-0000-000000000001', '44444444-4444-4444-4444-444444444444',
     'student', 'active'),
    ('aaaaaaaa-0000-0000-0000-000000000001', '77777777-7777-7777-7777-777777777777',
     'student', 'revoked'),
    ('aaaaaaaa-0000-0000-0000-000000000001', '88888888-8888-8888-8888-888888888888',
     'student', 'active'),
    ('bbbbbbbb-0000-0000-0000-000000000002', '33333333-3333-3333-3333-333333333333',
     'student', 'active');

INSERT INTO documents (id, course_id, uploaded_by, file_name, file_type,
                       storage_path, file_hash, byte_size, status) VALUES
    ('dddddddd-0000-0000-0000-00000000000a', 'aaaaaaaa-0000-0000-0000-000000000001',
     '11111111-1111-1111-1111-111111111111', 'os_hafta3.pdf', 'pdf',
     'courses/a/os_hafta3.pdf', 'hash-a1', 1024, 'completed'),
    -- Silme testinde harcanır; chunk'ı yoktur ki chunk sayıları kaymasın.
    ('dddddddd-0000-0000-0000-00000000000b', 'aaaaaaaa-0000-0000-0000-000000000001',
     '11111111-1111-1111-1111-111111111111', 'silinecek.pdf', 'pdf',
     'courses/a/silinecek.pdf', 'hash-a2', 512, 'completed'),
    ('dddddddd-0000-0000-0000-00000000000c', 'bbbbbbbb-0000-0000-0000-000000000002',
     '11111111-1111-1111-1111-111111111111', 'ds_hafta1.pdf', 'pdf',
     'courses/b/ds_hafta1.pdf', 'hash-b1', 2048, 'completed');

INSERT INTO chunks (id, course_id, document_id, chunk_index, page_number, text, token_count) VALUES
    ('cccccccc-0000-0000-0000-00000000000a', 'aaaaaaaa-0000-0000-0000-000000000001',
     'dddddddd-0000-0000-0000-00000000000a', 0, 12,
     'Deadlock için dört Coffman koşulu birlikte sağlanmalıdır.', 42),
    ('cccccccc-0000-0000-0000-00000000000c', 'bbbbbbbb-0000-0000-0000-000000000002',
     'dddddddd-0000-0000-0000-00000000000c', 0, 5,
     'Stack LIFO, queue FIFO prensibiyle çalışır.', 31);

INSERT INTO ingestion_jobs (id, document_id, status) VALUES
    ('eeeeeeee-0000-0000-0000-00000000000a', 'dddddddd-0000-0000-0000-00000000000a', 'completed'),
    ('eeeeeeee-0000-0000-0000-00000000000c', 'dddddddd-0000-0000-0000-00000000000c', 'completed');

INSERT INTO chat_sessions (id, course_id, user_id, mode) VALUES
    ('5a5a5a5a-0000-0000-0000-00000000000b', 'aaaaaaaa-0000-0000-0000-000000000001',
     '22222222-2222-2222-2222-222222222222', 'qa'),
    ('5a5a5a5a-0000-0000-0000-00000000000d', 'aaaaaaaa-0000-0000-0000-000000000001',
     '44444444-4444-4444-4444-444444444444', 'qa'),
    ('5a5a5a5a-0000-0000-0000-00000000000c', 'bbbbbbbb-0000-0000-0000-000000000002',
     '33333333-3333-3333-3333-333333333333', 'qa');

INSERT INTO chat_messages
    (id, session_id, course_id, role, content, status, seq, created_at) VALUES
    ('6b6b6b6b-0000-0000-0000-00000000000b', '5a5a5a5a-0000-0000-0000-00000000000b',
     'aaaaaaaa-0000-0000-0000-000000000001', 'user', 'Deadlock nedir?', NULL, 0,
     now() - interval '1 hour'),
    ('6b6b6b6b-0000-0000-0000-00000000001b', '5a5a5a5a-0000-0000-0000-00000000000b',
     'aaaaaaaa-0000-0000-0000-000000000001', 'assistant',
     'Deadlock dört Coffman koşulunun birlikte oluşmasıdır.', 'answered', 1,
     now() - interval '59 minutes'),
    ('6b6b6b6b-0000-0000-0000-00000000000d', '5a5a5a5a-0000-0000-0000-00000000000d',
     'aaaaaaaa-0000-0000-0000-000000000001', 'user', 'Bu soruyu hocam görmemeli.', NULL, 0,
     now() - interval '1 hour'),
    ('6b6b6b6b-0000-0000-0000-00000000001d', '5a5a5a5a-0000-0000-0000-00000000000d',
     'aaaaaaaa-0000-0000-0000-000000000001', 'assistant', 'Bu yanıt Deniz içindir.',
     'answered', 1, now() - interval '59 minutes'),
    ('6b6b6b6b-0000-0000-0000-00000000000c', '5a5a5a5a-0000-0000-0000-00000000000c',
     'bbbbbbbb-0000-0000-0000-000000000002', 'user', 'Yığın ile kuyruk farkı?', NULL, 0,
     now() - interval '1 hour'),
    ('6b6b6b6b-0000-0000-0000-00000000001c', '5a5a5a5a-0000-0000-0000-00000000000c',
     'bbbbbbbb-0000-0000-0000-000000000002', 'assistant', 'Yığın LIFO, kuyruk FIFO çalışır.',
     'answered', 1, now() - interval '59 minutes');

INSERT INTO answer_cache (id, course_id, question_hash, answer) VALUES
    ('7c7c7c7c-0000-0000-0000-00000000000a', 'aaaaaaaa-0000-0000-0000-000000000001',
     'hash-soru-a', '{"status": "answered", "text": "A dersinin cevabı"}'),
    ('7c7c7c7c-0000-0000-0000-00000000000c', 'bbbbbbbb-0000-0000-0000-000000000002',
     'hash-soru-b', '{"status": "answered", "text": "B dersinin cevabı"}');

INSERT INTO request_logs (course_id, user_id, route, mode, http_status, latency_ms) VALUES
    ('aaaaaaaa-0000-0000-0000-000000000001', '22222222-2222-2222-2222-222222222222',
     '/courses/{id}/chat', 'qa', 200, 850),
    ('bbbbbbbb-0000-0000-0000-000000000002', '33333333-3333-3333-3333-333333333333',
     '/courses/{id}/chat', 'qa', 200, 910);

-- ---------------------------------------------------------------------------
-- Testler: uygulama rolüyle
-- ---------------------------------------------------------------------------

SET LOCAL ROLE dou_app;

-- ===========================================================================
-- profiles_self_read / profiles_self_update  (+ INSERT ve DELETE politikası YOK)
-- ===========================================================================

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  profiles_read__ogrenci_yalniz_kendini_gorur (beklenen 1, gelen ' || count(*) || ')'
FROM profiles;

-- Öğrenci-öğrenci izolasyonu: aynı dersteki arkadaşının e-postası bile görünmez.
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  profiles_read__ogrenci_arkadasinin_profilini_goremez (beklenen 0, gelen '
       || count(*) || ')'
FROM profiles WHERE id = '44444444-4444-4444-4444-444444444444';

SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
-- Eğitmen kendini + A dersinin AKTİF öğrencilerini görür (gizem iptal, sayılmaz).
SELECT CASE WHEN count(*) = 4 THEN 'PASS' ELSE 'FAIL' END
       || '  profiles_read__egitmen_kendi_ogrencilerini_gorur (beklenen 4, gelen '
       || count(*) || ')'
FROM profiles;

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  profiles_read__egitmen_baska_dersin_ogrencisini_goremez (beklenen 0, gelen '
       || count(*) || ')'
FROM profiles WHERE id = '33333333-3333-3333-3333-333333333333';

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  profiles_read__iptal_edilmis_uyelik_egitmene_gorunmez (beklenen 0, gelen '
       || count(*) || ')'
FROM profiles WHERE id = '77777777-7777-7777-7777-777777777777';

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
WITH changed AS (
    UPDATE profiles SET full_name = 'Burak Güncel'
    WHERE id = '22222222-2222-2222-2222-222222222222' RETURNING 1
)
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  profiles_update__kendi_adini_degistirebilir (beklenen 1 satır, gelen '
       || count(*) || ')'
FROM changed;

WITH changed AS (
    UPDATE profiles SET full_name = 'Ele geçirildi'
    WHERE id = '44444444-4444-4444-4444-444444444444' RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  profiles_update__baskasinin_adini_degistiremez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM changed;

-- Yukarıdaki iddia `profiles_self_update`'i YALNIZ BAŞINA ölçmez: deniz'in satırı burak'a
-- zaten görünmüyor, yani red okuma politikasından da gelebilir (OKUMA NOTU 2). Aşağıdaki
-- iddia ayrımı kurar: eğitmen öğrencisinin profilini GÖRÜR ama DEĞİŞTİREMEZ; buradaki
-- reddin tek kaynağı `profiles_self_update` olabilir.
SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
WITH changed AS (
    UPDATE profiles SET full_name = 'Eğitmen değiştirdi'
    WHERE id = '22222222-2222-2222-2222-222222222222' RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  profiles_update__egitmen_ogrencinin_adini_degistiremez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM changed;

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';

-- `profiles_self_update`'te WITH CHECK yazılmamıştır ve PostgreSQL bu durumda USING
-- ifadesini WITH CHECK olarak da uygular. Sonuç: kullanıcı kendi satırını BAŞKASININ
-- kimliğine taşıyamaz. Bu davranış bir yan etki, kayıtlı bir karar değil; testi olsun
-- ki `WITH CHECK (true)` eklenirse kimse bunu "zararsız bir netleştirme" sanmasın.
DO $$
BEGIN
    UPDATE profiles SET id = '44444444-4444-4444-4444-444444444444'
    WHERE id = '22222222-2222-2222-2222-222222222222';
    RAISE NOTICE 'FAIL  profiles_update__kimligini_baskasina_tasiyamaz (update geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  profiles_update__kimligini_baskasina_tasiyamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  profiles_update__kimligini_baskasina_tasiyamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

-- Profil satırı yalnız kimlik sağlayıcısından doğar (0002 köprüsü). Uygulama rolünün
-- profil yaratma yetkisi yoktur: olsaydı, var olmayan bir kullanıcı adına satır açıp
-- derse üye eklemek mümkün olurdu.
DO $$
BEGIN
    INSERT INTO profiles (id, email, full_name)
    VALUES ('12121212-0000-0000-0000-000000000000', 'sahte@dogus.edu.tr', 'Sahte');
    RAISE NOTICE 'FAIL  profiles_insert__politika_yok_profil_yaratilamaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  profiles_insert__politika_yok_profil_yaratilamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  profiles_insert__politika_yok_profil_yaratilamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

WITH removed AS (
    DELETE FROM profiles WHERE id = '22222222-2222-2222-2222-222222222222' RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  profiles_delete__politika_yok_profil_silinemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM removed;

-- ===========================================================================
-- courses_member_read / courses_instructor_update  (+ INSERT ve DELETE politikası YOK)
-- ===========================================================================

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  courses_read__ogrenci_yalniz_uye_oldugu_dersi_gorur (beklenen 1, gelen '
       || count(*) || ')'
FROM courses;

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  courses_read__baska_ders_gorunmez (beklenen 0, gelen ' || count(*) || ')'
FROM courses WHERE id = 'bbbbbbbb-0000-0000-0000-000000000002';

-- Olumlu karşı kontrol: aynı sorgu O dersin öğrencisi için sonuç döndürür. Bu satır
-- olmadan "filtre her şeyi gizliyor" ile "filtre kullanıcıya göre çalışıyor" ayrılamaz.
SET LOCAL app.current_user_id = '33333333-3333-3333-3333-333333333333';
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  courses_read__kendi_dersinin_ogrencisi_gorur (beklenen 1, gelen '
       || count(*) || ')'
FROM courses WHERE id = 'bbbbbbbb-0000-0000-0000-000000000002';

SET LOCAL app.current_user_id = '55555555-5555-5555-5555-555555555555';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  courses_read__uyeligi_olmayan_hicbir_ders_gormez (beklenen 0, gelen '
       || count(*) || ')'
FROM courses;

-- İptal edilmiş üyelik erişim vermez: `app.is_member` yalnız status='active' sayar.
-- Bu, öğrenci dersten çıkarıldığında materyalin erişilemez olmasının tek dayanağı.
SET LOCAL app.current_user_id = '77777777-7777-7777-7777-777777777777';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  courses_read__iptal_edilmis_uyelik_ders_gostermez (beklenen 0, gelen '
       || count(*) || ')'
FROM courses;

SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
WITH changed AS (
    UPDATE courses SET title = 'İşletim Sistemleri (2026)'
    WHERE id = 'aaaaaaaa-0000-0000-0000-000000000001' RETURNING 1
)
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  courses_update__egitmen_kendi_dersini_guncelleyebilir (beklenen 1 satır, gelen '
       || count(*) || ')'
FROM changed;

WITH changed AS (
    UPDATE courses SET title = 'Ele geçirildi'
    WHERE id = 'bbbbbbbb-0000-0000-0000-000000000002' RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  courses_update__egitmen_baska_dersi_guncelleyemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM changed;

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
WITH changed AS (
    UPDATE courses SET title = 'Öğrenci değiştirdi'
    WHERE id = 'aaaaaaaa-0000-0000-0000-000000000001' RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  courses_update__ogrenci_ders_guncelleyemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM changed;

-- Ders oluşturma bir bootstrap işlemidir ve politikayla ifade edilemez (0001 yorumu);
-- doğrudan INSERT bilinçli olarak kapalıdır, meşru yol `app.create_course()`.
DO $$
BEGIN
    INSERT INTO courses (code, title, created_by)
    VALUES ('COME999', 'Kaçak Ders', '22222222-2222-2222-2222-222222222222');
    RAISE NOTICE 'FAIL  courses_insert__politika_yok_dogrudan_yazilamaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  courses_insert__politika_yok_dogrudan_yazilamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  courses_insert__politika_yok_dogrudan_yazilamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

WITH removed AS (
    DELETE FROM courses WHERE id = 'aaaaaaaa-0000-0000-0000-000000000001' RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  courses_delete__politika_yok_ders_silinemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM removed;

-- ===========================================================================
-- memberships_read / _insert / _instructor_update / _instructor_delete
-- ===========================================================================

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  memberships_read__ogrenci_yalniz_kendi_uyeligini_gorur (beklenen 1, gelen '
       || count(*) || ')'
FROM course_memberships;

-- Sınıf listesi öğrenciye kapalı: kimlerin kayıtlı olduğu da ders verisidir.
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  memberships_read__ogrenci_sinif_listesini_goremez (beklenen 0, gelen '
       || count(*) || ')'
FROM course_memberships WHERE user_id <> '22222222-2222-2222-2222-222222222222';

SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
SELECT CASE WHEN count(*) = 5 THEN 'PASS' ELSE 'FAIL' END
       || '  memberships_read__egitmen_dersin_tum_uyeliklerini_gorur (beklenen 5, gelen '
       || count(*) || ')'
FROM course_memberships;

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  memberships_read__egitmen_baska_dersin_uyeligini_goremez (beklenen 0, gelen '
       || count(*) || ')'
FROM course_memberships WHERE course_id = 'bbbbbbbb-0000-0000-0000-000000000002';

-- Yetki yükseltme denemesi: öğrenci kendi rolünü eğitmene çeviremez. Bu iddia
-- düşerse projedeki her "yalnız eğitmen" kontrolü anlamsızlaşır.
SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
DO $$
DECLARE
    changed integer;
BEGIN
    UPDATE course_memberships SET role = 'instructor'
    WHERE course_id = 'aaaaaaaa-0000-0000-0000-000000000001'
      AND user_id = '22222222-2222-2222-2222-222222222222';
    GET DIAGNOSTICS changed = ROW_COUNT;
    IF changed = 0 THEN
        RAISE NOTICE 'PASS  memberships_update__ogrenci_kendini_egitmen_yapamaz (0 satır)';
    ELSE
        RAISE NOTICE 'FAIL  memberships_update__ogrenci_kendini_egitmen_yapamaz (rol değişti)';
    END IF;
EXCEPTION
    -- 0012'nin dar `memberships_self_revoke` politikası satırı UPDATE için
    -- görünür kılar ama yalnız status=revoked son durumuna izin verir. Bu yüzden
    -- rol yükseltme 0 satır yerine WITH CHECK ihlali verebilir; ikisi de güvenli
    -- rettir. Politika `USING (true)` ile gevşetilirse UPDATE geçer ve FAIL yanar.
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  memberships_update__ogrenci_kendini_egitmen_yapamaz (RLS reddi)';
END
$$;

DO $$
BEGIN
    INSERT INTO course_memberships (course_id, user_id, role)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            '99999999-9999-9999-9999-999999999999', 'student');
    RAISE NOTICE 'FAIL  memberships_insert__ogrenci_uye_ekleyemez (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  memberships_insert__ogrenci_uye_ekleyemez';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  memberships_insert__ogrenci_uye_ekleyemez (beklenmedik hata: %)', SQLERRM;
END
$$;

-- Hedef, burak'ın GÖREBİLDİĞİ tek üyelik satırı: kendisininki. Başka birinin satırı
-- seçilseydi red okuma politikasından gelirdi ve `memberships_instructor_delete`
-- hiç ölçülmemiş olurdu (OKUMA NOTU 2). Öğrenci üyeliğini DELETE edemez;
-- 0012 yalnız status=revoked güncellemesini açar.
WITH removed AS (
    DELETE FROM course_memberships
    WHERE course_id = 'aaaaaaaa-0000-0000-0000-000000000001'
      AND user_id = '22222222-2222-2222-2222-222222222222'
    RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  memberships_delete__ogrenci_kendi_uyeligini_silemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM removed;

-- Üstteki silme, politika gevşetildiğinde GERÇEKTEN siler ve burak'ın üyeliği ortadan
-- kalkar; o andan sonraki her bölüm ("dersini görür", "belge okur", "oturum açar")
-- sessizce anlamsızlaşır ve bozulmamış politikalar da kırmızı yanar. Mutasyon koşusunda
-- ölçüldü: `app.is_instructor`'ın rol şartını düşüren mutasyon bu yüzden YAKALANAMAMIŞ
-- görünüyordu. Üyelik sahip rolle geri konuyor — bozulmamış şemada bu deyim hiçbir şeyi
-- değiştirmez, mutasyon altında ise testin kalan kısmını ölçülebilir tutar.
RESET ROLE;
INSERT INTO course_memberships (course_id, user_id, role, status)
VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
        '22222222-2222-2222-2222-222222222222', 'student', 'active')
ON CONFLICT (course_id, user_id) DO UPDATE SET role = 'student', status = 'active';
SET LOCAL ROLE dou_app;

SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
DO $$
BEGIN
    INSERT INTO course_memberships (course_id, user_id, role)
    VALUES ('bbbbbbbb-0000-0000-0000-000000000002',
            '99999999-9999-9999-9999-999999999999', 'student');
    RAISE NOTICE 'FAIL  memberships_insert__egitmen_baska_derse_uye_ekleyemez (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  memberships_insert__egitmen_baska_derse_uye_ekleyemez';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  memberships_insert__egitmen_baska_derse_uye_ekleyemez (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
BEGIN
    INSERT INTO course_memberships (course_id, user_id, role)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            '10101010-1010-1010-1010-101010101010', 'student');
    RAISE NOTICE 'PASS  memberships_insert__egitmen_kendi_dersine_uye_ekleyebilir';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'FAIL  memberships_insert__egitmen_kendi_dersine_uye_ekleyebilir (reddedildi)';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  memberships_insert__egitmen_kendi_dersine_uye_ekleyebilir (beklenmedik hata: %)', SQLERRM;
END
$$;

WITH changed AS (
    UPDATE course_memberships SET status = 'revoked'
    WHERE course_id = 'aaaaaaaa-0000-0000-0000-000000000001'
      AND user_id = '88888888-8888-8888-8888-888888888888'
    RETURNING 1
)
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  memberships_update__egitmen_uyeligi_iptal_edebilir (beklenen 1 satır, gelen '
       || count(*) || ')'
FROM changed;

WITH removed AS (
    DELETE FROM course_memberships
    WHERE course_id = 'aaaaaaaa-0000-0000-0000-000000000001'
      AND user_id = '88888888-8888-8888-8888-888888888888'
    RETURNING 1
)
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  memberships_delete__egitmen_uyelik_silebilir (beklenen 1 satır, gelen '
       || count(*) || ')'
FROM removed;

-- ===========================================================================
-- documents_member_read / _instructor_insert / _update / _delete
-- ===========================================================================

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
SELECT CASE WHEN count(*) = 2 THEN 'PASS' ELSE 'FAIL' END
       || '  documents_read__ogrenci_dersinin_belgelerini_gorur (beklenen 2, gelen '
       || count(*) || ')'
FROM documents;

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  documents_read__baska_dersin_belgesi_gorunmez (beklenen 0, gelen '
       || count(*) || ')'
FROM documents WHERE course_id = 'bbbbbbbb-0000-0000-0000-000000000002';

SET LOCAL app.current_user_id = '33333333-3333-3333-3333-333333333333';
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  documents_read__kendi_dersinin_ogrencisi_gorur (beklenen 1, gelen '
       || count(*) || ')'
FROM documents WHERE course_id = 'bbbbbbbb-0000-0000-0000-000000000002';

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
DO $$
BEGIN
    INSERT INTO documents (course_id, uploaded_by, file_name, file_type,
                           storage_path, file_hash, byte_size)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            '22222222-2222-2222-2222-222222222222', 'ogrenci.pdf', 'pdf',
            'x', 'hash-ogrenci', 10);
    RAISE NOTICE 'FAIL  documents_insert__ogrenci_belge_yukleyemez (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  documents_insert__ogrenci_belge_yukleyemez';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  documents_insert__ogrenci_belge_yukleyemez (beklenmedik hata: %)', SQLERRM;
END
$$;

WITH changed AS (
    UPDATE documents SET file_name = 'ogrenci_degistirdi.pdf'
    WHERE id = 'dddddddd-0000-0000-0000-00000000000a' RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  documents_update__ogrenci_belge_guncelleyemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM changed;

WITH removed AS (
    DELETE FROM documents WHERE id = 'dddddddd-0000-0000-0000-00000000000b' RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  documents_delete__ogrenci_belge_silemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM removed;

SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
DO $$
BEGIN
    INSERT INTO documents (course_id, uploaded_by, file_name, file_type,
                           storage_path, file_hash, byte_size)
    VALUES ('bbbbbbbb-0000-0000-0000-000000000002',
            '11111111-1111-1111-1111-111111111111', 'kacak.pdf', 'pdf',
            'y', 'hash-kacak', 10);
    RAISE NOTICE 'FAIL  documents_insert__egitmen_baska_derse_yukleyemez (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  documents_insert__egitmen_baska_derse_yukleyemez';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  documents_insert__egitmen_baska_derse_yukleyemez (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
BEGIN
    INSERT INTO documents (course_id, uploaded_by, file_name, file_type,
                           storage_path, file_hash, byte_size)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            '11111111-1111-1111-1111-111111111111', 'yeni.pdf', 'pdf',
            'z', 'hash-yeni', 10);
    RAISE NOTICE 'PASS  documents_insert__egitmen_kendi_dersine_yukleyebilir';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'FAIL  documents_insert__egitmen_kendi_dersine_yukleyebilir (reddedildi)';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  documents_insert__egitmen_kendi_dersine_yukleyebilir (beklenmedik hata: %)', SQLERRM;
END
$$;

WITH changed AS (
    UPDATE documents SET status = 'completed'
    WHERE id = 'dddddddd-0000-0000-0000-00000000000a' RETURNING 1
)
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  documents_update__egitmen_belge_guncelleyebilir (beklenen 1 satır, gelen '
       || count(*) || ')'
FROM changed;

WITH removed AS (
    DELETE FROM documents WHERE id = 'dddddddd-0000-0000-0000-00000000000b' RETURNING 1
)
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  documents_delete__egitmen_belge_silebilir (beklenen 1 satır, gelen '
       || count(*) || ')'
FROM removed;

-- ===========================================================================
-- chunks_member_read  (+ INSERT/UPDATE/DELETE politikası YOK — yazma worker'ındır)
-- ===========================================================================

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  chunks_read__ogrenci_kendi_dersinin_chunklarini_gorur (beklenen 1, gelen '
       || count(*) || ')'
FROM chunks;

-- Uygulama katmanı delinip course_id istemciden gelseydi olacak senaryo.
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  chunks_read__baska_dersin_chunki_gorunmez (beklenen 0, gelen ' || count(*) || ')'
FROM chunks WHERE course_id = 'bbbbbbbb-0000-0000-0000-000000000002';

SET LOCAL app.current_user_id = '33333333-3333-3333-3333-333333333333';
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  chunks_read__kendi_dersinin_ogrencisi_gorur (beklenen 1, gelen ' || count(*) || ')'
FROM chunks WHERE course_id = 'bbbbbbbb-0000-0000-0000-000000000002';

-- Chunk yazımı yalnız worker'ındır (dou_worker, BYPASSRLS). Uygulama rolü — eğitmen
-- bile olsa — chunk yazamaz: yazabilseydi retrieval'a kaynağı olmayan metin
-- enjekte edilebilir ve "kaynak yoksa cevap yok" güvencesi çökerdi (Anayasa I).
SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
DO $$
BEGIN
    INSERT INTO chunks (course_id, document_id, chunk_index, text, token_count)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            'dddddddd-0000-0000-0000-00000000000a', 99, 'Uydurma kaynak metni', 5);
    RAISE NOTICE 'FAIL  chunks_insert__politika_yok_uygulama_chunk_yazamaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  chunks_insert__politika_yok_uygulama_chunk_yazamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  chunks_insert__politika_yok_uygulama_chunk_yazamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

WITH changed AS (
    UPDATE chunks SET text = 'Değiştirilmiş kaynak'
    WHERE id = 'cccccccc-0000-0000-0000-00000000000a' RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  chunks_update__politika_yok_kaynak_degistirilemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM changed;

WITH removed AS (
    DELETE FROM chunks WHERE id = 'cccccccc-0000-0000-0000-00000000000a' RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  chunks_delete__politika_yok_kaynak_silinemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM removed;

-- ===========================================================================
-- jobs_instructor_read / _insert  (+ doğrudan UPDATE/DELETE politikası YOK)
-- ===========================================================================

SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  jobs_read__egitmen_kendi_dersinin_isini_gorur (beklenen 1, gelen '
       || count(*) || ')'
FROM ingestion_jobs;

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  jobs_read__ogrenci_is_kuyrugunu_goremez (beklenen 0, gelen ' || count(*) || ')'
FROM ingestion_jobs;

DO $$
BEGIN
    INSERT INTO ingestion_jobs (document_id)
    VALUES ('dddddddd-0000-0000-0000-00000000000a');
    RAISE NOTICE 'FAIL  jobs_insert__ogrenci_is_kuyruguna_yazamaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  jobs_insert__ogrenci_is_kuyruguna_yazamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  jobs_insert__ogrenci_is_kuyruguna_yazamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
DO $$
BEGIN
    INSERT INTO ingestion_jobs (document_id)
    VALUES ('dddddddd-0000-0000-0000-00000000000c');
    RAISE NOTICE 'FAIL  jobs_insert__egitmen_baska_dersin_isini_kuyruklayamaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  jobs_insert__egitmen_baska_dersin_isini_kuyruklayamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  jobs_insert__egitmen_baska_dersin_isini_kuyruklayamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
BEGIN
    INSERT INTO ingestion_jobs (document_id)
    VALUES ('dddddddd-0000-0000-0000-00000000000a');
    RAISE NOTICE 'PASS  jobs_insert__egitmen_kendi_dersinin_isini_kuyruklayabilir';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE
            'FAIL  jobs_insert__egitmen_kendi_dersinin_isini_kuyruklayabilir (reddedildi)';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  jobs_insert__egitmen_kendi_dersinin_isini_kuyruklayabilir (beklenmedik hata: %)', SQLERRM;
END
$$;

-- İş durumunu yalnız worker günceller; uygulama rolü kuyruğu ilerletemez. 0010
-- savunmayı iki katmanlı yapar: tablo UPDATE yetkisi de RLS politikası da yoktur.
DO $$
DECLARE
    v_count integer;
BEGIN
    UPDATE ingestion_jobs SET status = 'completed'
    WHERE id = 'eeeeeeee-0000-0000-0000-00000000000a';
    GET DIAGNOSTICS v_count = ROW_COUNT;
    IF v_count = 0 THEN
        RAISE NOTICE 'PASS  jobs_update__politika_yok_uygulama_isi_ilerletemez';
    ELSE
        RAISE NOTICE 'FAIL  jobs_update__politika_yok_uygulama_isi_ilerletemez (update geçti)';
    END IF;
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  jobs_update__politika_yok_uygulama_isi_ilerletemez';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  jobs_update__politika_yok_uygulama_isi_ilerletemez (beklenmedik hata: %)', SQLERRM;
END
$$;

WITH removed AS (
    DELETE FROM ingestion_jobs WHERE id = 'eeeeeeee-0000-0000-0000-00000000000a' RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  jobs_delete__politika_yok_is_silinemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM removed;

-- ===========================================================================
-- chat_sessions_self_read / _self_insert / _self_update / _self_delete
-- ===========================================================================

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  chat_sessions_read__kendi_oturumunu_gorur (beklenen 1, gelen ' || count(*) || ')'
FROM chat_sessions;

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  chat_sessions_read__baska_ogrencinin_oturumu_gorunmez (beklenen 0, gelen '
       || count(*) || ')'
FROM chat_sessions WHERE user_id = '44444444-4444-4444-4444-444444444444';

-- Eğitmen bile öğrencinin sohbet oturumunu göremez: 0003'te yazılı gizlilik kararı.
SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  chat_sessions_read__egitmen_ogrenci_oturumunu_goremez (beklenen 0, gelen '
       || count(*) || ')'
FROM chat_sessions;

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
-- Üye olunmayan derste oturum açma: `user_id = current` tek başına yetseydi geçerdi
-- (0004 incelemesi, kalem 2). Üyelik kontrolü olmadan kullanıcı, üyesi olmadığı dersin
-- verisine satır enjekte edebilirdi.
DO $$
BEGIN
    INSERT INTO chat_sessions (course_id, user_id)
    VALUES ('bbbbbbbb-0000-0000-0000-000000000002',
            '22222222-2222-2222-2222-222222222222');
    RAISE NOTICE 'FAIL  chat_sessions_insert__uye_olunmayan_derste_oturum_acilamaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  chat_sessions_insert__uye_olunmayan_derste_oturum_acilamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  chat_sessions_insert__uye_olunmayan_derste_oturum_acilamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
BEGIN
    INSERT INTO chat_sessions (course_id, user_id)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            '44444444-4444-4444-4444-444444444444');
    RAISE NOTICE 'FAIL  chat_sessions_insert__baskasi_adina_oturum_acilamaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  chat_sessions_insert__baskasi_adina_oturum_acilamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  chat_sessions_insert__baskasi_adina_oturum_acilamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
BEGIN
    INSERT INTO chat_sessions (course_id, user_id)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            '22222222-2222-2222-2222-222222222222');
    RAISE NOTICE 'PASS  chat_sessions_insert__kendi_dersinde_oturum_acabilir';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'FAIL  chat_sessions_insert__kendi_dersinde_oturum_acabilir (reddedildi)';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  chat_sessions_insert__kendi_dersinde_oturum_acabilir (beklenmedik hata: %)', SQLERRM;
END
$$;

WITH changed AS (
    UPDATE chat_sessions SET title = 'Deadlock çalışması'
    WHERE id = '5a5a5a5a-0000-0000-0000-00000000000b' RETURNING 1
)
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  chat_sessions_update__kendi_oturumunu_guncelleyebilir (beklenen 1 satır, gelen '
       || count(*) || ')'
FROM changed;

WITH changed AS (
    UPDATE chat_sessions SET title = 'Ele geçirildi'
    WHERE id = '5a5a5a5a-0000-0000-0000-00000000000d' RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  chat_sessions_update__baskasinin_oturumunu_guncelleyemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM changed;

-- WITH CHECK'in kanıtı: yazılmasaydı PostgreSQL güncellenen satır için USING'i
-- kullanır ve oturumun BAŞKA BİR DERSE taşınmasını engellemezdi.
DO $$
BEGIN
    UPDATE chat_sessions SET course_id = 'bbbbbbbb-0000-0000-0000-000000000002'
    WHERE id = '5a5a5a5a-0000-0000-0000-00000000000b';
    RAISE NOTICE 'FAIL  chat_sessions_update__oturum_yabanci_derse_tasinamaz (update geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  chat_sessions_update__oturum_yabanci_derse_tasinamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  chat_sessions_update__oturum_yabanci_derse_tasinamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

WITH removed AS (
    DELETE FROM chat_sessions WHERE id = '5a5a5a5a-0000-0000-0000-00000000000d' RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  chat_sessions_delete__baskasinin_oturumu_silinemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM removed;

-- ===========================================================================
-- chat_messages_self_read / _self_insert  (+ UPDATE/DELETE politikası YOK)
-- ===========================================================================

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
SELECT CASE WHEN count(*) = 2 THEN 'PASS' ELSE 'FAIL' END
       || '  chat_messages_read__kendi_mesajlarini_gorur (beklenen 2, gelen ' || count(*) || ')'
FROM chat_messages;

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  chat_messages_read__baska_ogrencinin_mesaji_gorunmez (beklenen 0, gelen '
       || count(*) || ')'
FROM chat_messages WHERE session_id = '5a5a5a5a-0000-0000-0000-00000000000d';

-- Ürünün gerekçelerinden biri, öğrencinin hocasına sormaya çekindiği soruyu
-- sisteme sorabilmesi. Eğitmenin mesajları satır satır okuyabilmesi bunu bozar.
SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  chat_messages_read__egitmen_ogrenci_sohbetini_okuyamaz (beklenen 0, gelen '
       || count(*) || ')'
FROM chat_messages;

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
DO $$
BEGIN
    INSERT INTO chat_messages (session_id, course_id, role, content)
    VALUES ('5a5a5a5a-0000-0000-0000-00000000000d',
            'aaaaaaaa-0000-0000-0000-000000000001', 'user', 'Başkasının oturumuna');
    RAISE NOTICE 'FAIL  chat_messages_insert__baskasinin_oturumuna_yazilamaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  chat_messages_insert__baskasinin_oturumuna_yazilamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  chat_messages_insert__baskasinin_oturumuna_yazilamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

-- Üçlü kontrolün kanıtı: oturum bana ait ama satırın course_id'si başka dersin.
-- Eşleşme aranmasaydı kendi oturumuna sahte bir course_id iliştirip başka dersin
-- kayıtlarına satır enjekte etmek mümkün olurdu.
DO $$
BEGIN
    INSERT INTO chat_messages (session_id, course_id, role, content)
    VALUES ('5a5a5a5a-0000-0000-0000-00000000000b',
            'bbbbbbbb-0000-0000-0000-000000000002', 'user', 'Sahte ders kimliği');
    RAISE NOTICE 'FAIL  chat_messages_insert__sahte_course_id_ile_yazilamaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  chat_messages_insert__sahte_course_id_ile_yazilamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  chat_messages_insert__sahte_course_id_ile_yazilamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
BEGIN
    INSERT INTO chat_messages (session_id, course_id, role, content)
    VALUES ('5a5a5a5a-0000-0000-0000-00000000000b',
            'aaaaaaaa-0000-0000-0000-000000000001', 'user', 'Kendi oturumuma');
    RAISE NOTICE 'PASS  chat_messages_insert__kendi_oturumuna_yazabilir';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'FAIL  chat_messages_insert__kendi_oturumuna_yazabilir (reddedildi)';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  chat_messages_insert__kendi_oturumuna_yazabilir (beklenmedik hata: %)', SQLERRM;
END
$$;

-- Mesaj geçmişi denetlenebilir olmak zorunda: sonradan düzeltilebilen bir geçmiş,
-- "sistem gerçekten yönlendirdi mi" sorusuna kanıt olamaz (Anayasa III).
WITH changed AS (
    UPDATE chat_messages SET content = 'Sonradan düzeltildi'
    WHERE id = '6b6b6b6b-0000-0000-0000-00000000000b' RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  chat_messages_update__politika_yok_gecmis_degistirilemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM changed;

WITH removed AS (
    DELETE FROM chat_messages WHERE id = '6b6b6b6b-0000-0000-0000-00000000000b' RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  chat_messages_delete__politika_yok_gecmis_silinemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM removed;

-- ===========================================================================
-- chat_message_feedback: özel varsayılan + açık rızayla öğretmen incelemesi
-- ===========================================================================

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
DO $$
BEGIN
    INSERT INTO chat_message_feedback
        (id, course_id, message_id, user_id, rating, reason, comment,
         share_with_instructor)
    VALUES
        ('fbfbfbfb-0000-0000-0000-000000000001',
         'aaaaaaaa-0000-0000-0000-000000000001',
         '6b6b6b6b-0000-0000-0000-00000000001b',
         '22222222-2222-2222-2222-222222222222',
         'unhelpful', 'citation_problem', 'Kaynak bağlantısı açılmadı.', false);
    RAISE NOTICE 'PASS  feedback_insert__ogrenci_kendi_asistan_yanitini_puanlar';
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  feedback_insert__ogrenci_kendi_asistan_yanitini_puanlar (%)', SQLERRM;
END
$$;

SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  feedback_read__ogrenci_kendi_puanini_gorur (beklenen 1, gelen '
       || count(*) || ')'
FROM chat_message_feedback;

SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  feedback_read__egitmen_izinsiz_metni_goremez (beklenen 0, gelen '
       || count(*) || ')'
FROM chat_message_feedback;

-- Toplu sayı görünür, sohbet metni görünmez. Böylece insan değerlendirmesi için
-- sinyal oluşur fakat bütün konuşmaları öğretmene açan bir gözetim ekranı oluşmaz.
SELECT CASE WHEN rated_count = 1 AND unhelpful_count = 1 AND shared_review_count = 0
            THEN 'PASS' ELSE 'FAIL' END
       || '  feedback_summary__egitmen_ozel_puani_yalniz_toplu_gorur'
FROM app.chat_feedback_summary('aaaaaaaa-0000-0000-0000-000000000001');

SET LOCAL app.current_user_id = '33333333-3333-3333-3333-333333333333';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  feedback_read__baska_ogrenci_puani_goremez (beklenen 0, gelen '
       || count(*) || ')'
FROM chat_message_feedback
WHERE id = 'fbfbfbfb-0000-0000-0000-000000000001';

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
DO $$
BEGIN
    INSERT INTO chat_message_feedback
        (course_id, message_id, user_id, rating, reason)
    VALUES
        ('aaaaaaaa-0000-0000-0000-000000000001',
         '6b6b6b6b-0000-0000-0000-00000000000b',
         '22222222-2222-2222-2222-222222222222', 'helpful', 'helpful');
    RAISE NOTICE 'FAIL  feedback_insert__kullanici_mesaji_puanlanamaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  feedback_insert__kullanici_mesaji_puanlanamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  feedback_insert__kullanici_mesaji_puanlanamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

UPDATE chat_message_feedback
   SET share_with_instructor = true
 WHERE id = 'fbfbfbfb-0000-0000-0000-000000000001';

SELECT CASE WHEN question_excerpt = 'Deadlock nedir?'
                  AND answer_excerpt = 'Deadlock dört Coffman koşulunun birlikte oluşmasıdır.'
            THEN 'PASS' ELSE 'FAIL' END
       || '  feedback_share__alintilari_istemci_degil_tetikleyici_uretir'
FROM chat_message_feedback
WHERE id = 'fbfbfbfb-0000-0000-0000-000000000001';

SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  feedback_read__egitmen_acikca_paylasilan_kaydi_gorur (beklenen 1, gelen '
       || count(*) || ')'
FROM chat_message_feedback
WHERE share_with_instructor;

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
UPDATE chat_message_feedback
   SET share_with_instructor = false
 WHERE id = 'fbfbfbfb-0000-0000-0000-000000000001';

SELECT CASE WHEN question_excerpt IS NULL AND answer_excerpt IS NULL
            THEN 'PASS' ELSE 'FAIL' END
       || '  feedback_share__riza_cekilince_alintilar_silinir'
FROM chat_message_feedback
WHERE id = 'fbfbfbfb-0000-0000-0000-000000000001';

-- KVKK veri hakkı: kullanıcı kendi sohbet oturumunu silebilir. Bu kontrol mesaj
-- iddialarından sonra yapılır; ON DELETE CASCADE geçmişi de kaldırır.
WITH removed AS (
    DELETE FROM chat_sessions WHERE id = '5a5a5a5a-0000-0000-0000-00000000000b' RETURNING 1
)
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  chat_sessions_delete__kendi_oturumunu_silebilir (beklenen 1 satır, gelen '
       || count(*) || ')'
FROM removed;

-- ===========================================================================
-- answer_cache_member_read / _member_insert / _instructor_delete  (+ UPDATE YOK)
-- ===========================================================================

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  answer_cache_read__uye_kendi_dersinin_onbellegini_gorur (beklenen 1, gelen '
       || count(*) || ')'
FROM answer_cache;

-- Bir dersin önbelleği başka derse servis edilirse izolasyon tezinin tamamı çöker.
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  answer_cache_read__baska_dersin_onbellegi_gorunmez (beklenen 0, gelen '
       || count(*) || ')'
FROM answer_cache WHERE course_id = 'bbbbbbbb-0000-0000-0000-000000000002';

SET LOCAL app.current_user_id = '33333333-3333-3333-3333-333333333333';
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  answer_cache_read__kendi_dersinin_uyesi_gorur (beklenen 1, gelen '
       || count(*) || ')'
FROM answer_cache WHERE course_id = 'bbbbbbbb-0000-0000-0000-000000000002';

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
DO $$
BEGIN
    INSERT INTO answer_cache (course_id, question_hash, answer)
    VALUES ('bbbbbbbb-0000-0000-0000-000000000002', 'kacak-hash', '{"text": "kaçak"}');
    RAISE NOTICE 'FAIL  answer_cache_insert__baska_derse_yazilamaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  answer_cache_insert__baska_derse_yazilamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  answer_cache_insert__baska_derse_yazilamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

-- Kabul edilen artık risk (0003 yorumu): dersin üyesi kendi dersinin önbelleğine
-- yazabilir. Guardrail'den geçmiş cevabın girmesi UYGULAMA katmanının garantisidir.
DO $$
BEGIN
    INSERT INTO answer_cache (course_id, question_hash, answer)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001', 'yeni-hash', '{"text": "yeni"}');
    RAISE NOTICE 'PASS  answer_cache_insert__uye_kendi_dersine_yazabilir';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'FAIL  answer_cache_insert__uye_kendi_dersine_yazabilir (reddedildi)';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  answer_cache_insert__uye_kendi_dersine_yazabilir (beklenmedik hata: %)', SQLERRM;
END
$$;

WITH changed AS (
    UPDATE answer_cache SET answer = '{"text": "değiştirildi"}'
    WHERE id = '7c7c7c7c-0000-0000-0000-00000000000a' RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  answer_cache_update__politika_yok_onbellek_degistirilemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM changed;

WITH removed AS (
    DELETE FROM answer_cache WHERE id = '7c7c7c7c-0000-0000-0000-00000000000a' RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  answer_cache_delete__ogrenci_onbellek_temizleyemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM removed;

SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
WITH removed AS (
    DELETE FROM answer_cache WHERE id = '7c7c7c7c-0000-0000-0000-00000000000a' RETURNING 1
)
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  answer_cache_delete__egitmen_onbellek_temizleyebilir (beklenen 1 satır, gelen '
       || count(*) || ')'
FROM removed;

-- ===========================================================================
-- request_logs_self_insert  (+ SELECT/UPDATE/DELETE politikası YOK)
-- ===========================================================================
--
-- 0003 bu tabloyu istemciye tamamen kapalı bıraktı; 0005 yalnız EĞİTMENE, yalnız kendi
-- dersi için SELECT açtı (analitik ekranı). O politikanın iddiaları rls_assessment.sql'de
-- yaşıyor ve burada tekrarlanmıyor. Buradaki kapsam 0003'ün yazma politikası ve
-- politikası hiç olmayan işlemler.

SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  request_logs_read__ogrenci_hicbir_kaydi_goremez (beklenen 0, gelen '
       || count(*) || ')'
FROM request_logs;

DO $$
BEGIN
    INSERT INTO request_logs (course_id, user_id, route, mode, http_status, latency_ms)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            '44444444-4444-4444-4444-444444444444', '/x', 'qa', 200, 10);
    RAISE NOTICE 'FAIL  request_logs_insert__baskasi_adina_yazilamaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  request_logs_insert__baskasi_adina_yazilamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  request_logs_insert__baskasi_adina_yazilamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
BEGIN
    INSERT INTO request_logs (course_id, user_id, route, mode, http_status, latency_ms)
    VALUES ('bbbbbbbb-0000-0000-0000-000000000002',
            '22222222-2222-2222-2222-222222222222', '/x', 'qa', 200, 10);
    RAISE NOTICE 'FAIL  request_logs_insert__uye_olunmayan_derse_yazilamaz (insert geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  request_logs_insert__uye_olunmayan_derse_yazilamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  request_logs_insert__uye_olunmayan_derse_yazilamaz (beklenmedik hata: %)', SQLERRM;
END
$$;

DO $$
BEGIN
    INSERT INTO request_logs (course_id, user_id, route, mode, http_status, latency_ms)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            '22222222-2222-2222-2222-222222222222', '/x', 'qa', 200, 10);
    RAISE NOTICE 'PASS  request_logs_insert__kendi_adina_kendi_dersine_yazabilir';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE
            'FAIL  request_logs_insert__kendi_adina_kendi_dersine_yazabilir (reddedildi)';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  request_logs_insert__kendi_adina_kendi_dersine_yazabilir (beklenmedik hata: %)', SQLERRM;
END
$$;

-- SELECT politikasının yokluğunun DOĞRUDAN sonucu: RETURNING çalışmaz, çünkü RETURNING
-- eklenen satırı okumayı gerektirir. `app/api/chat.py` bu yüzden ORM'in `session.add()`
-- yolunu değil RETURNING üretmeyen Core INSERT'ünü kullanıyor.
--
-- ÖLÇÜLEN SINIR (9 Ağustos, bu şerit): 0003'ün "bu tabloya INSERT ... RETURNING
-- yapılamaz" cümlesi artık YALNIZ ÖĞRENCİ İÇİN doğru. 0005 eğitmene kendi dersi için
-- SELECT açtığından eğitmen bağlamında RETURNING geçiyor (psql ile doğrulandı).
-- Kod bundan etkilenmiyor — Core INSERT rolden bağımsız — ama iddia dar tutuluyor ki
-- test doğru olmayan bir şeyi kanıtlıyormuş gibi durmasın (Anayasa III).
DO $$
DECLARE v_id uuid;
BEGIN
    INSERT INTO request_logs (course_id, user_id, route, mode, http_status, latency_ms)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            '22222222-2222-2222-2222-222222222222', '/x', 'qa', 200, 10)
    RETURNING id INTO v_id;
    RAISE NOTICE 'FAIL  request_logs_insert__ogrenci_baglaminda_returning_calismaz '
                 '(RETURNING geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  request_logs_insert__ogrenci_baglaminda_returning_calismaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  request_logs_insert__ogrenci_baglaminda_returning_calismaz (beklenmedik hata: %)', SQLERRM;
END
$$;

WITH changed AS (
    UPDATE request_logs SET latency_ms = 1 RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  request_logs_update__politika_yok_olcum_degistirilemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM changed;

WITH removed AS (
    DELETE FROM request_logs RETURNING 1
)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  request_logs_delete__politika_yok_olcum_silinemez (beklenen 0 satır, gelen '
       || count(*) || ')'
FROM removed;

-- ===========================================================================
-- Meşru bootstrap yolu: app.create_course()
-- ===========================================================================
--
-- Doğrudan INSERT kapalı (yukarıda kanıtlandı) ama ders açılabiliyor olmalı. Bu iki
-- iddia birlikte anlamlıdır: biri olmadan diğeri ya "hiçbir şey çalışmıyor" ya da
-- "her şey açık" durumunu izolasyon sanır.

SET LOCAL app.current_user_id = '55555555-5555-5555-5555-555555555555';
SELECT CASE WHEN app.create_course('COME777', 'Emre''nin Dersi') IS NOT NULL
            THEN 'PASS' ELSE 'FAIL' END
       || '  create_course__mesru_yolla_ders_acilabilir';

-- Ders açan kişi o dersin eğitmeni olur; aksi hâlde açtığı dersi göremezdi.
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  create_course__acan_kisi_egitmen_olur (beklenen 1, gelen ' || count(*) || ')'
FROM course_memberships
WHERE user_id = '55555555-5555-5555-5555-555555555555' AND role = 'instructor';

-- ===========================================================================
-- Oturum bağlamı yoksa hiçbir şey görünmez (Anayasa IV — fail-closed)
-- ===========================================================================
--
-- `app.current_user_id()` boş GUC'de NULL döner ve tüm politikalar kapanır. Bu, bir
-- kod yolunun `SET LOCAL app.current_user_id` yapmayı unutması hâlinde verinin
-- sızmayacağının güvencesidir.

SET LOCAL app.current_user_id = '';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  baglamsiz__chunks_gorunmez (beklenen 0, gelen ' || count(*) || ')' FROM chunks;
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  baglamsiz__courses_gorunmez (beklenen 0, gelen ' || count(*) || ')' FROM courses;
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  baglamsiz__documents_gorunmez (beklenen 0, gelen ' || count(*) || ')' FROM documents;
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  baglamsiz__profiles_gorunmez (beklenen 0, gelen ' || count(*) || ')' FROM profiles;
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  baglamsiz__memberships_gorunmez (beklenen 0, gelen ' || count(*) || ')'
FROM course_memberships;
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  baglamsiz__chat_sessions_gorunmez (beklenen 0, gelen ' || count(*) || ')'
FROM chat_sessions;
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  baglamsiz__chat_messages_gorunmez (beklenen 0, gelen ' || count(*) || ')'
FROM chat_messages;
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  baglamsiz__chat_feedback_gorunmez (beklenen 0, gelen ' || count(*) || ')'
FROM chat_message_feedback;
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  baglamsiz__answer_cache_gorunmez (beklenen 0, gelen ' || count(*) || ')'
FROM answer_cache;

ROLLBACK;
