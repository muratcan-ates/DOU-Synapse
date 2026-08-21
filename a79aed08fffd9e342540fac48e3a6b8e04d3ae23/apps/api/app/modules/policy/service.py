"""Ders politikasının tek çözümleme ve sunucu tarafı zorlama noktası."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import ChatMode
from app.core.config import Settings
from app.core.errors import PermissionDeniedError
from app.models.policy import CourseAiPolicy
from app.modules.assessment.socratic import MAX_STAGE_INDEX

DEFAULT_ALLOWED_MODES = frozenset({ChatMode.QA, ChatMode.SOCRATIC})


@dataclass(frozen=True, slots=True)
class CoursePolicy:
    allowed_modes: frozenset[ChatMode]
    max_hints: int
    source_document_ids: frozenset[UUID] | None
    evidence_threshold: float
    daily_token_budget: int | None
    student_daily_token_budget: int
    instructor_daily_token_budget: int
    max_output_tokens: int
    max_concurrent_requests: int


async def resolve_policy(
    session: AsyncSession, *, course_id: UUID, settings: Settings
) -> CoursePolicy:
    """NULL ve satır-yok durumlarını bugünkü global davranışa çözer."""
    row = await session.scalar(select(CourseAiPolicy).where(CourseAiPolicy.course_id == course_id))
    raw_hints = (
        settings.socratic_max_stage if row is None or row.max_hints is None else row.max_hints
    )
    max_hints = max(0, min(raw_hints, settings.socratic_max_stage, MAX_STAGE_INDEX))
    allowed = (
        DEFAULT_ALLOWED_MODES
        if row is None or row.allowed_modes is None
        else frozenset(row.allowed_modes)
    )
    if max_hints == 0:
        allowed = allowed - {ChatMode.SOCRATIC}
    return CoursePolicy(
        allowed_modes=allowed,
        max_hints=max_hints,
        source_document_ids=(
            None
            if row is None or row.source_document_ids is None
            else frozenset(row.source_document_ids)
        ),
        evidence_threshold=(
            settings.evidence_threshold
            if row is None or row.evidence_threshold is None
            else float(row.evidence_threshold)
        ),
        daily_token_budget=min(
            settings.course_agent_course_daily_hard_limit,
            (
                settings.course_agent_course_daily_hard_limit
                if row is None or row.daily_token_budget is None
                else row.daily_token_budget
            ),
        ),
        student_daily_token_budget=min(
            12000 if row is None else row.student_daily_token_budget,
            settings.course_agent_student_daily_hard_limit,
        ),
        instructor_daily_token_budget=min(
            40000 if row is None else row.instructor_daily_token_budget,
            settings.course_agent_instructor_daily_hard_limit,
        ),
        max_output_tokens=min(
            settings.llm_chat_max_tokens if row is None else row.max_output_tokens,
            settings.llm_chat_max_tokens,
        ),
        max_concurrent_requests=(1 if row is None else row.max_concurrent_requests),
    )


def assert_mode_allowed(policy: CoursePolicy, mode: ChatMode, *, is_instructor: bool) -> None:
    """Öğrenci mod kapısını oturum yaratılmadan önce zorlar; eğitmen test edebilir."""
    if not is_instructor and mode not in policy.allowed_modes:
        raise PermissionDeniedError(
            "Bu asistan modu dersin eğitmeni tarafından kapatıldı.",
            code="mode_not_allowed",
        )


async def tokens_used_today(session: AsyncSession, *, course_id: UUID) -> int:
    value = await session.scalar(
        text("SELECT app.course_tokens_today(:course_id)"), {"course_id": course_id}
    )
    return int(value or 0)


async def budget_exhausted(session: AsyncSession, *, course_id: UUID, policy: CoursePolicy) -> bool:
    """RLS'i delmeden toplamı okur; sınır dolmuşsa normal ürün durumu döndürür."""
    if policy.daily_token_budget is None:
        return False
    used = await tokens_used_today(session, course_id=course_id)
    return used >= policy.daily_token_budget


__all__ = [
    "CoursePolicy",
    "assert_mode_allowed",
    "budget_exhausted",
    "resolve_policy",
    "tokens_used_today",
]
