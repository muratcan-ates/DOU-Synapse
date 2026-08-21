"""Seyrek (kelime) arama — mevcut `chunks.fts` kolonu üzerinde PostgreSQL FTS.

Altyapı `0001_core_schema.sql`'de hazır: `fts` üretilmiş kolondur
(`to_tsvector('simple', app.immutable_unaccent(text))`) ve GIN indeksi kuruludur.
Burada yeniden inşa edilmez; sorgu **aynı** konfigürasyon ve aynı unaccent
fonksiyonuyla hazırlanır, aksi hâlde indeksle sorgu farklı normalleştirmeden geçer
ve eşleşme sessizce kaybolur.

`simple` seçimi bilinçlidir: köklendirme `fork()`, `TLB`, `O(n log n)` gibi teknik
tokenları bozar; bir işletim sistemleri dersinde bu, aramanın işe yaramaması demektir
(ARCHITECTURE.md §1, Sparse arama satırı).

---

**Sorgu ayrıştırıcı seçimi — `websearch_to_tsquery`, ölçülerek daraltılmış bir kararla.**

Karşılaştırılan iki aday da rastgele kullanıcı girdisinde hata vermez (`to_tsquery`
verirdi, bu yüzden hiç aday değil). Fark, öğrencinin yazdığı işaretlere ne olduğudur::

    girdi                     websearch                 plainto
    "page fault"              'page' <-> 'fault'        'page' & 'fault'   (tırnak yok sayılır)
    mutex -semaphore          'mutex' & !'semaphore'    'mutex' & 'semaphore' (eksi yok sayılır)

Öğrenci tam terim aramak için tırnak, elemek için eksi kullanır; `plainto_tsquery`
bu niyeti sessizce çöpe atar. Bu yüzden `websearch_to_tsquery`.

**Ama örtük VE'si tek başına kullanılamaz.** Örnek materyal (`sample_data/
isletim-sistemleri`, 80 paragraf) üzerinde on gerçek soruyla ölçüldü — `websearch`'ün
tüm terimleri zorunlu kılan varsayılanı, sorguların **10'da 9'unda sıfır sonuç**
döndürüyor::

    sorgu                                                 VE (varsayılan)   VEYA (gevşetilmiş)
    deadlock koşulları nedir                                      0                 9
    fork() ne yapar                                               0                10
    what are the four conditions for deadlock                     0                 9
    TLB nedir ve neden kullanılır                                 0                38
    round robin quantum seçimi context switch maliyeti            1                18
    üretici tüketici probleminde mutex nasıl kullanılır           0                13
    page replacement algorithms                                   0                 3
    semaphore ile mutex arasındaki fark nedir                     0                16
    Banker's Algorithm nasıl çalışır                              0                11

Sebep açık: doğal dilde sorulan bir soru "nedir", "nasıl", "ne yapar" gibi materyalde
geçmeyen sözcükler taşır ve VE bunların hepsini zorunlu kılar. Böyle bir FTS şeridi
hatta duruyor görünüp hiçbir şey katmaz — etkin görünüp iş yapmayan bileşen kusurdur
(Anayasa XI).

Bu yüzden: **öğrenci açık işaret kullandıysa `websearch` olduğu gibi uygulanır**
(niyetini bozmak yanlış olurdu), **kullanmadıysa örtük VE, VEYA'ya gevşetilir** ve
sıralamayı `ts_rank` yapar — daha çok terimi ve daha yoğun eşleşen parça yukarı çıkar.
VEYA yolunun getirdiği geniş aday kümesi RRF'e sıra olarak girer; alttaki gürültü
1/(k+rank) ile zaten sönümlenir.

`simple` konfigürasyonunun durak sözcüğü listesi yoktur, dolayısıyla "ve", "nedir"
gibi sözcükler de sorgu terimi olur ve VEYA yolunda geniş bir aday kümesi doğurur.
Doküman frekansına göre bunları elemek T043 kalibrasyonunun adayıdır; bugün
kalibrasyon verisi olmadan eşik uydurmak Anayasa III ihlali olurdu.

`ts_rank` (yoğunluk) yerine `ts_rank_cd` (kapsama yoğunluğu) da kullanılabilirdi;
RRF yalnızca **sırayı** tükettiği için bu seçim ancak FTS'in kendi içindeki sıralamayı
etkiler, hatta giren sinyali değil. Ölçülmeden değiştirilecek bir parametre değil.
"""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import RetrievedChunk

#: Öğrencinin açık arama işareti kullandığını gösteren desenler: tırnak içinde tam
#: ifade, sözcük başında eksi (eleme), ayrı sözcük olarak `or`. Üçü de
#: `websearch_to_tsquery`'nin anladığı işaretlerdir; biri varsa niyet bozulmadan
#: uygulanır. Türkçe "veya" bilinçli olarak listede yok: `websearch_to_tsquery` onu
#: bir işleç olarak tanımaz, sıradan bir terim sayar.
_EXPLICIT_OPERATOR = re.compile(r'"|(?:^|\s)-\w|(?:^|\s)or(?:\s|$)', re.IGNORECASE)

_SQL = text(
    """
    WITH q AS (
        SELECT CASE
            WHEN CAST(:strict AS boolean) THEN
                websearch_to_tsquery('simple', app.immutable_unaccent(:query))
            ELSE COALESCE(
                (SELECT to_tsquery('simple', string_agg(quote_literal(lexeme), ' | '))
                   FROM unnest(to_tsvector('simple', app.immutable_unaccent(:query)))),
                ''::tsquery)
        END AS query
    ),
    matched AS (
        SELECT c.id,
               c.document_id,
               c.page_number,
               c.slide_number,
               c.section_title,
               c.text,
               c.chunk_index,
               ts_rank(c.fts, q.query) AS rank
        FROM chunks c, q
        WHERE c.course_id = :course_id
          AND c.fts @@ q.query
        -- Eşitlik bozma `c.id` DEĞİL: birincil anahtar `gen_random_uuid()` ile
        -- üretiliyor, yani aynı korpus yeniden ingest edildiğinde aynı parça
        -- başka bir kimlik alıyor ve eşit rank'li satırların sırası değişiyor.
        -- Bir korpus içinde kararlıydı, korpuslar ARASINDA değildi (R2 ölçtü:
        -- yeniden kurulan indekste Recall@5 0.981 → 0.971 ve T044'ün MRR güven
        -- aralığı sıfırın bir yanından diğerine geçti — "hibrit dense'ten
        -- iyidir" hükmü bu yüzden geri çekildi).
        --
        -- `(document_id, chunk_index)` belgenin içeriğinden türüyor: aynı
        -- materyal yeniden işlendiğinde aynı sırayı verir. Ölçüm artık yeniden
        -- üretilebilir.
        ORDER BY rank DESC, c.document_id, c.chunk_index
        LIMIT :limit
    )
    SELECT m.id,
           m.document_id,
           d.file_name,
           m.page_number,
           m.slide_number,
           m.section_title,
           m.text,
           m.rank
    FROM matched m
    JOIN documents d ON d.id = m.document_id
    ORDER BY m.rank DESC, m.document_id, m.chunk_index
    """
)


def uses_explicit_operators(query: str) -> bool:
    """Sorgunun tırnak/eksi/`or` taşıyıp taşımadığı — VE'yi koruma kararı buna bağlı.

    Ayrı ve genel bir fonksiyon: kararın kendisi testin konusudur (`test_fts.py`),
    SQL'in içine gömülü kalsaydı ancak veritabanıyla sınanabilirdi.
    """
    return _EXPLICIT_OPERATOR.search(query) is not None


async def fts_search(
    session: AsyncSession, *, course_id: UUID, query: str, limit: int
) -> list[RetrievedChunk]:
    """Sorguyla kelime düzeyinde eşleşen `limit` parçayı `ts_rank` sırasıyla döndürür.

    Yalnızca `fts_score` doldurulur; birleştirme service.py'nin işidir.
    """
    if limit <= 0 or not query.strip():
        return []

    rows = (
        await session.execute(
            _SQL,
            {
                "query": query,
                "strict": uses_explicit_operators(query),
                "course_id": course_id,
                "limit": limit,
            },
        )
    ).all()

    return [
        RetrievedChunk(
            chunk_id=row.id,
            document_id=row.document_id,
            file_name=row.file_name,
            page_number=row.page_number,
            slide_number=row.slide_number,
            section_title=row.section_title,
            text=row.text,
            fts_score=float(row.rank),
        )
        for row in rows
    ]
