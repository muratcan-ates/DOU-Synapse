"""Öğrenme olaylarında gerçek API, yetki ve içeriksiz gösterim kabulü."""

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.chat import reset_rate_limit, set_pipeline
from tests.conftest import UserFactory
from tests.factories import Pipeline, build_course, install_pipeline, start


@pytest.mark.parametrize("given", ["B", "D"])
async def test_practice_records_four_event_types_and_instructor_summary(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    given: str,
) -> None:
    fixture = await build_course(client, users, admin_engine, approved=1)
    exam = await start(client, fixture, "practice")
    prefix = f"/courses/{fixture.course_id}"
    question_id = str(fixture.question_ids[0])
    hint = await client.post(
        f"{prefix}/exams/{exam['id']}/hint",
        headers=fixture.student,
        json={"question_id": question_id, "hint_level": 1},
    )
    assert hint.status_code == 200, hint.text
    assert hint.json()["source"]["chunk_id"] == str(fixture.chunk_ids[0])
    answer = await client.post(
        f"{prefix}/exams/{exam['id']}/answers",
        headers=fixture.student,
        json={"question_id": question_id, "given": given},
    )
    assert answer.status_code == 201, answer.text
    assert answer.json()["is_correct"] is False
    opened = await client.post(
        f"{prefix}/learning-events/citation-opened",
        headers=fixture.student,
        json={"chunk_id": answer.json()["why_wrong"]["chunk_id"], "session_id": exam["id"]},
    )
    assert opened.status_code == 201, opened.text
    events = await client.get(
        f"{prefix}/learning-events", headers=fixture.student, params={"session_id": exam["id"]}
    )
    assert events.status_code == 200, events.text
    assert {row["event_type"] for row in events.json()["items"]} == {
        "question_presented",
        "hint_requested",
        "answer_submitted",
        "citation_opened",
    }
    assert events.json()["total"] == 4
    assert all(
        set(row) == {"id", "event_type", "occurred_at", "session_id", "topic_id"}
        for row in events.json()["items"]
    )
    for days in (7, 30):
        summary = await client.get(
            f"{prefix}/learning-summary", headers=fixture.instructor, params={"days": days}
        )
        assert summary.status_code == 200, summary.text
        assert summary.json() == {
            "course_id": fixture.course_id,
            "days": days,
            "total_events": 4,
            "topics": [
                {
                    "topic_id": str(fixture.topic_id),
                    "topic_name": "Deadlock",
                    "wrong_answers": 1,
                    "hints_requested": 1,
                    "unsupported_refusals": 0,
                }
            ],
        }
    async with admin_engine.connect() as conn:
        actors = (
            (await conn.execute(text("SELECT DISTINCT actor_pseudo_id FROM learning_events")))
            .scalars()
            .all()
        )
    assert len(actors) == 1 and actors[0] != fixture.student_id


async def test_learning_summary_requires_course_instructor_and_valid_window(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    fixture = await build_course(client, users, admin_engine, approved=1)
    outsider = users.auth(await users.create("outsider-l2@example.test"))
    url = f"/courses/{fixture.course_id}/learning-summary"
    for auth, code in ((fixture.student, 403), (outsider, 404)):
        response = await client.get(url, headers=auth)
        assert response.status_code == code
        assert response.json()["error"]["code"] in {"permission_denied", "not_found"}
    for days in (0, 8, 31):
        response = await client.get(url, headers=fixture.instructor, params={"days": days})
        assert response.status_code == 422
        assert "topics" not in response.json()


async def test_learning_event_read_is_own_only_and_cannot_expose_grades(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    fixture = await build_course(client, users, admin_engine, approved=1)
    exam = await start(client, fixture, "exam")
    prefix = f"/courses/{fixture.course_id}"
    response = await client.post(
        f"{prefix}/exams/{exam['id']}/answers",
        headers=fixture.student,
        json={"question_id": str(fixture.question_ids[0]), "given": "B"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["score"] is None
    response = await client.get(f"{prefix}/learning-events", headers=fixture.student)
    assert response.json()["total"] == 2
    for row in response.json()["items"]:
        assert set(row) == {"id", "event_type", "occurred_at", "session_id", "topic_id"}
    response = await client.get(f"{prefix}/learning-events", headers=fixture.instructor)
    assert response.json() == {"items": [], "total": 0}


@pytest.mark.parametrize("bad_field", ["actor_pseudo_id", "event_type", "metadata_json"])
async def test_citation_cannot_accept_client_identity_or_event_payload(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    bad_field: str,
) -> None:
    fixture = await build_course(client, users, admin_engine, approved=1)
    response = await client.post(
        f"/courses/{fixture.course_id}/learning-events/citation-opened",
        headers=fixture.student,
        json={"chunk_id": str(fixture.chunk_ids[0]), bad_field: "forged"},
    )
    assert response.status_code == 422
    events = await client.get(
        f"/courses/{fixture.course_id}/learning-events", headers=fixture.student
    )
    assert events.json() == {"items": [], "total": 0}


async def test_citation_rejects_unknown_session_and_running_exam(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    fixture = await build_course(client, users, admin_engine, approved=1)
    url = f"/courses/{fixture.course_id}/learning-events/citation-opened"
    response = await client.post(
        url,
        headers=fixture.student,
        json={"chunk_id": str(fixture.chunk_ids[0]), "session_id": str(uuid4())},
    )
    assert response.status_code == 404
    await start(client, fixture, "exam")
    response = await client.post(
        url, headers=fixture.student, json={"chunk_id": str(fixture.chunk_ids[0])}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "exam_in_progress"


async def test_chat_scope_refusal_records_without_provider_or_raw_text(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    fixture = await build_course(client, users, admin_engine, approved=0)
    pipeline = Pipeline()
    install_pipeline(pipeline)
    reset_rate_limit()
    try:
        response = await client.post(
            f"/courses/{fixture.course_id}/chat",
            headers=fixture.student,
            json={"question": "Bugün yemek tarifi verir misin?"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] in {"out_of_scope", "insufficient_context"}
        assert pipeline.generator.calls == 0
        async with admin_engine.connect() as conn:
            rows = (
                (
                    await conn.execute(
                        text(
                            "SELECT event_type, metadata_json, outcome_json FROM learning_events "
                            "WHERE course_id=:cid"
                        ),
                        {"cid": UUID(fixture.course_id)},
                    )
                )
                .mappings()
                .all()
            )
        assert [dict(row) for row in rows] == [
            {
                "event_type": "unsupported_refusal",
                "metadata_json": {"source": "chat"},
                "outcome_json": None,
            }
        ]
    finally:
        set_pipeline()
        reset_rate_limit()


async def test_provider_429_is_recorded_even_if_chat_transaction_rolls_back(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings
    from app.core.db import rls_session
    from app.modules.agent.provider_events import LearningEventLlmClient, learning_provider_context
    from app.modules.generation.llm import LiteLlmClient, LlmRequest

    fixture = await build_course(client, users, admin_engine, approved=0)

    class ProviderRateLimit(Exception):
        status_code = 429

    async def limited(*args: object, **kwargs: object) -> None:
        raise ProviderRateLimit

    monkeypatch.setattr(LiteLlmClient, "_attempt", limited)
    adapter = LearningEventLlmClient(get_settings())
    with pytest.raises(ProviderRateLimit):
        async with rls_session(fixture.student_id) as session:
            with learning_provider_context(session, UUID(fixture.course_id)):
                await adapter._attempt(
                    "groq/test-model", LlmRequest(system="test", user="test"), budget=1, attempt=0
                )
    response = await client.get(
        f"/courses/{fixture.course_id}/learning-events", headers=fixture.student
    )
    assert response.status_code == 200, response.text
    assert [row["event_type"] for row in response.json()["items"]] == ["provider_rate_limited"]


async def test_telemetry_fault_preserves_original_429_and_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    from app.core.config import get_settings
    from app.modules.agent import provider_events
    from app.modules.generation.llm import LiteLlmClient, LlmRequest

    class ProviderRateLimit(Exception):
        status_code = 429

    original = ProviderRateLimit()

    async def limited(*args: object, **kwargs: object) -> None:
        raise original

    async def broken_telemetry() -> None:
        raise RuntimeError("sentetik ölçüm arızası")

    monkeypatch.setattr(LiteLlmClient, "_attempt", limited)
    monkeypatch.setattr(provider_events, "record_provider_rate_limit", broken_telemetry)
    adapter = provider_events.LearningEventLlmClient(get_settings())
    with pytest.raises(ProviderRateLimit) as caught:
        await adapter._attempt(
            "groq/test-model", LlmRequest(system="test", user="test"), budget=1, attempt=0
        )
    assert caught.value is original

    async def cancelled_telemetry() -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr(provider_events, "record_provider_rate_limit", cancelled_telemetry)
    with pytest.raises(asyncio.CancelledError):
        await adapter._attempt(
            "groq/test-model", LlmRequest(system="test", user="test"), budget=1, attempt=0
        )
