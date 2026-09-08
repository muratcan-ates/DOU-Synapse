"""Fence pending chat writes after privacy deletion without holding an LLM lock.

Revision reads are lock-free at request entry. Only final persistence and
privacy deletion share a short transaction lock; the revision pair preserves
course scope even though that lock is per user. Nothing here commits a session.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import AssistantAudience
from app.core.errors import ConflictError
from app.models.chat import ChatSession
from app.models.core import CourseMembership, MembershipRole, MembershipStatus


@dataclass(frozen=True, slots=True)
class PrivacyRevision:
    global_revision: int
    course_revision: int


def history_changed() -> ConflictError:
    return ConflictError(
        "Sohbet geçmişin veya ders erişimin değiştiği için bekleyen yanıt kaydedilmedi. "
        "Devam etmek için yeni bir sohbet aç.",
        code="chat_history_changed",
    )


async def acquire_user_chat_lock(session: AsyncSession, *, user_id: UUID) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:identity, 15024))"),
        {"identity": str(user_id)},
    )


async def read_revision(
    session: AsyncSession, *, user_id: UUID, course_id: UUID
) -> PrivacyRevision:
    result = await session.execute(
        text(
            "SELECT course_id, revision FROM public.chat_privacy_revisions "
            "WHERE user_id = :user_id AND (course_id IS NULL OR course_id = :course_id)"
        ),
        {"user_id": user_id, "course_id": course_id},
    )
    revisions = {row.course_id: int(row.revision) for row in result}
    return PrivacyRevision(revisions.get(None, 0), revisions.get(course_id, 0))


async def advance_revision(session: AsyncSession, *, user_id: UUID, course_id: UUID | None) -> None:
    """Called inside the deletion's transaction, even when it deletes no rows."""
    await session.execute(
        text(
            "INSERT INTO public.chat_privacy_revisions (user_id, course_id, revision) "
            "VALUES (:user_id, :course_id, 1) "
            "ON CONFLICT ON CONSTRAINT chat_privacy_revisions_scope_key "
            "DO UPDATE SET revision = chat_privacy_revisions.revision + 1"
        ),
        {"user_id": user_id, "course_id": course_id},
    )


async def finalize_session(
    session: AsyncSession,
    *,
    user_id: UUID,
    course_id: UUID,
    audience: AssistantAudience,
    started_revision: PrivacyRevision,
    chat_session: ChatSession,
    is_new: bool,
) -> ChatSession:
    """Recheck fresh SQL under the delete lock, then attach a transient session.

    ORM identity-map state from before provider I/O cannot prove either active
    membership or continued session existence. The lock lasts until the caller's
    transaction commits/rolls back, covering all subsequent messages and cache.
    """
    await acquire_user_chat_lock(session, user_id=user_id)
    if await read_revision(session, user_id=user_id, course_id=course_id) != started_revision:
        raise history_changed()
    role = await session.scalar(
        select(CourseMembership.role).where(
            CourseMembership.user_id == user_id,
            CourseMembership.course_id == course_id,
            CourseMembership.status == MembershipStatus.ACTIVE,
        )
    )
    expected_role = (
        MembershipRole.INSTRUCTOR
        if audience is AssistantAudience.INSTRUCTOR
        else MembershipRole.STUDENT
    )
    if role != expected_role:
        raise history_changed()
    if is_new:
        session.add(chat_session)
        await session.flush()
        return chat_session
    expected_mode = chat_session.mode
    current = await session.scalar(
        select(ChatSession)
        .where(
            ChatSession.id == chat_session.id,
            ChatSession.user_id == user_id,
            ChatSession.course_id == course_id,
        )
        .execution_options(populate_existing=True)
    )
    if current is None or current.audience is not audience or current.mode is not expected_mode:
        raise history_changed()
    return current
