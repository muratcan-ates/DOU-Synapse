"""Büyüyebilen liste uçlarının tek sayfa zarfı (FR-160...FR-163)."""

from __future__ import annotations

from pydantic import BaseModel


class PageOut[T](BaseModel):
    """Bir keyset sayfası; istemci imleci üretmez, yalnız geri gönderir."""

    items: list[T]
    next_cursor: str | None = None


__all__ = ["PageOut"]
