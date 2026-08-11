# Tehdit Modeli: 005 Rol Farkındalıklı Ders Ajanı

**Scope**: authenticated student/instructor drawer, mevcut course chat/RAG,
session/cache, `0015` token reservation/guard ledger ve provider sınırı
**Risk**: R3
**Durum**: Backend/migration tam API 878/878, frontend unit/typecheck/build yeşil;
penetration, gerçek-provider, gerçek tarayıcı, çok-worker yükü ve canlı hosting
ayrıca kanıtlanmalıdır

## 1. Korunan varlıklar

1. Ders kaynakları, chunk metinleri ve citation provenance.
2. Öğrenci soru/deneme/sohbet geçmişi ve geri bildirimi.
3. Eğitmen course policy ve öğretim bağlamı.
4. Sınav bütünlüğü ve active exam lock.
5. Kullanıcı/course token bütçesi, provider kotası ve maliyet.
6. System/developer prompt, Auth/DB/provider secret'ları.
7. Course membership, audience, RLS, session/cache izolasyonu.
8. İçeriksiz quota/guard telemetry.
9. AI davranış artifact'ları, approval, rollout ve rollback kanıtı.

## 2. Aktörler

| Aktör | Meşru yetki | İzin verilmeyen hedef |
|---|---|---|
| Öğrenci | Üye olduğu derste kendi chat/session'ı | instructor profili, başka course/user, sınav yardımı |
| Eğitmen | Eğitmeni olduğu dersin kaynaklı/eğitmen odaklı önerisi | öğrenci özel sohbet/notu, write action, platform secret |
| Platform admin | Ayrı operasyonel yönetim yüzeyi | membership olmadan akademik ajan bağlamı |
| Kötü niyetli hesap | Normal authenticated istemci | maliyet tüketme, prompt/secret çıkarma, çapraz erişim |
| Kaynak yükleyen eğitmen | Course document yükleme | belge içi talimatla sistem promptunu geçersiz kılma |
| AI provider | Gönderilen sınırlı prompt/context'i işleme | gereksiz PII veya başka course context'i alma |
| Operatör | deploy/config/DB işletimi | denetimsiz bypass veya chat içeriğini loglama |

Unauthenticated botlar Auth/edge sınırındadır. 005 account/course katmanını
güçlendirir; WAF, credential stuffing veya dağıtık IP savunması değildir.

## 3. Güven sınırları

```text
Browser (untrusted body, route, session id)
  -> FastAPI auth + CourseMember/UnlockedCourseMember
  -> server-resolved AssistantAudience
  -> PostgreSQL RLS + SECURITY DEFINER quota functions
  -> approved-source retrieval + role prompt + guardrails
  -> provider (bounded max_tokens, no tools)
  -> citation/leakage/sanitize guard
  -> typed response
```

Yayın sınırı:

```text
Git/PR -> R3 dossier/evidence -> protected staging -> canary flag -> production
```

## 4. Tehditler, kontroller ve kanıtlar

| ID | Tehdit / abuse path | Etki | İlk 005 kontrolü | Must-pass kanıt |
|---|---|---|---|---|
| TM-01 | İstemci `audience=instructor` veya `agent_profile=instructor_assistant` yollar | Yetki yükseltme | İstek şemasında alan yok, extra-forbid, membership projection | payload injection 422 + projection mutasyonu |
| TM-02 | Student instructor session UUID'sini tekrarlar | Prompt/veri sızıntısı | self RLS + course/user/audience eşleşmesi | direct API + RLS test |
| TM-03 | Mixed-role kullanıcı A rolünü B dersine taşır | Çapraz rol | Audience her course için yeniden çözülür | A-instructor/B-student testi |
| TM-04 | Role değişince eski instructor session sürer | Kalıcı yetki | immutable stored audience + current mismatch 409 `session_audience_changed` | role-change mutasyonu |
| TM-05 | Instructor öğrenci sohbeti/notu ister | Mahremiyet | source setinde student chat yok, self-only RLS, eylemsiz prompt | instructor privacy testi |
| TM-06 | Platform admin membership olmadan ajanı kullanır | Yetki genişlemesi | adminlik audience üretmez | admin-no-membership testi |
| TM-07 | Chat provider'dayken ikinci sekmede sınav başlar | Sınav bütünlüğü | entry guard + exam start/chat finalize aynı user transaction lock'u; finalize öncesi recheck | forced interleaving: 403, response/session/message/cache artifact'i 0 |
| TM-08 | Kullanıcı system prompt/secret ister | Secret sızıntısı | system-owned role prompt, source-only RAG, leakage/sanitize guard, secret context'te yok | attack fixture + log/source scan |
| TM-09 | Kaynak belgesi “talimatları yok say” der | Dolaylı prompt injection | belge untrusted evidence, prompt hierarchy, no tools, output/citation guard | poisoned-document fixture |
| TM-10 | Model kaynaksız cevap uydurur | Hallucination | evidence threshold, retrieved chunk membership, no-source-no-answer | faithfulness/abstention test |
| TM-11 | Instructor cache cevabı student'a döner | Veri/pedagoji ihlali | explicit audience + three revisions unique identity + audience-matched SELECT/INSERT RLS | cache-key mutasyonu + direct SQL cross-audience SELECT reddi |
| TM-12 | Policy/source/prompt değişir, cache bayat kalır | Yanlış cevap | policy/prompt/corpus revision | revision-change test |
| TM-13 | Cache içine unsafe HTML gelir | Browser compromise | cached response guard + safe renderer | script fixture + UI test |
| TM-14 | Farklı course/worker aynı user veya platform son token dilimini alır | Bütçe aşımı | sabit platform-gün lock'u, sonra course lock'u + atomik reservation | cross-course global-user/platform race, overshoot 0 |
| TM-15 | Provider çağrısında süreç çöker | Kalıcı concurrency kilidi veya maliyetin ücretsiz sayılması | lease zorlanan tek-provider deadline+marjından uzun, SQL 30..600; expiry yalnız concurrency'yi bırakır, günlük reserved charge kalır | deadline üst sınır + injected expiry/clock/quota testi |
| TM-16 | Provider exception/cancellation/unknown usage olur | Maliyeti ücretsiz sayıp kota kaçırma | `finally` reserved tutarı korur; yalnız ölçülmüş başarı actual'a iner | exception/cancel/missing-usage testi |
| TM-17 | Aynı HTTP istek replay edilir | İkinci provider maliyeti | Bu dilimde idempotency yok; token quota/concurrency/burst hasarı sınırlar | residual risk olarak açık; gelecek backlog |
| TM-18 | Cache hit flood edilir | API/DB DoS | Cache öncesi process-local burst limiter | cache-hit rate testi; multi-worker residual |
| TM-19 | Uzun output maliyet/latency taşır | Maliyet/DoS | course `max_output_tokens` ile global cap'in min'i provider'a gider | provider spy + cap mutasyonu |
| TM-20 | Sıradan kapsam dışı soru saldırı sayılır | Kullanılabilirlik/adalet | `scope_refused` içeriksiz ölçüm, adaptif ceza yok | repeated scope refusal sonrası access sürer |
| TM-21 | Guard ledger prompt/IP/hash taşır | KVKK/mahremiyet | Sabit kolonsuz allowlist schema | migration/source/schema scan |
| TM-22 | SECURITY DEFINER caller user/audience parametresine güvenir | Yetki aşımı | `app.current_user_id()` + membership içeride; sabit search_path | direct-call SQL test |
| TM-23 | Yeni tablolara app/worker/Public erişir | Sayaç/ledger manipülasyonu | ENABLE RLS, policy yok, explicit REVOKE; yalnız dar definer owner yolu | grant/RLS mutasyonu ve direct SQL red |
| TM-24 | 429 exception ana transaction'ı rollback eder | Kör nokta | Reserve/reject ve record ayrı kısa RLS transaction | rejected-event persistence testi |
| TM-25 | LLM çağrısı DB lock açıkken bekler | Pool starvation | Reservation transaction provider öncesi kapanır | instrumentation/concurrency testi |
| TM-26 | Provider raporu reserve tahminini aşar veya reconcile düşer | Eksik accounting/cevabı maskeleme | actual>reserved DB'de reddedilir; best-effort wrapper cevabı korur ve full reserved charge yerinde kalır | overage + injected reconcile failure testi |
| TM-27 | Agent tool/write action çağırır | Akademik kayıt değişimi | Tool schema/action endpoint yok; prompt sözleşmesi eylemsiz | no-tool source/contract scan |
| TM-28 | Kill switch yalnız UI'da uygulanır | Acil durdurma bypass | POST 503 `course_agent_disabled`, availability disabled | flag-off direct API + provider-spy 0 |
| TM-29 | Model/prompt/quota değişikliği doğrudan production'a çıkar | AI regression | R3 dossier, two approvals, canary, rollback | AI gate negatif testi |
| TM-30 | UI availability öncesi composer gösterir | Geçici bypass/yanlış UX | availability-first rendering | browser network assertion |
| TM-31 | Aynı process'te aynı kullanıcı/ders iki provider işi açar | Maliyet/yarış | süreç-içi concurrency gate 409 `concurrent_request`; worker'lar arası kalıcı reservation ayrıca 429 verir | local-gate mutasyonu + two-worker reservation yarışı |
| TM-32 | Eğitmen bütçeyi veya operator config'i aşırı yükseltir | Deployment maliyet tavanı aşılır | DB course-user/global-user/course/platform enforcement + 50k/200k/500k/5m ceiling | policy-high + üç hard-cap validation/race testi |
| TM-33 | Aktif sınavda `/me/export` eski kaynaklı cevapları indirir | Sınav yardım bypass'ı | exam start/export aynı user lock'u; any active student EXAM 423 `exam_export_locked` | export/exam forced interleaving + expired/practice/instructor istisnası |
| TM-34 | Provider hatasındaki veya başka öğrencideki charge yalnız reservation'da kalır, UI/precheck düşük gösterir | Yanıltıcı ders bütçesi/fail-open ön kontrol | `course_tokens_today` atomik ledger'da dersin bütün kullanıcılarının `charged_tokens` toplamını okur | provider-error ve iki-kullanıcılı course-budget görünürlük testi |

## 5. Kritik abuse akışları

### 5.1 Audience spoof ve session replay

1. Öğrenci request'e `audience=instructor` ekler; Pydantic 422 üretir.
2. Alan kaldırılıp başka kullanıcının session UUID'si verilirse RLS gizler.
3. Aynı user'ın role-change sonrası eski session'ı bulunabilse bile stored
   audience güncel audience ile uyuşmaz ve 409 `session_audience_changed` olur.
4. Instructor prompt/cache hiçbir aşamada student isteğine uygulanmaz.

### 5.2 Prompt injection ve secret istemi

1. Soru ürün chat mesajı olarak işlenir; quota/guard ledger'a yazılmaz.
2. Kaynak metni “komut” değil untrusted evidence olarak prompta girer.
3. System-owned role prompt source-only/no-tool/no-write sınırını taşır.
4. Citation, leakage ve sanitize guard yalnız retrieved kaynakları kabul eder.
5. `out_of_scope` yalnız içeriksiz `scope_refused` event'i üretir; adaptive
   strike/backoff veya prompt fingerprint üretmez.

İlk 005, bütün jailbreak çeşitlerini yakalayan yeni bir pre-retrieval classifier
iddiasında bulunmaz. Böyle bir kontrol ayrı ölçüm, privacy kararı ve R3 değişikliği ister.

### 5.3 Multi-worker quota yarışı

1. Her API isteği yeni reservation UUID'siyle reserve fonksiyonunu çağırır.
2. DB önce sabit platform-gün, sonra course transaction lock'u ile kararları sıralar.
3. Active reservation concurrency, course-user-day, global-user-day, course-day ve
   platform-day token toplamı aynı snapshot içinde okunur.
4. Yalnız uygun istek reservation oluşturur; red kendi içeriksiz event'ini yazar.
5. Transaction kapanınca provider çağrılır; sonuç ayrı reconcile işlemine gider.

### 5.4 Cache flood

1. Process-local sliding limiter cache lookup'tan önce çalışır.
2. Reddedilirse `rate_limited` event'i ayrı kısa transaction'da yazılır.
3. Cache hit provider/token reservation açmaz ve `cached=true` ölçülür.
4. Birden fazla worker arasında birleşik request/minute limiti yoktur; canlı edge
   koruması ve gelecekte DB/Redis bucket ayrı backlog'dur.

### 5.5 Sınav başlatma, chat finalizasyonu ve export yarışı

1. Üç yol aynı user-wide (`seed=15018`) transaction lock'unu alır.
2. Chat, provider dönüşünden sonra kendi dersi için active EXAM'i tekrar kontrol
   eder; exam önce commit etmişse 403 yükselir ve bu request'in chat artifact'leri
   rollback olur.
3. Export, kullanıcının tüm derslerinde aktif student EXAM arar; bulursa 423
   `exam_export_locked` döner. Practice/expired ve instructor preview açıktır.
4. Chat/export önce kilidi almışsa exam start transaction bitene kadar bekler;
   exam önce almışsa chat/export yeni durumu görür. Güvenlik zamanlamaya bırakılmaz.

## 6. Gizlilik tasarımı

### Ürün içeriği

Chat mesajları mevcut self-only modelde kalır. 005 bunları instructor veya
platform admine açmaz. Export hakkı korunur fakat kaynaklı cevap sızıntısını
önlemek için aktif student EXAM süresince 423 ile geçici geciktirilir.

### İçeriksiz mekanik veri

`ai_token_reservations` token/zaman/scope; `ai_guard_events` yalnız
`rate_limited|quota_exhausted|concurrency_limited|scope_refused` taşır.
Serbest metin, question, answer, citation, e-posta, IP, header, device veya prompt
hash/HMAC alanı yoktur. Direct human-facing SELECT/list endpoint'i yoktur.

Retention süresi/job'ı ilk migration'da tamamlanmış değildir. Privacy/operations
sahibi süreyi ve cleanup kanıtını production öncesi kayda bağlar.

## 7. Güvenlik invariantları

1. Audience current active course membership projection'ıdır.
2. No course membership = no agent; platform admin olsa bile.
3. Session audience immutable; güncel audience uyuşmazsa continuation yok.
4. Cache audience/revision dışına taşmaz.
5. Kaynak/kanıt yoksa akademik cevap yok.
6. Active real exam = answer-bearing assistant veya sourced privacy export yolu yok.
7. Cache miss'te reservation yoksa provider çağrısı yok.
8. Provider çağrısı effective output cap'i aşmaz.
9. Quota/guard kaydı serbest metin taşımaz.
10. Kill switch kapalıysa direct POST provider'a gitmez.
11. AI davranışı exact R3 evidence ve rollback olmadan production'a yükselmez.
12. Exam start/chat finalize/export user-wide lock dışında yarışamaz.

Her invariant için pozitif, negatif ve ilgili kontrol kaldırılınca kırmızı mutasyon
kanıtı gerekir.

## 8. Rollout stop koşulları

Canary öncesi exact eşik ve sahip dossier'da yazılır. Şunlar koşulsuz stop'tur:

- herhangi bir cross-course/cross-user/audience leakage;
- system prompt/secret leakage > 0;
- exam lock bypass > 0;
- active exam export bypass > 0;
- DB quota overshoot > 0;
- reservation recovery başarısızlığı > 0;
- feature flag kapalıyken provider çağrısı > 0.

Önceden belirlenmiş eşik aşımı da stop üretir:

- citation faithfulness/scope precision;
- p95 latency ve provider error budget;
- token/tur ve toplam maliyet;
- 429/refusal oranı;
- öğrenci/eğitmen rubric ve kullanıcı geri bildirimi.

Stop halinde `COURSE_AGENT_ENABLED=false`; 0015 şeması silinmez. Unreconciled
reservation'lar lease sona erince aktif concurrency'den düşer; gün içi reserved
charge quota muhasebesinde kalır.

## 9. Açık residual risk ve gelecek kontroller

İlk 005'te uygulanmış sayılmaz:

- request idempotency/replay key;
- DB-backed workerlar arası minute/request bucket;
- adaptive strike/temporary backoff;
- prompt HMAC/fingerprint;
- IP/device/WAF/credential-stuffing koruması;
- bireysel usage/abuse admin ekranı.

Bu nedenle credential çalınmış veya dağıtık hesap/IP saldırısı token bütçesine
kadar kaynak tüketebilir. Process-local burst limiter workerlar arasında birleşmez.
Canlı hosting edge/auth koruması ayrıca gerekir.

Diğer residual riskler:

- Prompt hierarchy ve deterministic guardrails tüm jailbreak varyantlarını garanti etmez.
- Provider data retention/region sözleşmesi repo testiyle kanıtlanamaz.
- Hash advisory-lock collision güvenliği bozmaz ama quota veya user-wide assessment
  işlemlerini gereksiz serileştirebilir.
- Retention job'ı yokken içeriksiz guard/reservation satırları büyüyebilir.
- Feature flag rollback şemayı kaldırmaz; bu bilinçli forward-compatible karardır.

Her risk production dossier'ında owner, tarih, kanıt veya açık kabul kararı taşır.
