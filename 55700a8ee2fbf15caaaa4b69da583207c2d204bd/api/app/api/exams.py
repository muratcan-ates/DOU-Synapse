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

from app.api.deps import CourseContext, CourseMemberDep, SessionDep, SettingsDep
from app.core.config import Settings, get_settings
from app.core.db import db_now
from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.models.assessment import (
    Answer,
    ExamBlueprint,
    ExamMode,
    ExamSession,
    ExamVersion,
    ExamVersionStatus,
    Question,
    QuestionStatus,
    Topic,
)
from app.modules.assessment.exam_paper import paper_question_ids
from app.modules.assessment.exam_state import effective_expiry, remaining_seconds
from app.modules.assessment.grading import (
    GradingOutcome,
    SourceMaterial,
    grade_answer,
    load_source_material,
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


# Zaman yardımcıları `app/modules/assessment/exam_state.py`'ye taşındı: aynı süre
# kuralına asistan kilidi de (`api/deps.py`) ihtiyaç duyuyor ve `deps.py`'nin bu
# dosyayı içe aktarması döngü olurdu. Yukarıdaki üç zaman kuralından ikincisinin
# (kırpma) gerekçesi artık orada yaşıyor.


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
    sources: dict[UUID, SourceMaterial],
    reveal: bool,
) -> AnswerFeedbackOut:
    """Kaydedilmiş cevabı gösterilebilir geri bildirime çevirir.

    `reveal=False` iken (sınav sürerken) puan da çözüm de gizlenir; kayıt yerinde
    durur, yalnız gösterilmez.

    Alıntı, cevabın kendi **odağıyla** üretilir: aynı chunk iki öğrenciye farklı
    çeldiriciler yüzünden gösteriliyorsa her biri kendi seçimiyle çelişen cümleyi
    görür. Malzeme toplu okunduğu için bu ek sorgu maliyeti getirmez.
    """
    feedback = answer.feedback or {}
    graded = feedback.get("durum") != "tamamlanamadi"
    if not reveal:
        return AnswerFeedbackOut(
            question_id=answer.question_id,
            graded=graded,
            message=None if graded else str(feedback.get("mesaj") or ""),
        )

    focus = str(feedback["odak"]) if feedback.get("odak") else None
    why_wrong = _chunk_id(feedback, "neden_yanlis_chunk_id")
    evidence = _chunk_id(feedback, "dayanak_chunk_id")
    missing = feedback.get("eksik_noktalar")

    def reference(chunk_id: UUID | None) -> SourceRefOut | None:
        material = sources.get(chunk_id) if chunk_id else None
        return material.reference(focus=focus) if material else None

    return AnswerFeedbackOut(
        question_id=answer.question_id,
        graded=graded,
        is_correct=answer.is_correct,
        score=answer.score,
        missing_points=[str(item) for item in missing] if isinstance(missing, list) else [],
        why_wrong=reference(why_wrong),
        evidence=reference(evidence),
        solution=solution_payload(question.type, question.payload) if question else None,
        message=str(feedback.get("mesaj")) if feedback.get("mesaj") else None,
    )


async def _session_out(
    session: AsyncSession,
    exam: ExamSession,
    *,
    settings: Settings,
    now: datetime,
    with_questions: bool = True,
) -> ExamSessionOut:
    """Oturumu istemci zarfına çevirir.

    `with_questions=False` yalnız liste ucunda kullanılır: orada soru metinleri
    gerekmiyor ve N oturum için N soru sorgusu koşturmanın da anlamı yok.
    """
    paper = await paper_question_ids(session, exam)
    questions = await _load_questions(session, paper) if with_questions else {}
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
        remaining_seconds=remaining_seconds(expiry, now),
        expired=expiry is not None and now >= expiry,
        finished_at=exam.finished_at,
        score=score_of(outcomes) if exam.finished_at else None,
        question_count=len(paper),
        answered_count=len(answered),
        exam_version_id=exam.exam_version_id,
        exam_blueprint_id=exam.exam_blueprint_id,
        attempt_no=exam.attempt_no,
        questions=[
            ExamQuestionOut(
                id=question_id,
                type=questions[question_id].type,
                payload=public_payload(questions[question_id].type, questions[question_id].payload),
                answered=question_id in answered,
            )
            for question_id in paper
            if question_id in questions
        ],
    )


# ---------------------------------------------------------------------------
# Uçlar
# ---------------------------------------------------------------------------


async def _start_blueprint_exam(
    blueprint_id: UUID,
    context: CourseContext,
    session: AsyncSession,
    settings: Settings,
) -> ExamSessionOut:
    """Yayınlanmış bir sınava oturum açar (FR-115, FR-116).

    Üç kapı da burada Türkçe konuşur; hepsinin veritabanı tarafında ikinci bir
    katmanı var ve iki katman bağımsız olarak doğru davranmalı (Anayasa II):

    - **Görünürlük.** Öğrenci yayınlanmamış bir blueprint'i `exam_blueprints_read`
      politikası yüzünden zaten göremez; burada 404 döner ve varlığı sızmaz.
    - **Yayın penceresi.** `exam_sessions_self_insert` politikası
      `app.is_exam_open(...)` çağırıyor, yani pencere kapalıyken INSERT'i
      veritabanı da reddeder. Buradaki kontrol yalnız anlaşılır bir cümle
      kurabilmek için var — politika ihlali kısıt adıyla döner (Anayasa V).
    - **Deneme hakkı.** Sayım burada yapılır, yarış `exam_sessions_attempt_key`
      tekil indeksiyle kapanır ve ikinci eşzamanlı istek 409'a çevrilir.

    Süre blueprint'in kendi `duration_minutes`'ıdır; global `exam_duration_minutes`
    bundan sonra yalnız prova akışının varsayılanıdır.
    """
    blueprint = await session.get(ExamBlueprint, blueprint_id)
    if blueprint is None or blueprint.course_id != context.course_id:
        raise NotFoundError("Sınav bulunamadı.")

    version = await session.scalar(
        select(ExamVersion).where(
            ExamVersion.blueprint_id == blueprint.id,
            ExamVersion.status == ExamVersionStatus.PUBLISHED,
        )
    )
    if version is None:
        raise ConflictError("Bu sınav henüz yayınlanmadı.")

    now = await db_now(session)
    if blueprint.opens_at is not None and now < blueprint.opens_at:
        raise ConflictError("Bu sınav henüz açılmadı; yayın penceresi başlamadan girilemez.")
    if blueprint.closes_at is not None and now >= blueprint.closes_at:
        raise ConflictError("Bu sınavın süresi doldu; yeni oturum başlatılamaz.")

    used = await session.scalar(
        select(func.count(ExamSession.id)).where(
            ExamSession.exam_blueprint_id == blueprint.id,
            ExamSession.user_id == context.user_id,
        )
    )
    used = int(used or 0)
    if used >= blueprint.max_attempts:
        raise ConflictError(
            f"Bu sınav için {blueprint.max_attempts} deneme hakkınız vardı ve hepsini kullandınız."
        )

    exam = ExamSession(
        course_id=context.course_id,
        user_id=context.user_id,
        mode=ExamMode.EXAM,
        started_at=now,
        expires_at=now + timedelta(minutes=blueprint.duration_minutes),
        # Kâğıt `exam_items`'tan okunur; iki kaynak birden yazılamaz.
        question_ids=None,
        exam_version_id=version.id,
        exam_blueprint_id=blueprint.id,
        attempt_no=used + 1,
    )
    session.add(exam)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "Bu sınav için başka bir oturum aynı anda başlatıldı; sayfayı yenileyin."
        ) from exc

    return await _session_out(session, exam, settings=settings, now=now)


@router.post("/exams", response_model=ExamSessionOut, status_code=status.HTTP_201_CREATED)
async def start_exam(
    payload: ExamStartRequest, context: CourseMemberDep, session: SessionDep
) -> ExamSessionOut:
    """Sınav ya da alıştırma oturumu açar.

    İki akış var ve ayrımı `blueprint_id` yapar:

    - **Prova (bugünkü akış).** Onaylı havuzdan rastgele soru çekilir ve oturumun
      `question_ids`'ine sabitlenir. Onaylı havuz boşsa oturum açılmaz: "kaynak
      yoksa cevap yok"un sınav ayağıdır.
    - **Blueprint sınavı (0008).** Kâğıt yayınlanmış sürümün `exam_items`'ından
      gelir; `question_ids` NULL kalır ve oturum `exam_version_id` ile o sürüme
      bağlanır. Sonradan yeni sürüm yayınlanması başlamış oturumu değiştirmez.

    İki akış aynı satırda karışamaz: `exam_sessions_paper_source` kısıtı kâğıdın
    iki kaynağı olmasını ifade edilemez kılıyor.
    """
    settings = get_settings()

    if payload.blueprint_id is not None:
        return await _start_blueprint_exam(payload.blueprint_id, context, session, settings)

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


@router.get("/exams", response_model=list[ExamSessionOut])
async def list_exams(context: CourseMemberDep, session: SessionDep) -> list[ExamSessionOut]:
    """Kullanıcının bu dersteki sınav oturumları, en yenisi başta.

    Neden gerekli: oturum kimliği yalnız istemcide tutulduğunda kaybolabiliyordu —
    tarayıcı verisi temizlenince ya da başka bir cihazdan girilince öğrenci devam
    eden sınavına DÖNEMİYORDU. Aynı boşluk ters yönde de açıktı: dönemeyen öğrenci
    yeni bir oturum açıp süreyi baştan alabiliyordu, yani süre sınırı istemcinin
    hafızasına bağlı kalıyordu. Süre sunucunun kararıysa (ve öyle), oturumu bulmak
    da sunucunun işi olmalı.

    Şerit 4 bunu görüp bilerek genişletmedi: brief yalnız `GET .../{session_id}`
    diyordu ve şeridin dışına taşmamak doğru karardı. Karar liderindi, bu.

    RLS başkasının oturumunu zaten göstermez; ders eşleşmesi ayrıca `WHERE` ile
    kontrol edilir — iki katman da bağımsız olarak doğru davranmalı (Anayasa II).

    Sorular gövdede TAŞINMAZ. Liste "hangi oturumlarım var" sorusunu cevaplar;
    soru metinlerini taşımak, bitmemiş bir sınavın sorularını tek listede dışarı
    vermek olurdu ve ekranın bu bilgiye ihtiyacı yok.
    """
    settings = get_settings()
    now = await db_now(session)
    rows = (
        await session.execute(
            select(ExamSession)
            .where(ExamSession.course_id == context.course_id)
            .order_by(ExamSession.started_at.desc())
        )
    ).scalars()
    return [
        await _session_out(session, exam, settings=settings, now=now, with_questions=False)
        for exam in rows
    ]


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

    if payload.question_id not in await paper_question_ids(session, exam):
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

    # Sağlayıcı burada çözümlenmez: MCQ ve kısa cevap LLM'siz puanlanır ve
    # sağlayıcı arızası sınavı düşürmemeli (grading.grade_answer, FR-020).
    outcome = await grade_answer(session, question, payload.given)

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
    sources = (
        await load_source_material(
            session,
            [
                chunk_id
                for chunk_id in (outcome.why_wrong_chunk_id, outcome.evidence_chunk_id)
                if chunk_id is not None
            ],
        )
        if reveal
        else {}
    )
    return _answer_feedback(
        answer, question=question if reveal else None, sources=sources, reveal=reveal
    )


@router.post("/exams/{session_id}/hint", response_model=HintOut)
async def request_hint(
    session_id: UUID,
    payload: HintRequest,
    context: CourseMemberDep,
    session: SessionDep,
    settings: SettingsDep,
) -> HintOut:
    """Kademeli ipucu — yalnız `practice` modunda.

    İpucu metni **kaynaktan türetilir**, modelden değil: kademe yükseldikçe sorunun
    dayandığı chunk'tan daha çoğu açılır. Böylece ipucu her zaman gerçek bir
    materyal parçasına dayanır (Anayasa I) ve LLM ayakta olmasa da çalışır.
    """
    exam = await _load_exam(session, session_id, context)

    if exam.mode is ExamMode.EXAM:
        raise PermissionDeniedError(
            "Sınav modunda ipucu kapalıdır. İpucu almak için alıştırma modunda çalışabilirsiniz."
        )

    if exam.finished_at is not None:
        raise ConflictError("Bu oturum tamamlandı.")

    if payload.question_id not in await paper_question_ids(session, exam):
        raise NotFoundError("Bu soru bu sınav oturumunda yok.")

    question = await session.get(Question, payload.question_id)
    if question is None:
        raise NotFoundError("Soru bulunamadı.")

    refs = await load_source_refs(session, [question.source_chunk_id])
    source = refs.get(question.source_chunk_id)
    if source is None:
        raise NotFoundError("Bu sorunun kaynağı okunamadı; ipucu üretilemiyor.")

    from app.modules.policy.service import resolve_policy

    policy = await resolve_policy(session, course_id=context.course_id, settings=settings)
    level = min(payload.hint_level, policy.max_hints)
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
    # `exam.score` YAZILMIYOR. Puan `answers`'tan türetiliyor (bu dosyanın
    # başındaki 3. kural ve `_session_out`); sütuna yazmak ölü bir yazmaydı ve
    # `0007`'nin kolon GRANT'i onu görünür kıldı — `dou_app` artık yalnız
    # `finished_at` yazabiliyor. Kısıt Şerit 4'ün Karar 2'si: öğrenci kendi
    # oturumunun süresini ve puanını değiştirememeli, ve RLS sütun kısıtı
    # veremediği için koruma GRANT'te.
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

    sources = await load_source_material(
        session,
        [
            chunk_id
            for answer in answers
            for key in ("neden_yanlis_chunk_id", "dayanak_chunk_id")
            if (chunk_id := _chunk_id(answer.feedback, key)) is not None
        ],
    )

    unanswered = len(await paper_question_ids(session, exam)) - len(answers)
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
                answer, question=questions.get(answer.question_id), sources=sources, reveal=True
            )
            for answer in answers
        ],
    )


def _finish_message(*, answered: int, unanswered: int, ungraded: int, score: float | None) -> str:
    if score is None:
        reason = (
            "Hiçbir soru cevaplanmadığı için"
            if answered == 0
            else "Hiçbir cevap değerlendirilemediği için"
        )
        return f"{reason} puan hesaplanmadı. Boş bırakılan sorular yanlış sayılmaz."
    parts = [f"{answered} soru cevaplandı."]
    if unanswered:
        parts.append(f"{unanswered} soru boş bırakıldı; boş sorular puana katılmaz.")
    if ungraded:
        parts.append(f"{ungraded} cevabın değerlendirmesi tamamlanamadı ve puana katılmadı.")
    return " ".join(parts)
