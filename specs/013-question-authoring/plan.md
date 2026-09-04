# Plan and lane reservation

Exact base: ba69ff9eec0a2867614dd145eb6e995f6c0af5ac. Worktree: /Users/muratates/code/dou-synapse-013-question-authoring.

## Coordination record — 2026-09-04

All local heads and known remote heads in the authoritative ~/code/DOU-Synapse repository were scanned. Remote branch list was checked through GitHub. 009-assessment-integrity and 010-api-observability remain unmerged candidates; prior existing worktrees are untouched. Root integrator reserves feature 013 and migration 0018_question_authoring.sql for this lane. Dossier IDs 010–012 already occur in PR branches. Migration 0016 has an existing collision (assessment integrity vs API contract admin access); 0017 is API observability. This lane neither renumbers nor imports those migrations. 0018 depends only on merged 0001–0015 and is additive; the gap preserves reservations. Future integration must reconcile the pre-existing 0016 collision independently.

## Ownership

- authoring_backend: API questions, assessment schemas/helper, config flag, central errors, focused backend tests, .env.example flag.
- assessment_contract_review: new migration0018 and direct SQL/mutation tests.
- authoring_frontend: question page, focused editor components/helpers, web types and tests.
- root: Speckit, E2E, documentation, OpenAPI, dossier/evidence, integration and final validation.

## Design

Reuse existing question_gen classification parameters and payload schemas. No new model calls or packages. POST draft update follows this repository's mutation/CORS convention. Lock before validating draft state; review uses same row lock. Database column grants and trigger preserve reviewed and referenced content, validate relational classification. Keep one current question record; do not retrofit snapshots or duplicate official/practice workflows from branch009.

## Risk and rollout

R3 because edited content feeds assessment. QUESTION_AUTHORING_ENABLED=false is the deployment default and authoring kill switch; use true only for local deterministic validation initially. Authoring state is queried for UI clarity, server checks remain authoritative. No staging or production exposure in this task. Independent engineering/domain/security review and real-provider calibration of classified generation remain prerequisites for learner rollout. Source/prompt/provider are unchanged except existing classification inputs now reach the generator.

Rollback disables the flag and deploys the previous application, retaining the additive DB guard and authored records. Do not drop the guard or rewrite reviewed questions as a rollback. Mixed deployments cannot author via old app; legacy nullable classification generation stays compatible.

## Verification

Temporary PostgreSQL cluster: /private/tmp/dou013-pgdata, port55439. Backend DB dou013_backend; root full-suite DB dou013_full; SQL agent owns dou013_sql/mutation DBs; browser DB dou_synapse_e2e_dou013. No shared/demo database. All provider tests use fake and hashing modes, blank real API keys. Targeted tests first, full suite/types/build and browser after integration. Mutation proof targets immutable content and course classification. Browser proves full teacher journey and draft edit, not model quality.
