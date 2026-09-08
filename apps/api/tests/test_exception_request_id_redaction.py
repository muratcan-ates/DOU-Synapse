"""S9: destek kimliğinde önceden var olan bilinen-kalıp maskesi korunur.

Yalnız sentetik değerler kullanılır. Gerçek formatter ve paylaşılan genel500
handler çağrılır; ağ sunucusu, DB, Settings veya sağlayıcı başlatılmaz.
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

SENSITIVE_IDS = [
    pytest.param("1" * 11, "[REDACTED_TCKN]", id="synthetic-eleven-digits"),
    pytest.param("sk-" + "SYNTHETIC" * 3, "[REDACTED_API_KEY]", id="synthetic-key-shape"),
]


@contextmanager
def emitted() -> Iterator[tuple[io.StringIO, io.StringIO]]:
    names = ("", "app.error", "httpx", "httpcore", "uvicorn", "uvicorn.error", "uvicorn.access")
    saved = {
        name: (logger.level, logger.handlers[:], logger.propagate, logger.disabled)
        for name in names
        if (logger := logging.getLogger(name)) is not None
    }
    stdout, stderr = io.StringIO(), io.StringIO()
    handler: logging.Handler | None = None
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            app_logging.configure_logging(logging.INFO)
            handlers = logging.getLogger().handlers
            assert len(handlers) == 1
            handler = handlers[0]
            yield stdout, stderr
    finally:
        for name, (level, handlers, propagate, disabled) in saved.items():
            logger = logging.getLogger(name)
            logger.setLevel(level)
            logger.handlers[:] = handlers
            logger.propagate = propagate
            logger.disabled = disabled
        if handler is not None:
            handler.close()


def assert_masked_log(output: str, request_id: str, expected_mask: str) -> dict[str, Any]:
    assert request_id not in output, "Bilinen hassas destek kimliği günlüğe ham taşındı."
    lines = output.splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["logger"] == "app.error"
    assert record["level"] == "ERROR"
    assert record["message"] == "beklenmeyen hata"
    assert record["context"] == {"error_code": "internal_error", "request_id": expected_mask}
    assert record["exception"]["error_type"] == "RuntimeError"
    return record


@pytest.mark.parametrize(("request_id", "expected_mask"), SENSITIVE_IDS)
def test_formatter_masks_known_sensitive_request_id_without_filter(
    request_id: str, expected_mask: str
) -> None:
    failure = RuntimeError("synthetic request-id regression")
    record = logging.LogRecord(
        "app.error",
        logging.ERROR,
        __file__,
        1,
        "beklenmeyen hata",
        (),
        (type(failure), failure, None),
    )
    record.context = {"request_id": request_id, "error_code": "internal_error"}
    # Filtre kurulmaz: biçimleyicinin kendi izinli alan seçimi maskeyi korumalı.
    output = app_logging.JsonFormatter().format(record)
    assert_masked_log(output, request_id, expected_mask)


@pytest.mark.parametrize(("request_id", "expected_mask"), SENSITIVE_IDS)
async def test_real_unhandled_handler_masks_log_and_preserves_response_support_id(
    request_id: str, expected_mask: str
) -> None:
    request = Request({"type": "http", "method": "GET", "path": "/synthetic", "headers": []})
    request.state.request_id = request_id
    with emitted() as (stdout, stderr):
        response = await errors.unhandled_error_handler(
            request, RuntimeError("synthetic request-id regression")
        )
    assert_masked_log(stdout.getvalue(), request_id, expected_mask)
    assert stderr.getvalue() == "", "Normal tanı yerine günlük arızası işareti kabul edilmez."
    assert response.status_code == 500
    # Bu dar yama HTTP kimliğini değiştirmez; yalnız logdaki bilinen kalıbı maskeler.
    assert json.loads(response.body) == {
        "error": {
            "code": "internal_error",
            "message": "İşlem tamamlanamadı. Lütfen daha sonra tekrar deneyin.",
            "request_id": request_id,
        }
    }
