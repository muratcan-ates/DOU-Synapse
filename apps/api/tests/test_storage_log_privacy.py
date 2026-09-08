"""Depolama ve HTTP istemcisi gerçek emitted logları özel metadata taşımamalı."""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stdout
from typing import Any

import httpx
import pytest

from app.core.errors import StorageUnavailableError
from app.core.logging import configure_logging
from app.modules.ingestion.storage import SupabaseStorage

PROJECT_HOST = "synthetic-private-project.invalid"
BUCKET = "SYNTHETIC_PRIVATE_BUCKET"
OBJECT_KEY = "courses/SYNTHETIC_COURSE/SYNTHETIC_OBJECT.md"
PRIVATE_BODY = b"SYNTHETIC_PRIVATE_BODY"
SERVICE_KEY = "SYNTHETIC_SERVICE_ROLE_CANARY"
SENSITIVE_MESSAGE = "SYNTHETIC_PRIVATE_TRANSPORT_MESSAGE"
CANARIES = (
    PROJECT_HOST,
    BUCKET,
    OBJECT_KEY,
    "SYNTHETIC_OBJECT",
    SERVICE_KEY,
    PRIVATE_BODY.decode(),
    SENSITIVE_MESSAGE,
)


@contextmanager
def _emitted_logs(level: int) -> Iterator[io.StringIO]:
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    names = ("httpx", "httpcore", "uvicorn", "uvicorn.access", "uvicorn.error")
    state = {
        name: (
            logging.getLogger(name).level,
            logging.getLogger(name).handlers[:],
            logging.getLogger(name).propagate,
        )
        for name in names
    }
    sink = io.StringIO()
    try:
        with redirect_stdout(sink):
            configure_logging(level)
            yield sink
    finally:
        root.handlers[:] = original_handlers
        root.setLevel(original_level)
        for name, (previous_level, handlers, propagate) in state.items():
            logger = logging.getLogger(name)
            logger.setLevel(previous_level)
            logger.handlers[:] = handlers
            logger.propagate = propagate


def _store(outcome: str) -> SupabaseStorage:
    def handle(request: httpx.Request) -> httpx.Response:
        if outcome == "transport_error":
            raise httpx.ReadTimeout(SENSITIVE_MESSAGE, request=request)
        return httpx.Response(200 if outcome == "success" else 503, content=PRIVATE_BODY)

    return SupabaseStorage(
        project_url=f"https://{PROJECT_HOST}",
        service_role_key=SERVICE_KEY,
        bucket=BUCKET,
        transport=httpx.MockTransport(handle),
    )


async def _operate(store: SupabaseStorage, operation: str) -> None:
    if operation == "save":
        await store.save(OBJECT_KEY, PRIVATE_BODY)
    elif operation == "load":
        await store.load(OBJECT_KEY)
    else:
        await store.delete(OBJECT_KEY)


def _assert_private(sink: io.StringIO) -> list[dict[str, Any]]:
    output = sink.getvalue()
    for canary in CANARIES:
        assert canary not in output
    return [json.loads(line) for line in output.splitlines()]


@pytest.mark.parametrize("level", [logging.INFO, logging.DEBUG])
@pytest.mark.parametrize("operation", ["save", "load", "delete"])
@pytest.mark.parametrize("outcome", ["success", "http_error", "transport_error"])
async def test_emitted_storage_logs_contain_only_safe_operation_metadata(
    level: int, operation: str, outcome: str
) -> None:
    with _emitted_logs(level) as sink:
        if outcome == "success":
            await _operate(_store(outcome), operation)
        else:
            with pytest.raises(StorageUnavailableError):
                await _operate(_store(outcome), operation)
    records = _assert_private(sink)
    if outcome == "success":
        assert records == []
    else:
        assert len(records) == 1
        expected = {"event": "storage_operation_failed", "operation": operation}
        if outcome == "http_error":
            expected["status_code"] = 503
        assert records[0]["context"] == expected
        assert "exception" not in records[0]


@pytest.mark.parametrize("operation", ["save", "load", "delete"])
@pytest.mark.parametrize("outcome", ["http_error", "transport_error"])
async def test_upper_worker_traceback_does_not_restore_private_transport_cause(
    operation: str,
    outcome: str,
) -> None:
    with _emitted_logs(logging.INFO) as sink:
        try:
            await _operate(_store(outcome), operation)
        except StorageUnavailableError:
            logging.getLogger("synthetic.worker").exception("worker operation failed")
    records = _assert_private(sink)
    assert len(records) == 2
    assert "StorageUnavailableError" in records[1]["exception"]
    assert "ReadTimeout" not in records[1]["exception"]
    assert "HTTPStatusError" not in records[1]["exception"]


def test_http_transport_debug_headers_are_suppressed_even_when_app_debug() -> None:
    with _emitted_logs(logging.DEBUG) as sink:
        logging.getLogger("httpcore.http11").debug("request headers %s", SERVICE_KEY)
        logging.getLogger("httpx").info("request URL %s/%s", PROJECT_HOST, OBJECT_KEY)
        logging.getLogger("app.synthetic").debug("useful application diagnostic")
    records = _assert_private(sink)
    assert len(records) == 1
    assert records[0]["message"] == "useful application diagnostic"
