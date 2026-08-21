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

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.models.assessment import ExamMode, ExamSession

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


def effective_expiry(exam: ExamSession, *, settings: Settings) -> datetime | None:
    """Kırpılmış bitiş zamanı. practice modda None (süresiz)."""
    if exam.mode is ExamMode.PRACTICE:
        return None
    cap = exam.started_at + timedelta(minutes=settings.exam_duration_minutes)
    if exam.expires_at is None:  # pragma: no cover - CHECK kısıtı bunu engeller
        return cap
    return min(exam.expires_at, cap)


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
    result = await session.execute(
        select(ExamSession)
        .where(
            ExamSession.user_id == user_id,
            ExamSession.course_id == course_id,
            ExamSession.mode == ExamMode.EXAM,
            ExamSession.finished_at.is_(None),
            ExamSession.expires_at > now,
        )
        .order_by(ExamSession.started_at.desc())
    )
    for exam in result.scalars():
        expiry = effective_expiry(exam, settings=settings)
        if expiry is not None and now < expiry:
            return exam
    return None
