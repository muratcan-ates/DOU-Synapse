# 002 — API sözleşme etkisi

Bu belge kararları yazar, seçenek sunmaz. Her karar mevcut koddan dosya:satır kanıtıyla bağlanmıştır. Kaynak gerçek `apps/api/app/api/*.py` + `apps/api/app/main.py`; sözleşme dosyası onun türevidir (`specs/001-course-assistant-mvp/contracts/README.md`).

---

## 0. Bugünkü sözleşmenin ölçüsü (değişimin başlangıç noktası)

Ölçülen (uydurulmadı — `openapi.json` ayrıştırılarak sayıldı):

| Ölçü | Değer |
|---|---|
| Dosya | `/Users/muratates/code/dou-lead/specs/001-course-assistant-mvp/contracts/openapi.json`, 3292 satır |
| Biçim | OpenAPI **3.1.0**; `info: {title: "DOU-Synapse API", version: "0.1.0"}` (`apps/api/app/core/config.py:77-78`) |
| Yol sayısı | **25** |
| İşlem sayısı | **31** |
| `components.schemas` | **48** |
| Şemada olmayan router | `/internal/drain` — `include_in_schema=False` (`apps/api/app/api/internal.py:41`) |
| Hata zarfı şeması | **YOK.** `components.schemas` içinde `HTTPValidationError` ve FastAPI'nin `ValidationError`'ı var; uygulamanın gerçek zarfı `{"error":{"code","message"}}` (`apps/api/app/core/errors.py:57-62`) **hiçbir uçta belgeli değil** — yalnız `contracts/README.md` düzyazısında anlatılıyor |

**Tespit (US8 / FR-180 kalemi, kod yazmadan kapanır):** `specs/001-course-assistant-mvp/contracts/README.md` başlığı hâlâ **"Mevcut uçlar (9 yol, 13 işlem)"** diyor ve tablosunda yalnız courses/documents/health var. Dosyanın kendisi 25 yol / 31 işlem taşıyor ve `README.md:483` doğru sayıyı ("25 yol") yazıyor. Aynı belgenin iki bölümü çelişiyor. 002'de bu tablo yeniden üretilecek; ayrıca aynı README'deki iki `[NEEDS CLARIFICATION]` (validation zarfı, CI diff kontrolü) **artık cevaplanmış durumda** ve kapatılacak: birincisi `main.py:83` ile çözüldü (`validation_error_handler` kayıtlı), ikincisi §4'te karara bağlanıyor.

---

## 1. YENİ uçlar

Ortak kurallar (hepsinde geçerli, uçlarda tekrarlanmaz):

- Yetki daima `deps.py` bağımlılıklarıyla verilir; uç kendi üyelik sorgusunu yazmaz (`apps/api/app/api/questions.py:13-14`'ün yazılı kuralı).
- **404 = varlık gizleme.** Üye olunmayan ders için `require_course_member` zaten 404 döner (`deps.py:108-111`); bu, aşağıdaki her ders kapsamlı ucun sessiz hata durumudur ve tabloda tekrar yazılmaz.
- **401** her korumalı uçta mümkündür (`deps.py:32-34`); tabloda tekrarlanmaz.
- Yeni model/zarflar **router'da değil `app/schemas/*` içinde** yaşar — `schemas/chat.py`'nin modül docstring'i (satır 166-171) bu kuralı bir kusurdan öğrenerek yazdı: zarfın iki tanımı olması istemciyi hiç koşmamış bir sözleşmeye karşı yazdırdı.

### 1.1 Sınav kilidi durumu (US1 / FR-105)

| Metot | Yol | Yetki |
|---|---|---|
| GET | `/courses/{course_id}/chat/availability` | **üye** (`CourseMemberDep`) |

Uç `apps/api/app/api/chat.py` içinde, `router = APIRouter(prefix="/courses/{course_id}")` altında yaşar.

**Yetki kuralı bilerek `CourseMemberDep`'tir, `UnlockedCourseMemberDep` değildir.** Kilit durumunu bildiren ucu kilitlemek, kullanıcıya "neden kilitli" diyemeyen bir kilit üretirdi. Aynı gerekçe router seviyesinde `APIRouter(dependencies=[...])` kullanılmamasının da sebebidir: router bağımlılığı bu ucu kendi kilidiyle kapatırdı.

Yanıt şeması — `app/schemas/chat.py`:

```python
class ChatAvailabilityOut(BaseModel):
    available: bool                  # falsy = kilitli (fail-closed, Anayasa IV)
    reason: str | None = None        # "exam_in_progress" | "policy_all_modes_closed"
    message: str | None = None       # Türkçe, sunucudan; arayüz metin uydurmaz
    allowed_modes: list[ChatMode]    # FR-130'un öğrenci yüzü (§1.4)
    hint_limit: int | None = None    # FR-131; None = sınır yok
```

Alan adı `locked` değil **`available`**: yanıt okunamaz ya da eksik gelirse falsy kalır ve arayüz kilitli tarafa düşer (Anayasa IV). `available: true` her zaman eğitmen için döner — muafiyet kuralı istemcide tekrarlanmaz (`deps.py:84-86`).

**Hata durumları:** yok. Bu uç kasten hiçbir zaman 403 dönmez; 401/404 dışında tek yanıtı 200'dür.

**Neden yeni bir uç, neden mevcut bir yanıta alan eklenmedi:** `GET /courses/{id}/exams` (`exams.py:327-360`) teorik olarak yeterli veriyi taşır ama oturum başına ayrı bir `_answers_of` sorgusu koşturuyor (`exams.py:231`, `:357-360`) — nav'ı altı ders sayfasında N+1 sorguya bağlardı. `GET /courses/{id}` (`courses.py:74-79`) dersin kimliğini anlatır; sohbet yüzeyinin durumunu oraya asmak, dersi her okuyan isteğe bir sınav sorgusu ekler.

### 1.2 Öğrenme çıktıları (FR-110)

| Metot | Yol | Yetki | Yanıt |
|---|---|---|---|
| GET | `/courses/{course_id}/learning-outcomes` | üye | `list[LearningOutcomeOut]` |
| POST | `/courses/{course_id}/learning-outcomes` | eğitmen | 201 `LearningOutcomeOut` |
| PUT | `/courses/{course_id}/learning-outcomes/{outcome_id}` | eğitmen | 200 `LearningOutcomeOut` |
| DELETE | `/courses/{course_id}/learning-outcomes/{outcome_id}` | eğitmen | 204 |

`app/api/questions.py` içindeki topics uçlarının (`questions.py:51-73`) birebir ikizidir; yeni router açılmaz, çünkü öğrenme çıktısı soru havuzunun ölçme eksenidir ve `questions.py` zaten `tags=["assessment"]` taşıyor.

```python
class LearningOutcomeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)      # "ÖÇ-3"
    description: str = Field(min_length=3, max_length=1000)
    topic_id: UUID | None = None

class LearningOutcomeOut(BaseModel):
    id: UUID; course_id: UUID; code: str; description: str
    topic_id: UUID | None; created_by: UUID; created_at: datetime
    question_count: int          # havuzda bu çıktıya bağlı onaylı soru sayısı
```

| Hata | Ne zaman |
|---|---|
| 409 `conflict` | Aynı derste aynı kod (`learning_outcomes_course_code_key`); `create_topic`'in `IntegrityError → ConflictError` deseni (`questions.py:60-63`) |
| 409 `conflict` | DELETE, bir blueprint hücresi bu çıktıya bağlıyken (`ON DELETE RESTRICT`); mesaj çıkış yolunu tarif eder — `documents.py:180-183`'ün kuralı |
| 422 `validation_error` | Boş/uzun kod |

**`PATCH` değil `PUT`, çünkü:** bu depoda `PATCH` hiç yoktur (openapi.json'da tek bir PATCH işlemi yok; `tasks.md:105` kararı açıkça "PATCH yerine POST"). Kısmi güncelleme yerine tam değiştirme seçiliyor ve aynı karar blueprint hücrelerinde **zorunlu** hâle geliyor: veri modeli `blueprint_cells` üzerinde `dou_app`'ten UPDATE yetkisini çekiyor, yani kısmi güncelleme depolama katmanında ifade edilemiyor. İki farklı varlık için iki farklı güncelleme fiili kullanmak, aynı kuralı iki kez hatırlamayı gerektirirdi (Anayasa XI).

### 1.3 Sınav blueprint'i (FR-111…FR-116)

**Yeni router: `apps/api/app/api/blueprints.py`**, `prefix="/courses/{course_id}"`, `tags=["blueprints"]`, `main.py`'ye `include_router` ile eklenir. Ayrı dosya olmasının sebebi `exams.py`'nin 632 satır olması ve öğrenci akışını anlatması (`exams.py:114-118`); blueprint bir **eğitmen tasarım yüzeyi**dir ve bir dosya tek bir işi anlatmalıdır (Anayasa XI).

| Metot | Yol | Yetki |
|---|---|---|
| GET | `/blueprints` | üye (öğrenci yalnız açık pencereli yayınlanmışları görür) |
| POST | `/blueprints` | eğitmen → 201 |
| GET | `/blueprints/{blueprint_id}` | üye |
| PUT | `/blueprints/{blueprint_id}` | eğitmen |
| DELETE | `/blueprints/{blueprint_id}` | eğitmen → 204 |
| GET | `/blueprints/{blueprint_id}/versions` | eğitmen |
| POST | `/blueprints/{blueprint_id}/versions` | eğitmen → 201 (draft) |
| GET | `/blueprints/{blueprint_id}/versions/{version_id}` | üye |
| PUT | `/blueprints/{blueprint_id}/versions/{version_id}/items` | eğitmen |
| GET | `/blueprints/{blueprint_id}/versions/{version_id}/readiness` | eğitmen |
| POST | `/blueprints/{blueprint_id}/versions/{version_id}/publish` | eğitmen |

İstek/yanıt şemaları — `app/schemas/blueprint.py`:

```python
class BlueprintCellIn(BaseModel):
    learning_outcome_id: UUID
    difficulty: QuestionDifficulty          # easy | medium | hard
    question_type: QuestionType             # 0004'ün enum'u, yeniden tanımlanmaz
    question_count: int = Field(ge=1, le=100)
    points_per_question: int = Field(default=1, ge=1, le=100)

class BlueprintIn(BaseModel):
    model_config = ConfigDict(extra="forbid")   # ChatRequest:61 deseni
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    duration_minutes: int = Field(ge=1, le=600)
    max_attempts: int = Field(default=1, ge=1)
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    cells: list[BlueprintCellIn] = Field(min_length=1, max_length=64)

class BlueprintOut(BaseModel):
    id: UUID; course_id: UUID; title: str; description: str | None
    duration_minutes: int; max_attempts: int
    opens_at: datetime | None; closes_at: datetime | None
    total_questions: int          # SUM(cells.question_count) — TÜRETİLİR, saklanmaz
    total_points: int             # SUM(count * points_per_question)
    cells: list[BlueprintCellOut] | None   # öğrenciye None
    published_version_no: int | None
    open_now: bool                # sunucu saatiyle; istemci saati karar vermez
    created_at: datetime; updated_at: datetime
```

**`cells` öğrenciye `None` döner, boş liste değil.** "Bu sınavda 2 zor açık uçlu var" sınav öncesi istihbarattır ve `blueprint_cells`'e öğrenci SELECT politikası bilerek yazılmıyor. Boş liste dönmek "hücre yok" derdi, yani veriyi yanlış anlatırdı; `None` "sana kapalı" der. Rol bazlı alan filtreleme deponun kurulu deseni: `questions.py:89-96` aynı `QuestionOut` modelinde `payload`'ı role göre daraltıyor.

**`total_questions` neden istekte yok, yanıtta var:** türetilmiş olduğu için tutarsız olamaz. spec.md:232'nin saydığı hata sınıflarından biri (tip toplamları adetle eşleşmiyor) böylece tanımdan silinir.

**Yayın kapısı iki uca bölünüyor ve bu bilinçli:**

- `GET .../readiness` → **200**, `BlueprintReadinessOut`:
  ```python
  class CellGapOut(BaseModel):
      learning_outcome_code: str; learning_outcome_id: UUID
      difficulty: QuestionDifficulty; question_type: QuestionType
      required: int; filled: int
  class BlueprintReadinessOut(BaseModel):
      publishable: bool
      gaps: list[CellGapOut]
      message: str            # "Zor MCQ hücresi 2 soru istiyor ama 1 tane var."
  ```
- `POST .../publish` → **200** `ExamVersionOut` ya da **409** `{"error":{"code":"blueprint_unfilled","message":"..."}}`.

**Neden ikiye bölündü:** hata zarfı tek biçimlidir ve yalnız `code` + `message` taşır (`errors.py:57-62`). FR-114'ün istediği hücre kırılımı yapısal veridir; onu 409 gövdesine sıkıştırmak zarfı büyütmeyi gerektirirdi ve zarfın tekliği bu deponun en çok yatırım yapılmış sözleşme kararıdır (`errors.py:68-75`'in tüm gerekçesi budur). Doğru bölme: **arayüz tabloyu yayın düğmesine basmadan önce `readiness`'ten okur**, 409 yalnız yarışı kapatır. Bu ayrıca "etkin görünüp iş yapmayan buton kusurdur" kuralını (Anayasa XI) karşılar — düğme, tablo doluyken etkinleşir.

| Hata | HTTP / code | Ne zaman |
|---|---|---|
| Tutarsız dağılım | 422 `validation_error` | FR-112; mesaj hücreyi Türkçe adıyla söyler |
| `opens_at >= closes_at` | 422 `validation_error` | `exam_blueprints_window_order` CHECK'inden önce uygulama katmanında |
| Dağılım karşılanmıyor | **409** `blueprint_unfilled` | FR-114 |
| Draft olmayan sürüme item yazma | **409** `conflict` | `exam_items` INSERT politikası `status='draft'` ister |
| Zaten yayınlanmış sürümü tekrar yayınlama | 409 `conflict` | `exam_versions_one_published` kısmi tekil indeksi |
| Oturumu olan blueprint'i silme | 409 `conflict` | `exam_sessions.exam_blueprint_id` RESTRICT |
| Öğrenci eğitmen ucunu çağırır | 403 `permission_denied` | `deps.py:118-121` |

**409 seçimi 422'ye tercih edildi çünkü:** yayınlanamama isteğin biçiminden değil sistemin o anki durumundan kaynaklanır ve kullanıcı eylemiyle (soru üretip onaylayarak) çözülür. `exams.py:399` ve `:417` 409'u tam bu sınıf için kullanıyor.

### 1.4 Ders AI politikası (FR-130…FR-137)

| Metot | Yol | Yetki |
|---|---|---|
| GET | `/courses/{course_id}/ai-policy` | **eğitmen** |
| PUT | `/courses/{course_id}/ai-policy` | eğitmen |
| GET | `/courses/{course_id}/ai-policy/history` | eğitmen (sayfalı) |

**Öğrenci için ayrı bir uç AÇILMIYOR.** Öğrencinin politikadan görmesi gereken tek şey "hangi modlar açık, kaç ipucu kaldı, asistan şu an kullanılabilir mi" — üçü de `GET /chat/availability`'de (§1.1) zaten var. İkinci bir öğrenci yüzeyi açmak, aynı kararı iki uçta hesaplamak olurdu ve ikisi ayrışırdı (Anayasa XI). Bütçe ve eşik bilgisi eğitmene özeldir.

```python
class CourseAiPolicyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowed_modes: list[ChatMode] | None = None    # None = global varsayılan (FR-136)
    hint_limit: int | None = Field(default=None, ge=0, le=10)
    evidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    daily_llm_budget: int | None = Field(default=None, ge=0)
    source_document_ids: list[UUID] | None = None  # None = tüm ders materyali

class CourseAiPolicyOut(CourseAiPolicyIn):
    course_id: UUID
    effective: EffectivePolicyOut     # NULL'lar çözülmüş hâli — arayüz çözmez
    updated_by: UUID | None; updated_at: datetime | None
    budget_used_today: int; budget_remaining_today: int | None
```

**`null` "ayarlanmamış" demektir ve bu ayrım sözleşmenin parçasıdır** (FR-136). Bu yüzden `PUT` tam değiştirmedir ve `extra="forbid"` taşır: eksik bırakılan alan "dokunma" değil "sıfırla"dır ve bu belirsizlik gövdeden okunabilir olmalıdır. Arayüzün varsayılanı kendi hesaplamaması için `effective` alanı sunucudan gelir — `errors.ts:5-9`'un "arayüz kendi metnini uydurmaz" kuralının veri karşılığı.

`allowed_modes` içinde `exam` **kabul edilmez** → 422. `post_chat` zaten `mode=exam`'i reddediyor (`chat.py:582-588`); politika üzerinden geri açılabilseydi o kural delinirdi.

Politika devreye girince **mevcut uçların hata yüzeyi genişler** (kırılma değil, ekleme):

| Uç | Yeni hata |
|---|---|
| `POST /chat` (`chat.py:561`) | 403 `mode_not_allowed` (FR-130); 429 `course_budget_exhausted` (FR-134 — 500 değil, çünkü arıza değil sınırdır) |
| `POST /exams/{id}/hint` (`exams.py:474`) | 409 `hint_limit_reached` (FR-131) |

`daily_llm_budget` için **429** seçildi, 402/503 değil: 429 zaten "şimdi olmaz, sonra dene" anlamını taşıyor ve `RateLimitError` bu depoda mevcut (`chat.py:589-594`). Ayrı `code` şart, çünkü arayüz kişisel hız sınırıyla ders bütçesini ayırt edip farklı cümle göstermeli.

### 1.5 KVKK — dışa aktarma ve silme (FR-200…FR-202)

**Yeni router: `apps/api/app/api/me.py`**, `prefix="/me"`, `PrincipalDep` ile (ders kapsamı yok). Emsal: `courses.py:31` `list_my_courses` zaten ders kapsamsız ve `PrincipalDep` kullanıyor.

| Metot | Yol | Yetki | Yanıt |
|---|---|---|---|
| GET | `/me/export` | kimlik | 200 `application/json` |
| POST | `/me/deletion-request` | kimlik | 202 `DeletionRequestOut` |
| DELETE | `/courses/{course_id}/chat/sessions/{session_id}` | üye | 204 |
| DELETE | `/courses/{course_id}/chat/sessions` | üye | 204 `X-Deleted-Count` yerine gövdede sayı |

Son iki uç `chat.py`'ye girer (ders kapsamlı, `CourseMemberDep`); silme kullanıcının **kendi** oturumudur ve RLS zaten başkasınınkini göstermez (`0003_chat.sql:171-175`).

**Kritik bulgu — bu iş bir migration olmadan çalışmaz.** `0003_chat.sql`'de `chat_sessions` için `_self_read` (171), `_self_insert` (177) ve `_self_update` (181) politikaları var; **DELETE politikası YOKTUR**. RLS altında politikasız komut sessizce 0 satır etkiler, yani `DELETE` başarılı görünüp hiçbir şey silmez — fail-closed doğru davranış ama FR-200'ü imkânsız kılar. Dahası `0003_chat.sql:186-188` `chat_messages` için "UPDATE/DELETE politikası YOKTUR — mesaj geçmişi denetlenebilir olmak zorundadır" diyerek bunu **bilinçli** bir karar olarak yazmış.

Karar: **oturum satırı silinir, mesajlar FK cascade ile gider** (`0003_chat.sql:68`, `ON DELETE CASCADE`). PostgreSQL'de referans bütünlüğü eylemleri RLS'i atlar, dolayısıyla `chat_messages`'a DELETE politikası eklemeye gerek yoktur ve 0003'ün denetlenebilirlik kararı **korunur**: mesaj tek tek silinemez, yalnız oturum bütün olarak kaldırılabilir. Gereken tek şey `chat_sessions` üzerinde bir `chat_sessions_self_delete` politikasıdır ve bu, 0003'ün yazılı kararını değiştirdiği için göç dosyasında gerekçesiyle yazılmalıdır. Veri modeli belgesinin §1'deki "US10 mevcut tablolar üzerinde çalışır" cümlesi bu yönüyle **eksiktir** ve düzeltilmelidir.

`GET /me/export` kapsamı ve **kapsam dışı bırakılanı da sözleşme yazar**:

```python
class UserExportOut(BaseModel):
    exported_at: datetime
    profile: ProfileExport
    memberships: list[MembershipExport]
    chat_sessions: list[ChatSessionExport]     # mesajlar ve atıflar gömülü
    exam_sessions: list[ExamSessionExport]     # cevaplar ve geri bildirim gömülü
    mastery: list[TopicProgress]               # mevcut şema yeniden kullanılır
    not_included: list[str]                    # neyin NEDEN olmadığı, Türkçe
```

`request_logs` dışa aktarmaya **girmez** ve bu `not_included`'da yazılır: o tabloda SELECT politikası bilinçli olarak yoktur (`chat.py:662-668`'in gerekçesi) ve zaten yalnız sayısal/kategorik alan taşır — kişisel içerik yoktur. Ölçüm kaydını "veriniz" diye sunmak, olmayan bir şeyi vaat etmek olurdu.

**Senkron 200, asenkron iş değil.** spec.md:237 büyük veride asenkron öneriyor; **ölçüm yok** ve tek kullanıcının kendi sohbeti + sınavı ile sınırlı bir gövdenin büyüklüğü ölçülmeden asenkron kuyruk eklemek, ölçmeden karmaşıklık eklemektir (Anayasa III + XI). Karar: senkron, ve bu sınır `docs/kvkk.md`'de yazılır. Ölçüm teslim öncesi koşulur; aşarsa 202 + iş kimliğine geçilir.

`POST /me/deletion-request` → **202** `{request_id, status: "received", message}`. Ders sahibi eğitmen için **409 `conflict`**: "Bu hesap N dersin eğitmeni. Hesap silinirse ders ve öğrenci verisi de silinir; önce dersleri devredin." — FR-202'nin "ne sessizce başarısız olsun ne veriyi düşürsün" şartı. `courses.py:150-151`'in "kendi eğitmen üyeliğinizi kaldıramazsınız" kararıyla aynı aile.

> **AÇIK KALAN (uydurulmuyor):** talebin yazılacağı `deletion_requests` tablosu veri modeli belgesinde tanımlanmadı (§8'de açık soru olarak duruyor). Uç bu tablo tanımlanmadan yazılamaz. Sözleşme tarafı hazırdır; göç kararı verilmeden uç eklenmemelidir.

### 1.6 Belge işleme işini yeniden çalıştırma (FR-213 / FR-214)

| Metot | Yol | Yetki | Yanıt |
|---|---|---|---|
| POST | `/courses/{course_id}/documents/{document_id}/reprocess` | eğitmen | **202** `DocumentUploadOut` |

`documents.py`'ye girer, `_trigger_worker`'ı (`documents.py:23-32`) aynen kullanır. **202**, çünkü yükleme ucu da 202 dönüyor (`documents.py:35`) ve iş aynı iştir: kuyruğa yeni bir `ingestion_jobs` satırı yazılır, istemci `status` alanını izler.

| Hata | Ne zaman |
|---|---|
| 409 `conflict` | Belgenin işi hâlâ `pending`/`running` — ikinci kuyruk satırı yazılmaz |
| 404 `not_found` | Belge yok ya da başka dersin (`documents.py:116`, `:130` deseni) |
| 403 | Öğrenci |

**`DocumentOut` genişler (additive, kırılmaz):**

```python
class IngestionJobOut(BaseModel):
    status: JobStatus              # pending | running | completed | failed
    attempt_count: int
    last_error: str | None
    next_attempt_at: datetime | None
class DocumentOut(BaseModel):
    ...                             # mevcut sekiz alan aynen
    job: IngestionJobOut | None = None   # öğrenciye None
```

`job` öğrenciye `None`'dır çünkü `jobs_instructor_read` (`0001_core_schema.sql:384-390`) satırı öğrenciye zaten göstermez — uygulama katmanı da bağımsız olarak `None` yazar (Anayasa II).

### 1.7 Yeni liste uçlarının hangisi sayfalanır — yazılı kural

FR-160 tam beş listeyi sayıyor; 002 birçok yeni liste ekliyor ve "hangisi sayfalanır" sorusu her yeni uçta yeniden sorulmasın diye kural burada tek yerde yazılıyor:

> **Satır sayısı kullanıcı eylemiyle sınırsız büyüyebiliyorsa sayfalanır; eğitmenin elle girdiği ve onlarla ölçülen listeler sayfalanmaz.**

| Sayfalanır | Sayfalanmaz |
|---|---|
| `/courses`, `/documents`, `/questions`, `/chat/sessions`, `/chat/sessions/{id}` (FR-160'ın beşi) | `/topics` (`questions.py:67`) |
| `/ai-policy/history` (denetim kaydı, zamanla büyür) | `/learning-outcomes`, `/blueprints`, `/blueprints/{id}/versions` |
| — | `/members` (`courses.py:82`), `/exams` (`exams.py:327`) |

`/members` ve `/exams` FR-160'ın listesinde **yok** ve 002'de sayfalanmıyor. Bu bir eksik değil karardır ve raporda böyle yazılır: `/exams` bir öğrencinin kendi oturumlarıdır ve kullanıcı başına onlarla ölçülür; `/members` bir sınıf mevcududur. İkisi de ölçülmedi; ölçülüp aşarlarsa aynı `PageOut` zarfına geçerler (§2), yeni bir mekanizma gerekmez.

### 1.8 Mevcut uçlarda **kırılmayan** sözleşme genişlemesi

Hepsi opsiyonel/nullable alan eklemesidir; TypeScript tarafında mevcut kod derlemeye devam eder.

| Uç | Eklenen | FR |
|---|---|---|
| `POST /questions/generate` isteği | `blueprint_id`, `learning_outcome_id`, `difficulty`, `cell_id` | FR-113 |
| `QuestionOut` | `learning_outcome_id`, `difficulty`, `source_stale: bool` | FR-113, FR-118 |
| `POST /documents` isteği | `replaces_document_id` (multipart alanı) | FR-118 |
| `DocumentOut` | `job`, `supersedes_document_id`, `superseded_at` | FR-213, FR-118 |
| `ExamStartRequest` | `blueprint_id: UUID \| None` | FR-116 |
| `ExamSessionOut` | `exam_version_id`, `exam_blueprint_id`, `attempt_no`, `title` | FR-115 |
| `AnswerFeedbackOut` | `rubric_breakdown: list[RubricScoreOut] \| None` | FR-117 |
| Hata zarfı | `request_id` (§3) | FR-155 |

`POST /exams` iki yeni hata kazanır: **403 `exam_not_open`** (pencere kapalı, FR-116) ve **409 `attempt_limit_reached`** (`max_attempts`, `exam_sessions_attempt_key` tekil indeksinden `IntegrityError → ConflictError`, `exams.py:438-442` deseni).

### 1.9 Sayısal etki

| | Bugün | 002 sonrası (projeksiyon) |
|---|---|---|
| Yol | 25 | **40** (+15) |
| İşlem | 31 | **55** (+24) |

Bu bir tahmindir; bağlayıcı sayı §4'teki export komutunun çıktısıdır ve teslim raporuna oradan yazılır (Anayasa III).

---

## 2. DEĞİŞEN uçlar — sayfalama (FR-160…FR-163)

### 2.1 Etkilenen beş uç ve bugünkü şekilleri

| # | Uç | Kod | Bugünkü yanıt | Bugünkü sıralama |
|---|---|---|---|---|
| 1 | `GET /courses` | `courses.py:30-45` | `CourseWithRole[]` | `Course.created_at DESC` (`:40`) |
| 2 | `GET /courses/{id}/documents` | `documents.py:99-106` | `DocumentOut[]` | `created_at DESC` (`:105`) |
| 3 | `GET /courses/{id}/questions` | `questions.py:120-151` | `QuestionOut[]` | `created_at DESC` (`:145`) |
| 4 | `GET /courses/{id}/chat/sessions` | `chat.py:701-709` | `ChatSessionOut[]` | `updated_at DESC` (`:707`) |
| 5 | `GET /courses/{id}/chat/sessions/{sid}` | `chat.py:712-739` | `ChatMessageOut[]` | `created_at, seq` **ASC** (`:726`) |

Beşinin de bugün `LIMIT`'i yoktur. Beşi de **belirlenimci değildir**: sıralama anahtarları tekil değil (`created_at` bir işlemin tüm satırlarında aynıdır — `0003_chat.sql:84-89` bunu `seq` sütunuyla bir kez öğrenmiş), dolayısıyla eşit anahtarlı satırların sırası bugün tanımsızdır. FR-163 tek başına bile bu beş sorguya dokunmayı gerektiriyor.

### 2.2 Yeni şekil

```python
class PageOut[T](BaseModel):          # Python 3.12, PEP 695 (Teknoloji Kilidi)
    items: list[T]
    next_cursor: str | None = None    # None = son sayfa
```

Sorgu parametreleri her beş uçta **aynı iki isim**: `limit` ve `cursor`.

**`total` alanı BİLEREK YOKTUR.** Her sayfada ikinci bir `COUNT(*)` koşturmak gerekir ve SC-008 tam olarak bunun tersini istiyor: "200 kayıtlık listede ilk sayfa, 20 kayıtlıkla aynı süre aralığında gelsin." `COUNT(*)` bu süreyi liste boyuyla doğrusal yapar. FR-160…163'ün hiçbiri toplam istemiyor.

**`has_more` de yoktur:** `next_cursor === null` zaten "son sayfa" demektir. İki sinyal, ikisinin ayrışabileceği anlamına gelir (Anayasa XI).

**İmleç opak bir metindir**, iki ayrı sorgu parametresi değil: urlsafe base64 (`"<created_at ISO>|<uuid>"`). Sebep sözleşmeseldir — iki parametre verilseydi sıralama anahtarı sözleşmenin parçası olurdu ve ileride sıralamayı değiştirmek kırıcı bir değişikliğe dönerdi. İstemci imleci **üretmez**, yalnız geri gönderir; bozuk imleç → **422 `invalid_cursor`**.

**`limit` kırpılır, reddedilmez.** FR-161 "sunucu kendi üst sınırını **uygular**" diyor, "reddeder" demiyor; ve emsal zaten kodda: `documents.py:137` `.limit(min(limit, 100))`. Daha fazla veri isteyen istemciyi hata ile cezalandırmak yerine verebileceğini veririz. Ayarlar `config.py`'ye `chat_rate_limit_*` (`:230-232`) komşuluğuna girer:

```python
page_size_default: int = 25
page_size_max: int = 100
```

**Sıralama anahtarları (FR-162 + FR-163):**

| Uç | Keyset | Neden |
|---|---|---|
| 1, 2, 3 | `(created_at DESC, id DESC)` | `created_at` tekil değil; `id` son kırıcı |
| 4 | `(updated_at DESC, id DESC)` | Bugünkü sıra korunur |
| 5 | `(created_at DESC, seq DESC, id DESC)` | `seq` tur içi sırayı taşır (`0003_chat.sql:84-89`); `id` yine son kırıcı |

Offset/limit **elendi**: FR-162 eşzamanlı ekleme sırasında kayıt atlamama/tekrarlamama istiyor ve offset bunu yapısal olarak veremez.

**5 numaralı ucun yönü değişir ve bu en büyük davranış farkıdır.** Bugün tüm geçmiş kronolojik artan dönüyor. Yeni davranış: **son `limit` mesaj** döner, sayfa içi sıra yine artandır (yani `fromHistory` tek bir sayfada aynen çalışır), imleç geriye — daha eskiye — yürür. US6 senaryo 4 birebir bunu istiyor ("son mesajlar gelir ve geriye doğru yüklenebilir"). Parametre adı yine `cursor`'dır, `before` değil: tek isim, tek sözlük; yönü ucun belgelenmiş özelliğidir.

### 2.3 Geriye uyumluluk — dürüst cevap

**Tel seviyesinde korunmuyor.** `Course[]` → `PageOut[CourseWithRole]` kırıcı bir değişikliktir ve öyle olduğu yazılır. Değerlendirilen ve **elenen** iki yol:

- *(a) Parametresiz istekte dizi, parametreli istekte zarf.* ELENDİ: aynı ucun iki şekli olur, OpenAPI'de `anyOf` olarak görünür, her istemci dallanmak zorunda kalır. Bu deponun `errors.py:68-75`'te verdiği kararın tersidir — orada iki hata zarfı vardı ve çözüm "istemci ikisini de tanısın" değil, **sunucuda birleştirmek** oldu.
- *(b) Gövde dizi kalsın, imleç `Link` / `X-Total-Count` başlıklarında gitsin.* ELENDİ: `api.ts:82-124` başlıkları hiç okumuyor, dolayısıyla frontend yine değişecek; üstelik CORS'ta `expose_headers` tanımlı değil (`main.py:47-56`) — tarayıcı bu başlıkları çapraz kaynakta okuyamaz bile. Kazanç sıfır, tip güvenliği kaybı gerçek.

Korunan şey **ürün davranışıdır**, üç mekanizmayla:

1. **Atomik commit.** Sözleşme ve `apps/web` aynı commit'te değişir. Emsal yazılı: `tasks.md:225` — "Yeni uç ekleyen her görev sözleşmeyi aynı commit'te günceller — sözleşme ile kod ayrışmaz."
2. **Zarfın tek yerde açılması.** `api.ts`'e `getPage<T>(path, params): Promise<Page<T>>` eklenir; sayfa bileşenleri `.items`'ı bir kez açar. `lib/questions.ts:251,266,285` ve `lib/chat.ts:253` gibi saf fonksiyonlar dizi almaya devam eder ve **hiç değişmez** — kırılma çekirdek mantığa değil, veri çekme sınırına hapsedilir.
3. **Varsayılan 25**, yani küçük derslerde ekran bugünküyle aynı görünür; "devamını yükle" yalnız gerçekten uzun listelerde belirir.

---

## 3. Hata zarfına `request_id` eklenmesinin sözleşme etkisi (FR-155 / SC-007)

### 3.1 Bugün ne var

`main.py:59-74` bir middleware'de `request_id` üretiyor (`X-Request-ID` başlığı varsa onu, yoksa `uuid4().hex`), yanıta `X-Request-ID` başlığı olarak yazıyor ve loga koyuyor. **Gövdeye yazmıyor.** Üç hata işleyicisinin üçü de `Request`'i alıp kullanmıyor (`errors.py:56`, `:105`, `:128` — parametre adı `_`).

### 3.2 Neden başlık tek başına yetmez — ölçülebilir engel

`main.py:47-56`'daki CORS yapılandırmasında **`expose_headers` yoktur.** Tarayıcı çapraz kaynak yanıtlarda yalnız CORS-safelisted başlıkları JavaScript'e açar; `X-Request-ID` bunlardan biri değildir. Frontend `localhost:3000`'den `localhost:8000`'e gidiyor (`config.py:113`), yani **çapraz kaynak** — bugün arayüz bu kimliği okuyamaz. SC-007 "her hata ekranı istek kimliğini gösterir — istisnasız" diyor. Dolayısıyla kimlik **gövdeye** girmek zorundadır. (`expose_headers` ayrıca eklenecek, ama sözleşmenin dayanağı gövdedir.)

### 3.3 Sözleşme değişikliği

```json
{ "error": { "code": "...", "message": "...", "request_id": "3f2a…" } }
```

**Additive ve kırılmaz:** `api.ts:137-146` `errorEnvelope` yalnız `code` ve `message` okur, bilinmeyen anahtarı yok sayar. Eski istemci çalışmaya devam eder.

Üç işleyicinin **üçü de** alanı taşır (`app_error_handler`, `validation_error_handler`, `unhandled_error_handler`) — "istisnasız" ancak böyle sağlanır. Alan **yalnız hata yanıtlarında** vardır; başarı zarflarına eklenmez, çünkü FR-155 hata yanıtlarını hedefliyor ve `ChatResponse` (`schemas/chat.py:159-183`) gibi ürün zarflarına altyapı alanı sokmak onları kirletir. `X-Request-ID` başlığı ise **tüm** yanıtlarda kalır.

**Mekanizma:** middleware `request.state.request_id = request_id` yazar (call_next'ten önce); işleyiciler bugün yok saydıkları `Request`'i kullanır. Contextvar elenmiştir: `request.state` FastAPI'nin bu iş için var olan mekanizmasıdır ve yeni modül gerektirmez.

**Güvenlik kararı — bugünkü davranış değişiyor:** `main.py:60` istemcinin gönderdiği `X-Request-ID`'yi **doğrulamadan** kabul ediyor. Bugün bu yalnız log kirletmeye yarar; kimlik gövdeye girince aynı metin yanıta da yansıyacak. Karar: istemci değeri yalnız `^[A-Za-z0-9_-]{1,64}$` desenine uyuyorsa kabul edilir, aksi hâlde sunucu kendi kimliğini üretir. Fail-closed (Anayasa IV).

### 3.4 `openapi.json`'daki asıl boşluk

Bugün sözleşme dosyası hata zarfını **hiç tarif etmiyor** (§0). `request_id` eklenirken bu da kapanır:

```python
class ErrorBody(BaseModel):
    code: str; message: str; request_id: str
class ErrorEnvelope(BaseModel):
    error: ErrorBody
```

`main.py`'deki her `include_router` çağrısına `responses={400:…, 401:…, 403:…, 404:…, 409:…, 413:…, 422:…, 500:…}` eklenir — **tek dosyada, uç başına tekrarlanmadan** (Anayasa XI). Yan etki: `components.schemas` 48'den 50'ye çıkar ve `HTTPValidationError` artık ölü şemadır (`validation_error_handler` 9 Ağustos'ta onu devre dışı bıraktı, `main.py:81-84`) — sözleşmede kaldığı sürece istemciyi var olmayan bir biçime karşı yazdırır ve `contracts/README.md`'nin "Bilinen istisna" paragrafı da **bayattır**, kaldırılacaktır.

---

## 4. `openapi.json` nasıl yeniden export edilir

**Mevcut komut bulundu:** `specs/001-course-assistant-mvp/contracts/README.md`, "openapi.json nasıl yeniden üretilir" bölümü. Depoda başka bir export betiği, Makefile hedefi ya da CI adımı **yoktur** (`.github/workflows/ci.yml:250` yalnız `curl -sf http://localhost:8000/openapi.json` ile sunucunun ayağa kalktığını yokluyor, sözleşmeyi karşılaştırmıyor).

```bash
cd apps/api
DEV_AUTH_ENABLED=true uv run python -c "
import json
from app.main import create_app
print(json.dumps(create_app().openapi(), ensure_ascii=False, indent=2))
" > ../../specs/001-course-assistant-mvp/contracts/openapi.json
```

`ensure_ascii=False` zorunludur (Türkçe docstring'ler escape edilmemeli); veritabanına bağlanılmaz, yalnız `DEV_AUTH_ENABLED=true` gerekir (`config.py::_check_auth_configuration`).

**Karar 1 — 002 kendi sözleşme dosyasını AÇMAZ; canlı dosya `001/contracts/openapi.json` olarak kalır.** Depo pratiği bu: dosya G2'de 9 uçla donduruldu ama T019/T030/T032/T038'in her biri onu yeniden export etti (`tasks.md:85, 105, 107, 120`) ve bugün 25 yol taşıyor. İkinci bir canlı dosya "hangisi güncel" sorusunu doğurur ve iki dosya sessizce ayrışır (Anayasa XI).

**Karar 2 — 002'nin başında bir kerelik dondurulmuş taban çekilir:**

```bash
cp specs/001-course-assistant-mvp/contracts/openapi.json \
   specs/002-production-hardening/contracts/openapi.baseline.json
```

Bu dosya **bir daha asla yeniden üretilmez**; 001→002 farkı böylece yeniden hesaplanabilir kalır. Yeniden üretilmediği için bayatlayamaz.

**Karar 3 — FR-183'ün otomatik kontrolü CI'a bağlanır** ve `contracts/README.md`'deki `[NEEDS CLARIFICATION: bu export CI'da otomatik diff kontrolüne bağlanacak mı?]` böylece kapanır:

```bash
- name: Sözleşme kodla aynı mı
  working-directory: apps/api
  env: { DEV_AUTH_ENABLED: "true" }
  run: |
    uv run python -c "
    import json
    from app.main import create_app
    print(json.dumps(create_app().openapi(), ensure_ascii=False, indent=2))
    " > /tmp/openapi.json
    diff -u ../../specs/001-course-assistant-mvp/contracts/openapi.json /tmp/openapi.json
```

`diff` sıfırdan farklı dönerse iş kırmızı yanar. `git diff --exit-code` yerine `diff -u` seçildi çünkü çıktı doğrudan **hangi ucun** ayrıştığını gösterir; kırmızı yanan ama neyi söylemeyen bir kapı, geliştiriciyi kapıyı devre dışı bırakmaya iter.

**Aynı commit'te düzeltilecek belge kalemleri (US8):** `contracts/README.md`'nin "9 yol, 13 işlem" başlığı ve uç tablosu; "Planlanan uçlar — HENÜZ YOK" bölümü (chat/exam/questions/analytics'in dördü de **artık var**); iki `[NEEDS CLARIFICATION]`; "Bilinen istisna" paragrafı.

> **Yan bulgu (sözleşme değil, FR-224'ün aynı sınıfı):** `config.py:203` `worker_drain_url` alanını tanımlıyor ama `internal.py:107` hâlâ `os.environ.get("WORKER_DRAIN_URL")` okuyor ve `internal.py:44-50`'deki yorum "Settings alanı değil" diyor — alan eklenmiş, yorum ve okuma yolu geride kalmış. Ayar adı aynı olduğu için davranış bozulmuyor; ama FR-173'ün kapsamına giren bir ayrışmadır.

---

## 5. Kırılma riski tablosu

**A — Sayfalama (§2). Derleme hatası verir; sessiz kırılma değil.**

| # | Kırılan dosya:satır | Nasıl kırılır | Düzeltme |
|---|---|---|---|
| 1 | `apps/web/app/courses/page.tsx:32` | `api.get<Course[]>("/courses")` nesne alır; `courses.map` çalışmaz | `getPage<Course>` + `.items` |
| 2 | `apps/web/app/courses/[courseId]/page.tsx:45` | `CourseDocument[]` → sayfa | `.items` |
| 3 | `apps/web/app/courses/[courseId]/page.tsx:50-52` | `pollWhile: (v) => v.documents.some(...)` — `some` sayfada yok. **En sinsi kalem:** TS yakalar ama düzeltme yanlış yapılırsa polling sessizce durur ve belge durum rozetleri donar | `v.documents.items.some(...)` |
| 4 | `apps/web/app/courses/[courseId]/questions/page.tsx:160` + `:82-83` `PoolData` | `Question[]` → sayfa | `.items`; `topics` (satır 159) **değişmez** — §1.7 kuralı |
| 5 | `apps/web/app/courses/[courseId]/chat/page.tsx:80` | `ChatSessionSummary[]` → sayfa | `.items` |
| 6 | `apps/web/app/courses/[courseId]/chat/page.tsx:112` + `lib/chat.ts:253` `fromHistory` | **Tip + yön birlikte değişir.** Bugün tam geçmiş artan; yeni: son N + geriye imleç. TS yalnız tipi yakalar, **yönü yakalamaz** — düzeltilmezse döküm sessizce eksik açılır | `.items` + eski sayfaları **başa ekleme**; `fromHistory` imzası değişmez |
| 7 | `apps/web/lib/types.ts` (tüm liste tipleri) | Yeni `Page<T>` tipi; mevcut arayüzler korunur | `export interface Page<T> { items: T[]; next_cursor: string \| null }` |
| 8 | `apps/web/lib/api.ts:148-162` | `api.get` yeterli değil (sorgu parametresi + zarf) | `getPage` eklenir; `get` **aynen kalır** |
| 9 | `apps/api/tests/test_courses.py`, `test_documents_api.py`, `test_assessment.py`, `test_chat_api.py`, `test_exams.py`, `test_isolation_layers.py` | `response.json()[0]`, `len(response.json())` iddiaları | `["items"]` eklenir |
| 10 | `apps/api/scripts/fill_answer_cache.py:103` | `for course in response.json()` — dizi bekliyor. **Sessiz kırılma riski en yüksek kalem:** tip denetimi yok, betik `_resolve_course` `None` döner ve önbellek doldurma sebepsizce boş çıkar | `response.json()["items"]` |
| 11 | `apps/web/e2e/flows.spec.ts:211` | `apiGet<BelgeOzeti[]>(".../documents")` | `.items` |
| 12 | `apps/api/scripts/measure_latency.py:94,194` | **Kırılmaz** — yalnız `POST /chat` kullanıyor | — |

**B — Sınav kilidi (US1). En tehlikeli sınıf: kırılma bir hata gibi görünmez, ürünün arızası gibi görünür.**

| # | Dosya:satır | Risk | Karşı önlem |
|---|---|---|---|
| 13 | `apps/web/app/courses/[courseId]/chat/page.tsx:80` | Kilitliyken `GET /chat/sessions` **403** döner. Sayfa `availability`'yi okumadan liste hatasına düşerse kullanıcı kilidi bir arıza sanar | Sayfa kilit kontrolünü liste hatasından **önce** değerlendirir (bağlayıcı sıra) |
| 14 | `apps/web/components/course-nav.tsx:17-24` (`TABS`) | Sekme kilitli çizilmezse spec senaryo 5 karşılanmaz | `locksWithAssistant` bayrağı; `<span aria-disabled>` + "Kilitli" metni (renk tek başına bilgi taşımaz, Anayasa VII) |
| 15 | Frontend'in genel 401/403 işlemesi (FR-171 oturum tazeleme) | "403 görünce girişe at" kuralı yazılırsa kilit kullanıcıyı **girişe fırlatır** | Yönlendirme kararı `error.code`'a bakar, yalnız HTTP durumuna değil |

**C — request_id (§3). Kırılmaz.**

| # | Dosya:satır | Etki |
|---|---|---|
| 16 | `apps/web/lib/api.ts:67-75` `ApiError` | `requestId` alanı eklenir; mevcut `catch` blokları etkilenmez |
| 17 | `apps/web/lib/errors.ts:5-9` `errorMessage` | **Değişmez.** Kimlik mesajın içine gömülmez, ayrı alan olarak taşınır |
| 18 | `apps/web/lib/errors.test.ts`, `chat.test.ts`, `questions.test.ts` fixture'ları | Yeni alan opsiyonel; testler geçmeye devam eder |

**D — Politika ve blueprint (§1.3, §1.4). Yeni hata kodları; mevcut kod derlenmeye devam eder ama davranış eksik kalır.**

| # | Dosya:satır | Risk |
|---|---|---|
| 19 | `apps/web/app/courses/[courseId]/chat/page.tsx` `sendError` yolu | 403 `mode_not_allowed` ve 429 `course_budget_exhausted` backend metniyle görünür (`errors.ts` sayesinde otomatik), ama **mod seçici** kapalı modu göstermeye devam eder → etkin görünüp iş yapmayan kontrol (Anayasa XI ihlali). `availability.allowed_modes` okunmalı |
| 20 | `apps/web/lib/exam.ts:283-292` (ipucu düğmesi) | 409 `hint_limit_reached` yeni; düğme sınır dolunca gizlenmeli |
| 21 | `apps/web/app/courses/[courseId]/questions/page.tsx` | `source_stale` işareti (FR-118) gösterilmezse veri gelir, ekran yok sayar — **sessiz** |

**E — Migration olmadan çalışmayacak sözleşme kalemleri (uç yazılmadan önce kapanmalı)**

| # | Kalem | Engel |
|---|---|---|
| 22 | `DELETE /chat/sessions/{id}` | `chat_sessions` üzerinde **DELETE politikası yok** (`0003_chat.sql:171-183`); RLS altında sessizce 0 satır siler ve uç 204 dönerek başarılı görünür |
| 23 | `POST /me/deletion-request` | Talep tablosu tanımlanmadı (veri modeli §8 açık sorusu) |
| 24 | Blueprint uçlarının tamamı | `0008_exam_blueprint.sql` yazılmadı |
| 25 | `PUT /ai-policy` | `0009_course_ai_policy.sql` yazılmadı |