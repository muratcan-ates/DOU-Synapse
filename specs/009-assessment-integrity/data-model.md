# Veri Modeli: 0016 Assessment Integrity

## `question_purpose`

```sql
CREATE TYPE question_purpose AS ENUM ('practice', 'assessment');
ALTER TABLE questions
  ADD COLUMN purpose question_purpose NOT NULL DEFAULT 'practice';
CREATE INDEX questions_course_purpose_approved_idx
  ON questions(course_id, purpose) WHERE status = 'approved';
```

Default yalnız geriye uyumluluk/backfill içindir; uygulama yeni satırda amacı açıkça yazar.
Question identity, course, topic, type, source ve purpose terminal status sonrası değişmez.

## `exam_sessions.feedback_available_at`

```sql
ALTER TABLE exam_sessions
  ADD COLUMN feedback_available_at timestamptz;
```

- Blueprint session: başlangıçta `blueprint.closes_at + duration_minutes`; `closes_at`
  yoksa yeni session reddedilir.
- Practice/legacy session: NULL; sonuç finish ile hemen açılır.
- Kolon UPDATE edilemez; yalnız INSERT anında yazılır.

## RLS ilkesi

`questions_read`:

- instructor: dersin tüm soruları;
- student/member: yalnız `status=approved` ve
  - `purpose=practice`, veya
  - sorunun `exam_items` üzerinden current user's own `exam_session` kâğıdında olması.

Policy içinden RLS'li tablo zincirine doğrudan recursive güven kurulmaz. Migration,
current user için boolean döndüren dar `SECURITY DEFINER` helper veya mevcut own-session
deseninin recursion-safe eşdeğerini kullanır; `PUBLIC` ve `dou_worker` execute edilirliği
açıkça çekilir.

`questions_instructor_update`, yalnız draft satır ve dar kolon grant'leriyle terminal
immutability'yi yapısal kılar. `dou_worker` assessment tablolarında write yetkisi almaz.

## İnvariantlar

1. Published/superseded `exam_items` question identity + payload + purpose değişmez.
2. Existing own session, status/purpose değişse bile kâğıdını okuyabilir.
3. `feedback_available_at`, started/expires zamanından bağımsız ileri taşınmaz.
4. Weighted score persisted `exam_sessions.score`'dan okunmaz.
5. Migration additive ve forward-only'dir; rollback kolon/enum drop etmez.

