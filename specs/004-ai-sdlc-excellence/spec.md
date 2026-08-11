# Feature Specification: AI SDLC and Engineering Excellence

**Feature Branch**: `004-ai-sdlc-excellence`

**Created**: 2026-08-11

**Status**: Local working-tree candidate under final audit; not yet committed,
pushed, or observed in GitHub CI; external enablement pending

**Base**: `2c178861` (`main`; PR #4 merged after all five required checks passed)

**Input**: Establish enforceable CI/CD, AI SDLC, supply-chain, reliability, and engineering-governance controls without claiming an unconfigured cloud deployment as production.

## User Scenarios & Testing

### User Story 1 - Traceable AI behavior changes (Priority: P1)

As the engineering and course owners, we can see exactly which prompt, model, provider, embedding space, retrieval setting, corpus, evaluator, and guardrail changed and which evidence supports promoting it.

**Why this priority**: The repository has strong evaluation tools, but an AI behavior change can currently merge without a current-SHA AI quality decision.

**Independent Test**: Change an AI-sensitive file without a valid manifest and confirm the AI gate fails; add a complete manifest with matching artifact hashes and confirm it passes.

**Acceptance Scenarios**:

1. **Given** an AI-sensitive file changed, **when** no change dossier covers it, **then** CI fails closed with the uncovered paths.
2. **Given** a manifest names an artifact hash that differs from the repository, **when** the gate runs, **then** promotion is rejected as unreproducible.
3. **Given** evidence is fake-provider or offline-only, **when** a production-grade claim is requested, **then** the record preserves that limitation instead of upgrading the evidence label.
4. **Given** an R2 or R3 change, **when** approval and rollout are planned, **then** named non-author owners, stop conditions, kill switch, and rollback are required.
5. **Given** a dossier already exists in the reviewed base, **when** it is
   corrected or advanced, **then** a new append-only revision binds the exact
   previous path and SHA-256, preserves lineage, advances by one, follows an
   allowed status transition and cannot fork or lower risk.
6. **Given** a dossier requests `canary`, `rolled-back` or `closed`, **when** the
   validator runs, **then** state-specific provider/environment, immutable named
   approval, deployment/flag and hash-bound rollback evidence are required;
   production success and rollback-before-production are distinct close paths.

---

### User Story 2 - Enforced pull-request and supply-chain quality (Priority: P1)

As maintainers, we receive fast required signals for code quality, dependency risk, security ownership, secret exposure, and build integrity before changes reach the shared branch.

**Why this priority**: At the `2c178861` base, CI was already substantial, but
type checking was advisory and ownership, dependency review, CodeQL, SBOM,
provenance, and PR policy were not represented in the repository.

**Independent Test**: Open a pull request that violates one new policy and verify the corresponding job turns red; inspect generated security/release artifacts for the reviewed commit.

**Acceptance Scenarios**:

1. **Given** a pull request, **when** required metadata or evidence is missing, **then** the PR checklist exposes the gap and the applicable machine gate fails.
2. **Given** sensitive paths change, **when** review is requested, **then** CODEOWNERS identifies the accountable owner.
3. **Given** a dependency change, **when** the security workflow runs, **then** dependency and static-analysis findings are visible without leaking secrets.
4. **Given** a third-party action or artifact, **when** it is promoted, **then** source-to-artifact identity is retained and exceptions are explicit and expiring.

---

### User Story 3 - Build once and promote safely (Priority: P1)

As release operators, we build one immutable candidate, retain its digest and evidence, and promote that same candidate through staging and production approval rather than rebuilding different binaries.

**Why this priority**: The existing image job validates a local image but explicitly does not publish or deploy it; that is CI, not CD.

**Independent Test**: Push a `v*` tag whose event SHA equals the current
`origin/main` HEAD; verify trusted workflow/job identities on that exact SHA,
publish once to quarantine, pull and test the exact digest, and only then admit
it with schema-valid, verifiable SBOM/provenance/evidence references. Deployment
remains unavailable until protected environments and credentials are configured.

**Acceptance Scenarios**:

1. **Given** a `v*` tag push whose event SHA equals current `origin/main` HEAD,
   **when** candidate build runs, **then** trusted workflow/job identities on
   that exact push SHA are complete and successful, one quarantine digest is
   generated, the pulled digest passes offline embedding/bake/RSS checks, and
   only that digest may be admitted. Manual/ref-selected/historical-main
   admission is unavailable.
2. **Given** staging credentials are absent, **when** the workflow runs, **then**
   candidate admission may succeed but candidate evidence can record only
   staging/production `not-configured`; it contains no promotion object and is
   never reported as deployed.
3. **Given** production promotion, **when** staging evidence or environment approval is absent, **then** production is blocked.
4. **Given** a deployment failure, **when** rollback is initiated, **then** the previous digest and compatibility constraints are known and post-rollback smoke verification is required.

---

### User Story 4 - Reliability and incident learning (Priority: P2)

As product operators, we define measurable service objectives for the journeys students and instructors depend on, alert on actionable error-budget burn, and turn incidents into verified preventive controls.

**Why this priority**: Keepalive checks availability opportunistically but is not monitoring, an SLO, an alert, or a recovery exercise.

**Independent Test**: Walk a synthetic incident through severity, timeline, containment, rollback, and corrective-action verification using the documented templates.

**Acceptance Scenarios**:

1. **Given** an SLO, **when** it is reviewed, **then** it has an SLI source, target, window, owner, data-quality rule, and runbook.
2. **Given** no telemetry source exists, **when** an SLO is proposed, **then** it stays `planned`, not `measured`.
3. **Given** an incident closes, **when** corrective actions remain unverified, **then** the learning record remains open.

---

### User Story 5 - Measurable engineering improvement (Priority: P3)

As the team, we can improve delivery speed and stability using a versioned scorecard and service-level DORA/flow signals without ranking individuals or treating missing data as zero.

**Independent Test**: Produce a scorecard in which every control has a state, owner, evidence, target, and next experiment, and missing telemetry is visibly marked unavailable.

## Edge Cases

- An AI file is renamed, deleted, generated, or changed only through configuration.
- A manifest uses a mutable model alias, stale base SHA, expired exception, or hash from another branch.
- Multiple manifests cover one file with incompatible risk tiers.
- A security job is skipped because of permissions, fork context, or absent GitHub feature support.
- A workflow builds successfully but artifact upload, attestation, staging, smoke, or rollback verification fails.
- A migration is irreversible or incompatible with the previous application digest.
- Real-provider secrets are unavailable; deterministic PR checks must remain useful without pretending to prove model quality.
- SLO telemetry is missing, delayed, duplicated, or contains personally identifiable student content.

## Requirements

### Functional Requirements

- **FR-001**: The repository MUST contain a machine-readable AI change schema and quality policy.
- **FR-002**: AI-sensitive changes MUST be detected from the reviewed diff, not from an author checkbox alone.
- **FR-003**: Each covered artifact MUST carry a reproducible path and SHA-256 digest.
- **FR-004**: The dossier MUST distinguish fake-provider, offline, real-provider, staging, canary, and production evidence.
- **FR-005**: R1/R2/R3 risk MUST determine evidence, approval, rollout, and rollback requirements.
- **FR-006**: AI gate failures MUST list actionable missing or stale fields without printing secrets or student content.
- **FR-007**: Calibration and holdout MUST remain separate and thresholds MUST be declared before candidate scoring.
- **FR-008**: A changed evaluator MUST NOT be the only judge of its own change without a stable human-reviewed anchor.
- **FR-009**: Production AI claims MUST require current-candidate real-provider and named human evidence; deterministic CI alone MUST NOT satisfy them.
- **FR-010**: The repository MUST define ownership and a pull-request evidence template.
- **FR-011**: Security analysis MUST cover source and dependency changes with least-privilege workflow permissions.
- **FR-012**: Dependency update automation MUST cover GitHub Actions, Python, and Bun/npm ecosystems.
- **FR-013**: Third-party actions and release artifacts MUST have an immutable-identity migration plan; unpinned controls MUST remain visible debt until migrated.
- **FR-014**: Delivery MUST admit only a `v*` push event SHA equal to current
  `origin/main` HEAD, verify exact trusted workflow/job identities on that push
  SHA, publish once to quarantine, pull and test that exact digest, and only
  then admit it only through an immutable evidence record with verifiable SBOM,
  provenance and attestation references; no mutable admitted tag is created.
- **FR-015**: Staging and production MUST promote the same digest; production MUST require an environment approval.
- **FR-016**: Missing deployment credentials MUST yield `not configured`, not a successful deployment claim.
- **FR-017**: Database delivery MUST define preflight, backup, migration serialization, compatibility, and rollback/forward-fix rules.
- **FR-018**: Post-deploy and post-rollback readiness/smoke evidence MUST be retained.
- **FR-019**: SLOs MUST define journey, SLI, source, target, window, owner, alert, and runbook.
- **FR-020**: Incident records MUST be blameless, time-ordered, and keep corrective actions open until behavior is verified.
- **FR-021**: ADRs MUST preserve superseded history and include operational, security, cost, migration, observation, and reversal consequences.
- **FR-022**: Engineering scorecards MUST distinguish documented, configured,
  enforced, and observed controls and retain owner/reviewer, trigger, exact
  evidence and observation time, failure policy, bypass/audit, current risk,
  target/next action, due date, and exception expiry.
- **FR-023**: Flow metrics MUST distinguish no activity from missing data and MUST NOT rank individuals.
- **FR-024**: Existing CI and application behavior MUST remain unchanged unless a new gate explicitly owns that behavior.
- **FR-025**: The feature MUST NOT modify production data or deploy external services without its own green evidence and explicit authorization.
- **FR-026**: AI dossiers and evidence reports MUST be append-only. Every later
  revision MUST preserve lineage, supersede one exact base record by path and
  SHA-256, increment exactly once, follow the allowed transition graph, prevent
  forks and risk downgrade, and leave prior records unchanged.
- **FR-027**: Canary MUST require candidate-bound real-provider/canary evidence
  and immutable named approvals; rolled-back MUST require bound rollback
  evidence and a disabled flag; closed MUST require either verified production
  success or verified rollback-before-production, never narrative attestation.

### Key Entities

- **AI Change Dossier**: Append-only immutable revision of risk, artifact
  identities, data digests, evaluation, named approvals, deployment, rollout,
  telemetry and rollback, chained to its exact predecessor by path and SHA-256.
- **AI Quality Policy**: Machine-readable path classification and minimum evidence/risk rules.
- **Release Candidate Evidence**: Current-main source SHA, trusted workflow/job
  identities, quarantine and admitted immutable digest, exact-digest product
  gates, and verifiable SBOM/provenance/attestation references; it cannot claim
  deployment.
- **Promotion Evidence**: A later append-only staging or production record for
  the same admitted digest, with immutable approver identity/reference/time/SHA,
  migration, backup, smoke, and rollback evidence.
- **Engineering Control**: A control state, owner, evidence, bypass, target, exception, and expiry.
- **SLO Record**: Journey, SLI source, target/window, budget, owner, alert, and runbook.
- **Incident Record**: Severity, impact, timeline, containment, recovery, contributing conditions, and verified actions.
- **ADR**: Immutable decision history and reversal/migration consequences.

## Success Criteria

- **SC-001**: 100% of AI-sensitive changed paths are covered by a valid, hash-matching dossier or CI fails.
- **SC-002**: The validator's positive and negative unit cases pass without network, database, or provider secrets.
- **SC-003**: Pull requests receive separate core CI, AI-governance, and security/supply-chain signals.
- **SC-004**: A tag-only candidate run can bind current-main source SHA and
  trusted push workflow identities, quarantine one image, admit only the exact
  pulled digest that passed offline embedding/bake/RSS checks, and retain
  schema-valid verifiable supply-chain evidence without claiming deployment.
- **SC-005**: Production promotion cannot execute without explicit environment approval and staging evidence.
- **SC-006**: Every published SLO is either backed by an observable source or explicitly marked planned/unmeasured.
- **SC-007**: Every control in the initial scorecard has a state,
  owner/reviewer, trigger, exact evidence and observation time, failure policy,
  bypass/audit path, current risk, target and next action, due date, and
  exception expiry.
- **SC-008**: No existing feature, migration, API contract, or student/instructor data is changed by the first infrastructure slice.

## Assumptions

- GitHub Actions remains the CI/CD orchestrator.
- GHCR is the default immutable container registry; real Azure/Vercel/Supabase credentials and environments are configured separately.
- Normal PRs use deterministic/fake-provider evidence; real-provider holdout runs execute only in a protected environment with separate eval keys.
- PR #4 was merged as `2c178861` after its five checks passed; this feature starts from that exact `main` commit.
- Branch protection and GitHub Environment approval are external settings and require live verification after repository files land.
