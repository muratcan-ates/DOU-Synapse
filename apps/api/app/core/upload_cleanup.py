"""Depolama nesneleri için işlem sonucuna bağlı, dar telafi kaydı.

Yeni yüklemenin telafisi rollback sonrası, mevcut belgenin fiziksel silinmesi
ise yalnız doğrulanmış COMMIT sonrası çalışır. Bu bir dağıtık transaction veya
kalıcı iş kuyruğu değildir. Belirsiz sonuçlarda içeriksiz uzlaştırma sinyali kalır.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger("app.upload_cleanup")
_PENDING_KEY = "dou_pending_upload_cleanup"
_PENDING_DELETIONS_KEY = "dou_pending_document_deletions"
Operation = Literal["upload", "document_delete"]


@dataclass(frozen=True)
class PendingStorageObject:
    key: str
    delete: Callable[[str], Awaitable[None]]


def register_upload_cleanup(
    session: AsyncSession, *, key: str, delete: Callable[[str], Awaitable[None]]
) -> None:
    """Başarılı save sonrası yeni nesne kaydedilir; eski materyal kaydedilmez."""
    pending: list[PendingStorageObject] = session.info.setdefault(_PENDING_KEY, [])
    pending.append(PendingStorageObject(key=key, delete=delete))


def discard_upload_cleanup(session: AsyncSession) -> None:
    session.info.pop(_PENDING_KEY, None)


def register_document_deletion(
    session: AsyncSession, *, key: str, delete: Callable[[str], Awaitable[None]]
) -> None:
    """Belge satırının silinmesi COMMIT olmadan mevcut nesneye dokunma."""
    pending: list[PendingStorageObject] = session.info.setdefault(_PENDING_DELETIONS_KEY, [])
    pending.append(PendingStorageObject(key=key, delete=delete))


def _definite_failure(error: BaseException, *, handler_failed: bool) -> bool:
    if isinstance(error, asyncio.CancelledError):
        # İptal edilen depolama I/O'su başka bir thread/serviste sürebilir.
        return False
    if handler_failed:
        return True
    if isinstance(error, DBAPIError) and not error.connection_invalidated:
        sqlstate = getattr(error.orig, "sqlstate", None)
        # PostgreSQL constraint veya transaction-rollback sınıfı: sunucu COMMIT'i
        # kesin reddetmiştir. Bağlantı kopması gibi bilinmeyen sonuçlar dahil değil.
        return isinstance(sqlstate, str) and sqlstate[:2] in {"23", "40"}
    return False


def _report_reconciliation(operation: Operation, reason: str, object_count: int) -> None:
    logger.error(
        "depolama nesneleri için uzlaştırma gerekiyor",
        extra={
            "context": {
                "event": f"{operation}_reconciliation_required",
                "reason": reason,
                "object_count": object_count,
            }
        },
    )


def report_unconfirmed_upload() -> None:
    """Save sahipliği doğrulanamadı: mevcut/kısmi nesneyi koru, içerik loglama."""
    _report_reconciliation("upload", "storage_outcome_unknown", 1)


async def _delete_pending_objects(
    pending: list[PendingStorageObject], operation: Operation
) -> None:
    failures = 0
    for index, item in enumerate(pending):
        try:
            await item.delete(item.key)
        except asyncio.CancelledError:
            # Önceki başarısızlar + sonucu belirsiz mevcut nesne + henüz
            # denenmemişler sayılır. Anahtar/hata metni loglanmaz, iptal korunur.
            _report_reconciliation(
                operation, "cleanup_outcome_unknown", failures + len(pending) - index
            )
            raise
        except Exception:
            # Depolama hata metni özel URL/sır içerebilir. Normal cleanup hatası
            # asıl uygulama hatasını veya doğrulanmış COMMIT'i değiştirmez.
            failures += 1
    if failures:
        _report_reconciliation(operation, "cleanup_failed", failures)


async def resolve_failed_uploads(
    session: AsyncSession, *, error: BaseException, handler_failed: bool
) -> None:
    pending: list[PendingStorageObject] = session.info.pop(_PENDING_KEY, [])
    if not pending:
        return
    if not _definite_failure(error, handler_failed=handler_failed):
        _report_reconciliation("upload", "transaction_outcome_unknown", len(pending))
        return
    await _delete_pending_objects(pending, "upload")


def retain_failed_document_deletions(
    session: AsyncSession, *, error: BaseException, handler_failed: bool
) -> None:
    """Başarısız/belirsiz işlemde mevcut dosyaları silme; belirsizliği bildir."""
    pending: list[PendingStorageObject] = session.info.pop(_PENDING_DELETIONS_KEY, [])
    if pending and not _definite_failure(error, handler_failed=handler_failed):
        _report_reconciliation("document_delete", "transaction_outcome_unknown", len(pending))


async def resolve_committed_document_deletions(session: AsyncSession) -> None:
    """Yalnız başarıyla kapanmış DB işlemi sonrasında çağrılır.

    Silme hatası COMMIT'i geri alamaz. 204 veritabanındaki belge/kaynak silimini
    korur; kalmış olabilecek özel nesne için operatöre uzlaştırma sinyali yazılır.
    """
    pending: list[PendingStorageObject] = session.info.pop(_PENDING_DELETIONS_KEY, [])
    await _delete_pending_objects(pending, "document_delete")
