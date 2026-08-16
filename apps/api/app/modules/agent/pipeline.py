"""Cevap hattının dikiş yeri — retrieval / generation / guardrail enjeksiyonu.

`app/api/chat.py`'den taşındı (modülerizasyon v2, PR 11): DI kaydı bir router
sorumluluğu değildir. Davranış birebir aynı; `chat.py` bu adları re-export eder,
dolayısıyla `chat.set_pipeline(...)` çağıran tüm testler ve betikler aynı
fonksiyon nesnesini kullanmaya devam eder.

Retriever İSTEK BAŞINA kurulur: `contracts.Retriever` imzasında `session` yoktur,
dolayısıyla gerçek uygulama oturumu kendi içinde taşır ve o oturum isteğin RLS
bağlamıdır. Süreç ömürlü tek bir retriever, isteklerin RLS bağlamını karıştırırdı.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import Generator, Guardrail, RetrievedChunk, Retriever
from app.core.errors import AppError

#: Retriever'ı isteğin RLS oturumundan kuran fabrika.
RetrieverFactory = Callable[[AsyncSession], Retriever]


class PipelineUnavailableError(AppError):
    """Retrieval/generation modülleri henüz takılı değil.

    Fail-closed (Anayasa IV): eksik hattı "cevap yok" diye maskelemek yerine açıkça
    hata döneriz. Aksi hâlde hattı bozuk bir sistem, ölçümde "kanıt yetersiz" oranı
    yüksek ama çalışıyor gibi görünürdü.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "pipeline_unavailable"


_retriever_factory: RetrieverFactory | None = None
_generator: Generator | None = None
_guardrails: Sequence[Guardrail] | None = None


def set_pipeline(
    *,
    retriever_factory: RetrieverFactory | None = None,
    generator: Generator | None = None,
    guardrails: Sequence[Guardrail] | None = None,
) -> None:
    """Cevap hattını takar. `ingestion.storage.set_storage()` ile aynı desen."""
    global _retriever_factory, _generator, _guardrails
    _retriever_factory = retriever_factory
    _generator = generator
    _guardrails = guardrails


class _DocumentScopedRetriever:
    """Enjekte edilen test retriever'larında da kaynak politikasını uygular."""

    def __init__(self, inner: Retriever, document_ids: frozenset[UUID]) -> None:
        self._inner = inner
        self._document_ids = document_ids

    async def search(self, *, course_id: UUID, query: str, limit: int = 8) -> list[RetrievedChunk]:
        chunks = await self._inner.search(course_id=course_id, query=query, limit=limit)
        return [chunk for chunk in chunks if chunk.document_id in self._document_ids][:limit]


def get_retriever(session: AsyncSession, document_ids: frozenset[UUID] | None = None) -> Retriever:
    if _retriever_factory is not None:
        injected = _retriever_factory(session)
        return (
            injected if document_ids is None else _DocumentScopedRetriever(injected, document_ids)
        )
    try:  # Şerit 1, T006
        from app.modules.retrieval.service import HybridRetriever
    except ImportError as exc:
        raise PipelineUnavailableError(
            "Arama hattı henüz hazır değil. Lütfen daha sonra tekrar deneyin."
        ) from exc
    return HybridRetriever(
        session,
        document_ids=None if document_ids is None else tuple(sorted(document_ids, key=str)),
    )


def get_generator() -> Generator:
    if _generator is not None:
        return _generator
    try:  # Şerit 2, T012
        from app.modules.generation.service import GenerationService
    except ImportError as exc:
        raise PipelineUnavailableError(
            "Cevap üretimi henüz hazır değil. Lütfen daha sonra tekrar deneyin."
        ) from exc
    return GenerationService()


def get_guardrails() -> Sequence[Guardrail]:
    """Zincir halkaları, Şerit 2'nin belirlediği SIRAYLA.

    Sıra bu dosyada kurulmaz: ARCHITECTURE §5 sırası (citation → leakage → sanitize)
    `modules/guardrails/chain.py` içinde tek yerde sabitlenir. Halkaların uygulanması
    (düşen atıfların temizlenmesi, sanitize edilmiş metnin yazılması) çağıranın işidir;
    `Guardrail.check()` karar döner, nesneyi değiştirmez.
    """
    if _guardrails is not None:
        return _guardrails
    try:  # Şerit 2
        from app.modules.guardrails.chain import GUARDRAIL_CHAIN
    except ImportError as exc:
        raise PipelineUnavailableError(
            "Güvenlik zinciri henüz hazır değil. Lütfen daha sonra tekrar deneyin."
        ) from exc
    return GUARDRAIL_CHAIN
