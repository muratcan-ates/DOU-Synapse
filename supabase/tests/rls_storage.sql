\set ON_ERROR_STOP on
\if :{?storage_mutation}
\else
\set storage_mutation none
\endif
BEGIN;
-- Gerçek çekirdek göçleri önceden uygulanır; yalnız Supabase şeması sentetiktir.
DO $$
BEGIN
    IF current_database() !~ '^dou_l5[a-z0-9_]*$'
        OR (inet_server_addr() IS NOT NULL AND inet_server_addr() NOT IN ('127.0.0.1'::inet, '::1'::inet))
    THEN RAISE EXCEPTION 'L5 yalnız ayrı yerel test veritabanında çalışır.'; END IF;
    IF to_regnamespace('storage') IS NOT NULL THEN
        RAISE EXCEPTION 'Var olan storage şemasında test çalıştırılmaz.';
    END IF;
    IF to_regclass('public.course_memberships') IS NULL
        OR to_regclass('public.documents') IS NULL OR to_regclass('public.exam_sessions') IS NULL
    THEN RAISE EXCEPTION 'Gerçek çekirdek göçleri önce uygulanmalıdır.'; END IF;
    IF EXISTS (SELECT 1 FROM pg_class WHERE oid IN ('public.course_memberships'::regclass,
        'public.documents'::regclass, 'public.exam_sessions'::regclass) AND NOT relforcerowsecurity)
    THEN RAISE EXCEPTION 'Çekirdek tablolar FORCE RLS kullanmalıdır.'; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN NOSUPERUSER NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN NOSUPERUSER NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        CREATE ROLE service_role NOLOGIN NOSUPERUSER BYPASSRLS;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('authenticated', 'anon')
        AND (rolsuper OR rolbypassrls))
        OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role' AND rolbypassrls)
    THEN RAISE EXCEPTION 'Supabase test rollerinin RLS bayrakları uygun değil.'; END IF;
END $$;

CREATE SCHEMA storage;
CREATE TABLE storage.buckets (id text PRIMARY KEY, name text NOT NULL, public boolean NOT NULL DEFAULT false);
CREATE TABLE storage.objects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), bucket_id text NOT NULL REFERENCES storage.buckets(id),
    name text NOT NULL, owner_id text, metadata jsonb, UNIQUE (bucket_id, name)
);
GRANT USAGE ON SCHEMA storage TO authenticated, anon, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON storage.objects TO authenticated, anon, service_role;
-- Önceden kalmış geniş permissive kural, restrictive sınırların gerçek nedenidir.
CREATE POLICY synthetic_existing_wide ON storage.objects FOR ALL TO PUBLIC USING (true) WITH CHECK (true);
-- Hosted postgres benzeri çekirdek PG16 rolü: SUPERUSER olmadan CREATEROLE+BYPASSRLS.
-- Bu profil Supabase hizmetinin canlı kurulumunu taklit ettiği iddiası değildir.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dou_l5_storage_installer') THEN
        RAISE EXCEPTION 'L5 kurucu fikstür rolü zaten var; paylaşılan rol değiştirilmez.';
    END IF;
    CREATE ROLE dou_l5_storage_installer NOLOGIN NOSUPERUSER CREATEROLE BYPASSRLS;
    EXECUTE format('GRANT CREATE ON DATABASE %I TO dou_l5_storage_installer', current_database());
END $$;
GRANT USAGE ON SCHEMA public TO dou_l5_storage_installer WITH GRANT OPTION;
GRANT SELECT (course_id, user_id, role, status) ON public.course_memberships
    TO dou_l5_storage_installer WITH GRANT OPTION;
GRANT SELECT (course_id, storage_path, uploaded_by) ON public.documents
    TO dou_l5_storage_installer WITH GRANT OPTION;
GRANT SELECT (course_id, user_id, mode, finished_at, expires_at) ON public.exam_sessions
    TO dou_l5_storage_installer WITH GRANT OPTION;
GRANT USAGE, CREATE ON SCHEMA storage TO dou_l5_storage_installer;
ALTER TABLE storage.objects OWNER TO dou_l5_storage_installer;
ALTER TABLE storage.buckets OWNER TO dou_l5_storage_installer;
SET LOCAL ROLE dou_l5_storage_installer;
\ir ../migrations/0029_private_storage.sql
-- Aynı kurucuyla tekrar uygulama da sahiplik/geçici yetki akışını sınar.
\ir ../migrations/0029_private_storage.sql
RESET ROLE;

SELECT set_config('l5.storage_mutation', :'storage_mutation', true);
DO $$
DECLARE selected text := current_setting('l5.storage_mutation');
BEGIN
    CASE selected
        WHEN 'none' THEN NULL;
        WHEN 'read' THEN ALTER POLICY dou_storage_read_boundary ON storage.objects USING (true);
        WHEN 'insert' THEN ALTER POLICY dou_storage_insert_boundary ON storage.objects WITH CHECK (true);
        WHEN 'delete' THEN ALTER POLICY dou_storage_delete_boundary ON storage.objects USING (true);
        WHEN 'update' THEN ALTER POLICY dou_storage_update_boundary ON storage.objects USING (true) WITH CHECK (true);
        ELSE RAISE EXCEPTION 'Bilinmeyen Storage mutasyonu';
    END CASE;
END $$;

CREATE FUNCTION pg_temp.l5_assert(label text, passed boolean) RETURNS void LANGUAGE plpgsql AS $$
BEGIN IF passed IS DISTINCT FROM true THEN RAISE EXCEPTION 'L5_ASSERT:%', label; END IF; END $$;
CREATE FUNCTION pg_temp.l5_denied(label text, statement text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    BEGIN EXECUTE statement;
    EXCEPTION WHEN insufficient_privilege THEN RETURN;
    END;
    RAISE EXCEPTION 'L5_ASSERT:%', label;
END $$;

INSERT INTO public.profiles (id, email)
SELECT ('10000000-0000-0000-0000-' || lpad(n::text, 12, '0'))::uuid,
    'l5-storage-' || n || '@example.invalid' FROM generate_series(1, 8) n;
INSERT INTO public.courses (id, code, title, created_by) VALUES
    ('a0000000-0000-0000-0000-000000000001', 'L5-STORAGE-A', 'L5 A', '10000000-0000-0000-0000-000000000001'),
    ('b0000000-0000-0000-0000-000000000001', 'L5-STORAGE-B', 'L5 B', '10000000-0000-0000-0000-000000000004');
INSERT INTO public.course_memberships (course_id, user_id, role, status)
SELECT 'a0000000-0000-0000-0000-000000000001'::uuid,
    ('10000000-0000-0000-0000-' || lpad(n::text, 12, '0'))::uuid,
    (CASE WHEN n = 1 THEN 'instructor' ELSE 'student' END)::public.membership_role,
    (CASE WHEN n = 6 THEN 'revoked' ELSE 'active' END)::public.membership_status
FROM unnest(ARRAY[1,2,3,4,6,8]) n;
INSERT INTO public.course_memberships (course_id, user_id, role) VALUES
    ('b0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000004', 'instructor');
INSERT INTO public.platform_admins (user_id) VALUES ('10000000-0000-0000-0000-000000000007');
INSERT INTO storage.buckets (id, name, public) VALUES ('l5-foreign', 'l5-foreign', true);
INSERT INTO storage.objects (bucket_id, name, owner_id)
SELECT 'course-materials', 'courses/a0000000-0000-0000-0000-000000000001/' || lpad(n::text, 32, '0') || '.md',
    CASE n WHEN 1 THEN '10000000-0000-0000-0000-000000000002'
        WHEN 2 THEN '10000000-0000-0000-0000-000000000001' WHEN 4 THEN '' ELSE NULL END
FROM generate_series(1, 6) n;
INSERT INTO storage.objects (bucket_id, name, owner_id) VALUES
    ('course-materials', 'courses/b0000000-0000-0000-0000-000000000001/00000000000000000000000000000001.md', '10000000-0000-0000-0000-000000000004'),
    ('course-materials', 'courses/a0000000-0000-0000-0000-000000000001/../secret.md', '10000000-0000-0000-0000-000000000002'),
    ('l5-foreign', 'unmanaged.md', NULL);
INSERT INTO public.documents (course_id, uploaded_by, file_name, file_type, storage_path, file_hash, byte_size) VALUES
    ('a0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000002', 'owned.md', '.md',
        'courses/a0000000-0000-0000-0000-000000000001/00000000000000000000000000000003.md', 'l5-owned', 1),
    ('b0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000002', 'foreign-course.md', '.md',
        'courses/a0000000-0000-0000-0000-000000000001/00000000000000000000000000000004.md', 'l5-foreign-course', 1),
    ('a0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000003', 'other-owner.md', '.md',
        'courses/a0000000-0000-0000-0000-000000000001/00000000000000000000000000000005.md', 'l5-other-owner', 1),
    ('a0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000002', 'other-path.md', '.md',
        'courses/a0000000-0000-0000-0000-000000000001/ffffffffffffffffffffffffffffffff.md', 'l5-other-path', 1);

-- Önce tek-politika mutasyonlarının açık, davranışsal oracle'ları.
SET LOCAL ROLE authenticated;
SELECT pg_temp.l5_assert('actual_authenticated_role', current_user = 'authenticated');
SELECT pg_temp.l5_assert('app_schema_not_exposed', NOT has_schema_privilege('app', 'USAGE'));
SELECT set_config('app.current_user_id', '10000000-0000-0000-0000-000000000001', true);
SELECT pg_temp.l5_denied('existing_app_create_course_not_exposed',
    $statement$SELECT app.create_course('L5-FORGED-COURSE', 'İzin verilmemeli')$statement$);
SELECT pg_temp.l5_denied('existing_app_add_member_not_exposed',
    $statement$SELECT app.add_course_member('a0000000-0000-0000-0000-000000000001',
    'l5-storage-5@example.invalid', 'instructor')$statement$);
SELECT pg_temp.l5_assert('authenticated_no_private_schema_create', NOT has_schema_privilege('storage_private', 'CREATE'));
SELECT set_config('request.jwt.claims', '{"sub":"10000000-0000-0000-0000-000000000005","role":"authenticated"}', true);
SELECT pg_temp.l5_assert('read_nonmember', (SELECT count(*) = 0 FROM storage.objects WHERE bucket_id = 'course-materials'));
SELECT set_config('request.jwt.claims', '{"sub":"10000000-0000-0000-0000-000000000003","role":"authenticated"}', true);
SELECT pg_temp.l5_denied('insert_student', $statement$INSERT INTO storage.objects (bucket_id, name, owner_id) VALUES
    ('course-materials', 'courses/a0000000-0000-0000-0000-000000000001/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.md',
    '10000000-0000-0000-0000-000000000003')$statement$);
WITH removed AS (DELETE FROM storage.objects WHERE name = 'courses/a0000000-0000-0000-0000-000000000001/00000000000000000000000000000001.md' RETURNING id)
SELECT pg_temp.l5_assert('delete_nonowner', (SELECT count(*) = 0 FROM removed));
WITH changed AS (UPDATE storage.objects SET metadata = '{"mutated":true}' WHERE name = 'courses/a0000000-0000-0000-0000-000000000001/00000000000000000000000000000001.md' RETURNING id)
SELECT pg_temp.l5_assert('update_student', (SELECT count(*) = 0 FROM changed));
SELECT pg_temp.l5_assert('student_list', (SELECT count(*) = 6 FROM storage.objects WHERE bucket_id = 'course-materials'));
SELECT pg_temp.l5_assert('student_download_foreign_denied', (SELECT count(*) = 0 FROM storage.objects WHERE name LIKE 'courses/b%'));
SELECT pg_temp.l5_assert('foreign_bucket_unchanged', (SELECT count(*) = 1 FROM storage.objects WHERE bucket_id = 'l5-foreign'));
SELECT pg_temp.l5_assert('malformed_path_denied', (SELECT count(*) = 0 FROM storage.objects WHERE name LIKE '%/../%'));

-- Üyelik yok, iptal edilmiş ve bağımsız platform yönetimi ders erişimi vermez.
DO $$
DECLARE actor text; removed_count bigint;
BEGIN
    FOREACH actor IN ARRAY ARRAY['10000000-0000-0000-0000-000000000005',
        '10000000-0000-0000-0000-000000000006', '10000000-0000-0000-0000-000000000007']
    LOOP
        PERFORM set_config('request.jwt.claims', json_build_object('sub', actor, 'role', 'authenticated')::text, true);
        PERFORM pg_temp.l5_assert('nonmember_revoked_admin_read', (SELECT count(*) = 0 FROM storage.objects WHERE bucket_id = 'course-materials'));
        DELETE FROM storage.objects WHERE bucket_id = 'course-materials';
        GET DIAGNOSTICS removed_count = ROW_COUNT;
        PERFORM pg_temp.l5_assert('nonmember_revoked_admin_delete', removed_count = 0);
    END LOOP;
END $$;

-- Eksik veya bozuk JWT varsa uygulama GUC'si kimlik kaynağına dönüşmez.
SELECT set_config('app.current_user_id', '10000000-0000-0000-0000-000000000001', true);
SELECT set_config('request.jwt.claim.sub', '', true);
SELECT set_config('request.jwt.claim.role', '', true);
DO $$
DECLARE claims text;
BEGIN
    FOREACH claims IN ARRAY ARRAY['', 'invalid-json', '[]', 'null', '{}',
        '{"sub":"broken","role":"authenticated"}',
        '{"sub":"10000000-0000-0000-0000-000000000001"}',
        '{"sub":"10000000-0000-0000-0000-000000000001","role":"service_role"}']
    LOOP
        PERFORM set_config('request.jwt.claims', claims, true);
        PERFORM pg_temp.l5_assert('invalid_claims_closed', (SELECT count(*) = 0 FROM storage.objects WHERE bucket_id = 'course-materials'));
    END LOOP;
END $$;
SELECT set_config('request.jwt.claims', '', true);
SELECT set_config('request.jwt.claim.sub', '10000000-0000-0000-0000-000000000003', true);
SELECT set_config('request.jwt.claim.role', 'authenticated', true);
SELECT pg_temp.l5_assert('legacy_jwt_claims', (SELECT count(*) = 6 FROM storage.objects WHERE bucket_id = 'course-materials'));
SELECT set_config('request.jwt.claims', '{"sub":"broken","role":"authenticated"}', true);
SELECT pg_temp.l5_assert('malformed_primary_no_legacy_fallback', (SELECT count(*) = 0 FROM storage.objects WHERE bucket_id = 'course-materials'));

-- Karma rol yalnız ilgili derste eğitmenlik verir.
SELECT set_config('request.jwt.claims', '{"sub":"10000000-0000-0000-0000-000000000004","role":"authenticated"}', true);
SELECT pg_temp.l5_assert('mixed_course_read', (SELECT count(*) = 7 FROM storage.objects WHERE bucket_id = 'course-materials'));
SELECT pg_temp.l5_denied('mixed_student_insert_denied', $statement$INSERT INTO storage.objects (bucket_id, name, owner_id) VALUES
    ('course-materials', 'courses/a0000000-0000-0000-0000-000000000001/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.md', '10000000-0000-0000-0000-000000000004')$statement$);
INSERT INTO storage.objects (bucket_id, name, owner_id) VALUES
    ('course-materials', 'courses/b0000000-0000-0000-0000-000000000001/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.md', '10000000-0000-0000-0000-000000000004');
WITH removed AS (DELETE FROM storage.objects WHERE name LIKE 'courses/b%/bbbb%' RETURNING id)
SELECT pg_temp.l5_assert('mixed_instructor_delete', (SELECT count(*) = 1 FROM removed));

-- Sınavın süre ve bitiş sınırları gerçek exam_sessions tablosundan okunur.
RESET ROLE;
INSERT INTO public.exam_sessions (id, course_id, user_id, mode, expires_at, question_ids) VALUES
    ('e0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001',
        '10000000-0000-0000-0000-000000000008', 'exam', now() + interval '1 hour', '{}'),
    ('e0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001',
        '10000000-0000-0000-0000-000000000001', 'exam', now() + interval '1 hour', '{}');
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', '{"sub":"10000000-0000-0000-0000-000000000008","role":"authenticated"}', true);
SELECT pg_temp.l5_assert('active_exam_read_denied', (SELECT count(*) = 0 FROM storage.objects WHERE bucket_id = 'course-materials'));
RESET ROLE;
UPDATE public.exam_sessions SET expires_at = now() - interval '1 second' WHERE id = 'e0000000-0000-0000-0000-000000000001';
SET LOCAL ROLE authenticated;
SELECT pg_temp.l5_assert('expired_exam_read_allowed', (SELECT count(*) = 6 FROM storage.objects WHERE bucket_id = 'course-materials'));
RESET ROLE;
UPDATE public.exam_sessions SET expires_at = now() + interval '1 hour', finished_at = now() WHERE id = 'e0000000-0000-0000-0000-000000000001';
SET LOCAL ROLE authenticated;
SELECT pg_temp.l5_assert('finished_exam_read_allowed', (SELECT count(*) = 6 FROM storage.objects WHERE bucket_id = 'course-materials'));
SELECT set_config('request.jwt.claims', '{"sub":"10000000-0000-0000-0000-000000000001","role":"authenticated"}', true);
SELECT pg_temp.l5_assert('instructor_exam_exemption', (SELECT count(*) = 6 FROM storage.objects WHERE bucket_id = 'course-materials'));
SELECT pg_temp.l5_denied('instructor_spoofed_owner_denied', $statement$INSERT INTO storage.objects (bucket_id, name, owner_id) VALUES
    ('course-materials', 'courses/a0000000-0000-0000-0000-000000000001/cccccccccccccccccccccccccccccccc.md', '10000000-0000-0000-0000-000000000003')$statement$);
INSERT INTO storage.objects (bucket_id, name, owner_id) VALUES
    ('course-materials', 'courses/a0000000-0000-0000-0000-000000000001/cccccccccccccccccccccccccccccccc.md', '10000000-0000-0000-0000-000000000001');
WITH removed AS (DELETE FROM storage.objects WHERE name LIKE '%/cccc%' RETURNING id)
SELECT pg_temp.l5_assert('instructor_insert_delete', (SELECT count(*) = 1 FROM removed));
WITH changed AS (UPDATE storage.objects SET name = 'courses/b0000000-0000-0000-0000-000000000001/dddddddddddddddddddddddddddddddd.md'
    WHERE name = 'courses/a0000000-0000-0000-0000-000000000001/00000000000000000000000000000002.md' RETURNING id)
SELECT pg_temp.l5_assert('instructor_move_denied', (SELECT count(*) = 0 FROM changed));

-- owner_id boş servis yüklemesinde yalnız tam belge/ders/yükleyen eşleşmesi yeterlidir.
SELECT set_config('request.jwt.claims', '{"sub":"10000000-0000-0000-0000-000000000002","role":"authenticated"}', true);
WITH removed AS (DELETE FROM storage.objects WHERE name IN (
    'courses/a0000000-0000-0000-0000-000000000001/00000000000000000000000000000004.md',
    'courses/a0000000-0000-0000-0000-000000000001/00000000000000000000000000000005.md',
    'courses/a0000000-0000-0000-0000-000000000001/00000000000000000000000000000006.md') RETURNING id)
SELECT pg_temp.l5_assert('service_owner_fallback_exact', (SELECT count(*) = 0 FROM removed));
WITH removed AS (DELETE FROM storage.objects WHERE name = 'courses/a0000000-0000-0000-0000-000000000001/00000000000000000000000000000003.md' RETURNING id)
SELECT pg_temp.l5_assert('service_owner_fallback_allowed', (SELECT count(*) = 1 FROM removed));
WITH removed AS (DELETE FROM storage.objects WHERE name = 'courses/a0000000-0000-0000-0000-000000000001/00000000000000000000000000000001.md' RETURNING id)
SELECT pg_temp.l5_assert('direct_owner_delete', (SELECT count(*) = 1 FROM removed));
SELECT set_config('request.jwt.claims', '{"sub":"10000000-0000-0000-0000-000000000001","role":"authenticated"}', true);
WITH removed AS (DELETE FROM storage.objects WHERE name = 'courses/a0000000-0000-0000-0000-000000000001/00000000000000000000000000000005.md' RETURNING id)
SELECT pg_temp.l5_assert('instructor_nonowner_delete', (SELECT count(*) = 1 FROM removed));

-- Anon, gerçek authenticated claim'i taklit etse de hedef bucket'a erişemez.
RESET ROLE;
SET LOCAL ROLE anon;
SELECT pg_temp.l5_assert('anonymous_read_denied', (SELECT count(*) = 0 FROM storage.objects WHERE bucket_id = 'course-materials'));
SELECT pg_temp.l5_assert('anonymous_foreign_bucket_unchanged', (SELECT count(*) = 1 FROM storage.objects WHERE bucket_id = 'l5-foreign'));
SELECT pg_temp.l5_denied('anonymous_helper_denied', $statement$SELECT storage_private.storage_can_access('courses/a0000000-0000-0000-0000-000000000001/00000000000000000000000000000002.md', 'read', NULL)$statement$);
RESET ROLE;
SET LOCAL ROLE service_role;
SELECT set_config('request.jwt.claims', '', true);
SELECT pg_temp.l5_assert('service_role_bypasses_rls', (SELECT count(*) > 0 FROM storage.objects WHERE bucket_id = 'course-materials' AND name LIKE 'courses/b%'));
RESET ROLE;
SELECT pg_temp.l5_assert('installer_not_superuser', (SELECT NOT rolsuper AND rolcreaterole AND rolbypassrls FROM pg_roles WHERE rolname = 'dou_l5_storage_installer'));
SELECT pg_temp.l5_assert('installer_admin_only', EXISTS (SELECT 1 FROM pg_auth_members
    WHERE roleid = 'dou_storage_guard'::regrole AND member = 'dou_l5_storage_installer'::regrole AND admin_option)
    AND NOT EXISTS (SELECT 1 FROM pg_auth_members WHERE roleid = 'dou_storage_guard'::regrole
        AND (inherit_option OR set_option OR member <> 'dou_l5_storage_installer'::regrole)));
SELECT pg_temp.l5_assert('guard_schema_create_revoked', NOT has_schema_privilege('dou_storage_guard', 'storage_private', 'CREATE'));
SELECT pg_temp.l5_assert('helper_narrow_owner', (SELECT count(*) = 3 FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid
    WHERE n.nspname = 'storage_private' AND p.proowner = 'dou_storage_guard'::regrole));
SELECT pg_temp.l5_assert('private_bucket', (SELECT public = false FROM storage.buckets WHERE id = 'course-materials'));
SELECT pg_temp.l5_assert('guard_no_exam_content', NOT has_column_privilege('dou_storage_guard', 'public.exam_sessions', 'question_ids', 'SELECT'));
SELECT pg_temp.l5_assert('guard_no_document_content', NOT has_column_privilege('dou_storage_guard', 'public.documents', 'file_name', 'SELECT'));
ROLLBACK;
\echo L5_STORAGE_BASELINE_PASS
