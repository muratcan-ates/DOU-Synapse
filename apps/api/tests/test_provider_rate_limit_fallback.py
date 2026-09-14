"""429 tekrarı, fixture kökeni ve kapsam reddi; canlı sağlayıcı kalitesi iddiası yok."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app.contracts import AnswerStatus, ChatMode, GeneratedAnswer, GuardrailVerdict
from app.core.config import Environment, get_settings
from app.modules.agent import provider_events, provider_fallback
from app.modules.agent.answers import produce_answer
from app.modules.agent.pipeline import get_generator, set_pipeline
from app.modules.agent.provider_fallback import (
    DEMO_FIXTURE_LABEL,
    DEMO_FIXTURE_TEXT,
    DemoFixtureAnswer,
    ProviderRateLimitExhausted,
    RateLimitSimulationForbidden,
    SameProviderRetryClient,
    build_chat_provider_client,
    provider_attempt_context,
    retry_after_seconds,
)
from app.modules.generation.llm import LlmRequest, LlmUnavailableError
from app.schemas.chat import LlmAnswerPayload, to_chat_response
from tests.conftest import UserFactory
from tests.factories import FakeRetriever, build_course, make_chunk


class TransportFailure(Exception):
    def __init__(self, status_code: int = 429, retry_after: str = "1") -> None:
        self.status_code = status_code
        self.headers = {"Retry-After": retry_after}


@pytest.fixture
def waits(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    values: list[float] = []

    async def record_wait(seconds: float) -> None:
        values.append(seconds)

    monkeypatch.setattr(provider_fallback, "_sleep", record_wait)
    return values


def configured_settings():
    return get_settings().model_copy(
        update={
            "llm_primary_model": "groq/test-primary",
            "llm_fallback_model": "gemini/test-secondary",
            "llm_max_retries": 3,
        }
    )


@pytest.mark.parametrize("attempt_budget", [0, -1])
async def test_nonpositive_attempt_budget_never_calls_provider(attempt_budget: int) -> None:
    calls = 0

    async def forbidden(**kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        raise AssertionError("sıfır çağrı bütçesi açıldı")

    adapter = SameProviderRetryClient(configured_settings(), completion_fn=forbidden)
    with pytest.raises(LlmUnavailableError) as caught:
        await adapter.complete(
            LlmRequest(system="sistem", user="kaynak", max_provider_attempts=attempt_budget)
        )
    assert not isinstance(caught.value, ProviderRateLimitExhausted)
    assert calls == 0


async def test_retry_honors_retry_after_and_uses_only_same_primary(waits: list[float]) -> None:
    calls: list[dict[str, Any]] = []

    async def completion(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        if len(calls) == 1:
            raise TransportFailure(retry_after="2")
        return {
            "choices": [{"message": {"content": "kaynaklı çıktı"}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 4},
        }

    adapter = SameProviderRetryClient(configured_settings(), completion_fn=completion)
    request = LlmRequest(system="sistem", user="kaynak", max_tokens=128, max_provider_attempts=1)
    answer = await adapter.complete(request)
    assert [call["model"] for call in calls] == ["groq/test-primary", "groq/test-primary"]
    assert all(call["max_tokens"] == 128 for call in calls)
    assert calls[0]["messages"] == calls[1]["messages"]
    assert waits == [2.0]
    assert answer.model == "groq/test-primary"
    assert answer.prompt_tokens == 12 and answer.completion_tokens == 4


async def test_retry_shares_monotonic_deadline_including_telemetry_and_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [100.0]
    calls: list[tuple[float, float]] = []
    delays: list[float] = []

    async def completion(**kwargs: Any) -> dict[str, Any]:
        calls.append((clock[0], kwargs["timeout"]))
        if len(calls) == 1:
            clock[0] += 2.0
            raise TransportFailure(retry_after="2")
        return {"choices": [{"message": {"content": "kaynaklı çıktı"}}]}

    async def measured_telemetry() -> None:
        clock[0] += 1.0

    async def controlled_wait(seconds: float) -> None:
        delays.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr(provider_fallback, "_monotonic", lambda: clock[0])
    monkeypatch.setattr(provider_fallback, "_sleep", controlled_wait)
    monkeypatch.setattr(provider_events, "record_provider_rate_limit", measured_telemetry)
    settings = configured_settings().model_copy(update={"llm_timeout_seconds": 10.0})
    adapter = SameProviderRetryClient(settings, completion_fn=completion)
    await adapter.complete(LlmRequest(system="sistem", user="kaynak", max_provider_attempts=1))
    assert calls == [(100.0, 10.0), (105.0, 5.0)]
    assert delays == [2.0]


@pytest.mark.parametrize("elapsed", [8.0, 9.0, 10.0])
async def test_retry_after_cannot_extend_exhausted_deadline(
    monkeypatch: pytest.MonkeyPatch, elapsed: float
) -> None:
    clock = [100.0]
    calls = 0
    delays: list[float] = []
    original = TransportFailure(retry_after="2")

    async def limited(**kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        clock[0] += elapsed
        raise original

    async def controlled_wait(seconds: float) -> None:
        delays.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr(provider_fallback, "_monotonic", lambda: clock[0])
    monkeypatch.setattr(provider_fallback, "_sleep", controlled_wait)
    settings = configured_settings().model_copy(update={"llm_timeout_seconds": 10.0})
    adapter = SameProviderRetryClient(settings, completion_fn=limited)
    with pytest.raises(ProviderRateLimitExhausted) as caught:
        await adapter.complete(LlmRequest(system="sistem", user="kaynak"))
    assert caught.value.__cause__ is original
    assert calls == 1 and delays == []


async def test_scheduler_oversleep_never_starts_retry_after_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [100.0]
    calls = 0
    original = TransportFailure(retry_after="1")

    async def limited(**kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        raise original

    async def oversleep(seconds: float) -> None:
        assert seconds == 1.0
        clock[0] += 10.0

    monkeypatch.setattr(provider_fallback, "_monotonic", lambda: clock[0])
    monkeypatch.setattr(provider_fallback, "_sleep", oversleep)
    settings = configured_settings().model_copy(update={"llm_timeout_seconds": 10.0})
    adapter = SameProviderRetryClient(settings, completion_fn=limited)
    with pytest.raises(ProviderRateLimitExhausted) as caught:
        await adapter.complete(LlmRequest(system="sistem", user="kaynak"))
    assert caught.value.__cause__ is original
    assert calls == 1


async def test_second_429_exhausts_exactly_two_attempts_and_preserves_cause(
    waits: list[float],
) -> None:
    calls: list[str] = []
    original = TransportFailure()

    async def limited(**kwargs: Any) -> None:
        calls.append(kwargs["model"])
        raise original

    adapter = SameProviderRetryClient(configured_settings(), completion_fn=limited)
    with pytest.raises(ProviderRateLimitExhausted) as caught:
        await adapter.complete(LlmRequest(system="sistem", user="kaynak"))
    assert caught.value.__cause__ is original
    assert calls == ["groq/test-primary", "groq/test-primary"]
    assert waits == [1.0]


async def test_retry_failure_after_429_preserves_cause_without_switching(
    waits: list[float],
) -> None:
    calls: list[str] = []
    original = TransportFailure(status_code=503)

    async def unavailable(**kwargs: Any) -> None:
        calls.append(kwargs["model"])
        if len(calls) == 1:
            raise TransportFailure()
        raise original

    adapter = SameProviderRetryClient(configured_settings(), completion_fn=unavailable)
    with pytest.raises(ProviderRateLimitExhausted) as caught:
        await adapter.complete(LlmRequest(system="sistem", user="kaynak", max_provider_attempts=1))
    assert caught.value.__cause__ is original
    assert calls == ["groq/test-primary", "groq/test-primary"]
    assert waits == [1.0]


async def test_long_retry_after_never_retries_before_provider_allows(waits: list[float]) -> None:
    calls = 0

    async def limited(**kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        raise TransportFailure(retry_after="120")

    adapter = SameProviderRetryClient(configured_settings(), completion_fn=limited)
    with pytest.raises(ProviderRateLimitExhausted):
        await adapter.complete(LlmRequest(system="sistem", user="kaynak"))
    assert calls == 1 and waits == []


@pytest.mark.parametrize("header,expected", [("0", 0.0), ("3", 3.0), ("bozuk", 1.0), ("-1", 1.0)])
def test_retry_after_header_parser(header: str, expected: float) -> None:
    assert retry_after_seconds(TransportFailure(retry_after=header)) == expected


def test_retry_after_http_date_and_response_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 13, 12, 0, 0, tzinfo=UTC)

    monkeypatch.setattr(provider_fallback, "datetime", FixedDateTime)
    future = TransportFailure(retry_after="Sun, 13 Sep 2026 12:00:03 GMT")
    assert retry_after_seconds(future) == 3.0
    past = TransportFailure(retry_after="Sun, 13 Sep 2026 11:59:59 GMT")
    assert retry_after_seconds(past) == 0.0
    response_error = TransportFailure()
    del response_error.headers
    response_error.response = SimpleNamespace(headers={"rEtRy-AfTeR": "2"})
    assert retry_after_seconds(response_error) == 2.0
    assert retry_after_seconds(RuntimeError()) == 1.0


async def test_non_429_never_switches_model_or_becomes_fixture(waits: list[float]) -> None:
    calls: list[str] = []
    original = TransportFailure(status_code=401)

    async def denied(**kwargs: Any) -> None:
        calls.append(kwargs["model"])
        raise original

    adapter = SameProviderRetryClient(configured_settings(), completion_fn=denied)
    with pytest.raises(LlmUnavailableError) as caught:
        await adapter.complete(LlmRequest(system="sistem", user="kaynak"))
    assert not isinstance(caught.value, ProviderRateLimitExhausted)
    assert caught.value.__cause__ is original
    assert calls == ["groq/test-primary"] and waits == []


async def test_telemetry_failure_does_not_mask_retry_or_cancellation(
    monkeypatch: pytest.MonkeyPatch, waits: list[float]
) -> None:
    original = TransportFailure()

    async def limited(**kwargs: Any) -> None:
        raise original

    async def broken_telemetry() -> None:
        raise RuntimeError("sentetik ölçüm hatası")

    monkeypatch.setattr(provider_events, "record_provider_rate_limit", broken_telemetry)
    adapter = SameProviderRetryClient(configured_settings(), completion_fn=limited)
    with pytest.raises(ProviderRateLimitExhausted) as caught:
        await adapter.complete(LlmRequest(system="sistem", user="kaynak"))
    assert caught.value.__cause__ is original
    assert waits == [1.0]

    async def cancelled_telemetry() -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr(provider_events, "record_provider_rate_limit", cancelled_telemetry)
    with pytest.raises(asyncio.CancelledError):
        await adapter.complete(LlmRequest(system="sistem", user="kaynak"))
    assert waits == [1.0]


async def test_slow_telemetry_exhausts_deadline_without_a_second_provider_call() -> None:
    entered = asyncio.Event()
    cancelled = asyncio.Event()
    never = asyncio.Event()
    calls = 0
    original = TransportFailure(retry_after="0")

    async def limited(**kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        raise original

    async def slow_telemetry() -> None:
        entered.set()
        try:
            await never.wait()
        finally:
            cancelled.set()

    settings = configured_settings().model_copy(update={"llm_timeout_seconds": 0.05})
    adapter = SameProviderRetryClient(settings, completion_fn=limited)
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(provider_events, "record_provider_rate_limit", slow_telemetry)
        with pytest.raises(ProviderRateLimitExhausted) as caught:
            await asyncio.wait_for(
                adapter.complete(LlmRequest(system="sistem", user="kaynak")), timeout=2.0
            )
    assert caught.value.__cause__ is original
    assert entered.is_set() and cancelled.is_set()
    assert calls == 1


@pytest.mark.parametrize("environment", [Environment.DEMO, Environment.PRODUCTION])
def test_simulation_flag_is_rejected_outside_local_environment(
    monkeypatch: pytest.MonkeyPatch, environment: Environment
) -> None:
    monkeypatch.setenv("LLM_SIMULATE_RATE_LIMIT", "1")
    settings = get_settings().model_copy(update={"environment": environment})
    monkeypatch.setattr(provider_fallback, "get_settings", lambda: settings)
    with pytest.raises(RateLimitSimulationForbidden):
        build_chat_provider_client()


def test_simulation_never_impersonates_real_evaluation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_SIMULATE_RATE_LIMIT", "1")
    settings = get_settings().model_copy(update={"eval_runtime_enabled": True})
    with pytest.raises(RateLimitSimulationForbidden):
        provider_fallback.simulation_enabled(settings)


async def test_provider_counter_resets_on_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_SIMULATE_RATE_LIMIT", "1")

    async def cancelled(**kwargs: Any) -> None:
        raise asyncio.CancelledError

    settings = configured_settings()
    adapter = SameProviderRetryClient(settings, completion_fn=cancelled)
    with pytest.raises(asyncio.CancelledError), provider_attempt_context(settings) as counter:
        await adapter.complete(LlmRequest(system="sistem", user="kaynak"))
    assert counter is not None and counter.attempts == 1
    assert provider_fallback._attempt_counter.get() is None


def test_only_trusted_answer_subtype_marks_fixture() -> None:
    raw = LlmAnswerPayload.model_validate(
        {"status": "answered", "answer": DEMO_FIXTURE_TEXT, "fixture": True}
    )
    answer = GeneratedAnswer(status=AnswerStatus.ANSWERED, mode=ChatMode.QA, text=raw.answer)
    response = to_chat_response(answer, session_id=uuid4(), message_id=uuid4())
    assert response.fixture is None
    assert response.provider_attempts is None
    trusted = DemoFixtureAnswer(status=answer.status, mode=answer.mode, text=answer.text)
    assert to_chat_response(trusted, session_id=uuid4(), message_id=uuid4()).fixture is True


async def test_fixture_still_must_pass_guardrail_chain(
    monkeypatch: pytest.MonkeyPatch, waits: list[float]
) -> None:
    monkeypatch.setenv("LLM_SIMULATE_RATE_LIMIT", "1")

    class BlockAll:
        def check(self, answer: GeneratedAnswer, chunks: list) -> GuardrailVerdict:
            return GuardrailVerdict(blocked=True, reason="sentetik kaynak reddi")

    outcome = await produce_answer(
        question="Deadlock nedir?",
        course_id=uuid4(),
        mode=ChatMode.QA,
        decision=None,
        retriever=FakeRetriever([make_chunk(dense_score=0.99)]),
        generator=get_generator(),
        guardrails=[BlockAll()],
        settings=get_settings(),
        allow_regeneration=False,
    )
    response = to_chat_response(outcome.answer, session_id=uuid4(), message_id=uuid4())
    assert response.status is AnswerStatus.INSUFFICIENT_CONTEXT
    assert response.fixture is None and response.citations == []
    assert response.provider_attempts == 2
    assert DEMO_FIXTURE_LABEL not in response.answer
    assert waits == [1.0]


@pytest.mark.parametrize("mode", ["qa", "socratic"])
async def test_api_simulation_returns_labelled_fixture_with_sources_and_two_events(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    waits: list[float],
    mode: str,
) -> None:
    fixture = await build_course(client, users, admin_engine, approved=0)
    chunk = make_chunk(chunk_id=fixture.chunk_ids[0], dense_score=0.99)
    monkeypatch.setenv("LLM_SIMULATE_RATE_LIMIT", "1")
    set_pipeline(retriever_factory=lambda session: FakeRetriever([chunk]))
    try:
        response = await client.post(
            f"/courses/{fixture.course_id}/chat",
            json={"question": "Deadlock nedir?", "mode": mode},
            headers=fixture.student,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "answered" and body["fixture"] is True
        assert body["answer"] == DEMO_FIXTURE_TEXT
        assert body["provider_attempts"] == 2
        assert body["citations"][0]["chunk_id"] == str(chunk.chunk_id)
        assert body["citations"][0]["file_name"] == chunk.file_name
        assert body["citations"][0]["location"] == chunk.location
        assert waits == [1.0]
        if mode == "socratic":
            assert body["socratic_stage"] == "diagnose"
            assert body["hints"][0]["text"] == DEMO_FIXTURE_TEXT

        events = await client.get(
            f"/courses/{fixture.course_id}/learning-events", headers=fixture.student
        )
        assert events.status_code == 200, events.text
        assert [item["event_type"] for item in events.json()["items"]].count(
            "provider_rate_limited"
        ) == 2

        history = await client.get(
            f"/courses/{fixture.course_id}/chat/sessions/{body['session_id']}",
            headers=fixture.student,
        )
        assert history.status_code == 200, history.text
        saved = next(item for item in history.json()["items"] if item["role"] == "assistant")
        assert saved["content"] == DEMO_FIXTURE_TEXT
        assert saved["citations"][0]["chunk_id"] == str(chunk.chunk_id)

        if mode == "qa":
            cached = await client.post(
                f"/courses/{fixture.course_id}/chat",
                json={"question": "Deadlock nedir?", "mode": mode},
                headers=fixture.student,
            )
            assert cached.status_code == 200, cached.text
            assert cached.json()["cached"] is True
            assert cached.json()["fixture"] is None
            assert cached.json()["provider_attempts"] == 0
            assert cached.json()["answer"] == DEMO_FIXTURE_TEXT
            assert cached.json()["citations"] == body["citations"]
            assert waits == [1.0]
    finally:
        set_pipeline()


@pytest.mark.parametrize("empty_sources", [False, True])
async def test_api_evidence_refusal_invokes_provider_zero_times(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    waits: list[float],
    empty_sources: bool,
) -> None:
    fixture = await build_course(client, users, admin_engine, approved=0)
    chunk = make_chunk(chunk_id=fixture.chunk_ids[0], dense_score=0.01, fts_score=0)
    monkeypatch.setenv("LLM_SIMULATE_RATE_LIMIT", "1")
    set_pipeline(retriever_factory=lambda session: FakeRetriever([] if empty_sources else [chunk]))
    try:
        response = await client.post(
            f"/courses/{fixture.course_id}/chat",
            json={"question": "Roma restoran rezervasyonu fiyatları", "mode": "qa"},
            headers=fixture.student,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == ("insufficient_context" if empty_sources else "out_of_scope")
        assert body["provider_attempts"] == 0 and body["fixture"] is None
        assert body["citations"] == [] and DEMO_FIXTURE_LABEL not in body["answer"]
        assert waits == []
        events = await client.get(
            f"/courses/{fixture.course_id}/learning-events", headers=fixture.student
        )
        assert events.status_code == 200, events.text
        assert "provider_rate_limited" not in [
            item["event_type"] for item in events.json()["items"]
        ]
    finally:
        set_pipeline()
