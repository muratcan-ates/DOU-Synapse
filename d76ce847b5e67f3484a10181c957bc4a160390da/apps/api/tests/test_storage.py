"""Belge depoları: yol güvenliği ve Supabase Storage sözleşmesi."""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import Settings
from app.core.errors import NotFoundError, StorageUnavailableError
from app.modules.ingestion.storage import SupabaseStorage


def _storage(handler: httpx.AsyncBaseTransport) -> SupabaseStorage:
    return SupabaseStorage(
        project_url="https://ornek.supabase.co/",
        service_role_key="yalniz-sunucu-anahtari",
        bucket="ders materyalleri",
        timeout_seconds=2,
        transport=handler,
    )


async def test_supabase_yukleme_uzerine_yazmaz_ve_kimligi_sunucuda_tasir() -> None:
    async def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.raw_path == (
            b"/storage/v1/object/ders%20materyalleri/courses/abc/hafta%203.pdf"
        )
        assert request.headers["authorization"] == "Bearer yalniz-sunucu-anahtari"
        assert request.headers["apikey"] == "yalniz-sunucu-anahtari"
        assert request.headers["x-upsert"] == "false"
        assert await request.aread() == b"pdf-baytlari"
        return httpx.Response(200, json={"Key": "courses/abc/hafta 3.pdf"})

    await _storage(httpx.MockTransport(handle)).save("courses/abc/hafta 3.pdf", b"pdf-baytlari")


async def test_supabase_okuma_baytlari_aynen_dondurur() -> None:
    async def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        return httpx.Response(200, content=b"kaynak")

    result = await _storage(httpx.MockTransport(handle)).load("courses/abc/not.md")
    assert result == b"kaynak"


async def test_supabase_olmayan_nesneyi_alan_hatasiyla_dondurur() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(404))

    with pytest.raises(NotFoundError, match="bulunamadı"):
        await _storage(transport).load("courses/abc/yok.pdf")


async def test_supabase_silme_storage_api_uzerinden_ve_idempotent() -> None:
    async def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.raw_path == b"/storage/v1/object/ders%20materyalleri"
        assert json.loads(await request.aread()) == {"prefixes": ["courses/abc/not.md"]}
        return httpx.Response(200, json=[{"name": "courses/abc/not.md"}])

    await _storage(httpx.MockTransport(handle)).delete("courses/abc/not.md")


@pytest.mark.parametrize("status_code", [400, 500, 503])
async def test_supabase_ham_saglayici_hatasini_kullaniciya_sizdirmaz(status_code: int) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(status_code, text="service-role=GIZLI")
    )

    with pytest.raises(StorageUnavailableError) as error:
        await _storage(transport).save("courses/abc/not.md", b"x")

    assert "GIZLI" not in error.value.message
    assert error.value.code == "storage_unavailable"


def test_supabase_backend_anahtarlari_eksikse_fail_closed() -> None:
    with pytest.raises(ValueError, match="SUPABASE_URL"):
        Settings(dev_auth_enabled=True, storage_backend="supabase")


def test_production_yerel_diski_reddeder() -> None:
    with pytest.raises(ValueError, match="STORAGE_BACKEND=supabase"):
        Settings(
            environment="production",
            supabase_jwt_secret="jwt-secret",
            dev_auth_enabled=False,
            llm_fake_provider=False,
            storage_backend="local",
        )
