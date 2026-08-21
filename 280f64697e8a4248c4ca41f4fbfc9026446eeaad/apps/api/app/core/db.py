"""Veritabanı motoru ve RLS bağlamlı oturum yönetimi.

İzolasyonun ikinci katmanı buradan geçer: her istek, işlem içinde
`app.current_user_id` GUC'sini ayarlar ve PostgreSQL politikaları bu değere bakar.
GUC ayarlanmadan açılan bir oturum hiçbir satır göremez (fail-closed).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _build_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        str(settings.database_url),
        echo=settings.db_echo,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
    )


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = _build_engine(get_settings())
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


async def set_rls_context(session: AsyncSession, user_id: UUID) -> None:
    """İşlem süresince geçerli kullanıcıyı ayarlar.

    `SET LOCAL` bind parametresi kabul etmediği için `set_config(..., is_local => true)`
    kullanılır; böylece değer sorgu metnine string olarak gömülmez.
    """
    await session.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": str(user_id)},
    )


@asynccontextmanager
async def rls_session(user_id: UUID) -> AsyncIterator[AsyncSession]:
    """Kullanıcı bağlamı ayarlanmış, işlem içinde bir oturum verir.

    Blok hatasız biterse commit, hata olursa rollback yapılır. `SET LOCAL` işleme bağlı
    olduğu için bağlantı havuza dönerken bağlam kendiliğinden temizlenir — bir sonraki
    isteğin önceki kullanıcının kimliğini devralması mümkün değildir.
    """
    factory = get_session_factory()
    async with factory() as session, session.begin():
        await set_rls_context(session, user_id)
        yield session
