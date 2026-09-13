-- Öğrenme olayları kimlik ve içerik taşımayan, xAPI'ye eşlenebilir ölçümlerdir.
-- Eğitmen yalnız konu toplamlarını görür; ham öğrenci satırları açılmaz.
BEGIN;

CREATE TABLE app.learning_event_secret (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    secret bytea NOT NULL CHECK (octet_length(secret) = 32)
);
REVOKE ALL ON app.learning_event_secret FROM PUBLIC, dou_app, dou_worker;
GRANT SELECT ON app.learning_event_secret TO dou_worker;

-- pgcrypto Supabase'de extensions, yerelde public şemasında olabilir. Gerçek
-- eklenti şemasını göç anında bağlarız; çağıran search_path ile değiştiremez.
DO $migration$
DECLARE
    crypto_schema text;
BEGIN
    SELECT n.nspname INTO STRICT crypto_schema
    FROM pg_catalog.pg_extension e
    JOIN pg_catalog.pg_namespace n ON n.oid = e.extnamespace
    WHERE e.extname = 'pgcrypto';
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO dou_worker', crypto_schema);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %I.hmac(bytea, bytea, text) TO dou_worker', crypto_schema);
    EXECUTE format('INSERT INTO app.learning_event_secret(secret) SELECT %I.gen_random_bytes(32)', crypto_schema);
    EXECUTE format($definition$
        CREATE FUNCTION app.learning_actor_pseudo_id(p_course_id uuid) RETURNS uuid
        LANGUAGE plpgsql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, app
        AS $function$
        DECLARE
            result uuid;
        BEGIN
            IF p_course_id IS NULL OR app.current_user_id() IS NULL OR NOT app.is_member(p_course_id) THEN
                RAISE EXCEPTION 'öğrenme olayı için aktif ders üyeliği gerekli'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            SELECT substr(encode(%I.hmac(
                convert_to(p_course_id::text || ':' || app.current_user_id()::text, 'UTF8'),
                s.secret, 'sha256'), 'hex'), 1, 32)::uuid INTO STRICT result
            FROM app.learning_event_secret s WHERE s.singleton;
            RETURN result;
        END
        $function$
    $definition$, crypto_schema);
END
$migration$;
REVOKE ALL ON FUNCTION app.learning_actor_pseudo_id(uuid) FROM PUBLIC, dou_app, dou_worker;
GRANT EXECUTE ON FUNCTION app.learning_actor_pseudo_id(uuid) TO dou_app, dou_worker;
ALTER FUNCTION app.learning_actor_pseudo_id(uuid) OWNER TO dou_worker;

CREATE TABLE public.learning_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    occurred_at timestamptz NOT NULL DEFAULT now(),
    actor_pseudo_id uuid NOT NULL,
    course_id uuid NOT NULL REFERENCES public.courses(id) ON DELETE CASCADE,
    topic_id uuid REFERENCES public.topics(id) ON DELETE SET NULL,
    session_id uuid,
    event_type text NOT NULL CHECK (event_type IN (
        'question_presented', 'answer_submitted', 'hint_requested',
        'citation_opened', 'unsupported_refusal', 'provider_rate_limited'
    )),
    object_type text CHECK (object_type IN ('question', 'chunk', 'chat_message')),
    object_id text,
    outcome_json jsonb,
    evidence_chunk_ids uuid[] CHECK (cardinality(evidence_chunk_ids) <= 32),
    latency_ms integer CHECK (latency_ms BETWEEN 0 AND 3600000),
    model_id text CHECK (model_id ~ '^[A-Za-z0-9_./:-]{1,120}$'),
    metadata_json jsonb,
    CONSTRAINT learning_events_object_pair CHECK (
        (object_type IS NULL AND object_id IS NULL) OR
        (object_type IS NOT NULL AND object_id IS NOT NULL AND
         object_id ~ '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
    ),
    -- Serbest metin, ad, e-posta ve yanıt bu JSON alanlarına da saklanamaz.
    CONSTRAINT learning_events_outcome_shape CHECK (outcome_json IS NULL OR (
        jsonb_typeof(outcome_json) = 'object' AND
        outcome_json - ARRAY['is_correct', 'score', 'hint_level', 'fixture'] = '{}'::jsonb AND
        (NOT outcome_json ? 'is_correct' OR jsonb_typeof(outcome_json->'is_correct') IN ('boolean', 'null')) AND
        (NOT outcome_json ? 'fixture' OR jsonb_typeof(outcome_json->'fixture') = 'boolean') AND
        CASE WHEN NOT outcome_json ? 'score' OR outcome_json->'score' = 'null'::jsonb THEN true
             WHEN jsonb_typeof(outcome_json->'score') = 'number'
             THEN (outcome_json->>'score')::numeric BETWEEN 0 AND 100 ELSE false END AND
        CASE WHEN NOT outcome_json ? 'hint_level' THEN true
             WHEN jsonb_typeof(outcome_json->'hint_level') = 'number'
             THEN (outcome_json->>'hint_level')::numeric IN (0, 1, 2, 3, 4) ELSE false END
    )),
    CONSTRAINT learning_events_metadata_shape CHECK (metadata_json IS NULL OR (
        jsonb_typeof(metadata_json) = 'object' AND
        metadata_json - 'source' = '{}'::jsonb AND
        (NOT metadata_json ? 'source' OR metadata_json->>'source' IN ('exam', 'chat', 'citation'))
    ))
);
CREATE INDEX learning_events_course_occurred_idx ON public.learning_events(course_id, occurred_at DESC);
CREATE INDEX learning_events_actor_session_idx ON public.learning_events(course_id, actor_pseudo_id, session_id);
ALTER TABLE public.learning_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.learning_events FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.learning_events FROM PUBLIC, dou_app, dou_worker;
GRANT SELECT (id, occurred_at, actor_pseudo_id, course_id, topic_id, session_id, event_type)
    ON public.learning_events TO dou_app;
GRANT SELECT, INSERT ON public.learning_events TO dou_worker;
CREATE POLICY learning_events_self_read ON public.learning_events FOR SELECT TO dou_app
    USING (app.is_member(course_id) AND NOT app.is_instructor(course_id)
        AND actor_pseudo_id = app.learning_actor_pseudo_id(course_id));

-- INSERT yalnız worker yetkisiyle gerçekleşir. API ayrı worker bağlantısı açmaz:
-- henüz commit edilmemiş sınav/cevap aynı işlemde görülür ve olay onunla atomiktir.
CREATE FUNCTION app.record_learning_event(
    p_course_id uuid,
    p_event_type text,
    p_topic_id uuid DEFAULT NULL,
    p_session_id uuid DEFAULT NULL,
    p_object_type text DEFAULT NULL,
    p_object_id text DEFAULT NULL,
    p_outcome_json jsonb DEFAULT NULL,
    p_evidence_chunk_ids uuid[] DEFAULT NULL,
    p_latency_ms integer DEFAULT NULL,
    p_model_id text DEFAULT NULL,
    p_metadata_json jsonb DEFAULT NULL
) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, app
AS $$
DECLARE
    v_actor uuid;
    v_event_id uuid;
    v_exam boolean := false;
    v_chat boolean := false;
    v_object uuid;
BEGIN
    v_actor := app.learning_actor_pseudo_id(p_course_id);
    IF p_event_type IS NULL OR p_event_type NOT IN (
        'question_presented', 'answer_submitted', 'hint_requested',
        'citation_opened', 'unsupported_refusal', 'provider_rate_limited'
    ) THEN
        RAISE EXCEPTION 'geçersiz öğrenme olayı' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF p_topic_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM public.topics t WHERE t.id = p_topic_id AND t.course_id = p_course_id
    ) THEN
        RAISE EXCEPTION 'konu ders kapsamında değil' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_session_id IS NOT NULL THEN
        SELECT EXISTS (SELECT 1 FROM public.exam_sessions s
            WHERE s.id = p_session_id AND s.course_id = p_course_id AND s.user_id = app.current_user_id())
            INTO v_exam;
        SELECT EXISTS (SELECT 1 FROM public.chat_sessions s
            WHERE s.id = p_session_id AND s.course_id = p_course_id AND s.user_id = app.current_user_id())
            INTO v_chat;
        IF NOT v_exam AND NOT v_chat THEN
            RAISE EXCEPTION 'oturum çağırana ve derse ait değil' USING ERRCODE = 'insufficient_privilege';
        END IF;
    END IF;
    IF p_object_id IS NOT NULL THEN
        v_object := p_object_id::uuid;
        IF p_object_type = 'question' AND EXISTS (
            SELECT 1 FROM public.questions q
            JOIN public.exam_sessions s ON s.id = p_session_id
            WHERE q.id = v_object AND q.course_id = p_course_id
              AND (p_topic_id IS NULL OR q.topic_id = p_topic_id)
              AND (q.id = ANY(s.question_ids) OR EXISTS (
                SELECT 1 FROM public.exam_items i WHERE i.exam_version_id = s.exam_version_id
                    AND i.question_id = q.id AND i.course_id = p_course_id
              ))
        ) AND v_exam THEN
            NULL;
        ELSIF p_object_type = 'chunk' AND EXISTS (
            SELECT 1 FROM public.chunks c WHERE c.id = v_object AND c.course_id = p_course_id
        ) THEN
            NULL;
        ELSIF p_object_type = 'chat_message' AND v_chat AND EXISTS (
            SELECT 1 FROM public.chat_messages m WHERE m.id = v_object
                AND m.course_id = p_course_id AND m.session_id = p_session_id
        ) THEN
            NULL;
        ELSE
            RAISE EXCEPTION 'olay nesnesi çağıranın ders ve oturum kapsamında değil'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
    END IF;
    IF p_event_type IN ('question_presented', 'answer_submitted') AND
       (NOT v_exam OR p_object_type IS DISTINCT FROM 'question' OR p_object_id IS NULL) THEN
        RAISE EXCEPTION 'soru olayı kendi sınavındaki soruya bağlanmalı' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF p_event_type = 'hint_requested' AND NOT v_exam AND NOT v_chat
       AND (p_metadata_json->>'source') IS DISTINCT FROM 'chat' THEN
        RAISE EXCEPTION 'ipucu olayı kendi oturumuna bağlanmalı' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF p_event_type = 'citation_opened' AND
       (p_object_type IS DISTINCT FROM 'chunk' OR p_object_id IS NULL) THEN
        RAISE EXCEPTION 'kaynak olayı bir kaynak parçasına bağlanmalı' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF p_evidence_chunk_ids IS NOT NULL AND (
        cardinality(p_evidence_chunk_ids) > 32 OR
        EXISTS (SELECT 1 FROM unnest(p_evidence_chunk_ids) cid WHERE cid IS NULL OR NOT EXISTS (
            SELECT 1 FROM public.chunks c WHERE c.id = cid AND c.course_id = p_course_id
        ))
    ) THEN
        RAISE EXCEPTION 'kanıt ders kapsamında değil' USING ERRCODE = 'insufficient_privilege';
    END IF;
    INSERT INTO public.learning_events (
        actor_pseudo_id, course_id, topic_id, session_id, event_type, object_type,
        object_id, outcome_json, evidence_chunk_ids, latency_ms, model_id, metadata_json
    ) VALUES (
        v_actor, p_course_id, p_topic_id, p_session_id, p_event_type, p_object_type,
        p_object_id, p_outcome_json, p_evidence_chunk_ids, p_latency_ms, p_model_id, p_metadata_json
    ) RETURNING id INTO v_event_id;
    RETURN v_event_id;
END
$$;
REVOKE ALL ON FUNCTION app.record_learning_event(uuid, text, uuid, uuid, text, text, jsonb, uuid[], integer, text, jsonb)
    FROM PUBLIC, dou_app, dou_worker;
GRANT EXECUTE ON FUNCTION app.record_learning_event(uuid, text, uuid, uuid, text, text, jsonb, uuid[], integer, text, jsonb)
    TO dou_app;
ALTER FUNCTION app.record_learning_event(uuid, text, uuid, uuid, text, text, jsonb, uuid[], integer, text, jsonb)
    OWNER TO dou_worker;

CREATE FUNCTION app.learning_summary(p_course_id uuid, p_days integer)
RETURNS TABLE(topic_id uuid, topic_name text, event_count bigint,
    wrong_answers bigint, hints_requested bigint, unsupported_refusals bigint)
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, app
AS $$
BEGIN
    IF p_course_id IS NULL OR app.current_user_id() IS NULL OR NOT app.is_instructor(p_course_id) THEN
        RAISE EXCEPTION 'öğrenme özeti için ders eğitmeni gerekli' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_days IS NULL OR p_days NOT IN (7, 30) THEN
        RAISE EXCEPTION 'özet penceresi 7 veya 30 gün olmalı' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    RETURN QUERY SELECT e.topic_id, coalesce(t.name, 'Konu belirtilmedi'), count(*),
        count(*) FILTER (WHERE e.event_type = 'answer_submitted' AND e.outcome_json->>'is_correct' = 'false'),
        count(*) FILTER (WHERE e.event_type = 'hint_requested'),
        count(*) FILTER (WHERE e.event_type = 'unsupported_refusal')
    FROM public.learning_events e LEFT JOIN public.topics t ON t.id = e.topic_id AND t.course_id = e.course_id
    WHERE e.course_id = p_course_id AND e.occurred_at >= now() - make_interval(days => p_days)
        AND e.occurred_at <= now()
    GROUP BY e.topic_id, t.name ORDER BY t.name NULLS LAST, e.topic_id;
END
$$;
REVOKE ALL ON FUNCTION app.learning_summary(uuid, integer) FROM PUBLIC, dou_app, dou_worker;
GRANT EXECUTE ON FUNCTION app.learning_summary(uuid, integer) TO dou_app;
ALTER FUNCTION app.learning_summary(uuid, integer) OWNER TO dou_worker;

COMMENT ON TABLE public.learning_events IS
    'Ders bazında gizli anahtarlı pseudo kimlik ile içeriksiz olay. xAPI''ye eşlenebilir; xAPI uyumluluk iddiası değildir.';
COMMIT;
