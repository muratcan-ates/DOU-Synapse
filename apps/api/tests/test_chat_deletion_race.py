"""B4 regression: deleting history must fence an already pending first chat turn.

Only model I/O is replaced. HTTP handlers, transactions, FK/RLS and persistence
remain real. Events establish statement ordering; no sleep-based race assertions.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api import chat, privacy
from app.contracts import AnswerStatus, ChatMode, Citation, GeneratedAnswer
from app.core.errors import ConflictError
from app.modules.agent.answers import AnswerOutcome
from app.modules.chat import lifecycle
from tests.conftest import UserFactory
from tests.factories import create_course, enroll_student

QUESTION = "SYNTHETIC_PENDING_PRIVATE_QUESTION"
ANSWER = "Sentetik bekletilen yanıt."


class SuspendedModel:
    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.status = AnswerStatus.INSUFFICIENT_CONTEXT

    async def answer(self, **kwargs: Any) -> AnswerOutcome:
        self.entered.set()
        await self.release.wait()
        return AnswerOutcome(
            GeneratedAnswer(
                status=self.status,
                mode=kwargs["mode"],
                text=ANSWER,
                citations=(
                    [
                        Citation(
                            chunk_id=uuid4(),
                            file_name="sentetik.pdf",
                            location="Sayfa 1",
                            quote="Sentetik kaynak.",
                        )
                    ]
                    if self.status is AnswerStatus.ANSWERED
                    else []
                ),
            )
        )


async def _fixture(
    client: AsyncClient,
    users: UserFactory,
    monkeypatch: pytest.MonkeyPatch,
    *,
    as_student: bool = False,
) -> tuple[UUID, dict[str, str], UUID, SuspendedModel]:
    user_id = await users.create("synthetic-delete-race@example.invalid")
    headers = users.auth(user_id)
    course_id = await create_course(client, headers, "DELETE-RACE")
    if as_student:
        student_email = "synthetic-race-student@example.com"
        user_id = await users.create(student_email)
        await enroll_student(client, headers, course_id, student_email)
        headers = users.auth(user_id)
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
@pytest.mark.parametrize("as_student", [False, True])
async def test_completed_bulk_delete_does_not_allow_pending_new_chat_to_repopulate(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    scope: str,
    as_student: bool,
) -> None:
    user_id, headers, course_id, model = await _fixture(
        client, users, monkeypatch, as_student=as_student
    )
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
        assert response.json()["error"]["code"] == "chat_history_changed"
        fresh = await client.post(
            f"/courses/{course_id}/chat",
            headers=headers,
            json={"question": "Silmeden sonra yeni soru"},
        )
        assert fresh.status_code == 200, fresh.text
        assert await _counts(admin_engine, user_id) == (1, 2)
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
        result = await asyncio.wait_for(pending, 5)
        assert result.status_code == 409, result.text
        assert result.json()["error"]["code"] == "chat_history_changed"
        assert await _counts(admin_engine, user_id) == (0, 0)
    finally:
        model.release.set()
        await asyncio.gather(pending, return_exceptions=True)


@pytest.mark.parametrize("as_student", [False, True])
async def test_profile_delete_does_not_leave_inflight_new_chat_after_success(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    as_student: bool,
) -> None:
    user_id, headers, course_id, model = await _fixture(
        client, users, monkeypatch, as_student=as_student
    )
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
        assert not isinstance(post_result, BaseException), repr(post_result)
        assert post_result.status_code == 409, post_result.text
        assert post_result.json()["error"]["code"] == "chat_history_changed"
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


@pytest.mark.parametrize("deleted_scope", ["other_course", "other_user", "other_session"])
async def test_scoped_delete_preserves_unrelated_pending_new_chat(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    deleted_scope: str,
) -> None:
    user_id, headers, course_id, model = await _fixture(client, users, monkeypatch)
    delete_headers = headers
    if deleted_scope == "other_course":
        other_course = await create_course(client, headers, "OTHER-COURSE")
        endpoint = f"/courses/{other_course}/chat/sessions"
    elif deleted_scope == "other_user":
        other_user = await users.create("other-delete-race@example.invalid")
        delete_headers = users.auth(other_user)
        endpoint = "/me/chat-history"
    else:
        model.release.set()
        first = await client.post(
            f"/courses/{course_id}/chat", headers=headers, json={"question": "Başka oturum"}
        )
        assert first.status_code == 200, first.text
        endpoint = f"/courses/{course_id}/chat/sessions/{first.json()['session_id']}"
        model.entered.clear()
        model.release.clear()
    pending = asyncio.create_task(
        client.post(f"/courses/{course_id}/chat", headers=headers, json={"question": QUESTION})
    )
    try:
        await asyncio.wait_for(model.entered.wait(), 5)
        deleted = await asyncio.wait_for(client.delete(endpoint, headers=delete_headers), 5)
        assert deleted.status_code == 200, deleted.text
        model.release.set()
        result = await asyncio.wait_for(pending, 5)
        assert result.status_code == 200, result.text
        assert await _counts(admin_engine, user_id) == (1, 2)
    finally:
        model.release.set()
        await asyncio.gather(pending, return_exceptions=True)


async def test_single_delete_preserves_pending_continuation_of_another_same_course_session(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, headers, course_id, model = await _fixture(client, users, monkeypatch)
    model.release.set()
    sessions = []
    for question in ["Birinci sohbet", "İkinci sohbet"]:
        result = await client.post(
            f"/courses/{course_id}/chat", headers=headers, json={"question": question}
        )
        assert result.status_code == 200, result.text
        sessions.append(result.json()["session_id"])
    model.release.clear()
    model.entered.clear()
    pending = asyncio.create_task(
        client.post(
            f"/courses/{course_id}/chat",
            headers=headers,
            json={"question": QUESTION, "session_id": sessions[1]},
        )
    )
    try:
        await asyncio.wait_for(model.entered.wait(), 5)
        deleted = await client.delete(
            f"/courses/{course_id}/chat/sessions/{sessions[0]}", headers=headers
        )
        assert deleted.status_code == 200, deleted.text
        model.release.set()
        result = await asyncio.wait_for(pending, 5)
        assert result.status_code == 200, result.text
        assert result.json()["session_id"] == sessions[1]
        assert await _counts(admin_engine, user_id) == (1, 4)
    finally:
        model.release.set()
        await asyncio.gather(pending, return_exceptions=True)


async def test_rolled_back_delete_does_not_cancel_pending_chat(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, headers, course_id, model = await _fixture(client, users, monkeypatch)
    original_delete = privacy._delete_owned_chat_sessions

    async def failing_delete(*args: Any, **kwargs: Any) -> int:
        await original_delete(*args, **kwargs)
        raise ConflictError("Sentetik işlem geri alındı.")

    monkeypatch.setattr(privacy, "_delete_owned_chat_sessions", failing_delete)
    pending = asyncio.create_task(
        client.post(f"/courses/{course_id}/chat", headers=headers, json={"question": QUESTION})
    )
    try:
        await asyncio.wait_for(model.entered.wait(), 5)
        deleted = await client.delete("/me/chat-history", headers=headers)
        assert deleted.status_code == 409, deleted.text
        async with admin_engine.connect() as connection:
            assert await connection.scalar(text("SELECT count(*) FROM chat_privacy_revisions")) == 0
        model.release.set()
        result = await asyncio.wait_for(pending, 5)
        assert result.status_code == 200, result.text
        assert await _counts(admin_engine, user_id) == (1, 2)
    finally:
        model.release.set()
        await asyncio.gather(pending, return_exceptions=True)


async def test_chat_finalization_first_is_then_deleted_after_its_commit(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, headers, course_id, model = await _fixture(client, users, monkeypatch)
    model.release.set()
    written = asyncio.Event()
    allow_commit = asyncio.Event()
    deletion_entered = asyncio.Event()
    original_append = chat._append_messages
    original_delete = privacy._delete_owned_chat_sessions

    async def held_append(*args: Any, **kwargs: Any) -> Any:
        result = await original_append(*args, **kwargs)
        written.set()
        await allow_commit.wait()
        return result

    async def observed_delete(*args: Any, **kwargs: Any) -> int:
        deletion_entered.set()
        return await original_delete(*args, **kwargs)

    monkeypatch.setattr(chat, "_append_messages", held_append)
    monkeypatch.setattr(privacy, "_delete_owned_chat_sessions", observed_delete)
    pending = asyncio.create_task(
        client.post(f"/courses/{course_id}/chat", headers=headers, json={"question": QUESTION})
    )
    deletion: asyncio.Task[Any] | None = None
    try:
        await asyncio.wait_for(written.wait(), 5)
        deletion = asyncio.create_task(client.delete("/me/chat-history", headers=headers))
        await asyncio.wait_for(deletion_entered.wait(), 5)
        assert not deletion.done()
        allow_commit.set()
        result, deleted = await asyncio.wait_for(asyncio.gather(pending, deletion), 5)
        assert result.status_code == 200, result.text
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["deleted_sessions"] == 1
        assert await _counts(admin_engine, user_id) == (0, 0)
    finally:
        allow_commit.set()
        await asyncio.gather(pending, *([deletion] if deletion else []), return_exceptions=True)


@pytest.mark.parametrize("path", ["cache", "budget_refusal", "socratic", "answered"])
async def test_delete_fences_every_common_finalization_path(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    user_id, headers, course_id, model = await _fixture(client, users, monkeypatch)
    model.release.set()
    if path == "answered":
        model.status = AnswerStatus.ANSWERED
    final_entered = asyncio.Event()
    final_release = asyncio.Event()
    original_finalize = lifecycle.finalize_session

    async def held_finalize(*args: Any, **kwargs: Any) -> Any:
        final_entered.set()
        await final_release.wait()
        return await original_finalize(*args, **kwargs)

    monkeypatch.setattr(lifecycle, "finalize_session", held_finalize)
    if path == "cache":

        async def cached(*args: Any, **kwargs: Any) -> GeneratedAnswer:
            return GeneratedAnswer(
                status=AnswerStatus.INSUFFICIENT_CONTEXT,
                mode=ChatMode.QA,
                text=ANSWER,
                citations=[],
            )

        monkeypatch.setattr(chat, "_lookup_cache", cached)
    elif path == "budget_refusal":

        async def exhausted(*args: Any, **kwargs: Any) -> bool:
            return True

        monkeypatch.setattr(chat.policy_service, "budget_exhausted", exhausted)
    pending = asyncio.create_task(
        client.post(
            f"/courses/{course_id}/chat",
            headers=headers,
            json={"question": QUESTION, "mode": "socratic" if path == "socratic" else "qa"},
        )
    )
    try:
        await asyncio.wait_for(final_entered.wait(), 5)
        assert model.entered.is_set() is (path not in {"cache", "budget_refusal"})
        deleted = await client.delete(f"/courses/{course_id}/chat/sessions", headers=headers)
        assert deleted.status_code == 200, deleted.text
        final_release.set()
        result = await asyncio.wait_for(pending, 5)
        assert result.status_code == 409, result.text
        assert result.json()["error"]["code"] == "chat_history_changed"
        assert await _counts(admin_engine, user_id) == (0, 0)
        async with admin_engine.connect() as connection:
            assert await connection.scalar(text("SELECT count(*) FROM request_logs")) == 0
            assert await connection.scalar(text("SELECT count(*) FROM answer_cache")) == 0
    finally:
        final_release.set()
        await asyncio.gather(pending, return_exceptions=True)


@pytest.mark.parametrize("change", ["revoked", "role"])
async def test_finalization_rechecks_membership_and_audience_after_model(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    user_id, headers, course_id, model = await _fixture(client, users, monkeypatch)
    pending = asyncio.create_task(
        client.post(f"/courses/{course_id}/chat", headers=headers, json={"question": QUESTION})
    )
    try:
        await asyncio.wait_for(model.entered.wait(), 5)
        async with admin_engine.begin() as connection:
            statement = (
                "UPDATE course_memberships SET status='revoked' WHERE user_id=:uid"
                if change == "revoked"
                else "UPDATE course_memberships SET role='student' WHERE user_id=:uid"
            )
            await connection.execute(text(statement), {"uid": user_id})
        model.release.set()
        result = await asyncio.wait_for(pending, 5)
        assert result.status_code == 409, result.text
        assert result.json()["error"]["code"] == "chat_history_changed"
        assert await _counts(admin_engine, user_id) == (0, 0)
    finally:
        model.release.set()
        await asyncio.gather(pending, return_exceptions=True)


@pytest.mark.parametrize("scope", ["all", "profile"])
async def test_global_deletion_cancels_pending_requests_in_both_courses(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    scope: str,
) -> None:
    user_id, headers, course_id, first_model = await _fixture(client, users, monkeypatch)
    second_course = await create_course(client, headers, "SECOND-PENDING-COURSE")
    second_model = SuspendedModel()

    async def scoped_model(**kwargs: Any) -> AnswerOutcome:
        model = first_model if kwargs["course_id"] == course_id else second_model
        return await model.answer(**kwargs)

    monkeypatch.setattr(chat, "produce_answer", scoped_model)
    pending = [
        asyncio.create_task(
            client.post(f"/courses/{cid}/chat", headers=headers, json={"question": QUESTION})
        )
        for cid in [course_id, second_course]
    ]
    try:
        await asyncio.wait_for(
            asyncio.gather(first_model.entered.wait(), second_model.entered.wait()), 5
        )
        deleted = await asyncio.wait_for(
            client.delete("/me" if scope == "profile" else "/me/chat-history", headers=headers), 5
        )
        assert deleted.status_code == 200, deleted.text
        first_model.release.set()
        second_model.release.set()
        results = await asyncio.wait_for(asyncio.gather(*pending), 5)
        assert [r.status_code for r in results] == [409, 409]
        assert await _counts(admin_engine, user_id) == (0, 0)
    finally:
        first_model.release.set()
        second_model.release.set()
        await asyncio.gather(*pending, return_exceptions=True)
