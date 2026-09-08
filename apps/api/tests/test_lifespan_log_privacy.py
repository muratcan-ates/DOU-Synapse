"""S9B gerçek logger/ASGI yaşam döngüsü; soket, DB veya sağlayıcı kullanılmaz.

Aday hazırlanırken pytest çalıştırılmadı. Aynı özel içerik oracle'ı donmuş S9
kaynağına karşı da koşulacak; eski kaynağın kırmızı sonucu ayrıca korunacak.
"""

from __future__ import annotations

import errno
import io
import json
import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager, redirect_stdout
from typing import Any

import pytest
from starlette.applications import Starlette
from uvicorn import Config
from uvicorn.lifespan.on import LifespanOn

from app.core import logging as app_logging

TEXT = "SENTETIK_LIFESPAN_OGRENCI_YANITI_CANARY"
URL = "https://service.invalid/private-canary?opaque=lifespan-secret-canary"
CAUSE = "SENTETIK_LIFESPAN_ALT_HATA_CANARY"
NOTE = "SENTETIK_LIFESPAN_NOT_CANARY"
CANARIES = (TEXT, URL, CAUSE, NOTE, "private-canary", "lifespan-secret-canary")
TIMEOUT_TEMPLATE = "Cancel %s running task(s), timeout graceful shutdown exceeded"


@contextmanager
def emitted(app: Starlette | None = None) -> Iterator[tuple[io.StringIO, Config]]:
    names = ("", "httpx", "httpcore", "uvicorn", "uvicorn.error", "uvicorn.access")
    saved = {
        name: (logger.level, logger.handlers[:], logger.propagate, logger.disabled)
        for name in names
        if (logger := logging.getLogger(name)) is not None
    }
    sink = io.StringIO()
    try:
        with redirect_stdout(sink):
            # Gerçek Uvicorn kurulum sırası; Config.load yalnız verilen ASGI nesnesini yükler.
            config = Config(
                app or Starlette(),
                log_level="debug",
                loop="asyncio",
                http="h11",
                ws="none",
                interface="asgi3",
                lifespan="on",
            )
            app_logging.configure_logging(logging.DEBUG)
            yield sink, config
    finally:
        for name, (level, handlers, propagate, disabled) in saved.items():
            logger = logging.getLogger(name)
            logger.setLevel(level)
            logger.handlers[:] = handlers
            logger.propagate = propagate
            logger.disabled = disabled


def records(sink: io.StringIO) -> list[dict[str, Any]]:
    raw = sink.getvalue()
    for marker in CANARIES:
        assert marker not in raw, "Özel sentetik değer yayımlanan sunucu günlüğüne taşındı."
    parsed = [json.loads(line) for line in raw.splitlines()]
    assert parsed, "Sunucu hata kanalı kapanmamalı."
    return parsed


def private_failure() -> None:
    try:
        raise ValueError(CAUSE + " " + URL)
    except ValueError as cause:
        error = RuntimeError(TEXT)
        error.add_note(NOTE)
        raise error from cause


@pytest.mark.parametrize("phase", ["startup", "shutdown", "normal"])
async def test_real_starlette_lifespan_failure_keeps_phase_without_raw_trace(phase: str) -> None:
    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        if phase == "startup":
            private_failure()
        yield
        if phase == "shutdown":
            private_failure()

    with emitted(Starlette(lifespan=lifespan)) as (sink, config):
        lifecycle = LifespanOn(config)
        await lifecycle.startup()
        if phase != "startup":
            await lifecycle.shutdown()
        parsed = records(sink)
        errors = [r for r in parsed if r["level"] == "ERROR"]
        if phase == "normal":
            assert not errors
            assert not lifecycle.should_exit
            messages = [r["message"] for r in parsed]
            assert "Application startup complete." in messages
            assert "Application shutdown complete." in messages
        else:
            assert lifecycle.should_exit
            assert len(errors) == 2
            assert [r["context"]["error_code"] for r in errors] == [
                "uvicorn_error",
                f"application_{phase}_failed",
            ]
            assert all(set(r) == {"ts", "level", "logger", "message", "context"} for r in errors)
            assert lifecycle.startup_failed == (phase == "startup")
            assert lifecycle.shutdown_failed == (phase == "shutdown")


@pytest.mark.parametrize("phase", ["startup", "shutdown"])
@pytest.mark.parametrize(
    "message", [TEXT, "Arbitrary plain failure: " + URL, json.dumps({"body": TEXT})]
)
async def test_actual_uvicorn_failed_message_is_not_detected_by_traceback_regex(
    phase: str, message: str
) -> None:
    with emitted() as (sink, config):
        lifecycle = LifespanOn(config)
        if phase == "shutdown":
            await lifecycle.send({"type": "lifespan.startup.complete"})
        if phase == "startup":
            await lifecycle.send({"type": "lifespan.startup.failed", "message": message})
            assert lifecycle.startup_failed and lifecycle.startup_event.is_set()
        else:
            await lifecycle.send({"type": "lifespan.shutdown.failed", "message": message})
            assert lifecycle.shutdown_failed and lifecycle.shutdown_event.is_set()
        event = records(sink)[0]
        assert event["context"] == {"error_code": "uvicorn_error"}
        assert event["level"] == "ERROR"


@pytest.mark.parametrize(
    ("template", "code"),
    [
        ("ASGI callable returned without starting response.", "asgi_response_not_started"),
        ("ASGI callable returned without completing response.", "asgi_response_not_completed"),
        ("ASGI callable returned without sending handshake.", "asgi_handshake_not_sent"),
        ("ASGI callable returned without completing handshake.", "asgi_handshake_not_completed"),
        ("ASGI callable should return None, but returned '%s'.", "asgi_invalid_return"),
        ("Error loading ASGI app factory: %s", "asgi_factory_load_failed"),
    ],
)
def test_fixed_protocol_errors_keep_diagnostics_and_drop_private_arguments(
    template: str, code: str
) -> None:
    args = (RuntimeError(TEXT + URL),) if "%s" in template else ()
    with emitted() as (sink, _):
        logging.getLogger("uvicorn.error").error(template, *args)
    event = records(sink)[0]
    assert event["context"] == {"error_code": code}
    assert event["message"] != "sunucu hata kaydı"


@pytest.mark.parametrize("count", [0, 3, 1_000_000, True, -1, 1_000_001, TEXT, {"body": TEXT}])
def test_timeout_keeps_only_a_bounded_integer_task_count(count: object) -> None:
    with emitted() as (sink, _):
        logging.getLogger("uvicorn.error").error(TIMEOUT_TEMPLATE, count)
    event = records(sink)[0]
    expected: dict[str, str | int] = {"error_code": "graceful_shutdown_timeout"}
    if type(count) is int and 0 <= count <= 1_000_000:
        expected["task_count"] = count
    assert event["context"] == expected


@pytest.mark.parametrize("number", [errno.EADDRINUSE, errno.EACCES, None, 99999999, TEXT])
def test_os_error_keeps_only_recognized_errno(number: object) -> None:
    error = OSError(number, TEXT + URL, NOTE)
    with emitted() as (sink, _):
        logging.getLogger("uvicorn.error").error(error)
    event = records(sink)[0]
    expected: dict[str, str | int] = {"error_code": "server_os_error"}
    if type(number) is int and number in errno.errorcode:
        expected.update(errno=number, errno_name=errno.errorcode[number])
    assert event["context"] == expected
    assert event["message"] == "sunucu işletim sistemi hatası"


@pytest.mark.parametrize("level", [logging.ERROR, logging.CRITICAL])
def test_unknown_errors_omit_all_other_free_text_channels(level: int) -> None:
    event = logging.getLogger("uvicorn.error").makeRecord(
        "uvicorn.error",
        level,
        URL,
        1,
        TEXT,
        (),
        None,
        extra={"context": {"body": TEXT}, "private_value": URL},
    )
    event.exc_text, event.stack_info = CAUSE, NOTE
    with emitted() as (sink, _):
        logging.getLogger("uvicorn.error").handle(event)
    parsed = records(sink)[0]
    assert parsed["level"] == logging.getLevelName(level)
    assert set(parsed) == {"ts", "level", "logger", "message", "context"}
    assert parsed["context"] == {"error_code": "uvicorn_error"}


@pytest.mark.parametrize("as_arg", [False, True])
def test_unknown_error_never_stringifies_message_or_argument(as_arg: bool) -> None:
    class Unprintable:
        def __str__(self) -> str:
            raise AssertionError("Serbest nesne biçimlendirilmemeli.")

    with emitted() as (sink, _):
        logger = logging.getLogger("uvicorn.error")
        if as_arg:
            logger.error("private message %s", Unprintable())
        else:
            logger.error(Unprintable())
    assert records(sink)[0]["context"] == {"error_code": "uvicorn_error"}


def test_formatter_alone_does_not_depend_on_redaction_filter() -> None:
    event = logging.LogRecord("uvicorn.error", logging.ERROR, URL, 1, TEXT, (), None)
    event.context = {"body": TEXT}
    event.exc_text, event.stack_info = CAUSE, NOTE
    sink = io.StringIO(app_logging.JsonFormatter().format(event))
    assert records(sink)[0]["context"] == {"error_code": "uvicorn_error"}


def test_real_uvicorn_configuration_keeps_error_channel_and_normal_status_messages() -> None:
    with emitted() as (sink, _):
        error = logging.getLogger("uvicorn.error")
        assert not error.disabled
        assert not error.handlers and error.propagate
        assert not logging.getLogger("uvicorn").handlers
        root_handlers = logging.getLogger().handlers
        assert len(root_handlers) == 1
        assert isinstance(root_handlers[0].formatter, app_logging.JsonFormatter)
        error.info("Application startup complete.")
        error.info("Application shutdown complete.")
        error.warning("Invalid HTTP request received.")
        error.error(TEXT)
    parsed = records(sink)
    assert len(parsed) == 4
    assert [r["message"] for r in parsed[:3]] == [
        "Application startup complete.",
        "Application shutdown complete.",
        "Invalid HTTP request received.",
    ]
    assert parsed[-1]["level"] == "ERROR"


def test_exc_info_retains_the_s9_summary_path() -> None:
    with emitted() as (sink, _):
        try:
            private_failure()
        except RuntimeError as error:
            logging.getLogger("uvicorn.error").error(
                "Exception in ASGI application\n", exc_info=error
            )
    event = records(sink)[0]
    assert event["context"] == {"error_code": "asgi_application_error"}
    assert event["exception"]["error_type"] == "RuntimeError"
