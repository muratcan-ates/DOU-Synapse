# Implementation Plan: Production Sertleştirme

**Branch**: `002-production-hardening` | **Date**: 2026-08-09 | **Spec**: [spec.md](spec.md)

**Input**: [spec.md](spec.md) · [.specify/memory/constitution.md](../../.specify/memory/constitution.md) v1.1.0

---

## Summary

002, yeni bir ürün eklemiyor: **001'in ürettiği çalışan sistemi gerçek kullanıcıların önüne çıkarılabilir hale getiriyor** ve hocanın "önce sınavın çatısını kur" isteğini karşılıyor.

Teknik yaklaşım tek cümleyle: **mevcut desenleri uzat, yeni desen icat etme.** Kilit `deps.py`'nin kurulu yetki-katmanı desenini kullanır; yeni tablolar `0004`'ün RLS desenini birebir tekrarlar; hız sınırlayıcı kopyalanmaz, `core/`'a taşınır; embedding çağrıları `storage.py`'nin zaten uyguladığı `asyncio.to_thread` desenine geçer. Araştırma fazında elenen seçeneklerin çoğu "daha temiz görünen ama ikinci bir yerde aynı kuralı tekrarlayan" seçeneklerdi (Anayasa XI).

Dört göç dosyası, bağlayıcı sırayla: `0008` blueprint → `0009` ders politikası → `0010` işleme dayanıklılığı → `0011` sayfalama indeksleri.

**Araştırmanın düzelttiği iki şartname varsayımı:**

1. **`exams` diye bir tablo yok.** Şartnamenin "mevcut sınav tablosu" varsayımı yanlıştı. Var olan `exam_sessions` bir öğrencinin tek denemesidir, öğretmenin sınavı değil. Blueprint onun **yerini almaz, üstüne gelir**.
2. **Sekiz varlığın beşi tablo olacak, üçü kolonla çözülecek.** `question_learning_outcomes` → `questions.learning_outcome_id`; `rubrics` → mevcut `questions.payload.rubric` (rubrik zaten bağlı, eksik olan ölçüt kırılımı); `exam_publications` → `exam_versions` üzerindeki yayın pencere kolonları. Üç ayrı tablo açmak, üç ayrı RLS politikası ve üç ayrı tutarlılık kuralı demekti.

---

## Technical Context

**Language/Version**: Python 3.12 (onnxruntime uyumu için sabit) · TypeScript 5 / Next.js 16 (App Router) · Bun

**Primary Dependencies**: FastAPI · SQLAlchemy 2 (async) · pydantic-settings · LiteLLM (Groq→Gemini failover) · fastembed (multilingual-e5-large, 1024 boyut) · Tailwind v4 · Playwright

**Storage**: PostgreSQL 16 + pgvector (HNSW, `vector_cosine_ops`). Şema düz SQL göçleriyle yönetilir, ORM'den üretilmez; `app/models/*.py` şemayı **yansıtır**.

**Testing**: pytest (`apps/api/tests/`, `uv run pytest -q` → 825) · `bun test` (`apps/web/lib/` → 290) · Playwright (`apps/web/e2e/`, 28 vaka) · `supabase/tests/rls_isolation.sql` (98 iddia, mutasyonla doğrulanıyor) <!-- docs-check: backend.tests = 825 --><!-- docs-check: frontend.tests = 290 --><!-- docs-check: e2e.tests = 28 -->

**Target Platform**: Vercel (web) + Azure Container Apps (API/worker, aynı imaj farklı komut) + Supabase (Postgres/Auth/Storage). **Bulut adımları bugüne kadar KOŞULMADI** — T050 açık.

**Project Type**: Web uygulaması (monorepo: `apps/api` + `apps/web`)

**Performance Goals**: Sıcak sorgu yolu p95 < 10 sn (uçtan uca cevap). Yeni kısıt: **belge işlenirken sağlık yoklaması kesintisiz yanıt vermeli** (SC-014) — bugün vermiyor.

**Constraints**: Yeni veri deposu, yeni çatı, yeni sağlayıcı **yok** (Anayasa "Teknoloji Kilidi"). Tek istisna `@supabase/supabase-js` ve gerekçesi PLAN.md'ye yazılacak. ACA replika belleği 4 GiB; embedding modeli imaja gömülü (~2,1 GB).

**Scale/Scope**: Tek sınıf ölçeği (onlarca öğrenci, yüzlerce belge parçası). 11 kullanıcı hikâyesi · 62 fonksiyonel gereksinim · 4 göç dosyası · 7 yeni tablo.

---

## Constitution Check

*GATE: Faz 0 öncesi geçmeli, Faz 1 sonrası yeniden bakılmalı.*

| İlke | Kapı | Durum |
|---|---|---|
| **I. Kaynak Yoksa Cevap Yok** | 002 atıf zincirini zayıflatmıyor mu? | **GEÇTİ.** FR-132 (kaynak seti) zinciri daraltıyor, gevşetmiyor: belge filtresi `course_id` ile aynı yere, aynı biçimde giriyor. FR-118 (kaynak sürümü) atıfın bayatladığını görünür kılıyor. |
| **II. İki Katmanlı İzolasyon** | Her yeni tablo RLS taşıyor mu? | **GEÇTİ.** Yedi yeni tablonun hepsi denormalize `course_id NOT NULL` + `ENABLE`/`FORCE ROW LEVEL SECURITY` + `app.is_member()`/`app.is_instructor()` politikaları alıyor. Kilit sorgusu `user_id` yüklemini RLS'e bırakmıyor, açıkça yazıyor — çünkü `exam_sessions_self_read` eğitmene dersin tüm oturumlarını açıyor. |
| **III. Ölçmeden İddia Etme** | Ölçülmemiş sayı yazılıyor mu? | **GEÇTİ.** Üç yerde açıkça "ölçülmedi" kaydı düşüldü: kilidin ek SELECT maliyeti, `questions` üzerindeki dördüncü indeksin yazma maliyeti, ısıtmanın başlangıç gecikmesi. FR-182 + SC-009 zaten bu ilkenin uygulaması. |
| **IV. Fail-Closed** | Belirsizlikte açılan bir yol var mı? | **GEÇTİ — bir düzeltmeyle.** Veri modeli, token bütçesi kontrolünün öğrenci bağlamında `request_logs`'u okuyamayacağını ve **fail-open** olacağını yakaladı; `SECURITY DEFINER` yardımcısıyla kapatıldı. Kilit sorgusunun kırpma kuralı SQL'e yazılmıyor çünkü SQL tarafı gevşek kalırsa kilit fail-open olur. |
| **V. Türkçe Birinci Sınıf** | Kullanıcıya dönen metinler? | **GEÇTİ.** Kilit metni tek sabitte (`exam_state.py`). Soğuk başlangıç metni `runbook.md`'den **kopyalanmıyor** — oradaki cümle jüriye söylenen bir replik ve em dash içeriyor (Anayasa V yasaklıyor); ekran metni ayrı yazılıyor. Blueprint tutarsızlık mesajı hücre adıyla Türkçe — PostgreSQL kısıt ihlali bu cümleyi kuramaz, yani doğrulama uygulama katmanında. |
| **VI. Kapsam Kapıları** | Dondurma öncesi kapsam şişiyor mu? | **RİSKLİ — bilinçli.** Kullanıcı tam kapsamı seçti (9 Ağustos). Kapı, spec.md §Uygulama sırası'ndaki kesme noktasıdır: yetişmeyen iş **sıranın sonundan** kesilir. Bu bir plan revizyonudur, anayasa ihlali değil; gerekçesi yazılıdır. |
| **VII. Tasarım Sistemi** | Yeni ekranlar token kullanıyor mu? | **GEÇTİ.** Blueprint ve politika ekranları `DESIGN.md` token'larını kullanır; ham hex yazılmaz. Kilit durumu hata rengiyle değil, nötr/bilgi yüzeyiyle gösterilir (abstention kuralının aynısı). |
| **VIII. Doğrulama Bitmeden Bitti Yok** | Mutasyon kanıtı var mı? | **GEÇTİ.** FR-106 kilidin kaldırıldığında kırmızı yanmasını şart koşuyor; `test_exam_lock.py`'nin sekizinci iddiası bir **karşı kontroldür** (kilit devre dışıyken 200 + kaynaklı cevap). FR-224 için bu kanıt **zaten üretildi** (aşağıya bakınız). |
| **IX. Git Disiplini** | Her görev kendi commit'i? | **GEÇTİ.** `Co-Authored-By` yok. Dal `002-production-hardening`. |
| **X. Demo Hazırlığı** | Sistem her akşam gösterilebilir mi? | **RİSK.** `0008`'in `exam_sessions.question_ids` NOT NULL'ını kaldırması, onu okuyan dört çağrı yerini **aynı commit'te** güncellemeyi zorunlu kılıyor; yoksa ilk blueprint oturumu `TypeError` ile düşer. Göç ve kod tek commit'te gider. |
| **XI. Modülerlik ve Tekrarsızlık** | Aynı kural ikinci kez yazılıyor mu? | **GEÇTİ — planın belkemiği.** Üç taşıma: `db_now` → `core/db.py`; `effective_expiry`/`remaining_seconds` → `modules/assessment/exam_state.py`; `_SlidingWindowLimiter` → `core/rate_limit.py`. Politika çözümlemesi tek fonksiyonda (`modules/policy/service.py`). İpucu üst sınırı bugün **iki ayrı yerde** sabit ve birbirinden habersiz — tek sözlüğe indiriliyor. |

**Complexity Tracking**: aşağıda.

---

## Project Structure

### Documentation (this feature)

```text
specs/002-production-hardening/
├── spec.md                    # Şartname (11 hikâye, 62 FR, 16 SC, uygulama sırası)
├── plan.md                    # Bu dosya
├── research.md                # Faz 0 — 5 alan, 37 karar, her biri dosya:satır kanıtlı
├── data-model.md              # Faz 1 — 4 göç, 7 yeni tablo, RLS ve GRANT/REVOKE dahil
├── quickstart.md              # Faz 1 — port tuzağı, her hikâyenin elle doğrulaması
├── contracts/
│   └── api-changes.md         # Faz 1 — yeni/değişen uçlar, kırılma riski tablosu
├── checklists/
│   └── requirements.md        # Şartname kalite kapısı + taslak 2 düzeltmeleri
└── tasks.md                   # Faz 2 — /speckit-tasks çıktısı
```

### Source Code (repository root)

```text
apps/api/app/
├── core/
│   ├── config.py              # DEĞİŞİK: jwt_issuer alias (FR-224, YAPILDI)
│   ├── db.py                  # DEĞİŞİK: db_now buraya taşınır
│   └── rate_limit.py          # YENİ: _SlidingWindowLimiter chat.py'den taşınır (FR-222)
├── api/
│   ├── deps.py                # DEĞİŞİK: UnlockedCourseMemberDep, PageDep
│   ├── chat.py                # DEĞİŞİK: kilit bağımlılığı, /chat/availability, limiter taşınır
│   ├── exams.py               # DEĞİŞİK: exam_state'e devreder, blueprint uçları
│   ├── questions.py           # DEĞİŞİK: kota, blueprint bağlantısı, sayfalama
│   ├── blueprints.py          # YENİ: blueprint + öğrenme çıktısı uçları
│   ├── policy.py              # YENİ: ders AI politikası uçları
│   └── privacy.py             # YENİ: KVKK dışa aktarma / silme uçları
├── modules/
│   ├── assessment/exam_state.py   # YENİ: yürüyen oturum sorgusu + süre kırpma (tek yer)
│   ├── policy/service.py          # YENİ: resolve_policy — NULL = global oku
│   ├── ingestion/pipeline.py      # DEĞİŞİK: to_thread (FR-220), retry/backoff (FR-213)
│   └── retrieval/dense.py, fts.py # DEĞİŞİK: to_thread + belge filtresi (FR-132)
├── schemas/page.py            # YENİ: generic Page[T] (FR-160)
└── main.py                    # DEĞİŞİK: ısıtma (FR-221), request_id zarfa (FR-155)

apps/web/
├── lib/
│   ├── api.ts                 # DEĞİŞİK: timeout bütçeleri, retry, requestId
│   ├── errors.ts              # DEĞİŞİK: classifyError
│   ├── use-resource.ts        # DEĞİŞİK: backoff'lu polling
│   ├── supabase.ts            # YENİ: gerçek oturum (FR-170)
│   └── security-headers.ts    # YENİ: tek sözlük, iki uygulama noktası
├── components/                # DEĞİŞİK: page-state (soğuk başlangıç, requestId), course-nav (kilit)
├── app/courses/[courseId]/
│   ├── blueprints/            # YENİ ekran
│   └── settings/              # YENİ ekran (AI politikası)
└── next.config.ts             # DEĞİŞİK: güvenlik başlıkları

supabase/migrations/
├── 0008_exam_blueprint.sql    # YENİ
├── 0009_course_ai_policy.sql  # YENİ
├── 0010_ingestion_retry.sql   # YENİ
└── 0011_pagination_indexes.sql # YENİ

scripts/docs_check.mjs         # YENİ: üç dar mekanik kapı (FR-183)
```

**Structure Decision**: Mevcut monorepo yapısı korunuyor. Yeni dizin yalnız iki tane: `app/modules/policy/` (politika çözümlemesi) ve kökte `scripts/` (belge kapısı, `apps/web/scripts/contrast.mjs` deseninde, bağımlılıksız Node ESM).

---

## Faz durumu

| Faz | Çıktı | Durum |
|---|---|---|
| 0 — Araştırma | `research.md` | **TAMAM** — 5 alan, 37 karar |
| 1 — Tasarım | `data-model.md`, `contracts/api-changes.md`, `quickstart.md` | **TAMAM** |
| 2 — Görevler | `tasks.md` | `/speckit-tasks` bekliyor |
| 3 — Uygulama | kod | FR-224 **YAPILDI**, gerisi sırada |

### Faz 1 sonrası anayasa yeniden değerlendirmesi

Tasarım, Faz 0'da görünmeyen **iki fail-open riski** ortaya çıkardı ve ikisi de kapatıldı:

1. **Token bütçesi fail-open** (Anayasa IV): `request_logs`'un SELECT politikası yalnız eğitmene açık; öğrenci bağlamında `sum(token_count)` sıfır satır görür ve bütçe kontrolü **her zaman geçer**. `SECURITY DEFINER` yardımcısıyla kapatıldı.
2. **Yeni tablolar tam yazılabilir doğar** (Anayasa II + FR-115): `0001_core_schema.sql:313-316` gelecekteki tüm tablolara `dou_app` için `UPDATE` veriyor. `0008` açıkça `REVOKE UPDATE ON exam_items, blueprint_cells` yazmazsa sürümlerin değişmezliği koda değil alışkanlığa dayanır.

İkisi de "yazılmayan satırın kusur olduğu" sınıfından — 001'in devir belgesinin **sessiz kusur** dediği aile. Bu yüzden `data-model.md` §2.11 ve §2.14 bilerek yapılmayanları da listeliyor.

---

## Complexity Tracking

| İhlal | Neden gerekli | Elenen basit alternatif ve eleme sebebi |
|---|---|---|
| **Kapsam, dondurma tarihine 8 gün kala genişletiliyor** (Anayasa VI) | Kullanıcının açık kararı (9 Ağustos): hocanın "önce sınavın çatısı" isteği ve ders AI politikası, teslim gereksinimlerinin parçası sayıldı | *Minimal blueprint* (mevcut yapıya 5 alan) önerildi ve **reddedildi**. Risk kabul edildi; kesme noktası spec.md §Uygulama sırası'ndadır — yetişmeyen iş sıranın sonundan kesilir, ortasından değil |
| **Yedi yeni tablo** | Blueprint'in sürüm değişmezliği (FR-115) ve dağılım doğrulanabilirliği (FR-112) veri modelinde çözülmezse uygulama koduna kaçar | *JSONB tek kolon* elendi: dağılım hücrelerine kısıt yazılamaz, `blueprint_cells` üzerindeki `CHECK`'ler uygulama koduna taşınırdı. *Snapshot* elendi: aynı soru metni iki yerde yaşar ve ayrışır |
| **Yeni npm bağımlılığı (`@supabase/supabase-js`)** | T023 gerçek kimliğin frontend ayağı; anahtar gelince yalnız yapılandırma kalsın | Elle JWT akışı yazmak elendi: token tazeleme, oturum kalıcılığı ve PKCE'yi yeniden yazmak, kütüphaneyi almaktan daha riskli. Gerekçe PLAN.md "Teknoloji Kilidi" bölümüne yazılacak |
| **`core/rate_limit.py` yeni modül** | Sınırlayıcı iki uçta gerekli; `chat.py`'de bırakılıp `questions.py`'den import edilmesi katman ihlali olurdu | *Kopyalamak* elendi (Anayasa XI). *`chat.py`'den import* elendi: `api/` katmanı `api/`'ye bağlanır, döngü riski |

---

## Kalan riskler

| Risk | Erken işaret | Geri dönüş |
|---|---|---|
| Blueprint 17 Ağustos'a yetişmez | 13 Ağustos akşamı `0008` uygulanmamışsa | Sıranın 7. maddesinden kesilir; US1-US2-US8-US5 tek başına savunulabilir bir teslim üretir |
| `exam_sessions.question_ids` NOT NULL kalkışı mevcut kodu düşürür | İlk blueprint oturumunda `TypeError` | Göç ve dört çağrı yerinin güncellenmesi **aynı commit'te**; ayrı giderse geri alınır |
| Kilit fazla kapatır (prova modunu da keser) | `practice` oturumunda 403 | Kabul senaryosu 4 tam olarak bunu ölçüyor; testte karşı kontrol var |
| Politika varsayılanları bugünkü davranışı değiştirir | Aynı soruya politika öncesi/sonrası farklı cevap | FR-136 kapısı; `resolve_policy` NULL'da global config'i döndürür ve bu birim testle sabitlenir |
| Anahtarlar "bu hafta" gelmez | 13 Ağustos'a kadar `.env` boş | US2'nin kota/eşzamanlılık/issuer/event-loop ayakları **anahtarsız da koşar**; ertelenmez. T047/T050/T051 raporda KOŞULMADI kalır |

---

## Şimdiden yapılmış iş

`002` dalında bugüne kadar kapatılan tek FR:

- **FR-224** (issuer ortam değişkeni uyuşmazlığı) — `apps/api/app/core/config.py`'de `AliasChoices("SUPABASE_JWT_ISSUER", "JWT_ISSUER")`; `apps/api/tests/test_config.py` (4 test) ve `docs/deployment.md`'ye eksik satır. **Mutasyonla doğrulandı**: alias kaldırıldığında hem genel tarayıcı testi hem özel test kırmızı yanıyor, geri alınınca yeşile dönüyor. Genel tarayıcı, `.env.example`'daki **her** değişkeni `Settings` alanlarına karşı denetlediği için SC-015'i de karşılar — yeni bir uyuşmazlık eklenirse test kırılır.
