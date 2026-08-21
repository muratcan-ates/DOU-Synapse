"""Test altyapısı.

Önemli kural: testler API'nin üretimde kullandığı `dou_api_runtime` LOGIN'iyle
bağlanır. Superuser ile bağlanılsaydı RLS sessizce atlanır ve izolasyon testleri
hiçbir şey kanıtlamadan yeşil yanardı.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = REPO_ROOT / "supabase" / "migrations"


def _default_test_db() -> str:
    """Çalışma ağacı başına ayrı test veritabanı adı üretir.

    Neden gerekli: `database` fixture'ı oturum başında bu veritabanını DROP+CREATE
    ediyor. Sabit tek bir ad kullanıldığında, paralel çalışan iki oturum aynı anda
    pytest koştuğunda birbirinin veritabanını siliyor ve hatalar rastgele, hiçbir
    değişiklikle ilişkisiz görünüyor. Beş şeridin üçü bu tuzağa bağımsız olarak
    çarptı ve her biri kendi `TEST_DB_NAME`'ini elle verdi.

    Ad, çalışma ağacının klasör adından türetilir; böylece kimse bir şey
    ayarlamak zorunda kalmadan her worktree kendi veritabanına sahip olur.
    Tek ağaçta çalışan biri için sonuç yine tek ve sabit bir addır.
    `TEST_DB_NAME` verilirse o kazanır (CI bunu kullanıyor).
    """
    slug = re.sub(r"[^a-z0-9]+", "_", REPO_ROOT.name.lower()).strip("_")
    return f"dou_synapse_test_{slug}" if slug else "dou_synapse_test"


TEST_DB = os.environ.get("TEST_DB_NAME") or _default_test_db()
PG_BIN = os.environ.get("PG_BIN", "/opt/homebrew/opt/postgresql@16/bin")
ADMIN_DSN = os.environ.get("TEST_ADMIN_DSN", f"postgresql+psycopg://localhost/{TEST_DB}")
APP_DSN = os.environ.get(
    "TEST_APP_DSN",
    f"postgresql+psycopg://dou_api_runtime:dou_api_runtime_local@localhost/{TEST_DB}",
)
# Worker üretimde olduğu gibi ayrı, RLS'i atlayan rolle bağlanır.
WORKER_DSN = os.environ.get(
    "TEST_WORKER_DSN", f"postgresql+psycopg://dou_worker:dou_worker_local@localhost/{TEST_DB}"
)


def _psql(database: str, *args: str) -> None:
    subprocess.run(  # noqa: S603
        [f"{PG_BIN}/psql", "-v", "ON_ERROR_STOP=1", "-q", "-d", database, *args],
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope="session", autouse=True)
def database() -> Iterator[None]:
    """Test veritabanını sıfırdan kurar."""
    _psql("postgres", "-c", f'DROP DATABASE IF EXISTS "{TEST_DB}"')
    _psql("postgres", "-c", f'CREATE DATABASE "{TEST_DB}"')
    for migration in sorted(MIGRATIONS.glob("*.sql")):
        _psql(TEST_DB, "-f", str(migration))
    _psql(
        TEST_DB,
        "-c",
        "ALTER ROLE dou_api_runtime LOGIN PASSWORD 'dou_api_runtime_local'",
    )
    _psql(TEST_DB, "-c", "ALTER ROLE dou_worker LOGIN PASSWORD 'dou_worker_local'")
    _psql(
        TEST_DB,
        "-c",
        f'GRANT CONNECT ON DATABASE "{TEST_DB}" TO dou_api_runtime, dou_worker',
    )
    yield
    _psql("postgres", "-c", f'DROP DATABASE IF EXISTS "{TEST_DB}"')


@pytest.fixture(scope="session", autouse=True)
def environment(database: None) -> Iterator[None]:
    """Ayarları test veritabanına yönlendirir ve geliştirme kimliğini açar."""
    os.environ["ENVIRONMENT"] = "local"
    os.environ["DATABASE_URL"] = APP_DSN
    os.environ["WORKER_DATABASE_URL"] = WORKER_DSN
    os.environ["DEV_AUTH_ENABLED"] = "true"
    # Üretim varsayılanı fail-closed; assessment sözleşme testleri özelliği
    # bilinçli olarak açar.
    os.environ["ASSESSMENT_BLUEPRINT_ENABLED"] = "true"
    os.environ["API_OBSERVABILITY_ENABLED"] = "true"
    os.environ["API_EVENT_RETENTION_DAYS"] = "7"
    os.environ["RELEASE_REVISION"] = "pytest"
    os.environ.pop("SUPABASE_JWT_SECRET", None)

    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def storage(tmp_path: Path) -> Iterator[None]:
    """Her test kendi geçici belge deposunu kullanır."""
    from app.modules.ingestion.storage import LocalFileStorage, set_storage

    set_storage(LocalFileStorage(tmp_path / "storage"))
    yield
    set_storage(None)


@pytest.fixture(autouse=True)
async def worker_cleanup() -> AsyncIterator[None]:
    yield
    from app import worker

    await worker.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _admin_engine_pool() -> AsyncIterator[AsyncEngine]:
    """Oturum boyunca tek admin motoru; testler `admin_engine` üzerinden alır.

    Her testte yeniden kurmanın kazancı yoktu, maliyeti her testte yeni bir bağlantı
    havuzuydu. `loop_scope` da verilmek zorunda; yalnız `scope="session"` yazmak
    pytest_asyncio'da her testi AssertionError ile düşürür.

    Bunun bedeli: paylaşılan havuzun bağlantıları, ilk kullanıldıkları event loop'a
    bağlıdır. Testler seri koştuğu için bu kurulum güvenli. Paralel koşu (pytest-xdist)
    eklendiği gün ilk kırılacak yer burasıdır; o zaman `poolclass=NullPool` gerekir.

    Ayrı ve gizli olmasının nedeni `clean_tables`: temizlik admin motoruna muhtaç,
    `admin_engine` de temizliğe. Havuzu araya koymak bu döngüyü açar.
    """
    engine = create_async_engine(ADMIN_DSN)
    yield engine
    await engine.dispose()


@pytest.fixture
async def clean_tables(environment: None, _admin_engine_pool: AsyncEngine) -> AsyncIterator[None]:
    """Testler arası tabloları boşaltır.

    Artık autouse değil: veritabanına hiç dokunmayan testler de her seferinde 11 tablo
    TRUNCATE ediyordu. Temizlik garantisi bilinçli olarak daraldı ve bu bilinçli —
    DB'ye dokunan her fixture zinciri (`admin_engine`, `client`, `worker_engine`) bunu
    zaten çekiyor, dolayısıyla veri gören her test yine temiz tabloyla başlıyor.
    """
    async with _admin_engine_pool.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE api_request_events, platform_admin_access_audit, platform_admins, "
                "mastery, answers, "
                "exam_sessions, questions, topics, "
                "chunks, ingestion_jobs, documents, course_memberships, "
                "courses, profiles RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest.fixture
def admin_engine(clean_tables: None, _admin_engine_pool: AsyncEngine) -> AsyncEngine:
    """Seed verisi için RLS'i atlayan bağlantı (tabloların sahibi).

    Motoru istemek temizliği de istemek demek: admin motoruna dokunan bir test
    tanım gereği veri yazıyor ya da okuyor.
    """
    return _admin_engine_pool


@pytest.fixture
async def client(clean_tables: None) -> AsyncIterator[AsyncClient]:
    from app.core.db import dispose_engine
    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    await dispose_engine()


class UserFactory:
    """Testler için profil oluşturur ve o kullanıcının auth başlığını verir."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def create(self, email: str, full_name: str | None = None) -> UUID:
        user_id = uuid4()
        async with self._engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO profiles (id, email, full_name) VALUES (:id, :email, :full_name)"
                ),
                {"id": user_id, "email": email, "full_name": full_name},
            )
        return user_id

    @staticmethod
    def auth(user_id: UUID) -> dict[str, str]:
        return {"Authorization": f"Bearer dev:{user_id}"}


@pytest.fixture
def users(admin_engine: AsyncEngine) -> UserFactory:
    return UserFactory(admin_engine)
