"""Kişisel içerik taşımayan platform operasyon ekranı sözleşmeleri.

KARAR (002 entegrasyonu): buradaki {items, total, limit, offset} zarfı, ürünün
onaylı sayfa zarfından (schemas/page.py: {items, next_cursor}) BİLİNÇLİ bir
sapmadır ve /admin SINIRINDA kalır. 002'nin offset+total'ı reddetme gerekçeleri
(eşzamanlı eklemede kayma, COUNT(*)'ın liste boyuyla doğrusallaşması) öğrenciye
dönük, büyüyebilen listeler içindi; salt-okunur, limit<=100 bir operasyon paneli
için toplam sayı işin kendisidir. /admin dışındaki HİÇBİR uç bu zarfı kullanamaz —
ürün yüzeyine liste eklerken schemas/page.py'ye git."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


ApiStatusClass = Literal["2xx", "3xx", "4xx", "5xx"]
ApiMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"]
ApiEnvironment = Literal["local", "demo", "production"]


class AdminApiEventQueryIn(BaseModel):
    """Icerik/kimlik tasimayan HTTP operasyon olaylarini sorgular."""

    model_config = ConfigDict(extra="forbid")

    window_minutes: Literal[15, 60, 1440] = 60
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=2_147_483_647)
    method: ApiMethod | None = None
    route: str | None = Field(default=None, min_length=1, max_length=256)
    status_class: ApiStatusClass | None = None
    request_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")

    @field_validator("method", mode="before")
    @classmethod
    def _normalise_method(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("route")
    @classmethod
    def _validate_route(cls, value: str | None) -> str | None:
        if value is None:
            return None
        route = value.strip()
        if not route or "?" in route or "#" in route:
            raise ValueError("route bir sorgu dizesi ya da parca tasiyamaz")
        return route


class _StatusCounts(BaseModel):
    requests_total: int = Field(ge=0)
    successful_total: int = Field(ge=0)
    redirect_total: int = Field(ge=0)
    client_error_total: int = Field(ge=0)
    server_error_total: int = Field(ge=0)
    p50_latency_ms: float | None = Field(default=None, ge=0)
    p95_latency_ms: float | None = Field(default=None, ge=0)


class AdminApiEventSummary(_StatusCounts):
    pass


class AdminApiRouteAggregate(BaseModel):
    method: ApiMethod
    route_template: str = Field(
        min_length=1,
        max_length=256,
        pattern=r"^(?:/[A-Za-z0-9_{}./-]{0,255}|UNMATCHED)$",
    )
    requests_total: int = Field(ge=0)
    error_total: int = Field(ge=0)
    p95_latency_ms: float | None = Field(default=None, ge=0)
    last_seen_at: datetime


class AdminApiEventItem(BaseModel):
    request_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    service: Literal["api"]
    environment: ApiEnvironment
    release_revision: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    method: ApiMethod
    route_template: str = Field(
        min_length=1,
        max_length=256,
        pattern=r"^(?:/[A-Za-z0-9_{}./-]{0,255}|UNMATCHED)$",
    )
    status_code: int = Field(ge=100, le=599)
    outcome_code: str | None = Field(default=None, pattern=r"^[a-z0-9_:-]{1,64}$")
    duration_ms: int = Field(ge=0, le=3_600_000)
    created_at: datetime


class AdminApiEventCollectorOut(BaseModel):
    scope: Literal["process"] = "process"
    status: Literal["disabled", "healthy", "degraded", "stopped"]
    retention_status: Literal["healthy", "degraded"]
    queue_depth: int = Field(ge=0)
    queue_capacity: int = Field(ge=0)
    persisted_total: int = Field(ge=0)
    dropped_total: int = Field(ge=0)
    failure_total: int = Field(ge=0)
    last_persisted_at: datetime | None
    last_error_at: datetime | None


class AdminApiEventListOut(BaseModel):
    measured_at: datetime
    window_minutes: Literal[15, 60, 1440]
    summary: AdminApiEventSummary
    routes: list[AdminApiRouteAggregate]
    items: list[AdminApiEventItem]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    collector: AdminApiEventCollectorOut
