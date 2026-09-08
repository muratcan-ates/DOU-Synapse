# OPS1 R1 — real SQL statement-error characterization

This candidate is unexecuted. It changes no repository source. The parent owns the trusted local DB guard, source staging, execution and evidence interpretation. No production SAVEPOINT, rollback, commit, authorization, audit function or response handler has been changed.

## Scope and operator entry

Stage `test_ops1_readiness_sql_error_characterization.py` as `apps/api/tests/test_ops1_readiness_sql_error_characterization.py` in the parent's isolated source tree. Its normal repository `tests/conftest.py` performs DROP/CREATE/migrations on its configured test database. Run **only through the existing root-owned guarded unique-DB runner**, with its numeric loopback, explicit port, actual application/admin identities and trusted target checks. The acknowledgement below is not a replacement for that guard. Do not run against an existing project, production or shared database.

The parent creates a new private mode-0700 output directory and supplies these additional environment fields to the guarded runner:

```text
OPS1_R1_ROOT_GUARDED_RUN=yes
OPS1_R1_REPORT_DIRECTORY=<new private output directory>
OPS1_R1_EXPECTED_SOURCES=<trusted source hash JSON path>
```

`expected-sources.json` captures the reviewed current source hashes; recheck those against the staged source before the run. If the parent intentionally stages a changed implementation for a separate comparison, produce a separate trusted expected manifest and separate output directory and preserve this baseline. Required source keys are the test's `SOURCE_FILES`. Include the test file's SHA from `MANIFEST.json` in the parent receipt as well. No connection URL, password or auth token belongs in CLI arguments or these report files.

Within the guarded runner, from the staged `apps/api` directory, the narrow pytest selection is:

```text
.venv/bin/python -m pytest -q tests/test_ops1_readiness_sql_error_characterization.py
```

There are two parametrized cases: ordinary SELECT 1 control and real SELECT 1 / 0 fault. Root may select `[control]` and `[division-by-zero]` separately if its runner requires one case per provisioned DB. This is a paired fault experiment, **not** a production-code removed-protection negative control. No test, database, server or candidate-module import was executed while preparing the candidate. A text-only AST parse extracted the literal source-file inventory for hashing; it did not execute the test or validate runtime behavior.

## What is observed

The fixture uses the real FastAPI application, real authorized `dou_app` session and ordinary function-scoped dependency exit. `ASGITransport(raise_app_exceptions=False)` lets the client receive the application's actual error response instead of rethrowing the ASGI exception. No HTTP status, body, auth dependency, SQL role check, audit SQL or transaction finalizer is stubbed.

1. A synthetic platform admin is provisioned through the existing admin-engine fixture. No course, document, chat, token budget or provider work is created.
2. Public readiness is observed before the experiment. The embedding state alone is fixed to `disabled` to isolate SQL behavior; quota readiness still uses the real separate control session.
3. `_database_checks` receives the actual supplied admin `AsyncSession`. Before the fault, a real query verifies current `dou_app`, no superuser/BYPASSRLS, row_security on and the exact synthetic principal context. The only injected failure is PostgreSQL SELECT 1 / 0, and its actual SQLSTATE is recorded, never a Python AsyncMock exception.
4. A wrapper calls the unmodified shared checker and records its returned fixed status values. It then attempts read-only SELECT 1 on that same session. This diagnostic read neither repairs nor rolls back a failed transaction. It records actual SQLSTATE or success; it does not replace context exit.
5. The actual admin response after the function-scoped session exit is reduced to status, known fixed dependency values and error-envelope/request-ID shape booleans. Neither a 200 degraded response nor a 500 is asserted in advance.
6. A separate admin-engine connection queries the exact request's persisted audit record after the HTTP exchange. Only count/allowed/actor-and-action-match counts are written. This verifies observable persistence; it does not imply the main transaction committed writes (the main route and injected queries are read-only).
7. After removing the injected failure, public readiness receives its normal fresh logical session. A real SELECT 1 and principal-context observation check whether the new session is usable and has no preceding admin identity. The original vector check and actual quota check still run. A distinct physical PostgreSQL backend is not required: correctly reset pooled connections may be reused.

The test writes `control.json` and `division-by-zero.json` using exclusive mode-0600 creation; existing reports are not overwritten. Only calibration is asserted: the actual role/principal conditions, one injected probe call, the requested real SQLSTATE and unchanged bound source files. A pytest PASS means a calibrated characterization was recorded, **not** that a particular HTTP or session recovery policy is accepted. The parent must inspect both JSON results.

## Root oracle and limits

| Observation | Control calibration/expected baseline | Fault characterization |
| --- | --- | --- |
| Actual injected SQLSTATE | null | 22012 must be real |
| Checker return | Read recorded snapshot | Read recorded snapshot; do not preset |
| Same-session subsequent SELECT | normally succeeds | Read SQLSTATE; 25P02 would demonstrate failed transaction |
| Actual admin HTTP | normally 200 with overview | Record actual status and response/error shape; do not choose outcome in advance |
| Persisted allowed audit | normally exactly one matching allowed record | Measure separately; main session failure cannot itself roll back an already separate audit transaction |
| Public next readiness | normally 200, clean logical session | Measure real recovery independently; public fields must not contain aggregates |

Evaluate unexpected values as findings or invalid environment, not as a reason to overwrite the receipt. The raw ordinary pytest capture must remain in the parent's private evidence directory; the candidate does not sanitize arbitrary application logs. The JSON exporter copies no raw response, exception text, request ID, principal, profile, SQL parameters or DSN. Source hashes and installed package versions make the measured stack identifiable.

This experiment covers an ordinary SQL statement error on an existing connection. It does not cover a lost socket, timeout, pool exhaustion, interrupted COMMIT, a write-bearing caller, or guarantee every failure yields a degraded overview. It does not prove the database COMMIT command tag: HTTP completion and independently visible audit are the measured boundaries. Do not infer audit rollback or user data loss from 25P02. No legal compliance, deployment, hosted-CI or provider-quality result is claimed.
