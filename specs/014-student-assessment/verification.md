# 014 local verification — 2026-09-04

Branch `014-student-assessment`, exact base `e59fc24a8bd4a838003f6b82d81e561800efb8d5` (local013). Candidate identity is the commit containing this report, bound as SELF in the AI dossier. No upstream, merge, staging or production deployment. Prior main remains `ba69ff9eec0a2867614dd145eb6e995f6c0af5ac`.

## Executed outcomes

| Check | Result |
|---|---:|
| Full API pytest | 1040 passed, 0 failed |
| Final focused workspace/assessment/source/duration regression | 168 passed |
| New workspace cases, including legacy source and lock races | 55 passed |
| New grading source cases | 28 passed |
| New duration SQL/API/privilege cases | 11 passed |
| Frontend library suite | 411 passed, 0 failed |
| Full real-HTTP Playwright | 38 passed, 0 skipped |
| AI governance validator tests | 76 passed |
| Ruff, format, mypy | pass; 99 application source files typed |
| Frontend TypeScript and production build | pass |
| Docs gate and light/dark contrast | pass |
| Gold-set structural/source integrity | pass; 40 calibration / 161 holdout / 159 parsed source locations |
| OpenAPI | 55 paths; new GET contracts asserted |

All provider-facing evidence is fake/mock + hashing. Tests use isolated PostgreSQL16+pgvector port55440: dou014_full, dou014_backend, dou014_grading, dou014_duration; browser dou_synapse_e2e_dou014 with API8014/web3114. No real students or live model calls.

## Reproduction

```sh
# apps/api; fixtures recreate only the named isolated database
PGHOST=127.0.0.1 PGPORT=55440 PGUSER=muratates \
PG_BIN=/opt/homebrew/opt/postgresql@16/bin TEST_DB_NAME=dou014_full \
TEST_ADMIN_DSN=postgresql+psycopg://muratates@127.0.0.1:55440/dou014_full \
TEST_APP_DSN=postgresql+psycopg://dou_app:dou_app_local@127.0.0.1:55440/dou014_full \
TEST_WORKER_DSN=postgresql+psycopg://dou_worker:dou_worker_local@127.0.0.1:55440/dou014_full \
GROQ_API_KEY='' GEMINI_API_KEY='' EMBEDDING_PROVIDER=hashing \
env -u LLM_FAKE_PROVIDER -u EMBEDDING_WARMUP_ENABLED .venv/bin/pytest -q
.venv/bin/ruff check app tests/test_exam_workspace.py tests/test_exam_duration_projection.py tests/test_grading_grounding.py tests/test_error_envelope.py
.venv/bin/ruff format --check .
.venv/bin/mypy app
# apps/web; API must already use this isolated database and fake/hash providers
PGHOST=127.0.0.1 PGPORT=55440 PGUSER=muratates \
E2E_API_URL=http://127.0.0.1:8014 E2E_PORT=3114 \
E2E_DATABASE_NAME=dou_synapse_e2e_dou014 ./node_modules/.bin/playwright test --workers=1
bun test lib/
./node_modules/.bin/tsc --noEmit --incremental false
node scripts/contrast.mjs
# repository root
node scripts/docs_check.mjs --duzelt
python3 -m unittest scripts/test_ai_sdlc_check.py
```

Browser API settings: ENVIRONMENT=local, DEV_AUTH_ENABLED=true, QUESTION_AUTHORING_ENABLED=true, STUDENT_ASSESSMENT_WORKSPACE_ENABLED=true, LLM_FAKE_PROVIDER=true, EMBEDDING_PROVIDER=hashing, EMBEDDING_WARMUP_ENABLED=false; real keys blank. CORS allows only the local test web URL. Production build is created by Playwright.

## What the new proof establishes

The synthetic teacher creates source/topic/outcome, generates and approves questions, publishes a blueprint through HTTP. Student selects a topic from two available topics, sees only its approved question, gets a source card on a wrong answer, finishes practice, joins a published timed exam, cannot reopen old solutions during it, clears remembered selection, resumes from server history without resetting expiry, submits/finishes and reloads the persisted source-backed result. 375px light/dark result and dark history screenshots were inspected without horizontal overflow.

Database/API negatives cover own vs peer/instructor/admin, PUBLIC/worker execution, closed enrollment window, revoked membership, read-only saved results and default-off flag. Removing the duration owner predicate inside a rolled-back test transaction makes the same isolation assertion fail; bypassing the result lock makes the response assertion fail. Real concurrent read/start and hint/finish transactions verify ordering.

Before the source fix, 25 of28 new grading cases failed; valid-source controls passed. Before wall-clock correction, all3 queued-deadline cases failed (late answer, closed admission, pre-wait start time); all pass after correction. Old source-free AI answers and sources that become empty/unreadable are now withheld on all result/aggregate projections without rewriting saved answers. Existing mastery is not backfilled; finish does not add mastery for such rows.

An initial full run found only the expected OpenAPI path-count change (52→55); the contract assertion now also requires all three GET routes and the full suite was rerun. Browser setup first used the wrong local PG port, then a new test selector assumed a radio value attribute; both test setup issues were corrected before the clean full run. No application guard was weakened to make tests pass.

## Remaining acceptance boundary

No semantic source-faithfulness or pedagogical grading claim is made. The existing real-provider holdout must be rerun and the instructor must evaluate answer/rubric quality. Independent engineering, domain and security/privacy approvals are pending. No real-provider, staging, canary, production or deployed rollback evidence exists for014. The deployment flag remains disabled by default.013 is also local-only; a main-targeted integration must validate the entire combined diff with its own exact-base governance record.

Operational rollback disables the workspace flag, retaining source/time guards and records. Prefer a forward fix; restoring the base application would reintroduce the bugs corrected here. Practice feedback from an individual answer is not restored until the session is finished; unsubmitted browser drafts are not persisted across reloads. Existing multiple timed legacy sessions remain supported and each can be closed safely.
