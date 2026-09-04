---
name: speckit-plan
description: "Create or update the current feature implementation plan and relevant research, data-model, contract, and quickstart artifacts. Use for Speckit technical planning from an existing specification, preserving existing plans and the current worktree."
---

# Speckit Plan

Translate the current specification into a concrete design and verification plan without silently implementing the feature.

## Resolve safely

1. Find the Git root and real branch; inspect worktree changes. From the root run `bash .specify/scripts/bash/check-prerequisites.sh --json --paths-only`, verify `REPO_ROOT`, and use `FEATURE_SPEC`, `IMPL_PLAN`, and `FEATURE_DIR`.
2. Honor an explicit feature directory or [.specify/feature.json](../../../.specify/feature.json) pin before branch-derived selection. If only branch validation fails, inspect [.specify/scripts/bash/common.sh](../../../.specify/scripts/bash/common.sh) and the verified directory/pin, then use a command-scoped `SPECIFY_FEATURE` equal to the verified feature basename when needed. Do not rename or switch branches. Ask for the target only when still ambiguous.
3. Read the spec, [.specify/memory/constitution.md](../../../.specify/memory/constitution.md), existing feature artifacts, and relevant repository architecture/dependency configuration. Retain explicit user constraints and prior accepted decisions.
4. Resolve `plan-template` with `resolve_template TEMPLATE_NAME REPO_ROOT` from [common.sh](../../../.specify/scripts/bash/common.sh); read the returned template. The repository default is [plan-template.md](../../../.specify/templates/plan-template.md). `bash .specify/scripts/bash/setup-plan.sh --json` copies the template over `plan.md` unconditionally: run it only when the target plan does not exist and a new plan is authorized. Otherwise update the existing plan deliberately using the template as a reference. If using the setup script, extract its JSON object after any informational output rather than assuming all stdout is JSON.

If a confirmed custom feature directory still fails the script's naming rule, use the read-only `get_feature_paths` resolver in [common.sh](../../../.specify/scripts/bash/common.sh) and check required files directly. Report that script limitation; do not change the branch or silently substitute another feature.

## Design the feature

- Fill the technical context from the actual repository: runtime, dependencies, storage, interfaces, testing, deployment constraints, and concrete file structure. Identify unknowns rather than inventing compatible versions or existing components.
- Evaluate the constitution before design and again after it. Resolve a conflict by changing the design within scope; do not amend the constitution to make the gate pass.
- Use `research.md` for decisions that need investigation: question, evidence, selected approach, alternatives, and tradeoffs. Verify unstable external technical claims against primary sources when needed. Do not add research for already settled routine details.
- Create or update `data-model.md` when entities, state transitions, ownership, or persistence change. Describe validation and authorization boundaries where they matter.
- Define relevant contracts under `contracts/` for changed API, event, CLI, or UI boundaries. Match the existing project conventions; do not generate unused interface types solely to fill a template.
- Write a reproducible `quickstart.md` for the planned verification and user flow. Separate offline/fake checks from real-provider or human acceptance gates. Specify prerequisites and expected results without claiming that planned commands have run.
- Keep the plan aligned with the spec and actual paths; preserve useful existing details. Record remaining decisions with their concrete implementation consequences.

Report the plan and supporting artifact paths, important decisions, unresolved blockers, and readiness for task breakdown. This workflow does not generate `tasks.md`, edit application code, update unrelated agent context, or execute hooks/commits/pushes. If broader implementation is already authorized, continue into its distinct next step without a redundant permission question.
