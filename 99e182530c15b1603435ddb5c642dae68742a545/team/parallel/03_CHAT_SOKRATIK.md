# Şerit 3 — Chat ucu + Sokratik motor

> **Önce `00_OKU_ONCE.md` dosyasını oku.** Bu belge yalnız senin şeridini anlatır.
> Branch: `feat/chat-socratic` · Görevler: T017-T020, T026-T028
> Bağımlılık: Şerit 1 ve 2'nin **imzası** (gövdesi değil) · Migration: **0003 senin**

---

## Neden bu şerit ürünün gösterilen yüzü

Danışmanın 10 Ağustos kapısı tek cümle: *"tarayıcıda login → ders → gerçek
materyale kaynaklı cevap."* O cümlenin backend'i sensin. Ve Sokratik mod — hocanın
toplantıda en çok üstünde durduğu şey — senin state machine'inde yaşıyor.

**Bağımlılığını beklemiyorsun.** `app/contracts.py`'de `Retriever` ve `Generator`
protokolleri tanımlı. Testlerinde bunları uygulayan sahte sınıflar yaz, üretim
yolunda gerçekleri çağır. Şerit 1 ve 2 `main`'e inince rebase alıp geçersin.

## Sahiplendiğin dosyalar

```
supabase/migrations/0003_chat.sql                YENİ  (numara SENİN)
apps/api/app/models/chat.py                      YENİ
apps/api/app/api/chat.py                         iskelet hazır, gövdeyi sen yaz
apps/api/app/modules/assessment/socratic.py      YENİ
apps/api/tests/test_chat_api.py                  YENİ
apps/api/tests/test_socratic.py                  YENİ
specs/001-course-assistant-mvp/tasks.md          yalnız T017-T020, T026-T028 satırları
```

`app/api/chat.py` **zaten var ve `main.py`'ye kayıtlı** — router tanımlı, gövde boş.
`main.py`'ye dokunma.

## Ne inşa ediyorsun

### T017 — Migration `0003_chat.sql`

Üç tablo. `0001_core_schema.sql` ve `0004_assessment.sql` desenini **birebir** izle:
her tabloda denormalize `course_id`, `ENABLE` + `FORCE ROW LEVEL SECURITY`,
politikalar `app.is_member()` / `app.is_instructor()` yardımcılarıyla.

**`chat_sessions`** — `course_id`, `user_id`, `mode` (qa|socratic), `state` (jsonb:
Sokratik kademe ve öğrenci denemesi burada yaşar), `created_at`, `updated_at`.

**`chat_messages`** — `session_id`, `course_id` (denormalize), `role`
(user|assistant), `content`, `citations` (jsonb), `status` (answered|
insufficient_context|out_of_scope), `socratic_stage`, `created_at`.

**`answer_cache`** — `course_id`, `question_hash`, `answer` (jsonb), `created_at`.
Tam eşleşmeli önbellek; demo günü aynı soruyu ikinci kez sormak ücretsiz ve anlık
olmalı.

**RLS'te dikkat — PR incelemesinde yakalanan hatayı tekrarlama:** denormalize
`course_id` taşıyan bir tabloya INSERT politikası yazarken **yalnız `user_id`
kontrolü yetmez.** `0004`'te bu unutulmuştu ve üye olmayan bir kullanıcı, üye
olmadığı dersin analitiğine satır enjekte edebiliyordu. Doğrusu:

```sql
CREATE POLICY chat_sessions_self_insert ON chat_sessions
    FOR INSERT WITH CHECK (
        user_id = app.current_user_id() AND app.is_member(course_id)
    );
```

`UPDATE` politikalarında `WITH CHECK` yazmayı unutma; yazılmazsa Postgres `USING`
ifadesini kullanır ve satırın başka bir derse **taşınmasını** engellemez.

`answer_cache` ders bazlıdır: bir dersin önbelleği başka derse **asla** servis
edilmez, yoksa izolasyon tezinin tamamı çöker.

### T018 — Modeller (`models/chat.py`)

`app/models/core.py` ve `app/models/assessment.py` desenini izle. Migration'lar
düz SQL'dir, ORM'den üretilmez; modeller şemayı **yansıtır**.

### T019 — Chat ucu (`api/chat.py`)

`POST /courses/{course_id}/chat`. Akış:

1. `CourseMemberDep` ile yetki (kendi üyelik sorgunu **yazma**)
2. `answer_cache` tam eşleşme kontrolü → varsa dön
3. Retrieval (`Retriever.search`)
4. Kanıt eşiği: yetersizse `insufficient_context`, LLM'e hiç gitme
5. Generation (`Generator.generate`)
6. Guardrail zinciri (Şerit 2'nin `chain.py`'si — sırayı sen kurmuyorsun)
7. Bloklandıysa abstention; geçtiyse kaydet ve dön

**Kapsam dışı ile yetersiz kanıt farklı durumlardır.** İkisi de "cevap yok" ama
mesajları ve ölçüm kategorileri ayrı (SC-005 yalnız `out_of_scope`'u ölçer).
Karıştırma.

Sokratik modda cevap yerine **kademeye uygun ipucu** döner ve kademe
`chat_sessions.state`'e yazılır.

### T026 — Sokratik state machine (`modules/assessment/socratic.py`)

Merdiven `app/contracts.py`'de tanımlı:

```
DIAGNOSE → NUDGE → CONCEPT_HINT → SIMILAR_EXAMPLE → EXPLAIN_WITH_SOURCE
```

**Pazarlıksız kurallar:**

1. **Öğrenci kendi denemesini yapmadan kademe İLERLEMEZ.** Bu kural prompt'a
   bırakılmaz, state machine'de zorlanır. "Sadece söyle" diyen öğrenci nazikçe
   reddedilir ve aynı kademede kalınır.
2. **İpuçları da uydurulmaz** — retrieve edilen chunk'tan türetilir ve `chunk_id`
   taşır. Kaynaksız ipucu, guardrail'den geçemez (Anayasa I ipuçlarını da kapsar).
3. **Her kademe geçişi event olarak loglanır** — sonradan "sistem gerçekten
   yönlendirdi mi" sorusuna cevap verebilmek için.
4. **Sınav modunda ipucu tamamen kapalıdır.**
5. State kalıcıdır: oturum yeniden yüklense de kademe korunur.

Öğrencinin "denemesi" ne sayılır? Bu bir tasarım kararı ve **sen vereceksin**.
Öneri: boş olmayan, sorunun konusuna dair bir metin. Ama "bilmiyorum" bir deneme
midir? Kararını ve gerekçeni docstring'e yaz; jüri bunu soracak.

### T020 + T028 — Testler

`test_chat_api.py`:
1. **Kaynaksız akademik cevap asla dönmez**
2. Kapsam dışı soru `out_of_scope` + nazik Türkçe metin
3. Yetersiz kanıt `insufficient_context` — ve bu ikisi karışmıyor
4. Başka dersin materyali cevaba karışmıyor (izolasyon)
5. `answer_cache` ders bazlı — A dersinin önbelleği B'ye servis edilmiyor
6. Üye olmayan 404 alıyor (403 değil)

`test_socratic.py` (tasks.md beş vaka sayıyor):
1. İlk turda cevap verilmez
2. Deneme olmadan kademe atlanmaz
3. Kaynaksız hint bloklanır
4. Israrcı öğrenci senaryosunda şablon ipucuna düşülür
5. State kalıcı — oturum yeniden yüklense de kademe korunur

## Sıra önerisi

1. `0003_chat.sql` — şema olmadan hiçbir şey test edilemez. RLS politikalarını
   yazarken yukarıdaki uyarıyı tekrar oku.
2. `models/chat.py`
3. `socratic.py` — **saf state machine olarak yaz**, veritabanından bağımsız.
   Böylece testleri hızlı ve DB'siz koşar. Kalıcılık `chat.py`'nin işi.
4. `test_socratic.py` — beş vaka, DB'siz, hızlı yeşil
5. `api/chat.py` — sahte `Retriever`/`Generator` ile
6. `test_chat_api.py`
7. Şerit 1 ve 2 indiğinde rebase al, gerçeklere geç, elle bir kez dene

## Bitti sayılma ölçütü

- [ ] `pytest -q` yeşil, `ruff` temiz
- [ ] `0003` sıfırdan bir veritabanına hatasız uygulanıyor
- [ ] RLS: üye olmayan kullanıcı chat oturumu açamıyor — **psql ile fiilen
      denendi**, sadece test değil
- [ ] Sokratik merdiven beş vakayı da geçiyor
- [ ] Gerçek retrieval + generation indiğinde: tarayıcıda gerçek materyale
      kaynaklı cevap alındı ve **sayfa numarası göründü** (Anayasa VIII)
- [ ] OpenAPI sözleşmesi oturumun sonunda yeniden export edildi
- [ ] `tasks.md`'de T017-T020, T026-T028 `[x]` + tarihli DONE notu

## Bittiğinde

Gruba haber ver: **chat ucu ve cevap sözleşmesi hazır.** Lider frontend'i buna
bağlayacak (T021-T022) — sen `apps/web`'e dokunma.

Vaktin kalırsa: **T023 Supabase Auth köprüsü** (`0002` migration, ayrılmış numara).
Ama önce gruba sor; auth değişikliği herkesi etkiler.
