"""Sunucu kimliği kökeni ve dar günlük muafiyeti; DB veya ağ gerekmez."""

from __future__ import annotations

import json
import logging
from uuid import UUID

import pytest
from fastapi import Request

from app.core import request_context
from app.core.logging import JsonFormatter, RedactionFilter
from app.core.request_context import ServerRequestId, request_id_of

DIGIT_RUN_UUID = UUID("abcdef12-3456-4abc-8def-12345678901a")


def request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": []})


def test_one_uuid_draw_and_same_exact_object_per_request(monkeypatch: pytest.MonkeyPatch) -> None:
    draws = 0

    def draw() -> UUID:
        nonlocal draws
        draws += 1
        return DIGIT_RUN_UUID

    monkeypatch.setattr(request_context, "uuid4", draw)
    current = request()
    first = request_id_of(current)
    assert type(first) is ServerRequestId
    assert first == DIGIT_RUN_UUID.hex
    assert request_id_of(current) is first is current.state.request_id
    assert draws == 1
    # Bu test kaynağı bilerek sabit UUID döndürür; gerçek entropi testi değildir.
    second = request_id_of(request())
    assert second is not first and draws == 2


@pytest.mark.parametrize("supplied", [DIGIT_RUN_UUID.hex, "Name_Student01234", None, 1])
def test_plain_state_values_never_gain_server_origin(supplied: object) -> None:
    current = request()
    current.state.request_id = supplied
    result = request_id_of(current)
    assert type(result) is ServerRequestId
    assert result != supplied
    assert UUID(result).version == 4
    with pytest.raises(TypeError):
        ServerRequestId("Name_Student01234")  # type: ignore[call-arg]


@pytest.mark.parametrize("logger_name", ["app.request", "app.error"])
@pytest.mark.parametrize("use_filter", [False, True])
def test_only_exact_internal_type_in_direct_context_keeps_digit_run(
    monkeypatch: pytest.MonkeyPatch, logger_name: str, use_filter: bool
) -> None:
    monkeypatch.setattr(request_context, "uuid4", lambda: DIGIT_RUN_UUID)
    support_id = ServerRequestId()
    failure = RuntimeError("sentetik sabit hata")
    record = logging.LogRecord(
        logger_name,
        logging.ERROR if logger_name == "app.error" else logging.INFO,
        __file__,
        1,
        "beklenmeyen hata" if logger_name == "app.error" else "istek tamamlandı",
        (),
        (type(failure), failure, None) if logger_name == "app.error" else None,
    )
    record.context = {"request_id": support_id}
    if use_filter:
        assert RedactionFilter().filter(record)
    output = JsonFormatter().format(record)
    assert json.loads(output)["context"]["request_id"] == DIGIT_RUN_UUID.hex
    assert "[REDACTED_TCKN]" not in output


@pytest.mark.parametrize("logger_name", ["app.request", "app.error", "app.other"])
def test_uuid_shaped_plain_string_has_no_redaction_exemption(logger_name: str) -> None:
    failure = RuntimeError("sentetik sabit hata")
    record = logging.LogRecord(
        logger_name,
        logging.ERROR,
        __file__,
        1,
        "beklenmeyen hata",
        (),
        (type(failure), failure, None) if logger_name == "app.error" else None,
    )
    record.context = {"request_id": DIGIT_RUN_UUID.hex}
    # Filtre atlandığında da context muafiyeti düz metne uygulanmaz.
    output = JsonFormatter().format(record)
    assert DIGIT_RUN_UUID.hex not in output
    assert "[REDACTED_TCKN]" in output


def test_subclass_other_logger_and_other_fields_are_not_exempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(request_context, "uuid4", lambda: DIGIT_RUN_UUID)

    class OtherId(ServerRequestId):
        pass

    untrusted = OtherId()
    current = request()
    current.state.request_id = untrusted
    assert type(request_id_of(current)) is ServerRequestId
    assert current.state.request_id is not untrusted
    for logger_name, context in [
        ("app.request", {"request_id": untrusted}),
        ("app.other", {"request_id": ServerRequestId()}),
        ("app.request", {"other": ServerRequestId(), "nested": {"request_id": ServerRequestId()}}),
    ]:
        record = logging.LogRecord(logger_name, logging.INFO, __file__, 1, "sabit", (), None)
        record.context = context
        assert RedactionFilter().filter(record)
        output = JsonFormatter().format(record)
        assert DIGIT_RUN_UUID.hex not in output
        assert "[REDACTED_TCKN]" in output


@pytest.mark.parametrize("kind", ["plain", "internal", "subclass"])
@pytest.mark.parametrize("use_filter", [False, True])
def test_tuple_values_cannot_bypass_context_or_extra_redaction(
    monkeypatch: pytest.MonkeyPatch, kind: str, use_filter: bool
) -> None:
    """Sıradan JSON dizisine dönüşen tuple, doğrudan alan muafiyeti kazanmaz."""
    monkeypatch.setattr(request_context, "uuid4", lambda: DIGIT_RUN_UUID)

    class OtherId(ServerRequestId):
        pass

    values = {
        "plain": DIGIT_RUN_UUID.hex,
        "internal": ServerRequestId(),
        "subclass": OtherId(),
    }
    value = values[kind]
    for logger_name in ("app.request", "app.error", "app.other"):
        record = logging.LogRecord(logger_name, logging.INFO, __file__, 1, "sabit", (), None)
        record.context = {
            "request_id": (value,),
            "nested": ({"request_id": value}, [("value", value)]),
        }
        record.detail = (value, {"values": [value]})
        if use_filter:
            assert RedactionFilter().filter(record)
        output = JsonFormatter().format(record)
        payload = json.loads(output)
        assert DIGIT_RUN_UUID.hex not in output
        assert "[REDACTED_TCKN]" in payload["context"]["request_id"][0]
        assert "[REDACTED_TCKN]" in payload["context"]["nested"][0]["request_id"]
        assert "[REDACTED_TCKN]" in payload["context"]["nested"][1][0][1]
        assert "[REDACTED_TCKN]" in payload["detail"][0]
        assert "[REDACTED_TCKN]" in payload["detail"][1]["values"][0]
