-- B4: durable, scoped invalidation of chat requests pending during privacy deletion.
-- 0021..0023 are reserved by parallel lanes; do not renumber this migration.
BEGIN;

CREATE TABLE public.chat_privacy_revisions (
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    course_id uuid REFERENCES public.courses(id) ON DELETE CASCADE,
    revision bigint NOT NULL CHECK (revision > 0),
    CONSTRAINT chat_privacy_revisions_scope_key UNIQUE NULLS NOT DISTINCT (user_id, course_id)
);

ALTER TABLE public.chat_privacy_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_privacy_revisions FORCE ROW LEVEL SECURITY;
-- Override 0001's broad default grants, including the worker's RLS bypass.
REVOKE ALL ON public.chat_privacy_revisions FROM PUBLIC, dou_app, dou_worker;
GRANT SELECT, INSERT ON public.chat_privacy_revisions TO dou_app;
GRANT UPDATE (revision) ON public.chat_privacy_revisions TO dou_app;

CREATE POLICY chat_privacy_revisions_self_read ON public.chat_privacy_revisions
    FOR SELECT USING (user_id = app.current_user_id());
CREATE POLICY chat_privacy_revisions_self_insert ON public.chat_privacy_revisions
    FOR INSERT WITH CHECK (
        user_id = app.current_user_id()
        AND (course_id IS NULL OR app.is_member(course_id))
    );
CREATE POLICY chat_privacy_revisions_self_update ON public.chat_privacy_revisions
    FOR UPDATE USING (user_id = app.current_user_id())
    WITH CHECK (
        user_id = app.current_user_id()
        AND (course_id IS NULL OR app.is_member(course_id))
    );

-- The app cannot lower a revision, reset it by deletion, move its scope or insert
-- a chosen starting value. This trigger runs as the caller, without elevated RLS.
CREATE FUNCTION app.chat_privacy_revision_monotonic() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, public, app
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.revision <> 1 THEN
            RAISE EXCEPTION 'invalid initial chat privacy revision' USING ERRCODE = '23514';
        END IF;
    ELSIF NEW.user_id IS DISTINCT FROM OLD.user_id
        OR NEW.course_id IS DISTINCT FROM OLD.course_id
        OR NEW.revision <> OLD.revision + 1 THEN
        RAISE EXCEPTION 'invalid chat privacy revision transition' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION app.chat_privacy_revision_monotonic() FROM PUBLIC, dou_app, dou_worker;
CREATE TRIGGER chat_privacy_revision_monotonic
    BEFORE INSERT OR UPDATE ON public.chat_privacy_revisions
    FOR EACH ROW EXECUTE FUNCTION app.chat_privacy_revision_monotonic();

COMMIT;
