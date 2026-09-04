---
name: speckit-analyze
description: "Review the current feature for conflicts, missing coverage, and constitution violations across its specification, plan, and tasks. Use when the user asks for Speckit analysis or a read-only consistency review before implementation."
---

# Speckit Analyze

Produce a read-only, evidence-based consistency report. Do not edit artifacts or implement fixes during an analysis-only request.

## Resolve and load

1. Locate the repository with `git rev-parse --show-toplevel`; record the real branch and worktree status. Run `.specify/scripts/bash/check-prerequisites.sh --json --paths-only` with Bash from that root. Use its `FEATURE_DIR`, `FEATURE_SPEC`, `IMPL_PLAN`, and `TASKS`; verify `REPO_ROOT` matches the selected repository.
2. An explicit feature directory or [.specify/feature.json](../../../.specify/feature.json) pin takes precedence over the branch name. Never select the highest numbered directory. If the script rejects a non-feature branch, inspect [.specify/scripts/bash/common.sh](../../../.specify/scripts/bash/common.sh) and the explicit directory/pin. A command-scoped `SPECIFY_FEATURE` set to that verified feature directory's basename can satisfy the legacy branch check without changing Git state. If the intended feature remains ambiguous, ask for the target.
3. Run `bash .specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` with the same resolved context. Read the reported spec, plan, and tasks, plus [.specify/memory/constitution.md](../../../.specify/memory/constitution.md). If a required artifact is absent, report it instead of inventing its contents.

If a confirmed custom feature directory still fails the script's naming rule, use the read-only `get_feature_paths` resolver in [common.sh](../../../.specify/scripts/bash/common.sh) and check required files directly. Report that script limitation; do not change the branch or silently substitute another feature.

## Analyze

- Inventory functional requirements, buildable success criteria, user stories, constraints, and task IDs. Map requirements and stories to tasks using explicit references and their actual actions. Separate outcome KPIs that do not themselves require implementation work from missing implementation coverage.
- Check duplication, ambiguous wording, underspecified actors/data/errors, contradictions, inconsistent terminology or paths, unmet constitution requirements, missing task coverage, and tasks without a justified requirement.
- Check task order and dependencies against the plan. Flag parallel tasks that modify the same files or depend on unfinished work. Distinguish evidence in the artifacts from assumptions.
- Grade severity: **critical** for a binding constitution violation or a missing core requirement that blocks the feature; **high** for conflicting behavior or an untestable important security/acceptance requirement; **medium** for material ambiguity or missing edge-case coverage; **low** for wording and minor duplication.

## Deliver

Give a compact findings table with ID, severity, category, exact file and line, impact, and a concrete recommendation. Include requirement-to-task coverage, unmapped tasks, and actual counts. Do not invent coverage percentages or imply that reading a test task proves the test passed. Prioritize actionable findings; consolidate repetitive findings when there are many.

State whether implementation can proceed and which decisions are still needed. If the user has already authorized fixes as part of broader work, hand these findings to that implementation step without asking for the same authorization again. An analysis-only request ends with the report. Never run extension hooks, commits, pushes, or external issue creation as a side effect.
