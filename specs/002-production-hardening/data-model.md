# Veri Modeli — 002 Production Hardening

**Kaynaklar ve doğruluk sırası:**

1. **UYGULANMIŞ şema** — tek gerçek: `supabase/migrations/0001…0012`.
2. Bu belge `0008…0011` göçlerinin tasarım gerekçesidir; dördü de uygulanmıştır.
   `0012_privacy_rights.sql` kullanıcı haklarının sonradan eklenen veri kapısıdır.
3. `specs/002-production-hardening/spec.md` (FR numaraları) ve `.specify/memory/constitution.md` (İlke II, III, IV, V, XI).

001'in veri modeli belgesi "uygulanmış / planlanan" ayrımını başlıklarla tutuyordu; bu belge aynı ayrımı **migration numarası** ekseninde tutar: her bölüm tek bir göç dosyasını anlatır ve o dosya yazıldığında bu belge değil kod birincil kaynak olur.

> **Şartname düzeltmesi (bilinçli, spec'e geri işlenecek):** spec.md Key Entities bölümü sekiz varlık sayar ve dış inceleme "mevcut `exams` tablosu" varsayar. Depoda `exams` diye bir tablo **yoktur**; en yakın tablo `exam_sessions`'dır (`0004_assessment.sql:74-91`) ve o bir öğretmen ürünü değil, **bir öğrencinin tek denemesidir**. Sekiz varlığın beşi tablo olur, üçü kolonla çözülür (§2.14). Gerekçeler ilgili bölümlerdedir.

---

## 0. Kapsam, göç numaralandırması ve neden dört dosya

002'nin tasarladığı dört göç uygulanmıştır:

| Dosya | Kapsam | FR | Bölüm |
|---|---|---|---|
| `0008_exam_blueprint.sql` | Sınav blueprint ailesi (5 yeni tablo, 3 mevcut tabloya kolon, 2 yardımcı fonksiyon, RLS + yetki) | FR-110…FR-119 | §2 |
| `0009_course_ai_policy.sql` | Ders AI politikası + değişiklik izi | FR-130…FR-137 | §3 |
| `0010_ingestion_retry.sql` | Belge işleme işlerinin geri çekilmeli yeniden denemesi ve elle yeniden çalıştırılması | FR-213, FR-214 | §4 |
| `0011_pagination_indexes.sql` | Anahtar-kümesi (keyset) sayfalamanın gerektirdiği belirlenimci sıralama indeksleri | FR-160…FR-163 | §5 |

**Neden tek dosya değil.** Deponun yerleşik âdeti "bir göç = bir iş"tir (`0005_analytics.sql:3` "TEK İŞ", `0006_embedding_provenance.sql:3` "TEK İŞ"). Dördü tek dosyaya konsaydı, sayfalama indeksinden dönen bir hata blueprint şemasının tamamını geri alırdı ve göç dosyası "niçin" yerine "neler" anlatan bir liste hâline gelirdi.

**Neden 0008 blueprint, 0009 politika.** Araştırma fazında iki ayrı şerit aynı numarayı (`0008`) talep etti: biri `0008_exam_blueprint.sql`, diğeri `0008_course_ai_policy.sql`. Çakışma burada çözülüyor: blueprint 0008'i alır, çünkü `exam_sessions_self_insert` politikasını DROP+CREATE ile yeniden kurar (§2.12) ve politika dosyasının böyle bir mevcut-politika müdahalesi yoktur; sıralamada daha kırılgan olan önce gider. Politika göçünün 0008'e bağımlılığı yoktur, tersi de doğrudur — ikisi bağımsızca uygulanabilir ama numaralar sıralı kalır.

**Uygulama sırası bağlayıcıdır:** 0008 → 0009 → 0010 → 0011. 0011, `questions` üzerindeki indeksleri 0008'in eklediği `questions_cell_idx` ile birlikte değerlendirdiği için en sona konmuştur (§5.3).

---

## 1. Şema değişikliği GETİRMEYEN hikâyeler

Bu bölüm "eksik" değil, **karar**dır: aşağıdaki hikâyeler kod işidir ve veritabanına dokunmaz. Yazılmasının sebebi US8'dir (belge-kod tutarlılığı): bir sonraki inceleme "blueprint geldi ama sınav kilidi için tablo yok" diye rapor yazmasın.

| Hikâye | Neden şema yok |
|---|---|
| **US1 — Sınav oturumu kilidi** (FR-101…FR-106) | Kilit, var olan `exam_sessions` satırına bakan bir sorgudur: `mode='exam' AND finished_at IS NULL AND expires_at > now()` + Python tarafındaki kırpma kuralı. Yeni kolon gerekmez. **Yeni indeks de eklenmiyor:** mevcut `exam_sessions_user_idx (user_id, started_at DESC)` (`0004_assessment.sql:94`) sorgunun öncü yüklemini karşılar; ek indeks Anayasa XI'in "ölçmeden karmaşıklık ekleme" kuralına takılır. Ölçüm yapılırsa ve gerekirse doğru düzeltme `CREATE INDEX exam_sessions_active_idx ON exam_sessions (user_id, course_id) WHERE finished_at IS NULL` kısmi indeksidir — **bugün eklenmiyor**. |
| **US2 — Bilinen kusurlar** (FR-220…FR-224) | Event loop bloklanması (thread havuzu), ısıtma, hız sınırı ve issuer ayar adı; hepsi uygulama katmanı. Eşzamanlı ikinci soru üretimini engellemek için de tablo gerekmez: tek replikalı topolojide süreç içi kilit ya da `pg_try_advisory_xact_lock` yeter ve ikisi de şemasızdır. |
| **US5 — Hata deneyimi** (FR-150…FR-156) | İstek kimliği yanıt zarfında ve logda taşınır; `request_logs` şemasına yazılmaz (o tablo `0003_chat.sql:132-134` gereği yalnız sayısal/kategorik alan taşır ve bu kısıt korunuyor). |
| **US7 — Gerçek kimlik** (FR-170…FR-173) | `0002_supabase_auth_bridge.sql` köprüsü zaten uygulanmış. Eksik olan arayüz ayağı ve bir ortam değişkeni adı. |
| **US8 — Belge doğruluğu** | Belge işi. |
| **US9 — Test verisi hijyeni** (FR-190…FR-192) | Temizlik, test desenini (`code`/`email` öneki) tanıyan bir komuttur. **Yeni bir `is_test_data` kolonu eklenmiyor:** üretim şemasına yalnız testler için kolon açmak, üretim verisine test kavramı sokar; desen tanıma yeterlidir ve `courses_code_key` (`0001_core_schema.sql:64`) zaten deseni tekilleştirir. |
| **US10 — Kullanıcı hakları** (FR-200…FR-203) | P3. Sohbet silme ve dışa aktarma mevcut tablolar üzerinde çalışır (`chat_sessions` ON DELETE CASCADE zinciri, `0003_chat.sql:68`). **Hesap silme talebi** için bir kuyruk tablosu gerekebilir — bu belgede tanımlanmadı, §8'de açık soru olarak duruyor. |

---

## 2. `0008_exam_blueprint.sql` — Sınav blueprint ailesi

### 2.0 Sekiz varlık, beş tablo: hangisi neden tablo değil

| spec.md'deki varlık | Kararı | Gerekçe |
|---|---|---|
| Öğrenme çıktısı | **Tablo** `learning_outcomes` | Bağımsız ömrü var, birden çok soru ve hücre ona bağlanıyor. |
| Sınav blueprint'i | **Tablo** `exam_blueprints` | — |
| Dağılım hücreleri | **Tablo** `blueprint_cells` | FR-114 "hangi hücrenin eksik olduğunu söyle" der; adreslenebilir hücre = `GROUP BY` edilebilir satır (§2.5). |
| Sınav sürümü | **Tablo** `exam_versions` | FR-115 dondurma ister. |
| Sürüm kalemleri | **Tablo** `exam_items` | Kâğıdın sırası ve puanı sürüme aittir. |
| `question_learning_outcomes` (M:N) | **Kolon** `questions.learning_outcome_id` | FR-113 tekil kardinalite istiyor ("her taslak **bir** öğrenme çıktısına ... bağlı gelmelidir"). Çoğa-çok, FR-112/FR-114 aritmetiğini imkânsız kılar: bir soru iki hücreye sayılırsa hücre toplamları soru sayısına eşitlenemez ve SC-003'ün "birebir uyar" iddiası karar verilemez hâle gelir. |
| `rubrics` | **Kolon değil, var olan yapı**: `questions.payload.rubric` | Rubrik zaten var (`apps/api/app/schemas/assessment.py:95-98`, `:105`) ve değerlendirme onu zaten okuyor. İkinci bir ev açmak aynı ürün kuralını iki yere yazmaktır (Anayasa XI). spec.md:346 de rubriği soruya bağlıyor, paylaşılan varlık demiyor. |
| `exam_publications` | **Kolonlar**: `exam_blueprints.opens_at/closes_at` + `exam_versions.status/published_at/published_by` | FR-111 yayın penceresini blueprint'in **alanı** olarak sayıyor. Ayrı tabloda "bir sınavın aynı anda tek yayınlanmış sürümü olur" kuralı iki tablo arasında uygulama koduyla korunurdu; sürümde kolon olunca kısmi tekil indeksle **yapısal** olur (§2.6). |

### 2.1 Yeni enum'lar

```sql
CREATE TYPE question_difficulty  AS ENUM ('easy', 'medium', 'hard');
CREATE TYPE exam_version_status  AS ENUM ('draft', 'published', 'superseded');
```

`0004_assessment.sql:19-21` deseni: enum'lar göçte tanımlanır, ORM yaratmaz (`apps/api/app/models/base.py:20-38`, `pg_enum(..., create_type=False)`). Değerler küçük harflidir; Python tarafında `StrEnum` üyeleri bu değerlere bağlanır.

### 2.2 `learning_outcomes`

Dersin ölçülebilir kazanımı. Soru, hücre ve raporlama bu eksene bağlanır.

| Alan | Tip | Kısıt |
|---|---|---|
| `id` | `uuid` | PK, DEFAULT `gen_random_uuid()` |
| `course_id` | `uuid` | NOT NULL, FK → `courses(id)` ON DELETE CASCADE |
| `code` | `text` | NOT NULL; CHECK `length(btrim(code)) > 0` (`learning_outcomes_code_not_blank`) |
| `description` | `text` | NOT NULL |
| `topic_id` | `uuid` | nullable, FK → `topics(id)` ON DELETE SET NULL |
| `created_by` | `uuid` | NOT NULL, FK → `profiles(id)` ON DELETE RESTRICT |
| `created_at` | `timestamptz` | NOT NULL, DEFAULT `now()` |

**İndeksler:**
- `learning_outcomes_course_code_key` — UNIQUE `(course_id, lower(code))`. `topics_course_name_key` (`0004_assessment.sql:37`) ve `courses_code_key` (`0001_core_schema.sql:64`) ile aynı desen: derste kod büyük/küçük harf duyarsız tekildir.
- `learning_outcomes_course_idx` — `(course_id)`.

**RLS politikaları** (`topics`'in birebir kopyası, `0004_assessment.sql:158-166`):

| Politika | Komut | Kural |
|---|---|---|
| `learning_outcomes_member_read` | SELECT | `app.is_member(course_id)` |
| `learning_outcomes_instructor_write` | INSERT | WITH CHECK `app.is_instructor(course_id)` |
| `learning_outcomes_instructor_update` | UPDATE | USING + WITH CHECK `app.is_instructor(course_id)` |
| `learning_outcomes_instructor_delete` | DELETE | `app.is_instructor(course_id)` |

UPDATE'e WITH CHECK bilerek yazılıyor: yazılmazsa PostgreSQL güncellenen satır için USING'i kullanır ve satırın **başka bir derse taşınmasını** engellemez (`0003_chat.sql:16-18`).

**Neden ayrı tablo, neden `topics`'e katılmadı.** `topics` mastery'nin birincil anahtarının parçasıdır (`0004_assessment.sql:136`, `PRIMARY KEY (user_id, topic_id)`) ve soru üretiminin retrieval sorgusu `topic.name`'dir. Konu bir **arama kolu**, çıktı bir **ölçülebilir iddia**dır. Birleştirmek mastery semantiğini ve ölçülmüş retrieval davranışını aynı anda değiştirirdi (Anayasa III). `topic_id` köprüsü ise üretimin bugünkü davranışını korumak için var: çıktı bir konuya bağlıysa soru üretimi bugünkü sorgusunu aynen kullanır.

**Konu ekseni notu (FR-111 "konu dağılımı").** Konu dağılımı **ayrı bir hücre ekseni değildir**; `blueprint_cells → learning_outcomes.topic_id` üzerinden türetilir. Ayrı eksen yapılsaydı hücre dörtlüsü beşliye çıkar, olası hücre sayısı konu sayısıyla çarpılır ve öğretmenin doldurması gereken tablo pratikte doldurulamaz hâle gelirdi. Bedeli: `topic_id`'si NULL olan bir çıktının konu ekseni yoktur ve iki çıktı aynı konuya bağlıysa konu dağılımı bir toplulaştırmadır. Bu bir kabul, bir kusur değil — ama §8'de açık soru olarak duruyor.

### 2.3 `questions` — değişen (mevcut tablo)

```sql
ALTER TABLE questions
    ADD COLUMN learning_outcome_id uuid REFERENCES learning_outcomes(id) ON DELETE SET NULL,
    ADD COLUMN difficulty question_difficulty;
```

| Kolon | Varsayılan | Bugünkü davranışı neden değiştirmez |
|---|---|---|
| `learning_outcome_id` | **NULL** (varsayılan yok) | Mevcut satırlar NULL kalır. Soru havuzu listesi `course_id`, `status` ve `topic_id` ile süzer (`apps/api/app/api/questions.py:134-142`); yeni kolona bakan tek şey yayın kapısıdır ve o yalnız blueprint akışında koşar. Prova sınavı soruları rastgele çeker, bu kolona bakmaz. |
| `difficulty` | **NULL** | Aynı. Zorluk bugün hiçbir yerde okunmuyor. |

**NOT NULL neden değil.** `0006_embedding_provenance.sql:33-37`'nin yazdığı gerekçe birebir geçerli: "NOT NULL + varsayılan değer koymak, bilmediğimiz bir şeyi biliyormuş gibi yazmak olurdu". Havuzdaki bir sorunun hangi kazanımı ölçtüğünü göç bilemez; `'medium'` gibi bir varsayılan, ölçülmemiş bir iddiayı veriye yazmak olurdu (Anayasa III).

**Bedeli açıkça yazılıyor:** "her soru bir çıktıya bağlıdır" kuralı **veri düzeyinde garanti değildir**. Kuralı zorlayan tek yer yayın kapısıdır (§2.5); kapı yakalamazsa çıktısı NULL bir soru hiçbir hücreye sayılmaz ve sınav sessizce eksik yayınlanır. FR-114 testi bu senaryoyu açıkça kapsamalıdır.

**Yeni indeks:**
```sql
CREATE INDEX questions_cell_idx ON questions (course_id, learning_outcome_id, difficulty, type)
    WHERE status = 'approved';
```
Hücre doldurma ("bu hücreye uyan onaylı sorular") ve yayın kapısı bu indeksten okunur. Kısmi indeks deseni `ingestion_jobs_pending_idx` (`0001_core_schema.sql:284-285`) ile aynıdır: sorgu zaten yalnız `approved` satırlarla ilgilenir.

### 2.4 `exam_blueprints`

Sınavın çatısı. Sorulardan **önce** vardır.

| Alan | Tip | Kısıt |
|---|---|---|
| `id` | `uuid` | PK, DEFAULT `gen_random_uuid()` |
| `course_id` | `uuid` | NOT NULL, FK → `courses(id)` ON DELETE CASCADE |
| `title` | `text` | NOT NULL; CHECK `length(btrim(title)) > 0` |
| `description` | `text` | nullable |
| `duration_minutes` | `integer` | NOT NULL, CHECK `BETWEEN 1 AND 600` |
| `max_attempts` | `smallint` | NOT NULL, DEFAULT `1`, CHECK `>= 1` |
| `opens_at` | `timestamptz` | nullable (NULL = başlangıç sınırı yok) |
| `closes_at` | `timestamptz` | nullable (NULL = bitiş sınırı yok) |
| `created_by` | `uuid` | NOT NULL, FK → `profiles(id)` ON DELETE RESTRICT |
| `created_at` | `timestamptz` | NOT NULL, DEFAULT `now()` |
| `updated_at` | `timestamptz` | NOT NULL, DEFAULT `now()` |

**Kısıtlar:** `exam_blueprints_window_order` — `CHECK (opens_at IS NULL OR closes_at IS NULL OR opens_at < closes_at)`. Ters pencere ifade edilemez olmalıdır; `0004_assessment.sql:88-90`'ın (`exam_sessions_exam_has_expiry`) kurduğu "geçersiz durumu ifade edilemez kıl" deseni.

**İndeks:** `exam_blueprints_course_idx` — `(course_id, created_at DESC, id DESC)` (sayfalama için baştan doğru; §5).

**`duration_minutes` neden burada, `exam_question_count` neden burada değil.** Süre FR-111'in açıkça saydığı bir blueprint alanıdır ve global `exam_duration_minutes = 20` (`apps/api/app/core/config.py:158`) bundan sonra yalnız **prova** akışının varsayılanıdır. Toplam soru sayısı ise **kolon değildir**: `SUM(blueprint_cells.question_count)`'tur. Türetilmiş olduğu için tutarsız olamaz — spec.md:235'in saydığı hata sınıflarından biri (tip toplamları adetle eşleşmiyor) tanımdan silinir.

**RLS politikaları:**

| Politika | Komut | Kural |
|---|---|---|
| `exam_blueprints_read` | SELECT | `app.is_instructor(course_id) OR (app.is_member(course_id) AND app.blueprint_open_to_students(id))` |
| `exam_blueprints_instructor_insert` | INSERT | WITH CHECK `app.is_instructor(course_id)` |
| `exam_blueprints_instructor_update` | UPDATE | USING + WITH CHECK `app.is_instructor(course_id)` |
| `exam_blueprints_instructor_delete` | DELETE | `app.is_instructor(course_id)` |

Okuma politikası `questions_read`'in (`0004_assessment.sql:168-174`, dosyanın "EN KRİTİK politika" dediği satırlar) yapısal ikizidir: *eğitmen hepsini görür, üye yalnız serbest bırakılmış alt kümeyi görür*. Orada serbest bırakan şey `status='approved'`, burada `yayınlanmış sürüm + açık pencere`. Böylece spec senaryo 1 ("blueprint taslak olarak kaydedilir ve öğrenciye görünmez") ve FR-116 aynı politikayla karşılanır.

### 2.5 `blueprint_cells`

Dağılımın atomik birimi: *(çıktı × zorluk × tip) → kaç soru, kaçar puan*.

| Alan | Tip | Kısıt |
|---|---|---|
| `id` | `uuid` | PK, DEFAULT `gen_random_uuid()` |
| `course_id` | `uuid` | NOT NULL, FK → `courses(id)` ON DELETE CASCADE — **denormalize** |
| `blueprint_id` | `uuid` | NOT NULL, FK → `exam_blueprints(id)` ON DELETE CASCADE |
| `learning_outcome_id` | `uuid` | NOT NULL, FK → `learning_outcomes(id)` ON DELETE RESTRICT |
| `difficulty` | `question_difficulty` | NOT NULL |
| `question_type` | `question_type` | NOT NULL (0004'ün enum'u) |
| `question_count` | `smallint` | NOT NULL, CHECK `BETWEEN 1 AND 100` |
| `points_per_question` | `smallint` | NOT NULL, DEFAULT `1`, CHECK `BETWEEN 1 AND 100` |

**Kısıt:** `UNIQUE (blueprint_id, learning_outcome_id, difficulty, question_type)` — aynı hücre iki kez tanımlanamaz. Bu, FR-112'nin bir bölümünü uygulama koduna hiç sormadan kapatır.

`ON DELETE RESTRICT` bilinçli: bir blueprint'te kullanılan öğrenme çıktısı silinemez. `questions.source_chunk_id` (`0004_assessment.sql:55`) ile aynı gerekçe — dayanağı silinmiş bir kural, doğrulanamayan bir kuraldır.

**RLS politikaları:**

| Politika | Komut | Kural |
|---|---|---|
| `blueprint_cells_instructor_read` | SELECT | `app.is_instructor(course_id)` |
| `blueprint_cells_instructor_insert` | INSERT | WITH CHECK `app.is_instructor(course_id)` |
| `blueprint_cells_instructor_delete` | DELETE | `app.is_instructor(course_id)` |

**Öğrenciye SELECT politikası BİLEREK YOKTUR.** "Bu sınavda 2 zor açık uçlu var" bilgisi sınav öncesi istihbarattır. Kapalı doğup gerekirse gerekçesiyle açmak deponun yazılı alışkanlığıdır: `request_logs` 0003'te tamamen kapatıldı, 0005'te dar bir kapsamla açıldı (`0005_analytics.sql:3-13`).

**UPDATE politikası da yoktur ve yetki de çekilir** (§2.11). Hücre kümesi bütün olarak DELETE+INSERT ile değişir. Gerekçe: FR-112 doğrulaması **küme üzerinde** yapılır (marjinaller birbirini tutuyor mu); tek hücrelik bir UPDATE doğrulamayı atlayıp tutarsız bir dağılım bırakabilirdi. Bedeli, düzenleme akışının tek işlemde silip yazmak zorunda olmasıdır.

**Neden JSONB değil.** Bu depo JSONB'yi iki gerekçeyle seçmiş: **varyant şekil** (`questions.payload`, dört tipin ortak zarfı, `0004_assessment.sql:50-52`) ve **şemasız büyüyecek durum** (`chat_sessions.state`, `0003_chat.sql:46-51`). Blueprint hücresi ikisi de değil: sabit dört alanlı bir demet ve üzerinde **toplama** yapılıyor. FR-114'ün istediği "eksik hücreler" raporu tek sorguya iniyor:

```sql
SELECT c.learning_outcome_id, c.difficulty, c.question_type,
       c.question_count, coalesce(f.filled, 0) AS filled
FROM blueprint_cells c
LEFT JOIN (
    SELECT q.learning_outcome_id, q.difficulty, q.type, count(*) AS filled
    FROM exam_items i JOIN questions q ON q.id = i.question_id
    WHERE i.exam_version_id = :version AND q.status = 'approved'
    GROUP BY 1, 2, 3
) f ON (f.learning_outcome_id, f.difficulty, f.type)
     = (c.learning_outcome_id, c.difficulty, c.question_type)
WHERE c.blueprint_id = :blueprint
  AND coalesce(f.filled, 0) <> c.question_count;
```

Dönen her satır bir eksik/fazla hücredir; **boş küme = yayınlanabilir**. JSONB'de bu diff Python'da elle üretilirdi ve `UNIQUE` ile çift hücre engellenemezdi.

**Yüzdeler SAKLANMAZ.** Arayüz "%40 kolay / %40 orta / %20 zor + 5 MCQ / 2 açık uçlu" alır, API bunu tam sayı hücrelere açar, saklanan gerçek **adet**tir. Gerekçe SC-003: %40 × 7 = 2,8 ve yuvarlama kuralı saklanan veride görünmezse "birebir uyar" karar verilemez hâle gelir.

**FR-112 neden DB CHECK'te değil.** Satır **içi** olgular CHECK'te (`question_count`, `points_per_question`, UNIQUE). Satırlar **arası** aritmetik ve Türkçe hücre adlı hata mesajı uygulama katmanında saf bir doğrulayıcı fonksiyondadır. İki sebep: (i) CHECK diğer satırlara bakamaz, tek alternatif trigger'dır ve bu depoda `public` şemasındaki hiçbir iş kuralı trigger'a yazılmamıştır (tek trigger `0002_supabase_auth_bridge.sql:191-207`, `auth.users` köprüsü ve ayrı bir rolün sahipliğinde); (ii) kısıt ihlali PostgreSQL'den kısıt adıyla döner, "Zor MCQ hücresi 2 soru istiyor ama 1 tane var" cümlesini üretemez — Anayasa V "backend tek hata zarfı üretir; frontend kendi hata metnini uydurmaz" der.

### 2.6 `exam_versions`

Yayınlanmış bir sınavın dondurulmuş hâli. Oturumlar buna bağlanır.

| Alan | Tip | Kısıt |
|---|---|---|
| `id` | `uuid` | PK, DEFAULT `gen_random_uuid()` |
| `course_id` | `uuid` | NOT NULL, FK → `courses(id)` ON DELETE CASCADE — denormalize |
| `blueprint_id` | `uuid` | NOT NULL, FK → `exam_blueprints(id)` ON DELETE CASCADE |
| `version_no` | `smallint` | NOT NULL, CHECK `>= 1`; UNIQUE `(blueprint_id, version_no)` |
| `status` | `exam_version_status` | NOT NULL, DEFAULT `'draft'` |
| `published_at` | `timestamptz` | nullable |
| `published_by` | `uuid` | nullable, FK → `profiles(id)` ON DELETE SET NULL |
| `superseded_at` | `timestamptz` | nullable |
| `blueprint_snapshot` | `jsonb` | nullable; yayın anında yazılır (§8 madde 1) |
| `created_at` | `timestamptz` | NOT NULL, DEFAULT `now()` |

**Kısıtlar:**

```sql
CONSTRAINT exam_versions_publish_consistency CHECK (
     (status = 'draft'      AND published_at IS NULL     AND published_by IS NULL     AND superseded_at IS NULL     AND blueprint_snapshot IS NULL)
  OR (status = 'published'  AND published_at IS NOT NULL AND published_by IS NOT NULL AND superseded_at IS NULL     AND blueprint_snapshot IS NOT NULL)
  OR (status = 'superseded' AND published_at IS NOT NULL AND superseded_at IS NOT NULL AND blueprint_snapshot IS NOT NULL))
```

`questions_reviewed_consistency` (`0004_assessment.sql:61-64`) ile birebir aynı kalıp: durum ile damgalar birlikte tutarlı olmak zorundadır.

```sql
CREATE UNIQUE INDEX exam_versions_one_published ON exam_versions (blueprint_id)
    WHERE status = 'published';
```

"Bir blueprint'in aynı anda tek yayınlanmış sürümü olur" kuralı **yapısal**dır; uygulama koduna sorulmaz.

**RLS politikaları:**

| Politika | Komut | Kural |
|---|---|---|
| `exam_versions_read` | SELECT | `app.is_instructor(course_id)` **OR** `(app.is_member(course_id) AND app.is_exam_open(id, course_id))` **OR** `EXISTS (SELECT 1 FROM exam_sessions s WHERE s.exam_version_id = exam_versions.id AND s.user_id = app.current_user_id())` |
| `exam_versions_instructor_insert` | INSERT | WITH CHECK `app.is_instructor(course_id)` |
| `exam_versions_instructor_update` | UPDATE | USING + WITH CHECK `app.is_instructor(course_id)` (yalnız §2.11'deki kolonlar yazılabilir) |
| `exam_versions_instructor_delete` | DELETE | `app.is_instructor(course_id) AND status = 'draft'` |

Üçüncü OR dalı FR-115'in okuma ayağıdır: **pencere kapansa da yürüyen oturumun sahibi kendi sürümünü görmeye devam eder.** FR-116 "kapandığında **yeni** oturum başlatamaz" der, başlamışı düşürmez. Bu dal `answers_self_read`'in (`0004_assessment.sql:197-204`) EXISTS kalıbının aynısıdır ve `exam_sessions_self_read` sayesinde kullanıcı kendi oturumunu zaten görebildiği için ek bir SECURITY DEFINER yardımcısı gerektirmez.

DELETE'in `status='draft'` koşulu: yayınlanmış bir sürüm silinemez — silinseydi ona bağlı oturumların kanıtı yok olurdu (zaten `exam_sessions.exam_version_id` RESTRICT ile de kapalı, §2.8; iki katman).

**Neden snapshot değil, sürüm tablosu.** Bu depoda soru **içeriği** zaten değişmezdir: `apps/api/app/api/questions.py`'de soruyu düzenleyen hiçbir uç yok (yalnız generate / approve / reject / delete). İçerik değişmezse **kimlikle referans, kopyayla saklama kadar sağlamdır** ve kopya yalnız (öğrenci sayısı × tam payload) şişkinliği getirir. Dahası snapshot aktif olarak zararlı olurdu: payload şeması değişince eski snapshot'lar `parse_payload`'dan düşer ve değerlendirme "değerlendirilemedi"ye çevrilir — geçmişi korumak yerine bozardı.

Bunun sonucu bir üründür, bir kabul değil: **"yayınlanmış sınavda soruyu değiştirmek", soru satırını düzenlemek değil, yeni bir soru üretip onaylayıp yeni sürüme koymaktır.** Böylece FR-119'un onay kapısı yeni içeriğe de uygulanır (spec.md:278 "blueprint akışı onu zayıflatmamalıdır").

**Ek kapı (uygulama katmanı):** yayınlanmış ve superseded olmayan bir sürümün kaleminde yer alan soru **reddedilemez**. Silme zaten `exam_items.question_id` RESTRICT ile kapalı; ama red bir `status` değişikliğidir ve `questions_read` (`0004_assessment.sql:170-174`) reddedilen soruyu öğrenciden gizlediği için yürüyen bir kâğıt sessizce kısalırdı. Kontrol uygulama katmanındadır çünkü kullanıcıya anlaşılır Türkçe bir ret dönmesi gerekir (Anayasa V).

### 2.7 `exam_items`

Bir sürümdeki kâğıdın sırası ve puanı.

| Alan | Tip | Kısıt |
|---|---|---|
| `id` | `uuid` | PK, DEFAULT `gen_random_uuid()` |
| `course_id` | `uuid` | NOT NULL, FK → `courses(id)` ON DELETE CASCADE — denormalize |
| `exam_version_id` | `uuid` | NOT NULL, FK → `exam_versions(id)` ON DELETE CASCADE |
| `position` | `smallint` | NOT NULL, CHECK `>= 1`; UNIQUE `(exam_version_id, position)` |
| `question_id` | `uuid` | NOT NULL, FK → `questions(id)` ON DELETE RESTRICT; UNIQUE `(exam_version_id, question_id)` |
| `points` | `smallint` | NOT NULL, CHECK `BETWEEN 1 AND 100` |

**`blueprint_cell_id` BİLEREK YOKTUR.** Kalemin hangi hücreyi doldurduğu `exam_items → questions (learning_outcome_id, difficulty, type)` üzerinden her an türetilebilir (§2.5'teki sorgu). Pointer tutmak, hücre silindiğinde ya kanıtı kaybettiren (SET NULL) ya da blueprint'i kilitleyen (RESTRICT) bir ikilem üretirdi.

**`points` neden kopyalanıyor.** `blueprint_cells.points_per_question`'dan **yayın anında** kopyalanır. Gerekçe `0004_assessment.sql:85-86`'nın gerekçesiyle aynıdır ("oturum açılırken sorular burada sabitlenir"): blueprint sonradan düzenlense de yayınlanmış kâğıdın puanlaması değişmez.

**RLS politikaları:**

| Politika | Komut | Kural |
|---|---|---|
| `exam_items_read` | SELECT | `app.is_instructor(course_id)` **OR** `EXISTS (SELECT 1 FROM exam_sessions s WHERE s.exam_version_id = exam_items.exam_version_id AND s.user_id = app.current_user_id())` |
| `exam_items_instructor_insert` | INSERT | WITH CHECK `app.is_instructor(course_id) AND EXISTS (SELECT 1 FROM exam_versions v WHERE v.id = exam_version_id AND v.course_id = exam_items.course_id AND v.status = 'draft')` |
| `exam_items_instructor_delete` | DELETE | `app.is_instructor(course_id) AND EXISTS (SELECT 1 FROM exam_versions v WHERE v.id = exam_items.exam_version_id AND v.status = 'draft')` |

Öğrenci kâğıdı ancak **o sürümde oturumu varsa** görür. Pencereye bağlanmadı: zil çaldığında yürüyen öğrencinin kâğıdı ekrandan silinmemelidir.

INSERT/DELETE politikalarındaki `status='draft'` koşulu FR-115'in **yapısal** ayağıdır: UPDATE yetkisi hiç verilmediği (§2.11) ve yayınlanmış sürüme kalem eklenip çıkarılamadığı için, yayınlanmış bir kâğıdın soru listesi hiçbir kod yolundan değiştirilemez. INSERT politikasındaki ikinci koşul (`v.course_id = exam_items.course_id`) `answers_self_insert`'in (`0004_assessment.sql:205-217`) üçlü kontrolüdür: denormalize `course_id` taşıyan satıra sahte bir ders kimliği iliştirilmesini engeller.

### 2.8 `exam_sessions` — değişen (mevcut tablo)

```sql
ALTER TABLE exam_sessions
    ADD COLUMN exam_version_id   uuid REFERENCES exam_versions(id)   ON DELETE RESTRICT,
    ADD COLUMN exam_blueprint_id uuid REFERENCES exam_blueprints(id) ON DELETE RESTRICT,
    ADD COLUMN attempt_no smallint CHECK (attempt_no IS NULL OR attempt_no >= 1),
    ALTER COLUMN question_ids DROP NOT NULL,
    ADD CONSTRAINT exam_sessions_paper_source
        CHECK (num_nonnulls(exam_version_id, question_ids) = 1),
    ADD CONSTRAINT exam_sessions_blueprint_pair CHECK (
        (exam_version_id IS NULL) = (exam_blueprint_id IS NULL)
        AND (exam_version_id IS NULL) = (attempt_no IS NULL));

CREATE UNIQUE INDEX exam_sessions_attempt_key
    ON exam_sessions (exam_blueprint_id, user_id, attempt_no);
```

| Kolon | Varsayılan | Bugünkü davranışı neden değiştirmez |
|---|---|---|
| `exam_version_id` | NULL | Mevcut ve prova oturumlarının hepsi NULL; kâğıt kaynağı `question_ids` olarak kalır. |
| `exam_blueprint_id` | NULL | Aynı. |
| `attempt_no` | NULL | Aynı; tekil indekste NULL'lar çakışmaz (PostgreSQL varsayılanı), bu yüzden mevcut satırlar birbirini engellemez. |

**İki akış yan yana yaşar:**
- `exam_version_id IS NULL` → bugünkü self-servis prova; `question_ids` yetkili kaynak (`0004_assessment.sql:85-87` notu aynen geçerli).
- `exam_version_id IS NOT NULL` → blueprint sınavı; kâğıt `exam_items`'tan `ORDER BY position` okunur, `question_ids` NULL kalır.

`num_nonnulls(...) = 1` kısıtı "kâğıdın iki kaynağı olamaz"ı ifade edilemez kılar. İkisini birden yazmak aynı gerçeği iki yere koymak olurdu ve bir sürüm geçişinde ikisinin ayrışması sessiz olurdu (Anayasa XI).

`exam_sessions_attempt_key`, FR-111'in yeniden deneme politikasını yarışa dayanıklı kılar: uygulama `max_attempts`'i kontrol eder, eşzamanlı ikinci istek unique ihlaline düşer ve mevcut `IntegrityError → ConflictError` deseniyle 409'a çevrilir. Bu, `0004_assessment.sql:115-117`'nin ("tek deneme veritabanı seviyesinde de zorlanır") bir üst granülaritede tekrarıdır.

`ON DELETE RESTRICT` + `0007_question_delete_and_exam_grants.sql:49-50`'nin çektiği tablo düzeyi UPDATE birlikte şunu verir: **yürüyen bir oturumun sürümü ne silinebilir ne değiştirilebilir.** FR-115'in garantisi uygulama koduna değil yetkilere dayanır (Anayasa II'nin ikinci katmanı).

> **0008'in yazmaması gereken satır:** `GRANT UPDATE ON exam_sessions TO dou_app`. 0007 bu yetkiyi bilerek çekmiş ve yalnız `finished_at`'i geri vermiştir; geniş bir UPDATE geri verilirse öğrenci kendi `expires_at`'ini yazabilir hâle gelir ve 0007'nin süre koruması sessizce geri alınır. Yeni kolonlar **INSERT anında** yazılır, UPDATE gerekmez.

**Değişmeyen ama not düşülen:** `exam_sessions.score` bugün ölü bir kolondur — puan `answers`'tan türetiliyor ve 0007 UPDATE'i çekmiş durumda. 0008 bu kolona dokunmuyor; kaldırılması ayrı bir karardır (§8).

**`exam_sessions_self_insert` politikası yeniden kurulur (FR-116'nın ikinci katmanı):**

```sql
DROP POLICY exam_sessions_self_insert ON exam_sessions;
CREATE POLICY exam_sessions_self_insert ON exam_sessions
    FOR INSERT WITH CHECK (
        user_id = app.current_user_id()
        AND app.is_member(course_id)
        AND (exam_version_id IS NULL OR app.is_exam_open(exam_version_id, course_id)));
```

0004'ün iki koşulu (`user_id` + `is_member`) **aynen korunur**; yalnız üçüncü koşul eklenir. `exam_sessions_self_update` politikasına (`0004_assessment.sql:191-193`) **dokunulmaz** — o politika bir PR incelemesinde kapatılmış gerçek bir açığın yamasıdır ve yeniden yazılırsa koşullarından biri düşebilir.

### 2.9 `documents` — değişen (FR-118, kaynak sürümü)

**Tespit önce:** bugün sürüm izi **yoktur** ve otomatik anlaşılamaz. `chunks`'ta sürüm alanı yok (`0001_core_schema.sql:236-257`); `0006`'nın eklediği `embedding_space` sürüm izi **değildir**, vektör uzayı kimliğidir (`0006_embedding_provenance.sql:20-31`) — içerik değişmeden kütüphane sürümü değiştiğinde de değişir. `documents`'ta yalnız `file_hash` var ve `documents_course_hash_key` (`0001_core_schema.sql:227`) aynı içeriğin ikinci yüklemesini 409 ile reddediyor. **Değiştirilmiş** bir dosya farklı hash taşır, yeni bir satır olarak girer, eski satır ve chunk'ları yerinde kalır ve ikisi arasında hiçbir bağ kurulmaz. FR-118 veri eksikliğinden değil **ilişki eksikliğinden** çalışmıyor.

```sql
ALTER TABLE documents
    ADD COLUMN supersedes_document_id uuid REFERENCES documents(id) ON DELETE SET NULL,
    ADD COLUMN superseded_at timestamptz;

CREATE INDEX documents_superseded_idx ON documents (course_id) WHERE superseded_at IS NOT NULL;
```

| Kolon | Varsayılan | Bugünkü davranışı neden değiştirmez |
|---|---|---|
| `supersedes_document_id` | NULL | Hiçbir mevcut satır bir başkasının yerine geçmiş sayılmaz. |
| `superseded_at` | NULL | Bayatlık sorgusu (`WHERE d.superseded_at IS NOT NULL`) göç anında **boş küme** döner; hiçbir soru işaretlenmez. |

**Bağ açık eylemle kurulur, tahminle değil.** Yükleme ucu opsiyonel `replaces_document_id` alır. Dosya adına bakarak otomatik eşleme **reddedildi**: `file_name` üzerinde hiçbir tekillik yok, "hafta3.pdf" her dönem yeniden yüklenir (yanlış pozitif) ve yeniden adlandırılmış bir güncelleme yakalanmaz (yanlış negatif). Yanlış işaretlenen bir soru, öğretmenin işarete olan güvenini bitirir; güvenilmez işaret, hiç işaret olmamasından kötüdür.

**Bayatlık SAKLANMAZ, TÜRETİLİR** — `questions.source_stale` gibi bir bayrak eklenmiyor:

```sql
SELECT q.id FROM questions q
  JOIN chunks c    ON c.id = q.source_chunk_id
  JOIN documents d ON d.id = c.document_id
 WHERE q.course_id = :course AND d.superseded_at IS NOT NULL;
```

Saklanan bir bayrağın bir yazıcısı olur ve o yazıcı yükleme anında o belgenin tüm chunk'larının tüm sorularını gezmek zorundadır; bu fan-out arka planda sessizce düşebilir ve düştüğünde işaret hiç görünmez (Anayasa XI, "ayrışma sessizdir"). Türetilmiş sorgu indeksli iki FK üzerinde her zaman doğrudur.

**Sınırı açıkça yazılıyor:** bu işaret **yalnız soru havuzunda** görünür. Eskimiş sayılan belgenin chunk'ları retrieval'da kalmaya devam eder, yani asistan hâlâ eski materyalden atıf verebilir. O, ders politikasının kaynak setinin (FR-132, §3.1) alanıdır. "Kaynak sürümü yönetiliyor" izlenimi verip pratikte yönetmemek Anayasa III ihlali olurdu; bu yüzden sınır belgede duruyor.

### 2.10 Yeni SECURITY DEFINER yardımcıları (`app` şeması)

İkisi de `STABLE SECURITY DEFINER SET search_path = public, app`, yalnız **boolean** döndürür, satır sızdırmaz — `app.is_member` ile birebir aynı gerekçe (`0001_core_schema.sql:83-85`): politika içinden başka bir RLS'li tabloya SELECT atmak iki tablonun politikalarını birbirine bağlar ve ilerideki bir politika değişikliği bu bağı sessizce bozar.

**`app.is_exam_open(p_version_id uuid, p_course_id uuid) → boolean`**
> `exam_versions v` var mı: `v.id = p_version_id` **ve** `v.course_id = p_course_id` **ve** `v.status = 'published'` **ve** blueprint'inin penceresi açık (`opens_at IS NULL OR opens_at <= now()`, `closes_at IS NULL OR now() < closes_at`).

İki argümanlıdır çünkü iki çağrı yeri de ders eşleşmesini ister: `exam_versions_read` (`app.is_exam_open(id, course_id)`) ve `exam_sessions_self_insert` (`app.is_exam_open(exam_version_id, course_id)`). Tek imza, kuralın tek yerde yaşamasını sağlar (Anayasa XI). *Not: araştırma fazı bu fonksiyonu iki farklı imzayla (bir ve iki argümanlı) yazmıştı; burada tek imzada birleştirildi.*

**`app.blueprint_open_to_students(p_blueprint_id uuid) → boolean`**
> Blueprint'in penceresi açık **ve** `status='published'` bir sürümü var mı.

`exam_blueprints_read` için gerekir. İkinci bir fonksiyon açmanın sebebi, blueprint politikasının `exam_versions`'a doğrudan EXISTS atmasını önlemektir.

Zaman kaynağı her ikisinde de `now()`, yani **işlemin veritabanı saatidir**; istemci saatine güvenilmez (`0004_assessment.sql:80-82`'nin yazdığı kural).

### 2.11 GRANT / REVOKE — 0008'in en kolay unutulan bölümü

`0001_core_schema.sql:313` ve `:315-316` tüm mevcut **ve gelecek** tablolara `dou_app` / `dou_worker` için `SELECT, INSERT, UPDATE, DELETE` verir. Yani 0008'de aşağıdakiler açıkça yazılmazsa yeni tablolar **tam yazılabilir doğar** ve FR-115'in yapısal ayağı hiç kurulmamış olur.

```sql
REVOKE UPDATE ON exam_items, blueprint_cells FROM dou_app;

REVOKE UPDATE ON exam_versions FROM dou_app;
GRANT  UPDATE (status, published_at, published_by, superseded_at, blueprint_snapshot)
    ON exam_versions TO dou_app;
```

Bu, `0007_question_delete_and_exam_grants.sql:43`'ün cümlesinin uygulanmasıdır: *"RLS satır düzeyinde çalışır, SÜTUN kısıtı veremez — bu yüzden kolon bazlı GRANT."*

> **Araştırma fazına göre düzeltme:** araştırma yalnız `(status, superseded_at)` yetkisi öneriyordu. Bu **yayınlamayı imkânsız kılardı**: `exam_versions_publish_consistency` `status='published'` için `published_at` ve `published_by`'ın NOT NULL olmasını ister ve sürüm satırı `draft` doğduğu için bu iki alan UPDATE ile yazılmak zorundadır. `blueprint_snapshot` beşinci kolon olarak aynı gerekçeyle katılır (§8 madde 1: kısıt onu da `published` için NOT NULL istiyor ve satır `draft` doğuyor). Beş kolon veriliyor; `blueprint_id`, `version_no`, `course_id` yazılamaz kalır — kâğıdın kimliği değişmez.

`dou_worker` yetkileri **çekilmiyor**: worker bu tabloların hiçbirine dokunmaz, ama 0001'in verdiği varsayılanı burada daraltmak, ilgisiz bir rolü ilgisiz bir gerekçeyle değiştirmek olurdu.

**Kabul edilen artık risk (açıkça yazılıyor, `0003_chat.sql:213-217`'nin üslubuyla):** `blueprint_cells`'e UPDATE yetkisi yoktur ama INSERT/DELETE vardır; dolayısıyla dağılımın "küme olarak doğrulanmış" olması **uygulama katmanının** garantisidir, veritabanınınki değil. Veritabanı yalnız "aynı hücre iki kez tanımlanamaz" ve "sayılar aralıkta" der. Bu kabul edilebilir çünkü kullanıcıların doğrudan veritabanı kimliği yoktur; tek yol API'dir.

### 2.12 RLS özeti — 0008'in beş tablosu

Beş tablo da `ENABLE` **ve** `FORCE ROW LEVEL SECURITY` alır (`0001_core_schema.sql:329-334` deseni: sahip rol bile politikalara tabidir). Politikasız tablo Anayasa II ihlalidir; aşağıda hiçbiri politikasız değildir.

| Tablo | SELECT | INSERT | UPDATE | DELETE |
|---|---|---|---|---|
| `learning_outcomes` | üye | eğitmen | eğitmen | eğitmen |
| `exam_blueprints` | eğitmen ∨ (üye ∧ açık) | eğitmen | eğitmen | eğitmen |
| `blueprint_cells` | eğitmen | eğitmen | **yok** (yetki de çekili) | eğitmen |
| `exam_versions` | eğitmen ∨ (üye ∧ açık) ∨ kendi oturumu | eğitmen | eğitmen (yalnız 5 kolon) | eğitmen ∧ draft |
| `exam_items` | eğitmen ∨ kendi oturumu | eğitmen ∧ draft | **yok** (yetki çekili) | eğitmen ∧ draft |

Beş tabloda da `course_id` **denormalize** edilmiştir; izolasyon filtresi JOIN'e bağlı kalmaz (`0004_assessment.sql:3-11`).

### 2.13 Göç güvenliği — 0008

- **Tek `BEGIN; … COMMIT;`.** `DROP POLICY exam_sessions_self_insert` satırı hata verirse (isim değişmişse) göçün tamamı geri alınır; yarı uygulanmış şema kalmaz.
- **Veri taşıması yok.** Beş tablo boş doğar. Mevcut `exam_sessions` satırlarının hepsi `question_ids` dolu / `exam_version_id` NULL olduğu için `exam_sessions_paper_source` ve `exam_sessions_blueprint_pair` kısıtları **ilk günden geçer** (`ALTER TABLE … ADD CONSTRAINT` mevcut satırları doğrular; bu doğrulama boş kümede değil, gerçek satırlarda koşar ve geçer).
- **`questions` ve `documents`'a eklenen dört kolonun hepsi nullable ve varsayılansızdır**; hiçbir mevcut satır yeniden yazılmaz, tablo yeniden yazımı (rewrite) tetiklenmez (PostgreSQL 11+ davranışı: varsayılansız kolon eklemek metadata işlemidir).
- **Kırılabilecek yer:** `exam_sessions.question_ids`'in NOT NULL'ı kalkıyor. Bunu okuyan kod (`_paper_question_ids` benzeri her yol) artık NULL'a hazır olmalıdır; bugünkü dört çağrı yeri de dizinin dolu olduğunu varsayıyor. Bu bir kod işidir ve 0008 ile aynı commit'te yapılmalıdır, yoksa ilk blueprint oturumu `TypeError` ile düşer.
- **Sessiz kalabilecek hata:** §2.11'deki REVOKE satırları unutulursa **hiçbir test kırmızı yanmaz**, çünkü uygulama kodu zaten doğru davranıyordur. Bu yüzden "kalem listesi güncellenemez" ve "hücre güncellenemez" için **yetkiyi doğrudan sınayan** ayrı testler yazılmalıdır — Anayasa II'nin "politika bilerek bozularak kanıtlanır" kuralının yetki karşılığı (`apps/api/tests/test_isolation_layers.py`'nin yöntemi).

### 2.14 0008'de BİLEREK YAPILMAYANLAR

Göç dosyasının başlığında gerekçeleriyle yazılacak (0007'nin (c) maddesinin âdeti, `0007:53-68`), yoksa bir sonraki inceleme bunları "eksik" diye raporlar:

1. **`rubrics` tablosu** — rubrik `questions.payload.rubric`'te yaşıyor ve değerlendirme onu zaten okuyor. Paylaşılan bir rubrik ayrıca sürümleme sorununu ikinci bir varlığa taşırdı: soru dondurulmuşken rubrik değişirse yürüyen sınavın puanlaması değişirdi.
2. **`question_learning_outcomes` ara tablosu** — kardinalite 1:N (§2.0).
3. **`exam_publications` tablosu** — yayın, sürümün durumudur (§2.0).
4. **`questions.source_stale` bayrağı** — türetilebilir (§2.9).
5. **`exam_items.blueprint_cell_id`** — türetilebilir (§2.7).
6. **Yeni bir `exams` tablosu ve `exam_sessions → attempts` yeniden adlandırması** — 35 sınav testi, dört RLS politikası ve 0007'nin kolon GRANT'i tek seferde kırılırdı; kazanç yalnız isimlendirme.
7. **`exam_version_cells` tablosu** — yayınlanan dağılımı dondurmanın normalize edilmiş biçimi. Altıncı tablo açmak yerine `exam_versions.blueprint_snapshot` jsonb'si seçildi; gerekçe ve reddedilen alternatifler §8 madde 1'de.

### 2.15 FR-117 rubrik kırılımı — şema değil, jsonb sözleşmesi

DDL yok; buraya yazılmasının sebebi verinin **şeklinin** değişmesidir:

- Ölçüt kırılımı mevcut `answers.feedback` jsonb'sine yeni bir anahtarla (`rubrik_kirilimi`) yazılır. O sütun tam bu iş için var (`0004_assessment.sql:110-112`) ve içeriği tek bir yerden üretiliyor.
- **Toplam puan modelden okunmaz**, ağırlıklarla bizim tarafımızdan hesaplanır: `round(Σ(weight_i × score_i) / 100)`. Model hem kırılım hem ayrı bir toplam verseydi ikisi çelişebilirdi ve öğrenciye gösterilen tablonun toplamı tutmazdı (Anayasa III).
- `OpenPayload.rubric` bugün ağırlık toplamını **doğrulamıyor** (`apps/api/app/schemas/assessment.py:95-98`, `:105`), oysa üç ayrı yer "ağırlıklar 100 üzerinden" diyor. Toplam kısıtı **yalnız yeni üretimde** zorlanmalıdır; okuma yolunda toplam 100 değilse ağırlıklar normalize edilmelidir. Aksi hâlde bugün havuzda duran onaylı sorular şema doğrulamasından düşer ve **sessizce değerlendirilemez** hâle gelir. Bu, 0008 ile aynı gün havuzun taranıp raporlanmasını gerektirir.

---

## 3. `0009_course_ai_policy.sql` — Ders AI politikası

### 3.1 `course_ai_policies`

Bir dersin asistan davranış sınırları. **Derse birebir bağlıdır**; satırın hiç olmaması FR-136'nın birinci savunması, kolonun NULL olması ikinci savunmasıdır.

| Alan | Tip | Kısıt | NULL ne demek |
|---|---|---|---|
| `course_id` | `uuid` | **PK**, FK → `courses(id)` ON DELETE CASCADE | — |
| `allowed_modes` | `chat_mode[]` | nullable; CHECK `allowed_modes IS NULL OR NOT ('exam' = ANY(allowed_modes))` | NULL = bugünkü davranış (`qa` + `socratic`). `'{}'` = **bilerek** tüm modlar kapalı (spec.md:237) |
| `max_hints` | `smallint` | nullable; CHECK `max_hints IS NULL OR max_hints >= 0` | NULL = global `socratic_max_stage` (`config.py:221`) |
| `source_document_ids` | `uuid[]` | nullable | NULL = dersin tüm belgeleri. `'{}'` = **bilerek** boş kaynak seti (spec.md:238) |
| `evidence_threshold` | `numeric(4,3)` | nullable; CHECK `BETWEEN 0 AND 1` | NULL = global `evidence_threshold` (`config.py:187`) |
| `daily_token_budget` | `integer` | nullable; CHECK `> 0` | NULL = sınırsız (bugünkü davranış) |
| `updated_by` | `uuid` | nullable, FK → `profiles(id)` ON DELETE SET NULL | — |
| `created_at` | `timestamptz` | NOT NULL, DEFAULT `now()` | — |
| `updated_at` | `timestamptz` | NOT NULL, DEFAULT `now()` | — |

**`max_hints`'e üst sınır CHECK'i yazılmadı** (araştırma fazı `BETWEEN 0 AND 4` öneriyordu). Üst sınır Sokratik merdivenin **uzunluğudur** ve o bilgi `modules/assessment/socratic.py`'nin kademe sırasında yaşar; SQL'e `4` yazmak aynı ürün kararını ikinci bir dilde tutmak olurdu (Anayasa XI). Çözümleyici `min(ders, global)` uygular; 99 yazan bir eğitmen global sınıra kırpılır, yani fail-closed davranış korunur.

**RLS politikaları:**

| Politika | Komut | Kural |
|---|---|---|
| `course_ai_policies_member_read` | SELECT | `app.is_member(course_id)` |
| `course_ai_policies_instructor_insert` | INSERT | WITH CHECK `app.is_instructor(course_id)` |
| `course_ai_policies_instructor_update` | UPDATE | USING + WITH CHECK `app.is_instructor(course_id)` |
| `course_ai_policies_instructor_delete` | DELETE | `app.is_instructor(course_id)` |

SELECT'in **üyeye** açık olması bilinçlidir: arayüz kilitli sekmeyi/kapalı modu ancak politikayı okuyabilirse çizebilir (FR-135 arayüzü sunucunun **aynası** yapar, karar vericisi değil). Sızan bilgi "bu derste Sokratik kapalı"dır ve öğrenci bunu ilk denemede zaten öğrenir.

DELETE = "politikayı sıfırla": satır silinince ders bugünkü davranışa döner (FR-136).

**Neden ayrı tablo, neden `courses.ai_policy jsonb` değil.** Üç somut engel:

1. **Yetki.** `courses_instructor_update` (`0001_core_schema.sql:353-354`) satır düzeyindedir, kolon kısıtı veremez; politika `courses`'a konursa eğitmen aynı UPDATE'le `code`, `title`, `created_by` alanlarına da yazabilir hâle gelir. Depo bu sorunu bir kez yaşadı ve çözümü kolon bazlı GRANT'ti (`0007:43`, `:49-50`). Ayrı tabloda böyle bir cerrahiye gerek yoktur: tablonun tamamı zaten politikanın kendisidir.
2. **Kısmi güncelleme.** JSONB blob'unda tek alanı değiştirmek oku-değiştir-yaz demektir; iki eğitmen farklı alanları aynı anda değiştirdiğinde biri sessizce kaybolur.
3. **Doğrulama.** JSONB, eşiğin [0,1] içinde olduğunu veya `allowed_modes` içine `exam` sızmadığını veritabanı düzeyinde iddia edemez. Bu depoda kural yazılırken CHECK kullanılır (`0004_assessment.sql:88-90`).

Ayrıca JSONB'nin bedeli bu depoda ölçülü: `chat_sessions.state` JSONB olduğu için okuma yolu her seferinde bozuk veriye karşı savunma yazmak zorunda. Dört ayrı çağrı yerinin (mod kapısı, ipucu tavanı, retrieval filtresi, bütçe) hepsinin bu savunmayı hatırlaması gereken bir tasarım, Anayasa XI'in tarif ettiği sessiz ayrışmanın kendisidir.

**Kaynak seti neden `uuid[]`, neden join tablosu değil.** `uuid[]` bu depoda FK'sız kullanılan yerleşik bir desendir (`exam_sessions.question_ids`, `0004_assessment.sql:86-87`). FK yokluğunun riski burada yapısal olarak sönüyor: silinen belgenin chunk'ları CASCADE ile gidiyor (`0001_core_schema.sql:240`), dolayısıyla dizide kalan ölü kimlik hiçbir satırla eşleşmez; okuma ucu diziyi canlı `documents` satırlarına karşı süzerek döner. Join tablosu ise FR-137'nin tek satırlık anlık görüntüsünü ikiye bölerdi (§3.2) ve "hiç ayarlanmamış" ile "bilerek boşaltılmış" ayrımını tutamazdı — satır yokluğu iki anlama gelirdi.

### 3.2 `course_ai_policy_audit` (FR-137)

Politika değişikliklerinin kim/ne zaman/ne izi.

| Alan | Tip | Kısıt |
|---|---|---|
| `id` | `uuid` | PK, DEFAULT `gen_random_uuid()` |
| `course_id` | `uuid` | NOT NULL, FK → `courses(id)` ON DELETE CASCADE |
| `changed_by` | `uuid` | nullable, FK → `profiles(id)` ON DELETE SET NULL |
| `changed_at` | `timestamptz` | NOT NULL, DEFAULT `now()` |
| `before` | `jsonb` | nullable (ilk yazımda NULL) |
| `after` | `jsonb` | nullable (silmede NULL) |

**İndeks:** `course_ai_policy_audit_course_idx` — `(course_id, changed_at DESC)` (`request_logs_course_idx`, `0003_chat.sql:149` ile aynı desen).

**RLS politikaları:**

| Politika | Komut | Kural |
|---|---|---|
| `course_ai_policy_audit_instructor_read` | SELECT | `app.is_instructor(course_id)` |
| `course_ai_policy_audit_insert` | INSERT | WITH CHECK `app.is_instructor(course_id)` |

UPDATE/DELETE politikası **yoktur** ve yetkileri de çekilir:
```sql
REVOKE UPDATE, DELETE ON course_ai_policy_audit FROM dou_app;
```
Gerekçe `0005_analytics.sql:28-30`'un cümlesidir: *"sonradan düzeltilebilirse hiçbir şeyin kanıtı olamaz (Anayasa III)."*

**Satırı kim yazar: trigger.** `course_ai_policies` üzerinde `AFTER INSERT OR UPDATE OR DELETE FOR EACH ROW` bir trigger, `to_jsonb(OLD)` / `to_jsonb(NEW)` ve `app.current_user_id()` ile tek satır yazar.

Bu, **`public` şemasındaki ilk iş trigger'ıdır** ve deponun bugünkü alışkanlığından sapar (tek trigger `0002_supabase_auth_bridge.sql:191-207`, `auth.users` köprüsü). Sapmanın gerekçesi: denetim izi bir **iş kuralı değil**, kaçırılamaz bir **kayıttır**. Uygulama katmanına bırakılırsa ileride eklenen bir "hızlı ayar" ucu izi yazmayı unutabilir ve FR-137 sessizce ihlal edilir — Anayasa XI'in "her dosyada yeniden hatırlanmak zorunda kalan kural er geç ihlal edilir" cümlesi tam olarak bu durumu tarif eder.

Trigger fonksiyonu **SECURITY DEFINER değildir**: çağıran rolle koşar ve yukarıdaki INSERT politikasından geçer. Definer yapmak, ölçülmüş bir ihtiyaç yokken RLS'i atlayan yeni bir yazma yüzeyi açardı (`0007:65-68`'in reddettiği şey).

**Kabul edilen artık risk:** INSERT politikası eğitmene açık olduğu için bir eğitmen kendi dersine sahte bir denetim satırı yazabilir (API üzerinden bir uç olmasa da politika buna izin verir). `answer_cache`'in kabul edilen riskiyle (`0003_chat.sql:213-217`) aynı sınıftadır ve aynı sebeple kabul edilebilir: kullanıcıların doğrudan veritabanı kimliği yoktur, tek yol API'dir.

### 3.3 `daily_token_budget` — neden yeni bir sayaç tablosu yok

Tüketim zaten ölçülüyor: `request_logs.token_count` (`0003_chat.sql:144`) ve `request_logs_course_idx (course_id, created_at DESC)` (`:149`). İkinci bir `course_token_usage` tablosu, aynı sayıyı iki yerde tutmak ve ayrışmasını beklemek olurdu.

Ama bir engel var ve açıkça yazılmalı: **`request_logs`'un `dou_app` için SELECT politikası yalnız eğitmene açıktır** (`0005_analytics.sql:34-35`). Öğrencinin isteği bağlamında yapılan bir `SELECT sum(token_count)` **sıfır satır görür** ve bütçe kontrolü **fail-open** olur — Anayasa IV'ün tam tersi. Bu yüzden 0009 bir yardımcı daha tanımlar:

**`app.course_tokens_today(p_course_id uuid) → bigint`** — `STABLE SECURITY DEFINER SET search_path = public, app`; `SELECT coalesce(sum(token_count), 0) FROM request_logs WHERE course_id = p_course_id AND created_at >= date_trunc('day', now())`. Yalnız bir **sayı** döndürür, satır sızdırmaz — `app.is_member`'ın gerekçesiyle aynı (`0001_core_schema.sql:83-85`).

İki sınır dürüstçe yazılıyor (Anayasa III):
1. `token_count` **nullable**'dır; önbellek isabetleri ve LLM'e hiç gitmeyen yollar bütçeye sayılmaz.
2. `request_logs`'a bugün **yalnız sohbet ucu** yazıyor (`apps/api/app/api/chat.py:662` çevresi; başka yazıcı yok). Yani ipucu üretimi, soru üretimi ve açık uçlu değerlendirmenin token'ları bütçeye **girmez**. FR-134'ün "dersin günlük LLM bütçesi" ifadesi bu hâliyle "dersin günlük **sohbet** bütçesi"dir. Ya diğer LLM yolları da `request_logs`'a yazmalı (tercih edilen, çünkü tablo bunun için var) ya da arayüzdeki etiket bunu söylemeli. §8'de açık soru.

Sorgu maliyeti **ölçülmedi** ve rapora "ölçülmedi" diye yazılacak.

### 3.4 Göç güvenliği — 0009

- **Veri taşıması yok.** İki tablo boş doğar; hiçbir dersin politikası yoktur, dolayısıyla FR-136 göç anında tanımı gereği sağlanır: her ders bugünkü davranışla çalışır.
- **Mevcut tabloya kolon eklenmez.** `courses` dokunulmaz kalır, `courses_instructor_update` politikası aynen durur.
- **Bağımlılık:** `chat_mode` enum'u 0003'ten gelir; `documents` 0001'den. İkisi de yerinde.
- **Kırılabilecek yer:** trigger, `course_ai_policies` üzerinde koşar ve `course_ai_policy_audit`'e INSERT eder. Audit tablosunun INSERT politikası eksik yazılırsa **politika yazma işleminin tamamı** "new row violates row-level security policy" ile düşer — yani sessiz değil, gürültülü kırılır. Bu doğru davranıştır (fail-closed) ama 0009 uygulanır uygulanmaz bir politika yazma denemesiyle sınanmalıdır.

---

## 4. `0010_ingestion_retry.sql` — Belge işleme dayanıklılığı (FR-213, FR-214)

**Bugünkü durum.** `ingestion_jobs` zaten `attempt_count` ve `last_error` taşıyor (`0001_core_schema.sql:276-277`) ve `MAX_ATTEMPTS = 3` kodda sabit (`apps/api/app/modules/ingestion/pipeline.py:29`). Eksik olan iki şey var: (i) başarısız iş **anında** `pending`'e geri konuyor (`pipeline.py:162-186`), yani "artan aralıklarla yeniden dene" hiç uygulanmıyor — üç deneme saniyeler içinde tükeniyor ve geçici bir arıza kalıcı hataya dönüşüyor; (ii) `ingestion_jobs` üzerinde eğitmen için **UPDATE politikası yok** (`0001_core_schema.sql:385-400`de yalnız SELECT ve INSERT var), yani FR-214'ün "yeniden çalıştırabilmeli"si veri katmanında imkânsız.

```sql
ALTER TABLE ingestion_jobs
    ADD COLUMN next_attempt_at timestamptz NOT NULL DEFAULT now(),
    ADD COLUMN requeued_by uuid REFERENCES profiles(id) ON DELETE SET NULL,
    ADD COLUMN requeued_at timestamptz;

DROP INDEX ingestion_jobs_pending_idx;
CREATE INDEX ingestion_jobs_pending_idx ON ingestion_jobs (next_attempt_at, created_at)
    WHERE status = 'pending';

CREATE POLICY jobs_instructor_update ON ingestion_jobs
    FOR UPDATE USING (
        EXISTS (SELECT 1 FROM documents d
                 WHERE d.id = ingestion_jobs.document_id AND app.is_instructor(d.course_id)))
    WITH CHECK (
        EXISTS (SELECT 1 FROM documents d
                 WHERE d.id = ingestion_jobs.document_id AND app.is_instructor(d.course_id)));

REVOKE UPDATE ON ingestion_jobs FROM dou_app;
GRANT  UPDATE (status, next_attempt_at, attempt_count, requeued_by, requeued_at)
       ON ingestion_jobs TO dou_app;
```

| Kolon | Varsayılan | Bugünkü davranışı neden değiştirmez |
|---|---|---|
| `next_attempt_at` | **`now()`** (NOT NULL) | Göç anında bekleyen her satır `now()` alır, yani `next_attempt_at <= now()` koşulunu **hemen** sağlar. Kuyruktaki hiçbir iş beklemeye alınmaz; davranış göç öncesiyle aynıdır. Yeni satırlar için de DEFAULT `now()` "hemen çalıştırılabilir" demektir; geri çekilme yalnız **başarısızlıktan sonra** `now() + gecikme` yazılarak devreye girer. |
| `requeued_by` / `requeued_at` | NULL | Hiçbir mevcut iş elle yeniden çalıştırılmamıştır; NULL bunu dürüstçe söyler. |

**`next_attempt_at` NOT NULL, `0006`'nın NULL tercihiyle çelişmiyor.** 0006'da NULL "kökeni bilinmiyor" anlamına geliyordu ve göç bunu gerçekten bilemiyordu. Burada göç değeri **biliyor**: bekleyen bir iş şu anda çalıştırılabilirdir, çünkü bugün de öyle davranıyor. Bilinen bir değeri nullable bırakmak, her okuma yerine bir `COALESCE` borcu yazmak olurdu.

**İndeks neden yeniden kuruluyor.** Kuyruk sorgusu `WHERE status='pending' AND next_attempt_at <= now() ORDER BY next_attempt_at, created_at` hâline gelir; eski kısmi indeks (`(created_at) WHERE status='pending'`, `0001_core_schema.sql:284-285`) yeni yüklemi karşılamaz. Kısmi indeks kalıbı korunuyor. `FOR UPDATE SKIP LOCKED` mekanizması (`pipeline.py:139-158`) değişmiyor.

**Geri çekilme süresi nerede yaşıyor.** Veritabanında değil, `pipeline.py`'de — `MAX_ATTEMPTS`'in yanında, tek sözlükte (Anayasa XI). Şema yalnız "ne zaman"ı taşır, "ne kadar"ı değil; aksi hâlde aynı politika hem SQL'de hem Python'da yaşardı.

**Elle yeniden çalıştırma (FR-214).** `status='pending'`, `next_attempt_at=now()`, `attempt_count=0`, `requeued_by`/`requeued_at` damgalanır. `attempt_count`'un sıfırlanması bilinçlidir: sıfırlanmazsa üç denemesi tükenmiş bir iş, ilk hatada anında tekrar `failed` olur ve "yeniden çalıştır" düğmesi hiçbir şey yapmayan bir düğmeye dönüşür — Anayasa XI'in "etkin görünüp iş yapmayan buton kusurdur" maddesi. Kaybedilen geçmiş (kaç kez denendiği) `requeued_at` damgasıyla kısmen telafi edilir; tam geçmiş için ayrı bir deneme tablosu gerekirdi ve ölçülmüş bir ihtiyaç yok.

**Kolon bazlı GRANT gerekçesi** yine `0007:43`: eğitmenin yeniden çalıştırması `started_at`, `completed_at`, `document_id` veya `last_error` alanlarına yazma yetkisi vermemelidir — hata metni işin kendi kaydıdır, kullanıcı tarafından düzeltilebilir olmamalıdır. `dou_worker` yetkileri **çekilmez**: worker `started_at`/`completed_at`/`last_error` yazmak zorundadır ve BYPASSRLS'lidir.

**FR-214'ün görünürlük ayağı zaten var:** ısrarla başarısız olan iş `documents.status='failed'` ve `documents.error_message` yazıyor (`pipeline.py:179-186`), bu da belge listesinde eğitmene görünüyor. 0010'un eklediği tek görünürlük "ne zaman tekrar denenecek"tir.

**Göç güvenliği.** Tek işlem. `DROP INDEX` + `CREATE INDEX` küçük bir kuyruk tablosunda anlıktır; **not:** üretimde veri birikmişse `CREATE INDEX CONCURRENTLY` bir işlem içinde koşamaz — o durumda indeks adımı ayrı ve elle uygulanmalıdır. `ALTER TABLE … ADD COLUMN … NOT NULL DEFAULT now()` PostgreSQL 11+'ta tablo yeniden yazımı gerektirmez (varsayılan katalogda tutulur).

---

## 5. `0011_pagination_indexes.sql` — Belirlenimci sıralama (FR-160…FR-163)

**Yeni tablo yok, yeni kolon yok.** Sayfalama bir **sıralama** sorunudur ve bu göç yalnız sıralamayı indeksle destekler. İmleç (`cursor`) kodlaması API sözleşmesidir, şema değil.

**Neden OFFSET değil, anahtar kümesi (keyset).** FR-162 "eşzamanlı ekleme sırasında kayıt atlamamalı veya tekrarlamamalı" der; OFFSET tam olarak bunu yapamaz — araya bir satır girdiğinde ikinci sayfa bir kaydı atlar. Keyset imleci `(sıralama_anahtarı, id)` çiftidir ve **tam sıralama** gerektirir: `id` tiebreaker'ı olmadan aynı `created_at`'e sahip iki satırın sırası birincil anahtara, yani rastgele bir UUID'ye kalır. Bu depo bu hatayı bir kez yaşadı ve çözümünü yazdı: `chat_messages.seq` sütunu tam olarak "aynı `created_at`'te sıralama rastgele kalıyordu, testle yakalandı" diye eklenmiştir (`0003_chat.sql:83-90`). FR-163'ün "belirlenimci sıralama" maddesi o dersin genelleştirilmesidir.

| # | Liste (bugünkü sorgu) | Bugünkü indeks | 0011'de |
|---|---|---|---|
| 5.1 | Dersler — `courses.py:31-46`, `ORDER BY courses.created_at DESC` | **yok** (`courses`'ta yalnız `courses_code_key`) | `CREATE INDEX courses_created_page_idx ON courses (created_at DESC, id DESC)` |
| 5.2 | Materyaller — `documents.py:100-105`, `ORDER BY created_at DESC` | `documents_course_idx (course_id, created_at DESC)` (`0001:228`) | **Değiştirilir:** `documents_course_page_idx (course_id, created_at DESC, id DESC)`; eski indeks DROP edilir (yeni indeks onun tam ön eki) |
| 5.3 | Sorular — `questions.py:121-147`, `ORDER BY created_at DESC`, isteğe bağlı `status` ve `topic_id` süzgeci | `questions_course_idx (course_id, status)` (`0004:67`), `questions_topic_idx` (`:68`) | **Eklenir:** `questions_course_page_idx (course_id, created_at DESC, id DESC)`. `questions_course_idx` **korunur** (öğrenci yolu her zaman `status='approved'` süzer, `questions.py:138-139`) |
| 5.4 | Sohbet oturumları — `chat.py:702-710`, `ORDER BY updated_at DESC` | `chat_sessions_user_idx (user_id, updated_at DESC)` (`0003:56`) | **Değiştirilir:** `chat_sessions_user_course_page_idx (user_id, course_id, updated_at DESC, id DESC)`; eski indeks DROP edilir |
| 5.5 | Sohbet mesajları — `chat.py:713-739`, `ORDER BY created_at, seq` | `chat_messages_session_idx (session_id, created_at, seq)` (`0003:97`) | **Değiştirilir:** `chat_messages_session_page_idx (session_id, created_at, seq, id)`; eski indeks DROP edilir |

**5.4'ün `user_id`'yi öne alması bir RLS gözlemidir.** Sorgu yalnız `course_id` ile süzüyor; kullanıcı süzgecini RLS ekliyor (`chat_sessions_self_read`, `0003_chat.sql:171-174`) ve `user_id = app.current_user_id()` **STABLE** bir fonksiyon karşılaştırması olduğu için indeks niteleyicisi olarak kullanılabilir. `app.is_member(course_id)` ise kullanılamaz (fonksiyon çağrısı, filtre olarak koşar). Yani gerçek erişim deseni `(user_id, course_id, updated_at)`'tır.

**5.5'te yön karıştırılmıyor.** Sohbet geçmişi "son mesajlar gelir, geriye doğru yüklenebilir" (spec.md:141) biçiminde okunur; B-tree indeksi her iki yönde de taranabildiği için sütunların hepsi **aynı yönde** (ASC) bırakılmıştır. Karışık yön (`created_at DESC, seq ASC`) indeksi tek yönlü hâle getirirdi.

**`questions` üzerindeki indeks sayısı — dürüst not.** 0008 `questions_cell_idx`'i, 0011 `questions_course_page_idx`'i ekliyor; mevcut ikisiyle birlikte dört indeks olur. Soru yazımı seyrek ve toplu olduğu için (üretim toplu, `question_generation_batch = 5`, `config.py:159`) bu kabul edilebilir görünüyor ama **ölçülmedi** ve rapora "ölçülmedi" yazılacak. Ölçüm gösterirse elenecek ilk aday `questions_topic_idx`'tir (`0004:68`), çünkü konu süzgeci her zaman `course_id` ile birlikte gelir.

**Sunucu üst sınırı (FR-161)** ve imleç kodlaması şema değil kod işidir; buraya not düşülmesinin tek sebebi, imlecin **sıralama anahtarının tamamını** (anahtar + `id`) taşımak zorunda olmasıdır — aksi hâlde yukarıdaki indekslerin `id` sütunları boşuna eklenmiş olur.

**Göç güvenliği — 0011.** Yalnız indeks yaratır ve siler; veri değişmez, kısıt değişmez, politika değişmez. En kötü hâlde geri alınabilir. **Not:** göç işlem içinde koştuğu için `CREATE INDEX` yazma kilidi alır; veri birikmiş bir üretim veritabanında indeks adımları `CONCURRENTLY` ile ve işlem dışında uygulanmalıdır. Eski indeksler **yeni indeksler yaratıldıktan sonra** silinir, böylece hiçbir an indekssiz kalınmaz.

---

## 6. İlişki özeti (002 sonrası, yalnız yeni ve değişen kenarlar)

```
courses           1───n learning_outcomes    (course_id, ON DELETE CASCADE)
topics            1───n learning_outcomes    (topic_id,  ON DELETE SET NULL)
learning_outcomes 1───n questions            (learning_outcome_id, ON DELETE SET NULL)   [YENİ kolon]
learning_outcomes 1───n blueprint_cells      (learning_outcome_id, ON DELETE RESTRICT)

courses           1───n exam_blueprints      (course_id, ON DELETE CASCADE)
exam_blueprints   1───n blueprint_cells      (blueprint_id, ON DELETE CASCADE)
exam_blueprints   1───n exam_versions        (blueprint_id, ON DELETE CASCADE)
exam_versions     1───n exam_items           (exam_version_id, ON DELETE CASCADE)
questions         1───n exam_items           (question_id, ON DELETE RESTRICT)

exam_versions     1───n exam_sessions        (exam_version_id,   ON DELETE RESTRICT)     [YENİ kolon]
exam_blueprints   1───n exam_sessions        (exam_blueprint_id, ON DELETE RESTRICT)     [YENİ kolon]

documents         1───n documents            (supersedes_document_id, ON DELETE SET NULL) [YENİ, kendine]

courses           1───1 course_ai_policies   (course_id = PK, ON DELETE CASCADE)
courses           1───n course_ai_policy_audit (course_id, ON DELETE CASCADE)
profiles          1───n course_ai_policy_audit (changed_by, ON DELETE SET NULL)
profiles          1───n ingestion_jobs       (requeued_by, ON DELETE SET NULL)            [YENİ kolon]
```

**Hücre ↔ kalem ilişkisi kasıtlı olarak YOKTUR** (§2.7): `exam_items` hangi hücreyi doldurduğunu `questions`'ın üç alanı üzerinden **türetir**.

**Silme yönleri özeti:** ders silinince blueprint ailesinin tamamı gider (CASCADE). Ama yayınlanmış bir sürüme bağlı **oturum** varsa sürüm silinemez (RESTRICT) ve bir kalemde kullanılan **soru** silinemez (RESTRICT) — `questions.source_chunk_id`'nin (`0004_assessment.sql:55`) kurduğu "dayanağı silinmiş kanıt, kanıt değildir" zincirinin devamı.

---

## 7. Migration yol haritası

| Numara | Dosya | Durum | Ön koşul |
|---|---|---|---|
| 0001–0007 | — | **uygulanmış** | — |
| 0008 | `0008_exam_blueprint.sql` | **uygulanmış** | yok |
| 0009 | `0009_course_ai_policy.sql` | **uygulanmış** | yok (0008'den bağımsız, numara sırası korunur) |
| 0010 | `0010_ingestion_retry.sql` | **uygulanmış** | yok |
| 0011 | `0011_pagination_indexes.sql` | **uygulanmış** | 0008 (soru indeksleri birlikte değerlendirilir) |
| 0012 | `0012_privacy_rights.sql` | **uygulanmış** | 0003 sohbet sahipliği |

Her göç, deponun âdetine uyan **uzun bir gerekçe başlığıyla** açılır: ne yaptığını değil **niçin o biçimde** yaptığını anlatır ve **bilerek yapılmayanları** gerekçesiyle yazar (`0004:1-11`, `0006:1-58`, `0007:1-9` ve `:53-68`).

Model tarafı: yeni tablolar `apps/api/app/models/` altına eklenir (`assessment.py` → blueprint ailesi; yeni `policy.py` → politika + denetim); enum'lar `pg_enum(..., create_type=False)` ile bağlanır (`apps/api/app/models/base.py:20-38`) ve **migration'lar düz SQL kalır, ORM'den üretilmez** (`models/assessment.py:3-5`).

Belge ayağı: bu dosya ve `ARCHITECTURE.md` §3 aynı commit'te güncellenir; US7/FR-180 belgelerin kodla çelişmemesini istiyor ve `specs/001-course-assistant-mvp/data-model.md`'nin §5'i (PLANLANAN varlıklar) 0003/0004 uygulandığı hâlde hâlâ "henüz migration yok" diyor — o bayatlık da 002 kapsamında düzeltilmelidir.

---

## 8. Kararlar ve açık sorular

Bu bölüm başlangıçta yalnız açık soru listesiydi. **T501 (2026-08-10)** Blok 5'in
kapısını açmak için dördünü kapattı; kapatılanlar `KARAR` etiketiyle ve gerekçesiyle
duruyor, kalanlar açık. Bir kararın gerekçesi sonradan çürütülebilir olsun diye
reddedilen seçenekler de yazılı bırakıldı.

Kapatılanlar 1, 2, 7 ve 9; açık kalanlar 3, 4, 5, 6 ve 8. Açık kalanların hiçbiri
`0008`'i bağlamıyor — 3 ve 4 `0009`'un (US4), 6 `0011`'in (US6), 8 US10'un alanı;
5 ise 0008'in dokunmadığı ölü bir kolon.

1. **KARAR (T501) — Yayınlanmış dağılım, sürümün üstünde jsonb kanıt olarak donar.**
   `exam_versions`'a `blueprint_snapshot jsonb` eklenir: yayın anında kapının
   doğruladığı hücre kümesi (çıktı, zorluk, tip, adet, puan) satır satır oraya
   kopyalanır. `draft` iken NULL, `published`/`superseded` iken NOT NULL — kısıt
   `exam_versions_publish_consistency`'nin üç dalına eklenir (§2.6). Kolon,
   §2.11'deki kolon bazlı UPDATE yetkisine katılır; yayın işlemi zaten o UPDATE'i
   atıyor, ikinci bir yazma yolu açılmaz.

   **Gerekçe.** Belgenin saydığı üç seçeneğin üçü de kabul edilmedi:
   (a) `exam_version_cells` tablosu doğru modeldir ama altıncı tablodur ve T502'nin
   saydığı beş tabloyu bozar; kazancı, yalnız okunup hiç toplulaştırılmayan bir
   kanıt için normalizasyon. (b) hücreleri kilitlemek doğal akışı kırar: v1
   yayındayken dağılımı düzeltmek isteyen öğretmenin önce v1'i yayından kaldırması
   gerekirdi, yani öğrenciler sınavı kaybederdi. (c) kabul etmek SC-003'ün
   "birebir uydu" iddiasını doğrulanamaz bırakır.

   Seçilen yol deponun **kendi kurduğu deseni** izliyor: `exam_items.points`
   `blueprint_cells.points_per_question`'dan tam olarak bu sebeple yayın anında
   kopyalanıyor (§2.7, "blueprint sonradan düzenlense de yayınlanmış kâğıdın
   puanlaması değişmez"). Dağılım da kâğıdın bir özelliğidir ve aynı anda donar.
   §2.5'in "hücre JSONB olmasın" gerekçesi burada geçerli değil: o gerekçe
   **çalışan küme** üzerinde `GROUP BY` yapıldığı içindi; snapshot toplulaştırılmaz,
   bütün olarak okunur ve bir daha yazılmaz — `answers.feedback`'in sınıfındandır.

   **Bedeli açıkça yazılıyor:** dağılım iki temsile sahip olur (canlı `blueprint_cells`
   ve donmuş `blueprint_snapshot`) ve ikisi bilerek ayrışır. Ayrışma sessiz olmasın
   diye arayüz, yayınlanmış bir sürümü gösterirken dağılımı **snapshot'tan** okur,
   hücrelerden değil; hücreler yalnız taslak düzenleme ekranında görünür.
2. **KARAR (T501) — Konu, öğrenme çıktısının türevidir; beşinci eksen açılmaz.**
   Hücre dörtlü kalır: *(çıktı × zorluk × tip)*. FR-111'in istediği "konu dağılımı",
   `blueprint_cells → learning_outcomes.topic_id` üzerinden **türetilmiş, salt
   okunur bir rapor** olarak karşılanır; öğretmen onu doğrudan düzenlemez.

   **Gerekçe.** Bağımsız konu ekseni hücre uzayını konu sayısıyla çarpar. COME 331'in
   bugünkü verisinde bile bu, öğretmenin eline doldurulamayacak bir tablo verir ve
   Anayasa XI'in "etkin görünüp iş yapmayan öğe kusurdur" ölçüsüne düşer: çoğu hücresi
   sıfır kalan bir ızgara, doldurulmuş bir dağılım gibi görünür. Kardinalite tarafı da
   aynı yöne bakıyor — FR-113 soruyu **tek** çıktıya bağlıyor (§2.0), yani bir sorunun
   konusu zaten çıktısı üzerinden tekil olarak belirli. İki eksen tutmak, aynı olguyu
   iki yere yazmak olurdu.

   **Bedeli açıkça yazılıyor ve arayüzde görünür kılınıyor:** `topic_id`'si NULL olan
   bir çıktının konu ekseni yoktur, ve aynı konuya bağlı iki çıktı raporda toplanır.
   Bu yüzden türetilmiş konu dağılımı ekranda "şu kadar soru konusuz çıktıdan geliyor"
   satırıyla birlikte gösterilir; sessizce yuvarlanmaz (Anayasa III).

   **Karar hocaya sorulmadan verildi** ve bu, kararın kendisinden ayrı bir gerçektir:
   geri alınması göç değil, `blueprint_cells`'e bir kolon ve UNIQUE kısıtının
   genişletilmesi demektir. Ucuz olduğu için şimdi kapatmak, açık bırakıp `0008`'i
   geciktirmekten iyi.
3. **KARAR — denetim izi trigger'dır.** Politika değişikliği uygulama yolundan
   bağımsız olarak aynı işlemde audit satırı üretir; uygulama katmanına bırakılıp
   kaçırılabilir hâle getirilmez.
4. **KARAR — günlük token bütçesi sohbet üretimini kapsar.** `request_logs` gerçek
   sohbet sağlayıcı kullanımını toplar. Soru üretimi ayrı, daha sıkı istek ve
   eşzamanlılık kotasıyla sınırlıdır; sahte sağlayıcıya tahmini token maliyeti
   yazılmaz. UI bu alanı "günlük sohbet token bütçesi" diye adlandırır.
5. **KARAR — `exam_sessions.score` geriye uyumluluk için korunur.** Yeni puan
   `answers` üzerinden türetilir; eski oturumları ve istemcileri tek teslim
   haftasında migration ile kırmanın ölçülmüş bir faydası yoktur.
6. **KARAR — keyset sayfası toplam sayı taşımaz.** `next_cursor` devam bilgisidir;
   her sayfada `COUNT(*)` çalıştırmak ilk sayfanın sabit maliyet hedefiyle
   çelişir. Toplam gereken ekran kendi analitik sayım ucunu kullanır.
7. **KARAR (T501) — Sınıflandırılmamış kalem, eksik hücre değil; kapının ayrı ve
   adı konmuş ikinci maddesidir.** Yayın kapısı **iki** liste döndürür ve ikisinden
   biri boş değilse yayın reddedilir:

   - `eksik_hucreler` — §2.5'in diff sorgusu: istenen adet ile dolan adet tutmayan
     hücreler.
   - `siniflandirilmamis_kalemler` — sürümün kaleminde olup `learning_outcome_id`'si
     veya `difficulty`'si NULL olan sorular; her biri soru kimliği ve hangi alanının
     eksik olduğuyla.

   **Gerekçe.** Sınıflandırılmamış bir kalem hiçbir hücreye sayılmaz, yani tek listeli
   bir kapıda **başka bir hücre eksikmiş gibi** görünür. Öğretmen o hücreye soru
   eklemeye çalışır, kâğıt uzar, kapı yine kapalı kalır ve gerçek sebep hiç
   söylenmemiş olur. Anayasa V "backend tek hata zarfı üretir" derken kastedilen tam
   olarak bu: sebebi bilen katman cümleyi de kurmalı. §2.3'ün "bedeli açıkça
   yazılıyor" notu bu kararla kapanır — kural veri düzeyinde garanti değildir, ama
   kapının **görmezden gelemeyeceği** bir maddesidir.

   Kapı yayınlanmaya çalışılan sürümün kalemlerine bakar, ders havuzunun tamamına
   değil: havuzda sınıflandırılmamış soru bulunması bir kusur değil, normaldir
   (§2.3, mevcut satırlar NULL doğar).

9. **KARAR (T501) — Yürüyen sınav, oturumun `exam_version_id`'si neyi gösteriyorsa
   onu görür; sürüm ne değişir ne değiştirilebilir.** Bağ oturum açılırken **INSERT
   anında** kurulur ve bir daha yazılmaz (0007 `exam_sessions` tablo düzeyi UPDATE'ini
   çekmişti, 0008 geri vermiyor — §2.8). Kâğıt her istekte `exam_items ORDER BY
   position` ile okunur; soru payload'ının kopyası **alınmaz** (§2.6'nın snapshot
   gerekçesi).

   Bunun üç sonucu yazılı olsun:

   - **v2 yayınlamak v1'deki oturumlara dokunmaz.** v1 `superseded` olur, ama satır
     durur, `exam_items`'ı durur ve RLS'in üçüncü OR dalı (§2.6) oturum sahibine
     okumayı sürdürür. Yeni oturumlar v2'ye açılır.
   - **Pencere kapanması yürüyen oturumu düşürmez.** FR-116 "yeni oturum
     başlatamaz" der; `app.is_exam_open` yalnız `exam_sessions_self_insert`'i ve
     üyenin listeleme görüşünü bağlar.
   - **Yayınlanmış sürümün kâğıdı hiçbir kod yolundan değişmez.** `exam_items`'ta
     UPDATE yetkisi yok (§2.11), INSERT/DELETE politikaları `status='draft'` istiyor
     (§2.7). Yani "sınav sürerken soru değişti" durumu ifade edilemez.

   Kalan tek sızıntı yolu, kâğıttaki bir sorunun sonradan **reddedilmesiydi**:
   `questions_read` reddedilen soruyu öğrenciden gizler ve yürüyen kâğıt sessizce
   kısalırdı. §2.6'nın öngördüğü uygulama kapısı bu kararın parçasıdır — yayınlanmış
   ve superseded olmayan bir sürümün kaleminde yer alan soru reddedilemez, ret
   isteğine Türkçe gerekçeli 409 döner.
8. **KARAR — US10 senkron, kullanıcı kapsamlıdır.** `0012` sohbet sahibinin
   silme yetkisini açar; export ve öğrenci anonimleştirme API işleminde tamamlanır.
   Eğitmen sahipliği varken anonimleştirme 409 ile reddedilir. Veri hacmi asenkron
   export gerektirecek düzeye çıkarsa ayrı iş tablosu v2 kararıdır.
9. **Ölçüm yok.** Bu belgedeki hiçbir indeks, sorgu maliyeti veya ek SELECT **ölçülmemiştir**. §2.3, §3.3 ve §5.3'teki "ölçülmedi" notları rapora aynen taşınmalıdır; aksi hâlde SC-009 (belge-kod çelişkisi sıfır) düşer.
