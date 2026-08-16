"""Sohbet ucu — Faz C (T019) + Sokratik entegrasyonu (T027).

Router `main.py`'ye ZATEN kayıtlıdır; bu dosya yalnız gövdeyi ekler.

## Akış (ARCHITECTURE §5 sırası, değiştirilemez)

    1. AuthZ            CourseMemberDep — course_id istemciden asla yetki değildir
    2. Sınırlar         soru uzunluğu + kullanıcı başına istek sınırı (FR-035)
    3. Önbellek         birebir eşleşme (yalnız QA modu) — isabette LLM'e hiç gidilmez
    4. Retrieval        Retriever.search (Şerit 1)
    5. Kanıt eşiği      altındaysa insufficient_context; LLM ÇAĞRILMAZ
    6. Generation       Generator.generate (Şerit 2)
    7. Guardrail        contracts.Guardrail halkaları, Şerit 2'nin sırasıyla
    8. Kayıt            mesajlar + oturum durumu + request_logs

## Modülerizasyon v2 bölünmesi (16 Ağustos)

1622 satırlık tek dosya beş katmana ayrıldı; bu dosyada yalnız router ve uç
zarfları kaldı. Public adların TAMAMI buradan re-export edilir — testler,
betikler ve `evaluation/` hiçbir import değiştirmeden çalışmaya devam eder:

- `modules/agent/pipeline.py`        DI dikişi (set_pipeline, get_*)
- `modules/agent/token_precharge.py` kota ön-şarj tavanı + 24 prompt hash'i
- `modules/agent/answers.py`         produce_answer + ret metinleri (DB'siz hat)
- `api/chat_cache.py`                önbellek anahtarı/revizyonu, atıf codec'i
- `api/chat_history.py`              oturum + mesaj kalıcılaştırması

## Sözleşme sahipliği (9 Ağustos'ta kapatıldı)

`ChatRequest`/`ChatResponse` bu dosyada GEÇİCİ olarak duruyordu, çünkü yazıldığı gün
`app/schemas/chat.py` (T010, Şerit 2) henüz inmemişti. T010 indi ve iki tanım aynı
anda yaşamaya devam etti; sonuç, istemcinin hiç koşmamış olana karşı yazmasıydı:
frontend `question`/`student_attempt` gönderiyor ve `hints[]`/`snippet` bekliyordu,
canlı uç ise `message` alıyor ve `quote` döndürüyordu. Her istek 422 olurdu.

Artık tek tanım `app/schemas/chat.py`'dedir ve buraya import edilir. Bu dosya zarfı
yeniden tanımlamaz.

`hints[]` dizisi zarfta VARDIR ama `answer`'ı tekrarlamaz: `to_chat_response`, ipucunu
yalnız Sokratik + `answered` + atıflı turlarda üretir ve ipucunun kaynağı cevabın
kaynağıyla aynı kümedir — tek atıf kümesi, tek doğrulama (Anayasa XI).
"""

from __future__ import annotations

import math
import time
from typing import Any
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import insert as sa_insert
from sqlalchemy import select

from app.api.chat_cache import (
    PROMPT_REVISION as PROMPT_REVISION,
)
from app.api.chat_cache import (
    CacheRevision,
    _audience,
    _cache_revision,
    _lookup_cache,
    _store_cache,
)
from app.api.chat_cache import (
    question_hash as question_hash,
)
from app.api.chat_history import (
    _append_messages,
    _is_first_turn,
    _load_or_create_session,
    _opening_question,
    _record_turn,
    _stored_state,
)
from app.api.deps import (
    CourseMemberDep,
    PageDep,
    SessionDep,
    SettingsDep,
    UnlockedCourseMemberDep,
)
from app.contracts import (
    AnswerStatus,
    AssistantAudience,
    ChatMode,
    RoleAwareClaimingGenerator,
    SocraticStage,
)
from app.core.db import db_now
from app.core.errors import (
    ConcurrencyLimitError,
    CourseAgentDisabledError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.pagination import (
    decode_message_cursor,
    decode_time_cursor,
    encode_message_cursor,
    encode_time_cursor,
    paginate_keyset,
)
from app.core.rate_limit import get_concurrency_gate, get_limiter, reset_rate_limit
from app.models.chat import (
    ChatMessage,
    ChatMessageFeedback,
    ChatRole,
    ChatSession,
    RequestLog,
)
from app.modules.agent import quota as agent_quota
from app.modules.agent.answers import (
    _REFUSAL_TEXT,
    AnswerOutcome,
    _refusal,
)
from app.modules.agent.answers import (
    MESSAGE_BLOCKED as MESSAGE_BLOCKED,
)
from app.modules.agent.answers import (
    MESSAGE_INSUFFICIENT_CONTEXT as MESSAGE_INSUFFICIENT_CONTEXT,
)
from app.modules.agent.answers import (
    MESSAGE_OUT_OF_SCOPE as MESSAGE_OUT_OF_SCOPE,
)
from app.modules.agent.answers import (
    apply_guardrails as apply_guardrails,
)
from app.modules.agent.answers import (
    produce_answer as produce_answer,
)
from app.modules.agent.pipeline import (
    PipelineUnavailableError as PipelineUnavailableError,
)
from app.modules.agent.pipeline import (
    RetrieverFactory as RetrieverFactory,
)
from app.modules.agent.pipeline import (
    get_generator,
    get_guardrails,
    get_retriever,
)
from app.modules.agent.pipeline import (
    set_pipeline as set_pipeline,
)
from app.modules.agent.token_precharge import (
    _EXACT_QUOTA_TOKENIZER_MODELS as _EXACT_QUOTA_TOKENIZER_MODELS,
)
from app.modules.agent.token_precharge import (
    _KNOWN_SYSTEM_PROMPT_SHA256S as _KNOWN_SYSTEM_PROMPT_SHA256S,
)
from app.modules.agent.token_precharge import (
    _KNOWN_SYSTEM_PROMPT_TOKEN_CEILING as _KNOWN_SYSTEM_PROMPT_TOKEN_CEILING,
)
from app.modules.agent.token_precharge import (
    _quota_input_token_ceiling as _quota_input_token_ceiling,
)
from app.modules.assessment import exam_state, socratic
from app.modules.policy import service as policy_service
from app.schemas.chat import (
    MAX_QUESTION_LENGTH,
    ChatRequest,
    ChatResponse,
    CitationOut,
    to_chat_response,
)
from app.schemas.feedback import ChatFeedbackOut
from app.schemas.page import PageOut

router = APIRouter(prefix="/courses/{course_id}", tags=["chat"])
logger = get_logger("app.chat")

# ---------------------------------------------------------------------------
# FR-035 sınırları
# ---------------------------------------------------------------------------

# İki sayının da yeri 9 Ağustos'ta düzeltildi (07_SERIT_RAPORLARI §6 borcu), ama
# aynı yere değil — çünkü doğaları farklı:
#
#: Soru uzunluğu `schemas/chat.py`'de kalır, `config.py`'de değil. Sebep teknik:
#: Pydantic `Field(max_length=...)` sınıf tanımlanırken sabit olmak zorundadır,
#: çalışma zamanı ayarından okunamaz. Sayı orada durduğu için OpenAPI'ye de
#: girer, yani istemci sınırı sözleşmeden öğrenir. Burada yalnız eski adıyla
#: yankılanıyor (dışa aktarılmış bir addı).
MAX_QUESTION_CHARS = MAX_QUESTION_LENGTH

#: Bu ucun sayaç kapsamı. Kapsam adı zorunlu çünkü sayaç `questions.py` ile
#: PAYLAŞILIYOR ve iki ucun doğal anahtarı da `kullanıcı:ders` — kapsam olmasaydı
#: sohbet etmek soru üretim kotasını sessizce tüketirdi.
RATE_LIMIT_SCOPE = "chat"


# ---------------------------------------------------------------------------
# Uç düzeyi şemalar
#
# `ChatRequest`/`ChatResponse`/`CitationOut` burada TANIMLANMAZ — `schemas/chat.py`'den
# gelir (bkz. modül docstring'i). Aşağıdaki ikisi yalnız bu uçta kullanılır: geçmiş
# okuma yüzeyi zarf katmanının değil, bu router'ın sözleşmesidir.
# ---------------------------------------------------------------------------


class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    course_id: UUID
    mode: ChatMode
    audience: AssistantAudience
    agent_profile: str
    title: str | None
    socratic_stage: SocraticStage | None = None
    created_at: Any
    updated_at: Any


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: ChatRole
    content: str
    citations: list[CitationOut] = Field(default_factory=list)
    status: AnswerStatus | None = None
    socratic_stage: SocraticStage | None = None
    created_at: Any
    feedback: ChatFeedbackOut | None = None


class ChatAvailabilityOut(BaseModel):
    """Asistanın bu kullanıcı için açık olup olmadığı.

    Arayüzün sekmeyi kilitlemek için ihtiyaç duyduğu tek bilgi. `reason` ve
    `message` sunucudan gelir; arayüz kendi metnini uydurmaz (Anayasa V) ve
    muafiyet kuralını tekrarlamaz — eğitmene her zaman `available=True` döner.
    """

    available: bool
    reason: str | None = None
    message: str | None = None
    allowed_modes: list[ChatMode]
    hint_limit: int
    audience: AssistantAudience
    agent_profile: str


def _citation_out_from_json(raw: dict[str, Any]) -> CitationOut:
    """Saklanan atıf satırını istemci zarfına çevirir.

    `quote` → `snippet` eşlemesi burada yapılır ve tek yerdedir: saklama biçimi
    `contracts.Citation`'ın alan adlarını izler, zarf ise arayüzün sözleşmesini.
    İkisini aynı ada zorlamak, sözleşme dosyasını sunum kaygısıyla değiştirmek
    olurdu. `.get` kullanılıyor çünkü `claim` alanı 9 Ağustos'tan önce yazılmış
    satırlarda yok — eski geçmiş okunamaz hâle gelmemeli.
    """
    return CitationOut(
        chunk_id=UUID(str(raw["chunk_id"])),
        claim=str(raw.get("claim", "")),
        file_name=str(raw["file_name"]),
        location=str(raw["location"]),
        snippet=str(raw.get("quote", "")),
    )


# ---------------------------------------------------------------------------
# Uçlar
# ---------------------------------------------------------------------------


@router.post("/chat", response_model=ChatResponse)
async def post_chat(
    payload: ChatRequest,
    context: UnlockedCourseMemberDep,
    session: SessionDep,
    settings: SettingsDep,
) -> ChatResponse:
    """Bir soru sorar ve kaynaklı cevabı (ya da gerekçeli reddi) döndürür.

    Abstention bir HATA DEĞİLDİR: kanıt yetersizse de kapsam dışıysa da yanıt 200'dür,
    `status` alanı sebebi söyler. Hata zarfına düşürülseydi istemci bunu bir arıza gibi
    gösterirdi; oysa reddetmek ürünün çalıştığının kanıtı.
    """
    started = time.perf_counter()

    if not settings.course_agent_enabled:
        raise CourseAgentDisabledError("Ders asistanı şu anda bakım nedeniyle kullanıma kapalı.")

    question = payload.question.strip()
    # Sokratik turlarda öğrencinin denemesi ayrı alanda gelir; gelmiyorsa sorunun
    # kendisi denemedir. İkinci hâl QA'ya ve merdivenin ilk turuna karşılık gelir.
    attempt = (payload.student_attempt or payload.question).strip()
    if not question:
        raise ValidationError("Soru boş olamaz.")
    if payload.mode is ChatMode.EXAM:
        # Mod politikaları backend'de zorlanır (FR-017): sınavda ipucu tamamen kapalıdır
        # ve bu uç bir ipucu/cevap yüzeyidir. Sınav etkileşimi exams.py üzerinden gider;
        # burada kabul edilseydi sınav modunun tek kuralı istemci tarafından delinirdi.
        raise ValidationError(
            "Sınav modunda asistan ipucu veremez. Sınav soruları sınav ekranından yanıtlanır."
        )
    rate_key = f"{context.user_id}:{context.course_id}"
    if not get_limiter().allow(
        RATE_LIMIT_SCOPE,
        rate_key,
        limit=settings.chat_rate_limit_requests,
        window_seconds=settings.chat_rate_limit_window_seconds,
    ):
        retry_after = max(
            1,
            int(
                get_limiter().retry_after(
                    RATE_LIMIT_SCOPE,
                    rate_key,
                    window_seconds=settings.chat_rate_limit_window_seconds,
                )
            ),
        )
        await agent_quota.record_guard_event(
            user_id=context.user_id,
            course_id=context.course_id,
            event_type="rate_limited",
        )
        raise RateLimitError(
            "Çok sık soru gönderiyorsun. Biraz bekleyip tekrar dener misin?",
            retry_after=retry_after,
        )
    policy = await policy_service.resolve_policy(
        session, course_id=context.course_id, settings=settings
    )
    policy_service.assert_mode_allowed(policy, payload.mode, is_instructor=context.is_instructor)
    audience = _audience(context)
    budget_exhausted = await policy_service.budget_exhausted(
        session, course_id=context.course_id, policy=policy
    )

    chat_session = (
        await _load_or_create_session(session, context, payload)
        if payload.session_id is not None
        else None
    )

    cached_answer = None
    cache_revision: CacheRevision | None = None
    if not budget_exhausted and payload.mode is ChatMode.QA:
        cache_revision = await _cache_revision(session, context, policy)
        cached_answer = await _lookup_cache(session, context.course_id, question, cache_revision)

    if chat_session is None:
        chat_session = await _load_or_create_session(session, context, payload)

    state: socratic.SocraticState | None = None
    decision: socratic.SocraticDecision | None = None
    # Aranacak metin. QA'da sorunun kendisi; Sokratik modda OTURUMUN AÇILIŞ SORUSU.
    #
    # Sokratik turlarda öğrencinin yazdığı bir denemedir, bir soru değil: "sanırım dört
    # koşul", "hı", "sadece söyle". Bunlarla arama yapılırsa hiçbir parça bulunmaz ve
    # merdiven, kanıt eşiğine takılıp çöker — canlı koşuda birebir bu gözlendi. Merdiven
    # tek bir sorunun etrafında ilerler, dolayısıyla arama da o soruya bağlı kalır.
    search_query = question
    if not budget_exhausted and chat_session.mode is ChatMode.SOCRATIC:
        state = _stored_state(chat_session) if not _is_first_turn(chat_session) else None
        decision = socratic.advance(state, attempt, max_stage_index=policy.max_hints)
        search_query = await _opening_question(session, chat_session, fallback=question)

    if budget_exhausted:
        outcome = _refusal(
            AnswerStatus.BUDGET_EXHAUSTED,
            chat_session.mode,
            _REFUSAL_TEXT[AnswerStatus.BUDGET_EXHAUSTED],
        )
    elif cached_answer is not None:
        # Önbellekten dönen cevap da zincirin metne bakan halkalarından geçer.
        # Geçmiyordu ve ölçüldü: satıra konmuş bir `<script>` etiketi hem cevap
        # metninde hem atıf kartında zarfa çıkıyordu. Atıf halkası bilerek
        # koşmaz — bu istekte retrieval yapılmadığı için karşılaştırılacak küme
        # yok; gerekçe `guardrails.chain.screen_cached`'de.
        from app.modules.guardrails.chain import blocked_answer, screen_cached

        screened = screen_cached(cached_answer)
        outcome = AnswerOutcome(
            blocked_answer(screened.block_reason, mode=chat_session.mode)
            if screened.blocked
            else screened.answer
        )
    else:
        reservation_id: UUID | None = None
        reserved_tokens = 0

        async def reserve_provider_budget(input_token_ceiling: int) -> None:
            nonlocal reservation_id, reserved_tokens
            requested_tokens = input_token_ceiling + min(
                policy.max_output_tokens, settings.llm_chat_max_tokens
            )
            reservation = await agent_quota.reserve(
                user_id=context.user_id,
                course_id=context.course_id,
                requested_tokens=requested_tokens,
                # LiteLlmClient enforces timeout * provider-count as its total
                # deadline. Add a 30 s reconciliation margin; Settings caps the
                # result below the SQL function's 600 s maximum.
                lease_seconds=math.ceil(settings.llm_timeout_seconds * 2 + 30),
                user_hard_limit=(
                    settings.course_agent_instructor_daily_hard_limit
                    if audience is AssistantAudience.INSTRUCTOR
                    else settings.course_agent_student_daily_hard_limit
                ),
                course_hard_limit=settings.course_agent_course_daily_hard_limit,
                platform_hard_limit=settings.course_agent_platform_daily_hard_limit,
            )
            reservation_id = reservation.reservation_id
            if not reservation.allowed:
                code = (
                    "agent_concurrency_limited"
                    if reservation.reason == "concurrency_limited"
                    else "agent_quota_exhausted"
                )
                message = (
                    "Önceki asistan isteğin hâlâ sürüyor. Tamamlanınca tekrar dene."
                    if reservation.reason == "concurrency_limited"
                    else "Günlük kişisel AI kullanım kotan doldu. Kota gece yarısı yenilenir."
                )
                raise RateLimitError(
                    message,
                    retry_after=reservation.retry_after_seconds,
                    code=code,
                )
            if reservation.audience is not audience:
                raise RuntimeError("quota audience disagrees with server course context")
            reserved_tokens = requested_tokens

        # Unknown usage and every exception retain the conservative reservation.
        # Refunding zero after a provider timeout would let a costly failed call
        # bypass the daily budget entirely.
        actual_tokens: int | None = None
        active_generator = get_generator()
        try:
            with get_concurrency_gate().hold(
                "chat-agent",
                rate_key,
                limit=policy.max_concurrent_requests,
                message="Önceki asistan isteğin hâlâ sürüyor.",
            ):
                outcome = await produce_answer(
                    question=search_query,
                    course_id=context.course_id,
                    mode=chat_session.mode,
                    decision=decision,
                    retriever=get_retriever(session, policy.source_document_ids),
                    generator=active_generator,
                    guardrails=get_guardrails(),
                    settings=settings,
                    student_attempt=payload.student_attempt,
                    evidence_threshold=policy.evidence_threshold,
                    audience=audience,
                    max_output_tokens=policy.max_output_tokens,
                    before_generation=reserve_provider_budget,
                    allow_regeneration=False,
                )
            measured_tokens = outcome.answer.prompt_tokens + outcome.answer.completion_tokens
            if measured_tokens > 0:
                actual_tokens = measured_tokens
            elif isinstance(active_generator, RoleAwareClaimingGenerator):
                actual_tokens = reserved_tokens
            else:
                # Legacy injected generators are test doubles and never cross a
                # provider boundary. Production GenerationService implements the
                # role-aware protocol, where missing usage is charged in full.
                actual_tokens = 0
        except ConcurrencyLimitError:
            await agent_quota.record_guard_event(
                user_id=context.user_id,
                course_id=context.course_id,
                event_type="concurrency_limited",
            )
            raise
        finally:
            if reservation_id is not None:
                await agent_quota.reconcile(
                    user_id=context.user_id,
                    reservation_id=reservation_id,
                    actual_tokens=reserved_tokens if actual_tokens is None else actual_tokens,
                )
    answer, claims = outcome.answer, outcome.claims

    # The dependency checked the exam lock at request entry, but retrieval and
    # provider I/O happen afterwards. Recheck at the last safe point so a
    # student cannot start a chat, begin an exam in a second tab, then receive
    # the pending sourced answer. Raising here rolls back this request's new
    # session/messages as well as withholding the response.
    if not context.is_instructor:
        await exam_state.acquire_user_assessment_lock(session, user_id=context.user_id)
        now = await db_now(session)
        active_exam = await exam_state.active_exam_session(
            session,
            user_id=context.user_id,
            course_id=context.course_id,
            now=now,
            settings=settings,
        )
        if active_exam is not None:
            raise exam_state.ExamLockedError(exam_state.EXAM_LOCK_MESSAGE)

    if answer.status is AnswerStatus.OUT_OF_SCOPE:
        await agent_quota.record_guard_event(
            user_id=context.user_id,
            course_id=context.course_id,
            event_type="scope_refused",
        )

    # Soru metni hiçbir log satırına yazılmaz (FR-035 redaksiyonu).
    await _record_turn(session, context, chat_session, answer, decision)

    if cached_answer is None and chat_session.mode is ChatMode.QA and cache_revision is not None:
        await _store_cache(session, context.course_id, question, answer, cache_revision)

    # Geçmişe öğrencinin GERÇEKTEN yazdığı metin yazılır. Sokratik turlarda bu, her
    # turda tekrarlanan açılış sorusu değil o turun denemesidir; soruyu tekrar yazmak
    # dökümü okunmaz hâle getirir ve "öğrenci ne denedi" sorusunu cevapsız bırakırdı.
    # İlk turda ikisi zaten aynı metindir, dolayısıyla açılış sorusu araması bozulmaz.
    turn_text = attempt if chat_session.mode is ChatMode.SOCRATIC else question
    assistant_message = await _append_messages(
        session, context, chat_session, turn_text, answer, claims
    )

    latency_ms = int((time.perf_counter() - started) * 1000)
    # RETURNING'siz Core INSERT — `.inline()` bunu zorlar.
    #
    # `request_logs` istemciye kapalıdır: SELECT politikası bilinçli olarak yoktur.
    # Hem ORM `session.add()` hem de düz Core insert, birincil anahtarı geri okumak
    # için örtük `INSERT ... RETURNING` üretir; RETURNING ise RLS altında SELECT
    # politikası ister. psql'de doğrulandı: RETURNING'li ekleme "new row violates
    # row-level security policy" ile düşer, RETURNING'siz ekleme geçer. Uygulamanın
    # bu satırı geri okumaya ihtiyacı yok, dolayısıyla doğru düzeltme politikayı
    # gevşetmek değil RETURNING'i bırakmaktır.
    await session.execute(
        sa_insert(RequestLog)
        .inline()
        .values(
            course_id=context.course_id,
            user_id=context.user_id,
            route="POST /courses/{course_id}/chat",
            mode=chat_session.mode,
            audience=audience,
            status=answer.status,
            http_status=status.HTTP_200_OK,
            latency_ms=latency_ms,
            token_count=answer.prompt_tokens + answer.completion_tokens,
            cache_hit=cached_answer is not None,
        )
    )
    await session.flush()

    # Mod OTURUMUN modudur, üretecin bildirdiği değil: oturum modu sunucuda kilitlidir
    # (`_load_or_create_session`), üretecin döndürdüğü alan ise yalnız bir yankı. Sahte
    # bir üreteç yanlış modu yankılarsa zarf Sokratik turu QA gibi gösterirdi.
    answer.mode = chat_session.mode
    return to_chat_response(
        answer,
        session_id=chat_session.id,
        message_id=assistant_message.id,
        claims=claims,
        cached=cached_answer is not None,
        audience=audience,
    )


@router.get("/chat/availability", response_model=ChatAvailabilityOut)
async def chat_availability(
    context: CourseMemberDep,
    session: SessionDep,
    settings: SettingsDep,
) -> ChatAvailabilityOut:
    """Asistan bu kullanıcı için açık mı?

    Bu uç bilerek `CourseMemberDep` alır, `UnlockedCourseMemberDep` DEĞİL:
    kilitliyken de cevap verebilmesi gerekiyor, yoksa arayüz kilidin sebebini
    hiç öğrenemez ve kullanıcıya "bir şeyler ters gitti" demek zorunda kalır.

    Kararı `deps.require_assistant_unlocked` ile AYNI fonksiyondan okur; iki
    yüzey ayrı ayrı hesaplasaydı biri diğerinden sapardı (Anayasa XI) ve sapma
    sessiz olurdu — sekme açık görünüp istek 403 dönerdi.
    """
    policy = await policy_service.resolve_policy(
        session, course_id=context.course_id, settings=settings
    )
    audience = _audience(context)

    def availability(
        *,
        available: bool,
        allowed_modes: list[ChatMode],
        reason: str | None = None,
        message: str | None = None,
    ) -> ChatAvailabilityOut:
        # Beş dönüş noktasının ortak kuyruğu tek yerde: hint_limit/audience/profile
        # hiçbir dalda farklılaşmıyordu ama beş kez yazılıyordu.
        return ChatAvailabilityOut(
            available=available,
            reason=reason,
            message=message,
            allowed_modes=allowed_modes,
            hint_limit=policy.max_hints,
            audience=audience,
            agent_profile=audience.agent_profile,
        )

    policy_modes: list[ChatMode] = [
        mode for mode in (ChatMode.QA, ChatMode.SOCRATIC) if mode in policy.allowed_modes
    ]
    # Ders politikası öğrencinin kullanabildiği modları sınırlar. Eğitmen ise
    # kendi yapılandırmasını kaynaklı QA/Sokratik akışta test edebilir; POST
    # kapısındaki `assert_mode_allowed(..., is_instructor=True)` ile aynı karar
    # burada da görünür olmalı, yoksa API izin verirken UI besteciyi kapatır.
    allowed_modes = [ChatMode.QA, ChatMode.SOCRATIC] if context.is_instructor else policy_modes
    if not settings.course_agent_enabled:
        return availability(
            available=False,
            reason="globally_disabled",
            message="Ders asistanı şu anda bakım nedeniyle kullanıma kapalı.",
            allowed_modes=[],
        )
    if context.is_instructor:
        return availability(available=True, allowed_modes=allowed_modes)
    now = await db_now(session)
    active = await exam_state.active_exam_session(
        session,
        user_id=context.user_id,
        course_id=context.course_id,
        now=now,
        settings=settings,
    )
    if active is None:
        if not allowed_modes:
            return availability(
                available=False,
                reason="policy_all_modes_closed",
                message="Bu ders için asistan modları eğitmen tarafından kapatıldı.",
                allowed_modes=allowed_modes,
            )
        return availability(available=True, allowed_modes=allowed_modes)
    return availability(
        available=False,
        reason=exam_state.EXAM_LOCK_REASON,
        message=exam_state.EXAM_LOCK_MESSAGE,
        allowed_modes=allowed_modes,
    )


@router.get("/chat/sessions", response_model=PageOut[ChatSessionOut])
async def list_sessions(
    context: UnlockedCourseMemberDep,
    session: SessionDep,
    page: PageDep,
) -> PageOut[ChatSessionOut]:
    """Kullanıcının bu dersteki sohbet oturumları. RLS başkasınınkini zaten göstermez."""
    query = select(ChatSession).where(ChatSession.course_id == context.course_id)
    result = await paginate_keyset(
        session,
        query,
        key_columns=(ChatSession.updated_at, ChatSession.id),
        page=page,
        decode=decode_time_cursor,
        encode=lambda last: encode_time_cursor(last.updated_at, last.id),
    )
    return PageOut(items=[_session_out(row) for row in result.rows], next_cursor=result.next_cursor)


@router.get("/chat/sessions/{session_id}", response_model=PageOut[ChatMessageOut])
async def list_messages(
    session_id: UUID,
    context: UnlockedCourseMemberDep,
    session: SessionDep,
    page: PageDep,
) -> PageOut[ChatMessageOut]:
    chat_session = await session.get(ChatSession, session_id)
    # RLS başka kullanıcının/dersin oturumunu zaten gizler; ders eşleşmesi ayrıca
    # kontrol edilir — iki katman da bağımsız olarak doğru davranmalı.
    if chat_session is None or chat_session.course_id != context.course_id:
        raise NotFoundError("Sohbet oturumu bulunamadı.")

    query = select(ChatMessage).where(ChatMessage.session_id == session_id)
    result = await paginate_keyset(
        session,
        query,
        key_columns=(ChatMessage.created_at, ChatMessage.seq, ChatMessage.id),
        page=page,
        decode=decode_message_cursor,
        encode=lambda last: encode_message_cursor(last.created_at, last.seq, last.id),
    )
    visible_desc = result.rows
    next_cursor = result.next_cursor
    feedback_rows = (
        list(
            (
                await session.execute(
                    select(ChatMessageFeedback).where(
                        ChatMessageFeedback.message_id.in_(
                            [message.id for message in visible_desc]
                        ),
                        ChatMessageFeedback.user_id == context.user_id,
                    )
                )
            ).scalars()
        )
        if visible_desc
        else []
    )
    feedback_by_message = {feedback.message_id: feedback for feedback in feedback_rows}
    items = [
        ChatMessageOut(
            id=message.id,
            role=message.role,
            content=message.content,
            citations=[_citation_out_from_json(raw) for raw in message.citations],
            status=message.status,
            socratic_stage=message.socratic_stage,
            created_at=message.created_at,
            feedback=(
                ChatFeedbackOut.model_validate(feedback_by_message[message.id])
                if message.id in feedback_by_message
                else None
            ),
        )
        for message in reversed(visible_desc)
    ]
    return PageOut(items=items, next_cursor=next_cursor)


def _session_out(chat_session: ChatSession) -> ChatSessionOut:
    state = socratic.SocraticState.from_json(chat_session.state.get("socratic"))
    return ChatSessionOut(
        id=chat_session.id,
        course_id=chat_session.course_id,
        mode=chat_session.mode,
        audience=chat_session.audience,
        agent_profile=chat_session.audience.agent_profile,
        title=chat_session.title,
        socratic_stage=state.stage if chat_session.mode is ChatMode.SOCRATIC else None,
        created_at=chat_session.created_at,
        updated_at=chat_session.updated_at,
    )


__all__ = [
    "MAX_QUESTION_CHARS",
    "ChatRequest",
    "ChatResponse",
    "apply_guardrails",
    "produce_answer",
    "question_hash",
    "reset_rate_limit",
    "router",
    "set_pipeline",
]
