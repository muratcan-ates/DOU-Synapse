# Şerit 1 — Retrieval hattı

> **Önce `00_OKU_ONCE.md` dosyasını oku.** Bu belge yalnız senin şeridini anlatır.
> Branch: `feat/retrieval` · Görevler: T003-T007 · Bağımlılık: **yok, hemen tam hız**

---

## Neden bu şerit önce bitmeli

Sen projenin **darboğazısın.** Chat ucu, Sokratik mod, soru üretimi ve
değerlendirme altyapısı — hepsi retrieval'ın çıktısını bekliyor. `HANDOFF.md`'nin
kendi ifadesiyle: *"T006 herkesi bloklar."*

Diğer şeritler senin **imzana** karşı yazıyor (`app/contracts.py` içindeki
`Retriever` protokolü), yani sen yazarken onlar da ilerliyor. Ama gerçek arama
inmeden hiçbiri gerçek materyalle sınanamaz.

## Sahiplendiğin dosyalar

Bu listenin dışına çıkma:

```
apps/api/app/modules/retrieval/__init__.py
apps/api/app/modules/retrieval/dense.py          YENİ
apps/api/app/modules/retrieval/fts.py            YENİ
apps/api/app/modules/retrieval/fusion.py         YENİ
apps/api/app/modules/retrieval/service.py        YENİ
apps/api/tests/test_retrieval.py                 YENİ
apps/api/tests/test_fts.py                       YENİ (istersen)
specs/001-course-assistant-mvp/tasks.md          yalnız T003-T007 satırları
```

## Ne inşa ediyorsun

`app/contracts.py`'deki `Retriever` protokolünü uygulayan bir servis:

```python
async def search(self, *, course_id: UUID, query: str, limit: int = 8) -> list[RetrievedChunk]
```

Üç parça hâlinde:

### T003-T004 — Dense arama (`dense.py`)

Soruyu embedding'e çevir, `chunks.embedding` üzerinde pgvector ile en yakın
komşuları getir. Ayarlar `config.py`'de hazır: `retrieval_dense_candidates`.

**Kritik:** E5 modeli `query:` / `passage:` öneki bekler ve fastembed bunu
**eklemez**. İndeksleme tarafında `passage:` kullanılıyor; sen sorguya `query:`
eklemek zorundasın. Bunu `test_embedding_prefix.py` zaten sabitliyor — oku,
aynı deseni izle. Öneki unutursan arama sessizce kötüleşir; hata vermez, sadece
yanlış sonuç döner. Bu, en pahalı hata türü.

Mesafe operatörü seçimi (`<->` L2, `<=>` kosinüs, `<#>` iç çarpım) modelin
normalizasyonuna bağlıdır. Hangisini seçtiğini **ölç ve gerekçesini docstring'e
yaz**; "muhtemelen kosinüs" yeterli değil (Anayasa III).

### T004 — Full-text arama (`fts.py`)

**FTS altyapısı `0001_core_schema.sql`'de ZATEN VAR:** `chunks.fts` kolonu ve GIN
indeksi kurulu, konfigürasyon `simple` + `unaccent`. Yeniden inşa etme, migration
açma.

`simple` seçimi bilinçli: köklendirme `fork()`, `O(n log n)`, `malloc` gibi teknik
tokenları bozar. Bir bilgisayar mühendisliği dersinde bu, aramanın işe yaramaması
demektir. Gerekçe `ARCHITECTURE.md`'de.

Sorguyu `websearch_to_tsquery` ya da `plainto_tsquery` ile hazırla; hangisini
seçtiğini gerekçelendir (kullanıcı tırnak/eksi işareti kullanabilir mi?).

### T005 — RRF birleşimi (`fusion.py`)

Reciprocal Rank Fusion: iki sıralamayı skorlarını normalize etmeye çalışmadan
birleştirir. Formül:

```
score(d) = Σ  1 / (k + rank_i(d))
```

`k` sabiti `config.retrieval_rrf_k` (varsayılan 60). RRF'in tercih sebebi,
dense skorlarıyla FTS skorlarının **karşılaştırılamaz ölçekte** olması; ikisini
ağırlıklı toplamak için önce kalibre etmek gerekirdi, RRF sıralamayla çalıştığı
için buna ihtiyaç duymaz.

`RetrievedChunk` üç skoru da taşır (`dense_score`, `fts_score`, `fused_score`).
Doldur — bir parçanın **neden geldiğini** söyleyemezsek eşik kalibrasyonu (T043)
körleşir.

### T006 — Servis (`service.py`)

İkisini koştur, birleştir, `limit` kadar döndür. Kanıt eşiği (`evidence_threshold`)
burada mı uygulanır yoksa çağıranda mı — kararı sen ver ve **gerekçesini yaz**.
Öneri: retrieval ham sonuç döndürsün, eşik kararı generation katmanında verilsin;
böylece aynı arama farklı eşiklerle değerlendirilebilir (T043 bunu gerektirecek).

### T007 — Testler (`test_retrieval.py`)

En az şunlar, ve **ilki pazarlıksız**:

1. **İzolasyon:** Başka dersin chunk'ı hiçbir koşulda dönmez. İki ders kur, ikisine
   de benzer içerik yükle, A dersinde arama yap, B'nin parçasının gelmediğini
   kanıtla. Bu test yalnız "gelmiyor" demesin — **politikayı bozup kırmızı
   yandığını da göster** (Anayasa II deseni).
2. **RRF doğruluğu:** Sentetik iki sıralamayla, elle hesaplanmış beklenen sonucu
   doğrula. Gerçek embedding kullanma; formülü test ediyorsun, modeli değil.
3. **Boş sonuç:** Materyalde karşılığı olmayan sorgu boş liste döndürür, patlamaz.
4. **Türkçe + İngilizce:** Materyal TR/EN karışık. İki dilde de sorgu çalışmalı.
5. **Teknik token:** `fork()` gibi bir token aranabilmeli — `simple` seçiminin
   sebebi buydu, testle sabitle.

Testler `hashing` embedding sağlayıcısıyla koşar (deterministik, ağsız). Gerçek
model indirmeyi teste sokma; CI'da ağ yok.

## Sıra önerisi

1. `test_retrieval.py`'de izolasyon testini **önce** yaz (kırmızı yanacak).
2. `fts.py` — en kolayı, altyapı hazır, hemen yeşil alırsın.
3. `dense.py` — E5 önekine dikkat.
4. `fusion.py` — saf fonksiyon, hızlı test edilir.
5. `service.py` — üçünü birleştir.
6. Gerçek materyalle elle dene: `sample_data/isletim-sistemleri` yüklü bir derste
   "deadlock koşulları nedir" sorusunun doğru sayfayı getirdiğini **gör**.

## Bitti sayılma ölçütü

- [ ] `uv run pytest -q` yeşil (mevcut 92 + seninkiler)
- [ ] `uv run ruff check .` ve `ruff format --check .` temiz
- [ ] İzolasyon testi politikayı bozunca **kırmızı yanıyor** (kanıtla, çıktıyı commit gövdesine yaz)
- [ ] Gerçek materyalde TR ve EN sorgu doğru sayfayı getiriyor — **tarayıcıda ya da
      psql'de gözlendi**, sadece test değil (Anayasa VIII)
- [ ] `tasks.md`'de T003-T007 `[x]` + tarihli DONE notu
- [ ] Mesafe operatörü ve tsquery seçiminin gerekçesi docstring'de

## Bittiğinde

Gruba **`Retriever` protokolünün gerçek uygulamasının hazır olduğunu** yaz — Şerit
3 ve 4 sahte uygulamalarını bırakıp seninkine geçecek.

Vaktin kalırsa: **T045 embedding A/B** (multilingual-e5-large vs bge-m3) senin
alanına en yakın iş. Ama önce Şerit 5'e sor, ölçüm altyapısı onda.
