# Data model

No tables, columns or backfills. Existing exam_sessions, exam_blueprints, exam_versions, exam_items and answers remain authoritative.

Migration0019 adds app.own_exam_duration(uuid) RETURNS integer, STABLE SECURITY DEFINER, fixed pg_catalog/public/app search_path. Only dou_app receives EXECUTE. Function binds exam_sessions.user_id to app.current_user_id(), joins blueprint by both id and course, returns null for missing/nonowned/null ids. It returns no source, question, answer or other-user metadata. Membership is intentionally not required inside this duration-only projection: an owner's active exam privacy lock survives membership revocation. API membership checks remain independent. Public/dou_worker have no EXECUTE grant.

The existing effective expiry min(stored expiry, started_at + blueprint duration) remains the sole time rule. No duration inferred from client input or persisted expires_at gap. Catalogue counts only owned attempts. Results are pure projections; results_locked distinguishes a closed session whose answer-bearing details are temporarily withheld.

Saved AI answers are revalidated on reads, including old records created before014. Their evidence must match the question source and remain readable/nonempty. A hidden or malformed question is not displayable. GET/finish/session totals share this projection, so an ungrounded detail cannot retain a contradictory aggregate score. Reads never rewrite historical answers or mastery; finishing an ungraded legacy exam does not add mastery. Deterministic MCQ/short-answer grading remains unchanged.

Assessment deadline and admission checks use the database wall clock (`clock_timestamp()`) after acquiring the user lock. Transaction-start `now()` is intentionally not used for this decision: a request can wait past expiry. The shared core db_now helper retains its other callers' semantics.
