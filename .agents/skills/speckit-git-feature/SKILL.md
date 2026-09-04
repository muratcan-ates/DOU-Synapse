---
name: speckit-git-feature
description: Create or locate a Spec Kit feature branch and an appropriate isolated worktree from a verified starting commit, using the requested name or repository numbering convention.
---

# Resolve and create a feature branch

Resolve the repository from the task, not from the installed skill's path. Read its local instructions and record the current branch, full HEAD, status, and `git worktree list --porcelain`. If continuing a feature already assigned to this task, reuse that feature and checkout; do not allocate another number merely because this skill was selected.

## Choose the exact target

1. Preserve an explicitly requested branch name, including a `GIT_BRANCH_NAME` value supplied for this task. Treat an unexplained ambient value as context to reconcile, not permission to switch branches. Validate the selected name with `git check-ref-format --branch`.
2. Otherwise read `branch_numbering` from the [Git extension configuration](../../../.specify/extensions/git/git-config.yml), then [initialization options](../../../.specify/init-options.json); absent configuration means sequential numbering. Use a concise feature slug. For sequential numbering, inspect all local and remote-tracking branches plus `specs/` directories and choose the next unused number. Recognize an optional one-segment namespace such as `feat/016-name`; exclude timestamp names from the numeric maximum. For timestamp mode use `YYYYMMDD-HHMMSS-slug` and still check for collisions.
3. When remote freshness matters and network access is available, inspect the relevant remote heads with `git ls-remote --heads <remote>`. A failed lookup is unknown freshness, not an empty remote. Do not fetch/prune every remote as a side effect of choosing a number. In an offline task report the local-only collision check honestly.
4. Resolve the requested starting state to an exact commit with `git rev-parse --verify '<ref>^{commit}'`. Honor an explicit branch/ref/working-tree request. Otherwise use the repository's documented base; if none exists, choose the current verified HEAD and disclose it before creating. If the user expects uncommitted changes, identify which task-owned changes must be carried to the new checkout rather than silently dropping or committing them.

## Create without disturbing other work

Recheck the selected branch and spec prefix immediately before creation. A name collision is not permission to reset or overwrite a branch. If it already exists, inspect its SHA and assigned worktree and continue there only when it is the requested feature; report a genuine ambiguity.

For a new feature in a shared or occupied checkout, prefer `git worktree add -b <branch> <new-path> <verified-base-sha>` at an unused path allowed by the repository instructions. In an already isolated task checkout, a branch change is appropriate only when the current work and requested starting state are preserved. Never force another worktree off its branch, stash unrelated changes, reset, or delete a checkout to make creation succeed.

Creating a branch does not authorize an initial commit, push, Git identity changes or hook installation. This skill creates Git state only; the specification workflow creates `specs/` content. Verify the resulting branch, full HEAD, working-tree path and prefix. Label a name computed without Git as a proposal, never as a created branch.

## Existing extension

Do not blindly run the [Bash feature helper](../../../.specify/extensions/git/scripts/bash/create-new-feature.sh) or [PowerShell equivalent](../../../.specify/extensions/git/scripts/powershell/create-new-feature.ps1): the normal path fetches/prunes and changes the caller's branch. Its dry-run may still contact remotes. The Bash version supports `--dry-run`, `--short-name`, `--number`, `--timestamp`, and `--allow-existing-branch`; it has no `--create` flag. Inspect the installed version before using a helper. Prefer the explicit Git operations above so the base and target checkout stay visible.
