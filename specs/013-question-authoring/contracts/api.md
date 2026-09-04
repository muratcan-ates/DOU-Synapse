# API contract

Course prefix: /courses/{course_id}; instructor access required for authoring operations.

- GET /questions/authoring -> 200 {enabled: boolean}.
- POST /questions/generate adds optional learning_outcome_id: UUID|null and difficulty: easy|medium|hard|null. Pair must be both set or both null; same-course outcome with matching/null topic. Existing requests remain valid. Classified generation requires authoring flag.
- POST /questions/{question_id}/draft takes {payload: object, learning_outcome_id: UUID|null, difficulty: easy|medium|hard|null}. Entire typed payload and classification replaced atomically, extra fields forbidden. Only unused drafts. 200 returns QuestionOut with source/classification. 403 instructor requirement, 404 inaccessible question/outcome, 409 immutable/reference conflict, 422 invalid payload/classification, 503 authoring disabled; repository error envelope includes request_id.
- QuestionOut exposes existing learning_outcome_id/difficulty/source_stale correctly. Student payload filtering remains unchanged.

Validation follows stored question type; type/course/topic/source/status/reviewer cannot be changed. Referenced MCQ chunk IDs are validated within the course. Edited essays require nonempty rubric totaling100. Model calls are never made during manual editing.
