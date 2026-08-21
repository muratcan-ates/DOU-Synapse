# API Sözleşmesi: 005 Rol Farkındalıklı Ders Ajanı

**Base URL**: mevcut API kökü
**Auth**: `Authorization: Bearer <token>`
**Course scope**: active membership + RLS
**Hata zarfı**: `{"error":{"code","message","request_id"}}`

005 ayrı bir `/agent` backend'i açmaz. Küçük ders asistanı ve tam sayfa sohbet,
mevcut course-scoped chat uçlarını kullanır. Aşağıdaki alanlar feature dalındaki
Python şemaları ve `0015_role_aware_course_agent.sql` ile hizalıdır; henüz
sunulmayan usage/backoff alanları sözleşmeye eklenmez.

## 1. Kimlik sözleşmesi

İstemci audience veya persona göndermez. Sunucu her ders için active membership
rolünü çözer:

```text
membership student    -> audience student    -> agent_profile student_coach
membership instructor -> audience instructor -> agent_profile instructor_assistant
```

`audience` yetki bağlamıdır. `agent_profile` yalnız görünür davranış/etiket adıdır;
ek DB yetkisi vermez. Platform adminlik course membership üretmez. localStorage,
route, UI etiketi, request body/query/header veya önceki ders oturumu karar girdisi
değildir. `ChatRequest.extra="forbid"` bu sınırı zorlar.

## 2. `POST /courses/{course_id}/chat`

### İstek — değişmedi

```json
{
  "question": "Deadlock için gerekli koşullar nelerdir?",
  "mode": "socratic",
  "session_id": null,
  "student_attempt": "Karşılıklı dışlama olabilir."
}
```

Kurallar:

- `audience`, `agent_profile`, `system_prompt`, `max_tokens`, `tools`, `quota`,
  `model`, `provider` veya `user_id` alanı 422 olur.
- `question` trim sonrası 3..2000 karakterdir.
- `mode=exam` bu cevap/ipucu ucunda 422 olur.
- `session_id` varsa course, current user, mode ve stored audience doğrulanır.
- `COURSE_AGENT_ENABLED=false` ise POST 503 `course_agent_disabled` döner;
  frontend availability üzerinden composer çizmez. Ayarın varsayılanı `true`dır;
  bu bütün mevcut `/chat` yolunu durduran emergency kill switch'tir, cohort seçmez.

### 200 cevap veya abstention

```json
{
  "session_id": "11111111-1111-1111-1111-111111111111",
  "message_id": "22222222-2222-2222-2222-222222222222",
  "status": "answered",
  "mode": "socratic",
  "answer": "Önce kaynağın paylaşılamama koşulunu düşün.",
  "citations": [
    {
      "chunk_id": "33333333-3333-3333-3333-333333333333",
      "claim": "Karşılıklı dışlama",
      "file_name": "week-7.pdf",
      "location": "Sayfa 12",
      "snippet": "..."
    }
  ],
  "hints": [],
  "socratic_stage": "concept_hint",
  "cached": false,
  "audience": "student",
  "agent_profile": "student_coach"
}
```

005'in geriye uyumlu yeni alanları yalnız `audience` ve `agent_profile`'dır.
`status`, mevcut `answered|insufficient_context|out_of_scope|budget_exhausted`
değerlerinden biridir. Abstention hata değildir ve 200 zarfını korur. API bu
dilimde kalan token/request sayısını, provider/model adını veya guard ayrıntısını
döndürmez; frontend bunları tahmin etmez.

### Hata matrisi

| HTTP | code | Anlam |
|---:|---|---|
| 401 | `unauthenticated` | Geçerli kimlik yok |
| 403 | `exam_in_progress` | Öğrencinin gerçek sınav kilidi aktif |
| 403/404 | mevcut membership/RLS kodu | Course erişimi yok |
| 422 | `validation_error` | Yasak alan, kısa/boş soru veya `exam` modu |
| 409 | `session_audience_changed` | Stored session audience güncel role uymuyor |
| 409 | `concurrent_request` | Aynı API sürecinde aynı kullanıcı/ders için önceki agent isteği sürüyor |
| 429 | `rate_limited` | Process-local burst sınırı |
| 429 | `agent_concurrency_limited` | Kalıcı aktif reservation sınırı |
| 429 | `agent_quota_exhausted` | Kullanıcı/course günlük token bütçesi |
| 503 | `course_agent_disabled` | Global kill switch kapalı |

429 yanıtları tek hata zarfını taşır ve sayısal bekleme süresini `Retry-After`
header'ında verir. Body'de bu dilime ait `retry_after_seconds` alanı yoktur.
`concurrent_request` süreç-içi hızlı kapıdır; worker'lar arası otorite olan kalıcı
reservation reddinden (`agent_concurrency_limited`) ayrı tutulur.

### Cache ve muhasebe

- Process-local burst sınırı cache lookup'tan önce çalışır.
- Cache hit provider/token reservation açmaz; request log `cached=true` olur.
- Cache identity `course_id + audience + policy_revision + prompt_revision +
  corpus_revision + question_hash` sözleşmesine bağlıdır.
- Başka audience/revision satırına fallback yapılmaz.
- Request idempotency key bu sözleşmede yoktur; her HTTP çağrısı yeni reservation
  UUID'si üretebilir.

## 3. `GET /courses/{course_id}/chat/availability`

Bu uç `CourseMemberDep` ile kilitliyken de erişilebilir. Tam response:

```json
{
  "available": true,
  "reason": null,
  "message": null,
  "allowed_modes": ["qa", "socratic"],
  "hint_limit": 3,
  "audience": "instructor",
  "agent_profile": "instructor_assistant"
}
```

Kill switch örneği:

```json
{
  "available": false,
  "reason": "globally_disabled",
  "message": "Ders asistanı şu anda bakım nedeniyle kullanıma kapalı.",
  "allowed_modes": [],
  "hint_limit": 3,
  "audience": "student",
  "agent_profile": "student_coach"
}
```

Öğrenci için diğer `reason` değerleri mevcut sınav kilidi ve
`policy_all_modes_closed` olabilir. Response'ta `default_mode`, `agent`, usage,
limit veya `can_take_actions` nesnesi yoktur. UI allowed modes içinden seçim yapar;
kimliği veya policy'yi kendisi yeniden çözmez.

## 4. Session zarfları

### `GET /courses/{course_id}/chat/sessions`

Mevcut `PageOut` zarfını korur:

```json
{
  "items": [
    {
      "id": "11111111-1111-1111-1111-111111111111",
      "course_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      "mode": "qa",
      "audience": "instructor",
      "agent_profile": "instructor_assistant",
      "title": "Deadlock anlatımı",
      "socratic_stage": null,
      "created_at": "2026-08-11T09:55:00Z",
      "updated_at": "2026-08-11T10:00:00Z"
    }
  ],
  "next_cursor": null
}
```

Liste RLS altında current user + course satırlarını okur; her satır kendi stored
audience/profile alanını taşır. Role değişen kullanıcı kendi eski oturum
geçmişini görebilir fakat POST continuation güncel role uymayan session'ı 409 ile
reddeder. Yeni session her zaman current audience ile açılır.

### `GET /courses/{course_id}/chat/sessions/{session_id}`

Mesaj geçmişi mevcut `PageOut[ChatMessageOut]` zarfını korur. Oturum current
user/course'a ait değilse RLS gizler. Kendi legacy/role-change geçmişini okumak
continuation yetkisi vermez; aynı `session_id` POST'a verilirse güncel audience
eşleşmesi ayrıca zorlanır.

### Silme

Mevcut self-delete/privacy davranışı korunur. 005 öğretmen veya platform admine
başka kullanıcının chat içeriğini okuma/silme yetkisi vermez.

### `GET /me/export` sınav bütünlüğü

Bu mevcut privacy ucu önceki kaynaklı asistan cevaplarını da taşır. Sınav
başlatma ve chat finalizasyonuyla aynı kullanıcı düzeyi transaction advisory
kilidini alır.

| Durum | Sonuç |
|---|---|
| Herhangi bir derste aktif student EXAM | 423 `exam_export_locked` |
| Practice veya süresi dolmuş EXAM | Mevcut 200 export |
| Instructor exam preview | Mevcut 200 export |

423, aynı `{"error":{"code","message","request_id"}}` zarfını kullanır. Hak
silinmez; aktif sınav bittikten sonra tekrar denenir. Forced-interleaving
sözleşmesi: export kilidi önce alırsa transaction bittikten sonra sınav başlar;
sınav önce commit ederse export 423 görür.

## 5. Course AI policy

`GET/PUT /courses/{course_id}/ai-policy` mevcut alanları korur ve şu dört alanı
ekler:

```json
{
  "allowed_modes": ["qa", "socratic"],
  "hint_limit": 3,
  "evidence_threshold": 0.35,
  "daily_llm_budget": 100000,
  "source_document_ids": null,
  "student_daily_token_budget": 12000,
  "instructor_daily_token_budget": 40000,
  "max_output_tokens": 700,
  "max_concurrent_requests": 1
}
```

Validation:

| Alan | Aralık/default |
|---|---|
| `student_daily_token_budget` | 256..1,000,000; default 12,000 |
| `instructor_daily_token_budget` | 256..1,000,000; default 40,000 |
| `max_output_tokens` | 64..4096; default 700 |
| `max_concurrent_requests` | 1..4; default 1 |

Yalnız course instructor PUT yapabilir. `effective` response'u aynı dört çözülmüş
alanı ve mevcut policy alanlarını taşır. `max_output_tokens`, provider çağrısında
global `llm_chat_max_tokens` ile `min()` alınır. Bu dilimde audience başına ayrı
output/concurrency, daily request veya adaptive backoff policy alanı yoktur.

Operator-owned ve instructor policy API'sine açılmayan deployment tavanları:

```text
COURSE_AGENT_STUDENT_DAILY_HARD_LIMIT=50000
COURSE_AGENT_INSTRUCTOR_DAILY_HARD_LIMIT=200000
COURSE_AGENT_COURSE_DAILY_HARD_LIMIT=500000
COURSE_AGENT_PLATFORM_DAILY_HARD_LIMIT=5000000
```

Ders içi user/day bütçesi ilgili audience course policy'sidir. Cross-course
global user/day, course aggregate/day ve platform aggregate/day operator-owned
tavanlardır; eğitmen bunları request/policy ile yükseltemez. DB student,
instructor, course ve platform için 50000/200000/500000/5000000 ceiling'lerini zorlar.

## 6. İç quota fonksiyonları

Public HTTP API değildir:

```text
app.reserve_course_agent_tokens(
  course_id, reservation_id, requested_tokens, lease_seconds,
  user_hard_limit, course_hard_limit, platform_hard_limit
)
  -> (allowed, reason, audience, retry_after_seconds, reservation_id)

app.reconcile_course_agent_tokens(reservation_id, actual_tokens) -> void

app.record_course_agent_guard_event(course_id, event_type) -> void

app.course_tokens_today(course_id) -> bigint
```

Kurallar:

- Fonksiyonlar `app.current_user_id()` ve active membership'i içeride yeniden çözer;
  `user_id` veya audience parametresi kabul etmez.
- Reserve önce sabit platform-gün (`seed=15015`), sonra course (`seed=15016`)
  advisory transaction lock'u alır. Course-user, global-user, course ve platform
  toplamları ile concurrency kararını atomik verir; provider I/O sırasında DB
  lock/transaction tutulmaz.
- `lease_seconds` SQL'de `30..600` aralığındadır ve HTTP katmanında zorlanan
  provider deadline'ından uzun bir reconciliation marjıyla hesaplanır.
- `user_hard_limit` SQL'de `1..1000000`, `course_hard_limit` `1..500000`,
  `platform_hard_limit` `1..5000000` aralığında doğrulanır. DB user limitini
  server-resolved audience'ın 50000/200000 ceiling'ine; course/platform limitini
  500000/5000000 ceiling'ine bağlar. HTTP katmanı üç limiti operator ayarından
  verir; istemci göndermez.
- Quota/concurrency reddini reserve fonksiyonu doğrudan event ledger'a yazar.
- `course_tokens_today`, legacy `request_logs` yerine dersin bütün kullanıcıları
  için aynı atomik reservation ledger'ının `charged_tokens` toplamını döndürür;
  provider hatasında kalan full precharge ders bütçesi göstergesinden kaybolmaz.
  Kullanıcı tavanı ayrıca reserve fonksiyonunda tüm dersler üzerinden uygulanır.
- `record_course_agent_guard_event` HTTP katmanından yalnız
  `rate_limited|scope_refused` kabul eder.
- Reconcile aynı reservation'da yalnız ilk güncellemeyi uygular; ölçülmüş başarı
  actual kullanımı, provider hatası/iptal/bilinmeyen usage ise reserved tutarı
  gönderir. `actual > reserved` DB'de reddedilir ve reserved charge korunur.
  Wrapper best-effort'tur: reconcile hatası kullanıcıya üretilmiş cevabı
  maskelemez. Bu request-level replay/idempotency sözleşmesi değildir.

## 7. Frontend sözleşmesi

`CourseAssistant`:

- Yeni backend endpoint tanımlamaz.
- Kimliği `availability.audience/agent_profile` alanlarından gösterir; persona
  toggle'ı yoktur.
- Availability gelmeden composer/session isteği çıkarmaz.
- Global disabled, policy closed veya exam lock durumunda composer çizmez.
- Tam sayfa ile aynı session/chat endpoint ve şemalarını kullanır; drawer-to-
  full-page deep-link ilk 005 sözleşmesinde vaat edilmez.
- Agentin öneri verdiğini, tool/write action yapmadığını kullanıcıya açıklar.
- 200 abstention ile 403/409/422/429/503 hata durumlarını ayrı Türkçe UX olarak gösterir.
- API'de olmayan remaining usage veya adaptive backoff sayısı uydurmaz.

## 8. Gizlilik ve telemetry

Kalıcı `ai_guard_events` yalnız şunları saklar:

```text
id, course_id, user_id, audience,
event_type(rate_limited|quota_exhausted|concurrency_limited|scope_refused), created_at
```

`ai_token_reservations` yalnız UUID kapsamları, audience, token sayıları ve
zamanları taşır. Şunlar bu tablolarda/loglarda yasaktır:

```text
question, answer, source text, citation snippet, system prompt, secret, JWT,
email, IP, user-agent, device id, raw prompt hash veya HMAC fingerprint
```

Normal kullanıcı, instructor, platform admin, `dou_worker` ve Public için yeni
tablolara doğrudan SELECT/UPDATE/DELETE grant'i yoktur. Bireysel abuse ledger
veya usage ekranı 005'in ürün sözleşmesi değildir.

## 9. Açık gelecek backlog'u

Aşağıdakiler 005'in must-pass API sözleşmesi değildir:

- request idempotency/replay key;
- DB-backed minute/request bucket;
- adaptive strike/temporary backoff;
- prompt HMAC/fingerprint;
- IP/device/WAF katmanı;
- kullanıcıya remaining quota özeti;
- bireysel kullanım/abuse admin ekranı.

Eklenmeleri ayrı privacy/threat/spec ve geriye uyumlu contract değişikliği ister.
