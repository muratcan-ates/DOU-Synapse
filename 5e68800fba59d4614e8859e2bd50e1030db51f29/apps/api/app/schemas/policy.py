"""Ders AI politikası API sözleşmeleri."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts import ChatMode


class CourseAiPolicyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_modes: list[ChatMode] | None = None
    hint_limit: int | None = Field(default=None, ge=0, le=10)
    evidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    daily_llm_budget: int | None = Field(default=None, ge=1)
    source_document_ids: list[UUID] | None = None

    @model_validator(mode="after")
    def _exam_is_not_an_assistant_mode(self) -> CourseAiPolicyIn:
        if self.allowed_modes is not None and ChatMode.EXAM in self.allowed_modes:
            raise ValueError("Sınav modu sohbet politikasıyla açılamaz")
        if self.allowed_modes is not None and len(set(self.allowed_modes)) != len(
            self.allowed_modes
        ):
            raise ValueError("Aynı asistan modu iki kez gönderilemez")
        if self.source_document_ids is not None and len(set(self.source_document_ids)) != len(
            self.source_document_ids
        ):
            raise ValueError("Aynı kaynak iki kez seçilemez")
        return self


class EffectivePolicyOut(BaseModel):
    allowed_modes: list[ChatMode]
    hint_limit: int
    evidence_threshold: float
    daily_llm_budget: int | None
    source_document_ids: list[UUID] | None


class CourseAiPolicyOut(CourseAiPolicyIn):
    course_id: UUID
    effective: EffectivePolicyOut
    updated_by: UUID | None = None
    updated_at: datetime | None = None
    budget_used_today: int = 0
    budget_remaining_today: int | None = None


class CourseAiPolicyAuditOut(BaseModel):
    id: UUID
    course_id: UUID
    changed_by: UUID | None
    changed_at: datetime
    before: dict[str, Any] | None
    after: dict[str, Any] | None


__all__ = [
    "CourseAiPolicyAuditOut",
    "CourseAiPolicyIn",
    "CourseAiPolicyOut",
    "EffectivePolicyOut",
]
