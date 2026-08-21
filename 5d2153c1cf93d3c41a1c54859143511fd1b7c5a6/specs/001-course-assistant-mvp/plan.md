# Implementation Plan: Course Assistant MVP (CourseGPT)

**Branch**: `main` (iş şu an `main` üzerinde; Anayasa IX gereği takım çalışması başladığında
issue → branch → PR → 1 review akışına geçilir) | **Date**: 2026-08-05 |
**Spec**: [spec.md](spec.md) — 7 kullanıcı hikâyesi, FR-001..FR-035, hoca gereksinim
eşleme tablosu ve ölçülmüş başarı kriterleri (bu planla aynı turda üretildi).

**Input**: Hocanın (Yasemin Karagül, COME 491/492) CourseGPT taslağındaki zorunlu
gereksinimler + [PLAN.md](../../PLAN.md) P0 kapsam tablosu +
[contracts/openapi.json](contracts/openapi.json) (dondurulmuş G1-G4 sözleşmesi).

## Summary

Öğretmenin yüklediği ders materyallerini (PDF / PPTX / Markdown / kod) ders bazında izole
eden; öğrencinin sorularına **yalnızca bu materyallerden, dosya adı + sayfa/slayt
kaynağıyla** cevap veren; cevabı göstermeden önce **fail-closed guardrail zincirinden**
geçiren (citation set-membership doğrulama + kanıt eşiği + kod/çözüm sızıntı filtresi);
Sokratik çalışma, sınav provası, kod inceleme (`code_trace` / `bug_hunt`) ve konu bazlı
Mastery-Lite takibi sunan web tabanlı öğretim asistanı.

Teknik yaklaşım: Next.js (Vercel) + FastAPI (Azure Container Apps) + Supabase
(PostgreSQL + pgvector + Auth + Storage, RLS ile ikinci izolasyon katmanı) + hybrid
retrieval (dense pgvector + Postgres FTS + RRF) + LiteLLM Router (Groq → Gemini otomatik
failover). Gerekçeli karar tablosu için [ARCHITECTURE.md](../../ARCHITECTURE.md) §1.

**Mevcut durum (2026-08-05):** Backend G1-G4 tamamlandı — kurs/üyelik API'si, upload +
asenkron ingestion (job tablosu + `/drain` worker), chunking + embedding + pgvector
kaydı çalışıyor; frontend iskeleti ve demo yolu ekranlarının ilk hali var. Sırada:
retrieval + RAG hattı, guardrail zinciri, Sokratik motor, sınav modu, mastery, eval, deploy.

## Technical Context

Aşağıdaki sürümler repodan doğrulanmıştır
([apps/api/pyproject.toml](../../apps/api/pyproject.toml),
[apps/web/package.json](../../apps/web/package.json)).

**Language/Version**:
- Backend: Python `>=3.12,<3.13` (pin gerekçesi pyproject'te: onnxruntime/fastembed uyumu)
- Frontend: TypeScript `^5`, Node tipleri `^20`; paket yöneticisi Bun `1.3.14`

**Primary Dependencies**:
- API: FastAPI `>=0.115`, Uvicorn `>=0.32`, Pydantic `>=2.9` (+ pydantic-settings),
  SQLAlchemy[asyncio] `>=2.0.36`, psycopg[binary,pool] `>=3.2`, pgvector `>=0.3.6`,
  PyJWT[crypto] `>=2.9`, httpx `>=0.27`, fastembed `>=0.5`
  (`intfloat/multilingual-e5-large`, 1024 boyut, imaja gömülü), PyMuPDF `>=1.24`,
  python-pptx `>=1.0`
- Web: Next.js `16.3.0`, React `19.2.8`, Tailwind CSS `^4` (@tailwindcss/postcss)
- Dev/QA: pytest `>=8.3` (asyncio_mode=auto), ruff `>=0.7`, mypy `>=1.13` (strict-ish:
  `disallow_untyped_defs`)
- Henüz eklenmemiş, planda olan: **LiteLLM** (generation modülüyle birlikte gelecek;
  `app/modules/generation/` şu an boş). ARCHITECTURE.md'de shadcn/ui hedeflenir;
  `package.json`'da yok. KARAR: el yazımı bileşen seti (`apps/web/components/ui.tsx`,
  DESIGN.md token'larına tabi) yeterlidir ve kanonik yaklaşımdır; shadcn/ui ancak somut
  bir bileşen ihtiyacı el yazımıyla pahalıya gelirse, plan revizyonuyla eklenir.

**Storage**: Supabase PostgreSQL + pgvector (tek veritabanı; ayrı vektör deposu bilinçli
olarak yok) + Supabase Storage (private bucket). Migration'lar düz SQL:
`supabase/migrations/0001_core_schema.sql`. (Not: `apps/api/README.md` migration dosyasını
`0001_init.sql` diye anıyor — gerçek ad `0001_core_schema.sql`; README düzeltilmeli.)

**Testing**: pytest (+pytest-asyncio) — `apps/api/tests/` (courses, documents, ingestion,
embedding, **embedding prefix davranışı** `test_embedding_prefix.py`, log redaction);
SQL düzeyi RLS izolasyon testi `supabase/tests/rls_isolation.sql`; CI:
`.github/workflows/ci.yml`.

**Target Platform**: Web — Vercel (frontend) + Azure Container Apps (api + worker) +
Supabase (managed Postgres/Auth/Storage); lokal/fallback `docker-compose.yml`.

**Project Type**: Web uygulaması (monorepo: `apps/web` + `apps/api` + `supabase`).

**Performance Goals**: Uçtan uca cevap p95 < 10 sn (**sıcak replika, sorgu yolu** —
PLAN.md §5); cold-start ayrıca ölçülür (G14); demo/prova günleri minReplicas=1.

**Constraints**: İnternet bilgisi karıştırılmaz (yalnızca ders materyali); her yanıtta
kaynak zorunlu (ipuçları dahil); fail-closed guardrail; upload ≤ 20 MB + magic byte
kontrolü; maliyet hedefi ~$0-15/ay; Supabase free-tier pause riskine karşı keep-alive.

**Scale/Scope**: Bitirme projesi ölçeği — 1 örnek ders paketi (İşletim Sistemleri),
4 kişilik takım, ≥50 soruluk gold set, tek eğitmen + sınıf senaryosu. 1M+ chunk ölçeği
bilinçli olarak v2'ye bırakıldı (ARCHITECTURE.md §9).

## Mimari Kararlar (özet + çapraz referans)

Ayrıntı ve elenen alternatifler [ARCHITECTURE.md](../../ARCHITECTURE.md)'dedir; burada
yalnızca karar + tek cümlelik gerekçe:

| Karar | Gerekçe | Detay |
|---|---|---|
| Tek veritabanı: Supabase Postgres + pgvector | İkinci vektör deposu = senkron + yetki sızıntısı riski | ARCHITECTURE.md §1 |
| Embedding: multilingual-e5-large (1024), imaja gömülü | bge-m3 fastembed dense kataloğunda yok; e5 tek bağımlılıkla çok dilli; runtime'da HF bağımlılığı istenmez | ARCHITECTURE.md §1 (e5 önek kuralı dahil) |
| Sparse: Postgres FTS `simple`+`unaccent` | Köklendirme `fork()`, `O(n log n)` gibi teknik tokenları bozar | ARCHITECTURE.md §1 |
| Füzyon: RRF (k=60) | Öğrenilmiş fusion için veri yok; skor normalizasyonu kırılgan | ARCHITECTURE.md §1 |
| LLM: LiteLLM Router, Groq→Gemini otomatik failover | Tek sağlayıcı kota/kesinti riski; failover kod seviyesinde, manuel değil | ARCHITECTURE.md §1 |
| Orkestrasyon: düz Python + açık state machine | LangChain vb. debug şeffaflığını düşürür; anayasada bilinçli dışarıda | ARCHITECTURE.md §1, Anayasa "Teknoloji Kilidi" |
| Arka plan işleri: Postgres job tablosu (`FOR UPDATE SKIP LOCKED`) + HTTP `/drain` worker | Sürekli poll, scale-to-zero ile çelişir; Redis+Celery kapsam şişirir | ARCHITECTURE.md §1, §4 |
| Guardrail zinciri sırası (AuthZ → Retrieval → Evidence gate → Generation → Citation validator → Pedagojik filtre → Sanitize) | Her adım bir güvenlik sınırı; sıralama kritik | ARCHITECTURE.md §5 |
| G1'den itibaren sürekli deploy | CORS/JWT/cold-start sürprizleri teslime 2 gün kala yaşanmasın | ARCHITECTURE.md §1 |

## Constitution Check

*GATE: Faz 0 araştırmasından önce geçilmeli; Faz 1 tasarımından sonra yeniden kontrol
edilir.* Kaynak: [.specify/memory/constitution.md](../../.specify/memory/constitution.md)
v1.0.0. İhlal yok; Complexity Tracking boş.

| # | İlke | Bu planın uyumu |
|---|---|---|
| I | Kaynak Yoksa Cevap Yok | Cevap şemasında her citation `chunk_id` taşır ve set-membership kontrolünden geçer; dosya adı + sayfa chunk metadata'sından üretilir; geçerli atıf kalmazsa cevap gösterilmez. Sokratik ipuçları da `chunk_id` taşır ve evidence-gate'ten geçer (ARCHITECTURE.md §5). Retrieval/guardrail modülleri bu sözleşmeyle yazılacak. |
| II | İki Katmanlı İzolasyon | Server-side `course_id` (istemciden asla yetki değil) + Postgres RLS; `chunks.course_id` denormalize, her sorguda zorunlu WHERE. RLS izolasyon testi repoda: `supabase/tests/rls_isolation.sql`; G13'te policy bilerek bozulup testin kırmızı yandığı kanıtlanır. |
| III | Ölçmeden İddia Etme | Gold set kalibrasyon (~15) / holdout ayrımı; eşikler kalibrasyonla ayarlanır, rapor yalnızca holdout metriklerini yayınlar; baseline vs hybrid anlamlılık kaydıyla; faithfulness manuel örneklem (20-30 cevap, 2 etiketleyici). Çalıştırılmayan deney için sonuç yazılmaz. |
| IV | Fail-Closed Varsayılanlar | Kanıt eşiği altında ABSTAIN; citation temizlenip boş kalırsa cevap yok; pedagojik filtre ihlalinde 1 regen, sonra şablon ipucu; embedding üretilemezse belge "completed" olmaz (mevcut ingestion pipeline'ında bu davranış var). DEV_AUTH üretimde reddedilir. |
| V | Türkçe Birinci Sınıftır | Backend tek hata zarfı üretir (`app/core/errors.py`); kullanıcı metinleri Türkçe; embedding (multilingual-e5) ve FTS (`simple`+`unaccent`) seçimleri TR/EN karışık materyale göre yapıldı ve testle sabitlendi (`tests/test_embedding_prefix.py`). |
| VI | Kapsam Kapıları | G5 (Pzt 10 Ağu) dikey dilim kapısı geçilmeden üstüne özellik inşa edilmez; G10 (Pzt 17 Ağu) özellik dondurma sonrası yalnız bayrak arkasında P1 (`ENABLE_RERANKER` vb.). Kapsam dışı listesi PLAN.md §2'de gerekçeli. |
| VII | Tasarım Sistemi Disiplini | Token kaynağı [DESIGN.md](../../DESIGN.md); bileşende ham hex yok; abstention hata gibi gösterilmez; durum renk+metin(+ikon) üçlüsüyle; koyu tema zorunlu. Frontend ekranları bu kurala göre yazılacak. |
| VIII | Doğrulama Bitmeden "Bitti" Yok | Her görev: pytest yeşil + ruff temiz + davranış gerçek ortamda (tarayıcı / gerçek API isteği) gözlenmiş olmadan kapanmaz; kapılar canlı URL'de geçilir. |
| IX | Git Disiplini | Conventional commit, gövde "neden" anlatır; Co-Authored-By / "Generated with" asla; repo `~/code/DOU-Synapse` (iCloud dışı); `.env` repoya girmez (`.env.example` var); `main` korumalı, takımla birlikte branch+PR+review. |
| X | Demo Hazırlığı | `answer_cache` (exact-match) P0; demo runbook A/B/C planı (canlı bulut / hotspot / offline Compose + cache) ARCHITECTURE.md §6'da; en az 1 tam offline prova; seed (`supabase/seed_demo.sql`) repoda; ham stack trace kullanıcıya gösterilmez. |

## Project Structure

### Documentation (this feature)

```text
specs/001-course-assistant-mvp/
├── plan.md              # Bu dosya
├── contracts/
│   └── openapi.json     # G2'de dondurulan sözleşme (courses, members, documents,
│                        # chunks, health uçları) — frontend mock'ları buna yazılır
├── checklists/          # (şu an boş)
└── tasks.md             # tek iş listesi kaynağı (60 görev, 8 faz — üretildi)
```

`spec.md`, `research.md`, `data-model.md`, `quickstart.md` bu dizinde üretilmiş durumda.
KARAR: uygulanmış şema için kanonik kaynak migration SQL'idir; `data-model.md` onun
okunabilir dökümü, ARCHITECTURE §3 ise planlanan tabloların kaynağıdır — data-model.md her
migration'la birlikte güncellenir.

### Source Code (repository root)

Mevcut ağaç (repodan doğrulandı); `(plan)` işaretli yollar PLAN/ARCHITECTURE'da taahhüt
edilmiş ama henüz oluşturulmamış dizinlerdir:

```text
DOU-Synapse/
├── apps/
│   ├── web/                        # Next.js 16 (App Router) + Tailwind v4, Bun
│   │   ├── app/                    # layout, ana sayfa, courses/[courseId]
│   │   ├── components/             # app-shell, course-nav, source-card, ui
│   │   └── lib/                    # api.ts (API istemcisi), types.ts
│   └── api/                        # FastAPI (Python 3.12)
│       ├── app/
│       │   ├── api/                # courses, documents, health, deps (authz)
│       │   ├── core/               # config, db, security (JWT), errors, logging
│       │   ├── models/             # SQLAlchemy tabloları
│       │   ├── schemas/            # Pydantic sözleşmeleri (course, document)
│       │   ├── modules/
│       │   │   ├── ingestion/      # validation, storage, parsers, chunking,
│       │   │   │                   # embedding, pipeline  (G3-G4'te dolduruldu)
│       │   │   ├── retrieval/      # (boş — sıradaki iş: dense + FTS + RRF)
│       │   │   ├── generation/     # (boş — LLM çağrısı, LiteLLM, şemalı çıktı)
│       │   │   ├── guardrails/     # (boş — citation validator, evidence gate,
│       │   │   │                   #  sızıntı filtresi)
│       │   │   ├── assessment/     # (boş — soru üretimi, puanlama, "neden yanlış")
│       │   │   └── mastery/        # (boş — EWMA performans göstergesi)
│       │   ├── main.py
│       │   └── worker.py           # /drain ile tetiklenen job consumer
│       ├── tests/                  # courses, documents, ingestion, embedding(+prefix),
│       │                           # log redaction
│       ├── storage/                # lokal geliştirme dosya deposu
│       └── Dockerfile
├── supabase/
│   ├── migrations/0001_core_schema.sql
│   ├── tests/rls_isolation.sql
│   ├── local_dev_setup.sql
│   └── seed_demo.sql
├── specs/001-course-assistant-mvp/ # bu özelliğin dokümantasyonu (yukarıda)
├── evaluation/                     # (plan) gold_set/ calibration.json, holdout.json,
│                                   # evaluate.py — G11-G12'de oluşacak
├── sample_data/                    # (plan) İşletim Sistemleri materyal paketi
├── docs/                           # (plan) test-report, instructor-guide,
│                                   # student-guide, runbook — G12'den itibaren
├── .github/workflows/ci.yml
├── docker-compose.yml              # lokal/fallback profili
├── .env.example
├── PLAN.md · ARCHITECTURE.md · DESIGN.md · README.md
└── .specify/                       # şablonlar + anayasa
```

**Structure Decision**: Monorepo web uygulaması — `apps/web` (Next.js) + `apps/api`
(FastAPI, modüler `app/modules/*` düzeni `apps/api/README.md`'deki modül haritasıyla
birebir) + `supabase` (SQL migration/RLS/seed). Bu yapı zaten kurulu ve G1-G4 işleri
içinde doğrulandı; yeni özellikler (retrieval, generation, guardrails, assessment,
mastery) mevcut boş modül dizinlerini doldurur, yeni üst düzey yapı gerektirmez.
`evaluation/`, `sample_data/`, `docs/` PLAN.md takvimindeki günlerinde açılacaktır.

## Takvim ve Kapılar (PLAN.md ile birebir)

Tam gün-gün tablo [PLAN.md §3](../../PLAN.md)'tedir; bu planın bağlandığı sert kapılar:

| Kapı | Tarih | Koşul |
|---|---|---|
| **Dikey dilim kapısı (G5)** | Pzt 10 Ağu 2026 | Uçtan uca kaynaklı cevap, gerçek materyalle, canlı URL'de. Geçilemezse OpenAI File Search yedeğine karar verilir; mimari büyütülmez. |
| **Özellik dondurma (G10)** | Pzt 17 Ağu 2026 (gün sonu) | Sonrasında yalnız bayrak arkasında P1 + düzeltme. |
| **Teslim (G15)** | Pzt 24 Ağu 2026 | Yalnızca kritik düzeltme, demo provası, sürüm etiketi, teslim. |

Ara hedefler (PLAN.md'den): G6 citation validator + eşik kalibrasyonu, G7 hybrid + Sokratik
state machine, G8 sızıntı filtresi + soru üretici, G9 sınav modu + Mastery-Lite backend,
G11-G12 gold set + otomatik eval + kılavuz taslakları, G13 güvenlik/negatif testler
(prod URL'de), G14 son deploy + demo cache + yedek/restore provası.
Hafta sonları plansız buffer'dır; P0 işi hafta sonuna yazılmaz.

## Complexity Tracking

> Yalnızca Constitution Check ihlali gerekçelendirilecekse doldurulur.

İhlal yok — tablo boş.
