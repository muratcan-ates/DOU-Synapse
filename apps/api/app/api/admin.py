"""Salt okunur ve kişisel sohbet içermeyen platform operasyon uçları."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import text

from app.api.deps import PlatformAdminDep, SessionDep
from app.contracts import AnswerStatus
from app.core.request_observability import observer_snapshot
from app.core.warmup import warmup_is_ready, warmup_state
from app.models.core import JobStatus
from app.schemas.admin import (
    AdminApiEventListOut,
    AdminApiEventQueryIn,
    AdminCourseListOut,
    AdminIngestionListOut,
    AdminOverviewOut,
    AdminRequestListOut,
    AdminUserListOut,
    AdminUserQueryIn,
)

router = APIRouter(prefix="/admin", tags=["admin"])

PageLimit = Annotated[int, Query(ge=1, le=100)]
PageOffset = Annotated[int, Query(ge=0)]


@router.get("/overview", response_model=AdminOverviewOut)
async def get_admin_overview(
    admin: PlatformAdminDep,
    session: SessionDep,
) -> AdminOverviewOut:
    del admin
    value = await session.scalar(text("SELECT app.admin_overview()"))
    overview = dict(value or {})
    embedding_status = warmup_state()
    overview.update(
        {
            "status": "ok" if warmup_is_ready(embedding_status) else "degraded",
            "database_status": "ok",
            "embedding_status": embedding_status,
            "measured_at": datetime.now(UTC),
        }
    )
    return AdminOverviewOut.model_validate(overview)


@router.post("/users", response_model=AdminUserListOut)
async def list_admin_users(
    query: AdminUserQueryIn,
    admin: PlatformAdminDep,
    session: SessionDep,
) -> AdminUserListOut:
    """Kullanıcı dizinini URL'ye ad/e-posta bırakmadan sorgula."""

    del admin
    value = await session.scalar(
        text("SELECT app.admin_users(:limit, :offset, :search)"),
        {
            "limit": query.limit,
            "offset": query.offset,
            "search": query.search,
        },
    )
    return AdminUserListOut.model_validate(value)


@router.get("/courses", response_model=AdminCourseListOut)
async def list_admin_courses(
    admin: PlatformAdminDep,
    session: SessionDep,
    limit: PageLimit = 25,
    offset: PageOffset = 0,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> AdminCourseListOut:
    del admin
    value = await session.scalar(
        text("SELECT app.admin_courses(:limit, :offset, :search)"),
        {"limit": limit, "offset": offset, "search": search},
    )
    return AdminCourseListOut.model_validate(value)


@router.get("/requests", response_model=AdminRequestListOut)
async def list_admin_requests(
    admin: PlatformAdminDep,
    session: SessionDep,
    limit: PageLimit = 25,
    offset: PageOffset = 0,
    route: Annotated[str | None, Query(max_length=200)] = None,
    status: AnswerStatus | None = None,
) -> AdminRequestListOut:
    del admin
    value = await session.scalar(
        text("SELECT app.admin_request_logs(:limit, :offset, :route, :status)"),
        {
            "limit": limit,
            "offset": offset,
            "route": route,
            "status": status.value if status is not None else None,
        },
    )
    return AdminRequestListOut.model_validate(value)


@router.get("/ingestion", response_model=AdminIngestionListOut)
async def list_admin_ingestion(
    admin: PlatformAdminDep,
    session: SessionDep,
    limit: PageLimit = 25,
    offset: PageOffset = 0,
    status: JobStatus | None = None,
) -> AdminIngestionListOut:
    del admin
    value = await session.scalar(
        text("SELECT app.admin_ingestion_jobs(:limit, :offset, :status)"),
        {
            "limit": limit,
            "offset": offset,
            "status": status.value if status is not None else None,
        },
    )
    return AdminIngestionListOut.model_validate(value)


@router.post("/api-events/query", response_model=AdminApiEventListOut)
async def query_admin_api_events(
    query: AdminApiEventQueryIn,
    admin: PlatformAdminDep,
    session: SessionDep,
) -> AdminApiEventListOut:
    """Kisisel icerik olmadan API sagligi ve destek kodu aramasi."""

    del admin
    value = await session.scalar(
        text(
            "SELECT app.admin_api_request_events("
            ":window_minutes, :limit, :offset, :method, :route, "
            ":status_class, :request_id)"
        ),
        {
            "window_minutes": query.window_minutes,
            "limit": query.limit,
            "offset": query.offset,
            "method": query.method,
            "route": query.route,
            "status_class": query.status_class,
            "request_id": query.request_id,
        },
    )
    result = dict(value or {})
    result["collector"] = observer_snapshot()
    return AdminApiEventListOut.model_validate(result)
