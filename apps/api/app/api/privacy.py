"""Kullanıcının kendi verisi üzerindeki KVKK hakları."""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import UUID

from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import Result

from app.api.deps import CourseMemberDep, PrincipalDep, SessionDep
from app.core.db import db_now
from app.core.errors import ConflictError, NotFoundError
from app.models.assessment import Answer, ExamSession, Mastery
from app.models.chat import ChatMessage, ChatMessageFeedback, ChatSession
from app.models.core import Course, CourseMembership, MembershipStatus, Profile
from app.schemas.privacy import (
    AccountAnonymizationOut,
    ChatDeletionOut,
    ExportAnswerOut,
    ExportChatFeedbackOut,
    ExportChatMessageOut,
    ExportChatSessionOut,
    ExportExamSessionOut,
    ExportMasteryOut,
    ExportMembershipOut,
    ExportProfileOut,
    UserDataExportOut,
)

router = APIRouter(tags=["privacy"])


def _affected_rows(result: Result[Any]) -> int:
    value = getattr(result, "rowcount", 0)
    return value if isinstance(value, int) and value > 0 else 0


async def _delete_owned_chat_sessions(
    session: SessionDep,
    *,
    user_id: UUID,
    course_id: UUID | None = None,
    session_id: UUID | None = None,
) -> int:
    conditions = [ChatSession.user_id == user_id]
    if course_id is not None:
        conditions.append(ChatSession.course_id == course_id)
    if session_id is not None:
        conditions.append(ChatSession.id == session_id)
    result = await session.execute(delete(ChatSession).where(*conditions))
    return _affected_rows(result)


@router.delete(
    "/courses/{course_id}/chat/sessions/{session_id}",
    response_model=ChatDeletionOut,
)
async def delete_chat_session(
    session_id: UUID,
    context: CourseMemberDep,
    session: SessionDep,
) -> ChatDeletionOut:
    deleted = await _delete_owned_chat_sessions(
        session,
        user_id=context.user_id,
        course_id=context.course_id,
        session_id=session_id,
    )
    if deleted == 0:
        raise NotFoundError("Sohbet oturumu bulunamadı.")
    return ChatDeletionOut(deleted_sessions=deleted)


@router.delete(
    "/courses/{course_id}/chat/sessions",
    response_model=ChatDeletionOut,
)
async def delete_course_chat_history(
    context: CourseMemberDep,
    session: SessionDep,
) -> ChatDeletionOut:
    deleted = await _delete_owned_chat_sessions(
        session,
        user_id=context.user_id,
        course_id=context.course_id,
    )
    return ChatDeletionOut(deleted_sessions=deleted)


@router.delete("/me/chat-history", response_model=ChatDeletionOut)
async def delete_all_chat_history(
    principal: PrincipalDep,
    session: SessionDep,
) -> ChatDeletionOut:
    """Aktif üyelikten bağımsız olarak kullanıcının tüm sohbet geçmişini sil."""
    deleted = await _delete_owned_chat_sessions(session, user_id=principal.user_id)
    return ChatDeletionOut(deleted_sessions=deleted)


@router.get("/me/export", response_model=UserDataExportOut)
async def export_my_data(
    principal: PrincipalDep,
    session: SessionDep,
) -> JSONResponse:
    """Kullanıcının verisini açık uygulama filtreleriyle tek JSON dosyası olarak ver."""
    user_id = principal.user_id
    profile = await session.get(Profile, user_id)
    if profile is None:
        raise NotFoundError("Kullanıcı profili bulunamadı.")

    memberships = (
        (
            await session.execute(
                select(CourseMembership)
                .where(CourseMembership.user_id == user_id)
                .order_by(CourseMembership.created_at)
            )
        )
        .scalars()
        .all()
    )
    chat_sessions = (
        (
            await session.execute(
                select(ChatSession)
                .where(ChatSession.user_id == user_id)
                .order_by(ChatSession.created_at)
            )
        )
        .scalars()
        .all()
    )
    chat_ids = [item.id for item in chat_sessions]
    chat_messages: list[ChatMessage] = []
    if chat_ids:
        chat_messages = list(
            (
                await session.execute(
                    select(ChatMessage)
                    .where(ChatMessage.session_id.in_(chat_ids))
                    .order_by(ChatMessage.created_at, ChatMessage.seq)
                )
            )
            .scalars()
            .all()
        )
    feedback_by_message: dict[UUID, ChatMessageFeedback] = {}
    if chat_messages:
        feedback_rows = (
            (
                await session.execute(
                    select(ChatMessageFeedback).where(
                        ChatMessageFeedback.user_id == user_id,
                        ChatMessageFeedback.message_id.in_([item.id for item in chat_messages]),
                    )
                )
            )
            .scalars()
            .all()
        )
        feedback_by_message = {item.message_id: item for item in feedback_rows}

    messages_by_session: dict[UUID, list[ExportChatMessageOut]] = defaultdict(list)
    for message in chat_messages:
        feedback = feedback_by_message.get(message.id)
        messages_by_session[message.session_id].append(
            ExportChatMessageOut(
                **ExportChatMessageOut.model_validate(message).model_dump(exclude={"feedback"}),
                feedback=(
                    ExportChatFeedbackOut.model_validate(feedback) if feedback is not None else None
                ),
            )
        )

    exam_sessions = (
        (
            await session.execute(
                select(ExamSession)
                .where(ExamSession.user_id == user_id)
                .order_by(ExamSession.started_at)
            )
        )
        .scalars()
        .all()
    )
    exam_ids = [item.id for item in exam_sessions]
    answers: list[Answer] = []
    if exam_ids:
        answers = list(
            (
                await session.execute(
                    select(Answer)
                    .where(Answer.session_id.in_(exam_ids))
                    .order_by(Answer.answered_at)
                )
            )
            .scalars()
            .all()
        )
    answers_by_session: dict[UUID, list[ExportAnswerOut]] = defaultdict(list)
    for answer in answers:
        answers_by_session[answer.session_id].append(ExportAnswerOut.model_validate(answer))

    mastery = (
        (
            await session.execute(
                select(Mastery)
                .where(Mastery.user_id == user_id)
                .order_by(Mastery.course_id, Mastery.topic_id)
            )
        )
        .scalars()
        .all()
    )
    generated_at = await db_now(session)
    payload = UserDataExportOut(
        generated_at=generated_at,
        profile=ExportProfileOut.model_validate(profile),
        memberships=[ExportMembershipOut.model_validate(item) for item in memberships],
        chat_sessions=[
            ExportChatSessionOut(
                **ExportChatSessionOut.model_validate(item).model_dump(exclude={"messages"}),
                messages=messages_by_session[item.id],
            )
            for item in chat_sessions
        ],
        exam_sessions=[
            ExportExamSessionOut(
                **ExportExamSessionOut.model_validate(item).model_dump(exclude={"answers"}),
                answers=answers_by_session[item.id],
            )
            for item in exam_sessions
        ],
        mastery=[ExportMasteryOut.model_validate(item) for item in mastery],
    )
    filename = f"dou-synapse-verilerim-{generated_at.date().isoformat()}.json"
    return JSONResponse(
        content=jsonable_encoder(payload),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/me", response_model=AccountAnonymizationOut)
async def anonymize_my_account(
    principal: PrincipalDep,
    session: SessionDep,
) -> AccountAnonymizationOut:
    """Kişisel profili anonimleştir, geçmişi sil ve üyelikleri iptal et.

    Ders/materyal/konu sahipliği RESTRICT bağları nedeniyle silinmez. Profil satırı
    benzersiz bir tombstone olarak kalır; bağlı akademik kayıtların bütünlüğü korunur.
    Gerçek auth hesabı kimlik sağlayıcısında ayrıca kapatılmalıdır.
    """
    user_id = principal.user_id
    profile = await session.get(Profile, user_id)
    if profile is None:
        raise NotFoundError("Kullanıcı profili bulunamadı.")
    if profile.email == f"silinmis+{user_id}@dou-synapse.invalid":
        raise ConflictError("Bu hesap daha önce anonimleştirildi.")

    retained_owned_courses = int(
        await session.scalar(select(func.count(Course.id)).where(Course.created_by == user_id)) or 0
    )
    deleted_chat_sessions = await _delete_owned_chat_sessions(session, user_id=user_id)
    membership_result = await session.execute(
        update(CourseMembership)
        .where(
            CourseMembership.user_id == user_id,
            CourseMembership.status != MembershipStatus.REVOKED,
        )
        .values(status=MembershipStatus.REVOKED)
    )
    revoked_memberships = _affected_rows(membership_result)
    await session.execute(
        update(Profile)
        .where(Profile.id == user_id)
        .values(
            email=f"silinmis+{user_id}@dou-synapse.invalid",
            full_name=None,
        )
    )
    return AccountAnonymizationOut(
        deleted_chat_sessions=deleted_chat_sessions,
        revoked_memberships=revoked_memberships,
        retained_owned_courses=retained_owned_courses,
        message=(
            "Uygulama profili anonimleştirildi ve üyelikler kapatıldı. "
            "Üniversite kimlik hesabının kapatılması kimlik sağlayıcısında ayrıca yapılmalıdır."
        ),
    )
