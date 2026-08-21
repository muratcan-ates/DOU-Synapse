"""Eğitmenin ders bazlı AI davranış sınırlarını yönettiği uçlar."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.api.deps import CourseInstructorDep, SessionDep, SettingsDep
from app.contracts import ChatMode
from app.core.errors import ValidationError
from app.models.core import Document
from app.models.policy import CourseAiPolicy, CourseAiPolicyAudit
from app.modules.policy.service import resolve_policy, tokens_used_today
from app.schemas.policy import (
    CourseAiPolicyAuditOut,
    CourseAiPolicyIn,
    CourseAiPolicyOut,
    EffectivePolicyOut,
)

router = APIRouter(prefix="/courses/{course_id}/ai-policy", tags=["policy"])


def _ordered_modes(modes: frozenset[ChatMode]) -> list[ChatMode]:
    return [mode for mode in (ChatMode.QA, ChatMode.SOCRATIC) if mode in modes]


async def _out(
    session: SessionDep,
    *,
    course_id: UUID,
    settings: SettingsDep,
) -> CourseAiPolicyOut:
    row = await session.scalar(select(CourseAiPolicy).where(CourseAiPolicy.course_id == course_id))
    effective = await resolve_policy(session, course_id=course_id, settings=settings)
    configured_sources = None if row is None else row.source_document_ids
    live_sources: list[UUID] | None = None
    if configured_sources is not None:
        live_sources = sorted(
            (
                await session.scalars(
                    select(Document.id).where(
                        Document.course_id == course_id,
                        Document.id.in_(configured_sources),
                    )
                )
            ).all(),
            key=str,
        )
    used = await tokens_used_today(session, course_id=course_id)
    remaining = (
        None
        if effective.daily_token_budget is None
        else max(0, effective.daily_token_budget - used)
    )
    return CourseAiPolicyOut(
        course_id=course_id,
        allowed_modes=None if row is None or row.allowed_modes is None else row.allowed_modes,
        hint_limit=None if row is None else row.max_hints,
        evidence_threshold=(
            None if row is None or row.evidence_threshold is None else float(row.evidence_threshold)
        ),
        daily_llm_budget=None if row is None else row.daily_token_budget,
        source_document_ids=live_sources,
        student_daily_token_budget=(12000 if row is None else row.student_daily_token_budget),
        instructor_daily_token_budget=(40000 if row is None else row.instructor_daily_token_budget),
        max_output_tokens=700 if row is None else row.max_output_tokens,
        max_concurrent_requests=1 if row is None else row.max_concurrent_requests,
        effective=EffectivePolicyOut(
            allowed_modes=_ordered_modes(effective.allowed_modes),
            hint_limit=effective.max_hints,
            evidence_threshold=effective.evidence_threshold,
            daily_llm_budget=effective.daily_token_budget,
            source_document_ids=(None if effective.source_document_ids is None else live_sources),
            student_daily_token_budget=effective.student_daily_token_budget,
            instructor_daily_token_budget=effective.instructor_daily_token_budget,
            max_output_tokens=effective.max_output_tokens,
            max_concurrent_requests=effective.max_concurrent_requests,
        ),
        updated_by=None if row is None else row.updated_by,
        updated_at=None if row is None else row.updated_at,
        budget_used_today=used,
        budget_remaining_today=remaining,
    )


@router.get("", response_model=CourseAiPolicyOut)
async def get_policy(
    context: CourseInstructorDep, session: SessionDep, settings: SettingsDep
) -> CourseAiPolicyOut:
    return await _out(session, course_id=context.course_id, settings=settings)


@router.put("", response_model=CourseAiPolicyOut)
async def put_policy(
    payload: CourseAiPolicyIn,
    context: CourseInstructorDep,
    session: SessionDep,
    settings: SettingsDep,
) -> CourseAiPolicyOut:
    if payload.source_document_ids is not None:
        existing = set(
            (
                await session.scalars(
                    select(Document.id).where(
                        Document.course_id == context.course_id,
                        Document.id.in_(payload.source_document_ids),
                    )
                )
            ).all()
        )
        missing = set(payload.source_document_ids) - existing
        if missing:
            raise ValidationError(
                "Kaynak politikası yalnızca bu derse ait mevcut belgeleri içerebilir."
            )

    values = {
        "course_id": context.course_id,
        "allowed_modes": payload.allowed_modes,
        "max_hints": payload.hint_limit,
        "source_document_ids": payload.source_document_ids,
        "evidence_threshold": payload.evidence_threshold,
        "daily_token_budget": payload.daily_llm_budget,
        "student_daily_token_budget": payload.student_daily_token_budget,
        "instructor_daily_token_budget": payload.instructor_daily_token_budget,
        "max_output_tokens": payload.max_output_tokens,
        "max_concurrent_requests": payload.max_concurrent_requests,
        "updated_by": context.user_id,
        "updated_at": func.now(),
    }
    statement = pg_insert(CourseAiPolicy).values(**values)
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[CourseAiPolicy.course_id],
            set_={key: value for key, value in values.items() if key != "course_id"},
        )
    )
    # Eski kaynak/eşik altında üretilmiş cevap yeni politikayı delmesin.
    await session.execute(
        text("SELECT app.invalidate_course_agent_cache(:course_id)"),
        {"course_id": context.course_id},
    )
    await session.flush()
    return await _out(session, course_id=context.course_id, settings=settings)


@router.get("/history", response_model=list[CourseAiPolicyAuditOut])
async def policy_history(
    context: CourseInstructorDep,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[CourseAiPolicyAuditOut]:
    rows = (
        await session.scalars(
            select(CourseAiPolicyAudit)
            .where(CourseAiPolicyAudit.course_id == context.course_id)
            .order_by(CourseAiPolicyAudit.changed_at.desc(), CourseAiPolicyAudit.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return [CourseAiPolicyAuditOut.model_validate(row, from_attributes=True) for row in rows]
