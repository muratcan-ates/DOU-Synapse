-- DOU-Synapse — ders bazlı AI politikası, değişiklik izi ve sohbet bütçesi

-- Bütçe dolması bir HTTP hatası değil, kaynak/kapsam reddi gibi normal bir
-- cevap sonucudur. Ayrı enum değeri ölçümü `insufficient_context` yalanından
-- korur; API bu sonucu 200 zarfında döndürür.
ALTER TYPE answer_status ADD VALUE 'budget_exhausted';

CREATE TABLE course_ai_policies (
    course_id uuid PRIMARY KEY REFERENCES courses(id) ON DELETE CASCADE,
    allowed_modes chat_mode[],
    max_hints smallint CHECK (max_hints IS NULL OR max_hints >= 0),
    source_document_ids uuid[],
    evidence_threshold numeric(4,3)
        CHECK (evidence_threshold IS NULL OR evidence_threshold BETWEEN 0 AND 1),
    daily_token_budget integer
        CHECK (daily_token_budget IS NULL OR daily_token_budget > 0),
    updated_by uuid REFERENCES profiles(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT course_ai_policies_no_exam CHECK (
        allowed_modes IS NULL OR NOT ('exam'::chat_mode = ANY(allowed_modes))
    )
);

CREATE TABLE course_ai_policy_audit (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    changed_by uuid REFERENCES profiles(id) ON DELETE SET NULL,
    changed_at timestamptz NOT NULL DEFAULT now(),
    before jsonb,
    after jsonb
);

CREATE INDEX course_ai_policy_audit_course_idx
    ON course_ai_policy_audit (course_id, changed_at DESC);

ALTER TABLE course_ai_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE course_ai_policies FORCE ROW LEVEL SECURITY;
ALTER TABLE course_ai_policy_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE course_ai_policy_audit FORCE ROW LEVEL SECURITY;

CREATE POLICY course_ai_policies_member_read ON course_ai_policies
    FOR SELECT USING (app.is_member(course_id));
CREATE POLICY course_ai_policies_instructor_insert ON course_ai_policies
    FOR INSERT WITH CHECK (app.is_instructor(course_id));
CREATE POLICY course_ai_policies_instructor_update ON course_ai_policies
    FOR UPDATE USING (app.is_instructor(course_id))
    WITH CHECK (app.is_instructor(course_id));
CREATE POLICY course_ai_policies_instructor_delete ON course_ai_policies
    FOR DELETE USING (app.is_instructor(course_id));

CREATE POLICY course_ai_policy_audit_instructor_read ON course_ai_policy_audit
    FOR SELECT USING (app.is_instructor(course_id));
CREATE POLICY course_ai_policy_audit_insert ON course_ai_policy_audit
    FOR INSERT WITH CHECK (app.is_instructor(course_id));

REVOKE UPDATE, DELETE ON course_ai_policy_audit FROM dou_app;
REVOKE ALL PRIVILEGES ON course_ai_policies, course_ai_policy_audit FROM dou_worker;

CREATE OR REPLACE FUNCTION app.audit_course_ai_policy()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, app
AS $$
BEGIN
    INSERT INTO course_ai_policy_audit (course_id, changed_by, before, after)
    VALUES (
        COALESCE(NEW.course_id, OLD.course_id),
        app.current_user_id(),
        CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE to_jsonb(OLD) END,
        CASE WHEN TG_OP = 'DELETE' THEN NULL ELSE to_jsonb(NEW) END
    );
    RETURN COALESCE(NEW, OLD);
END
$$;

CREATE TRIGGER course_ai_policy_audit_trigger
AFTER INSERT OR UPDATE OR DELETE ON course_ai_policies
FOR EACH ROW EXECUTE FUNCTION app.audit_course_ai_policy();

-- Öğrenci request_logs satırlarını okuyamaz. Toplamı doğrudan tablodan almak
-- bu yüzden her zaman sıfır görüp bütçeyi fail-open bırakırdı. Yardımcı yalnız
-- üyeliği doğrulanmış dersin bugünkü toplamını döndürür; satır sızdırmaz.
CREATE OR REPLACE FUNCTION app.course_tokens_today(p_course_id uuid)
RETURNS bigint
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public, app
AS $$
BEGIN
    IF NOT app.is_member(p_course_id) THEN
        RAISE EXCEPTION 'course membership required' USING ERRCODE = '42501';
    END IF;
    RETURN (
        SELECT COALESCE(sum(token_count), 0)::bigint
        FROM request_logs
        WHERE course_id = p_course_id
          AND created_at >= (
              date_trunc('day', now() AT TIME ZONE 'Europe/Istanbul')
              AT TIME ZONE 'Europe/Istanbul'
          )
    );
END
$$;

REVOKE ALL ON FUNCTION app.course_tokens_today(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.course_tokens_today(uuid) TO dou_app;
