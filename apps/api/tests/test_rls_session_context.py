"""Havuzlanmış bağlantıda RLS bağlamının işlem sınırını geçmediğinin kanıtı.

Neden ayrı dosya: `test_isolation_layers` iki katmanın AYRI AYRI tuttuğunu ölçüyor;
buradaki soru başka — **aynı fiziksel bağlantı** iki kullanıcıya sırayla verildiğinde
birincinin kimliği ikincisine geçiyor mu? Transaction modundaki havuzlayıcı (PgBouncer,
Supabase 6543) arkasında bu sorunun cevabı ürünün tamamını belirler: oturum seviyesinde
bırakılan bir GUC orada başka bir kullanıcının isteğine devredilir.

Deney kurulumu bunu görünür kılar: havuz **tek bağlantıya** indirilir ve her adımda
`pg_backend_pid()` okunur; iddialar ancak üç oturum da aynı sunucu bağlantısındayken
anlam taşır, bu yüzden PID eşitliği de iddia edilir.

SABOTAJ ÖLÇÜMÜ: `set_rls_context` içindeki `set_config(..., true)` üçüncü argümanı
`false` yapıldığında bu dosya KIRMIZI yanar — bağlam işlemden sonra bağlantıda kalır ve
bağlamsız oturum önceki kullanıcının kimliğini okur. Ölçüm bir kez bilerek yapıldı.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db import engine_target, get_session_factory, rls_session, set_rls_context
from tests.conftest import UserFactory

COURSES = text("SELECT count(*) FROM courses")
BACKEND = text("SELECT pg_backend_pid()")
CONTEXT = text("SELECT current_setting('app.current_user_id', true)")


@pytest.fixture
async def single_connection_pool(clean_tables: None) -> AsyncIterator[None]:
    """Uygulama havuzunu tek bağlantıya indirir.

    Varsayılan havuzda sıradaki oturum başka bir bağlantıya düşebilir ve sızıntı
    testi yanlışlıkla yeşil yanar. Tek bağlantı, sızıntının görünebileceği tek
    kurulumdur; ayrıca `pg_backend_pid()` eşitliği bunu ölçerek doğrular.
    """
    from app.core.config import get_settings
    from app.core.db import dispose_engine

    previous = {key: os.environ.get(key) for key in ("DB_POOL_SIZE", "DB_MAX_OVERFLOW")}
    os.environ["DB_POOL_SIZE"] = "1"
    os.environ["DB_MAX_OVERFLOW"] = "0"
    get_settings.cache_clear()
    await dispose_engine()
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()
        await dispose_engine()


async def _seed_course(engine: AsyncEngine, *, owner: UUID, code: str) -> UUID:
    """Dersi ve sahibinin eğitmen üyeliğini RLS'i atlayan bağlantıyla yazar."""
    course_id = uuid4()
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO courses (id, code, title, created_by) "
                "VALUES (:id, :code, :title, :owner)"
            ),
            {"id": course_id, "code": code, "title": f"{code} Dersi", "owner": owner},
        )
        await connection.execute(
            text(
                "INSERT INTO course_memberships (course_id, user_id, role) "
                "VALUES (:course, :user, 'instructor')"
            ),
            {"course": course_id, "user": owner},
        )
    return course_id


async def test_next_user_on_same_connection_cannot_see_previous_users_rows(
    single_connection_pool: None, users: UserFactory, admin_engine: AsyncEngine
) -> None:
    birinci = await users.create("pooler-first@synthetic.invalid")
    ikinci = await users.create("pooler-second@synthetic.invalid")
    await _seed_course(admin_engine, owner=birinci, code="RLS-POOL-1")

    async with rls_session(birinci) as session:
        ilk_backend = (await session.execute(BACKEND)).scalar_one()
        assert (await session.execute(COURSES)).scalar_one() == 1
        assert (await session.execute(CONTEXT)).scalar_one() == str(birinci)

    async with rls_session(ikinci) as session:
        # Aynı fiziksel bağlantı olmasaydı aşağıdaki sıfır bir şey kanıtlamazdı.
        assert (await session.execute(BACKEND)).scalar_one() == ilk_backend
        assert (await session.execute(CONTEXT)).scalar_one() == str(ikinci)
        assert (await session.execute(COURSES)).scalar_one() == 0


async def test_context_free_session_on_returned_connection_starts_empty(
    single_connection_pool: None, users: UserFactory, admin_engine: AsyncEngine
) -> None:
    """Havuza dönen bağlantıda önceki kullanıcının kimliği KALMAMALIDIR.

    Sızıntının en tehlikeli biçimi budur: bağlam kurmayan bir kod yolu (bakım
    sorgusu, sağlık kontrolü, hata yolunda açılan oturum) önceki isteğin kimliğini
    devralırsa, hiçbir politika bunu yakalayamaz — RLS'e göre o kullanıcı odur.
    """
    sahip = await users.create("pooler-owner@synthetic.invalid")
    await _seed_course(admin_engine, owner=sahip, code="RLS-POOL-2")

    async with rls_session(sahip) as session:
        sahip_backend = (await session.execute(BACKEND)).scalar_one()
        assert (await session.execute(COURSES)).scalar_one() == 1

    factory = get_session_factory()
    async with factory() as session, session.begin():
        assert (await session.execute(BACKEND)).scalar_one() == sahip_backend
        assert (await session.execute(CONTEXT)).scalar_one() in (None, "")
        assert (await session.execute(text("SELECT app.current_user_id()"))).scalar_one() is None
        assert (await session.execute(COURSES)).scalar_one() == 0


async def test_context_outside_a_transaction_is_refused_loudly(
    single_connection_pool: None, users: UserFactory
) -> None:
    """İşlemsiz bağlam kurma sessizce kabul edilmez."""
    kullanici = await users.create("pooler-no-transaction@synthetic.invalid")
    factory = get_session_factory()
    async with factory() as session:
        assert not session.in_transaction()
        with pytest.raises(RuntimeError):
            await set_rls_context(session, kullanici)


# --- DSN'den havuzlayıcı kipi (veritabanına dokunmaz) ------------------------


def test_direct_dsn_is_untouched_and_adds_no_connect_args() -> None:
    url, connect_args = engine_target("postgresql+psycopg://dou_app@127.0.0.1:5432/dou")
    assert connect_args == {}
    assert url.render_as_string(hide_password=False) == (
        "postgresql+psycopg://dou_app@127.0.0.1:5432/dou"
    )


@pytest.mark.parametrize(
    "marker",
    ["pgbouncer=true", "pool_mode=transaction", "prepared_statements=false"],
)
def test_transaction_pooler_marker_disables_psycopg_prepared_statements(marker: str) -> None:
    url, connect_args = engine_target(f"postgresql+psycopg://dou_app@127.0.0.1:6543/dou?{marker}")
    # İşaret sürücüye geçerse bağlantı "bilinmeyen parametre" ile hiç açılmaz.
    assert dict(url.query) == {}
    assert connect_args == {"prepare_threshold": None}


def test_transaction_pooler_marker_disables_asyncpg_statement_cache() -> None:
    url, connect_args = engine_target("postgresql+asyncpg://dou_app@127.0.0.1:6543/dou?pgbouncer=1")
    assert dict(url.query) == {}
    assert connect_args == {"statement_cache_size": 0, "prepared_statement_cache_size": 0}


def test_session_mode_marker_is_dropped_without_changing_driver_behaviour() -> None:
    url, connect_args = engine_target(
        "postgresql+psycopg://dou_app@127.0.0.1:5432/dou?pool_mode=session&pgbouncer=false"
    )
    assert dict(url.query) == {}
    assert connect_args == {}


def test_unknown_driver_gets_no_invented_connect_args() -> None:
    _, connect_args = engine_target("postgresql+pg8000://dou_app@127.0.0.1:6543/dou?pgbouncer=true")
    assert connect_args == {}
