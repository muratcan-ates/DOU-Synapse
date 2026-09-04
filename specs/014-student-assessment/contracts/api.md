# API contract

All paths are relative to /courses/{course_id}; current course membership and explicit session ownership remain mandatory.

- GET /exams/catalog → {enabled, items}. When disabled false/empty. Only currently open published exams; item fields blueprint_id, title, description, duration_minutes, opens_at, closes_at, max_attempts, used_attempts, remaining_attempts, can_start. No cells, questions or answer keys.
- GET /exams/history → PageOut<ExamSessionOut>, bounded pagination ordered by started_at; owned session summaries only, no question/answer contents. Disabled503.
- GET /exams remains the legacy array but explicitly owner-filtered even for instructors.
- POST /exams reuses {mode,topic_id?,blueprint_id?}; topic scopes practice, blueprint selects existing timed version. Practice is blocked during same-course student exam.
- GET /exams/{id}/results → ExamFinishOut plus results_locked:false. Only finished owned sessions; unfinished409, active same-course student exam403 exam_in_progress, flag-disabled503. No grading/write side effects.
- POST /exams/{id}/finish → ExamFinishOut plus results_locked. If another same-course student timed session remains active, closes this session and returns results_locked:true, score:null, results:[], factual counts and message. Otherwise saved source-grounded results.
- Existing practice answer/hint endpoints block while same-course student timed exam runs, using shared transaction advisory lock. Ungraded feedback omits source-free scoring claims and answer keys.

Exam start, result reads, practice assistance and finish serialize on existing per-user assessment transaction lock. Different course and instructor exemptions follow established policy. The current database wall clock after any lock wait controls availability and duration; a queued request cannot reuse its pre-wait transaction timestamp. Frontend localStorage is only a course-and-user scoped hint; history is durable server state.
