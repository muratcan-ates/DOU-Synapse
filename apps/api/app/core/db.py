"""Veritabanı motoru ve RLS bağlamlı oturum yönetimi.

İzolasyonun ikinci katmanı buradan geçer: her istek, işlem içinde
`app.current_user_id` GUC'sini ayarlar ve PostgreSQL politikaları bu değere bakar.
GUC ayarlanmadan açılan bir oturum hiçbir satır göremez (fail-closed).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_control_engine: AsyncEngine | None = None
_control_session_factory: async_sessionmaker[AsyncSession] | None = None


def _build_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        str(settings.database_url),
        echo=settings.db_echo,
        hide_parameters=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
    )


def _build_control_engine(settings: Settings) -> AsyncEngine:
    """Kisa, bagimsiz kontrol islemleri icin tek baglantili havuz.

    Chat istegi ana RLS oturumunu provider I/O boyunca tasir. Kota rezervasyonu
    ayni havuzu kullansaydi butun ana baglantilar bu isteklerce tutuldugunda
    her istek ikinci baglantiyi bekler ve havuz ilerleyemezdi. Bu havuz yalniz
    kisa reservation/reconcile islemleri icindir; bir baglanti ve sifir overflow
    ile veritabani yukunu sinirli tutarken ana istek havuzundan bagimsiz kalir.
    """
    return create_async_engine(
        str(settings.database_url),
        echo=settings.db_echo,
        hide_parameters=True,
        pool_size=1,
        max_overflow=0,
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


def get_control_session_factory() -> async_sessionmaker[AsyncSession]:
    global _control_engine, _control_session_factory
    if _control_engine is None:
        _control_engine = _build_control_engine(get_settings())
    if _control_session_factory is None:
        _control_session_factory = async_sessionmaker(
            bind=_control_engine,
            expire_on_commit=False,
            autoflush=False,
        )
    return _control_session_factory


async def dispose_engine() -> None:
    global _control_engine, _control_session_factory, _engine, _session_factory
    if _control_engine is not None:
        await _control_engine.dispose()
    if _engine is not None:
        await _engine.dispose()
    _control_engine = None
    _control_session_factory = None
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


@asynccontextmanager
async def control_rls_session(user_id: UUID) -> AsyncIterator[AsyncSession]:
    """Ana istek havuzundan bagimsiz, kisa ve RLS-baglamli islem.

    Bu baglam provider, dosya veya ag I/O'su tasimamalidir. Tek baglantili
    bounded havuz, yalniz atomik kota/telemetri kontrol islemlerini siralar.
    """
    factory = get_control_session_factory()
    async with factory() as session, session.begin():
        await set_rls_context(session, user_id)
        yield session


async def db_now(session: AsyncSession) -> datetime:
    """İşlemin veritabanı saati.

    İşlem içinde sabittir, dolayısıyla aynı istekte yapılan iki karşılaştırma
    (süre doldu mu / kalan kaç saniye) tutarlıdır.

    Burada yaşamasının sebebi: saat üç ayrı ürün kuralının girdisi oldu — sınav
    süresi (`modules/assessment/exam_state.py`), asistan kilidi (`api/deps.py`) ve
    ileride sınav yayın penceresi. Bunları bir sınav modülünden saat almaya
    zorlamak, ikinci bir `SELECT now()` sarmalayıcısının yazılmasının en kısa
    yoluydu (Anayasa XI).
    """
    value = await session.scalar(select(func.now()))
    if value is None:  # pragma: no cover - now() hiçbir zaman NULL dönmez
        raise RuntimeError("veritabanı saati okunamadı")
    return value
