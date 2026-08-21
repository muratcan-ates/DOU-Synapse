"""Kişisel içerik taşımayan platform operasyon ekranı sözleşmeleri."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.contracts import AnswerStatus, ChatMode
from app.models.core import JobStatus


class AdminOverviewOut(BaseModel):
    status: str
    database_status: str
    embedding_status: str
    measured_at: datetime
    users_total: int
    active_memberships_total: int
    courses_total: int
    documents_total: int
    ingestion_processing: int
    ingestion_failed: int
    chat_turns_24h: int
    p95_latency_ms: float | None
    tokens_24h: int


class AdminUserItem(BaseModel):
    id: UUID
    masked_email: str
    full_name: str | None
    created_at: datetime
    is_platform_admin: bool
    active_course_count: int


class AdminUserQueryIn(BaseModel):
    """PII içerebilecek aramayı URL yerine doğrulanan gövdede taşır."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    search: str | None = Field(default=None, max_length=200)


class AdminCourseItem(BaseModel):
    id: UUID
    code: str
    title: str
    created_at: datetime
    creator_name: str
    active_member_count: int
    documents_total: int
    documents_failed: int


class AdminRequestItem(BaseModel):
    # Ölçüm tablosu satır kimliğidir; middleware destek/request kimliği değildir.
    log_id: UUID
    course_id: UUID
    course_code: str
    route: str
    mode: ChatMode
    status: AnswerStatus | None
    http_status: int
    latency_ms: int
    token_count: int | None
    cache_hit: bool
    created_at: datetime


class AdminIngestionItem(BaseModel):
    id: UUID
    document_id: UUID
    course_id: UUID
    course_code: str
    status: JobStatus
    attempt_count: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class AdminUserListOut(BaseModel):
    items: list[AdminUserItem]
    total: int
    limit: int
    offset: int


class AdminCourseListOut(BaseModel):
    items: list[AdminCourseItem]
    total: int
    limit: int
    offset: int


class AdminRequestListOut(BaseModel):
    items: list[AdminRequestItem]
    total: int
    limit: int
    offset: int


class AdminIngestionListOut(BaseModel):
    items: list[AdminIngestionItem]
    total: int
    limit: int
    offset: int
