"""Ingestion hattı: belgeyi ayrıştır, chunk'la, kaydet.

Bu kod worker bağlamında çalışır ve `dou_worker` rolüyle bağlanır: `chunks` tablosunda
bilinçli olarak hiçbir INSERT politikası yoktur, yazma yetkisi yalnızca worker'ındır
(ARCHITECTURE.md §6). Worker asla bir kullanıcı isteği adına çalışmaz; yalnızca
kuyruktaki işleri işler.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.vector_space import current_space
from app.modules.ingestion import parsers
from app.modules.ingestion.chunking import Chunk, chunk_blocks
from app.modules.ingestion.embedding import get_embedding_provider
from app.modules.ingestion.storage import DocumentStorage

logger = get_logger("app.ingestion")

MAX_ATTEMPTS = 3
# Kısa ama gerçek geri çekilme: iç HTTP tetik bütçesi 10 saniye. İlk iki hata
# arasında 1 + 3 saniye beklemek, geçici dosya/depolama yarışlarını söndürürken
# worker çağrısını orkestratör zaman aşımının içinde tutar.
RETRY_BACKOFF_SECONDS: tuple[float, ...] = (1.0, 3.0)


@dataclass(frozen=True, slots=True)
class IngestionResult:
    document_id: UUID
    chunk_count: int
    page_count: int | None


def _parse_and_chunk(content: bytes, file_type: str) -> tuple[parsers.ParsedDocument, list[Chunk]]:
    """Ayrıştırma ve chunk'lama — tek senkron blok.

    İkisi tek `to_thread` sıçramasında birlikte koşar çünkü aralarında await
    edilecek hiçbir şey yok; ayrı ayrı sarmak iki thread sıçraması demek olurdu ve
    bedeli karşılıksız kalırdı.
    """
    parsed = parsers.parse(content, file_type)
    return parsed, chunk_blocks(parsed.blocks)


async def process_document(
    session: AsyncSession, storage: DocumentStorage, document_id: UUID
) -> IngestionResult:
    """Tek bir belgeyi işler ve chunk'larını yazar.

    Yeniden işlenebilir olması için önce mevcut chunk'lar silinir; böylece yarım kalmış
    bir denemeden sonra tekrar çalıştırmak kopya chunk üretmez.
    """
    row = (
        await session.execute(
            text(
                "SELECT course_id, file_name, file_type, storage_path FROM documents WHERE id = :id"
            ),
            {"id": document_id},
        )
    ).one()

    await session.execute(
        text("UPDATE documents SET status = 'processing', updated_at = now() WHERE id = :id"),
        {"id": document_id},
    )

    content = await storage.load(row.storage_path)
    # Ayrıştırma ve embedding üretimi SENKRON ve CPU'ya bağlı işlerdir; doğrudan
    # çağrılırsa event loop'u tutarlar (FR-220). Bu zincir bugün API sürecinde
    # koşuyor: `documents.py` yüklemeden sonra `internal.trigger_drain()` çağırıyor
    # ve `WORKER_DRAIN_URL` tanımsızken (yerel + Compose + demo yolu) drain aynı
    # süreçte yapılıyor — yani "arka planda koşuyor" savunması bu satırları
    # kurtarmıyor. Desen yeni değil: `storage.py` aynı modülde üç yerde
    # `asyncio.to_thread` kullanıyor, pahalı olan tarafa uygulanmamıştı.
    parsed, chunks = await asyncio.to_thread(_parse_and_chunk, content, row.file_type)

    if not chunks:
        raise AppError("Belgeden aranabilir içerik çıkarılamadı.")

    # Embedding chunk'lar yazılmadan ÖNCE üretilir: sağlayıcı hata verirse belge
    # "completed" görünüp aranamayan chunk'lar bırakmaz.
    provider = get_embedding_provider()
    # Vektörün hangi uzayda üretildiği chunk'la BİRLİKTE yazılır (0006). Ayrı
    # yazılsaydı, ikisinin arasında bir hata olduğunda hangisinin doğru olduğunu
    # söyleyecek bir kayıt kalmazdı.
    space = current_space()
    batch_size = get_settings().embedding_batch_size
    embeddings: list[list[float]] = []
    for start in range(0, len(chunks), batch_size):
        batch = [chunk.text for chunk in chunks[start : start + batch_size]]
        # Sarma DÖNGÜNÜN İÇİNDE, parti başına: N partilik bir belge event loop'a N
        # geri dönüş noktası verir. Döngünün tamamı tek `to_thread`'e alınsaydı
        # tek nokta kalırdı ve `worker_batch_size=5` ile arka arkaya beş belge
        # işlenirken loop yine uzun aralıklarla susardı.
        embeddings.extend(await asyncio.to_thread(provider.embed_documents, batch))

    if len(embeddings) != len(chunks):  # pragma: no cover - sağlayıcı sözleşme ihlali
        raise AppError("Embedding üretimi beklenen sayıda vektör döndürmedi.")

    await session.execute(text("DELETE FROM chunks WHERE document_id = :id"), {"id": document_id})

    await session.execute(
        text(
            "INSERT INTO chunks (course_id, document_id, chunk_index, page_number, "
            "slide_number, section_title, content_type, text, token_count, embedding, "
            "embedding_space) "
            "VALUES (:course_id, :document_id, :chunk_index, :page_number, :slide_number, "
            ":section_title, CAST(:content_type AS chunk_content_type), :text, :token_count, "
            "CAST(:embedding AS vector), :embedding_space)"
        ),
        [
            {
                "course_id": row.course_id,
                "document_id": document_id,
                "chunk_index": index,
                "page_number": chunk.page_number,
                "slide_number": chunk.slide_number,
                "section_title": chunk.section_title,
                "content_type": chunk.content_type.value,
                "text": chunk.text,
                "token_count": chunk.token_count,
                "embedding": str(embedding),
                "embedding_space": space,
            }
            for index, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True))
        ],
    )

    await session.execute(
        text(
            "UPDATE documents SET status = 'completed', chunk_count = :chunk_count, "
            "page_count = :page_count, error_message = NULL, updated_at = now() "
            "WHERE id = :id"
        ),
        {
            "id": document_id,
            "chunk_count": len(chunks),
            "page_count": parsed.page_count,
        },
    )

    logger.info(
        "belge işlendi",
        extra={
            "context": {
                "document_id": str(document_id),
                "chunk_count": len(chunks),
                "page_count": parsed.page_count,
            }
        },
    )
    return IngestionResult(document_id, len(chunks), parsed.page_count)


async def claim_next_job(session: AsyncSession) -> tuple[UUID, UUID, int] | None:
    """Kuyruktan bir iş kilitleyip alır.

    `FOR UPDATE SKIP LOCKED`, birden fazla worker'ın aynı işi almasını engeller ve
    kilitli satırı beklemek yerine atlar — ayrı bir kuyruk servisine ihtiyaç bırakmaz.
    """
    row = (
        await session.execute(
            text(
                "UPDATE ingestion_jobs SET status = 'processing', "
                "attempt_count = attempt_count + 1, started_at = now() "
                "WHERE id = ("
                "  SELECT id FROM ingestion_jobs "
                "  WHERE status = 'pending' AND next_attempt_at <= now() "
                "  ORDER BY next_attempt_at, created_at, id "
                "  FOR UPDATE SKIP LOCKED LIMIT 1"
                ") RETURNING id, document_id, attempt_count"
            )
        )
    ).one_or_none()
    if row is None:
        return None
    return row.id, row.document_id, row.attempt_count


async def _fail_job(
    session: AsyncSession, job_id: UUID, document_id: UUID, attempt: int, message: str
) -> float | None:
    """Hatayı kaydeder; deneme hakkı kalmışsa işi kuyruğa geri koyar."""
    exhausted = attempt >= MAX_ATTEMPTS
    delay_seconds = None if exhausted else RETRY_BACKOFF_SECONDS[attempt - 1]
    await session.execute(
        text(
            "UPDATE ingestion_jobs SET status = CAST(:status AS job_status), "
            "last_error = :error, completed_at = CASE WHEN :exhausted THEN now() END, "
            "next_attempt_at = CASE WHEN :exhausted THEN next_attempt_at "
            "ELSE now() + make_interval(secs => :delay_seconds) END "
            "WHERE id = :id"
        ),
        {
            "id": job_id,
            "status": "failed" if exhausted else "pending",
            "error": message[:2000],
            "exhausted": exhausted,
            "delay_seconds": delay_seconds or 0,
        },
    )
    if exhausted:
        await session.execute(
            text(
                "UPDATE documents SET status = 'failed', error_message = :error, "
                "updated_at = now() WHERE id = :id"
            ),
            {"id": document_id, "error": message[:2000]},
        )
    return delay_seconds


async def run_pending_jobs(
    session_factory: object, storage: DocumentStorage, *, limit: int = 5
) -> int:
    """Bekleyen işleri sırayla işler ve işlenen iş sayısını döndürür.

    Her iş kendi işlemindedir: biri patlarsa diğerleri etkilenmez.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    assert isinstance(session_factory, async_sessionmaker)
    processed = 0

    for _ in range(limit):
        async with session_factory() as session, session.begin():
            claimed = await claim_next_job(session)
        if claimed is None:
            break

        job_id, document_id, attempt = claimed
        try:
            async with session_factory() as session, session.begin():
                await process_document(session, storage, document_id)
                await session.execute(
                    text(
                        "UPDATE ingestion_jobs SET status = 'completed', completed_at = now() "
                        "WHERE id = :id"
                    ),
                    {"id": job_id},
                )
        except Exception as exc:
            logger.warning(
                "belge işlenemedi",
                extra={
                    "context": {
                        "document_id": str(document_id),
                        "attempt": attempt,
                        "error": str(exc),
                    }
                },
            )
            message = exc.message if isinstance(exc, AppError) else "Belge işlenemedi."
            async with session_factory() as session, session.begin():
                retry_after = await _fail_job(session, job_id, document_id, attempt, message)
            # İşlem kapandıktan sonra bekle: açık transaction tutmayız. DB'deki
            # `next_attempt_at` başka worker'ın aynı işi erken almasını da engeller.
            if retry_after is not None:
                await asyncio.sleep(retry_after)
        processed += 1

    return processed


def utcnow() -> datetime:
    return datetime.now(tz=UTC)
