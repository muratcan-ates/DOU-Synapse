-- 013: edit unused draft questions without changing a paper's live question row.
-- Exam versions and legacy practice sessions reference questions, not snapshots.
-- No historical payload/classification backfill is performed by this migration.
BEGIN;

-- RLS authorizes course instructors; column grants independently limit their
-- write surface. Ingestion workers never author/review questions.
REVOKE UPDATE ON public.questions FROM dou_app, dou_worker;
GRANT UPDATE (payload, learning_outcome_id, difficulty, status, reviewed_by, reviewed_at)
    ON public.questions TO dou_app;

CREATE OR REPLACE FUNCTION app.guard_question_authoring()
RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, app
AS $$
DECLARE
    content_changed boolean;
    classification_changed boolean;
BEGIN
    -- This guard only refuses/validates a write already authorized by table
    -- grants and RLS. Its definer context sees references hidden by RLS; it
    -- neither performs privileged writes nor exposes their existence via RPC.
    IF TG_OP = 'UPDATE' THEN
        IF NEW.id IS DISTINCT FROM OLD.id
           OR NEW.course_id IS DISTINCT FROM OLD.course_id
           OR NEW.topic_id IS DISTINCT FROM OLD.topic_id
           OR NEW.source_chunk_id IS DISTINCT FROM OLD.source_chunk_id
           OR NEW.type IS DISTINCT FROM OLD.type
           OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
            RAISE EXCEPTION 'question identity and source are immutable'
                USING ERRCODE = '23514', CONSTRAINT = 'questions_authoring_immutable';
        END IF;

        IF OLD.status <> 'draft' AND NEW.status = 'draft' THEN
            RAISE EXCEPTION 'reviewed question cannot return to draft'
                USING ERRCODE = '23514', CONSTRAINT = 'questions_authoring_immutable';
        END IF;

        classification_changed := NEW.learning_outcome_id IS DISTINCT FROM OLD.learning_outcome_id
                                  OR NEW.difficulty IS DISTINCT FROM OLD.difficulty;
        content_changed := NEW.payload IS DISTINCT FROM OLD.payload OR classification_changed;
        IF content_changed THEN
            IF OLD.status <> 'draft'
               OR EXISTS (SELECT 1 FROM public.exam_items i WHERE i.question_id = OLD.id)
               OR EXISTS (SELECT 1 FROM public.answers a WHERE a.question_id = OLD.id)
               OR EXISTS (SELECT 1 FROM public.exam_sessions s WHERE OLD.id = ANY(s.question_ids)) THEN
                RAISE EXCEPTION 'reviewed or referenced question content is immutable'
                    USING ERRCODE = '23514', CONSTRAINT = 'questions_authoring_immutable';
            END IF;
        END IF;

        -- Preserve the existing ON DELETE SET NULL outcome FK for UNUSED drafts:
        -- an FK action also clears difficulty. Reviewed/in-use questions fail
        -- above, so deleting their outcome cannot rewrite historical grading.
        -- Direct partial-pair updates remain invalid (ordinary trigger depth 1).
        IF pg_trigger_depth() > 1
           AND OLD.learning_outcome_id IS NOT NULL
           AND NEW.learning_outcome_id IS NULL
           AND NEW.difficulty IS NOT DISTINCT FROM OLD.difficulty THEN
            NEW.difficulty := NULL;
        END IF;
    ELSE
        classification_changed := true;
    END IF;

    IF classification_changed THEN
        IF (NEW.learning_outcome_id IS NULL) <> (NEW.difficulty IS NULL) THEN
            RAISE EXCEPTION 'learning outcome and difficulty must be supplied together'
                USING ERRCODE = '23514', CONSTRAINT = 'questions_authoring_classification';
        END IF;
        IF NEW.learning_outcome_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM public.learning_outcomes lo
            WHERE lo.id = NEW.learning_outcome_id
              AND lo.course_id = NEW.course_id
              AND (lo.topic_id IS NULL OR lo.topic_id = NEW.topic_id)
        ) THEN
            RAISE EXCEPTION 'learning outcome does not match question course and topic'
                USING ERRCODE = '23514', CONSTRAINT = 'questions_authoring_classification';
        END IF;
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER questions_authoring_guard
BEFORE INSERT OR UPDATE ON public.questions
FOR EACH ROW EXECUTE FUNCTION app.guard_question_authoring();

-- A reference can otherwise race a draft edit, particularly question_ids arrays
-- (which have no FK). FOR SHARE also conflicts with raw SQL non-key UPDATE, not
-- just the API's FOR UPDATE. Ordered locks make multi-question papers consistent.
CREATE OR REPLACE FUNCTION app.lock_question_authoring_reference()
RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, app
AS $$
DECLARE
    referenced_ids uuid[];
BEGIN
    IF TG_TABLE_NAME = 'exam_sessions' THEN
        referenced_ids := NEW.question_ids;
    ELSE
        referenced_ids := ARRAY[NEW.question_id];
    END IF;
    PERFORM q.id FROM public.questions q
    WHERE q.id = ANY(referenced_ids)
    ORDER BY q.id
    FOR SHARE;
    RETURN NEW;
END
$$;

CREATE TRIGGER exam_items_authoring_reference_lock
BEFORE INSERT OR UPDATE OF question_id ON public.exam_items
FOR EACH ROW EXECUTE FUNCTION app.lock_question_authoring_reference();
CREATE TRIGGER answers_authoring_reference_lock
BEFORE INSERT OR UPDATE OF question_id ON public.answers
FOR EACH ROW EXECUTE FUNCTION app.lock_question_authoring_reference();
CREATE TRIGGER exam_sessions_authoring_reference_lock
BEFORE INSERT OR UPDATE OF question_ids ON public.exam_sessions
FOR EACH ROW EXECUTE FUNCTION app.lock_question_authoring_reference();

REVOKE ALL ON FUNCTION app.guard_question_authoring() FROM PUBLIC, dou_app, dou_worker;
REVOKE ALL ON FUNCTION app.lock_question_authoring_reference() FROM PUBLIC, dou_app, dou_worker;

COMMIT;
