# Veri Modeli: 0016 Assessment Integrity

## `question_purpose`

```sql
CREATE TYPE question_purpose AS ENUM ('practice', 'assessment');
ALTER TABLE questions
  ADD COLUMN purpose question_purpose NOT NULL DEFAULT 'practice';
CREATE INDEX questions_course_purpose_approved_idx
  ON questions(course_id, purpose) WHERE status = 'approved';
```

Default yalnız kâğıtsız eski veri için geriye uyumluluktur. Migration yalnız
`exam_item` tarafından referanslanan soruyu `assessment` yapar. Aynı soru ayrıca
`exam_version_id IS NULL` legacy oturumun `question_ids` dizisindeyse özgün satır,
oturum dizisi ve `answers.question_id` değişmez; özgün soru `assessment` olur. Dar
own-session helper dalı yalnız o legacy oturum sahibinin eski referansla devamını
sağlar. Yeni practice seçimi yine yalnız `purpose=practice` kullanır; başka öğrenciye
ve gelecekteki practice havuzuna istisna yoktur. Uygulama yeni satırda amacı açıkça yazar.
Question identity, course, topic, type, source ve purpose terminal status sonrası değişmez.

## `exam_sessions.feedback_available_at`

```sql
ALTER TABLE exam_sessions
  ADD COLUMN feedback_available_at timestamptz;
```

- Blueprint session: başlangıçta `blueprint.closes_at + duration_minutes`; `closes_at`
  yoksa yeni session reddedilir.
- Migration öncesi blueprint session: kapanış varsa aynı güvenli formülle; yoksa
  migration DB saatinden bir tam blueprint süresi sonrasına muhafazakâr backfill edilir.
  Böylece eski aktif oturum bitirilebilir kalır ve sonuç erken açılmaz.
- Practice/legacy session: NULL; sonuç finish ile hemen açılır.
- Kolon UPDATE edilemez; yalnız INSERT anında yazılır. INSERT trigger'ı blueprint
  snapshot'ının `closes_at + duration_minutes` sınırından erken olmadığını bağımsız
  olarak doğrular; legacy/practice satırına gecikmeli tarih yazılamaz.

## RLS ilkesi

### Bağlantı rolleri

- `dou_app`: NOLOGIN, parolasız, `BYPASSRLS` taşımayan ortak izin taşıyıcısı.
- `dou_api_runtime`: LOGIN; `NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
  NOBYPASSRLS INHERIT`; `dou_app` üyeliği `INHERIT TRUE`, `SET FALSE`,
  `ADMIN FALSE`.
- `app.is_api_runtime()`: yalnız `session_user = 'dou_api_runtime'` için true.

Rol grafiği de fail-closed doğrulanır: `dou_app` hiçbir parent rolden miras alamaz;
`dou_api_runtime`ın üyesi yoktur ve runtime yalnız `dou_app` parent'ını taşıyabilir.
Bu kontroller, başka bir rolün hassas direct grant'leri dolaylı miras almasını veya
carrier'ın beklenmeyen geniş yetkiyi içeri çekmesini engeller.

Hassas `questions`, `answers`, `exam_sessions`, `exam_versions` ve `exam_items`
yüzeylerinde carrier'ın ilgili doğrudan ACL'leri çekilir; gerekli dar ACL runtime'a
verilir ve restrictive RLS gerçek bağlantı kimliğini zorlar. Yönetilen pooler
`session_user`ı korumalıdır; yalnız `SET ROLE` uyumlu değildir.

`ALTER DEFAULT PRIVILEGES` owner'a özeldir. `0016`, `public` gelecek tablolarında
`dou_app`/`dou_worker` için blanket SELECT/INSERT/UPDATE/DELETE bırakan bütün ilgili
`pg_default_acl` owner kayıtlarını normalize eder. Fonksiyonlarda PostgreSQL'in
hard-wired PUBLIC EXECUTE varsayılanı schema-local REVOKE ile kapanmadığından `app`
schema sahibi, mevcut `app` fonksiyon owner'ları ve current migration owner için
global REVOKE uygular; varsa schema-local PUBLIC grant'i de çeker. Etkin global
varsayılanı `acldefault` ile kontrol eder ve kalıntıda transaction'ı durdurur. Yeni
migration gereken runtime/worker ACL'ini açıkça vermelidir.

`questions_read`:

- instructor: dersin tüm soruları;
- student/member: yalnız `status=approved` ve
  - `purpose=practice`, veya
  - sorunun `exam_items` üzerinden current user's own `exam_session` kâğıdında olması,
    ya da
  - migration öncesi legacy own-session `question_ids` dizisinde zaten bulunması.

Policy içinden RLS'li tablo zincirine doğrudan recursive güven kurulmaz. Migration,
current user için boolean döndüren dar `SECURITY DEFINER` helper veya mevcut own-session
deseninin recursion-safe eşdeğerini kullanır; `PUBLIC` ve `dou_worker` execute edilirliği
açıkça çekilir.

`questions_instructor_update`, yalnız draft satır ve dar kolon grant'leriyle terminal
immutability'yi yapısal kılar. `dou_worker` assessment tablolarında write yetkisi almaz.

## İnvariantlar

1. Published/superseded `exam_items` question identity + payload + purpose değişmez.
   `exam_versions.blueprint_snapshot` ve yayın kanıtı da terminal durumda değişmez;
   yalnız published → superseded geçişinde `superseded_at` eklenebilir.
2. Existing own session, status/purpose değişse bile kâğıdını okuyabilir.
3. Yeni session'ın `feedback_available_at` değeri, started/expires zamanından bağımsız
   değiştirilemez; migration backfill'i bir kez ve veritabanı saatiyle yapılır.
4. Weighted score persisted `exam_sessions.score`'dan okunmaz.
5. Migration additive ve forward-only'dir; rollback kolon/enum drop etmez.
6. Migration sonrası uygulama bağlantısı ve rollback revizyonu `dou_api_runtime`
   kullanır; `dou_app` LOGIN/parolası geri açılmaz.
7. Mixed-use upgrade'de legacy session/answer kimlikleri değişmez; yalnız mevcut
   oturum sahibi dar own-session dalıyla görür, resmî kök assessment-only kalır.
8. Farklı owner'ların unsafe default ACL kalıntısı sessizce yaşayamaz.
