# Tasks: AI SDLC and Engineering Excellence

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md)

## Phase 1 — Specification and boundaries

- [x] T001 Record evidence-backed current state: strong CI, no active CD, partial AI SDLC, partially institutionalized engineering excellence.
- [x] T002 Rebase isolated `004-ai-sdlc-excellence` onto merged `main` commit `2c178861`; retain the iCloud-free worktree under `~/code`.
- [x] T003 Define no-production-write/no-deployment-claim boundary.

## Phase 2 — AI change governance

- [x] T101 Add `.ai/schema.json`, `.ai/policy.json`, `.ai/README.md`, and example dossier.
- [x] T102 Implement `scripts/ai_sdlc_check.py` with diff, coverage, SHA, risk, evidence, privacy, rollout, and rollback validation.
- [x] T103 Add positive and mutation-style negative tests in `scripts/test_ai_sdlc_check.py`.
- [x] T104 Add `.github/workflows/ai-quality.yml` with reviewed-head diff and gold-set integrity checks.

## Phase 3 — PR and supply-chain controls

- [x] T201 Add `.github/CODEOWNERS` and `.github/pull_request_template.md`.
- [x] T202 Add `.github/dependabot.yml` for Actions, uv, and Bun lock ecosystems.
- [x] T203 Add least-privilege `.github/workflows/security.yml` for dependency review and CodeQL.
- [x] T204 Document action pinning, secret/container scanning, SBOM, provenance, and exception backlog without claiming unenforced controls.

## Phase 4 — Candidate delivery

- [x] T301 Add `.github/workflows/release-candidate.yml` with tag-only current-main
  admission, exact trusted push workflow/job identities, one quarantine publish,
  exact-digest product gates before admission, fail-closed schema validation,
  verifiable supply-chain evidence, and no deployment claim.
- [ ] T302 Require protected environment input and same-digest promotion contract for staging/production.
- [x] T303 Add release/rollback evidence format and post-deploy smoke contract.

T302 stays open: the same-digest contract is documented, but protected staging
and production environments do not exist yet and cannot be enforced by a
repository-only change.

## Phase 5 — Engineering operating system

- [x] T401 Add AI SDLC and engineering-excellence guides.
- [x] T402 Add ADR threshold/template and initial decision record.
- [x] T403 Add planned/measured SLO and error-budget contract.
- [x] T404 Add incident severity/timeline/corrective-action verification template.
- [x] T405 Add build-once release and rollback runbook.

## Phase 6 — Verification

- [x] T501 Run JSON parsing and validator unit/mutation cases.
- [x] T502 Parse all new workflows and verify least-privilege permissions/triggers.
- [x] T503 Run repository format/diff checks and applicable existing gates.
- [x] T504 Re-run affected gates on exact merged-`main` base `2c178861` (the rebase itself is complete).
- [ ] T505 Push the feature branch; report commit/upstream/CI separately.

**2026-08-11 local evidence:** The final governance observation records
AI/workflow/release unit controls 87/87, repository workflow policy, governance
JSON/YAML parsing, governance Ruff/format, patch hygiene and documentation truth
as passing. Exact commands, timestamp, base SHA and limitations are retained in
[local verification evidence](evidence/2026-08-11-local-verification.md).
Earlier in the same local work session the full backend 851/851 and frontend
311/311 suites, production web build and mypy also passed; the isolated backend
test database was removed afterward. Those earlier product results were not
re-run or rebound to an immutable candidate during the final documentation
observation. GitHub CI and release-candidate execution are not implied.

## Phase 7 — External enablement (not repository-completable)

- [ ] T601 Configure and verify `main` branch protection/ruleset.
- [ ] T602 Configure protected staging/production environments and independent production approval.
- [ ] T603 Configure GHCR and cloud OIDC/deployment credentials.
- [ ] T604 Prove real staging deployment, migration, Supabase Auth/Storage, real LLM, smoke, and alerts.
- [ ] T605 Perform backup-restore and rollback exercise against a non-production target.
- [ ] T606 Promote the exact staging digest to production and verify post-deploy SLO telemetry.

No Phase 7 item may be marked complete from documentation or a dry run.
