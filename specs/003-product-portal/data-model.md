# Veri Modeli: Rol Bazlı Ürün Portalı

**Feature**: 003 Product Portal
**Migration**: `0014_platform_admin_console.sql`
**Durum**: Yerel migration, RLS referans ve mutasyon kapılarıyla doğrulandı; staging uygulanmadı

---

## 1. Modelleme ilkesi

003, dashboard veya profil için ikinci bir veri kopyası açmaz. Üç sınıf veri vardır:

1. **Mevcut kalıcı gerçekler**: `profiles`, `courses`, `course_memberships`,
   `documents`, `questions`, `exam_versions`, `mastery`, `request_logs`,
   `ingestion_jobs`.
2. **Yeni kalıcı gerçekler**: platform operasyon yetkisi ilişkisi ve admin endpoint
   erişim kararlarının append-only denetim izi.
3. **Türetilmiş projeksiyonlar**: profil, dashboard ve admin listeleri.

Dashboard sayıları saklanmaz; aksi hâlde belge/soru/sınav değiştiğinde ikinci bir
“doğru” doğar. Projeksiyonlar istek anında mevcut tablolardan hesaplanır.

---

## 2. Mevcut varlıklar

### 2.1 `profiles`

| Alan | Tip | Portal kullanımı |
|---|---|---|
| `id` | uuid PK | Kimlik sağlayıcıyla birebir kullanıcı |
| `email` | text unique | Kişinin kendi profilinde tam; admin dizininde maskeli |
| `full_name` | text nullable | Kullanıcının güncelleyebildiği görünen ad |
| `created_at` | timestamptz | Profil/admin kullanıcı dizini |

Yeni kolon eklenmez. `PATCH /me/profile` yalnız `full_name` değiştirir. E-posta
kimlik sağlayıcısına aittir; ders rolü ve adminlik bu tabloda tutulmaz.

### 2.2 `course_memberships`

Bir kullanıcının her dersteki rolünün tek kaynağıdır:

```text
(course_id, user_id) -> role {instructor, student}, status {active, revoked}
```

Sistem geneli öğrenci/eğitmen rolü türetilmez. Aynı kullanıcı A dersinde eğitmen,
B dersinde öğrenci olabilir.

### 2.3 `request_logs`

Şema gereği prompt, cevap veya başka serbest akademik metin taşımaz. Admin request
projeksiyonunda yalnız şu alanlar kullanılabilir:

- log kimliği,
- course kimliği ve kodu,
- route, mod, cevap durum sınıfı, HTTP durum,
- latency, token count, cache hit, created_at.

Kullanıcı UUID'si, e-posta veya hash/pseudonym request projeksiyonuna alınmaz.

### 2.4 `ingestion_jobs`

Admin ingestion projeksiyonu için durum, deneme sayısı ve zaman damgalarının
kaynağıdır. `documents` ile course ilişkisi çözülür; **dosya adı seçilmez**.

---

## 3. Yeni tablolar

### 3.1 `platform_admins`

```sql
CREATE TABLE platform_admins (
    user_id     uuid PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
    granted_by  uuid REFERENCES profiles(id) ON DELETE SET NULL,
    granted_at  timestamptz NOT NULL DEFAULT now()
);
```

#### Semantik

- Bir satır, kullanıcının platform operasyon konsolunu okuyabildiğini söyler.
- Satır, hiçbir derse üyelik vermez.
- Satır, eğitmenlik veya öğrenci verisi üzerinde akademik superuser yetkisi vermez.
- `granted_by`, kontrollü atamayı yapan profil silinirse `NULL` olabilir; atama
  zamanı korunur.
- İlk admin uygulama içinden değil, kurulum/DBA adımıyla atanır.

#### Neden `profiles.role` değil?

`profiles.role`, aynı kişiyi tek role zorlar ve mevcut ders bazlı modelle çelişir.
Platform rolünün yaşam döngüsü de farklıdır: normal API kendisini admin yapamaz;
yetki kontrollü operatör işlemiyle verilir.

#### RLS ve grant tasarımı

```sql
ALTER TABLE platform_admins ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE platform_admins FROM PUBLIC, dou_app, dou_worker;
```

Tabloda kullanıcı politikası yoktur. RLS **FORCE edilmez**.

**Neden FORCE yok?** Dar `SECURITY DEFINER` yardımcıları tablo sahibinin yetkisiyle
bu ilişkiyi okumalıdır. Politikasız tabloya FORCE uygulanırsa tablo sahibi de sıfır
satır görür ve güvenli helper çalışamaz. Güvenlik aşağıdaki üç katmandadır:

1. PUBLIC, `dou_app`, `dou_worker` doğrudan tablo grant'i taşımaz.
2. Normal uygulama yazma fonksiyonu yoktur; atama/geri alma yalnız DBA'dadır.
3. Dışarı açılan her admin fonksiyonu kendi içinde platform admin kontrolünü tekrarlar.

Bu karar doğrudan RLS ve izin testleriyle kanıtlanmalıdır; yalnız DDL okumak yeterli değildir.

### 3.2 `platform_admin_access_audit`

```sql
CREATE TABLE platform_admin_access_audit (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id uuid NOT NULL,
    action        text NOT NULL,
    result        text NOT NULL,
    request_id    text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);
```

Kısıtlar:

- `action`, yalnız `GET /admin/overview`, `POST /admin/users`,
  `GET /admin/courses`, `GET /admin/requests` ve `GET /admin/ingestion`
  allowlist'indeki beş değerden biridir.
- `result`, `allowed | denied` değerlerinden biridir.
- `request_id`, 1–128 karakterlik güvenli `[A-Za-z0-9_-]` biçimindedir.
- Tablo RLS ENABLE, FORCE değildir; PUBLIC/`dou_app`/`dou_worker` grant'i yoktur.
- Admin UI veya genel API için bu tabloyu okuyan liste endpoint'i yoktur.

Buradaki ham `actor_user_id`, güvenlik erişim denetimi içindir ve kapalı DB
tablosunda kalır; request ölçüm listesine veya telemetry export'una taşınmaz.
Dependency audit helper'ını ana isteğin transaction'ından ayrı tamamlar. Böylece
403 üreten denied karar, ana istek rollback olduğunda kaybolmaz.

---

## 4. Güvenli yardımcılar

### 4.1 `app.is_platform_admin()`

```text
girdi: app.current_user_id()
çıktı: boolean
özellik: STABLE, SECURITY DEFINER, sabit search_path
```

Fonksiyon `current_user_id` yoksa false döner. Execute varsayılanı PUBLIC'ten geri
alınır, yalnız `dou_app`'e verilir. Bu yardımcı API dependency'sinde ve her admin
projeksiyonunun içinde kullanılır; dependency tek başına güvenlik sınırı değildir.

### 4.2 `app.audit_platform_admin_access(action, request_id)`

```text
girdi: allowlist action + güvenli request_id
çıktı: o anda DB'den hesaplanan boolean admin kararı
özellik: VOLATILE, SECURITY DEFINER, sabit search_path
yan etki: platform_admin_access_audit INSERT
```

İstemci `result` sağlayamaz. Fonksiyon sonucu `app.is_platform_admin()` ile yeniden
hesaplar, allowed/denied satırını yazar ve bool döndürür. EXECUTE PUBLIC'ten geri
alınır; yalnız `dou_app`e verilir.

---

## 5. Profil projeksiyonu

Kalıcı tablo değildir.

```text
ProfileOut
├── id
├── email                    # yalnız kişinin kendi tam e-postası
├── full_name
├── created_at
├── is_platform_admin        # app.is_platform_admin()
└── memberships[]
    ├── course_id
    ├── course_code
    ├── course_title
    └── role
```

Üyelikler yalnız `status='active'` satırlardan gelir ve ders kodu/başlığıyla
belirlenimci sıralanır.

---

## 6. Dashboard projeksiyonu

Kalıcı tablo değildir. Giriş yapan kişinin aktif üyelikleri üzerinden hesaplanır.

### 6.1 `DashboardViewer`

`id`, kendi `email`, `full_name`, `is_platform_admin`.

### 6.2 `DashboardCourse`

| Alan | Türetim |
|---|---|
| `id`, `code`, `title` | `courses` |
| `role` | aktif `course_memberships` |
| `documents_total` | dersteki belge sayısı |
| `documents_processing` | status `uploaded` veya `processing` |
| `documents_failed` | yalnız eğitmen kartında failed; öğrenci için 0 |
| `questions_total` | dersteki soru sayısı |
| `draft_questions` | yalnız eğitmen kartında draft; öğrenci için 0 |
| `published_exams` | `exam_versions.status='published'` |
| `mastery_score` | yalnız giriş yapan kullanıcının ders ortalaması |
| `last_activity_at` | belge, soru ve kişinin sınav aktivitesinin en yenisi |
| `assistant_locked` | öğrenci rolünde, aynı derste etkin ve süresi dolmamış gerçek sınav oturumu var mı |
| `assistant_lock_reason` | kilitliyken server sabiti `exam_in_progress`; aksi durumda `null` |
| `assistant_lock_message` | kilitliyken server kaynaklı Türkçe açıklama; aksi durumda `null` |

Üç asistan kilidi alanı kalıcı dashboard verisi değildir. API, mevcut sınav durum
yardımcısının tek sorguda döndürdüğü ders kümesinden türetir. Eğitmen kartında
`assistant_locked=false` olur; frontend rol veya süre üzerinden ikinci bir kilit
hesabı yapmaz.

### 6.3 `DashboardSummary`

```text
total_courses      = course sayısı
instructor_courses = role=instructor course sayısı
student_courses    = total - instructor
action_items       = eğitmen derslerinde
                     documents_processing
                   + documents_failed
                   + draft_questions
```

`action_items` bir saklanan iş listesi değildir; görünür kaynak sayıların toplamıdır.

---

## 7. Admin projeksiyonları

Hepsi `jsonb` döndüren dar `SECURITY DEFINER` fonksiyonlarıdır. Her fonksiyon
adminliği yeniden doğrular ve sabit allowlist alanlarını seçer. Dört liste fonksiyonu ayrıca:

1. `limit` 1–100, `offset >= 0` doğrular,
2. belirlenimci `created_at DESC, id DESC` sırası kullanır.

### 7.1 `app.admin_overview()`

DB projeksiyonu:

- `users_total`
- `active_memberships_total`
- `courses_total`
- `documents_total`
- `ingestion_processing`
- `ingestion_failed`
- `chat_turns_24h`
- `p95_latency_ms`
- `tokens_24h`

Son üç kullanım alanı yalnız son 24 saatin başarılı
`POST /courses/{course_id}/chat` satırlarından hesaplanır; genel HTTP istek sayısı
veya başarısız istek sayısı değildir.

API katmanı buna şu runtime alanlarını ekler:

- `status`
- `database_status`
- `embedding_status`
- `measured_at`

Bu alanlar migration'a yazılmaz; DB embedding warmup durumunu bilemez.

### 7.2 `app.admin_users(limit, offset, search)`

| Alan | Gizlilik kararı |
|---|---|
| `id` | Destek dizininde izinli kararlı hesap kimliği |
| `masked_email` | Tam e-posta dönmez |
| `full_name` | Yetkili kullanıcı dizininde izinli; telemetry'ye yayılmaz |
| `created_at` | Hesap yaşı |
| `is_platform_admin` | Operasyon rolü |
| `active_course_count` | İçeriksiz ilişki sayısı |

Arama `full_name` ve SQL tarafında üretilen maskelenmiş e-posta ifadesi üzerinde
çalışır. Tam e-posta araması eşleşmez. API, değeri `POST /admin/users` JSON
gövdesinde taşır; URL/query access loglarına arama metni bırakılmaz. Yanıt her
durumda yalnız maskeli e-posta döndürür.

### 7.3 `app.admin_courses(limit, offset, search)`

- `id`, `code`, `title`, `created_at`
- `creator_name`
- `active_member_count`
- `documents_total`, `documents_failed`

Bu projeksiyon dersin operasyonel varlığını gösterir; kaynak metni, sohbet, sınav
cevabı veya soru payload'ı taşımaz.

### 7.4 `app.admin_request_logs(limit, offset, route, status)`

- `log_id`
- `course_id`, `course_code`
- `route`, `mode`, `status`, `http_status`
- `latency_ms`, `token_count`, `cache_hit`, `created_at`

Kullanıcı UUID'si, e-posta, hash/pseudonym veya kullanıcı diziniyle eşlenebilecek
başka bir kimlik alanı bilinçli olarak yoktur.

### 7.5 `app.admin_ingestion_jobs(limit, offset, status)`

- `id`, `document_id`
- `course_id`, `course_code`
- `status`, `attempt_count`
- `started_at`, `completed_at`, `created_at`

**Bilinçli olarak yok**: `file_name`, storage path, document text, chunk text,
`last_error`. İlk üçü akademik/sistem metaverisi sızdırır; sonuncusu ham teknik veya
içerik parçası taşıyabilir. Ayrıntılı hata yalnız güvenli telemetry backend'inde
request/trace bağlamıyla incelenir.

---

## 8. Sayfalama ve indeksler

İlk admin dikey dilimi mevcut backend sözleşmesiyle `limit/offset` kullanır ve
`total` döndürür. Limit hem FastAPI hem SQL fonksiyonunda en fazla 100'dür.

Yeni indeksler:

```sql
profiles (created_at DESC, id DESC)
platform_admin_access_audit (created_at DESC, id DESC)
request_logs (created_at DESC, id DESC)
request_logs (status, created_at DESC, id DESC)
ingestion_jobs (status, created_at DESC, id DESC)
```

**Kabul edilen sınır**: Offset pagination eşzamanlı eklemede tekrar/atlama üretebilir.
Admin konsolu operasyonel ve salt okunur ilk dilim olduğu için kabul edilir; yüksek
hacim ölçülürse 002'nin keyset `PageOut` desenine taşınır. Bu sınır gizlenmez.

---

## 9. İlişki özeti

```text
profiles 1 ─── 0..1 platform_admins
    │                    │
    │                    └── platform operasyon yetkisi
    │
    └──< course_memberships >── courses
                 │                 │
                 │                 ├── documents ── ingestion_jobs
                 │                 ├── questions
                 │                 ├── exam_versions / exam_sessions
                 │                 └── request_logs
                 │
                 └── profil ve dashboard projeksiyonları

platform_admins
    └── admin SECURITY DEFINER projeksiyonlarını açar
        └── akademik course membership politikalarını DEĞİŞTİRMEZ

admin endpoint denemesi
    └── app.audit_platform_admin_access()
        └── platform_admin_access_audit (allowed/denied, UI'da okunmaz)
```

---

## 10. Gizlilik matrisi

| Veri | Kendi profili | Ders eğitmeni | Platform admin | Telemetry |
|---|---:|---:|---:|---:|
| Kendi tam e-posta | Evet | Üyelik yönetim sözleşmesi kadar | Hayır, maskeli | Hayır |
| Görünen ad | Evet | Aktif üyelik listesinde | Kullanıcı dizininde | Hayır |
| Ders rolü | Kendi üyelikleri | Kendi dersi | Aktif course sayısı/operasyon özeti | Hayır |
| Öğrenci sohbet metni | Kendi | Hayır | Hayır | Hayır |
| Sınav cevabı | Kendi akışı | Yetkili değerlendirme akışı | Hayır | Hayır |
| Prompt/model cevabı | Kendi akışı | Toplu ölçüm dışında hayır | Hayır | Hayır |
| Request ölçümü | Kendi satırını okuyamaz | Kendi derste toplu/izinli | İçeriksiz allowlist | İçeriksiz |
| Dosya adı | Ders üyesi yüzeyinde | Kendi dersinde | Ingestion listesinde hayır | Hayır |
| Admin erişim actor UUID | Kendi profilinde kimlik olarak | Hayır | Admin UI'da hayır | Kapalı audit tablosunda; export yok |

---

## 11. Migration güvenliği ve sıra

- `0013_chat_feedback.sql` entegrasyon için rezerve edilmiştir.
- Portal migration'ı `0014_platform_admin_console.sql`'dır.
- Tek `BEGIN/COMMIT` içinde uygulanır.
- Function EXECUTE varsayılanı PUBLIC'ten geri alınır.
- `app.is_platform_admin`, `app.audit_platform_admin_access` ve admin fonksiyonları
  yalnız `dou_app` için EXECUTE alır.
- `platform_admins` ve `platform_admin_access_audit` tablo grant'i `dou_app` ve
  `dou_worker` için geri verilmez.
- Migration downgrade yazmaz; geri dönüş yeni ileri migration ile yapılır.

### Doğrulama kapıları

1. Admin olmayan çağrıda her helper hata verir.
2. `dou_app` doğrudan platform_admins SELECT/INSERT/UPDATE/DELETE yapamaz.
3. DBA bir admin atadığında helper true olur.
4. Admin course üyeliği olmadan course akademik endpoint'ine erişemez.
5. Request projeksiyonunda prompt/response/user UUID yoktur.
6. Ingestion projeksiyonunda `file_name`, path, error text yoktur.
7. Limit 101 hem API hem SQL düzeyinde reddedilir.
8. Admin satırı kaldırıldığında aynı oturumun admin helper çağrısı reddedilir.
9. Allowed ve denied admin endpoint denemeleri audit tablosuna yazılır; 403 denied
   satırını rollback etmez.
10. Uygulama/worker audit tablosunu doğrudan okuyamaz veya değiştiremez.

---

## 12. Bilinçli yapılmayanlar

- `profiles` içine global role kolonu.
- Adminin bütün tablolara bypass yetkisi.
- Admin UI'dan admin atama/geri alma.
- Admin rolü verme/geri alma yaşam döngüsü için ayrı değişiklik audit'i; mevcut
  tablo yalnız admin endpoint erişim kararlarını kaydeder.
- Dashboard cache/materialized view; ölçüm olmadan karmaşıklık eklenmez.
- Resmi dönem, danışman, duyuru, GPA veya transkript tabloları.
- Ham log tablosu ya da prompt/cevap telemetry'si.
