# API contracts — 015

## GET /courses/{course_id}/exams/{session_id}/answers/{question_id}
Response: existing AnswerFeedbackOut. Existing student workspace feature flag: off ->503. Current course member and explicit session owner required; course/session/question mismatch or missing answer ->404. Practice only (timed session ->403). Same-course active exam help lock ->403. Acquire existing assessment user lock before session/help checks. Finished practice may be read. Reuse _saved_feedback/_answer_feedback readable-source validation; no grading, mastery, answer or session mutation.

## GET /courses/{course_id}/questions/{question_id}/exam-usage
CourseInstructorDep; explicit question/course match. PageOut with stable descending created_at/id keyset, standard cursor/limit. Each item: id (equals version_id), blueprint_id, title, version_id, version_no, status (draft/published/superseded). Return each version once even if duplicate items exist. No student/session/answer/score or owner metadata. Other-course/non-instructor cannot enumerate. UI links ?blueprint_id=...&version_id=... and shows paper read-only without making published versions editable.

## Internal evaluation provenance
Hidden existing internal router, separate EVAL_RUNTIME_SECRET and explicit eval mode; closed by default and forbidden in production. Runtime snapshot contains safe allowlisted configuration digest, full candidate SHA and run identity. Per-response receipt identifies actual provider/model and outcome (provider, fake, cache, no_provider) and binds to runtime/run. Only loopback harness sends secret; redirects disabled. Missing or inconsistent receipt cannot yield real-quality acceptance. Offline preflight proves configuration only; live target probe proves access only. Provider and evaluation owners maintain exact schema together and test mismatches. No key, raw DSN, prompt, answer or personal data in receipts.
