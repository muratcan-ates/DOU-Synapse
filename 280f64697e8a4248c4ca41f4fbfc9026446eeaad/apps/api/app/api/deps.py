"""İstek bağımlılıkları: kimlik doğrulama, oturum ve ders yetkilendirmesi.

İzolasyonun birinci katmanı burasıdır. Kural: **course_id istemciden gelen bir yetki
belgesi değildir.** Yol parametresindeki ders kimliği yalnızca "hangi ders" sorusunu
yanıtlar; kullanıcının o derse erişip erişemeyeceği her istekte sunucuda üyelik
tablosundan doğrulanır. İkinci katman olan RLS de aynı oturumda devrededir.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Path, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import rls_session
from app.core.errors import AuthenticationError, NotFoundError, PermissionDeniedError
from app.core.security import Principal, authenticate
from app.models.core import CourseMembership, MembershipRole, MembershipStatus

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_principal(request: Request, settings: SettingsDep) -> Principal:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthenticationError("Bu işlem için giriş yapmanız gerekiyor.")
    return authenticate(token, settings)


PrincipalDep = Annotated[Principal, Depends(get_principal)]


async def get_session(principal: PrincipalDep) -> AsyncIterator[AsyncSession]:
    """Kullanıcı bağlamı ayarlanmış veritabanı oturumu."""
    async with rls_session(principal.user_id) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


@dataclass(frozen=True, slots=True)
class CourseContext:
    """Sunucu tarafında doğrulanmış ders erişimi."""

    course_id: UUID
    user_id: UUID
    role: MembershipRole

    @property
    def is_instructor(self) -> bool:
        return self.role is MembershipRole.INSTRUCTOR


async def _load_membership(
    session: AsyncSession, user_id: UUID, course_id: UUID
) -> CourseMembership | None:
    result = await session.execute(
        select(CourseMembership).where(
            CourseMembership.course_id == course_id,
            CourseMembership.user_id == user_id,
            CourseMembership.status == MembershipStatus.ACTIVE,
        )
    )
    return result.scalar_one_or_none()


async def require_course_member(
    principal: PrincipalDep,
    session: SessionDep,
    course_id: Annotated[UUID, Path(description="Ders kimliği")],
) -> CourseContext:
    membership = await _load_membership(session, principal.user_id, course_id)
    if membership is None:
        # Üye olunmayan dersin varlığını sızdırmamak için 404 döner: erişimi olmayan
        # kullanıcı, dersin var olup olmadığını öğrenemez.
        raise NotFoundError("Ders bulunamadı.")
    return CourseContext(course_id=course_id, user_id=principal.user_id, role=membership.role)


CourseMemberDep = Annotated[CourseContext, Depends(require_course_member)]


async def require_course_instructor(context: CourseMemberDep) -> CourseContext:
    if not context.is_instructor:
        raise PermissionDeniedError("Bu işlem yalnızca dersin eğitmeni tarafından yapılabilir.")
    return context


CourseInstructorDep = Annotated[CourseContext, Depends(require_course_instructor)]
