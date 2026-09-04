# 015 local verification — 2026-09-04

Branch `015-completion-program`; exact base `4e948d5fc5ec42f447838cb1e95e22f5881cb0fa` (local014 including013). Candidate is the commit containing this report, bound as SELF in the new AI dossier. Main remains `ba69ff9eec0a2867614dd145eb6e995f6c0af5ac`; no upstream push, merge, PR CI, staging or production deployment.

## Executed results

| Gate | Result |
|---|---:|
| Full API pytest | 1154 passed, 0 failed |
| Stored practice feedback / usage + workspace/envelope regression | 81 passed |
| Provider/runtime/chat/generation/internal/config regression | 151 passed |
| Final quota-order regression | 17 passed |
| Evaluation provenance/DSN/packet/scorer regression | 107 passed |
| Web library tests | 421 passed, 0 failed |
| Full real-HTTP Playwright | 38 passed, 0 skipped |
| AI governance validator tests | 76 passed |
| Ruff / format / mypy | pass;105 app source files |
| Web TypeScript / production build | pass |
| Docs / light-dark contrast | pass |
| Goldset/source integrity | pass;40 calibration,161 holdout,159 parsed source locations |
| OpenAPI | 57 paths;both new GET contracts asserted |
| Synthetic backup/restore | 27 public tables with matching row counts;app function count preserved |
| Corpus-builder real API/worker smoke | completed source,6 chunks,student membership;password-free manifest |
| Provider offline preflight | expected blocked/missing credentials;0 provider calls;quality not_evaluated |

All model-facing executed proof uses fake/hash or injected transports. A completed injected transport is a contract test, not a live model result. Local text extraction checked29 PDF pages with no page below30 extracted characters; current sample packet does not require OCR. The acceptance packet binds22 source hashes and5 grading-form drafts; human scores and approvals remain blank.

## Reproduction

```sh
# apps/api; fixtures recreate only the named isolated database
PGHOST=localhost PGPORT=55440 PGUSER=muratates \
PG_BIN=/opt/homebrew/opt/postgresql@16/bin TEST_DB_NAME=dou015_full \
TEST_ADMIN_DSN=postgresql+psycopg://muratates@localhost:55440/dou015_full \
TEST_APP_DSN=postgresql+psycopg://dou_app:dou_app_local@localhost:55440/dou015_full \
TEST_WORKER_DSN=postgresql+psycopg://dou_worker:dou_worker_local@localhost:55440/dou015_full \
GROQ_API_KEY='' GEMINI_API_KEY='' EMBEDDING_PROVIDER=hashing \
env -u LLM_FAKE_PROVIDER -u EMBEDDING_WARMUP_ENABLED .venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy app
# apps/web; API already uses isolated browser DB and explicit fake/hash providers
E2E_API_URL=http://localhost:8015 E2E_PORT=3115 \
E2E_DATABASE_NAME=dou_synapse_e2e_dou015 PGHOST=localhost PGPORT=55440 \
PGUSER=muratates PG_BIN=/opt/homebrew/opt/postgresql@16/bin \
./node_modules/.bin/playwright test --workers=1
bun test lib/
./node_modules/.bin/tsc --noEmit --incremental false
node scripts/contrast.mjs
# repository root
node scripts/docs_check.mjs
apps/api/.venv/bin/python evaluation/verify_gold_set.py
apps/api/.venv/bin/python -m unittest scripts/test_ai_sdlc_check.py
DEV_AUTH_ENABLED=true apps/api/.venv/bin/python scripts/provider_preflight.py --offline
```

API8015/web3115; PG16+pgvector port55440. Unique DBs dou015_root, dou015_provider, dou015_eval, dou015_full; browser dou_synapse_e2e_dou015; corpus smoke dou015_eval_corpus; local restore dou_synapse_restore_dou015. No shared/demo database used. Browser flags QUESTION_AUTHORING_ENABLED and STUDENT_ASSESSMENT_WORKSPACE_ENABLED true; DEV_AUTH_ENABLED true; LLM_FAKE_PROVIDER true; EMBEDDING_PROVIDER hashing; EVAL_RUNTIME_ENABLED false. CORS only local web URL. Production web build is run by Playwright.

## What changed and what the proof catches

A student selects an answer, reloads and gets the unsent draft back, submits and the draft disappears, reloads an answered practice question and receives saved source-grounded feedback. A timed exam blocks old result and practice-feedback reads; finishing preserves source cards. Instructor replaces source material, follows the stale-question usage list to the precise published version and sees a read-only paper.375px light/dark paper/result screenshots were inspected; no horizontal overflow.

Backend negatives prove owner vs instructor/peer/course, practice-only route, default-off feature, active-exam serialization, source revalidation without regrading, course-scoped usage and timestamp/UUID pagination. Removing the practice help lock exposes a solution and makes the same protection assertion fail. Historical answer/mastery records remain unchanged.

Independent code review found six defects in the initial evaluation implementation: environment proxy secret routing; inherited PGHOSTADDR/wrong host routing; one receipt replayed across questions; contradictory receipt flags/targets; modified checkpoint answer/derived metrics; identical application/evaluation keys. Each was fixed and the independent reviewer reran the memory-only reproductions successfully. This is automated code review, not independent human release/domain approval.

A real corpus setup smoke also found the old local_dev_setup.sql assumed a shared database. Builder now uses pre-provisioned app/worker LOGIN roles, validates all three exact host/port/database targets before writes, sanitizes PG routing environment and grants CONNECT only on the selected isolated corpus. No global role passwords are changed.

The first full API run was1152 passed/1 failed: an old quota-order test assumed every default model had a calibrated token ceiling. The test now separately checks measured-model optimization and the new unmeasured default's conservative byte ceiling; reservation-before-provider remains mandatory and runtime quota code was not weakened. Final full run1154 passed. Initial new browser failures were upload-envelope/list-route/ambiguous/exact-text test assumptions; selectors/contracts were corrected, then the entire38-test suite passed.

## Remaining boundary

Actual provider access/quality, real grading run, teacher source approval, independent human labels, main-targeted whole-diff governance/PR CI, Docker container build, real Auth/Storage/worker deployment, staging/PITR/rollback and live acceptance were not run. Docker executable was unavailable; real model keys were absent. Local database restore does not establish staging restore/PITR. See release-review.md, docs/completion-program.md and evaluation/acceptance/README.md. Do not call this production verified.
