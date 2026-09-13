"""Ders asistanında tek sağlayıcı tekrarı ve açıkça etiketlenen demo son durağı."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from app.contracts import AnswerStatus, ChatMode, GeneratedAnswer, RetrievedChunk, SocraticStage
from app.core.config import Environment, Settings, get_settings
from app.core.errors import AppError
from app.modules.agent.provider_events import LearningEventLlmClient, build_learning_event_client
from app.modules.generation.llm import LlmClient, LlmCompletion, LlmRequest, LlmUnavailableError

DEMO_FIXTURE_LABEL = "Önceden kaydedilmiş demo yanıtı"
DEMO_FIXTURE_TEXT = (
    f"{DEMO_FIXTURE_LABEL}\n\n"
    "Aşağıdaki ders kaynağını açıp soruyla ilgili tanımı kendi cümlelerinle özetle. "
    "Ardından hangi adımda takıldığını yaz."
)
MAX_RETRY_AFTER_SECONDS = 4.0
DEFAULT_RETRY_AFTER_SECONDS = 1.0
_sleep = asyncio.sleep
_monotonic = time.monotonic


class RateLimitSimulationForbidden(AppError):
    status_code = 503
    code = "rate_limit_simulation_forbidden"

    def __init__(self) -> None:
        super().__init__("Sağlayıcı sınırı benzetimi yalnız yerel demo ortamında kullanılabilir.")


def simulation_enabled(settings: Settings) -> bool:
    """Benzetim üretime veya gerçek sağlayıcı ölçümüne karışamaz."""
    if os.environ.get("LLM_SIMULATE_RATE_LIMIT") != "1":
        return False
    if settings.environment is not Environment.LOCAL or settings.eval_runtime_enabled:
        raise RateLimitSimulationForbidden
    return True


class SimulatedProviderRateLimit(Exception):
    """Aynı adapter gözlem yolundan geçen, yalnız yerelde kurulabilen 429."""

    status_code = 429

    def __init__(self) -> None:
        self.headers = {"Retry-After": "1"}


async def _simulate_rate_limit(**kwargs: object) -> None:
    del kwargs
    raise SimulatedProviderRateLimit


class ProviderRateLimitExhausted(LlmUnavailableError):
    """429 sonrasındaki kontrollü tekrar bütçesi bir yanıt üretemedi."""


@dataclass(slots=True)
class ProviderObservedAnswer(GeneratedAnswer):
    """Yalnız yerel benzetim isteğinde ölçülen transport deneme sayısı."""

    provider_attempts: int | None = None


@dataclass(slots=True)
class DemoFixtureAnswer(ProviderObservedAnswer):
    """Fixture kimliği serbest yanıt metninden değil bu sunucu tipinden gelir."""


@dataclass(slots=True)
class ProviderAttemptCounter:
    attempts: int = 0


_attempt_counter: ContextVar[ProviderAttemptCounter | None] = ContextVar(
    "agent_provider_attempts", default=None
)


@contextmanager
def provider_attempt_context(settings: Settings) -> Iterator[ProviderAttemptCounter | None]:
    counter = ProviderAttemptCounter() if simulation_enabled(settings) else None
    token = _attempt_counter.set(counter)
    try:
        yield counter
    finally:
        _attempt_counter.reset(token)


def attach_provider_attempts(
    answer: GeneratedAnswer, counter: ProviderAttemptCounter | None
) -> GeneratedAnswer:
    if counter is None:
        return answer
    if isinstance(answer, ProviderObservedAnswer):
        return replace(answer, provider_attempts=counter.attempts)
    return ProviderObservedAnswer(
        status=answer.status,
        mode=answer.mode,
        text=answer.text,
        citations=answer.citations,
        socratic_stage=answer.socratic_stage,
        provider=answer.provider,
        model=answer.model,
        prompt_tokens=answer.prompt_tokens,
        completion_tokens=answer.completion_tokens,
        provider_attempts=counter.attempts,
    )


def retry_after_seconds(error: Exception) -> float:
    headers = getattr(error, "headers", None)
    if not isinstance(headers, Mapping):
        headers = getattr(getattr(error, "response", None), "headers", None)
    if not isinstance(headers, Mapping):
        return DEFAULT_RETRY_AFTER_SECONDS
    raw = next(
        (str(value) for key, value in headers.items() if str(key).lower() == "retry-after"), ""
    )
    if raw.isascii() and raw.isdigit():
        return float(raw)
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            return DEFAULT_RETRY_AFTER_SECONDS
        return max(0.0, (parsed - datetime.now(UTC)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return DEFAULT_RETRY_AFTER_SECONDS


class SameProviderRetryClient(LearningEventLlmClient):
    """429'da aynı birincil hedefe bir kez döner; model veya sağlayıcı değiştirmez."""

    async def _attempt(
        self, model: str, request: LlmRequest, *, budget: float, attempt: int
    ) -> LlmCompletion:
        counter = _attempt_counter.get()
        if counter is not None:
            counter.attempts += 1
        # Üst katman her ham 429'u B3 olay yazıcısıyla gözler. Yazıcı arızası
        # özgün sağlayıcı hatasını değiştirmez; süreç iptali yakalanmaz.
        return await super()._attempt(model, request, budget=budget, attempt=attempt)

    async def complete(self, request: LlmRequest) -> LlmCompletion:
        if request.max_provider_attempts is not None and request.max_provider_attempts <= 0:
            raise LlmUnavailableError
        model = self._settings.llm_primary_model
        if not model:
            raise LlmUnavailableError
        # L2-B4'ün açık 429 istisnası: role-aware max_provider_attempts=1
        # sınırı yalnız ham 429 sonrası tek aynı-model tekrarına açılır.
        # Başarılı completion en fazla birdir; 429'un ücret/token maliyeti
        # hakkında çıkarım yapılmaz ve genel failover politikası kullanılmaz.
        deadline = _monotonic() + self._settings.llm_timeout_seconds
        last_error: Exception | None = None
        for attempt in range(2):
            budget = deadline - _monotonic()
            if budget <= 0:
                if last_error is not None:
                    raise ProviderRateLimitExhausted from last_error
                raise LlmUnavailableError
            try:
                return await self._attempt(model, request, budget=budget, attempt=attempt)
            except Exception as error:
                if getattr(error, "status_code", None) != 429:
                    if attempt == 1:
                        raise ProviderRateLimitExhausted from error
                    raise LlmUnavailableError from error
                if attempt == 1:
                    raise ProviderRateLimitExhausted from error
                last_error = error
                delay = retry_after_seconds(error)
                # İlk çağrı ve 429 olayı yazılırken geçen süre aynı tek-primary
                # bütçesini tüketir. Bekleme ikinci denemeye ek süre yaratmaz.
                remaining = deadline - _monotonic()
                # Retry-After kalan bütçeye sığmazsa daha erken çağrı yapılmaz;
                # ikinci çağrı için süre kalmadığında açık fixture yolu seçilir.
                if delay > MAX_RETRY_AFTER_SECONDS or delay >= remaining:
                    raise ProviderRateLimitExhausted from error
                await _sleep(delay)
        raise AssertionError("sağlayıcı tekrar bütçesi aşıldı")


def build_chat_provider_client() -> LlmClient:
    settings = get_settings()
    if simulation_enabled(settings):
        return SameProviderRetryClient(settings, completion_fn=_simulate_rate_limit)
    client = build_learning_event_client()
    return (
        SameProviderRetryClient(settings) if isinstance(client, LearningEventLlmClient) else client
    )


def demo_fixture_answer(
    chunks: list[RetrievedChunk], *, mode: ChatMode, stage: SocraticStage | None
) -> DemoFixtureAnswer:
    """Sabit metin; yalnız mevcut kanıt kümesinden, özgün metadata ile kaynak kartı."""
    if not chunks or mode is ChatMode.EXAM:
        raise ProviderRateLimitExhausted
    from app.modules.assessment.socratic import hint_citation
    from app.modules.guardrails.citation import build_citations
    from app.schemas.chat import LlmCitation

    if mode is ChatMode.SOCRATIC:
        # Sokratik kaynak kartının mevcut çözüm gizleme sözleşmesi korunur.
        citations = [hint_citation(chunk) for chunk in chunks]
    else:
        citations, _ = build_citations(
            [LlmCitation(chunk_id=chunk.chunk_id) for chunk in chunks], chunks
        )
    return DemoFixtureAnswer(
        status=AnswerStatus.ANSWERED,
        mode=mode,
        text=DEMO_FIXTURE_TEXT,
        citations=citations,
        socratic_stage=stage,
        provider="recorded-demo-fixture",
    )
