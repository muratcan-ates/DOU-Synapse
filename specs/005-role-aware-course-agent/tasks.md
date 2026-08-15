# Görevler: 005 Rol Farkındalıklı Ders Ajanı

**Branch**: `005-role-aware-course-agent`
**Base**: `7c1c219`
**Durum**: Speckit + backend/migration + frontend kodlandı. Güncel entegrasyon
ağacında API 894/894, mypy 92 dosya, frontend 349/349 (30 test dosyası),
typecheck/build ve seri gerçek-API tarayıcı 36/36 ölçüldü. R3 dossier yazıldı;
append-only final R4 kökü yerel no-ref exact adayda `main` tabanına karşı PASS.
Gerçek commit/PR CI gözlemi hâlâ açık. DB/RLS mutasyon betiği izole veritabanlarında
uygulandı. Uygulama katmanı
kırmızı/restore/yeşil matrisi 12/12 geçti. Otomatik mobile/dark/keyboard/focus/ağ
turu tamamlandı; manuel VoiceOver+Safari, doğrudan exam/kill-switch tarayıcı
yolları, GitHub CI, provider/staging/rollout açık.
**Migration**: `0015_role_aware_course_agent.sql`

## İşaret sözlüğü

- `[x]`: Bu Speckit artefaktı yazıldı ve contract drift açısından kontrol edildi.
- `[ ]`: Açık; dosya görülmüş olsa bile gerekli kapılar geçmeden DONE değildir.
- `KOŞULMADI`: secret, gerçek provider, staging veya production gerektiği için açık.

## Bağımlılık grafiği

```text
P0 contract + R3 dossier
  -> P1 0015 DB/RLS
      -> P2 backend vertical slice
          -> P3 Next.js drawer
              -> P4 repo evidence
                  -> P5 staging/canary/rollback

P6 future abuse hardening (005 release kapısı değildir)
```

Ortak contract/config/chat/type dosyaları lider tarafından bir kez düzenlenir;
paralel şeritler aynı hot file'a yazmaz.

---

## P0 — Speckit ve R3 change control

- [x] **T001** `spec.md`: course-scoped, eylemsiz, role-aware assistant ve
  acceptance/out-of-scope yazıldı. — DONE 2026-08-11
- [x] **T002** `research.md`: reuse, audience, cache, quota, privacy ve UI
  kararları yazıldı. — DONE 2026-08-11
- [x] **T003** `data-model.md`: exact 0015 tablo/fonksiyon/RLS/rollback modeli
  yazıldı. — DONE 2026-08-11
- [x] **T004** `contracts/api.md`: gerçek request/response/error/policy/internal
  function sözleşmesi yazıldı. — DONE 2026-08-11
- [x] **T005** `threat-model.md`: shipped-now kontroller, residual risk ve future
  backlog ayrıldı. — DONE 2026-08-11
- [x] **T006** `quickstart.md`: izole DB, mutation, browser, R3 ve rollout kapıları
  yazıldı. — DONE 2026-08-11
- [x] **T007** Repo başlangıç varsayılanlarını spec/ADR kararı olarak sabitle:
  course 12000/40000/700/1 ve deployment user/course/platform hard cap
  50000/200000/500000/5000000. Lease sabit ürün default'u değil, provider deadline'ını
  aşan doğrulanmış server hesabıdır.
  Bunlar production onayı değildir; retention, gerçek
  maliyet kalibrasyonu ve isimli dış approvals P5'te açık kalır. — DONE 2026-08-11
- [x] **T008** `.ai/changes/` altında 005 R3 dossier root revision oluştur;
  prompt/retrieval/cache/quota/output/kill-switch artefaktlarını exact SHA'ya bağla.
  Dossier/evidence yazıldı ve immutable feature commit'inde
  `AI_SDLC_CHECK=PASS` alındı. — DONE 2026-08-11
- [x] **T009** Lider ortak sözleşmeyi sabitledi:
  `AssistantAudience(student|instructor)` ve türetilen
  `student_coach|instructor_assistant`; `COURSE_AGENT_ENABLED`. — DONE 2026-08-11

**P0 kapısı**: İstemci persona seçmez; tool/write yoktur; gelecek abuse kontrolleri
005 tamamlandı diye işaretlenmez; iki bağımsız approval sahibi adlandırılır.

---

## P1 — `0015` kalıcı quota, guard ledger ve RLS

- [x] **T101** `assistant_audience` enum'u, immutable `chat_sessions.audience`
  backfill/trigger'ı ve exact membership projection'ı ekle.
- [x] **T102** `answer_cache` için `audience`, `policy_revision`,
  `prompt_revision`, `corpus_revision` ve altı alanlı unique identity ekle.
- [x] **T103** `course_ai_policies` alanlarını ekle:
  `student_daily_token_budget=12000`, `instructor_daily_token_budget=40000`,
  `max_output_tokens=700`, `max_concurrent_requests=1` ve constraint'ler.
- [x] **T104** `ai_token_reservations` tablosunu exact kolon/lease/index/CASCADE
  sözleşmesiyle oluştur.
- [x] **T105** `ai_guard_events` tablosunu yalnız
  `rate_limited|quota_exhausted|concurrency_limited|scope_refused` allowlist'iyle oluştur.
- [x] **T106** `app.reserve_course_agent_tokens(course_id,reservation_id,requested_tokens,lease_seconds,user_hard_limit,course_hard_limit,platform_hard_limit)`:
  current user/membership, Europe/Istanbul course-user/global-user/course/platform
  token, platform-gün sonra course lock, active reservation concurrency, `30..600`
  lease, DB 50k/200k/500k/5m ceiling ve içeriksiz red event'i. — DONE 2026-08-11
- [x] **T107** `app.reconcile_course_agent_tokens(reservation_id,actual_tokens)`,
  `app.record_course_agent_guard_event(course_id,event_type)` ve reservation-ledger
  tabanlı `app.course_tokens_today(course_id)` fonksiyonlarını yaz.
- [x] **T108** Yeni tablolarda ENABLE RLS, policy yok, explicit REVOKE; FORCE RLS
  kullanma ki dar SECURITY DEFINER owner yolu çalışsın. Yalnız `dou_app` için dar
  function EXECUTE, `dou_worker` ve Public için revoke.
- [x] **T109** Taze 0001..0015 SQL testleri: role/backfill/immutability/cache unique,
  direct grants, current-user ownership, invalid event/requested token.
- [x] **T110** Gerçek bağlantılı race: course-user, cross-course global-user ve
  platform son token diliminde overshoot 0; ikinci aktif reservation reddi.
- [x] **T111** Deadline'dan uzun lease ve expired-unreconciled davranışı;
  provider error/cancel/missing usage'da reserved charge'ın korunduğu, first-reconcile
  wins, lease sonunda yalnız concurrency'nin boşaldığı, günlük charge'ın kaldığı
  ve actual'ın reservation'ı aşamadığı testler. — T101–T111 taze hedefli
  backend paketiyle 157/157, 2026-08-11
- [x] **T112** RLS/mutation script: membership, audience immutability,
  forged-session RLS, answer-cache audience SELECT/INSERT, function-only table
  grant, PUBLIC helper execute, advisory lock, günlük kota, eşzamanlılık ve
  privacy sınırları **ayrı ayrı** gevşetildiğinde kırmızı. Cross-audience direct
  SQL SELECT ayrıca reddedilir.
  `rls_role_aware_agent_mutation_check.sh`, 0001..0015'i PID ile adlandırılmış
  izole DB'lere uyguladı; referans koşuda 8 kapalı sınır + 3 kalıcı kota iddiası
  geçti, 11/11 mutasyon beklenen kesin sızıntıyı yakaladı ve koşu sonunda geçici
  DB kalıntısı 0 ölçüldü. — DONE 2026-08-11
- [x] **T113** Course/profile delete CASCADE ve KVKK export `not_included`
  davranışını doğrula; retention job yoksa açık risk olarak bırak. `/me/export`,
  ham reservation/guard satırı veya kimliği taşımadan iki içeriksiz operasyon
  kategorisini additive `not_included` açıklamalarıyla bildiriyor. Benzersiz test
  DB'sindeki gerçek PostgreSQL koşusunda hem course hem profile DELETE sonrasında
  reservation/guard satırı 0 kaldı; aktif sınav 423 ve kullanıcı düzeyi yarış
  kilidi korundu. `test_user_rights.py` 13/13, Ruff, mypy 92 dosya ve
  `git diff --check` yeşil. Canlı retention/operator cleanup işi açık risktir.
  — DONE 2026-08-11

**P1 kapısı**: Taze DB, SQL 0 FAIL, race overshoot 0, adlandırılmış mutasyonlar
kırmızı/geri dönüşte yeşil; ortak/demo DB kullanılmadı.

---

## P2 — Backend audience, session/cache, quota ve output cap

- [x] **T201** `contracts.py`: tek `AssistantAudience`; `agent_profile` yalnız
  server-derived property. Request şemasına eş alan ekleme.
- [x] **T202** Membership context'ten audience projection'ını tek fonksiyonda yap;
  platform adminliği projection üretmesin.
- [x] **T203** Student/instructor system-owned prompt revision'ı; source-only,
  no-tools/no-write, instructor için student-private-data yasağı.
- [x] **T204** Session create/resume/list akışına immutable audience bağla;
  mismatch 409 `session_audience_changed`.
- [x] **T205** Cache lookup/store identity'sini audience + policy/prompt/corpus
  revision'a bağla; başka profile/revision fallback yapma.
- [x] **T206** Policy input/effective output'a dört yeni exact alanı ve validation
  aralıklarını ekle; mevcut `daily_llm_budget` course bütçesini koru.
- [x] **T207** Kısa bağımsız RLS session kullanan quota wrapper'ları yaz:
  reserve/reconcile/record; provider I/O sırasında DB lock tutma.
- [x] **T208** Chat sırası: kill switch -> process burst -> reservation-ledger
  course precheck
  -> cache -> process-local concurrency -> durable reservation -> provider ->
  finally conservative reconcile.
- [x] **T209** Cache hit'te provider reservation açma; request log `cached=true`;
  burst kontrolü cache lookup'tan önce kalsın.
- [x] **T210** Provider `max_tokens` değerini
  `min(policy.max_output_tokens, settings.llm_chat_max_tokens)` ile zorla.
- [x] **T211** Chat/availability/session response'a yalnız `audience` ve
  `agent_profile` ekle; request'e ekleme; usage/refusal_reason/default_mode uydurma.
- [x] **T212** Error contract'ı çivile: 409
  `session_audience_changed|concurrent_request`, 429
  `rate_limited|agent_concurrency_limited|agent_quota_exhausted`, 503
  `course_agent_disabled`, `Retry-After` header ve tek request_id zarfı.
- [x] **T213** `COURSE_AGENT_ENABLED=false`: availability disabled, direct POST
  503 ve provider spy çağrısı 0.
- [x] **T214** Exam lock: entry yolları + exam start/chat finalize aynı user lock'u;
  forced interleaving 403 ve response/session/message/cache artifact'i 0; expiry,
  practice ve instructor istisnası. — DONE 2026-08-11
- [x] **T215** Guard event persistence: rate/scope ayrı kısa transaction; quota/
  concurrency event reserve fonksiyonunda; HTTP exception sonrası satır kalır.
- [x] **T216** Privacy tests: instructor student chat/not okuyamaz, admin-no-membership,
  cross-course/user; reservation/guard logs prompt/answer/source/IP/hash taşımaz.
- [x] **T217** Backend unit/integration/mutation: audience, session, cache,
  provider reservation, concurrency, output cap, exam dependency yolları,
  guard-event privacy, kill switch, chat-finalize/exam ve export/exam user lock.
  14 hedef test node'undaki 18 test önce yeşil; 12/12 mutasyon uygulandığında
  kırmızı, birebir restore sonrasında 12/12 hedef koşu yeşil ve geçici DB kalıntısı
  0. Fake-provider/local mekanik kanıtı final R4 evidence kaydına
  `.ai/evidence/005-role-aware-course-agent-application-mutations-final.json`
  olarak bağlandı; gerçek model kalitesini kanıtlamaz. — DONE 2026-08-15
- [x] **T218** `/me/export` exam start ile aynı user lock'u: active student EXAM
  423 `exam_export_locked`; forced interleaving, expired/practice ve instructor
  preview istisnaları. — DONE 2026-08-11

**P2 kapısı**: Hedefli pytest + ruff/format/mypy yeşil; kontroller kaldırılınca
ilgili test kırmızı; fake-provider kanıtının kalite olmadığı raporda açık.
Mevcut yerel tam paket kanıtı: taze hedefli 157/157, `apps/api/tests` 894/894,
ruff/format ve mypy 92 dosya temiz. Yeni uygulama guard dosyası ayrıca 11/11;
mutasyon baseline'ı 18/18 ve 12/12 uygulanan kırmızı/restore/yeşil turu temizdir.
Fake-provider kanıtı gerçek model kalitesi değildir.

---

## P3 — Next.js `CourseAssistant`

- [x] **T301** Type/helper'ları API contract ile hizala; audience/profile request
  body'ye hiç girmesin. — DONE 2026-08-11
- [x] **T302** Course nav'da floating ve dashboard course card'da inline
  `CourseAssistant`; her instance yalnız taşıyıcı course id'ye bağlı; login/
  admin-no-course yüzeyinde genel chat yok. — DONE 2026-08-11
- [x] **T303** Server-derived “Öğrenci çalışma koçu” / “Eğitmen yardımcısı” etiketi,
  source-only ve eylemsiz öneri metni; persona toggle yok. — DONE 2026-08-11
- [x] **T304** Drawer içinde mode/session continuation; course değişiminde session
  sıfırlama; full-page deep-link teslim edilmediyse acceptance sayma. — DONE 2026-08-11
- [x] **T305** Loading/empty/error/locked/abstention/rate/quota/concurrency/
  role-change/global-disabled durumları için ayrı Türkçe UX ve request_id support code.
  — DONE 2026-08-11
- [x] **T306** Availability gelmeden composer/session fetch yok; aynı course/
  dashboard verisi duplicate fetch edilmez. — DONE 2026-08-11
- [ ] **T307** 375px, dark, keyboard, dialog label, focus trap+return, screen reader
  ve reduced motion. Playwright 375 px + dark + reduced-motion bağlamında dialog
  adı/açıklaması, Tab/Shift+Tab focus trap'i, Escape sonrası tetikleyiciye odak
  dönüşü ve yatay taşmasız görünümü gerçek tarayıcıda doğruladı. Manuel
  VoiceOver+Safari gözlemi yapılmadığı için **PARTIAL**.
- [x] **T308** Vitest: student/instructor/mixed-role, course switch, no audience
  payload, 200/403/409/422/429/503, session continuation ve disabled composer.
  — frontend `bun test lib/` 325/325, 2026-08-11 <!-- docs-check: tarihsel 325 · 2026-08-11 -->
- [ ] **T309** Browser network: exam lock/direct API, kill switch, no prefetch,
  no duplicate request, console ve horizontal overflow. Playwright, drawer
  açılmadan availability isteği olmadığını; ilk açılışta tam 1 availability ve
  gönderimde tam 1 chat POST olduğunu, console/page error ve yatay taşma
  bulunmadığını doğruladı. Direct exam POST ve kill-switch tarayıcı yolları henüz
  otomatik koşulmadığı için **PARTIAL**.

**P3 kapısı**: `bun test`, typecheck, production build, hedefli seri Playwright ve
elle student/instructor/mobile/dark turu yeşil.

---

## P4 — Bütünleşik repo kanıtı ve AI-SDLC

- [x] **T401** Backend tam pytest, ruff/format/mypy; sayaçları docs_check kaynağına bırak.
  `pytest -q apps/api/tests` 894/894, ruff/format ve mypy 92 dosya temiz;
  repo-root çıplak pytest 005 dışı `scripts.*` import collection sorunu buldu.
  Backend kapsamı DONE 2026-08-15.
- [x] **T402** Taze DB tam migration + agent SQL/RLS/mutation paketi.
  `rls_role_aware_agent_mutation_check.sh`, izole PID DB'lerinde 0001..0015'i
  uyguladı; 8 kapalı sınır + 3 kota referansı geçti, 11/11 DB/RLS mutasyonu beklenen
  sızıntıyı yakaladı ve kalıntı DB 0 ölçüldü. Bu kanıt T217/T410'daki uygulama
  katmanı tam mutasyon matrisinin yerine geçmez. — DONE 2026-08-11
- [x] **T403** Frontend tam unit/typecheck/build. — 349/349 test, 30 test dosyası,
  typecheck ve production build temiz, 2026-08-15
- [x] **T404** Seri gerçek-API Playwright; koşu-önekli setup/teardown, kalıntı 0,
  protected `COME 331` yerinde. — DONE 2026-08-15: benzersiz PostgreSQL
  veritabanında 36/36 gerçek-API vaka tek worker ile geçti; teardown sonrası E2E
  ders/audit kalıntısı 0/0. Ayrı fail-closed temizlik kanıtında yalnız
  hedef ders/audit silindi; run desenine sokulan
  `c3b76077-20de-47e5-9fe1-4e770ffa64d2` UUID'li ders kaldı, kodu `COME 331`e
  geri getirildi ve geçici veritabanı trap ile kaldırıldı.
- [x] **T405** OpenAPI çalışan app'ten üret; request'te audience/agent_profile/
  max_tokens/user_id olmadığını ve response/policy exact alanlarını doğrula.
  — 50 path, 119 schema; ChatRequest dört onaylı alan, 2026-08-15
- [x] **T406** `docs_check`, `git diff --check`, migration order ve Speckit drift taraması.
  Tablo/migration/test sayaçları kaynağından doğrulandı; whitespace ve sözleşme
  taraması temiz. — DONE 2026-08-15
- [x] **T407** Offline/fake RAG eval: student Socratic, instructor grounded yardım,
  scope abstention, citation set-membership, poisoned source/leakage attack set.
  Dondurulmuş 7 sentetik vaka ağ kapalı ve DB'siz gerçek `produce_answer` hattında
  7/7 geçti: 3/3 cevaplı tur retrieved citation kümesinde kaldı, 1/1 normal kapsam
  dışı ve 2/2 cross-role probe provider çağrılmadan reddedildi, iki Sokratik turda
  kalıp sızıntısı 0, forged citation 1/1 fail-closed, poisoned source sınırı 1/1
  kaçırılmadı ve 4/4 role prompt sözleşmesi geçti. Bu yalnız fake-provider mekanik
  kanıtıdır; semantic claim entailment/citation faithfulness,
  gerçek model pedagojisi ve insan kabulü **KOŞULMADI**. Koşu, dirty working-tree
  overlay'inin `4d94bc6d72c85e85e6cfc6451d6f48a010a6789f` tabanını ve exact artefakt
  hash'lerini kaydetti. Temiz exact-candidate yeniden koşusu üretim davranış
  bağımlılıklarını exact hashlerle doğruladı ve
  `.ai/evidence/005-role-aware-course-agent-offline-fake-final.json` kaydını
  üretti. — DONE 2026-08-15
- [x] **T408** Multi-worker load: quota overshoot 0, concurrency/lease recovery,
  p95 latency/pool pressure ve cache-hit burst residual raporu. — DONE 2026-08-15:
  taze 15-migration PostgreSQL DB, hashing embedding, gecikmeli fake provider ve
  iki uvicorn worker ile gerçek HTTP koşusu geçti. Son kota dilimindeki 4 istekten
  1'i kabul/3'ü güvenli ret, max charge=budget=3201 ve overshoot=0; aynı kullanıcı
  concurrency yarışı diğer worker'da 1 kalıcı 429 + aynı worker'da 3 process-local
  409 verdi; tüm rakip istekler 409/429 ile reddedildi ve ölçülen aktif
  reservation tepesi 1'de kaldı. Provider 503 sonrası 200 toparlandı; sentetik
  terk edilmiş 4 s lease boyunca 429, expiry sonrası 200 oldu. İki derste 16/16
  cache-miss isteği geçti
  (p95 1659.16 ms, peak 18/22 bağlantı, 0 pool/transport/5xx); 64/64 cache-hit
  patlaması geçti (p95 493.73 ms, yeni reservation/charge=0). Koşu sırasında
  bulunan ana-havuz starvation'ı bounded 1+0 kontrol havuzu ve ana istek havuzunu
  tamamen doyuran regresyon testiyle kapandı; exact DB/storage/log cleanup kalıntısı 0.
  Kanıt: `evidence/t408-multiworker-local-v2.json`. Bu yerel fake/hash mekanik
  kanıtıdır; gerçek-provider kalitesi, staging/production kapasitesi ve SLO
  sertifikası **KOŞULMADI**.
- [x] **T409** 005 R4 dossier exact base/head, prompt/model/provider/retrieval/
  quota/output/flag revisions ve evidence hash'leriyle PASS.
  Append-only `main` entegrasyon kaydı; 894 backend, 349 frontend, 36 seri
  gerçek-API tarayıcı, 11/11 DB mutasyonu ve privacy/cascade kanıtını yeni rapor
  hash'ine bağlar.
  Fake-provider mekanik kanıtı PASS; real-provider/staging iddiaları açıkça
  `not_run`. Güncel kontrol-havuzu, UI hata/oturum düzeltmeleri ve yeni kanıtlar
  eski R3/karantina/Git geçmişi değiştirilmeden append-only R4 köküne bağlandı.
  Birleştirilmemiş çalışma ağacının birebir no-ref adayı `ebb422fc7d742a65bb817aa77009a05bded10f3b`
  için `main@2c178861a3e484af8643f999f210db040eb84e68 → aday`
  `AI_SDLC_CHECK=PASS`; gerçek final commit ve PR CI kapısı T703–T705'te açık.
  — DONE 2026-08-16
- [x] **T410** Uygulama mutasyon matrisi geçici kaynak kopyasında 12/12 kırmızı,
  restore sonrası 12/12 hedef koşu yeşil ve DB kalıntısı 0 olarak raporlandı.
  Kayıt yalnız sentetik fixture + fake provider kullanır, ham içerik tutmaz;
  kaynak/koşucu hash'leri
  `.ai/evidence/005-role-aware-course-agent-application-mutations-final.json`
  kaydına bağlandı.
  — DONE 2026-08-15

**P4 kapısı**: Repo adayı yerelde doğrulanmıştır. Gerçek provider/staging/deploy
olmadan “production” değildir.

---

## P5 — Korumalı staging, insan değerlendirmesi ve rollout

- [ ] **T501** Gerçek Supabase Auth/Storage ve staging 0015; student/instructor/
  mixed/admin RLS yolculukları. — KOŞULMADI
- [ ] **T502** Exact provider/model ile student ve instructor ayrı holdout/rubric;
  faithfulness, scope, leakage, token/tur. — KOŞULMADI
- [ ] **T503** Pedagoji/ürün ve güvenlik/operasyon için iki bağımsız isimli,
  immutable approval. — KOŞULMADI
- [ ] **T504** Normal staging'de `COURSE_AGENT_ENABLED=true`; ayrıca `false`
  emergency rollback provası: direct POST 503, provider 0, 0015 verisi korunur.
  Cohort canary ayrı deployment kontrolüdür. — KOŞULMADI
- [ ] **T505** Internal/eğitmen canary; sonra küçük öğrenci canary; stop eşiklerini
  izleyip go/stop kaydı yaz. — KOŞULMADI
- [ ] **T506** Leakage, exam bypass, quota overshoot veya rollback failure >0 ise
  flag kapat; eşik aşımı varsa aynı davranış. — KOŞULMADI
- [ ] **T507** Aday yalnız aynı SHA/revision/approval ile kademeli genişletilir;
  rollout/rollback dossier'a append-only eklenir. — KOŞULMADI

---

## P6 — Gelecek abuse hardening backlog'u (005 release kapısı değil)

Bu görevler ilk 005 uygulaması içinde DONE işaretlenmez:

- [ ] **F601** Request idempotency/replay key ve duplicate-provider-call sözleşmesi.
- [ ] **F602** Workerlar arası DB/Redis minute/request bucket.
- [ ] **F603** Adaptive strike/temporary backoff; false-positive/fairness ölçümü.
- [ ] **F604** Privacy onaylı prompt HMAC/fingerprint ve rotation/retention.
- [ ] **F605** IP/device/WAF/credential-stuffing edge koruması.
- [ ] **F606** Privacy-safe toplu operasyon paneli; bireysel prompt/ledger görünümü yok.

Her biri ayrı threat/privacy/R3 değişikliği ve acceptance/mutation kanıtı ister.

---

## P7 — Git/PR teslimi

- [x] **T701** Feature değişikliklerini küçük amaçlı commit'lerde topla; attribution
  ve branch sahipliğini koru. Backend, frontend, Speckit/docs ve R3 kanıtı ayrı
  amaçlı commit'lere ayrıldı. — DONE 2026-08-11
- [x] **T702** Branch'i push et; local HEAD = origin branch ölç.
  `005-role-aware-course-agent` origin'e gönderildi; local/origin eşitliği
  push sonrası ölçüldü. — DONE 2026-08-11
- [ ] **T703** Draft PR aç; required CI ve AI/security gates sonucunu gözle.
- [ ] **T704** CI, R3 approvals ve release verification yeşil olmadan main'e merge etme.
- [ ] **T705** Merge sonrası main SHA, migration, OpenAPI/docs ve deploy durumunu
  ayrı raporla; merge'i production ile karıştırma.

## Son rapor şablonu

```text
Kodlandı:
Yerelde doğrulandı:
Origin/PR/CI:
Staging:
Production:
KOŞULMADI:
Gelecek backlog:
Açık blocker/risk:
Rollback:
```
