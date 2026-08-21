-- DOU-Synapse — platform yöneticisi ve güvenli operasyon konsolu
--
-- Platform işletim yetkisi ders eğitmenliğinden bağımsızdır. Uygulama rolünün
-- platform_admins üzerinde doğrudan okuma veya yazma hakkı yoktur. Yönetim
-- sorguları kişisel sohbet/cevap metni döndürmeyen, kendi içinde yetkiyi yeniden
-- doğrulayan dar SECURITY DEFINER fonksiyonları üzerinden çalışır.

BEGIN;

CREATE TABLE platform_admins (
    user_id     uuid PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
    granted_by  uuid REFERENCES profiles(id) ON DELETE SET NULL,
    granted_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE platform_admin_access_audit (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id uuid NOT NULL,
    action        text NOT NULL,
    result        text NOT NULL,
    request_id    text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT platform_admin_access_audit_action CHECK (
        action IN (
            'GET /admin/overview',
            'POST /admin/users',
            'GET /admin/courses',
            'GET /admin/requests',
            'GET /admin/ingestion'
        )
    ),
    CONSTRAINT platform_admin_access_audit_result CHECK (result IN ('allowed', 'denied')),
    CONSTRAINT platform_admin_access_audit_request_id CHECK (
        request_id ~ '^[A-Za-z0-9_-]{1,128}$'
    )
);

COMMENT ON TABLE platform_admins IS
    'Ders rollerinden ayrı, yalnız kontrollü kurulum/DBA adımıyla atanan platform rolü.';

COMMENT ON TABLE platform_admin_access_audit IS
    'Platform admin yetki kararlarının içeriksiz ve uygulama açısından append-only izi.';

ALTER TABLE platform_admins ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_admin_access_audit ENABLE ROW LEVEL SECURITY;

-- Politika bilinçli olarak yoktur: uygulama/worker tabloyu doğrudan okuyamaz
-- veya değiştiremez. Tablo sahibi dar SECURITY DEFINER yardımcılarında RLS'i
-- atlar; FORCE kullanılmamasının sebebi budur. İlk yönetici kurulum rolüyle atanır.
REVOKE ALL ON TABLE platform_admins FROM PUBLIC, dou_app, dou_worker;
REVOKE ALL ON TABLE platform_admin_access_audit FROM PUBLIC, dou_app, dou_worker;

CREATE OR REPLACE FUNCTION app.is_platform_admin() RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, app AS $$
    SELECT app.current_user_id() IS NOT NULL
       AND EXISTS (
            SELECT 1
            FROM public.platform_admins AS pa
            WHERE pa.user_id = app.current_user_id()
       )
$$;

-- Yetki kararı ve audit yazımı aynı dar fonksiyondadır. `result` istemciden
-- alınmaz; tabloya yazılan karar, o anda veritabanından yeniden hesaplanır.
-- API bu fonksiyonu ayrı ve tamamlanan bir işlemde çağır; denied kararından
-- sonra ana istek 403 ile kesilse bile audit satırı geri alınmaz.
CREATE OR REPLACE FUNCTION app.audit_platform_admin_access(
    p_action text,
    p_request_id text
) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public, app AS $$
DECLARE
    v_actor uuid := app.current_user_id();
    v_allowed boolean;
BEGIN
    IF v_actor IS NULL THEN
        RAISE EXCEPTION 'kimlik bağlamı yok'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_action IS NULL OR p_action NOT IN (
        'GET /admin/overview',
        'POST /admin/users',
        'GET /admin/courses',
        'GET /admin/requests',
        'GET /admin/ingestion'
    ) THEN
        RAISE EXCEPTION 'geçersiz admin eylemi'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF p_request_id IS NULL OR p_request_id !~ '^[A-Za-z0-9_-]{1,128}$' THEN
        RAISE EXCEPTION 'geçersiz istek kimliği'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    v_allowed := app.is_platform_admin();
    INSERT INTO public.platform_admin_access_audit (
        actor_user_id,
        action,
        result,
        request_id
    ) VALUES (
        v_actor,
        p_action,
        CASE WHEN v_allowed THEN 'allowed' ELSE 'denied' END,
        p_request_id
    );
    RETURN v_allowed;
END
$$;

CREATE OR REPLACE FUNCTION app.admin_overview() RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, app AS $$
DECLARE
    v_result jsonb;
BEGIN
    IF NOT app.is_platform_admin() THEN
        RAISE EXCEPTION 'platform yöneticisi değil'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    WITH successful_chat_turns AS (
        SELECT latency_ms, token_count
        FROM public.request_logs
        WHERE created_at >= now() - interval '24 hours'
          AND route = 'POST /courses/{course_id}/chat'
          AND http_status BETWEEN 200 AND 299
    )
    SELECT jsonb_build_object(
        'users_total',          (SELECT count(*) FROM public.profiles),
        'active_memberships_total',
                                (SELECT count(*) FROM public.course_memberships
                                 WHERE status = 'active'),
        'courses_total',        (SELECT count(*) FROM public.courses),
        'documents_total',      (SELECT count(*) FROM public.documents),
        'ingestion_processing', (SELECT count(*) FROM public.ingestion_jobs
                                 WHERE status = 'processing'),
        'ingestion_failed',     (SELECT count(*) FROM public.ingestion_jobs
                                 WHERE status = 'failed'),
        'chat_turns_24h',       (SELECT count(*) FROM successful_chat_turns),
        'p95_latency_ms',       (SELECT percentile_cont(0.95)
                                           WITHIN GROUP (ORDER BY latency_ms)
                                 FROM successful_chat_turns),
        'tokens_24h',           (SELECT coalesce(sum(token_count), 0)
                                 FROM successful_chat_turns)
    ) INTO v_result;

    RETURN v_result;
END
$$;

CREATE OR REPLACE FUNCTION app.admin_users(
    p_limit integer,
    p_offset integer,
    p_search text
) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, app AS $$
DECLARE
    v_result jsonb;
BEGIN
    IF NOT app.is_platform_admin() THEN
        RAISE EXCEPTION 'platform yöneticisi değil'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_limit IS NULL OR p_offset IS NULL
       OR p_limit < 1 OR p_limit > 100 OR p_offset < 0 THEN
        RAISE EXCEPTION 'geçersiz sayfalama'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    WITH filtered AS (
        SELECT p.id,
               CASE
                   WHEN position('@' IN p.email) > 1 THEN
                       left(split_part(p.email, '@', 1), 2)
                           || '***@' || split_part(p.email, '@', 2)
                   ELSE '***'
               END AS masked_email,
               p.full_name,
               p.created_at,
               EXISTS (
                   SELECT 1 FROM public.platform_admins AS pa WHERE pa.user_id = p.id
               ) AS is_platform_admin,
               (
                   SELECT count(*)
                   FROM public.course_memberships AS m
                   WHERE m.user_id = p.id AND m.status = 'active'
               ) AS active_course_count
        FROM public.profiles AS p
        WHERE nullif(btrim(p_search), '') IS NULL
           OR coalesce(p.full_name, '') ILIKE '%' || btrim(p_search) || '%'
           OR CASE
                  WHEN position('@' IN p.email) > 1 THEN
                      left(split_part(p.email, '@', 1), 2)
                          || '***@' || split_part(p.email, '@', 2)
                  ELSE '***'
              END ILIKE '%' || btrim(p_search) || '%'
    ), paged AS (
        SELECT *
        FROM filtered
        ORDER BY created_at DESC, id DESC
        LIMIT p_limit OFFSET p_offset
    )
    SELECT jsonb_build_object(
        'items', coalesce(
            (SELECT jsonb_agg(
                jsonb_build_object(
                    'id', id,
                    'masked_email', masked_email,
                    'full_name', full_name,
                    'created_at', created_at,
                    'is_platform_admin', is_platform_admin,
                    'active_course_count', active_course_count
                ) ORDER BY created_at DESC, id DESC
             ) FROM paged),
            '[]'::jsonb
        ),
        'total', (SELECT count(*) FROM filtered),
        'limit', p_limit,
        'offset', p_offset
    ) INTO v_result;

    RETURN v_result;
END
$$;

CREATE OR REPLACE FUNCTION app.admin_courses(
    p_limit integer,
    p_offset integer,
    p_search text
) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, app AS $$
DECLARE
    v_result jsonb;
BEGIN
    IF NOT app.is_platform_admin() THEN
        RAISE EXCEPTION 'platform yöneticisi değil'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_limit IS NULL OR p_offset IS NULL
       OR p_limit < 1 OR p_limit > 100 OR p_offset < 0 THEN
        RAISE EXCEPTION 'geçersiz sayfalama'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    WITH filtered AS (
        SELECT c.id,
               c.code,
               c.title,
               c.created_at,
               coalesce(nullif(btrim(creator.full_name), ''), 'Ad belirtilmemiş')
                   AS creator_name,
               (
                   SELECT count(*) FROM public.course_memberships AS m
                   WHERE m.course_id = c.id AND m.status = 'active'
               ) AS active_member_count,
               (
                   SELECT count(*) FROM public.documents AS d WHERE d.course_id = c.id
               ) AS documents_total,
               (
                   SELECT count(*) FROM public.documents AS d
                   WHERE d.course_id = c.id AND d.status = 'failed'
               ) AS documents_failed
        FROM public.courses AS c
        JOIN public.profiles AS creator ON creator.id = c.created_by
        WHERE nullif(btrim(p_search), '') IS NULL
           OR c.code ILIKE '%' || btrim(p_search) || '%'
           OR c.title ILIKE '%' || btrim(p_search) || '%'
    ), paged AS (
        SELECT *
        FROM filtered
        ORDER BY created_at DESC, id DESC
        LIMIT p_limit OFFSET p_offset
    )
    SELECT jsonb_build_object(
        'items', coalesce(
            (SELECT jsonb_agg(
                jsonb_build_object(
                    'id', id,
                    'code', code,
                    'title', title,
                    'created_at', created_at,
                    'creator_name', creator_name,
                    'active_member_count', active_member_count,
                    'documents_total', documents_total,
                    'documents_failed', documents_failed
                ) ORDER BY created_at DESC, id DESC
             ) FROM paged),
            '[]'::jsonb
        ),
        'total', (SELECT count(*) FROM filtered),
        'limit', p_limit,
        'offset', p_offset
    ) INTO v_result;

    RETURN v_result;
END
$$;

CREATE OR REPLACE FUNCTION app.admin_request_logs(
    p_limit integer,
    p_offset integer,
    p_route text,
    p_status text
) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, app AS $$
DECLARE
    v_result jsonb;
BEGIN
    IF NOT app.is_platform_admin() THEN
        RAISE EXCEPTION 'platform yöneticisi değil'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_limit IS NULL OR p_offset IS NULL
       OR p_limit < 1 OR p_limit > 100 OR p_offset < 0 THEN
        RAISE EXCEPTION 'geçersiz sayfalama'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    WITH filtered AS (
        SELECT r.id,
               r.course_id,
               c.code AS course_code,
               r.route,
               r.mode::text AS mode,
               r.status::text AS status,
               r.http_status,
               r.latency_ms,
               r.token_count,
               r.cache_hit,
               r.created_at
        FROM public.request_logs AS r
        JOIN public.courses AS c ON c.id = r.course_id
        WHERE (nullif(btrim(p_route), '') IS NULL OR r.route = btrim(p_route))
          AND (nullif(btrim(p_status), '') IS NULL OR r.status::text = btrim(p_status))
    ), paged AS (
        SELECT *
        FROM filtered
        ORDER BY created_at DESC, id DESC
        LIMIT p_limit OFFSET p_offset
    )
    SELECT jsonb_build_object(
        'items', coalesce(
            (SELECT jsonb_agg(
                jsonb_build_object(
                    'log_id', id,
                    'course_id', course_id,
                    'course_code', course_code,
                    'route', route,
                    'mode', mode,
                    'status', status,
                    'http_status', http_status,
                    'latency_ms', latency_ms,
                    'token_count', token_count,
                    'cache_hit', cache_hit,
                    'created_at', created_at
                ) ORDER BY created_at DESC, id DESC
             ) FROM paged),
            '[]'::jsonb
        ),
        'total', (SELECT count(*) FROM filtered),
        'limit', p_limit,
        'offset', p_offset
    ) INTO v_result;

    RETURN v_result;
END
$$;

CREATE OR REPLACE FUNCTION app.admin_ingestion_jobs(
    p_limit integer,
    p_offset integer,
    p_status text
) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, app AS $$
DECLARE
    v_result jsonb;
BEGIN
    IF NOT app.is_platform_admin() THEN
        RAISE EXCEPTION 'platform yöneticisi değil'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_limit IS NULL OR p_offset IS NULL
       OR p_limit < 1 OR p_limit > 100 OR p_offset < 0 THEN
        RAISE EXCEPTION 'geçersiz sayfalama'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    WITH filtered AS (
        SELECT j.id,
               j.document_id,
               d.course_id,
               c.code AS course_code,
               j.status::text AS status,
               j.attempt_count,
               j.started_at,
               j.completed_at,
               j.created_at
        FROM public.ingestion_jobs AS j
        JOIN public.documents AS d ON d.id = j.document_id
        JOIN public.courses AS c ON c.id = d.course_id
        WHERE nullif(btrim(p_status), '') IS NULL OR j.status::text = btrim(p_status)
    ), paged AS (
        SELECT *
        FROM filtered
        ORDER BY created_at DESC, id DESC
        LIMIT p_limit OFFSET p_offset
    )
    SELECT jsonb_build_object(
        'items', coalesce(
            (SELECT jsonb_agg(
                jsonb_build_object(
                    'id', id,
                    'document_id', document_id,
                    'course_id', course_id,
                    'course_code', course_code,
                    'status', status,
                    'attempt_count', attempt_count,
                    'started_at', started_at,
                    'completed_at', completed_at,
                    'created_at', created_at
                ) ORDER BY created_at DESC, id DESC
             ) FROM paged),
            '[]'::jsonb
        ),
        'total', (SELECT count(*) FROM filtered),
        'limit', p_limit,
        'offset', p_offset
    ) INTO v_result;

    RETURN v_result;
END
$$;

-- Operasyon listelerinin sabit sıralamasını ve filtrelerini destekler.
CREATE INDEX profiles_admin_page_idx ON profiles (created_at DESC, id DESC);
CREATE INDEX platform_admin_access_audit_created_idx
    ON platform_admin_access_audit (created_at DESC, id DESC);
CREATE INDEX request_logs_admin_page_idx ON request_logs (created_at DESC, id DESC);
CREATE INDEX request_logs_admin_status_page_idx
    ON request_logs (status, created_at DESC, id DESC);
CREATE INDEX ingestion_jobs_admin_status_page_idx
    ON ingestion_jobs (status, created_at DESC, id DESC);

-- PostgreSQL fonksiyonlara varsayılan olarak PUBLIC EXECUTE verir. Bu varsayılan
-- kapatılmazsa API bağımlılığı atlanarak fonksiyon çağrısı denenebilirdi.
REVOKE EXECUTE ON FUNCTION app.is_platform_admin() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION app.audit_platform_admin_access(text, text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION app.admin_overview() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION app.admin_users(integer, integer, text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION app.admin_courses(integer, integer, text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION app.admin_request_logs(integer, integer, text, text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION app.admin_ingestion_jobs(integer, integer, text) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION app.is_platform_admin() TO dou_app;
GRANT EXECUTE ON FUNCTION app.audit_platform_admin_access(text, text) TO dou_app;
GRANT EXECUTE ON FUNCTION app.admin_overview() TO dou_app;
GRANT EXECUTE ON FUNCTION app.admin_users(integer, integer, text) TO dou_app;
GRANT EXECUTE ON FUNCTION app.admin_courses(integer, integer, text) TO dou_app;
GRANT EXECUTE ON FUNCTION app.admin_request_logs(integer, integer, text, text) TO dou_app;
GRANT EXECUTE ON FUNCTION app.admin_ingestion_jobs(integer, integer, text) TO dou_app;

COMMIT;
