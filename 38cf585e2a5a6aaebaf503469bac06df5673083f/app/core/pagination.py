"""Opak keyset imleçlerinin kodlama ve doğrulaması."""

from __future__ import annotations

import base64
from datetime import datetime
from uuid import UUID

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


__all__ = [
    "InvalidCursorError",
    "decode_message_cursor",
    "decode_time_cursor",
    "encode_message_cursor",
    "encode_time_cursor",
]
