-- 013 question authoring: real dou_app/dou_worker SQL, no API authorization.
-- Run on a dedicated migrated test database as its owner. All fixtures roll back.
\set ON_ERROR_STOP on
\pset tuples_only on
\pset format unaligned
BEGIN;
CREATE TEMP TABLE authoring_results (name text, ok boolean);
GRANT INSERT, SELECT ON authoring_results TO dou_app, dou_worker;
CREATE FUNCTION pg_temp.expect_count(label text, command text, expected bigint)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE actual bigint;
BEGIN
    EXECUTE command;
    GET DIAGNOSTICS actual = ROW_COUNT;
    INSERT INTO authoring_results VALUES (label, actual = expected);
    RAISE NOTICE '%  %', CASE WHEN actual = expected THEN 'PASS' ELSE 'FAIL' END, label;
END $$;
CREATE FUNCTION pg_temp.expect_error(label text, command text, expected_state text,
                                      expected_constraint text DEFAULT NULL)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE actual_state text; actual_constraint text; matched boolean;
BEGIN
    BEGIN
        EXECUTE command;
        -- Roll back unexpectedly accepted mutations as well as rejected ones.
        RAISE EXCEPTION USING ERRCODE = 'PZ001', MESSAGE = 'mutation accepted';
    EXCEPTION WHEN OTHERS THEN
        GET STACKED DIAGNOSTICS actual_state = RETURNED_SQLSTATE,
                                actual_constraint = CONSTRAINT_NAME;
    END;
    matched := actual_state = expected_state
               AND (expected_constraint IS NULL OR actual_constraint = expected_constraint);
    INSERT INTO authoring_results VALUES (label, matched);
    RAISE NOTICE '%  % (state %, constraint %)',
        CASE WHEN matched THEN 'PASS' ELSE 'FAIL' END, label, actual_state, actual_constraint;
END $$;

INSERT INTO profiles (id,email,full_name) VALUES ('13000000-0000-0000-0000-000000000001','authoring1@example.test','Authoring 1'),('13000000-0000-0000-0000-000000000002','authoring2@example.test','Authoring 2'),('13000000-0000-0000-0000-000000000003','authoring3@example.test','Authoring 3'),('13000000-0000-0000-0000-000000000004','authoring4@example.test','Authoring 4');
INSERT INTO platform_admins (user_id) VALUES ('13000000-0000-0000-0000-000000000004');
INSERT INTO courses (id,code,title,created_by) VALUES ('13000000-0000-0000-0000-000000000010','QA013A','Authoring A','13000000-0000-0000-0000-000000000001'),('13000000-0000-0000-0000-000000000020','QA013B','Authoring B','13000000-0000-0000-0000-000000000003');
INSERT INTO course_memberships(course_id,user_id,role) VALUES ('13000000-0000-0000-0000-000000000010','13000000-0000-0000-0000-000000000001','instructor'),('13000000-0000-0000-0000-000000000010','13000000-0000-0000-0000-000000000002','student'),('13000000-0000-0000-0000-000000000020','13000000-0000-0000-0000-000000000001','student'),('13000000-0000-0000-0000-000000000020','13000000-0000-0000-0000-000000000003','instructor');
INSERT INTO topics(id,course_id,name,created_by) VALUES ('13000000-0000-0000-0000-000000000011','13000000-0000-0000-0000-000000000010','Main topic','13000000-0000-0000-0000-000000000001'),('13000000-0000-0000-0000-000000000012','13000000-0000-0000-0000-000000000010','Other topic','13000000-0000-0000-0000-000000000001'),('13000000-0000-0000-0000-000000000021','13000000-0000-0000-0000-000000000020','Foreign topic','13000000-0000-0000-0000-000000000003');
INSERT INTO documents(id,course_id,uploaded_by,file_name,file_type,storage_path,file_hash,byte_size,status) VALUES ('13000000-0000-0000-0000-000000000030','13000000-0000-0000-0000-000000000010','13000000-0000-0000-0000-000000000001','qa.md','md','qa/13','qa13',10,'completed');
INSERT INTO chunks(id,course_id,document_id,chunk_index,page_number,text,token_count) VALUES ('13000000-0000-0000-0000-000000000031','13000000-0000-0000-0000-000000000010','13000000-0000-0000-0000-000000000030',0,1,'Authoring source content',4);
INSERT INTO learning_outcomes(id,course_id,topic_id,code,description,created_by) VALUES ('13000000-0000-0000-0000-000000000040','13000000-0000-0000-0000-000000000010','13000000-0000-0000-0000-000000000011','CO40','Outcome 40','13000000-0000-0000-0000-000000000001'),('13000000-0000-0000-0000-000000000041','13000000-0000-0000-0000-000000000010','13000000-0000-0000-0000-000000000012','CO41','Outcome 41','13000000-0000-0000-0000-000000000001'),('13000000-0000-0000-0000-000000000042','13000000-0000-0000-0000-000000000020','13000000-0000-0000-0000-000000000021','CO42','Outcome 42','13000000-0000-0000-0000-000000000003'),('13000000-0000-0000-0000-000000000043','13000000-0000-0000-0000-000000000010',NULL,'CO43','Outcome 43','13000000-0000-0000-0000-000000000001'),('13000000-0000-0000-0000-000000000044','13000000-0000-0000-0000-000000000010','13000000-0000-0000-0000-000000000011','CO44','Outcome 44','13000000-0000-0000-0000-000000000001'),('13000000-0000-0000-0000-000000000045','13000000-0000-0000-0000-000000000010','13000000-0000-0000-0000-000000000011','CO45','Outcome 45','13000000-0000-0000-0000-000000000001');
INSERT INTO questions(id,course_id,topic_id,type,payload,source_chunk_id,status,created_by,reviewed_by,reviewed_at,learning_outcome_id,difficulty) VALUES ('13000000-0000-0000-0000-000000000050','13000000-0000-0000-0000-000000000010','13000000-0000-0000-0000-000000000011','open','{"prompt":"Initial question","answer_key":"Initial answer","key_points":["Initial"]}','13000000-0000-0000-0000-000000000031','draft','13000000-0000-0000-0000-000000000001',NULL,NULL,NULL,NULL);
INSERT INTO questions(id,course_id,topic_id,type,payload,source_chunk_id,status,created_by,reviewed_by,reviewed_at,learning_outcome_id,difficulty) VALUES ('13000000-0000-0000-0000-000000000051','13000000-0000-0000-0000-000000000010','13000000-0000-0000-0000-000000000011','open','{"prompt":"Initial question","answer_key":"Initial answer","key_points":["Initial"]}','13000000-0000-0000-0000-000000000031','approved','13000000-0000-0000-0000-000000000001','13000000-0000-0000-0000-000000000001',now(),NULL,NULL);
INSERT INTO questions(id,course_id,topic_id,type,payload,source_chunk_id,status,created_by,reviewed_by,reviewed_at,learning_outcome_id,difficulty) VALUES ('13000000-0000-0000-0000-000000000052','13000000-0000-0000-0000-000000000010','13000000-0000-0000-0000-000000000011','open','{"prompt":"Initial question","answer_key":"Initial answer","key_points":["Initial"]}','13000000-0000-0000-0000-000000000031','rejected','13000000-0000-0000-0000-000000000001','13000000-0000-0000-0000-000000000001',now(),NULL,NULL);
INSERT INTO questions(id,course_id,topic_id,type,payload,source_chunk_id,status,created_by,reviewed_by,reviewed_at,learning_outcome_id,difficulty) VALUES ('13000000-0000-0000-0000-000000000053','13000000-0000-0000-0000-000000000010','13000000-0000-0000-0000-000000000011','open','{"prompt":"Initial question","answer_key":"Initial answer","key_points":["Initial"]}','13000000-0000-0000-0000-000000000031','draft','13000000-0000-0000-0000-000000000001',NULL,NULL,NULL,NULL);
INSERT INTO questions(id,course_id,topic_id,type,payload,source_chunk_id,status,created_by,reviewed_by,reviewed_at,learning_outcome_id,difficulty) VALUES ('13000000-0000-0000-0000-000000000054','13000000-0000-0000-0000-000000000010','13000000-0000-0000-0000-000000000011','open','{"prompt":"Initial question","answer_key":"Initial answer","key_points":["Initial"]}','13000000-0000-0000-0000-000000000031','draft','13000000-0000-0000-0000-000000000001',NULL,NULL,NULL,NULL);
INSERT INTO questions(id,course_id,topic_id,type,payload,source_chunk_id,status,created_by,reviewed_by,reviewed_at,learning_outcome_id,difficulty) VALUES ('13000000-0000-0000-0000-000000000055','13000000-0000-0000-0000-000000000010','13000000-0000-0000-0000-000000000011','open','{"prompt":"Initial question","answer_key":"Initial answer","key_points":["Initial"]}','13000000-0000-0000-0000-000000000031','draft','13000000-0000-0000-0000-000000000001',NULL,NULL,NULL,NULL);
INSERT INTO questions(id,course_id,topic_id,type,payload,source_chunk_id,status,created_by,reviewed_by,reviewed_at,learning_outcome_id,difficulty) VALUES ('13000000-0000-0000-0000-000000000056','13000000-0000-0000-0000-000000000010','13000000-0000-0000-0000-000000000011','open','{"prompt":"Initial question","answer_key":"Initial answer","key_points":["Initial"]}','13000000-0000-0000-0000-000000000031','draft','13000000-0000-0000-0000-000000000001',NULL,NULL,'13000000-0000-0000-0000-000000000044','medium');
INSERT INTO questions(id,course_id,topic_id,type,payload,source_chunk_id,status,created_by,reviewed_by,reviewed_at,learning_outcome_id,difficulty) VALUES ('13000000-0000-0000-0000-000000000057','13000000-0000-0000-0000-000000000010','13000000-0000-0000-0000-000000000011','open','{"prompt":"Initial question","answer_key":"Initial answer","key_points":["Initial"]}','13000000-0000-0000-0000-000000000031','approved','13000000-0000-0000-0000-000000000001','13000000-0000-0000-0000-000000000001',now(),'13000000-0000-0000-0000-000000000045','medium');
INSERT INTO questions(id,course_id,topic_id,type,payload,source_chunk_id,status,created_by,reviewed_by,reviewed_at,learning_outcome_id,difficulty) VALUES ('13000000-0000-0000-0000-000000000058','13000000-0000-0000-0000-000000000020','13000000-0000-0000-0000-000000000021','open','{"prompt":"Initial question","answer_key":"Initial answer","key_points":["Initial"]}','13000000-0000-0000-0000-000000000031','approved','13000000-0000-0000-0000-000000000003','13000000-0000-0000-0000-000000000003',now(),NULL,NULL);
INSERT INTO exam_blueprints(id,course_id,title,duration_minutes,created_by) VALUES ('13000000-0000-0000-0000-000000000060','13000000-0000-0000-0000-000000000010','QA paper',30,'13000000-0000-0000-0000-000000000001');
INSERT INTO exam_versions(id,course_id,blueprint_id,version_no) VALUES ('13000000-0000-0000-0000-000000000061','13000000-0000-0000-0000-000000000010','13000000-0000-0000-0000-000000000060',1);
INSERT INTO exam_items(id,course_id,exam_version_id,position,question_id,points) VALUES ('13000000-0000-0000-0000-000000000062','13000000-0000-0000-0000-000000000010','13000000-0000-0000-0000-000000000061',1,'13000000-0000-0000-0000-000000000053',1);
INSERT INTO exam_sessions(id,course_id,user_id,mode,question_ids) VALUES ('13000000-0000-0000-0000-000000000063','13000000-0000-0000-0000-000000000020','13000000-0000-0000-0000-000000000003','practice',ARRAY['13000000-0000-0000-0000-000000000055'::uuid]),('13000000-0000-0000-0000-000000000064','13000000-0000-0000-0000-000000000010','13000000-0000-0000-0000-000000000002','practice',ARRAY[]::uuid[]);
INSERT INTO answers(id,session_id,question_id,course_id,given) VALUES ('13000000-0000-0000-0000-000000000065','13000000-0000-0000-0000-000000000064','13000000-0000-0000-0000-000000000054','13000000-0000-0000-0000-000000000010','student answer');
SET LOCAL ROLE dou_app; SET LOCAL app.current_user_id = '13000000-0000-0000-0000-000000000001';
SELECT pg_temp.expect_count('instructor_edits_unused_draft', $cmd$UPDATE questions SET payload=jsonb_set(payload,'{prompt}','"Updated question"') WHERE id='13000000-0000-0000-0000-000000000050'$cmd$, 1);
SELECT pg_temp.expect_count('instructor_classifies_draft', $cmd$UPDATE questions SET learning_outcome_id='13000000-0000-0000-0000-000000000040',difficulty='hard' WHERE id='13000000-0000-0000-0000-000000000050'$cmd$, 1);
SELECT pg_temp.expect_count('unlinked_outcome_is_valid', $cmd$UPDATE questions SET learning_outcome_id='13000000-0000-0000-0000-000000000043' WHERE id='13000000-0000-0000-0000-000000000050'$cmd$, 1);
SELECT pg_temp.expect_error('foreign_outcome_denied', $cmd$UPDATE questions SET learning_outcome_id='13000000-0000-0000-0000-000000000042' WHERE id='13000000-0000-0000-0000-000000000050'$cmd$, '23514', 'questions_authoring_classification');
SELECT pg_temp.expect_error('wrong_topic_outcome_denied', $cmd$UPDATE questions SET learning_outcome_id='13000000-0000-0000-0000-000000000041' WHERE id='13000000-0000-0000-0000-000000000050'$cmd$, '23514', 'questions_authoring_classification');
SELECT pg_temp.expect_error('partial_classification_denied', $cmd$UPDATE questions SET learning_outcome_id=NULL WHERE id='13000000-0000-0000-0000-000000000050'$cmd$, '23514', 'questions_authoring_classification');
SELECT pg_temp.expect_count('clear_classification_pair', $cmd$UPDATE questions SET learning_outcome_id=NULL,difficulty=NULL WHERE id='13000000-0000-0000-0000-000000000050'$cmd$, 1);
SELECT pg_temp.expect_error('approved_payload_immutable', $cmd$UPDATE questions SET payload=jsonb_set(payload,'{prompt}','"Forbidden question"') WHERE id='13000000-0000-0000-0000-000000000051'$cmd$, '23514', 'questions_authoring_immutable');
SELECT pg_temp.expect_error('rejected_payload_immutable', $cmd$UPDATE questions SET payload=jsonb_set(payload,'{prompt}','"Forbidden question"') WHERE id='13000000-0000-0000-0000-000000000052'$cmd$, '23514', 'questions_authoring_immutable');
SELECT pg_temp.expect_error('paper_draft_immutable', $cmd$UPDATE questions SET payload=jsonb_set(payload,'{prompt}','"Forbidden question"') WHERE id='13000000-0000-0000-0000-000000000053'$cmd$, '23514', 'questions_authoring_immutable');
SELECT pg_temp.expect_error('answered_draft_immutable', $cmd$UPDATE questions SET payload=jsonb_set(payload,'{prompt}','"Forbidden question"') WHERE id='13000000-0000-0000-0000-000000000054'$cmd$, '23514', 'questions_authoring_immutable');
SELECT pg_temp.expect_error('hidden_session_draft_immutable', $cmd$UPDATE questions SET payload=jsonb_set(payload,'{prompt}','"Forbidden question"') WHERE id='13000000-0000-0000-0000-000000000055'$cmd$, '23514', 'questions_authoring_immutable');
SELECT pg_temp.expect_error('reviewed_classification_immutable', $cmd$UPDATE questions SET learning_outcome_id='13000000-0000-0000-0000-000000000040',difficulty='easy' WHERE id='13000000-0000-0000-0000-000000000051'$cmd$, '23514', 'questions_authoring_immutable');
SELECT pg_temp.expect_error('reviewed_cannot_return_to_draft', $cmd$UPDATE questions SET status='draft',reviewed_by=NULL,reviewed_at=NULL WHERE id='13000000-0000-0000-0000-000000000051'$cmd$, '23514', 'questions_authoring_immutable');
SELECT pg_temp.expect_count('approved_can_be_rejected', $cmd$UPDATE questions SET status='rejected',reviewed_at=now() WHERE id='13000000-0000-0000-0000-000000000051'$cmd$, 1);
SELECT pg_temp.expect_count('reviewed_can_be_reapproved', $cmd$UPDATE questions SET status='approved',reviewed_at=now() WHERE id='13000000-0000-0000-0000-000000000051'$cmd$, 1);
SELECT pg_temp.expect_count('draft_approval_works', $cmd$UPDATE questions SET status='approved',reviewed_by='13000000-0000-0000-0000-000000000001',reviewed_at=now() WHERE id='13000000-0000-0000-0000-000000000050'$cmd$, 1);
SELECT pg_temp.expect_error('identity_column_grant_denied', $cmd$UPDATE questions SET topic_id='13000000-0000-0000-0000-000000000012' WHERE id='13000000-0000-0000-0000-000000000056'$cmd$, '42501', NULL);
SELECT pg_temp.expect_count('unused_draft_outcome_delete_allowed', $cmd$DELETE FROM learning_outcomes WHERE id='13000000-0000-0000-0000-000000000044'$cmd$, 1);
SELECT pg_temp.expect_count('fk_clear_keeps_pair_consistent', $cmd$SELECT 1 FROM questions WHERE id='13000000-0000-0000-0000-000000000056' AND learning_outcome_id IS NULL AND difficulty IS NULL$cmd$, 1);
SELECT pg_temp.expect_error('reviewed_outcome_delete_denied', $cmd$DELETE FROM learning_outcomes WHERE id='13000000-0000-0000-0000-000000000045'$cmd$, '23514', 'questions_authoring_immutable');
SELECT pg_temp.expect_count('mixed_role_cannot_edit_other_course', $cmd$UPDATE questions SET reviewed_at=now() WHERE id='13000000-0000-0000-0000-000000000058'$cmd$, 0);
SET LOCAL app.current_user_id = '13000000-0000-0000-0000-000000000002';
SELECT pg_temp.expect_count('student_cannot_edit_visible_question', $cmd$UPDATE questions SET reviewed_at=now() WHERE id='13000000-0000-0000-0000-000000000051'$cmd$, 0);
SET LOCAL app.current_user_id = '13000000-0000-0000-0000-000000000004';
SELECT pg_temp.expect_count('platform_admin_has_no_course_authoring', $cmd$UPDATE questions SET reviewed_at=now() WHERE id='13000000-0000-0000-0000-000000000051'$cmd$, 0);
SET LOCAL app.current_user_id = ''; SET LOCAL ROLE dou_worker;
SELECT pg_temp.expect_error('worker_cannot_author_questions', $cmd$UPDATE questions SET payload=jsonb_set(payload,'{prompt}','"Worker edit"') WHERE id='13000000-0000-0000-0000-000000000056'$cmd$, '42501', NULL);
RESET ROLE;
SELECT pg_temp.expect_error('identity_trigger_even_for_owner', $cmd$UPDATE questions SET topic_id='13000000-0000-0000-0000-000000000012' WHERE id='13000000-0000-0000-0000-000000000056'$cmd$, '23514', 'questions_authoring_immutable');
SELECT CASE WHEN NOT has_function_privilege('dou_app','app.guard_question_authoring()','EXECUTE') AND NOT has_function_privilege('dou_worker','app.lock_question_authoring_reference()','EXECUTE') THEN 'PASS' ELSE 'FAIL' END || '  trigger_helpers_not_rpc';
SELECT CASE WHEN bool_and(ok) THEN 'PASS' ELSE 'FAIL' END || '  question_authoring_all (' || count(*) || ' checks)' FROM authoring_results;
ROLLBACK;
