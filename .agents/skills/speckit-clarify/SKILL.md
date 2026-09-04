---
name: speckit-clarify
description: "Resolve material ambiguities in the current feature specification and record accepted answers in the specification. Use for Speckit clarification before planning or when unresolved requirements affect behavior, architecture, or acceptance tests."
---

# Speckit Clarify

Clarify decisions that affect implementation or verification while preserving the user's established scope and answers.

## Read the current feature

1. Resolve the Git root and actual branch. Run `bash .specify/scripts/bash/check-prerequisites.sh --json --paths-only` there; verify its `REPO_ROOT` and use `FEATURE_SPEC` and `FEATURE_DIR`.
2. Prefer an explicitly supplied feature directory, then the [.specify/feature.json](../../../.specify/feature.json) pin, over branch-derived paths. If the script fails only because of the branch naming check, inspect [.specify/scripts/bash/common.sh](../../../.specify/scripts/bash/common.sh) and the verified pin/directory. A command-scoped `SPECIFY_FEATURE` using that verified feature basename is available without a Git checkout. Do not change branches or guess the latest feature. Ask for the target only if it is unresolved.
3. Read the full spec, relevant existing clarifications, and [.specify/memory/constitution.md](../../../.specify/memory/constitution.md). If the spec is absent, report that a specification is needed; do not silently create a different feature.

If a confirmed custom feature directory still fails the script's naming rule, use the read-only `get_feature_paths` resolver in [common.sh](../../../.specify/scripts/bash/common.sh) and check required files directly. Report that script limitation; do not change the branch or silently substitute another feature.

## Clarify selectively

Review actors and permissions, functional scope, data identity/lifecycle, user-visible states, accessibility, errors/recovery, integration behavior, concurrency, privacy, performance, constraints, terminology, and measurable acceptance. Rank gaps by how much an answer would change the design, code, or tests.

- Reuse answers already given in the conversation or artifacts. Resolve routine details with reasonable documented assumptions. Do not reopen settled decisions or require confirmation for already authorized work.
- Ask only questions with a material unresolved consequence, one at a time, up to five in the session. Offer a brief recommended answer with its tradeoff when useful; keep open answers short. Use a question tool only if it is available for the current mode; otherwise ask plainly.
- Stop when the user says to stop, the important gaps are resolved, or five questions have been answered. Continue useful independent work when an unanswered question does not block it.

## Record accepted answers

After each accepted answer, update the actual affected requirement, story, data rule, or acceptance condition. Remove conflicting wording rather than appending a contradictory note. Preserve unrelated sections and existing identifiers.

Add or reuse `## Clarifications` and `### Session YYYY-MM-DD` using the current date. Record `- Q: <question> → A: <accepted answer>`. Save the target spec after each accepted answer; do not portray an unconfirmed suggestion as a user decision. Record assumptions distinctly from accepted answers.

Check that each clarification is testable and consistent with the rest of the spec. Report the spec path, decisions resolved, any important deferred questions, and whether planning or implementation still has a blocker. Do not edit application code, weaken the constitution to resolve a conflict, run hooks, commit, push, or publish anything.
