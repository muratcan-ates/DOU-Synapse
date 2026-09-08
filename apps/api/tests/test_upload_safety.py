"""Yükleme reddi ve işlem hatası özel dosyaları sahipsiz bırakmamalıdır."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from io import BytesIO
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, UploadFile
from sqlalchemy.exc import IntegrityError, OperationalError

from app.api import deps, documents
from app.api.deps import CourseContext
from app.core.errors import ConflictError, NotFoundError, PayloadTooLargeError
from app.core.security import Principal
from app.core.upload_cleanup import register_document_deletion, register_upload_cleanup
from app.models.core import MembershipRole


def _context() -> CourseContext:
    return CourseContext(course_id=uuid4(), user_id=uuid4(), role=MembershipRole.INSTRUCTOR)


def _session(*, replaced: Any = None) -> Any:
    return SimpleNamespace(
        info={},
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
        get=AsyncMock(return_value=replaced),
    )


async def test_upload_reads_at_most_limit_plus_one() -> None:
    calls: list[int] = []

    class TrackedFile(BytesIO):
        def read(self, size: int = -1) -> bytes:
            calls.append(size)
            return super().read(size)

    file = UploadFile(file=TrackedFile(b"x" * 1024), filename="synthetic.md")
    with pytest.raises(PayloadTooLargeError):
        await documents.upload_document(
            context=_context(),
            session=_session(),
            settings=SimpleNamespace(max_upload_bytes=16, allowed_upload_extensions={".md"}),
            background=BackgroundTasks(),
            file=file,
            replaces_document_id=None,
        )
    assert calls == [17]


@pytest.mark.parametrize("kind", ["missing", "foreign", "superseded"])
async def test_invalid_replacement_never_writes_storage(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    context = _context()
    row = (
        None
        if kind == "missing"
        else SimpleNamespace(
            course_id=uuid4() if kind == "foreign" else context.course_id, superseded_at=object()
        )
    )
    storage = SimpleNamespace(save=AsyncMock(), delete=AsyncMock())
    monkeypatch.setattr(documents, "get_storage", lambda: storage)
    with pytest.raises(ConflictError if kind == "superseded" else NotFoundError):
        await documents.upload_document(
            context=context,
            session=_session(replaced=row),
            settings=SimpleNamespace(max_upload_bytes=1024, allowed_upload_extensions={".md"}),
            background=BackgroundTasks(),
            file=UploadFile(file=BytesIO(b"synthetic private material"), filename="synthetic.md"),
            replaces_document_id=uuid4(),
        )
    storage.save.assert_not_awaited()
    storage.delete.assert_not_awaited()


async def _dependency(
    monkeypatch: pytest.MonkeyPatch,
    session: Any,
    *,
    commit_error: BaseException | None = None,
    events: list[str] | None = None,
) -> Any:
    @asynccontextmanager
    async def transaction(user_id: Any) -> Any:
        yield session
        if events is not None:
            events.append("commit.attempt")
        if commit_error is not None:
            raise commit_error
        if events is not None:
            events.append("commit.confirmed")

    monkeypatch.setattr(deps, "rls_session", transaction)
    generator = deps.get_session(Principal(user_id=uuid4()))
    assert await anext(generator) is session
    return generator


async def test_handler_failure_cleans_only_new_key(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    delete = AsyncMock()
    generator = await _dependency(monkeypatch, session)
    register_upload_cleanup(session, key="synthetic/new-object", delete=delete)
    error = RuntimeError("synthetic flush failure")
    with pytest.raises(RuntimeError) as raised:
        await generator.athrow(error)
    assert raised.value is error
    delete.assert_awaited_once_with("synthetic/new-object")
    assert session.info == {}


async def test_successful_commit_keeps_object_and_discards_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session()
    delete = AsyncMock()
    generator = await _dependency(monkeypatch, session)
    register_upload_cleanup(session, key="synthetic/new-object", delete=delete)
    with pytest.raises(StopAsyncIteration):
        await anext(generator)
    delete.assert_not_awaited()
    assert session.info == {}


class _ConstraintRejected(Exception):
    sqlstate = "23514"


async def test_definite_constraint_commit_rejection_cleans_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session()
    delete = AsyncMock()
    error = IntegrityError("COMMIT", {}, _ConstraintRejected("synthetic deferred constraint"))
    generator = await _dependency(monkeypatch, session, commit_error=error)
    register_upload_cleanup(session, key="synthetic/new-object", delete=delete)
    with pytest.raises(IntegrityError) as raised:
        await anext(generator)
    assert raised.value is error
    delete.assert_awaited_once_with("synthetic/new-object")


@pytest.mark.parametrize("cancelled", [False, True])
async def test_ambiguous_commit_or_cancel_retains_object(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, cancelled: bool
) -> None:
    session = _session()
    delete = AsyncMock()
    marker = "SYNTHETIC_PRIVATE_OBJECT_MARKER"
    error = (
        asyncio.CancelledError()
        if cancelled
        else OperationalError("COMMIT", {}, Exception(marker), connection_invalidated=True)
    )
    generator = await _dependency(monkeypatch, session, commit_error=None if cancelled else error)
    register_upload_cleanup(session, key=marker, delete=delete)
    with pytest.raises(type(error)):
        if cancelled:
            await generator.athrow(error)
        else:
            await anext(generator)
    delete.assert_not_awaited()
    assert session.info == {}
    events = [record.context for record in caplog.records if hasattr(record, "context")]
    assert events == [
        {
            "event": "upload_reconciliation_required",
            "reason": "transaction_outcome_unknown",
            "object_count": 1,
        }
    ]
    assert marker not in caplog.text
    assert marker not in repr(events)


async def test_cleanup_failure_preserves_original_error_and_logs_no_payload(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    session = _session()
    marker = "SYNTHETIC_PRIVATE_STORAGE_URL"
    delete = AsyncMock(side_effect=RuntimeError(marker))
    generator = await _dependency(monkeypatch, session)
    register_upload_cleanup(session, key=marker, delete=delete)
    error = ValueError("synthetic handler failure")
    with pytest.raises(ValueError) as raised:
        await generator.athrow(error)
    assert raised.value is error
    assert marker not in caplog.text
    assert [record.context for record in caplog.records if hasattr(record, "context")] == [
        {"event": "upload_reconciliation_required", "reason": "cleanup_failed", "object_count": 1}
    ]


@pytest.mark.parametrize("case", ["invalid_replacement", "flush_failure", "success"])
async def test_real_upload_storage_lifecycle(
    client: Any, users: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Any, case: str
) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.core import Document
    from app.modules.ingestion.storage import LocalFileStorage, set_storage
    from tests.factories import create_course

    headers = users.auth(await users.create("synthetic-upload@example.invalid"))
    course_id = await create_course(client, headers, "SAFE-UPLOAD")
    storage = LocalFileStorage(tmp_path / "tracked")
    set_storage(storage)
    monkeypatch.setattr(documents, "_trigger_worker", AsyncMock())
    if case == "flush_failure":
        original = AsyncSession.flush

        async def fail_document_flush(self: AsyncSession, *args: Any, **kwargs: Any) -> None:
            if any(isinstance(row, Document) for row in self.new):
                raise RuntimeError("synthetic document flush failure")
            await original(self, *args, **kwargs)

        monkeypatch.setattr(AsyncSession, "flush", fail_document_flush)
    request = client.post(
        f"/courses/{course_id}/documents",
        headers=headers,
        files={"file": ("synthetic.md", b"private synthetic material", "text/markdown")},
        data={"replaces_document_id": str(uuid4())} if case == "invalid_replacement" else None,
    )
    if case == "flush_failure":
        with pytest.raises(RuntimeError, match="synthetic document flush"):
            await request
    else:
        response = await request
        assert response.status_code == (404 if case == "invalid_replacement" else 202)
    files = [path for path in (tmp_path / "tracked").rglob("*") if path.is_file()]
    assert len(files) == (1 if case == "success" else 0)
    if files:
        assert files[0].read_bytes() == b"private synthetic material"


@pytest.mark.parametrize("outcome", ["existing_object", "partial_write"])
async def test_unconfirmed_save_never_deletes_existing_or_partial_object(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, outcome: str
) -> None:
    from dataclasses import replace

    import httpx

    from app.core.errors import StorageUnavailableError
    from app.modules.ingestion.storage import SupabaseStorage

    key = "courses/synthetic/SYNTHETIC_OBJECT_KEY.md"
    previous = b"synthetic existing material"
    fresh = b"synthetic new material"
    objects = {key: previous} if outcome == "existing_object" else {}
    methods: list[str] = []

    async def storage_request(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.method == "POST":
            assert request.headers["x-upsert"] == "false"
            if outcome == "existing_object":
                return httpx.Response(409)
            objects[key] = request.content
            raise httpx.ReadTimeout("synthetic uncertain upload", request=request)
        if request.method == "DELETE":
            objects.pop(key, None)
            return httpx.Response(200)
        pytest.fail("beklenmeyen depolama isteği")

    store = SupabaseStorage(
        project_url="https://synthetic.invalid",
        service_role_key="synthetic-test-key",
        bucket="private",
        transport=httpx.MockTransport(storage_request),
    )
    validate = documents.validate_upload

    def fixed_key(**kwargs: Any) -> Any:
        return replace(validate(**kwargs), storage_key=key)

    monkeypatch.setattr(documents, "get_storage", lambda: store)
    monkeypatch.setattr(documents, "validate_upload", fixed_key)
    session = _session()
    generator = await _dependency(monkeypatch, session)
    with pytest.raises(StorageUnavailableError) as failed_save:
        await documents.upload_document(
            context=_context(),
            session=session,
            settings=SimpleNamespace(max_upload_bytes=1024, allowed_upload_extensions={".md"}),
            background=BackgroundTasks(),
            file=UploadFile(file=BytesIO(fresh), filename="synthetic.md"),
            replaces_document_id=None,
        )
    with pytest.raises(StorageUnavailableError):
        await generator.athrow(failed_save.value)
    assert objects == {key: previous if outcome == "existing_object" else fresh}
    assert methods == ["POST"]
    assert session.info == {}
    reconciliation = [
        record.context
        for record in caplog.records
        if getattr(record, "context", {}).get("event") == "upload_reconciliation_required"
    ]
    assert reconciliation == [
        {
            "event": "upload_reconciliation_required",
            "reason": "storage_outcome_unknown",
            "object_count": 1,
        }
    ]
    assert key not in repr(reconciliation)


async def _existing_document(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any, events: list[str]
) -> tuple[CourseContext, Any, Any, Any]:
    from app.modules.ingestion.storage import LocalFileStorage

    context = _context()
    key = "courses/SYNTHETIC_COURSE/SYNTHETIC_EXISTING_OBJECT.md"
    store = LocalFileStorage(tmp_path / "existing")
    await store.save(key, b"synthetic existing source bytes")
    row = SimpleNamespace(id=uuid4(), course_id=context.course_id, storage_path=key)
    session = _session(replaced=row)
    session.delete = AsyncMock(side_effect=lambda document: events.append("row.delete"))
    session.flush = AsyncMock(side_effect=lambda: events.append("row.flush"))
    delete = store.delete

    async def tracked_delete(object_key: str) -> None:
        events.append("object.delete")
        await delete(object_key)

    monkeypatch.setattr(store, "delete", tracked_delete)
    monkeypatch.setattr(documents, "get_storage", lambda: store)
    return context, row, session, store


async def test_document_delete_waits_for_confirmed_commit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    events: list[str] = []
    context, row, session, store = await _existing_document(monkeypatch, tmp_path, events)
    generator = await _dependency(monkeypatch, session, events=events)
    assert await documents.delete_document(row.id, context, session) is None
    assert events == ["row.delete", "row.flush"]
    assert await store.load(row.storage_path) == b"synthetic existing source bytes"
    with pytest.raises(StopAsyncIteration):
        await anext(generator)
    assert events == [
        "row.delete",
        "row.flush",
        "commit.attempt",
        "commit.confirmed",
        "object.delete",
    ]
    assert not (tmp_path / "existing" / row.storage_path).exists()
    assert session.info == {}


@pytest.mark.parametrize("outcome", ["constraint", "disconnect", "commit_cancel", "handler_failed"])
async def test_document_delete_retains_file_without_confirmed_commit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    caplog: pytest.LogCaptureFixture,
    outcome: str,
) -> None:
    events: list[str] = []
    context, row, session, store = await _existing_document(monkeypatch, tmp_path, events)
    errors = {
        "constraint": IntegrityError("COMMIT", {}, _ConstraintRejected("synthetic constraint")),
        "disconnect": OperationalError(
            "COMMIT", {}, Exception("synthetic disconnect"), connection_invalidated=True
        ),
        "commit_cancel": asyncio.CancelledError(),
        "handler_failed": RuntimeError("synthetic downstream failure"),
    }
    error = errors[outcome]
    generator = await _dependency(
        monkeypatch,
        session,
        commit_error=None if outcome == "handler_failed" else error,
        events=events,
    )
    await documents.delete_document(row.id, context, session)
    with pytest.raises(type(error)):
        if outcome == "handler_failed":
            await generator.athrow(error)
        else:
            await anext(generator)
    assert "object.delete" not in events
    assert "commit.confirmed" not in events
    assert await store.load(row.storage_path) == b"synthetic existing source bytes"
    assert session.info == {}
    reconciliation = [record.context for record in caplog.records if hasattr(record, "context")]
    assert reconciliation == (
        [
            {
                "event": "document_delete_reconciliation_required",
                "reason": "transaction_outcome_unknown",
                "object_count": 1,
            }
        ]
        if outcome in {"disconnect", "commit_cancel"}
        else []
    )
    assert row.storage_path not in caplog.text


async def test_document_delete_constraint_retains_original_file_and_conflict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    events: list[str] = []
    context, row, session, store = await _existing_document(monkeypatch, tmp_path, events)
    generator = await _dependency(monkeypatch, session, events=events)
    session.flush.side_effect = IntegrityError("DELETE", {}, _ConstraintRejected("synthetic FK"))
    with pytest.raises(ConflictError) as failure:
        await documents.delete_document(row.id, context, session)
    with pytest.raises(ConflictError) as propagated:
        await generator.athrow(failure.value)
    assert propagated.value is failure.value
    assert "commit.attempt" not in events
    assert "object.delete" not in events
    assert await store.load(row.storage_path) == b"synthetic existing source bytes"
    assert session.info == {}


async def test_document_delete_cleanup_failure_keeps_committed_result_and_safe_signal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any, caplog: pytest.LogCaptureFixture
) -> None:
    events: list[str] = []
    context, row, session, store = await _existing_document(monkeypatch, tmp_path, events)
    marker = "SYNTHETIC_PRIVATE_DELETE_ERROR"
    monkeypatch.setattr(store, "delete", AsyncMock(side_effect=RuntimeError(marker)))
    generator = await _dependency(monkeypatch, session, events=events)
    await documents.delete_document(row.id, context, session)
    with pytest.raises(StopAsyncIteration):
        await anext(generator)
    assert "commit.confirmed" in events
    assert await store.load(row.storage_path) == b"synthetic existing source bytes"
    assert session.info == {}
    assert [record.context for record in caplog.records if hasattr(record, "context")] == [
        {
            "event": "document_delete_reconciliation_required",
            "reason": "cleanup_failed",
            "object_count": 1,
        }
    ]
    assert marker not in caplog.text
    assert row.storage_path not in caplog.text


@pytest.mark.parametrize("operation", ["upload", "document_delete"])
async def test_cleanup_cancellation_reports_all_unfinished_objects_and_preserves_cancel(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, operation: str
) -> None:
    session = _session()
    generator = await _dependency(monkeypatch, session)
    keys = [f"SYNTHETIC_PRIVATE_OBJECT_{index}" for index in range(4)]
    remaining = set(keys)
    calls: list[str] = []
    started = asyncio.Event()
    never_finish = asyncio.Event()

    async def delete(key: str) -> None:
        calls.append(key)
        if key == keys[1]:
            raise RuntimeError("SYNTHETIC_PRIVATE_DELETE_ERROR")
        if key == keys[2]:
            started.set()
            await never_finish.wait()
        remaining.remove(key)

    register = register_upload_cleanup if operation == "upload" else register_document_deletion
    for key in keys:
        register(session, key=key, delete=delete)
    failure = ValueError("synthetic rollback trigger")
    work = generator.athrow(failure) if operation == "upload" else anext(generator)
    task = asyncio.ensure_future(work)
    await asyncio.wait_for(started.wait(), timeout=2)
    task.cancel("SYNTHETIC_PRIVATE_CANCEL_REASON")
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls == keys[:3]
    assert remaining == set(keys[1:])
    assert session.info == {}
    assert [record.context for record in caplog.records if hasattr(record, "context")] == [
        {
            "event": f"{operation}_reconciliation_required",
            "reason": "cleanup_outcome_unknown",
            "object_count": 3,
        }
    ]
    assert "SYNTHETIC_PRIVATE" not in caplog.text


@pytest.mark.parametrize("outcome", ["success", "deferred_rejection", "cleanup_failure"])
async def test_real_document_deletion_transaction_boundary(
    client: Any,
    users: Any,
    admin_engine: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    caplog: pytest.LogCaptureFixture,
    outcome: str,
) -> None:
    from sqlalchemy import text

    from app.modules.ingestion.storage import LocalFileStorage, set_storage
    from tests.factories import create_course

    headers = users.auth(await users.create("synthetic-delete@example.invalid"))
    course_id = await create_course(client, headers, "SAFE-DELETE")
    store = LocalFileStorage(tmp_path / "document-delete")
    set_storage(store)
    monkeypatch.setattr(documents, "_trigger_worker", AsyncMock())
    content = b"synthetic source kept until database commit"
    uploaded = await client.post(
        f"/courses/{course_id}/documents",
        headers=headers,
        files={"file": ("synthetic.md", content, "text/markdown")},
    )
    assert uploaded.status_code == 202, uploaded.text
    document_id = uploaded.json()["document"]["id"]
    async with admin_engine.begin() as conn:
        storage_key = await conn.scalar(
            text("SELECT storage_path FROM documents WHERE id = :id"), {"id": document_id}
        )
        await conn.execute(
            text(
                "INSERT INTO chunks (course_id, document_id, chunk_index, "
                "content_type, text, token_count) "
                "VALUES (:course_id, :document_id, 0, 'text', 'synthetic source', 2)"
            ),
            {"course_id": course_id, "document_id": document_id},
        )
    assert isinstance(storage_key, str)
    assert await store.load(storage_key) == content

    async def counts() -> tuple[int, int]:
        async with admin_engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT (SELECT count(*) FROM documents WHERE id = :id), "
                        "(SELECT count(*) FROM chunks WHERE document_id = :id)"
                    ),
                    {"id": document_id},
                )
            ).one()
        return int(row[0]), int(row[1])

    assert await counts() == (1, 1)
    delete = store.delete
    deletion_observations: list[tuple[int, int]] = []

    async def delete_only_committed(object_key: str) -> None:
        snapshot = await counts()
        deletion_observations.append(snapshot)
        assert snapshot == (0, 0), (
            "nesne silinirken belge/chunk silimi başka bağlantıda COMMIT olmuş olmalı"
        )
        if outcome == "cleanup_failure":
            raise RuntimeError("SYNTHETIC_PRIVATE_POSTCOMMIT_STORAGE_ERROR")
        await delete(object_key)

    monkeypatch.setattr(store, "delete", delete_only_committed)
    if outcome == "deferred_rejection":
        async with admin_engine.begin() as conn:
            await conn.execute(
                text("""
                CREATE FUNCTION app.test_reject_document_delete_commit() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN
                    RAISE EXCEPTION 'synthetic deferred delete rejection' USING ERRCODE = '23514';
                END $$
            """)
            )
            await conn.execute(
                text("""
                CREATE CONSTRAINT TRIGGER test_reject_document_delete_commit
                AFTER DELETE ON documents DEFERRABLE INITIALLY DEFERRED
                FOR EACH ROW EXECUTE FUNCTION app.test_reject_document_delete_commit()
            """)
            )
    try:
        request = client.delete(f"/courses/{course_id}/documents/{document_id}", headers=headers)
        if outcome == "deferred_rejection":
            with pytest.raises(IntegrityError) as rejected:
                await request
            assert rejected.value.orig.sqlstate == "23514"
        else:
            response = await request
            assert response.status_code == 204, response.text
        remains = outcome == "deferred_rejection"
        assert await counts() == ((1, 1) if remains else (0, 0))
        listed = await client.get(f"/courses/{course_id}/documents/{document_id}", headers=headers)
        assert listed.status_code == (200 if remains else 404)
        if outcome != "success":
            assert await store.load(storage_key) == content
        else:
            assert not (tmp_path / "document-delete" / storage_key).exists()
        assert deletion_observations == ([] if remains else [(0, 0)])
        events = [
            record.context
            for record in caplog.records
            if getattr(record, "context", {}).get("event")
            == "document_delete_reconciliation_required"
        ]
        assert events == (
            [
                {
                    "event": "document_delete_reconciliation_required",
                    "reason": "cleanup_failed",
                    "object_count": 1,
                }
            ]
            if outcome == "cleanup_failure"
            else []
        )
        assert "SYNTHETIC_PRIVATE_POSTCOMMIT_STORAGE_ERROR" not in caplog.text
    finally:
        if outcome == "deferred_rejection":
            async with admin_engine.begin() as conn:
                await conn.execute(
                    text("DROP TRIGGER test_reject_document_delete_commit ON documents")
                )
                await conn.execute(text("DROP FUNCTION app.test_reject_document_delete_commit()"))
