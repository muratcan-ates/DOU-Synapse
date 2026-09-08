"""Lease-fenced ingestion: commit a claim, compute without DB locks, then finalize."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.vector_space import current_space
from app.modules.ingestion import parsers
from app.modules.ingestion.chunking import Chunk, chunk_blocks
from app.modules.ingestion.claims import (
    MAX_ATTEMPTS as MAX_ATTEMPTS,
)
from app.modules.ingestion.claims import (
    RETRY_BACKOFF_SECONDS as RETRY_BACKOFF_SECONDS,
)
from app.modules.ingestion.claims import (
    Claim,
    FailureReason,
    LostClaim,
    assert_live_token,
    claim_next_job,
    fail_claim,
    heartbeat,
    lock_claim,
    transaction,
    verify_claim,
)
from app.modules.ingestion.embedding import get_embedding_provider
from app.modules.ingestion.storage import DocumentStorage

logger = get_logger("app.ingestion")


@dataclass(frozen=True, slots=True)
class IngestionResult:
    document_id: UUID
    chunk_count: int
    page_count: int | None


@dataclass(frozen=True, slots=True)
class PreparedDocument:
    chunks: list[Chunk]
    embeddings: list[list[float]]
    embedding_space: str
    page_count: int | None


class SourceHashMismatch(Exception):
    """Uploaded source bytes no longer match the authorized source snapshot."""


def _parse_and_chunk(content: bytes, file_type: str) -> tuple[parsers.ParsedDocument, list[Chunk]]:
    parsed = parsers.parse(content, file_type)
    return parsed, chunk_blocks(parsed.blocks)


async def process_document(storage: DocumentStorage, claim: Claim) -> PreparedDocument:
    """No session/connection enters storage, parser or provider work."""
    content = await storage.load(claim.storage_path)
    if len(content) != claim.byte_size or hashlib.sha256(content).hexdigest() != claim.file_hash:
        raise SourceHashMismatch()
    parsed, chunks = await asyncio.to_thread(_parse_and_chunk, content, claim.file_type)
    if not chunks:
        raise AppError("Belgeden aranabilir içerik çıkarılamadı.")
    provider = get_embedding_provider()
    space = current_space()
    batch_size = get_settings().embedding_batch_size
    embeddings: list[list[float]] = []
    for start in range(0, len(chunks), batch_size):
        batch = [chunk.text for chunk in chunks[start : start + batch_size]]
        embeddings.extend(await asyncio.to_thread(provider.embed_documents, batch))
    if len(embeddings) != len(chunks):
        raise AppError("Embedding üretimi beklenen sayıda vektör döndürmedi.")
    return PreparedDocument(chunks, embeddings, space, parsed.page_count)


async def _heartbeat_loop(factory: async_sessionmaker[AsyncSession], claim: Claim) -> None:
    while True:
        await asyncio.sleep(get_settings().ingestion_heartbeat_seconds)
        await heartbeat(factory, claim)


async def _stop_task(task: asyncio.Task[Any]) -> None:
    task.cancel()
    # Tasks may have failed in the same loop turn. Consume their exception so
    # asyncio never emits an unhandled-task traceback with source/connection data.
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await task


async def _prepare_with_heartbeat(
    factory: async_sessionmaker[AsyncSession], storage: DocumentStorage, claim: Claim
) -> PreparedDocument:
    await verify_claim(factory, claim)
    compute = asyncio.create_task(process_document(storage, claim))
    renewal = asyncio.create_task(_heartbeat_loop(factory, claim))
    try:
        await asyncio.wait({compute, renewal}, return_when=asyncio.FIRST_COMPLETED)
        if renewal.done():
            # No renewal outcome grants authority: normal return is unexpected,
            # and an exception may contain SQL/provider details. Fail closed.
            raise LostClaim()
        return await compute
    finally:
        await _stop_task(compute)
        await _stop_task(renewal)


async def finalize_document(
    factory: async_sessionmaker[AsyncSession], claim: Claim, prepared: PreparedDocument
) -> IngestionResult:
    async with transaction(factory) as session:
        await lock_claim(session, claim)
        await session.execute(
            text("DELETE FROM public.chunks WHERE document_id = :id"),
            {"id": claim.document_id},
        )
        await session.execute(
            text(
                "INSERT INTO public.chunks (course_id, document_id, chunk_index, page_number, "
                "slide_number, section_title, content_type, text, token_count, embedding, "
                "embedding_space) VALUES (:course_id, :document_id, :chunk_index, :page_number, "
                ":slide_number, :section_title, CAST(:content_type AS public.chunk_content_type), "
                ":text, :token_count, CAST(:embedding AS public.vector), :embedding_space)"
            ),
            [
                {
                    "course_id": claim.course_id,
                    "document_id": claim.document_id,
                    "chunk_index": index,
                    "page_number": chunk.page_number,
                    "slide_number": chunk.slide_number,
                    "section_title": chunk.section_title,
                    "content_type": chunk.content_type.value,
                    "text": chunk.text,
                    "token_count": chunk.token_count,
                    "embedding": str(embedding),
                    "embedding_space": prepared.embedding_space,
                }
                for index, (chunk, embedding) in enumerate(
                    zip(prepared.chunks, prepared.embeddings, strict=True)
                )
            ],
        )
        await assert_live_token(session, claim)
        await session.execute(
            text(
                "UPDATE public.documents SET status = 'completed', chunk_count = :chunk_count, "
                "page_count = :page_count, error_message = NULL, "
                "updated_at = pg_catalog.clock_timestamp() WHERE id = :id"
            ),
            {
                "id": claim.document_id,
                "chunk_count": len(prepared.chunks),
                "page_count": prepared.page_count,
            },
        )
        # Successful CAS is the authority point under both row locks. If expiry
        # occurred during chunk insertion, the entire transaction must roll back.
        completed = await session.scalar(
            text(
                "UPDATE public.ingestion_jobs SET status = 'completed', "
                "completed_at = pg_catalog.clock_timestamp(), last_error = NULL, "
                "claim_token = NULL, claim_document_revision = NULL, lease_expires_at = NULL "
                "WHERE id = :id AND status = 'processing' AND claim_token = :token "
                "AND claim_document_revision = :revision "
                "AND lease_expires_at > pg_catalog.clock_timestamp() RETURNING id"
            ),
            {"id": claim.job_id, "token": claim.token, "revision": claim.revision},
        )
        if completed is None:
            raise LostClaim()
    logger.info("belge işlendi", extra={"context": {"chunk_count": len(prepared.chunks)}})
    return IngestionResult(claim.document_id, len(prepared.chunks), prepared.page_count)


async def _release_cancelled(factory: async_sessionmaker[AsyncSession], claim: Claim) -> None:
    try:
        await fail_claim(factory, claim, FailureReason.CANCELLED)
    except LostClaim:
        pass  # Expired/deleted/replaced claims belong to reclaim/current owner.
    except Exception:
        logger.warning("ingestion kontrolü kullanılamadı", extra={"context": {"stage": "release"}})


async def _cancel_cleanup(factory: async_sessionmaker[AsyncSession], claim: Claim) -> None:
    cleanup = asyncio.create_task(_release_cancelled(factory, claim))
    try:
        # Shield permits one cancellation to finish its bounded short release.
        # Repeated cancellation must not leave an unobserved background task.
        await asyncio.shield(cleanup)
    except asyncio.CancelledError:
        await _stop_task(cleanup)
        raise


async def _backoff(delay: float, stop_event: asyncio.Event | None) -> None:
    if stop_event is None:
        await asyncio.sleep(delay)
    else:
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=delay)


async def run_pending_jobs(
    session_factory: object,
    storage: DocumentStorage,
    *,
    limit: int = 5,
    stop_event: asyncio.Event | None = None,
) -> int:
    """Process current claims; retain consumed attempts across crash/cancellation."""
    assert isinstance(session_factory, async_sessionmaker)
    processed = 0
    for _ in range(limit):
        if stop_event is not None and stop_event.is_set():
            break
        try:
            async with transaction(session_factory) as session:
                claimed = await claim_next_job(session)
        except Exception:
            logger.warning(
                "ingestion kontrolü kullanılamadı", extra={"context": {"stage": "claim"}}
            )
            break
        if claimed is None:
            break
        try:
            prepared = await _prepare_with_heartbeat(session_factory, storage, claimed)
            await finalize_document(session_factory, claimed, prepared)
        except asyncio.CancelledError:
            await _cancel_cleanup(session_factory, claimed)
            raise
        except LostClaim:
            logger.info("ingestion sahipliği geçersiz", extra={"context": {"stage": "processing"}})
        except Exception as exc:
            reason = (
                FailureReason.SOURCE_HASH_MISMATCH
                if isinstance(exc, SourceHashMismatch)
                else FailureReason.COMPUTE_FAILED
            )
            logger.warning(
                "belge işlenemedi",
                extra={"context": {"reason": reason.value, "attempt": claimed.attempt}},
            )
            try:
                retry_after = await fail_claim(session_factory, claimed, reason)
            except LostClaim:
                retry_after = None
            except Exception:
                logger.warning(
                    "ingestion kontrolü kullanılamadı", extra={"context": {"stage": "failure"}}
                )
                retry_after = None
            if retry_after is not None:
                await _backoff(retry_after, stop_event)
        processed += 1
    return processed
