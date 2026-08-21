# Local verification evidence — 2026-08-11

## Evidence identity and scope

- **Observed at:** `2026-08-11T03:43:58+03:00`
- **Branch:** `004-ai-sdlc-excellence`
- **Base/HEAD at observation:**
  `2c178861a3e484af8643f999f210db040eb84e68`
- **Upstream:** unavailable
- **Candidate binding:** none. The feature files were still an uncommitted local
  working-tree candidate. These results cover the filesystem snapshot observed
  locally; they are not evidence for an immutable commit, pull request, GitHub
  Actions run, tag, image digest, staging deployment or production deployment.
- **Privacy:** no secret, token, prompt/answer body, student identifier, uploaded
  document content or external service payload is retained here.

## Commands and observed results

| Check | Exact command | Result |
|---|---|---|
| AI governance unit/mutation suite | `python3 -m unittest scripts.test_ai_sdlc_check` | PASS — 47 tests |
| Workflow policy unit/mutation suite | `apps/api/.venv/bin/python -m unittest scripts.test_workflow_policy_check` | PASS — 14 tests |
| Repository workflow policy | `apps/api/.venv/bin/python scripts/workflow_policy_check.py` | PASS — `WORKFLOW_POLICY_CHECK=PASS` |
| Release evidence and trusted-check suite | `python3 -m unittest discover -s .release -p 'test_*.py'` | PASS — 26 tests |
| Governance control total | Sum of the three independent unit suites above | PASS — 87 tests |
| Governance JSON parse | Parse `.specify/feature.json`, `.ai/**/*.json`, `.release/**/*.json` with Python stdlib | PASS — 7 files |
| Workflow/config YAML parse | Parse `.github/workflows/*.yml` and `.github/dependabot.yml` with PyYAML from the project environment | PASS — 6 files |
| Documentation truth | `UV_CACHE_DIR=/private/tmp/dou-ai-sdlc-docs-uv node scripts/docs_check.mjs` | PASS — 93 documents; all live counts matched source-derived inventory |
| Governance lint | `RUFF_CACHE_DIR=/private/tmp/dou-ai-sdlc-ruff apps/api/.venv/bin/ruff check ...` | PASS |
| Governance format | `RUFF_CACHE_DIR=/private/tmp/dou-ai-sdlc-ruff apps/api/.venv/bin/ruff format --check ...` | PASS — 9 files already formatted |
| Patch hygiene | `git diff --check` | PASS |

The documentation truth check reported the current source-derived inventory as
851 backend tests, 311 frontend library tests and 33 Playwright tests. Those are
collection/list counts, not proof that the full product suites ran during this
final documentation observation. The earlier full product-suite results remain
separate local session evidence in `tasks.md`; they were not rebound here to an
uncommitted candidate.

## What this evidence proves

- The local AI governance validator's positive and mutation-style negative
  cases passed, including immutable lineage/revision, state-specific approval,
  rollback and close-path rules.
- The local workflow policy rejected unsafe workflow identities in its unit
  suite and accepted the repository files in the observed working tree.
- The local release evidence/trusted-check schema and verifier cases passed.
- Owned JSON/YAML/Markdown files were parseable and internally consistent at
  the observation time.

## Limitations and open external evidence

- No reviewed candidate SHA exists yet. The bootstrap dossier/example hash must
  be finalized only after an explicitly authorized commit candidate exists.
- No GitHub PR/Actions run, required-check ruleset, Code Owner review, protected
  `release-candidate`/staging/production Environment or audit-visible bypass was
  observed.
- The AI suite is deterministic/offline. It did not call a real provider,
  measure model quality, authenticate an external approval, route canary
  traffic, exercise a live kill switch or observe production telemetry.
- No tag was pushed; no image was published to quarantine; no registry digest,
  SBOM, provenance, attestation, candidate admission or promotion record was
  produced.
- No live staging migration, Supabase Auth/Storage, backup/restore, rollback,
  alert delivery, SLO observation or production promotion was performed.

Therefore this evidence supports a local working-tree audit only. It must not be
used to label the repository `enforced`, `observed`, deployed or
production-ready.
