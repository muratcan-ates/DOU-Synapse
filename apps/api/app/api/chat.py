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

## Şeritler arası dikiş

Retrieval (Şerit 1) ve generation/guardrail (Şerit 2) modülleri bu oturum yazılırken
henüz yoktu. Bu dosya onların **gövdesine değil, `app/contracts.py`'deki imzasına**
karşı yazıldı. `set_pipeline()` ile gerçek uygulamalar takılır; takılı değilse uç
fail-closed davranıp 503 döner — sessizce boş cevap üretmez.

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

import hashlib
import time
import unicodedata
from collections import defaultdict, deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import insert as sa_insert
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CourseContext, CourseMemberDep, SessionDep, SettingsDep
from app.contracts import (
    AnswerStatus,
    ChatMode,
    Citation,
    ClaimingGenerator,
    GeneratedAnswer,
    Generator,
    Guardrail,
    RetrievedChunk,
    Retriever,
    SocraticStage,
)
from app.core.config import Settings
from app.core.errors import AppError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.chat import AnswerCache, ChatMessage, ChatRole, ChatSession, RequestLog
from app.modules.assessment import socratic
from app.schemas.chat import (
    MAX_QUESTION_LENGTH,
    ChatRequest,
    ChatResponse,
    CitationOut,
    to_chat_response,
)

router = APIRouter(prefix="/courses/{course_id}", tags=["chat"])
logger = get_logger("app.chat")

#: Retriever'ı isteğin RLS oturumundan kuran fabrika.
RetrieverFactory = Callable[[AsyncSession], Retriever]

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


class RateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"


class PipelineUnavailableError(AppError):
    """Retrieval/generation modülleri henüz takılı değil.

    Fail-closed (Anayasa IV): eksik hattı "cevap yok" diye maskelemek yerine açıkça
    hata döneriz. Aksi hâlde hattı bozuk bir sistem, ölçümde "kanıt yetersiz" oranı
    yüksek ama çalışıyor gibi görünürdü.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "pipeline_unavailable"


class _SlidingWindowLimiter:
    """Süreç içi kayan pencere sayacı.

    Dürüst sınır (Anayasa III): sayaç **süreç içidir.** Birden fazla uvicorn worker'ı
    çalıştığında sınır worker başına uygulanır; MVP tek süreçle koşuyor. Dağıtık sınır
    Redis ister ve kapsam dışıdır — raporda bu haliyle anlatılacak.

    Sınır ve pencere kurucuda değil `allow()` çağrısında verilir: değerler artık
    ayarlardan (`Settings.chat_rate_limit_*`) geliyor ve ayarlar isteğe bağlı bir
    bağımlılık. Sayaç süreç ömürlü, eşik ise istek başına okunuyor — böylece sayı
    değişince süreç yeniden başlatılmadan da geçerli olur.
    """

    def __init__(self) -> None:
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, *, limit: int, window_seconds: float) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()


_rate_limiter = _SlidingWindowLimiter()


def reset_rate_limit() -> None:
    """Testler için sayaç sıfırlama."""
    _rate_limiter.reset()


# ---------------------------------------------------------------------------
# Şeritler arası dikiş: retrieval / generation / guardrail
# ---------------------------------------------------------------------------

#: Retriever İSTEK BAŞINA kurulur: `contracts.Retriever` imzasında `session` yoktur,
#: dolayısıyla gerçek uygulama oturumu kendi içinde taşır ve o oturum isteğin RLS
#: bağlamıdır. Süreç ömürlü tek bir retriever, isteklerin RLS bağlamını karıştırırdı.
_retriever_factory: RetrieverFactory | None = None
_generator: Generator | None = None
_guardrails: Sequence[Guardrail] | None = None


def set_pipeline(
    *,
    retriever_factory: RetrieverFactory | None = None,
    generator: Generator | None = None,
    guardrails: Sequence[Guardrail] | None = None,
) -> None:
    """Cevap hattını takar. `ingestion.storage.set_storage()` ile aynı desen."""
    global _retriever_factory, _generator, _guardrails
    _retriever_factory = retriever_factory
    _generator = generator
    _guardrails = guardrails


def get_retriever(session: AsyncSession) -> Retriever:
    if _retriever_factory is not None:
        return _retriever_factory(session)
    try:  # Şerit 1, T006
        from app.modules.retrieval.service import HybridRetriever
    except ImportError as exc:
        raise PipelineUnavailableError(
            "Arama hattı henüz hazır değil. Lütfen daha sonra tekrar deneyin."
        ) from exc
    return HybridRetriever(session)


def get_generator() -> Generator:
    if _generator is not None:
        return _generator
    try:  # Şerit 2, T012
        from app.modules.generation.service import GenerationService
    except ImportError as exc:
        raise PipelineUnavailableError(
            "Cevap üretimi henüz hazır değil. Lütfen daha sonra tekrar deneyin."
        ) from exc
    return GenerationService()


def get_guardrails() -> Sequence[Guardrail]:
    """Zincir halkaları, Şerit 2'nin belirlediği SIRAYLA.

    Sıra bu dosyada kurulmaz: ARCHITECTURE §5 sırası (citation → leakage → sanitize)
    `modules/guardrails/chain.py` içinde tek yerde sabitlenir. Halkaların uygulanması
    (düşen atıfların temizlenmesi, sanitize edilmiş metnin yazılması) çağıranın işidir;
    `Guardrail.check()` karar döner, nesneyi değiştirmez.
    """
    if _guardrails is not None:
        return _guardrails
    try:  # Şerit 2
        from app.modules.guardrails.chain import GUARDRAIL_CHAIN
    except ImportError as exc:
        raise PipelineUnavailableError(
            "Güvenlik zinciri henüz hazır değil. Lütfen daha sonra tekrar deneyin."
        ) from exc
    return GUARDRAIL_CHAIN


# ---------------------------------------------------------------------------
# Kullanıcıya dönen sabit metinler
# ---------------------------------------------------------------------------

# Reddin sözü BİZE aittir, modele değil (Anayasa V + injection savunması): kaynak
# bulunamadığında ya da cevap bloklandığında kullanıcıya modelin ürettiği metin değil
# bu sabitler gider. Materyalin içine gömülmüş bir talimat, ret metnini ele geçiremez.
MESSAGE_INSUFFICIENT_CONTEXT = (
    "Bu soruya ders materyalinde yeterli dayanak bulamadım, bu yüzden cevap vermiyorum. "
    "Soruyu biraz daha somutlaştırıp tekrar denemek ister misin? "
    "Konunun geçtiği hafta ya da kavram adını eklemen genelde yeterli oluyor."
)
MESSAGE_OUT_OF_SCOPE = (
    "Bu soru dersin kapsamı dışında görünüyor. Yalnızca bu derse yüklenmiş "
    "materyallerden cevap verebiliyorum; ders dışı konularda bilerek sessiz kalıyorum."
)
MESSAGE_BLOCKED = (
    "Bir cevap hazırladım ama gösterebileceğim geçerli bir kaynağa bağlayamadım, "
    "bu yüzden paylaşmıyorum. Kaynağı doğrulanmamış cevap vermemeyi tercih ediyorum."
)


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


# ---------------------------------------------------------------------------
# Önbellek anahtarı
# ---------------------------------------------------------------------------


def question_hash(mode: ChatMode, question: str) -> str:
    """Birebir eşleşme anahtarı (FR-034). Benzerlik tabanlı eşleşme YOKTUR.

    Normalizasyon yalnız Unicode biçimi (NFC) ve boşluk sadeleştirmesidir; harf
    büyüklüğü KORUNUR. Sebep: Türkçede i/İ ve ı/I dönüşümü kayıplıdır (Anayasa V) ve
    "aynı soru" tanımını bozar. Mod anahtarın parçasıdır — bir QA cevabı Sokratik moda
    servis edilirse merdiven baypas edilmiş olur.
    """
    normalized = " ".join(unicodedata.normalize("NFC", question).split())
    return hashlib.sha256(f"{mode.value}\n{normalized}".encode()).hexdigest()


def _citation_to_json(citation: Citation, claim: str = "") -> dict[str, str]:
    return {
        "chunk_id": str(citation.chunk_id),
        "file_name": citation.file_name,
        "location": citation.location,
        "quote": citation.quote,
        "claim": claim,
    }


def _citation_from_json(raw: dict[str, Any]) -> Citation:
    return Citation(
        chunk_id=UUID(str(raw["chunk_id"])),
        file_name=str(raw["file_name"]),
        location=str(raw["location"]),
        quote=str(raw.get("quote", "")),
    )


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
# Cevap hattı — veritabanından bağımsız, bu yüzden DB'siz test edilebilir
# ---------------------------------------------------------------------------


def apply_guardrails(
    answer: GeneratedAnswer,
    retrieved: list[RetrievedChunk],
    guardrails: Sequence[Guardrail],
) -> tuple[GeneratedAnswer, bool, list[UUID]]:
    """Zinciri koşturur — uygulama `guardrails.chain.screen()`'e devredilir.

    Bu fonksiyon önce kendi uygulayıcısını taşıyordu: Şerit 2'nin `chain.py`'si
    henüz yokken yazılmıştı ve aynı işi ikinci kez yapıyordu (Anayasa XI).
    9 Ağustos birleştirmesinde gövde silindi; sıra ve halka etkilerinin
    uygulanması artık tek yerde. Burada yalnız çağrı biçimi korunuyor, çünkü
    bu dosyanın testleri daraltılmış bir zincir enjekte ediyor.
    """
    from app.modules.guardrails.chain import screen

    outcome = screen(answer, retrieved, guardrails)
    return outcome.answer, outcome.blocked, outcome.dropped_citations


@dataclass(frozen=True, slots=True)
class AnswerOutcome:
    """Bir turun sonucu: cevap + atıf başına iddia metni.

    `claims` ayrı taşınır çünkü `contracts.Citation` bilinçli olarak `claim`
    taşımaz (sözleşme dosyasındaki karara bakın): guardrail hiçbir kararında ona
    bakmaz, dolayısıyla zincirin sözleşmesine girmemesi gerekir. Sunum katmanına
    ulaşması gereken tek yer burasıdır.
    """

    answer: GeneratedAnswer
    claims: dict[UUID, str] = field(default_factory=dict)


def _refusal(status_value: AnswerStatus, mode: ChatMode, text: str) -> AnswerOutcome:
    return AnswerOutcome(GeneratedAnswer(status=status_value, mode=mode, text=text, citations=[]))


def _has_evidence(chunks: list[RetrievedChunk], threshold: float) -> bool:
    """Kanıt eşiği. Boş sonuç ya da eşik altı en iyi skor → cevap yok.

    Ölçülen sinyal **dense skorudur, füzyon skoru değil.** RRF skoru 1/(k+sıra)
    toplamıdır: k=60'ta en iyi sonuç bile ~0.016 çıkar, yani 0.35'lik eşikle
    karşılaştırıldığında her soru reddedilirdi. Füzyon skoru sıralama içindir,
    kalibre edilebilir bir güven ölçüsü değildir. Şerit 1'in kapısı (`retrieval
    service.retrieve`) da aynı sinyale bakar; iki katmanın aynı fikirde olması
    tesadüf değil, şart.

    Eşiğe burada ikinci kez bakılması bilinçlidir: iki katman da bağımsız olarak
    doğru davranmalıdır (Anayasa II deseni). Eşik değeri KALİBRE EDİLMEMİŞTİR
    (T043); hiçbir raporda kullanılamaz.
    """
    return bool(chunks) and max(c.dense_score for c in chunks) >= threshold


async def _generate(
    generator: Generator,
    *,
    question: str,
    chunks: list[RetrievedChunk],
    mode: ChatMode,
    stage: SocraticStage | None,
    student_attempt: str | None,
) -> tuple[GeneratedAnswer, dict[UUID, str]]:
    """Üreteci çağırır ve varsa iddia metinlerini de alır.

    `ClaimingGenerator` uygulayan bir üreteç `generate_with_claims` sunar; sunmayan
    (test ikizleri, sahte üreteç) yalnız `Generator`'ı uygular. Kontrol burada tek
    yerde yapılır, çağıranların her birinde değil.
    """
    if isinstance(generator, ClaimingGenerator):
        result = await generator.generate_with_claims(
            question=question,
            chunks=chunks,
            mode=mode,
            socratic_stage=stage,
            student_attempt=student_attempt,
        )
        return result.answer, dict(result.claims)

    answer = await generator.generate(
        question=question,
        chunks=chunks,
        mode=mode,
        socratic_stage=stage,
        student_attempt=student_attempt,
    )
    return answer, {}


async def produce_answer(
    *,
    question: str,
    course_id: UUID,
    mode: ChatMode,
    decision: socratic.SocraticDecision | None,
    retriever: Retriever,
    generator: Generator,
    guardrails: Sequence[Guardrail],
    settings: Settings,
    student_attempt: str | None = None,
) -> AnswerOutcome:
    """Bir turun cevabını üretir. Veritabanına dokunmaz, oturum durumu yazmaz.

    `decision` yalnız Sokratik modda doludur ve kademeyi TAŞIR: servis edilecek kademe
    state machine'in kararıdır, modelin değil. Model kendini bir üst kademeye terfi
    ettiremez.

    `student_attempt` öğrencinin bu turdaki denemesidir ve üretime GEÇİRİLİR: neyi
    yanlış anladığını görmeden verilen ipucu yönlendirme değil tahmindir. 9 Ağustos'a
    kadar alan sözleşmede vardı ama bu uç onu hiç göndermiyordu.
    """
    chunks = await retriever.search(
        course_id=course_id, query=question, limit=settings.retrieval_top_k
    )
    if not _has_evidence(chunks, settings.evidence_threshold):
        # LLM'e HİÇ gidilmez: kanıt yoksa üretilecek bir şey de yoktur.
        return _refusal(AnswerStatus.INSUFFICIENT_CONTEXT, mode, MESSAGE_INSUFFICIENT_CONTEXT)

    stage = decision.stage if decision is not None else None

    # Israrcı öğrenci: deneme yapılmadıysa üretim hiç çalıştırılmaz. Kullanıcı nazik
    # uyarıyı ve AYNI kademenin deterministik şablon ipucunu alır — merdiven ilerlemez,
    # kaynak yine taşınır (FR-013/FR-016) ve LLM bütçesi ısrarla tüketilemez.
    if decision is not None and decision.refusal_notice is not None:
        hint_text, citation = socratic.template_hint(decision.stage, chunks[0])
        return AnswerOutcome(
            GeneratedAnswer(
                status=AnswerStatus.ANSWERED,
                mode=mode,
                text=f"{decision.refusal_notice}\n\n{hint_text}",
                citations=[citation],
                socratic_stage=decision.stage,
            )
        )

    answer, claims = await _generate(
        generator,
        question=question,
        chunks=chunks,
        mode=mode,
        stage=stage,
        student_attempt=student_attempt,
    )

    if answer.status is AnswerStatus.OUT_OF_SCOPE:
        return _refusal(AnswerStatus.OUT_OF_SCOPE, mode, MESSAGE_OUT_OF_SCOPE)
    if answer.status is AnswerStatus.INSUFFICIENT_CONTEXT:
        return _refusal(AnswerStatus.INSUFFICIENT_CONTEXT, mode, MESSAGE_INSUFFICIENT_CONTEXT)

    # Kademe sunucu otoritesindedir.
    answer.socratic_stage = stage
    answer, blocked, _ = apply_guardrails(answer, chunks, guardrails)

    if blocked and mode is ChatMode.SOCRATIC:
        # FR-015: ihlalde BİR kez yeniden üret, sürerse deterministik şablona düş.
        regenerated, claims = await _generate(
            generator,
            question=question,
            chunks=chunks,
            mode=mode,
            stage=stage,
            student_attempt=student_attempt,
        )
        regenerated.socratic_stage = stage
        regenerated, blocked, _ = apply_guardrails(regenerated, chunks, guardrails)
        answer = regenerated

    if blocked:
        if mode is ChatMode.SOCRATIC and stage is not None:
            hint_text, citation = socratic.template_hint(stage, chunks[0])
            return AnswerOutcome(
                GeneratedAnswer(
                    status=AnswerStatus.ANSWERED,
                    mode=mode,
                    text=hint_text,
                    citations=[citation],
                    socratic_stage=stage,
                )
            )
        # QA modunda deterministik bir son durak yoktur: gösterilemeyen cevap
        # gösterilmez (FR-012, fail-closed).
        return _refusal(AnswerStatus.INSUFFICIENT_CONTEXT, mode, MESSAGE_BLOCKED)

    if not answer.citations:
        # Zincir bloklamasa bile kaynaksız akademik cevap kullanıcıya gitmez (FR-013).
        return _refusal(AnswerStatus.INSUFFICIENT_CONTEXT, mode, MESSAGE_BLOCKED)

    # Düşen atıfların iddiaları da düşer: guardrail bir atıfı elediyse onun iddia
    # metnini taşımak, gösterilmeyen bir kaynağa ait cümleyi ekranda bırakırdı.
    kept = {c.chunk_id for c in answer.citations}
    return AnswerOutcome(answer, {k: v for k, v in claims.items() if k in kept})


# ---------------------------------------------------------------------------
# Uçlar
# ---------------------------------------------------------------------------


@router.post("/chat", response_model=ChatResponse)
async def post_chat(
    payload: ChatRequest,
    context: CourseMemberDep,
    session: SessionDep,
    settings: SettingsDep,
) -> ChatResponse:
    """Bir soru sorar ve kaynaklı cevabı (ya da gerekçeli reddi) döndürür.

    Abstention bir HATA DEĞİLDİR: kanıt yetersizse de kapsam dışıysa da yanıt 200'dür,
    `status` alanı sebebi söyler. Hata zarfına düşürülseydi istemci bunu bir arıza gibi
    gösterirdi; oysa reddetmek ürünün çalıştığının kanıtı.
    """
    started = time.perf_counter()

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
    if not _rate_limiter.allow(
        f"{context.user_id}:{context.course_id}",
        limit=settings.chat_rate_limit_requests,
        window_seconds=settings.chat_rate_limit_window_seconds,
    ):
        raise RateLimitError("Çok sık soru gönderiyorsun. Bir dakika bekleyip tekrar dener misin?")

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
    if chat_session.mode is ChatMode.SOCRATIC:
        state = _stored_state(chat_session) if not _is_first_turn(chat_session) else None
        decision = socratic.advance(state, attempt)
        search_query = await _opening_question(session, chat_session, fallback=question)

    cached_answer = None
    if chat_session.mode is ChatMode.QA:
        cached_answer = await _lookup_cache(session, context.course_id, question)

    if cached_answer is not None:
        outcome = AnswerOutcome(cached_answer)
    else:
        outcome = await produce_answer(
            question=search_query,
            course_id=context.course_id,
            mode=chat_session.mode,
            decision=decision,
            retriever=get_retriever(session),
            generator=get_generator(),
            guardrails=get_guardrails(),
            settings=settings,
            student_attempt=payload.student_attempt,
        )
    answer, claims = outcome.answer, outcome.claims

    # Soru metni hiçbir log satırına yazılmaz (FR-035 redaksiyonu).
    await _record_turn(session, context, chat_session, answer, decision)

    if cached_answer is None and chat_session.mode is ChatMode.QA:
        await _store_cache(session, context.course_id, question, answer)

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
            status=answer.status,
            http_status=status.HTTP_200_OK,
            latency_ms=latency_ms,
            # Token sayısı sözleşmede taşınmıyor; Şerit 2 GeneratedAnswer'a eklerse
            # burası dolar. Uydurulmuş bir sayı yazmaktansa boş bırakılıyor (Anayasa III).
            token_count=None,
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
    )


@router.get("/chat/sessions", response_model=list[ChatSessionOut])
async def list_sessions(context: CourseMemberDep, session: SessionDep) -> list[ChatSessionOut]:
    """Kullanıcının bu dersteki sohbet oturumları. RLS başkasınınkini zaten göstermez."""
    result = await session.execute(
        select(ChatSession)
        .where(ChatSession.course_id == context.course_id)
        .order_by(ChatSession.updated_at.desc())
    )
    return [_session_out(row) for row in result.scalars()]


@router.get("/chat/sessions/{session_id}", response_model=list[ChatMessageOut])
async def list_messages(
    session_id: UUID, context: CourseMemberDep, session: SessionDep
) -> list[ChatMessageOut]:
    chat_session = await session.get(ChatSession, session_id)
    # RLS başka kullanıcının/dersin oturumunu zaten gizler; ders eşleşmesi ayrıca
    # kontrol edilir — iki katman da bağımsız olarak doğru davranmalı.
    if chat_session is None or chat_session.course_id != context.course_id:
        raise NotFoundError("Sohbet oturumu bulunamadı.")

    result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        # created_at turlar arasını, seq tur içini sıralar — bkz. models/chat.py.
        .order_by(ChatMessage.created_at, ChatMessage.seq)
    )
    return [
        ChatMessageOut(
            id=message.id,
            role=message.role,
            content=message.content,
            citations=[_citation_out_from_json(raw) for raw in message.citations],
            status=message.status,
            socratic_stage=message.socratic_stage,
            created_at=message.created_at,
        )
        for message in result.scalars()
    ]


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------


def _session_out(chat_session: ChatSession) -> ChatSessionOut:
    state = socratic.SocraticState.from_json(chat_session.state.get("socratic"))
    return ChatSessionOut(
        id=chat_session.id,
        course_id=chat_session.course_id,
        mode=chat_session.mode,
        title=chat_session.title,
        socratic_stage=state.stage if chat_session.mode is ChatMode.SOCRATIC else None,
        created_at=chat_session.created_at,
        updated_at=chat_session.updated_at,
    )


def _is_first_turn(chat_session: ChatSession) -> bool:
    return "socratic" not in chat_session.state


def _stored_state(chat_session: ChatSession) -> socratic.SocraticState:
    return socratic.SocraticState.from_json(chat_session.state.get("socratic"))


async def _load_or_create_session(
    session: AsyncSession, context: CourseContext, payload: ChatRequest
) -> ChatSession:
    if payload.session_id is None:
        chat_session = ChatSession(
            course_id=context.course_id,
            user_id=context.user_id,
            mode=payload.mode,
            state={},
            title=payload.question.strip()[:80],
        )
        session.add(chat_session)
        await session.flush()
        return chat_session

    # Ayrı ad: yukarıdaki dalda `chat_session` ChatSession, burada `get()`
    # ChatSession | None döndürüyor. Aynı ada yazmak mypy'ı kırıyordu ve
    # okuyucuya da iki farklı şeyin aynı değişken olduğunu ima ediyordu.
    existing = await session.get(ChatSession, payload.session_id)
    if existing is None or existing.course_id != context.course_id:
        raise NotFoundError("Sohbet oturumu bulunamadı.")
    if existing.mode is not payload.mode:
        # Mod ortasında değiştirilemez: Sokratik durum moda aittir, QA'ya geçip geri
        # dönmek merdiveni sıfırlamanın kolay yolu olurdu.
        raise ValidationError(
            "Bu oturum farklı bir modda başlatılmış. Yeni mod için yeni bir sohbet aç."
        )
    return existing


async def _opening_question(
    session: AsyncSession, chat_session: ChatSession, *, fallback: str
) -> str:
    """Oturumu açan kullanıcı mesajı — Sokratik merdivenin üzerinde ilerlediği soru.

    Ayrı bir sütunda kopyalanmıyor, ilk mesajdan okunuyor: aynı veriyi iki yerde
    tutmak, birinin güncellenip diğerinin unutulduğu bir hata sınıfı açardı
    (Anayasa XI). `chat_messages` üzerinde (session_id, created_at, seq) indeksi var.

    NOT (gruba iletildi): öğrencinin son denemesi üretime geçirilemiyor çünkü
    `contracts.Generator.generate` imzasında böyle bir alan yok. Kademe metni bu
    yüzden denemeye değil yalnız kademeye ve soruya göre şekilleniyor.
    """
    content = await session.scalar(
        select(ChatMessage.content)
        .where(
            ChatMessage.session_id == chat_session.id,
            ChatMessage.role == ChatRole.USER,
        )
        .order_by(ChatMessage.created_at, ChatMessage.seq)
        .limit(1)
    )
    return content or fallback


async def _lookup_cache(
    session: AsyncSession, course_id: UUID, question: str
) -> GeneratedAnswer | None:
    """Birebir eşleşmeli önbellek araması. Ders bazlıdır: A'nın cevabı B'ye gitmez."""
    row = (
        await session.execute(
            select(AnswerCache).where(
                AnswerCache.course_id == course_id,
                AnswerCache.question_hash == question_hash(ChatMode.QA, question),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None

    payload = row.answer
    try:
        return GeneratedAnswer(
            status=AnswerStatus(payload["status"]),
            mode=ChatMode.QA,
            text=str(payload["text"]),
            citations=[_citation_from_json(c) for c in payload.get("citations", [])],
        )
    except (KeyError, ValueError, TypeError):
        # Bozuk önbellek satırı yok sayılır ve cevap yeniden üretilir; önbellek bir
        # hızlandırmadır, doğruluk kaynağı değildir.
        logger.warning("bozuk önbellek satırı yok sayıldı", extra={"context": {"id": str(row.id)}})
        return None


async def _store_cache(
    session: AsyncSession, course_id: UUID, question: str, answer: GeneratedAnswer
) -> None:
    """Yalnız TAM HATTAN geçmiş, kaynaklı bir cevap önbelleğe girer."""
    if answer.status is not AnswerStatus.ANSWERED or not answer.citations:
        return
    await session.execute(
        pg_insert(AnswerCache)
        .values(
            course_id=course_id,
            question_hash=question_hash(ChatMode.QA, question),
            answer={
                "status": answer.status.value,
                "text": answer.text,
                "citations": [_citation_to_json(c) for c in answer.citations],
            },
        )
        .on_conflict_do_nothing(index_elements=["course_id", "question_hash"])
    )


async def _record_turn(
    session: AsyncSession,
    context: CourseContext,
    chat_session: ChatSession,
    answer: GeneratedAnswer,
    decision: socratic.SocraticDecision | None,
) -> None:
    """Sokratik durumu kalıcılaştırır ve kademe geçişini olay olarak loglar.

    Durum **yalnız gerçekten ipucu servis edildiyse** yazılır. Kanıt eşiği aşılamadıysa
    ya da soru kapsam dışıysa kullanıcı hiçbir ipucu almamıştır; o turu ilerleme saymak,
    öğrenciyi hiç yardım almadığı bir kademeye taşırdı. Canlı koşuda gözlendi: materyali
    olmayan bir soruya yapılan deneme, merdiveni sessizce bir kademe yukarı itiyordu.

    Ölçü olarak `answer.socratic_stage` kullanılıyor çünkü bu alan tam olarak "bu turda
    şu kademenin ipucu gösterildi" demektir; abstention yollarında None kalır.
    """
    if decision is None or answer.socratic_stage is None:
        return

    chat_session.state = {**chat_session.state, "socratic": decision.state.to_json()}

    if decision.transition is not None:
        # FR-014: her kademe geçişi kayıt altına alınır. İki yerde birden — durum
        # jsonb'sinde (kalıcı, sorgulanabilir) ve yapılandırılmış logda (zaman serisi).
        logger.info(
            "sokratik kademe ilerledi",
            extra={
                "context": {
                    "course_id": str(context.course_id),
                    "session_id": str(chat_session.id),
                    "from": decision.transition.from_stage.value,
                    "to": decision.transition.to_stage.value,
                    "attempt": decision.attempt_kind.value,
                }
            },
        )
    elif decision.refusal_notice is not None:
        logger.info(
            "sokratik kademe korundu",
            extra={
                "context": {
                    "course_id": str(context.course_id),
                    "session_id": str(chat_session.id),
                    "stage": decision.stage.value,
                    "attempt": decision.attempt_kind.value,
                    "refusals": decision.state.refusals,
                }
            },
        )


async def _append_messages(
    session: AsyncSession,
    context: CourseContext,
    chat_session: ChatSession,
    turn_text: str,
    answer: GeneratedAnswer,
    claims: dict[UUID, str],
) -> ChatMessage:
    session.add(
        ChatMessage(
            session_id=chat_session.id,
            course_id=context.course_id,
            role=ChatRole.USER,
            content=turn_text,
            citations=[],
            status=None,
            socratic_stage=None,
            seq=0,
        )
    )
    assistant = ChatMessage(
        session_id=chat_session.id,
        course_id=context.course_id,
        role=ChatRole.ASSISTANT,
        content=answer.text,
        citations=[_citation_to_json(c, claims.get(c.chunk_id, "")) for c in answer.citations],
        status=answer.status,
        socratic_stage=answer.socratic_stage,
        seq=1,
    )
    session.add(assistant)
    await session.flush()
    return assistant


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
