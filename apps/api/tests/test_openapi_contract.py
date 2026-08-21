"""Etkileşimli OpenAPI ve çalışma zamanı hata sözleşmesinin tek kaynak testi."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import (
    ErrorEnvelope,
    error_response,
    starlette_http_exception_handler,
    unhandled_error_handler,
)
from app.core.openapi import configure_openapi

HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
ERROR_REF = "#/components/schemas/ErrorEnvelope"
TRACKED_OPENAPI = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "001-course-assistant-mvp"
    / "contracts"
    / "openapi.json"
)


@pytest.fixture
def contract_app() -> FastAPI:
    from app.main import create_app

    return create_app()


@pytest.fixture
def schema(contract_app: FastAPI) -> dict[str, Any]:
    # Gerçek uygulama fabrikasının yayınladığı sözleşmeyi sınar; main bağlantısı
    # unutulursa burada doğrudan kırılmalıdır. Tekrarlı çağrı ayrı testtedir.
    return contract_app.openapi()


def operations(schema: dict[str, Any]) -> Iterator[tuple[str, str, dict[str, Any]]]:
    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            if method.lower() in HTTP_METHODS:
                yield path, method.lower(), operation


def assert_error_response(response: dict[str, Any]) -> None:
    assert response["content"]["application/json"]["schema"] == {"$ref": ERROR_REF}


def assert_runtime_envelope(body: dict[str, Any], *, code: str, message: str) -> None:
    assert body.keys() == {"error"}
    assert body["error"].keys() == {"code", "message", "request_id"}
    assert body["error"]["code"] == code
    assert body["error"]["message"] == message
    assert body["error"]["request_id"]


class TestOpenAPIKimlikSozlesmesi:
    def test_tracked_openapi_canli_sozlesmeyle_birebirdir(self, schema: dict[str, Any]) -> None:
        assert json.loads(TRACKED_OPENAPI.read_text(encoding="utf-8")) == schema

    def test_bearer_auth_gercek_guvenlik_semasidir(self, schema: dict[str, Any]) -> None:
        assert schema["components"]["securitySchemes"] == {
            "BearerAuth": {"type": "http", "scheme": "bearer"}
        }

        public = {("/health/live", "get"), ("/health/ready", "get")}
        seen_public: set[tuple[str, str]] = set()
        for path, method, operation in operations(schema):
            if (path, method) in public:
                assert not operation.get("security")
                seen_public.add((path, method))
            else:
                assert operation.get("security") == [{"BearerAuth": []}], (
                    f"korunan operation bearer şeması taşımıyor: {method.upper()} {path}"
                )
        assert seen_public == public

    @pytest.mark.parametrize("authorization", [None, "Basic dXNlcjpwYXNz"])
    async def test_runtime_401_turkce_zarfi_korur(
        self, contract_app: FastAPI, authorization: str | None
    ) -> None:
        transport = ASGITransport(app=contract_app)
        headers = {} if authorization is None else {"Authorization": authorization}
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/me/profile", headers=headers)

        assert response.status_code == 401
        assert_runtime_envelope(
            response.json(),
            code="unauthenticated",
            message="Bu işlem için giriş yapmanız gerekiyor.",
        )


class TestOpenAPIHataSozlesmesi:
    def test_error_envelope_runtime_modeliyle_birebirdir(self, schema: dict[str, Any]) -> None:
        expected = ErrorEnvelope.model_json_schema(
            mode="serialization",
            ref_template="#/components/schemas/{model}",
        )
        definitions = expected.pop("$defs", {})

        assert schema["components"]["schemas"]["ErrorEnvelope"] == expected
        for name, definition in definitions.items():
            assert schema["components"]["schemas"][name] == definition

    def test_401_403_404_405_422_500_tek_error_envelope_refini_kullanir(
        self, schema: dict[str, Any]
    ) -> None:
        for _path, _method, operation in operations(schema):
            responses = operation["responses"]
            assert_error_response(responses["404"])
            assert_error_response(responses["405"])
            assert_error_response(responses["500"])
            if operation.get("security"):
                assert_error_response(responses["401"])
                assert_error_response(responses["403"])
            if "422" in responses:
                assert_error_response(responses["422"])

        serialized = str(schema)
        assert "HTTPValidationError" not in serialized
        assert "#/components/schemas/ValidationError" not in serialized
        assert all(value != {} for value in schema["components"]["schemas"].values())

    def test_openapi_ozellestirmesi_idempotent_ve_cache_guvenlidir(
        self, contract_app: FastAPI
    ) -> None:
        configure_openapi(contract_app)
        first = contract_app.openapi()
        configure_openapi(contract_app)
        second = contract_app.openapi()

        assert second is first
        assert second["components"]["schemas"]["ErrorEnvelope"]

        contract_app.openapi_schema = None
        rebuilt = contract_app.openapi()
        assert rebuilt is contract_app.openapi_schema
        assert rebuilt["components"]["schemas"]["ErrorEnvelope"]
        assert "HTTPValidationError" not in str(rebuilt)


class TestRuntimeHttpHatalari:
    async def test_router_404_tek_turkce_zarftir(self, contract_app: FastAPI) -> None:
        transport = ASGITransport(app=contract_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/var-olmayan-adres")

        assert response.status_code == 404
        assert_runtime_envelope(
            response.json(),
            code="not_found",
            message="İstenen adres bulunamadı.",
        )

    async def test_router_405_tek_turkce_zarftir_ve_allow_korunur(
        self, contract_app: FastAPI
    ) -> None:
        transport = ASGITransport(app=contract_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/health/live")

        assert response.status_code == 405
        assert "GET" in response.headers["Allow"]
        assert_runtime_envelope(
            response.json(),
            code="method_not_allowed",
            message="Bu işlem bu adres için desteklenmiyor.",
        )

    async def test_http_handler_outcome_code_yazar(self) -> None:
        request = Request({"type": "http", "method": "GET", "path": "/yok", "headers": []})

        response = await starlette_http_exception_handler(request, StarletteHTTPException(404))

        assert response.status_code == 404
        assert request.state.outcome_code == "not_found"

    def test_error_response_outcome_code_yazar(self) -> None:
        request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})

        error_response(request, status_code=409, code="conflict", message="Çakışma.")

        assert request.state.outcome_code == "conflict"

    async def test_unhandled_log_korelasyon_ve_sinif_tasir(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
        request.state.request_id = "a" * 32

        with caplog.at_level(logging.ERROR, logger="app.error"):
            response = await unhandled_error_handler(request, RuntimeError("ham-deger"))

        record = next(record for record in caplog.records if record.name == "app.error")
        assert record.context == {  # type: ignore[attr-defined]
            "request_id": "a" * 32,
            "exception_class": "RuntimeError",
        }
        assert "ham-deger" not in str(record.context)  # type: ignore[attr-defined]
        assert response.status_code == 500
        assert request.state.outcome_code == "internal_error"
