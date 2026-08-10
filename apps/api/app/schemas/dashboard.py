"""Rol duyarlı ürün ana sayfası sözleşmeleri."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.models.core import MembershipRole


class DashboardViewer(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str | None
    is_platform_admin: bool


class DashboardSummary(BaseModel):
    total_courses: int
    instructor_courses: int
    student_courses: int
    action_items: int


class DashboardCourse(BaseModel):
    id: UUID
    code: str
    title: str
    role: MembershipRole
    documents_total: int
    documents_processing: int
    documents_failed: int
    questions_total: int
    draft_questions: int
    published_exams: int
    mastery_score: float | None
    last_activity_at: datetime | None
    assistant_locked: bool
    assistant_lock_reason: str | None
    assistant_lock_message: str | None


class DashboardOut(BaseModel):
    viewer: DashboardViewer
    summary: DashboardSummary
    courses: list[DashboardCourse]
