"""Sınav oturumunun zaman durumu ve asistan kilidi — tek kaynak.

Bu modül iki soruyu yanıtlar ve ikisini de **yalnız burada** yanıtlar:

1. Bir sınav oturumu ne zaman biter? (`effective_expiry`, `remaining_seconds`)
2. Bir öğrencinin şu anda yürüyen bir sınavı var mı? (`active_exam_session`)

Kodun `api/exams.py`'den buraya taşınmasının sebebi ikinci soru. `api/deps.py`
asistan kilidini kurarken aynı süre kuralına ihtiyaç duyuyor ve `deps.py`'nin
`exams.py`'yi içe aktarması doğrudan bir döngü olurdu (`exams.py` zaten `deps`'i
aktarıyor). `app/modules/*` bugün `app/api/*`'ye hiç bağlı değil; ortak kuralın
evi burası.

**Kırpma kuralı neden SQL'e yazılmıyor.** `active_exam_session` sorgusundaki
`expires_at > now` yalnız bir daraltma yüklemidir — `min(expires_at, started_at +
süre)`'nin iki argümanından biri, dolayısıyla nihai koşulun gerekli ama yeterli
olmayan hâli. Nihai kararı Python'daki `effective_expiry` verir. Aynı kuralı bir
de `func.least(...)` ile SQL'e yazmak, tek bir ürün kararını iki dilde tutmak
olurdu; `exam_duration_minutes` değiştiğinde ya da kural sıkılaştığında ikisinden
biri geride kalırdı — üstelik sessizce, çünkü SQL tarafı gevşek kalırsa kilit
**fail-open** olur (Anayasa IV'ün tam tersi).

`api/exams.py`'nin üç zaman kuralından ikincisi (kırpma) bu modülde yaşar; o
dosyanın başlığındaki tablo hâlâ mod politikalarının tek anlatımıdır.
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.models.assessment import ExamBlueprint, ExamMode, ExamSession
from app.models.core import CourseMembership, MembershipRole

#: Kilit gerekçesi. İKİ yüzeyde birden kullanılır: 403 zarfının `error.code`'u ve
#: `GET /chat/availability`'nin `reason` alanı. Tek sabit olması, arayüzün iki
#: yüzeyi farklı tanıyıp birinde kilidi kaçırmasını engeller.
EXAM_LOCK_REASON = "exam_in_progress"

#: Kullanıcıya dönen metin (Anayasa V). Arayüz kendi metnini uydurmaz; hem 403
#: gövdesi hem yoklama ucu bu cümleyi taşır.
EXAM_LOCK_MESSAGE = (
    "Şu anda süren bir sınav oturumun var. Sınav bitene ya da süresi dolana kadar "
    "asistanı kullanamazsın. Sınavı bitirince buradan devam edebilirsin."
)


class ExamLockedError(AppError):
    """Yürüyen sınav oturumu asistanı kapattı."""

    status_code = status.HTTP_403_FORBIDDEN
    code = EXAM_LOCK_REASON


async def acquire_user_assessment_lock(session: AsyncSession, *, user_id: UUID) -> None:
    """Serialize exam start with chat finalization and privacy export.

    The lock is transaction scoped. Chat acquires it immediately before its
    final active-exam check and keeps it while persisting the answer. Exam
    start and the data export acquire the same user key before inspecting or
    writing exam-sensitive data. PostgreSQL then permits exactly one order:
    either chat/export commits first and the exam starts afterwards, or the
    exam commits first and the competing operation observes it.
    """

    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:identity, 15018))"),
        {"identity": str(user_id)},
    )


class AssessmentExportLockedError(AppError):
    """An active exam temporarily withholds answer-bearing export data."""

    status_code = status.HTTP_423_LOCKED
    code = "exam_export_locked"


def effective_expiry(
    exam: ExamSession, *, settings: Settings, cap_minutes: int | None = None
) -> datetime | None:
    """Kırpılmış bitiş zamanı. practice modda None (süresiz).

    `cap_minutes` verilmezse global `exam_duration_minutes` kullanılır; bu, bugünkü
    PROVA akışının kuralıdır. Blueprint sınavında süre sınavın kendi alanıdır
    (FR-111) ve çağıran onu buraya geçirir.

    **Varsayılan neden global kalıyor:** kırpma bir güvenlik kuralıdır, ve argümanı
    unutulan bir çağrı yeri kırpmayı GEVŞETMEK yerine SIKMALIDIR. 20 dakikalık
    global sınır 45 dakikalık bir blueprint için yanlıştır ama zararsız yönde
    yanlıştır; tersi olsaydı unutulan her çağrı süreyi uzatırdı (Anayasa IV).

    0008 turunda TARAYICIDA ölçülen kusur buydu: blueprint 45 dakika derken oturum
    20'de bitiyordu. Hiçbir test yakalamıyordu çünkü blueprint akışının süresini
    sınayan bir test yoktu; şimdi var.
    """
    if exam.mode is ExamMode.PRACTICE:
        return None
    minutes = settings.exam_duration_minutes if cap_minutes is None else cap_minutes
    cap = exam.started_at + timedelta(minutes=minutes)
    if exam.expires_at is None:  # pragma: no cover - CHECK kısıtı bunu engeller
        return cap
    return min(exam.expires_at, cap)


async def session_cap_minutes(
    session: AsyncSession, exam: ExamSession, *, settings: Settings
) -> int:
    """Bu oturumun kırpma sınırı: blueprint sınavında sınavın kendi süresi.

    Prova oturumunda SORGU KOŞMAZ. Blueprint oturumunda `exam_blueprints`'ten tek
    kolon okunur; satır bulunamazsa (FK RESTRICT sayesinde olamaz) global sınıra
    düşer — belirsizlikte kural sıkı kalır.
    """
    if exam.exam_blueprint_id is None:
        return settings.exam_duration_minutes
    minutes = await session.scalar(
        select(ExamBlueprint.duration_minutes).where(ExamBlueprint.id == exam.exam_blueprint_id)
    )
    return int(minutes) if minutes is not None else settings.exam_duration_minutes


def remaining_seconds(expiry: datetime | None, now: datetime) -> int | None:
    if expiry is None:
        return None
    return max(0, int((expiry - now).total_seconds()))


async def active_exam_session(
    session: AsyncSession,
    *,
    user_id: UUID,
    course_id: UUID,
    now: datetime,
    settings: Settings,
) -> ExamSession | None:
    """Bu kullanıcının bu derste **yürüyen** sınav oturumu (yoksa None).

    "Yürüyen" = `exam` modunda, bitirilmemiş ve etkin süresi dolmamış. Prova
    (`practice`) oturumu hiçbir zaman yürüyen sayılmaz: prova modu yardımı
    kapatmaz, tam tersine ipucu orada açıktır (`api/exams.py` mod tablosu).

    Kilit **ders bazlıdır**: `course_id` yüklemi bilerek buradadır. A dersinde
    sınav veren öğrenci B dersinin asistanını kullanabilir — kilidin amacı o
    sınavın bütünlüğü, öğrencinin tüm gününü kapatmak değil.

    `user_id` yüklemi RLS'e BIRAKILMAZ, açıkça yazılır: `exam_sessions_self_read`
    politikası eğitmene dersin bütün oturumlarını açıyor, dolayısıyla RLS tek
    başına "kendi oturumu" anlamına gelmiyor (Anayasa II: iki katman birbirinin
    yerine geçmez).
    """
    active = await active_exam_sessions_by_course(
        session,
        user_id=user_id,
        course_ids={course_id},
        now=now,
        settings=settings,
    )
    return active.get(course_id)


async def any_active_student_exam_session(
    session: AsyncSession,
    *,
    user_id: UUID,
    now: datetime,
    settings: Settings,
) -> ExamSession | None:
    """Return an active exam unless the stored course role is instructor.

    Instructors are deliberately exempt from the assistant exam lock and must
    remain able to export their own data while previewing an exam. A student's
    lock, however, must survive a membership status change: otherwise revoking
    the membership during an exam would expose prior answer-bearing chat data
    through ``/me/export``. The outer join is fail-closed for legacy or damaged
    rows with no membership: only a known instructor role receives the
    exception.
    """

    course_ids = set(
        (
            await session.scalars(
                select(ExamSession.course_id)
                .outerjoin(
                    CourseMembership,
                    (CourseMembership.course_id == ExamSession.course_id)
                    & (CourseMembership.user_id == ExamSession.user_id),
                )
                .where(
                    ExamSession.user_id == user_id,
                    ExamSession.mode == ExamMode.EXAM,
                    ExamSession.finished_at.is_(None),
                    ExamSession.expires_at > now,
                    CourseMembership.role.is_distinct_from(MembershipRole.INSTRUCTOR),
                )
            )
        ).all()
    )
    active = await active_exam_sessions_by_course(
        session,
        user_id=user_id,
        course_ids=course_ids,
        now=now,
        settings=settings,
    )
    return next(iter(active.values()), None)


async def any_unreleased_student_blueprint_session(
    session: AsyncSession,
    *,
    user_id: UUID,
    now: datetime,
) -> ExamSession | None:
    """KVKK export'unda çözüm/puan sızdırabilecek resmî oturumu bulur.

    ``finished_at`` burada istisna değildir: erken biten blueprint sınavının cevap
    ve puanı güvenli yayın anına kadar hâlâ sınav korumasındadır. NULL schedule,
    migration öncesi tarihsel belirsizliktir ve fail-closed kilitli kalır. Yalnız
    bilinen instructor rolü preview istisnası alır.
    """

    return await session.scalar(
        select(ExamSession)
        .outerjoin(
            CourseMembership,
            (CourseMembership.course_id == ExamSession.course_id)
            & (CourseMembership.user_id == ExamSession.user_id),
        )
        .where(
            ExamSession.user_id == user_id,
            ExamSession.exam_version_id.is_not(None),
            (
                ExamSession.feedback_available_at.is_(None)
                | (ExamSession.feedback_available_at > now)
            ),
            CourseMembership.role.is_distinct_from(MembershipRole.INSTRUCTOR),
        )
        .order_by(ExamSession.started_at.desc())
        .limit(1)
    )


async def active_exam_sessions_by_course(
    session: AsyncSession,
    *,
    user_id: UUID,
    course_ids: Collection[UUID],
    now: datetime,
    settings: Settings,
) -> dict[UUID, ExamSession]:
    """Ders kümesindeki yürüyen sınavları tek sorguda döndürür.

    Dashboard, öğrencinin her dersi için availability ucuna ayrı istek atmaz ve
    sunucu da ders başına ayrı sorgu çalıştırmaz. Blueprint süreleri aynı sorguda
    alınır; nihai karar yine :func:`effective_expiry` ile Python'da verilir. Bu,
    tek-ders kilidinin ``min(expires_at, started_at + süre)`` kuralını aynen
    korurken N+1 sorgusunu önler.

    Bir derste birden fazla bitirilmemiş satır varsa en yeni yürüyen oturum
    seçilir. En yeni satır etkin süresiyle dolmuşsa daha eski satırlar da
    değerlendirilir; farklı blueprint süreleri yüzünden eski bir oturum hâlâ
    yürür durumda olabilir.
    """
    requested_courses = set(course_ids)
    if not requested_courses:
        return {}

    result = await session.execute(
        select(ExamSession, ExamBlueprint.duration_minutes)
        .outerjoin(ExamBlueprint, ExamBlueprint.id == ExamSession.exam_blueprint_id)
        .where(
            ExamSession.user_id == user_id,
            ExamSession.course_id.in_(requested_courses),
            ExamSession.mode == ExamMode.EXAM,
            ExamSession.finished_at.is_(None),
            ExamSession.expires_at > now,
        )
        .order_by(ExamSession.started_at.desc())
    )
    active: dict[UUID, ExamSession] = {}
    for exam, blueprint_duration in result.tuples():
        if exam.course_id in active:
            continue
        # Blueprint sınavının süresi kendi alanındadır; global sınırla kırpmak
        # kilidi ERKEN açardı — 45 dakikalık sınavın 21. dakikasında asistan
        # serbest kalırdı. Fail-open, yani Anayasa IV'ün tam tersi.
        cap = (
            int(blueprint_duration)
            if blueprint_duration is not None
            else settings.exam_duration_minutes
        )
        expiry = effective_expiry(exam, settings=settings, cap_minutes=cap)
        if expiry is not None and now < expiry:
            active[exam.course_id] = exam
    return active
