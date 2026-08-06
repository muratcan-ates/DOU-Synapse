"""Test altyapısı.

Önemli kural: testler API'nin üretimde kullandığı `dou_app` rolüyle bağlanır. Superuser
ile bağlanılsaydı RLS sessizce atlanır ve izolasyon testleri hiçbir şey kanıtlamadan
yeşil yanardı.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = REPO_ROOT / "supabase" / "migrations"

TEST_DB = os.environ.get("TEST_DB_NAME", "dou_synapse_test")
PG_BIN = os.environ.get("PG_BIN", "/opt/homebrew/opt/postgresql@16/bin")
ADMIN_DSN = os.environ.get("TEST_ADMIN_DSN", f"postgresql+psycopg://localhost/{TEST_DB}")
APP_DSN = os.environ.get(
    "TEST_APP_DSN", f"postgresql+psycopg://dou_app:dou_app_local@localhost/{TEST_DB}"
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
    _psql(TEST_DB, "-c", "ALTER ROLE dou_app LOGIN PASSWORD 'dou_app_local'")
    _psql(TEST_DB, "-c", "ALTER ROLE dou_worker LOGIN PASSWORD 'dou_worker_local'")
    _psql(TEST_DB, "-c", f'GRANT CONNECT ON DATABASE "{TEST_DB}" TO dou_app, dou_worker')
    yield
    _psql("postgres", "-c", f'DROP DATABASE IF EXISTS "{TEST_DB}"')


@pytest.fixture(scope="session", autouse=True)
def environment(database: None) -> Iterator[None]:
    """Ayarları test veritabanına yönlendirir ve geliştirme kimliğini açar."""
    os.environ["ENVIRONMENT"] = "local"
    os.environ["DATABASE_URL"] = APP_DSN
    os.environ["WORKER_DATABASE_URL"] = WORKER_DSN
    os.environ["DEV_AUTH_ENABLED"] = "true"
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


@pytest.fixture
async def admin_engine() -> AsyncIterator[AsyncEngine]:
    """Seed verisi için RLS'i atlayan bağlantı (tabloların sahibi)."""
    engine = create_async_engine(ADMIN_DSN)
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_tables(environment: None, admin_engine: AsyncEngine) -> AsyncIterator[None]:
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE mastery, answers, exam_sessions, questions, topics, "
                "chunks, ingestion_jobs, documents, course_memberships, "
                "courses, profiles RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
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
