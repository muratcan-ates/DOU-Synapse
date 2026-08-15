# Quickstart: AI SDLC and Engineering Excellence

## Local deterministic gate

```bash
python3 scripts/ai_sdlc_check.py \
  --repo-root . \
  --policy .ai/policy.json \
  --base-sha HEAD~1 \
  --head-sha HEAD

python3 -m unittest scripts/test_ai_sdlc_check.py
```

Expected: a non-AI change passes without a dossier; an AI-sensitive fixture without a dossier fails; hash and candidate-SHA mutations fail.

For a dossier revision, add a new file instead of editing the base record. Keep
the `lineage_id`, increment `revision` by one, set `previous_status`, and bind
`supersedes.path` plus `supersedes.sha256` to the exact predecessor already in
the reviewed base. Confirm fork, duplicate revision, skipped status, risk
downgrade and predecessor rewrite mutations all fail.

Before `canary`, bind passing real-provider/canary reports and all required
immutable named approvals to the exact candidate. Before `rolled-back`, bind the
rollback report hash and candidate/deployment identity and disable the flag.
`closed` is valid only after verified production success or verified
rollback-before-production; a dossier field is not external approval or live
observation.

## Validate machine-readable files

```bash
python3 -m json.tool .ai/policy.json >/dev/null
python3 -m json.tool .ai/schema.json >/dev/null
python3 -m json.tool .ai/changes/example.json >/dev/null
python3 .release/test_validate_evidence.py
python3 .release/test_verify_checks.py
```

## GitHub checks

After pushing the branch, confirm separate checks for:

- existing core CI;
- AI change governance and gold-set integrity;
- CodeQL/dependency security;
- candidate admission only from a `v*` push event SHA equal to current
  `origin/main` HEAD and exact trusted workflow/job identities.

Skipped/unavailable jobs are not passing evidence. Record why they could not run.

The local validator is offline. A pass proves the repository contract for the
reviewed diff; it does not observe provider execution, GitHub ruleset/reviewer
enforcement, protected Environments, canary routing, deployment or production
telemetry.

Also prove workflow dependencies stay immutable:

```bash
python3 scripts/workflow_policy_check.py
python3 -m unittest scripts/test_workflow_policy_check.py
```

## Candidate delivery

After all required checks pass on the current `origin/main` HEAD, create and
push a `v*` tag that points exactly to that commit. The push event SHA is the
only source input; there is no manual, ref-selected, or historical-main path.
The workflow must reject a moved main head, untrusted/foreign/manual workflow
identity, wrong event/head SHA, duplicate/newer spoof, incomplete workflow/job
pagination, or any missing/skipped/stale/failed required gate.

Verify the workflow builds and publishes once under a quarantine identity,
immediately pulls the exact `name@digest`, and runs offline embedding,
bake-report and `<4 GiB` RSS checks on that digest. Only then may the digest be
recorded as admitted through an immutable evidence artifact; no mutable
admitted tag is created. Candidate JSON must pass
`.release/validate_evidence.py` and contain exact trusted run/job identities and
verifiable SBOM/provenance/attestation references. It can contain only
staging/production `not-configured` and no promotion object. Verified states
require later append-only promotion records for
the same digest with immutable named approval, migration, backup, smoke and
rollback evidence.

## External configuration checklist

These cannot be completed from repository code alone:

1. Protect `main`: PR required, independent approval, required checks, stale approval dismissal, force-push/delete off, bypass audited.
2. Protect the named `release-candidate` Environment and create protected
   `staging` and `production` GitHub Environments; production requires an
   independent named approval.
3. Configure OIDC or least-privilege credentials, registry permissions, deployment targets, URLs, and secrets.
4. Prove staging migration, auth/storage/real-LLM smoke, backup restore, rollback, and alert delivery.
5. Re-run release verification against the exact promoted digest.
