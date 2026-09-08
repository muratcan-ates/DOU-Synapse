"""Actual health handler with offline DB faults and synthetic secrets."""

import json
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import Response

from app.api import health
from app.core import readiness


class HealthTests(unittest.IsolatedAsyncioTestCase):
    async def test_chained_database_fault_never_logs_url_token_or_cause(self):
        @asynccontextmanager
        async def broken_session():
            try:
                raise ValueError("postgresql://synthetic:synthetic-password@127.0.0.1/db")
            except ValueError as cause:
                raise RuntimeError("Authorization: Bearer synthetic-token") from cause
            yield  # unreachable: implements the session context manager shape

        logger = Mock()
        response = Response()
        with (
            patch.object(readiness, "get_session_factory", return_value=broken_session),
            patch.object(readiness, "request_quota_is_ready", AsyncMock(return_value=False)),
            patch.object(readiness, "get_settings", return_value=SimpleNamespace()),
            patch.object(readiness, "warmup_state", return_value="disabled"),
            patch.object(readiness, "logger", logger),
        ):
            result = await health.ready(response)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["checks"]["request_quota"], "error")
        logger.warning.assert_called_once_with(
            "hazırlık kontrolü başarısız",
            extra={"context": {"error_type": "RuntimeError", "stage": "database_probe"}},
        )
        serialized = repr(logger.mock_calls) + json.dumps(result)
        for canary in [
            "postgresql://",
            "synthetic-password",
            "synthetic-token",
            "Authorization",
            "ValueError",
        ]:
            self.assertNotIn(canary, serialized)
        self.assertNotIn("exc_info", logger.warning.call_args.kwargs)

    async def test_live_has_no_request_quota_or_database_dependency(self):
        with (
            patch.object(
                readiness, "get_session_factory", side_effect=AssertionError("DB touched")
            ),
            patch.object(
                readiness, "request_quota_is_ready", side_effect=AssertionError("quota touched")
            ),
            patch.object(
                health,
                "get_settings",
                return_value=SimpleNamespace(environment="test", api_version="synthetic"),
            ),
        ):
            self.assertEqual((await health.live())["status"], "ok")


if __name__ == "__main__":
    unittest.main(verbosity=2)
