"""Sınav provası uçları — T032.

Router `main.py`'ye ZATEN kayıtlı; bu dosya yalnız gövde ekler.

**Mod politikaları sunucuda zorlanır.** Frontend "exam modunda ipucu butonunu
gizlemek" ile yetinir; reddi buradan gelir (FR-017):

| | `exam` | `practice` |
|---|---|---|
| Süre | `EXAM_DURATION_MINUTES` | süresiz (`expires_at = NULL`) |
| İpucu | **403** | kaynaktan türetilmiş kademeli ipucu |
| Deneme | soru başına tek — ikincisi **409** | oturum başına yine tek, yeni oturum serbest |
| Geri bildirim | `/finish`'te | cevapla birlikte, anında |
| Mastery | bitişte, tüm cevaplarla | ilk cevapta, anında |

Üç zaman kuralı, ikisi güvenlik biri tutarlılık:

1. **Saat veritabanınındır.** Kalan süre her istekte `SELECT now()` ile okunur;
   ne istemci saati ne uygulama sunucusunun saati kullanılır.
2. **`expires_at` kırpılır.** Etkin bitiş `min(expires_at, started_at + süre)`'dir,
   yani satırdaki `expires_at` ileri atılsa bile süre uzamaz. Bu kırpma tek başına
   yeterli DEĞİLDİR: `started_at` de aynı politikayla yazılabildiği için ikisini
   birden değiştiren biri süreyi yine uzatabilir. Yapısal kapanış `0005`'teki
   kolon bazlı GRANT'e bağlıdır (KARARLAR_SERIT4.md Karar 2). Bugün API'de bu iki
   sütuna yazan hiçbir uç yoktur; sömürü doğrudan veritabanı erişimi ister.
3. **Puan `answers`'tan türetilir**, `exam_sessions.score`'dan okunmaz. `answers`
   write-once olduğu için öğrencinin dokunamayacağı tek kayıt odur (Karar 1).

Cevap satırı puanıyla birlikte yazılır ve bir daha güncellenmez; `exam` modunda
geri bildirim yazım anında değil, **gösterim anında** tutulur.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CourseContext, CourseMemberDep, SessionDep
from app.core.config import Settings, get_settings
from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.models.assessment import Answer, ExamMode, ExamSession, Question, QuestionStatus, Topic
from app.modules.assessment import question_gen
from app.modules.assessment.grading import (
    GradingOutcome,
    grade_answer,
    load_source_refs,
    score_of,
)
from app.modules.mastery.service import record_answer
from app.schemas.assessment import (
    AnswerFeedbackOut,
    AnswerSubmitRequest,
    ExamFinishOut,
    ExamQuestionOut,
    ExamSessionOut,
    ExamStartRequest,
    HintOut,
    HintRequest,
    SourceRefOut,
    public_payload,
    solution_payload,
)

router = APIRouter(prefix="/courses/{course_id}", tags=["exams"])


# ---------------------------------------------------------------------------
# Zaman
# ---------------------------------------------------------------------------


async def db_now(session: AsyncSession) -> datetime:
    """İşlemin veritabanı saati.

    İşlem içinde sabittir, dolayısıyla aynı istekte yapılan iki karşılaştırma
    (süre doldu mu / kalan kaç saniye) tutarlıdır.
    """
    value = await session.scalar(select(func.now()))
    if value is None:  # pragma: no cover - now() hiçbir zaman NULL dönmez
        raise RuntimeError("veritabanı saati okunamadı")
    return value


def effective_expiry(exam: ExamSession, *, settings: Settings) -> datetime | None:
    """Kırpılmış bitiş zamanı. practice modda None (süresiz)."""
    if exam.mode is ExamMode.PRACTICE:
        return None
    cap = exam.started_at + timedelta(minutes=settings.exam_duration_minutes)
    if exam.expires_at is None:  # pragma: no cover - CHECK kısıtı bunu engeller
        return cap
    return min(exam.expires_at, cap)


def _remaining_seconds(expiry: datetime | None, now: datetime) -> int | None:
    if expiry is None:
        return None
    return max(0, int((expiry - now).total_seconds()))


# ---------------------------------------------------------------------------
# Yükleme yardımcıları
# ---------------------------------------------------------------------------


async def _load_exam(
    session: AsyncSession, session_id: UUID, context: CourseContext
) -> ExamSession:
    """Oturumu yükler. Başkasının oturumu, varlığı sızdırılmadan 404 döner.

    Eğitmen RLS'te kendi dersinin oturumlarını okuyabilir (analitik için) ama bu
    uçlar öğrenci akışıdır: burada yalnız oturumun sahibi geçer.
    """
    exam = await session.get(ExamSession, session_id)
    if exam is None or exam.course_id != context.course_id or exam.user_id != context.user_id:
        raise NotFoundError("Sınav oturumu bulunamadı.")
    return exam


async def _load_questions(session: AsyncSession, question_ids: list[UUID]) -> dict[UUID, Question]:
    """Oturumun sorularını okur.

    Oturum açılırken sorular sabitlenir, ama sabitlenmiş bir soru sonradan
    reddedilirse RLS onu öğrenciye kapatır ve burada eksik döner. Bu bilinçlidir:
    puan zaten `answers` satırından gelir, yani kaybolan soru verilmiş bir cevabın
    puanını değiştirmez; yalnız çözümü gösterilemez.
    """
    if not question_ids:
        return {}
    rows = await session.execute(select(Question).where(Question.id.in_(question_ids)))
    return {question.id: question for question in rows.scalars()}


async def _answers_of(session: AsyncSession, session_id: UUID) -> list[Answer]:
    rows = await session.execute(
        select(Answer).where(Answer.session_id == session_id).order_by(Answer.answered_at)
    )
    return list(rows.scalars().all())


# ---------------------------------------------------------------------------
# Geri bildirim biçimleme
# ---------------------------------------------------------------------------


def _feedback_payload(outcome: GradingOutcome) -> dict[str, object]:
    """`answers.feedback` jsonb'si. Puan kendi sütununda; burada tekrarlanmaz."""
    return {
        "durum": "degerlendirildi" if outcome.graded else "tamamlanamadi",
        "eksik_noktalar": outcome.missing_points,
        "dayanak_chunk_id": str(outcome.evidence_chunk_id) if outcome.evidence_chunk_id else None,
        "neden_yanlis_chunk_id": (
            str(outcome.why_wrong_chunk_id) if outcome.why_wrong_chunk_id else None
        ),
        "mesaj": outcome.message,
        "odak": outcome.focus,
    }


def _chunk_id(feedback: dict[str, object] | None, key: str) -> UUID | None:
    raw = (feedback or {}).get(key)
    return UUID(str(raw)) if raw else None


def _answer_feedback(
    answer: Answer,
    *,
    question: Question | None,
    refs: dict[UUID, SourceRefOut],
    reveal: bool,
) -> AnswerFeedbackOut:
    """Kaydedilmiş cevabı gösterilebilir geri bildirime çevirir.

    `reveal=False` iken (sınav sürerken) puan da çözüm de gizlenir; kayıt yerinde
    durur, yalnız gösterilmez.
    """
    feedback = answer.feedback or {}
    graded = feedback.get("durum") != "tamamlanamadi"
    if not reveal:
        return AnswerFeedbackOut(
            question_id=answer.question_id,
            graded=graded,
            message=None if graded else str(feedback.get("mesaj") or ""),
        )

    why_wrong = _chunk_id(feedback, "neden_yanlis_chunk_id")
    evidence = _chunk_id(feedback, "dayanak_chunk_id")
    missing = feedback.get("eksik_noktalar")
    return AnswerFeedbackOut(
        question_id=answer.question_id,
        graded=graded,
        is_correct=answer.is_correct,
        score=answer.score,
        missing_points=[str(item) for item in missing] if isinstance(missing, list) else [],
        why_wrong=refs.get(why_wrong) if why_wrong else None,
        evidence=refs.get(evidence) if evidence else None,
        solution=solution_payload(question.type, question.payload) if question else None,
        message=str(feedback.get("mesaj")) if feedback.get("mesaj") else None,
    )


async def _session_out(
    session: AsyncSession, exam: ExamSession, *, settings: Settings, now: datetime
) -> ExamSessionOut:
    questions = await _load_questions(session, list(exam.question_ids))
    answers = await _answers_of(session, exam.id)
    answered = {answer.question_id for answer in answers}
    expiry = effective_expiry(exam, settings=settings)

    outcomes = [
        GradingOutcome(
            graded=(answer.feedback or {}).get("durum") != "tamamlanamadi",
            score=answer.score,
        )
        for answer in answers
    ]

    return ExamSessionOut(
        id=exam.id,
        course_id=exam.course_id,
        mode=exam.mode,
        started_at=exam.started_at,
        expires_at=expiry,
        remaining_seconds=_remaining_seconds(expiry, now),
        expired=expiry is not None and now >= expiry,
        finished_at=exam.finished_at,
        score=score_of(outcomes) if exam.finished_at else None,
        question_count=len(exam.question_ids),
        answered_count=len(answered),
        questions=[
            ExamQuestionOut(
                id=question_id,
                type=questions[question_id].type,
                payload=public_payload(questions[question_id].type, questions[question_id].payload),
                answered=question_id in answered,
            )
            for question_id in exam.question_ids
            if question_id in questions
        ],
    )


# ---------------------------------------------------------------------------
# Uçlar
# ---------------------------------------------------------------------------


@router.post("/exams", response_model=ExamSessionOut, status_code=status.HTTP_201_CREATED)
async def start_exam(
    payload: ExamStartRequest, context: CourseMemberDep, session: SessionDep
) -> ExamSessionOut:
    """Sınav ya da alıştırma oturumu açar.

    Onaylı havuz boşsa oturum açılmaz: "kaynak yoksa cevap yok"un sınav ayağıdır.
    Sorular burada sabitlenir; sonradan yapılan onay/red başlamış oturumun soru
    listesini değiştirmez.
    """
    settings = get_settings()

    if payload.topic_id is not None:
        topic = await session.get(Topic, payload.topic_id)
        if topic is None or topic.course_id != context.course_id:
            raise NotFoundError("Konu bulunamadı.")

    query = select(Question.id).where(
        Question.course_id == context.course_id,
        Question.status == QuestionStatus.APPROVED,
    )
    if payload.topic_id is not None:
        query = query.where(Question.topic_id == payload.topic_id)

    question_ids = list(
        (await session.execute(query.order_by(func.random()).limit(settings.exam_question_count)))
        .scalars()
        .all()
    )
    if not question_ids:
        raise ConflictError(
            "Bu derste henüz onaylanmış soru yok. Eğitmeniniz soruları onayladıktan "
            "sonra sınav provası başlatabilirsiniz."
        )

    now = await db_now(session)
    exam = ExamSession(
        course_id=context.course_id,
        user_id=context.user_id,
        mode=payload.mode,
        started_at=now,
        expires_at=(
            now + timedelta(minutes=settings.exam_duration_minutes)
            if payload.mode is ExamMode.EXAM
            else None
        ),
        question_ids=question_ids,
    )
    session.add(exam)
    await session.flush()

    return await _session_out(session, exam, settings=settings, now=now)


@router.get("/exams/{session_id}", response_model=ExamSessionOut)
async def get_exam(
    session_id: UUID, context: CourseMemberDep, session: SessionDep
) -> ExamSessionOut:
    """Oturum durumu ve **kalan süre**.

    Bağlantı koparsa öğrenci buraya döner ve kaldığı yerden devam eder: sayaç
    istemcide, süre sunucudadır.
    """
    settings = get_settings()
    exam = await _load_exam(session, session_id, context)
    return await _session_out(session, exam, settings=settings, now=await db_now(session))


@router.post(
    "/exams/{session_id}/answers",
    response_model=AnswerFeedbackOut,
    status_code=status.HTTP_201_CREATED,
)
async def submit_answer(
    session_id: UUID,
    payload: AnswerSubmitRequest,
    context: CourseMemberDep,
    session: SessionDep,
) -> AnswerFeedbackOut:
    """Cevabı kaydeder ve **aynı işlemde** puanlar.

    Puan cevapla birlikte yazılır çünkü `answers` satırı bir daha güncellenmez
    (Karar 1). `exam` modunda puan yazılır ama döndürülmez; `practice` modunda
    anında geri bildirim olarak döner.
    """
    settings = get_settings()
    exam = await _load_exam(session, session_id, context)
    now = await db_now(session)

    if exam.finished_at is not None:
        raise ConflictError("Bu oturum tamamlandı; yeni cevap kabul edilmiyor.")

    expiry = effective_expiry(exam, settings=settings)
    if expiry is not None and now >= expiry:
        raise ConflictError("Sınav süresi doldu; cevap kabul edilmiyor.")

    if payload.question_id not in exam.question_ids:
        raise NotFoundError("Bu soru bu sınav oturumunda yok.")

    if exam.mode is ExamMode.EXAM and payload.hint_level > 0:
        raise PermissionDeniedError("Sınav modunda ipucu kapalıdır.")

    existing = await session.scalar(
        select(Answer.id).where(
            Answer.session_id == exam.id, Answer.question_id == payload.question_id
        )
    )
    if existing is not None:
        raise ConflictError("Bu soruyu zaten cevapladınız; soru başına tek deneme hakkı var.")

    question = await session.get(Question, payload.question_id)
    if question is None:
        raise NotFoundError("Soru bulunamadı.")

    outcome = await grade_answer(
        session, question, payload.given, completion=question_gen.get_completion()
    )

    answer = Answer(
        session_id=exam.id,
        question_id=question.id,
        course_id=exam.course_id,
        given=payload.given,
        is_correct=outcome.is_correct,
        score=outcome.score,
        hint_level=payload.hint_level,
        feedback=_feedback_payload(outcome),
    )
    session.add(answer)
    try:
        await session.flush()
    except IntegrityError as exc:
        # UNIQUE (session_id, question_id): yukarıdaki kontrolle yarışan ikinci istek.
        raise ConflictError("Bu soruyu zaten cevapladınız.") from exc

    if exam.mode is ExamMode.PRACTICE and outcome.graded and outcome.score is not None:
        # FR-017: practice modda mastery ilk cevapta işlenir (bitişi beklemez).
        await record_answer(
            session,
            user_id=context.user_id,
            topic_id=question.topic_id,
            course_id=exam.course_id,
            raw_score=outcome.score,
            hint_level=payload.hint_level,
            alpha=settings.mastery_alpha,
        )

    reveal = exam.mode is ExamMode.PRACTICE
    refs = (
        await load_source_refs(
            session,
            [
                chunk_id
                for chunk_id in (outcome.why_wrong_chunk_id, outcome.evidence_chunk_id)
                if chunk_id is not None
            ],
            focus=outcome.focus,
        )
        if reveal
        else {}
    )
    return _answer_feedback(answer, question=question if reveal else None, refs=refs, reveal=reveal)


@router.post("/exams/{session_id}/hint", response_model=HintOut)
async def request_hint(
    session_id: UUID,
    payload: HintRequest,
    context: CourseMemberDep,
    session: SessionDep,
) -> HintOut:
    """Kademeli ipucu — yalnız `practice` modunda.

    İpucu metni **kaynaktan türetilir**, modelden değil: kademe yükseldikçe sorunun
    dayandığı chunk'tan daha çoğu açılır. Böylece ipucu her zaman gerçek bir
    materyal parçasına dayanır (Anayasa I) ve LLM ayakta olmasa da çalışır.
    """
    settings = get_settings()
    exam = await _load_exam(session, session_id, context)

    if exam.mode is ExamMode.EXAM:
        raise PermissionDeniedError(
            "Sınav modunda ipucu kapalıdır. İpucu almak için alıştırma modunda çalışabilirsiniz."
        )

    if exam.finished_at is not None:
        raise ConflictError("Bu oturum tamamlandı.")

    if payload.question_id not in exam.question_ids:
        raise NotFoundError("Bu soru bu sınav oturumunda yok.")

    question = await session.get(Question, payload.question_id)
    if question is None:
        raise NotFoundError("Soru bulunamadı.")

    refs = await load_source_refs(session, [question.source_chunk_id])
    source = refs.get(question.source_chunk_id)
    if source is None:
        raise NotFoundError("Bu sorunun kaynağı okunamadı; ipucu üretilemiyor.")

    level = min(payload.hint_level, settings.socratic_max_stage)
    return HintOut(
        question_id=question.id,
        hint_level=level,
        text=_hint_text(level, source),
        source=source,
    )


#: Kademe → kaynaktan açılacak oran. 1. kademe yalnız konumu söyler, 4. kademe
#: kaynaklı açıklamanın tamamını verir (Sokratik merdivenin ölçme ayağı).
_HINT_FRACTIONS: dict[int, float] = {1: 0.0, 2: 0.25, 3: 0.5, 4: 1.0}


def _hint_text(level: int, source: SourceRefOut) -> str:
    where = f"Bu sorunun dayandığı bölüm: {source.file_name} · {source.location}."
    fraction = _HINT_FRACTIONS.get(level, 0.0)
    if fraction <= 0:
        return f"{where} Önce oraya bakıp kendi cevabını dene."
    cut = max(60, int(len(source.snippet) * fraction))
    excerpt = source.snippet[:cut].rstrip()
    suffix = "" if cut >= len(source.snippet) else "…"
    return f"{where}\n\nKaynaktan: {excerpt}{suffix}"


@router.post("/exams/{session_id}/finish", response_model=ExamFinishOut)
async def finish_exam(
    session_id: UUID, context: CourseMemberDep, session: SessionDep
) -> ExamFinishOut:
    """Oturumu kapatır, puanı açıklar ve soru bazlı geri bildirimi verir (FR-018).

    Cevaplanmamış sorular **boş** sayılır: yanlış değildirler ve paydaya girmezler.
    Değerlendirilememiş cevaplar da paydaya girmez (FR-020) — uydurma puan yerine
    açık bir "değerlendirilemedi" sayısı raporlanır.
    """
    settings = get_settings()
    exam = await _load_exam(session, session_id, context)
    now = await db_now(session)

    if exam.finished_at is not None:
        raise ConflictError("Bu oturum zaten tamamlandı.")

    answers = await _answers_of(session, exam.id)
    questions = await _load_questions(session, [answer.question_id for answer in answers])

    outcomes = [
        GradingOutcome(
            graded=(answer.feedback or {}).get("durum") != "tamamlanamadi",
            score=answer.score,
        )
        for answer in answers
    ]
    total = score_of(outcomes)
    ungraded = sum(1 for outcome in outcomes if not outcome.graded)

    exam.finished_at = now
    exam.score = total
    await session.flush()

    if exam.mode is ExamMode.EXAM:
        # T037: sınav modunda mastery bitişte, tüm cevaplarla işlenir.
        for answer in answers:
            question = questions.get(answer.question_id)
            if question is None or answer.score is None:
                continue
            await record_answer(
                session,
                user_id=context.user_id,
                topic_id=question.topic_id,
                course_id=exam.course_id,
                raw_score=answer.score,
                hint_level=answer.hint_level,
                alpha=settings.mastery_alpha,
            )

    refs = await load_source_refs(
        session,
        [
            chunk_id
            for answer in answers
            for key in ("neden_yanlis_chunk_id", "dayanak_chunk_id")
            if (chunk_id := _chunk_id(answer.feedback, key)) is not None
        ],
    )

    unanswered = len(exam.question_ids) - len(answers)
    return ExamFinishOut(
        session_id=exam.id,
        score=total,
        answered_count=len(answers),
        unanswered_count=unanswered,
        ungraded_count=ungraded,
        message=_finish_message(
            answered=len(answers), unanswered=unanswered, ungraded=ungraded, score=total
        ),
        results=[
            _answer_feedback(
                answer, question=questions.get(answer.question_id), refs=refs, reveal=True
            )
            for answer in answers
        ],
    )


def _finish_message(*, answered: int, unanswered: int, ungraded: int, score: float | None) -> str:
    if score is None:
        return (
            "Hiçbir cevap değerlendirilemediği için puan hesaplanmadı. "
            "Boş bırakılan sorular yanlış sayılmaz."
        )
    parts = [f"{answered} soru cevaplandı."]
    if unanswered:
        parts.append(f"{unanswered} soru boş bırakıldı; boş sorular puana katılmaz.")
    if ungraded:
        parts.append(f"{ungraded} cevabın değerlendirmesi tamamlanamadı ve puana katılmadı.")
    return " ".join(parts)
