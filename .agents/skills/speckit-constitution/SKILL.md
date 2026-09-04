---
name: speckit-constitution
description: "Create or amend the repository constitution when the user requests changes to project principles or governance. Use for Speckit constitution work, including versioned amendments and checking affected templates; not for weakening rules to make an unrelated feature pass."
---

# Speckit Constitution

Apply the requested governance change to [.specify/memory/constitution.md](../../../.specify/memory/constitution.md) and make its consequences reviewable.

## Establish scope

1. Find the repository with `git rev-parse --show-toplevel`; record the current branch and worktree status. Read applicable repository instructions and the existing constitution.
2. Run `bash .specify/scripts/bash/check-prerequisites.sh --json --paths-only` for feature context when relevant. A global constitution amendment does not require an active feature. Respect [.specify/feature.json](../../../.specify/feature.json) and explicit feature selection; a legacy branch-name failure is not a reason to switch branches or create a feature.
3. Read the requested principles, relevant project documentation, and [.specify/templates/constitution-template.md](../../../.specify/templates/constitution-template.md) if creating a constitution was explicitly requested and none exists. Preserve the user's chosen number and scope of principles. Do not turn a feature request into a governance rewrite.

## Amend coherently

- Replace placeholders with concrete, testable rules and their rationale. Retain relevant existing principles; avoid aspirational wording without an observable obligation. Do not invent approval, authorship, or dates.
- Preserve the original ratification date. Set the last-amended date only when an amendment is made. Mark genuinely unknown required information with a specific TODO and explain it.
- Apply semantic versioning: major for removal or incompatible redefinition of a principle; minor for a new principle or material added guidance; patch for clarifications that do not change obligations. Explain the chosen increment.
- Check [.specify/templates/plan-template.md](../../../.specify/templates/plan-template.md), [spec-template.md](../../../.specify/templates/spec-template.md), and [tasks-template.md](../../../.specify/templates/tasks-template.md), plus the relevant current project guidance. Resolve any active template overrides through `resolve_template TEMPLATE_NAME REPO_ROOT` in [.specify/scripts/bash/common.sh](../../../.specify/scripts/bash/common.sh). Do not assume optional template directories or agent-update scripts exist.
- Make only propagation changes necessary for the authorized amendment and permitted by file ownership. Record dependencies that are outside scope or read-only instead of silently changing them. Never modify source reference material or weaken a requirement merely to remove a failing feature gate.

Add a concise HTML Sync Impact Report at the top of the constitution: old and new version, changed/added/removed principles, dependent files updated or pending, and unresolved TODOs. Preserve substantive prior decisions.

Check for unexplained placeholders, contradictory obligations, version/date consistency, and actual alignment of changed templates. Report the amendment, rationale, affected paths, and any pending decisions. A suggested commit message is optional; do not run commits, pushes, extension hooks, or external publication automatically.
