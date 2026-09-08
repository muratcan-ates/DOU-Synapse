"""S9C: actual owned-handler failures, captured stdout/stderr, synthetic only.

No DB, socket, server or provider is used. Root runs both frozen S9B and S9C
against these same assertions; preparation is not an executed acceptance result.
"""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from typing import Any

import pytest
from fastapi import Request

from app.core import errors
from app.core import logging as app_logging

PRIVATE = "SYNTHETIC_STUDENT_ANSWER_S9C_CANARY"
PRIVATE_URL = "https://provider.invalid/s9c-private?token=opaque-s9c-secret"
SUPPORT_ID = "synthetic-s9c-support"
CANARIES = (PRIVATE, PRIVATE_URL, "opaque-s9c-secret")


class OutputSink:
    def __init__(self, mode: str, failure: BaseException | None = None) -> None:
        self.mode = mode
        self.failure = failure
        self.writes = 0
        self.flushes = 0
        self.parts: list[str] = []

    def write(self, value: str) -> int:
        self.writes += 1
        if self.mode == "write":
            raise self.failure if self.failure is not None else OSError("synthetic sink failure")
        self.parts.append(value)
        return len(value)

    def flush(self) -> None:
        self.flushes += 1
        if self.mode == "flush":
            raise self.failure if self.failure is not None else OSError("synthetic flush failure")

    def getvalue(self) -> str:
        return "".join(self.parts)


class FailureFormatter(logging.Formatter):
    def __init__(self, error: BaseException | None = None) -> None:
        super().__init__()
        self.error = error

    def format(self, record: logging.LogRecord) -> str:
        del record
        raise self.error if self.error is not None else ValueError(PRIVATE + PRIVATE_URL)


class FailingFallback:
    def __init__(self, error: BaseException | None = None) -> None:
        self.error = error
        self.writes = 0

    def write(self, value: str) -> int:
        del value
        self.writes += 1
        raise self.error if self.error is not None else ValueError("synthetic closed fallback")

    def flush(self) -> None:
        pass


class ReentrantFallback:
    def __init__(self) -> None:
        self.writes = 0
        self.parts: list[str] = []

    def write(self, value: str) -> int:
        self.writes += 1
        if self.writes > 2:
            # Bound the old negative arm too; no deep recursive/stress test.
            raise OSError("synthetic fallback recursion limit")
        self.parts.append(value)
        logging.getLogger("uvicorn.error").error(PRIVATE + PRIVATE_URL)
        return len(value)

    def flush(self) -> None:
        pass

    def getvalue(self) -> str:
        return "".join(self.parts)


@contextmanager
def handler_output(
    stdout: Any, stderr: Any, *, formatter: logging.Formatter | None = None
) -> Iterator[logging.Handler]:
    names = ("", "app.error", "httpx", "httpcore", "uvicorn", "uvicorn.error", "uvicorn.access")
    saved = {
        name: (logger.level, logger.handlers[:], logger.propagate, logger.disabled)
        for name in names
        if (logger := logging.getLogger(name)) is not None
    }
    old_raise_exceptions = logging.raiseExceptions
    handler: logging.Handler | None = None
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            app_logging.configure_logging(logging.DEBUG)
            assert logging.raiseExceptions is old_raise_exceptions
            handlers = logging.getLogger().handlers
            assert len(handlers) == 1
            handler = handlers[0]
            if formatter is not None:
                handler.setFormatter(formatter)
            yield handler
    finally:
        for name, (level, handlers, propagate, disabled) in saved.items():
            logger = logging.getLogger(name)
            logger.setLevel(level)
            logger.handlers[:] = handlers
            logger.propagate = propagate
            logger.disabled = disabled
        if handler is not None:
            handler.close()


def assert_private_absent(*outputs: str) -> None:
    for output in outputs:
        for marker in CANARIES:
            assert marker not in output, "synthetic private value escaped through logging failure"
        assert "--- Logging error ---" not in output


def assert_fixed_fallback(value: str) -> None:
    assert value.isascii()
    lines = value.splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "level": "ERROR",
        "logger": "app.logging",
        "message": "log emission failed",
        "context": {"error_code": "logging_output_failed"},
    }


@pytest.mark.parametrize("mode", ["write", "flush", "formatter"])
@pytest.mark.parametrize("channel", ["plain_server", "exception"])
def test_failed_emission_never_reprints_original_record(mode: str, channel: str) -> None:
    stdout = OutputSink(mode)
    stderr = io.StringIO()
    formatter = FailureFormatter() if mode == "formatter" else None
    with handler_output(stdout, stderr, formatter=formatter):
        logger = logging.getLogger("uvicorn.error")
        if channel == "plain_server":
            logger.error(PRIVATE + " %s", PRIVATE_URL)
        else:
            exc = ValueError(PRIVATE + PRIVATE_URL)
            logger.error(PRIVATE + " %s", PRIVATE_URL, exc_info=(type(exc), exc, None))
    assert_private_absent(stdout.getvalue(), stderr.getvalue())
    assert_fixed_fallback(stderr.getvalue())


@pytest.mark.parametrize("mode", ["write", "flush", "formatter"])
def test_failed_fallback_does_not_escape_or_try_another_logging_path(mode: str) -> None:
    stdout = OutputSink(mode)
    stderr = FailingFallback()
    formatter = FailureFormatter() if mode == "formatter" else None
    with handler_output(stdout, stderr, formatter=formatter):
        logging.getLogger("uvicorn.error").error(PRIVATE)
    assert stderr.writes == 1
    assert_private_absent(stdout.getvalue())


def test_fallback_reentry_is_bounded_at_the_same_handler() -> None:
    stdout = OutputSink("write")
    stderr = ReentrantFallback()
    with handler_output(stdout, stderr):
        logging.getLogger("uvicorn.error").error(PRIVATE)
    assert stdout.writes == stderr.writes == 1
    assert_private_absent(stdout.getvalue(), stderr.getvalue())
    assert_fixed_fallback(stderr.getvalue())


@pytest.mark.parametrize("mode", ["write", "flush", "formatter", "formatter_recursion"])
@pytest.mark.parametrize("broken_fallback", [False, True])
async def test_generic_500_response_survives_owned_logging_failure(
    mode: str, broken_fallback: bool
) -> None:
    request = Request({"type": "http", "method": "GET", "path": "/synthetic", "headers": []})
    request.state.request_id = SUPPORT_ID
    stdout = OutputSink(mode)
    stderr = FailingFallback() if broken_fallback else io.StringIO()
    formatter: logging.Formatter | None = None
    if mode == "formatter":
        formatter = FailureFormatter()
    elif mode == "formatter_recursion":
        # A logger-raised RecursionError, not deliberate process stack exhaustion.
        formatter = FailureFormatter(RecursionError(PRIVATE))
    with handler_output(stdout, stderr, formatter=formatter):
        response = await errors.unhandled_error_handler(
            request, RuntimeError(PRIVATE + PRIVATE_URL)
        )
    assert response.status_code == 500
    assert json.loads(response.body) == {
        "error": {
            "code": "internal_error",
            "message": "İşlem tamamlanamadı. Lütfen daha sonra tekrar deneyin.",
            "request_id": SUPPORT_ID,
        }
    }
    assert_private_absent(stdout.getvalue(), response.body.decode())
    if isinstance(stderr, io.StringIO):
        assert_private_absent(stderr.getvalue())
        assert_fixed_fallback(stderr.getvalue())
    else:
        assert stderr.writes == 1


@pytest.mark.parametrize("kind", [KeyboardInterrupt, SystemExit])
@pytest.mark.parametrize("stage", ["write", "formatter", "fallback"])
def test_process_control_exceptions_are_not_swallowed(
    kind: type[BaseException], stage: str
) -> None:
    signal = kind()
    stdout = OutputSink("write", signal if stage == "write" else None)
    stderr = FailingFallback(signal) if stage == "fallback" else io.StringIO()
    formatter = FailureFormatter(signal) if stage == "formatter" else None
    with handler_output(stdout, stderr, formatter=formatter) as handler:
        with pytest.raises(kind) as caught:
            logging.getLogger("uvicorn.error").error(PRIVATE)
        assert caught.value is signal
        # A caught control signal must not leave the handler's reentry latch set.
        healthy = io.StringIO()
        handler.stream = healthy
        handler.setFormatter(app_logging.JsonFormatter())
        logging.getLogger("uvicorn.error").error("Application startup failed. Exiting.")
        assert (
            json.loads(healthy.getvalue())["context"]["error_code"] == "application_startup_failed"
        )


def test_fallback_does_not_stringify_or_represent_private_objects() -> None:
    calls: list[str] = []

    class Unprintable:
        def __str__(self) -> str:
            calls.append("str")
            raise AssertionError(PRIVATE)

        def __repr__(self) -> str:
            calls.append("repr")
            raise AssertionError(PRIVATE)

    stdout, stderr = OutputSink("write"), io.StringIO()
    with handler_output(stdout, stderr):
        logging.getLogger("uvicorn.error").error(Unprintable(), Unprintable())
    assert calls == []
    assert_fixed_fallback(stderr.getvalue())
    assert_private_absent(stderr.getvalue())


@pytest.mark.parametrize("raise_exceptions", [False, True])
def test_normal_events_and_global_logging_failure_setting_are_preserved(
    raise_exceptions: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(logging, "raiseExceptions", raise_exceptions)
    stdout, stderr = OutputSink("normal"), io.StringIO()
    with handler_output(stdout, stderr):
        server = logging.getLogger("uvicorn.error")
        assert not server.disabled and server.propagate and not server.handlers
        server.info("Application startup complete.")
        server.warning("Invalid HTTP request received.")
        server.error("Application shutdown failed. Exiting.")
        assert logging.raiseExceptions is raise_exceptions
    parsed = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert [record["level"] for record in parsed] == ["INFO", "WARNING", "ERROR"]
    assert parsed[0]["message"] == "Application startup complete."
    assert parsed[1]["message"] == "Invalid HTTP request received."
    assert parsed[2]["context"]["error_code"] == "application_shutdown_failed"
    assert stderr.getvalue() == ""
