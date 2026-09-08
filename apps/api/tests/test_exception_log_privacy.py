"""S9 yayımlanan JSON sınırı; yalnız sentetik içerik, ASGI ve logger çağrıları.

Bu aday hazırlanırken testler çalıştırılmadı. Root, DB'siz runner veya mevcut
fixture protokolü ile eski/aday kaynakta aynı oracle'ları yürütecek.
"""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from typing import Any

import pytest
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from uvicorn import Config

from app.core import errors
from app.core import logging as app_logging
from app.core.config import Settings, get_settings

TEXT = "SENTETIK_OGRENCI_CEVABI_CANARY"
URL = "https://provider.invalid/private-path-canary?token=opaque_secret_canary"
NOTE = "SENTETIK_ISTISNA_NOTU_CANARY"
CAUSE = "SENTETIK_ALT_HATA_CANARY"
SUPPORT_ID = "synthetic-support-09"
CANARIES = (TEXT, URL, NOTE, CAUSE, "opaque_secret_canary", "private-path-canary")


@contextmanager
def emitted(*, server_config: bool = False) -> Iterator[io.StringIO]:
    names = (
        "",
        "app.error",
        "app.exception",
        "app.request",
        "httpx",
        "httpcore",
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "uvicorn.asgi",
        "test.external",
    )
    old = {
        name: (logger.level, logger.handlers[:], logger.propagate, logger.disabled)
        for name in names
        if (logger := logging.getLogger(name)) is not None
    }
    sink = io.StringIO()
    try:
        with redirect_stdout(sink):
            if server_config:
                # Gerçek Uvicorn logger kurulumu; app yükleme/socket/server yok.
                Config("app.main:app", access_log=True, log_level="debug")
            app_logging.configure_logging(logging.DEBUG)
            yield sink
    finally:
        for name, (level, handlers, propagate, disabled) in old.items():
            logger = logging.getLogger(name)
            logger.setLevel(level)
            logger.handlers[:] = handlers
            logger.propagate = propagate
            logger.disabled = disabled


def private_exception(*, group: bool = False) -> Exception:
    try:
        try:
            raise ValueError(CAUSE + " " + URL)
        except ValueError as cause:
            outer = (
                ExceptionGroup(TEXT, [RuntimeError(TEXT), KeyError(URL)])
                if group
                else RuntimeError(TEXT)
            )
            outer.add_note(NOTE)
            raise outer from cause
    except (RuntimeError, ExceptionGroup) as error:
        return error


def no_private_output(sink: io.StringIO) -> list[dict[str, Any]]:
    output = sink.getvalue()
    for value in CANARIES:
        assert value not in output, "Özel sentetik değer yayımlanan günlüğe taşındı."
    records = [json.loads(line) for line in output.splitlines()]
    assert records
    return records


@pytest.mark.parametrize("group", [False, True])
async def test_generic_handler_omits_exception_chain_notes_and_group_content(
    group: bool,
) -> None:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/private-path-canary",
            "headers": [],
        }
    )
    support_id = errors.request_id_of(request)
    exc = private_exception(group=group)
    with emitted() as sink:
        response = await errors.unhandled_error_handler(request, exc)
    record = no_private_output(sink)[0]
    assert record["logger"] == "app.error"
    assert record["level"] == "ERROR"
    assert record["context"] == {
        "error_code": "internal_error",
        "request_id": support_id,
    }
    assert record["exception"]["error_type"] == ("ExceptionGroup" if group else "RuntimeError")
    assert set(record["exception"]) == {"error_type", "frames", "frames_truncated"}
    body = json.loads(response.body)
    assert response.status_code == 500
    assert body == {
        "error": {
            "code": "internal_error",
            "message": "İşlem tamamlanamadı. Lütfen daha sonra tekrar deneyin.",
            "request_id": support_id,
        }
    }


async def test_missing_state_uses_one_support_id_in_log_and_response() -> None:
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    with emitted() as sink:
        response = await errors.unhandled_error_handler(request, private_exception())
    record = no_private_output(sink)[0]
    support_id = json.loads(response.body)["error"]["request_id"]
    assert support_id and record["context"]["request_id"] == support_id


@pytest.mark.parametrize(
    "channel", ["message", "args", "exception_arg", "extra", "context", "cached_trace"]
)
def test_exception_record_cannot_reinsert_private_data_through_other_fields(
    channel: str,
) -> None:
    exc = private_exception()
    message, args, extra = "beklenmeyen hata", (), {}
    if channel == "message":
        message = TEXT
    elif channel == "args":
        message, args = "ayrıntı: %s", (TEXT,)
    elif channel == "exception_arg":
        message, args = "ayrıntı: %s", (exc,)
    elif channel == "extra":
        extra = {"private_payload": {"body": TEXT, "url": URL}}
    elif channel == "context":
        extra = {"context": {"answer": TEXT, "error_code": URL}}
    else:
        extra = {"private_payload": NOTE}
    record = logging.getLogger("app.error").makeRecord(
        "app.error",
        logging.ERROR,
        __file__,
        1,
        message,
        args,
        (type(exc), exc, exc.__traceback__),
        extra=extra,
    )
    if channel == "cached_trace":
        record.exc_text, record.stack_info = TEXT, URL
    with emitted() as sink:
        logging.getLogger("app.error").handle(record)
    parsed = no_private_output(sink)[0]
    assert set(parsed) == {"ts", "level", "logger", "message", "context", "exception"}
    assert set(parsed["context"]) == {"error_code"}


def test_exception_object_stringification_is_not_needed() -> None:
    class Unprintable(Exception):
        def __str__(self) -> str:
            raise AssertionError("İstisna metni biçimlendirilmemeli.")

    error = Unprintable(TEXT)
    with emitted() as sink:
        logging.getLogger("test.external").error(error, exc_info=(type(error), error, None))
    record = no_private_output(sink)[0]
    assert record["logger"] == "app.exception"
    assert record["message"] == "istisna kaydedildi"
    assert record["exception"]["error_type"] == "Exception"


def test_formatter_without_filter_does_not_format_exception_text() -> None:
    exc = private_exception()
    record = logging.LogRecord(
        "app.error",
        logging.ERROR,
        __file__,
        1,
        TEXT,
        (exc,),
        (type(exc), exc, exc.__traceback__),
    )
    record.private_value = URL
    serialized = app_logging.JsonFormatter().format(record)
    for value in CANARIES:
        assert value not in serialized
    assert json.loads(serialized)["context"]["error_code"] == "exception_recorded"


def test_unknown_exception_type_name_is_not_a_free_text_channel() -> None:
    error_class = type(TEXT, (Exception,), {})
    exc = error_class(URL)
    with emitted() as sink:
        logging.getLogger("app.error").error("beklenmeyen hata", exc_info=(type(exc), exc, None))
    record = no_private_output(sink)[0]
    assert record["exception"]["error_type"] == "Exception"


def test_frame_metadata_uses_only_known_relative_path_function_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = (tmp_path / "app").resolve()
    source = root / "core" / "synthetic.py"
    source.parent.mkdir(parents=True)
    source.write_text('def sentinel():\n    raise RuntimeError("' + TEXT + '")\n')
    monkeypatch.setattr(app_logging, "_APP_ROOT", root, raising=False)
    namespace = {}
    # Gerçek dosya adı/satırı; kaynak satırının kendisi özel sentetik değer taşıyor.
    exec(compile(source.read_text(), str(source), "exec"), namespace)  # noqa: S102
    with emitted() as sink:
        try:
            namespace["sentinel"]()
        except RuntimeError:
            logging.getLogger("app.error").exception("beklenmeyen hata")
    record = no_private_output(sink)[0]
    assert str(tmp_path) not in sink.getvalue()
    assert record["exception"]["frames"] == [
        {"path": "core/synthetic.py", "function": "sentinel", "line": 2}
    ]


@pytest.mark.parametrize("forged", ["outside_path", "unknown_function"])
def test_forged_private_frame_metadata_is_omitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, forged: str
) -> None:
    root = (tmp_path / "app").resolve()
    source = root / "core" / "synthetic.py"
    source.parent.mkdir(parents=True)
    source.write_text('def sentinel():\n    raise RuntimeError("' + TEXT + '")\n')
    monkeypatch.setattr(app_logging, "_APP_ROOT", root, raising=False)
    namespace = {}
    filename = str(source) if forged == "unknown_function" else str(tmp_path / (NOTE + ".py"))
    exec(compile(source.read_text(), filename, "exec"), namespace)  # noqa: S102
    function = namespace["sentinel"]
    if forged == "unknown_function":
        function.__code__ = function.__code__.replace(co_name=NOTE)
    with emitted() as sink:
        try:
            function()
        except RuntimeError:
            logging.getLogger("app.error").exception("beklenmeyen hata")
    record = no_private_output(sink)[0]
    assert record["exception"]["frames"] == []


def test_traceback_scan_and_application_frames_are_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = (tmp_path / "app").resolve()
    source = root / "core" / "recursive.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        'def recurse(n):\n    if n:\n        return recurse(n-1)\n    raise RuntimeError("'
        + TEXT
        + '")\n'
    )
    monkeypatch.setattr(app_logging, "_APP_ROOT", root, raising=False)
    namespace = {}
    exec(compile(source.read_text(), str(source), "exec"), namespace)  # noqa: S102
    with emitted() as sink:
        try:
            namespace["recurse"](100)
        except RuntimeError:
            logging.getLogger("app.error").exception("beklenmeyen hata")
    record = no_private_output(sink)[0]
    assert len(record["exception"]["frames"]) == 8
    assert record["exception"]["frames_truncated"] is True


def test_uvicorn_exception_channel_reaches_only_project_json_handler() -> None:
    with emitted(server_config=True) as sink:
        server = logging.getLogger("uvicorn.error")
        assert server.handlers == [] and server.propagate
        assert logging.getLogger("uvicorn").handlers == []
        assert logging.getLogger("uvicorn").propagate
        assert len(logging.getLogger().handlers) == 1
        assert isinstance(logging.getLogger().handlers[0].formatter, app_logging.JsonFormatter)
        server.info("Application startup complete.")
        server.error("Exception in ASGI application\n", exc_info=private_exception())
    records = no_private_output(sink)
    assert len(records) == 2
    assert records[0]["message"] == "Application startup complete."
    assert records[1]["logger"] == "uvicorn.error"
    assert records[1]["context"]["error_code"] == "asgi_application_error"
    assert records[1]["exception"]["error_type"] == "RuntimeError"


async def test_actual_main_500_and_outer_asgi_rethrow_both_use_safe_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main

    settings = Settings(
        _env_file=None,
        environment="local",
        dev_auth_enabled=True,
        llm_fake_provider=True,
        embedding_provider="hashing",
        groq_api_key="",
        gemini_api_key="",
        openai_api_key="",
        eval_runtime_enabled=False,
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    app = main.create_app()
    app.dependency_overrides[get_settings] = lambda: settings

    @app.post("/__s9_private_probe")
    async def private_endpoint(request: Request) -> None:
        body = await request.body()
        try:
            raise ValueError(request.url.query + " " + request.headers.get("Authorization", ""))
        except ValueError as cause:
            error = RuntimeError(body.decode())
            error.add_note(NOTE)
            raise error from cause

    class ServerBoundary:
        # Gerçek Uvicorn ağ döngüsü değildir; Starlette'in gerçek yeniden-yükseltmesini
        # aynı sabit server logger çağrısıyla gözler. Gerçek server kanıtı root'ta ayrıdır.
        def __init__(self):
            self.errors = 0

        async def __call__(self, scope, receive, send):
            try:
                await app(scope, receive, send)
            except BaseException as exc:
                self.errors += 1
                logging.getLogger("uvicorn.error").error(
                    "Exception in ASGI application\n", exc_info=exc
                )

    boundary = ServerBoundary()
    with emitted(server_config=True) as sink:
        async with AsyncClient(
            transport=ASGITransport(app=boundary), base_url="http://test"
        ) as client:
            response = await client.post(
                "/__s9_private_probe?token=opaque_secret_canary",
                content=TEXT,
                headers={"X-Request-ID": SUPPORT_ID, "Authorization": URL},
            )
    records = no_private_output(sink)
    assert boundary.errors == 1, "Gerçek Starlette 500 sonrası yeniden yükseltmesi gözlenmedi."
    assert response.status_code == 500
    support_id = response.json()["error"]["request_id"]
    assert support_id and support_id != SUPPORT_ID
    assert SUPPORT_ID not in sink.getvalue()
    assert response.json()["error"] == {
        "code": "internal_error",
        "message": "İşlem tamamlanamadı. Lütfen daha sonra tekrar deneyin.",
        "request_id": support_id,
    }
    app_errors = [record for record in records if record["logger"] == "app.error"]
    server_errors = [record for record in records if record["logger"] == "uvicorn.error"]
    assert len(app_errors) == len(server_errors) == 1
    assert app_errors[0]["context"]["request_id"] == support_id
    assert not any(record["message"] == "istek tamamlandı" for record in records)
