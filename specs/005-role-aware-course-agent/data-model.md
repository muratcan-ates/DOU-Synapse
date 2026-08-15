# Veri Modeli: 005 Rol Farkındalıklı Ders Ajanı

**Migration**: `0015_role_aware_course_agent.sql`
**Durum**: `0015` ve backend feature dalında kodlandı; taze hedefli paket 157/157,
tam API paketi son adayda 894/894. T113 export/cascade sözleşmesi benzersiz gerçek
PostgreSQL DB'sinde 13/13 doğrulandı. Canlı retention, provider ve staging kanıtı yok.

## 1. Modelleme ilkeleri

1. `audience`, istemci personası değil active course membership rolünün projection'ıdır.
2. `agent_profile`, audience'dan türetilen sunum/davranış adıdır; DB yetkisi değildir.
3. Session/cache audience'ı açık kolonla taşır.
4. Token maliyeti provider çağrısından önce kalıcı reservation ile charge edilir.
5. Guard telemetry serbest metin içermez.
6. Quota/guard tabloları function-only'dir; normal roller doğrudan okuyamaz.

## 2. `assistant_audience`

```sql
CREATE TYPE assistant_audience AS ENUM ('student', 'instructor');
```

Sunucu projection'ı:

```text
membership student    -> audience student    -> agent_profile student_coach
membership instructor -> audience instructor -> agent_profile instructor_assistant
platform admin        -> projection yok; course membership ayrıca gerekir
```

`agent_profile` DB enum'u değildir. Python/TypeScript, server `audience` değerinden
yalnız şu iki sabit değeri üretir; istemci rol seçemez.

## 3. Mevcut tablo değişiklikleri

### 3.1 `chat_sessions.audience`

| Alan | Tip | Kural |
|---|---|---|
| `audience` | `assistant_audience` | NOT NULL, session ömründe immutable |

Migration:

1. Nullable kolon ekler.
2. Aynı `(course_id,user_id)` active membership varsa role göre backfill eder.
3. Eşleşmeyen legacy satırı fail-closed `student` yapar.
4. NOT NULL yapar.
5. `BEFORE UPDATE OF audience` trigger'ı değişikliği `23514` ile reddeder.

Yeni session insert'inde uygulama audience'ı açıkça yazar. Request body'de matching
alan yoktur. Güncel membership audience'ı stored audience ile uyuşmazsa API session'ı
sürdürmez.

### 3.2 `answer_cache`

| Alan | Tip | Başlangıç/backfill |
|---|---|---|
| `audience` | `assistant_audience` | NOT NULL DEFAULT `student` |
| `policy_revision` | text | NOT NULL DEFAULT `legacy` |
| `prompt_revision` | text | NOT NULL DEFAULT `legacy` |
| `corpus_revision` | text | NOT NULL DEFAULT `legacy` |

Yeni unique identity:

```text
(course_id, audience, policy_revision, prompt_revision,
 corpus_revision, question_hash)
```

`question_hash` mode + normalize soru hash'idir. Audience yalnız hash içine
saklanmaz; explicit kolon ve unique key çapraz profil cache'ini şemada engeller.

### 3.3 `course_ai_policies`

| Alan | Tip | DB default | Constraint |
|---|---|---:|---|
| `student_daily_token_budget` | integer | 12000 | >0 |
| `instructor_daily_token_budget` | integer | 40000 | >0 |
| `max_output_tokens` | integer | 700 | 64..4096 |
| `max_concurrent_requests` | smallint | 1 | 1..4 |

Mevcut DB `daily_token_budget` (API'de `daily_llm_budget`) course toplam günlük sınırıdır. Yeni student/instructor
alanları aynı course içinde kullanıcı başına günlük sınırdır. `max_output_tokens`
iki audience için ortak course policy değeridir ve ayrıca global
`llm_chat_max_tokens` ile `min()` alınır.

Deployment ayrıca API ayarlarında `course_agent_student_daily_hard_limit=50000`
`course_agent_instructor_daily_hard_limit=200000` ve
`course_agent_course_daily_hard_limit=500000` ve
`course_agent_platform_daily_hard_limit=5000000` varsayılan tavanlarını taşır.
Reserve fonksiyonu ders içi kullanıcı policy'sini; cross-course global kullanıcı,
ders toplam ve platform toplam hard cap'lerini birlikte uygular. Course instructor
bu tavanları policy PUT ile yükseltemez. DB yanlış deployment config'ini de
fail-closed reddeder: student 50000, instructor 200000, course 500000 ve platform
5000000 mutlak ceiling'dir.

Policy satırı yoksa service aynı güvenli repo varsayılanlarını çözer. Bu değerlerin
tek davranış kaynağı migration + policy service testleriyle drift'e karşı çivilenir.
Mevcut audit trigger yeni alanların before/after değerlerini de kaydeder.

## 4. `ai_token_reservations`

Provider I/O dışında commit edilen kalıcı charge/lease tablosu:

| Alan | Tip | Kural |
|---|---|---|
| `id` | uuid PK | API service tarafından yeni reservation UUID |
| `course_id` | uuid FK courses | ON DELETE CASCADE |
| `user_id` | uuid FK profiles | ON DELETE CASCADE |
| `audience` | `assistant_audience` | DB membership'ten çözer |
| `reserved_tokens` | integer | >0; ilk worst-case estimate |
| `charged_tokens` | integer | >=0; başlangıçta reserved, reconcile sonrası actual |
| `created_at` | timestamptz | now() |
| `expires_at` | timestamptz | created_at'tan sonra; API'nin doğrulanmış deadline+marj lease'i |
| `reconciled_at` | timestamptz nullable | ilk reconcile zamanı |

İndeksler:

```text
ai_token_reservations_course_day_idx         (course_id, created_at)
ai_token_reservations_user_day_idx           (course_id, user_id, created_at)
ai_token_reservations_global_user_day_idx    (user_id, created_at)
ai_token_reservations_platform_day_idx       (created_at)
```

Günlük quota hesabı `Europe/Istanbul` gün sınırında:

```text
created_at bugünün aralığındaysa charged_tokens her durumda sayılır
active concurrency ise yalnız reconciled_at IS NULL AND expires_at > now()
```

Böylece:

- provider öncesi worst-case charge quota'yı korur;
- başarılı çağrı gerçek tokenla reconcile edilir;
- provider exception/cancellation/bilinmeyen usage rezerve edilen tutarla reconcile
  edilir; bilinmeyen maliyet ücretsiz sayılmaz;
- süreç tamamen çökerse süresi geçen unreconciled satır yalnız aktif concurrency
  hesabından düşer; reserved charge gün sonuna kadar course-user/global-user/course/
  platform quota toplamlarında kalır;
- geçmiş satır silinmez; geç reconcile ilk-yazma kuralıyla gerçek charge'a inebilir.

Bu dilim request-level idempotency key sözleşmesi sunmaz. `id` benzersiz reservation
kimliğidir; her yeni HTTP çağrısı yeni UUID üretir. Replay/idempotency ayrı gelecek
özelliğidir. Reconcile yalnız `reconciled_at IS NULL` satırı güncellediği için ilk
uzlaştırma kazanır; sonraki çağrı charge'ı değiştirmez.

## 5. `ai_guard_events`

İçeriksiz kalıcı kontrol olayı:

| Alan | Tip | Kural |
|---|---|---|
| `id` | uuid PK | generated |
| `course_id` | uuid FK | ON DELETE CASCADE |
| `user_id` | uuid FK | ON DELETE CASCADE; yalnız enforcement/operasyon |
| `audience` | assistant_audience | DB membership'ten çözer |
| `event_type` | text | allowlist CHECK |
| `created_at` | timestamptz | now() |

Allowlist:

```text
rate_limited
quota_exhausted
concurrency_limited
scope_refused
```

Serbest `details`, question, answer, citation/source, IP, header, user-agent,
prompt hash/fingerprint veya e-posta kolonu yoktur. Event bu dilimde adaptif
strike/backoff üretmez; `scope_refused` ölçüm olması dışında ceza değildir.

Retention job/policy ilk migration'da uygulanmış sayılmaz. Canlı ortam saklama
süresi ürün/privacy sahibiyle belirlenip ayrı audit-visible operasyon görevi olarak kalır.

## 6. SECURITY DEFINER fonksiyonları

### 6.1 `app.course_tokens_today(course_id)`

- Current user'ın aktif course membership'ini fonksiyon içinde doğrular.
- `request_logs` yerine Europe/Istanbul gün sınırında dersin bütün kullanıcıları
  için `ai_token_reservations.charged_tokens` toplamını döndürür.
- Provider hatasında reconcile edilmemiş tam ön charge ders bütçesi göstergesinde
  ve mevcut precheck'te görünür. Global kullanıcı tavanı ayrıca reserve
  fonksiyonunda kullanıcının bütün dersleri üzerinden uygulanır.
- Public ve `dou_worker` execute yetkisi yoktur; `dou_app` dar execute alır.

### 6.2 `app.reserve_course_agent_tokens(course_id, reservation_id, requested_tokens, lease_seconds, user_hard_limit, course_hard_limit, platform_hard_limit)`

`RETURNS TABLE(allowed, reason, audience, retry_after_seconds, reservation_id)`.

Fonksiyon:

1. `requested_tokens` değerini `1..100000`, `lease_seconds` değerini `30..600`,
   `user_hard_limit` değerini `1..1000000`, `course_hard_limit` değerini
   `1..500000`, `platform_hard_limit` değerini `1..5000000` ile sınar; prompt
   gövdesi kabul etmez.
2. `app.current_user_id()` ve active membership'i kendisi çözer; user/audience parametresi yoktur.
3. Membership role'den `assistant_audience` üretir.
4. Course policy veya 12000/40000/1 güvenli varsayılanlarını okur. Ders içi
   kullanıcı bütçesi policy'dir; global kullanıcı, ders toplam ve platform toplam
   sınırları yalnız operator-owned hard cap'lerden gelir. User/course/platform
   tavanı DB ceiling'ini aşarsa 22023 ile reddeder.
5. Önce sabit platform-gün (`seed=15015`), sonra course (`seed=15016`)
   transaction advisory lock'unu alır; lock LLM I/O'ya taşınmaz.
6. Bu user/course için süresi dolmamış unreconciled reservation sayısını concurrency ile karşılaştırır.
7. Europe/Istanbul gününde course-user, global-user, course ve platform
   `charged_tokens` toplamını birlikte sınar.
8. Redde içeriksiz `concurrency_limited|quota_exhausted` event'i yazıp normal decision döndürür.
9. Kabulde `lease_seconds` kadar reservation ekler ve commit edilecek decision
   döndürür. HTTP rol-farkındalıklı yolunda bu değer zorlanan tek provider
   denemesinin deadline'ını aşan reconciliation marjıyla hesaplanır.

### 6.3 `app.reconcile_course_agent_tokens(reservation_id, actual_tokens)`

- Actual `0..100000`.
- Reservation current DB user'a ait değilse 42501.
- Reserve ile aynı sırada platform-gün sonra course advisory lock alır.
- `actual_tokens > reserved_tokens` ise 22023 ile reddeder; satırın muhafazakâr
  reserved charge'ı değişmez.
- Yalnız `reconciled_at IS NULL` satırı geçerli actual charge + now ile günceller.
- İlk reconcile'dan sonra aynı/different tekrar no-op'tur; charge yeniden yazılmaz.
- HTTP wrapper reconcile'ı best-effort yapar: DB uzlaştırma hatası üretilmiş
  cevabı maskelemez ve önceden commit edilmiş reserved charge yerinde kalır.

### 6.4 `app.record_course_agent_guard_event(course_id, event_type)`

- HTTP servisinin yazabildiği explicit event türleri `rate_limited|scope_refused`.
- Quota/concurrency event'lerini reserve fonksiyonu kendi kararıyla yazar.
- Current user active membership'i yeniden doğrular.
- Audience'ı role'den çözer; prompt veya details kabul etmez.

## 7. RLS ve grant matrisi

| Varlık | dou_app direct | dou_worker | Public | Yol |
|---|---:|---:|---:|---|
| chat_sessions | mevcut self RLS | yok | yok | chat API |
| answer_cache | audience-matched member SELECT/INSERT RLS | yok | yok | chat service |
| course_ai_policies | member read / instructor write | yok | yok | policy API |
| ai_token_reservations | REVOKE ALL | REVOKE ALL | REVOKE ALL | definer reserve/reconcile |
| ai_guard_events | REVOKE ALL | REVOKE ALL | REVOKE ALL | definer reserve/record |

İki yeni tablo `ENABLE RLS` alır, normal roller için policy taşımaz ve bilerek
`FORCE RLS` almaz: dar `SECURITY DEFINER` fonksiyon sahibi no-policy tablolara
erişebilmelidir. Fonksiyonlarda sabit `search_path=pg_catalog,public,app`
kullanılır; `dou_app`, `dou_worker` ve Public doğrudan tablo grant'i veya
owner/BYPASSRLS yetkisi almaz.

## 8. Privacy, silme ve saklama

- Course/profile silme FK cascade ile 005 satırlarını kaldırır. 2026-08-11
  benzersiz gerçek PostgreSQL DB koşusunda iki DELETE yolu ayrı ayrı sınandı ve
  reservation/guard kalıntısı 0 ölçüldü.
- Kullanıcı export'u ham reservations/guard events satırı veya kimliği taşımaz;
  bunlar prompt içermeyen iç güvenlik/maliyet mekanizmaları olarak additive
  `not_included` alanında iki içeriksiz Türkçe açıklamayla yer alır.
- Export önceki kaynaklı chat cevaplarını içerdiği için sınav başlatma/chat
  finalizasyonuyla aynı user-wide `seed=15018` transaction kilidini alır. Herhangi
  bir derste aktif student EXAM varsa 423 `exam_export_locked`; practice/expired
  sınav ve instructor preview izinlidir.
- Eğitmen/platform admin için bireysel usage/guard liste endpoint'i yoktur.
- Request/guard satırları soru/cevap/source içeriği taşımaz.
- Canlı retention ve operator cleanup repo kodu + ortam kanıtı olmadan tamamlanmış sayılmaz.

T113 yerel kanıtı: `test_user_rights.py` 13/13, Ruff, mypy 92 dosya ve
`git diff --check` yeşil; aktif sınav 423 ve user-lock yarış sözleşmesi korundu.
Bu, canlı retention/operator cleanup kanıtı değildir.

## 9. Rollback/forward-fix

Migration additive'dir. Varsayılanı `true` olan `COURSE_AGENT_ENABLED`, cohort
canary seçicisi değil mevcut `/chat` yolunun acil kill switch'idir. Rollback'te
`false` yapılarak uygulama davranışı kapatılır; `0015` production DB'den sökülmez.

- Yeni reservation açılmaz.
- Açık unreconciled satırlar kendi doğrulanmış lease'i sona erince aktif concurrency
  hesabından düşer; reserved charge aynı günün quota hesabında korunur.
- Audience'lı session/cache okunabilir kalır.
- Guard/usage kanıtı retention kararına kadar korunur.
- Şema kusuru `0016` forward-fix ile düzeltilir; 0015 yeniden numaralanmaz/değiştirilmez.

## 10. Açık gelecek backlog'u

Bu migration'ın teslim iddiasına dahil değildir:

- request idempotency/replay anahtarı;
- DB-backed minute/request bucket;
- adaptive strike/backoff;
- prompt HMAC/fingerprint;
- IP/device/WAF bot limiti;
- human-facing per-user usage/abuse ekranı.

Bunlar ihtiyaç ölçülürse ayrı privacy/threat/spec ile eklenir.
