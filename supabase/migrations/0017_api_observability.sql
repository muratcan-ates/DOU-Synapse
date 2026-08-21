-- DOU-Synapse — privacy-safe API request observability (010)
--
-- Bu tablo bir ham log deposu degildir. Yalniz route sablonu, durum sinifi,
-- sure ve destek kodu tasir; kullanici/ders kimligi, URL, sorgu, govde, IP,
-- user-agent, hata metni ve egitim icerigi semada yer bulamaz.

-- Existing admin-audit CHECK is widened online before the feature transaction.
-- Phase 1 takes only a short metadata lock; phase 2 scans under the lighter
-- validation lock; phase 3 swaps names in another short metadata transaction.
-- Each phase is retry-safe if an operator-enforced timeout interrupts rollout.
BEGIN;
SET LOCAL lock_timeout = '5s';
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint AS constraint_row
        WHERE constraint_row.conrelid = 'public.platform_admin_access_audit'::regclass
          AND constraint_row.conname = 'platform_admin_access_audit_action'
          AND pg_get_constraintdef(constraint_row.oid)
              NOT LIKE '%POST /admin/api-events/query%'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_constraint AS constraint_row
        WHERE constraint_row.conrelid = 'public.platform_admin_access_audit'::regclass
          AND constraint_row.conname = 'platform_admin_access_audit_action_0017'
    ) THEN
        ALTER TABLE platform_admin_access_audit
            ADD CONSTRAINT platform_admin_access_audit_action_0017 CHECK (
                action IN (
                    'GET /admin/overview',
                    'POST /admin/users',
                    'GET /admin/courses',
                    'GET /admin/requests',
                    'GET /admin/ingestion',
                    'POST /admin/api-events/query'
                )
            ) NOT VALID;
    END IF;
END
$$;
COMMIT;

BEGIN;
SET LOCAL statement_timeout = '60s';
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint AS constraint_row
        WHERE constraint_row.conrelid = 'public.platform_admin_access_audit'::regclass
          AND constraint_row.conname = 'platform_admin_access_audit_action_0017'
          AND NOT constraint_row.convalidated
    ) THEN
        ALTER TABLE platform_admin_access_audit
            VALIDATE CONSTRAINT platform_admin_access_audit_action_0017;
    END IF;
END
$$;
COMMIT;

BEGIN;
SET LOCAL lock_timeout = '5s';
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint AS constraint_row
        WHERE constraint_row.conrelid = 'public.platform_admin_access_audit'::regclass
          AND constraint_row.conname = 'platform_admin_access_audit_action_0017'
    ) THEN
        ALTER TABLE platform_admin_access_audit
            DROP CONSTRAINT IF EXISTS platform_admin_access_audit_action;
        ALTER TABLE platform_admin_access_audit
            RENAME CONSTRAINT platform_admin_access_audit_action_0017
            TO platform_admin_access_audit_action;
    END IF;
END
$$;
COMMIT;

BEGIN;

CREATE TABLE api_request_events (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id        text NOT NULL,
    service           text NOT NULL,
    environment       text NOT NULL,
    release_revision  text NOT NULL,
    method            text NOT NULL,
    route_template    text NOT NULL,
    status_code       smallint NOT NULL,
    outcome_code      text,
    duration_ms       integer NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    expires_at        timestamptz NOT NULL,
    CONSTRAINT api_request_events_request_id_unique UNIQUE (request_id),
    CONSTRAINT api_request_events_request_id_safe CHECK (
        request_id ~ '^[a-f0-9]{32}$'
    ),
    CONSTRAINT api_request_events_service_safe CHECK (
        service = 'api'
    ),
    CONSTRAINT api_request_events_environment_safe CHECK (
        environment IN ('local', 'demo', 'production')
    ),
    CONSTRAINT api_request_events_revision_safe CHECK (
        release_revision ~ '^[A-Za-z0-9._-]{1,128}$'
    ),
    CONSTRAINT api_request_events_method_safe CHECK (
        method IN ('GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD')
    ),
    CONSTRAINT api_request_events_route_safe CHECK (
        length(route_template) BETWEEN 1 AND 256
        AND (route_template = 'UNMATCHED' OR route_template ~ '^/[A-Za-z0-9_{}./-]*$')
        AND route_template !~* '(^|/)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}($|/)'
        AND route_template NOT LIKE '/admin%'
        AND route_template NOT LIKE '/health%'
        AND route_template <> '/docs'
        AND route_template NOT LIKE '/docs/%'
        AND route_template NOT IN ('/redoc', '/openapi.json')
    ),
    CONSTRAINT api_request_events_status_safe CHECK (status_code BETWEEN 100 AND 599),
    CONSTRAINT api_request_events_outcome_safe CHECK (
        outcome_code IS NULL OR outcome_code ~ '^[a-z0-9_:-]{1,64}$'
    ),
    CONSTRAINT api_request_events_duration_safe CHECK (
        duration_ms BETWEEN 0 AND 3600000
    ),
    CONSTRAINT api_request_events_expiry_safe CHECK (expires_at > created_at)
);

COMMENT ON TABLE api_request_events IS
    'Kisa omurlu, iceriksiz HTTP operasyon olaylari. Ham log veya kullanici analitigi degildir.';
COMMENT ON COLUMN api_request_events.id IS
    'Yalniz deterministik siralama/purge icin dahili anahtar; API yanitina cikmaz.';
COMMENT ON COLUMN api_request_events.request_id IS
    'Sunucunun urettigi tekil 32-hex korelasyon kodu; retry ayni HTTP olayini ikinci kez yazamaz.';
COMMENT ON COLUMN api_request_events.route_template IS
    'Sunucu route sablonu veya UNMATCHED; ham URL/path degildir.';

ALTER TABLE api_request_events ENABLE ROW LEVEL SECURITY;

-- Politika yoktur ve dogrudan tablo yetkisi hicbir calisma rolune verilmez.
-- Yazma/okuma yalniz asagidaki dar SECURITY DEFINER yuzeylerinden gecmektedir.
REVOKE ALL ON TABLE api_request_events
    FROM PUBLIC, dou_app, dou_worker, dou_api_runtime;

CREATE INDEX api_request_events_created_idx
    ON api_request_events (created_at DESC, id DESC);
CREATE INDEX api_request_events_route_idx
    ON api_request_events (method, route_template, created_at DESC);
CREATE INDEX api_request_events_expiry_idx
    ON api_request_events (expires_at, id);

CREATE OR REPLACE FUNCTION app.record_api_request_events(
    p_events jsonb,
    p_retention_days integer
) RETURNS integer
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public, app AS $$
DECLARE
    v_count integer;
    v_now timestamptz := statement_timestamp();
    v_event jsonb;
BEGIN
    -- current_user/SET ROLE/GUC taklit edilebilir; session_user gercek baglanti
    -- kimligidir. Yalniz dou_api_runtime bu yazma yuzeyine girebilir.
    IF session_user <> 'dou_api_runtime' THEN
        RAISE EXCEPTION 'yalniz api runtime olay yazabilir'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_retention_days IS NULL OR p_retention_days < 1 OR p_retention_days > 30 THEN
        RAISE EXCEPTION 'gecersiz saklama suresi'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF p_events IS NULL OR jsonb_typeof(p_events) <> 'array' THEN
        RAISE EXCEPTION 'olay paketi dizi olmali'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    v_count := jsonb_array_length(p_events);
    IF v_count < 1 OR v_count > 100 THEN
        RAISE EXCEPTION 'olay paketi 1..100 kayit olmali'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    FOR v_event IN SELECT value FROM jsonb_array_elements(p_events)
    LOOP
        IF jsonb_typeof(v_event) <> 'object'
           OR (SELECT array_agg(key ORDER BY key) FROM jsonb_object_keys(v_event) AS key)
              IS DISTINCT FROM ARRAY[
                  'duration_ms', 'environment', 'method', 'outcome_code',
                  'release_revision', 'request_id', 'route_template',
                  'service', 'status_code'
              ]::text[]
           OR jsonb_typeof(v_event->'request_id') <> 'string'
           OR (v_event->>'request_id') !~ '^[a-f0-9]{32}$'
           OR v_event->>'service' <> 'api'
           OR v_event->>'environment' NOT IN ('local', 'demo', 'production')
           OR (v_event->>'release_revision') !~ '^[A-Za-z0-9._-]{1,128}$'
           OR v_event->>'method' NOT IN ('GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD')
           OR length(v_event->>'route_template') NOT BETWEEN 1 AND 256
           OR NOT (
                v_event->>'route_template' = 'UNMATCHED'
                OR v_event->>'route_template' ~ '^/[A-Za-z0-9_{}./-]*$'
           )
           OR v_event->>'route_template' LIKE '/admin%'
           OR v_event->>'route_template' LIKE '/health%'
           OR v_event->>'route_template' = '/docs'
           OR v_event->>'route_template' LIKE '/docs/%'
           OR v_event->>'route_template' IN ('/redoc', '/openapi.json')
           OR v_event->>'route_template' ~* '(^|/)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}($|/)'
           OR jsonb_typeof(v_event->'status_code') <> 'number'
           OR (v_event->>'status_code') !~ '^[0-9]{3}$'
           OR (v_event->>'status_code')::integer NOT BETWEEN 100 AND 599
           OR (
                jsonb_typeof(v_event->'outcome_code') <> 'null'
                AND (
                    jsonb_typeof(v_event->'outcome_code') <> 'string'
                    OR (v_event->>'outcome_code') !~ '^[a-z0-9_:-]{1,64}$'
                )
           )
           OR jsonb_typeof(v_event->'duration_ms') <> 'number'
           OR (v_event->>'duration_ms') !~ '^[0-9]{1,8}$'
           OR (v_event->>'duration_ms')::integer NOT BETWEEN 0 AND 3600000 THEN
            RAISE EXCEPTION 'gecersiz veya guvensiz api olayi'
                USING ERRCODE = 'invalid_parameter_value';
        END IF;
    END LOOP;

    INSERT INTO public.api_request_events (
        request_id,
        service,
        environment,
        release_revision,
        method,
        route_template,
        status_code,
        outcome_code,
        duration_ms,
        created_at,
        expires_at
    )
    SELECT event->>'request_id',
           event->>'service',
           event->>'environment',
           event->>'release_revision',
           event->>'method',
           event->>'route_template',
           (event->>'status_code')::smallint,
           event->>'outcome_code',
           (event->>'duration_ms')::integer,
           v_now,
           v_now + make_interval(days => p_retention_days)
    FROM jsonb_array_elements(p_events) AS event
    ON CONFLICT (request_id) DO NOTHING;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END
$$;

CREATE OR REPLACE FUNCTION app.admin_api_request_events(
    p_window_minutes integer,
    p_limit integer,
    p_offset integer,
    p_method text,
    p_route text,
    p_status_class text,
    p_request_id text
) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, app AS $$
DECLARE
    v_result jsonb;
    v_measured_at timestamptz := statement_timestamp();
BEGIN
    IF NOT app.is_platform_admin() THEN
        RAISE EXCEPTION 'platform yoneticisi degil'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_window_minutes IS NULL OR p_window_minutes NOT IN (15, 60, 1440) THEN
        RAISE EXCEPTION 'gecersiz gozlem penceresi'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF p_limit IS NULL OR p_offset IS NULL
       OR p_limit < 1 OR p_limit > 100 OR p_offset < 0 THEN
        RAISE EXCEPTION 'gecersiz sayfalama'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF p_method IS NOT NULL
       AND btrim(p_method) NOT IN ('GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD') THEN
        RAISE EXCEPTION 'gecersiz HTTP metodu'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF p_route IS NOT NULL AND (
        length(btrim(p_route)) NOT BETWEEN 1 AND 256
        OR btrim(p_route) ~ '[?#]'
    ) THEN
        RAISE EXCEPTION 'gecersiz route sablonu'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF p_status_class IS NOT NULL
       AND btrim(p_status_class) NOT IN ('2xx', '3xx', '4xx', '5xx') THEN
        RAISE EXCEPTION 'gecersiz durum sinifi'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF p_request_id IS NOT NULL
       AND btrim(p_request_id) !~ '^[a-f0-9]{32}$' THEN
        RAISE EXCEPTION 'gecersiz istek kimligi'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    WITH filtered AS MATERIALIZED (
        SELECT event.*
        FROM public.api_request_events AS event
        WHERE event.created_at >= v_measured_at - make_interval(mins => p_window_minutes)
          AND event.created_at <= v_measured_at
          AND event.expires_at > v_measured_at
          AND (p_method IS NULL OR event.method = btrim(p_method))
          AND (p_route IS NULL OR event.route_template = btrim(p_route))
          AND (
              p_status_class IS NULL
              OR event.status_code / 100 = left(btrim(p_status_class), 1)::integer
          )
          AND (p_request_id IS NULL OR event.request_id = btrim(p_request_id))
    ), paged AS (
        SELECT *
        FROM filtered
        ORDER BY created_at DESC, id DESC
        LIMIT p_limit OFFSET p_offset
    ), route_stats AS (
        SELECT method,
               route_template,
               count(*) AS requests_total,
               count(*) FILTER (WHERE status_code BETWEEN 400 AND 599) AS error_total,
               percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95,
               max(created_at) AS last_seen_at
        FROM filtered
        GROUP BY method, route_template
        ORDER BY requests_total DESC, method, route_template
        LIMIT 25
    )
    SELECT jsonb_build_object(
        'measured_at', v_measured_at,
        'window_minutes', p_window_minutes,
        'summary', jsonb_build_object(
            'requests_total', count(*),
            'successful_total', count(*) FILTER (WHERE status_code BETWEEN 200 AND 299),
            'redirect_total', count(*) FILTER (WHERE status_code BETWEEN 300 AND 399),
            'client_error_total', count(*) FILTER (WHERE status_code BETWEEN 400 AND 499),
            'server_error_total', count(*) FILTER (WHERE status_code BETWEEN 500 AND 599),
            'p50_latency_ms', percentile_cont(0.50) WITHIN GROUP (ORDER BY duration_ms),
            'p95_latency_ms', percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms)
        ),
        'routes', coalesce(
            (SELECT jsonb_agg(
                jsonb_build_object(
                    'method', method,
                    'route_template', route_template,
                    'requests_total', requests_total,
                    'error_total', error_total,
                    'p95_latency_ms', p95,
                    'last_seen_at', last_seen_at
                ) ORDER BY requests_total DESC, method, route_template
            ) FROM route_stats),
            '[]'::jsonb
        ),
        'items', coalesce(
            (SELECT jsonb_agg(
                jsonb_build_object(
                    'request_id', request_id,
                    'service', service,
                    'environment', environment,
                    'release_revision', release_revision,
                    'method', method,
                    'route_template', route_template,
                    'status_code', status_code,
                    'outcome_code', outcome_code,
                    'duration_ms', duration_ms,
                    'created_at', created_at
                ) ORDER BY created_at DESC, id DESC
            ) FROM paged),
            '[]'::jsonb
        ),
        'total', count(*),
        'limit', p_limit,
        'offset', p_offset
    ) INTO v_result
    FROM filtered;

    RETURN v_result;
END
$$;

CREATE OR REPLACE FUNCTION app.purge_expired_api_request_events(
    p_limit integer
) RETURNS integer
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public, app AS $$
DECLARE
    v_deleted integer;
BEGIN
    IF session_user <> 'dou_api_runtime' THEN
        RAISE EXCEPTION 'yalniz api runtime olay temizleyebilir'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_limit IS NULL OR p_limit < 1 OR p_limit > 10000 THEN
        RAISE EXCEPTION 'gecersiz temizleme siniri'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    WITH expired AS (
        SELECT id
        FROM public.api_request_events
        WHERE expires_at <= statement_timestamp()
        ORDER BY expires_at, id
        LIMIT p_limit
        FOR UPDATE SKIP LOCKED
    )
    DELETE FROM public.api_request_events AS event
    USING expired
    WHERE event.id = expired.id;

    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RETURN v_deleted;
END
$$;

CREATE OR REPLACE FUNCTION app.audit_platform_admin_access(
    p_action text,
    p_request_id text
) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public, app AS $$
DECLARE
    v_actor uuid := app.current_user_id();
    v_allowed boolean;
    v_safe_request_id text;
BEGIN
    IF v_actor IS NULL THEN
        RAISE EXCEPTION 'kimlik baglami yok'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_action IS NULL OR p_action NOT IN (
        'GET /admin/overview',
        'POST /admin/users',
        'GET /admin/courses',
        'GET /admin/requests',
        'GET /admin/ingestion',
        'POST /admin/api-events/query'
    ) THEN
        RAISE EXCEPTION 'gecersiz admin eylemi'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF p_request_id ~ '^[a-f0-9]{32}$' THEN
        v_safe_request_id := p_request_id;
    ELSIF p_request_id ~ '^[A-Za-z0-9_-]{1,128}$' THEN
        -- Expand/contract uyumu: 0017 once uygulanirken eski API replikalari
        -- istemci basligini audit fonksiyonuna tasiyabilir. Ham/pseudonymous
        -- degeri depolamak yerine korelasyonsuz yeni bir server kodu uret;
        -- yeni API zaten ilk dala girer. Eski replika drain edildikten sonra
        -- gelecek bir migration legacy dali kaldirabilir.
        v_safe_request_id := replace(gen_random_uuid()::text, '-', '');
    ELSE
        RAISE EXCEPTION 'gecersiz istek kimligi'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    v_allowed := app.is_platform_admin();
    INSERT INTO public.platform_admin_access_audit (
        actor_user_id, action, result, request_id
    ) VALUES (
        v_actor,
        p_action,
        CASE WHEN v_allowed THEN 'allowed' ELSE 'denied' END,
        v_safe_request_id
    );
    RETURN v_allowed;
END
$$;

-- PostgreSQL fonksiyonlara varsayilan PUBLIC EXECUTE verebilir; her yuzey once
-- tamamen kapatilir, sonra yalniz gerekli gercek/tasiyici role acilir.
REVOKE ALL ON FUNCTION app.record_api_request_events(jsonb, integer)
    FROM PUBLIC, dou_app, dou_worker, dou_api_runtime;
REVOKE ALL ON FUNCTION app.admin_api_request_events(
    integer, integer, integer, text, text, text, text
) FROM PUBLIC, dou_app, dou_worker, dou_api_runtime;
REVOKE ALL ON FUNCTION app.purge_expired_api_request_events(integer)
    FROM PUBLIC, dou_app, dou_worker, dou_api_runtime;

GRANT EXECUTE ON FUNCTION app.record_api_request_events(jsonb, integer)
    TO dou_api_runtime;
GRANT EXECUTE ON FUNCTION app.admin_api_request_events(
    integer, integer, integer, text, text, text, text
) TO dou_app;
GRANT EXECUTE ON FUNCTION app.purge_expired_api_request_events(integer)
    TO dou_api_runtime;

COMMIT;
