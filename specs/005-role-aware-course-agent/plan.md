# Uygulama Planı: Rol Farkındalıklı Ders Ajanı

**Branch**: `005-role-aware-course-agent` | **Date**: 2026-08-11 | **Base**: `7c1c219` | **Spec**: [spec.md](spec.md)

## Özet

Mevcut FastAPI chat/RAG hattını rol farkındalıklı hâle getir; audience'ı ders
üyeliğinden sunucuda çöz; session/cache'i audience ve prompt/policy revizyonuna
bağla; `0015` ile atomik ve kalıcı quota/abuse katmanı kur; aynı sözleşmeyi
kullanan erişilebilir bir Next.js chatbox ekle. AI davranış değişikliğini R3
dossier, mutasyon, canary ve rollback ile yönet.

## Teknik bağlam

**Frontend**: Next.js 16.3 App Router, React 19.2, TypeScript 5, Tailwind CSS 4
**Backend**: Python 3.12, FastAPI, SQLAlchemy 2 async
**Veri**: PostgreSQL 16, pgvector, düz SQL migration, iki katmanlı app + RLS
**AI**: Mevcut LiteLLM provider, fastembed, hybrid retrieval, guardrail zinciri
**Test**: pytest, RLS SQL/mutasyon, Vitest, tsc, Next build, seri Playwright,
AI-SDLC validator ve gerçek-provider holdout (korumalı ortam)
**Migration**: `0015_role_aware_course_agent.sql`
**Feature flag**: `COURSE_AGENT_ENABLED=true` varsayılanlı acil kill switch;
mevcut `/chat` yolunu kapatır, cohort/canary seçici değildir

## Anayasa kontrolü

- **I / II — Kaynak ve AI sınırı**: Aynı retrieval/citation zinciri; kaynak yoksa cevap yok.
- **III — Ölçüm**: Token/reservation/refusal/output-cap sayısal ve içeriksiz kaydedilir.
- **IV — RLS**: Audience, quota ve abuse yetkisi istemci rolünden türetilmez;
  course membership + dar SECURITY DEFINER fonksiyonları bağımsız zorlar.
- **V — Türkçe hata**: Mevcut tek hata zarfı ve request_id korunur.
- **VI — Sınav güvenliği**: Giriş kapıları ortak exam-state kaynağını kullanır;
  sınav başlatma, chat finalizasyonu ve privacy export aynı kullanıcı düzeyi
  transaction kilidinde atomik sıralanır.
- **VII — Abstention**: Kapsam/kanıt/bütçe reddi normal ürün sonucu; saldırı ve
  hız sınırı güvenlik hatasıdır.
- **VIII — Kırılabilir kanıt**: Audience/cache/quota/exam guard mutasyonları şarttır.
- **IX — Modern yığın**: Yeni framework/ajan orkestratörü eklenmez.
- **XI — Tek sahiplik**: Chatbox ve tam sayfa aynı API/store/provider'ı paylaşır.

Anayasa istisnası yoktur. “Ajan” mevcut anayasanın dışarıda bıraktığı çok-ajanlı
orkestrasyon değildir; tek, eylemsiz ve kaynak-bounded yardımcıdır.

## Uygulama dilimleri

### Dilim 0 — Sözleşme, threat model ve R3 dossier

1. Bu Speckit paketini onayla.
2. AI-sensitive path listesini çıkar; 005 R3 dossier root revision oluştur.
3. Prompt/audience/guardrail/limit için baseline metrik ve rollback flag'ini yaz.
4. Migration numarası `0015` ve ortak sözleşme enum sahipliğini sabitle.

### Dilim 1 — Audience ve rol-bounded chat çekirdeği

1. Ortak contract'ta `AssistantAudience {student,instructor}` tanımla ve
   `agent_profile {student_coach,instructor_assistant}` değerini ondan türet.
2. Audience'ı `CourseContext.role` üzerinden tek server fonksiyonunda çöz.
3. Session oluştururken immutable audience yaz; devamda eşleşme kontrolü yap.
4. Generator/prompt builder'a server-owned audience ver; client şemasına koyma.
5. Instructor promptunu eylemsiz/kaynaksal; student promptunu Sokratik sınırla yaz.
6. Cache anahtarına audience + policy/source/prompt contract revision ekle.

### Dilim 2 — `0015` kalıcı quota ve abuse katmanı

1. Migration'da policy alanları, token reservation ve içeriksiz guard event'i ekle.
2. Dar SECURITY DEFINER reserve/reconcile/record fonksiyonlarını yaz.
3. Fonksiyon içinde current user, membership, audience ve sınırları yeniden çöz.
4. App/worker/Public direct grant'lerini açıkça kapat.
5. Provider öncesi kısa ayrı işlemde reserve; ölçülmüş başarıyı gerçek tokenla,
   provider hatası/iptal/bilinmeyen usage yolunu rezerve edilen tutarla ilk-yazma
   kazanır biçiminde reconcile et.
6. Sabit platform-gün kilidini sonra course kilidini al; ders-kullanıcı,
   global-kullanıcı, ders ve platform toplamlarını aynı kararda sınırla.
7. Process-local limiter'ı hızlı katman olarak koru; DB kararı otorite olsun.

### Dilim 3 — API sözleşmesi ve abuse guard

1. Availability/session/chat response'larına yalnız server-resolved `audience`
   ve `agent_profile` alanlarını ekle; istemciye usage veya güvenlik ayrıntısı uydurma.
2. Mevcut source/evidence/citation/leakage guardrail zincirini iki audience için koru.
3. Provider `max_tokens` değerini course policy ile global hard ceiling'in en
   küçüğüyle zorla.
4. İçeriksiz rate/quota/concurrency/scope guard event'lerini uygula; adaptif
   repeat/backoff'u ayrı gelecek backlog'unda tut.
5. Cache hit, abstention, provider error ve cancellation accounting yollarını kapat.
6. Sınav başlatma/chat finalizasyonu/privacy export'u kullanıcı düzeyi kilitte
   sırala; aktif öğrenci EXAM sırasında export'u 423 ile geçici durdur.

### Dilim 4 — Frontend AgentChatbox

1. Ortak `CourseAssistant` helper/type'larını chat response/availability ile paylaş.
2. Course nav'da floating drawer, dashboard course card'da course-bound inline trigger.
3. Öğrenci/eğitmen etiketi, kaynak sınırı, mode ve mevcut abstention/error UX'ini ekle.
4. Drawer içinde aynı `session_id` ile çok turlu devamı koru; tam sayfaya
   deep-link'i ilk 005 acceptance kapsamına alma.
5. Mobile/dark/loading/empty/error/locked/focus/reduced-motion durumlarını tamamla.

### Dilim 5 — Kanıt ve yayın

1. Hedefli backend/frontend/RLS testleri ve negatif/mutasyon çivileri.
2. Tam paket, OpenAPI, docs_check, build ve seri gerçek-API Playwright.
3. R3 dossier artifact hash/evidence/approval/rollout/rollback alanlarını güncelle.
4. Normal akışta flag açık staging real-provider holdout; ayrıca flag kapalı
   acil rollback provası. Cohort canary gerekiyorsa ayrı deployment kontrolü kullan.
5. Eğitmen canary → küçük öğrenci canary → metrik eşikleri geçerse genişlet.

## Proje yapısı ve dosya sahipliği

```text
supabase/migrations/0015_role_aware_course_agent.sql
supabase/tests/rls_agent.sql
supabase/tests/rls_agent_mutation_check.sh

apps/api/app/contracts.py                    # ortak AssistantAudience
apps/api/app/api/chat.py                     # tek chat uçları
apps/api/app/api/exams.py                    # user-level assessment lock caller
apps/api/app/api/privacy.py                  # active-exam export gate
apps/api/app/schemas/chat.py                 # istemci zarfı; audience input yok
apps/api/app/models/chat.py
apps/api/app/models/policy.py
apps/api/app/modules/agent/                   # rol/prompt/abuse/quota servisleri
apps/api/app/modules/assessment/exam_state.py # ortak kullanıcı kilidi
apps/api/app/modules/generation/              # audience + output cap dikişi
apps/api/app/core/config.py                   # hard ceiling/flag/secret ayarları
apps/api/tests/test_agent_*.py

apps/web/components/course-assistant/**        # ortak drawer yüzeyi
apps/web/lib/course-assistant.ts               # onaylı identity/yardımcılar
apps/web/lib/types.ts                          # onaylı zarf
apps/web/components/course-nav.tsx             # course-scoped floating trigger
apps/web/components/portal/dashboard-course-card.tsx # course-bound inline trigger
apps/web/e2e/agent-chatbox.spec.ts

.ai/changes/005-role-aware-course-agent-*.json
.ai/evidence/005-*.json
specs/005-role-aware-course-agent/**
```

**Rezerv dosyalar**: `apps/api/app/contracts.py`, `apps/api/app/api/chat.py`,
`apps/api/app/core/config.py`, `apps/web/lib/types.ts`, OpenAPI ve `.ai` dossier
aynı anda birden çok şeride verilmez. Bir lider sözleşme commit'i önce iner.

## Paralel çalışma haritası

| Şerit | Sahiplik | Bağımlılık |
|---|---|---|
| A — DB/security | 0015, SQL functions, RLS/mutation | sözleşme enum kararı |
| B — backend agent | role/prompt/quota service, API tests | A contract + lider common files |
| C — frontend | AgentChatbox/provider/tests | API contract fixture |
| D — evidence | Speckit, dossier, eval/Playwright | A+B+C son SHA |

Her şerit güncel base SHA'dan ayrı worktree ve benzersiz `TEST_DB_NAME` ile
çalışır. Ağır DB/Playwright paketleri paylaşımlı veritabanında paralel koşmaz.

## Tasarım kapıları

1. **Role gate**: audience input yok; current membership ile session audience eşleşir.
2. **Source gate**: source/evidence/citation guard değişmeden tek yol.
3. **Exam gate**: exam start/chat finalize/export aynı user lock'unda; zorlanmış
   interleaving chat artifact'i veya export sızıntısı bırakmaz.
4. **Quota gate**: provider öncesi DB reservation; platform-gün sonra course lock;
   course-user/global-user/course/platform yarış testleri.
5. **Output gate**: provider request cap + response hard ceiling.
6. **Abuse gate**: content-free ledger, ordinary out-of-scope cezalandırılmaz.
7. **Privacy gate**: instructor/admin öğrenci prompt/answer/ledger satırı göremez.
8. **AI-SDLC gate**: R3 dossier exact hashes + two named approvals + rollback flag.

## Rollout

```text
candidate merge (`COURSE_AGENT_ENABLED=true`; mevcut chat davranışı korunur)
  -> staging: fake + real-provider holdout + `false` kill-switch provası
  -> internal/eğitmen canary
  -> %5 öğrenci kohortu
  -> %25
  -> %100
```

Her aşama aynı candidate SHA, prompt revision, model/provider ve policy digest ile
ölçülür. Bu repo flag'i cohort seçmez; cohort hedefleme korumalı deployment
ortamının açık görevidir. Stop koşulları threat-model ve dossier'da önceden
yazılır. Rollback: flag `false` yapılır, yeni `/chat` POST'ları 503 ile durur ve
provider çağrılmaz; 0015 tabloları silinmez, aktif reservations reconcile/lease
ile kapanır.

## Complexity tracking

Yeni bir orchestration framework, queue, Redis veya tool runtime eklenmez.
PostgreSQL-backed reservation tercihinin maliyeti üç küçük tablo ve dar
fonksiyonlardır; karşılığında çok-worker yarışında fail-open process-local quota
riski kapanır. Redis ancak ölçülmüş DB yükü SLO'yu bozarsa ayrı ADR ile düşünülür.
