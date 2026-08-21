"""E5 önek davranışının testleri.

Bu testler modeli indirmez; `FastEmbedProvider`'ın modele HANGİ metni gönderdiğini
doğrular. Önek eksikse hiçbir hata alınmaz, yalnızca retrieval kalitesi sessizce
düşer — bu yüzden davranışın testle sabitlenmesi gerekir.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.modules.ingestion.embedding import FastEmbedProvider


class FakeModel:
    """Kendisine gönderilen metinleri kaydeden sahte model."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    def embed(self, texts: Sequence[str], **_: Any) -> list[list[float]]:
        self.seen.extend(texts)
        return [[0.0] * 1024 for _ in texts]


def _provider_with_fake(model_name: str) -> tuple[FastEmbedProvider, FakeModel]:
    provider = FastEmbedProvider(model_name=model_name)
    fake = FakeModel()
    provider._model = fake
    return provider, fake


class TestE5Prefixes:
    def test_belgelere_passage_oneki_eklenir(self) -> None:
        provider, fake = _provider_with_fake("intfloat/multilingual-e5-large")
        provider.embed_documents(["Deadlock kosullari"])
        assert fake.seen == ["passage: Deadlock kosullari"]

    def test_sorguya_query_oneki_eklenir(self) -> None:
        provider, fake = _provider_with_fake("intfloat/multilingual-e5-large")
        provider.embed_query("Coffman kosullari nedir")
        assert fake.seen == ["query: Coffman kosullari nedir"]

    def test_sorgu_ve_belge_onekleri_farklidir(self) -> None:
        """E5'in asimetrik kullanımı: aynı metin sorgu ve belge olarak farklı gider."""
        provider, fake = _provider_with_fake("intfloat/multilingual-e5-large")
        provider.embed_query("ayni metin")
        provider.embed_documents(["ayni metin"])
        assert fake.seen[0] != fake.seen[1]

    def test_e5_olmayan_model_onek_almaz(self) -> None:
        provider, fake = _provider_with_fake("BAAI/bge-m3")
        provider.embed_query("sorgu")
        provider.embed_documents(["belge"])
        assert fake.seen == ["sorgu", "belge"]

    def test_toplu_belgelerin_hepsi_onek_alir(self) -> None:
        provider, fake = _provider_with_fake("intfloat/multilingual-e5-large")
        provider.embed_documents(["bir", "iki", "uc"])
        assert fake.seen == ["passage: bir", "passage: iki", "passage: uc"]

    def test_dimension_semayla_uyumlu(self) -> None:
        provider, _ = _provider_with_fake("intfloat/multilingual-e5-large")
        # chunks.embedding vector(1024) olarak tanımlı; uyuşmazlık INSERT'te patlar.
        assert provider.dimension == 1024
