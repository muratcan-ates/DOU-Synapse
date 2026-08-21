-- 010 API observability veritabani guvenlik/mahremiyet kaniti.
-- Beklenen cikti: her iddia PASS; herhangi bir FAIL CI kapisini kapatir.

\set ON_ERROR_STOP on
\pset format unaligned
\pset tuples_only on

BEGIN;

INSERT INTO profiles (id, email, full_name) VALUES
    ('a1000000-0000-0000-0000-000000000001', 'obs-admin@dogus.edu.tr', 'Obs Admin'),
    ('a1000000-0000-0000-0000-000000000002', 'obs-normal@dogus.edu.tr', 'Obs Normal');
INSERT INTO platform_admins (user_id)
VALUES ('a1000000-0000-0000-0000-000000000001');

SELECT CASE WHEN (
    SELECT array_agg(column_name::text ORDER BY ordinal_position)
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'api_request_events'
) = ARRAY[
    'id', 'request_id', 'service', 'environment', 'release_revision', 'method',
    'route_template', 'status_code', 'outcome_code', 'duration_ms', 'created_at',
    'expires_at'
]::text[] THEN 'PASS  schema__exact_iceriksiz_kolon_kumesi'
ELSE 'FAIL  schema__exact_iceriksiz_kolon_kumesi' END;

SELECT CASE WHEN
       NOT EXISTS (
           SELECT 1
           FROM pg_proc AS function_row,
                LATERAL aclexplode(
                    coalesce(function_row.proacl, acldefault('f', function_row.proowner))
                ) AS privilege
           WHERE function_row.oid = 'app.record_api_request_events(jsonb,integer)'::regprocedure
             AND privilege.grantee = 0
             AND privilege.privilege_type = 'EXECUTE'
       )
   AND NOT has_function_privilege(
           'dou_app', 'app.record_api_request_events(jsonb,integer)', 'EXECUTE'
       )
   AND NOT has_function_privilege(
           'dou_worker', 'app.record_api_request_events(jsonb,integer)', 'EXECUTE'
       )
   AND has_function_privilege(
           'dou_api_runtime', 'app.record_api_request_events(jsonb,integer)', 'EXECUTE'
       )
   AND NOT EXISTS (
           SELECT 1
           FROM pg_proc AS function_row,
                LATERAL aclexplode(
                    coalesce(function_row.proacl, acldefault('f', function_row.proowner))
                ) AS privilege
           WHERE function_row.oid =
                 'app.admin_api_request_events(integer,integer,integer,text,text,text,text)'::regprocedure
             AND privilege.grantee = 0
             AND privilege.privilege_type = 'EXECUTE'
       )
   AND has_function_privilege(
           'dou_app',
           'app.admin_api_request_events(integer,integer,integer,text,text,text,text)',
           'EXECUTE'
       )
   AND has_function_privilege(
           'dou_api_runtime',
           'app.admin_api_request_events(integer,integer,integer,text,text,text,text)',
           'EXECUTE'
       )
   AND NOT has_function_privilege(
           'dou_worker',
           'app.admin_api_request_events(integer,integer,integer,text,text,text,text)',
           'EXECUTE'
       )
   AND NOT EXISTS (
           SELECT 1
           FROM pg_proc AS function_row,
                LATERAL aclexplode(
                    coalesce(function_row.proacl, acldefault('f', function_row.proowner))
                ) AS privilege
           WHERE function_row.oid =
                 'app.purge_expired_api_request_events(integer)'::regprocedure
             AND privilege.grantee = 0
             AND privilege.privilege_type = 'EXECUTE'
       )
   AND NOT has_function_privilege(
           'dou_app', 'app.purge_expired_api_request_events(integer)', 'EXECUTE'
       )
   AND NOT has_function_privilege(
           'dou_worker', 'app.purge_expired_api_request_events(integer)', 'EXECUTE'
       )
   AND has_function_privilege(
           'dou_api_runtime', 'app.purge_expired_api_request_events(integer)', 'EXECUTE'
       )
THEN 'PASS  acl__fonksiyon_yuzeyleri_exact_rol_allowlist'
ELSE 'FAIL  acl__fonksiyon_yuzeyleri_exact_rol_allowlist' END;

-- Gercek runtime session_user ile dar batch writer calisir.
SET SESSION AUTHORIZATION dou_api_runtime;
SELECT set_config(
    'app.current_user_id',
    'a1000000-0000-0000-0000-000000000001',
    false
);

SELECT app.record_api_request_events(
    '[
      {"request_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","service":"api","environment":"demo",
       "release_revision":"010-test","method":"POST",
       "route_template":"/courses/{course_id}/chat","status_code":500,
       "outcome_code":"internal_error","duration_ms":100},
      {"request_id":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","service":"api","environment":"demo",
       "release_revision":"010-test","method":"POST",
       "route_template":"/courses/{course_id}/chat","status_code":200,
       "outcome_code":null,"duration_ms":20},
      {"request_id":"cccccccccccccccccccccccccccccccc","service":"api","environment":"demo",
       "release_revision":"010-test","method":"GET",
       "route_template":"UNMATCHED","status_code":404,
       "outcome_code":"not_found","duration_ms":10}
    ]'::jsonb,
    7
) AS runtime_inserted \gset

SELECT CASE WHEN :'runtime_inserted'::integer = 3
    THEN 'PASS  runtime_writer__batch_yazilir'
    ELSE 'FAIL  runtime_writer__batch_yazilir' END;

SELECT app.record_api_request_events(
    '[{"request_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","service":"api","environment":"demo",
       "release_revision":"010-test","method":"POST",
       "route_template":"/courses/{course_id}/chat","status_code":500,
       "outcome_code":"internal_error","duration_ms":100}]'::jsonb,
    7
) AS retry_inserted \gset

SELECT app.admin_api_request_events(
    60, 25, 0, NULL, NULL, NULL,
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
) AS retry_payload \gset

SELECT CASE WHEN :'retry_inserted'::integer = 0
                  AND (:'retry_payload'::jsonb->>'total')::integer = 1
    THEN 'PASS  runtime_writer__retry_idempotent_tek_http_olayi'
    ELSE 'FAIL  runtime_writer__retry_idempotent_tek_http_olayi' END;

DO $$
BEGIN
    PERFORM app.record_api_request_events(
        '[{"request_id":"cccccccccccccccccccccccccccccccc","service":"api","environment":"demo",
           "release_revision":"010-test","method":"GET","route_template":"/dashboard",
           "status_code":200,"outcome_code":null,"duration_ms":1,
           "prompt":"gizli"}]'::jsonb,
        7
    );
    RAISE NOTICE 'FAIL  runtime_writer__fazladan_icerik_alani_reddedilir';
EXCEPTION
    WHEN invalid_parameter_value THEN
        RAISE NOTICE 'PASS  runtime_writer__fazladan_icerik_alani_reddedilir';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  runtime_writer__fazladan_icerik_alani_reddedilir (yanlis hata: %)', SQLSTATE;
END
$$;

DO $$
BEGIN
    PERFORM app.record_api_request_events(
        '[{"request_id":"dddddddddddddddddddddddddddddddd","service":"api","environment":"demo",
           "release_revision":"010-test","method":"GET",
           "route_template":"/docs/oauth2-redirect","status_code":200,
           "outcome_code":null,"duration_ms":1}]'::jsonb,
        7
    );
    RAISE NOTICE 'FAIL  runtime_writer__docs_alt_yolu_reddedilir';
EXCEPTION
    WHEN invalid_parameter_value THEN
        RAISE NOTICE 'PASS  runtime_writer__docs_alt_yolu_reddedilir';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  runtime_writer__docs_alt_yolu_reddedilir (yanlis hata: %)', SQLSTATE;
END
$$;

DO $$
BEGIN
    INSERT INTO public.api_request_events (
        request_id, service, environment, release_revision, method, route_template,
        status_code, duration_ms, expires_at
    ) VALUES (
        'ffffffffffffffffffffffffffffffff', 'api', 'demo', '010-direct', 'GET',
        '/dashboard', 200, 1, now() + interval '1 day'
    );
    RAISE NOTICE 'FAIL  rls__runtime_dogrudan_tabloya_insert_yapamaz';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  rls__runtime_dogrudan_tabloya_insert_yapamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  rls__runtime_dogrudan_tabloya_insert_yapamaz (yanlis hata: %)', SQLSTATE;
END
$$;

DO $$
BEGIN
    UPDATE public.api_request_events SET duration_ms = 2;
    RAISE NOTICE 'FAIL  rls__runtime_dogrudan_tabloyu_update_edemez';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  rls__runtime_dogrudan_tabloyu_update_edemez';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  rls__runtime_dogrudan_tabloyu_update_edemez (yanlis hata: %)', SQLSTATE;
END
$$;

DO $$
BEGIN
    DELETE FROM public.api_request_events;
    RAISE NOTICE 'FAIL  rls__runtime_dogrudan_tablodan_delete_yapamaz';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  rls__runtime_dogrudan_tablodan_delete_yapamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  rls__runtime_dogrudan_tablodan_delete_yapamaz (yanlis hata: %)', SQLSTATE;
END
$$;

DO $$
BEGIN
    PERFORM app.record_api_request_events(
        '[{"request_id":"dddddddddddddddddddddddddddddddd","service":"api","environment":"demo",
           "release_revision":"010-test","method":"GET",
           "route_template":"/courses/550e8400-e29b-41d4-a716-446655440000",
           "status_code":200,"outcome_code":null,"duration_ms":1}]'::jsonb,
        7
    );
    RAISE NOTICE 'FAIL  runtime_writer__ham_uuid_path_reddedilir';
EXCEPTION
    WHEN invalid_parameter_value THEN
        RAISE NOTICE 'PASS  runtime_writer__ham_uuid_path_reddedilir';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  runtime_writer__ham_uuid_path_reddedilir (yanlis hata: %)', SQLSTATE;
END
$$;

DO $$
BEGIN
    PERFORM count(*) FROM public.api_request_events;
    RAISE NOTICE 'FAIL  rls__runtime_dogrudan_tablo_okuyamaz';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  rls__runtime_dogrudan_tablo_okuyamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  rls__runtime_dogrudan_tablo_okuyamaz (yanlis hata: %)', SQLSTATE;
END
$$;

-- Admin yardimcisi yetkiyi SQL icinde yeniden sorar.
SELECT app.admin_api_request_events(
    60, 25, 0, 'POST', '/courses/{course_id}/chat', '5xx',
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
) AS admin_payload \gset

SELECT CASE WHEN
       (:'admin_payload'::jsonb->>'total')::integer = 1
   AND (:'admin_payload'::jsonb->'summary'->>'requests_total')::integer = 1
   AND (:'admin_payload'::jsonb->'summary'->>'server_error_total')::integer = 1
   AND (:'admin_payload'::jsonb->'routes'->0->>'route_template')
       = '/courses/{course_id}/chat'
   AND (:'admin_payload'::jsonb->'items'->0->>'route_template')
       = '/courses/{course_id}/chat'
   AND (SELECT array_agg(key ORDER BY key)
        FROM jsonb_object_keys(:'admin_payload'::jsonb->'items'->0) AS key)
       = ARRAY[
           'created_at', 'duration_ms', 'environment', 'method', 'outcome_code',
           'release_revision', 'request_id', 'route_template', 'service', 'status_code'
         ]::text[]
THEN 'PASS  admin_query__filtreli_exact_guvenli_projeksiyon'
ELSE 'FAIL  admin_query__filtreli_exact_guvenli_projeksiyon' END;

SELECT set_config(
    'app.current_user_id',
    'a1000000-0000-0000-0000-000000000002',
    false
);
DO $$
BEGIN
    PERFORM app.admin_api_request_events(60, 25, 0, NULL, NULL, NULL, NULL);
    RAISE NOTICE 'FAIL  admin_query__normal_kullanici_sql_yardimcisindan_reddedilir';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  admin_query__normal_kullanici_sql_yardimcisindan_reddedilir';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  admin_query__normal_kullanici_sql_yardimcisindan_reddedilir (yanlis hata: %)', SQLSTATE;
END
$$;

SELECT app.audit_platform_admin_access(
    'POST /admin/api-events/query', '11111111111111111111111111111111'
) AS denied_audit \gset
SELECT set_config(
    'app.current_user_id',
    'a1000000-0000-0000-0000-000000000001',
    false
);
SELECT app.audit_platform_admin_access(
    'POST /admin/api-events/query', '22222222222222222222222222222222'
) AS allowed_audit \gset

SELECT CASE WHEN :'denied_audit'::boolean IS FALSE
                  AND :'allowed_audit'::boolean IS TRUE
    THEN 'PASS  admin_audit__yeni_eylem_allowed_denied_kararini_kaydeder'
    ELSE 'FAIL  admin_audit__yeni_eylem_allowed_denied_kararini_kaydeder' END;

SELECT app.audit_platform_admin_access(
    'POST /admin/api-events/query',
    'legacy-client-trace_123'
) AS legacy_audit \gset

SELECT CASE WHEN :'legacy_audit'::boolean IS TRUE
    THEN 'PASS  admin_audit__legacy_header_mixed_surumde_500_uretmez'
    ELSE 'FAIL  admin_audit__legacy_header_mixed_surumde_500_uretmez' END;

RESET SESSION AUTHORIZATION;

SELECT CASE WHEN
       count(*) FILTER (WHERE result = 'allowed') = 2
   AND count(*) FILTER (WHERE result = 'denied') = 1
   AND bool_and(request_id ~ '^[a-f0-9]{32}$')
   AND count(*) FILTER (WHERE request_id = 'legacy-client-trace_123') = 0
THEN 'PASS  admin_audit__uc_karar_append_only_tabloda'
ELSE 'FAIL  admin_audit__uc_karar_append_only_tabloda' END
FROM platform_admin_access_audit
WHERE action = 'POST /admin/api-events/query';

-- Carrier ve worker, GUC ile admin/runtime taklit etse bile dar yuzeylere giremez.
SET SESSION AUTHORIZATION dou_app;
SELECT set_config(
    'app.current_user_id',
    'a1000000-0000-0000-0000-000000000001',
    false
);
DO $$
BEGIN
    PERFORM app.record_api_request_events(
        '[{"request_id":"eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee","service":"api","environment":"demo",
           "release_revision":"010-test","method":"GET","route_template":"/dashboard",
           "status_code":200,"outcome_code":null,"duration_ms":1}]'::jsonb,
        7
    );
    RAISE NOTICE 'FAIL  runtime_writer__carrier_session_user_yazamaz';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  runtime_writer__carrier_session_user_yazamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  runtime_writer__carrier_session_user_yazamaz (yanlis hata: %)', SQLSTATE;
END
$$;
DO $$
BEGIN
    PERFORM count(*) FROM public.api_request_events;
    RAISE NOTICE 'FAIL  rls__carrier_dogrudan_tablo_okuyamaz';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  rls__carrier_dogrudan_tablo_okuyamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  rls__carrier_dogrudan_tablo_okuyamaz (yanlis hata: %)', SQLSTATE;
END
$$;
RESET SESSION AUTHORIZATION;

SET SESSION AUTHORIZATION dou_worker;
DO $$
BEGIN
    PERFORM count(*) FROM public.api_request_events;
    RAISE NOTICE 'FAIL  rls__worker_dogrudan_tablo_okuyamaz';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  rls__worker_dogrudan_tablo_okuyamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  rls__worker_dogrudan_tablo_okuyamaz (yanlis hata: %)', SQLSTATE;
END
$$;
DO $$
BEGIN
    INSERT INTO public.api_request_events (
        request_id, service, environment, release_revision, method, route_template,
        status_code, duration_ms, expires_at
    ) VALUES (
        'ffffffffffffffffffffffffffffffff', 'api', 'demo', '010-worker', 'GET',
        '/dashboard', 200, 1, now() + interval '1 day'
    );
    RAISE NOTICE 'FAIL  rls__worker_dogrudan_tabloya_insert_yapamaz';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  rls__worker_dogrudan_tabloya_insert_yapamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  rls__worker_dogrudan_tabloya_insert_yapamaz (yanlis hata: %)', SQLSTATE;
END
$$;
DO $$
BEGIN
    UPDATE public.api_request_events SET duration_ms = 2;
    RAISE NOTICE 'FAIL  rls__worker_dogrudan_tabloyu_update_edemez';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  rls__worker_dogrudan_tabloyu_update_edemez';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  rls__worker_dogrudan_tabloyu_update_edemez (yanlis hata: %)', SQLSTATE;
END
$$;
DO $$
BEGIN
    DELETE FROM public.api_request_events;
    RAISE NOTICE 'FAIL  rls__worker_dogrudan_tablodan_delete_yapamaz';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  rls__worker_dogrudan_tablodan_delete_yapamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  rls__worker_dogrudan_tablodan_delete_yapamaz (yanlis hata: %)', SQLSTATE;
END
$$;
DO $$
BEGIN
    PERFORM app.record_api_request_events(
        '[{"request_id":"99999999999999999999999999999999","service":"api","environment":"demo",
           "release_revision":"010-test","method":"GET","route_template":"/dashboard",
           "status_code":200,"outcome_code":null,"duration_ms":1}]'::jsonb,
        7
    );
    RAISE NOTICE 'FAIL  runtime_writer__worker_session_user_yazamaz';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'PASS  runtime_writer__worker_session_user_yazamaz';
    WHEN OTHERS THEN
        RAISE NOTICE 'FAIL  runtime_writer__worker_session_user_yazamaz (yanlis hata: %)', SQLSTATE;
END
$$;
RESET SESSION AUTHORIZATION;

-- Purge yalniz suresi dolanlari ve tek cagri limitini asmayacak sekilde siler.
INSERT INTO api_request_events (
    request_id, service, environment, release_revision, method, route_template,
    status_code, outcome_code, duration_ms, created_at, expires_at
) VALUES
    ('11111111111111111111111111111111', 'api', 'demo', '010-expired', 'GET', '/dashboard', 200, NULL, 1,
     now() - interval '2 days', now() - interval '1 day'),
    ('22222222222222222222222222222222', 'api', 'demo', '010-expired', 'GET', '/dashboard', 200, NULL, 1,
     now() - interval '2 days', now() - interval '1 day'),
    ('33333333333333333333333333333333', 'api', 'demo', '010-future', 'GET', '/dashboard', 200, NULL, 1,
     now(), now() + interval '1 day');

SET SESSION AUTHORIZATION dou_api_runtime;
SELECT app.purge_expired_api_request_events(1) AS purged_count \gset
RESET SESSION AUTHORIZATION;

SELECT CASE WHEN :'purged_count'::integer = 1
                  AND count(*) FILTER (WHERE release_revision = '010-expired') = 1
                  AND count(*) FILTER (WHERE release_revision = '010-future') = 1
    THEN 'PASS  purge__bounded_ve_yalniz_suresi_dolan_kayit'
    ELSE 'FAIL  purge__bounded_ve_yalniz_suresi_dolan_kayit' END
FROM api_request_events;

ROLLBACK;
