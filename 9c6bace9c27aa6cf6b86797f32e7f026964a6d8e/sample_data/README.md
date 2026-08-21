# sample_data/isletim-sistemleri — Örnek Ders Materyali Paketi (T002)

İşletim Sistemleri dersi için hazırlanmış örnek materyal paketi. Amaç: retrieval,
chunking (sayfa/slayt metadata'sı), soru üretimi (`code_trace`/`bug_hunt` dahil) ve
gold set'in üzerine kurulacağı gerçek, telifsiz bir korpus sağlamak.

**Telif:** Tüm metinler bu paket için **kendi üretimimizdir** (Metehan Alphan, R5 — Data
& Eval). Hiçbir dosya bir eğitmenin ders slaytından kopyalanmamıştır. Kod örnekleri
klasik, kamuya mal olmuş işletim sistemi ders kitabı örneklerinin (üretici-tüketici,
fork() + wait()) yeniden yazılmış halidir; birebir alıntı değildir.

**Gerçek öğrenci verisi yoktur.**

## İçerik

| Dosya | Tür | Sayfa/slayt | Konu | Kaynak / lisans | Canlı demo |
|---|---|---|---|---|---|
| `01-processes.pdf` | PDF | 3 | Süreç, thread, `fork()`, context switch | Kendi üretimi | — |
| `02-cpu-scheduling.pdf` | PDF | 3 | CPU zamanlama: round-robin, SJF, öncelikli | Kendi üretimi | — |
| `03-memory-management.pdf` | PDF | 2 | Sayfalama, TLB, sayfa değiştirme | Kendi üretimi | — |
| `04-synchronization.pdf` | PDF | 3 | Mutex, semafor, üretici-tüketici | Kendi üretimi | — |
| `05-deadlock-demo.pdf` | PDF | 2 | Deadlock dört koşulu, Banker's Algorithm | Kendi üretimi | **EVET** |
| `06-file-systems.pptx` | PPTX | 7 slayt | Dosya sistemleri, inode, boş alan yönetimi | Kendi üretimi | — |
| `producer_consumer.py` | Kod (Python) | — | Üretici-tüketici — **bilinçli hatalı** (`bug_hunt` için: `wait()` mutex içinde çağrılıyor, yanlış sıra) | Kendi üretimi | — |
| `fork_example.c` | Kod (C) | — | `fork()` + `waitpid()` + doğru fd kapatma (`code_trace` için) | Kendi üretimi | — |

## Zorunlu özellikler — nasıl karşılandı

- **TR/EN karışık + teknik token:** `fork()`, `TLB`, `O(n log n)`, `O(m × n²)`, `mutex`,
  `context switch`, `semaphore`, `page fault`, `deadlock` metinlerde birebir geçiyor
  (FTS `simple` + `unaccent` konfigürasyonunun test edilmesi için — köklendirme yok,
  bu tokenlar bozulmadan aranabilmeli).
- **Bilinçli hatalı kod:** `producer_consumer.py` — `wait(empty)`/`wait(full)` çağrıları
  mutex kritik bölgesinin İÇİNDE yapılıyor; doğrusu mutex'ten önce ve dışında olmalı
  (04-synchronization.md'de doğru sıra anlatılır). Bu hatanın tek doğrulanmış sonucu
  **deadlock**'tur (15/15 koşumda kilitlenme, tampon taşması/taşınması hiç gözlenmedi) —
  `bug_hunt` sorusunun cevap anahtarı budur.
- **Aynı konu iki dosyada, farklı açılardan:**
  - **context switch**: `01-processes.pdf` süreç/thread açısından tanımlar;
    `02-cpu-scheduling.pdf` round-robin quantum seçiminin context switch maliyetiyle
    ödünleşimini anlatır; `03-memory-management.pdf` TLB flush açısından ele alır.
    Bu üçlü, `multi_chunk` gold set sorularının malzemesidir.
  - **fork() sonrası dosya tanımlayıcısı**: `01-processes.md`'de uyarı olarak geçer,
    `fork_example.c`'de doğru uygulaması gösterilir.
- **Küçük demo PDF'i:** `05-deadlock-demo.pdf` (2 sayfa) canlı demo yüklemesi için
  ayrıca işaretlenmiştir; diğer materyal önceden işlenmiş seed olarak durur.

## Not — sayfa sayıları hakkında

Brief'te önerilen sayfa aralığı 8-12'ydi; bu paketteki PDF'ler daha kısa (2-3 sayfa)
üretildi çünkü amaç retrieval/chunking/citation testleri için gerçek, çok sayfalı,
teknik terim yoğun materyal sağlamaktı — sayfa sayısı değil içerik çeşitliliği önceliklendi.
Gerekirse her dosya aynı desende genişletilebilir (yeni alt başlıklar eklenerek); şema ve
format değişmez.

## Kabul kriteri (brief §Teslimat 1) — 9 Ağustos 2026'da doğrulandı

Paket gerçek ingest hattından geçirildi (Anayasa VIII: gözlenmeden bitmedi). Koşu
`evaluation/build_corpus.py` ile yapıldı — gerçek yükleme ucu, gerçek doğrulama,
gerçek worker, gerçek chunking ve embedding; hiçbir satır doğrudan INSERT edilmedi:

```bash
cd apps/api
uv run python ../../evaluation/build_corpus.py --database dou_synapse_eval --recreate
```

**Sonuç: 8/8 dosya `completed`, 33 chunk.**

| Dosya | Chunk | Sayfa no'lu | Slayt no'lu | Embedding'li |
|---|---:|---:|---:|---:|
| `01-processes.pdf` | 3 | 3 | — | 3 |
| `02-cpu-scheduling.pdf` | 4 | 4 | — | 4 |
| `03-memory-management.pdf` | 3 | 3 | — | 3 |
| `04-synchronization.pdf` | 4 | 4 | — | 4 |
| `05-deadlock-demo.pdf` | 4 | 4 | — | 4 |
| `06-file-systems.pptx` | 7 | — | 7 | 7 |
| `fork_example.c` | 2 | — | — | 2 |
| `producer_consumer.py` | 6 | — | — | 6 |

Her PDF chunk'ı sayfa, her slayt chunk'ı slayt numarası taşıyor; kod chunk'larında
ikisi de yok ve olmamalı (konum bilgisi `section_title` içinde satır aralığı olarak
durur). Chunk sayısının sayfa sayısından fazla olduğu dosyalarda bir sayfa birden çok
chunk'a bölünmüş; **hiçbir chunk iki sayfayı birleştirmiyor** (ARCHITECTURE §3).

Aynı korpusa karşı gold set kaynakları da doğrulandı — `calibration.json` ve
`holdout.json` içindeki her `expected_sources` girdisinin karşılığı korpusta var:

```bash
uv run python ../../evaluation/verify_gold_set.py --corpus <build_corpus çıktısı>.json
```

**`.md` dosyaları korpusa girmez.** Pakette her ders notunun hem `.md` hem `.pdf`
hâli var; derse yüklenen PDF'tir, Markdown kaynak metindir. İkisi birden yüklenirse
her sayfa iki kez temsil edilir ve Recall olduğundan yüksek çıkar.

**Ölçüm koşusu için not:** yukarıdaki doğrulama yerel varsayılan olan
`EMBEDDING_PROVIDER=hashing` ile yapıldı. Bu deterministik SAHTE bir embedding'dir;
ingest hattının çalıştığını kanıtlar ama **bu korpusta ölçülen Recall rapora giremez**.
Ölçüm koşuları `EMBEDDING_PROVIDER=fastembed` ile yeniden kurulmuş korpusta yapılır;
`build_corpus.py` hangi sağlayıcıyla kurduğunu her özetine yazar ve `hashing` ise
uyarır.
