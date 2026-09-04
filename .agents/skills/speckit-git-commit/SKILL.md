---
name: speckit-git-commit
description: Commit inspected, task-owned Spec Kit changes when a commit is requested or already authorized; preserve unrelated work, existing Git configuration, and commit hooks.
---

# Commit the reviewed task

Resolve the intended repository from the current task and `git rev-parse --show-toplevel`; an installed skill's directory is not the target repository. Read applicable repository instructions. Confirm the current branch, full HEAD, `git worktree list --porcelain`, and `git status --short` before changing the index.

## Establish the commit scope

- Use the user's current request and existing session authorization. A Spec Kit event or `auto_commit` setting alone is not authorization to commit everything. If the task requests only review, produce a proposed file list and message without staging.
- Inspect both unstaged and staged diffs, including new files. Identify the exact task-owned paths and, where ownership is mixed, the exact hunks. Preserve unrelated staged and unstaged work. Never stage the whole repository with `git add .`, `git add -A`, or commit with `-a`.
- Run the validation required for those changes. Inspect the final diff for unintended generated files and credentials. Record failures accurately; do not bypass required gates.
- Preserve configured author identity, signing, remotes and hooks. If required identity is missing, use values already supplied by the user; otherwise report the missing input. Do not invent an author or change global Git configuration.

## Make one scoped commit

Review the effective hook location (`core.hooksPath` or `git rev-parse --git-path hooks`) and active commit-hook commands before execution. Existing validation hooks remain in force. If a hook would push, deploy, or make another external change, that action must already be within the user's authorization; otherwise stop before the commit and explain the concrete hook. Do not bypass hooks or install Spec Kit auto-commit hooks.

Stage only reviewed task changes with explicit paths or selected hunks. Check the staged patch again immediately before committing. When unrelated files are already staged, an explicit `git commit --only -- <owned-paths>` can isolate the commit **only when every selected file's full working-tree content is task-owned and reviewed**; it ignores partial staging for those files. For mixed files, use an isolated index or task checkout containing only the inspected patch, preserving the user's index. Do not include unreviewed hunks to simplify the operation.

Write the exact commit message to a temporary file and use `git commit -F <message-file>` with the chosen scoped strategy. An empty task diff is a no-op. Do not amend, create an empty commit, push or change branches unless the task separately calls for it. If a hook changes files or a commit fails, inspect the resulting state before retrying; do not repeat staging blindly.

Verify the new full SHA, committed paths and remaining working-tree/index changes. Report what was committed, the validation result, and anything deliberately left outside the task.

## Existing extension

The repository's [Bash auto-commit helper](../../../.specify/extensions/git/scripts/bash/auto-commit.sh) and [PowerShell equivalent](../../../.specify/extensions/git/scripts/powershell/auto-commit.ps1) stage the whole tree when enabled. Read its configuration as context; use the scoped procedure above instead of invoking that helper. This skill does not register or run before/after command hooks.
