---
name: speckit-git-initialize
description: Initialize Git in the intended unversioned Spec Kit project, or report an existing repository without changing it; create a reviewed initial commit only when requested.
---

# Initialize the intended project

Locate the project directory from the task and its `.specify/` marker if present; do not use the installed skill's directory as the project. Inspect the target's existing files and whether Git is available before changing anything.

Run `git -C <project> rev-parse --show-toplevel` and inspect `.git` as either a file or directory. If the target already belongs to a repository, including a linked worktree or a parent repository, initialization is a **read-only no-op**: report its actual root, branch or detached state, and full HEAD if one exists. An existing repository with an unborn HEAD is still initialized. Do not create a nested repository, reset its history, or create an initial commit merely because HEAD is absent.

For an unversioned project that the user wants initialized:

1. Confirm the exact target directory. Preserve existing files, ignore rules, Git templates, identity, signing and remote configuration. Do not derive an author name or email from the project name.
2. Run `git -C <project> init`; if the user supplied an initial branch, pass the supported `--initial-branch=<name>` after validating it. Otherwise let the user's configured Git default apply instead of rewriting global configuration.
3. Verify that the resulting repository root is exactly the intended directory. Report initialization separately from creation of a commit.

## Initial commit, when in scope

An initial commit requires the user's request or existing session authorization for that commit. Inspect all proposed files, existing ignore rules, configured author identity, and the effective commit hooks. Stage only the reviewed project paths; do not use `git add .` or silently include credentials, caches, build products or unrelated files. Preserve partial and unrelated staging.

Run applicable validation, inspect the staged diff, and commit with a reviewed message. Active validation hooks remain in force; external effects such as a push require their own already-established authorization. Do not disable hooks to force success. If identity is missing, use only identity values already supplied by the user or report the missing input; do not set global name/email, signing or default-branch configuration. Do not create an empty commit unless requested.

On a failure, inspect and report the actual state before any retry: Git initialization may have succeeded even if the commit did not. Never delete `.git` as automatic rollback. No remote creation, push, hook registration or package installation is implied by initialization.

## Existing extension

The repository's [Bash initialization helper](../../../.specify/extensions/git/scripts/bash/initialize-repo.sh) and [PowerShell equivalent](../../../.specify/extensions/git/scripts/powershell/initialize-repo.ps1) couple initialization with whole-tree staging and an initial commit. Use the explicit steps above; do not invoke the helper or copy its `git init` / `git add .` / commit fallback sequence.
