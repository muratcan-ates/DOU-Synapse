-- 0025: shared request admission; follows the published 0024 lifecycle migration.
-- Function-only, pseudonymous abuse-prevention state. Not provider token usage.
-- Explicit pg_temp-last prevents implicit temporary relation/type shadowing.
-- Existing migration-owner/BYPASSRLS model is required for the membership check.

CREATE TABLE app.request_rate_policies (
    scope text PRIMARY KEY CHECK (scope IN ('chat', 'qgen')),
    request_limit integer NOT NULL CHECK (request_limit BETWEEN 1 AND 100),
    window_ms integer NOT NULL CHECK (window_ms BETWEEN 1 AND 3600000)
);

-- Canonical deployment policy. Different worker settings FAIL CLOSED; they
-- cannot invent a second fingerprint-keyed budget. No application update API.
-- Changing these values requires a drained, deliberate DBA rollout (see docs).
INSERT INTO app.request_rate_policies(scope, request_limit, window_ms)
VALUES ('chat', 20, 60000), ('qgen', 5, 300000);

CREATE TABLE app.rate_limit_windows (
    scope text NOT NULL REFERENCES app.request_rate_policies(scope),
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    course_id uuid NOT NULL REFERENCES public.courses(id) ON DELETE CASCADE,
    policy_fingerprint text NOT NULL CHECK (policy_fingerprint ~ '^[0-9a-f]{64}$'),
    accepted_at timestamptz[] NOT NULL,
    expires_at timestamptz NOT NULL,
    PRIMARY KEY (scope, user_id, course_id),
    CHECK (cardinality(accepted_at) BETWEEN 1 AND 100),
    CHECK (array_ndims(accepted_at) = 1 AND array_lower(accepted_at, 1) = 1),
    CHECK (array_position(accepted_at, NULL) IS NULL)
);
CREATE INDEX rate_limit_windows_expiry_idx ON app.rate_limit_windows(expires_at);
COMMENT ON TABLE app.rate_limit_windows IS
    'Pseudonymous user/course IDs and accepted-request timestamps; personal data, '
    'not anonymous. No content/IP/header/token. Logical expiry is immediate; '
    'physical retention ends only after successful bounded maintenance or FK deletion.';
ALTER TABLE app.request_rate_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.rate_limit_windows ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app.request_rate_policies, app.rate_limit_windows FROM PUBLIC, dou_app, dou_worker;

CREATE FUNCTION app.request_quota_policies()
RETURNS TABLE(scope text, fingerprint text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT p.scope,
           pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
               p.scope || ':' || p.request_limit::text || ':' || p.window_ms::text,
               'UTF8'
           )), 'hex')
    FROM app.request_rate_policies AS p
$$;
REVOKE ALL ON FUNCTION app.request_quota_policies() FROM PUBLIC, dou_worker;
GRANT EXECUTE ON FUNCTION app.request_quota_policies() TO dou_app;

CREATE FUNCTION app.take_request_slot(
    p_course_id uuid,
    p_scope text,
    p_limit integer,
    p_window_ms integer,
    p_fingerprint text
)
RETURNS TABLE(allowed boolean, reason text, retry_after_seconds integer)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    v_user_id uuid := app.current_user_id();
    v_role public.membership_role;
    v_limit integer;
    v_window_ms integer;
    v_fingerprint text;
    v_stored_fingerprint text;
    v_hits timestamptz[];
    v_active timestamptz[];
    v_now timestamptz;
    v_window interval;
    v_retry integer;
BEGIN
    IF p_scope IS NULL OR p_scope NOT IN ('chat', 'qgen')
       OR p_limit IS NULL OR p_limit NOT BETWEEN 1 AND 100
       OR p_window_ms IS NULL OR p_window_ms NOT BETWEEN 1 AND 3600000
       OR p_fingerprint IS NULL OR p_fingerprint !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'invalid request policy' USING ERRCODE = '22023';
    END IF;
    IF v_user_id IS NULL OR p_course_id IS NULL THEN
        RETURN QUERY SELECT false, 'not_member'::text, 0;
        RETURN;
    END IF;
    -- Hold this membership decision through the short control commit. FOR SHARE
    -- conflicts with status/role revocation, unlike FOR KEY SHARE.
    SELECT m.role INTO v_role
    FROM public.course_memberships AS m
    WHERE m.course_id = p_course_id AND m.user_id = v_user_id
      AND m.status = 'active'::public.membership_status
    FOR SHARE OF m;
    IF v_role IS NULL THEN
        RETURN QUERY SELECT false, 'not_member'::text, 0;
        RETURN;
    END IF;
    IF p_scope = 'qgen' AND v_role <> 'instructor'::public.membership_role THEN
        RETURN QUERY SELECT false, 'not_instructor'::text, 0;
        RETURN;
    END IF;

    -- Concurrent readers do not serialize different users. An operator cannot
    -- modify the canonical policy mid-admission; ordinary app roles cannot
    -- modify it at all. This is NOT a live-policy-reconfiguration procedure.
    SELECT p.request_limit, p.window_ms INTO v_limit, v_window_ms
    FROM app.request_rate_policies AS p WHERE p.scope = p_scope FOR SHARE OF p;
    v_fingerprint := pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
        p_scope || ':' || v_limit::text || ':' || v_window_ms::text, 'UTF8'
    )), 'hex');
    IF v_limit IS NULL OR v_limit <> p_limit OR v_window_ms <> p_window_ms
       OR v_fingerprint IS DISTINCT FROM p_fingerprint THEN
        RETURN QUERY SELECT false, 'policy_mismatch'::text, 0;
        RETURN;
    END IF;

    -- Short per-(scope,user,course) transaction lock. Hash collisions cause
    -- conservative extra waiting, never extra acceptance. Namespace 15023 is
    -- reserved for request admission/expiry. No provider work is inside this function.
    PERFORM pg_catalog.pg_advisory_xact_lock(
        15023, pg_catalog.hashtext(p_scope || ':' || v_user_id::text || ':' || p_course_id::text)
    );
    SELECT w.accepted_at, w.policy_fingerprint INTO v_hits, v_stored_fingerprint
    FROM app.rate_limit_windows AS w
    WHERE w.scope = p_scope AND w.user_id = v_user_id AND w.course_id = p_course_id
    FOR UPDATE OF w;
    -- Unlike now(), this timestamp includes advisory AND row-lock waiting.
    v_now := pg_catalog.clock_timestamp();
    v_window := v_window_ms * interval '1 millisecond';
    -- Existing state cannot be reinterpreted/reset by silently switching policy.
    -- Expired rows with an old fingerprint require maintenance/rollout too.
    IF v_stored_fingerprint IS NOT NULL AND v_stored_fingerprint <> v_fingerprint THEN
        RETURN QUERY SELECT false, 'policy_mismatch'::text, 0;
        RETURN;
    END IF;
    SELECT COALESCE(pg_catalog.array_agg(h ORDER BY h), ARRAY[]::timestamptz[])
    INTO v_active FROM pg_catalog.unnest(COALESCE(v_hits, ARRAY[]::timestamptz[])) AS h
    WHERE h > v_now - v_window; -- Exact boundary is expired: (now-window, now].

    IF pg_catalog.cardinality(v_active) >= v_limit THEN
        v_retry := GREATEST(1, LEAST(3600, pg_catalog.ceil(
            EXTRACT(EPOCH FROM (v_active[1] + v_window - v_now))
        )::integer));
        -- Denied requests do not append a timestamp, write a row or extend TTL.
        RETURN QUERY SELECT false, 'rate_limited'::text, v_retry;
        RETURN;
    END IF;
    v_active := pg_catalog.array_append(v_active, v_now);
    INSERT INTO app.rate_limit_windows AS existing
        (scope, user_id, course_id, policy_fingerprint, accepted_at, expires_at)
    VALUES (p_scope, v_user_id, p_course_id, v_fingerprint, v_active,
            (SELECT max(h) FROM pg_catalog.unnest(v_active) AS h) + v_window)
    ON CONFLICT (scope, user_id, course_id) DO UPDATE
        SET accepted_at = EXCLUDED.accepted_at, expires_at = EXCLUDED.expires_at;
    RETURN QUERY SELECT true, 'accepted'::text, 0;
END
$$;
REVOKE ALL ON FUNCTION app.take_request_slot(uuid, text, integer, integer, text)
    FROM PUBLIC, dou_worker;
GRANT EXECUTE ON FUNCTION app.take_request_slot(uuid, text, integer, integer, text) TO dou_app;

CREATE FUNCTION app.purge_expired_request_windows(p_batch_size integer)
RETURNS integer
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    v_count integer;
    v_now timestamptz := pg_catalog.clock_timestamp();
BEGIN
    IF p_batch_size IS NULL OR p_batch_size NOT BETWEEN 1 AND 1000 THEN
        RAISE EXCEPTION 'invalid quota maintenance batch' USING ERRCODE = '22023';
    END IF;
    IF NOT pg_catalog.pg_try_advisory_xact_lock(15023, 0) THEN
        RETURN 0;
    END IF;
    WITH expired AS (
        SELECT w.scope, w.user_id, w.course_id FROM app.rate_limit_windows AS w
        WHERE w.expires_at <= v_now ORDER BY w.expires_at
        LIMIT p_batch_size FOR UPDATE OF w SKIP LOCKED
    )
    DELETE FROM app.rate_limit_windows AS w USING expired AS e
    WHERE w.scope = e.scope AND w.user_id = e.user_id AND w.course_id = e.course_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END
$$;
REVOKE ALL ON FUNCTION app.purge_expired_request_windows(integer) FROM PUBLIC, dou_app;
GRANT EXECUTE ON FUNCTION app.purge_expired_request_windows(integer) TO dou_worker;
