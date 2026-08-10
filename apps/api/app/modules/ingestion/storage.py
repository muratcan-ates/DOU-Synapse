"""Belge deposu.

Arayüz bilinçli olarak dardır (yaz/oku/sil): böylece yerel dosya sistemi ile Supabase
Storage arasında geçiş, çağıran kodu değiştirmeden yapılabilir. Çevrimdışı demo yerel
depoyla çalışır (ARCHITECTURE.md §6, C planı).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

import httpx

from app.core.errors import NotFoundError, StorageUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)


class DocumentStorage(Protocol):
    async def save(self, key: str, content: bytes) -> None: ...

    async def load(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...


class LocalFileStorage:
    """Yerel disk deposu.

    `key` her zaman sunucu tarafında üretilir (bkz. validation.validate_upload); yine de
    kök dizin dışına çıkan bir anahtarın diske dokunmaması için burada ikinci kez
    doğrulanır — depoya güvenmeyen bir çağıran olsa bile dizin geçişi engellenir.
    """

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        target = (self._root / key).resolve()
        if not target.is_relative_to(self._root):
            raise ValueError(f"Depo kökü dışında anahtar: {key!r}")
        return target

    async def save(self, key: str, content: bytes) -> None:
        path = self._resolve(key)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

        await asyncio.to_thread(_write)

    async def load(self, key: str) -> bytes:
        path = self._resolve(key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError as exc:
            raise NotFoundError("Belge dosyası bulunamadı.") from exc

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        await asyncio.to_thread(path.unlink, True)


class SupabaseStorage:
    """Supabase Storage'ın özel bucket'ına sunucu taraflı adaptör.

    Service-role anahtarı yalnız API/worker sürecinde yaşar. Nesne yolları
    sunucu tarafından UUID ile üretildiği hâlde URL birleştirmeden önce ayrıca
    kodlanır. Yükleme ``upsert=false`` kullanır; beklenmedik bir anahtar
    çakışması var olan materyalin sessizce üstüne yazamaz.
    """

    def __init__(
        self,
        *,
        project_url: str,
        service_role_key: str,
        bucket: str,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = project_url.rstrip("/") + "/storage/v1"
        self._service_role_key = service_role_key
        self._bucket = bucket
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self._service_role_key,
            "authorization": f"Bearer {self._service_role_key}",
        }

    def _object_url(self, key: str | None = None) -> str:
        bucket = quote(self._bucket, safe="")
        base = f"{self._base_url}/object/{bucket}"
        return f"{base}/{quote(key, safe='/')}" if key is not None else base

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self._timeout_seconds,
            transport=self._transport,
            follow_redirects=False,
        )

    async def save(self, key: str, content: bytes) -> None:
        headers = {
            **self._headers,
            "content-type": "application/octet-stream",
            "x-upsert": "false",
        }
        try:
            async with self._client() as client:
                response = await client.post(
                    self._object_url(key), headers=headers, content=content
                )
            response.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.exception("Supabase Storage yazma hatası", exc_info=exc)
            raise StorageUnavailableError(
                "Belge deposuna şu anda erişilemiyor. Lütfen yeniden deneyin."
            ) from exc

    async def load(self, key: str) -> bytes:
        try:
            async with self._client() as client:
                response = await client.get(self._object_url(key), headers=self._headers)
            if response.status_code == 404:
                raise NotFoundError("Belge dosyası bulunamadı.")
            response.raise_for_status()
            return response.content
        except NotFoundError:
            raise
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.exception("Supabase Storage okuma hatası", exc_info=exc)
            raise StorageUnavailableError(
                "Belge deposuna şu anda erişilemiyor. Lütfen yeniden deneyin."
            ) from exc

    async def delete(self, key: str) -> None:
        try:
            async with self._client() as client:
                response = await client.request(
                    "DELETE",
                    self._object_url(),
                    headers={**self._headers, "content-type": "application/json"},
                    json={"prefixes": [key]},
                )
            # Yerel adaptör gibi silmeyi idempotent tut: olmayan nesne zaten
            # istenen son durumdadır.
            if response.status_code == 404:
                return
            response.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.exception("Supabase Storage silme hatası", exc_info=exc)
            raise StorageUnavailableError(
                "Belge deposuna şu anda erişilemiyor. Lütfen yeniden deneyin."
            ) from exc


_storage: DocumentStorage | None = None


def get_storage() -> DocumentStorage:
    global _storage
    if _storage is None:
        from app.core.config import get_settings

        settings = get_settings()
        if settings.storage_backend == "supabase":
            # Settings doğrulayıcısı bu iki değerin varlığını zorlar. Assert'ler
            # type checker'a aynı invarianti taşır; çalışma zamanı kaçış kapısı
            # değildir.
            assert settings.supabase_url is not None
            assert settings.supabase_service_role_key is not None
            _storage = SupabaseStorage(
                project_url=settings.supabase_url,
                service_role_key=settings.supabase_service_role_key,
                bucket=settings.supabase_storage_bucket,
                timeout_seconds=settings.storage_timeout_seconds,
            )
        else:
            _storage = LocalFileStorage(Path(settings.storage_root))
    return _storage


def set_storage(storage: DocumentStorage | None) -> None:
    """Testlerin depoyu değiştirebilmesi için."""
    global _storage
    _storage = storage
