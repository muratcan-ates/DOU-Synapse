# OPS1 read-only second review

Base c45e0e7073c92638ced7a3ff523578dd598c350b; applied dirty OPS1 sources read on8 September2026. No repository changes, tests, PostgreSQL calls, server/browser runs or dependency installs in this review. Source findings below are not measured runtime results.

## Conclusion

No concrete admin-role bypass, public aggregate leak, enum/null-constraint defect or p95 denominator error was found in the applied patch. The two previous monkeypatch locations were correctly updated. The new helper's supplied-session SQL-error path has a bounded validation gap; it must not be described as leaving the caller's transaction usable or as guaranteed to fail COMMIT. Current production callers do not demonstrate data loss through this path.

## R1 — supplied-session SQL failure is caught without transaction recovery

Location: `apps/api/app/core/readiness.py:49–56`; caller `apps/api/app/api/admin.py:36–49`; outer session `apps/api/app/core/db.py:124–127` and `apps/api/app/api/deps.py:71–91`.

If the extension-catalog query raises a real SQL statement error on the supplied session, catching the Python exception does not clear PostgreSQL's failed transaction. The helper reports database=error and pgvector becomes unknown in the admin result, but the session is not guaranteed usable for another query. An ordinary aborted transaction and a lost/invalidated physical connection have different exit behavior. Do not claim “COMMIT always raises”: installed psycopg `_connection_base.py:570–585` sends COMMIT, and `_exec_command` accepts COMMAND_OK without verifying a COMMIT command tag; SQLAlchemy `orm/session.py:1311–1332` marks committed after its transaction.commit returns. This source inspection does not replace actual PG measurement of HTTP/exit outcome.

Why this is not a confirmed data-loss or audit-regression finding in the current route:

- `app.admin_overview()` is STABLE/read-only and is executed before the new probe. No user mutation follows the new probe in this handler.
- Platform-admin audit is **a separate completed transaction** in `api/deps.py:220–224`. Aborting the overview session cannot roll that audit back. The initial worry that the allowed audit disappears is not supported by the actual code.
- Authentication and overview SQL may already fail before probing; existing function-scoped transaction handling must continue to block a response when it cannot complete safely. No invented empty totals are introduced.
- An extension missing from the catalog is not a SQL exception; it yields databaseok/pgvectormissing/degraded without aborting the session. Canonical quota mismatch also uses the separate existing control transaction and does not abort the admin session.

Root's smallest useful additional measurement: in an isolated synthetic DB, inject a real failing SQL statement only at `_database_checks` on the actual passed session (not an AsyncMock exception). Observe helper result, subsequent same-session SELECT SQLSTATE, actual admin response/exit, and independently persisted allowed audit for a unique request ID. Preserve a matched normal request and no confidential error body. A helper direct SQL probe can establish25P02; the real HTTP case establishes whether this stack returns degraded200 or safe error. Do not drop extensions/revoke cluster roles or alter unrelated deployment permissions to make this case.

If root requires “recoverable probe error still returns a valid degraded overview”, the bounded correction is a savepoint around only the supplied-session probe, with the catch outside the savepoint, plus an actual statement-error regression. Do not add a second application-pool borrow or call rollback/commit on the caller's whole transaction. If root instead keeps the current narrowly read-only behavior, document its failure semantics and prohibit reuse in a write-bearing session; the existing mocked session-success test is not proof of post-error session health. A new timeout architecture is unnecessary for this review finding.

## Verified source/contracts

### Fixtures and p95

`tests/test_admin_readiness.py:117–145` matches actual migrations:

- `qa` is a valid chat_mode; answered/out_of_scope are valid answer_status (0003:30–32).
- request_logs.status and token_count are nullable; latency values are nonnegative; cache_hit has DEFAULTfalse (0003:135–146).
- Later audience is NOT NULL **with DEFAULTstudent** (0015:114–115), so omitted fixture audience does not violate a constraint. The root fixture writes via admin_engine; it is not testing request-log self-insert RLS, which is unchanged and separately covered.
- CourseFactory returns UUID and creates actual course membership; fixture foreign keys and UUID binds are consistent. Existing clean_tables removes courses/profiles with cascade, so request_logs are cleaned between DB-backed tests.
- Overview SQL0014:124–147 selects exact chat route + HTTP200–299 + last24h. The two selected latencies100/300 give percentile_cont(.95)=290, sample2, token30. HTTP200 out_of_scope rightly remains a technical-success sample;503/429, other route,25h row and rolled-back200 row do not count. Empty p95 remains null, not0ms. No all-request failure metric is claimed.

The policy mismatch test changes client Settings against the real canonical SQL fingerprint for chat andqgen, then restores it. This is a real SQL contract test once root runs it, not a changed database policy row. Both public/admin observations are stable under the controlled mismatch. Checking zero new quota windows is useful but does not alone prove no arbitrary provider calls; source shows no provider/storage invocation and the standard test environment is synthetic.

### Auth and privacy

`api/admin.py` retains PlatformAdminDep and the SQL helper rechecks platform admin. A course instructor remains a separate axis and cannot reach the overview helper. The new forbidden_probe tests ensure the new checker is not reached before authorization, without removing independent RLS/SQL enforcement. Existing direct SQL and denied audit tests remain necessary.

Public health still serializes only status/checks and its original dictionary-shaped OpenAPI response; admin totals/identities never flow through the helper. New field values are fixed dependency states. The moved health privacy test still checks chained synthetic DSN/token/cause absence and absence of exc_info. Public liveness remains independent of the shared checker.

No new raw path, course/user/claim identifier or request content was added to logs/UI/metrics. Generic app.error traceback privacy remains a pre-existing separate concern; this review does not certify it.

### Existing patch targets

`tests/test_portal.py:548` now patches `app.core.readiness.warmup_state`. `tests/test_request_quota_health.py` now patches checker dependencies/logger on core.readiness, while liveness Settings remains patched on api.health. Search of current tests found no remaining old app.api.admin.warmup_state or app.api.health dependency monkeypatch target requiring relocation. The moved test bodies preserve their assertions.

### UI and observation limits

New optional client fields use `?? "unknown"`; missing/null fields display “Ölçülemedi” with warning tone. Explicit error/missing states now have Turkish labels. New server fields are required in its successful response, which is an additive schema change; regenerate OpenAPI. Existing AdminGate, async Resource error/refresh behavior and authorization fetch order remain unchanged.

P95 label includes sample count and states successful recorded HTTP-chat scope; failures and no-row calls are explicitly outside it. This wording does not turn technical HTTP200 refusals into a pedagogical-success score. Added badges wrap using existing flex-wrap. Actual375px/dark rendering is still unmeasured in this review.

The first new browser test uses an actual authorized API response. The degraded/legacy cases deliberately modify only response fields and are labeled UI contract fixtures; they cannot establish real quota/DB failure in a browser. Actual error/recovery is the backend SQL test. No new role or policy fixture shortcut is introduced.

The helper provides **shared evaluation semantics, not one atomic global snapshot**. Admin aggregation, vector query, canonical control query and warmup state occur sequentially. Separate requests may disagree if state changes between them. A dependency can fail after either response; neither status includes LLM/Storage/worker scheduling or durable exam submission. These are documented scope limits, not a new regression or reason to add timeout/config complexity now.

## Root acceptance still required

Actual focused API tests, the admin-status negative control, optional R1 statement-error characterization, targeted web tests/tsc/build, the real/fixture-labeled browser cases and existing admin role/mobile/dark checks. No passing result is asserted by this read-only review. Root's own runs remain the authoritative evidence.

## Inspected source hashes

```json
{
  "apps/api/app/core/readiness.py": "9b1d71dd447cad646ec3dadce6307f89547e24384007667b59c455a4f664064e",
  "apps/api/app/api/admin.py": "fdf679b526046e41cfc78d266a91bbef5bebc4f8a0a27338a192e8b702a53a46",
  "apps/api/app/api/health.py": "b11c51dd7f38846bca5f5250dd561a80ed0785c16750f190bdb7dcb376e20f43",
  "apps/api/app/api/deps.py": "77edb1855d0c5d16b1c17d5a383d3ebadb5ffa0b087692c32ba14d8ab1cbb360",
  "apps/api/app/core/db.py": "31eb66fa632d00ff62b3ff3cde80020b47d6b2c64c2190ff120035a8f321083c",
  "apps/api/tests/test_admin_readiness.py": "afec8d51bb5d878cd6c4496e9f7c237d112fa01cec9b1b8c53b994779ba18e16",
  "apps/api/tests/test_portal.py": "6d2b1571323734b78990761c0aca1dd58f93bf8e3af16cd7cbe06e1c4808b0de",
  "apps/api/tests/test_request_quota_health.py": "f16559528f3dcd84bca27b34fefcdebc03b6cca0f788a462168417d74000574c",
  "apps/web/app/admin/page.tsx": "f5cbfeca2871c09c71a6ab1d1d8a8630b17a8943fb14752a5133abbabf255677",
  "apps/web/e2e/admin-readiness.spec.ts": "b9818492d3dddf65471c467db153a3d9dbf19d69cf7ac9ac33a762915d478de5"
}
```
