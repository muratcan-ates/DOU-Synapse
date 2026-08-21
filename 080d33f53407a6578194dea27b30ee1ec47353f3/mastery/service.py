"""Mastery-Lite: konu bazlı EWMA ile çalışma performans göstergesi.

    yeni = 0.7 x eski + 0.3 x son_skor
    ipucu kademesi çarpanları: 0 -> 1.00, 1 -> 0.85, 2 -> 0.70, 3 -> 0.50, 4 -> 0.25
    seviye eşikleri: < 0.40 Geliştirilmeli | 0.40-0.74 Orta | >= 0.75 İyi

SADELEŞTİRME GEREKÇESİ (raporda aynen savunulur): BKT/IRT gibi yerleşik öğrenci
modelleri parametre kestirimi için bizde olmayan öğrenci verisi ister. EWMA, yakın
geçmişe ağırlık veren üstel unutma modellerine kaba bir yaklaşımdır; 0.7/0.3 seçimi
(``Settings.mastery_alpha``) duyarlılık notuyla raporlanır (bkz. docs/test-report.md).

Bu çıktı RESMÎ NOT DEĞİLDİR; çalışma önerisi göstergesidir (human-in-the-loop).
Arayüzde bu ibare zorunludur (ARCHITECTURE.md §5).

Karar noktaları:
- Skor alanı 0-1'dir. Grading 0-100 döndürür; bu modül /100 ile normalize eder.
- İpucu çarpanı EWMA'dan ÖNCE ham skora uygulanır: son = raw/100 * HINT_MULTIPLIERS[level].
- İlk cevapta (kayıt yok) `yeni = son` — 0.7*0 ile başlatmak öğrenciyi haksız yere düşük
  gösterirdi. answer_count 1 olur. Bu davranış test_mastery.py'de sabitlenir.
- Seviye eşikleri sınır dahildir: skor tam 0.40 -> Orta, tam 0.75 -> İyi.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Mastery

HINT_MULTIPLIERS: dict[int, float] = {0: 1.00, 1: 0.85, 2: 0.70, 3: 0.50, 4: 0.25}

DEFAULT_ALPHA = 0.3  # Settings.mastery_alpha ile aynı değer; çağıran ayarı geçebilir.


class MasteryLevel(StrEnum):
    NEEDS_WORK = "needs_work"  # Geliştirilmeli
    MEDIUM = "medium"  # Orta
    GOOD = "good"  # İyi


def level_for(score: float) -> MasteryLevel:
    """Skor -> seviye etiketi. Sınırlar dahildir: 0.40 Orta'ya, 0.75 İyi'ye girer."""
    if score >= 0.75:
        return MasteryLevel.GOOD
    if score >= 0.40:
        return MasteryLevel.MEDIUM
    return MasteryLevel.NEEDS_WORK


def _hint_multiplier(hint_level: int) -> float:
    try:
        return HINT_MULTIPLIERS[hint_level]
    except KeyError:
        # Beklenmeyen bir kademe değeri gelirse en katı çarpanı uygula (fail-closed):
        # olduğundan yüksek mastery göstermektense düşük göstermek tercih edilir.
        return HINT_MULTIPLIERS[max(HINT_MULTIPLIERS)]


def compute_new_score(
    *,
    previous_score: float | None,
    previous_answer_count: int,
    raw_score: int,
    hint_level: int = 0,
    alpha: float = DEFAULT_ALPHA,
) -> float:
    """Tek bir cevaptan yeni mastery skorunu hesaplar (0-1). Yan etkisizdir, test edilebilir."""
    normalized = max(0.0, min(1.0, raw_score / 100))
    last = normalized * _hint_multiplier(hint_level)

    if previous_answer_count == 0 or previous_score is None:
        return last

    return (1 - alpha) * previous_score + alpha * last


async def record_answer(
    session: AsyncSession,
    *,
    user_id: UUID,
    topic_id: UUID,
    course_id: UUID,
    raw_score: int,
    hint_level: int = 0,
    alpha: float = DEFAULT_ALPHA,
) -> float:
    """Cevabı mastery'ye işler ve güncel puanı döndürür.

    Bu, `exams.py` (T037, sınav bitişinde) ve Sokratik oturum kapanışında `chat.py`
    (R1'in dosyası — çağrıyı R1 ekler, bu imza R1'e yazılı verilir) tarafından çağrılan
    tek giriş noktasıdır. `mastery` tablosuna INSERT/UPDATE `dou_app` rolüyle yapılır;
    RLS politikaları (`mastery_self_insert`/`mastery_self_update`) `user_id = current_user_id()`
    şartını arar, dolayısıyla bu fonksiyon yalnızca çağıran kullanıcının kendi satırını
    güncelleyebilir.
    """
    existing = await session.execute(
        select(Mastery).where(Mastery.user_id == user_id, Mastery.topic_id == topic_id)
    )
    row = existing.scalar_one_or_none()

    new_score = compute_new_score(
        previous_score=row.score if row else None,
        previous_answer_count=row.answer_count if row else 0,
        raw_score=raw_score,
        hint_level=hint_level,
        alpha=alpha,
    )

    if row is None:
        row = Mastery(
            user_id=user_id,
            topic_id=topic_id,
            course_id=course_id,
            score=new_score,
            answer_count=1,
        )
        session.add(row)
    else:
        row.score = new_score
        row.answer_count += 1

    await session.flush()
    return new_score
