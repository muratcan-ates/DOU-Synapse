"""Kaynak bağlamı ve öğretmen retrieval laboratuvarı uçları."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import (
    CourseInstructorDep,
    SessionDep,
    SettingsDep,
    UnlockedCourseMemberDep,
)
from app.core.errors import NotFoundError
from app.models.core import Chunk, Document
from app.modules.retrieval.inspection import inspect_retrieval
from app.modules.retrieval.scope import EvidenceLevel
from app.schemas.source import (
    RetrievalCandidateOut,
    RetrievalInspectionOut,
    RetrievalInspectRequest,
    SourceContextChunkOut,
    SourceContextOut,
)

router = APIRouter(prefix="/courses/{course_id}/sources", tags=["sources"])


@router.post("/inspect", response_model=RetrievalInspectionOut)
async def inspect_sources(
    payload: RetrievalInspectRequest,
    context: CourseInstructorDep,
    session: SessionDep,
    settings: SettingsDep,
) -> RetrievalInspectionOut:
    """Bir sorgunun getirdiği parçaları ve kanıt kararını LLM çağırmadan göster."""
    result = await inspect_retrieval(
        session,
        course_id=context.course_id,
        query=payload.query,
        limit=payload.limit,
        settings=settings,
    )
    verdict = result.verdict
    candidates = [
        RetrievalCandidateOut(
            rank=rank,
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            file_name=chunk.file_name,
            location=chunk.location,
            text=chunk.text,
            dense_score=chunk.dense_score,
            fts_score=chunk.fts_score,
            fused_score=chunk.fused_score,
        )
        for rank, chunk in enumerate(result.candidates, start=1)
    ]
    return RetrievalInspectionOut(
        query=result.query,
        level=verdict.level,
        answer_allowed=verdict.level is EvidenceLevel.SUFFICIENT,
        threshold=verdict.threshold,
        best_dense_score=verdict.best_dense_score,
        best_fts_score=verdict.best_fts_score,
        lexical_coverage=verdict.lexical_coverage,
        candidate_count=len(candidates),
        candidates=candidates,
    )


@router.get("/{chunk_id}", response_model=SourceContextOut)
async def source_context(
    chunk_id: UUID,
    context: UnlockedCourseMemberDep,
    session: SessionDep,
) -> SourceContextOut:
    """Atıfın seçili parçasını komşu parçalarıyla özgün belge bağlamında göster.

    Bu bir yardım yüzeyidir; öğrenci için aktif sınav kilidine bağlıdır. Eğitmen
    aynı bağımlılığın içinde muaf tutulur. Yalnız snippet değil, önceki/sonraki
    parça da döner; kullanıcı atfın cümle bağlamını gerçekten denetleyebilir.
    """
    selected = await session.get(Chunk, chunk_id)
    if selected is None or selected.course_id != context.course_id:
        raise NotFoundError("Kaynak parça bulunamadı.")

    document = await session.get(Document, selected.document_id)
    if document is None or document.course_id != context.course_id:
        raise NotFoundError("Kaynak belge bulunamadı.")

    lower = max(0, selected.chunk_index - 1)
    upper = selected.chunk_index + 1
    chunks = (
        (
            await session.execute(
                select(Chunk)
                .where(
                    Chunk.document_id == selected.document_id,
                    Chunk.chunk_index >= lower,
                    Chunk.chunk_index <= upper,
                )
                .order_by(Chunk.chunk_index)
            )
        )
        .scalars()
        .all()
    )
    return SourceContextOut(
        document_id=document.id,
        file_name=document.file_name,
        selected_chunk_id=selected.id,
        chunks=[
            SourceContextChunkOut(
                id=chunk.id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                slide_number=chunk.slide_number,
                section_title=chunk.section_title,
                content_type=chunk.content_type.value,
                token_count=chunk.token_count,
                text=chunk.text,
                selected=chunk.id == selected.id,
            )
            for chunk in chunks
        ],
    )
