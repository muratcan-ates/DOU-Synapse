-- RLS izolasyon kanıtı (ARCHITECTURE.md §6, PLAN.md G13).
--
-- Bu betik "politika var" demez; politikaların GERÇEKTEN tetiklendiğini gösterir.
-- Beklenen çıktı: her satırda PASS. Politikalar bozulursa (ör. USING (true) yapılırsa)
-- ilgili satır FAIL'e döner — testin kırmızı yanabildiğini kanıtlayan senaryo budur.
--
-- Çalıştırma:  psql -d dou_synapse -f supabase/tests/rls_isolation.sql

\set ON_ERROR_STOP on
\pset format unaligned
\pset tuples_only on

BEGIN;

-- --- Kurulum: sahip/superuser olarak seed (RLS'i atlar) --------------------
INSERT INTO profiles (id, email, full_name) VALUES
    ('11111111-1111-1111-1111-111111111111', 'ayse@dogus.edu.tr',  'Ayşe Eğitmen'),
    ('22222222-2222-2222-2222-222222222222', 'burak@dogus.edu.tr', 'Burak Öğrenci'),
    ('33333333-3333-3333-3333-333333333333', 'ceren@dogus.edu.tr', 'Ceren Öğrenci');

INSERT INTO courses (id, code, title, created_by) VALUES
    ('aaaaaaaa-0000-0000-0000-000000000001', 'COME301', 'İşletim Sistemleri',
     '11111111-1111-1111-1111-111111111111'),
    ('bbbbbbbb-0000-0000-0000-000000000002', 'COME302', 'Veri Yapıları',
     '11111111-1111-1111-1111-111111111111');

INSERT INTO course_memberships (course_id, user_id, role) VALUES
    ('aaaaaaaa-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 'instructor'),
    ('aaaaaaaa-0000-0000-0000-000000000001', '22222222-2222-2222-2222-222222222222', 'student'),
    ('bbbbbbbb-0000-0000-0000-000000000002', '33333333-3333-3333-3333-333333333333', 'student');

INSERT INTO documents (id, course_id, uploaded_by, file_name, file_type,
                       storage_path, file_hash, byte_size, status) VALUES
    ('dddddddd-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001',
     '11111111-1111-1111-1111-111111111111', 'os_hafta3.pdf', 'pdf',
     'courses/a/os_hafta3.pdf', 'hash-a', 1024, 'completed'),
    ('dddddddd-0000-0000-0000-000000000002', 'bbbbbbbb-0000-0000-0000-000000000002',
     '11111111-1111-1111-1111-111111111111', 'ds_hafta1.pdf', 'pdf',
     'courses/b/ds_hafta1.pdf', 'hash-b', 2048, 'completed');

INSERT INTO chunks (course_id, document_id, chunk_index, page_number, text, token_count) VALUES
    ('aaaaaaaa-0000-0000-0000-000000000001', 'dddddddd-0000-0000-0000-000000000001',
     0, 12, 'Deadlock için dört Coffman koşulu birlikte sağlanmalıdır.', 42),
    ('bbbbbbbb-0000-0000-0000-000000000002', 'dddddddd-0000-0000-0000-000000000002',
     0, 5,  'Stack LIFO, queue FIFO prensibiyle çalışır.', 31);

-- --- Testler: uygulama rolüyle ---------------------------------------------
SET LOCAL ROLE dou_app;

-- 1) Burak (COME301 öğrencisi) yalnızca kendi dersinin chunk'ını görür.
SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  ogrenci_kendi_dersinin_chunklarini_gorur (beklenen 1, gelen ' || count(*) || ')'
FROM chunks;

-- 2) Burak, başka dersin chunk'ını açıkça sorgulasa bile göremez.
--    (Uygulama katmanı delinip course_id istemciden gelseydi olacak senaryo.)
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  baska_dersin_chunki_gorunmez (beklenen 0, gelen ' || count(*) || ')'
FROM chunks WHERE course_id = 'bbbbbbbb-0000-0000-0000-000000000002';

-- 3) Aynı sorgu, o dersin gerçek öğrencisi için sonuç döndürür — yani filtre
--    "her şeyi gizle" değil, gerçekten kullanıcıya göre çalışıyor.
SET LOCAL app.current_user_id = '33333333-3333-3333-3333-333333333333';
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  ceren_kendi_dersini_gorur (beklenen 1, gelen ' || count(*) || ')'
FROM chunks WHERE course_id = 'bbbbbbbb-0000-0000-0000-000000000002';

-- 4) Belgeler de aynı şekilde izole.
SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  belgeler_izole (beklenen 1, gelen ' || count(*) || ')'
FROM documents;

-- 5) Oturum bağlamı hiç ayarlanmamışsa hiçbir satır görünmez (fail-closed).
SET LOCAL app.current_user_id = '';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
       || '  baglamsiz_istek_hicbir_sey_gormez (beklenen 0, gelen ' || count(*) || ')'
FROM chunks;

-- 6) Öğrenci belge yükleyemez (yalnızca eğitmen).
SET LOCAL app.current_user_id = '22222222-2222-2222-2222-222222222222';
DO $$
BEGIN
    INSERT INTO documents (course_id, uploaded_by, file_name, file_type,
                           storage_path, file_hash, byte_size)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            '22222222-2222-2222-2222-222222222222', 'sahte.pdf', 'pdf',
            'x', 'hash-x', 10);
    RAISE NOTICE 'FAIL  ogrenci_belge_yukleyemez (insert beklenmedik şekilde geçti)';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  ogrenci_belge_yukleyemez';
END
$$;

-- 7) Eğitmen kendi dersine belge yükleyebilir.
SET LOCAL app.current_user_id = '11111111-1111-1111-1111-111111111111';
DO $$
BEGIN
    INSERT INTO documents (course_id, uploaded_by, file_name, file_type,
                           storage_path, file_hash, byte_size)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001',
            '11111111-1111-1111-1111-111111111111', 'yeni.pdf', 'pdf',
            'y', 'hash-y', 10);
    RAISE NOTICE 'PASS  egitmen_belge_yukleyebilir';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'FAIL  egitmen_belge_yukleyebilir (insert reddedildi)';
END
$$;

-- 8) Eğitmen kendi dersinin iki chunk'ından yalnızca birini görür (diğer ders kapalı).
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
       || '  egitmen_yalnizca_uye_oldugu_dersi_gorur (beklenen 1, gelen ' || count(*) || ')'
FROM chunks;

ROLLBACK;
