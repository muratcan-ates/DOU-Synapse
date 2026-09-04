---
name: speckit-specify
description: "Create or revise a feature specification from the user's request, with prioritized user stories and measurable acceptance criteria. Use for Speckit feature specification work while preserving the current Git branch and keeping new feature creation distinct from implementation."
---

# Speckit Specify

Use the actual user request and established conversation scope as the feature brief. Do not ask the user to repeat a description already provided.

## Select the target without changing Git state

1. Find the repository with `git rev-parse --show-toplevel`; record the actual branch and worktree status. Run `bash .specify/scripts/bash/check-prerequisites.sh --json --paths-only` from that root and verify any returned `REPO_ROOT`.
2. Distinguish revising the current feature from an explicit request for a new feature. For revisions, use the resolved `FEATURE_SPEC`: an explicit feature directory or [.specify/feature.json](../../../.specify/feature.json) pin takes precedence over branch-derived paths. If a legacy branch check rejects the branch, inspect [.specify/scripts/bash/common.sh](../../../.specify/scripts/bash/common.sh) and the verified directory/pin; a command-scoped `SPECIFY_FEATURE` set to that verified basename permits discovery without a checkout. Do not guess the latest directory.
3. For a new feature, honor a user-specified directory/number/name; otherwise read [.specify/init-options.json](../../../.specify/init-options.json) when present and inspect existing feature directories and local branches. The existing `bash .specify/scripts/bash/create-new-feature.sh --json --dry-run` can propose a path with `--short-name`, `--number`, or `--timestamp`. Without an explicit number it may query remote heads even in dry-run; report offline numbering uncertainty rather than claiming remote uniqueness.
4. Do not run the mutating feature-creation script merely to write a spec: it can fetch and check out a branch. Preserve the user's branch/worktree. Create the confirmed feature directory and spec directly from the resolved template. For an authorized new feature, update [.specify/feature.json](../../../.specify/feature.json) to pin that directory while preserving unrelated metadata. Never overwrite an existing feature or change a pin to a different feature during a revision. If target selection is genuinely ambiguous, ask only for that decision.
5. Resolve `spec-template` using `resolve_template TEMPLATE_NAME REPO_ROOT` in [.specify/scripts/bash/common.sh](../../../.specify/scripts/bash/common.sh). The repository default is [spec-template.md](../../../.specify/templates/spec-template.md). Read the returned template and [.specify/memory/constitution.md](../../../.specify/memory/constitution.md); keep read-only reference material untouched.

If a confirmed custom feature directory still fails the script's naming rule, use the read-only `get_feature_paths` resolver in [common.sh](../../../.specify/scripts/bash/common.sh) and check required files directly. Report that script limitation; do not change the branch or silently substitute another feature.

## Write the specification

- Capture actors, the problem, boundaries, explicit constraints, and the intended outcome. Keep the specification technology-neutral except for constraints the user actually imposed.
- Write prioritized user stories with independent value and concrete Given/When/Then acceptance scenarios. Describe normal, failure, permission, empty-state, and recovery behavior where relevant.
- Give functional requirements stable `FR-` identifiers and success criteria stable `SC-` identifiers. Make success observable and measurable; separate a buildable acceptance criterion from a later product outcome metric.
- Describe key entities and ownership where they affect behavior. Include scope exclusions only when they resolve a real ambiguity; do not expand into adjacent features.
- Resolve routine choices with documented assumptions. Use at most three clearly identified clarification markers for high-impact unresolved scope, security, or acceptance decisions. Ask only when a material answer is required; do not treat every template field as a reason to stop.
- Replace template examples and placeholders with this feature's content. During revision preserve identifiers, accepted clarifications, unrelated requirements, and manually maintained evidence.

Create or update `FEATURE_DIR/checklists/requirements.md` with a focused review of clarity, completeness, consistency, and testability. Preserve existing IDs, completion marks, and notes. Fix specification defects within scope; leave unresolved user decisions visible rather than marking the checklist passed.

Report the spec path, scope, acceptance coverage, assumptions, and remaining decisions. Do not automatically generate implementation, execute extension hooks, create Git branches, commit, push, or create external issues. Continue an already authorized broader workflow as its next separate step without requesting duplicate approval.
