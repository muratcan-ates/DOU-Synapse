# API Sözleşmesi: 003 Product Portal

**Base URL**: mevcut API kökü
**Auth**: `Authorization: Bearer <token>`
**Hata zarfı**: bütün uçlarda mevcut tek Türkçe zarf

```json
{
  "error": {
    "code": "permission_denied",
    "message": "Bu işlem yalnızca platform yöneticisine açıktır.",
    "request_id": "f16b3d4249a34a53a0e1f2d9db985a8a"
  }
}
```

Bu dosya 003 için onaylanan hedef sözleşmedir. Pydantic, TypeScript ve migration
aynı anda bu sözleşmeye taşınmaktadır; çalışma ağacında geçici fark bulunabilir.
OpenAPI export, hedefli test ve gerçek HTTP doğrulaması tamamlanana kadar
“uygulandı” veya “donduruldu” sayılmaz.

---

## 1. Profil

### `GET /me/profile`

Giriş yapan kişinin kendi profilini ve aktif ders üyeliklerini döndürür.

**200**

```json
{
  "id": "11111111-1111-1111-1111-111111111111",
  "email": "ayse@example.edu",
  "full_name": "Ayşe Yılmaz",
  "created_at": "2026-08-01T09:00:00Z",
  "is_platform_admin": false,
  "memberships": [
    {
      "course_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      "course_code": "COME331",
      "course_title": "İşletim Sistemleri",
      "role": "student"
    }
  ]
}
```

**Gizlilik**: Tam e-posta yalnız kullanıcının kendi profilidir. Üyelikler yalnız
aktif satırlardır.

**Hatalar**: `401 unauthenticated`, `404 not_found`.

### `PATCH /me/profile`

Değiştirilebilir tek alan `full_name`'dir.

**İstek**

```json
{
  "full_name": "Ayşe Yılmaz"
}
```

Kurallar:

- Alan zorunludur; `null` kabul edilmez.
- Boşluklar tek boşluğa normalize edilir.
- Normalize değer 2–120 karakter olmalıdır.
- Ekstra alanlar `extra="forbid"` nedeniyle reddedilir.
- `email`, ders rolü ve `is_platform_admin` bu uçtan değiştirilemez.

**200**: `GET /me/profile` ile aynı güncel zarf.

**Hatalar**: `401 unauthenticated`, `404 not_found`, `422 validation_error`.

---

## 2. Rol bazlı dashboard

### `GET /dashboard`

Tek istekle kullanıcı, özet ve bütün aktif ders kartlarını döndürür.

**200**

```json
{
  "viewer": {
    "id": "11111111-1111-1111-1111-111111111111",
    "email": "ayse@example.edu",
    "full_name": "Ayşe Yılmaz",
    "is_platform_admin": false
  },
  "summary": {
    "total_courses": 2,
    "instructor_courses": 1,
    "student_courses": 1,
    "action_items": 4
  },
  "courses": [
    {
      "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      "code": "COME331",
      "title": "İşletim Sistemleri",
      "role": "instructor",
      "documents_total": 6,
      "documents_processing": 1,
      "documents_failed": 1,
      "questions_total": 20,
      "draft_questions": 2,
      "published_exams": 1,
      "mastery_score": null,
      "last_activity_at": "2026-08-10T14:12:00Z"
    },
    {
      "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      "code": "COME214",
      "title": "Veri Yapıları",
      "role": "student",
      "documents_total": 4,
      "documents_processing": 0,
      "documents_failed": 0,
      "questions_total": 15,
      "draft_questions": 0,
      "published_exams": 1,
      "mastery_score": 0.72,
      "last_activity_at": "2026-08-09T19:30:00Z"
    }
  ]
}
```

**Semantik**:

- `documents_processing`: `uploaded + processing`.
- `documents_failed` ve `draft_questions`: yalnız eğitmen kartında gerçek sayı;
  öğrenci kartında 0.
- `action_items`: yalnız eğitmen dersleri için
  `documents_processing + documents_failed + draft_questions`.
- `mastery_score`: yalnız giriş yapan kişinin ortalaması, `0..1` veya `null`.
- `published_exams`: yayınlanmış sürüm sayısıdır; taslak blueprint sayısı değildir.
- Sözleşmede taslak blueprint sayacı yoktur. UI yalnız blueprint aracına bağlantı verir.

**Hatalar**: `401 unauthenticated`, `404 not_found`.

---

## 3. Platform admin ortak kuralları

Admin uçlarının tamamı:

- `PlatformAdminDep` ile yetki doğrular,
- SQL yardımcılarında yetkiyi ikinci kez doğrular,
- salt okunurdur,
- admin olmayan kullanıcıya `403 permission_denied` döndürür,
- platform adminine akademik course membership vermez,
- erişim kararını ayrı tamamlanan işlemde allowlist action ve `request_id` ile
  audit eder; denied karar ana 403 işlemiyle rollback olmaz.

Liste zarfları:

```json
{
  "items": [],
  "total": 0,
  "limit": 25,
  "offset": 0
}
```

GET liste uçlarının ortak query alanları (`/courses`, `/requests`, `/ingestion`):

- `limit`: integer, varsayılan 25, `1..100`.
- `offset`: integer, varsayılan 0, `>=0`.

API ve SQL katmanı limiti ayrı ayrı doğrular.

---

## 4. Admin overview

### `GET /admin/overview`

**200**

```json
{
  "status": "ok",
  "database_status": "ok",
  "embedding_status": "ok",
  "measured_at": "2026-08-10T18:00:00Z",
  "users_total": 18,
  "active_memberships_total": 31,
  "courses_total": 6,
  "documents_total": 42,
  "ingestion_processing": 1,
  "ingestion_failed": 2,
  "chat_turns_24h": 320,
  "p95_latency_ms": 1460.5,
  "tokens_24h": 182400
}
```

Alanlar:

- `embedding_status`: `disabled | warming | ok | failed`.
- `p95_latency_ms`: son 24 saatte istek yoksa `null`.
- `chat_turns_24h`, `p95_latency_ms` ve `tokens_24h`: yalnız son 24 saatin
  başarılı `POST /courses/{course_id}/chat` satırlarından türetilir.
- `status`: embedding `ok|disabled` ise `ok`; `warming|failed` ise `degraded`.
- `measured_at`: API katmanının UTC ölçüm zamanı.

Bu overview, orkestratör probe'larının yerine geçmez. `/health/live` ve
`/health/ready` production probe kaynakları olarak kalır.

---

## 5. Admin kullanıcı dizini

### `POST /admin/users`

JSON gövde:

```json
{
  "limit": 25,
  "offset": 0,
  "search": "Ayşe"
}
```

Kurallar:

- `limit`: varsayılan 25, `1..100`.
- `offset`: varsayılan 0, `>=0`.
- `search`: opsiyonel/null `full_name` veya maskelenmiş e-posta araması, en fazla
  200 karakter. Tam e-posta araması eşleşmez.
- Ekstra alanlar reddedilir.
- UI placeholder'ı `Ad veya maskeli e-posta` olmalıdır.
- `search` hiçbir URL/query parametresine yazılmaz.

**200 item örneği**

```json
{
  "items": [
    {
      "id": "11111111-1111-1111-1111-111111111111",
      "masked_email": "ay***@example.edu",
      "full_name": "Ayşe Yılmaz",
      "created_at": "2026-08-01T09:00:00Z",
      "is_platform_admin": false,
      "active_course_count": 2
    }
  ],
  "total": 1,
  "limit": 25,
  "offset": 0
}
```

**Gizlilik**: Arama tam ad ve SQL tarafında üretilen maskelenmiş e-posta ifadesi
üzerinde çalışır. Tam e-posta araması eşleşmez. Arama JSON gövdesinde kaldığı için
URL/query access loglarına isim/e-posta bırakılmaz; HTTP body ayrıca uygulama loguna
yazılmaz. Yanıt da tam e-posta döndürmez. Bu uç, yetkili destek kullanıcı
dizinidir; kullanıcı `id` ve `full_name` taşıyabilir. Bu kimlikler request/ingestion
listesine yayılmaz.

---

## 6. Admin ders dizini

### `GET /admin/courses`

Query:

- ortak `limit`, `offset`
- `search`: opsiyonel string, en fazla 200 karakter

**200 item örneği**

```json
{
  "items": [
    {
      "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      "code": "COME331",
      "title": "İşletim Sistemleri",
      "created_at": "2026-08-03T11:00:00Z",
      "creator_name": "Yasemin Karagül",
      "active_member_count": 24,
      "documents_total": 6,
      "documents_failed": 1
    }
  ],
  "total": 1,
  "limit": 25,
  "offset": 0
}
```

Bu uç kaynak metni, soru payload'ı, sınav cevabı veya sohbet taşımaz.

---

## 7. Admin request ölçümleri

### `GET /admin/requests`

Query:

- ortak `limit`, `offset`
- `route`: opsiyonel tam route filtresi, en fazla 200 karakter
- `status`: opsiyonel
  `answered | insufficient_context | out_of_scope | budget_exhausted`

**200 item örneği**

```json
{
  "items": [
    {
      "log_id": "33333333-3333-3333-3333-333333333333",
      "course_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      "course_code": "COME331",
      "route": "/courses/{course_id}/chat",
      "mode": "socratic",
      "status": "answered",
      "http_status": 200,
      "latency_ms": 1320,
      "token_count": 860,
      "cache_hit": false,
      "created_at": "2026-08-10T17:58:00Z"
    }
  ],
  "total": 1,
  "limit": 25,
  "offset": 0
}
```

**Alan sınırı**:

- `log_id`, ölçüm satır kimliğidir; middleware `request_id` değildir.
- Kullanıcı UUID'si, e-posta, hash/pseudonym veya kullanıcı diziniyle eşlenebilecek
  başka bir kimlik alanı yoktur.
- Prompt, model cevabı, citation metni ve kaynak içeriği yoktur.
- `status` bazı teknik/erken hata satırlarında `null` olabilir.

---

## 8. Admin ingestion işleri

### `GET /admin/ingestion`

Query:

- ortak `limit`, `offset`
- `status`: opsiyonel `pending | processing | completed | failed`

**200 item örneği**

```json
{
  "items": [
    {
      "id": "44444444-4444-4444-4444-444444444444",
      "document_id": "55555555-5555-5555-5555-555555555555",
      "course_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      "course_code": "COME331",
      "status": "failed",
      "attempt_count": 3,
      "started_at": "2026-08-10T17:40:00Z",
      "completed_at": null,
      "created_at": "2026-08-10T17:38:00Z"
    }
  ],
  "total": 1,
  "limit": 25,
  "offset": 0
}
```

**Bilinçli olarak dönmez**:

- `file_name`
- storage path
- belge/chunk metni
- `last_error`

Operasyon için kimlik, ders kodu, durum, deneme ve zaman yeterlidir. Teknik hata
ayrıntısı güvenli telemetry backend'inde aranır.

---

## 9. Yetki ve negatif sözleşmeler

### Admin olmayan kullanıcı

```http
GET /admin/overview
HTTP/1.1 403 Forbidden
```

```json
{
  "error": {
    "code": "permission_denied",
    "message": "Bu işlem yalnızca platform yöneticisine açıktır.",
    "request_id": "..."
  }
}
```

Aynı sonuç `POST /admin/users`, `GET /admin/courses`, `GET /admin/requests` ve
`GET /admin/ingestion` için geçerlidir.

403 yanıtı verilmeden önce güvenli audit helper'ı `denied` kararını ayrı DB
işleminde yazar. Audit tablosunu okuyan genel/admin endpoint'i yoktur.

### Platform admin fakat ders üyesi değil

Platform admin `/admin/*` okuyabilir. Aynı kullanıcı üyesi olmadığı
`/courses/{course_id}` akademik ucunda mevcut `404 not_found` ders izolasyonunu
görür. Admin rolü course dependency'yi atlamaz.

### Self-promotion

Normal uygulama rolü `platform_admins` tablosuna doğrudan SELECT/INSERT/UPDATE/
DELETE yapamaz. Admin atama API'si yoktur.

---

## 10. Kırılma ve uyumluluk

- Yeni uçlar ekleyicidir; mevcut course/chat/exam sözleşmesini değiştirmez.
- Giriş başarı yönlendirmesi `/courses` yerine `/dashboard` olur; deep-link course
  URL'leri değişmez.
- AppShell kullanıcı adını server profiline bağlar; profil yüklenene kadar admin
  linki fail-closed gizlidir.
- Admin pagination offset tabanlıdır. Yüksek hacimde keyset'e geçiş response
  sözleşmesini değiştireceği için ayrı feature olarak ele alınmalıdır.
- OpenAPI yeniden export edilmeden bu belge tek başına generated contract sayılmaz.
