# Veri Modeli — 001 Course Assistant MVP

**Kaynaklar ve doğruluk sırası:**

1. **UYGULANMIŞ şema** — tek gerçek: [`supabase/migrations/0001_core_schema.sql`](../../supabase/migrations/0001_core_schema.sql)
2. **PLANLANAN tablolar** — [`ARCHITECTURE.md`](../../ARCHITECTURE.md) §3 (henüz migration'ı yok)

Bu belge ikisini **ayrı başlıklar altında** tutar. Planlanan bir tablo migration'a
girdiğinde ilgili bölüm "uygulanmış" tarafına taşınır ve bu belge güncellenir.

> **Şema sapması notu (bilinçli):** ARCHITECTURE.md §3 `profiles` için
> `role: instructor|student` alanı listeler; uygulanmış şemada bu alan **yoktur**.
> Migration'daki tablo yorumu gerekçeyi verir: *"Sistem geneli rol yoktur; yetki
> daima ders bazlıdır (course_memberships)."* Aynı şekilde §3'teki
> `courses.instructor_id` uygulamada `courses.created_by` olarak gerçekleşmiştir.
> Uygulanmış şema esas alınır.

---

## 1. Oturum Bağlamı ve Veritabanı Rolleri (uygulanmış)

RLS'in temeli: API her istek için işlem içinde `SET LOCAL app.current_user_id = '<uuid>'`
yapar. Politikalar bu GUC'yi `app.current_user_id()` üzerinden okur; ayarlanmamışsa
fonksiyon NULL döner ve **hiçbir satır görünmez (fail-closed)** — Anayasa İlke IV.

| Rol | Özellikler | Amaç |
|---|---|---|
| `dou_app` | `NOLOGIN`, tablo sahibi DEĞİL, `BYPASSRLS` YOK | API'nin bağlandığı rol; tüm RLS politikalarına tabidir (Anayasa İlke II) |
| `dou_worker` | `NOLOGIN`, `BYPASSRLS` | Ingestion worker'ı; asla kullanıcı isteği bağlamında çalışmaz, yalnızca kuyruk işler. `chunks`'a INSERT politikası bilinçli olarak yoktur — worker RLS'i atlayarak yazar |

Her iki role `public` şemasındaki tüm tablolarda `SELECT, INSERT, UPDATE, DELETE`
ve `app` şemasındaki fonksiyonlarda `EXECUTE` verilmiştir (grant ≠ görünürlük;
`dou_app` için satır erişimini RLS belirler).

Tüm tablolar hem `ENABLE` hem `FORCE ROW LEVEL SECURITY` taşır — sahip rol bile
politikalara tabidir.

### Yardımcı fonksiyonlar

| Fonksiyon | Tip | Ne yapar |
|---|---|---|
| `app.current_user_id() → uuid` | `STABLE` | `app.current_user_id` GUC'sini okur; boş/ayarsızsa NULL |
| `app.immutable_unaccent(text) → text` | `IMMUTABLE STRICT PARALLEL SAFE` | Generated column'da kullanılabilir unaccent sarmalayıcısı (`unaccent()` STABLE olduğu için gerekli) |

---

## 2. UYGULANMIŞ Varlıklar (`0001_core_schema.sql`)

### 2.1 `profiles`

Kullanıcı profili. Supabase'de `auth.users` kimliğiyle birebir eşleşir; lokal
geliştirmede doğrudan yazıldığı için `auth` şemasına FK **verilmemiştir**.

| Alan | Tip | Kısıt |
|---|---|---|
| `id` | `uuid` | PK |
| `email` | `text` | NOT NULL, UNIQUE |
| `full_name` | `text` | nullable |
| `created_at` | `timestamptz` | NOT NULL, DEFAULT `now()` |

Sistem geneli `role` alanı **yoktur** — rol ders bazlıdır (`course_memberships.role`).

> [NEEDS CLARIFICATION: Migration yorumunda anılan `0002_supabase_auth_bridge.sql`
> repoda henüz yok. `auth.users → profiles` senkronizasyonu (trigger mi, uygulama
> katmanı mı) hangi migration'da ve nasıl kurulacak?]

**RLS politikaları:**

| Politika | Komut | Kural |
|---|---|---|
| `profiles_self_read` | SELECT | `id = app.current_user_id() OR app.is_instructor_of(id)` — kullanıcı kendini, eğitmen kendi dersindeki öğrencileri görür; öğrenciler birbirini göremez |
| `profiles_self_update` | UPDATE | `id = app.current_user_id()` |

INSERT/DELETE politikası yok → `dou_app` üzerinden profil eklenemez/silinemez.

### 2.2 `courses`

| Alan | Tip | Kısıt |
|---|---|---|
| `id` | `uuid` | PK, DEFAULT `gen_random_uuid()` |
| `code` | `text` | NOT NULL; CHECK `length(btrim(code)) > 0` (`courses_code_not_blank`) |
| `title` | `text` | NOT NULL |
| `created_by` | `uuid` | NOT NULL, FK → `profiles(id)` ON DELETE RESTRICT |
| `created_at` | `timestamptz` | NOT NULL, DEFAULT `now()` |

**İndeksler:** `courses_code_key` — UNIQUE `lower(code)` (ders kodu büyük/küçük
harf duyarsız tekildir).

**RLS politikaları:**

| Politika | Komut | Kural |
|---|---|---|
| `courses_member_read` | SELECT | `app.is_member(id)` |
| `courses_instructor_update` | UPDATE | `app.is_instructor(id)` |

**INSERT politikası bilinçli olarak yoktur.** Ders oluşturma bir bootstrap
işlemidir (nesneyi yaratıp aynı anda sahibi olursunuz); politikayla ifade
edilmeye çalışıldığında ya `RETURNING`'i kıran ya da okuma yüzeyini genişleten
bir tasarım çıkar. Bunun yerine `app.create_course()` (bkz. §3) atomik olarak
yapar; uygulama rolünün `courses`'a doğrudan yazma yolu RLS ile kapalıdır.

### 2.3 `course_memberships`

Enum'lar: `membership_role = ('instructor', 'student')`,
`membership_status = ('active', 'revoked')`.

| Alan | Tip | Kısıt |
|---|---|---|
| `course_id` | `uuid` | NOT NULL, FK → `courses(id)` ON DELETE CASCADE; PK'nın parçası |
| `user_id` | `uuid` | NOT NULL, FK → `profiles(id)` ON DELETE CASCADE; PK'nın parçası |
| `role` | `membership_role` | NOT NULL |
| `status` | `membership_status` | NOT NULL, DEFAULT `'active'` |
| `created_at` | `timestamptz` | NOT NULL, DEFAULT `now()` |

**PK:** `(course_id, user_id)` — bir kullanıcının bir derste tek üyeliği olur;
tekrar davet "yeni satır" değil, mevcut satırın reaktivasyonudur
(`add_course_member` → `reactivated`).

**İndeks:** `course_memberships_user_idx` — `(user_id, status)`.

**RLS politikaları:**

| Politika | Komut | Kural |
|---|---|---|
| `memberships_read` | SELECT | `user_id = app.current_user_id() OR app.is_instructor(course_id)` — kullanıcı kendi üyeliklerini, eğitmen dersin tüm üyeliklerini görür |
| `memberships_insert` | INSERT | WITH CHECK `app.is_instructor(course_id)` — ilk eğitmen üyeliği `create_course()` içinde yazıldığından bootstrap istisnası gerekmez |
| `memberships_instructor_update` | UPDATE | `app.is_instructor(course_id)` |
| `memberships_instructor_delete` | DELETE | `app.is_instructor(course_id)` |

### 2.4 `documents`

Enum: `document_status = ('uploaded', 'processing', 'completed', 'failed')`.

| Alan | Tip | Kısıt |
|---|---|---|
| `id` | `uuid` | PK, DEFAULT `gen_random_uuid()` |
| `course_id` | `uuid` | NOT NULL, FK → `courses(id)` ON DELETE CASCADE |
| `uploaded_by` | `uuid` | NOT NULL, FK → `profiles(id)` ON DELETE RESTRICT |
| `file_name` | `text` | NOT NULL |
| `file_type` | `text` | NOT NULL |
| `storage_path` | `text` | NOT NULL |
| `file_hash` | `text` | NOT NULL |
| `byte_size` | `bigint` | NOT NULL, CHECK `byte_size > 0` |
| `status` | `document_status` | NOT NULL, DEFAULT `'uploaded'` |
| `page_count` | `integer` | nullable |
| `chunk_count` | `integer` | NOT NULL, DEFAULT `0` |
| `error_message` | `text` | nullable |
| `created_at` | `timestamptz` | NOT NULL, DEFAULT `now()` |
| `updated_at` | `timestamptz` | NOT NULL, DEFAULT `now()` |

**İndeksler:**
- `documents_course_hash_key` — UNIQUE `(course_id, file_hash)`: aynı dosyanın
  aynı derse ikinci kez yüklenip yeniden embed edilmesini engeller.
- `documents_course_idx` — `(course_id, created_at DESC)`.

**RLS politikaları:**

| Politika | Komut | Kural |
|---|---|---|
| `documents_member_read` | SELECT | `app.is_member(course_id)` |
| `documents_instructor_insert` | INSERT | WITH CHECK `app.is_instructor(course_id)` |
| `documents_instructor_update` | UPDATE | `app.is_instructor(course_id)` |
| `documents_instructor_delete` | DELETE | `app.is_instructor(course_id)` |

### 2.5 `chunks`

Enum: `chunk_content_type = ('text', 'table', 'code')`.

| Alan | Tip | Kısıt |
|---|---|---|
| `id` | `uuid` | PK, DEFAULT `gen_random_uuid()` |
| `course_id` | `uuid` | NOT NULL, FK → `courses(id)` ON DELETE CASCADE — **denormalize**: retrieval filtresi JOIN'e bağlı kalmasın (ARCHITECTURE.md §3) |
| `document_id` | `uuid` | NOT NULL, FK → `documents(id)` ON DELETE CASCADE |
| `chunk_index` | `integer` | NOT NULL; UNIQUE `(document_id, chunk_index)` |
| `page_number` | `integer` | nullable (PDF) |
| `slide_number` | `integer` | nullable (PPTX) |
| `section_title` | `text` | nullable |
| `content_type` | `chunk_content_type` | NOT NULL, DEFAULT `'text'` |
| `language` | `text` | nullable |
| `text` | `text` | NOT NULL |
| `token_count` | `integer` | NOT NULL |
| `embedding` | `vector(1024)` | nullable (multilingual-e5-large boyutu; worker doldurur) |
| `fts` | `tsvector` | GENERATED ALWAYS AS `to_tsvector('simple', app.immutable_unaccent(text))` STORED — köklendirme yok, `fork()`/`TLB` gibi teknik tokenlar korunur |
| `created_at` | `timestamptz` | NOT NULL, DEFAULT `now()` |

**İndeksler:**
- `chunks_course_idx` — `(course_id)`
- `chunks_fts_idx` — GIN `(fts)`
- `chunks_embedding_idx` — HNSW `(embedding vector_cosine_ops)` WITH `(m = 16, ef_construction = 64)`; kosinüs mesafesi retrieval katmanıyla eşleşir

**RLS politikaları:**

| Politika | Komut | Kural |
|---|---|---|
| `chunks_member_read` | SELECT | `app.is_member(course_id)` |

INSERT/UPDATE/DELETE politikası **bilinçli olarak yoktur** — yazma yalnızca
`dou_worker`'ındır (BYPASSRLS; kullanıcı isteği bağlamında asla çalışmaz).

### 2.6 `ingestion_jobs`

Enum: `job_status = ('pending', 'processing', 'completed', 'failed')`.

| Alan | Tip | Kısıt |
|---|---|---|
| `id` | `uuid` | PK, DEFAULT `gen_random_uuid()` |
| `document_id` | `uuid` | NOT NULL, FK → `documents(id)` ON DELETE CASCADE |
| `status` | `job_status` | NOT NULL, DEFAULT `'pending'` |
| `attempt_count` | `integer` | NOT NULL, DEFAULT `0` |
| `last_error` | `text` | nullable |
| `started_at` | `timestamptz` | nullable |
| `completed_at` | `timestamptz` | nullable |
| `created_at` | `timestamptz` | NOT NULL, DEFAULT `now()` |

**İndeks:** `ingestion_jobs_pending_idx` — partial, `(created_at) WHERE status = 'pending'`;
worker `FOR UPDATE SKIP LOCKED` ile bu indeks üzerinden sıradaki işi çeker.

**RLS politikaları:**

| Politika | Komut | Kural |
|---|---|---|
| `jobs_instructor_read` | SELECT | `EXISTS (documents d WHERE d.id = document_id AND app.is_instructor(d.course_id))` |
| `jobs_instructor_insert` | INSERT | WITH CHECK — aynı EXISTS kuralı |

---

## 3. SECURITY DEFINER Fonksiyonları (uygulanmış, `app` şeması)

Hepsi `SET search_path = public, app` ile sabitlenmiştir (search_path hijack önlemi).

### 3.1 `app.is_member(p_course_id uuid) → boolean`

`STABLE SECURITY DEFINER`. Çağıranın (`app.current_user_id()`) derste `active`
üyeliği var mı? **SECURITY DEFINER gerekçesi:** politikalar bu fonksiyonu
çağırırken üyelik tablosunu okumak zorundadır; aksi halde `course_memberships`
üzerindeki RLS ile sonsuz özyineleme oluşur. Yalnızca boolean döndürür, satır
sızdırmaz.

### 3.2 `app.is_instructor(p_course_id uuid) → boolean`

`STABLE SECURITY DEFINER`. `is_member` ile aynı, ek koşul `role = 'instructor'`.

### 3.3 `app.create_course(p_code text, p_title text) → uuid`

`plpgsql SECURITY DEFINER`. Dersi ve oluşturanın eğitmen üyeliğini **tek
işlemde** yazar:

1. `app.current_user_id()` NULL ise → `insufficient_privilege` hatası
   ("oturum bağlamı ayarlanmamış") — fail-closed.
2. `INSERT INTO courses (code, title, created_by)` — `btrim` uygulanmış değerlerle.
3. `INSERT INTO course_memberships (course_id, user_id, 'instructor', 'active')`.
4. Yeni `course_id` döner.

**SECURITY DEFINER gerekçesi:** bootstrap adımında kullanıcının henüz üyeliği
yoktur; hiçbir RLS politikası "üyeliği olmayan ama bu dersi yaratan kişi"
durumunu okuma yüzeyini genişletmeden ifade edemez. Fonksiyon yalnızca çağıranın
**kendi adına** ders açmasına izin verir.

### 3.4 `app.add_course_member(p_course_id uuid, p_email text, p_role membership_role, OUT result text, OUT user_id uuid)`

`plpgsql SECURITY DEFINER`. Derse e-posta ile üye ekler:

1. **İlk adım yetki kontrolü:** `app.is_instructor(p_course_id)` değilse →
   `insufficient_privilege` ("ders eğitmeni değil"); hiçbir arama yapılmaz.
2. `profiles`'ta `lower(email)` eşleşmesi aranır; yoksa `result = 'no_user'`.
3. Mevcut üyelik durumuna göre:
   - `active` → `result = 'already_member'` (değişiklik yok)
   - üyelik yok → INSERT, `result = 'added'`
   - `revoked` → `status = 'active', role = p_role` UPDATE, `result = 'reactivated'`

**SECURITY DEFINER gerekçesi:** e-postadan kullanıcı bulmak `profiles`
üzerindeki RLS'i aşmayı gerektirir. Yetki kontrolü ilk adım olduğu için e-posta
numaralandırma (enumeration) yalnızca ilgili dersin eğitmenine açıktır ve
dışarıya profil satırı sızmaz.

### 3.5 `app.is_instructor_of(p_user_id uuid) → boolean`

`STABLE SECURITY DEFINER`. Çağıran, `p_user_id`'nin aktif üye olduğu herhangi
bir dersin aktif eğitmeni mi? `profiles_self_read` politikasında kullanılır:
eğitmen kendi öğrencilerinin profilini görür, öğrenciler birbirininkini göremez.

---

## 4. İlişki Özeti (uygulanmış)

```
profiles 1───n courses            (created_by, ON DELETE RESTRICT)
profiles 1───n course_memberships (user_id,   ON DELETE CASCADE)
courses  1───n course_memberships (course_id, ON DELETE CASCADE)
courses  1───n documents          (course_id, ON DELETE CASCADE)
profiles 1───n documents          (uploaded_by, ON DELETE RESTRICT)
courses  1───n chunks             (course_id, ON DELETE CASCADE — denormalize)
documents 1──n chunks             (document_id, ON DELETE CASCADE)
documents 1──n ingestion_jobs     (document_id, ON DELETE CASCADE)
```

Chunk kuralları (ARCHITECTURE.md §3): bir chunk iki sayfayı birleştirmez;
400–600 token, ~%15 overlap; kod dosyaları fonksiyon/sınıf sınırından bölünür;
`file_hash` ile tekrar embed engellenir.

---

## 5. PLANLANAN Varlıklar (ARCHITECTURE.md §3 — **henüz migration yok**)

Aşağıdaki tablolar ARCHITECTURE.md §3'teki taslaktan **aynen** aktarılmıştır.
Hiçbiri `supabase/migrations/` altında mevcut değildir; alan listeleri taslak
düzeyindedir ve migration yazılırken tip/kısıt/RLS detayları netleştirilecektir.
Uygulanmış tabloların desenleri (uuid PK, `course_id` FK + RLS, enum tipler,
FORCE RLS) bu tablolara da uygulanmalıdır.

### 5.1 `topics` — henüz migration yok

```
topics (id, course_id, name)          -- eğitmen tanımlar
```

Mastery-Lite ve soru havuzunun konu ekseni. `course_id` → `courses`.

> [NEEDS CLARIFICATION: Konu tekilliği (`UNIQUE (course_id, name)`?) ve
> RLS yazma politikası (yalnız eğitmen?) migration'da kararlaştırılacak.]

### 5.2 `questions` — henüz migration yok

```
questions (id, course_id, topic_id,
           type: mcq|open|code_trace|bug_hunt,     -- kod inceleme = ayrı soru tipleri
           payload jsonb, source_chunk_id, status: draft|approved|rejected)
```

PLAN.md P0 #10: soru havuzu JSON şemalı; **eğitmen onayı olmadan yayınlanmaz**
(`status: draft → approved`). `source_chunk_id` → `chunks` (üretimin dayandığı
kaynak; guardrail felsefesiyle tutarlı).

> [NEEDS CLARIFICATION: `payload` jsonb'nin tip bazlı şeması (MCQ şıkları,
> distractor→kaynak eşlemesi, code_trace beklenen çıktı, rubrik) Pydantic
> tarafında mı, CHECK constraint'le mi doğrulanacak?]

### 5.3 `exam_sessions` — henüz migration yok

```
exam_sessions (id, user_id, course_id, mode: practice|exam, started_at, ...)
```

PLAN.md P0 #8: süreli, ipucu kapalı, tek deneme. `mode = exam` politikaları
(hint kapalı, geri bildirim sınav sonunda) backend'de uygulanır (ARCHITECTURE §5).

> [NEEDS CLARIFICATION: §3'teki `...` — süre limiti, bitiş zamanı, durum alanı
> (in_progress|submitted|expired?) migration'da tanımlanacak.]

### 5.4 `answers` — henüz migration yok

```
answers (id, session_id, question_id, given, is_correct,
         feedback jsonb: {score, eksik_noktalar[], dayanak_chunk_id})
```

Açık uçlu değerlendirme şeması (ARCHITECTURE §5): `{score: 0-100,
eksik_noktalar: [...], dayanak_chunk_id}`; `dayanak_chunk_id` set-membership
kontrolünden geçer. `session_id` → `exam_sessions`, `question_id` → `questions`.

### 5.5 `mastery` — henüz migration yok

```
mastery (user_id, topic_id, score float, updated_at)
```

Konu bazlı EWMA: `yeni_puan = 0.7 × eski_puan + 0.3 × son_cevap_skoru`;
ipucu kademesi çarpanları 0→1.00 · 1→0.85 · 2→0.70 · 3→0.50 · 4→0.25;
eşikler <0.40 Geliştirilmeli · 0.40-0.74 Orta · ≥0.75 İyi (ARCHITECTURE §5).
Doğal PK adayı `(user_id, topic_id)`. Çıktı resmî not değil **çalışma önerisi
göstergesidir** (human-in-the-loop); arayüzde bu ibare yer alır.

### 5.6 `answer_cache` — henüz migration yok

```
answer_cache (course_id, question_hash, response jsonb)   -- exact-match demo cache (P0)
```

PLAN.md P0 #15: exact-match cache; demo senaryosu soruları önceden doldurulur
(offline sigortası, C planının veri kaynağı). Semantik cache bilinçli olarak
reddedildi (yanlış eşleşme = yanlış cevap).

### 5.7 `chat_sessions` / `chat_messages` — henüz migration yok

```
chat_sessions / chat_messages (mode: qa|socratic, state, citations jsonb)
```

Sokratik state machine durumu (`DIAGNOSE → NUDGE → CONCEPT_HINT →
SIMILAR_EXAMPLE → EXPLAIN_WITH_SOURCE`) backend'de tutulur; her kademe event
olarak loglanır. `citations jsonb` cevap şemasındaki
`[{chunk_id, claim}]` yapısını taşır; dosya adı + sayfa eşlemesini backend
`chunk_id` üzerinden kendisi yapar.

> [NEEDS CLARIFICATION: §3 iki tabloyu tek satırda listeler; alanların
> session/message dağılımı (state hangisinde, mode hangisinde) migration'da
> netleşecek. KVKK saklama süresi de burada uygulanır (ARCHITECTURE §6).]

### 5.8 `request_logs` — henüz migration yok

```
request_logs (redaction'lı; latency, status, course_id, token_count)
```

Gözlemleme katmanı (ARCHITECTURE §1): yapılandırılmış JSON log + request/hata
tabloları; loglarda key/TCKN/e-posta redaction (ARCHITECTURE §6). Günlük token
tüketimi kota bütçesi için buradan izlenir.

---

## 6. Migration Yol Haritası Notu

- Uygulanmış: `0001_core_schema.sql` (G1-G4 kapsamı: kurs/üyelik, ingestion,
  chunk/embedding altyapısı).
- Referans verilmiş ama **henüz yok**: `0002_supabase_auth_bridge.sql`
  (`profiles` yorumunda anılıyor).
- §5'teki tablolar sıradaki iş paketlerinin (soru üretici G8, sınav G9,
  mastery G9-G10, chat/Sokratik G7, demo cache G14) migration'larıyla gelecek.
