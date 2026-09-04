# Implementation plan — 015

## Source of truth
Branch 015-completion-program; worktree /Users/muratates/code/dou-synapse-015-completion-program; exact base 4e948d5fc5ec42f447838cb1e95e22f5881cb0fa. Remote main verified ba69ff9eec0a2867614dd145eb6e995f6c0af5ac. 013/014 immutable evidence is preserved. All local/remote refs checked: 015 spec and 0020 migration unused. No migration is planned. Other worktrees remain untouched.

## Ownership
- student_api_audit: core/config.py, provider configuration helper/preflight CLI, generation/llm.py, internal provenance endpoint, chat response receipt integration, provider tests, .env.example and provider docs. Own narrowly necessary schema/header changes for provenance; coordinate with evaluator.
- mail_requirements: evaluation/provenance.py, evaluate.py, backends.py, build_corpus.py, faithfulness and injection scripts; acceptance packet; test_eval_readiness.py and minimal existing faithfulness fixture changes.
- student_ui_audit: exam draft helpers, running exam and feedback recovery, question usage panel, blueprint deep links/read-only version view, lib/types and narrow lib/api.ts logout cleanup, related web tests.
- root: specs, completion ledger/skill, practice-feedback and question-usage API/schema/tests, E2E, OpenAPI/docs synchronization, environment, unified verification, immutable AI dossier/evidence and local integration commit.

## Design
Reuse stored answers and existing source-validation projection for a read-only practice feedback endpoint. Serialize help reads with exam starts under the existing user assessment lock. Instructor question usage uses course-scoped joins and keyset pagination; metadata only. Draft cache stores unsent strings in sessionStorage, restored only after fresh server checks. Read-only blueprint deep links reuse existing paper APIs. Provider configuration has one safe allowlist snapshot/digest; protected eval runtime and per-response receipts distinguish configured capability from actual outcome. Existing human faithfulness labels/scoring are reused. Corpus builder validates three DSNs before any write.

## Rollout and rollback
Existing STUDENT_ASSESSMENT_WORKSPACE_ENABLED controls practice feedback; existing instructor RBAC controls usage metadata. EVAL_RUNTIME_ENABLED=false by default and forbidden in production; evaluation secret unset closes endpoint. Disable eval mode/secret and restart to remove provenance surface. Disable student workspace for its new reads; retain source and exam safety guards. No destructive data migration. Independent engineering, domain and privacy approvals remain pending before student deployment. Complete reviewable local work before any final human gate.

## Verification
Reuse isolated stopped cluster /private/tmp/dou014-pgdata on port55440 with new DBs dou015_root, dou015_provider, dou015_eval, dou015_full and dou_synapse_e2e_dou015. API8015/web3115. Existing DBs are not used. Targeted API/UI tests and removed-guard proof, full pytest/Vitest, Ruff/mypy/types/build, Playwright real HTTP with explicit fake/hash provider, OpenAPI/docs/goldset/contrast, exact-candidate AI lineage validation. Real probes require actual keys and are never implied by local tests.
