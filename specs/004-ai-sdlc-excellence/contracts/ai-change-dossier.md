# Contract: AI change dossier and gate

## Invocation

```text
python scripts/ai_sdlc_check.py \
  --repo-root . \
  --policy .ai/policy.json \
  --base-sha <base> \
  --head-sha <reviewed-head>
```

Exit `0` means the changed-path dossier contract is valid. A non-zero exit lists uncovered paths, malformed records, stale SHAs, or hash mismatches. It does not score real-model quality.

This is an offline structural decision. It does not prove that a provider ran,
an environment received a deployment, a GitHub ruleset required the check, a
named reviewer acted, a canary received traffic, or production telemetry was
observed. Those claims require the referenced external records and protected
workflow/environment controls.

## Changed-path rules

1. Compute the diff from merge base to reviewed head.
2. Match paths against policy AI-sensitive patterns.
3. If no AI-sensitive path changed, validate policy/schema and exit successfully.
4. Otherwise require changed dossiers under `.ai/changes/`.
5. Every sensitive path must be covered by at least one artifact entry with its current SHA-256; deleted files use the explicit `deleted` artifact state.
6. All covering dossiers must target the reviewed head and agree on the highest risk tier.

## Immutable revision and lineage contract

Each dossier is an append-only snapshot with a stable `lineage_id` and
increasing `revision`. Revision 1 is a root with `supersedes: null` and no
previous status. A later revision MUST point through
`supersedes {path, sha256}` to the exact previous dossier already present in the
reviewed base, preserve the lineage, increment by exactly one, declare the
previous status, and never lower risk. Existing dossiers and evidence reports
in the base may not be rewritten or deleted. Duplicate revisions, two children
of one parent, status skips and lineage forks fail closed.

Allowed transitions (including a same-state append-only revision) are:

```text
draft              -> draft | evidence-ready | rolled-back
evidence-ready     -> evidence-ready | awaiting-approval | rolled-back
awaiting-approval  -> awaiting-approval | canary | rolled-back
canary             -> canary | expanded | rolled-back
expanded           -> expanded | closed | rolled-back
rolled-back        -> rolled-back | closed
closed             -> closed
```

## Machine-bound decision fields

The record binds provider, model, prompt, tool-schema, guardrail, retrieval,
embedding and evaluator revisions; corpus/evaluation-set digests and privacy
classification; baseline and candidate metrics with operator, predeclared
threshold, sample size and exact command; feature flag, candidate, deployment
and environment identities; and named approval actor, immutable review ref,
decision time and candidate SHA. Narrative prose cannot substitute for these
machine fields.

## Evidence contract

- `fake-provider`: deterministic mechanics only.
- `offline-replay`: recorded-input comparison only.
- `real-provider`: current provider/model behavior for recorded settings.
- `staging`: integrated runtime evidence.
- `canary`: limited live cohort evidence.
- `production`: observed live state only.

Evidence is a SHA-256-bound JSON report whose internal candidate and label must
match the dossier. Passing external evidence also requires an immutable GitHub
Actions run URL. The gate rejects a production-ready status if required
real-provider/human evidence references are absent. It does not accept narrative
text as a substitute for a result artifact.

`canary` requires passing real-provider and canary evidence, all risk-required
independent named approvals bound to the exact candidate, and a canary
deployment/flag identity. `rolled-back` requires passing rollback evidence bound
to the candidate, deployment identity, report path and digest, with the flag
disabled.

`closed` has exactly two accepted branches:

- verified production success: real-provider + production evidence, all named
  immutable approvals, production-ready/production decision, exact production
  deployment and enabled flag; or
- verified rollback before production: no promotion claim/target, disabled
  flag, `verified-before-production` rollback state and bound passing rollback
  evidence.

A verified-after-production rollback supports `rolled-back`; it is not the
rollback-before-production shortcut to `closed`.

## Privacy and logs

Failures may print repository paths, identifiers, hashes, and missing field names. They must not print environment secrets, prompt/answer bodies, JWTs, student IDs, or uploaded document content.
