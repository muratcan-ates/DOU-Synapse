---
name: speckit-tasks
description: "Generate or update an actionable dependency-ordered tasks.md from the current feature specification and implementation plan. Use for Speckit task breakdown, preserving completed work and making each user story independently verifiable."
---

# Speckit Tasks

Turn the current plan into concrete work with stable task IDs, real paths, dependencies, and verifiable completion conditions.

## Load the correct feature

1. Locate the Git root and actual branch. Run `bash .specify/scripts/bash/check-prerequisites.sh --json --paths-only` there; verify `REPO_ROOT` and use the returned paths. Explicit feature selection and [.specify/feature.json](../../../.specify/feature.json) take precedence over the branch name.
2. If the script rejects only the branch format, inspect [.specify/scripts/bash/common.sh](../../../.specify/scripts/bash/common.sh) and the verified directory/pin. Use a command-scoped `SPECIFY_FEATURE` with the verified feature basename if needed; do not switch or rename the branch or select the highest feature number. Ask for the target only if unresolved.
3. Run `bash .specify/scripts/bash/setup-tasks.sh --json` in that same context. This script reports paths and the resolved `TASKS_TEMPLATE` without writing tasks. The repository default is [tasks-template.md](../../../.specify/templates/tasks-template.md). Read the resolved template, the feature spec and plan, existing tasks, and [.specify/memory/constitution.md](../../../.specify/memory/constitution.md). Also read relevant available research, data-model, contracts, and quickstart artifacts.
4. If spec or plan is missing, report the missing prerequisite. Complete it only as a separate workflow when the user's existing scope authorizes it; do not fabricate task details from a title.

If a confirmed custom feature directory still fails the script's naming rule, use the read-only `get_feature_paths` resolver in [common.sh](../../../.specify/scripts/bash/common.sh) and check required files directly. Report that script limitation; do not change the branch or silently substitute another feature.

## Build the task graph

- Organize setup and shared foundations first, then prioritized user stories, then necessary integration and verification. Each story should deliver useful behavior that can be tested independently where feasible.
- Use `- [ ] T001 [P] [US1] Concrete action in path/to/file`. Task IDs are mandatory; `[P]` and `[US1]` are included only when applicable. Setup/foundation tasks need not have a story marker.
- Map tasks to actual requirements, contracts, and plan decisions. Include precise paths and a clear completion result; split work that cannot reasonably be completed and verified as one task.
- Mark `[P]` only for work whose dependencies are satisfied and whose files do not overlap with the simultaneous task. State dependencies and the proposed parallel groups explicitly.
- Include meaningful regression and acceptance checks required by the user, spec, constitution, and existing repository gates. Do not create implementation-mirroring tests or require universal test-first development unless the plan calls for it. Keep real-provider and named human acceptance distinct from deterministic checks.
- When updating an existing tasks file, preserve completed tasks, stable IDs, status, and evidence. Add new IDs after existing ones and explain superseded scope; never reset all tasks to unchecked or renumber away traceability.
- Remove unused example tasks and placeholder paths from the template. Check that each required story and buildable acceptance requirement is covered and that no new task introduces unauthorized scope.

Write the resolved `TASKS` path. Report task counts, story coverage, dependencies, independent work opportunities, and unresolved planning decisions. Generating tasks does not implement code, change branches, execute hooks, commit, push, or create external issues.
