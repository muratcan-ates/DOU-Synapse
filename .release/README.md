# Release evidence

`release-candidate.yml` has one repository-controlled admission path: a `v*`
tag **push** whose event SHA equals the current `origin/main` HEAD. There is no
manual or ref-selected release path. The privileged job names the
`release-candidate` GitHub Environment, but repository files cannot enforce its
reviewers or branch rules; those protections remain an external prerequisite.

## Identity-bound admission

Display names and commit check-runs are not trusted identities. The workflow
queries all paginated workflow runs and jobs for these exact paths:

- `.github/workflows/ci.yml` — five CI jobs
- `.github/workflows/ai-quality.yml` — two AI governance jobs
- `.github/workflows/security.yml` — workflow policy plus two CodeQL jobs

Every accepted run must be the single completed successful `push` run for the
exact source SHA on `main`. Each required job name must occur exactly once in
that run and be completed successfully. A wrong workflow path/event/SHA,
duplicate run or job, missing URL, skipped result, or truncated pagination
fails closed. Manual and foreign workflows cannot satisfy admission.

Required job identities, in evidence order:

- `API — lint, tip, test`
- `API imajı — build + ağsız embedding kanıtı`
- `Web — lint, tip`
- `Belgeler — canlı sayı kapısı`
- `Uçtan uca — gerçek API + tarayıcı`
- `Govern reviewed AI diff`
- `Verify gold-set integrity`
- `Workflow dependency policy`
- `CodeQL (javascript-typescript)`
- `CodeQL (python)`

`Dependency review` is intentionally PR-only and therefore is not reused as a
main-push release identity.

## Quarantine before admission

The API image is built and pushed once under a
`quarantine-<sha>-<run>-<attempt>` tag. The workflow immediately pulls the
published `image.name@image.digest` and runs all artifact gates on that exact
digest: offline embedding, bake-report validation, and a measured `< 4 GiB`
RSS assertion. It also proves that the registry contains exact SBOM and SLSA
provenance descriptor digests and records the GitHub attestation URL and bundle
digest.

Only after those gates pass does the workflow create and validate
`release-evidence/candidate.json`, then upload the immutable evidence artifact.
No mutable “admitted” image tag is created: the admitted identity is the exact
digest recorded by the evidence artifact. A failed gate can leave only a
clearly named quarantine tag, never an admission record.

## Candidate is not promotion

Schema version 2 separates two record types:

- `candidate`: exact digest and supply-chain/artifact admission evidence;
  staging and production must both remain `not-configured`, and a promotion
  object is forbidden.
- `promotion`: later evidence for the **same** digest and source SHA. Production
  verification requires named approval with immutable GitHub user identity,
  approval reference/time/SHA/digest, staging and production smoke evidence,
  migration preflight/decision, verified backup, and rollback readiness or
  exercise evidence.

The dependency-free validator rejects unknown schema keywords and unknown
evidence fields, validates the field shapes, and enforces cross-field semantic
relationships. In particular, every check head SHA must equal `source.sha`,
every job must map to its trusted workflow, every promotion record must reuse
the candidate digest, and candidate evidence cannot self-claim deployment.

## Fail-closed staging preflight

`staging_preflight.py` consumes a schema-valid candidate and checks the live
web/API endpoints, anonymous/dev/staging authentication, private Supabase
storage, the exact remote migration ledger, assistant availability, a
cache-free cited real-provider response, and immutable backup/rollback
references. Secrets are read only from the environment and are redacted from
both outputs; database credentials are passed to `psql` through PostgreSQL
environment variables rather than command arguments.

Run it with the inputs documented in
[`specs/006-release-readiness/quickstart.md`](../specs/006-release-readiness/quickstart.md).
It always writes JSON and Markdown evidence when argument parsing succeeds:

- exit `0`: every preflight check passed;
- exit `1`: at least one configured live check failed;
- exit `2`: evidence, credentials, or another prerequisite is missing/blocked.

Even exit `0` is only `kind: staging_preflight`. It is not a deployment record,
environment approval, promotion record, or `staging-verified` claim.

Offline verification:

```bash
python3 -m unittest discover -s .release -p 'test_*.py'
```

This directory does **not** prove that protected environments, live staging or
production, cloud identities, backup/restore, smoke tests, or rollback have
been configured or exercised. Those remain explicit external evidence until a
valid promotion record exists.
