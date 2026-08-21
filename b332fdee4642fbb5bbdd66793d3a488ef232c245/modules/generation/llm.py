"""LLM erişimi — Groq → Gemini otomatik failover (T009).

Failover neden KOD seviyesinde: ücretsiz katmanda kota bir anda dolar ve 429
döner. Elle model değiştirmek, sunum sırasında kimsenin yapamayacağı bir iştir;
o yüzden sıradaki sağlayıcıya düşme kararı burada, çağrı yolunda verilir ve
hangi cevabın hangi sağlayıcıyla üretildiği `GeneratedAnswer.provider/.model`
alanlarında taşınır (Anayasa III: raporlanacak sayı ölçülebilir olmalı).

İki sert sınır var ve ikisi de bilinçli:

* **Deneme sayısı** `llm_max_retries` ile sınırlıdır. Sonsuz retry, ücretsiz
  katmanda günlük kotayı bir sabahta tüketir.
* **Süre** çift katmanlıdır: her denemenin kendi zaman aşımı vardır ve tüm
  `complete()` çağrısının bir üst bütçesi vardır. Tek katman yetmez — asılı
  kalan bir istek üzerine failover eklenince toplam süre sessizce katlanır ve
  öğrenci sınav sırasında bekler (SC-010).

`litellm` MODÜL SEVİYESİNDE import EDİLMEZ: paketi içe aktarmak saniyeler sürer
ve testlerin çoğu LLM'e hiç dokunmaz. Ağsız CI'da import'un kendisi de risktir.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from fastapi import status

from app.contracts import ChatMode, SocraticStage
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.logging import get_logger

logger = get_logger("app.llm")

#: Üstel geri çekilme: ilk bekleme, sonra her denemede ikiye katlanır.
BACKOFF_BASE_SECONDS = 0.5
#: Bekleme tavanı. Geri çekilme, zaman aşımı bütçesini tek başına yiyemez.
BACKOFF_MAX_SECONDS = 4.0

#: Sağlayıcı geçici olarak yanıt veremiyor: aynı sağlayıcıda tekrar denemek anlamlı.
_RETRYABLE_EXCEPTIONS = frozenset(
    {
        "APIConnectionError",
        "APIError",
        "InternalServerError",
        "RateLimitError",
        "ServiceUnavailableError",
        "Timeout",
        "APITimeoutError",
    }
)
_RETRYABLE_STATUS = frozenset({408, 409, 429, 500, 502, 503, 504})
#: Kimlik/istek hatası: aynı sağlayıcıda tekrar denemek kesinlikle boşuna, doğrudan
#: sıradaki sağlayıcıya geçilir.
_FATAL_STATUS = frozenset({400, 401, 403, 404, 422})


class LlmUnavailableError(AppError):
    """Hiçbir sağlayıcı cevap veremedi.

    Bilerek `insufficient_context` DÖNÜLMEZ: "materyalde kanıt yok" demek ile
    "modele ulaşamadık" demek farklı şeylerdir ve ikincisini birincisi gibi
    raporlamak SC-005 ret oranını sahte biçimde şişirir (Anayasa III).
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "llm_unavailable"

    def __init__(self) -> None:
        super().__init__(
            "Cevap üretme servisine şu anda ulaşılamıyor. Lütfen birazdan tekrar deneyin."
        )


class LlmTask(StrEnum):
    """İsteğin ne İSTEDİĞİ — `ChatMode`'dan farklı bir eksen.

    `ChatMode` bir sohbet turunun pedagojik kipidir (QA / Sokratik / sınav) ve
    üçünün de çıktısı bir cevap zarfıdır. Soru üretimi ise bambaşka bir şema
    ister (`{"questions": [...]}`) ve hiçbir `ChatMode` değeri onu anlatamaz;
    varsayılan `QA` ile gönderildiği için sahte sağlayıcı soru üretimi
    isteğine SOHBET CEVABI dönüyordu (14_R4 Kusur 4).

    Gerçek sağlayıcı bu alanı kullanmaz — prompt zaten göreve göre kurulur.
    Alan, deterministik sahte sağlayıcının hangi şemayı üreteceğini bilmesi
    için var; çevrimdışı demo (PLAN plan C) soru üretimini de göstermek zorunda.
    """

    CHAT = "chat"
    QUESTION_GEN = "question_gen"


@dataclass(frozen=True, slots=True)
class LlmRequest:
    """Sağlayıcıya gidecek tek istek.

    `mode`, `socratic_stage` ve `task`'ı gerçek sağlayıcı kullanmaz — prompt
    zaten göreve ve moda göre kurulmuştur. Burada durmalarının sebebi
    deterministik sahte sağlayıcı: ağsız koşarken de göreve ve moda uygun,
    gerçekten atıf yapan bir çıktı üretebilmesi gerekiyor (bkz. `fake.py`).
    """

    system: str
    user: str
    mode: ChatMode = ChatMode.QA
    socratic_stage: SocraticStage | None = None
    #: JSON zorlaması: sağlayıcı destekliyorsa serbest metin dönmesini engeller.
    json_output: bool = True
    #: Guardrail ihlali sonrası yeniden üretim. Prompt zaten sıkılaşır; sahte
    #: sağlayıcı da bu bayrakla ihlalsiz cevaba geçer.
    strict_retry: bool = False
    #: Varsayılan `CHAT`: alanı bilmeyen çağıranlar bugünkü davranışı korur.
    #: Sahte sağlayıcı, alan verilmemişse prompt'un biçiminden görevi çıkarır —
    #: gerekçe ve o çıkarımın nasıl kilitlendiği `fake.py`'de.
    task: LlmTask = LlmTask.CHAT


@dataclass(frozen=True, slots=True)
class LlmCompletion:
    """Sağlayıcı cevabı ve ölçüm alanları."""

    text: str
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    duration_ms: float = 0.0


class LlmClient(Protocol):
    """Üretim servisinin gördüğü tek yüzey. Gerçek ve sahte sağlayıcı aynı imzayı uygular."""

    async def complete(self, request: LlmRequest) -> LlmCompletion: ...


def provider_of(model: str) -> str:
    """`groq/llama-3.3-70b` → `groq`. LiteLLM model adı sağlayıcıyı önek olarak taşır."""
    return model.split("/", 1)[0] if "/" in model else model


class LiteLlmClient:
    """LiteLLM üzerinden sırayla sağlayıcı deneyen istemci.

    `completion_fn` enjekte edilebilir: 429 → failover davranışını gerçek ağa
    çıkmadan test edebilmek için. Üretimde `None` bırakılır ve `litellm.acompletion`
    tembel olarak yüklenir.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        completion_fn: Any | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._completion_fn = completion_fn

    @property
    def _targets(self) -> list[str]:
        """Denenecek modeller, sırayla. Aynı model iki kez listelenmez."""
        ordered = [self._settings.llm_primary_model, self._settings.llm_fallback_model]
        seen: list[str] = []
        for model in ordered:
            if model and model not in seen:
                seen.append(model)
        return seen

    def _api_key_for(self, model: str) -> str | None:
        provider = provider_of(model)
        if provider == "groq":
            return self._settings.groq_api_key
        if provider in {"gemini", "vertex_ai"}:
            return self._settings.gemini_api_key
        return None

    async def _load_completion_fn(self) -> Any:
        if self._completion_fn is not None:
            return self._completion_fn
        # Tembel import: litellm ağır bir pakettir, LLM'e dokunmayan testleri yavaşlatmaz.
        import litellm

        litellm.drop_params = True  # sağlayıcının desteklemediği parametreyi sessizce at
        self._completion_fn = litellm.acompletion
        return self._completion_fn

    async def complete(self, request: LlmRequest) -> LlmCompletion:
        targets = self._targets
        if not targets:
            raise LlmUnavailableError

        settings = self._settings
        per_attempt = settings.llm_timeout_seconds
        # Toplam bütçe sağlayıcı başına bir zaman aşımı kadardır: birincisi asılı
        # kalırsa ikincisi hâlâ gerçek bir şans bulur, ama toplam süre sınırsız
        # büyümez. Tek katmanlı bir zaman aşımı bu iki şeyden birini kaybettirirdi.
        deadline = time.monotonic() + per_attempt * len(targets)
        last_error: Exception | None = None

        for model in targets:
            for attempt in range(settings.llm_max_retries + 1):
                budget = min(per_attempt, deadline - time.monotonic())
                if budget <= 0:
                    logger.warning(
                        "llm süre bütçesi tükendi",
                        extra={"context": {"model": model, "attempt": attempt}},
                    )
                    raise LlmUnavailableError

                try:
                    return await self._attempt(model, request, budget=budget, attempt=attempt)
                except Exception as exc:  # sınıflandırma _is_retryable'da yapılır
                    last_error = exc
                    retryable = _is_retryable(exc)
                    logger.warning(
                        "llm çağrısı başarısız",
                        extra={
                            "context": {
                                "provider": provider_of(model),
                                "model": model,
                                "attempt": attempt,
                                "error": type(exc).__name__,
                                "retryable": retryable,
                            }
                        },
                    )
                    if not retryable or attempt >= settings.llm_max_retries:
                        break  # sıradaki sağlayıcıya düş
                    await asyncio.sleep(_backoff_for(attempt))

        logger.error(
            "tüm llm sağlayıcıları başarısız",
            extra={"context": {"models": targets, "error": type(last_error).__name__}},
        )
        raise LlmUnavailableError

    async def _attempt(
        self, model: str, request: LlmRequest, *, budget: float, attempt: int
    ) -> LlmCompletion:
        completion_fn = await self._load_completion_fn()
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "temperature": self._settings.llm_temperature,
            "timeout": budget,
        }
        api_key = self._api_key_for(model)
        if api_key:
            kwargs["api_key"] = api_key
        if request.json_output:
            kwargs["response_format"] = {"type": "json_object"}

        started = time.perf_counter()
        async with asyncio.timeout(budget):
            response = await completion_fn(**kwargs)
        duration_ms = round((time.perf_counter() - started) * 1000, 1)

        text = _extract_text(response)
        prompt_tokens, completion_tokens = _extract_usage(response)
        # Token kullanımı maskeli logger'a yazılır: kota tüketimini ölçmeden
        # "ücretsiz katmana sığıyoruz" diyemeyiz (Anayasa III).
        logger.info(
            "llm cevabı üretildi",
            extra={
                "context": {
                    "provider": provider_of(model),
                    "model": model,
                    "attempt": attempt,
                    "duration_ms": duration_ms,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                }
            },
        )
        return LlmCompletion(
            text=text,
            provider=provider_of(model),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_ms=duration_ms,
        )


def _backoff_for(attempt: int) -> float:
    return min(BACKOFF_BASE_SECONDS * (2**attempt), BACKOFF_MAX_SECONDS)


def _is_retryable(exc: Exception) -> bool:
    """Aynı sağlayıcıda tekrar denemek anlamlı mı?

    Sınıflandırma litellm istisna SINIFLARINA değil, adlarına ve `status_code`
    alanına bakar. Sebep: litellm'i sınıflandırma uğruna modül seviyesinde import
    etmek, LLM'e dokunmayan her testi yavaşlatırdı.
    """
    if isinstance(exc, asyncio.TimeoutError | TimeoutError):
        return True
    code = getattr(exc, "status_code", None)
    if isinstance(code, int):
        if code in _FATAL_STATUS:
            return False
        return code in _RETRYABLE_STATUS
    return type(exc).__name__ in _RETRYABLE_EXCEPTIONS


def _extract_text(response: Any) -> str:
    """LiteLLM cevabından metni çıkarır; sözlük ve nesne biçimini birlikte destekler."""
    choices = _get(response, "choices") or []
    if not choices:
        return ""
    message = _get(choices[0], "message")
    content = _get(message, "content") if message is not None else None
    return content or ""


def _extract_usage(response: Any) -> tuple[int, int]:
    usage = _get(response, "usage")
    if usage is None:
        return 0, 0
    prompt = _get(usage, "prompt_tokens") or 0
    completion = _get(usage, "completion_tokens") or 0
    return int(prompt), int(completion)


def _get(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def build_llm_client(settings: Settings | None = None) -> LlmClient:
    """Ayarlara göre gerçek ya da deterministik sahte sağlayıcıyı verir.

    Anahtar yoksa sahteye düşmek bir kolaylık değil, dayanıklılık kararıdır:
    CI'da ağ ve anahtar yoktur, çevrimdışı demo (PLAN plan C) da buna dayanır.
    Üretimde sahte sağlayıcının açılmasını `Settings` doğrulayıcısı zaten
    reddediyor, yani bu dal gerçek öğrenciye uydurma cevap gönderemez.
    """
    settings = settings or get_settings()
    from app.modules.generation.fake import FakeLlmClient

    if settings.llm_fake_provider:
        return FakeLlmClient()
    if not (settings.groq_api_key or settings.gemini_api_key):
        if settings.is_production:
            raise LlmUnavailableError
        logger.warning("llm anahtarı yok — deterministik sahte sağlayıcıya düşülüyor")
        return FakeLlmClient()
    return LiteLlmClient(settings)
