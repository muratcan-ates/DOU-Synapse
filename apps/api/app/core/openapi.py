"""Çalışan API ile yayınlanan OpenAPI hata ve kimlik sözleşmesini eşitler."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from app.core.errors import ErrorEnvelope

_CONFIGURED_MARKER = "_dou_openapi_configured"
_ERROR_REF = {"$ref": "#/components/schemas/ErrorEnvelope"}


def _error_response(description: str) -> dict[str, Any]:
    return {
        "description": description,
        "content": {"application/json": {"schema": dict(_ERROR_REF)}},
    }


def _install_error_schema(schema: dict[str, Any]) -> None:
    components = schema.setdefault("components", {})
    schemas = components.setdefault("schemas", {})

    envelope_schema = ErrorEnvelope.model_json_schema(
        mode="serialization",
        ref_template="#/components/schemas/{model}",
    )
    definitions = envelope_schema.pop("$defs", {})
    schemas.update(definitions)
    schemas["ErrorEnvelope"] = envelope_schema


def _normalize_operations(schema: dict[str, Any]) -> None:
    for path_item in schema.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in {
                "get",
                "put",
                "post",
                "delete",
                "options",
                "head",
                "patch",
                "trace",
            } or not isinstance(operation, dict):
                continue

            responses = operation.setdefault("responses", {})
            if "422" in responses:
                responses["422"] = _error_response("Gönderilen veri geçersiz.")
            if operation.get("security"):
                responses["401"] = _error_response("Kimlik doğrulaması gerekli.")
                responses["403"] = _error_response("Bu işlem için yetkiniz yok.")
            responses["404"] = _error_response("İstenen adres veya kaynak bulunamadı.")
            responses["405"] = _error_response("Bu HTTP metodu bu adreste desteklenmiyor.")
            responses["500"] = _error_response("Beklenmeyen sunucu hatası.")


def _remove_stale_validation_schemas(schema: dict[str, Any]) -> None:
    schemas = schema.get("components", {}).get("schemas", {})
    if not isinstance(schemas, dict):
        return
    # FastAPI'nin varsayılan 422 şeması artık hiçbir operation tarafından
    # kullanılmıyor. Onu bırakmak iki eşzamanlı hata sözleşmesi varmış izlenimi
    # verir; boş bileşenler de aynı nedenle temizlenir.
    schemas.pop("HTTPValidationError", None)
    schemas.pop("ValidationError", None)
    for name, value in list(schemas.items()):
        if value == {}:
            schemas.pop(name)


def _normalize_schema(schema: dict[str, Any]) -> dict[str, Any]:
    _install_error_schema(schema)
    _normalize_operations(schema)
    _remove_stale_validation_schemas(schema)
    return schema


def configure_openapi(app: FastAPI) -> None:
    """FastAPI'nin önbelleğini koruyarak sözleşmeyi bir kez özelleştirir.

    Fonksiyon schema üretilmeden önce veya sonra çağrılabilir. Tekrar çağrı yeni
    wrapper katmanları oluşturmaz; ``app.openapi_schema`` temizlense bile saklanan
    özgün üretici yeni şemayı aynı kurallarla yeniden normalleştirir.
    """

    if getattr(app.state, _CONFIGURED_MARKER, False):
        if app.openapi_schema is not None:
            _normalize_schema(app.openapi_schema)
        return

    original_openapi = app.openapi

    def custom_openapi() -> dict[str, Any]:
        schema = original_openapi()
        app.openapi_schema = _normalize_schema(schema)
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
    setattr(app.state, _CONFIGURED_MARKER, True)
    if app.openapi_schema is not None:
        _normalize_schema(app.openapi_schema)
