"""Merkezi HTTP sınırının route, hata ve header korelasyon testleri."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.api.deps import PrincipalDep
from app.core.config import get_settings

SERVER_REQUEST_ID = re.compile(r"^[a-f0-9]{32}$")
ATTACKER_REQUEST_ID = "c2VjcmV0X2VtYWlsX2NvbnRlbnQ"


class ProbeBody(BaseModel):
    value: int


@pytest.fixture
def observability_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Testte docs açık, gerçek collector kapalı; enqueue spy ile ölçülür."""

    monkeypatch.setenv("API_DOCS_ENABLED", "true")
    monkeypatch.setenv("API_OBSERVABILITY_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _app_with_probe() -> FastAPI:
    from app.main import create_app

    app = create_app()

    @app.get("/probe/{item_id}", include_in_schema=False)
    async def probe(item_id: str) -> dict[str, str]:
        return {"item_id": item_id}

    @app.get("/probe-error", include_in_schema=False)
    async def probe_error() -> None:
        raise RuntimeError("gizli-ham-istisna")

    @app.get("/probe-auth", include_in_schema=False)
    async def probe_auth(principal: PrincipalDep) -> dict[str, str]:
        return {"user_id": str(principal.user_id)}

    @app.post("/probe-body", include_in_schema=False)
    async def probe_body(payload: ProbeBody) -> dict[str, int]:
        return payload.model_dump()

    @app.delete("/probe-empty", status_code=204, include_in_schema=False)
    async def probe_empty() -> None:
        return None

    @app.get("/admin/probe", include_in_schema=False)
    async def admin_probe() -> dict[str, str]:
        return {"status": "ok"}

    return app


class TestRequestBoundary:
    async def test_204_govdesiz_yanit_tarayicida_iptal_gibi_gorunmez(
        self,
        observability_settings: None,
    ) -> None:
        app = _app_with_probe()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/probe-empty")

        assert response.status_code == 204
        assert response.content == b""
        assert "content-type" not in response.headers
        assert "content-length" not in response.headers
        assert SERVER_REQUEST_ID.fullmatch(response.headers["X-Request-ID"])

    async def test_dynamic_path_yerine_route_template_loglanir_ve_kuyruga_verilir(
        self,
        observability_settings: None,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        events: list[dict[str, Any]] = []
        monkeypatch.setattr("app.main.enqueue_request_event", lambda **event: events.append(event))
        app = _app_with_probe()
        raw_identifier = "550e8400-e29b-41d4-a716-446655440000"

        with caplog.at_level(logging.INFO, logger="app.request"):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/probe/{raw_identifier}?prompt=gizli",
                    headers={"X-Request-ID": ATTACKER_REQUEST_ID},
                )

        assert response.status_code == 200
        request_id = response.headers["X-Request-ID"]
        assert SERVER_REQUEST_ID.fullmatch(request_id)
        assert request_id != ATTACKER_REQUEST_ID
        assert events == [
            {
                "request_id": request_id,
                "method": "GET",
                "route_template": "/probe/{item_id}",
                "status_code": 200,
                "outcome_code": None,
                "duration_ms": events[0]["duration_ms"],
            }
        ]
        assert raw_identifier not in str(events)
        assert "gizli" not in str(events)
        record = next(item for item in caplog.records if item.name == "app.request")
        assert record.context["request_id"] == request_id  # type: ignore[attr-defined]
        assert record.context["route"] == "/probe/{item_id}"  # type: ignore[attr-defined]
        assert raw_identifier not in str(record.context)  # type: ignore[attr-defined]
        assert ATTACKER_REQUEST_ID not in str(record.context)  # type: ignore[attr-defined]

    async def test_unhandled_500_header_zarf_log_ve_event_ayni_kodu_tasir(
        self,
        observability_settings: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        events: list[dict[str, Any]] = []
        monkeypatch.setattr("app.main.enqueue_request_event", lambda **event: events.append(event))
        app = _app_with_probe()

        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=True),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/probe-error",
                headers={
                    "X-Request-ID": ATTACKER_REQUEST_ID,
                    "Origin": "http://localhost:3000",
                },
            )

        assert response.status_code == 500
        request_id = response.headers["X-Request-ID"]
        assert SERVER_REQUEST_ID.fullmatch(request_id)
        assert request_id != ATTACKER_REQUEST_ID
        assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
        assert response.json() == {
            "error": {
                "code": "internal_error",
                "message": "İşlem tamamlanamadı. Lütfen daha sonra tekrar deneyin.",
                "request_id": request_id,
            }
        }
        assert events[0]["request_id"] == request_id
        assert events[0]["route_template"] == "/probe-error"
        assert events[0]["status_code"] == 500
        assert events[0]["outcome_code"] == "internal_error"
        assert "gizli-ham-istisna" not in str(events)

    @pytest.mark.parametrize(
        ("method", "path", "payload", "expected_status", "expected_code"),
        [
            ("GET", "/probe-auth", None, 401, "unauthenticated"),
            ("GET", "/missing/secret-value", None, 404, "not_found"),
            ("POST", "/probe/sabit", None, 405, "method_not_allowed"),
            ("POST", "/probe-body", {}, 422, "validation_error"),
        ],
    )
    async def test_error_matrix_header_zarf_ve_event_korelasyonu(
        self,
        observability_settings: None,
        monkeypatch: pytest.MonkeyPatch,
        method: str,
        path: str,
        payload: dict[str, object] | None,
        expected_status: int,
        expected_code: str,
    ) -> None:
        events: list[dict[str, Any]] = []
        monkeypatch.setattr("app.main.enqueue_request_event", lambda **event: events.append(event))
        app = _app_with_probe()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.request(
                method,
                path,
                headers={"X-Request-ID": ATTACKER_REQUEST_ID},
                json=payload,
            )

        assert response.status_code == expected_status
        request_id = response.headers["X-Request-ID"]
        assert SERVER_REQUEST_ID.fullmatch(request_id)
        assert request_id != ATTACKER_REQUEST_ID
        assert response.headers["X-Request-ID"] == request_id
        assert response.json()["error"] == {
            "code": expected_code,
            "message": response.json()["error"]["message"],
            "request_id": request_id,
        }
        assert len(events) == 1
        assert events[0]["request_id"] == request_id
        assert events[0]["status_code"] == expected_status
        assert events[0]["outcome_code"] == expected_code

    async def test_health_admin_ve_options_event_uretmez(
        self,
        observability_settings: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import asyncio

        from app.core import request_observability as observer

        queue: asyncio.Queue[object] = asyncio.Queue()
        monkeypatch.setattr(observer, "_queue", queue)
        monkeypatch.setattr(observer, "_state", observer._ObserverState(status="healthy"))
        monkeypatch.setattr(
            observer,
            "get_settings",
            lambda: SimpleNamespace(
                api_observability_enabled=True,
                environment=SimpleNamespace(value="local"),
                release_revision="exclusion-test",
            ),
        )
        app = _app_with_probe()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            health = await client.get("/health/live")
            unknown_health = await client.get("/health/yok")
            admin = await client.get("/admin/probe")
            unknown_admin = await client.get("/admin/yok")
            docs = await client.get("/docs")
            docs_redirect = await client.get("/docs/oauth2-redirect")
            redoc = await client.get("/redoc")
            contract = await client.get("/openapi.json")
            options = await client.options("/probe/sabit")

        assert health.status_code == 200
        assert unknown_health.status_code == 404
        assert admin.status_code == 200
        assert unknown_admin.status_code == 404
        assert docs.status_code == 200
        assert docs_redirect.status_code == 200
        assert redoc.status_code == 404
        assert contract.status_code == 200
        assert options.status_code in {200, 405}
        assert queue.empty()

    async def test_docs_csp_yalniz_yerel_etkilesimli_yuzeye_izin_verir(
        self,
        observability_settings: None,
    ) -> None:
        app = _app_with_probe()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            docs = await client.get("/docs")
            redoc = await client.get("/redoc")
            api = await client.get("/probe/sabit")

        assert docs.status_code == 200
        assert redoc.status_code == 404
        assert "https://cdn.jsdelivr.net" in docs.headers["Content-Security-Policy"]
        assert "script-src 'unsafe-inline'" in docs.headers["Content-Security-Policy"]
        assert api.headers["Content-Security-Policy"] == (
            "default-src 'none'; frame-ancestors 'none'"
        )
        assert redoc.headers["Content-Security-Policy"] == (
            "default-src 'none'; frame-ancestors 'none'"
        )
