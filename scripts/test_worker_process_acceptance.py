"""D3 gerçek ayrıştırıcı/worker adayları; yalnız sabitlenmiş L4 başlatıcısıyla çalışır."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import signal
import subprocess
import sys
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app import worker
from app.api import documents as documents_api
from app.core.errors import ValidationError
from app.modules.ingestion import claims, parsers
from app.modules.ingestion.storage import LocalFileStorage, get_storage
from tests.conftest import APP_DSN, REPO_ROOT, WORKER_DSN, UserFactory
from tests.factories import create_course

# API veritabanını silip kuran test hazırlığı başlamadan toplama aşaması reddedilir.
if os.environ.get("DOU_L4_D3_PREFLIGHT") != "owned-new-database-verified":
    raise RuntimeError("D3_REQUIRES_OWNED_NEW_DATABASE_LAUNCHER")

BROKEN_PDF = b"%PDF-1.7\n% synthetic.invalid malformed PDF without objects or xref\n%%EOF\n"
GOOD_MARKDOWN = b"# Synthetic source\n\nVirtual memory separates process address spaces.\n"


async def upload(
    client: AsyncClient, users: UserFactory, monkeypatch: pytest.MonkeyPatch, *, broken: bool
) -> tuple[UUID, UUID]:
    async def no_background_trigger() -> None:
        return None

    monkeypatch.setattr(documents_api, "_trigger_worker", no_background_trigger)
    headers = users.auth(await users.create("worker-d3@synthetic.invalid"))
    course = await create_course(client, headers, "D3-WORKER")
    name, content, mime = (
        ("synthetic-broken.pdf", BROKEN_PDF, "application/pdf")
        if broken
        else ("synthetic.md", GOOD_MARKDOWN, "text/markdown")
    )
    response = await client.post(
        f"/courses/{course}/documents", headers=headers, files={"file": (name, content, mime)}
    )
    assert response.status_code == 202
    return course, UUID(response.json()["document"]["id"])


async def state(engine: AsyncEngine, document: UUID) -> dict[str, Any]:
    async with engine.connect() as connection:
        result = await connection.execute(
            text(
                "SELECT j.id AS job_id, j.document_id, d.course_id, j.status::text, "
                "j.attempt_count, j.claim_token, j.claim_document_revision, j.lease_expires_at, "
                "j.next_attempt_at, j.started_at, j.completed_at, j.last_error, "
                "d.status::text AS document_status, d.ingestion_revision, d.error_message, "
                "d.updated_at, d.chunk_count AS declared_chunks, "
                "(SELECT count(*) FROM chunks WHERE document_id = d.id) AS actual_chunks "
                "FROM ingestion_jobs j JOIN documents d ON d.id = j.document_id WHERE d.id = :id"
            ),
            {"id": document},
        )
        return dict(result.mappings().one())


def assert_released(row: dict[str, Any]) -> None:
    assert row["claim_token"] is None
    assert row["claim_document_revision"] is None
    assert row["lease_expires_at"] is None
    assert row["actual_chunks"] == 0


async def test_malformed_pdf_exhausts_three_real_parser_attempts_without_fourth_claim(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Gerçek ayrıştırma hatasını kayıp dosya ve içerik özeti uyuşmazlığından ayır.
    with pytest.raises(ValidationError):
        parsers.parse(BROKEN_PDF, ".pdf")
    _, document = await upload(client, users, monkeypatch, broken=True)
    original_parse = parsers.parse
    parser_calls: list[str] = []

    def observed_parse(content: bytes, file_type: str) -> parsers.ParsedDocument:
        assert content == BROKEN_PDF and file_type == ".pdf"
        parser_calls.append(hashlib.sha256(content).hexdigest())
        return original_parse(content, file_type)

    monkeypatch.setattr(parsers, "parse", observed_parse)
    factory = worker._get_session_factory()
    async with factory() as session, session.begin():
        assert tuple(
            (
                await session.execute(
                    text(
                        "SELECT current_user, rolsuper, rolbypassrls FROM pg_roles "
                        "WHERE rolname=current_user"
                    )
                )
            ).one()
        ) == ("dou_worker", False, True)
    first_job = (await state(admin_engine, document))["job_id"]
    async with asyncio.timeout(30):
        for attempt in range(1, 4):
            assert await worker.drain(limit=1) == 1
            row = await state(admin_engine, document)
            assert row["job_id"] == first_job
            assert row["attempt_count"] == attempt
            assert row["last_error"] == claims.FailureReason.COMPUTE_FAILED.value
            assert_released(row)
            if attempt < 3:
                assert row["status"] == "pending" and row["document_status"] == "uploaded"
                assert row["completed_at"] is None and row["error_message"] is None
            else:
                assert row["status"] == row["document_status"] == "failed"
                assert row["completed_at"] is not None
                assert row["error_message"] == claims.DOCUMENT_FAILURE_MESSAGE
        terminal = await state(admin_engine, document)
        assert len(parser_calls) == 3
        assert await worker.drain(limit=1) == 0
        async with claims.transaction(factory) as session:
            assert await claims.claim_next_job(session) is None
        assert await state(admin_engine, document) == terminal
        assert len(parser_calls) == 3


async def test_real_sigterm_releases_current_live_claim_before_worker_process_exits(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    course, document = await upload(client, users, monkeypatch, broken=False)
    storage = get_storage()
    assert isinstance(storage, LocalFileStorage)
    child_path = REPO_ROOT / "scripts/l4_worker_signal_child.py"
    child_sha = hashlib.sha256(child_path.read_bytes()).hexdigest()
    nonce = str(uuid4())
    child_env = {
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "PYTHONPATH": str(REPO_ROOT / "apps/api"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "LITELLM_LOCAL_MODEL_COST_MAP": "True",
        "HF_HUB_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "DO_NOT_TRACK": "1",
        "DATABASE_URL": APP_DSN,
        "WORKER_DATABASE_URL": WORKER_DSN,
        "TEST_DB_NAME": os.environ["TEST_DB_NAME"],
        "DOU_L4_D3_PREFLIGHT": "owned-new-database-verified",
        "DOU_L4_D3_DOCUMENT": str(document),
        "DOU_L4_D3_NONCE": nonce,
        "DOU_L4_D3_STORAGE_ROOT": str(storage._root),
    }
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(child_path),
        cwd=REPO_ROOT / "apps/api",
        env=child_env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        # Yalnız başlatıcının yalıtılmış grubunu devral; kendi süreç ağacımız temizlenebilsin.
        start_new_session=False,
        limit=8192,
    )
    try:
        assert process.stdout is not None
        raw = await asyncio.wait_for(process.stdout.readline(), timeout=20)
        assert len(raw) <= 8192
        event = json.loads(raw)
        assert event["event"] == "prepared-before-finalize"
        assert event["nonce"] == nonce and event["child_sha256"] == child_sha
        assert event["database_identity"] == {
            "role": "dou_worker",
            "rolsuper": False,
            "rolbypassrls": True,
            "database": os.environ["TEST_DB_NAME"],
        }
        assert event["claim_class"] == "app.modules.ingestion.claims.Claim"
        assert event["prepared_chunks"] > 0
        row = await state(admin_engine, document)
        assert row["status"] == row["document_status"] == "processing"
        assert row["actual_chunks"] == 0
        assert row["job_id"] == UUID(event["job_id"])
        assert row["document_id"] == UUID(event["document_id"]) == document
        assert row["course_id"] == UUID(event["course_id"]) == course
        assert row["claim_token"] == UUID(event["token"])
        assert row["claim_document_revision"] == row["ingestion_revision"] == event["revision"]
        assert row["attempt_count"] == event["attempt"] == 1
        async with admin_engine.connect() as connection:
            assert (
                await connection.scalar(
                    text(
                        "SELECT lease_expires_at > clock_timestamp() FROM ingestion_jobs "
                        "WHERE id=:id"
                    ),
                    {"id": row["job_id"]},
                )
                is True
            )
        # Sinyalden hemen önce kendi sürecimizin kimliğini ve değişmeyen kaynak özetini
        # yeniden doğrula. Özel borudan gelen tek kullanımlık değer bu koşuyu tanımlar.
        assert event["pid"] == process.pid and event["ppid"] == os.getpid()
        assert event["process_group"] == os.getpgrp() == os.getpgid(process.pid)
        assert process.returncode is None
        assert hashlib.sha256(child_path.read_bytes()).hexdigest() == child_sha
        process.send_signal(signal.SIGTERM)
        assert await asyncio.wait_for(process.wait(), timeout=10) == 0
        released = await state(admin_engine, document)
        assert released["job_id"] == row["job_id"]
        assert released["attempt_count"] == 1
        assert released["status"] == "pending" and released["document_status"] == "uploaded"
        assert released["last_error"] == claims.FailureReason.CANCELLED.value
        assert released["completed_at"] is None and released["error_message"] is None
        assert_released(released)
    finally:
        # Yalnız bu çağrının başlattığı alt süreç sonlandırılır; süreç adına göre arama yapılmaz.
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=10)
            except TimeoutError:
                process.kill()
                await asyncio.wait_for(process.wait(), timeout=5)
