"""Gerçek ASGI isteklerinin yayımlanan JSON günlüklerinde ham yol bulunmamalı."""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from httpx import ASGITransport, AsyncClient
from uvicorn import Config
from uvicorn.protocols.utils import get_path_with_query_string

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError, StorageUnavailableError
from app.core.logging import configure_logging

COURSE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
DOCUMENT_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
PATH_CANARY = "SYNTHETIC_PRIVATE_PATH_CANARY"
QUERY_CANARY = "SYNTHETIC_PRIVATE_QUERY_CANARY"
HEADER_CANARY = "SYNTHETIC_PRIVATE_HEADER_CANARY"
REQUEST_ID = "synthetic-support-id"
CANARIES = (COURSE_ID, DOCUMENT_ID, PATH_CANARY, QUERY_CANARY, HEADER_CANARY)


@contextmanager
def _emitted_logs(
    level: int = logging.INFO, *, server_logging: bool = False
) -> Iterator[io.StringIO]:
    """Üretim biçimleyici ve filtreyi çalıştır; tüm logger durumunu geri yükle."""
    names = (
        "",
        "app.request",
        "httpx",
        "httpcore",
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "uvicorn.asgi",
    )
    state = {
        name: (
            logging.getLogger(name).level,
            logging.getLogger(name).handlers[:],
            logging.getLogger(name).propagate,
            logging.getLogger(name).disabled,
        )
        for name in names
    }
    sink = io.StringIO()
    try:
        with redirect_stdout(sink):
            if server_logging:
                # Gerçek Config logger'ları kurar; app yüklemez/sunucu açmaz.
                # Üretimde de uygulamanın lifespan kurulumu bu adımdan sonradır.
                Config("app.main:app", access_log=True, log_level="debug")
            configure_logging(level)
            logging.getLogger("app.request").setLevel(logging.INFO)
            yield sink
    finally:
        for name, (level, handlers, propagate, disabled) in state.items():
            logger = logging.getLogger(name)
            logger.setLevel(level)
            logger.handlers[:] = handlers
            logger.propagate = propagate
            logger.disabled = disabled


@pytest.fixture
def logging_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FastAPI:
    """Yaşam döngüsü/DB/sağlayıcı çalıştırmadan gerçek uygulama ve yönlendirici."""
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
        max_upload_bytes=1024,
        cors_origins=["http://localhost:3000"],
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    app = main.create_app()
    app.dependency_overrides[get_settings] = lambda: settings

    @app.get("/__log_probe/items/{item_id}")
    async def item(item_id: UUID) -> dict[str, str]:
        return {"item_id": str(item_id)}

    @app.get("/__log_probe/items/{item_id}/children/{child_id}")
    async def child_item(item_id: UUID, child_id: UUID) -> dict[str, str]:
        return {"item_id": str(item_id), "child_id": str(child_id)}

    @app.get("/__log_probe/missing/{item_id}")
    async def missing(item_id: UUID) -> None:
        raise NotFoundError("Sentetik kayıt bulunamadı.")

    @app.get("/__log_probe/unavailable/{item_id}")
    async def unavailable(item_id: UUID) -> None:
        raise StorageUnavailableError("Sentetik hizmet kullanılamıyor.")

    @app.get("/__log_probe/crash/{item_id}")
    async def crash(item_id: UUID) -> None:
        raise RuntimeError("sentetik sabit hata")

    static = tmp_path / "public"
    static.mkdir()
    (static / PATH_CANARY).write_text("sentetik herkese açık dosya", encoding="utf-8")
    app.mount("/__log_probe/static", StaticFiles(directory=static))

    mounted_app = FastAPI()

    @mounted_app.get("/items/{item_id}")
    async def mounted_item(item_id: UUID) -> dict[str, str]:
        return {"item_id": str(item_id)}

    app.mount("/__log_probe/tenant/{tenant_id}", mounted_app)
    return app


def _request_record(sink: io.StringIO) -> dict[str, Any]:
    output = sink.getvalue()
    for canary in CANARIES:
        assert canary not in output, f"Özel canary JSON günlüğüne taşındı: {canary}"
    records = [json.loads(line) for line in output.splitlines()]
    completed = [
        record
        for record in records
        if record["logger"] == "app.request" and record["message"] == "istek tamamlandı"
    ]
    assert len(completed) == 1
    context = completed[0]["context"]
    assert set(context) == {"request_id", "method", "path", "status", "duration_ms"}
    assert context["request_id"] == REQUEST_ID
    assert isinstance(context["duration_ms"], (int, float)) and context["duration_ms"] >= 0
    return context


@pytest.mark.parametrize(
    ("method", "path", "status", "template", "error_code"),
    [
        (
            "GET",
            f"/courses/{COURSE_ID}/documents/{DOCUMENT_ID}",
            401,
            "/courses/{course_id}/documents/{document_id}",
            "unauthenticated",
        ),
        (
            "PUT",
            f"/courses/{COURSE_ID}/documents/{DOCUMENT_ID}",
            405,
            "/courses/{course_id}/documents/{document_id}",
            None,
        ),
        (
            "GET",
            f"/__log_probe/items/{COURSE_ID}",
            200,
            "/__log_probe/items/{item_id}",
            None,
        ),
        (
            "GET",
            f"/__log_probe/items/{COURSE_ID}/children/{DOCUMENT_ID}",
            200,
            "/__log_probe/items/{item_id}/children/{child_id}",
            None,
        ),
        (
            "GET",
            f"/__log_probe/missing/{COURSE_ID}",
            404,
            "/__log_probe/missing/{item_id}",
            "not_found",
        ),
        (
            "GET",
            f"/__log_probe/unavailable/{COURSE_ID}",
            503,
            "/__log_probe/unavailable/{item_id}",
            "storage_unavailable",
        ),
        (
            "GET",
            f"/__log_probe/items/{PATH_CANARY}",
            422,
            "/__log_probe/items/{item_id}",
            "validation_error",
        ),
    ],
)
async def test_matched_route_logs_template_preserving_response_contract(
    logging_app: FastAPI,
    method: str,
    path: str,
    status: int,
    template: str,
    error_code: str | None,
) -> None:
    with _emitted_logs() as sink:
        async with AsyncClient(
            transport=ASGITransport(app=logging_app), base_url="http://test"
        ) as client:
            response = await client.request(
                method,
                path,
                params={"private": QUERY_CANARY},
                headers={"X-Request-ID": REQUEST_ID, "X-Synthetic-Private": HEADER_CANARY},
            )
    assert response.status_code == status
    assert response.headers["X-Request-ID"] == REQUEST_ID
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    if error_code:
        assert response.json()["error"]["code"] == error_code
        assert response.json()["error"]["request_id"] == REQUEST_ID
    if status == 200:
        assert response.json()["item_id"] == COURSE_ID
        if "children" in path:
            assert response.json()["child_id"] == DOCUMENT_ID
    if status == 405:
        assert "GET" in response.headers["Allow"]
    record = _request_record(sink)
    assert record["path"] == template
    assert record["status"] == status
    assert record["method"] == method


@pytest.mark.parametrize(
    ("path", "status"),
    [
        (f"/not-a-route/{PATH_CANARY}/{COURSE_ID}", 404),
        (f"/not-a-route/{PATH_CANARY}%2F{DOCUMENT_ID}", 404),
        (f"/not-a-route/{PATH_CANARY}%0A{DOCUMENT_ID}", 404),
        (f"/__log_probe/items/{COURSE_ID}/", 307),
        (f"/__log_probe/static/{PATH_CANARY}", 200),
        (f"/__log_probe/static/missing-{PATH_CANARY}", 404),
        (f"/__log_probe/tenant/{PATH_CANARY}/missing/{DOCUMENT_ID}", 404),
    ],
)
async def test_unmatched_redirect_and_static_paths_have_no_raw_fallback(
    logging_app: FastAPI, path: str, status: int
) -> None:
    with _emitted_logs() as sink:
        async with AsyncClient(
            transport=ASGITransport(app=logging_app), base_url="http://test"
        ) as client:
            response = await client.get(
                path, params={"private": QUERY_CANARY}, headers={"X-Request-ID": REQUEST_ID}
            )
    assert response.status_code == status
    assert response.headers["X-Request-ID"] == REQUEST_ID
    if status == 307:
        assert COURSE_ID in response.headers["Location"]
    if status == 200:
        assert response.text == "sentetik herkese açık dosya"
    record = _request_record(sink)
    assert record["path"] == "<unmatched>"
    assert record["status"] == status


async def test_mounted_api_uses_inner_template_without_concrete_mount_path(
    logging_app: FastAPI,
) -> None:
    with _emitted_logs() as sink:
        async with AsyncClient(
            transport=ASGITransport(app=logging_app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/__log_probe/tenant/{PATH_CANARY}/items/{DOCUMENT_ID}",
                headers={"X-Request-ID": REQUEST_ID},
            )
    assert response.status_code == 200
    assert response.json() == {"item_id": DOCUMENT_ID}
    assert _request_record(sink)["path"] == "/items/{item_id}"


async def test_proxy_root_path_does_not_enter_matched_template(logging_app: FastAPI) -> None:
    with _emitted_logs() as sink:
        async with AsyncClient(
            transport=ASGITransport(app=logging_app, root_path=f"/proxy/{PATH_CANARY}"),
            base_url="http://test",
        ) as client:
            response = await client.get(
                f"/proxy/{PATH_CANARY}/__log_probe/items/{COURSE_ID}",
                headers={"X-Request-ID": REQUEST_ID},
            )
    assert response.status_code == 200
    assert _request_record(sink)["path"] == "/__log_probe/items/{item_id}"


@pytest.mark.parametrize("early_response", ["body_limit", "cors"])
async def test_early_middleware_response_uses_constant_without_route(
    logging_app: FastAPI, early_response: str
) -> None:
    headers = {"X-Request-ID": REQUEST_ID, "Origin": "http://localhost:3000"}
    if early_response == "body_limit":
        method = "POST"
        headers["Content-Length"] = "999999999"
        path = f"/courses/{COURSE_ID}/documents"
        status = 413
    else:
        method = "OPTIONS"
        headers["Access-Control-Request-Method"] = "GET"
        path = f"/not-a-route/{PATH_CANARY}"
        status = 200
    with _emitted_logs() as sink:
        async with AsyncClient(
            transport=ASGITransport(app=logging_app), base_url="http://test"
        ) as client:
            response = await client.request(method, path, headers=headers)
    assert response.status_code == status
    assert response.headers["X-Request-ID"] == REQUEST_ID
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
    if status == 413:
        assert response.json()["error"]["request_id"] == REQUEST_ID
    record = _request_record(sink)
    assert record["path"] == "<unmatched>"
    assert record["status"] == status
    assert record["method"] == method


async def test_unhandled_error_keeps_existing_error_envelope_without_completion_log(
    logging_app: FastAPI,
) -> None:
    """call_next hatasında tamamlandı kaydı yoktur; bu değişiklik yeni kayıt eklemez."""
    with _emitted_logs() as sink:
        async with AsyncClient(
            transport=ASGITransport(app=logging_app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            response = await client.get(
                f"/__log_probe/crash/{COURSE_ID}", headers={"X-Request-ID": REQUEST_ID}
            )
    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "internal_error",
        "message": "İşlem tamamlanamadı. Lütfen daha sonra tekrar deneyin.",
        "request_id": REQUEST_ID,
    }
    output = sink.getvalue()
    for canary in CANARIES:
        assert canary not in output
    records = [json.loads(line) for line in output.splitlines()]
    assert not any(record["message"] == "istek tamamlandı" for record in records)
    assert any(record["logger"] == "app.error" for record in records)


@pytest.mark.parametrize("level", [logging.INFO, logging.DEBUG])
async def test_uvicorn_access_suppressed_after_server_setup_but_errors_and_routes_remain(
    logging_app: FastAPI, level: int
) -> None:
    """Gerçek biçimleyiciye URL/query verilse de erişim kanalı çıktı üretmemeli."""
    path = f"/courses/{COURSE_ID}/documents/{DOCUMENT_ID}"
    with _emitted_logs(level, server_logging=True) as sink:
        async with AsyncClient(
            transport=ASGITransport(app=logging_app), base_url="http://test"
        ) as client:
            response = await client.get(
                path, params={"private": QUERY_CANARY}, headers={"X-Request-ID": REQUEST_ID}
            )
        # Kurulu Uvicorn protokolü de aynı yardımcı ve logger çağrısını kullanır.
        # Burada soket/sunucu yok; gerçek ağ kanalı ayrı süreç testinin konusudur.
        url = get_path_with_query_string(
            {"path": path, "query_string": f"private={QUERY_CANARY}".encode()}
        )
        access = logging.getLogger("uvicorn.access")
        access.setLevel(logging.DEBUG)
        access.info('%s - "%s %s HTTP/%s" %d', "127.0.0.1:1234", "GET", url, "1.1", 401)
        access.debug("sentetik erişim tanısı %s", PATH_CANARY)
        logging.getLogger("uvicorn.error").warning("sentetik sunucu hatası")
    assert response.status_code == 401
    context = _request_record(sink)
    assert context["path"] == "/courses/{course_id}/documents/{document_id}"
    records = [json.loads(line) for line in sink.getvalue().splitlines()]
    assert not any(record["logger"] == "uvicorn.access" for record in records)
    errors = [record for record in records if record["logger"] == "uvicorn.error"]
    assert len(errors) == 1
    assert errors[0]["message"] == "sentetik sunucu hatası"
