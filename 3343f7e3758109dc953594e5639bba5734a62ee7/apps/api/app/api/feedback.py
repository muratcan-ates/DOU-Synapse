"""Yanıt geri bildirimi ve gizlilik korumalı eğitmen kalite kuyruğu."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select, text

from app.api.deps import CourseInstructorDep, CourseMemberDep, SessionDep
from app.core.errors import NotFoundError, PermissionDeniedError
from app.models.chat import ChatMessage, ChatMessageFeedback, ChatRole, ChatSession
from app.models.core import Profile
from app.schemas.feedback import (
    ChatFeedbackOut,
    ChatFeedbackUpsert,
    ChatQualityOut,
    SharedFeedbackOut,
)

router = APIRouter(prefix="/courses/{course_id}/chat", tags=["chat-quality"])


@router.put("/messages/{message_id}/feedback", response_model=ChatFeedbackOut)
async def upsert_feedback(
    message_id: UUID,
    payload: ChatFeedbackUpsert,
    context: CourseMemberDep,
    session: SessionDep,
) -> ChatFeedbackOut:
    """Kendi asistan mesajımın puanını oluşturur veya değiştirir.

    Mesaj metni istemciden alınmaz. Paylaşım seçilmişse SQL tetikleyicisi gerçek
    oturumdaki soru-cevap çiftini kopyalar; böylece sahte bir alıntı yüklenemez.
    """
    if context.is_instructor:
        raise PermissionDeniedError("Yanıt geri bildirimi öğrenci deneyimi için kullanılır.")

    message = (
        await session.execute(
            select(ChatMessage)
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .where(
                ChatMessage.id == message_id,
                ChatMessage.course_id == context.course_id,
                ChatMessage.role == ChatRole.ASSISTANT,
                ChatSession.user_id == context.user_id,
                ChatSession.course_id == context.course_id,
            )
        )
    ).scalar_one_or_none()
    if message is None:
        raise NotFoundError("Puanlanabilir asistan yanıtı bulunamadı.")

    feedback = (
        await session.execute(
            select(ChatMessageFeedback).where(
                ChatMessageFeedback.message_id == message.id,
                ChatMessageFeedback.user_id == context.user_id,
            )
        )
    ).scalar_one_or_none()
    if feedback is None:
        feedback = ChatMessageFeedback(
            course_id=context.course_id,
            message_id=message.id,
            user_id=context.user_id,
            rating=payload.rating,
            reason=payload.reason,
            comment=payload.comment,
            share_with_instructor=payload.share_with_instructor,
        )
        session.add(feedback)
    else:
        feedback.rating = payload.rating
        feedback.reason = payload.reason
        feedback.comment = payload.comment
        feedback.share_with_instructor = payload.share_with_instructor

    await session.flush()
    await session.refresh(feedback)
    return ChatFeedbackOut.model_validate(feedback)


_SUMMARY = text("SELECT * FROM app.chat_feedback_summary(:course_id)")


@router.get("/quality", response_model=ChatQualityOut)
async def chat_quality(
    context: CourseInstructorDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> ChatQualityOut:
    """Toplu kalite dağılımı ve öğrencinin açıkça paylaştığı inceleme kayıtları."""
    summary = (await session.execute(_SUMMARY, {"course_id": context.course_id})).one()
    rows = (
        await session.execute(
            select(ChatMessageFeedback, Profile.full_name, Profile.email)
            .join(Profile, Profile.id == ChatMessageFeedback.user_id)
            .where(
                ChatMessageFeedback.course_id == context.course_id,
                ChatMessageFeedback.share_with_instructor.is_(True),
            )
            .order_by(ChatMessageFeedback.updated_at.desc(), ChatMessageFeedback.id.desc())
            .limit(limit)
        )
    ).all()
    recent = [
        SharedFeedbackOut(
            id=feedback.id,
            message_id=feedback.message_id,
            student_name=full_name or email,
            rating=feedback.rating,
            reason=feedback.reason,
            comment=feedback.comment,
            question_excerpt=feedback.question_excerpt,
            answer_excerpt=feedback.answer_excerpt or "",
            updated_at=feedback.updated_at,
        )
        for feedback, full_name, email in rows
    ]
    return ChatQualityOut(
        course_id=context.course_id,
        rated_count=int(summary.rated_count),
        helpful_count=int(summary.helpful_count),
        unhelpful_count=int(summary.unhelpful_count),
        shared_review_count=int(summary.shared_review_count),
        reason_counts={str(key): int(value) for key, value in summary.reason_counts.items()},
        recent_shared=recent,
    )
