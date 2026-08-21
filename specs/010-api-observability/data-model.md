# Veri Modeli: 0017 API Observability

## `api_request_events`

| Alan | Kural |
|---|---|
| `id` | İç DB kimliği; API/DOM'a dönmez |
| `request_id` | Sunucunun ürettiği tekil 32 karakter küçük harf hex; istemci başlığı saklanmaz, retry aynı olayı çoğaltmaz |
| `service` | Bu dilimde sabit `api` |
| `environment` | `local|demo|production` |
| `release_revision` | İçeriksiz, bounded deployment etiketi |
| `method` | İzinli büyük harf HTTP methodu |
| `route_template` | Normalize FastAPI şablonu veya `UNMATCHED`; ham path değil |
| `status_code` | 100–599 |
| `outcome_code` | Bounded uygulama hata kodu veya NULL; exception text değil |
| `duration_ms` | 0–3_600_000 tamsayı |
| `created_at` | DB zamanı |
| `expires_at` | `created_at + retention`; mutable değil |

Tabloda `user_id`, `course_id`, `document_id`, IP, user-agent, query, body, prompt,
answer, source, token, e-posta, stack veya ham hata kolonu bulunmaz. Şema düzeyindeki
bu yokluk, redaction hatasına bağlı kalmayan privacy invariantıdır.

## Yetki modeli

- RLS açık; uygulama/worker için doğrudan policy yoktur.
- `app.record_api_request_events(jsonb, integer)` yalnız exact API runtime session
  identity ile en fazla 100 satır ekler ve alanları yeniden doğrular.
- `app.admin_api_request_events(...)` yalnız doğrulanmış platform admin bağlamında dar JSON
  projection döndürür; tablo `id`/`expires_at` görünmez.
- `app.purge_expired_api_request_events(integer)` yalnız `expires_at <= now()`
  satırlarından bounded batch siler.
- PUBLIC, carrier ve worker function/table yetkileri açıkça çekilir; gereken runtime
  execute grant'i exact role'a verilir.

## İndeks ve retention

- `(created_at DESC, id DESC)` genel pencere/sayfalama
- `(method, route_template, created_at DESC)` uç aggregation/filter
- `UNIQUE (request_id)` destek kodu ve idempotent retry
- `expires_at` bounded purge

Retention 1–30 gün; production değeri explicit olmalıdır. Query süresi en fazla
24 saattir; retention uzunluğu sorgu penceresini büyütmez.
