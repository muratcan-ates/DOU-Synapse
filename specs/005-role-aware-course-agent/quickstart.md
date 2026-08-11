# Quickstart: 005 Rol Farkındalıklı Ders Ajanı

Bu belge uygulama ve doğrulama sırasıdır; tek başına “çalışıyor”, “staging” veya
“production” kanıtı değildir.

## 1. Güvenli checkout ve izolasyon

Repo iCloud dışında bir `~/code` worktree'sinde olmalıdır. Başlangıç kontrolü:

```bash
git status --short --branch
git rev-parse HEAD
git merge-base HEAD 7c1c219
git worktree list --porcelain
```

Beklenen feature base `7c1c219`'dir. Her paralel şerit kendi `.venv`,
`node_modules`, port ve `TEST_DB_NAME` değerini kullanır:

```bash
export TEST_DB_NAME=dou_synapse_test_agent_005_<lane>
export API_PORT=8051
export WEB_PORT=3051
```

Paylaşılan DB'de ağır DB/Playwright paketleri paralel koşmaz; `COME 331` hiçbir
teardown hedefi olmaz.

## 2. Tasarım kapısı

Uygulamadan önce şu paket birlikte okunur:

```text
.specify/memory/constitution.md
specs/005-role-aware-course-agent/spec.md
specs/005-role-aware-course-agent/plan.md
specs/005-role-aware-course-agent/data-model.md
specs/005-role-aware-course-agent/contracts/api.md
specs/005-role-aware-course-agent/threat-model.md
.ai/README.md
.ai/policy.json
```

İlk repo varsayılanları:

```text
student user/day token:    12000
instructor user/day token: 40000
student deployment hard:   50000
instructor deployment hard:200000
course deployment hard:    500000
platform deployment hard: 5000000
course max output:           700
active reservation/user:       1
reservation lease:        enforced provider deadline + reconciliation marjı (SQL 30..600 sn)
kill switch: COURSE_AGENT_ENABLED
```

Bunlar staging maliyet/pedagoji ölçümü ve iki isimli onay olmadan production
eşiği diye sunulmaz. Guard-event retention süresi ve production canary eşikleri
ayrıca karara bağlanır.

## 3. Migration ve SQL kanıtı

Migration sabittir:

```text
supabase/migrations/0015_role_aware_course_agent.sql
```

Taze izole DB'ye 0001..0015 uygulanır. SQL testleri en az şunları kanıtlar:

- `assistant_audience` yalnız `student|instructor`;
- session audience immutable;
- cache unique identity audience + üç revision içerir;
- cache SELECT/INSERT RLS yalnız current course audience'ını görür/yazar;
- normal kullanıcı, instructor, `dou_worker` ve Public yeni tablolara doğrudan erişemez;
- definer fonksiyon current user/membership'i içeride çözer;
- başka user/course reservation'ı reconcile edemez;
- iki gerçek bağlantı aynı user/course için son token dilimini birlikte alamaz;
- aktif reservation sayısı `max_concurrent_requests` değerini aşamaz;
- course user budget server-owned audience hard cap'i, course toplam budget
  server-owned course hard cap'i aşamaz; cross-course global-user ve platform
  toplamları da atomiktir; DB 50k/200k/500k/5m ceiling'leri ayrıca zorlar;
- reserve fonksiyonu 7 argümanlıdır ve lock sırası sabit platform-gün sonra course'tur;
- course-day, course-user-day, global-user-day ve platform-day indeksleri vardır;
- süresi geçmiş unreconciled satır concurrency'yi bırakır fakat reserved charge
  aynı günün user/course quota toplamında kalır;
- quota/concurrency/rate/scope event'lerinde serbest metin kolonu yoktur.

Örnek hedefli komut, test dosyası uygulama şeridinde oluşturulduktan sonra:

```bash
psql "$ADMIN_DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f supabase/tests/rls_role_aware_agent.sql
```

Request replay/idempotency, DB minute/request bucket, HMAC/fingerprint ve adaptive
strike/backoff bu SQL paketinin must-pass şartı değildir; ayrı gelecek backlog'udur.

## 4. Backend hedefli paket

```bash
cd apps/api
uv sync --extra dev
```

Hedefli testler mevcut ve 005'e eklenen testlerden seçilir:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/test_chat_api.py tests/test_answer_cache.py tests/test_exam_lock.py tests/test_policy.py tests/test_role_aware_agent.py tests/test_user_rights.py  # 157 passed  # docs-check: tarihsel 157 · 2026-08-11
```

Ardından statik ve tam paket:

```bash
RUFF_CACHE_DIR=/private/tmp/dou-agent-ruff uv run ruff check .
RUFF_CACHE_DIR=/private/tmp/dou-agent-ruff uv run ruff format --check .
uv run mypy app
PYTHONDONTWRITEBYTECODE=1 uv run pytest -q  # 879 passed  # docs-check: backend.tests = 879
```

2026-08-11 backend handoff kanıtı:

```text
taze hedefli backend paketi: 157/157
pytest -q apps/api/tests:     878/878
backend mypy:                92 dosya temiz
ledger-counter son düzeltme:   27/27 + ruff + diff temiz
frontend lib testleri:        322/322
frontend typecheck/build:     temiz
```

Repo kökünden çıplak pytest, 005 dışı kardeş `scripts.*` import collection
sorununa takıldı; bu nedenle repo-root full suite yeşil diye raporlanmaz. Son
dar düzeltmenin ruff kanıtı tam format kapısı yerine geçmez. Browser,
real-provider ve staging de bu sayıların içinde değildir.

Provider spy şu sözleşmeyi kanıtlar:

```text
effective_output = min(course_policy.max_output_tokens, settings.llm_chat_max_tokens)
provider request max_tokens <= effective_output
```

Fake provider; rol/kota/zarf mekaniğini kanıtlayabilir, gerçek pedagojik kaliteyi,
faithfulness'i veya maliyeti kanıtlamaz.

## 5. Zorunlu mutasyon kanıtları

Kontrol gerçekten kaldırılıp testin kırmızı olduğu görülür; sonra üretim kodu geri
alınıp aynı test tekrar yeşil koşar:

1. `ChatRequest` audience kabul etsin → payload-injection testi kırmızı.
2. Membership-to-audience projection değişsin → student/instructor testleri kırmızı.
3. Session audience karşılaştırması kalksın → role-change continuation testi kırmızı.
4. Cache unique/key'den audience veya revision kalksın → cross-profile/cache testi kırmızı.
5. Reserve fonksiyonundaki lock veya quota check kalksın → iki bağlantılı race testi kırmızı.
6. Concurrency filtresi kalksın → ikinci aktif reservation testi kırmızı.
7. Provider output cap aktarımı kalksın → adapter spy testi kırmızı.
8. `UnlockedCourseMemberDep` chat/list/detail yolundan kalksın → direct API/second-tab testi kırmızı.
9. Guard event'e `details`, prompt/hash/IP alanı eklensin → privacy schema testi kırmızı.
10. `COURSE_AGENT_ENABLED` POST/availability kontrolü kalksın → kill-switch testi kırmızı.
11. Exam start veya chat finalization'dan user lock/recheck kalksın → forced
    interleaving testi cevap/artifact kaçağını yakalayıp kırmızı.
12. `/me/export` user lock/active-exam kontrolü kalksın → export/exam race testi kırmızı.

Uygulanmamış mutasyonun ardından yeşil kalan test kanıt değildir.

## 6. Frontend hedefli paket

```bash
cd apps/web
bun install --frozen-lockfile
bun test
bun run typecheck
bun run build
```

UI test matrisi:

- server-derived `student/student_coach` ve `instructor/instructor_assistant`;
- mixed-role course değişimi;
- request body'de audience/agent_profile olmaması;
- üyelik yok/yanlış course scope, loading, empty ve network error;
- global disabled, policy closed ve exam locked durumunda composer olmaması;
- 200 abstention; 409 `session_audience_changed|concurrent_request`;
  422 invalid payload; 429 rate/quota/durable concurrency; 503 kill switch;
- 375 px, dark mode, keyboard, focus trap/return ve reduced motion;
- API'de olmayan remaining usage veya backoff sayısı gösterilmemesi.

Drawer'ın mevcut oturumunu full-page'e deep-link etmesi 005'in bu ilk diliminde
teslim edilmediyse acceptance iddiası değildir; ayrı UI devam görevi olarak açık kalır.

## 7. Gerçek API + tarayıcı

Sunucu kimliği/readiness doğrulanmadan E2E sonucu yorumlanmaz:

```bash
curl -fsS "http://localhost:${API_PORT}/health/live"
curl -fsS "http://localhost:${API_PORT}/health/ready"
```

Embedding `warming` ise beklenir. Seri E2E:

```bash
cd apps/web
API_BASE_URL="http://localhost:${API_PORT}" \
WEB_BASE_URL="http://localhost:${WEB_PORT}" \
bunx playwright test e2e/agent-chatbox.spec.ts --workers=1
```

Tarayıcı/ağ kanıtı:

- rol etiketi sunucu membership'iyle uyumlu;
- hiçbir istek audience, agent_profile, user_id veya max_tokens göndermez;
- availability gelmeden chat/session isteği yoktur;
- aktif gerçek sınavda drawer ve tam sayfa composer yok, direct POST 403'tür;
- herhangi bir derste aktif student EXAM varken `/me/export` 423
  `exam_export_locked`; practice/expired ve instructor preview 200'dür;
- practice ve süresi dolmuş exam chat'i kilitlemez;
- aynı görünümde duplicate availability/dashboard fetch yoktur;
- 375 px yatay taşma ve console hatası yoktur;
- global kill switch kapalıyken composer/provider çağrısı yoktur.

## 8. Sözleşme ve belge kapısı

```bash
node scripts/docs_check.mjs
git diff --check
```

OpenAPI çalışan `create_app().openapi()` çıktısından yeniden üretilir. Diff'te:

- request'e audience/agent_profile/max_tokens/user_id eklenmediği;
- chat response, availability ve session listesinde yalnız onaylı audience/profile
  alanlarının bulunduğu;
- policy'nin dört yeni alanı ve validation aralıkları;
- tek hata zarfı ve `request_id`

kontrol edilir. OpenAPI bu Speckit şeridi tarafından elle düzenlenmez.

Son adayın ölçülen sözleşmesi: 50 path, 119 schema; `ChatRequest` yalnız
`mode|question|session_id|student_attempt` taşır. Audience/profile/user/max_tokens
request alanı değildir.

## 9. R3 AI-SDLC kapısı

```bash
python scripts/ai_sdlc_check.py \
  --repo-root . \
  --policy .ai/policy.json \
  --base-sha 7c1c219 \
  --head-sha "$(git rev-parse HEAD)"
```

Dossier en az şunları bağlar:

- student/instructor prompt revision ve exact candidate SHA;
- provider/model/embedding/retrieval/guardrail revision;
- audience/cache/session/quota/output/kill-switch değişikliği;
- fake/offline test kanıtı ve epistemik sınırı;
- real-provider holdout planı;
- pedagoji/ürün ve güvenlik/operasyon için iki isimli onay;
- canary stop koşulları ve `COURSE_AGENT_ENABLED` rollback provası.

## 10. Staging, rollout ve rollback

Repo kapıları yeşil olsa bile production öncesi:

1. Normal staging için `COURSE_AGENT_ENABLED=true`; ayrıca `false` emergency
   rollback provasında availability `globally_disabled`, POST 503 ve provider 0.
2. Gerçek Supabase Auth/RLS/Storage ile role ve migration doğrulaması.
3. Exact provider/model ile student/instructor ayrı holdout ve insan rubric'i.
4. Multi-worker quota/concurrency/load/cancellation testi.
5. Internal/eğitmen canary, ardından küçük öğrenci canary.
6. Leakage, faithfulness, scope, p95 latency, token/tur, 429/refusal ve feedback
   stop eşiklerinin izlenmesi.

Stop koşulunda `COURSE_AGENT_ENABLED=false`; 0015 geri sökülmez. Yeni provider
çağrısı açılmaz, unreconciled reservation kendi doğrulanmış lease'i sona erince
aktif concurrency hesabından düşer; aynı günün muhafazakâr quota charge'ı kalır.
Şema kusuru yeni forward-fix migration ile düzeltilir.

`COURSE_AGENT_ENABLED` mevcut `/chat` yolunun kill switch'idir, cohort seçici
değildir. Internal/eğitmen/öğrenci canary hedeflemesi korumalı deployment
ortamında ayrıca kurulup kanıtlanmalıdır.

## 11. Son rapor

```text
Kodlandı:
Yerelde doğrulandı:
Origin/PR/CI:
Staging:
Production:
KOŞULMADI:
Açık blocker/risk:
Rollback:
```
