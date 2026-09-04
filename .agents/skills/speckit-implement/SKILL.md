---
name: speckit-implement
description: "Implement the current feature's approved specification and dependency-ordered task plan, preserving worktree ownership and recording verification. Use when the user asks Speckit to implement or continue an existing feature plan, including an explicitly selected task subset."
---

# Speckit Implement

Carry the user's authorized implementation through to verified task completion. Keep the current branch/worktree and unrelated work intact.

## Establish the execution boundary

1. Locate the Git root, actual branch, and worktree status. Run `bash .specify/scripts/bash/check-prerequisites.sh --json --paths-only` from that root and verify `REPO_ROOT`. Use its feature paths; an explicit directory or [.specify/feature.json](../../../.specify/feature.json) pin outranks the branch name.
2. If only the legacy branch check fails, inspect [.specify/scripts/bash/common.sh](../../../.specify/scripts/bash/common.sh) and the verified pin/directory. A command-scoped `SPECIFY_FEATURE` with the verified feature basename can run the scripts without checking out another branch. Never choose a feature merely because its number is greatest. Ask for the target only if unresolved.
3. Run `bash .specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` in that same context. Read the spec, plan, tasks, constitution, applicable repository instructions, and the supporting research/data model/contracts/quickstart that the tasks depend on. Missing prerequisites are gaps to report or complete only when already within the user's authorization.
4. Respect the requested task subset, explicit file ownership, and read-only references. Inspect existing changes before editing. Do not reset, stash, overwrite, or include another contributor's work without authorization.

If a confirmed custom feature directory still fails the script's naming rule, use the read-only `get_feature_paths` resolver in [common.sh](../../../.specify/scripts/bash/common.sh) and check required files directly. Report that script limitation; do not change the branch or silently substitute another feature.

## Execute the plan

- Review feature checklists. Distinguish a binding unresolved acceptance/approval gate from an unchecked advisory item. Complete authorized preparation and independent tasks; do not ask again merely because the user already said to continue. If a genuine decision or named human approval blocks work, explain the exact file/rule and the concrete result awaiting it. Do not manufacture an approval.
- Follow task dependencies. Parallelize only tasks with independent dependencies and non-overlapping files. If delegating, assign bounded ownership and integrate the evidence before marking the parent task complete.
- Inspect actual project structure, dependency locks, and scripts before choosing commands. Add ignore rules only for actual new generated artifacts; preserve tracked examples and existing exclusions. Do not copy generic setup boilerplate into a working repository.
- Implement the smallest complete behavior required by the plan, including relevant error, permission, and recovery paths. Preserve API, database, and UI contracts or update their authorized artifacts together.
- Use existing test fixtures and meaningful regression checks for the changed behavior, plus required repository gates. For DOU-Synapse database tests, use an isolated feature-specific database and the existing admin/app/worker DSN contract; verify all three target the same explicit host, port, and database before any reset. Do not use a shared application database as a test target.
- Mark a task `[x]` only after its implementation and required verification pass. Preserve task IDs and attach concise evidence or a reference to the verification record. A partially implemented or unverified task stays open with its exact remaining blocker.

## Finish the slice

Review the diff against the requested scope. Report completed tasks and behavior, actual verification results, and remaining risks or gates. If a check cannot run, say why and do not equate compilation or fake-provider tests with real-provider quality. Continue the remaining authorized tasks when they are ready.

Do not execute extension hooks, automatically commit or push, create external issues, deploy, or claim release approval as an implementation side effect. Those actions need authorization in the current task scope.
