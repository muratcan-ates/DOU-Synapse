"""Soru ve konu (topic) uçları — T030.

İki katmanlı izolasyonun ölçme ayağı burada görünür hâle gelir: **öğrenci yalnız
`approved` soruları görür.** Bu kural iki kez zorlanır — uygulama katmanında
sorguya `status = 'approved'` eklenerek, veritabanı katmanında `questions_read`
politikasıyla. İki katmanın biri kaldırıldığında diğerinin hâlâ tuttuğu
`tests/test_assessment.py`'de kanıtlanır.

`payload` istemciye asla ham gitmez: eğitmen tam payload'ı görür (cevap anahtarını
görerek onaylar — FR-023), öğrenci `public_payload()` beyaz listesinden geçmiş
hâlini görür. Cevap anahtarı, çeldirici kaynakları ve rubrik öğrenciye gitmez.

Yetkilendirme daima `CourseMemberDep` / `CourseInstructorDep` ile yapılır; kendi
üyelik sorgusu yazılmaz (Anayasa II).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CourseContext, CourseInstructorDep, CourseMemberDep, SessionDep
from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.assessment import Question, QuestionStatus, QuestionType, Topic
from app.modules.assessment import question_gen
from app.modules.assessment.grading import load_source_refs
from app.schemas.assessment import (
    QuestionGenerateRequest,
    QuestionGenerationOut,
    QuestionOut,
    SourceRefOut,
    TopicCreate,
    TopicOut,
    public_payload,
)

router = APIRouter(prefix="/courses/{course_id}", tags=["assessment"])


# ---------------------------------------------------------------------------
# Konular
# ---------------------------------------------------------------------------


@router.post("/topics", response_model=TopicOut, status_code=status.HTTP_201_CREATED)
async def create_topic(
    payload: TopicCreate, context: CourseInstructorDep, session: SessionDep
) -> TopicOut:
    """Konu oluşturur. Yalnızca dersin eğitmeni oluşturabilir (FR-027)."""
    topic = Topic(
        course_id=context.course_id, name=payload.name.strip(), created_by=context.user_id
    )
    session.add(topic)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError(f"'{payload.name}' adlı bir konu bu derste zaten var.") from exc
    return TopicOut.model_validate(topic)


@router.get("/topics", response_model=list[TopicOut])
async def list_topics(context: CourseMemberDep, session: SessionDep) -> list[TopicOut]:
    """Konu listesi. Dersin tüm üyeleri (öğrenci + eğitmen) görebilir."""
    result = await session.execute(
        select(Topic).where(Topic.course_id == context.course_id).order_by(Topic.created_at)
    )
    return [TopicOut.model_validate(topic) for topic in result.scalars().all()]


# ---------------------------------------------------------------------------
# Soru havuzu
# ---------------------------------------------------------------------------


async def _question_out(
    session: AsyncSession, question: Question, *, context: CourseContext
) -> QuestionOut:
    """Tek soruyu rolüne göre biçimler. Liste ucu toplu sürümü kullanır."""
    refs = await load_source_refs(session, [question.source_chunk_id])
    return _build_out(question, context=context, source=refs.get(question.source_chunk_id))


def _build_out(
    question: Question, *, context: CourseContext, source: SourceRefOut | None
) -> QuestionOut:
    payload = (
        question.payload
        if context.is_instructor
        else public_payload(question.type, question.payload)
    )
    return QuestionOut(
        id=question.id,
        course_id=question.course_id,
        topic_id=question.topic_id,
        type=question.type,
        payload=payload,
        status=question.status,
        created_by=question.created_by,
        reviewed_by=question.reviewed_by,
        reviewed_at=question.reviewed_at,
        created_at=question.created_at,
        source=source,
    )


async def _load_question(session: AsyncSession, question_id: UUID, course_id: UUID) -> Question:
    """Soruyu yükler; başka dersin sorusu ise varlığını sızdırmadan 404 döner."""
    question = await session.get(Question, question_id)
    if question is None or question.course_id != course_id:
        raise NotFoundError("Soru bulunamadı.")
    return question


@router.get("/questions", response_model=list[QuestionOut])
async def list_questions(
    context: CourseMemberDep,
    session: SessionDep,
    status_filter: Annotated[QuestionStatus | None, Query(alias="status")] = None,
    topic_id: Annotated[UUID | None, Query()] = None,
) -> list[QuestionOut]:
    """Soru havuzu.

    Öğrenci için `status` parametresi **ne gelirse gelsin** `approved`'a sabitlenir;
    eğitmen isterse duruma göre süzer. RLS ikinci katman olarak zaten kapatır, ama
    uygulama katmanı da kapatır — iki katmanlı izolasyon tam olarak budur.
    """
    query = select(Question).where(Question.course_id == context.course_id)

    if context.is_instructor:
        if status_filter is not None:
            query = query.where(Question.status == status_filter)
    else:
        query = query.where(Question.status == QuestionStatus.APPROVED)

    if topic_id is not None:
        query = query.where(Question.topic_id == topic_id)

    questions = list(
        (await session.execute(query.order_by(Question.created_at.desc()))).scalars().all()
    )
    refs = await load_source_refs(session, [question.source_chunk_id for question in questions])
    return [
        _build_out(question, context=context, source=refs.get(question.source_chunk_id))
        for question in questions
    ]


@router.post("/questions/generate", response_model=QuestionGenerationOut)
async def generate_questions(
    payload: QuestionGenerateRequest, context: CourseInstructorDep, session: SessionDep
) -> QuestionGenerationOut:
    """Materyalden soru üretir. Üretilen her soru `draft`'tır (FR-023).

    Eğitmen çerçeveyi kurar: konu, tip, biçim ve isterse örnek sorular. Sistem o
    üslupta üretir ama onay vermez — bu uçtan `approved` çıkmaz.

    Yanıt `201` değil `200`: bu uç N kaynak yaratan bir toplu iştir ve kaçının
    yazıldığı gövdedeki raporda durur. Hiçbiri şemadan geçmediğinde `201 Created`
    dönmek, yaratılmamış bir şeyi yaratıldı diye bildirmek olurdu.
    """
    settings = get_settings()

    topic = await session.get(Topic, payload.topic_id)
    if topic is None or topic.course_id != context.course_id:
        raise NotFoundError("Konu bulunamadı.")

    if payload.answer_format is not None and payload.question_type is not QuestionType.OPEN:
        raise ValidationError("answer_format yalnızca 'open' tipi sorular için verilebilir.")

    report = await question_gen.generate_questions(
        session,
        course_id=context.course_id,
        topic=topic,
        question_type=payload.question_type,
        count=payload.count or settings.question_generation_batch,
        created_by=context.user_id,
        retriever=question_gen.resolve_retriever(session),
        completion=question_gen.resolve_completion(),
        answer_format=payload.answer_format,
        example_questions=payload.example_questions,
        retrieval_limit=settings.retrieval_top_k,
    )

    refs = await load_source_refs(
        session, [question.source_chunk_id for question in report.questions]
    )
    return QuestionGenerationOut(
        requested=report.requested,
        returned=report.returned,
        accepted=report.accepted,
        rejected=report.rejected,
        rejection_reasons=report.rejection_reasons,
        questions=[
            _build_out(question, context=context, source=refs.get(question.source_chunk_id))
            for question in report.questions
        ],
    )


async def _review(
    session: AsyncSession,
    context: CourseContext,
    question_id: UUID,
    new_status: QuestionStatus,
) -> QuestionOut:
    """Onay ve red aynı işi yapar; ayrı yazmak iki kopya demek olurdu (Anayasa XI).

    `questions_reviewed_consistency` CHECK'i `reviewed_by` ve `reviewed_at`'in
    ikisini birden ister; ikisi de burada, tek yerde yazılır.
    """
    question = await _load_question(session, question_id, context.course_id)
    question.status = new_status
    question.reviewed_by = context.user_id
    # Zaman damgası veritabanı saatinden: incelemeler farklı sunucu saatleriyle
    # sıralanamaz hâle gelmesin.
    question.reviewed_at = func.now()
    await session.flush()
    await session.refresh(question)
    return await _question_out(session, question, context=context)


@router.post("/questions/{question_id}/approve", response_model=QuestionOut)
async def approve_question(
    question_id: UUID, context: CourseInstructorDep, session: SessionDep
) -> QuestionOut:
    """Soruyu onaylar; ancak bundan sonra öğrenciye görünür."""
    return await _review(session, context, question_id, QuestionStatus.APPROVED)


@router.post("/questions/{question_id}/reject", response_model=QuestionOut)
async def reject_question(
    question_id: UUID, context: CourseInstructorDep, session: SessionDep
) -> QuestionOut:
    """Soruyu reddeder. Kayıt silinmez: havuzun neyi elediği de bir veridir."""
    return await _review(session, context, question_id, QuestionStatus.REJECTED)
