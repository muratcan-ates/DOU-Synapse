"""Embedding sağlayıcısı ve vektör yazımı testleri."""

from __future__ import annotations

import math

from httpx import AsyncClient
from sqlalchemy import text as sql_text

from app.modules.ingestion.embedding import EMBEDDING_DIM, HashingEmbeddingProvider
from tests.conftest import UserFactory
from tests.test_ingestion import make_pdf


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


class TestHashingProvider:
    def test_dogru_boyut(self) -> None:
        provider = HashingEmbeddingProvider()
        assert provider.dimension == EMBEDDING_DIM
        assert len(provider.embed_query("deadlock nedir")) == EMBEDDING_DIM

    def test_deterministik(self) -> None:
        provider = HashingEmbeddingProvider()
        assert provider.embed_query("aynı metin") == provider.embed_query("aynı metin")

    def test_birim_vektor(self) -> None:
        vector = HashingEmbeddingProvider().embed_query("deadlock coffman kosullari")
        assert math.isclose(math.sqrt(sum(v * v for v in vector)), 1.0, rel_tol=1e-9)

    def test_benzer_metinler_daha_yakin(self) -> None:
        """Sözcük örtüşmesi kosinüs benzerliğine yansımalı; retrieval testleri buna dayanır."""
        provider = HashingEmbeddingProvider()
        query = provider.embed_query("deadlock coffman kosullari")
        related = provider.embed_query("coffman kosullari deadlock icin gereklidir")
        unrelated = provider.embed_query("binary search sirali dizide calisir")
        assert cosine(query, related) > cosine(query, unrelated)

    def test_bos_metin_cokmez(self) -> None:
        assert len(HashingEmbeddingProvider().embed_query("")) == EMBEDDING_DIM

    def test_toplu_embedding_tek_tek_ile_ayni(self) -> None:
        provider = HashingEmbeddingProvider()
        texts = ["birinci metin", "ikinci metin"]
        assert provider.embed_documents(texts) == [provider.embed_query(t) for t in texts]


class TestPipelineEmbedding:
    async def test_chunklara_vektor_yazilir(
        self, client: AsyncClient, users: UserFactory, admin_engine
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = (
            await client.post("/courses", json={"code": "COME301", "title": "OS"}, headers=ayse)
        ).json()["id"]
        await client.post(
            f"/courses/{course_id}/documents",
            files={"file": ("d.pdf", make_pdf(["Deadlock kosullari"]), "application/pdf")},
            headers=ayse,
        )

        from app import worker

        await worker.drain()

        async with admin_engine.begin() as conn:
            missing = await conn.scalar(
                sql_text("SELECT count(*) FROM chunks WHERE embedding IS NULL")
            )
            total = await conn.scalar(sql_text("SELECT count(*) FROM chunks"))
            dimension = await conn.scalar(
                sql_text("SELECT vector_dims(embedding) FROM chunks LIMIT 1")
            )
        assert total > 0
        assert missing == 0
        assert dimension == EMBEDDING_DIM

    async def test_vektor_aramasi_calisir(
        self, client: AsyncClient, users: UserFactory, admin_engine
    ) -> None:
        """pgvector kosinüs araması, ilgili sayfayı ilgisiz sayfadan öne çıkarmalı."""
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = (
            await client.post("/courses", json={"code": "COME301", "title": "OS"}, headers=ayse)
        ).json()["id"]
        pdf = make_pdf(
            [
                "Deadlock icin dort Coffman kosulu birlikte saglanmalidir",
                "Binary search sirali dizide arama alanini ikiye boler",
            ]
        )
        await client.post(
            f"/courses/{course_id}/documents",
            files={"file": ("d.pdf", pdf, "application/pdf")},
            headers=ayse,
        )

        from app import worker
        from app.modules.ingestion.embedding import get_embedding_provider

        await worker.drain()

        query = str(get_embedding_provider().embed_query("Coffman kosullari deadlock"))
        async with admin_engine.begin() as conn:
            page = await conn.scalar(
                sql_text(
                    "SELECT page_number FROM chunks WHERE course_id = :course_id "
                    "ORDER BY embedding <=> CAST(:query AS vector) LIMIT 1"
                ),
                {"course_id": course_id, "query": query},
            )
        assert page == 1
