"""Kaynak bağlamı ve eğitmen retrieval laboratuvarı sözleşmeleri."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.retrieval.scope import EvidenceLevel


class RetrievalInspectRequest(BaseModel):
    """LLM çağırmadan çalıştırılan öğretmen retrieval sorgusu."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=3, max_length=2_000)
    limit: int = Field(default=8, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        """Boşluklardan oluşan sorguların pahalı retrieval işini tetiklemesini engelle."""
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("Sorgu en az 3 karakter olmalıdır.")
        return normalized


class RetrievalCandidateOut(BaseModel):
    rank: int
    chunk_id: UUID
    document_id: UUID
    file_name: str
    location: str
    text: str
    dense_score: float
    fts_score: float
    fused_score: float


class RetrievalInspectionOut(BaseModel):
    query: str
    level: EvidenceLevel
    answer_allowed: bool
    threshold: float
    best_dense_score: float
    best_fts_score: float
    lexical_coverage: float
    candidate_count: int
    candidates: list[RetrievalCandidateOut]


class SourceContextChunkOut(BaseModel):
    id: UUID
    chunk_index: int
    page_number: int | None
    slide_number: int | None
    section_title: str | None
    content_type: str
    token_count: int
    text: str
    selected: bool


class SourceContextOut(BaseModel):
    document_id: UUID
    file_name: str
    selected_chunk_id: UUID
    chunks: list[SourceContextChunkOut]
