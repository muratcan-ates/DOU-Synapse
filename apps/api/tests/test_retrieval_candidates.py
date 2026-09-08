"""C1 contracts: offline call controls plus real dou_app source/filter/tie regressions.

The corpus is synthetic and hashing-based; these tests do not certify semantic
quality. Real SQL tests deliberately invert UUID ordering while preserving source
hashes. The shared factory's default UUID-based fake hash is explicitly replaced.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.core.config import Settings
from app.core.db import get_engine, rls_session, set_rls_context
from app.core.vector_space import current_space
from app.modules.ingestion.embedding import HashingEmbeddingProvider, set_embedding_provider
from app.modules.retrieval import dense, fts, service
from tests.conftest import WORKER_DSN, UserFactory
from tests.factories import create_course, seed_document

BODY = "Semafor kritik bolgeyi korur."


@pytest.fixture
async def worker_engine(clean_tables: None) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(WORKER_DSN)
    yield engine
    await engine.dispose()


class RecordingSession:
    def __init__(self, previous_mode: str = "auto") -> None:
        self.previous_mode = previous_mode
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    async def execute(self, query: object, params: dict[str, object] | None = None) -> object:
        self.calls.append((str(query), params))
        row = SimpleNamespace(
            id=UUID(int=1),
            document_id=UUID(int=2),
            file_name="kaynak.pdf",
            page_number=7,
            slide_number=2,
            section_title="Kritik bölüm",
            text=BODY,
            embedding_space=current_space(),
            similarity=0.75,
        )
        return SimpleNamespace(all=lambda: [row], scalar_one=lambda: self.previous_mode)


@pytest.mark.parametrize("previous_mode", ["auto", "force_custom_plan", "force_generic_plan"])
@pytest.mark.parametrize("selected", [None, (), (UUID(int=2),)])
async def test_dense_call_retains_metadata_filter_distinction_and_bounded_multiplier(
    selected: tuple[UUID, ...] | None,
    previous_mode: str,
) -> None:
    session = RecordingSession(previous_mode)
    set_embedding_provider(HashingEmbeddingProvider())
    try:
        rows = await dense.dense_search(
            session,
            course_id=UUID(int=3),
            query="semafor",
            limit=3,
            document_ids=selected,
            candidate_multiplier=4,
        )
    finally:
        set_embedding_provider(None)
    assert len(session.calls) == 5
    assert session.calls[0][0] == "SELECT set_config('hnsw.iterative_scan', 'relaxed_order', true)"
    assert session.calls[1][0] == "SELECT current_setting('plan_cache_mode')"
    assert session.calls[2][0] == "SELECT set_config('plan_cache_mode', 'force_custom_plan', true)"
    assert session.calls[4] == (
        "SELECT set_config('plan_cache_mode', :mode, true)",
        {"mode": previous_mode},
    )
    assert session.calls[3][1] == {
        "query_vector": session.calls[3][1]["query_vector"],
        "course_id": UUID(int=3),
        "limit": 3,
        "candidate_limit": 12,
        "filter_documents": selected is not None,
        "document_ids": list(selected or ()),
    }
    assert len(rows) == 1
    result = rows[0]
    assert (result.chunk_id, result.document_id, result.file_name) == (
        UUID(int=1),
        UUID(int=2),
        "kaynak.pdf",
    )
    assert (result.page_number, result.slide_number, result.section_title, result.text) == (
        7,
        2,
        "Kritik bölüm",
        BODY,
    )
    assert result.dense_score == 0.75


@pytest.mark.parametrize("multiplier", [0, 9])
async def test_invalid_direct_multiplier_fails_before_embedding_or_sql(multiplier: int) -> None:
    session = RecordingSession()
    with pytest.raises(ValueError, match="1 ile 8"):
        await dense.dense_search(
            session,
            course_id=UUID(int=3),
            query="semafor",
            limit=3,
            candidate_multiplier=multiplier,
        )
    assert session.calls == []


@pytest.mark.parametrize("query,limit", [("", 3), ("  ", 3), ("semafor", 0)])
async def test_empty_dense_request_does_not_change_transaction_settings(
    query: str, limit: int
) -> None:
    session = RecordingSession()
    assert await dense.dense_search(session, course_id=UUID(int=3), query=query, limit=limit) == []
    assert session.calls == []


async def test_hybrid_custom_settings_pass_multiplier_to_actual_dense_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dense_call = AsyncMock(return_value=[])
    monkeypatch.setattr(service, "dense_search", dense_call)
    monkeypatch.setattr(service, "fts_search", AsyncMock(return_value=[]))
    settings = Settings(
        _env_file=None,
        environment="local",
        dev_auth_enabled=True,
        embedding_provider="hashing",
        retrieval_dense_candidate_multiplier=3,
    )
    assert (
        await service.HybridRetriever(RecordingSession(), settings).search(
            course_id=UUID(int=3), query="semafor", limit=3
        )
        == []
    )
    assert dense_call.await_args.kwargs["candidate_multiplier"] == 3


def test_sql_places_ann_order_before_bounded_window_and_content_order_outside() -> None:
    sql = str(dense._SQL)
    inner, outer = sql.split("    SELECT n.id", 1)
    assert "WITH nearest AS MATERIALIZED" in inner
    assert (
        "ORDER BY c.embedding <=> CAST(:query_vector AS vector)\n        LIMIT :candidate_limit"
        in inner
    )
    assert "ORDER BY distance," not in inner
    assert "ORDER BY n.distance + 0, d.file_hash, n.chunk_index\n    LIMIT :limit" in outer
    assert "c.embedding IS NOT NULL" in inner
    assert "c.course_id = :course_id" in inner
    assert "c.document_id = ANY(CAST(:document_ids AS uuid[]))" in inner
    for value in (
        "n.document_id",
        "d.file_name",
        "n.page_number",
        "n.slide_number",
        "n.section_title",
        "n.text",
        "n.embedding_space",
        "similarity",
    ):
        assert value in outer


@pytest.mark.parametrize("search", [dense.dense_search])
async def test_real_two_reingests_with_reversed_uuid_order_preserve_content_sources(
    search: object,
    client: AsyncClient,
    users: UserFactory,
    worker_engine: AsyncEngine,
) -> None:
    owner = await users.create("content-ties@synthetic.invalid")
    course = await create_course(client, users.auth(owner), "C1-TIES")
    sources = [
        (name, hashlib.sha256((f"# {name}\n" + (BODY + "\n") * 5).encode()).hexdigest())
        for name in ("alpha.md", "beta.md")
    ]
    sources.sort(key=lambda item: item[1])
    cohorts: list[list[object]] = []
    returned_ids: list[set[UUID]] = []
    for generation in range(2):
        async with worker_engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM documents WHERE course_id=:course"), {"course": course}
            )
        for rank, (name, content_hash) in enumerate(sources):
            uuid_rank = 1 - rank if generation == 0 else rank
            doc_id = UUID(int=100 + generation * 100 + uuid_rank)
            chunk_ids = [
                UUID(int=1000 + generation * 100 + rank * 10 + index) for index in range(5)
            ]
            with patch("tests.factories.uuid4", side_effect=[doc_id, *chunk_ids]):
                seeded = await seed_document(
                    worker_engine,
                    course_id=course,
                    uploaded_by=owner,
                    file_name=name,
                    passages=[(index + 1, BODY) for index in range(5)],
                    embeddings=True,
                    embedding_space=current_space(),
                )
            async with worker_engine.begin() as connection:
                await connection.execute(
                    text("UPDATE documents SET file_hash=:hash WHERE id=:id"),
                    {"hash": content_hash, "id": seeded.document_id},
                )
                await connection.execute(
                    text(
                        "UPDATE chunks SET slide_number=chunk_index+10, section_title=:title "
                        "WHERE document_id=:id"
                    ),
                    {"title": name, "id": seeded.document_id},
                )
        async with rls_session(owner) as session:
            rows = await search(session, course_id=course, query="semafor", limit=3)
        assert len(rows) == 3
        scores = [
            row.dense_score if search is dense.dense_search else row.fts_score for row in rows
        ]
        assert len({round(score, 9) for score in scores}) == 1
        normalized = [
            (row.file_name, row.page_number, row.slide_number, row.section_title, row.text)
            for row in rows
        ]
        expected_name = sources[0][0]
        assert normalized == [(expected_name, i + 1, i + 10, expected_name, BODY) for i in range(3)]
        cohorts.append(normalized)
        returned_ids.append({row.chunk_id for row in rows})
    assert cohorts[0] == cohorts[1]
    assert returned_ids[0].isdisjoint(returned_ids[1])


@pytest.mark.parametrize("search", [dense.dense_search, fts.fts_search])
async def test_real_document_filters_empty_foreign_and_unauthorized_scopes(
    search: object,
    client: AsyncClient,
    users: UserFactory,
    worker_engine: AsyncEngine,
) -> None:
    owner = await users.create("filter-owner@synthetic.invalid")
    outsider = await users.create("filter-outsider@synthetic.invalid")
    course = await create_course(client, users.auth(owner), "C1-FILTER-A")
    foreign_course = await create_course(client, users.auth(owner), "C1-FILTER-B")
    allowed = await seed_document(
        worker_engine,
        course_id=course,
        uploaded_by=owner,
        file_name="allowed.md",
        passages=[BODY],
        embeddings=True,
    )
    foreign = await seed_document(
        worker_engine,
        course_id=foreign_course,
        uploaded_by=owner,
        file_name="foreign.md",
        passages=[BODY],
        embeddings=True,
    )
    async with rls_session(owner) as session:
        unrestricted = await search(
            session, course_id=course, query="semafor", limit=3, document_ids=None
        )
        assert [row.chunk_id for row in unrestricted] == allowed.chunk_ids
        assert (
            await search(session, course_id=course, query="semafor", limit=3, document_ids=()) == []
        )
        assert (
            await search(
                session,
                course_id=course,
                query="semafor",
                limit=3,
                document_ids=(foreign.document_id,),
            )
            == []
        )
        selected = await search(
            session,
            course_id=course,
            query="semafor",
            limit=3,
            document_ids=(allowed.document_id, foreign.document_id),
        )
        assert [row.chunk_id for row in selected] == allowed.chunk_ids
    async with rls_session(outsider) as session:
        assert (
            await search(
                session,
                course_id=course,
                query="semafor",
                limit=3,
                document_ids=(allowed.document_id,),
            )
            == []
        )
    async with worker_engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE course_memberships SET status='revoked' "
                "WHERE course_id=:course AND user_id=:owner"
            ),
            {"course": course, "owner": owner},
        )
    async with rls_session(owner) as session:
        assert await search(session, course_id=course, query="semafor", limit=3) == []


@pytest.mark.parametrize("rollback", [False, True])
async def test_real_iterative_setting_stays_in_transaction(
    rollback: bool,
    client: AsyncClient,
    users: UserFactory,
    worker_engine: AsyncEngine,
) -> None:
    owner = await users.create("local-setting@synthetic.invalid")
    course = await create_course(client, users.auth(owner), "C1-LOCAL")
    await seed_document(
        worker_engine, course_id=course, uploaded_by=owner, passages=[BODY], embeddings=True
    )
    # Keep the physical connection checked out: a different idle pool connection
    # could conceal a session-level setting leak after commit or rollback.
    async with get_engine().connect() as connection:
        try:
            async with AsyncSession(bind=connection) as session, session.begin():
                backend = (await session.execute(text("SELECT pg_backend_pid()"))).scalar_one()
                await session.execute(text("SELECT set_config('hnsw.iterative_scan', 'off', true)"))
                await set_rls_context(session, owner)
                await dense.dense_search(session, course_id=course, query="semafor", limit=3)
                assert (
                    await session.execute(text("SELECT current_setting('hnsw.iterative_scan')"))
                ).scalar_one() == "relaxed_order"
                if rollback:
                    raise RuntimeError("synthetic rollback")
        except RuntimeError as exc:
            assert rollback and str(exc) == "synthetic rollback"
        try:
            assert (
                await connection.execute(text("SELECT pg_backend_pid()"))
            ).scalar_one() == backend
            value = (
                await connection.execute(
                    text("SELECT current_setting('hnsw.iterative_scan', true)")
                )
            ).scalar_one()
            assert value in (None, "off")
        finally:
            # A negative session-level mutation must not poison the shared pool.
            await connection.execute(text("SELECT set_config('hnsw.iterative_scan', 'off', false)"))
            await connection.commit()


async def test_real_materialized_window_is_bounded_with_enough_eligible_chunks(
    client: AsyncClient,
    users: UserFactory,
    worker_engine: AsyncEngine,
) -> None:
    owner = await users.create("window@synthetic.invalid")
    course = await create_course(client, users.auth(owner), "C1-WINDOW")
    await seed_document(
        worker_engine, course_id=course, uploaded_by=owner, passages=[BODY] * 31, embeddings=True
    )
    async with rls_session(owner) as session:
        await dense.dense_search(
            session, course_id=course, query="semafor", limit=3, candidate_multiplier=8
        )
        query_vector = dense.get_embedding_provider().embed_query("semafor")
        plan = (
            await session.execute(
                text("EXPLAIN (ANALYZE, FORMAT JSON) " + str(dense._SQL)),
                {
                    "query_vector": str(query_vector),
                    "course_id": course,
                    "limit": 3,
                    "candidate_limit": 24,
                    "filter_documents": False,
                    "document_ids": [],
                },
            )
        ).scalar_one()[0]

    def nodes(node: dict[str, object]) -> list[dict[str, object]]:
        return [node, *[nested for child in node.get("Plans", []) for nested in nodes(child)]]

    candidates = [node for node in nodes(plan["Plan"]) if node.get("Subplan Name") == "CTE nearest"]
    assert len(candidates) == 1 and candidates[0]["Actual Rows"] == 24
    assert plan["Plan"]["Actual Rows"] == 3


@pytest.mark.parametrize("error", [RuntimeError("synthetic SQL failure"), asyncio.CancelledError()])
async def test_query_failure_preserves_original_error_and_leaves_rollback_to_caller(
    error: BaseException,
) -> None:
    class FailingSession(RecordingSession):
        async def execute(self, query: object, params: dict[str, object] | None = None) -> object:
            if "WITH nearest" in str(query):
                self.calls.append((str(query), params))
                raise error
            return await super().execute(query, params)

    session = FailingSession()
    set_embedding_provider(HashingEmbeddingProvider())
    try:
        with pytest.raises(type(error)) as caught:
            await dense.dense_search(session, course_id=UUID(int=3), query="semafor", limit=3)
    finally:
        set_embedding_provider(None)
    assert caught.value is error
    assert len(session.calls) == 4
    assert "WITH nearest" in session.calls[-1][0]
    assert not any(params and "mode" in params for _, params in session.calls)
    # Sahtede rollback yok: retrieval çağıranın bekleyen işlerini geri alamaz.


@pytest.mark.parametrize("stage", ["mismatch", "dto"])
async def test_python_checks_run_after_original_plan_mode_is_restored(
    stage: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = RecordingSession("force_generic_plan")
    sentinel = RuntimeError("synthetic Python validation failure")

    def fail(*args: object, **kwargs: object) -> None:
        assert session.calls[-1] == (
            "SELECT set_config('plan_cache_mode', :mode, true)",
            {"mode": "force_generic_plan"},
        )
        raise sentinel

    monkeypatch.setattr(
        dense, "_assert_same_space" if stage == "mismatch" else "RetrievedChunk", fail
    )
    set_embedding_provider(HashingEmbeddingProvider())
    try:
        with pytest.raises(RuntimeError) as caught:
            await dense.dense_search(session, course_id=UUID(int=3), query="semafor", limit=3)
    finally:
        set_embedding_provider(None)
    assert caught.value is sentinel


@pytest.mark.parametrize("mode", ["auto", "force_generic_plan", "force_custom_plan"])
async def test_real_dense_restores_caller_plan_policy_before_fts(
    mode: str,
    client: AsyncClient,
    users: UserFactory,
    worker_engine: AsyncEngine,
) -> None:
    owner = await users.create("plan-policy@synthetic.invalid")
    course = await create_course(client, users.auth(owner), "C1-PLAN-POLICY")
    await seed_document(
        worker_engine, course_id=course, uploaded_by=owner, passages=[BODY], embeddings=True
    )
    async with get_engine().connect() as connection:
        async with AsyncSession(bind=connection) as session, session.begin():
            await set_rls_context(session, owner)
            backend = (await session.execute(text("SELECT pg_backend_pid()"))).scalar_one()
            initial = (await session.execute(text("SHOW plan_cache_mode"))).scalar_one()
            await session.execute(
                text("SELECT set_config('plan_cache_mode', :mode, true)"), {"mode": mode}
            )
            assert await dense.dense_search(session, course_id=course, query="semafor", limit=3)
            assert (await session.execute(text("SHOW plan_cache_mode"))).scalar_one() == mode
            assert await fts.fts_search(session, course_id=course, query="semafor", limit=3)
            assert (await session.execute(text("SHOW plan_cache_mode"))).scalar_one() == mode
        assert (await connection.execute(text("SELECT pg_backend_pid()"))).scalar_one() == backend
        assert (await connection.execute(text("SHOW plan_cache_mode"))).scalar_one() == initial
        await connection.rollback()


async def test_real_failed_dense_sql_rolls_back_caller_work_and_plan_on_same_backend(
    client: AsyncClient,
    users: UserFactory,
    worker_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await users.create("plan-sql-error@synthetic.invalid")
    course = await create_course(client, users.auth(owner), "C1-PLAN-ERROR")
    marker = "uncommitted synthetic title"
    async with get_engine().connect() as connection:
        with pytest.raises(DBAPIError) as caught:
            async with AsyncSession(bind=connection) as session, session.begin():
                await set_rls_context(session, owner)
                backend = (await session.execute(text("SELECT pg_backend_pid()"))).scalar_one()
                initial = (await session.execute(text("SHOW plan_cache_mode"))).scalar_one()
                original = (
                    await session.execute(
                        text("SELECT title FROM courses WHERE id=:id"), {"id": course}
                    )
                ).scalar_one()
                await session.execute(
                    text("UPDATE courses SET title=:title WHERE id=:id"),
                    {"title": marker, "id": course},
                )
                # Gerçek plan ayarlarından sonra gerçek PostgreSQL hatası.
                monkeypatch.setattr(dense, "_SQL", text("SELECT 1 / 0"))
                await dense.dense_search(session, course_id=course, query="semafor", limit=3)
        assert caught.value.orig.sqlstate == "22012"
        async with AsyncSession(bind=connection) as session, session.begin():
            await set_rls_context(session, owner)
            assert (await session.execute(text("SELECT pg_backend_pid()"))).scalar_one() == backend
            assert (await session.execute(text("SHOW plan_cache_mode"))).scalar_one() == initial
            assert (
                await session.execute(
                    text("SELECT title FROM courses WHERE id=:id"), {"id": course}
                )
            ).scalar_one() == original


async def test_real_cancelled_dense_does_not_leave_plan_policy_on_reused_connection(
    client: AsyncClient,
    users: UserFactory,
    worker_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await users.create("plan-cancel@synthetic.invalid")
    course = await create_course(client, users.auth(owner), "C1-PLAN-CANCEL")
    engine = get_engine()
    started = asyncio.Event()
    initial_state: dict[str, object] = {}
    monkeypatch.setattr(dense, "_SQL", text("SELECT pg_sleep(30)"))

    def signal_query(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        if statement == "SELECT pg_sleep(30)":
            started.set()

    event.listen(engine.sync_engine, "before_cursor_execute", signal_query)
    try:
        async with engine.connect() as connection:

            async def request() -> None:
                async with AsyncSession(bind=connection) as session, session.begin():
                    await set_rls_context(session, owner)
                    initial_state["pid"] = (
                        await session.execute(text("SELECT pg_backend_pid()"))
                    ).scalar_one()
                    initial_state["mode"] = (
                        await session.execute(text("SHOW plan_cache_mode"))
                    ).scalar_one()
                    await dense.dense_search(session, course_id=course, query="semafor", limit=3)

            task = asyncio.create_task(request())
            try:
                await asyncio.wait_for(started.wait(), timeout=5)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                # psycopg iptali fiziksel bağlantıyı geçersiz kılıp atabilir. Aynı
                # bağlantıda geri alma veya temiz politikayla yeni bağlantı gerekir;
                # kapanmış soketin yeniden kullanılacağını varsayma.
                invalidated = connection.invalidated
                async with AsyncSession(bind=connection) as session, session.begin():
                    await set_rls_context(session, owner)
                    pid = (await session.execute(text("SELECT pg_backend_pid()"))).scalar_one()
                    assert (
                        await session.execute(text("SHOW plan_cache_mode"))
                    ).scalar_one() == initial_state["mode"]
                    assert (
                        (pid != initial_state["pid"])
                        if invalidated
                        else (pid == initial_state["pid"])
                    )
            finally:
                if not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", signal_query)
