-- Keep an owned exam's duration available after its entry window closes.
-- This projection exposes no question, source or other user's exam metadata.
BEGIN;

CREATE FUNCTION app.own_exam_duration(p_session_id uuid)
RETURNS integer
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, app
AS $$
    SELECT b.duration_minutes
    FROM public.exam_sessions s
    JOIN public.exam_blueprints b
      ON b.id = s.exam_blueprint_id AND b.course_id = s.course_id
    WHERE s.id = p_session_id AND s.user_id = app.current_user_id()
$$;

REVOKE ALL ON FUNCTION app.own_exam_duration(uuid) FROM PUBLIC, dou_app, dou_worker;
GRANT EXECUTE ON FUNCTION app.own_exam_duration(uuid) TO dou_app;

COMMIT;
