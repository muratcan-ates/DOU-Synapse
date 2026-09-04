---
name: speckit-checklist
description: "Create or update a feature-specific checklist that tests the quality of requirements: completeness, clarity, consistency, measurability, and coverage. Use for Speckit requirement checklists, including UX, security, API, or release requirement reviews; not for executing application tests."
---

# Speckit Checklist

Create a checklist of questions about the requirements, not a list of checks that claim the implementation works.

## Resolve context

1. Find the Git root and record the current branch. From that root, run `bash .specify/scripts/bash/check-prerequisites.sh --json --paths-only`; verify the returned `REPO_ROOT` and use the returned feature paths. Read the spec and any relevant plan or tasks.
2. Respect an explicit `SPECIFY_FEATURE_DIRECTORY` or the [.specify/feature.json](../../../.specify/feature.json) pin before deriving a feature from the branch. Never guess from the latest directory. If the legacy branch check rejects the current branch, inspect [common.sh](../../../.specify/scripts/bash/common.sh) and the verified directory/pin; use a command-scoped `SPECIFY_FEATURE` equal to the verified feature basename if needed. Do not rename or switch branches. Ask only if the feature itself is still ambiguous.
3. Infer the checklist's audience, focus, and depth from the user's request. Ask only material unanswered questions; use stated assumptions for routine choices. Read [.specify/memory/constitution.md](../../../.specify/memory/constitution.md) when its requirements affect the chosen focus.
4. Resolve `checklist-template` through `resolve_template TEMPLATE_NAME REPO_ROOT` in [.specify/scripts/bash/common.sh](../../../.specify/scripts/bash/common.sh), from the repository root, and read the returned file. This preserves template overrides and presets; the repository default is [checklist-template.md](../../../.specify/templates/checklist-template.md).

If a confirmed custom feature directory still fails the script's naming rule, use the read-only `get_feature_paths` resolver in [common.sh](../../../.specify/scripts/bash/common.sh) and check required files directly. Report that script limitation; do not change the branch or silently substitute another feature.

## Write the checklist

- Write `FEATURE_DIR/checklists/<focus>.md`. Reuse a matching checklist when appropriate. Preserve existing item IDs, completion marks, notes, and human decisions; append new IDs after the highest existing `CHK` number instead of resetting the file. Only revise existing text when the user's requested update calls for it.
- Use the form `- [ ] CHK001 Are failure outcomes defined for ...? [Completeness, Spec §FR-003]`.
- Test completeness, clarity, consistency, measurable acceptance, scenario coverage, dependencies, assumptions, and conflicts. Cover normal, alternate, error, recovery, and relevant nonfunctional scenarios without adding unrelated product scope.
- Trace each question to a real section or use `[Gap]`, `[Ambiguity]`, `[Conflict]`, or `[Assumption]`. Never invent section IDs. Prefer a focused set of distinct, useful questions; combine overlaps.
- Ask questions such as “Are expired-session behavior and the student's next action specified?” Avoid implementation assertions such as “Verify that the API returns 403.” Do not pre-check an item merely because related code exists.

Report the checklist path, focus, item count, and unresolved requirement decisions. Do not run application tests, modify source code, execute extension hooks, or create Git/external changes beyond the requested checklist artifact.
