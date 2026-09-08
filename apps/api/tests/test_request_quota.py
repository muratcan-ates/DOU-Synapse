"""Request admission transaction/error contracts, with an explicit control-session fake."""

from __future__ import annotations

import asyncio
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

from starlette.requests import Request

from app.core import request_quota as quota
from app.core.errors import NotFoundError, PermissionDeniedError, app_error_handler

ACCEPT = {"allowed": True, "reason": "accepted", "retry_after_seconds": 0}


class Result:
    def __init__(self, row):
        self.row = row

    def mappings(self):
        return self

    def one(self):
        return self.row

    def all(self):
        return self.row


class Control:
    def __init__(self, row=None):
        self.row = row if row is not None else ACCEPT
        self.events = []
        self.calls = []
        self.actor = None
        self.fail_at = None
        self.commit_wait = None
        self.enter_wait = None
        self.sql_wait = None
        self.reached_commit = asyncio.Event()
        self.reached_sql = asyncio.Event()

    @asynccontextmanager
    async def session(self, actor):
        self.actor = actor
        self.events.append("acquire")
        if self.enter_wait is not None:
            await self.enter_wait.wait()
        try:
            yield self
            self.events.append("commit_start")
            self.reached_commit.set()
            if self.commit_wait is not None:
                await self.commit_wait.wait()
            if self.fail_at == "commit":
                raise RuntimeError("SYNTHETIC_SECRET_COMMIT")
            self.events.append("committed")
        except BaseException:
            self.events.append("rollback_or_uncertain")
            raise
        finally:
            self.events.append("released")

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.calls.append((sql, params))
        if "set_config" in sql:
            return Result(None)
        self.reached_sql.set()
        if self.sql_wait is not None:
            await self.sql_wait.wait()
        if self.fail_at == "sql":
            try:
                raise ValueError("postgresql://synthetic:synthetic-password@127.0.0.1/db")
            except ValueError as cause:
                raise RuntimeError("SYNTHETIC_SECRET_SQL Bearer synthetic-token") from cause
        return Result(self.row)


class PolicyTests(unittest.TestCase):
    def test_equivalent_configuration_has_one_fingerprint(self):
        a = quota.RequestPolicy.from_seconds("chat", 20, 60.0)
        b = quota.RequestPolicy.from_seconds("chat", 20, 60)
        self.assertEqual(a, b)
        self.assertEqual(a.window_ms, 60000)
        self.assertNotEqual(
            a.fingerprint, quota.RequestPolicy.from_seconds("chat", 19, 60).fingerprint
        )
        self.assertNotEqual(
            a.fingerprint, quota.RequestPolicy.from_seconds("qgen", 20, 60).fingerprint
        )

    def test_invalid_or_ambiguous_settings_are_rejected(self):
        for scope, limit, seconds in [
            ("foreign", 20, 60),
            (None, 20, 60),
            ("chat", None, 60),
            ("chat", True, 60),
            ("chat", 0, 60),
            ("chat", 101, 60),
            ("chat", 1.1, 60),
            ("chat", 1, 0),
            ("chat", 1, -1),
            ("chat", 1, float("nan")),
            ("chat", 1, float("inf")),
            ("chat", 1, -float("inf")),
            ("chat", 1, 3600.001),
            ("chat", 1, 0.0001),
            ("chat", 1, None),
            ("chat", 1, True),
        ]:
            with (
                self.subTest(scope=scope, limit=limit, seconds=seconds),
                self.assertRaises(ValueError),
            ):
                quota.RequestPolicy.from_seconds(scope, limit, seconds)


class AdmissionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.control = Control()
        self.actor, self.course = uuid4(), uuid4()
        self.patcher = patch.object(quota, "control_rls_session", self.control.session)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    async def take(self, **overrides):
        values = dict(
            user_id=self.actor,
            course_id=self.course,
            scope="chat",
            limit=20,
            window_seconds=60,
        )
        values.update(overrides)
        return await quota.take_request_slot(**values)

    async def test_independent_commit_and_release_precede_caller_provider_work(self):
        self.control.commit_wait = asyncio.Event()
        provider = []

        async def caller():
            accepted = await self.take()
            if accepted.allowed:
                provider.append(self.control.events.copy())

        task = asyncio.create_task(caller())
        await self.control.reached_commit.wait()
        self.assertEqual(provider, [])
        self.control.commit_wait.set()
        await task
        self.assertEqual(provider, [["acquire", "commit_start", "committed", "released"]])

    async def test_caller_failure_has_no_control_refund_path(self):
        async def caller():
            self.assertTrue((await self.take()).allowed)
            raise RuntimeError("synthetic main operation rollback")

        with self.assertRaisesRegex(RuntimeError, "main operation"):
            await caller()
        self.assertEqual(self.control.events[-2:], ["committed", "released"])
        self.assertEqual(len(self.control.calls), 2)
        # Actual independent transaction durability must still be measured with PG.

    async def test_parameters_use_authenticated_context_without_request_content(self):
        await self.take()
        self.assertEqual(self.control.actor, self.actor)
        sql, params = self.control.calls[1]
        self.assertEqual(params["course_id"], self.course)
        self.assertNotIn("user_id", params)
        self.assertEqual(set(params), {"course_id", "scope", "limit", "window_ms", "fingerprint"})
        self.assertNotIn(str(self.course), sql)
        self.assertEqual(
            self.control.calls[0][1],
            {"lock_timeout": "250ms", "statement_timeout": "500ms"},
        )

    async def test_denial_uses_the_single_atomic_retry_value(self):
        self.control.row = {
            "allowed": False,
            "reason": "rate_limited",
            "retry_after_seconds": 298,
        }
        result = await self.take(scope="qgen", limit=5, window_seconds=300)
        self.assertFalse(result.allowed)
        self.assertEqual(result.retry_after_seconds, 298)
        self.assertEqual(len(self.control.calls), 2)  # no second retry-after read
        self.assertEqual(self.control.events[-2:], ["committed", "released"])

    async def test_control_commit_failure_never_reaches_provider_or_retries(self):
        self.control.fail_at = "commit"
        provider = []
        with self.assertRaises(quota.RequestQuotaUnavailableError) as caught:
            result = await self.take()
            provider.append(result)
        self.assertEqual(provider, [])
        self.assertEqual(self.control.events.count("acquire"), 1)
        self.assertEqual(caught.exception.headers, {"Retry-After": "1"})
        self.assertNotIn("SYNTHETIC_SECRET", str(caught.exception))

    async def test_sql_failure_uses_the_same_safe_503_envelope(self):
        self.control.fail_at = "sql"
        with self.assertRaises(quota.RequestQuotaUnavailableError) as caught:
            await self.take()
        request = Request({"type": "http", "headers": []})
        response = await app_error_handler(request, caught.exception)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["retry-after"], "1")
        self.assertIn(b'"code":"rate_limit_unavailable"', response.body)
        self.assertNotIn(b"SYNTHETIC_SECRET", response.body)
        self.assertNotIn(b"synthetic-password", response.body)
        self.assertNotIn(b"synthetic-token", response.body)
        self.assertIsNone(caught.exception.__cause__)
        self.assertTrue(caught.exception.__suppress_context__)
        self.assertNotIn(str(self.actor).encode(), response.body)

    async def test_unauthorized_membership_has_explicit_404_or_403(self):
        for reason, error in [
            ("not_member", NotFoundError),
            ("not_instructor", PermissionDeniedError),
        ]:
            with self.subTest(reason=reason):
                self.control.row = {
                    "allowed": False,
                    "reason": reason,
                    "retry_after_seconds": 0,
                }
                with self.assertRaises(error):
                    await self.take()

    async def test_policy_mismatch_and_malformed_results_fail_closed(self):
        for row in [
            {"allowed": False, "reason": "policy_mismatch", "retry_after_seconds": 0},
            {"allowed": "true", "reason": "accepted", "retry_after_seconds": 0},
            {"allowed": True, "reason": "rate_limited", "retry_after_seconds": 1},
            {"allowed": False, "reason": "rate_limited", "retry_after_seconds": 0},
            {"allowed": False, "reason": "rate_limited", "retry_after_seconds": 3601},
            {"allowed": False, "reason": "rate_limited", "retry_after_seconds": True},
            {"allowed": True, "reason": "accepted", "retry_after_seconds": 1},
        ]:
            with self.subTest(row=row):
                self.control.row = row
                with self.assertRaises(quota.RequestQuotaUnavailableError):
                    await self.take()

    async def test_local_bad_config_is_503_without_any_db_attempt(self):
        with self.assertRaises(quota.RequestQuotaUnavailableError):
            await self.take(window_seconds=float("nan"))
        self.assertEqual(self.control.events, [])

    async def test_deadline_covers_acquisition_statement_and_commit(self):
        for stage in ("enter_wait", "sql_wait", "commit_wait"):
            with self.subTest(stage=stage):
                setattr(self.control, stage, asyncio.Event())
                with patch.object(quota, "CONTROL_TIMEOUT_SECONDS", 0.005):
                    with self.assertRaises(quota.RequestQuotaUnavailableError):
                        await asyncio.wait_for(self.take(), timeout=0.5)
                setattr(self.control, stage, None)

    async def test_external_cancellation_propagates_without_retry(self):
        self.control.sql_wait = asyncio.Event()
        task = asyncio.create_task(self.take())
        await self.control.reached_sql.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.control.events.count("acquire"), 1)
        self.assertNotIn("committed", self.control.events)


class ReadinessTests(unittest.IsolatedAsyncioTestCase):
    async def test_policy_projection_does_not_consume_a_slot(self):
        rows = [
            {
                "scope": scope,
                "fingerprint": quota.RequestPolicy.from_seconds(scope, limit, seconds).fingerprint,
            }
            for scope, limit, seconds in [("chat", 20, 60), ("qgen", 5, 300)]
        ]
        control = Control(rows)
        settings = SimpleNamespace(
            chat_rate_limit_requests=20,
            chat_rate_limit_window_seconds=60,
            question_gen_rate_limit_requests=5,
            question_gen_rate_limit_window_seconds=300,
        )
        with patch.object(quota, "control_rls_session", control.session):
            self.assertTrue(await quota.request_quota_is_ready(settings))
            self.assertEqual(control.actor, UUID(int=0))
            self.assertIn("request_quota_policies", control.calls[-1][0])
            settings.chat_rate_limit_requests = 21
            self.assertFalse(await quota.request_quota_is_ready(settings))
            settings.chat_rate_limit_requests = 20
            control.fail_at = "commit"
            self.assertFalse(await quota.request_quota_is_ready(settings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
