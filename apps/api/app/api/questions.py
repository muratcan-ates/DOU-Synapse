"""Soru ve konu (topic) uçları — T030.

İki katmanlı izolasyonun ölçme ayağı burada görünür hâle gelir: soru bankası
yalnız eğitmene açıktır. Öğrenci onaylı practice sorularını dahi toplu listelemez;
onlara yalnız sunucunun kurduğu practice kâğıdı üzerinden ulaşır. Resmî assessment
sorusu ise RLS'te ayrıca öğrencinin kendi dondurulmuş sınav kâğıdına bağlanır.

`payload` istemciye asla ham gitmez: eğitmen tam payload'ı görür (cevap anahtarını
görerek onaylar — FR-023), öğrenci `public_payload()` beyaz listesinden geçmiş
hâlini görür. Cevap anahtarı, çeldirici kaynakları ve rubrik öğrenciye gitmez.

Yetkilendirme daima `CourseMemberDep` / `CourseInstructorDep` ile yapılır; kendi
üyelik sorgusu yazılmaz (Anayasa II).
"""

from __future__ import annotations

import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CourseContext,
    CourseInstructorDep,
    CourseMemberDep,
    PageDep,
    SessionDep,
)
from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, RateLimitError, ValidationError
from app.core.pagination import paginate
from app.core.rate_limit import get_concurrency_gate, get_limiter
from app.models.assessment import (
    LearningOutcome,
    Question,
    QuestionPurpose,
    QuestionStatus,
    QuestionType,
    Topic,
)
from app.models.core import Chunk, Document
from app.modules.assessment import question_gen
from app.modules.assessment.grading import load_source_refs
from app.modules.generation.llm import LlmTask
from app.schemas.assessment import (
    QuestionClassificationRequest,
    QuestionGenerateRequest,
    QuestionGenerationOut,
    QuestionOut,
    SourceRefOut,
    TopicCreate,
    TopicOut,
    public_payload,
)
from app.schemas.page import PageOut

router = APIRouter(prefix="/courses/{course_id}", tags=["assessment"])

#: Sayaç kapsamı. Sınırlayıcı `api/chat.py` ile PAYLAŞILIYOR ve iki ucun doğal
#: anahtarı da `kullanıcı:ders`; kapsam olmasaydı sohbet etmek soru üretim
#: kotasını sessizce tüketirdi (`core/rate_limit.py`).
QUESTION_GEN_SCOPE = "qgen"


def _bekleme_metni(saniye: float) -> str:
    """Kalan süreyi kullanıcıya okunur biçimde yazar.

    YUKARI yuvarlanıyor: 4,2 saniye kaldığında "4 saniye" demek, kullanıcıyı
    hâlâ reddedilecek bir denemeye yollamak olurdu.

    Sayı hata METNİNE giriyor, ayrı bir alana değil: hata zarfı
    `{code, message, request_id}` olarak sabittir (lider sözleşmesi) ve
    `Retry-After` başlığı `expose_headers` olmadan çapraz-origin JavaScript'e
    görünmüyor — `core/errors.py` aynı gerekçeyi istek kimliği için zaten
    yazmış. Arayüz backend'in mesajını olduğu gibi gösteriyor (`lib/api.ts`),
    yani bilgi kullanıcıya ulaşıyor.
    """
    kalan = max(1, math.ceil(saniye))
    if kalan < 60:
        return f"{kalan} saniye"
    return f"{math.ceil(kalan / 60)} dakika"


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
async def list_topics(
    context: CourseMemberDep,
    session: SessionDep,
) -> list[TopicOut]:
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
    stale = await _source_stale_map(session, [question.source_chunk_id])
    return _build_out(
        question,
        context=context,
        source=refs.get(question.source_chunk_id),
        source_stale=stale.get(question.source_chunk_id, False),
    )


async def _source_stale_map(session: AsyncSession, chunk_ids: list[UUID]) -> dict[UUID, bool]:
    """Kaynak belgesi açıkça yeni sürümle değiştirilmiş chunk'ları toplu bulur."""
    if not chunk_ids:
        return {}
    rows = await session.execute(
        select(Chunk.id, Document.superseded_at)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.id.in_(set(chunk_ids)))
    )
    return {chunk_id: superseded_at is not None for chunk_id, superseded_at in rows}


def _build_out(
    question: Question,
    *,
    context: CourseContext,
    source: SourceRefOut | None,
    source_stale: bool,
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
        purpose=question.purpose,
        created_by=question.created_by,
        reviewed_by=question.reviewed_by,
        reviewed_at=question.reviewed_at,
        created_at=question.created_at,
        source=source,
        source_stale=source_stale,
        learning_outcome_id=question.learning_outcome_id,
        difficulty=question.difficulty,
    )


async def _load_question(session: AsyncSession, question_id: UUID, course_id: UUID) -> Question:
    """Soruyu yükler; başka dersin sorusu ise varlığını sızdırmadan 404 döner."""
    question = await session.get(Question, question_id)
    if question is None or question.course_id != course_id:
        raise NotFoundError("Soru bulunamadı.")
    return question


@router.get("/questions", response_model=PageOut[QuestionOut])
async def list_questions(
    context: CourseInstructorDep,
    session: SessionDep,
    page: PageDep,
    status_filter: Annotated[QuestionStatus | None, Query(alias="status")] = None,
    purpose_filter: Annotated[QuestionPurpose | None, Query(alias="purpose")] = None,
    topic_id: Annotated[UUID | None, Query()] = None,
) -> PageOut[QuestionOut]:
    """Eğitmenin soru havuzu; öğrenciye toplu extraction yüzeyi açılmaz."""
    query = select(Question).where(Question.course_id == context.course_id)

    if status_filter is not None:
        query = query.where(Question.status == status_filter)
    if purpose_filter is not None:
        query = query.where(Question.purpose == purpose_filter)

    if topic_id is not None:
        query = query.where(Question.topic_id == topic_id)

    result = await paginate(session, query, model=Question, page=page)
    visible = result.rows
    refs = await load_source_refs(session, [question.source_chunk_id for question in visible])
    stale = await _source_stale_map(session, [question.source_chunk_id for question in visible])
    items = [
        _build_out(
            question,
            context=context,
            source=refs.get(question.source_chunk_id),
            source_stale=stale.get(question.source_chunk_id, False),
        )
        for question in visible
    ]
    return PageOut(items=items, next_cursor=result.next_cursor)


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

    # İki kapı da gövdenin İLK işi (FR-222): sınıra takılan bir istek hiçbir iş
    # yapmamalı — ne konu doğrulaması, ne retrieval, ne LLM turu. Kapı üretim
    # başladıktan sonra kapansaydı maliyet zaten ödenmiş olurdu.
    #
    # Sıra bilinçli: önce eşzamanlılık, sonra kota. Tersi olsaydı eşzamanlılığa
    # takılan istek hiç iş yapmadığı hâlde bir kota hakkı yakardı.
    #
    # İki kapının ANAHTARLARI farklı ve bu bir tutarsızlık değil. Kota
    # `kullanıcı:ders` — bir öğretmenin iki dersteki kullanımı ayrı ölçülür.
    # Eşzamanlılık yalnız `kullanıcı`: sınırın gerekçesi maliyet değil
    # tutarlılık, ve karışan şey öğretmenin kendi dikkati (`config.py`).
    gate = get_concurrency_gate()
    limiter = get_limiter()
    kota_anahtari = f"{context.user_id}:{context.course_id}"

    with gate.hold(
        QUESTION_GEN_SCOPE,
        str(context.user_id),
        limit=settings.question_gen_max_concurrent,
        message=(
            "Başlattığın bir soru üretimi hâlâ sürüyor. O tamamlandığında yenisini başlatabilirsin."
        ),
    ):
        if not limiter.allow(
            QUESTION_GEN_SCOPE,
            kota_anahtari,
            limit=settings.question_gen_rate_limit_requests,
            window_seconds=settings.question_gen_rate_limit_window_seconds,
        ):
            bekleme = limiter.retry_after(
                QUESTION_GEN_SCOPE,
                kota_anahtari,
                window_seconds=settings.question_gen_rate_limit_window_seconds,
            )
            raise RateLimitError(
                f"Soru üretimi kotan doldu. {_bekleme_metni(bekleme)} sonra tekrar deneyebilirsin."
            )

        topic = await session.get(Topic, payload.topic_id)
        if topic is None or topic.course_id != context.course_id:
            raise NotFoundError("Konu bulunamadı.")

        if payload.answer_format is not None and payload.question_type is not QuestionType.OPEN:
            raise ValidationError("answer_format yalnızca 'open' tipi sorular için verilebilir.")

        learning_outcome: LearningOutcome | None = None
        if payload.learning_outcome_id is not None:
            learning_outcome = await session.get(LearningOutcome, payload.learning_outcome_id)
            if learning_outcome is None or learning_outcome.course_id != context.course_id:
                raise NotFoundError("Öğrenme çıktısı bulunamadı.")
            if learning_outcome.topic_id not in (None, topic.id):
                raise ValidationError(
                    "Seçilen öğrenme çıktısı bu konuya bağlı değil. "
                    "Önce çıktıyı doğru konuya bağlayın."
                )

        report = await question_gen.generate_questions(
            session,
            course_id=context.course_id,
            topic=topic,
            question_type=payload.question_type,
            count=payload.count or settings.question_generation_batch,
            created_by=context.user_id,
            retriever=question_gen.resolve_retriever(session),
            completion=question_gen.resolve_completion(LlmTask.QUESTION_GEN),
            answer_format=payload.answer_format,
            example_questions=payload.example_questions,
            retrieval_limit=settings.retrieval_top_k,
            learning_outcome=learning_outcome,
            difficulty=payload.difficulty,
            purpose=payload.purpose,
        )

        refs = await load_source_refs(
            session, [question.source_chunk_id for question in report.questions]
        )
        stale = await _source_stale_map(
            session, [question.source_chunk_id for question in report.questions]
        )
        return QuestionGenerationOut(
            requested=report.requested,
            returned=report.returned,
            accepted=report.accepted,
            rejected=report.rejected,
            rejection_reasons=report.rejection_reasons,
            questions=[
                _build_out(
                    question,
                    context=context,
                    source=refs.get(question.source_chunk_id),
                    source_stale=stale.get(question.source_chunk_id, False),
                )
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
    if question.status is not QuestionStatus.DRAFT:
        raise ConflictError(
            "İncelenmiş bir soru değiştirilemez. İçerik veya karar değişikliği için "
            "yeni bir taslak üretin; yayınlanmış sınav kâğıtları sabit kalır.",
            code="question_immutable",
        )
    if (
        new_status is QuestionStatus.APPROVED
        and question.purpose is QuestionPurpose.ASSESSMENT
        and (question.learning_outcome_id is None or question.difficulty is None)
    ):
        raise ConflictError(
            "Resmî sınav sorusu onaylanmadan önce öğrenme çıktısı ve zorluk "
            "sınıflandırması tamamlanmalıdır.",
            code="question_classification_required",
        )
    question.status = new_status
    question.reviewed_by = context.user_id
    # Zaman damgası veritabanı saatinden: incelemeler farklı sunucu saatleriyle
    # sıralanamaz hâle gelmesin.
    question.reviewed_at = func.now()
    await session.flush()
    await session.refresh(question)
    return await _question_out(session, question, context=context)


@router.patch(
    "/questions/{question_id}/classification",
    response_model=QuestionOut,
)
async def classify_question(
    question_id: UUID,
    payload: QuestionClassificationRequest,
    context: CourseInstructorDep,
    session: SessionDep,
) -> QuestionOut:
    """Taslak soruyu bir öğrenme çıktısı ve zorluk hücresine bağlar.

    Soru gövdesi, cevap, kaynak, tip ve purpose bu uçta yoktur. İncelenmiş bir
    sorunun sınıflandırmasını değiştirmek yayınlanmış kâğıt hücresini geriye dönük
    oynatacağından hem uygulama hem RLS/trigger katmanında kapalıdır.
    """

    question = await _load_question(session, question_id, context.course_id)
    if question.status is not QuestionStatus.DRAFT:
        raise ConflictError(
            "İncelenmiş bir sorunun sınıflandırması değiştirilemez. "
            "Yeni sınıflandırma için yeni bir taslak üretin.",
            code="question_immutable",
        )

    learning_outcome = await session.get(LearningOutcome, payload.learning_outcome_id)
    if learning_outcome is None or learning_outcome.course_id != context.course_id:
        raise NotFoundError("Öğrenme çıktısı bulunamadı.")
    if learning_outcome.topic_id not in (None, question.topic_id):
        raise ValidationError(
            "Seçilen öğrenme çıktısı bu sorunun konusuna bağlı değil. "
            "Önce çıktıyı doğru konuya bağlayın."
        )

    question.learning_outcome_id = learning_outcome.id
    question.difficulty = payload.difficulty
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


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    question_id: UUID, context: CourseInstructorDep, session: SessionDep
) -> None:
    """Soruyu havuzdan tamamen siler. Reddetmekten FARKLI bir iş.

    Reddetmek pedagojik bir karardır: soru öğrenciye görünmez ama satır durur ve
    "havuzun neyi elediği" ölçülebilir kalır. Silmek yapısal bir işlemdir ve tek
    bir gerçek ihtiyaçtan doğuyor: `questions.source_chunk_id` `ON DELETE RESTRICT`
    taşıyor, yani bir belgeden üretilmiş soru havuzda durduğu sürece o BELGE
    silinemiyor.

    Bu uç olmadan `documents.py`'nin 409 mesajı ("Önce ilgili soruları kaldırın")
    var olmayan bir çıkış yolunu tarif ediyordu — yapılamayacak bir şeyi öneren
    hata mesajı, hiç mesaj vermemekten kötüdür.

    Cevaplanmış soru silinmez: `answers.question_id` de RESTRICT taşır ve bir
    öğrencinin verdiği cevabın sorusunu silmek, o cevabı okunamaz hâle getirirdi.
    Veritabanı bunu zaten reddediyor; burada hata anlaşılır Türkçeye çevriliyor.
    """
    question = await _load_question(session, question_id, context.course_id)
    await session.delete(question)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "Bu soru bir sınavda cevaplanmış, bu yüzden silinemiyor. "
            "Öğrencilere görünmesini istemiyorsanız reddedebilirsiniz."
        ) from exc
