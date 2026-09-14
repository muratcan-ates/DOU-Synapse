-- Uygulama ve worker rolleriyle doğrudan sınır kanıtı; sonuçlar geri alınır.
\set ON_ERROR_STOP on
\pset format unaligned
\pset tuples_only on
BEGIN;
CREATE TEMP TABLE learning_assertions (name text, passed boolean);
GRANT SELECT, INSERT ON learning_assertions TO dou_app, dou_worker;
CREATE FUNCTION pg_temp.learning_check(passed boolean, name text) RETURNS void
LANGUAGE sql AS $$ INSERT INTO learning_assertions VALUES (name, passed IS TRUE) $$;
CREATE FUNCTION pg_temp.learning_denied(statement text, name text) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    EXECUTE statement;
    PERFORM pg_temp.learning_check(false, name);
EXCEPTION WHEN insufficient_privilege OR check_violation OR invalid_parameter_value THEN
    PERFORM pg_temp.learning_check(true, name);
END
$$;

INSERT INTO public.profiles(id, email) VALUES
('27000000-0000-0000-0000-000000000001','learning-instructor@example.test'),
('27000000-0000-0000-0000-000000000002','learning-student@example.test'),
('27000000-0000-0000-0000-000000000003','learning-peer@example.test'),
('27000000-0000-0000-0000-000000000004','learning-outsider@example.test');
INSERT INTO public.courses(id, code, title, created_by) VALUES
('27000000-0000-0000-0000-00000000000a','LEARNING-A','Öğrenme A','27000000-0000-0000-0000-000000000001'),
('27000000-0000-0000-0000-00000000000b','LEARNING-B','Öğrenme B','27000000-0000-0000-0000-000000000001');
INSERT INTO public.course_memberships(course_id,user_id,role) VALUES
('27000000-0000-0000-0000-00000000000a','27000000-0000-0000-0000-000000000001','instructor'),
('27000000-0000-0000-0000-00000000000a','27000000-0000-0000-0000-000000000002','student'),
('27000000-0000-0000-0000-00000000000a','27000000-0000-0000-0000-000000000003','student'),
('27000000-0000-0000-0000-00000000000b','27000000-0000-0000-0000-000000000001','student'),
('27000000-0000-0000-0000-00000000000b','27000000-0000-0000-0000-000000000002','student');
INSERT INTO public.topics(id,course_id,name,created_by) VALUES
('27000000-0000-0000-0000-00000000001a','27000000-0000-0000-0000-00000000000a','Kilitlenme','27000000-0000-0000-0000-000000000001'),
('27000000-0000-0000-0000-00000000001b','27000000-0000-0000-0000-00000000000b','Yığın','27000000-0000-0000-0000-000000000001');
INSERT INTO public.chat_sessions(id,course_id,user_id,mode) VALUES
('27000000-0000-0000-0000-00000000002a','27000000-0000-0000-0000-00000000000a','27000000-0000-0000-0000-000000000002','qa'),
('27000000-0000-0000-0000-00000000002b','27000000-0000-0000-0000-00000000000a','27000000-0000-0000-0000-000000000003','qa');

SET LOCAL ROLE dou_app;
SELECT set_config('app.current_user_id','27000000-0000-0000-0000-000000000002',true);
SELECT pg_temp.learning_check(
    app.learning_actor_pseudo_id('27000000-0000-0000-0000-00000000000a') <> app.current_user_id(),
    'pseudo_is_not_user_id');
SELECT pg_temp.learning_check(
    app.learning_actor_pseudo_id('27000000-0000-0000-0000-00000000000a') <>
    app.learning_actor_pseudo_id('27000000-0000-0000-0000-00000000000b'), 'pseudo_is_course_scoped');
SELECT app.record_learning_event('27000000-0000-0000-0000-00000000000a','unsupported_refusal',
    '27000000-0000-0000-0000-00000000001a','27000000-0000-0000-0000-00000000002a');
SELECT app.record_learning_event('27000000-0000-0000-0000-00000000000b','unsupported_refusal');
SELECT pg_temp.learning_check((SELECT count(*) FROM public.learning_events) = 2, 'student_reads_own_events');
SELECT pg_temp.learning_check(NOT has_table_privilege('dou_app','public.learning_events','INSERT'), 'app_has_no_insert_grant');
SELECT pg_temp.learning_denied($q$ INSERT INTO public.learning_events(actor_pseudo_id,course_id,event_type)
    VALUES ('27000000-0000-0000-0000-000000000002','27000000-0000-0000-0000-00000000000a','unsupported_refusal') $q$, 'app_cannot_insert_directly');
SELECT pg_temp.learning_denied('SELECT secret FROM app.learning_event_secret', 'app_cannot_read_secret');
SELECT pg_temp.learning_denied('SELECT outcome_json FROM public.learning_events', 'student_cannot_read_exam_outcome');
SELECT pg_temp.learning_denied('SELECT evidence_chunk_ids FROM public.learning_events', 'student_cannot_read_exam_evidence');
SELECT pg_temp.learning_denied($q$ SELECT app.learning_summary('27000000-0000-0000-0000-00000000000a',7) $q$, 'student_cannot_read_aggregate');
SELECT pg_temp.learning_denied($q$ SELECT app.record_learning_event('27000000-0000-0000-0000-00000000000a','unsupported_refusal',NULL,'27000000-0000-0000-0000-00000000002b') $q$, 'writer_rejects_peer_session');
SELECT pg_temp.learning_denied($q$ SELECT app.record_learning_event('27000000-0000-0000-0000-00000000000a','unsupported_refusal','27000000-0000-0000-0000-00000000001b') $q$, 'writer_rejects_foreign_topic');
SELECT pg_temp.learning_denied($q$ SELECT app.record_learning_event('27000000-0000-0000-0000-00000000000a','unsupported_refusal',p_outcome_json => '{"answer":"özel metin"}') $q$, 'writer_rejects_raw_content');
SELECT pg_temp.learning_denied($q$ UPDATE public.learning_events SET event_type='provider_rate_limited' $q$, 'app_cannot_update');
SELECT pg_temp.learning_denied('DELETE FROM public.learning_events', 'app_cannot_delete');

SELECT set_config('app.current_user_id','27000000-0000-0000-0000-000000000003',true);
SELECT pg_temp.learning_check((SELECT count(*) FROM public.learning_events) = 0, 'student_cannot_read_peer');
SELECT app.record_learning_event('27000000-0000-0000-0000-00000000000a','hint_requested',
    '27000000-0000-0000-0000-00000000001a','27000000-0000-0000-0000-00000000002b');
SELECT pg_temp.learning_check((SELECT count(*) FROM public.learning_events) = 1, 'peer_reads_own_event_only');

SELECT set_config('app.current_user_id','27000000-0000-0000-0000-000000000001',true);
SELECT pg_temp.learning_check((SELECT count(*) FROM public.learning_events) = 0, 'instructor_cannot_read_raw_events');
SELECT pg_temp.learning_check((SELECT event_count=2 AND hints_requested=1 AND unsupported_refusals=1
    FROM app.learning_summary('27000000-0000-0000-0000-00000000000a',7)
    WHERE topic_id='27000000-0000-0000-0000-00000000001a'),'instructor_reads_topic_totals');
SELECT pg_temp.learning_denied($q$ SELECT app.learning_summary('27000000-0000-0000-0000-00000000000b',7) $q$, 'mixed_role_cannot_read_foreign_aggregate');
SELECT pg_temp.learning_denied($q$ SELECT app.learning_summary('27000000-0000-0000-0000-00000000000a',NULL) $q$, 'summary_rejects_null_window');
SELECT pg_temp.learning_denied($q$ SELECT app.learning_summary('27000000-0000-0000-0000-00000000000a',8) $q$, 'summary_rejects_unknown_window');

SELECT set_config('app.current_user_id','27000000-0000-0000-0000-000000000004',true);
SELECT pg_temp.learning_check((SELECT count(*) FROM public.learning_events) = 0, 'nonmember_cannot_read');
SELECT pg_temp.learning_denied($q$ SELECT app.record_learning_event('27000000-0000-0000-0000-00000000000a','unsupported_refusal') $q$, 'nonmember_cannot_record');
SELECT set_config('app.current_user_id','',true);
SELECT pg_temp.learning_denied($q$ SELECT app.record_learning_event('27000000-0000-0000-0000-00000000000a','unsupported_refusal') $q$, 'missing_context_cannot_record');
SELECT pg_temp.learning_check((SELECT count(*) FROM public.learning_events) = 0, 'missing_context_cannot_read');

RESET ROLE;
UPDATE public.course_memberships SET status='revoked' WHERE user_id='27000000-0000-0000-0000-000000000003';
SET LOCAL ROLE dou_app;
SELECT set_config('app.current_user_id','27000000-0000-0000-0000-000000000003',true);
SELECT pg_temp.learning_check((SELECT count(*) FROM public.learning_events) = 0, 'revoked_member_cannot_read');
SELECT pg_temp.learning_denied($q$ SELECT app.record_learning_event('27000000-0000-0000-0000-00000000000a','unsupported_refusal') $q$, 'revoked_member_cannot_record');

SET LOCAL ROLE dou_worker;
SELECT set_config('app.current_user_id','27000000-0000-0000-0000-000000000002',true);
INSERT INTO public.learning_events(actor_pseudo_id,course_id,event_type)
VALUES(app.learning_actor_pseudo_id('27000000-0000-0000-0000-00000000000a'),
    '27000000-0000-0000-0000-00000000000a','provider_rate_limited');
SELECT pg_temp.learning_check((SELECT count(*) FROM public.learning_events) = 4, 'worker_can_insert');
RESET ROLE;
SELECT pg_temp.learning_check(
    (SELECT r.rolname='dou_worker' FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
     WHERE p.oid='app.record_learning_event(uuid,text,uuid,uuid,text,text,jsonb,uuid[],integer,text,jsonb)'::regprocedure),
    'recorder_executes_as_worker');
SELECT pg_temp.learning_check(NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_proc p, LATERAL aclexplode(coalesce(p.proacl, acldefault('f',p.proowner))) a
    WHERE p.oid IN ('app.learning_summary(uuid,integer)'::regprocedure,
        'app.learning_actor_pseudo_id(uuid)'::regprocedure,
        'app.record_learning_event(uuid,text,uuid,uuid,text,text,jsonb,uuid[],integer,text,jsonb)'::regprocedure)
        AND a.grantee=0 AND a.privilege_type='EXECUTE'), 'helpers_have_no_public_execute');
SELECT CASE WHEN passed THEN 'PASS  ' ELSE 'FAIL  ' END || name FROM learning_assertions ORDER BY name;
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM learning_assertions WHERE NOT passed) THEN
        RAISE EXCEPTION 'öğrenme olayı RLS iddiası başarısız';
    END IF;
END $$;
ROLLBACK;
