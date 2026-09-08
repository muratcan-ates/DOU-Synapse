# D2 blocker observer — proposed test-only correction

The full API run reached1560 PASS and failed this one test while waiting for a matching `pg_stat_activity` row. It did not reach the final LostClaim/state assertions. The production function's separate fresh DB-clock check after locking was not shown to fail by that result.

The observer holds one blocker transaction while repeatedly reading `pg_stat_activity`. A transaction-local activity snapshot obtained before the worker starts waiting can hide that later wait. Refreshing the observer with `pg_stat_clear_snapshot()` is a targeted correction; a real rerun is still required to establish that this caused the recorded intermittent timeout.

The proposed file changes only `test_failure_waiting_for_job_lock_cannot_release_an_expired_claim`:

- Prime the no-waiter snapshot before starting the worker task, making the stale-observer scenario explicit.
- Refresh statistics before each poll while retaining the actual job-row lock.
- Match only a dou_worker blocked by this connection's PID, not any unrelated worker.
- Observe a real lock waiter before the400ms database lease deadline, then hold the lock until the actual DB clock crosses it.
- Keep the0.8s observer bound, final LostClaim and exact job/document state equality.

No production or repository file was edited and no database was started. `observer-refresh.patch` is against the original file whose hash is in `source-receipt.json`.

Root validation: run this test on a uniquely provisioned test DB; run the same test in a disposable copy with only the `pg_stat_clear_snapshot` call removed. With the primed pre-worker snapshot the negative copy should fail in the waiter observer, while the corrected copy must observe the lock and cross actual expiry. Preserve both results, then run the complete API suite. Do not replace a timeout with a larger number or call the proposed correction measured until those runs pass.
