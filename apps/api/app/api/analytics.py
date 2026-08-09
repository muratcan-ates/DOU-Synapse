"""Analitik uçları — Faz E (T038).

Ekran iki role birden hizmet eder ve rol değişince SORU değişir:

- **Öğrenci** — "hangi konuya çalışmalıyım?" → kendi konu listesi, en düşük skordan.
- **Eğitmen** — "sınıf nerede zorlanıyor?" → konu bazlı sınıf ortalaması, en çok
  yanlış yapılan sorular, kapsam dışı ret oranı.

İki ayrı uç var, tek bir role-göre-dallanan uç değil. Gerekçe Anayasa II: yetki
yol düzeyinde `CourseMemberDep`/`CourseInstructorDep` ile kurulursa, sınıf verisini
öğrenciye sızdırmak için birinin gövdedeki bir `if`'i unutması yetmez. Kendi üyelik
sorgumuzu yazmayız; deps.py zaten doğrusunu yapıyor ve RLS ikinci katman olarak
aynı oturumda devrededir.

Yanıt şemaları bu dosyada tanımlı, `app/schemas/assessment.py`'de değil: o dosya
paralel geliştirme sırasında Şerit 4'ün (soru/sınav uçları) elinde ve aynı dosyaya
iki elin dokunması tam da önlenmek istenen şey (00_OKU_ONCE §1).
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import Float, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CourseInstructorDep, CourseMemberDep, SessionDep
from app.models.assessment import Answer, Mastery, Question, Topic
from app.modules.mastery.service import MasteryLevel, level_for

router = APIRouter(prefix="/courses/{course_id}", tags=["analytics"])

#: Eğitmen görünümünde listelenecek azami "en çok yanlış yapılan soru" sayısı.
MISSED_QUESTION_LIMIT = 5


# ---------------------------------------------------------------------------
# Yanıt şemaları
# ---------------------------------------------------------------------------


class TopicProgress(BaseModel):
    """Öğrencinin tek bir konudaki durumu."""

    topic_id: UUID
    name: str
    #: 0-1 arası EWMA göstergesi (mastery/service.py).
    score: float
    #: Seviye sunucuda hesaplanır ki iki taraf aynı eşiği kullansın (FR-027:
    #: <0.40 Geliştirilmeli · 0.40-0.74 Orta · >=0.75 İyi). Aynı eşikler arayüzde
    #: `lib/labels.ts`'te de var; sayılar değişirse İKİSİ BİRDEN değişmeli.
    level: MasteryLevel
    answer_count: int


class StudentAnalytics(BaseModel):
    course_id: UUID
    #: En düşük skordan başlar: listenin tepesi "önce şuna bak" demektir.
    topics: list[TopicProgress]
    #: Takip edilen konu yoksa None — 0.0 döndürmek "her şeyde sıfırsın" demek olurdu.
    average_score: float | None
    tracked_topics: int
    #: Henüz hiç cevap verilmemiş konu sayısı. Bu konular `topics` listesine
    #: GİRMEZ: skoru olmayan bir konuyu 0.0 ile göstermek "Geliştirilmeli"
    #: etiketi üretir ve öğrenciye çalışmadığı bir konuda başarısız olduğunu
    #: söyler. Sayı olarak bildirilir, uydurma skorla değil.
    untracked_topics: int
    needs_work_topics: int
    answered_questions: int


class ClassTopicProgress(BaseModel):
    topic_id: UUID
    name: str
    average_score: float
    level: MasteryLevel
    student_count: int
    answer_count: int


class MissedQuestion(BaseModel):
    question_id: UUID
    topic_name: str
    stem: str
    wrong_rate: float
    #: Payda ayrıca döner: 1 cevaptan 1 yanlış da %100'dür ve payda görünmeden
    #: bu oran yanıltıcıdır (Anayasa III).
    graded_answer_count: int


class OutOfScopeStat(BaseModel):
    """Kapsam dışı ret istatistiği (SC-005).

    `source` alanı zorunlu: sayının nereden geldiği görünmeden sayı raporlanamaz.
    `chat_messages` tablosu (migration 0003, Şerit 3) henüz inmemişse alan
    `unavailable` döner ve oran None kalır — tahmin üretilmez.
    """

    source: Literal["chat_messages", "unavailable"]
    rate: float | None
    out_of_scope_count: int | None
    #: `insufficient_context` AYRI tutulur: "materyalde var olabilir ama kanıt zayıf"
    #: ile "bu ders bu konuyu hiç kapsamıyor" farklı şeylerdir ve SC-005 yalnız
    #: ikincisini ölçer (contracts.AnswerStatus).
    insufficient_context_count: int | None
    assistant_message_count: int | None
    note: str


class ClassAnalytics(BaseModel):
    course_id: UUID
    topics: list[ClassTopicProgress]
    missed_questions: list[MissedQuestion]
    average_score: float | None
    tracked_topics: int
    untracked_topics: int
    student_count: int
    answered_questions: int
    out_of_scope: OutOfScopeStat


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------


async def _course_topic_count(session: AsyncSession, course_id: UUID) -> int:
    result = await session.execute(
        select(func.count()).select_from(Topic).where(Topic.course_id == course_id)
    )
    return int(result.scalar_one())


_CHAT_MESSAGES_PROBE = text(
    """
    SELECT count(*) FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'chat_messages'
      AND column_name IN ('course_id', 'role', 'status')
    """
)

_OUT_OF_SCOPE_QUERY = text(
    """
    SELECT count(*) FILTER (WHERE status = 'out_of_scope')          AS out_of_scope,
           count(*) FILTER (WHERE status = 'insufficient_context')  AS insufficient_context,
           count(*)                                                 AS total
    FROM chat_messages
    WHERE course_id = :course_id AND role = 'assistant'
    """
)


async def _out_of_scope_stat(session: AsyncSession, course_id: UUID) -> OutOfScopeStat:
    """Kapsam dışı ret oranı — kaynağı yoksa sayı da yok.

    Tablo varlığı her istekte sorulur (tek ucuz katalog sorgusu) çünkü süreç ömrü
    boyunca önbelleğe alınırsa 0003 uygulandıktan sonra API yeniden başlatılana
    kadar "kaynak yok" demeye devam ederdi — ve bunu kimse fark etmezdi.
    """
    available = int((await session.execute(_CHAT_MESSAGES_PROBE)).scalar_one()) == 3
    if not available:
        return OutOfScopeStat(
            source="unavailable",
            rate=None,
            out_of_scope_count=None,
            insufficient_context_count=None,
            assistant_message_count=None,
            note=(
                "Sohbet kayıtları henüz bu ortamda yok (migration 0003). "
                "Kapsam dışı ret oranı ölçülmedi."
            ),
        )

    row = (await session.execute(_OUT_OF_SCOPE_QUERY, {"course_id": course_id})).one()
    out_of_scope, insufficient_context, total = int(row[0]), int(row[1]), int(row[2])
    return OutOfScopeStat(
        source="chat_messages",
        rate=(out_of_scope / total) if total else None,
        out_of_scope_count=out_of_scope,
        insufficient_context_count=insufficient_context,
        assistant_message_count=total,
        note=(
            "Oran, asistanın verdiği cevaplar içinde kapsam dışı diye reddedilenlerin "
            "payıdır. Kanıt yetersizliği (insufficient_context) bu orana girmez."
        )
        if total
        else "Bu derste henüz asistan cevabı yok; oran hesaplanamadı.",
    )


# ---------------------------------------------------------------------------
# Uçlar
# ---------------------------------------------------------------------------


@router.get("/analytics/me", response_model=StudentAnalytics)
async def my_progress(context: CourseMemberDep, session: SessionDep) -> StudentAnalytics:
    """Kendi konu bazlı ilerlemem. Dersin her üyesi kendi satırlarını görür.

    Bu gösterge resmî bir not DEĞİLDİR; nereye çalışılacağını gösteren bir öneridir
    (ARCHITECTURE §5). İbare arayüzde zorunludur.
    """
    result = await session.execute(
        select(Topic.id, Topic.name, Mastery.score, Mastery.answer_count)
        .join(Mastery, Mastery.topic_id == Topic.id)
        .where(Mastery.course_id == context.course_id, Mastery.user_id == context.user_id)
        .order_by(Mastery.score.asc(), Topic.name.asc())
    )
    topics = [
        TopicProgress(
            topic_id=row.id,
            name=row.name,
            score=row.score,
            level=level_for(row.score),
            answer_count=row.answer_count,
        )
        for row in result
    ]

    total_topics = await _course_topic_count(session, context.course_id)
    return StudentAnalytics(
        course_id=context.course_id,
        topics=topics,
        average_score=(sum(t.score for t in topics) / len(topics)) if topics else None,
        tracked_topics=len(topics),
        untracked_topics=max(0, total_topics - len(topics)),
        needs_work_topics=sum(1 for t in topics if t.level is MasteryLevel.NEEDS_WORK),
        answered_questions=sum(t.answer_count for t in topics),
    )


@router.get("/analytics/class", response_model=ClassAnalytics)
async def class_progress(
    context: CourseInstructorDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=20)] = MISSED_QUESTION_LIMIT,
) -> ClassAnalytics:
    """Sınıf analitiği. Yalnız dersin eğitmeni görebilir."""
    topic_rows = (
        await session.execute(
            select(
                Topic.id,
                Topic.name,
                func.avg(Mastery.score).label("average_score"),
                func.count(Mastery.user_id).label("student_count"),
                func.coalesce(func.sum(Mastery.answer_count), 0).label("answer_count"),
            )
            .join(Mastery, Mastery.topic_id == Topic.id)
            .where(Mastery.course_id == context.course_id)
            .group_by(Topic.id, Topic.name)
            .order_by(func.avg(Mastery.score).asc(), Topic.name.asc())
        )
    ).all()

    topics = [
        ClassTopicProgress(
            topic_id=row.id,
            name=row.name,
            average_score=float(row.average_score),
            level=level_for(float(row.average_score)),
            student_count=int(row.student_count),
            answer_count=int(row.answer_count),
        )
        for row in topic_rows
    ]

    # "Yanlış" = is_correct açıkça false. Henüz değerlendirilmemiş (NULL) cevaplar
    # PAYDAYA DA GİRMEZ: değerlendirilmemiş bir cevabı doğru saymak oranı düşürür,
    # yanlış saymak yükseltir; ikisi de ölçmediğimiz bir şeyi rapor etmek olur.
    graded = func.count(Answer.id).filter(Answer.is_correct.isnot(None))
    wrong = func.count(Answer.id).filter(Answer.is_correct.is_(False))
    wrong_rate = cast(wrong, Float) / cast(graded, Float)
    stem = func.coalesce(Question.payload["stem"].astext, Question.payload["prompt"].astext, "")

    missed_rows = (
        await session.execute(
            select(
                Question.id,
                Topic.name.label("topic_name"),
                stem.label("stem"),
                wrong_rate.label("wrong_rate"),
                graded.label("graded_answer_count"),
            )
            .select_from(Answer)
            .join(Question, Question.id == Answer.question_id)
            .join(Topic, Topic.id == Question.topic_id)
            .where(Answer.course_id == context.course_id)
            .group_by(Question.id, Topic.name, stem)
            .having(graded > 0)
            .order_by(wrong_rate.desc(), graded.desc())
            .limit(limit)
        )
    ).all()

    missed_questions = [
        MissedQuestion(
            question_id=row.id,
            topic_name=row.topic_name,
            stem=row.stem,
            wrong_rate=float(row.wrong_rate),
            graded_answer_count=int(row.graded_answer_count),
        )
        for row in missed_rows
    ]

    student_count = int(
        (
            await session.execute(
                select(func.count(func.distinct(Mastery.user_id))).where(
                    Mastery.course_id == context.course_id
                )
            )
        ).scalar_one()
    )
    answered_questions = int(
        (
            await session.execute(
                select(func.coalesce(func.sum(Mastery.answer_count), 0)).where(
                    Mastery.course_id == context.course_id
                )
            )
        ).scalar_one()
    )
    total_topics = await _course_topic_count(session, context.course_id)

    return ClassAnalytics(
        course_id=context.course_id,
        topics=topics,
        missed_questions=missed_questions,
        average_score=(sum(t.average_score for t in topics) / len(topics) if topics else None),
        tracked_topics=len(topics),
        untracked_topics=max(0, total_topics - len(topics)),
        student_count=student_count,
        answered_questions=answered_questions,
        out_of_scope=await _out_of_scope_stat(session, context.course_id),
    )
