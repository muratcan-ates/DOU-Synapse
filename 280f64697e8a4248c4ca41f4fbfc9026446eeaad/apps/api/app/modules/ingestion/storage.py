"""Belge deposu.

Arayüz bilinçli olarak dardır (yaz/oku/sil): böylece yerel dosya sistemi ile Supabase
Storage arasında geçiş, çağıran kodu değiştirmeden yapılabilir. Çevrimdışı demo yerel
depoyla çalışır (ARCHITECTURE.md §6, C planı).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol

from app.core.errors import NotFoundError


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


_storage: DocumentStorage | None = None


def get_storage() -> DocumentStorage:
    global _storage
    if _storage is None:
        from app.core.config import get_settings

        _storage = LocalFileStorage(Path(get_settings().storage_root))
    return _storage


def set_storage(storage: DocumentStorage | None) -> None:
    """Testlerin depoyu değiştirebilmesi için."""
    global _storage
    _storage = storage
