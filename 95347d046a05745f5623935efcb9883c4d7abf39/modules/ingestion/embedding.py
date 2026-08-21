"""Embedding sağlayıcıları.

İki uygulama vardır:

* `FastEmbedProvider` — üretim yolu. Varsayılan model `intfloat/multilingual-e5-large`
  (1024 boyut), ONNX üzerinde CPU'da çalışır. Türkçe/İngilizce karışık ders materyali
  için çok dilli model şarttır; İngilizce odaklı bir model bu içerikte retrieval
  kalitesini düşürür.

  Mimaride ilk tercih bge-m3'tü; ancak fastembed'in dense model kataloğunda bge-m3
  bulunmuyor (yalnız seyrek/çok-vektörlü biçimde). Ek bir çalışma zamanı (sentence-
  transformers/optimum) getirmek yerine, aynı 1024 boyutu veren ve fastembed'de doğrudan
  desteklenen multilingual-e5-large seçildi; şema değişmedi. bge-m3, 3. haftadaki
  embedding A/B karşılaştırmasının adayı olarak duruyor (PLAN.md G11).
* `HashingEmbeddingProvider` — testler ve çevrimdışı geliştirme. Sözcük tabanlı hashing
  trick kullanır; anlamsal değil ama **sözcük örtüşmesine göre gerçek bir benzerlik**
  üretir, dolayısıyla retrieval sıralamasını model indirmeden deterministik biçimde
  sınayabiliriz.

Kritik kısıt: `EMBEDDING_PROVIDER` bir çalışma-zamanı yedeği DEĞİLDİR. Sağlayıcı
değişince vektör uzayı değişir; mevcut indeks anlamsızlaşır ve tüm korpusun yeniden
işlenmesi gerekir. Bu yüzden ayar ingest zamanına aittir.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Protocol

from app.core.logging import get_logger

logger = get_logger("app.embedding")

EMBEDDING_DIM = 1024
FASTEMBED_MODEL = "intfloat/multilingual-e5-large"


class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int: ...

    @property
    def name(self) -> str: ...

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


_WORD = re.compile(r"\w+", re.UNICODE)


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


class HashingEmbeddingProvider:
    """Deterministik, model indirmeyen embedding.

    Sözcükleri hashing trick ile boyutlara dağıtır. Eş anlamlıları yakalayamaz; amacı
    kaliteli retrieval değil, hattın uçtan uca sınanabilmesidir.
    """

    def __init__(self, dimension: int = EMBEDDING_DIM) -> None:
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def name(self) -> str:
        return "hashing-v1"

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        for word in _WORD.findall(text.casefold()):
            digest = hashlib.blake2b(word.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        return _normalize(vector)

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class FastEmbedProvider:
    """ONNX üzerinde CPU'da çalışan çok dilli üretim sağlayıcısı.

    Model tembel yüklenir. Dağıtımda model imaja gömülür; çalışma zamanında
    HuggingFace'e bağımlı kalmak, scale-to-zero sonrası ilk isteği dış bir servise
    bağlar ve demo günü kabul edilemez bir risk oluşturur (ARCHITECTURE.md §1).

    **e5 öneki uyarısı:** E5 ailesi modeller, sorgu ve belge metinlerinin `query: ` ve
    `passage: ` önekleriyle verilmesini bekler. fastembed'in `query_embed()` metodu
    varsayılan olarak düz `embed()`'e düşer ve bu önekleri EKLEMEZ; dolayısıyla önek
    burada açıkça uygulanır. Atlanırsa hiçbir hata alınmaz, yalnızca retrieval kalitesi
    sessizce düşer — bu yüzden davranış testle sabitlenmiştir.
    """

    def __init__(self, model_name: str = FASTEMBED_MODEL, cache_dir: str | None = None) -> None:
        self._model_name = model_name
        self._cache_dir = cache_dir
        self._model: object | None = None
        needs_prefix = "e5" in model_name.lower()
        self._query_prefix = "query: " if needs_prefix else ""
        self._passage_prefix = "passage: " if needs_prefix else ""

    @property
    def dimension(self) -> int:
        return EMBEDDING_DIM

    @property
    def name(self) -> str:
        return self._model_name

    def _load(self) -> object:
        if self._model is None:
            from fastembed import TextEmbedding

            logger.info(
                "embedding modeli yükleniyor", extra={"context": {"model": self._model_name}}
            )
            self._model = TextEmbedding(model_name=self._model_name, cache_dir=self._cache_dir)
        return self._model

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        model = self._load()
        prefixed = [f"{self._passage_prefix}{text}" for text in texts]
        return [list(map(float, vector)) for vector in model.embed(prefixed)]  # type: ignore[attr-defined]

    def embed_query(self, text: str) -> list[float]:
        model = self._load()
        prefixed = f"{self._query_prefix}{text}"
        return next(list(map(float, vector)) for vector in model.embed([prefixed]))  # type: ignore[attr-defined]


_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    global _provider
    if _provider is None:
        from app.core.config import get_settings

        settings = get_settings()
        if settings.embedding_provider == "fastembed":
            _provider = FastEmbedProvider(
                model_name=settings.embedding_model, cache_dir=settings.embedding_cache_dir
            )
        else:
            _provider = HashingEmbeddingProvider()
        logger.info("embedding sağlayıcısı", extra={"context": {"provider": _provider.name}})
    return _provider


def set_embedding_provider(provider: EmbeddingProvider | None) -> None:
    """Testlerin sağlayıcıyı değiştirebilmesi için."""
    global _provider
    _provider = provider
