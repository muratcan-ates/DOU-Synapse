-- L5: Supabase'ın yönettiği şema varsa yalnız course-materials bucket'ını kapatır.
-- Tek DO atomiktir; çağıranın BEGIN/ROLLBACK sınırını bozacak COMMIT içermez.
DO $migration$
DECLARE
    migration_actor name := current_user;
    migration_actor_id oid := current_user::regrole;
    migration_superuser boolean;
    original_self_grant text;
    role_name text;
BEGIN
    IF to_regclass('storage.objects') IS NULL THEN
        RAISE NOTICE 'Storage şeması yok; private Storage kurulumu uygulanmadı.';
        RETURN;
    END IF;
    IF to_regclass('storage.buckets') IS NULL
        OR to_regclass('public.course_memberships') IS NULL
        OR to_regclass('public.documents') IS NULL
        OR to_regclass('public.exam_sessions') IS NULL
        OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated')
    THEN
        RAISE EXCEPTION 'Private Storage ön koşulları eksik.';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'storage' AND table_name = 'objects'
            AND column_name = 'owner_id' AND data_type = 'text'
    ) THEN
        RAISE EXCEPTION 'Private Storage modern owner_id text sütunu gerektirir.';
    END IF;

    IF current_setting('server_version_num')::integer < 160000 THEN
        RAISE EXCEPTION 'Private Storage PG16 veya sonraki rol yetki modelini gerektirir.';
    END IF;
    SELECT rolsuper INTO migration_superuser FROM pg_roles WHERE oid = migration_actor_id;
    IF migration_actor IN ('authenticated', 'anon', 'service_role', 'dou_app', 'dou_worker')
        OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE oid = migration_actor_id
            AND (rolsuper OR (rolcreaterole AND rolbypassrls)))
    THEN RAISE EXCEPTION 'Private Storage kurucusu CREATEROLE ve BYPASSRLS gerektirir.'; END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dou_storage_guard') THEN
        -- PG16 yaratıcısına ADMIN verir. SET/INHERIT yalnız aşağıdaki geçici
        -- üyelikten gelir; oturumun önceden seçtiği varsayılan buna karışmaz.
        original_self_grant := current_setting('createrole_self_grant');
        PERFORM set_config('createrole_self_grant', '', true);
        CREATE ROLE dou_storage_guard NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOINHERIT NOREPLICATION BYPASSRLS;
        PERFORM set_config('createrole_self_grant', original_self_grant, true);
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'dou_storage_guard'
            AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication
                OR NOT rolbypassrls)
    ) OR EXISTS (
        SELECT 1 FROM pg_auth_members
        WHERE member = 'dou_storage_guard'::regrole
            OR (roleid = 'dou_storage_guard'::regrole AND NOT (
                member = migration_actor_id AND admin_option
                AND NOT inherit_option AND NOT set_option
            ))
    ) THEN
        RAISE EXCEPTION 'Private Storage yardımcı rolünün yetkileri beklenenden geniş.';
    END IF;

    FOREACH role_name IN ARRAY ARRAY['authenticated', 'anon', 'service_role', 'dou_app', 'dou_worker']
    LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            IF pg_has_role(role_name, 'dou_storage_guard', 'MEMBER') THEN
                RAISE EXCEPTION 'İstemci veya uygulama rolü Storage yardımcı rolüne üye olamaz.';
            END IF;
        END IF;
    END LOOP;

    IF to_regnamespace('storage_private') IS NULL THEN
        CREATE SCHEMA storage_private;
    ELSIF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'storage_private'
        AND nspowner <> migration_actor_id) THEN
        RAISE EXCEPTION 'Private Storage yardımcı şemasının sahibi kurucu olmalı.';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'storage_private' AND (
            p.proname NOT IN ('storage_user_id', 'storage_object_course', 'storage_can_access')
            OR p.proowner <> 'dou_storage_guard'::regrole
        )) OR EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'storage_private')
    THEN RAISE EXCEPTION 'Private Storage yardımcı şeması başka nesneler içeriyor.'; END IF;
    REVOKE ALL ON SCHEMA storage_private FROM PUBLIC;
    FOREACH role_name IN ARRAY ARRAY['authenticated', 'anon', 'service_role', 'dou_app', 'dou_worker']
    LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('REVOKE ALL ON SCHEMA storage_private FROM %I', role_name);
        END IF;
    END LOOP;
    GRANT USAGE ON SCHEMA public TO dou_storage_guard;
    GRANT USAGE, CREATE ON SCHEMA storage_private TO dou_storage_guard;
    IF NOT migration_superuser THEN
        -- Grantor açık seçilir: otomatik ADMIN satırı korunur; kurulum bitince
        -- yalnız bu kurucunun geçici SET/INHERIT satırı geri alınır.
        EXECUTE format('GRANT dou_storage_guard TO %I WITH SET TRUE GRANTED BY %I',
            migration_actor, migration_actor);
        EXECUTE format('GRANT dou_storage_guard TO %I WITH INHERIT TRUE GRANTED BY %I',
            migration_actor, migration_actor);
    END IF;
    GRANT SELECT (course_id, user_id, role, status)
        ON public.course_memberships TO dou_storage_guard;
    GRANT SELECT (course_id, storage_path, uploaded_by)
        ON public.documents TO dou_storage_guard;
    GRANT SELECT (course_id, user_id, mode, finished_at, expires_at)
        ON public.exam_sessions TO dou_storage_guard;

    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION storage_private.storage_user_id() RETURNS uuid
    LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path = pg_catalog
    AS $fn$
    DECLARE
        raw_claims text := nullif(current_setting('request.jwt.claims', true), '');
        claims jsonb;
        user_text text;
        role_text text;
    BEGIN
        IF raw_claims IS NOT NULL THEN
            claims := raw_claims::jsonb;
            IF jsonb_typeof(claims) <> 'object' THEN RETURN NULL; END IF;
            user_text := claims->>'sub';
            role_text := claims->>'role';
        ELSE
            user_text := nullif(current_setting('request.jwt.claim.sub', true), '');
            role_text := nullif(current_setting('request.jwt.claim.role', true), '');
        END IF;
        IF role_text IS DISTINCT FROM 'authenticated'
            OR user_text IS NULL
            OR user_text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        THEN RETURN NULL; END IF;
        RETURN user_text::uuid;
    EXCEPTION WHEN invalid_text_representation THEN RETURN NULL;
    END $fn$
    $ddl$;

    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION storage_private.storage_object_course(object_name text) RETURNS uuid
    LANGUAGE sql IMMUTABLE STRICT SECURITY INVOKER SET search_path = pg_catalog
    AS $fn$
        SELECT CASE WHEN object_name ~
            '^courses/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/[0-9a-f]{32}\.(pdf|pptx|md|txt|py|java|js|ts|c|h|cpp)$'
        THEN split_part(object_name, '/', 2)::uuid ELSE NULL END
    $fn$
    $ddl$;

    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION storage_private.storage_can_access(
        object_name text, action_name text, object_owner text DEFAULT NULL
    ) RETURNS boolean
    LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog
    AS $fn$
    DECLARE
        actor uuid := storage_private.storage_user_id();
        course uuid := storage_private.storage_object_course(object_name);
        course_role text;
    BEGIN
        IF actor IS NULL OR course IS NULL THEN RETURN false; END IF;
        SELECT m.role::text INTO course_role FROM public.course_memberships m
        WHERE m.course_id = course AND m.user_id = actor AND m.status = 'active';
        IF course_role IS NULL THEN RETURN false; END IF;
        IF action_name = 'read' THEN
            RETURN course_role = 'instructor' OR NOT EXISTS (
                SELECT 1 FROM public.exam_sessions e
                WHERE e.course_id = course AND e.user_id = actor AND e.mode = 'exam'
                    AND e.finished_at IS NULL AND e.expires_at > now()
            );
        ELSIF action_name = 'insert' THEN
            RETURN course_role = 'instructor' AND object_owner = actor::text;
        ELSIF action_name = 'delete' THEN
            RETURN course_role = 'instructor' OR object_owner = actor::text OR (
                nullif(object_owner, '') IS NULL AND EXISTS (
                    SELECT 1 FROM public.documents d
                    WHERE d.course_id = course AND d.storage_path = object_name
                        AND d.uploaded_by = actor
                )
            );
        END IF;
        -- UPDATE/upsert yeniden adlandırarak ders/nesne yetkisi taşıyamaz.
        RETURN false;
    END $fn$
    $ddl$;

    REVOKE ALL ON ALL FUNCTIONS IN SCHEMA storage_private FROM PUBLIC;
    FOREACH role_name IN ARRAY ARRAY['authenticated', 'anon', 'service_role', 'dou_app', 'dou_worker']
    LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('REVOKE ALL ON ALL FUNCTIONS IN SCHEMA storage_private FROM %I', role_name);
        END IF;
    END LOOP;
    GRANT USAGE ON SCHEMA storage_private TO authenticated;
    GRANT EXECUTE ON FUNCTION storage_private.storage_user_id() TO authenticated;
    GRANT EXECUTE ON FUNCTION storage_private.storage_object_course(text) TO authenticated;
    GRANT EXECUTE ON FUNCTION storage_private.storage_can_access(text, text, text) TO authenticated;
    ALTER FUNCTION storage_private.storage_user_id() OWNER TO dou_storage_guard;
    ALTER FUNCTION storage_private.storage_object_course(text) OWNER TO dou_storage_guard;
    ALTER FUNCTION storage_private.storage_can_access(text, text, text) OWNER TO dou_storage_guard;
    REVOKE CREATE ON SCHEMA storage_private FROM dou_storage_guard;
    IF NOT migration_superuser THEN
        EXECUTE format('REVOKE dou_storage_guard FROM %I GRANTED BY %I',
            migration_actor, migration_actor);
    END IF;
    IF EXISTS (SELECT 1 FROM pg_auth_members
        WHERE roleid = 'dou_storage_guard'::regrole AND (inherit_option OR set_option))
    THEN RAISE EXCEPTION 'Private Storage geçici rol yetkileri geri alınamadı.'; END IF;

    INSERT INTO storage.buckets (id, name, public)
        VALUES ('course-materials', 'course-materials', false)
        ON CONFLICT (id) DO UPDATE SET public = false;
    -- Supabase nesne tablosunda RLS zaten açıktır. Hosted policy yönetimi izni
    -- tablo sahipliği değildir; gereksiz ALTER TABLE bu kurulumda reddedilir.
    IF NOT (SELECT relrowsecurity FROM pg_class WHERE oid = 'storage.objects'::regclass) THEN
        ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;
    END IF;

    -- Permissive politikalar OR ile birleşir. Mevcut geniş bir politika olsa bile
    -- işlem başına restrictive sınır hedef bucket için üyeliği zorlar.
    DROP POLICY IF EXISTS dou_storage_allow ON storage.objects;
    CREATE POLICY dou_storage_allow ON storage.objects FOR ALL TO authenticated
        USING (bucket_id = 'course-materials') WITH CHECK (bucket_id = 'course-materials');
    DROP POLICY IF EXISTS dou_storage_read_boundary ON storage.objects;
    CREATE POLICY dou_storage_read_boundary ON storage.objects AS RESTRICTIVE
        FOR SELECT TO authenticated
        USING (bucket_id <> 'course-materials' OR storage_private.storage_can_access(name, 'read', owner_id));
    DROP POLICY IF EXISTS dou_storage_insert_boundary ON storage.objects;
    CREATE POLICY dou_storage_insert_boundary ON storage.objects AS RESTRICTIVE
        FOR INSERT TO authenticated
        WITH CHECK (bucket_id <> 'course-materials' OR storage_private.storage_can_access(name, 'insert', owner_id));
    DROP POLICY IF EXISTS dou_storage_delete_boundary ON storage.objects;
    CREATE POLICY dou_storage_delete_boundary ON storage.objects AS RESTRICTIVE
        FOR DELETE TO authenticated
        USING (bucket_id <> 'course-materials' OR storage_private.storage_can_access(name, 'delete', owner_id));
    DROP POLICY IF EXISTS dou_storage_update_boundary ON storage.objects;
    CREATE POLICY dou_storage_update_boundary ON storage.objects AS RESTRICTIVE
        FOR UPDATE TO authenticated
        USING (bucket_id <> 'course-materials') WITH CHECK (bucket_id <> 'course-materials');
    DROP POLICY IF EXISTS dou_storage_identity_boundary ON storage.objects;
    CREATE POLICY dou_storage_identity_boundary ON storage.objects AS RESTRICTIVE
        FOR ALL TO PUBLIC
        USING (bucket_id <> 'course-materials' OR current_user = 'authenticated')
        WITH CHECK (bucket_id <> 'course-materials' OR current_user = 'authenticated');
END
$migration$;
