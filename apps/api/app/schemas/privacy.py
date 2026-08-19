"""KVKK veri dışa aktarma ve anonimleştirme sözleşmeleri."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.contracts import AnswerStatus, ChatMode, SocraticStage
from app.models.assessment import ExamMode
from app.models.chat import ChatFeedbackRating, ChatFeedbackReason, ChatRole
from app.models.core import MembershipRole, MembershipStatus

USER_DATA_EXPORT_NOT_INCLUDED: tuple[str, ...] = (
    "ai_token_reservations: Soru, cevap veya kaynak metni içermeyen token bütçesi, "
    "maliyet ve eşzamanlılık operasyon kaydıdır; bu dışa aktarıma dahil edilmez.",
    "ai_guard_events: Soru, cevap veya kaynak metni içermeyen hız, kota, "
    "eşzamanlılık ve kapsam reddi güvenlik kaydıdır; bu dışa aktarıma dahil edilmez.",
)


class _FromRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ExportProfileOut(_FromRow):
    id: UUID
    email: str
    full_name: str | None
    created_at: datetime


class ExportMembershipOut(_FromRow):
    course_id: UUID
    role: MembershipRole
    status: MembershipStatus
    created_at: datetime


class ExportChatFeedbackOut(_FromRow):
    id: UUID
    rating: ChatFeedbackRating
    reason: ChatFeedbackReason
    comment: str | None
    share_with_instructor: bool
    created_at: datetime
    updated_at: datetime


class ExportChatMessageOut(_FromRow):
    id: UUID
    role: ChatRole
    content: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    status: AnswerStatus | None
    socratic_stage: SocraticStage | None
    seq: int
    created_at: datetime
    feedback: ExportChatFeedbackOut | None = None


class ExportChatSessionOut(_FromRow):
    id: UUID
    course_id: UUID
    mode: ChatMode
    state: dict[str, Any] = Field(default_factory=dict)
    title: str | None
    created_at: datetime
    updated_at: datetime
    messages: list[ExportChatMessageOut] = Field(default_factory=list)


class ExportAnswerOut(_FromRow):
    id: UUID
    question_id: UUID
    given: str | None
    is_correct: bool | None
    score: int | None
    hint_level: int
    feedback: dict[str, Any] | None
    answered_at: datetime


class ExportExamSessionOut(_FromRow):
    id: UUID
    course_id: UUID
    mode: ExamMode
    started_at: datetime
    expires_at: datetime | None
    finished_at: datetime | None
    score: float | None
    # Legacy/practice kâğıdı burada taşınır; resmî blueprint kâğıdının tek kaynağı
    # exam_version_id + exam_items olduğu için question_ids bilinçli olarak NULL'dır.
    question_ids: list[UUID] | None
    exam_version_id: UUID | None
    exam_blueprint_id: UUID | None
    attempt_no: int | None
    feedback_available_at: datetime | None
    answers: list[ExportAnswerOut] = Field(default_factory=list)


class ExportMasteryOut(_FromRow):
    course_id: UUID
    topic_id: UUID
    score: float
    answer_count: int
    updated_at: datetime


class UserDataExportOut(BaseModel):
    schema_version: Literal["2"] = "2"
    generated_at: datetime
    profile: ExportProfileOut
    memberships: list[ExportMembershipOut]
    chat_sessions: list[ExportChatSessionOut]
    exam_sessions: list[ExportExamSessionOut]
    mastery: list[ExportMasteryOut]
    not_included: list[str] = Field(default_factory=lambda: list(USER_DATA_EXPORT_NOT_INCLUDED))


class ChatDeletionOut(BaseModel):
    deleted_sessions: int


class AccountAnonymizationOut(BaseModel):
    anonymized: bool = True
    deleted_chat_sessions: int
    revoked_memberships: int
    retained_owned_courses: int
    identity_provider_action_required: bool = True
    message: str
