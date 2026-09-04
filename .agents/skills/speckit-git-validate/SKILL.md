---
name: speckit-git-validate
description: Read-only validation of the actual Spec Kit branch name and matching specification directory, including sequential and timestamp prefixes, detached HEAD and ambiguous feature context.
---

# Validate branch and feature context

Resolve the repository from the task's working directory, not from the installed skill directory. This workflow reads Git and `specs/`; it does not switch, rename, create or delete branches, edit configuration, commit, fetch or push.

Read the actual branch with `git symbolic-ref --quiet --short HEAD` and the full HEAD with `git rev-parse --verify HEAD`. Record the repository root and relevant `git worktree list --porcelain` entry. Detached HEAD and an unborn branch are distinct states; report them honestly instead of substituting a feature name from an environment variable.

## Naming and directory checks

- Read local naming instructions. The installed Spec Kit Git helpers support a sequential prefix of at least three digits (`016-topic`, `1000-topic`) or a timestamp prefix (`YYYYMMDD-HHMMSS-topic`). An optional single namespace such as `feat/016-topic` is normalized for the Spec Kit check; retain the full actual Git name in the result.
- Validate Git syntax with `git check-ref-format --branch <name>`. Check timestamp form before sequential form, require a nonempty feature suffix, and reject malformed timestamp-like prefixes rather than interpreting the date as a large sequential number. A project-specific naming exception should be reported under that policy, not silently rewritten.
- Extract the complete prefix: `016` for sequential, `YYYYMMDD-HHMMSS` for timestamp. Inspect the corresponding `specs/<prefix>-*` directories under the resolved repository. Report an exact matching directory, a missing directory, or multiple candidates; do not silently select the newest or alphabetically first candidate. If explicit feature metadata identifies one candidate, verify it against the actual branch and report the relationship.
- Check [feature metadata](../../../.specify/feature.json) or a task-supplied `SPECIFY_FEATURE` if present as additional context. Report disagreement with the actual branch. An override must not turn an unrelated checkout into a passing branch validation.

Without Git or a repository, an explicitly supplied `SPECIFY_FEATURE` can be checked as a **declared feature only** together with local `specs/`. It does not prove a branch exists. If neither source is available, report validation skipped with the concrete reason.

Return the actual branch/state, full SHA when available, detected numbering scheme, matching spec path(s), and any mismatch. Naming validity and spec-directory presence are separate results: one passing does not make the other pass. Leave proposed corrections as findings unless the user's task independently authorizes making them.

## Existing extension

Read the [validation command reference](../../../.specify/extensions/git/commands/speckit.git.validate.md) and installed naming helpers for [Bash](../../../.specify/extensions/git/scripts/bash/git-common.sh) or [PowerShell](../../../.specify/extensions/git/scripts/powershell/git-common.ps1). Read the actual installed helper before reuse. Its Git checks are a naming aid, not a reason to run branch-creation or auto-commit hooks.
