"""B4 regression: deleting history must fence an already pending first chat turn.

Only model I/O is replaced. HTTP handlers, transactions, FK/RLS and persistence
remain real. Events establish statement ordering; no sleep-based race assertions.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import pytest
from app.api import chat, privacy
from app.contracts import AnswerStatus, GeneratedAnswer
from app.modules.agent.answers import AnswerOutcome
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import UserFactory
from tests.factories import create_course

QUESTION = "SYNTHETIC_PENDING_PRIVATE_QUESTION"
ANSWER = "Sentetik bekletilen yanıt."


class SuspendedModel:
    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def answer(self, **kwargs: Any) -> AnswerOutcome:
        self.entered.set()
        await self.release.wait()
        return AnswerOutcome(
            GeneratedAnswer(
                status=AnswerStatus.INSUFFICIENT_CONTEXT,
                mode=kwargs["mode"],
                text=ANSWER,
                citations=[],
            )
        )


async def _fixture(
    client: AsyncClient, users: UserFactory, monkeypatch: pytest.MonkeyPatch
) -> tuple[UUID, dict[str, str], UUID, SuspendedModel]:
    user_id = await users.create("synthetic-delete-race@example.invalid")
    headers = users.auth(user_id)
    course_id = await create_course(client, headers, "DELETE-RACE")
    model = SuspendedModel()
    monkeypatch.setattr(chat, "produce_answer", model.answer)
    chat.reset_rate_limit()
    return user_id, headers, course_id, model


async def _counts(engine: AsyncEngine, user_id: UUID) -> tuple[int, int]:
    async with engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    "SELECT (SELECT count(*) FROM chat_sessions WHERE user_id=:uid), "
                    "(SELECT count(*) FROM chat_messages m JOIN chat_sessions s "
                    "ON s.id=m.session_id WHERE s.user_id=:uid)"
                ),
                {"uid": user_id},
            )
        ).one()
    return int(row[0]), int(row[1])


@pytest.mark.parametrize("scope", ["course", "all"])
async def test_completed_bulk_delete_does_not_allow_pending_new_chat_to_repopulate(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    scope: str,
) -> None:
    user_id, headers, course_id, model = await _fixture(client, users, monkeypatch)
    pending = asyncio.create_task(
        client.post(f"/courses/{course_id}/chat", headers=headers, json={"question": QUESTION})
    )
    try:
        await asyncio.wait_for(model.entered.wait(), timeout=5)
        assert await _counts(admin_engine, user_id) == (0, 0), "new session is uncommitted"
        endpoint = (
            f"/courses/{course_id}/chat/sessions" if scope == "course" else "/me/chat-history"
        )
        deleted = await asyncio.wait_for(client.delete(endpoint, headers=headers), timeout=5)
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["deleted_sessions"] == 0
        assert not pending.done(), "DELETE response must precede model completion"
        model.release.set()
        response = await asyncio.wait_for(pending, timeout=5)
        persisted = await _counts(admin_engine, user_id)
        assert persisted == (0, 0), (
            f"completed {scope} DELETE was undone by pre-existing POST: "
            f"status={response.status_code}, sessions/messages={persisted}"
        )
        assert response.status_code == 409, response.text
    finally:
        model.release.set()
        await asyncio.gather(pending, return_exceptions=True)


async def test_deleted_existing_session_is_not_recreated_by_pending_turn(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, headers, course_id, model = await _fixture(client, users, monkeypatch)
    model.release.set()
    first = await client.post(
        f"/courses/{course_id}/chat", headers=headers, json={"question": "Sentetik ilk soru"}
    )
    assert first.status_code == 200, first.text
    session_id = first.json()["session_id"]
    model.entered.clear()
    model.release.clear()
    pending = asyncio.create_task(
        client.post(
            f"/courses/{course_id}/chat",
            headers=headers,
            json={"question": QUESTION, "session_id": session_id},
        )
    )
    try:
        await asyncio.wait_for(model.entered.wait(), timeout=5)
        deleted = await asyncio.wait_for(
            client.delete(f"/courses/{course_id}/chat/sessions/{session_id}", headers=headers),
            timeout=5,
        )
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["deleted_sessions"] == 1
        model.release.set()
        result = (await asyncio.wait_for(asyncio.gather(pending, return_exceptions=True), 5))[0]
        # Current code rejects with DB/RLS error; a later fix should return a
        # controlled 409. This case measures non-recreation, not correct UX yet.
        assert isinstance(result, Exception) or result.status_code >= 400
        assert await _counts(admin_engine, user_id) == (0, 0)
    finally:
        model.release.set()
        await asyncio.gather(pending, return_exceptions=True)


async def test_profile_delete_does_not_leave_inflight_new_chat_after_success(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, headers, course_id, model = await _fixture(client, users, monkeypatch)
    delete_scanned = asyncio.Event()
    original_delete = privacy._delete_owned_chat_sessions

    async def observed_delete(*args: Any, **kwargs: Any) -> int:
        result = await original_delete(*args, **kwargs)
        delete_scanned.set()
        return result

    monkeypatch.setattr(privacy, "_delete_owned_chat_sessions", observed_delete)
    pending = asyncio.create_task(
        client.post(f"/courses/{course_id}/chat", headers=headers, json={"question": QUESTION})
    )
    deletion: asyncio.Task[Any] | None = None
    try:
        await asyncio.wait_for(model.entered.wait(), timeout=5)
        deletion = asyncio.create_task(client.delete("/me", headers=headers))
        await asyncio.wait_for(delete_scanned.wait(), timeout=5)
        model.release.set()
        results = await asyncio.wait_for(
            asyncio.gather(pending, deletion, return_exceptions=True), timeout=8
        )
        post_result, deleted = results
        assert not isinstance(deleted, BaseException), repr(deleted)
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["deleted_chat_sessions"] == 0
        persisted = await _counts(admin_engine, user_id)
        assert persisted == (0, 0), (
            "profile anonymization succeeded but retained pending chat: "
            f"POST={getattr(post_result, 'status_code', type(post_result).__name__)}, "
            f"sessions/messages={persisted}"
        )
    finally:
        model.release.set()
        await asyncio.gather(pending, *([deletion] if deletion else []), return_exceptions=True)
