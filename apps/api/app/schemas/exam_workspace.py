"""Student assessment discovery projections; no question or answer-bearing fields."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PublishedExamSummary(BaseModel):
    blueprint_id: UUID
    title: str
    description: str | None
    duration_minutes: int
    opens_at: datetime | None
    closes_at: datetime | None
    max_attempts: int
    used_attempts: int
    remaining_attempts: int
    can_start: bool


class ExamCatalogOut(BaseModel):
    enabled: bool
    items: list[PublishedExamSummary]
