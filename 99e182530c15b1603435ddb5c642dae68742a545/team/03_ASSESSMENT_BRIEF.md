# R3 — Assessment & Analytics (Ölçme ve Analitik) Brief

> **Kime:** DOU-Synapse takımının **R3 — Assessment & Analytics** rolüne.
> **Ne:** Soru havuzu, eğitmen onayı, sınav modu, değerlendirme ("neden yanlış?") ve
> Mastery-Lite. Backend'in **ölçme** ayağının tamamı sende.
>
> **Görevlerin:** T024-T025 (migration + modeller) · T029-T033 (soru üretimi, topics/questions
> ucu, grading, exams ucu, testler) · **Faz E'nin tamamı** (T036-T039).
>
> **Takvim:** Faz D işleri G7-G9 (12-14 Ağustos), Faz E G9-G10 (14-17 Ağustos).
> **G10 = 17 Ağustos = özellik dondurma.** Senin işin dondurmadan önce biten son
> özellik grubudur; geciken iş kesilir, ertelenmez. Teslim 24 Ağustos.
>
> İş listesinin tek kaynağı [`specs/001-course-assistant-mvp/tasks.md`](../../specs/001-course-assistant-mvp/tasks.md),
> dosya sahipliğinin tek kaynağı [`00_TAKIM_KOORDINASYON.md`](00_TAKIM_KOORDINASYON.md).
> Bu brief o ikisini **açıklar**, yerine geçmez. Çelişki görürsen tasks.md kazanır.

---

## 0. Bir bakışta

**Senin dosyaların (bunları yalnız sen düzenlersin):**

```
supabase/migrations/0004_assessment.sql            ← T024
apps/api/app/models/assessment.py                  ← T025
apps/api/app/modules/assessment/question_gen.py    ← T029
apps/api/app/modules/assessment/grading.py         ← T031
apps/api/app/modules/mastery/                      ← T036 (TAMAMI senin)
apps/api/app/api/questions.py                      ← T030
apps/api/app/api/exams.py                          ← T032, T037
apps/api/app/api/analytics.py                      ← T038
apps/api/tests/test_assessment.py                  ← T033
apps/api/tests/test_mastery.py                     ← T039
```

**Ortak (sıcak) dosyalar — yalnız EKLEME yaparsın:**
`apps/api/app/core/config.py` (kendi `# --- Assessment ---` bölümüne),
`apps/api/app/main.py` (yalnız `include_router` satırı + import),
`specs/001-course-assistant-mvp/contracts/openapi.json` (elle değil, yeniden export ederek),
`specs/001-course-assistant-mvp/tasks.md` (yalnız kendi satırının `[ ]` → `[x]` işareti).

**Senin OLMAYAN ama seninle konuşan dosyalar:**

| Dosya | Sahibi | Sana bakan yüzü |
|---|---|---|
| `app/modules/retrieval/service.py` (T006) | R1 | `retrieve(session, course_id, query)` — soru üretiminin ve grading'in kaynak chunk'ları |
| `app/modules/generation/llm.py`, `service.py` (T009/T012) | R1 | LiteLLM router + şemalı üretim; sen bunu **çağırırsın**, kendi LLM istemcini yazmazsın |
| `app/modules/guardrails/citation.py` (T013) | R2 | `dayanak_chunk_id` set-membership kontrolü |
| `app/modules/assessment/socratic.py` (T026) | R2 | Sokratik state machine — **aynı klasördesin ama bu dosya senin değil** |
| `app/api/chat.py` (T019/T027) | R1 | T037'de mastery güncellemesi buradan da çağrılacak — kodu R1 ekler, fonksiyonu sen verirsin |
| `apps/web/**` | R4 (Muratcan) | Sınav ekranı, soru onay paneli, analitik ekranı senin uçlarını tüketir |

**Kritik yol — bunu ilk bitir:**
`00_TAKIM_KOORDINASYON.md §4` T024'ü takımın 3 numaralı darboğazı olarak işaretliyor.
**T024 (migration) + T030'un `topics` ucu** senin kendi işlerinin de, R4'ün sınav ve soru
onay ekranlarının da önünü açar. Sıra: `T024 → T025 → T030'un topics kısmı → gruba haber ver`.
Soru üretimi (T029) ve mastery (T036) topics olmadan anlamsızdır.

---

## 1. Kurulum (bir kez, ~45 dakika)

Repo kökü **`~/code/DOU-Synapse`** olacak. iCloud'a senkronlanan klasörlere (Masaüstü,
Belgeler) koyma — Python projelerini bozar (Anayasa IX).

Tam ve doğrulanmış kurulum belgesi: [`specs/001-course-assistant-mvp/quickstart.md`](../../specs/001-course-assistant-mvp/quickstart.md).
Aşağısı onun kopyala-yapıştır özetidir.

### 1.1. Önkoşullar

```bash
brew install uv
brew install oven-sh/bun/bun
xcode-select --install        # pgvector'ü derlemek için make/clang
```

### 1.2. PostgreSQL 16 + pgvector (kaynaktan)

Proje **PostgreSQL 16'ya sabitlidir**. Homebrew'un `pgvector` paketi pg17/18'e karşı
derlenir ve 16'ya kurulmaz; bu yüzden pgvector kaynaktan derlenir.

```bash
brew install postgresql@16
brew services start postgresql@16

# postgresql@16 keg-only: PATH'e ekle (kalıcı olması için ~/.zshrc'ye de yaz)
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"

cd /tmp
git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git
cd pgvector
make PG_CONFIG=/opt/homebrew/opt/postgresql@16/bin/pg_config
make install PG_CONFIG=/opt/homebrew/opt/postgresql@16/bin/pg_config
```

Doğrulama (boş dönerse derleme yanlış `pg_config` ile yapılmıştır):

```bash
psql -d postgres -c "SELECT name FROM pg_available_extensions WHERE name = 'vector';"
```

### 1.3. Veritabanı: oluştur → migrate → yerel roller → seed

**Sıra önemlidir.** Migration `dou_app` / `dou_worker` rollerini NOLOGIN oluşturur;
`local_dev_setup.sql` yalnız yerelde giriş açar; seed demo kullanıcılarını yazar.

```bash
cd ~/code/DOU-Synapse
createdb dou_synapse
psql -d dou_synapse -f supabase/migrations/0001_core_schema.sql
psql -d dou_synapse -f supabase/local_dev_setup.sql
psql -d dou_synapse -f supabase/seed_demo.sql
```

İsteğe bağlı RLS kanıtı (hepsi PASS dönmeli, sonunda ROLLBACK yapar):

```bash
psql -d dou_synapse -f supabase/tests/rls_isolation.sql
```

### 1.4. Backend

```bash
cd ~/code/DOU-Synapse/apps/api
uv venv --python 3.12          # pyproject: >=3.12,<3.13 (onnxruntime/fastembed pini)
uv pip install -e ".[dev]"
cp ../../.env.example .env
uv run uvicorn app.main:app --reload
```

Ayrı bir terminalde:

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

`.env.example` varsayılanları yerel kurulumla **birebir** eşleşir; hiçbir değeri
değiştirmeden çalışır. Senin için önemli iki değişken:

- `DEV_AUTH_ENABLED=true` → `Bearer dev:<uuid>` kimlikleri kabul edilir.
- `EMBEDDING_PROVIDER=hashing` → deterministik yerel embedding, model indirmeden
  çevrimdışı geliştirme. **Testlerde bu değer kullanılır, değiştirme.**

### 1.5. Frontend (R4'ün ekranlarını görmek için)

```bash
cd ~/code/DOU-Synapse/apps/web
bun install
bun run dev        # http://localhost:3000
```

### 1.6. Testler ve kalite kapıları

```bash
cd ~/code/DOU-Synapse/apps/api
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

`conftest.py` her koşuda `dou_synapse_test` veritabanını düşürüp sıfırdan kurar;
geliştirme veritabanına dokunmaz. Testler **kasıtlı olarak `dou_app` rolüyle**
bağlanır — superuser ile koşan bir izolasyon testi hiçbir şey kanıtlamaz.

### 1.7. Demo kullanıcıları

| Kullanıcı | E-posta | UI rolü | UUID |
|---|---|---|---|
| Ayşe Hoca | `ayse@dogus.edu.tr` | instructor | `11111111-1111-1111-1111-111111111111` |
| Burak Yılmaz | `burak@dogus.edu.tr` | student | `22222222-2222-2222-2222-222222222222` |

Elle API çağırırken: `Authorization: Bearer dev:11111111-1111-1111-1111-111111111111`.

`profiles` tablosunda **sistem geneli rol sütunu yoktur**; yetki daima ders bazlıdır
(`course_memberships.role`). "Eğitmen" demek "bu dersteki üyelik rolü instructor" demektir.

### 1.8. Branch aç

```bash
cd ~/code/DOU-Synapse
git checkout main && git pull
git checkout -b feat/T024-assessment-migration
```

**Görev = commit = PR.** Her görev kendi branch'i ve kendi PR'ı ile kapanır.

---

## YAPIŞTIRILACAK PROMPT (Başlıyor)

> Yeni bir AI sohbeti aç, aşağıdaki bloğun tamamını yapıştır. Sonra "Adım 1'den
> başlayalım" de. Her yeni görev için sohbeti yenilemek yerine aynı sohbette devam et,
> bağlam korunur.

Merhaba. Doğuş Üniversitesi COME 491/492 bitirme projesi **DOU-Synapse (CourseGPT)**
takımındayım ve rolüm **R3 — Assessment & Analytics**. Teslim: **24 Ağustos 2026**.

**Ürün:** Eğitmenin yüklediği ders materyalleriyle SINIRLI, her cevabı dosya adı +
sayfa/slayt kaynağıyla veren bir RAG ders asistanı. Materyalde karşılığı olmayan soru
nazikçe reddedilir; internet bilgisi hiçbir cevaba karışmaz.

**Repo:** https://github.com/muratcan-ates/DOU-Synapse — lokal: `~/code/DOU-Synapse`

**Stack:** Python 3.12 + FastAPI + SQLAlchemy async + psycopg · PostgreSQL 16 + pgvector ·
Next.js 16 + Tailwind v4 + Bun · uv (Python paket yöneticisi) · ruff + pytest ·
LiteLLM (Groq → Gemini failover). **LangChain / LlamaIndex / LangGraph BİLİNÇLİ OLARAK
YOK** — düz Python servis kodu ve açık state machine kullanıyoruz; bana bu çatıları
önerme.

**Şu an biten altyapı:** ders/üyelik API'si, dosya yükleme + PDF/PPTX/MD/kod parser'ları,
sayfa sınırını koruyan chunking, embedding (multilingual-e5-large; testte `hashing`),
pgvector, iki katmanlı izolasyon (uygulama + PostgreSQL RLS), Next.js frontend
(giriş, ders listesi, materyal yükleme, sekmeler, üye yönetimi, sınav ve Sokratik
ekranlarının tasarım önizlemeleri). 68 test geçiyor.

**Benim görevlerim:** T024-T025 (assessment migration + SQLAlchemy modelleri),
T029 (soru üretimi), T030 (topics + questions uçları), T031 (grading),
T032 (exams ucu), T033 (assessment testleri), T036-T039 (Mastery-Lite + analitik + testler).

**Benim dosyalarım (yalnız bunları düzenlerim):**
`supabase/migrations/0004_assessment.sql`, `apps/api/app/models/assessment.py`,
`apps/api/app/modules/assessment/question_gen.py`,
`apps/api/app/modules/assessment/grading.py`, `apps/api/app/modules/mastery/`,
`apps/api/app/api/{questions,exams,analytics}.py`,
`apps/api/tests/{test_assessment,test_mastery}.py`.
Ortak dosyalarda yalnız **ekleme** yaparım: `app/core/config.py`, `app/main.py`,
`contracts/openapi.json`, `tasks.md`.

**Bana ait OLMAYAN dosyalar — bunlara kod yazmanı istemiyorum, dokunma:**
`app/modules/retrieval/*` ve `app/modules/generation/*` (R1),
`app/modules/guardrails/*` ve `app/modules/assessment/socratic.py` (R2),
`app/api/chat.py` (R1), `apps/web/**` (R4),
`supabase/migrations/0001_core_schema.sql` (DONDURULMUŞ),
`app/core/security.py`, `app/api/deps.py` (auth; değişecekse takım lideri onaylar).

**Projenin pazarlık edilmez ilkeleri (Anayasa v1.0.0), benim işimi doğrudan bağlayanlar:**

1. **Kaynak yoksa cevap yok.** Öğrenciye giden her akademik içerik gerçek bir chunk'a
   atıfla doğrulanır; `chunk_id` set-membership kontrolünden geçer. Dosya adı ve sayfa
   numarası model metninden DEĞİL chunk metadata'sından üretilir.
2. **İki katmanlı izolasyon.** Uygulama katmanında sunucu tarafı üyelik doğrulaması +
   PostgreSQL RLS. **İstemciden gelen `course_id` asla yetki değildir.** Yeni uç yazarken
   `app/api/deps.py` içindeki `CourseMemberDep` / `CourseInstructorDep` kullanılır.
3. **Fail-closed.** Belirsizlikte sistem kapanır, açılmaz: şemaya uymayan LLM çıktısı
   havuza yazılmaz, geçersiz dayanak atılır, onaylı soru yoksa sınav başlamaz.
4. **Türkçe birinci sınıftır.** Kullanıcıya dönen her metin (hata mesajları dahil)
   anlaşılır Türkçedir; ham stack trace asla gösterilmez. Kod, commit mesajları ve
   dosya adları İngilizcedir.
5. **Ölçmeden iddia etme.** "Deterministik" ve "garanti" kelimeleri yalnız gerçekten
   deterministik mekanizmalar için kullanılır.
6. **Doğrulama bitmeden "bitti" yok.** Test yeşil + lint temiz + davranış gerçek API
   çağrısıyla gözlenmiş olmadan görev kapanmaz.

**Benim işimin özel kuralları:**

- `questions.payload` **jsonb** ve dört tip taşır: `mcq | open | code_trace | bug_hunt`.
- **Eğitmen onayı olmadan soru öğrenciye GÖSTERİLMEZ.** `status: draft|approved|rejected`;
  bu kural hem uygulama kodunda hem RLS politikasında zorlanır.
- **Sınav modu politikaları sunucuda zorlanır.** `exam` → ipucu kapalı, tek deneme,
  geri bildirim sınav sonunda; `practice` → süresiz, ipucu açık, anında geri bildirim.
  Süre ve soru sayısı MVP'de config sabitlerinden gelir (eğitmen ayar ekranı P1).
- **Süre dolunca cevaplanmamış sorular BOŞ sayılır — yanlış sayılmaz, puana katılmaz.**
  Bağlantı koparsa öğrenci kalan süreyle devam eder (oturum durumu sunucuda).
  Onaylı soru havuzu boşsa sınav başlatılamaz.
- **"Neden yanlış":** MCQ'da çeldirici (distractor) → `source_chunk` eşlemesi birincil ve
  deterministik yoldur; LLM'e sorulmaz.
- **Açık uçlu değerlendirme şeması:** `{score: 0-100, eksik_noktalar: [...], dayanak_chunk_id}`
  ve `dayanak_chunk_id` citation validator'ın set-membership kontrolünden geçer.
- **Mastery EWMA:** `yeni = 0.7 × eski + 0.3 × son_skor`. İpucu kademesi çarpanları:
  0→1.00 · 1→0.85 · 2→0.70 · 3→0.50 · 4→0.25. Seviye eşikleri: <0.40 Geliştirilmeli ·
  0.40-0.74 Orta · ≥0.75 İyi. Çıktı **resmî not değil**, çalışma önerisi göstergesidir
  (human-in-the-loop; arayüzde bu ibare yer alır).
- **Kod ASLA çalıştırılmaz.** `code_trace` ve `bug_hunt` değerlendirmesi tamamen cevap
  anahtarı üzerinden, statik yapılır. Sandbox, `exec`, `subprocess` yok.

**Benim bilgi seviyem:** Python ve FastAPI ile rahatım; SQLAlchemy async ve PostgreSQL
RLS politikaları yazmakta yeniyim. **Türkçe anlat, kod ve commit mesajları İngilizce
olsun.** Bana tam dosya ver, "şurayı da güncelle" deyip geçme; hangi dosyanın hangi
satırına ne ekleyeceğimi açıkça söyle.

**Çalışma biçimimiz:** Bir seferde tek görev. Görev bitmeden diğerine geçmiyoruz.
Her görev sonunda `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`
üçünü de yeşil görmeden PR açmıyorum.

**Bu projeyi anladığını göstermek için, koda başlamadan önce şu beşini cevapla:**

1. Hangi görevlerden sorumluyum ve hangisini **ilk** yazmalıyım, neden?
2. Bir öğrenci `draft` durumundaki bir soruyu hangi iki mekanizma sayesinde göremez?
3. `exam` ve `practice` modlarının sunucuda zorlanan farkları neler?
4. Sınav süresi dolduğunda cevaplanmamış sorulara ne olur?
5. Neden hiçbir aşamada kod çalıştırmıyoruz?

Sonra Adım 1'e (T024 migration) geçelim.

## YAPIŞTIRILACAK PROMPT (Bitti)

---

## 2. Teslimatlar

### Teslimat 1 — T024: `supabase/migrations/0004_assessment.sql` (EN KRİTİK, ilk yaz)

Beş tablo + üç enum + RLS politikaları. `0001_core_schema.sql`'in üslubunu birebir
taklit et: `BEGIN; ... COMMIT;`, Türkçe yorumlar, `ENABLE` **ve** `FORCE ROW LEVEL SECURITY`,
politikalar `app.is_member()` / `app.is_instructor()` yardımcılarını kullanır.

```sql
CREATE TYPE question_type   AS ENUM ('mcq', 'open', 'code_trace', 'bug_hunt');
CREATE TYPE question_status AS ENUM ('draft', 'approved', 'rejected');
CREATE TYPE exam_mode       AS ENUM ('practice', 'exam');

topics        (id, course_id, name, created_by, created_at)
questions     (id, course_id, topic_id, type question_type, payload jsonb,
               source_chunk_id → chunks(id), status question_status DEFAULT 'draft',
               created_by, reviewed_by, reviewed_at, created_at)
exam_sessions (id, course_id, user_id, mode exam_mode, started_at, expires_at,
               finished_at, score numeric, question_ids uuid[])
answers       (id, session_id, question_id, course_id, given text,
               is_correct boolean, score integer, hint_level integer DEFAULT 0,
               feedback jsonb, answered_at)
mastery       (user_id, topic_id, course_id, score double precision,
               answer_count integer, updated_at, PRIMARY KEY (user_id, topic_id))
```

**Tasarım kuralları — bunlara uy, gerekçeleri var:**

- **`course_id`'yi denormalize et** (`questions`, `exam_sessions`, `answers`, `mastery`).
  `chunks` tablosunda da aynısı yapıldı: izolasyon filtresi JOIN'e bağlı kalmaz, RLS
  politikası tek satırda yazılır. Küçük bir tekrar, büyük bir güvenlik sadeliği.
- **`expires_at` sütunda tutulur**, her istekte hesaplanmaz. Bağlantı koptuğunda kalan
  süre buradan okunur; istemcinin saatine güvenilmez.
- **`question_ids uuid[]`**: sınav oturumu açılırken seçilen sorular sabitlenir. Sonradan
  onaylanan/reddedilen sorular başlamış bir sınavı değiştirmez.
- **`feedback jsonb`** biçimi ARCHITECTURE §5 ile birebir aynı:
  `{"score": 0-100, "eksik_noktalar": [...], "dayanak_chunk_id": "..."}`.
- `mastery.answer_count` "ilk cevap mı" sorusunu cevaplar (T036'daki başlangıç davranışı).

**RLS politikaları — projenin en kritik satırları:**

```sql
-- topics: dersin üyeleri okur, yalnız eğitmen yazar.
CREATE POLICY topics_member_read      ON topics FOR SELECT USING (app.is_member(course_id));
CREATE POLICY topics_instructor_write ON topics FOR INSERT WITH CHECK (app.is_instructor(course_id));

-- questions: ÖĞRENCİ YALNIZ approved GÖRÜR. draft/rejected yalnız eğitmene açıktır.
CREATE POLICY questions_read ON questions
    FOR SELECT USING (
        app.is_instructor(course_id)
        OR (app.is_member(course_id) AND status = 'approved')
    );
```

`exam_sessions` ve `answers`: kullanıcı yalnız kendi satırlarını görür/yazar; eğitmen
kendi dersinin satırlarını **okur** (analitik için), yazamaz. `mastery`: öğrenci kendi
satırını, eğitmen kendi dersinin satırlarını okur.

**`payload` jsonb biçimleri — dört tip.** Bu şekli T029, T031 ve R4'ün ekranı ortak
kullanacak; bir kez kararlaştır, sonra değiştirme:

```jsonc
// mcq
{"stem": "...", "options": [{"key": "A", "text": "..."}, ...],
 "answer_key": "B",
 "distractor_sources": {"A": "<chunk_id>", "C": "<chunk_id>", "D": "<chunk_id>"},
 "explanation": "..."}

// open
{"prompt": "...", "answer_key": "...",
 "key_points": ["...", "..."],          // eksik_noktalar bunlara karşı çıkarılır
 "rubric": [{"point": "...", "weight": 40}, ...]}

// code_trace
{"language": "python", "code": "...", "prompt": "Bu kodun çıktısı nedir?",
 "answer_key": "<beklenen çıktı>", "explanation": "..."}

// bug_hunt
{"language": "c", "code": "...", "prompt": "Koddaki hatayı bulun.",
 "answer_key": {"line": 12, "bug_type": "off-by-one", "fix_summary": "..."},
 "explanation": "..."}
```

`distractor_sources` **"neden yanlış?"nin deterministik yakıtıdır** (T031). Üretimde
zorunlu tut; boşsa soru şemadan geçmez.

**Kabul:** Migration temiz bir veritabanında hatasız koşar, `pytest` yeşil kalır
(conftest tüm migration'ları sırayla uygular), `supabase/tests/rls_isolation.sql`
hâlâ PASS döner.

**Bitince gruba haber ver:** "T024 hazır, 0004_assessment.sql main'de." R4 sınav ekranını
buna göre planlıyor.

---

### Teslimat 2 — T025: `apps/api/app/models/assessment.py`

0004'teki tabloların SQLAlchemy modelleri. **Deseni `app/models/core.py`'den kopyala:**
`Mapped[...]` + `mapped_column`, `uuid_pk` / `uuid_fk` / `created_at` yardımcı tipleri,
enum'lar için `_pg_enum(...)` (mevcut PostgreSQL enum tipine bağlanır, `create_type=False`).

Migration'lar düz SQL'dir, ORM'den **üretilmez**. Model dosyası şemayı *yansıtır*;
şema değişikliği önce SQL'de yapılır.

```python
class QuestionType(StrEnum):
    MCQ = "mcq"
    OPEN = "open"
    CODE_TRACE = "code_trace"
    BUG_HUNT = "bug_hunt"

class QuestionStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"

class ExamMode(StrEnum):
    PRACTICE = "practice"
    EXAM = "exam"
```

`payload` ve `feedback` için `sqlalchemy.dialects.postgresql.JSONB` kullan; Python
tarafında `dict[str, Any]`.

---

### Teslimat 3 — T030: `apps/api/app/api/questions.py`

**Bu ucun `topics` kısmını T029'dan ÖNCE bitir.** Soru üretimi de mastery de konuya
bağlıdır; R4'ün soru onay panelindeki konu ekleme formu da buraya bağlanır (FR-027).

| Yöntem | Yol | Yetki | Not |
|---|---|---|---|
| `POST` | `/courses/{course_id}/topics` | `CourseInstructorDep` | Konu oluştur |
| `GET` | `/courses/{course_id}/topics` | `CourseMemberDep` | Konu listesi |
| `POST` | `/courses/{course_id}/questions/generate` | `CourseInstructorDep` | Gövde: `{topic_id, type, count}` → `draft` sorular |
| `GET` | `/courses/{course_id}/questions` | `CourseMemberDep` | `?status=` filtresi; öğrenci yalnız `approved` görür |
| `PATCH` | `/courses/{course_id}/questions/{question_id}/approve` | `CourseInstructorDep` | |
| `PATCH` | `/courses/{course_id}/questions/{question_id}/reject` | `CourseInstructorDep` | |

**Kurallar:**

- Yetkilendirme **daima** `CourseMemberDep` / `CourseInstructorDep` ile. Kendi üyelik
  sorgunu yazma; `deps.py` senin dosyan değil ve zaten doğru yapıyor.
- `GET /questions` öğrenci için `status` parametresi ne gelirse gelsin **sunucuda**
  `approved`'a sabitlenir. RLS ikinci katman olarak zaten kapatır; ama uygulama katmanı
  da kapatmalı — "iki katmanlı izolasyon" tam olarak budur.
- Hata mesajları Türkçe ve `app/core/errors.py` sınıflarıyla: `NotFoundError`,
  `PermissionDeniedError`, `ConflictError`, `ValidationError`. Kendi JSON hata gövdeni
  üretme; zarf `{error: {code, message}}` merkezî handler'dan gelir.
- Şemalar `apps/api/app/schemas/assessment.py` içinde (yeni dosya, senin).

`main.py`'ye tek satır ekle ve OpenAPI'yi yeniden export et (§4.3).

---

### Teslimat 4 — T029: `apps/api/app/modules/assessment/question_gen.py`

İçerikten dört tipte soru üretir. **Kendi LLM istemcini yazma** — R1'in
`app/modules/generation/` servisini çağır.

```python
async def generate_questions(
    session: AsyncSession,
    *,
    course_id: UUID,
    topic_id: UUID,
    question_type: QuestionType,
    count: int,
) -> list[Question]:
    """Konu adıyla retrieve edilen chunk'lardan `status=draft` soru üretir.

    Her soru bir kaynak chunk'a bağlıdır (`source_chunk_id`); şemaya uymayan
    çıktı bir kez yeniden denenir, yine uymazsa HAVUZA YAZILMAZ (fail-closed).
    """
```

**Akış:** konu adı → `retrieve(session, course_id, topic.name)` → chunk'lar →
prompt → LLM → **Pydantic doğrulama** → geçersizse **1 retry** → hâlâ geçersizse
o soruyu at (`ValidationError` fırlatma; geçerli olanları yaz, kaça düştüğünü döndür).

**Zorunlu alanlar:**

- `source_chunk_id` **her soruda zorunlu** ve retrieve edilmiş kümeye ait olmalı.
  Model uydurursa soru düşer.
- `mcq` için `distractor_sources` doldurulur: her yanlış şıkkın çeliştiği chunk.
  Modelden bunu istemek yerine, şıkkın dayandığı chunk'ı **retrieve edilmiş kümeden
  eşleştirerek** yaz — deterministik yol her zaman birincildir.
- Üretilen her soru `status=draft`. **`approved` üreten bir kod yolu hiç olmasın.**

**Ölçüt:** SC-009 şema geçerliliği ≥ %98. Kaç soru üretildi / kaçı şemadan geçti
sayısını logla; R5 bunu test raporuna yazacak.

---

### Teslimat 5 — T031: `apps/api/app/modules/assessment/grading.py`

İki ayrı yol; karıştırma.

**MCQ — tamamen deterministik, LLM yok:**

```
seçilen == answer_key  → is_correct=True, score=100
seçilen != answer_key  → is_correct=False, score=0
                         "neden yanlış" = payload.distractor_sources[seçilen]
                         → chunk metadata'sından {file_name, page_number|slide_number, snippet}
```

Dosya adı ve sayfa **chunk metadata'sından** üretilir, model metninden değil (Anayasa I).

**open / code_trace / bug_hunt — şemalı LLM değerlendirmesi:**

```
öğrenci cevabı + payload.answer_key + kaynak chunk'lar
  → LLM → Pydantic: {score: 0-100, eksik_noktalar: [str], dayanak_chunk_id: UUID}
  → şema bozuksa 1 retry
  → yine bozuksa DEĞERLENDİRME TAMAMLANAMADI (uydurma puan gösterme — FR-020)
  → dayanak_chunk_id set-membership kontrolünden geçer; geçmezse dayanak DÜŞER
```

Set-membership kontrolü R2'nin `guardrails/citation.py`'ı ile **aynı davranışı** yapar.
T013 henüz main'de değilse kendi dosyanda küçük bir yardımcı yaz (`_valid_source_ids`
kümesine üyelik), T013 gelince R2'nin fonksiyonuna geç. **`guardrails/` klasörüne kod
yazma** — o dosyalar R2'nin.

**`code_trace` / `bug_hunt` için kritik uyarı:** kod **çalıştırılmaz**. Ne `exec`, ne
`eval`, ne `subprocess`, ne Docker sandbox. Değerlendirme tamamen cevap anahtarı ve
kaynak chunk üzerinden metinseldir (FR-026). Bunu modül docstring'ine yaz — jüri
soracak, kod okuyan bulacak.

---

### Teslimat 6 — T032: `apps/api/app/api/exams.py`

| Yöntem | Yol | Ne yapar |
|---|---|---|
| `POST` | `/courses/{course_id}/exams` | Oturum başlat (`{mode, topic_id?}`) |
| `GET` | `/courses/{course_id}/exams/{session_id}` | Oturum durumu + **kalan süre** + sorular |
| `POST` | `/courses/{course_id}/exams/{session_id}/answers` | Cevap gönder |
| `POST` | `/courses/{course_id}/exams/{session_id}/finish` | Bitir → puan + soru bazlı geri bildirim |

**Sunucuda zorlanan mod politikaları — bu tablo ucun sözleşmesidir:**

| | `exam` | `practice` |
|---|---|---|
| Süre | `EXAM_DURATION_MINUTES` (config sabiti) | **Süresiz** (`expires_at = NULL`) |
| İpucu | **Kapalı** — istenirse `403` + Türkçe mesaj | Açık |
| Deneme | Soru başına **tek** — ikincisi `409` | Serbest |
| Geri bildirim | **Sınav sonunda** (`/finish`) | **Anında**, cevapla birlikte döner |
| Mastery | Bitişte, tüm cevaplarla | **İlk cevap** esas alınır (FR-017) |

**Bunlar istemciye bırakılmaz.** Frontend "exam modunda ipucu butonunu gizlemek" ile
yetinir; reddi backend verir.

**Kenar durumlar — hepsi T033'te testli:**

- **Onaylı havuz boşsa** oturum başlatılamaz → `ConflictError` + "Bu derste henüz
  onaylanmış soru yok." Bu, "kaynak yoksa cevap yok"un sınav ayağıdır.
- **Süre dolduysa** cevap kabul edilmez → `409`. Cevaplanmamış sorular **BOŞ** sayılır:
  yanlış değildir ve **puana katılmaz**. Yani `puan = (verilen cevapların skor toplamı) /
  (cevaplanan soru sayısı)`. Hiç cevap yoksa puan gösterilmez, açıklayıcı Türkçe mesaj döner.
- **Bağlantı koparsa** öğrenci `GET .../{session_id}` ile döner ve `expires_at - now()`
  kadar süreyle devam eder. Süre sunucuda, sayaç istemcide.
- Soru sayısı ve süre `config.py`'deki sabitlerden gelir — eğitmen ayar ekranı P1'dir,
  yapma.

`config.py`'ye ekleyeceğin bölüm (var olan hiçbir alanı silmeden, kendi başlığının altına):

```python
    # --- Assessment ---------------------------------------------------------
    exam_question_count: int = 10
    exam_duration_minutes: int = 20
    question_generation_batch: int = 5
    mastery_alpha: float = 0.3          # yeni = (1-alpha)*eski + alpha*son
```

---

### Teslimat 7 — T036: `apps/api/app/modules/mastery/service.py`

```python
"""Mastery-Lite: konu bazlı EWMA ile çalışma performans göstergesi.

    yeni = 0.7 x eski + 0.3 x son_skor
    ipucu kademesi çarpanları: 0 -> 1.00, 1 -> 0.85, 2 -> 0.70, 3 -> 0.50, 4 -> 0.25
    seviye eşikleri: < 0.40 Geliştirilmeli | 0.40-0.74 Orta | >= 0.75 İyi

SADELEŞTİRME GEREKÇESİ (raporda aynen savunulur): BKT/IRT gibi yerleşik öğrenci
modelleri parametre kestirimi için bizde olmayan öğrenci verisi ister. EWMA, yakın
geçmişe ağırlık veren üstel unutma modellerine kaba bir yaklaşımdır; 0.7/0.3 seçimi
duyarlılık notuyla raporlanır.

Bu çıktı RESMÎ NOT DEĞİLDİR; çalışma önerisi göstergesidir (human-in-the-loop).
Arayüzde bu ibare zorunludur.
"""

HINT_MULTIPLIERS = {0: 1.00, 1: 0.85, 2: 0.70, 3: 0.50, 4: 0.25}
```

**Karar noktaları — netleştir ve docstring'e yaz:**

- Skor alanı **0-1**. Grading 0-100 döndürür; `/100` ile normalize et.
- Çarpan **EWMA'dan önce** ham skora uygulanır: `son = raw/100 * HINT_MULTIPLIERS[level]`.
- **İlk cevap** (kayıt yok): `yeni = son` (0.7×0 ile başlatma — öğrenciyi haksız yere
  düşük gösterir). `answer_count` 1 olur. Bu davranış T039'da testle sabitlenir.
- Seviye eşikleri **sınır dahil**: 0.40 → Orta, 0.75 → İyi. T039 bu iki sınırı tam
  değerle test eder.

---

### Teslimat 8 — T037: mastery entegrasyonu

- **`app/api/exams.py`** (senin dosyan): `/finish` içinde grading sonrası her cevabın
  konusu için `mastery.update(...)` çağrılır.
- **`app/api/chat.py`** (R1'in dosyası): Sokratik oturum kapanışında ipucu kademesi
  çarpanıyla aynı fonksiyon çağrılır. **Bu dosyaya sen kod yazmazsın.** Yapman gereken:
  `mastery/service.py` içinde tek ve temiz bir giriş noktası bırakmak —

  ```python
  async def record_answer(
      session: AsyncSession, *, user_id: UUID, topic_id: UUID, course_id: UUID,
      raw_score: int, hint_level: int = 0,
  ) -> float:
      """Cevabı mastery'ye işler ve güncel puanı döndürür."""
  ```

  sonra R1'e "chat.py'nin Sokratik kapanışında şunu çağır" diye imzayı vermek. Çağrıyı o ekler.

---

### Teslimat 9 — T038: `apps/api/app/api/analytics.py`

| Yöntem | Yol | Yetki | İçerik |
|---|---|---|---|
| `GET` | `/courses/{course_id}/analytics/me` | `CourseMemberDep` | Öğrencinin konu bazlı mastery listesi + seviye etiketi |
| `GET` | `/courses/{course_id}/analytics/course` | `CourseInstructorDep` | Konu bazlı sınıf ortalaması, en çok yanlış yapılan sorular, kapsam dışı ret istatistiği |

Ret istatistiği `request_logs` / `chat_messages`'tan gelir (R1'in T017 migration'ı).
O tablolar henüz yoksa bu alanı **son bırak** ve `null` dönüp UI'da "veri yok" göster —
uydurma sayı üretme (Anayasa III).

`/analytics/course` yanıtına **öğrenci adı bazlı döküm koyma**; MVP'de konu bazlı
toplulaştırma yeterli ve KVKK açısından daha temiz.

---

### Teslimat 10 — T033 + T039: testler

**`tests/test_assessment.py` — sekiz vaka, tasks.md'de tek tek sayılı:**

1. Soru üretimi şema geçerliliği; bozuk LLM çıktısı retry sonrası **reddedilir**.
2. `draft` soru öğrenci uçlarından **görünmez**.
3. `exam` modunda ipucu isteği **reddedilir**.
4. Süre dolunca cevap kabul edilmez **ve** cevaplanmamış sorular boş sayılır (puana katılmaz).
5. MCQ "neden yanlış" **doğru çeldirici kaynağını** döndürür.
6. Boş onaylı havuzda sınav başlatma **reddedilir**.
7. Oturuma dönüşte **kalan süre korunur**.
8. `practice` modda ipucu açık **ve** anında geri bildirim gelir.

**`tests/test_mastery.py` — dört vaka:** EWMA hesabı · ipucu çarpanları ·
seviye sınır değerleri (**0.40 ve 0.75 tam sınırda**) · ilk cevapta başlangıç davranışı.

**Test kuralları:**

- LLM **mock'lanır**. Testte gerçek Groq/Gemini çağrısı olmaz: ağ yok, kota yok,
  belirsizlik yok. `monkeypatch` ile generation servisini değiştir.
- `EMBEDDING_PROVIDER=hashing` (conftest zaten ayarlıyor) — deterministik.
- Süre testinde `sleep` kullanma; `expires_at`'i geçmişe çekerek veya saati enjekte
  ederek test et. Yavaş test, koşulmayan testtir.
- İzolasyon testi ekle (tasks.md'de zorunlu değil ama Anayasa II bunu bekler): başka
  dersin sorusu/oturumu hiçbir koşulda dönmez.
- Yeni tabloların TRUNCATE listesine eklenmesi gerekirse `conftest.py`'de o satır ortak
  alandır; yalnız kendi tablo adlarını **ekle**, var olanı düzenleme.

---

## 3. KURALLAR

1. **`course_id` istemciden gelen bir yetki değildir.** Her uçta `CourseMemberDep` veya
   `CourseInstructorDep`. Kendi üyelik sorgunu yazma.
2. **Onaysız soru öğrenciye gösterilmez — iki katmanda.** Uygulama kodunda filtre + RLS
   politikası. Biri unutulursa diğeri kurtarır; ikisi de olacak.
3. **Sınav politikaları sunucuda.** İpucu kapalılığı, tek deneme, geri bildirim zamanı,
   süre: hepsi backend kararı. Frontend'e güvenme.
4. **Fail-closed.** Şema bozuksa yazma, dayanak geçersizse düşür, havuz boşsa başlatma,
   değerlendirme yapılamıyorsa uydurma puan gösterme.
5. **Kaynak referansı chunk metadata'sından üretilir**, model metninden asla.
6. **Kod çalıştırma yok.** `exec` / `eval` / `subprocess` / sandbox — hiçbiri.
7. **Migration'lar düz SQL.** ORM'den üretilmez; `0001_core_schema.sql` dondurulmuştur,
   şema değişikliği yeni migration ile yapılır.
8. **Sıcak dosyalarda ekleme yap, düzenleme yapma.** `config.py`'de kendi bölümüne,
   `main.py`'de tek `include_router` satırı. Çakışırsa `git pull --rebase` + kendi satırını
   yeniden ekle; asla `--ours` / `--theirs` ile toptan çözme.
9. **Yeni uç = aynı commit'te OpenAPI güncellemesi.** Sözleşme ile kod ayrışmaz.
10. **Türkçe kullanıcı metni, İngilizce kod.** Commit mesajları conventional commit
    (`feat:`, `fix:`, `test:`), gövdede "ne" değil **"neden"**.
11. **`Co-Authored-By` satırı ASLA eklenmez.** AI kullansan da commit yalnız senin adına
    gider (Anayasa IX).
12. **Görev = commit = PR.** Bir görev bitmeden diğerine geçme; `main`'e doğrudan push yok.
13. **PR öncesi üçlü kapı:** `uv run pytest` + `uv run ruff check .` +
    `uv run ruff format --check .` — üçü de yeşil değilse PR açma.
14. **30 dakika kuralı.** 30 dakikadan fazla takılırsan gruba yaz. Tek başına saat harcama.

---

## 4. YAPMA listesi

- `supabase/migrations/0001_core_schema.sql`'i değiştirme (DONDURULMUŞ).
- `app/core/security.py` ve `app/api/deps.py`'ye dokunma (auth; Murat onaylar).
- `app/modules/guardrails/` ve `app/modules/assessment/socratic.py`'ye kod yazma (R2).
- `app/modules/retrieval/` ve `app/modules/generation/`'a kod yazma (R1) — **çağır, yazma.**
- `app/api/chat.py`'ye dokunma (R1) — T037'de imzayı ver, çağrıyı o ekler.
- `apps/web/` altına dokunma, `lib/types.ts`'i düzenleme (R4). Tip değişikliğini R4'e bildir.
- `openapi.json`'ı **elle** düzenleme — export komutunu çalıştır.
- Kendi LLM istemcini/`httpx` çağrını yazma — LiteLLM router R1'de.
- LangChain / LlamaIndex / LangGraph ekleme (bilinçli olarak kapsam dışı).
- Kod çalıştıran hiçbir şey yazma (sandbox, `exec`, container).
- Testte gerçek LLM çağırma.
- Semantik/benzerlik tabanlı soru eşleştirme yazma — yalnız exact-match cache var (FR-034).
- Eğitmen sınav ayarı ekranı yapma (P1, kapsam dışı).
- `.env` commit etme; gerçek anahtarı AI'ya verme.
- Ölçmediğin bir sayıyı rapora/PR açıklamasına yazma.

---

## 5. Çıktı kontrol listesi

**T024 (migration) — PR öncesi:**

- [ ] Temiz veritabanında hatasız koşuyor; `pytest` tüm migration'ları uygulayıp yeşil kalıyor
- [ ] 5 tablo + 3 enum var; `course_id` denormalize edildi (questions, exam_sessions, answers, mastery)
- [ ] Her tabloda `ENABLE` **ve** `FORCE ROW LEVEL SECURITY`
- [ ] Öğrenci `draft` soruyu **göremediği** politika ile kanıtlanıyor (`psql` ile elle denendi)
- [ ] `rls_isolation.sql` hâlâ PASS
- [ ] Gruba "T024 hazır" mesajı atıldı

**T025 (modeller):**

- [ ] `core.py` deseni birebir (`_pg_enum`, `uuid_pk`, `Mapped[...]`)
- [ ] `payload` ve `feedback` JSONB; enum'lar `create_type=False`
- [ ] `ruff check` + `ruff format --check` temiz

**T030 (topics + questions ucu):**

- [ ] `POST/GET /courses/{course_id}/topics` çalışıyor (gerçek `curl` ile denendi)
- [ ] Öğrenci `GET /questions` çağrısında yalnız `approved` görüyor (gerçek istekle kanıtlı)
- [ ] Üye olmayan kullanıcı `404` alıyor (dersin varlığı sızmıyor)
- [ ] `main.py`'ye router eklendi, `openapi.json` yeniden export edildi
- [ ] Gruba "topics ucu hazır" mesajı atıldı (R4 bekliyor)

**T029 (soru üretimi):**

- [ ] Dört tip de üretiliyor, hepsi `status=draft`
- [ ] `source_chunk_id` her soruda dolu ve retrieve edilmiş kümeye ait
- [ ] `mcq` payload'ında `distractor_sources` dolu
- [ ] Bozuk çıktı 1 retry sonrası **havuza yazılmıyor**
- [ ] Şema geçerlilik oranı loglanıyor (SC-009 ölçümü için)

**T031 (grading):**

- [ ] MCQ tamamen deterministik, LLM çağrısı yok
- [ ] "Neden yanlış" doğru çeldiricinin kaynağını, dosya adı + sayfa/slayt ile döndürüyor
- [ ] Açık uçlu çıktı `{score, eksik_noktalar[], dayanak_chunk_id}` şemasına uyuyor
- [ ] `dayanak_chunk_id` set kontrolünden geçiyor; geçmezse düşüyor
- [ ] Modül docstring'inde "kod asla çalıştırılmaz" gerekçesi yazılı

**T032 (exams ucu):**

- [ ] `exam` ve `practice` farkları sunucuda zorlanıyor (dört madde de)
- [ ] Boş onaylı havuzda `409` + Türkçe mesaj
- [ ] Süre dolunca cevap reddediliyor; cevapsızlar puana katılmıyor
- [ ] `GET .../{session_id}` kalan süreyi doğru döndürüyor
- [ ] `openapi.json` güncellendi

**T033 + T039 (testler):**

- [ ] T033'ün 8 vakası da ayrı test fonksiyonu olarak var
- [ ] T039'un 4 vakası var; 0.40 ve 0.75 **tam sınırda** test edildi
- [ ] Hiçbir test gerçek LLM veya ağ çağırmıyor
- [ ] Testler `sleep` kullanmıyor
- [ ] Başka dersin verisi dönmediği testle kanıtlı

**T036-T038 (mastery + analitik):**

- [ ] EWMA, çarpanlar, eşikler ARCHITECTURE §5 ile birebir aynı
- [ ] İlk cevap davranışı docstring'de yazılı ve testli
- [ ] `record_answer(...)` imzası R1'e iletildi
- [ ] Analitik uçları doğru yetki bağımlılığını kullanıyor
- [ ] Ölçülmemiş hiçbir alan uydurma değerle doldurulmadı

---

## 6. Adım adım plan

### Adım 1 — T024 migration (G7 sabahı, EN KRİTİK)

```bash
git checkout -b feat/T024-assessment-migration
```

AI'ya şunu söyle:

> "`supabase/migrations/0004_assessment.sql` yazacağım. `0001_core_schema.sql`'in üslubunu
> birebir taklit et: BEGIN/COMMIT, Türkçe yorumlar, ENABLE + FORCE ROW LEVEL SECURITY,
> politikalar `app.is_member()` / `app.is_instructor()` yardımcılarını kullansın.
> Tablolar: topics, questions, exam_sessions, answers, mastery. Enum'lar: question_type
> (mcq|open|code_trace|bug_hunt), question_status (draft|approved|rejected), exam_mode
> (practice|exam). `course_id`'yi questions, exam_sessions, answers ve mastery'de
> denormalize et. En kritik politika: öğrenci yalnız `approved` soruları görebilsin,
> draft/rejected yalnız eğitmene açık olsun. `payload` ve `feedback` jsonb."

Sonra: `psql -d dou_synapse -f supabase/migrations/0004_assessment.sql` → `uv run pytest`.
İki eğitmen/öğrenci hesabıyla `psql` üzerinden `SET LOCAL app.current_user_id` yapıp
draft sorunun öğrenciye görünmediğini **elle gör**. Commit, PR, gruba haber.

### Adım 2 — T025 modeller (G7)

```bash
git checkout -b feat/T025-assessment-models
```

> "`apps/api/app/models/assessment.py` yazacağım. `app/models/core.py` desenini birebir
> kullan: `_pg_enum` yardımcısı, `uuid_pk`/`uuid_fk`/`created_at` tipleri, JSONB için
> `sqlalchemy.dialects.postgresql.JSONB`. 0004'teki beş tabloyu birebir yansıt."

### Adım 3 — T030'un topics kısmı (G7, aynı gün bitir)

Konu CRUD'u küçük bir iştir ama üç kişiyi bekletir. Uç ayağa kalkar kalkmaz
`curl` ile dene, OpenAPI'yi export et, gruba yaz.

### Adım 4 — T029 soru üretimi (G8)

R1'in generation servisi hazır olmalı. Değilse mock'la ilerle ve arayüzü sabitle;
gerçek servis gelince tek satır değişecek biçimde yaz.

### Adım 5 — T030'un kalanı: generate / list / approve / reject (G8)

R4'ün soru onay paneli buna bağlanır; bittiğinde haber ver.

### Adım 6 — T031 grading (G9)

Önce MCQ yolunu bitir (deterministik, testi kolay), sonra LLM'li açık uçlu yolu.

### Adım 7 — T032 exams ucu (G9)

Mod politikalarını en başta ayrı bir fonksiyonda topla (`_policy_for(mode)`);
uç kodu politikayı okur, kendi kararını vermez.

### Adım 8 — T033 testler (G9)

Sekiz vakayı tek tek yaz. Buradaki bir kırmızı, demoda bir felakettir.

### Adım 9 — T036-T039 mastery + analitik (G9-G10)

Faz E'nin tamamı sende. **G10 (17 Ağustos) özellik dondurma** — bu adım biterse
özellik seti tamamlanmış olur.

### Adım 10 — Devir (G10)

R4'e sınav/analitik uçlarının son hâlini, R5'e SC-009 (şema geçerliliği) ve
"neden yanlış" örneklerini ver. Test raporundaki ölçme bölümünün verisi senden çıkacak.

### Zaman planı

| Gün | İş | Süre |
|---|---|---|
| Kurulum (bir kez) | §1'in tamamı | 45-60 dk |
| G7 | T024 + T025 + topics ucu | ~6 sa |
| G8 | T029 + T030'un kalanı | ~6 sa |
| G9 | T031 + T032 + T033 | ~8 sa |
| G9-G10 | T036 + T037 + T038 + T039 | ~6 sa |
| G10 | Devir + dondurma kontrolü | ~2 sa |

---

## 7. Ortak dosya protokolü

### 7.1. `config.py`

Kendi `# --- Assessment ---` başlığının altına ekle. Var olan hiçbir alanı silme,
sırasını değiştirme.

### 7.2. `main.py`

Yalnız import + tek `include_router` satırı. Başka hiçbir şey.

### 7.3. OpenAPI yeniden export (uç ekleyen her commit'te)

```bash
cd apps/api && .venv/bin/python -c "
import json, os
os.environ.setdefault('DEV_AUTH_ENABLED','true')
from app.main import create_app
spec = create_app().openapi()
open('../../specs/001-course-assistant-mvp/contracts/openapi.json','w').write(
    json.dumps(spec, ensure_ascii=False, indent=2))
print('güncellendi:', len(spec['paths']), 'yol')
"
```

(uv ortamı kullanıyorsan `.venv/bin/python` yerine `uv run python`.)

### 7.4. `tasks.md`

Yalnız kendi görevinin `[ ]` → `[x]` işareti ve tarihli DONE notu. Başkasının satırına
dokunma.

---

## 8. Takıldığında

1. Hata mesajının **tamamını** + çalıştırdığın komutu + ne beklediğini yapıştır.
2. Migration hatalarında `psql`'in tam çıktısını ver; SQLAlchemy hatalarında traceback'in
   son 20 satırı yeterli.
3. **30 dakikadan fazla takılırsan gruba yaz.** Özellikle T024 gecikirse üç kişi bekler.
4. Başkasının dosyasını düzeltmen gerektiğini düşünüyorsan **düzeltme, sahibine söyle**.
5. "Şunu da ekleyeyim" diye düşündüğünde önce gruba sor — PLAN'da bilinçli olarak
   kesilmiş bir şeyi geri getiriyor olabilirsin.
6. AI'ya **asla verme:** gerçek `.env` içeriği, LLM API anahtarları, Supabase service-role
   anahtarı, gerçek öğrenci verisi.
7. **AI'ya bırakılmayacak işler** (insan gözüyle kontrol edilir): RLS politikaları ve
   migration'lar, `course_id` filtreleri ve yetkilendirme kodu, rapora yazılacak metrikler.
   AI yazsa bile **satır satır sen okuyacaksın**.

---

## 9. Son söz

Senin işin projenin **"öğretiyor mu?"** sorusunun cevabı. Retrieval ve guardrail zinciri
"yanlış cevap vermiyoruz"u kanıtlar; sen **"öğrenci gerçekten ölçülüyor mu, eksiği
söyleniyor mu, hoca kontrolü elinde tutuyor mu"** sorularının kodunu yazıyorsun.
Demo günü jürinin gördüğü tam döngü senden geçiyor:

**eğitmen soru ürettirir → onaylar → öğrenci sınava girer → puan + "neden yanlış" +
eksik noktalar görür → mastery değişir.**

Üç cümlede özet:

- **Onaysız soru öğrenciye gitmez** — iki katmanda zorlanır, tek katmana güvenilmez.
- **Politikalar sunucuda** — ipucu kapalılığı bir UI kararı değil, bir güvenlik sınırıdır.
- **Puan bir öneridir, not değildir** — insan döngüde kalır ve arayüz bunu söyler.

T024'ü ilk gün bitir ve gruba haber ver. Gecikirse üç kişi bekler; erken biterse
takımın önü açılır.

İyi çalışmalar.
