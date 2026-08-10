"""Öğrenci yanıt geri bildirimi ve eğitmen kalite görünümü sözleşmeleri."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.chat import ChatFeedbackRating, ChatFeedbackReason


class ChatFeedbackUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: ChatFeedbackRating
    reason: ChatFeedbackReason
    comment: str | None = Field(default=None, max_length=1000)
    share_with_instructor: bool = False

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def reason_matches_rating(self) -> ChatFeedbackUpsert:
        if self.rating is ChatFeedbackRating.HELPFUL:
            if self.reason not in {ChatFeedbackReason.HELPFUL, ChatFeedbackReason.OTHER}:
                raise ValueError("Yararlı puanı yalnız yararlı veya diğer gerekçesiyle kaydedilir.")
            if self.share_with_instructor:
                raise ValueError("Öğretmen incelemesi yalnız sorun bildirilen cevaplar içindir.")
        elif self.reason is ChatFeedbackReason.HELPFUL:
            raise ValueError("Sorun bildirilen cevapta yararlı gerekçesi kullanılamaz.")
        return self


class ChatFeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    message_id: UUID
    rating: ChatFeedbackRating
    reason: ChatFeedbackReason
    comment: str | None
    share_with_instructor: bool
    created_at: datetime
    updated_at: datetime


class SharedFeedbackOut(BaseModel):
    id: UUID
    message_id: UUID
    student_name: str
    rating: ChatFeedbackRating
    reason: ChatFeedbackReason
    comment: str | None
    question_excerpt: str | None
    answer_excerpt: str
    updated_at: datetime


class ChatQualityOut(BaseModel):
    course_id: UUID
    rated_count: int
    helpful_count: int
    unhelpful_count: int
    shared_review_count: int
    reason_counts: dict[str, int]
    recent_shared: list[SharedFeedbackOut]
