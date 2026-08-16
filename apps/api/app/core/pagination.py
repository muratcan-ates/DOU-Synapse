"""Opak keyset imleçlerinin kodlama/doğrulaması ve keyset sayfalama dansının tek yeri."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import Select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationError


class InvalidCursorError(ValidationError):
    code = "invalid_cursor"


def _encode(parts: list[str]) -> str:
    raw = "|".join(parts).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode(cursor: str, expected_parts: int) -> list[str]:
    try:
        padding = "=" * (-len(cursor) % 4)
        parts = base64.urlsafe_b64decode(cursor + padding).decode("utf-8").split("|")
    except (ValueError, UnicodeDecodeError) as exc:
        raise InvalidCursorError("Sayfalama imleci geçersiz.") from exc
    if len(parts) != expected_parts or any(not part for part in parts):
        raise InvalidCursorError("Sayfalama imleci geçersiz.")
    return parts


def encode_time_cursor(created_at: datetime, row_id: UUID) -> str:
    return _encode([created_at.isoformat(), str(row_id)])


def decode_time_cursor(cursor: str) -> tuple[datetime, UUID]:
    raw_time, raw_id = _decode(cursor, 2)
    try:
        parsed_time = datetime.fromisoformat(raw_time)
        parsed_id = UUID(raw_id)
    except ValueError as exc:
        raise InvalidCursorError("Sayfalama imleci geçersiz.") from exc
    if parsed_time.tzinfo is None:
        raise InvalidCursorError("Sayfalama imleci geçersiz.")
    return parsed_time, parsed_id


def encode_message_cursor(created_at: datetime, seq: int, row_id: UUID) -> str:
    return _encode([created_at.isoformat(), str(seq), str(row_id)])


def decode_message_cursor(cursor: str) -> tuple[datetime, int, UUID]:
    raw_time, raw_seq, raw_id = _decode(cursor, 3)
    try:
        parsed_time = datetime.fromisoformat(raw_time)
        parsed_seq = int(raw_seq)
        parsed_id = UUID(raw_id)
    except ValueError as exc:
        raise InvalidCursorError("Sayfalama imleci geçersiz.") from exc
    if parsed_time.tzinfo is None or parsed_seq < 0:
        raise InvalidCursorError("Sayfalama imleci geçersiz.")
    return parsed_time, parsed_seq, parsed_id


class SupportsPageParams(Protocol):
    """Sayfa parametrelerinin yapısal tipi.

    `api.deps.PageParams` bu şekle uyar; core katmanı api'yi import edemeyeceği
    için sözleşme burada Protocol olarak durur. Yardımcı yalnız iki alana bakar:
    üst sınıra çoktan kırpılmış `limit` ve istemcinin aynen geri gönderdiği
    opak `cursor`.
    """

    @property
    def limit(self) -> int: ...

    @property
    def cursor(self) -> str | None: ...


@dataclass(frozen=True)
class KeysetPage[RowT]:
    """Bir keyset sayfasının ham sonucu: görünür satırlar + sonraki imleç."""

    rows: list[RowT]
    next_cursor: str | None


async def paginate(
    session: AsyncSession,
    query: Select[Any],
    *,
    model: Any,
    page: SupportsPageParams,
    scalars: bool = True,
) -> KeysetPage[Any]:
    """`(created_at, id)` keyset sayfalama dansının tek yeri.

    Dans her liste ucunda aynıydı ve elle kopyalanıyordu: imleci çöz →
    `tuple_(created_at, id) <` filtresi → `DESC, DESC` sıralama → `limit + 1`
    satır iste → görünür dilimi ayır → fazla satır varsa son görünür kayıttan
    `next_cursor` üret. Bozuk imleç `InvalidCursorError` (422) fırlatır ve
    sorgu hiç koşmaz; `limit` üst sınırı burada değil `get_page_params`'ta
    kırpılır — ikisi de davranış sözleşmesinin parçasıdır.

    `scalars=True` iken satırlar `model` örnekleridir. `scalars=False` iken
    satırlar `Row` döner ve imlecin türetildiği varlık SELECT'in İLK kolonundaki
    `model` kabul edilir (ör. `select(Course, CourseMembership.role)`).
    """
    if page.cursor is not None:
        created_at, row_id = decode_time_cursor(page.cursor)
        query = query.where(tuple_(model.created_at, model.id) < (created_at, row_id))
    result = await session.execute(
        query.order_by(model.created_at.desc(), model.id.desc()).limit(page.limit + 1)
    )
    rows: list[Any] = list(result.scalars()) if scalars else list(result.all())
    visible = rows[: page.limit]
    next_cursor = None
    if len(rows) > page.limit:
        last = visible[-1] if scalars else visible[-1][0]
        next_cursor = encode_time_cursor(last.created_at, last.id)
    return KeysetPage(rows=visible, next_cursor=next_cursor)


__all__ = [
    "InvalidCursorError",
    "KeysetPage",
    "SupportsPageParams",
    "decode_message_cursor",
    "decode_time_cursor",
    "encode_message_cursor",
    "encode_time_cursor",
    "paginate",
]
