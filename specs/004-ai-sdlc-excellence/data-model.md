# Data Model: AI SDLC and Engineering Excellence

This feature adds no runtime database tables. Records are immutable or append-only repository artifacts and GitHub workflow artifacts.

## AIChangeDossier

| Field | Type | Rule |
|---|---|---|
| `schema_version` | integer | Exact supported wire version; never infer a new number from prose revisions |
| `change_id` | string | Stable, filename-matching ID |
| `lineage_id`, `revision` | string, integer | Stable lineage and exact append-only revision sequence |
| `supersedes`, `previous_status` | object/null, enum/null | Later revisions bind the previous base-record path and SHA-256; roots use null |
| `governance_record_risk` | enum | Dossier audit record itself remains R3 |
| `risk_tier` | enum | `R1`, `R2`, `R3`; highest match wins |
| `status` | enum | Exact transition table below; same-state append-only revision is allowed |
| `owner` | string | Named accountable owner; no secret/email required |
| `base_sha`, `candidate_sha` | Git SHA | Candidate is bound to reviewed head |
| `summary` | string | Intended behavior change, not implementation prose |
| `behavior` | object | Immutable provider/model/prompt/tool/guardrail/retrieval/embedding/evaluator revisions |
| `data` | object | Corpus and evaluation-set SHA-256 digests plus privacy class |
| `artifacts` | array | Repo path, state and SHA-256; deletions are explicit |
| `evidence` | array | Environment label, result, hash-bound JSON report and exact candidate identity |
| `evaluation` | object | Calibration/holdout/anchor refs; baseline/candidate metrics, operator, threshold, sample size and exact command |
| `approval_requirements` | array | Role, named actor, decision, immutable ref/time/candidate and author independence |
| `deployment` | object | Feature flag/state, candidate, deployment identity and environment |
| `rollout` | object | flag, kill switch, initial exposure, stop/expand rules |
| `rollback` | object | previous compatible artifact, command/runbook, time objective, verification |
| `privacy` | object | identifiable-content flag and handling statement |
| `created_at`, `review_by` | date-time | Review date is mandatory for temporary changes/exceptions |

## AIQualityPolicy

Defines AI-sensitive path patterns, risk escalation rules, allowed evidence labels, required fields by tier, immutable evidence language, and production claim rules. Threshold values are versioned here only when a machine reader enforces them.

## ReleaseEvidence

| Field | Meaning |
|---|---|
| source SHA | Reviewed source identity |
| image reference and digest | Build-once candidate identity |
| quarantine reference | Pre-admission registry identity; never a candidate claim |
| admitted digest/reference | Exact pulled and product-gated candidate identity |
| SBOM reference and digest | Verifiable component identity associated with admitted digest |
| provenance/attestation reference and digest | Verifiable builder and inputs identity |
| exact-digest verification | Workflow run in which the published digest passed offline embedding, bake report, and RSS gates |
| required checks | Exact ordered check names, passing state, and run URLs |
| trusted gate identities | Exact workflow path, push event, head SHA, run/job IDs and immutable URLs |
| candidate state | Quarantined or admitted; no staging/production claim |

Migration, named immutable approval, backup, promotion smoke, and rollback
evidence are later append-only staging/production records bound to the same
admitted digest. Candidate evidence is not edited to add them. Schema support
is not evidence that those operations ran.

## EngineeringControl

State is one of `documented`, `configured`, `enforced`, `observed`. Each
control also stores accountable owner, independent reviewer, trigger, exact
evidence and observation time, failure policy, bypass/audit path, current risk,
target state, next action, due date, exception rationale and expiry. An absent
exception is recorded explicitly as none; an unobserved external control uses
`unavailable`, never an implied success.

## Lifecycle invariants

- Missing or skipped evidence never becomes passing evidence.
- Candidate admission comes only from a `v*` push event SHA equal to current
  `origin/main` HEAD; manual/ref-selected/historical-main identity is unavailable.
- Required gates are accepted only from exact trusted workflow/job identities,
  push event and head SHA; pagination, duplicates, missing or foreign runs fail
  closed.
- Publication starts in quarantine. Candidate evidence is created only after
  the exact pulled digest passes offline embedding, bake-report, and RSS gates,
  has verifiable supply-chain identities, and the JSON passes the schema validator.
- A dossier cannot reduce risk without a new reviewed revision.
- A dossier root has revision 1 and no parent. Later revisions supersede exactly
  one base-existing dossier by path and SHA-256, keep lineage, increment exactly
  once and may not fork or rewrite history.
- Allowed status transitions are `draft` to draft/evidence-ready/rolled-back;
  evidence-ready to evidence-ready/awaiting-approval/rolled-back;
  awaiting-approval to awaiting-approval/canary/rolled-back; canary to
  canary/expanded/rolled-back; expanded to expanded/closed/rolled-back;
  rolled-back to rolled-back/closed; and closed to closed.
- Canary requires real-provider and canary evidence plus exact-candidate named
  approvals. Rolled-back requires bound rollback evidence and a disabled flag.
- Closed requires either verified production success or a bound
  rollback-before-production with no promotion and a disabled flag; a
  verified-after-production rollback does not take the latter shortcut.
- Production approval cannot be represented by committed self-attestation.
- A release environment must consume the candidate digest, not a rebuilt tag.
- Superseded ADRs and closed incidents retain history.
- Personally identifiable student content is excluded unless a separately approved de-identification and retention process exists.
