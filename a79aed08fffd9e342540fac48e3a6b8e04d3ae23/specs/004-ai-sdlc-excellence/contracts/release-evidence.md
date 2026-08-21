# Contract: release candidate and promotion evidence

The machine-readable schema is `.release/evidence.schema.json` version 2. It
distinguishes `record_type: candidate` from `record_type: promotion`.
Candidate admission is intentionally narrower than "a commit exists in
`main`": only a `v*` push event whose immutable event SHA equals the current
`origin/main` HEAD may start the release workflow. Manual, branch-selected,
historical-main, foreign-workflow, duplicate, or newer-spoofed evidence is not
admissible.

## Trusted gate identity

Each required gate is accepted only when all of these bind to the candidate:

- the exact trusted workflow path/identity and expected job name;
- event type `push`;
- exact candidate `head_sha`;
- `completed` with `success`;
- an immutable GitHub Actions run/job URL and identifiers;
- no duplicate/manual/foreign/newer result that can shadow the admitted run.

The workflow-runs and jobs APIs are read to exhaustion. Reported totals must
equal the records received. Missing pages, missing jobs, skipped/cancelled
results, ambiguous duplicates, mutable identity, or mismatched SHA fail closed.
A successful job with the same display name but the wrong workflow identity is
not evidence.

## Quarantine and admission

1. One image is built and published under a quarantine identity.
2. Its exact `name@sha256:digest` is pulled from GHCR.
3. That pulled digest must pass offline embedding, bake-report, and `<4 GiB`
   RSS gates.
4. SBOM, provenance, and attestation must carry verifiable references/digests;
   prose such as `embedded` is not sufficient identity.
5. Only after those checks may the immutable digest be recorded as admitted in
   an immutable evidence artifact. No mutable admitted tag is created.

Failure before admission leaves a quarantined artifact, not a release
candidate. Retention and deletion of quarantine/admitted artifacts are external
registry controls and remain unverified until observed in GHCR.

## Candidate record

The candidate record binds at least:

- repository, exact current-main source SHA and immutable workflow run;
- quarantine reference, admitted immutable digest/reference and admission time;
- exact-digest product-gate evidence;
- verifiable SBOM, provenance, and attestation identities;
- exact trusted workflow/job evidence for every required gate;
- candidate admission plus staging/production `not-configured`; the promotion
  object is forbidden.

A valid candidate record proves an admitted, tested image digest exists. Its
environment values remain `not-configured`; it cannot claim staging or
production deployment, approval, smoke, backup, migration, rollback, SLO, or
real-provider success.

## Promotion record

Staging and production are later, append-only immutable records that reference
the same admitted candidate digest. Each promotion record requires:

- target environment and exact source/candidate digest;
- named approver, immutable actor identity, approval reference, timestamp and
  approved SHA;
- migration decision and compatibility evidence;
- backup/restore status and evidence;
- target-specific smoke result and immutable run reference;
- previous digest plus rollback readiness/exercise evidence;
- for production, a successful staging record for the same digest.

Candidate evidence is never edited to manufacture promotion evidence. Missing,
skipped, `not-run`, `not-configured`, rejected, failed, or stale data remains
non-passing.

## External enablement boundary

The repository configures candidate mechanics only. The following remain open
until read from the live system or exercised safely:

- `main` and release-tag rulesets, required checks and audit-visible bypass;
- protected release-candidate, staging and production Environments;
- independent approvers and immutable approval records;
- GHCR package permissions, quarantine/admitted retention and cleanup;
- cloud OIDC/credentials, deployment targets, smoke/telemetry routes;
- a real candidate run and same-digest staging/production promotion.

The first implementation slice must not be reported as deployed or
production-ready.
