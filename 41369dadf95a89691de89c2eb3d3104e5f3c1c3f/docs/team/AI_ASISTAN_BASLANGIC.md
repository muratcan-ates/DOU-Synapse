# AI Asistanı Başlangıç Promptu — Herkes İçin

> Bu dosya **rol fark etmeksizin herkes içindir**. Claude / ChatGPT / Gemini ile yeni bir sohbet
> açtığında ilk mesaj olarak aşağıdaki "YAPIŞTIRILACAK PROMPT" bloğunu olduğu gibi yapıştır,
> içindeki **"Benim rolüm"** satırını doldur, sonra kendi rol brief'inle devam et.
>
> Amaç: asistanın projeyi baştan doğru anlaması. Bunu atlarsan asistan LangChain önerir,
> `course_id`'yi istemciden alır, abstention'ı hata sanır ve saatlerce yanlış yönde üretir.
>
> İş listesi: [`specs/001-course-assistant-mvp/tasks.md`](../../specs/001-course-assistant-mvp/tasks.md) ·
> Sahiplik matrisi: [`00_TAKIM_KOORDINASYON.md`](00_TAKIM_KOORDINASYON.md)

---

## YAPIŞTIRILACAK PROMPT (Başlıyor)

Merhaba. **DOU-Synapse (kod adı: CourseGPT)** adlı bir bitirme projesinde çalışıyorum ve senden
bu proje üzerinde yardım isteyeceğim. Önce projeyi tanı, sonra sana rolümü ve ilk görevimi
vereceğim.

### Proje nedir

Doğuş Üniversitesi **COME 491/492 bitirme projesi**. Eğitmenin yüklediği ders materyalleriyle
**sınırlandırılmış** bir RAG ders asistanı: öğrenci soru sorar, sistem cevabı **yalnızca o dersin
yüklenmiş materyallerinden** üretir ve her cevabın yanında **dosya adı + sayfa/slayt numarası**
gösterir. Materyalde karşılığı olmayan soru nazikçe reddedilir; internet bilgisi veya modelin
genel bilgisi hiçbir cevaba karışmaz.

Bunun üstünde dört mod var:
- **Sohbet (qa)** — kaynaklı soru-cevap
- **Sokratik mod** — cevap verilmez; kademeli, kaynaklı ipuçlarıyla çözdürülür
- **Sınav provası** — süreli, ipucu kapalı, tek deneme; sonunda puan + "neden yanlış?" analizi
- **Kod/senaryo inceleme** — `code_trace` (çıktıyı tahmin et) ve `bug_hunt` (hatayı bul);
  kod hiçbir koşulda çalıştırılmaz

**Repo:** https://github.com/muratcan-ates/DOU-Synapse
**Lokal yol:** `~/code/DOU-Synapse` (iCloud senkronlu klasörlere ASLA konmaz — Python projelerini bozar)
**Teslim:** 24 Ağustos 2026
**Sert kapılar:** 10 Ağustos = dikey RAG demosu (uçtan uca kaynaklı cevap) · 17 Ağustos = özellik dondurma

### Mevcut durum (bitmiş işler)

Bunlar **çalışıyor ve test edilmiş** durumda — sıfırdan yazmayı önerme, üzerine inşa et:

- Kimlik doğrulama (Supabase JWT + yerelde `Bearer dev:<uuid>` dev-auth), ders ve üyelik API'si
- Dosya yükleme + doğrulama (uzantı beyaz listesi + boyut + magic byte) + iş kuyruğu tablosu
- Parser'lar: PDF (PyMuPDF, sayfa bazlı), PPTX (python-pptx, slayt bazlı), Markdown, düz metin, kod
- Chunking — **bir chunk iki sayfayı birleştirmez**, sayfa/slayt metadata'sı korunur
- Embedding (`intfloat/multilingual-e5-large`, 1024 boyut; testlerde deterministik `hashing` sağlayıcı)
- pgvector kaydı + **iki katmanlı izolasyon** (uygulama katmanı üyelik kontrolü + PostgreSQL RLS)
- Next.js frontend: giriş, ders listesi, materyal yükleme + durum, sekmeler, üye yönetimi,
  sınav ve Sokratik ekranlarının tasarım önizlemeleri
- **68 pytest testi geçiyor**, ruff temiz, CI kurulu

**Henüz yazılmamış** (kalan işlerin tamamı `specs/001-course-assistant-mvp/tasks.md`'de T001-T060
olarak listeli): retrieval hattı (dense + FTS + RRF), LLM üretimi, guardrail zinciri, chat API'si,
Sokratik state machine, soru üretimi ve sınav, mastery/analitik, eval harness, deploy, belgeler.

### Teknoloji yığını (sürümleriyle — bunlar sabit)

**Backend**
- Python **3.12** (`>=3.12,<3.13` olarak sabitli — onnxruntime/fastembed uyumu)
- FastAPI ≥0.115 · uvicorn ≥0.32 · Pydantic ≥2.9 + pydantic-settings ≥2.6
- SQLAlchemy **2.0.36+ async** · psycopg **3.2** (`postgresql+psycopg://`) · pgvector ≥0.3.6
- fastembed ≥0.5 · PyMuPDF ≥1.24 · python-pptx ≥1.0 · PyJWT ≥2.9
- **uv** (Python paket yöneticisi — `pip`/`poetry`/`conda` değil): `uv venv`, `uv pip install`, `uv run`
- ruff (lint + format) · pytest ≥8.3 + pytest-asyncio (`asyncio_mode = "auto"`) · mypy

**Veritabanı**
- PostgreSQL **16** (sabit) + pgvector (yerelde v0.8.0, kaynaktan derlenir) + `unaccent` + `pgcrypto`
- Şema düz SQL migration'larla yönetilir (`supabase/migrations/`), ORM'den **üretilmez**
- Üretimde Supabase (PostgreSQL + Auth + Storage) — tek veritabanı, ayrı vektör DB yok

**Frontend**
- Next.js **16.3.0** (App Router) · React **19.2.8** · TypeScript 5
- Tailwind CSS **v4** (`@tailwindcss/postcss`) — v3 değil, `tailwind.config.js` yok
- Paket yöneticisi **Bun 1.3.14** (`bun install`, `bun run dev` — npm/yarn/pnpm değil)

**LLM ve deploy (yazılacak)**
- LiteLLM Router: Groq (Llama) → Gemini Flash **otomatik failover** + exponential backoff
- Vercel (web) + Azure Container Apps (api + worker, tek imaj iki servis) + Supabase

**Bilinçli olarak KULLANILMAYANLAR** — bunları önerme:
- **LangChain / LlamaIndex / LangGraph** — düz Python servis kodu + açık state machine kullanıyoruz
  (debug şeffaflığı için; bu karar `ARCHITECTURE.md`'de yazılı)
- Ayrı vektör veritabanı (Qdrant / FAISS / Chroma) — pgvector yeterli, ikinci depo yetki sızıntısı riski
- Redis + Celery, Kafka, K8s, mikroservis — iş kuyruğu Postgres tablosunda (`FOR UPDATE SKIP LOCKED`)
- Semantik önbellek — yalnızca birebir eşleşmeli (exact-match) demo önbelleği var
- Fine-tuning, GraphRAG, multi-agent, OCR, kod çalıştırma sandbox'ı

### Proje yapısı (gerçek dizinler)

```
DOU-Synapse/
├── apps/
│   ├── api/                              # FastAPI backend (Python 3.12, uv)
│   │   ├── app/
│   │   │   ├── api/                      # courses.py · documents.py · deps.py · health.py
│   │   │   ├── core/                     # config.py · db.py · security.py · errors.py · logging.py
│   │   │   ├── models/                   # base.py · core.py (SQLAlchemy)
│   │   │   ├── schemas/                  # course.py · document.py (Pydantic)
│   │   │   ├── modules/
│   │   │   │   ├── ingestion/            # validation · parsers · storage · chunking · embedding · pipeline  [DOLU]
│   │   │   │   ├── retrieval/            # [BOŞ — Faz A]
│   │   │   │   ├── generation/           # [BOŞ — Faz B]
│   │   │   │   ├── guardrails/           # [BOŞ — Faz B]
│   │   │   │   ├── assessment/           # [BOŞ — Faz D]
│   │   │   │   └── mastery/              # [BOŞ — Faz E]
│   │   │   ├── main.py                   # create_app + router kayıtları
│   │   │   └── worker.py                 # in-process drain() + `python -m app.worker` döngüsü (HTTP /drain T049'da)
│   │   ├── tests/                        # conftest.py + 68 geçen test
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   └── web/                              # Next.js 16 + Bun
│       ├── app/
│       │   ├── page.tsx                  # giriş (şimdilik dev-token kartları)
│       │   ├── layout.tsx · globals.css  # tasarım token'ları DESIGN.md'den
│       │   └── courses/
│       │       ├── page.tsx              # ders listesi
│       │       └── [courseId]/
│       │           ├── page.tsx          # materyal yükleme + durum + sekmeler
│       │           ├── chat/page.tsx     # sohbet (mock)
│       │           ├── exam/page.tsx     # sınav (mock)
│       │           └── members/page.tsx  # üye yönetimi
│       ├── components/                   # app-shell · course-nav · source-card · socratic-ladder · ui
│       ├── lib/                          # api.ts · types.ts
│       ├── AGENTS.md                     # ÖNEMLİ — aşağıdaki Next.js notuna bak
│       └── package.json
├── supabase/
│   ├── migrations/0001_core_schema.sql   # DONDURULMUŞ — değiştirilmez
│   ├── local_dev_setup.sql               # yalnız yerel: dou_app/dou_worker rollerine LOGIN
│   ├── seed_demo.sql                     # demo kullanıcıları (sabit UUID'ler)
│   └── tests/rls_isolation.sql           # RLS canlılık kanıtı
├── specs/001-course-assistant-mvp/
│   ├── spec.md                           # FR-001..FR-035, kullanıcı hikâyeleri, SC-001..SC-011
│   ├── plan.md · data-model.md · research.md · quickstart.md
│   ├── tasks.md                          # T001-T060, TAM dosya yollarıyla — TEK iş listesi
│   └── contracts/openapi.json            # dondurulmuş API sözleşmesi
├── .specify/memory/constitution.md       # 10 ilkelik anayasa (bağlayıcı)
├── docs/team/                            # 00_TAKIM_KOORDINASYON.md · bu dosya
├── .github/workflows/ci.yml              # ruff + pytest + RLS izolasyon kanıtı (+ mypy bilgilendirici, continue-on-error)
├── PLAN.md · ARCHITECTURE.md · DESIGN.md · README.md
├── docker-compose.yml                    # çevrimdışı fallback yığını
└── .env.example                          # gerçek .env asla commit edilmez

# Henüz oluşturulmamış (görevlerle gelecek):
#   evaluation/{gold_set,results,faithfulness}/ · sample_data/ · docs/{test-report,runbook,*-guide}.md
```

### Takımdaki roller

| # | Rol | Sorumluluk alanı |
|---|-----|------------------|
| **R1** | Backend / RAG | retrieval, generation, chat API'si, LLM failover |
| **R2** | Guardrail & QA | citation validator, sızıntı filtresi, sanitize, Sokratik state machine, güvenlik testleri |
| **R3** | Assessment & Analytics | soru üretimi, değerlendirme, sınav uçları, mastery, analitik |
| **R4** | Frontend | `apps/web` tamamı (Muratcan) |
| **R5** | Data & Eval | örnek materyal paketi, gold set, eval harness, test raporu, kullanım kılavuzları |

**Benim rolüm: [BURAYA YAZ — ör. "R2, Guardrail & QA"]**

Her dosyanın **tek sahibi** vardır. Sahibi olmadığım bir dosyayı düzenlemem; sahibine söylerim.
Sahiplik matrisi `docs/team/00_TAKIM_KOORDINASYON.md`'de. Bana bir değişiklik önerirken
"bu dosya senin rolüne mi ait?" diye sor; emin değilsen matrise bakmamı iste.

### Pazarlık edilmeyen ilkeler (anayasadan — 10 ilkenin en sık ihlal edilenleri)

1. **Kaynak yoksa cevap yok.** Öğrenciye giden hiçbir akademik cevap (Sokratik ipuçları dahil)
   retrieval'dan gelmemiş bir kaynağa dayanamaz. Atıflar `chunk_id` **set-membership** kontrolünden
   geçer; geçerli atıf kalmazsa cevap **hiç gösterilmez**. Dosya adı ve sayfa numarası model
   metninden değil, chunk metadata'sından üretilir.
2. **İki katmanlı izolasyon.** Ders verisi hem uygulama katmanında (sunucu tarafı üyelik
   doğrulaması) hem PostgreSQL RLS'te izole edilir. API, tablo sahibi olmayan ve BYPASSRLS
   taşımayan `dou_app` rolüyle bağlanır; testler de aynı rolle koşar.
3. **Fail-closed varsayılanlar.** Belirsizlikte sistem kapanır, açılmaz: kanıt eşiği aşılamazsa
   abstention; pedagojik filtre ihlali regen'le çözülmezse şablon ipucuna düşülür; embedding
   üretilemezse belge `completed` işaretlenmez; `DEV_AUTH` üretimde açılamaz.
4. **Ölçmeden iddia etme.** "Hızlandı", "iyileşti", "dayanıklı" demeden önce ölç. Eşikler
   kalibrasyon setiyle ayarlanır, metrikler holdout sette raporlanır; ikisi **asla** karışmaz.
5. **Türkçe birinci sınıftır.** Kullanıcıya dönen her metin (hata mesajları dahil) anlaşılır
   Türkçedir; backend tek hata zarfı üretir (`{error:{code,message}}`), frontend kendi hata
   metnini uydurmaz. `text-transform: uppercase` yasaktır (i/İ bozulur). UI metninde em dash yok.
6. **Doğrulama bitmeden "bitti" yok.** Test yeşil + lint temiz + davranış gerçek ortamda
   (tarayıcıda veya gerçek API çağrısıyla) gözlenmiş olmadan görev kapanmaz.
7. **Git disiplini.** Her görev kendi branch'i + conventional commit'i + PR'ı ile kapanır.
   Commit mesajı İngilizce, gövdesi "ne"yi değil "neden"i anlatır.
   **`Co-Authored-By` veya "Generated with" satırı ASLA eklenmez** — sen yazmış olsan bile
   commit yalnız benim adıma gider. Commit mesajı önerirken bu satırları koyma.

### Sorgu pipeline'ı ve guardrail zinciri (sıralama bir güvenlik sınırıdır)

```
1. AuthZ        JWT doğrula → user_id → üyelik kontrolü
                (course_id İSTEMCİDEN ASLA güvenilmez; backend belirler)
2. Retrieval    dense top-20 (pgvector) ∥ FTS top-20 → RRF (k=60) → top-8
                her sorguda zorunlu WHERE course_id = :authorized_course_id
3. Evidence     en iyi sonuç eşik altındaysa → ABSTAIN (fail-closed)
   gate
4. Generation   bağlam <retrieved_context><source id page> XML etiketleriyle VERİ olarak
                işaretlenir (indirect injection önlemi); çıktı Pydantic şemasına valide, 1 retry
5. Citation     cevaptaki chunk_id'ler ⊆ retrieve edilen küme mi? (deterministik set-membership)
   validator    Değilse temizle; geçerli citation kalmadıysa CEVAP GÖSTERİLMEZ
6. Pedagojik    (Sokratik/sınav modunda) kod bloğu + doğrudan-çözüm dedektörü → ihlalde 1 regen;
   filtre       yine ihlalse ŞABLON İPUCUNA DÜŞ (deterministik son durak)
7. Sanitize     Markdown/HTML temizliği (XSS) → gönder + event log
```

Cevap şeması:

```json
{
  "status": "answered | insufficient_context | out_of_scope",
  "mode": "qa | socratic | exam",
  "answer": "...",
  "citations": [{"chunk_id": "…", "claim": "…"}],
  "hints": [{"text": "…", "chunk_id": "…"}]
}
```

Sokratik state machine (backend'de tutulur):
`DIAGNOSE → NUDGE → CONCEPT_HINT → SIMILAR_EXAMPLE → EXPLAIN_WITH_SOURCE`
Öğrenci denemesi olmadan kademe ilerlemez. `exam` modunda ipucu tamamen kapalıdır.

### Yerel kurulum gerçekleri (bunlar doğrulanmış — tahmin etme)

```bash
# PostgreSQL 16 keg-only: PATH'e eklenmeli
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"

# pgvector KAYNAKTAN derlenir (brew paketi pg17/18'e karşı derlenir, 16'ya kurulmaz)
make PG_CONFIG=/opt/homebrew/opt/postgresql@16/bin/pg_config
make install PG_CONFIG=/opt/homebrew/opt/postgresql@16/bin/pg_config

# Veritabanı — SIRA ÖNEMLİ
createdb dou_synapse
psql -d dou_synapse -f supabase/migrations/0001_core_schema.sql
psql -d dou_synapse -f supabase/local_dev_setup.sql     # yalnız yerel: rollere LOGIN
psql -d dou_synapse -f supabase/seed_demo.sql           # demo kullanıcıları

# Backend
cd apps/api
uv venv --python 3.12
uv pip install -e ".[dev]"
cp ../../.env.example .env        # varsayılanlar yerelle birebir eşleşir, değiştirme
uv run uvicorn app.main:app --reload      # localhost:8000

# Kalite kapıları (PR öncesi üçü de yeşil olmalı)
uv run pytest
uv run ruff check .
uv run ruff format --check .

# Frontend
cd apps/web
bun install
bun run dev                        # localhost:3000, API'yi localhost:8000'de bekler
```

Demo girişi: giriş sayfasındaki iki kart — **Ayşe Hoca** (eğitmen) ve **Burak Yılmaz** (öğrenci).
Tıklayınca tarayıcıya `Bearer dev:<uuid>` token'ı yazılır; backend bunu `DEV_AUTH_ENABLED=true`
iken kabul eder.

### Next.js 16 ve Tailwind v4 hakkında önemli not

**Bu, senin eğitim verindeki Next.js değil.** Next.js 16 ve Tailwind v4, eski sürümlerden
kırıcı biçimde farklı: API'ler, dosya yapısı ve konvansiyonlar değişmiş olabilir. Frontend
tarafında tek satır kod yazmadan önce:

1. `apps/web/AGENTS.md` dosyasını oku (bunu `next dev` kendisi yazıyor),
2. `apps/web/node_modules/next/dist/docs/` altındaki ilgili rehberi oku,
3. Tailwind v4'te `tailwind.config.js` yok — kurulum `app/globals.css` içindeki
   `@import "tailwindcss";` satırıyla yapılır, PostCSS eklentisi `@tailwindcss/postcss`'tir,
   ve renk/tipografi token'ları aynı dosyada CSS değişkeni olarak tanımlıdır (kaynağı
   `DESIGN.md`). Bileşen içinde ham hex yazılmaz; token yoksa önce `DESIGN.md`'ye eklenir.

Hafızandan Next.js 13/14/15 veya Tailwind v3 deseni yazma; önce dokümana bak. Emin değilsen
"bu sürümde nasıl olduğunu doğrulamam gerek" de ve bana dosyayı okumamı söyle.

### Dil tercihi

Sohbet, açıklamalar ve belgeler **Türkçe**. Kod, değişken/fonksiyon adları, commit mesajları,
branch adları ve dosya adları **İngilizce**. Kullanıcıya (öğrenci/eğitmen) dönen arayüz ve
hata metinleri **Türkçe**.

### Bana nasıl yardım etmeni istiyorum

- Kod bloklarını kopyala-yapıştır çalışacak biçimde ver; ne yaptığını Türkçe açıkla.
- Bir dosya yolu söylediğimde önce dosyayı okumamı iste, varsayımla yazma.
- Emin olmadığın bir şeyi "muhtemelen böyledir" diye yazma; **"bunu doğrulamamız gerek"** de.
- Kapsam genişletme önerme. `tasks.md`'de olmayan bir iş aklına gelirse söyle ama kendiliğinden
  ekleme — 17 Ağustos'ta özellik dondurma var.
- Bir görevi bitirdiğimizde bana çıktı kontrol listesi ver (testler, lint, tarayıcıda gözlem).

### Bu projeyi anladığını göstermek için şu 5 soruya cevap ver

1. **Hangi embedding modelini kullanıyoruz, boyutu kaç, ve neden bge-m3 değil?** İlk tercih
   neydi, hangi somut kısıt yüzünden değişti, ve bge-m3 şu an projede hangi rolde?
2. **`course_id` neden yetki sayılmaz?** İstemci istekte bir ders kimliği gönderdiğinde
   backend ne yapar, ve izolasyonun ikinci katmanı nedir? Yeni bir uç yazarken hangi
   bağımlılığı kullanmam gerekir?
3. **Abstention (yetersiz kaynak / kapsam dışı ret) neden hata gibi gösterilmez?** HTTP olarak
   ne döner, cevap şemasındaki hangi `status` değerleriyle ifade edilir, ve arayüzde neden
   kırmızı kullanılmaz?
4. **Citation validator "geçerli atıf kalmadı" derse ne olur, ve bu kontrol neyi garanti
   ETMEZ?** Dosya adı ile sayfa numarası nereden üretilir — model metninden mi, başka bir
   yerden mi?
5. **Kalibrasyon seti ile holdout seti neden asla karışmaz?** Hangisiyle eşik ayarlanır,
   hangisinde metrik raporlanır, ve rapora her sonucun yanına hangi dürüstlük notu düşülür?

Cevaplarını verdikten sonra sana rolümü ve ilk görevimin numarasını (`tasks.md`'deki T00X)
söyleyeceğim; oradan devam edeceğiz.

## YAPIŞTIRILACAK PROMPT (Bitti)

---

## Nasıl kullanırsın

1. Asistanında (Claude / ChatGPT / Gemini) **yeni bir sohbet** aç. Uzayan sohbette asistan
   bağlamı kaybeder — her yeni görev için yeni sohbet daha iyidir.
2. Yukarıdaki "YAPIŞTIRILACAK PROMPT" bloğunu **başlık satırları dahil** kopyalayıp yapıştır.
3. **"Benim rolüm:"** satırını doldurmayı unutma. Boş bırakırsan asistan sana başkasının
   dosyalarını düzenletir.
4. Asistan 5 doğrulama sorusunu cevaplasın. **Cevaplar tutmuyorsa bağlamı anlamamıştır** —
   yanlış cevapladığı maddeyi düzelt, ilgili belgeyi (`ARCHITECTURE.md`, `spec.md`,
   `.specify/memory/constitution.md`) ona ver ve tekrar sor. Yanlış anlamış bir asistanla
   koda başlama.
5. Sonra kendi görevini ver: **`tasks.md`'deki görev numarası + tam dosya yolu + kabul kriteri.**
   Örnek: *"T005'i yapacağım: `apps/api/app/modules/retrieval/fusion.py` — Reciprocal Rank
   Fusion, k=60, T003 ve T004'ün sonuç listelerini birleştirip top-8 döndürecek."*
6. Kod geldikçe **kendin çalıştır, çıktıyı yapıştır.** Asistanın "çalışması gerekir" demesi
   kanıt değildir (Anayasa VIII).
7. Bitince kalite kapılarını koştur: `uv run pytest` + `uv run ruff check .` +
   `uv run ruff format --check .`. Üçü de yeşil değilse PR açma.

**İpuçları**

- Hata aldığında **komutun tamamını + hata çıktısının tamamını** yapıştır; özetleme.
- Asistan büyük bir dosyayı bir seferde yazmak isterse durdur: önce iskelet + testler, sonra
  gövde. Küçük parçalar daha kolay doğrulanır.
- "Bu dosyanın sahibi kim?" diye kendine sor. Emin değilsen `00_TAKIM_KOORDINASYON.md` §2.
- 30 dakikadan fazla takılırsan gruba yaz. Asistanla saatlerce döngüye girme.

---

## Önemli uyarılar

### AI'ya ASLA verilmeyecekler

Bunlar sohbete yapıştırılırsa üçüncü taraf bir servise gitmiş olur ve geri alınamaz:

- **Gerçek `.env` içeriği.** Yalnız `.env.example` paylaşılır (değerleri boş şablondur).
- **LLM API anahtarları** (Groq, Gemini, `EVAL_LLM_API_KEY`) — hiçbir biçimde, "sadece test
  edeceğiz" diye bile.
- **Supabase service-role anahtarı**, `SUPABASE_JWT_SECRET`, veritabanı üretim parolaları.
- **Gerçek öğrenci verisi**: isim, e-posta, öğrenci numarası, gerçek sohbet kayıtları, gerçek
  sınav cevapları. Test verisi gerekiyorsa uydurma veri kullan.
- **Üretim bağlantı dizeleri** ve `pg_dump` çıktıları.

Bir asistan bu bilgilerden birini isterse: **verme.** Hata ayıklama için anahtar gerekiyorsa
değeri değil, davranışı anlat ("401 dönüyor", "Groq 429 veriyor").

### AI'ya BIRAKILMAYACAK işler

Bunları asistan taslak olarak yazabilir ama **insan gözüyle satır satır incelenmeden merge
edilmez** — projenin güvenlik ve dürüstlük iddiaları bunlara dayanıyor:

- **RLS politikaları ve migration'lar.** Sessizce yanlış yazılmış bir policy testleri sahte
  yeşil yakar. `supabase/migrations/0001_core_schema.sql` zaten dondurulmuştur.
- **Yetkilendirme kodu ve `course_id` filtreleri.** `app/core/security.py` ve `app/api/deps.py`
  değişecekse Murat onaylar.
- **Gold set cevapları** (`evaluation/gold_set/`). Doğru kaynak eşlemesini AI üretirse sistemi
  kendi ürettiği cevaba karşı ölçmüş oluruz — jürinin ilk soracağı şey budur.
- **Rapora yazılacak metrikler.** Hiçbir sayı asistanın tahmininden gelmez; ölçüm koşulur,
  çıktı `evaluation/results/` altına yazılır (Anayasa III).
- **API anahtarı / secret kullanan kod yolları.**

### Diğer

- **Asistan LangChain / LlamaIndex / LangGraph önerirse reddet.** Bu bilinçli bir karar
  (`ARCHITECTURE.md` §1); asistanların varsayılan RAG refleksi bu kütüphaneleri getirmektir.
- **Asistan `pip install` derse düzelt:** bu projede `uv pip install`. Frontend'de `npm install`
  değil `bun install`.
- **Asistan Next.js/Tailwind kodu yazarken hafızasına güvenme.** `apps/web/AGENTS.md` +
  `node_modules/next/dist/docs/` okunmadan yazılan kod büyük ihtimalle eski sürüme aittir.
- **Commit mesajlarında `Co-Authored-By` / "Generated with Claude" satırlarını sil.** Asistanlar
  bunu alışkanlıkla ekler; Anayasa IX bunu yasaklar, contributors listesinde yalnız takım
  üyeleri görünür.
- **Kapsam dışına çıkma.** Asistan "şunu da ekleyelim" derse `tasks.md`'ye bak. Listede yoksa
  önce gruba sor — PLAN'da bilerek kesilmiş bir şeyi geri getiriyor olabilirsin.
- **Abstention'ı "düzeltmeye" çalışma.** Sistem cevap vermiyorsa bu çoğu zaman bug değil,
  fail-closed tasarımın çalışmasıdır. Eşik kalibrasyonu ayrı bir görevdir (T043).

---

## Son söz

Bu projenin ayırt edici iddiası hız veya özellik sayısı değil: **kaynağı doğrulanmadan hiçbir
cevabın gösterilmemesi.** Asistan sana daha "akıllı" görünen bir kısayol önerdiğinde ölçüt hep
aynı: *bu değişiklik, kaynaksız bir cevabın öğrenciye ulaşmasını mümkün kılıyor mu?* Cevap
"belki" ise, yapma.

Kanıt yoksa cevap yok.
