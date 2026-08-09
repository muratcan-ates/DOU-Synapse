"""Yoğun (anlamsal) arama — pgvector üzerinde en yakın komşu.

Sorgu, indeksleme ile **aynı** sağlayıcıdan geçer (`ingestion.embedding`); ayrı bir
sorgu-embedder tanımlamak, indeksin vektör uzayından sessizce sapma riski demektir.
Sağlayıcı `query:` / `passage:` asimetrisini kendi içinde uygular ve bu davranış
`tests/test_embedding_prefix.py` ile sabitlenmiştir — burada tekrar önek eklenmez,
eklenirse `query: query: ...` olur.

---

**Mesafe operatörü: `<=>` (kosinüs). Karar tahmin değil, ölçüm.**

İlk varsayım şuydu: "vektörler birimdir, o hâlde `<->` (L2), `<=>` (kosinüs) ve `<#>`
(iç çarpım) aynı sıralamayı verir, seçim yalnız indeks uyumu meselesidir." **Ölçüm bu
varsayımı çürüttü.** Üretim sağlayıcısının (`multilingual-e5-large`, fastembed 0.8,
ortalama havuzlama) çıktısı birim DEĞİL — gerçek materyalin 80 pasajında ölçülen
normlar 27.4-30.3 arasında, sorgu normları 28.6-29.4 (`HashingEmbeddingProvider` ise
açıkça normalize ediyor, normu tam 1.0). Uzunluk sabit olmayınca ‖a-b‖² = 2 - 2·cos(a,b)
özdeşliği düşer ve üç operatör ayrışır. 12 sorguda top-8 sıralaması::

    kosinüse göre farklı sıralama üreten sorgu sayısı
      <-> (L2)          10/12
      <#> (iç çarpım)   12/12

Yani operatör seçimi sonucu gerçekten değiştiriyor; "muhtemelen kosinüs" demek
retrieval kalitesini kör bir yazı-turaya bırakmak olurdu.

`<=>` üç sebeple seçildi ve üçü de aynı yöne işaret ediyor:

1. **Modelin eğitildiği ölçü budur.** E5 ailesi kosinüs benzerliğiyle (sıcaklık
   ölçekli InfoNCE) eğitilir; vektör uzunluğu anlam taşımaz, yön taşır. `<->` ve `<#>`
   uzunluğa duyarlıdır ve uzun pasajları yapay olarak öne/arkaya iter.
2. **İndeks yalnız bunu destekler.** `chunks_embedding_idx` `vector_cosine_ops` ile
   kuruludur (0001_core_schema.sql); `<->`/`<#>` yazmak HNSW'yi devre dışı bırakır.
3. **Eşik taşıyabilen tek skor bundan çıkar.** `1 - (a <=> b)` gerçek kosinüs
   benzerliğidir, [-1, 1] mutlak ölçeğindedir ve sorgudan bağımsız anlamı vardır.
   `<#>` negatif iç çarpım, `<->` sınırsız mesafe döndürür; ikisi de kanıt kapısını
   (service.py) besleyemez.

**Bilinen sınır — filtrelenmiş ANN.** `WHERE course_id = ...` + RLS ile birlikte HNSW,
`ef_search` kadar aday üretip sonra filtreler; korpus büyüdükçe küçük bir dersin
sonuçları eksik dönebilir. Bugünkü ölçekte bu risk **gerçekleşmiyor, çünkü HNSW hiç
kullanılmıyor** — gerçek materyal yüklü veritabanında (33 chunk, 8 belge) alınan plan::

    Limit
      ->  Sort  (Sort Key: (embedding <=> '...'))
            ->  Bitmap Heap Scan on chunks c
                  Recheck Cond: (course_id = '...')
                  Filter: app.is_member(course_id)
                  ->  Bitmap Index Scan on chunks_course_idx

Planlayıcı `course_id` indeksinden gidip tam sıralama yapıyor, yani sonuç kesin.
(Plandaki `Filter: app.is_member(course_id)` satırı ayrıca RLS'in `dou_app` bağlantısında
gerçekten devrede olduğunun doğrudan kanıtı.) Korpus büyüyüp planlayıcı HNSW'ye geçtiğinde
çözüm pgvector 0.8'in `hnsw.iterative_scan` ayarıdır; bugün açılmadı çünkü davranışı
gerçek ölçekte ölçülmedi (Anayasa III).

Yetki notu: `course_id` bir yetki belgesi değildir, arama alanını daraltır. İzolasyonun
ikinci katmanı `chunks_member_read` RLS politikasıdır ve aynı oturumda zaten devrededir.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import RetrievedChunk
from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.vector_space import current_space
from app.modules.ingestion.embedding import get_embedding_provider

logger = get_logger("app.retrieval.dense")

# Aday kümesi chunks üzerinde seçilir, dosya adı SONRA join'lenir: documents'e katılmak
# sıralama adımına girerse planlayıcı HNSW indeksinden düşebilir.
_SQL = text(
    """
    WITH nearest AS (
        SELECT c.id,
               c.document_id,
               c.page_number,
               c.slide_number,
               c.section_title,
               c.text,
               c.embedding_space,
               c.embedding <=> CAST(:query_vector AS vector) AS distance
        FROM chunks c
        WHERE c.course_id = :course_id
          AND c.embedding IS NOT NULL
        ORDER BY c.embedding <=> CAST(:query_vector AS vector)
        LIMIT :limit
    )
    SELECT n.id,
           n.document_id,
           d.file_name,
           n.page_number,
           n.slide_number,
           n.section_title,
           n.text,
           n.embedding_space,
           1 - n.distance AS similarity
    FROM nearest n
    JOIN documents d ON d.id = n.document_id
    ORDER BY n.distance, n.id
    """
)


class EmbeddingSpaceMismatchError(AppError):
    """Korpus bir vektör uzayında, sorgu başkasında (0006).

    Neden fail-closed: uyuşmazlık ÇÖKMEZ. Kosinüs hesabı iki uzaydan gelen
    vektörlerde de bir sayı üretir, sıralama da üretilir — yalnızca anlamsızdır.
    Sessizce devam etmek, alakasız parçalara dayanan "kaynaklı" bir cevap üretmek
    demektir ve kullanıcı açısından en kötü hata türüdür: yanlış olduğunu
    anlamanın yolu yoktur (Anayasa I + IV).

    503 seçildi, 500 değil: bu bir kod hatası değil, yapılandırma/veri durumu.
    Korpus doğru sağlayıcıyla yeniden embed edildiğinde ya da sunucu doğru
    `EMBEDDING_PROVIDER` ile başlatıldığında düzelir.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "embedding_space_mismatch"

    def __init__(self, expected: str, found: set[str]) -> None:
        super().__init__(
            "Ders materyalinin arama indeksi bu sunucununkinden farklı bir modelle "
            "üretilmiş. Güvenilmez sonuç döndürmemek için aramayı durdurdum."
        )
        self.expected = expected
        self.found = sorted(found)


def _assert_same_space(rows: list[Any], expected: str) -> None:
    """Dönen satırların damgası bu sürecin uzayıyla uyuşuyor mu.

    Kontrol **dönen satırlar üzerinde** yapılıyor, dersin tamamı üzerinde değil.
    İki sebep, ikisi de aynı yöne çıkıyor: (1) ekstra sorgu yok, damga zaten
    seçilen satırlarla geliyor; (2) korunması gereken şey kullanılacak parçalar —
    top-k'ya girmemiş bir satırın uzayı bu cevabı etkilemez.

    `NULL` damga uyuşmazlık SAYILMAZ. 0006 öncesi yazılmış her satır damgasızdır;
    onları reddetmek göçün uygulandığı anda çalışan her kurulumu durdururdu.
    Gerekçe ve sınırı `supabase/migrations/0006_embedding_provenance.sql`'de.
    """
    found = {row.embedding_space for row in rows if row.embedding_space}
    if found and found != {expected}:
        logger.error(
            "embedding uzayı uyuşmazlığı",
            extra={"context": {"expected": expected, "found": sorted(found)}},
        )
        raise EmbeddingSpaceMismatchError(expected, found)


async def dense_search(
    session: AsyncSession, *, course_id: UUID, query: str, limit: int
) -> list[RetrievedChunk]:
    """Sorguya anlamsal olarak en yakın `limit` parçayı döndürür.

    Yalnızca `dense_score` doldurulur; `fts_score` ve `fused_score` birleştirme
    adımının işidir (service.py). Bir parçanın neden geldiğini ayrı ayrı taşımak,
    eşik kalibrasyonunun (T043) ön koşuludur.

    Uzay denetimi burada, FTS tarafında değil: uyuşmazlıktan etkilenen tek şerit
    bu. `ts_rank` sözcüklere bakar ve embedding sağlayıcısı değişince kıpırdamaz.
    """
    if limit <= 0 or not query.strip():
        return []

    # Üç sarmanın en kritiği burası (FR-220): ingestion ayrı bir worker sürecine
    # taşınsa bile sorgu embedding'i HER sohbet isteğinde API sürecinde koşar.
    # fastembed/ONNX çıkarımı senkron ve CPU'ya bağlıdır; doğrudan çağrıldığında
    # o süre boyunca sağlık yoklaması dahil hiçbir istek işlenemez.
    vector = await asyncio.to_thread(get_embedding_provider().embed_query, query)
    rows = (
        await session.execute(
            _SQL,
            {"query_vector": str(vector), "course_id": course_id, "limit": limit},
        )
    ).all()
    _assert_same_space(list(rows), current_space())

    return [
        RetrievedChunk(
            chunk_id=row.id,
            document_id=row.document_id,
            file_name=row.file_name,
            page_number=row.page_number,
            slide_number=row.slide_number,
            section_title=row.section_title,
            text=row.text,
            dense_score=float(row.similarity),
        )
        for row in rows
    ]
