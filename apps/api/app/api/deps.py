"""İstek bağımlılıkları: kimlik doğrulama, oturum ve ders yetkilendirmesi.

İzolasyonun birinci katmanı burasıdır. Kural: **course_id istemciden gelen bir yetki
belgesi değildir.** Yol parametresindeki ders kimliği yalnızca "hangi ders" sorusunu
yanıtlar; kullanıcının o derse erişip erişemeyeceği her istekte sunucuda üyelik
tablosundan doğrulanır. İkinci katman olan RLS de aynı oturumda devrededir.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import Depends, Path, Query, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import db_now, rls_session
from app.core.errors import (
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    request_id_of,
)
from app.core.security import Principal, authenticate
from app.models.core import CourseMembership, MembershipRole, MembershipStatus
from app.modules.assessment import exam_state

SettingsDep = Annotated[Settings, Depends(get_settings)]

# `auto_error=False` zorunludur: HTTPBearer'ın varsayılan İngilizce 401/403
# gövdesi projenin Türkçe ErrorEnvelope sözleşmesini atlamamalı. Aynı dependency
# OpenAPI'ye gerçek bearer güvenlik şemasını da taşır; sözleşme artık elle yazılan
# bir "Authorization" açıklamasına dayanmaz.
_bearer_auth = HTTPBearer(auto_error=False, scheme_name="BearerAuth")
BearerCredentialsDep = Annotated[
    HTTPAuthorizationCredentials | None,
    Security(_bearer_auth),
]


@dataclass(frozen=True, slots=True)
class PageParams:
    limit: int
    cursor: str | None


def get_page_params(
    settings: SettingsDep,
    limit: Annotated[int | None, Query(ge=1)] = None,
    cursor: Annotated[str | None, Query(min_length=1)] = None,
) -> PageParams:
    """İstemcinin boyunu sunucu üst sınırına kırpar; büyük istek 422 olmaz."""
    requested = settings.page_size_default if limit is None else limit
    return PageParams(limit=min(requested, settings.page_size_max), cursor=cursor)


PageDep = Annotated[PageParams, Depends(get_page_params)]


def get_principal(
    credentials: BearerCredentialsDep,
    settings: SettingsDep,
) -> Principal:
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Bu işlem için giriş yapmanız gerekiyor.")
    return authenticate(credentials.credentials, settings)


PrincipalDep = Annotated[Principal, Security(get_principal)]


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


class CourseOwnedRow(Protocol):
    """`course_id` kolonu taşıyan bir ORM satırının yapısal tipi."""

    course_id: UUID


async def load_owned[ModelT: CourseOwnedRow](
    session: AsyncSession,
    model: type[ModelT],
    row_id: UUID,
    context: CourseContext,
    *,
    message: str,
) -> ModelT:
    """Ders sahipliği doğrulanmış tek kayıt yükler.

    'X is None or X.course_id != context.course_id → 404' kalıbının tek yeri.
    RLS başka dersin kaydını zaten gizler; yine de ders eşleşmesi açıkça kontrol
    edilir — iki katman da bağımsız olarak doğru davranmalı. Kayıt hiç yokken
    de başka derse aitken de AYNI 404 döner: yabancı kaydın varlığı sızdırılmaz.
    Mesaj çağıran uca aittir; kullanıcıya dönen metin uca özgü kalır.
    """
    row = await session.get(model, row_id)
    if row is None or row.course_id != context.course_id:
        raise NotFoundError(message)
    return row


async def require_platform_admin(
    principal: PrincipalDep,
    request: Request,
) -> Principal:
    """Ders eğitmenliğinden bağımsız platform işletim yetkisini doğrular.

    İstemci rolü/e-posta listesi kullanılmaz. Yetki, uygulamanın doğrudan
    okuyamadığı `platform_admins` tablosunu dar bir SECURITY DEFINER yardımcıyla
    sorgular. Yönetim SQL fonksiyonları da aynı kontrolü yeniden yapar.

    Karar ayrı, tamamlanan bir işlemde audit tablosuna yazılır. Aynı işlem
    kullanılsaydı `PermissionDeniedError` bağımlılık oturumunu rollback eder ve
    tam da reddedilen denemelerin izi kaybolurdu.
    """
    action = f"{request.method.upper()} {request.url.path}"
    async with rls_session(principal.user_id) as audit_session:
        is_admin = await audit_session.scalar(
            text("SELECT app.audit_platform_admin_access(:action, :request_id)"),
            {"action": action, "request_id": request_id_of(request)},
        )
    if is_admin is not True:
        raise PermissionDeniedError("Bu işlem yalnızca platform yöneticisine açıktır.")
    return principal


PlatformAdminDep = Annotated[Principal, Depends(require_platform_admin)]


async def require_assistant_unlocked(
    context: CourseMemberDep,
    session: SessionDep,
    settings: SettingsDep,
) -> CourseContext:
    """Yürüyen sınav oturumu varsa asistan yüzeylerini kapatır.

    **Neden bağımlılık, neden uç gövdesi değil.** Kural moddan bağımsız olmak
    zorunda (FR-102): gövdeye yazılsaydı `payload.mode` elin altında olurdu ve
    moda bağlı bir istisna eklemek bir satırlık iş hâline gelirdi. Bağımlılık
    modu göremez, dolayısıyla mod bağımsızlığı yapısaldır.

    **Neden `require_course_member`'a gömülmedi.** Aynı bağımlılığı sınav uçları
    da kullanıyor; oraya gömülse sınav veren öğrenci kendi sınavına cevap
    veremez hâle gelirdi.

    **Kapsam POST ile sınırlı değil.** Geçmiş okuma ucu (`GET
    /chat/sessions/{id}`) önceki turların kaynaklı cevap metnini ve atıflarını
    aynen döndürüyor; sınav sırasında açılan ikinci sekmede okunabilen bir
    yardım yüzeyi. Bu yüzden kilit üç ucun üçünde de aynı kapıdan geçer.

    Eğitmen muafiyeti ilk satırdadır (FR-103): sorgu hiç koşmaz. Kilit
    değerlendirilen kişiyi hedefler; kendi dersinin sınavını açan bir eğitmen
    asistandan mahrum kalmaz.

    Modül `exam_state` olarak içe aktarılıp `exam_state.active_exam_session(...)`
    diye çağrılıyor: `from ... import active_exam_session` bağlanmış bir kopya
    bırakır ve mutasyon testinin monkeypatch'i etkisiz kalırdı — testin
    kırılabilirliği FR-106'nın kendisidir.
    """
    if context.is_instructor:
        return context
    now = await db_now(session)
    active = await exam_state.active_exam_session(
        session,
        user_id=context.user_id,
        course_id=context.course_id,
        now=now,
        settings=settings,
    )
    if active is not None:
        raise exam_state.ExamLockedError(exam_state.EXAM_LOCK_MESSAGE)
    return context


#: Adı bilerek göze batıcı: chat router'ına eklenecek dördüncü bir uç
#: `CourseMemberDep` yazarsa kilidi sessizce atlar, ve bu annotation'ın yokluğu
#: incelemede fark edilebilir olmalı.
UnlockedCourseMemberDep = Annotated[CourseContext, Depends(require_assistant_unlocked)]
