"""Sentetik D3 alt süreci: gerçek worker girişinde, kayıt öncesi asenkron bekleme.

Özel protokol devralınan stdout borusuna yazılır; uygulama çıktıları atılır.
Genel uygulama ortamıyla veya üretim veritabanı adresiyle çalıştırılmamalıdır.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import make_url


def main() -> int:
    protocol = os.fdopen(os.dup(sys.stdout.fileno()), "w", buffering=1)
    null = os.open(os.devnull, os.O_WRONLY)
    os.dup2(null, sys.stdout.fileno())
    os.dup2(null, sys.stderr.fileno())
    os.close(null)
    try:
        if os.environ.get("DOU_L4_D3_PREFLIGHT") != "owned-new-database-verified":
            raise ValueError
        database = os.environ["TEST_DB_NAME"]
        if not database.startswith("dou_l4_d3_"):
            raise ValueError
        for name, username in (("DATABASE_URL", "dou_app"), ("WORKER_DATABASE_URL", "dou_worker")):
            url = make_url(os.environ[name])
            if (
                url.drivername != "postgresql+psycopg"
                or url.host != "127.0.0.1"
                or url.port != 55484
                or url.database != database
                or url.username != username
                or url.query
            ):
                raise ValueError
        expected_document = UUID(os.environ["DOU_L4_D3_DOCUMENT"])
        nonce = UUID(os.environ["DOU_L4_D3_NONCE"])
        storage_root = Path(os.environ["DOU_L4_D3_STORAGE_ROOT"]).resolve(strict=True)
        from app.core import config

        settings = config.Settings(
            _env_file=None,
            environment="local",
            dev_auth_enabled=True,
            database_url=os.environ["DATABASE_URL"],
            worker_database_url=os.environ["WORKER_DATABASE_URL"],
            embedding_provider="hashing",
            storage_backend="local",
            storage_root=str(storage_root),
            worker_batch_size=1,
            worker_shutdown_grace_seconds=0.25,
            ingestion_lease_seconds=60,
            ingestion_heartbeat_seconds=0.25,
            ingestion_control_timeout_seconds=5,
        )
        config.get_settings = lambda: settings
        from app import worker
        from app.modules.ingestion import pipeline
        from app.modules.ingestion.claims import Claim

        original = pipeline.process_document
        child_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

        async def prepared_barrier(storage: object, claim: Claim) -> pipeline.PreparedDocument:
            if not isinstance(claim, Claim) or claim.document_id != expected_document:
                raise ValueError
            prepared = await original(storage, claim)
            if not prepared.chunks or len(prepared.chunks) != len(prepared.embeddings):
                raise ValueError
            async with pipeline.transaction(worker._get_session_factory()) as session:
                identity = dict(
                    (
                        await session.execute(
                            text(
                                "SELECT current_user AS role, rolsuper, rolbypassrls, "
                                "current_database() AS database FROM pg_roles "
                                "WHERE rolname=current_user"
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
            if identity != {
                "role": "dou_worker",
                "rolsuper": False,
                "rolbypassrls": True,
                "database": database,
            }:
                raise ValueError
            protocol.write(
                json.dumps(
                    {
                        "event": "prepared-before-finalize",
                        "pid": os.getpid(),
                        "ppid": os.getppid(),
                        "process_group": os.getpgrp(),
                        "nonce": str(nonce),
                        "database_identity": identity,
                        "claim_class": f"{Claim.__module__}.{Claim.__qualname__}",
                        "job_id": str(claim.job_id),
                        "document_id": str(claim.document_id),
                        "course_id": str(claim.course_id),
                        "token": str(claim.token),
                        "attempt": claim.attempt,
                        "revision": claim.revision,
                        "prepared_chunks": len(prepared.chunks),
                        "child_sha256": child_sha256,
                    }
                )
                + "\n"
            )
            await asyncio.Event().wait()
            raise AssertionError("unreachable synthetic barrier")

        pipeline.process_document = prepared_barrier
        worker.main()  # Üretimdeki SIGTERM işleyicisini kurar ve worker yaşam döngüsünü çalıştırır.
        return 0
    except BaseException:
        protocol.write('{"event":"child-failed","code":"WORKER_PROBE_FAILED"}\n')
        return 1
    finally:
        protocol.close()


if __name__ == "__main__":
    raise SystemExit(main())
