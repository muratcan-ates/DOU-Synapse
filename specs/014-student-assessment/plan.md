# Implementation plan — 014

## Source of truth

Branch: 014-student-assessment. Worktree: /Users/muratates/code/dou-synapse-014-student-assessment. Exact base: e59fc24a8bd4a838003f6b82d81e561800efb8d5 (local013). Remote main verified ba69ff9eec0a2867614dd145eb6e995f6c0af5ac. Other worktrees remain untouched. Migration0019_exam_duration_projection.sql reserved after checking local and remote refs; existing incoming0016 collision is not imported or renumbered.

## Ownership

- student_api_audit: exams API, schemas, config/errors, flag and focused backend tests except test_assessment.py.
- student_ui_audit: exam page/components, exam helpers/types and unit tests.
- mail_requirements: grading.py, test_grading_grounding.py and minimal test_assessment.py correction.
- root: duration helper/migration and tests, Speckit, E2E, docs, OpenAPI, governance evidence and integration.

## Design

Reuse existing approved pool, blueprint publication, exam session and answer storage. Add a safe catalog projection and paginated owner history; reuse POST start with optional topic/blueprint. A finished-result GET projects saved answers without mutations. Shared assessment advisory lock serializes answer-bearing reads and exam starts; finish closes before deciding whether to withhold results. Narrow SECURITY DEFINER duration function exposes only an owned session's duration when blueprint row visibility expires. AI scoring must reference one of the readable supplied chunks; existing two-attempt budget remains.

## Risk, rollout and rollback

R3: assessment results and source/privacy boundaries. STUDENT_ASSESSMENT_WORKSPACE_ENABLED=false is deployment default; local synthetic tests explicitly enable. Disable flag and restart API to remove new workspace endpoints; keep source and duration guards. Restoring base code would restore known bugs and requires separate review; prefer forward fix with workspace disabled. Migration is additive and retains all records. Independent engineering, domain and security/privacy approvals and real-provider source/grade calibration remain pending before student deployment.

## Verification environment

Isolated PostgreSQL cluster /private/tmp/dou014-pgdata port55440; DBs dou014_backend, dou014_grading, dou014_duration, dou014_full, dou014_sql; browser dou_synapse_e2e_dou014 at API8014/web3114. No shared/demo DB. Fake/mock and hashing providers only, blank real keys. Targeted tests, removed-guard mutation proof, full regression, types/build, real-HTTP Playwright, docs/OpenAPI, exact-candidate AI dossier validation. No production-readiness claim.
