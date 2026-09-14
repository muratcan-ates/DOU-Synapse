"""D2 aynı bağlantıda yalıtım; yerel psycopg kabulü, canlı havuzlayıcı kanıtı değildir.

Üretimdeki oturum bağlamları, bu teste özel tek bağlantılı havuzdan oturum açar.
Bağlantı A -> bağlamsız -> B geçişlerinde bırakılır ve yeniden alınır. Mevcut SQL
iptal testleri sürücünün bağlantıyı geçersiz kılmasını ayrıca kapsar; buradaki
iptal, açık işlem sürerken uygulama işini bekleme aşamasında gerçekleşir.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import psycopg
import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import SessionTransactionOrigin

from app.core import db
from app.core.vector_space import current_space
from app.modules.ingestion.embedding import HashingEmbeddingProvider, set_embedding_provider
from app.modules.retrieval import dense
from tests.conftest import APP_DSN, UserFactory
from tests.factories import SeededDocument, create_course, seed_document


class RequestedRollback(Exception):
    """Doğrulama veya veritabanı hatasından ayrı, denetimli uygulama hatası."""


async def context_state(session: AsyncSession) -> dict[str, Any]:
    result = await session.execute(
        text(
            "SELECT pg_backend_pid() AS pid, "
            "NULLIF(current_setting('app.current_user_id', true), '') AS uid, "
            "current_setting('hnsw.iterative_scan') AS iterative_scan, "
            "current_setting('plan_cache_mode') AS plan_mode, "
            "current_setting('row_security') AS row_security, "
            "current_user AS role, rolsuper, rolbypassrls "
            "FROM pg_roles WHERE rolname = current_user"
        )
    )
    state = dict(result.mappings().one())
    assert state["role"] == "dou_app"
    assert state["row_security"] == "on"
    assert state["rolsuper"] is False and state["rolbypassrls"] is False
    transaction = session.sync_session.get_transaction()
    assert transaction is not None and transaction.origin is SessionTransactionOrigin.BEGIN
    return state


async def assert_visible_rows(
    session: AsyncSession, course: UUID | None, document: SeededDocument | None
) -> None:
    # Ders filtresi yoktur: eksik RLS politikası veya eski kimlik, uygulamanın
    # WHERE koşulunun ya da arayıcının course_id filtresinin arkasında gizlenemez.
    assert set((await session.execute(text("SELECT id FROM courses"))).scalars()) == (
        {course} if course is not None else set()
    )
    assert set((await session.execute(text("SELECT id FROM documents"))).scalars()) == (
        {document.document_id} if document is not None else set()
    )
    assert set((await session.execute(text("SELECT id FROM chunks"))).scalars()) == (
        set(document.chunk_ids) if document is not None else set()
    )


@pytest.mark.parametrize("context_name", ["rls_session", "control_rls_session"])
@pytest.mark.parametrize("outcome", ["commit", "rollback", "sql-error", "cancel"])
async def test_rls_and_dense_context_cannot_cross_users_on_same_psycopg_backend(
    context_name: str,
    outcome: str,
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_a = await users.create("context-a@synthetic.invalid")
    user_b = await users.create("context-b@synthetic.invalid")
    course_a = await create_course(client, users.auth(user_a), "D2-CONTEXT-A")
    course_b = await create_course(client, users.auth(user_b), "D2-CONTEXT-B")
    engine = create_async_engine(APP_DSN, pool_size=1, max_overflow=0, pool_timeout=5)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    getter = (
        "get_session_factory" if context_name == "rls_session" else "get_control_session_factory"
    )
    monkeypatch.setattr(db, getter, lambda: factory)
    scope = getattr(db, context_name)
    set_embedding_provider(HashingEmbeddingProvider())
    try:
        assert engine.dialect.driver == "psycopg"
        async with engine.connect() as connection:
            raw = await connection.get_raw_connection()
            assert isinstance(raw.driver_connection, psycopg.AsyncConnection)
        document_a = await seed_document(
            admin_engine,
            course_id=course_a,
            uploaded_by=user_a,
            passages=["Sentetik A: sanal bellek adres alanını ayırır."],
            embeddings=True,
            embedding_space=current_space(),
        )
        document_b = await seed_document(
            admin_engine,
            course_id=course_b,
            uploaded_by=user_b,
            passages=["Sentetik B: bellek sayfaları fiziksel çerçevelere eşlenir."],
            embeddings=True,
            embedding_space=current_space(),
        )
        async with factory() as session, session.begin():
            # Başlangıç durumunu kaydetmeden pgvector GUC tanımlarını yükle.
            # Oturum genelinde SET, elle RESET veya bağlantı değişimi kullanılmaz.
            assert await session.scalar(text("SELECT vector_dims('[1]'::vector)")) == 1
            baseline = await context_state(session)
            assert baseline["uid"] is None
            assert baseline["iterative_scan"] != "relaxed_order"
            assert baseline["plan_mode"] != "force_custom_plan"
            await assert_visible_rows(session, None, None)

        entered = asyncio.Event()
        never_released = asyncio.Event()

        async def request_a() -> None:
            async with scope(user_a) as session:
                before = await context_state(session)
                assert before == {**baseline, "uid": str(user_a)}
                await assert_visible_rows(session, course_a, document_a)
                rows = await dense.dense_search(
                    session, course_id=course_a, query="sanal bellek", limit=3
                )
                assert {row.chunk_id for row in rows} == set(document_a.chunk_ids)
                assert (
                    await dense.dense_search(
                        session, course_id=course_b, query="sanal bellek", limit=3
                    )
                    == []
                )
                assert await context_state(session) == {
                    **before,
                    "iterative_scan": "relaxed_order",
                }
                if outcome == "rollback":
                    raise RequestedRollback
                if outcome == "sql-error":
                    # Gerçek yoğun arama, PostgreSQL hatası öncesinde iki yerel
                    # ayarı da uygular; işlemin sahibi geri alma işlemini yapmalıdır.
                    with monkeypatch.context() as change:
                        change.setattr(dense, "_SQL", text("SELECT 1 / 0"))
                        await dense.dense_search(
                            session, course_id=course_a, query="sanal bellek", limit=3
                        )
                if outcome == "cancel":
                    entered.set()
                    await never_released.wait()

        async with asyncio.timeout(20):
            if outcome == "rollback":
                with pytest.raises(RequestedRollback):
                    await request_a()
            elif outcome == "sql-error":
                with pytest.raises(DBAPIError) as caught:
                    await request_a()
                assert caught.value.orig.sqlstate == "22012"
            elif outcome == "cancel":
                task = asyncio.create_task(request_a())
                ready = asyncio.create_task(entered.wait())
                try:
                    done, _ = await asyncio.wait(
                        {task, ready}, timeout=5, return_when=asyncio.FIRST_COMPLETED
                    )
                    if task in done:
                        # Erken hatayı olay bekleme zaman aşımının altında gizleme.
                        await task
                        pytest.fail("İstek iptal noktasında beklemeden tamamlandı.")
                    if ready not in done:
                        raise TimeoutError("İstek iptal bekleme noktasına ulaşamadı.")
                    assert ready.result() is True
                    task.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await task
                finally:
                    for owned in (task, ready):
                        if not owned.done():
                            owned.cancel()
                    await asyncio.gather(task, ready, return_exceptions=True)
            else:
                await request_a()

        # Aynı bağlantı yeniden alınır; yeni bağlantı veya elle temizlik komutu yoktur.
        async with factory() as session, session.begin():
            assert await context_state(session) == baseline
            await assert_visible_rows(session, None, None)

        async with scope(user_b) as session:
            before = await context_state(session)
            assert before == {**baseline, "uid": str(user_b)}
            await assert_visible_rows(session, course_b, document_b)
            assert (
                await dense.dense_search(session, course_id=course_a, query="sanal bellek", limit=3)
                == []
            )
            rows = await dense.dense_search(
                session, course_id=course_b, query="sanal bellek", limit=3
            )
            assert {row.chunk_id for row in rows} == set(document_b.chunk_ids)
            assert await context_state(session) == {
                **before,
                "iterative_scan": "relaxed_order",
            }

        async with factory() as session, session.begin():
            assert await context_state(session) == baseline
            await assert_visible_rows(session, None, None)
    finally:
        set_embedding_provider(None)
        # Negatif mutasyon koşularını oturum genelinde RESET göndermeden yalıt.
        await engine.dispose()
