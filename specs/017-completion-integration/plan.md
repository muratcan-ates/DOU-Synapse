# Plan — 017

## Identity and reservation
Worktree /Users/muratates/code/dou-synapse-017-completion-integration; branch 017-completion-integration. Starting base 0b70847165b2b12cc4df0652d617f79c0c27c2f5. Integration comparison base GitHub main ba69ff9eec0a2867614dd145eb6e995f6c0af5ac, reverified 2026-09-07. All local refs, remote branches and worktrees scanned. No active competing task found. Root reserves feature017 and, after scanning every local/remote ref, migration0020_policy_audit_cascade on 2026-09-07 for the reproduced course-delete audit foreign-key failure. Import PR23 migration0016_api_contract_admin_access only; old009/010 assessment_integrity0016 is not an incoming lane. Existing0018/0019 retained;0017 remains unclaimed by this work.

## Ownership
- product_gap_audit: exam running/finished UI and required helper, new focused E2E tests, exams.py hint-zero boundary and its focused API test. DB dou017_product.
- quality_acceptance_audit: acceptance prepare_packet, faithfulness score_labels, test_eval_readiness/test_faithfulness_scoring and their README guidance; no DB/network.
- lineage_delivery_audit: API Dockerfile and test_evaluation_runtime; narrowly required packaging test.
- root: merges/conflict resolution, main.py/CI/shared config, this spec/ledger, environment, full validation, aggregate .ai and PR preparation. Agents do not stage or commit.

## Isolated environment
New cluster /private/tmp/dou017-pgdata on localhost55447; socket /private/tmp/dou017-pgsocket. Unique dou017_* DBs, E2E DB dou_synapse_e2e_dou017. API8017/web3117. No shared database or existing lane environment copied. Fake/hash provider for local verification, eval runtime disabled except explicit isolated contract tests.

## Integration
Simulate PR25 e4f30d7ee98a2fdee62b2c19d46024f178d80dc9 and PR23 fbc142734ea7f1b56c79f2972c154080249a77cd. Preserve ancestry with merges. Resolve documentation conflicts using current product behavior and newly measured results. Preserve 015 evaluation initialization, quota model parametrization, authoring mutations and feature flags alongside PR23 docs gate/readiness.

## Validation and promotion
Targeted regressions first, full API/RLS/mutations/web/types/build/real-HTTP browser next; OpenAPI/docs/contrast and exact main→candidate governance. Container build can run in PR CI if local runtime absent. Prepare reviewable PR after local fixes. Engineering/domain/security approvals remain pending; do not change main or production. Final aggregate dossier+evidence added together after all product/document edits; no later source commit without new evidence revision.

## Discovered integration regression
Real HTTP browser tests found course deletion rolled back because the policy audit DELETE trigger inserted an audit row after its parent course disappeared during cascade. Root assigns quality_acceptance_audit migration0020_policy_audit_cascade.sql plus focused SQL/API regressions in a new test file; DB dou017_cascade. Direct policy deletion must remain audited while whole-course cascade must not create an orphan. No existing migration is edited.
