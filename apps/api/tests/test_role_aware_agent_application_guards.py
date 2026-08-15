"""Application-layer guard contracts for the 005 mutation matrix.

These tests cover seams that the PostgreSQL/RLS mutation package cannot see:
cache identity, provider reservation ordering, process-local concurrency,
provider-side output ceilings, privacy-safe guard-event shape, and the
transaction ordering between chat finalization and exam start.

They use only synthetic users, course identifiers, and content.  No prompt,
answer, email, provider payload, or stable real-user identifier is retained as
evidence by the mutation runner.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api import exams as exams_api
from app.api.chat import (
    produce_answer,
    question_hash,
    reset_rate_limit,
    set_pipeline,
)
from app.contracts import (
    AnswerStatus,
    AssistantAudience,
    ChatMode,
    GeneratedAnswer,
    RetrievedChunk,
)
from app.core.config import Settings
from app.modules.agent import quota as agent_quota
from app.modules.assessment import exam_state
from app.modules.generation.llm import LlmCompletion, LlmRequest
from app.modules.generation.service import GenerationService
from tests.conftest import UserFactory
from tests.factories import (
    FakeCitationGuardrail,
    FakeGenerator,
    FakeRetriever,
    create_course,
    make_chunk,
    sourced_answer,
)
from tests.test_exams import build_course, start

COURSE_ID = UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture(autouse=True)
def _reset_chat_singletons() -> Iterator[None]:
    """Keep the process-local limiter and injected pipeline test-local."""

    reset_rate_limit()
    yield
    set_pipeline()
    reset_rate_limit()


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("audience", AssistantAudience.INSTRUCTOR),
        ("policy_revision", "policy-v2"),
        ("prompt_revision", "prompt-v2"),
        ("corpus_revision", "corpus-v2"),
    ],
)
def test_cache_identity_changes_with_audience_and_every_revision(
    field: str,
    changed: AssistantAudience | str,
) -> None:
    """Every server-owned dimension must invalidate the application cache key."""

    base_values: dict[str, AssistantAudience | str] = {
        "audience": AssistantAudience.STUDENT,
        "policy_revision": "policy-v1",
        "prompt_revision": "prompt-v1",
        "corpus_revision": "corpus-v1",
    }
    base = question_hash(ChatMode.QA, "Deadlock nedir?", **base_values)  # type: ignore[arg-type]
    changed_values = {**base_values, field: changed}
    candidate = question_hash(
        ChatMode.QA,
        "Deadlock nedir?",
        **changed_values,  # type: ignore[arg-type]
    )

    assert candidate != base


async def test_provider_budget_is_reserved_before_generation() -> None:
    """The durable precharge callback runs before the provider seam."""

    chunk = make_chunk()
    events: list[str] = []

    class OrderedGenerator(FakeGenerator):
        async def generate(self, **kwargs: Any) -> GeneratedAnswer:
            events.append("provider")
            return await super().generate(**kwargs)

    async def reserve(input_token_ceiling: int) -> None:
        assert input_token_ceiling > 0
        events.append("reserve")

    outcome = await produce_answer(
        question="Deadlock nedir?",
        course_id=COURSE_ID,
        mode=ChatMode.QA,
        decision=None,
        retriever=FakeRetriever([chunk]),
        generator=OrderedGenerator([sourced_answer(chunk)]),
        guardrails=[FakeCitationGuardrail()],
        settings=Settings(dev_auth_enabled=True, evidence_threshold=0.35),
        audience=AssistantAudience.STUDENT,
        max_output_tokens=321,
        before_generation=reserve,
        allow_regeneration=False,
    )

    assert outcome.answer.status is AnswerStatus.ANSWERED
    assert events == ["reserve", "provider"]


async def test_process_concurrency_gate_rejects_second_same_user_request(
    client: AsyncClient,
    users: UserFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The in-process gate remains a fast first layer before durable quota."""

    instructor_id = await users.create("mutation.concurrency@dogus.edu.tr")
    headers = users.auth(instructor_id)
    course_id = await create_course(client, headers, "MUT-CONC")
    chunk = make_chunk()
    first_entered = asyncio.Event()
    release_first = asyncio.Event()

    class BlockingGenerator:
        def __init__(self) -> None:
            self.calls = 0

        async def generate(
            self,
            *,
            question: str,
            chunks: list[RetrievedChunk],
            mode: ChatMode,
            socratic_stage: Any = None,
            student_attempt: str | None = None,
        ) -> GeneratedAnswer:
            del question, chunks, mode, socratic_stage, student_attempt
            self.calls += 1
            if self.calls == 1:
                first_entered.set()
                await release_first.wait()
            return sourced_answer(chunk)

    generator = BlockingGenerator()
    set_pipeline(
        retriever_factory=lambda _session: FakeRetriever([chunk]),
        generator=generator,
        guardrails=[FakeCitationGuardrail()],
    )

    async def allowed_reservation(**_kwargs: Any) -> agent_quota.TokenReservation:
        return agent_quota.TokenReservation(
            allowed=True,
            reason=None,
            audience=AssistantAudience.INSTRUCTOR,
            retry_after_seconds=0,
            reservation_id=uuid4(),
        )

    async def no_op(**_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(agent_quota, "reserve", allowed_reservation)
    monkeypatch.setattr(agent_quota, "reconcile", no_op)
    monkeypatch.setattr(agent_quota, "record_guard_event", no_op)

    first = asyncio.create_task(
        client.post(
            f"/courses/{course_id}/chat",
            json={"question": "Deadlock nedir?"},
            headers=headers,
        )
    )
    await asyncio.wait_for(first_entered.wait(), timeout=2)
    second = await client.post(
        f"/courses/{course_id}/chat",
        json={"question": "Deadlock nedir?"},
        headers=headers,
    )
    release_first.set()
    first_response = await asyncio.wait_for(first, timeout=2)

    assert first_response.status_code == 200, first_response.text
    assert second.status_code == 409, second.text
    assert second.json()["error"]["code"] == "concurrent_request"
    assert generator.calls == 1


async def test_global_output_ceiling_is_sent_to_provider() -> None:
    """A course-provided cap cannot raise the deployment/provider ceiling."""

    calls: list[LlmRequest] = []

    class RecordingLlm:
        async def complete(self, request: LlmRequest) -> LlmCompletion:
            calls.append(request)
            return LlmCompletion(
                text='{"status":"answered","answer":"Tamam","citations":[]}',
                provider="fake",
                model="fake-v1",
            )

    service = GenerationService(
        settings=Settings(
            dev_auth_enabled=True,
            llm_chat_max_tokens=128,
            llm_max_retries=0,
        ),
        llm=RecordingLlm(),  # type: ignore[arg-type]
    )
    await service.generate_role_aware_with_claims(
        question="Deadlock nedir?",
        chunks=[make_chunk()],
        mode=ChatMode.QA,
        audience=AssistantAudience.STUDENT,
        max_output_tokens=4096,
    )

    assert len(calls) == 1
    assert calls[0].max_tokens == 128


async def test_guard_event_schema_has_no_free_text_or_request_identity(
    admin_engine: AsyncEngine,
) -> None:
    """Privacy is structural: the event table cannot store user content."""

    async with admin_engine.connect() as connection:
        columns = set(
            (
                await connection.scalars(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name='ai_guard_events'"
                    )
                )
            ).all()
        )

    assert columns == {
        "id",
        "course_id",
        "user_id",
        "audience",
        "event_type",
        "created_at",
        "bucket_start",
    }


async def test_exam_dependency_blocks_chat_and_history_before_provider(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    """All three protected routes close at dependency entry during an exam."""

    fixture = await build_course(client, users, admin_engine)
    chunk = make_chunk()
    generator = FakeGenerator([sourced_answer(chunk)])
    set_pipeline(
        retriever_factory=lambda _session: FakeRetriever([chunk]),
        generator=generator,
        guardrails=[FakeCitationGuardrail()],
    )
    await start(client, fixture, "exam")

    chat = await client.post(
        f"/courses/{fixture.course_id}/chat",
        json={"question": "Deadlock nedir?"},
        headers=fixture.student,
    )
    listing = await client.get(
        f"/courses/{fixture.course_id}/chat/sessions",
        headers=fixture.student,
    )
    detail = await client.get(
        f"/courses/{fixture.course_id}/chat/sessions/{UUID(int=0)}",
        headers=fixture.student,
    )

    assert [chat.status_code, listing.status_code, detail.status_code] == [403, 403, 403]
    assert generator.calls == 0


async def test_chat_finalization_and_exam_start_share_user_lock(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Once chat finalization holds the lock, exam start waits for its commit."""

    fixture = await build_course(client, users, admin_engine)
    chunk = make_chunk()
    install_pipeline_for_course = FakeRetriever([chunk])
    set_pipeline(
        retriever_factory=lambda _session: install_pipeline_for_course,
        generator=FakeGenerator([sourced_answer(chunk)]),
        guardrails=[FakeCitationGuardrail()],
    )
    final_check_holds_lock = asyncio.Event()
    release_final_check = asyncio.Event()
    exam_lock_returned = asyncio.Event()
    original = exam_state.active_exam_session
    original_exam_lock = exams_api.acquire_user_assessment_lock
    calls = 0

    async def pause_only_final_check(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            final_check_holds_lock.set()
            await release_final_check.wait()
        return await original(*args, **kwargs)

    async def allowed_reservation(**_kwargs: Any) -> agent_quota.TokenReservation:
        return agent_quota.TokenReservation(
            allowed=True,
            reason=None,
            audience=AssistantAudience.STUDENT,
            retry_after_seconds=0,
            reservation_id=uuid4(),
        )

    async def no_op(**_kwargs: Any) -> None:
        return None

    async def observe_exam_lock(*args: Any, **kwargs: Any) -> None:
        await original_exam_lock(*args, **kwargs)
        exam_lock_returned.set()

    monkeypatch.setattr(exam_state, "active_exam_session", pause_only_final_check)
    monkeypatch.setattr(exams_api, "acquire_user_assessment_lock", observe_exam_lock)
    monkeypatch.setattr(agent_quota, "reserve", allowed_reservation)
    monkeypatch.setattr(agent_quota, "reconcile", no_op)

    chat_task = asyncio.create_task(
        client.post(
            f"/courses/{fixture.course_id}/chat",
            json={"question": "Deadlock nedir?"},
            headers=fixture.student,
        )
    )
    await asyncio.wait_for(final_check_holds_lock.wait(), timeout=2)
    exam_task = asyncio.create_task(start(client, fixture, "exam"))
    exam_acquired_while_chat_held_lock = False
    try:
        await asyncio.wait_for(exam_lock_returned.wait(), timeout=1)
        exam_acquired_while_chat_held_lock = True
    except TimeoutError:
        pass
    finally:
        release_final_check.set()

    chat = await asyncio.wait_for(chat_task, timeout=2)
    exam = await asyncio.wait_for(exam_task, timeout=2)

    assert exam_acquired_while_chat_held_lock is False
    assert chat.status_code == 200, chat.text
    assert exam["mode"] == "exam"


async def test_export_and_exam_start_share_user_lock(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exam start cannot acquire the user lock while an export holds it."""

    fixture = await build_course(client, users, admin_engine)
    export_holds_lock = asyncio.Event()
    release_export = asyncio.Event()
    exam_lock_returned = asyncio.Event()
    original_check = exam_state.any_active_student_exam_session
    original_exam_lock = exams_api.acquire_user_assessment_lock

    async def pause_export_check(*args: Any, **kwargs: Any) -> Any:
        export_holds_lock.set()
        await release_export.wait()
        return await original_check(*args, **kwargs)

    async def observe_exam_lock(*args: Any, **kwargs: Any) -> None:
        await original_exam_lock(*args, **kwargs)
        exam_lock_returned.set()

    monkeypatch.setattr(exam_state, "any_active_student_exam_session", pause_export_check)
    monkeypatch.setattr(exams_api, "acquire_user_assessment_lock", observe_exam_lock)
    export_task = asyncio.create_task(client.get("/me/export", headers=fixture.student))
    await asyncio.wait_for(export_holds_lock.wait(), timeout=2)
    exam_task = asyncio.create_task(start(client, fixture, "exam"))
    exam_acquired_while_export_held_lock = False
    try:
        await asyncio.wait_for(exam_lock_returned.wait(), timeout=1)
        exam_acquired_while_export_held_lock = True
    except TimeoutError:
        pass
    finally:
        release_export.set()

    export = await asyncio.wait_for(export_task, timeout=2)
    exam = await asyncio.wait_for(exam_task, timeout=2)

    assert exam_acquired_while_export_held_lock is False
    assert export.status_code == 200, export.text
    assert exam["mode"] == "exam"
