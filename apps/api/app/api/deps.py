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


#: `scope="function"` — commit'in yanıt gönderilmeden ÖNCE olmasını sağlar.
#:
#: Ölçülen kusur (lider şeridi, 9 Ağustos): `POST /documents` `202` dönüyor, hemen
#: ardındaki `GET` **0 belge** görüyor, bir saniye sonraki `GET` 1 belge görüyor.
#: Arayüz bunu geçici bir tazeleme penceresiyle maskeliyordu; asıl sebep sunucuda.
#:
#: FastAPI 0.141'in istek işleyicisi (`routing.get_request_handler`) şu sırayla
#: çalışıyor:
#:
#:     async with AsyncExitStack() as request_stack:      # varsayılan yield kapsamı
#:         async with AsyncExitStack() as function_stack:
#:             response = await endpoint(...)
#:         await response(scope, receive, send)           # yanıt BURADA gidiyor
#:     # request_stack burada kapanıyor → rls_session çıkışı → COMMIT
#:
#: Yani varsayılan (`scope="request"`) kapsamda commit, istemci yanıtı aldıktan
#: SONRA gerçekleşiyor; istemcinin hemen yaptığı ikinci istek işlemi henüz
#: görmüyor. `scope="function"` bağımlılığı `function_stack`'e taşır ve commit
#: yanıt yazılmadan önce biter — istemcinin gözlemleyebildiği her yanıt, kalıcı
#: hâle gelmiş bir işlemi temsil eder.
#:
#: Düzeltme bilinçli olarak TEK YERDE: uçların her birine `await session.commit()`
#: eklemek aynı kuralı on üç yerde hatırlamayı gerektirirdi ve biri unutulduğunda
#: kusur sessizce geri gelirdi (Anayasa XI).
#:
#: Not: `BackgroundTasks` yine yanıttan sonra çalışır ve bu doğrudur — worker
#: tetiği kullanıcıyı bekletmemeli. Yalnız veritabanı işlemi öne alınıyor.
SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]


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
