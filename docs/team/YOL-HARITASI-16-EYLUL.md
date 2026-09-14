# DOU-Synapse — Tam Yol Haritası (14 → 16 Eylül 2026)

Yazılış: 14 Eylül 2026, 22:30. Kaynaklar: danışmanın 27 Temmuz proje öneri e-postası,
Graduation toplantı notları (Notion), 14 Eylül akşam planı (artifact "16 Eylül Planı") ve
bu gece ölçülen depo durumu. Her satır ya ölçülmüş bir durumdur ya da saatli bir iştir;
ölçülmeyen şey "ölçülmedi" diye yazılır.

## 0. Danışmanın istekleri ↔ sistemin gerçek durumu

Kural: "VAR" yalnız çalıştırılmış kanıtla yazıldı. Boşluk kodları (G1–G4) §2'de saatlendi.

### E-posta §2 — Temel modüller

| # | İstek | Durum | Kanıt / boşluk |
|---|---|---|---|
| A1 | Kapsam ve kaynak yönetimi: PDF/Markdown/kod yüklenir, yalnız bunlar bilgi tabanıdır | **VAR** | FR-004–008; demo dersi COME302'de 5 belge (pptx, pdf, md), 22 parça; kapsam dışı ret bu gece gerçek modelle ölçüldü |
| A2 | Sokratik mod (cevabı verme, ipucuyla çözdür) | **VAR** | Sunucu tarafı kademeli durum makinesi; ısrarda ilerlemiyor (bu gece gerçek modelle doğrulandı); kod/çözüm sızıntısı fail-closed |
| A2′ | Sınav prova modu (süreli, puanla, detaylı geri bildirim) | **VAR** | `exam`/`practice` modları, süre, rubrikli açık uçlu değerlendirme, sonda geri bildirim |
| A2″ | "Hoca modelin davranışını ayarlar" | **VAR** | Ders başına yapay zekâ politikası (`PUT /courses/{id}/ai-policy`, geçmişiyle) |
| A3 | Soru havuzu üretici: çoktan seçmeli / açık uçlu + cevap anahtarı | **VAR** | `POST …/questions/generate`; tipler `mcq`, `open`, `code_trace`, `bug_hunt`; üretilen her soru TASLAK, eğitmen onayı olmadan öğrenci görmez |
| B1 | İnteraktif soru çözümü: cevap ders notlarına göre değerlendirilir, eksik söylenir | **VAR** | Practice modunda anında geri bildirim; açık uçluda rubrik + kaynak parçalar |
| B2 | "Neden yanlış?" — çelişen slayt bölümü gösterilir | **VAR** | Yanlış çeldirici için kaynak bölümü kartı (`grounded-wrong-feedback.spec.ts`) |
| B3 | Kod / senaryo inceleme (çıktı analizi, hata buldurma) | **VAR (statik)** | `code_trace` ve `bug_hunt` soru tipleri; kod hiçbir koşulda çalıştırılmaz (bilinçli, belgede gerekçeli) |
| C1 | Müfredat dışını nazikçe reddet | **VAR** | `out_of_scope` ayrı durum; "İtalya'nın başkenti…" bu gece gerçek modelle reddedildi |
| C2 | Dayandığı slayt/sayfa numarasını göstermek zorunda | **VAR** | Atıf dosya+sayfa/slayt taşır, model metninden değil parça meta verisinden üretilir ve getirilen kümeye karşı mekanik doğrulanır |

### E-posta §3 — Teknoloji yığını (öneri listesi; "farklı geliştirmeler yapabilirsiniz")

| Öneri | Bizde | Not |
|---|---|---|
| FastAPI / Flask | **FastAPI** | ✓ |
| LangChain / LlamaIndex | **Kullanılmıyor** | Bilinçli: kendi retrieval→kanıt eşiği→LLM→guardrail hattı; gerekçe `ARCHITECTURE.md`. Gereksinim v2 §2.2'de bir paragrafla açıklanır |
| OpenAI API / Groq API (veya Ollama) | **Groq üzerinden OpenAI'ın `gpt-oss-120b` modeli**, yedek `qwen3.6-27b` | İkisini de karşılar; Gemini ikinci sağlayıcı olarak eklenecek (anahtar Murat'ta). OpenAI API sağlayıcısı kodda yok — sunum sonrası |
| FAISS / ChromaDB / Qdrant | **PostgreSQL 16 + pgvector** | Tek veritabanı = RLS ile ders izolasyonu aynı işlemde; ayrı vektör deposunda bu kanıt verilemezdi |
| Streamlit / Gradio, gerekiyorsa Next.js/React | **Next.js 16** | E-posta açıkça izin veriyor |

### E-posta §5 — Beklenen çıktılar

| Çıktı | Durum | Boşluk |
|---|---|---|
| 1. Çalışır web platformu | **VAR** (yerel: API 8020 + web 3020, gerçek Groq) | Canlı URL yok; danışman toplantıda yerel çalışmayı kabul edip video istedi. Bulut = sunum sonrası |
| 2. Örnek ders materyali paketi + başarı testi raporu | **Paket VAR** (`sample_data/isletim-sistemleri`) · **Rapor KISMİ** | `docs/test-report.md` ve `evaluation/results` retrieval ölçümleri sahte sağlayıcı/hash ile; **gerçek modelle holdout koşusu hiç yapılmadı** → **G1** |
| 3. Eğitmen ve öğrenci kılavuzu | **VAR** (`docs/instructor-guide.md`, `docs/student-guide.md`) | Görselleri eski siyah raylı kabuk → **G4** |

### Toplantı notları

| # | Danışman | Durum | Boşluk |
|---|---|---|---|
| M1 | Yapay zekânın rolünü net tanımla: Exam Mentor / Class Assistant / CourseGPT | **KISMİ** | Tanımlar `docs/RAD_PROMPTLARI.md`'de; arayüzde "Ders Koçu" (öğrenci) ve "Eğitmen Asistanı" kimlikleri var. Rol · yüzey · kanıt sütunlu **tablo belgede yok** → madde 13 (bu gece, gereksinim v2 içinde) |
| M2 | Çoklu soru biçimi (test / klasik / kısa cevap); çerçeve önce kurulsun | **VAR** | Eğitmen tip + biçim + konu seçer; `example_questions` (≤5) verirse üslup taklit edilir; blueprint ile hedef×zorluk×tip matrisi. "Kısa cevap": `open` tipinin `answer_format` alt türü — `essay` (rubrikle LLM değerlendirir) / `short_answer` (`accepted_answers` ile deterministik eşleşir); beşinci soru tipi değil, değerlendirme mantığı (FR-036) |
| M3 | Müfredat/kitaptan örnek soru üret, cevabı vermeden yönlendir | **VAR** | Üretim yüklenen materyalden; kitap yüklenirse aynı hat. Yönlendirme = Sokratik mod |
| M4 | "Çok geniş düşünüyorsunuz; yapay zekâ nerede değer katıyor?" | Sunum işi | Madde 19: akış üç rol üzerinden anlatılır, özellik listesi değil |
| M5 | Gereksinim analizi belgesi: fonksiyonel gereksinimler + kullanım senaryoları + arayüzler; NFR gerekmez | **EKSİK** | Mevcut belge 6 Ağustos tarihli, kullanım senaryosu ve arayüz bölümü yok → madde 12 (bu gece taslak) |
| M6 | 10–15 dk adım adım video | **EKSİK** | Senaryo `docs/team/VIDEO_SENARYOSU.md` hazır → madde 15 |
| M7 | Kitap/kaynak bağlantıları | **KISMİ** | `docs/references.md` iskeleti bu gece yazıldı (yalnız gerçek atıflar); kitap satırları "Murat ekleyecek" |

### Bu gece sorulan üç şey

- **Supabase:** danışmanın e-postasında ve toplantıda "Supabase" **geçmiyor**; Supabase bizim kimlik/depolama barındırma tercihimizdi. Yerel Postgres + `DEV_AUTH` + yerel depolama aynı işlevi veriyor, sunuma bu hâliyle giriliyor. Doğru karar.
- **Gerçek LLM:** zorunlu — danışmanın istediği her davranış model davranışı. Demo `run_api.sh` ile **gerçek Groq**'ta; sahte sağlayıcı yalnız test/CI ve çevrimdışı yedekte (`DOU_DEMO_OFFLINE=1`).
- **Gemini / OpenAI:** Gemini **ekle** (ikinci sağlayıcı; `GEMINI_API_KEY` + `LLM_FALLBACK_MODEL=gemini/…`). OpenAI **ekleme** (kod tanımıyor; gpt-oss zaten Groq'ta; "bedava OpenAI API" siteleri resmî değil).

## 1. 14 Eylül gecesi — durum (22:30)

| # | İş | Durum |
|---|---|---|
| 1 | Disk ≥15 GB | ✓ 22 GB (APFS anlık görüntüleri macOS'un kendisi temizledi; bun önbelleği silindi) |
| 2 | Groq anahtarı | ✓ `.env`'de; gerçek cevap 5,7 sn, kaynaklı; ret ve Sokratik doğrulandı |
| 3 | `gh auth login` | ✓ muratcan-ates (repo, workflow) |
| 4 | CI Storage RLS kırmızısı | ✓ kök neden: test koruması Docker servis konteynerinin `172.x` adresini reddediyordu; düzeltme `292bf8e` main'de, CI koşuyor |
| 5 | `025-campus-ui` incelemesi | ⏳ 15 Eylül |
| 6 | P2 al, P1 uzlaştır | ⏳ 15 Eylül |
| 7 | Demo gerçek modelle + önbellek | ✓ gerçek model · ⏳ `fill_answer_cache.py` COME302 ile doluyor (Groq kota beklemeleriyle) |
| 8 | Playwright tarayıcıları | ✓ gerek yok: yerelde sistem Chrome (`channel: "chrome"`); indirme CDN'de kopuyordu. Süit CI'da koşacak (yerel koşu CI'nın sahiplenme kurulumuna bağlı) |
| B1 | `/docs` sayfası yeni kabuk | ✓ 16efd97 (açık/koyu ekran görüntüsüyle) |
| B3 | Kaynak listesi iskeleti | ✓ `docs/references.md` |
| B7 | Yedek betiği + Plan C | ✓ `scripts/demo/backup_demo.sh` (prova: bkz. gece raporu) · runbook Plan C docker'sız yeniden yazıldı · `DOU_DEMO_OFFLINE=1` |
| B2 | Gereksinim belgesi v2 | ⏳ bu gece taslak |
| B9 | Gece raporu | ⏳ gece sonunda |

### GPT'nin yeni tasarımı gelince TAŞINACAK iki düzeltme

Tasarım turu GPT'de (`025-campus-ui`); yeni kabuk geldiğinde aşağıdaki iki kusur
yeniden doğabilir, çünkü ikisi de kabuk/ızgara yapısına bağlı. Commit `7ab347c`.

1. **Izgara `minmax(0,1fr)` + `min-w-0`.** Sohbet sayfasında sade `1fr` kullanılırsa
   telefon genişliğinde sütun içeriğin min-content genişliğine şişer ve sayfa yana
   kayar (ölçüldü: kapsayıcı 343px, sütun 550,578px). Yeni tasarımda her ızgara
   çocuğunda `min-w-0` olmalı.
2. **Mobil gezinme çubuğu DOM'da içerikten ÖNCE.** `fixed` konumlandığı için
   görünüm etkilenmez; sonda durursa klavye kullanıcısı ana menüye ancak bütün
   sayfayı geçerek ulaşır (30 sekmede ulaşılamadı → 4 sekme).

3. **Görünen etiket metni değişmez.** Kabuk turu sınav sayacını `2/3`'ten
   `2 / 3`'e çevirdi ve `flows.spec.ts:704` kırıldı. Tasarım turunun kendi kuralı
   "rol/etiket/href/test-id değişmez"di; yeni tasarımda da geçerli.

Doğrulama betiği hazır: `scratchpad/dogrula375.mjs` — 375x812 koyu temada
taşmayı ve sekme sayısını ölçer. Yeni tasarım geldiğinde önce bunu koştur.

## 2. 15 Eylül — saatli sıra

Kural: her blok bitmeden sonrakine geçilmez; bloğu aşan iş sunum sonrasına yazılır.

| Saat | # | İş | Kim | Çıkış ölçütü |
|---|---|---|---|---|
| 09:00–09:30 | 4/9 | CI sonucunu oku: `api` yeşilse e2e ilk kez koştu; kırmızı spec'leri düzelt | Claude | `gh run view` tüm işler yeşil ya da kırmızı listesi + neden |
| 09:30–10:30 | 10 · G4 | README'deki 8 görsel + kılavuz görselleri yeni kabukla yenile (demo yığını, gerçek veri) | Claude | `docs/images/*.png` tarihleri 15 Eyl; README'de eski siyah ray kalmadı |
| 10:30–11:30 | 12 · 13 | Gereksinim v2'yi hocaya gönderilecek hale getir: kullanım senaryoları, arayüzler, rol tablosu, §8 ölçülen sayılar | Claude taslak → Murat okur, gönderir | Danışmanın 3 isteği de belgede (FR, use case, arayüz); NFR kısa not |
| 11:30–12:30 | 6 · 5 | Dallar: P2 (temiz) al; P1'in 3 çakışmasını uzlaştır; `025-campus-ui` inceleme raporu | Claude · merge kararı Murat | main'de P2; P1 raporu; 025 için "al/alma" gerekçesi |
| 13:30–15:00 | **G1** | Gerçek modelle değerlendirme koşusu: `EVAL_LLM_PROVIDER=gemini` + anahtar → holdout (Recall@5/8, atıf hassasiyeti, kapsam dışı ret) → `docs/test-report.md` | Murat anahtar · Claude koşu | Rapor "gerçek model" etiketli sayılarla; zaman aşarsa sahte-sağlayıcı ölçümü **etiketli** kalır, uydurulmaz |
| 15:00–15:30 | 11 | Yönetişimi yeşile çevir (r1 kayıtları karantina) | Murat onayı → Claude | "Govern reviewed AI diff" yeşil ya da ENGEL notu |
| 15:30–16:30 | 15 | Video: `VIDEO_SENARYOSU.md` ile 10–15 dk, önbellek dolu, gerçek Groq | Murat çeker | OneDrive linki danışmana |
| 16:30–17:30 | 18 · 17 | Kronometreli prova (rol geçişi, kaynak kartı, kapsam dışı, ipucu merdiveni) + yedek klasörünü USB/iCloud'a | Murat + Claude | Süre tablosu; yedek makine dışında |
| Akşam | 19 · 20 | Sunum akışı + çökme senaryosu (hangi dakikada ne; internet giderse Plan C); salon/donanım/bildirim | Murat | Tek sayfalık akış |

### CI uçtan uca: 9 kırmızıdan 3'ü düzeltildi, 6'sı düzenek boşluğu (sunum sonrası)

İlk gerçek koşu (run 34884025385): **72 geçti, 9 düştü, 1 kararsız.** Kök nedenler:

| Testler | Kök neden | Durum |
|---|---|---|
| `portal.spec:531` · `chat-history-deletion:82` · `flows.spec:686` | Kabuk turunun gerçek regresyonları: mobil DOM sırası, ızgara `1fr`, etiket biçimi | **Düzeltildi** (7ab347c, b06736a), gerçek tarayıcıyla ölçüldü |
| `grounded-wrong-feedback` (3) | API `LLM_SIMULATE_GROUNDED_FEEDBACK=1` ile başlatılmalı | **not-run**: koşucu bu bayrağı hiç kurmuyor |
| `provider-fallback` (3) | API `LLM_SIMULATE_RATE_LIMIT=1` ile başlatılmalı | **not-run**: aynı boşluk |

Bu 6 test bu düzenekte **hiç koşabilir durumda değildi**; testlerin kendi başlıkları da
"ayrı API süreci … L1 normal/simülasyon seçimini ayrı bağlamalıdır" diyor.
`run_owned_e2e.py:72` tek API süreci açıyor ve iki bayrağı da kurmuyor. İki bayrak aynı
anda açılamaz: bayrak açıkken `provider_fallback.py:196` **her** üretim çağrısında 429
simüle eder, yani diğer bütün sohbet testleri düşerdi. Çözüm fazlı koşu: ana faz + iki
simülasyon fazı, her biri kendi API süreciyle. `run_owned_e2e.py` hassas yol DEĞİL
(dossier gerekmez), `ci.yml` hassas (R2) — bu yüzden fazlama koşucunun içinde yapılmalı,
`ci.yml`e dokunmadan. Denetim muhasebesi (`ownedApiPid`, makbuz sayımı) tek API sürecine
göre yazıldığı için değişiklik dikkat ister; sunum öncesi riskli, sunum sonrasına alındı.

Ertelenen (sunum sonrası, v2): CI e2e fazlı koşu (yukarıdaki 6 test) · Supabase Auth/Storage + canlı URL · OpenAI sağlayıcısı ·
kod çalıştırma (hayır, bilinçli) · LMS/LTI · öğrenci self-enroll · gerçek zamanlı işbirliği.

## 3. 16 Eylül — sunum günü kontrol listesi

- [ ] `sh scripts/demo/run_api.sh` → logda `sağlayıcı: Groq`; `curl :8020/health/ready` 200
- [ ] `sh scripts/demo/run_web.sh` → `:3020` giriş sayfası; Ayşe Hoca / Burak Yılmaz kartları
- [ ] `answer_cache` dolu: `psql -d dou_demo -Atc "select count(*) from answer_cache"` ≥ senaryo sorusu sayısı
- [ ] Plan C provası yapıldı: Wi-Fi kapalı, senaryo sorusu kopyala-yapıştır → cevap önbellekten
- [ ] Telefon hotspot bağlı ve şarjda; laptop adaptörde; bildirimler susturuldu; çözünürlük ayarlı
- [ ] Yedek klasörü (`dou_demo.bundle` + `api.env` + OKU.md) USB'de
- [ ] Sunum akışı tek sayfa masada; üç rol (Ders Asistanı / Sınav Mentoru / Soru Üretici) sırasıyla
