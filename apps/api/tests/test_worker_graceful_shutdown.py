"""SIGTERM/SIGINT kapatma yolu: yeni iş yok, elindeki iş ya biter ya lease'i bırakır.

İki katmanda ölçülür:

* **Sözleşme (DB'siz).** Sinyal işleyicisi doğrudan çağrılır — pytest sürecine gerçek
  sinyal gönderilmez ve gerçek işleyici kurulmaz (`add_signal_handler` testte yakalanır).
  Gerçek süreç öldürme ayrı, kök denetimli bir koşudur; asyncio iptali SIGKILL değildir.
* **Gerçek PostgreSQL.** Kapanış gerçekten claim edilmiş bir işin ortasına düşürülür ve
  lease'in bırakıldığı, son denemedeyse işin ölü mektuba yazıldığı satırdan okunur.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app import worker
from app.api import documents as documents_api
from app.modules.ingestion.claims import MAX_ATTEMPTS
from app.modules.ingestion.storage import get_storage
from tests.factories import create_course

CONTENT = b"# Sentetik kaynak\n\nKapatma yolunun gercek belgesi.\n"


class CapturedSignals:
    """Gerçek sinyal düzenini değiştirmeden işleyicileri toplar."""

    def __init__(self) -> None:
        self.handlers: dict[int, tuple[Any, tuple[Any, ...]]] = {}
        self.removed: list[int] = []

    def add(self, number: int, callback: Any, *args: Any) -> None:
        self.handlers[number] = (callback, args)

    def remove(self, number: int) -> bool:
        self.removed.append(number)
        return self.handlers.pop(number, None) is not None

    def fire(self, number: int) -> None:
        callback, args = self.handlers[number]
        callback(*args)


@pytest.fixture
def captured_signals(monkeypatch: pytest.MonkeyPatch) -> CapturedSignals:
    captured = CapturedSignals()
    loop = asyncio.get_event_loop()
    monkeypatch.setattr(loop, "add_signal_handler", captured.add)
    monkeypatch.setattr(loop, "remove_signal_handler", captured.remove)
    return captured


@pytest.fixture
def unit_worker(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """DB, kota bakımı ve günlükleme sınırlarını sahteler; kapanış yolu gerçektir."""
    dispose = AsyncMock()
    monkeypatch.setattr(worker, "configure_logging", Mock())
    monkeypatch.setattr(worker, "dispose", dispose)
    monkeypatch.setattr(worker, "_quota_maintenance", AsyncMock())
    monkeypatch.setattr(
        worker,
        "get_settings",
        Mock(return_value=SimpleNamespace(worker_shutdown_grace_seconds=0.5)),
    )
    return dispose


async def _settle(task: asyncio.Task[None]) -> None:
    if not task.done():
        task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.wait_for(task, 1)


@pytest.mark.parametrize("number", [signal.SIGTERM, signal.SIGINT])
async def test_signal_finishes_current_batch_and_claims_no_new_work(
    number: signal.Signals,
    captured_signals: CapturedSignals,
    unit_worker: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered, release = asyncio.Event(), asyncio.Event()
    rounds: list[asyncio.Event] = []
    finished = False

    async def drain(*, stop_event: asyncio.Event) -> int:
        nonlocal finished
        rounds.append(stop_event)
        entered.set()
        await release.wait()
        finished = True
        return 1

    monkeypatch.setattr(worker, "drain", drain)
    task = asyncio.create_task(worker._run_signal_worker())
    try:
        await asyncio.wait_for(entered.wait(), 1)
        assert set(captured_signals.handlers) == set(worker.SHUTDOWN_SIGNALS)
        captured_signals.fire(number)
        # Sinyal, süren turu kesmez: iş kendi hızında biter.
        assert not finished
        release.set()
        await asyncio.wait_for(task, 1)
    finally:
        await _settle(task)
    assert finished
    # İkinci bir tur BAŞLAMAZ; süren tura da aynı durdurma olayı verilmiştir.
    assert len(rounds) == 1 and rounds[0].is_set()
    unit_worker.assert_awaited_once()


async def test_first_signal_returns_both_signals_to_the_operating_system(
    captured_signals: CapturedSignals, unit_worker: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Takılan bir kapanış operatörü rehin alamaz: ikinci sinyal varsayılana düşer."""
    entered, release = asyncio.Event(), asyncio.Event()

    async def drain(*, stop_event: asyncio.Event) -> int:
        entered.set()
        await release.wait()
        return 0

    monkeypatch.setattr(worker, "drain", drain)
    task = asyncio.create_task(worker._run_signal_worker())
    try:
        await asyncio.wait_for(entered.wait(), 1)
        captured_signals.fire(signal.SIGTERM)
        # Süreç hâlâ kapanmaya çalışırken işleyiciler çoktan kaldırılmış olmalı.
        assert set(captured_signals.removed) == set(worker.SHUTDOWN_SIGNALS)
        assert captured_signals.handlers == {}
        release.set()
        await asyncio.wait_for(task, 1)
    finally:
        await _settle(task)


async def test_repeated_stop_request_is_idempotent_and_logged_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_event_loop()
    removed: list[int] = []
    with caplog.at_level("INFO", logger="app.worker"):
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(loop, "remove_signal_handler", lambda number: removed.append(number))
            worker._request_stop(stop, loop, signal.SIGTERM)
            worker._request_stop(stop, loop, signal.SIGTERM)
    assert stop.is_set()
    records = [record for record in caplog.records if record.name == "app.worker"]
    assert len(records) == 1
    assert records[0].context == {"stage": "shutdown", "signal": "SIGTERM"}


# --- Gerçek PostgreSQL: kapanış lease'i bırakır ------------------------------


class BlockingStorage:
    """Kapanış, işin ortasına düşsün diye yüklemeyi bekleten depo."""

    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.inner = get_storage()

    async def load(self, key: str) -> bytes:
        self.entered.set()
        await self.release.wait()
        return await self.inner.load(key)

    async def save(self, key: str, content: bytes) -> None:
        await self.inner.save(key, content)

    async def delete(self, key: str) -> None:
        await self.inner.delete(key)


@pytest.fixture
async def blocked_job(client: Any, users: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    async def do_not_trigger() -> None:
        return None

    monkeypatch.setattr(documents_api, "_trigger_worker", do_not_trigger)
    headers = users.auth(await users.create("graceful-shutdown@synthetic.invalid"))
    course_id = await create_course(client, headers, "L4SHUTDOWN")
    response = await client.post(
        f"/courses/{course_id}/documents",
        headers=headers,
        files={"file": ("sentetik.md", CONTENT, "text/markdown")},
    )
    assert response.status_code == 202, response.text
    # Havuz, ayarlar sahtelenmeden önce kurulur: sahte ayar nesnesinde DSN yoktur.
    worker._get_session_factory()
    storage = BlockingStorage()
    monkeypatch.setattr(worker, "get_storage", lambda: storage)
    monkeypatch.setattr(
        worker,
        "get_settings",
        Mock(return_value=SimpleNamespace(worker_shutdown_grace_seconds=0.05, worker_batch_size=5)),
    )
    return storage, UUID(response.json()["document"]["id"])


async def _job_state(engine: AsyncEngine, document_id: UUID) -> dict[str, Any]:
    async with engine.connect() as connection:
        return dict(
            (
                await connection.execute(
                    text(
                        "SELECT j.status::text, j.attempt_count, j.claim_token, "
                        "j.lease_expires_at, j.last_error, d.status::text AS document_status, "
                        "d.error_message FROM ingestion_jobs j JOIN documents d "
                        "ON d.id = j.document_id WHERE d.id = :id"
                    ),
                    {"id": document_id},
                )
            )
            .mappings()
            .one()
        )


async def _bump_attempts(engine: AsyncEngine, document_id: UUID, attempts: int) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text("UPDATE ingestion_jobs SET attempt_count = :n WHERE document_id = :id"),
            {"n": attempts, "id": document_id},
        )


async def _stop_during_claim(storage: BlockingStorage) -> None:
    """Gerçek drain bir işi claim edip yüklemede beklerken kapatma sinyalini uygular."""
    stop = asyncio.Event()
    loop = asyncio.get_event_loop()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(loop, "remove_signal_handler", lambda number: True)
        task = asyncio.create_task(worker.run_forever(stop_event=stop))
        try:
            await asyncio.wait_for(storage.entered.wait(), 10)
            worker._request_stop(stop, loop, signal.SIGTERM)
            await asyncio.wait_for(task, 10)
        finally:
            storage.release.set()
            await _settle(task)


async def test_shutdown_releases_the_lease_of_the_unfinished_job(
    blocked_job: Any, admin_engine: AsyncEngine
) -> None:
    storage, document_id = blocked_job
    await _stop_during_claim(storage)

    state = await _job_state(admin_engine, document_id)
    # Lease bırakıldı: iş yeniden alınabilir, kimse süresinin dolmasını beklemez.
    assert state["claim_token"] is None and state["lease_expires_at"] is None
    assert state["status"] == "pending" and state["last_error"] == "cancelled"
    assert state["attempt_count"] == 1
    assert state["document_status"] == "uploaded" and state["error_message"] is None


async def test_shutdown_on_the_last_attempt_marks_the_job_dead_lettered(
    blocked_job: Any, admin_engine: AsyncEngine
) -> None:
    """Son deneme iptal olursa iş sessizce kaybolmaz; ölü mektup olarak işaretlenir."""
    storage, document_id = blocked_job
    await _bump_attempts(admin_engine, document_id, MAX_ATTEMPTS - 1)
    await _stop_during_claim(storage)

    state = await _job_state(admin_engine, document_id)
    assert state["status"] == "failed" and state["last_error"] == "cancelled"
    assert state["claim_token"] is None and state["lease_expires_at"] is None
    assert state["document_status"] == "failed" and state["error_message"]
