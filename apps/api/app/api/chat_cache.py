"""Sohbet önbelleği: anahtar, revizyon parmak izleri ve birebir eşleşme.

`app/api/chat.py`'den taşındı (modülerizasyon v2, PR 11). Davranış birebir aynı;
`chat.py` public adları (`question_hash`, `PROMPT_REVISION`, `CacheRevision`)
re-export eder. Tek yenilik `CacheRevision.hash_for`: `_lookup_cache` ile
`_store_cache` içindeki birebir aynı `question_hash(...)` çağrı bloğu tek yere
indi — anahtar üretimi artık iki kopyada sürüklenemez.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CourseContext
from app.contracts import AnswerStatus, AssistantAudience, ChatMode, Citation, GeneratedAnswer
from app.core.logging import get_logger
from app.models.chat import AnswerCache
from app.models.core import Document, DocumentStatus
from app.modules.policy import service as policy_service

logger = get_logger("app.chat")

PROMPT_REVISION = "005-role-aware-course-agent-v1"


def question_hash(
    mode: ChatMode,
    question: str,
    *,
    audience: AssistantAudience = AssistantAudience.STUDENT,
    policy_revision: str = "legacy",
    prompt_revision: str = "legacy",
    corpus_revision: str = "legacy",
) -> str:
    """Birebir eşleşme anahtarı (FR-034). Benzerlik tabanlı eşleşme YOKTUR.

    Normalizasyon yalnız Unicode biçimi (NFC) ve boşluk sadeleştirmesidir; harf
    büyüklüğü KORUNUR. Sebep: Türkçede i/İ ve ı/I dönüşümü kayıplıdır (Anayasa V) ve
    "aynı soru" tanımını bozar. Mod anahtarın parçasıdır — bir QA cevabı Sokratik moda
    servis edilirse merdiven baypas edilmiş olur.
    """
    normalized = " ".join(unicodedata.normalize("NFC", question).split())
    identity = "\n".join(
        (
            audience.value,
            mode.value,
            policy_revision,
            prompt_revision,
            corpus_revision,
            normalized,
        )
    )
    return hashlib.sha256(identity.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class CacheRevision:
    audience: AssistantAudience
    policy: str
    prompt: str
    corpus: str

    def hash_for(self, question: str, *, mode: ChatMode = ChatMode.QA) -> str:
        """Bu revizyon bağlamında sorunun önbellek anahtarı."""
        return question_hash(
            mode,
            question,
            audience=self.audience,
            policy_revision=self.policy,
            prompt_revision=self.prompt,
            corpus_revision=self.corpus,
        )


def _audience(context: CourseContext) -> AssistantAudience:
    return AssistantAudience.INSTRUCTOR if context.is_instructor else AssistantAudience.STUDENT


async def _cache_revision(
    session: AsyncSession,
    context: CourseContext,
    policy: policy_service.CoursePolicy,
) -> CacheRevision:
    policy_payload = {
        "allowed_modes": sorted(mode.value for mode in policy.allowed_modes),
        "max_hints": policy.max_hints,
        "sources": (
            None
            if policy.source_document_ids is None
            else sorted(str(value) for value in policy.source_document_ids)
        ),
        "evidence_threshold": policy.evidence_threshold,
        "daily_token_budget": policy.daily_token_budget,
        "student_daily_token_budget": policy.student_daily_token_budget,
        "instructor_daily_token_budget": policy.instructor_daily_token_budget,
        "max_output_tokens": policy.max_output_tokens,
        "max_concurrent_requests": policy.max_concurrent_requests,
    }
    policy_revision = hashlib.sha256(
        json.dumps(policy_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    query = select(
        Document.id,
        Document.file_hash,
        Document.updated_at,
        Document.superseded_at,
    ).where(
        Document.course_id == context.course_id,
        Document.status == DocumentStatus.COMPLETED,
        Document.superseded_at.is_(None),
    )
    if policy.source_document_ids is not None:
        query = query.where(Document.id.in_(policy.source_document_ids))
    rows = (await session.execute(query.order_by(Document.id))).all()
    corpus_payload = [
        (
            str(row.id),
            row.file_hash,
            row.updated_at.isoformat(),
            None if row.superseded_at is None else row.superseded_at.isoformat(),
        )
        for row in rows
    ]
    corpus_revision = hashlib.sha256(
        json.dumps(corpus_payload, separators=(",", ":")).encode()
    ).hexdigest()
    return CacheRevision(
        audience=_audience(context),
        policy=policy_revision,
        prompt=PROMPT_REVISION,
        corpus=corpus_revision,
    )


def _citation_to_json(citation: Citation, claim: str = "") -> dict[str, str]:
    return {
        "chunk_id": str(citation.chunk_id),
        "file_name": citation.file_name,
        "location": citation.location,
        "quote": citation.quote,
        "claim": claim,
    }


def _citation_from_json(raw: dict[str, Any]) -> Citation:
    return Citation(
        chunk_id=UUID(str(raw["chunk_id"])),
        file_name=str(raw["file_name"]),
        location=str(raw["location"]),
        quote=str(raw.get("quote", "")),
    )


async def _lookup_cache(
    session: AsyncSession,
    course_id: UUID,
    question: str,
    revision: CacheRevision,
) -> GeneratedAnswer | None:
    """Birebir eşleşmeli önbellek araması. Ders bazlıdır: A'nın cevabı B'ye gitmez."""
    row = (
        await session.execute(
            select(AnswerCache).where(
                AnswerCache.course_id == course_id,
                AnswerCache.audience == revision.audience,
                AnswerCache.policy_revision == revision.policy,
                AnswerCache.prompt_revision == revision.prompt,
                AnswerCache.corpus_revision == revision.corpus,
                AnswerCache.question_hash == revision.hash_for(question),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None

    payload = row.answer
    try:
        return GeneratedAnswer(
            status=AnswerStatus(payload["status"]),
            mode=ChatMode.QA,
            text=str(payload["text"]),
            citations=[_citation_from_json(c) for c in payload.get("citations", [])],
        )
    except (KeyError, ValueError, TypeError):
        # Bozuk önbellek satırı yok sayılır ve cevap yeniden üretilir; önbellek bir
        # hızlandırmadır, doğruluk kaynağı değildir.
        logger.warning("bozuk önbellek satırı yok sayıldı", extra={"context": {"id": str(row.id)}})
        return None


async def _store_cache(
    session: AsyncSession,
    course_id: UUID,
    question: str,
    answer: GeneratedAnswer,
    revision: CacheRevision,
) -> None:
    """Yalnız TAM HATTAN geçmiş, kaynaklı bir cevap önbelleğe girer."""
    if answer.status is not AnswerStatus.ANSWERED or not answer.citations:
        return
    await session.execute(
        pg_insert(AnswerCache)
        .values(
            course_id=course_id,
            audience=revision.audience,
            policy_revision=revision.policy,
            prompt_revision=revision.prompt,
            corpus_revision=revision.corpus,
            question_hash=revision.hash_for(question),
            answer={
                "status": answer.status.value,
                "text": answer.text,
                "citations": [_citation_to_json(c) for c in answer.citations],
            },
        )
        .on_conflict_do_nothing(
            index_elements=[
                "course_id",
                "audience",
                "policy_revision",
                "prompt_revision",
                "corpus_revision",
                "question_hash",
            ]
        )
    )
