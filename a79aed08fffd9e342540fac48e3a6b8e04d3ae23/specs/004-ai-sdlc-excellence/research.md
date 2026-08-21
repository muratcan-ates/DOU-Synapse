# Research: AI SDLC and Engineering Excellence

## Current-state findings

### CI exists and is substantive

The current CI runs API lint/format/type/test, clean PostgreSQL migrations, RLS mutation checks, container/offline embedding checks, web type/unit/accessibility/build, documentation truth, and real API/browser E2E. This is a strong CI baseline.

At the feature base, the pipeline was not fully enforced engineering excellence:
mypy was advisory, dependency installation bypassed the lockfile, no repository
ownership/PR template existed, and dependency review, CodeQL, SBOM, provenance,
attestation, or immutable deployment promotion was absent.

### CD does not exist yet

The image job explicitly does not push. `keepalive.yml` is a scheduled readiness ping, not deployment or monitoring. Cloud setup and rollback are written as manual instructions and remain unverified. Therefore the honest state is **CI present; CD not active**.

### AI SDLC is partial but unusually strong for a student project

Existing strengths include calibration/holdout separation, a versioned gold set, retrieval and E2E harnesses, bootstrap/McNemar metrics, citation and scope guardrails, prompt-injection boundaries, provider fallback telemetry, embedding provenance, and privacy-controlled user feedback.

The missing closed loop is: AI artifact change → current-SHA real-provider evidence → independent human/domain approval → automated promotion decision → canary/production monitoring → verified rollback → feedback converted into regression evidence.

### Engineering excellence is practiced but not institutionalized

Speckit, a constitution, isolated worktrees/test databases, source-derived docs, RLS mutation tests, typed contracts, and runbooks exist. Missing repository-level controls include CODEOWNERS, PR evidence template, ADR history, SLO/error-budget definitions, incident-action verification, dependency/security automation, build provenance, and DORA/flow event definitions.

## Decisions

### D1 — Preserve the core CI behavior and strengthen its contract

PR #4 merged as `2c178861` after all five checks passed. Preserve those jobs and
their behavior, but make mypy blocking, install from the frozen locks, apply
least-privilege permissions/timeouts, and pin every third-party action by full
commit SHA. AI, security, and release jobs remain separate workflows so their
permissions and failure ownership stay narrow.

### D2 — Gate AI changes with a repository dossier

Use `.ai/policy.json`, `.ai/schema.json`, and `.ai/changes/*.json`. The validator computes changed paths and SHA-256 values from the reviewed commit. Author checkboxes are supplementary, never the source of truth.

Dossiers and evidence are append-only snapshots. A later record keeps a stable
lineage, increments revision exactly once, and supersedes the exact previous
base-record path and SHA-256. The validator rejects parent forks, duplicate
revisions, status skips, risk downgrades and base-record rewrites. State is also
machine-bound: canary needs real-provider/canary evidence and immutable named
approvals; rollback needs exact candidate/deployment/report binding; closed is
either verified production success or verified rollback before production.

### D3 — Separate deterministic PR proof from real-provider proof

Normal PRs validate manifests, gold-set integrity, deterministic tests, and policy. Real-provider holdout, human faithfulness review, cost/latency, and domain approval run in a protected environment. The latter are required for production AI claims but are not faked when secrets are absent.

The offline validator can verify diff coverage, schema shape, hashes, lineage,
status compatibility and referenced repository reports. It cannot itself prove
that a provider ran, traffic reached a canary, a deployment occurred, a GitHub
review/Environment decision is authentic, a ruleset blocked merge, or production
telemetry was observed; those remain external evidence and enforcement.

### D4 — Build once, promote by digest

The release-candidate workflow admits only a `v*` push event SHA equal to the
current `origin/main` HEAD. Required evidence is bound to trusted workflow/job
identity, push event and exact head SHA, with pagination and duplicate checks.
It builds and publishes once under quarantine, then pulls and product-tests the
exact digest before that digest can be admitted and receive verifiable
SBOM/provenance/attestation references. Staging/production use later immutable
promotion records for the same digest. Manual/ref-selected/historical-main
admission and rebuilding per environment are rejected because both weaken the
reviewed-source-to-runtime identity.

### D5 — Do not invent a cloud deployment

Provider-specific Azure/Vercel/Supabase deployment needs real accounts, OIDC/secrets, domains, and migration decisions. The repository can supply the gated candidate contract and operating runbook now; external enablement remains an explicit task and cannot be marked deployed.

### D6 — GitHub-native supply-chain baseline

Use least-privilege workflow permissions, Dependabot, dependency review, CodeQL,
an SBOM, and artifact provenance/attestation. All remote actions, including the
existing core CI, are pinned by full commit SHA. A repository gate rejects a
mutable action ref, quoted/inline `pull_request_target`, unresolved local action,
or a mutable dependency nested in a local composite. The control is
repo-configured and mutation-tested; it is not `enforced` until a live required
check/ruleset proves that a violation blocks merge.

### D7 — File-based governance first

AI dossiers, ADRs, SLOs, incident records, and scorecards start as versioned files. A database/UI is rejected for this slice because it adds permissions, migrations, and product complexity before the operating model is proven.

## Standards alignment

- NIST AI RMF and its Generative AI Profile support managing AI risk throughout design, use, evaluation, and monitoring.
- NIST SSDF and its Generative AI community profile support integrating secure-development practices into the lifecycle.
- SLSA provenance binds an artifact to its build inputs and process.
- OWASP LLM guidance treats prompt injection, sensitive disclosure, supply-chain, excessive agency, and vector/embedding risks as distinct controls.

These are design inputs, not certification claims.
