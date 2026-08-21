# DOU-SYNAPSE MASTER HANDOFF — 5 Ağustos 2026

> Bu belge, 4-5 Ağustos 2026'daki iki günlük yoğun geliştirme oturumunun tam devir
> teslimidir. Projeye yeni katılan biri (Eren, Metehan) yalnız bu belgeyi ve kendi rol
> brief'ini okuyarak çalışmaya başlayabilir. Her iddia repoda doğrulanabilir durumdadır.

**Repo:** https://github.com/muratcan-ates/DOU-Synapse · lokal: `~/code/DOU-Synapse`
**Teslim:** 24 Ağustos 2026 · **Hoca:** Yasemin Karagül · **Ders:** COME 491/492
**Toplantı:** Perşembe 20:00

---

## 1. Proje tek paragrafta

**DOU-Synapse (CourseGPT):** Eğitmenin yüklediği ders materyaliyle **sınırlı**, her cevabı
**sayfa/slayt kaynağıyla** veren, Sokratik öğretim + sınav provası + konu bazlı ilerleme
takibi sunan RAG ders asistanı. Tezimiz tek cümle: **kaynak yoksa cevap yoktur.** Jüri
anlatısı: Harvard CS50 Duck değerlendirmesinde cevapların %22'sinde kod sızdırıldığı
raporlandı; biz sızıntı oranımızı kendi test setimizde ölçüp raporluyoruz — garanti değil,
ölçüm.

---

## 2. Ne oldu — iki günün özeti

| Zaman | İş |
|---|---|
| 4 Ağu öğlen | Hocanın CourseGPT taslağı + 9 derin araştırma raporu (ChatGPT/Gemini) sentezlendi → 8 haftalık plan yazıldı |
| 4 Ağu akşam | "3 haftamız var" düzeltmesi → plan 15 iş gününe indirildi; **4 mercekli adversaryal denetimden** geçirildi (takvim hatası dahil 30+ bulgu düzeltildi) → `PLAN.md` + `ARCHITECTURE.md` push |
| 4 Ağu gece | **Backend G1-G4 tek gecede yazıldı**: şema+RLS, ders/üyelik API, ingestion (PDF/PPTX/MD/kod), embedding. 68 test |
| 5 Ağu akşam | **Frontend**: Next.js 16 + tasarım sistemi (taste-skill & minimalist-ui uygulanmış) + 6 ekran; **spec-kit benimsendi**: anayasa + `specs/001` (10 ajanlık workflow üretti, 3 denetçi doğruladı) + 60 görevlik `tasks.md`; takım koordinasyon belgesi + rol brief'leri |

Commit zinciri: `4f3bd55` plan → `5f12b76` API iskeleti → `e143fd2` ingestion →
`8d902f0` embedding → `9929787` frontend → `f11e779` frontend genişletme →
`3cc4faa` spec-kit. Contributors listesinde yalnız Muratcan görünür (bilinçli — Anayasa IX).

---

## 3. Şu an ÇALIŞAN şeyler (hepsi doğrulanmış)

- **Ders/üyelik API'si** — ders açma, e-postayla üye ekleme/çıkarma; üye-olmayan 404 alır
  (varlık sızdırılmaz)
- **İki katmanlı izolasyon, kanıtlı** — uygulama katmanı (course_id istemciden yetki
  sayılmaz) + PostgreSQL RLS. Testler `dou_app` rolüyle koşar (superuser değil — yoksa RLS
  sessizce atlanır ve test sahte yeşil yanar). `supabase/tests/rls_isolation.sql` politikayı
  bilerek bozup testin KIRMIZI yanabildiğini kanıtlar; **CI bunu her koşuda yapar**
- **Ingestion hattı** — magic-byte doğrulama (uzantısı değiştirilen .exe reddedilir), UUID
  depolama anahtarı (path traversal ölü), sayfa/slayt/satır-aralığı metadata'sını KORUYAN
  parser'lar, sayfa sınırını asla birleştirmeyen chunking, hash'le kopya reddi
- **Embedding** — chunk'lar 1024-boyutlu vektörle pgvector'de; worker ayrı süreç
  (`python -m app.worker`); testlerde model indirmeyen deterministik hashing sağlayıcısı.
  Not: lokalde upload sonrası API içi drain de denenir ama garantili değildir — belge
  "Sırada"da kalırsa ayrı terminalde worker'ı çalıştırın (tek doğru yol budur)
- **Frontend (localhost:3000)** — giriş (Ayşe Hoca / Burak Yılmaz demo kartları), ders
  listesi+oluşturma, materyal yükleme + 2sn polling'li durum rozetleri, chunk önizleme,
  sekmeler (Materyaller/Asistan/Sınav/Katılımcılar), üye yönetimi, belge silme; sohbet +
  sınav ekranları **"tasarım önizlemesi" etiketli** (motor Faz C/D'de bağlanacak). Koyu tema
  ve mobil 375px doğrulandı
- **92 test + CI** (ruff, mypy, pytest, RLS kanıtı — pgvector/pg16 imajında).
  **8 Ağu düzeltmesi:** CI ilk commit'ten beri hiç koşmamıştı (`hashFiles` job
  düzeyinde geçersiz → `startup_failure`). Düzeltildi; ilk yeşil koşu 8 Ağustos

## 4. Henüz OLMAYAN şeyler (kimse var sanmasın)

- **Retrieval/RAG hattı yok** — `modules/retrieval|generation|guardrails` dizinleri
  BOŞ (9 Ağu itibarıyla beş şeritli paralel geliştirmede; bkz. §10). Sohbet ve sınav
  ekranlarındaki içerik örnek veridir
- **LLM entegrasyonu yok** — `litellm` bağımlılığı ve `config.py` ayarları 9 Ağustos'ta
  önden eklendi, gövde Şerit 2'de yazılıyor
- **Bulut deploy YAPILMADI** — PLAN G1'de "hello world deploy" yazıyordu ama fiilen
  yapılmadı; ilk gerçek deploy T049-T050. Canlı URL yok, her şey lokal
- **Supabase Auth yok** — giriş `dev:<uuid>` token'ıyla (yalnız DEV_AUTH_ENABLED iken);
  gerçek auth T023
- **Gold set yok** — `evaluation/` dizini boş; T041 Şerit 5'te. Ölçüm altyapısı
  olmadan spec'teki hiçbir sayı raporlanamaz (Anayasa III)

> **Not (9 Ağu):** §3 ve §4, 5 Ağustos'ta yazıldı. O tarihten sonra eklenenler:
> `sample_data/` paketi, ölçme şeması (`0004`), mastery servisi, konu uçları, soru
> havuzu ve ilerleme ekranları (tasarım önizlemesi), CI düzeltmesi, arayüz refactor'u.
> Güncel durum için `README.md` "Yapılanlar / Yapılacaklar" bölümüne bak.

---

## 5. Kritik kararlar ve NEDENLERİ (tartışma yeniden açılmasın)

| Karar | Neden |
|---|---|
| pgvector, ayrı vektör DB yok | İkinci depo = senkron + ders-arası sızıntı riski; ölçeğimizde gereksiz |
| **LangChain/LlamaIndex/LangGraph YOK** | İnce pipeline düz Python'la şeffaf; Sokratik mod basit state machine |
| Embedding: **multilingual-e5-large** (bge-m3 DEĞİL) | fastembed'in dense kataloğunda bge-m3 yok; aynı 1024 boyut, şema değişmedi. bge-m3 T045'te A/B adayı. **E5 `query:`/`passage:` öneki zorunlu ve fastembed bunu EKLEMEZ** — bizim kodda, testle sabit (`test_embedding_prefix.py`) |
| `EMBEDDING_PROVIDER` ingest-zamanı kararı | Değiştirmek = tüm korpus yeniden embed; runtime yedeği DEĞİL |
| FTS: `simple` + unaccent | Köklendirme `fork()`, `O(n log n)` gibi teknik tokenları bozar. **FTS altyapısı 0001'de ZATEN VAR** (`chunks.fts` + GIN) — yeniden inşa etme |
| Worker ayrı süreç + `FOR UPDATE SKIP LOCKED` | Redis/Celery yok; API içi arka plan tetiği güvenilir çıkmadı. Bulutta HTTP `/drain` (T049) |
| Ders oluşturma + üye ekleme SECURITY DEFINER fonksiyonlarında | `INSERT..RETURNING` SELECT politikasını tetikler; bootstrap politikayla ifade edilemedi (yaşanmış, çözülmüş) |
| Kırmızı #C50C1F yalnız 3 yerde; koyu temada #FF6B78 | Ham kırmızı koyu zeminde 2.87:1 — okunmaz (ölçüldü). Kırmızı ASLA hata rengi değil |
| Abstention hata gibi GÖSTERİLMEZ | "Materyalde yok" bir başarıdır; ürünün varlık sebebi |
| Sınav: süre/soru sayısı config sabiti; süre dolunca cevapsız BOŞ sayılır; öğrenci derse yalnız eğitmen davetiyle katılır | Spec'te karara bağlandı, yeniden tartışılmaz (spec.md FR-003/FR-017) |
| uppercase + em dash UI'da YASAK | Türkçe i/İ dönüşümü bozulur; DESIGN.md kuralı |

## 6. Yaşanmış tuzaklar (zaman kaybetme)

1. **Superuser'la test koşma** — RLS sessizce atlanır, izolasyon testin hiçbir şey kanıtlamaz.
   `conftest.py` zaten `dou_app` ile bağlanıyor; bozma.
2. **brew'daki pgvector pg17/18 için** — pg16'ya KAYNAKTAN derlenir (quickstart'ta komut).
3. **Python 3.12 pinli** — onnxruntime/fastembed 3.13+ desteklemiyor; `uv venv --python 3.12`.
4. **Postgres 16 keg-only** — `PATH`'e `/opt/homebrew/opt/postgresql@16/bin` eklenmeli.
5. **`.test` TLD'li e-postalar** — email-validator reddeder; test verilerinde `@dogus.edu.tr`.
6. **`.gitignore`'da çıplak `models/`** yazmak `app/models/` Python paketini yutar (yaşandı;
   şimdi `/model_cache/` + `*.onnx`).
7. **Next.js 16 + Tailwind v4 eğitim verinizden farklı** — AI asistanına
   `apps/web/AGENTS.md`'yi okutun.
8. **Migration numaraları:** 0002 = auth bridge (ayrılmış), 0003 = chat, 0004 = assessment.

---

## 7. Beş dakikada ayağa kaldırma

Tam anlatım: `specs/001-course-assistant-mvp/quickstart.md`. Özet:

```bash
git clone https://github.com/muratcan-ates/DOU-Synapse.git ~/code/DOU-Synapse
cd ~/code/DOU-Synapse
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
createdb dou_synapse
for f in supabase/migrations/*.sql; do psql -v ON_ERROR_STOP=1 -d dou_synapse -f "$f"; done
psql -d dou_synapse -f supabase/local_dev_setup.sql
psql -d dou_synapse -f supabase/seed_demo.sql

cd apps/api && uv venv --python 3.12 && uv pip install -e ".[dev]"
cp ../../.env.example .env          # varsayılanlar yeterli
uv run pytest -q                    # 68 test yeşil olmalı
uv run uvicorn app.main:app --port 8000   # + ayrı terminalde: uv run python -m app.worker

cd ../web && bun install && bun run dev      # localhost:3000
# Girişte "Ayşe Hoca" (eğitmen) veya "Burak Yılmaz" (öğrenci) kartına tıkla
```

---

## 8. Belge haritası — ne nerede

| Belge | Ne işe yarar |
|---|---|
| `specs/001-course-assistant-mvp/tasks.md` | **TEK iş listesi**: 60 görev, 8 faz, tam dosya yolları |
| `docs/team/00_TAKIM_KOORDINASYON.md` | Dosya sahipliği matrisi, sıcak dosya protokolü, git akışı |
| `docs/team/0X_*_BRIEF.md` | Rol brief'leri (AI'ya yapıştırılabilir) |
| `docs/team/AI_ASISTAN_BASLANGIC.md` | Her rolün AI asistanına vereceği ortak başlangıç promptu |
| `specs/001-course-assistant-mvp/spec.md` | 35 FR, kullanıcı hikâyeleri, hoca eşleme tablosu |
| `ARCHITECTURE.md` | Teknik kararlar + gerekçeler + elenen alternatifler |
| `PLAN.md` | Takvim, kapılar (G5: 10 Ağu dikey demo, G10: 17 Ağu dondurma), riskler |
| `DESIGN.md` | Tasarım token'ları — arayüzün tek otoritesi |
| `.specify/memory/constitution.md` | 10 pazarlıksız ilke |
| `specs/.../quickstart.md` · `data-model.md` · `research.md` · `contracts/` | Kurulum · şema · karar gerekçeleri · OpenAPI |

## 9. Rol dağılımı ve ilk görevler

| Kişi | Roller | İlk görevleri | Not |
|---|---|---|---|
| **Eren** | R1+R2 (Backend/RAG + Guardrail) | T003→T004→T005→**T006** (retrieval), sonra T008-T016 | **T006 herkesi bloklar — takımın önceliği.** T010 (cevap şeması) bitince gruba haber |
| **Metehan** | R3+R5 (Assessment + Eval) | **T041** (gold set — bugün başlar, günde 5-8 soru) + **T002** (sample_data) + T024 (migration) | T041 ve T002 hiçbir şeyi beklemez |
| **Muratcan** | R4 + lead | T021-T022 (chat gerçek veriye), sıcak dosya hakemliği, PR review | Faz G: T048-T053 Eren'de, T051 Eren (R2 şapkası), T054-T055 Eren+Murat ortak |

İlk gün her iki arkadaş için: (1) GitHub kullanıcı adını Murat'a at → collaborator ekler,
(2) §7'deki kurulumu yap, 68 testi yeşil gör, (3) kendi brief'ini oku, (4) AI asistanına
`AI_ASISTAN_BASLANGIC.md`'yi yapıştır, (5) ilk görevinin branch'ini aç.

**30 dakika kuralı:** Bir hatada 30 dakikadan fazla takılırsan gruba yaz.

---

## 10. Paralel geliştirme (9 Ağustos'tan itibaren)

Cevap üretim hattı takvime sığmadığı için iş beş şeride bölündü ve şeritler
paralel çalışıyor. Sıcak dosyalar (`main.py`, `config.py`, `pyproject.toml`)
oturumlar başlamadan önce tek seferde hallededildi; modüller arası tipler
`apps/api/app/contracts.py`'de sabitlendi ve o dosyayı yalnız lider değiştirir.

Başlamadan önce **`docs/team/parallel/00_OKU_ONCE.md`** okunur, sonra kendi
şerit belgesi:

| Şerit | Alan | Belge |
|---|---|---|
| 1 | Retrieval hattı | `parallel/01_RETRIEVAL.md` |
| 2 | Generation + guardrails | `parallel/02_GENERATION.md` |
| 3 | Chat ucu + Sokratik | `parallel/03_CHAT_SOKRATIK.md` |
| 4 | Soru üretimi + sınav | `parallel/04_SORU_SINAV.md` |
| 5 | Analitik + değerlendirme | `parallel/05_ANALITIK_EVAL.md` |
| — | Frontend, RLS kanıtı, CI | lider |

Kural: **sahiplendiğin dosya listesinin dışına çıkma.** Listende olmayan bir
dosyaya ihtiyacın varsa gruba yaz, kendin düzenleme.

## 11. "Bitti" tanımına eklenen kalem (Anayasa XI)

Bir iş, çalışıyor olması yetmez; **modüler ve tekrarsız** da olmalıdır:

- Aynı davranış üçüncü kez yazılıyorsa ortak modüle çıkarılır
- Kural, ton ve eşik gibi ürün kararları tek sözlükte yaşar
- Etkin görünüp iş yapmayan buton veya uç kusurdur
- Ölü kod, ölü export ve ulaşılamayan dal commit'te temizlenir
- Gereksiz iş (durdurulmayan polling, her etkileşimde tam sayfa yenileme, aynı
  veriyi iki kez çekme) kusur sayılır

Gerekçe 9 Ağustos denetiminde görüldü: altı arayüz sayfası aynı üç deseni
tekrarlıyordu ve tekrarlar birbirinden ayrışmıştı — biri hatayı temizlemiyor,
biri sessizce yutuyor, biri her silmede tam sayfa yeniliyordu. Hiçbiri mevcut on
ilkeyi ihlal etmiyordu, çünkü kod sağlığı yazılı bir kural değildi. Artık kural.
