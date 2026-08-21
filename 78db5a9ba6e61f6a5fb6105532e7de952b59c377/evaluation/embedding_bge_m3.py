"""bge-m3 embedding sağlayıcısı — YALNIZ ölçüm için (T045).

Neden `apps/api` içinde değil: bu bir üretim sağlayıcısı değildir. T045 "e5-large mi
bge-m3 mü daha iyi" sorusunu ölçer; **karar ingest zamanıdır** ve sağlayıcıyı
değiştirmek tüm korpusun yeniden işlenmesi demektir. Ölçüm kazanan çıksa bile üretim
indeksi bu şeritte değişmez (12_R2_OLCUM.md İş 1). Dolayısıyla kodu da üretim
paketine girmez; burada, ölçüm klasöründe yaşar.

**Neden fastembed kullanılmıyor:** fastembed 0.8.0'ın dense model kataloğunda bge-m3
YOK — `TextEmbedding.list_supported_models()` çıktısında bulunmuyor; BAAI ailesinden
yalnız İngilizce `bge-*-en` modelleri var (bu, `app/modules/ingestion/embedding.py`
dosyasındaki "fastembed'in dense kataloğunda bge-m3 bulunmuyor" notunu doğrular).
Bu yüzden model resmî `BAAI/bge-m3` deposundaki ONNX dışa aktarımından, doğrudan
`onnxruntime` ile koşturuluyor. İki bağımlılık da (onnxruntime, tokenizers) fastembed
ile birlikte zaten kurulu; yeni bir çalışma zamanı (torch/sentence-transformers)
getirilmedi.

**Önek farkı — sessiz bir çöp kaynağı:** E5 ailesi `query: ` / `passage: ` öneklerini
ZORUNLU kılar, bge-m3 ise önek KULLANMAZ. İkisini karıştırmak hata vermez, yalnız
retrieval kalitesini düşürür. Bu sınıf artık önek eklemez ve `name` alanında bunu
açıkça söyler; karşılaştırmanın iki kolu da kendi doğru biçiminde çalışır.

Model indirme (bir kez, ~2,3 GB):

    uv run python -c "from huggingface_hub import snapshot_download; \\
        snapshot_download('BAAI/bge-m3', allow_patterns=['onnx/*'], \\
        cache_dir='~/.cache/dou-eval-models')"
"""

from __future__ import annotations

import glob
import os
from collections.abc import Sequence
from pathlib import Path

MODEL_ID = "BAAI/bge-m3"
EMBEDDING_DIM = 1024

#: Model deposunun indirildiği yer. Ortam değişkeniyle değiştirilebilir; ölçüm
#: koşusunun hangi kopyayı kullandığı sonuç dosyasına `embedding_model` olarak yazılır.
DEFAULT_CACHE = os.environ.get(
    "DOU_EVAL_MODEL_CACHE", str(Path.home() / ".cache" / "dou-eval-models")
)

#: bge-m3 sekiz bin token'a kadar destekler ama ölçüm korpusundaki chunk'lar ~500
#: token. Sınırı düşük tutmak koşuyu hızlandırır; kesme olursa uyarı basılır, çünkü
#: sessizce kırpılan bir chunk retrieval'ı bozar ve sebebi görünmez olur.
MAX_TOKENS = 1024


class BgeM3Unavailable(RuntimeError):
    """Model indirilmemiş. Mesaj ne yapılacağını söyler."""


def _find_onnx(cache_dir: str) -> tuple[str, str]:
    model = glob.glob(f"{cache_dir}/models--BAAI--bge-m3/snapshots/*/onnx/model.onnx")
    tokenizer = glob.glob(f"{cache_dir}/models--BAAI--bge-m3/snapshots/*/onnx/tokenizer.json")
    if not model or not tokenizer:
        raise BgeM3Unavailable(
            f"bge-m3 ONNX dosyaları {cache_dir} altında bulunamadı.\n"
            "İndirmek için:\n"
            '  uv run python -c "from huggingface_hub import snapshot_download; '
            "snapshot_download('BAAI/bge-m3', allow_patterns=['onnx/*'], "
            f"cache_dir='{cache_dir}')\""
        )
    return model[0], tokenizer[0]


class BgeM3OnnxProvider:
    """`app.modules.ingestion.embedding.EmbeddingProvider` protokolünü uygular.

    `set_embedding_provider()` ile enjekte edilir; üretim kodunda hiçbir değişiklik
    gerektirmez. Boyut 1024 — e5-large ile aynı, yani `vector(1024)` kolonu ve şema
    değişmeden ikinci bir indeks kurulabiliyor. Karşılaştırmayı ucuzlatan şey bu.
    """

    def __init__(self, cache_dir: str = DEFAULT_CACHE, batch_size: int = 8) -> None:
        self._model_path, self._tokenizer_path = _find_onnx(cache_dir)
        self._batch_size = batch_size
        self._session: object | None = None
        self._tokenizer: object | None = None
        self.truncated = 0

    @property
    def dimension(self) -> int:
        return EMBEDDING_DIM

    @property
    def name(self) -> str:
        # Sonuç dosyasındaki `embedding_model` bu değeri alır. Önek davranışının
        # adın içinde durması, iki kolun ayarını rapordan geri okunabilir kılıyor.
        return f"{MODEL_ID} (onnx, öneksiz)"

    def _load(self) -> tuple[object, object]:
        if self._session is None:
            import onnxruntime as ort
            from tokenizers import Tokenizer

            options = ort.SessionOptions()
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self._session = ort.InferenceSession(
                self._model_path, options, providers=["CPUExecutionProvider"]
            )
            tokenizer = Tokenizer.from_file(self._tokenizer_path)
            tokenizer.enable_truncation(max_length=MAX_TOKENS)
            tokenizer.enable_padding()
            self._tokenizer = tokenizer
        return self._session, self._tokenizer  # type: ignore[return-value]

    def _embed(self, texts: Sequence[str]) -> list[list[float]]:
        import numpy as np

        session, tokenizer = self._load()
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = list(texts[start : start + self._batch_size])
            encoded = tokenizer.encode_batch(batch)  # type: ignore[attr-defined]
            for text, encoding in zip(batch, encoded, strict=True):
                # Kırpma sessiz kalmamalı: kırpılan chunk'ın vektörü metnin tamamını
                # temsil etmez ve Recall bundan etkilenir.
                if len(encoding.ids) >= MAX_TOKENS and len(text) > 0:
                    self.truncated += 1

            input_ids = np.array([e.ids for e in encoded], dtype=np.int64)
            attention = np.array([e.attention_mask for e in encoded], dtype=np.int64)
            outputs = session.run(  # type: ignore[attr-defined]
                ["sentence_embedding"],
                {"input_ids": input_ids, "attention_mask": attention},
            )
            # bge-m3'ün yoğun (dense) vektörü CLS token'ının izdüşümüdür ve ONNX dışa
            # aktarımı bunu `sentence_embedding` olarak veriyor. L2 normalizasyonu
            # burada açıkça uygulanıyor: pgvector kosinüs mesafesi normalize edilmiş
            # vektör varsayar ve e5 kolu da (fastembed içinde) normalize dönüyor.
            batch_vectors = outputs[0]
            norms = np.linalg.norm(batch_vectors, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            vectors.extend((batch_vectors / norms).astype(float).tolist())
        return vectors

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        # Önek YOK. E5 ile en kritik fark bu; bge-m3 sorgu ve belgeyi aynı biçimde alır.
        return self._embed([text])[0]


def install() -> BgeM3OnnxProvider:
    """Sağlayıcıyı üretim kancasına takar ve örneği döndürür."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))
    from app.modules.ingestion.embedding import set_embedding_provider

    provider = BgeM3OnnxProvider()
    set_embedding_provider(provider)
    return provider
