"""Offline maintenance transaction contracts, not evidence of physical PG expiry."""

import unittest
from contextlib import asynccontextmanager

from app.core import request_quota_maintenance as maintenance


class Session:
    def __init__(self):
        self.result = 3
        self.events = []
        self.args = None
        self.fail_commit = False

    def __call__(self):
        return self

    async def __aenter__(self):
        self.events.append("acquire")
        return self

    async def __aexit__(self, *_):
        self.events.append("released")

    @asynccontextmanager
    async def begin(self):
        yield
        if self.fail_commit:
            raise RuntimeError("SYNTHETIC_MAINTENANCE_SECRET")
        self.events.append("committed")

    async def execute(self, _statement, _params):
        return None

    async def scalar(self, statement, params):
        self.args = (str(statement), params)
        return self.result


class MaintenanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_batch_result_returns_only_after_commit(self):
        session = Session()
        self.assertEqual(await maintenance.purge_expired_request_windows(session, batch_size=5), 3)
        self.assertEqual(session.events, ["acquire", "committed", "released"])
        self.assertEqual(
            session.args,
            ("SELECT app.purge_expired_request_windows(:batch_size)", {"batch_size": 5}),
        )

    async def test_bad_batch_never_opens_control_transaction(self):
        for batch in [None, 0, -1, 1001, True, 2.5]:
            session = Session()
            with self.subTest(batch=batch), self.assertRaises(ValueError):
                await maintenance.purge_expired_request_windows(session, batch_size=batch)
            self.assertEqual(session.events, [])

    async def test_invalid_result_and_uncertain_commit_have_fixed_error(self):
        for result, fail_commit in [(False, False), (6, False), (-1, False), (3, True)]:
            session = Session()
            session.result, session.fail_commit = result, fail_commit
            with self.subTest(result=result, fail_commit=fail_commit):
                with self.assertRaises(maintenance.RequestQuotaMaintenanceError) as caught:
                    await maintenance.purge_expired_request_windows(session, batch_size=5)
                self.assertEqual(str(caught.exception), "request quota maintenance unavailable")
                self.assertNotIn("committed", session.events)


if __name__ == "__main__":
    unittest.main(verbosity=2)
