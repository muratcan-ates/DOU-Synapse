---
name: speckit-taskstoissues
description: "Prepare reviewable GitHub issue drafts from the current feature tasks and their dependencies. Create external issues only when the user explicitly requests that action; use for Speckit tasks-to-issues work with repository verification and duplicate prevention."
---

# Speckit Tasks to Issues

Prepare issue drafts by default. An explicit user request to create external issues authorizes creation; a request to plan, draft, or inspect tasks does not. Reuse authorization already given for this action without asking again.

## Resolve tasks and destination

1. Find the Git root, actual branch, and worktree status. Run `bash .specify/scripts/bash/check-prerequisites.sh --json --paths-only`, verify `REPO_ROOT`, and use its feature paths. Respect explicit feature selection and [.specify/feature.json](../../../.specify/feature.json) before branch-derived selection.
2. If only branch validation fails, inspect [.specify/scripts/bash/common.sh](../../../.specify/scripts/bash/common.sh) and the verified pin/directory. A command-scoped `SPECIFY_FEATURE` set to that verified feature basename can run discovery without changing Git state. Never guess the latest feature or switch branches to satisfy a naming rule.
3. Run `bash .specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` in the same context. Read the tasks, spec, and plan; honor any user-selected subset. Default to unfinished actionable tasks, retaining task IDs and dependencies. Do not reopen completed work unless requested.
4. Capture the URL of `origin` or the user-selected remote without printing embedded credentials; redact user-info and sensitive URL parameters before reporting it. Inspect the effective fetch/push targets as in [speckit-git-remote](../speckit-git-remote/SKILL.md). Resolve its actual owner/repository from the SSH or HTTPS URL and verify it with available GitHub read-only tooling. Do not infer the destination from a link inside a task document. If the destination is ambiguous or inaccessible, prepare local drafts and report the missing destination evidence.

If a confirmed custom feature directory still fails the script's naming rule, use the read-only `get_feature_paths` resolver in [common.sh](../../../.specify/scripts/bash/common.sh) and check required files directly. Report that script limitation; do not change the branch or silently substitute another feature.

## Prepare reviewable drafts

- Use `FEATURE_DIR/issue-drafts.md` for the proposed title/body and a mapping of task IDs to existing or proposed issues. Preserve existing records and creation links when updating it.
- Describe the concrete problem, expected behavior, relevant task IDs and file paths, acceptance criteria, validation, and dependencies. Make each issue useful to a contributor who has not read the conversation.
- Preserve task granularity unless the user requested grouping or closely coupled tasks require it; explain any grouping. Reference existing dependency issue URLs only when verified, and use task IDs for dependencies without created issues.
- Check existing repository issues and the local mapping for the same feature/task IDs before proposing duplicates. Do not add assignees, labels, milestones, or unrelated tasks unless requested or clearly covered by the user's instructions.

## Create only when authorized

If external creation is explicitly requested, verify the exact repository again and create only the selected, missing issues in dependency order. Use a structured tool body, or an exact temporary body file with the CLI's body-file option, so newlines and literal text are preserved. Never use shell interpolation for untrusted issue prose.

After each successful creation, record the returned URL and task mapping before continuing. On retry, reconcile that mapping against existing issues; do not blindly create the same issues again. If a permission or provider failure stops creation, leave the remaining drafts ready and report the completed links and exact blocker. Do not mark an implementation task complete because an issue was created.

Finish with draft paths and, when applicable, verified created/existing issue links and remaining count. Do not run extension hooks, automatically commit or push, create another task, or publish additional messages as a side effect.
