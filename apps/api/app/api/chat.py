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
import json
import math
import time
import unicodedata
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import insert as sa_insert
from sqlalchemy import select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CourseContext,
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
    Citation,
    ClaimingGenerator,
    GeneratedAnswer,
    Generator,
    Guardrail,
    RetrievedChunk,
    Retriever,
    RoleAwareClaimingGenerator,
    SocraticStage,
)
from app.core.config import Settings
from app.core.db import db_now
from app.core.errors import (
    AppError,
    ConcurrencyLimitError,
    ConflictError,
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
)
from app.core.rate_limit import get_concurrency_gate, get_limiter, reset_rate_limit
from app.models.chat import (
    AnswerCache,
    ChatMessage,
    ChatMessageFeedback,
    ChatRole,
    ChatSession,
    RequestLog,
)
from app.models.core import Document, DocumentStatus
from app.modules.agent import quota as agent_quota
from app.modules.assessment import exam_state, socratic
from app.modules.generation import prompts as generation_prompts
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


class PipelineUnavailableError(AppError):
    """Retrieval/generation modülleri henüz takılı değil.

    Fail-closed (Anayasa IV): eksik hattı "cevap yok" diye maskelemek yerine açıkça
    hata döneriz. Aksi hâlde hattı bozuk bir sistem, ölçümde "kanıt yetersiz" oranı
    yüksek ama çalışıyor gibi görünürdü.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "pipeline_unavailable"


#: Bu ucun sayaç kapsamı. Kapsam adı zorunlu çünkü sayaç `questions.py` ile
#: PAYLAŞILIYOR ve iki ucun doğal anahtarı da `kullanıcı:ders` — kapsam olmasaydı
#: sohbet etmek soru üretim kotasını sessizce tüketirdi.
RATE_LIMIT_SCOPE = "chat"


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


class _DocumentScopedRetriever:
    """Enjekte edilen test retriever'larında da kaynak politikasını uygular."""

    def __init__(self, inner: Retriever, document_ids: frozenset[UUID]) -> None:
        self._inner = inner
        self._document_ids = document_ids

    async def search(self, *, course_id: UUID, query: str, limit: int = 8) -> list[RetrievedChunk]:
        chunks = await self._inner.search(course_id=course_id, query=query, limit=limit)
        return [chunk for chunk in chunks if chunk.document_id in self._document_ids][:limit]


def get_retriever(session: AsyncSession, document_ids: frozenset[UUID] | None = None) -> Retriever:
    if _retriever_factory is not None:
        injected = _retriever_factory(session)
        return (
            injected if document_ids is None else _DocumentScopedRetriever(injected, document_ids)
        )
    try:  # Şerit 1, T006
        from app.modules.retrieval.service import HybridRetriever
    except ImportError as exc:
        raise PipelineUnavailableError(
            "Arama hattı henüz hazır değil. Lütfen daha sonra tekrar deneyin."
        ) from exc
    return HybridRetriever(
        session,
        document_ids=None if document_ids is None else tuple(sorted(document_ids, key=str)),
    )


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


# ---------------------------------------------------------------------------
# Önbellek anahtarı
# ---------------------------------------------------------------------------


def question_hash(
    mode: ChatMode,
    question: str,
    *,
    audience: AssistantAudience = AssistantAudience.STUDENT,
    policy_revision: str = "legacy",
    prompt_revision: str = "legacy",
    corpus_revision: str = "legacy",
) -> str:
    """Birebir eşleşme anahtarı (FR-034). Benzerlik tabanlı eşleşme YOKTUR.

    Normalizasyon yalnız Unicode biçimi (NFC) ve boşluk sadeleştirmesidir; harf
    büyüklüğü KORUNUR. Sebep: Türkçede i/İ ve ı/I dönüşümü kayıplıdır (Anayasa V) ve
    "aynı soru" tanımını bozar. Mod anahtarın parçasıdır — bir QA cevabı Sokratik moda
    servis edilirse merdiven baypas edilmiş olur.
    """
    normalized = " ".join(unicodedata.normalize("NFC", question).split())
    identity = "\n".join(
        (
            audience.value,
            mode.value,
            policy_revision,
            prompt_revision,
            corpus_revision,
            normalized,
        )
    )
    return hashlib.sha256(identity.encode()).hexdigest()


PROMPT_REVISION = "005-role-aware-course-agent-v1"

# The role-aware path deliberately allows exactly one provider attempt. The
# first configured model is therefore the only tokenizer contract relevant to
# its pre-charge. Current server-owned system prompt variants were measured
# offline with Xenova/llama-3-tokenizer at immutable revision
# 72bff9ee09897a16b3b4b2b9995fecb0bfa7dbe6. The largest was 1,021 tokens, so
# 1,024 is a conservative content ceiling. Runtime code never loads a tokenizer
# or reaches the network: a changed model or prompt hash retains the original
# UTF-8 byte ceiling until its tokenizer contract is reviewed.
_EXACT_QUOTA_TOKENIZER_MODELS = frozenset({"groq/llama-3.3-70b-versatile"})
_KNOWN_SYSTEM_PROMPT_TOKEN_CEILING = 1_024
_KNOWN_SYSTEM_PROMPT_SHA256S = frozenset(
    {
        "04e64389ae8ae9d4927b8f2fc08bc73e27cf8e3b7cdf23887503c3124b46a731",
        "12ecae0c278f1f02438c5b84eba3e83018bb7bd1add3edd613dce6401c4768a6",
        "14b6340cf745a30968e2eb25baa60f85583d665863655c38322e3fd9d1759f97",
        "214d26a24498f89b91b24f63646a797bf9eb2eb7ff94e0262aa5d75b39ef610c",
        "21d12ef9470f1b55891ed994bbaaaadd7edfd37c0558059ee29c8110af256257",
        "25b66d67cdff9aebe26583482aec942fc935c480fdeac0078c1a8975d95709cf",
        "2986e32d663a2f9ec2a2c2e3ed68f1f3fd01201c2e704968138b3ac2492a969a",
        "2cae2f0ea35773dd8328a0379cda1d08a401b451b8c7981e48303ca5e3b2a4ac",
        "6be3c39bc5e5eaf78d3e2560f9b320b1568906dad44a1fd5add6b5e44c746c78",
        "707d21b48855d4dbbd1862e4861a2a4ef716777a29b154f724df1a596ae7ccdd",
        "73d86031f7f38729c8398358e0f3ec98b0c8ec1076dae251c816918eb514c336",
        "8d23337fde9688a02a57d2a18c11cd19aebe88764c3f1bc8b98fb65d8dff2a15",
        "8dee1ff9e2dce744cfcdcb8d84d6087d1befd38c54bede20cdd46cd9a717a262",
        "94fedefe163b204aa91e0ff1ae292e3bf4bc178a15488fccc484962073ce9e6c",
        "99840996caa3914a1b0785eba08f31c80c39bd5dd08f681f4486532fd39e2f16",
        "a555d952d429d5d5daaa44a84292387f0bf6bd82b7e3b4999aae46528923f1fc",
        "af52efec0404fbc936536a9f2c7e8a89fd490dfce416fdd0f16553b51fb9c84a",
        "b23c5ef3d91c17b543a14f1cc534df1f143721db8315a1a171788b207e8137e8",
        "c7dd3e44c4c1dff02c01171294e1a867774fee9cbc982d99f93f1f0820323728",
        "cd197f265e9ed408618dd8af26d6966af6921b367a0f5ac171cae9afeef19af7",
        "e0b5e509112a3b26e3f77c754f6a54c6728287e8fc5042aeb19cfa865d2f47b6",
        "e6ff7afba2a8ec42ecd517c5f84694e9254b11a51b132f54b78550e1aacb501e",
        "f2b75ee449c0f2ebaf5e3b7b79c11c5d0c4c370224e43267b3d957714a9d3323",
        "f4073973c1302b9cbe6b06437005e54f5be79cc2b17a3a5b9739ff95975c49d0",
    }
)


def _quota_input_token_ceiling(
    request: generation_prompts.LlmRequest,
    *,
    model: str,
    byte_safe_ceiling: int,
) -> int:
    """Return a local, conservative token pre-charge for a reviewed prompt.

    Dynamic user content retains one reserved token per UTF-8 byte, which is a
    safe ceiling for the reviewed byte-level tokenizer. The known system prompt
    uses its offline-measured ceiling and the existing framing allowance stays
    intact. Unknown model/prompt combinations fail closed to the all-byte
    ceiling; no request-path tokenizer, file, or network dependency exists.
    """

    if model not in _EXACT_QUOTA_TOKENIZER_MODELS:
        return byte_safe_ceiling
    system_prompt_hash = hashlib.sha256(request.system.encode()).hexdigest()
    if system_prompt_hash not in _KNOWN_SYSTEM_PROMPT_SHA256S:
        return byte_safe_ceiling

    tokenizer_ceiling = (
        _KNOWN_SYSTEM_PROMPT_TOKEN_CEILING
        + len(request.user.encode())
        + generation_prompts.MESSAGE_FRAMING_TOKEN_CEILING
    )
    return min(byte_safe_ceiling, tokenizer_ceiling)


@dataclass(frozen=True, slots=True)
class CacheRevision:
    audience: AssistantAudience
    policy: str
    prompt: str
    corpus: str


def _audience(context: CourseContext) -> AssistantAudience:
    return AssistantAudience.INSTRUCTOR if context.is_instructor else AssistantAudience.STUDENT


async def _cache_revision(
    session: AsyncSession,
    context: CourseContext,
    policy: policy_service.CoursePolicy,
) -> CacheRevision:
    policy_payload = {
        "allowed_modes": sorted(mode.value for mode in policy.allowed_modes),
        "max_hints": policy.max_hints,
        "sources": (
            None
            if policy.source_document_ids is None
            else sorted(str(value) for value in policy.source_document_ids)
        ),
        "evidence_threshold": policy.evidence_threshold,
        "daily_token_budget": policy.daily_token_budget,
        "student_daily_token_budget": policy.student_daily_token_budget,
        "instructor_daily_token_budget": policy.instructor_daily_token_budget,
        "max_output_tokens": policy.max_output_tokens,
        "max_concurrent_requests": policy.max_concurrent_requests,
    }
    policy_revision = hashlib.sha256(
        json.dumps(policy_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    query = select(
        Document.id,
        Document.file_hash,
        Document.updated_at,
        Document.superseded_at,
    ).where(
        Document.course_id == context.course_id,
        Document.status == DocumentStatus.COMPLETED,
        Document.superseded_at.is_(None),
    )
    if policy.source_document_ids is not None:
        query = query.where(Document.id.in_(policy.source_document_ids))
    rows = (await session.execute(query.order_by(Document.id))).all()
    corpus_payload = [
        (
            str(row.id),
            row.file_hash,
            row.updated_at.isoformat(),
            None if row.superseded_at is None else row.superseded_at.isoformat(),
        )
        for row in rows
    ]
    corpus_revision = hashlib.sha256(
        json.dumps(corpus_payload, separators=(",", ":")).encode()
    ).hexdigest()
    return CacheRevision(
        audience=_audience(context),
        policy=policy_revision,
        prompt=PROMPT_REVISION,
        corpus=corpus_revision,
    )


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


def _refusal(
    status_value: AnswerStatus,
    mode: ChatMode,
    text: str,
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> AnswerOutcome:
    return AnswerOutcome(
        GeneratedAnswer(
            status=status_value,
            mode=mode,
            text=text,
            citations=[],
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
    )


#: Reddin statüsü → kullanıcıya gidecek sabit metin. Sözlük, çağrı yerinde bir
#: if/else zincirinden iyidir: yeni bir ret statüsü eklendiğinde burada eksik
#: kalırsa KeyError verir, sessizce yanlış metin göstermez (fail-closed).
_REFUSAL_TEXT: dict[AnswerStatus, str] = {
    AnswerStatus.OUT_OF_SCOPE: MESSAGE_OUT_OF_SCOPE,
    AnswerStatus.INSUFFICIENT_CONTEXT: MESSAGE_INSUFFICIENT_CONTEXT,
    AnswerStatus.BUDGET_EXHAUSTED: (
        "Bu dersin günlük sohbet AI bütçesi doldu. Bütçe gece yarısı yenilenir."
    ),
}


def _evidence_refusal(
    chunks: list[RetrievedChunk], query: str, threshold: float
) -> AnswerStatus | None:
    """Kanıt kapısı. Cevap üretilebiliyorsa `None`, üretilemiyorsa reddin statüsü.

    Ölçülen birincil sinyal **dense skorudur, füzyon skoru değil.** RRF skoru
    1/(k+sıra) toplamıdır: k=60'ta en iyi sonuç bile ~0.016 çıkar, dolayısıyla
    füzyon skoru sıralama içindir, kalibre edilebilir bir güven ölçüsü değildir.

    Eşiğe burada ikinci kez bakılması bilinçlidir: iki katman da bağımsız olarak
    doğru davranmalıdır (Anayasa II deseni). Eşik `evaluation/calibration.md`'de
    kalibre edildi (0.81); aynı belge holdout'ta hedefi tutturmadığını da yazıyor
    ve sebebin eşiğin değeri değil sinyalin darlığı olduğunu gösteriyor.

    Bu yüzden eşiğin ALTINDA kalan sorgu artık tek bir etikete düşmüyor: kapsam
    dışı sorularla dayanağı zayıf sorular `retrieval.scope` içinde, ölçülmüş
    ikinci ve üçüncü sinyalle ayrılıyor. **Cevaplanan küme değişmez** —
    "yeterli kanıt" koşulu eskisiyle birebir aynı.

    İçeriden import, `get_retriever`/`apply_guardrails` ile aynı desen: modül
    henüz inmemişse uç fail-closed davranır, sessizce cevap üretmez.
    """
    from app.modules.retrieval.scope import assess_evidence

    return assess_evidence(chunks, query=query, threshold=threshold).refusal_status


async def _generate(
    generator: Generator,
    *,
    question: str,
    chunks: list[RetrievedChunk],
    mode: ChatMode,
    stage: SocraticStage | None,
    student_attempt: str | None,
    audience: AssistantAudience,
    max_output_tokens: int,
) -> tuple[GeneratedAnswer, dict[UUID, str]]:
    """Üreteci çağırır ve varsa iddia metinlerini de alır.

    `ClaimingGenerator` uygulayan bir üreteç `generate_with_claims` sunar; sunmayan
    (test ikizleri, sahte üreteç) yalnız `Generator`'ı uygular. Kontrol burada tek
    yerde yapılır, çağıranların her birinde değil.
    """
    if isinstance(generator, RoleAwareClaimingGenerator):
        result = await generator.generate_role_aware_with_claims(
            question=question,
            chunks=chunks,
            mode=mode,
            audience=audience,
            max_output_tokens=max_output_tokens,
            socratic_stage=stage,
            student_attempt=student_attempt,
        )
        return result.answer, dict(result.claims)

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
    evidence_threshold: float | None = None,
    audience: AssistantAudience = AssistantAudience.STUDENT,
    max_output_tokens: int = 700,
    before_generation: Callable[[int], Awaitable[None]] | None = None,
    allow_regeneration: bool = True,
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
    threshold = settings.evidence_threshold if evidence_threshold is None else evidence_threshold
    refusal = _evidence_refusal(chunks, question, threshold)
    if refusal is not None:
        # LLM'e HİÇ gidilmez: kanıt yoksa üretilecek bir şey de yoktur. Kapsam dışı
        # olduğu deterministik olarak saptanmışsa da gidilmez — modele sormak hem
        # kota harcar hem de materyale gömülü bir talimata kapıyı açık bırakırdı.
        return _refusal(refusal, mode, _REFUSAL_TEXT[refusal])

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

    try:
        chunks, byte_safe_input_token_ceiling = generation_prompts.fit_chunks_to_input_budget(
            question,
            chunks,
            max_input_bytes=settings.llm_chat_max_input_bytes,
            mode=mode,
            audience=audience,
            socratic_stage=stage,
            student_attempt=student_attempt,
        )
    except generation_prompts.PromptBudgetExceeded as exc:
        raise ValidationError(
            "Soru ve deneme, asistanın güvenli bağlam sınırını aşıyor.",
            code="agent_prompt_too_large",
        ) from exc
    if not chunks:
        return _refusal(AnswerStatus.INSUFFICIENT_CONTEXT, mode, MESSAGE_INSUFFICIENT_CONTEXT)

    # Persistent quota is reserved only when this turn will actually reach the
    # provider. Retrieval abstention and the deterministic Socratic template do
    # not hold a two-minute reservation or consume provider budget. The callback
    # receives a reviewed-model token ceiling for known server prompts. Unknown
    # models/prompts retain the provider-independent byte ceiling instead of
    # guessing a divisor or loading a tokenizer on the request path.
    if before_generation is not None:
        quota_request = generation_prompts.build_request(
            question,
            chunks,
            mode=mode,
            audience=audience,
            socratic_stage=stage,
            student_attempt=student_attempt,
        )
        provider_model = settings.llm_primary_model or settings.llm_fallback_model
        input_token_ceiling = _quota_input_token_ceiling(
            quota_request,
            model=provider_model,
            byte_safe_ceiling=byte_safe_input_token_ceiling,
        )
        await before_generation(input_token_ceiling)

    answer, claims = await _generate(
        generator,
        question=question,
        chunks=chunks,
        mode=mode,
        stage=stage,
        student_attempt=student_attempt,
        audience=audience,
        max_output_tokens=max_output_tokens,
    )

    if answer.status is AnswerStatus.OUT_OF_SCOPE:
        return _refusal(
            AnswerStatus.OUT_OF_SCOPE,
            mode,
            MESSAGE_OUT_OF_SCOPE,
            prompt_tokens=answer.prompt_tokens,
            completion_tokens=answer.completion_tokens,
        )
    if answer.status is AnswerStatus.INSUFFICIENT_CONTEXT:
        return _refusal(
            AnswerStatus.INSUFFICIENT_CONTEXT,
            mode,
            MESSAGE_INSUFFICIENT_CONTEXT,
            prompt_tokens=answer.prompt_tokens,
            completion_tokens=answer.completion_tokens,
        )

    # Kademe sunucu otoritesindedir.
    answer.socratic_stage = stage
    answer, blocked, _ = apply_guardrails(answer, chunks, guardrails)

    if blocked and mode is ChatMode.SOCRATIC and allow_regeneration:
        # FR-015: ihlalde BİR kez yeniden üret, sürerse deterministik şablona düş.
        regenerated, claims = await _generate(
            generator,
            question=question,
            chunks=chunks,
            mode=mode,
            stage=stage,
            student_attempt=student_attempt,
            audience=audience,
            max_output_tokens=max_output_tokens,
        )
        regenerated.socratic_stage = stage
        regenerated, blocked, _ = apply_guardrails(regenerated, chunks, guardrails)
        regenerated.prompt_tokens += answer.prompt_tokens
        regenerated.completion_tokens += answer.completion_tokens
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
                    prompt_tokens=answer.prompt_tokens,
                    completion_tokens=answer.completion_tokens,
                )
            )
        # QA modunda deterministik bir son durak yoktur: gösterilemeyen cevap
        # gösterilmez (FR-012, fail-closed).
        return _refusal(
            AnswerStatus.INSUFFICIENT_CONTEXT,
            mode,
            MESSAGE_BLOCKED,
            prompt_tokens=answer.prompt_tokens,
            completion_tokens=answer.completion_tokens,
        )

    if not answer.citations:
        # Zincir bloklamasa bile kaynaksız akademik cevap kullanıcıya gitmez (FR-013).
        return _refusal(
            AnswerStatus.INSUFFICIENT_CONTEXT,
            mode,
            MESSAGE_BLOCKED,
            prompt_tokens=answer.prompt_tokens,
            completion_tokens=answer.completion_tokens,
        )

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
    policy_modes: list[ChatMode] = [
        mode for mode in (ChatMode.QA, ChatMode.SOCRATIC) if mode in policy.allowed_modes
    ]
    # Ders politikası öğrencinin kullanabildiği modları sınırlar. Eğitmen ise
    # kendi yapılandırmasını kaynaklı QA/Sokratik akışta test edebilir; POST
    # kapısındaki `assert_mode_allowed(..., is_instructor=True)` ile aynı karar
    # burada da görünür olmalı, yoksa API izin verirken UI besteciyi kapatır.
    allowed_modes = [ChatMode.QA, ChatMode.SOCRATIC] if context.is_instructor else policy_modes
    if not settings.course_agent_enabled:
        return ChatAvailabilityOut(
            available=False,
            reason="globally_disabled",
            message="Ders asistanı şu anda bakım nedeniyle kullanıma kapalı.",
            allowed_modes=[],
            hint_limit=policy.max_hints,
            audience=audience,
            agent_profile=audience.agent_profile,
        )
    if context.is_instructor:
        return ChatAvailabilityOut(
            available=True,
            allowed_modes=allowed_modes,
            hint_limit=policy.max_hints,
            audience=audience,
            agent_profile=audience.agent_profile,
        )
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
            return ChatAvailabilityOut(
                available=False,
                reason="policy_all_modes_closed",
                message="Bu ders için asistan modları eğitmen tarafından kapatıldı.",
                allowed_modes=allowed_modes,
                hint_limit=policy.max_hints,
                audience=audience,
                agent_profile=audience.agent_profile,
            )
        return ChatAvailabilityOut(
            available=True,
            allowed_modes=allowed_modes,
            hint_limit=policy.max_hints,
            audience=audience,
            agent_profile=audience.agent_profile,
        )
    return ChatAvailabilityOut(
        available=False,
        reason=exam_state.EXAM_LOCK_REASON,
        message=exam_state.EXAM_LOCK_MESSAGE,
        allowed_modes=allowed_modes,
        hint_limit=policy.max_hints,
        audience=audience,
        agent_profile=audience.agent_profile,
    )


@router.get("/chat/sessions", response_model=PageOut[ChatSessionOut])
async def list_sessions(
    context: UnlockedCourseMemberDep,
    session: SessionDep,
    page: PageDep,
) -> PageOut[ChatSessionOut]:
    """Kullanıcının bu dersteki sohbet oturumları. RLS başkasınınkini zaten göstermez."""
    query = select(ChatSession).where(ChatSession.course_id == context.course_id)
    if page.cursor is not None:
        updated_at, row_id = decode_time_cursor(page.cursor)
        query = query.where(tuple_(ChatSession.updated_at, ChatSession.id) < (updated_at, row_id))
    result = await session.execute(
        query.order_by(ChatSession.updated_at.desc(), ChatSession.id.desc()).limit(page.limit + 1)
    )
    rows = list(result.scalars())
    visible = rows[: page.limit]
    next_cursor = (
        encode_time_cursor(visible[-1].updated_at, visible[-1].id)
        if len(rows) > page.limit
        else None
    )
    return PageOut(items=[_session_out(row) for row in visible], next_cursor=next_cursor)


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
    if page.cursor is not None:
        created_at, seq, row_id = decode_message_cursor(page.cursor)
        query = query.where(
            tuple_(ChatMessage.created_at, ChatMessage.seq, ChatMessage.id)
            < (created_at, seq, row_id)
        )
    result = await session.execute(
        query.order_by(
            ChatMessage.created_at.desc(), ChatMessage.seq.desc(), ChatMessage.id.desc()
        ).limit(page.limit + 1)
    )
    rows = list(result.scalars())
    visible_desc = rows[: page.limit]
    next_cursor = (
        encode_message_cursor(
            visible_desc[-1].created_at, visible_desc[-1].seq, visible_desc[-1].id
        )
        if len(rows) > page.limit
        else None
    )
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


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------


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
            audience=_audience(context),
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
    if existing.audience is not _audience(context):
        raise ConflictError(
            "Ders rolün değiştiği için bu sohbet sürdürülemez. Yeni bir sohbet aç.",
            code="session_audience_changed",
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
    session: AsyncSession,
    course_id: UUID,
    question: str,
    revision: CacheRevision,
) -> GeneratedAnswer | None:
    """Birebir eşleşmeli önbellek araması. Ders bazlıdır: A'nın cevabı B'ye gitmez."""
    row = (
        await session.execute(
            select(AnswerCache).where(
                AnswerCache.course_id == course_id,
                AnswerCache.audience == revision.audience,
                AnswerCache.policy_revision == revision.policy,
                AnswerCache.prompt_revision == revision.prompt,
                AnswerCache.corpus_revision == revision.corpus,
                AnswerCache.question_hash
                == question_hash(
                    ChatMode.QA,
                    question,
                    audience=revision.audience,
                    policy_revision=revision.policy,
                    prompt_revision=revision.prompt,
                    corpus_revision=revision.corpus,
                ),
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
    session: AsyncSession,
    course_id: UUID,
    question: str,
    answer: GeneratedAnswer,
    revision: CacheRevision,
) -> None:
    """Yalnız TAM HATTAN geçmiş, kaynaklı bir cevap önbelleğe girer."""
    if answer.status is not AnswerStatus.ANSWERED or not answer.citations:
        return
    await session.execute(
        pg_insert(AnswerCache)
        .values(
            course_id=course_id,
            audience=revision.audience,
            policy_revision=revision.policy,
            prompt_revision=revision.prompt,
            corpus_revision=revision.corpus,
            question_hash=question_hash(
                ChatMode.QA,
                question,
                audience=revision.audience,
                policy_revision=revision.policy,
                prompt_revision=revision.prompt,
                corpus_revision=revision.corpus,
            ),
            answer={
                "status": answer.status.value,
                "text": answer.text,
                "citations": [_citation_to_json(c) for c in answer.citations],
            },
        )
        .on_conflict_do_nothing(
            index_elements=[
                "course_id",
                "audience",
                "policy_revision",
                "prompt_revision",
                "corpus_revision",
                "question_hash",
            ]
        )
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
