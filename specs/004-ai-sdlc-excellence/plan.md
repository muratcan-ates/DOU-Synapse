# Implementation Plan: AI SDLC and Engineering Excellence

**Branch**: `004-ai-sdlc-excellence` | **Date**: 2026-08-11 | **Spec**: [spec.md](spec.md)

## Summary

Add a low-conflict repository-governance slice around the existing product: a deterministic AI change dossier gate, PR ownership and templates, dependency/security automation, candidate build evidence, and honest SLO/ADR/incident/release operating documents. Keep the newly green core CI stable by adding independent workflows, and keep live deployment conditional until protected environments and credentials exist.

## Technical Context

**Language/Version**: Python 3.12 for deterministic validators; GitHub Actions YAML; JSON; Markdown

**Primary Dependencies**: Python standard library, existing `uv`, existing Docker build, GitHub-native Actions

**Storage**: Versioned repository files and GitHub artifacts; no database migration

**Testing**: Python `unittest`, JSON parse/schema-shape checks, workflow YAML parse, action/static policy checks, existing repository gates where applicable

**Target Platform**: GitHub pull requests and protected GitHub Environments; Linux Actions runners

**Project Type**: Repository-wide delivery and AI-governance infrastructure

**Performance Goals**: Deterministic AI dossier gate under 10 seconds; security jobs parallel to core CI; candidate publication outside the fast PR path

**Constraints**: No production credentials; no external deployment claim; no student content in governance artifacts; do not weaken the five green core CI checks

**Scale/Scope**: One repository, Python API, Next.js web app, one container image used by API and worker, versioned evaluation corpus

## Constitution Check

- **I. Tek doğruluk kaynağı**: Policy and dossier schema are machine-readable; Markdown explains rather than duplicates live result counts.
- **II. Sınırları belirli AI**: AI artifacts, corpus, and provider evidence are versioned; production claims require real-provider evidence.
- **III. Ölçülmemiş sayı yok**: Workflows retain evidence labels and never translate skipped/unconfigured into success.
- **IV. RLS ve rol güvenliği**: First slice adds no database or authorization surface.
- **V. İzole test**: Validator tests need no shared database, network, or secrets.
- **VIII. Kırmızı yanabilen kapılar**: Negative tests prove missing dossier, stale hash, unsafe promotion, and malformed policy fail.
- **XI. Tek sahiplik**: New files are isolated; existing `ci.yml` remains owned by the active release integrator.

Post-design re-check: no constitution exception is required. External branch protection and environment configuration remain observable follow-up tasks, not claimed implementation.

## Project Structure

```text
.ai/
├── README.md
├── policy.json
├── schema.json
└── changes/example.json
.github/
├── CODEOWNERS
├── dependabot.yml
├── pull_request_template.md
└── workflows/
    ├── ai-quality.yml
    ├── security.yml
    └── release-candidate.yml
.release/
├── README.md
├── evidence.schema.json
├── validate_evidence.py
├── verify_checks.py
├── test_validate_evidence.py
└── test_verify_checks.py
docs/
├── adr/README.md
└── engineering/
    ├── AI_SDLC.md
    ├── ENGINEERING_EXCELLENCE.md
    ├── INCIDENT_RESPONSE.md
    ├── RELEASE_PROCESS.md
    └── SLO.md
scripts/
├── ai_sdlc_check.py
├── test_ai_sdlc_check.py
├── workflow_policy_check.py
└── test_workflow_policy_check.py
specs/004-ai-sdlc-excellence/
├── evidence/2026-08-11-local-verification.md
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── tasks.md
└── contracts/ai-change-dossier.md
```

**Structure Decision**: Repository-root controls keep the gate visible and reusable without coupling it to API or web runtime packages. The first slice is intentionally file-based and migration-free.

The existing core CI keeps the same five product gates while becoming
fail-closed for type checking, frozen dependency resolution, least-privilege
permissions, bounded runtime, and immutable third-party action identities.

## Delivery Slices

1. **AI change gate**: append-only lineage/revision schema, artifact/evaluation/
   approval/deployment identities, state-specific promotion and rollback policy,
   validator, mutation-style unit cases, PR workflow.
2. **PR and supply-chain baseline**: ownership, PR evidence template, dependency updates, CodeQL/dependency review.
3. **Candidate delivery**: admit only a `v*` push event SHA equal to current
   `origin/main` HEAD and exact trusted workflow/job identities; publish once
   to quarantine; pull and product-test the exact digest before admission; then
   generate verifiable SBOM/provenance/attestation references and schema-valid
   candidate evidence. Deployment remains explicitly unconfigured.
4. **Operating system**: ADR, SLO, incident, release, and scorecard documents.
5. **External enablement**: configure required checks, environments, OIDC/secrets, and provider-specific deployment in a live GitHub/cloud session.

## Complexity Tracking

No new application framework, service, database table, or runtime dependency is introduced. Multiple workflow files are preferred over expanding the active `ci.yml` because they have distinct permissions, cadence, and failure ownership.
