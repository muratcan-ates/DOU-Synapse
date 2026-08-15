-- DOU-Synapse — role-aware course agent, immutable audience and atomic quotas

BEGIN;

CREATE TYPE assistant_audience AS ENUM ('student', 'instructor');

ALTER TABLE chat_sessions
    ADD COLUMN audience assistant_audience;

UPDATE chat_sessions AS s
SET audience = CASE m.role
    WHEN 'instructor'::membership_role THEN 'instructor'::assistant_audience
    ELSE 'student'::assistant_audience
END
FROM course_memberships AS m
WHERE m.course_id = s.course_id AND m.user_id = s.user_id;

UPDATE chat_sessions SET audience = 'student' WHERE audience IS NULL;
ALTER TABLE chat_sessions ALTER COLUMN audience SET NOT NULL;
ALTER TABLE chat_sessions ALTER COLUMN audience SET DEFAULT 'student';

DROP POLICY chat_sessions_self_insert ON chat_sessions;
CREATE POLICY chat_sessions_self_insert ON chat_sessions
    FOR INSERT WITH CHECK (
        user_id = app.current_user_id()
        AND app.is_member(course_id)
        AND audience = CASE WHEN app.is_instructor(course_id)
            THEN 'instructor'::assistant_audience
            ELSE 'student'::assistant_audience END
    );
DROP POLICY chat_sessions_self_update ON chat_sessions;
CREATE POLICY chat_sessions_self_update ON chat_sessions
    FOR UPDATE USING (user_id = app.current_user_id() AND app.is_member(course_id))
    WITH CHECK (
        user_id = app.current_user_id()
        AND app.is_member(course_id)
        AND audience = CASE WHEN app.is_instructor(course_id)
            THEN 'instructor'::assistant_audience
            ELSE 'student'::assistant_audience END
    );

CREATE OR REPLACE FUNCTION app.chat_session_audience_immutable()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, public, app AS $$
BEGIN
    IF NEW.audience IS DISTINCT FROM OLD.audience THEN
        RAISE EXCEPTION 'chat session audience is immutable' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER chat_session_audience_immutable
BEFORE UPDATE OF audience ON chat_sessions
FOR EACH ROW EXECUTE FUNCTION app.chat_session_audience_immutable();

ALTER TABLE answer_cache
    ADD COLUMN audience assistant_audience NOT NULL DEFAULT 'student',
    ADD COLUMN policy_revision text NOT NULL DEFAULT 'legacy',
    ADD COLUMN prompt_revision text NOT NULL DEFAULT 'legacy',
    ADD COLUMN corpus_revision text NOT NULL DEFAULT 'legacy';

DROP INDEX answer_cache_course_question_key;
CREATE UNIQUE INDEX answer_cache_context_question_key ON answer_cache (
    course_id, audience, policy_revision, prompt_revision, corpus_revision, question_hash
);

DROP POLICY answer_cache_member_insert ON answer_cache;
DROP POLICY answer_cache_member_read ON answer_cache;
-- 0003'teki doğrudan eğitmen DELETE yüzeyi, audience ayrımından sonra güvenli
-- değildir: DELETE satır görünürlüğüne de bağlıdır ve tek bir audience satırını
-- hedefler. Temizlik aşağıdaki SECURITY DEFINER fonksiyonundan, dersin bütün
-- audience/revision kayıtlarını atomik silerek yapılır. BYPASSRLS sahibi worker'ın
-- bütün doğrudan tablo grant'leri de ayrıca kapatılmalıdır; yalnız policy kaldırmak
-- onu durdurmaz.
DROP POLICY answer_cache_instructor_delete ON answer_cache;
REVOKE DELETE ON TABLE answer_cache FROM PUBLIC, dou_app;
REVOKE ALL ON TABLE answer_cache FROM dou_worker;
CREATE POLICY answer_cache_member_read ON answer_cache
    FOR SELECT USING (
        app.is_member(course_id)
        AND audience = CASE WHEN app.is_instructor(course_id)
            THEN 'instructor'::assistant_audience
            ELSE 'student'::assistant_audience END
    );
CREATE POLICY answer_cache_member_insert ON answer_cache
    FOR INSERT WITH CHECK (
        app.is_member(course_id)
        AND audience = CASE WHEN app.is_instructor(course_id)
            THEN 'instructor'::assistant_audience
            ELSE 'student'::assistant_audience END
    );

ALTER TABLE request_logs
    ADD COLUMN audience assistant_audience NOT NULL DEFAULT 'student';

UPDATE request_logs AS l
SET audience = CASE m.role
    WHEN 'instructor'::membership_role THEN 'instructor'::assistant_audience
    ELSE 'student'::assistant_audience
END
FROM course_memberships AS m
WHERE m.course_id = l.course_id AND m.user_id = l.user_id;

DROP POLICY request_logs_self_insert ON request_logs;
CREATE POLICY request_logs_self_insert ON request_logs
    FOR INSERT WITH CHECK (
        user_id = app.current_user_id()
        AND app.is_member(course_id)
        AND audience = CASE WHEN app.is_instructor(course_id)
            THEN 'instructor'::assistant_audience
            ELSE 'student'::assistant_audience END
    );

CREATE OR REPLACE FUNCTION app.invalidate_course_agent_cache(p_course_id uuid)
RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public, app
AS $$
BEGIN
    IF NOT app.is_instructor(p_course_id) THEN
        RAISE EXCEPTION 'instructor membership required' USING ERRCODE = '42501';
    END IF;
    DELETE FROM public.answer_cache WHERE course_id = p_course_id;
END
$$;

REVOKE ALL ON FUNCTION app.invalidate_course_agent_cache(uuid) FROM PUBLIC, dou_worker;
GRANT EXECUTE ON FUNCTION app.invalidate_course_agent_cache(uuid) TO dou_app;

ALTER TABLE course_ai_policies
    ADD COLUMN student_daily_token_budget integer NOT NULL DEFAULT 12000
        CHECK (student_daily_token_budget > 0),
    ADD COLUMN instructor_daily_token_budget integer NOT NULL DEFAULT 40000
        CHECK (instructor_daily_token_budget > 0),
    ADD COLUMN max_output_tokens integer NOT NULL DEFAULT 700
        CHECK (max_output_tokens BETWEEN 64 AND 4096),
    ADD COLUMN max_concurrent_requests smallint NOT NULL DEFAULT 1
        CHECK (max_concurrent_requests BETWEEN 1 AND 4);

CREATE TABLE ai_token_reservations (
    id uuid PRIMARY KEY,
    course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    audience assistant_audience NOT NULL,
    reserved_tokens integer NOT NULL CHECK (reserved_tokens > 0),
    charged_tokens integer NOT NULL CHECK (charged_tokens >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    reconciled_at timestamptz,
    CONSTRAINT ai_token_reservation_expiry CHECK (expires_at > created_at)
);

CREATE INDEX ai_token_reservations_course_day_idx
    ON ai_token_reservations (course_id, created_at);
CREATE INDEX ai_token_reservations_user_day_idx
    ON ai_token_reservations (course_id, user_id, created_at);
CREATE INDEX ai_token_reservations_global_user_day_idx
    ON ai_token_reservations (user_id, created_at);
CREATE INDEX ai_token_reservations_platform_day_idx
    ON ai_token_reservations (created_at);

CREATE TABLE ai_guard_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    audience assistant_audience NOT NULL,
    event_type text NOT NULL CHECK (event_type IN (
        'rate_limited', 'quota_exhausted', 'concurrency_limited', 'scope_refused'
    )),
    bucket_start timestamptz NOT NULL DEFAULT date_trunc('minute', now()),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ai_guard_events_one_per_bucket
        UNIQUE (course_id, user_id, event_type, bucket_start)
);

CREATE INDEX ai_guard_events_course_idx ON ai_guard_events (course_id, created_at DESC);

ALTER TABLE ai_token_reservations ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_guard_events ENABLE ROW LEVEL SECURITY;

-- These tables are function-only. There are deliberately no RLS policies and
-- no direct grants: neither students nor instructors can read individual usage.
REVOKE ALL ON ai_token_reservations, ai_guard_events FROM PUBLIC, dou_app, dou_worker;

-- 0009 originally derived this number from request_logs. The atomic ledger is
-- now the billing authority: a provider error intentionally leaves its full
-- conservative reservation charged, and the course policy is shared by every
-- member, so the UI/precheck must see the whole course total instead of a
-- lower per-user or request-log total.
CREATE OR REPLACE FUNCTION app.course_tokens_today(p_course_id uuid)
RETURNS bigint
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public, app
AS $$
BEGIN
    IF NOT app.is_member(p_course_id) THEN
        RAISE EXCEPTION 'course membership required' USING ERRCODE = '42501';
    END IF;
    RETURN (
        SELECT COALESCE(sum(r.charged_tokens), 0)::bigint
        FROM public.ai_token_reservations AS r
        WHERE r.course_id = p_course_id
          AND r.created_at >= (
              date_trunc('day', now() AT TIME ZONE 'Europe/Istanbul')
              AT TIME ZONE 'Europe/Istanbul'
          )
          AND r.created_at < (
              (date_trunc('day', now() AT TIME ZONE 'Europe/Istanbul') + interval '1 day')
              AT TIME ZONE 'Europe/Istanbul'
          )
    );
END
$$;

REVOKE ALL ON FUNCTION app.course_tokens_today(uuid) FROM PUBLIC, dou_worker;
GRANT EXECUTE ON FUNCTION app.course_tokens_today(uuid) TO dou_app;

CREATE OR REPLACE FUNCTION app.reserve_course_agent_tokens(
    p_course_id uuid,
    p_reservation_id uuid,
    p_requested_tokens integer,
    p_lease_seconds integer,
    p_user_hard_limit integer,
    p_course_hard_limit integer,
    p_platform_hard_limit integer
)
RETURNS TABLE (
    allowed boolean,
    reason text,
    audience assistant_audience,
    retry_after_seconds integer,
    reservation_id uuid
)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public, app
AS $$
DECLARE
    v_user_id uuid := app.current_user_id();
    v_role membership_role;
    v_audience assistant_audience;
    v_course_budget integer;
    v_user_budget integer;
    v_role_hard_ceiling integer;
    v_max_concurrent integer;
    v_course_used bigint;
    v_user_used bigint;
    v_global_user_used bigint;
    v_platform_used bigint;
    v_active integer;
    v_retry integer;
    v_day_start timestamptz := date_trunc('day', now() AT TIME ZONE 'Europe/Istanbul')
        AT TIME ZONE 'Europe/Istanbul';
    v_day_end timestamptz := (date_trunc('day', now() AT TIME ZONE 'Europe/Istanbul')
        + interval '1 day') AT TIME ZONE 'Europe/Istanbul';
BEGIN
    IF p_requested_tokens <= 0 OR p_requested_tokens > 100000 THEN
        RAISE EXCEPTION 'invalid token reservation' USING ERRCODE = '22023';
    END IF;
    IF p_lease_seconds < 30 OR p_lease_seconds > 600 THEN
        RAISE EXCEPTION 'invalid reservation lease' USING ERRCODE = '22023';
    END IF;
    IF p_user_hard_limit <= 0 OR p_user_hard_limit > 1000000 THEN
        RAISE EXCEPTION 'invalid platform user budget' USING ERRCODE = '22023';
    END IF;
    IF p_course_hard_limit <= 0 OR p_course_hard_limit > 500000 THEN
        RAISE EXCEPTION 'invalid platform course budget' USING ERRCODE = '22023';
    END IF;
    IF p_platform_hard_limit <= 0 OR p_platform_hard_limit > 5000000 THEN
        RAISE EXCEPTION 'invalid platform aggregate budget' USING ERRCODE = '22023';
    END IF;

    SELECT m.role INTO v_role
    FROM public.course_memberships AS m
    WHERE m.course_id = p_course_id AND m.user_id = v_user_id
      AND m.status = 'active'::membership_status;
    IF v_role IS NULL THEN
        RAISE EXCEPTION 'course membership required' USING ERRCODE = '42501';
    END IF;
    v_audience := CASE v_role
        WHEN 'instructor'::membership_role THEN 'instructor'::assistant_audience
        ELSE 'student'::assistant_audience
    END;
    v_role_hard_ceiling := CASE v_audience
        WHEN 'instructor' THEN 200000
        ELSE 50000
    END;
    IF p_user_hard_limit > v_role_hard_ceiling THEN
        RAISE EXCEPTION 'platform user budget exceeds database ceiling'
            USING ERRCODE = '22023';
    END IF;

    SELECT p.daily_token_budget,
           CASE v_audience
               WHEN 'instructor' THEN p.instructor_daily_token_budget
               ELSE p.student_daily_token_budget
           END,
           p.max_concurrent_requests
    INTO v_course_budget, v_user_budget, v_max_concurrent
    FROM public.course_ai_policies AS p WHERE p.course_id = p_course_id;
    v_user_budget := COALESCE(v_user_budget, CASE v_audience WHEN 'instructor' THEN 40000 ELSE 12000 END);
    v_course_budget := LEAST(COALESCE(v_course_budget, p_course_hard_limit), p_course_hard_limit);
    v_max_concurrent := COALESCE(v_max_concurrent, 1);

    -- The reservation enforces course, cross-course user and platform totals.
    -- A course-only lock would let two different courses read the same stale
    -- user/platform totals and jointly exceed a hard ceiling. The fixed lock
    -- serializes only these short reservation transactions; it is committed
    -- before provider I/O and therefore never spans the slow LLM call.
    PERFORM pg_advisory_xact_lock(hashtextextended('course-agent-platform-daily', 15015));
    PERFORM pg_advisory_xact_lock(hashtextextended(p_course_id::text, 15016));

    SELECT count(*)::integer, COALESCE(EXTRACT(EPOCH FROM min(r.expires_at) - now()), 1)::integer
    INTO v_active, v_retry
    FROM public.ai_token_reservations AS r
    WHERE r.course_id = p_course_id AND r.user_id = v_user_id
      AND r.reconciled_at IS NULL AND r.expires_at > now();
    IF v_active >= v_max_concurrent THEN
        INSERT INTO public.ai_guard_events(course_id, user_id, audience, event_type)
        VALUES (p_course_id, v_user_id, v_audience, 'concurrency_limited')
        ON CONFLICT (course_id, user_id, event_type, bucket_start) DO NOTHING;
        RETURN QUERY SELECT false, 'concurrency_limited', v_audience, GREATEST(v_retry, 1), NULL::uuid;
        RETURN;
    END IF;

    SELECT COALESCE(sum(r.charged_tokens), 0) INTO v_course_used
    FROM public.ai_token_reservations AS r
    WHERE r.course_id = p_course_id AND r.created_at >= v_day_start AND r.created_at < v_day_end;
    SELECT COALESCE(sum(r.charged_tokens), 0) INTO v_user_used
    FROM public.ai_token_reservations AS r
    WHERE r.course_id = p_course_id AND r.user_id = v_user_id
      AND r.created_at >= v_day_start AND r.created_at < v_day_end;
    SELECT COALESCE(sum(r.charged_tokens), 0) INTO v_global_user_used
    FROM public.ai_token_reservations AS r
    WHERE r.user_id = v_user_id
      AND r.created_at >= v_day_start AND r.created_at < v_day_end;
    SELECT COALESCE(sum(r.charged_tokens), 0) INTO v_platform_used
    FROM public.ai_token_reservations AS r
    WHERE r.created_at >= v_day_start AND r.created_at < v_day_end;

    IF v_user_used + p_requested_tokens > v_user_budget
       OR v_global_user_used + p_requested_tokens > p_user_hard_limit
       OR v_course_used + p_requested_tokens > v_course_budget
       OR v_platform_used + p_requested_tokens > p_platform_hard_limit THEN
        INSERT INTO public.ai_guard_events(course_id, user_id, audience, event_type)
        VALUES (p_course_id, v_user_id, v_audience, 'quota_exhausted')
        ON CONFLICT (course_id, user_id, event_type, bucket_start) DO NOTHING;
        v_retry := GREATEST(1, EXTRACT(EPOCH FROM v_day_end - now())::integer);
        RETURN QUERY SELECT false, 'quota_exhausted', v_audience, v_retry, NULL::uuid;
        RETURN;
    END IF;

    INSERT INTO public.ai_token_reservations(
        id, course_id, user_id, audience, reserved_tokens, charged_tokens, expires_at
    ) VALUES (
        p_reservation_id, p_course_id, v_user_id, v_audience,
        p_requested_tokens, p_requested_tokens, now() + make_interval(secs => p_lease_seconds)
    );
    RETURN QUERY SELECT true, NULL::text, v_audience, 0, p_reservation_id;
END
$$;

CREATE OR REPLACE FUNCTION app.reconcile_course_agent_tokens(
    p_reservation_id uuid,
    p_actual_tokens integer
)
RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public, app
AS $$
DECLARE
    v_user_id uuid := app.current_user_id();
    v_course_id uuid;
    v_reserved_tokens integer;
BEGIN
    IF p_actual_tokens < 0 OR p_actual_tokens > 100000 THEN
        RAISE EXCEPTION 'invalid actual token count' USING ERRCODE = '22023';
    END IF;
    SELECT r.course_id, r.reserved_tokens INTO v_course_id, v_reserved_tokens
    FROM public.ai_token_reservations AS r
    WHERE r.id = p_reservation_id AND r.user_id = v_user_id;
    IF v_course_id IS NULL THEN
        RAISE EXCEPTION 'reservation not found' USING ERRCODE = '42501';
    END IF;
    IF p_actual_tokens > v_reserved_tokens THEN
        RAISE EXCEPTION 'actual token count exceeds reservation' USING ERRCODE = '22023';
    END IF;
    -- Use the same deterministic order as reservation. A concurrent refund
    -- may otherwise make the aggregate snapshot depend on transaction timing.
    PERFORM pg_advisory_xact_lock(hashtextextended('course-agent-platform-daily', 15015));
    PERFORM pg_advisory_xact_lock(hashtextextended(v_course_id::text, 15016));
    UPDATE public.ai_token_reservations
    SET charged_tokens = p_actual_tokens, reconciled_at = now()
    WHERE id = p_reservation_id AND user_id = v_user_id AND reconciled_at IS NULL;
END
$$;

CREATE OR REPLACE FUNCTION app.record_course_agent_guard_event(
    p_course_id uuid,
    p_event_type text
)
RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public, app
AS $$
DECLARE
    v_user_id uuid := app.current_user_id();
    v_role membership_role;
BEGIN
    IF p_event_type NOT IN ('rate_limited', 'scope_refused', 'concurrency_limited') THEN
        RAISE EXCEPTION 'unsupported guard event' USING ERRCODE = '22023';
    END IF;
    SELECT m.role INTO v_role FROM public.course_memberships AS m
    WHERE m.course_id = p_course_id AND m.user_id = v_user_id
      AND m.status = 'active'::membership_status;
    IF v_role IS NULL THEN
        RAISE EXCEPTION 'course membership required' USING ERRCODE = '42501';
    END IF;
    INSERT INTO public.ai_guard_events(course_id, user_id, audience, event_type)
    VALUES (
        p_course_id, v_user_id,
        CASE v_role WHEN 'instructor' THEN 'instructor'::assistant_audience
                    ELSE 'student'::assistant_audience END,
        p_event_type
    ) ON CONFLICT (course_id, user_id, event_type, bucket_start) DO NOTHING;
END
$$;

REVOKE ALL ON FUNCTION app.reserve_course_agent_tokens(uuid, uuid, integer, integer, integer, integer, integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.reconcile_course_agent_tokens(uuid, integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.record_course_agent_guard_event(uuid, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.reserve_course_agent_tokens(uuid, uuid, integer, integer, integer, integer, integer) TO dou_app;
GRANT EXECUTE ON FUNCTION app.reconcile_course_agent_tokens(uuid, integer) TO dou_app;
GRANT EXECUTE ON FUNCTION app.record_course_agent_guard_event(uuid, text) TO dou_app;

REVOKE ALL ON FUNCTION app.reserve_course_agent_tokens(uuid, uuid, integer, integer, integer, integer, integer) FROM dou_worker;
REVOKE ALL ON FUNCTION app.reconcile_course_agent_tokens(uuid, integer) FROM dou_worker;
REVOKE ALL ON FUNCTION app.record_course_agent_guard_event(uuid, text) FROM dou_worker;

COMMENT ON TABLE ai_guard_events IS
    'Content-free abuse telemetry, deduplicated per user/course/event/minute. Never stores prompts, answers, citations, IP addresses or headers. Retention is an external operations responsibility; this migration does not claim automatic purge.';

COMMIT;
