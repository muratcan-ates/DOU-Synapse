# sample_data/isletim-sistemleri — Örnek Ders Materyali Paketi (T002)

İşletim Sistemleri dersi için hazırlanmış örnek materyal paketi. Amaç: retrieval,
chunking (sayfa/slayt metadata'sı), soru üretimi (`code_trace`/`bug_hunt` dahil) ve
gold set'in üzerine kurulacağı gerçek, telifsiz bir korpus sağlamak.

**Telif:** Tüm metinler bu paket için **kendi üretimimizdir** (v1: Metehan Alphan,
R5 — Data & Eval; v2: R2 — Ölçüm). Hiçbir dosya bir eğitmenin ders slaytından
kopyalanmamıştır. Kod örnekleri klasik, kamuya mal olmuş işletim sistemi ders kitabı
örneklerinin (üretici-tüketici, `fork()` + `wait()`, Banker's Algorithm) yeniden
yazılmış halidir; birebir alıntı değildir.

**Gerçek öğrenci verisi yoktur.**

## Sürümler

| Sürüm | Tarih | Dosya | Chunk | Neden |
|---|---|---:|---:|---|
| v1 | 6-9 Ağu 2026 | 8 | 33 | İlk paket: chunking, atıf ve sayfa metadata'sı testleri |
| **v2** | **9 Ağu 2026** | **22** | **167** | **Retrieval ölçümü doygundu; korpus büyütüldü** |

### v2 neden gerekliydi

9 Ağustos holdout koşusunda **Recall@5 ve Recall@8 = 1.000** çıktı. Bu bir başarı
değil, ölçütün doygunluğuydu: korpus 33 chunk'tı ve `top_k=8` her sorguda korpusun
yaklaşık **dörtte birini** döndürüyordu. O boyutta "beklenen kaynak ilk 8'de mi"
sorusunun cevabı neredeyse her zaman evettir ve retrieval kalitesi hakkında hiçbir şey
söylemez (`docs/test-report.md` §6).

v2'de korpus **167 chunk**'a çıktı; `top_k=8` artık korpusun **%4,8'ini** döndürüyor.
Ölçüt bu oranda ayırt edici olabilir.

**v1 dosyalarına dokunulmadı.** Değiştirilselerdi `holdout.json` ve `calibration.json`
içindeki 91 kaynak referansının sayfa numaraları sessizce koparadı ve 9 Ağustos
koşularıyla karşılaştırma imkânı kaybolurdu. v2 tümüyle **ektir**.

### v2 materyali nasıl üretildi

v1 PDF'leri pandoc + XeLaTeX ile üretilmişti; o araç zinciri bu makinede yok. v2 için
kaynak Markdown'dan PDF/PPTX üreten bir betik yazıldı:

```bash
cd apps/api && uv run python ../../sample_data/generate_material.py
cd apps/api && uv run python ../../sample_data/generate_material.py --check
```

Betik yalnız ön bilgisinde `format: pdf|pptx` beyan eden Markdown'ları işler; v1'in beş
kaynağı beyan taşımadığı için atlanır. Sayfa/slayt bölmesi kaynakta `<!-- sayfa -->` ve
`<!-- slayt -->` ile **açıkça** yazılır — akışa bırakılsaydı fontun birkaç piksellik
farkı bir cümleyi sonraki sayfaya atar ve gold set'in `(dosya, sayfa)` kimliği koparadı.

**Font:** metin bizim, font değil. Türkçe `ı/İ/ş/ğ` glifleri Base-14 PDF fontlarında
yok; işletim sisteminin Unicode fontu (macOS'ta Arial) kullanılır ve PDF'e yalnız
**alt kümesi** gömülür — bir belgeyi yazdırırken olan şeyin aynısı. Font dosyası depoya
konmaz; betik gliflerini denetler ve eksikse durur.

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

### v2 ile eklenenler (9 Ağustos 2026)

| Dosya | Tür | Sayfa/slayt | Konu | Kaynak / lisans |
|---|---|---|---|---|
| `07-virtual-memory.pdf` | PDF | 4 | Talep üzerine sayfalama, FIFO/LRU/Clock/OPT, Belady, thrashing, çalışma kümesi, copy-on-write | Kendi üretimi |
| `08-io-systems.pdf` | PDF | 4 | Yoklama/kesme/DMA, sürücü katmanları, tamponlama, kesme birleştirme | Kendi üretimi |
| `09-disk-and-storage.pdf` | PDF | 4 | FCFS/SSTF/SCAN/C-SCAN/LOOK, SSD + FTL + aşınma dengeleme, RAID 0/1/5/6/10 | Kendi üretimi |
| `10-security-and-protection.pdf` | PDF | 4 | En az ayrıcalık, ACL/capability, setuid, buffer overflow, kanarya/DEP/ASLR/ROP, şifre özetleme | Kendi üretimi |
| `11-virtualization-containers.pptx` | PPTX | 19 slayt | Hipervizör Tip 1/2, tam sanallaştırma/paravirt, VT-x, namespace, cgroups, konteyner katmanları | Kendi üretimi |
| `12-real-time-scheduling.pptx` | PPTX | 19 slayt | Katı/yumuşak gerçek zaman, WCET, RM, EDF, öncelik tersine dönmesi, kalıtım/tavan | Kendi üretimi |
| `13-ipc.pptx` | PPTX | 18 slayt | Boru, FIFO, mesaj kuyruğu, paylaşımlı bellek, semafor, sinyal, soket, RPC | Kendi üretimi |
| `14-distributed-os.pptx` | PPTX | 18 slayt | Kısmi arıza, Lamport/vektör saat, karşılıklı dışlama, 2PC, konsensüs, CAP, çoğaltma | Kendi üretimi |
| `15-boot-and-kernel.pptx` | PPTX | 19 slayt | BIOS/UEFI, önyükleyici, initramfs, sistem çağrısı, monolitik/mikro/hibrit çekirdek | Kendi üretimi |
| `reader_writer.py` | Kod (Python) | — | Okuyucu-yazar — **bilinçli hatalı** (`bug_hunt`: yazar açlığı) | Kendi üretimi |
| `page_replacement.py` | Kod (Python) | — | FIFO/LRU/Clock/OPT benzetimi — **bilinçli hatalı** (`bug_hunt`: LRU isabet durumunda tazelemiyor) | Kendi üretimi |
| `thread_pool.py` | Kod (Python) | — | Sınırlı kuyruklu thread havuzu, doğru (`code_trace`) | Kendi üretimi |
| `bankers_algorithm.c` | Kod (C) | — | Banker's güvenlik denetimi + kaynak isteği, doğru (`code_trace`) | Kendi üretimi |
| `pipe_shell.c` | Kod (C) | — | `pipe()` + iki `fork()` + `dup2()` + `execvp()`, doğru (`code_trace`) | Kendi üretimi |

### v2'deki iki kasıtlı hata — gözlendi, tahmin edilmedi

Anayasa III gereği bu iki hatanın sonucu **koşturularak** doğrulandı; aşağıdaki
sayılar ölçümdür.

**`reader_writer.py` — yazar açlığı.** İlk okuyucu `kaynak_kilidi`'ni alır, son okuyucu
bırakır. Okuyucular üst üste bindiğinde `okuyucu_sayisi` hiç sıfıra düşmez ve kilit hiç
bırakılmaz. 2 saniyelik koşuda ölçülen:

| Okuyucu | Okuma | Yazma | Yazarın en uzun beklemesi |
|---:|---:|---:|---:|
| 1 | 345 | 344 | 0,003 sn |
| 2 | 1373 | 1 | 2,000 sn |
| 4 | 2672 | 1 | 2,002 sn |
| 8 | 5613 | 0 | 2,000 sn |

```bash
python3 sample_data/isletim-sistemleri/reader_writer.py
```

Tek okuyucuyla kusur hiç görünmez; iki okuyucuda ortaya çıkar. `bug_hunt` sorusunun
cevap anahtarı budur. Üç tekrar koşuda da yazar 1 kez yazabildi (8 okuyucu, 1,5 sn).

**`page_replacement.py` — LRU tazelemiyor.** İsabet durumunda sayfa listenin sonuna
taşınmıyor; algoritma FIFO'ya çöküyor. Klasik referans dizisi ve 3 çerçeveyle ölçülen:

| Algoritma | Sayfa hatası | Beklenen |
|---|---:|---:|
| FIFO | 15 | 15 (doğru) |
| **LRU** | **15** | **12 — kusur burada** |
| Clock | 14 | 14 (doğru) |
| Optimal | 9 | 9 (doğru) |

`bug_hunt` işaretinin kendisi çıktının içindedir: LRU'nun FIFO'dan ayrıldığı tek yer
isabet davranışıdır, ikisi aynı sayıyı veriyorsa o davranış eksiktir. Aynı betik FIFO'nun
**Belady anomalisini** de gösteriyor (3 çerçevede 9 hata, 4 çerçevede 10 hata) —
07-virtual-memory.pdf §3.1'deki iddianın koşturulabilir kanıtı.

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

**v2 notu:** chunk sayısını belirleyen şey sayfa sayısı değil, sayfa başına düşen metin
miktarıdır. Chunk hedefi 500 token (≈1850 karakter) ve bir chunk iki sayfayı birleştirmez;
dolayısıyla ~1500 karakterlik bir PDF sayfası **1** chunk üretirken ~450 karakterlik bir
slayt da **1** chunk üretir. Slayt başına düşen karakter maliyeti dörtte biridir. v2'de
sunum ağırlıklı gidilmesinin sebebi budur — ve bu, gerçek ders materyalinin dağılımına
da PDF ağırlıklı bir pakete kıyasla daha yakındır.

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

## v2 kabul kriteri — 9 Ağustos 2026'da doğrulandı

Aynı hat, aynı komut, genişletilmiş paket:

```bash
cd apps/api
EMBEDDING_PROVIDER=fastembed uv run python ../../evaluation/build_corpus.py \
    --database dou_synapse_eval --recreate --out /tmp/corpus_e5.json
```

**Sonuç: 22/22 dosya `completed`, 167 chunk, 167'sinde embedding var.**

| Dosya | Chunk | Sayfa no'lu | Slayt no'lu | Embedding'li |
|---|---:|---:|---:|---:|
| `01-processes.pdf` | 3 | 3 | — | 3 |
| `02-cpu-scheduling.pdf` | 4 | 4 | — | 4 |
| `03-memory-management.pdf` | 3 | 3 | — | 3 |
| `04-synchronization.pdf` | 4 | 4 | — | 4 |
| `05-deadlock-demo.pdf` | 4 | 4 | — | 4 |
| `06-file-systems.pptx` | 7 | — | 7 | 7 |
| `07-virtual-memory.pdf` | 5 | 5 | — | 5 |
| `08-io-systems.pdf` | 4 | 4 | — | 4 |
| `09-disk-and-storage.pdf` | 4 | 4 | — | 4 |
| `10-security-and-protection.pdf` | 5 | 5 | — | 5 |
| `11-virtualization-containers.pptx` | 19 | — | 19 | 19 |
| `12-real-time-scheduling.pptx` | 19 | — | 19 | 19 |
| `13-ipc.pptx` | 18 | — | 18 | 18 |
| `14-distributed-os.pptx` | 18 | — | 18 | 18 |
| `15-boot-and-kernel.pptx` | 19 | — | 19 | 19 |
| `bankers_algorithm.c` | 4 | — | — | 4 |
| `fork_example.c` | 2 | — | — | 2 |
| `page_replacement.py` | 6 | — | — | 6 |
| `pipe_shell.c` | 3 | — | — | 3 |
| `producer_consumer.py` | 6 | — | — | 6 |
| `reader_writer.py` | 4 | — | — | 4 |
| `thread_pool.py` | 6 | — | — | 6 |
| **TOPLAM** | **167** | **36** | **100** | **167** |

Gold set kaynakları hem ayrıştırıcıya hem de bu korpusa karşı yeniden doğrulandı
(`verify_gold_set.py --corpus`): kalibrasyon 40 soru, holdout 161 soru, hepsi PASS.

Yeni kod dosyalarının derlendiği ve koştuğu da gözlendi:

```bash
cc -std=c11 -Wall -Wextra -o /tmp/banker sample_data/isletim-sistemleri/bankers_algorithm.c && /tmp/banker
cc -std=c11 -Wall -Wextra -o /tmp/pipe_shell sample_data/isletim-sistemleri/pipe_shell.c && /tmp/pipe_shell
python3 sample_data/isletim-sistemleri/thread_pool.py       # toplam=5050
python3 sample_data/isletim-sistemleri/page_replacement.py
python3 sample_data/isletim-sistemleri/reader_writer.py
```

`bankers_algorithm.c` çıktısı ders kitabı örneğiyle uyuşuyor: başlangıç durumu güvenli
(sıra P1 P3 P4 P0 P2), P1'in `(1,0,2)` isteği karşılanıyor, P4'ün `(3,3,0)` isteği
kaynak yetersizliğinden bekletiliyor, P0'ın `(0,2,0)` isteği sistemi güvensiz yapacağı
için reddediliyor.
