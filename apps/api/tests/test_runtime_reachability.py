"""Runbook A6: kullanılan yolları gerçek çağrıyla ayıran ağsız regresyonlar."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app.contracts import AnswerStatus
from app.modules.agent.answers import _evidence_refusal
from app.modules.generation.llm import LiteLlmClient, LlmRequest
from app.modules.ingestion import embedding
from tests.conftest import UserFactory
from tests.factories import create_course, make_chunk, seed_document
from tests.test_generation import ok_response, settings_for


@pytest.mark.parametrize(
    ("error_name", "status_code", "expected_attempts"),
    [
        ("APIConnectionError", None, 2),
        ("APIError", None, 2),
        ("InternalServerError", None, 2),
        ("RateLimitError", None, 2),
        ("ServiceUnavailableError", None, 2),
        ("APITimeoutError", None, 2),
        ("UnknownProviderError", None, 1),
        ("RateLimitError", 401, 1),
    ],
)
async def test_saglayici_hata_adi_gercek_retry_kararina_ulasir(
    monkeypatch: pytest.MonkeyPatch,
    error_name: str,
    status_code: int | None,
    expected_attempts: int,
) -> None:
    """Sınıf adı yedeği ölü değildir; HTTP durumu varsa adın önüne geçer."""
    calls: list[str] = []
    provider_error = type(error_name, (Exception,), {"status_code": status_code})

    async def completion(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs["model"])
        if len(calls) == 1:
            raise provider_error("sentetik hata")
        return ok_response()

    async def no_sleep(_seconds: float) -> None:
        pass

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    client = LiteLlmClient(settings_for(llm_max_retries=1), completion_fn=completion)
    result = await client.complete(LlmRequest(system="s", user="u"))
    assert len(calls) == 2
    assert calls.count("groq/llama-3.3-70b-versatile") == expected_attempts
    assert result.provider == ("groq" if expected_attempts == 2 else "gemini")


@pytest.mark.parametrize(
    ("query", "dense", "expected"),
    [
        ("Osmanlı padişahı", 0.2, AnswerStatus.OUT_OF_SCOPE),
        ("deadlock süreç", 0.2, AnswerStatus.INSUFFICIENT_CONTEXT),
        ("deadlock süreç", 0.95, None),
    ],
)
def test_ajan_kanit_karari_kapsam_reddini_ayirt_eder(
    query: str, dense: float, expected: AnswerStatus | None
) -> None:
    candidate = make_chunk(text="deadlock süreç kaynak bekler", dense_score=dense, fts_score=0.0)
    assert _evidence_refusal([candidate], query, 0.81) is expected


@pytest.mark.parametrize(
    ("query", "level", "answer_allowed"),
    [
        ("  deadlock süreç kaynak bekler  ", "sufficient", True),
        ("Osmanlı padişahı", "out_of_scope", False),
        ("deadlock", "weak", False),
    ],
)
async def test_kaynak_laboratuvari_gercek_arama_ve_karari_birlikte_dondurur(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    query: str,
    level: str,
    answer_allowed: bool,
) -> None:
    """API → inspection → dense/FTS/RLS; arama servisi veya karar mock'lanmaz."""
    from app.core.config import get_settings

    monkeypatch.setenv("EVIDENCE_THRESHOLD", "0.81")
    get_settings.cache_clear()
    monkeypatch.setattr(embedding, "_provider", embedding.HashingEmbeddingProvider())
    teacher_id = await users.create("inspection@dogus.edu.tr")
    teacher = users.auth(teacher_id)
    course_id = await create_course(client, teacher, "INSPECT018")
    other_id = await create_course(client, teacher, "OTHER018")
    source = await seed_document(
        admin_engine,
        course_id=course_id,
        uploaded_by=teacher_id,
        file_name="ders.md",
        passages=["deadlock süreç kaynak bekler"],
        embeddings=True,
    )
    await seed_document(
        admin_engine,
        course_id=other_id,
        uploaded_by=teacher_id,
        file_name="baska.md",
        passages=["deadlock süreç kaynak bekler"],
        embeddings=True,
    )
    response = await client.post(
        f"/courses/{course_id}/sources/inspect",
        headers=teacher,
        json={"query": query, "limit": 1},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["query"] == query.strip()
    assert body["level"] == level
    assert body["answer_allowed"] is answer_allowed
    assert body["candidate_count"] == 1
    assert body["candidates"][0]["chunk_id"] == str(source.chunk_ids[0])
    assert body["candidates"][0]["file_name"] == "ders.md"
    assert body["candidates"][0]["text"] == "deadlock süreç kaynak bekler"
