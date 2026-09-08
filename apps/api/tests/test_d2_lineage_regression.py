"""Önceki belgenin gerçek API silmesi, halefin kaynak claim'ini bozmamalıdır.

Kök görev bu dosyayı izole stage tests/test_d2_lineage_regression.py konumuna
kopyalayarak mevcut conftest hedef koruması altında çalıştırır. Bu dosya kendi
DB'sini kurmaz; DB yürütmesi yalnız kök görevindir.
"""

from uuid import UUID

from app.modules.ingestion import pipeline
from app.modules.ingestion.storage import get_storage
from tests.test_worker_recovery import (
    job_state,
    pending_source,  # noqa: F401 - pytest'in mevcut fixture kaydı
    take,
)


async def test_deleting_predecessor_preserves_claimed_successor_revision_and_completion(
    pending_source,  # noqa: F811 - pytest fixture injection shadows its registration import
    admin_engine,
    client,
):
    factory, predecessor_id, headers, course_id = pending_source
    predecessor_claim = await take(factory)
    assert predecessor_claim is not None
    predecessor_output = await pipeline.process_document(get_storage(), predecessor_claim)
    await pipeline.finalize_document(factory, predecessor_claim, predecessor_output)
    predecessor_state = await job_state(admin_engine, predecessor_id)
    assert predecessor_state["status"] == "completed" and predecessor_state["chunk_count"] > 0

    replacement = await client.post(
        f"/courses/{course_id}/documents",
        headers=headers,
        files={
            "file": (
                "successor.md",
                b"# Replacement source\n\n"
                b"Virtual memory maps logical addresses to physical frames.",
                "text/markdown",
            )
        },
        data={"replaces_document_id": str(predecessor_id)},
    )
    assert replacement.status_code == 202, replacement.text
    successor_id = UUID(replacement.json()["document"]["id"])
    assert replacement.json()["document"]["supersedes_document_id"] == str(predecessor_id)
    current = await take(factory)
    assert current is not None and current.document_id == successor_id
    prepared = await pipeline.process_document(get_storage(), current)
    before = await job_state(admin_engine, successor_id)
    assert before["document_status"] == before["status"] == "processing"
    assert before["claim_token"] == current.token

    deleted = await client.delete(
        f"/courses/{course_id}/documents/{predecessor_id}", headers=headers
    )
    assert deleted.status_code == 204, deleted.text
    successor = await client.get(f"/courses/{course_id}/documents/{successor_id}", headers=headers)
    assert successor.status_code == 200, successor.text
    assert successor.json()["supersedes_document_id"] is None

    after_lineage_cleanup = await job_state(admin_engine, successor_id)
    assert after_lineage_cleanup["ingestion_revision"] == before["ingestion_revision"], (
        "Önceki belgeye ilişkin FK temizliği halefin kendi kaynak revision'ını değiştirmemeli"
    )
    assert after_lineage_cleanup["claim_token"] == current.token
    await pipeline.finalize_document(factory, current, prepared)
    completed = await job_state(admin_engine, successor_id)
    assert completed["status"] == completed["document_status"] == "completed"
    assert completed["ingestion_revision"] == before["ingestion_revision"]
    assert completed["attempt_count"] == 1
    assert completed["claim_token"] is None and completed["chunk_count"] == len(prepared.chunks)
