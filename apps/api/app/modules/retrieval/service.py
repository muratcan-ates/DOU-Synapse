"""Hibrit retrieval servisi — Faz A'nın dışarı verdiği tek yüzey.

İki arama paralel koşar, RRF ile birleşir, `limit` kadar parça döner. Modülün iki
farklı giriş noktası vardır ve **ayrı olmaları bilinçlidir**:

``HybridRetriever.search()``
    `contracts.Retriever` protokolünün gerçek uygulaması. **Ham** sonuç döndürür;
    kanıt eşiği uygulanmaz. Kalibrasyon (T043) aynı aramayı farklı eşiklerle
    değerlendirebilsin diye böyle: arama bir kez koşar, eşik süpürülür.

``retrieve()``
    Üretim yolu (tasks.md T006). Aramayı koşar ve **kanıt kapısını uygular**;
    eşik aşılamazsa `chunks` BOŞ döner (fail-closed, Anayasa IV). Çağıranın bayrağı
    gözden kaçırıp elindeki zayıf parçalarla cevap üretmesi mümkün olmasın diye
    parçalar bilerek geri verilmez.

---

**Kanıt eşiği neye uygulanır — ve neye uygulanamaz.**

Hattaki üç skorun yalnız biri mutlak ölçeklidir:

* `fused_score` (RRF): sıraya bakar, içeriğe değil. Üst sınırı sorgunun kalitesinden
  bağımsızdır (n sıralama için n/(k+1)); tamamen alakasız bir korpusta da aynı değeri
  üretir, çünkü her sıralamanın bir birincisi vardır. **Eşik taşıyamaz.** (Varsayılan
  k=60 ile iki sıralamada üst sınır ≈ 0.033'tür; `evidence_threshold=0.35` ile
  karşılaştırılsaydı her sorgu abstain ederdi — kapı kapalı değil, mühürlü olurdu.)
* `fts_score` (`ts_rank`): sorgunun terim sayısına ve belge uzunluğuna bağlıdır,
  sorgular arasında karşılaştırılamaz.
* `dense_score`: kosinüs benzerliği, [-1, 1], sorgudan bağımsız anlamı olan tek sayı.

Bu yüzden kapı **en iyi parçanın `dense_score`'una** bakar.

**Eşik kalibre EDİLMEMİŞTİR** (`config.evidence_threshold = 0.35`, T043). Bu kod eşiği
seçmez, yalnızca uygular. Ama uygulanacak yeri seçerken dağılım ölçüldü ve çıkan tablo
T043'e devredilmesi gereken bir bulgu — 8 konuyla ilgili + 4 konu dışı sorgu, gerçek
materyalin 80 pasajı üzerinde, en iyi parçanın kosinüs benzerliği::

    sağlayıcı            ilgili sorgular   konu dışı sorgular   ayrım    0.35 ne yapar
    multilingual-e5      0.834 - 0.888     0.690 - 0.782        +0.051   hiç kapanmaz
    hashing              0.104 - 0.707     0.000 - 0.207        -0.103   8 ilgili sorgunun
                                                                          6'sını da keser

Tek bir sayı iki sağlayıcıda **ters yönlerde** yanılıyor: e5'te 0.35 konu dışı
sorguların tamamının altında kalır (kapı hep açık), hashing'de ilgili sorguların çoğunun
üstünde kalır (kapı hep kapalı). Sebebi yapısal — e5 alakasız çiftlerde bile ~0.7 taban
benzerlik üretir, hashing ise sözcük örtüşmesine dayandığı için uzun pasajlarda
benzerliği doğal olarak seyreltir.

Ölçüm sonra **gerçek ingest hattından geçmiş chunk'lar** üzerinde tekrarlandı (üretim
modeli, 8 belge / 33 chunk, 14 ilgili + 10 konu dışı sorgu)::

    en iyi kosinüs        min      medyan    max
    ilgili   (n=14)      0.7963   0.8351   0.8671
    konu dışı (n=10)     0.6710   0.7549   0.7966

    varsayılan eşik 0.35 → konu dışı sorguların 10/10'u kapıdan GEÇİYOR

Dağılımlar uçlarda birbirine değiyor, ama sinyalin kendisi sağlam: **en iyi kesim
0.7963'te doğruluk 0.96** (14 ilgilinin hiçbiri kaçmıyor, 10 konu dışından 1'i geçiyor).
Yani sorun sinyal seçimi değil, eşiğin değeri — 0.35 olması gereken yerin ~0.45 altında.

Aday bir alternatif sinyal de ölçüldü: en iyi parçanın skoru eksi korpusun medyan skoru
("marj"). Daha kötü ayırıyor (en iyi kesim 0.0564'te doğruluk 0.88), dolayısıyla mutlak
kosinüste kalındı.

n=24 bir **yön göstergesidir, kalibrasyon değildir**; kalibrasyon ve holdout setleri
ayrılmadan bu sayı rapora giremez (ARCHITECTURE.md §7). `config.py` ve kalibrasyon bu
şeridin dosyaları değil — bulgu gruba ve T043'e bırakıldı, varsayılan değere
dokunulmadı. Bugün buradan çıkan tek iddia şudur: kapı **belirlenimcidir ve kapalı
tarafa düşer** — seçilen sayının doğruluğu iddia edilmiyor.

`candidate_count` çağırana bırakılmış bir ayrımdır: sıfırsa ders bu konuyu hiç
kapsamıyor olabilir (`out_of_scope`), sıfır değilken abstain edildiyse kanıt zayıf
demektir (`insufficient_context`). Bu eşleme cevap katmanının kararıdır; retrieval
ikisini ayırt edecek anlamsal bilgiye sahip değildir (contracts.AnswerStatus).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import RetrievedChunk
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.modules.retrieval.dense import dense_search
from app.modules.retrieval.fts import fts_search
from app.modules.retrieval.fusion import reciprocal_rank_fusion

logger = get_logger("app.retrieval")


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """Üretim yolunun çıktısı: parçalar + kapının neden öyle karar verdiği.

    `abstained` ise `chunks` boştur. Kararın gerekçesi (`best_dense_score`,
    `threshold`, `candidate_count`) taşınır; aksi hâlde "neden cevap vermedi"
    sorusu ancak sorguyu elle tekrarlayarak yanıtlanabilirdi.
    """

    chunks: list[RetrievedChunk]
    abstained: bool
    best_dense_score: float
    threshold: float
    candidate_count: int


class HybridRetriever:
    """`contracts.Retriever` protokolünün gerçek uygulaması.

    Oturumu taşır çünkü protokolün imzasında `session` yoktur: retriever bir istek
    bağlamına (ve dolayısıyla o isteğin RLS oturumuna) bağlı kurulur.
    """

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()

    async def search(self, *, course_id: UUID, query: str, limit: int = 8) -> list[RetrievedChunk]:
        """Hibrit arama, HAM sonuç. Kanıt eşiği uygulanmaz — bkz. modül docstring'i."""
        if limit <= 0 or not query.strip():
            return []

        settings = self._settings
        # İki arama aynı oturumu paylaşamaz: SQLAlchemy AsyncSession eşzamanlı iki
        # sorguyu desteklemez ve tek bağlantı üzerinde sıraya girerler. Sıralı koşmak
        # burada dürüst olan: sahte bir paralellik iddiası ölçüme girerse yanıltır.
        dense_hits = await dense_search(
            self._session,
            course_id=course_id,
            query=query,
            limit=settings.retrieval_dense_candidates,
        )
        fts_hits = await fts_search(
            self._session,
            course_id=course_id,
            query=query,
            limit=settings.retrieval_fts_candidates,
        )
        return fuse(dense_hits, fts_hits, limit=limit, rrf_k=settings.retrieval_rrf_k)


def fuse(
    dense_hits: list[RetrievedChunk],
    fts_hits: list[RetrievedChunk],
    *,
    limit: int,
    rrf_k: int,
) -> list[RetrievedChunk]:
    """İki sıralamayı RRF ile birleştirir ve üç skoru da dolu parçalar döndürür.

    Saf fonksiyon: veritabanı gerektirmez, böylece birleştirme davranışı sentetik
    sıralamalarla sınanabilir. Bir parça yalnız bir şeritten geldiyse diğer skoru
    0.0 kalır — bu bilgi kalibrasyonda "hangi şerit ne getirdi" sorusunu yanıtlar.
    """
    by_id: dict[UUID, RetrievedChunk] = {}
    dense_scores: dict[UUID, float] = {}
    fts_scores: dict[UUID, float] = {}

    for chunk in dense_hits:
        by_id.setdefault(chunk.chunk_id, chunk)
        dense_scores[chunk.chunk_id] = chunk.dense_score
    for chunk in fts_hits:
        by_id.setdefault(chunk.chunk_id, chunk)
        fts_scores[chunk.chunk_id] = chunk.fts_score

    fused = reciprocal_rank_fusion(
        [[chunk.chunk_id for chunk in dense_hits], [chunk.chunk_id for chunk in fts_hits]],
        k=rrf_k,
    )

    return [
        replace(
            by_id[chunk_id],
            dense_score=dense_scores.get(chunk_id, 0.0),
            fts_score=fts_scores.get(chunk_id, 0.0),
            fused_score=score,
        )
        for chunk_id, score in fused[:limit]
    ]


async def retrieve(
    session: AsyncSession,
    *,
    course_id: UUID,
    query: str,
    limit: int | None = None,
    settings: Settings | None = None,
) -> RetrievalResult:
    """Üretim yolu: hibrit arama + kanıt kapısı (fail-closed).

    `course_id` yetki DEĞİLDİR — çağıran üyeliği `CourseMemberDep` ile zaten
    doğrulamıştır ve RLS aynı oturumda ikinci katman olarak durur.
    """
    settings = settings or get_settings()
    top_k = limit if limit is not None else settings.retrieval_top_k

    retriever = HybridRetriever(session, settings)
    chunks = await retriever.search(course_id=course_id, query=query, limit=top_k)

    best_dense = max((chunk.dense_score for chunk in chunks), default=0.0)
    threshold = settings.evidence_threshold
    abstained = best_dense < threshold

    if abstained:
        logger.info(
            "kanıt eşiği aşılamadı, abstain",
            extra={
                "context": {
                    "course_id": str(course_id),
                    "candidate_count": len(chunks),
                    "best_dense_score": round(best_dense, 4),
                    "threshold": threshold,
                }
            },
        )

    return RetrievalResult(
        chunks=[] if abstained else chunks,
        abstained=abstained,
        best_dense_score=best_dense,
        threshold=threshold,
        candidate_count=len(chunks),
    )


__all__ = [
    "HybridRetriever",
    "RetrievalResult",
    "fuse",
    "retrieve",
]
