"""Eğitmenin retrieval sonucunu LLM maliyeti olmadan incelemesi için servis."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import RetrievedChunk
from app.core.config import Settings, get_settings
from app.modules.retrieval.scope import EvidenceVerdict, assess_evidence
from app.modules.retrieval.service import HybridRetriever


@dataclass(frozen=True, slots=True)
class RetrievalInspection:
    """Ham adaylar ile üretimde uygulanan kanıt kararını birlikte taşır."""

    query: str
    candidates: list[RetrievedChunk]
    verdict: EvidenceVerdict


async def inspect_retrieval(
    session: AsyncSession,
    *,
    course_id: UUID,
    query: str,
    limit: int,
    settings: Settings | None = None,
) -> RetrievalInspection:
    """Üretim retriever'ını çalıştır; abstain olsa da ham adayları eğitmene göster.

    `retrieve()` abstention durumunda chunk listesini bilerek boşaltır. Öğrenci
    cevabı için doğru olan bu fail-closed davranış, öğretmen tanısı için yanlıştır:
    öğretmen hangi zayıf parçanın geldiğini görmeden parçalama/eşik sorununu ayıramaz.
    Burada aynı `HybridRetriever` ve aynı `assess_evidence` kullanılır, yalnız LLM
    çağrılmaz ve ham adaylar saklanır.
    """
    resolved = settings or get_settings()
    clean_query = query.strip()
    retriever = HybridRetriever(session, resolved)
    candidates = await retriever.search(course_id=course_id, query=clean_query, limit=limit)
    verdict = assess_evidence(
        candidates,
        query=clean_query,
        threshold=resolved.evidence_threshold,
    )
    return RetrievalInspection(query=clean_query, candidates=candidates, verdict=verdict)


__all__ = ["RetrievalInspection", "inspect_retrieval"]
