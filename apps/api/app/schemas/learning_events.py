"""İçerik taşımayan öğrenme olayı ve eğitmen özeti sözleşmeleri."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LearningTopicSummary(BaseModel):
    topic_id: UUID | None
    topic_name: str
    wrong_answers: int = Field(ge=0)
    hints_requested: int = Field(ge=0)
    unsupported_refusals: int = Field(ge=0)


class LearningSummaryOut(BaseModel):
    course_id: UUID
    days: Literal[7, 30]
    topics: list[LearningTopicSummary]
    total_events: int = Field(ge=0)


class CitationOpenedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: UUID
    session_id: UUID | None = None


class LearningEventReceipt(BaseModel):
    id: UUID


class LearningEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    event_type: str
    occurred_at: datetime
    session_id: UUID | None
    topic_id: UUID | None


class LearningEventsOut(BaseModel):
    items: list[LearningEventOut]
    total: int
