# Local validation

Use this worktree and an isolated PostgreSQL16+pgvector cluster, never a shared course database. Root validation uses port55439 and unique TEST_DB_NAME values with explicit TEST_ADMIN_DSN, TEST_APP_DSN, TEST_WORKER_DSN. Set LLM_FAKE_PROVIDER=true, EMBEDDING_PROVIDER=hashing, EMBEDDING_WARMUP_ENABLED=false, QUESTION_AUTHORING_ENABLED=true and blank provider keys. Dependencies are pinned in uv.lock and bun.lock.

Teacher journey: create course and topic; add a learning outcome in blueprint screen; upload a short Markdown source; generate MCQ with matching outcome and difficulty; edit its stem/answer; save; approve; create matching blueprint/cell/version; add approved question; verify readiness and publish. Attempt another edit after approval: it must be unavailable/denied. Repeat edit rendering for essay, short answer, code trace and bug hunt. Disable authoring flag and verify capabilities disabled and direct write503.

Use API tests and SQL tests for negative role/reference/race cases. Full browser test exercises only deterministic fake-provider flow. Actual Groq/Gemini pedagogical quality, human acceptance and staging remain separate evidence.

Known UI limit: in-progress changes prompt before refresh and link navigation, but native browser Back within App Router is not intercepted. Save before using Back; draft autosave/recovery is outside this slice. No real provider, human pedagogical review, staging deployment or previous-binary rollback drill was run.
