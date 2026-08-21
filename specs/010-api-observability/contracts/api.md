# API Sözleşmesi

## `POST /admin/api-events/query`

Bearer kimliği ve platform admin yetkisi gerekir. POST seçimi bilinçlidir: destek
kodu URL, proxy access logu veya tarayıcı geçmişine yazılmaz.

```json
{
  "window_minutes": 60,
  "limit": 25,
  "offset": 0,
  "method": "POST",
  "route": "/courses/{course_id}/chat",
  "status_class": "5xx",
  "request_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
```

- `window_minutes`: `15 | 60 | 1440`
- `status_class`: `2xx | 3xx | 4xx | 5xx`
- filtreler opsiyonel; `extra=forbid`
- `limit`: 1–100, `offset >= 0`

Yanıt:

```json
{
  "measured_at": "2026-08-20T00:00:00Z",
  "window_minutes": 60,
  "summary": {
    "requests_total": 120,
    "successful_total": 105,
    "redirect_total": 4,
    "client_error_total": 9,
    "server_error_total": 2,
    "p50_latency_ms": 84.0,
    "p95_latency_ms": 842.0
  },
  "routes": [
    {
      "method": "POST",
      "route_template": "/courses/{course_id}/chat",
      "requests_total": 40,
      "error_total": 3,
      "p95_latency_ms": 901.0,
      "last_seen_at": "2026-08-20T00:00:00Z"
    }
  ],
  "items": [
    {
      "request_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "service": "api",
      "environment": "local",
      "release_revision": "db2f42a",
      "method": "POST",
      "route_template": "/courses/{course_id}/chat",
      "status_code": 500,
      "outcome_code": "internal_error",
      "duration_ms": 913,
      "created_at": "2026-08-20T00:00:00Z"
    }
  ],
  "total": 2,
  "limit": 25,
  "offset": 0,
  "collector": {
    "scope": "process",
    "status": "healthy",
    "retention_status": "healthy",
    "queue_depth": 0,
    "queue_capacity": 1000,
    "persisted_total": 120,
    "dropped_total": 0,
    "failure_total": 0,
    "last_persisted_at": "2026-08-20T00:00:00Z",
    "last_error_at": null
  }
}
```

`collector` yalnız isteği karşılayan API sürecinin durumudur; bütün cluster veya
production SLO kanıtı değildir.

## Ortak hata zarfı

```json
{
  "error": {
    "code": "validation_error",
    "message": "Gönderilen veri geçersiz.",
    "request_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }
}
```

OpenAPI mevcut Pydantic modelinden aynı zarfı üretir. Korumalı uçlar `BearerAuth`
security requirement taşır; `/health/live` ve `/health/ready` public kalır.
