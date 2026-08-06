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
  (04-synchronization.md'de doğru sıra anlatılır). Bu hata deadlock riski ve sayaç
  tutarsızlığına yol açar — `bug_hunt` sorusunun cevap anahtarı budur.
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

## Kabul kriteri (brief §Teslimat 1)

Paket `apps/web` üzerinden bir derse yüklendiğinde tüm dosyaların `completed` durumuna
geçtiği ve chunk'ların sayfa/slayt metadata'sı taşıdığı **gerçek bir yüklemeyle
doğrulanmalıdır** (Anayasa VIII). Bu depoda yerel Postgres/pgvector çalıştıramadığım
için bu adımı ben yapamadım — Metehan'ın yerel ortamında ilk iş bu olmalı.
