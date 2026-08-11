# DOU-Synapse AI change governance

This directory makes AI-behaviour changes reviewable as a chain of evidence, not
as an unqualified “tests passed” statement. The normal pull-request gate is
deterministic and uses no provider secret.

## What is governed

`.ai/policy.json` classifies prompts, models, retrieval, embeddings, guardrails,
grading, exam behaviour and evaluators as R1, R2 or R3. A pull request that
changes a classified path must include a dossier under `.ai/changes/`.

Each dossier records:

- the reviewed base and candidate commit;
- immutable provider, model, prompt, tool-schema, guardrail, retrieval,
  embedding and evaluator revisions;
- corpus and evaluation-set digests with a privacy classification;
- every changed AI artifact and its SHA-256 digest (or an explicit deletion);
- evidence with an honest environment label, a SHA-256-bound JSON report and
  the exact candidate identity recorded inside that report;
- calibration, holdout and human-anchor references, baseline/candidate metrics,
  predeclared thresholds, sample size and the exact evaluation command;
- named, independent approval actors with immutable review reference, decision
  time and exact candidate identity;
- flag state, candidate identity, deployment identity and environment;
- rollout limits, a kill switch, stop/expand conditions and active-exam policy;
- a previous compatible artifact and bounded rollback procedure; and
- privacy handling without student content in logs or committed evidence.

`candidate_sha: "SELF"` is not a floating alias. In CI the repository is checked
out at `github.event.pull_request.head.sha`, and the validator resolves `SELF`
only to that exact reviewed commit. A dossier is eligible only when its
`base_sha` equals the computed merge base, so an old dossier cannot silently
authorize a later pull request.

The same gate runs after a `main` push against the exact
`github.event.before -> github.sha` range. There is deliberately no manual
workflow trigger that could overwrite the required check context. Mutable branch
or tag names are rejected by the validator. Third-party
actions are pinned to verified 40-character commits, and checkout credentials
are not persisted while pull-request code executes.

The governance policy, schema, checker, tests and workflow are hard-coded R3
bootstrap paths. A policy edit cannot lower their tier or relax the minimum
approval, privacy, rollout or production-evidence rules. A sensitive rename to
an unclassified path is rejected; a low-similarity delete/add move into runtime
code is also rejected until the destination is explicitly classified.

Change dossiers and evidence reports are append-only audit records. A correction
is a new dossier/report; an existing record is never rewritten or deleted. New
evidence must be referenced by a dossier added in the same reviewed diff and its
digest must match. This preserves the evidence that an earlier decision actually
used instead of merely preserving its filename.

Every dossier revision has a stable `lineage_id`, an increasing `revision`, and
either a root marker or a `supersedes` reference containing the exact previous
record path and SHA-256. The previous revision must already exist in the reviewed
base. One parent may have only one child; lineage changes, sequence gaps, status
skips, risk downgrades, forks and history rewrites fail closed. The audit record
itself is always governance R3 even when the represented behaviour is R1/R2.

All database migrations remain R3. This intentionally accepts some conservative
false positives instead of lowering the approval/evidence floor for a migration
whose AI, assessment, privacy or authorization impact may be discovered only
during review. Known chat, assessment, embedding, exam, course-policy, ingestion
and feedback migrations are also pinned by exact-path regression tests.

The published JSON schema is enforced by a fixed digest and matching hard-coded
object-shape invariants in the stdlib validator. Reducing it to a permissive shell
therefore fails before a dossier can authorize the candidate.

## Evidence labels are not interchangeable

- `fake-provider`: deterministic mechanics only.
- `offline-replay`: replayed inputs without a live provider.
- `real-provider`: live provider evaluation.
- `staging`, `canary`, `production`: observations in the named environment.
- `rollback`: hash-bound verification that a named deployment returned to the
  recorded compatible state.

The validator never upgrades one label into another. A `production-ready` claim
needs passing real-provider evidence, passing staging/canary/production evidence
and immutable GitHub pull-request review URLs from named human approvals. Passing
external evidence must also carry a GitHub Actions run URL in its hash-bound JSON
report. The ordinary PR workflow does not make that claim; live-provider and
production promotion remain protected, explicit acts.

## Run locally

Use the exact base and candidate commits that a reviewer will inspect:

```bash
python3 scripts/ai_sdlc_check.py \
  --repo-root . \
  --policy .ai/policy.json \
  --base-sha <base-commit> \
  --head-sha <candidate-commit>

python3 -m unittest scripts/test_ai_sdlc_check.py
```

The checker prints only stable error codes, dossier IDs and repository paths. It
does not echo summaries, evidence payloads, prompts, secrets or student content.

## Promotion and rollback

CI acceptance means only that the reviewed diff is covered by a structurally
valid, commit-bound dossier. It is not production approval. Risk owners must
record their decision in the review system named by the dossier. If a stop
condition fires, use the versioned kill switch first, execute the recorded
rollback procedure, preserve audit evidence and mark the dossier `rolled-back`.
`canary` requires candidate-bound approved review records. `rolled-back` requires
passing hash-bound rollback evidence tied to the deployment identity. `closed`
has exactly two valid outcomes: verified production success, or a verified
rollback-before-production path with the flag disabled. Status, target and
promotion claims that disagree are rejected.
