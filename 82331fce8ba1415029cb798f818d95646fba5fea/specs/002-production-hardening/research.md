# Faz 0: Araştırma — 002 Production Sertleştirme

**Üretim tarihi**: 2026-08-09
**Yöntem**: beş bağımsız ajan, her biri kendi karar alanını mevcut kodu okuyarak çözdü. Her karar dosya:satır kanıtına bağlıdır ve elenen seçenekler eleme gerekçesiyle yazılıdır.

> **Hikâye numaraları hakkında**: bu araştırma, `spec.md`'nin hikâyeleri yeniden numaralanmadan önce koştu.
> Aşağıdaki metinlerde geçen "User Story N" ifadeleri **FR numaralarına** göre okunmalıdır — FR numaraları
> sabittir, hikâye numaraları bir kez kaydı. Güncel eşleme: FR-101..106 → US1 · FR-220..224 → US2 ·
> FR-110..119 → US3 · FR-130..137 → US4 · FR-150..156 → US5 · FR-160..163 → US6 · FR-170..173 → US7 ·
> FR-180..183 → US8 · FR-190..192 → US9 · FR-200..203 → US10 · FR-213..215 → US11.

---

## Sınav oturumu kilidi (002, User Story 1 / FR-101..FR-106)

### 1. Kilit kontrolü nereye girecek: dependency (deps.py) mi, uç gövdesi (chat.py) mi?

**Karar**: deps.py'ye YENİ bir katmanlı bağımlılık olarak girecek: `async def require_assistant_unlocked(context: CourseMemberDep, session: SessionDep, settings: SettingsDep) -> CourseContext` ve onun `UnlockedCourseMemberDep = Annotated[CourseContext, Depends(require_assistant_unlocked)]` takması. chat.py'deki ÜÇ uç da (`post_chat` 561-567, `list_sessions` 701-702, `list_messages` 712-715) `CourseMemberDep` yerine `UnlockedCourseMemberDep` alacak. Router seviyesinde `APIRouter(dependencies=[...])` KULLANILMAYACAK. Uç gövdesine inline `if` yazılmayacak.

**Gerekçe**: 1) Desen zaten var: deps.py:118-124 `require_course_instructor(context: CourseMemberDep)` + `CourseInstructorDep`, yani "CourseMemberDep üstüne bir yetki katmanı bindir ve bağlamı geri döndür" bu depoda kurulu tek desen; kilit onun ikizidir. 2) Kilit moddan bağımsızdır (FR-102). Gövdeye yazılırsa `payload.mode` elin altındadır ve ilk itirazda moda bağlı bir istisna eklemek bir satırlık iş olur; bağımlılıkta gövde modu GÖREMEZ, mod bağımsızlığı yapısal olur. 3) Kapsam POST ile sınırlı değil: `list_messages` (chat.py:712-739) geçmiş turların kaynaklı cevap metnini ve atıflarını aynen döndürür, yani sınav sırasında açılan ikinci sekmede okunabilen bir yardım yüzeyidir; gövdeye yazılan kontrol yalnız POST'u kapatır, bağımlılık üçünü birden kapatır. 4) Sıra: bağımlılık gövdeden ÖNCE koşar, yani kilit hız sınırlayıcıdan (chat.py:589-594) önce karar verir. Bu doğru sıradır çünkü sınırlayıcının gerekçesi LLM bütçesidir (chat.py:126-131) ve kilitli istek zaten LLM'e hiç gitmez; ayrıca üyelik SELECT'i de (deps.py:107) bugün sınırlayıcıdan önce koşuyor, yani "ucuz DB kontrolü sayaçtan önce" mevcut düzendir. 5) Hata haritalaması hazır: deps.py bugün de AppError fırlatıyor (deps.py:33, 111) ve tek zarfa dönüşüyor (errors.py:57-62); bağımlılıkta fırlatılan hata için ek bir şey gerekmez.

**Elenen seçenekler**: (a) `require_course_member`'ın kendisine gömmek — ELENDİ: aynı bağımlılığı sınav uçları da kullanıyor (exams.py:275, 366, 385), sınav süren öğrenci kendi sınavına cevap veremez hâle gelirdi. (b) `post_chat` gövdesine `if` — ELENDİ: yalnız POST'u kapatır, geçmiş okuma yüzeyi açık kalır ve kural chat.py'de üç kez hatırlanmak zorunda kalır (Anayasa XI). (c) Router seviyesinde `dependencies=[...]` — ELENDİ: kilit durumunu bildiren `GET /chat/availability` ucu (Karar 5) aynı router'da yaşayacak ve router bağımlılığı onu KENDİ kilidiyle kapatırdı; ayrıca dönüş değeri enjekte edilemediği için uçlar `CourseMemberDep`'i ikinci kez yazmak zorunda kalırdı.

**Dokunulacak dosyalar**:
- `apps/api/app/api/deps.py`
- `apps/api/app/api/chat.py`

**Risk**: İleride chat router'ına eklenen dördüncü bir uç `CourseMemberDep` yazıp kilidi atlar. Karşı önlem: annotation adı `UnlockedCourseMemberDep` olarak bilerek göze batıcı seçiliyor ve testlerden biri (Karar 6, test 7) geçmiş okuma ucunu da 403 bekliyor; yeni uç eklendiğinde aynı testin yanına satır eklenmesi gözden kaçarsa kilit sessizce delinir.

---

### 2. "Yürüyen sınav oturumu" sorgusu tam olarak nasıl yazılacak ve exams.py'deki effective_expiry/db_now nasıl paylaşılacak?

**Karar**: İki ayrı taşıma + tek yeni fonksiyon. (1) `db_now` (exams.py:78-88) `app/core/db.py`'ye taşınacak — jenerik işlem saati, oturum semantiğinin sahibi orası (db.py:1-6). (2) `effective_expiry` (exams.py:90-98) ve `_remaining_seconds` (exams.py:100-103) yeni `app/modules/assessment/exam_state.py`'ye taşınacak (`remaining_seconds` adıyla, artık modül dışına açıldığı için alt çizgisiz). exams.py bunları import edip kendi kopyalarını SİLECEK; exams.py docstring'indeki üç zaman kuralının 2. maddesi (exams.py:20-26, kırpma gerekçesi) kodla birlikte yeni modüle taşınacak, exams.py'de yalnız işaret kalacak. (3) Aynı modülde tek sorgu:

```python
async def active_exam_session(session, *, user_id, course_id, now, settings) -> ExamSession | None:
    rows = await session.execute(
        select(ExamSession).where(
            ExamSession.user_id == user_id,
            ExamSession.course_id == course_id,
            ExamSession.mode == ExamMode.EXAM,
            ExamSession.finished_at.is_(None),
            ExamSession.expires_at > now,
        ).order_by(ExamSession.started_at.desc())
    )
    for exam in rows.scalars():
        expiry = effective_expiry(exam, settings=settings)
        if expiry is not None and now < expiry:
            return exam
    return None
```

Kırpma kuralı SQL'e YAZILMAYACAK: `expires_at > now` yalnız bir daraltma yüklemidir (min'in iki argümanından biri, dolayısıyla `min(...) > now`un gerekli koşulu), nihai kararı Python'daki `effective_expiry` verir. deps.py modülü `from app.modules.assessment import exam_state` biçiminde import edip `exam_state.active_exam_session(...)` diye çağıracak (chat.py:74 + 609'daki `socratic` deseni) — hem testin tek attribute'u monkeypatch'leyebilmesi için, hem de bağlanmış isim kopyası bırakmamak için.

**Gerekçe**: Anayasa XI'in gerekçesi satır tasarrufu değil ayrışma: kırpma kuralını (`min(expires_at, started_at + süre)`) bir de SQL'de `func.least(...)` diye yazmak, aynı ürün kararını İKİ DİLDE tutmak olurdu ve `exam_duration_minutes` değiştiğinde ya da kural sıkılaştığında ikisinden biri geride kalırdı — üstelik sessizce, çünkü SQL tarafı gevşek kalırsa kilit fail-open olur. Katmanlama temiz: `app/modules/*` bugün `app/api/*`'ye hiç bağlı değil (grading.py:44-54 yalnız core/models/schemas import ediyor), tersine bağımlılık ise mevcut (exams.py:43 deps'i import ediyor), dolayısıyla ortak modülü modules/assessment altına koymak döngüsel import riskini tamamen ortadan kaldırır — deps.py'nin exams.py'yi import etmesi doğrudan döngü olurdu. `db_now`un assessment'a değil core/db'ye gitmesinin sebebi: FR-116'nın yayın penceresi ve FR-162'nin sayfalama imleci de "işlemin veritabanı saatine" ihtiyaç duyacak; onları bir sınav modülünden saat almaya zorlamak, ikinci bir kopya yazılmasının en kısa yoludur. RLS ile uygulama katmanı burada da bağımsız olarak doğru: `exam_sessions_self_read` (0004_assessment.sql:182-185) eğitmene dersin TÜM oturumlarını açar, bu yüzden `user_id == context.user_id` yüklemi RLS'e bırakılmıyor, açıkça yazılıyor (Anayasa II).

**Elenen seçenekler**: (a) `effective_expiry`i exams.py'de bırakıp deps.py'den import etmek — ELENDİ: `app/api/deps.py` → `app/api/exams.py` → `app/api/deps.py` döngüsü. (b) Kırpmayı SQL'de `func.least(expires_at, started_at + make_interval(...)) > now` ile yapıp tek sorguda bitirmek — ELENDİ: kural ikinci kez yazılır (Anayasa XI) ve SQL tarafı gevşek kalırsa kilit fail-open olur (Anayasa IV'ün tersi). (c) `started_at > now - süre` ek daraltması — ELENDİ: aday satır sayısını azaltırdı ama kırpma kuralının SQL'e sızmış hâlidir; ayarla ayrışırsa aktif oturumu eleyip fail-open üretir. (d) Ortak modülü `app/core/`'a koymak — ELENDİ: core jenerik altyapıdır (config, db, errors, security, logging); sınav kuralı ürün mantığıdır ve modules/assessment onun evi.

**Dokunulacak dosyalar**:
- `apps/api/app/modules/assessment/exam_state.py`
- `apps/api/app/core/db.py`
- `apps/api/app/api/exams.py`
- `apps/api/app/api/deps.py`

**Risk**: Aday satır kümesi büyüyebilir: `start_exam` (exams.py:273-324) aynı öğrenci için ikinci bir aktif oturum açmayı ENGELLEMİYOR ve terk edilen oturum `finished_at IS NULL` olarak kalıcı duruyor. `expires_at > now` yüklemi bunları doğal olarak eleyince küme pratikte 0-1 satır; ama süre uzatılırsa (ayar) ya da ileride uzun süreli sınav eklenirse döngü birkaç satır dönmeye başlar. Kırılma biçimi performans değil davranış: eş zamanlı iki aktif oturumda `started_at DESC` ile ilk bulunanı döndürmek, mesajda hangi oturumun gösterileceğini belirsizleştirir.

---

### 3. Öğretmen muafiyeti nasıl belirlenecek — CourseContext'te rol var mı?

**Karar**: Var ve doğrudan kullanılacak: `CourseContext.role` (deps.py:81) + `is_instructor` property (deps.py:84-86). Muafiyet kilidin İLK satırı olacak: `if context.is_instructor: return context` — sorgu bile koşmayacak. `MembershipRole` yalnız INSTRUCTOR/STUDENT taşıyor (models/core.py:29-31), dolayısıyla "eğitmen değilse öğrencidir" bugün tam bir ayrım; kural yine de "eğitmen muaf" biçiminde yazılacak, "öğrenciye uygula" biçiminde değil.

**Gerekçe**: FR-103 ve Edge Case (spec.md:211) kilidi "değerlendirilen kişi"ye bağlıyor; rol bilgisi zaten sunucuda doğrulanmış hâlde bağlamda duruyor (deps.py:107-112, üyelik tablosundan) ve istemciden gelmiyor. Erken dönüş ölçülebilir bir kazanç da sağlıyor: eğitmen her sohbet isteğinde bir SELECT ödemez. Kuralı olumsuz yazmamanın sebebi ileriye dönük: 002 sonrası rol eklenirse (asistan/gözlemci) "eğitmen değil → kilitle" fail-closed kalır, "öğrenci ise kilitle" ise yeni rolü sessizce muaf yapardı (Anayasa IV).

**Elenen seçenekler**: (a) Rolü `exam_state` sorgusunun içine `OR is_instructor` olarak gömmek — ELENDİ: muafiyet bir yetki kararıdır, sorgu değil; deps.py'de kalması onu diğer yetki kararlarıyla aynı yerde tutar. (b) Frontend'de rol bakıp isteği hiç göndermemek — ELENDİ: FR-105/Anayasa II, arayüzdeki gizleme sunucu kararının yerine geçmez; ayrıca localStorage'daki rol yetki belgesi değildir (session.ts:16-17).

**Dokunulacak dosyalar**:
- `apps/api/app/api/deps.py`

**Risk**: Eğitmen kendi dersinde sınav provası başlatıp asistanı kullanabilir; bu bilinçli (spec.md:211) ama demo sırasında "kilit çalışmıyor" gibi görünebilir. Testte (Karar 6, test 5) bu davranış açıkça iddia edilerek belgeleniyor.

---

### 4. Hata tipi ne olacak, hangi HTTP kodu, Türkçe metin ne?

**Karar**: `exam_state.py` içinde `class ExamLockedError(AppError): status_code = status.HTTP_403_FORBIDDEN; code = "exam_in_progress"`. Metin de aynı modülde tek sabit olacak:

`EXAM_LOCK_MESSAGE = "Şu anda süren bir sınav oturumun var. Sınav bitene ya da süresi dolana kadar asistanı kullanamazsın. Sınavı bitirince buradan devam edebilirsin."`

`code` string'i de tek sabitte (`EXAM_LOCK_REASON = "exam_in_progress"`) yaşayacak ve İKİ yüzeyde birden kullanılacak: 403 zarfının `error.code`'u ve `GET /chat/availability`'nin `reason` alanı.

**Gerekçe**: 403 seçimi: en yakın emsal exams.py:490-493 ve 408-409 — "bu yüzey şu anda sana kapalı" kararı zaten `PermissionDeniedError` (403) ile veriliyor. 404 ELENMELİ çünkü bu depoda 404 varlık gizlemek için ayrılmış (deps.py:110-111) ve burada gizlenecek bir şey yok: öğrenci sınavının açık olduğunu zaten biliyor. 422 (chat.py:582-588'in `mode=exam` reddi) farklı bir doğa: orada istek biçimi kabul edilmiyor, burada istek geçerli ama durum kapalı. 409 cazip ama FR-153 ile çakışıyor: arayüz kalıcı hatada "Tekrar dene" göstermemeli ve 403 zaten kalıcı sınıfında; 409 exams.py'de "tekrar denenebilir olmayan ama kullanıcı eylemiyle çözülen" durumlar için kullanılıyor (exams.py:399, 417) ve karışırdı. Ayrı bir `code` şart: frontend'in bunu genel yetki hatasından ayırt etmesi gerekiyor (FR-105 kilitli yüzey). Sınıfın modules/ altında yaşaması emsalli: `EmbeddingSpaceMismatchError` (modules/retrieval/dense.py:114), `LlmUnavailableError` (modules/generation/llm.py:62) — alan hataları core/errors.py'ye değil kuralın yanına yazılıyor; core/errors.py taşıma seviyesi hiyerarşi olarak kalıyor. Metnin sesi "sen"li: sohbet yüzeyinin mevcut sesi bu (chat.py:236-238, 594), sınav yüzeyi ise "siz"li (exams.py:492); hata sohbet ucundan döndüğü için sohbetin sesi kazanıyor. Metinde em dash yok, uppercase yok, ham teknik terim yok (Anayasa V).

**Elenen seçenekler**: (a) `raise PermissionDeniedError(msg, code="exam_in_progress")` — AppError.__init__ bunu destekliyor (errors.py:20-24) ama depoda tek bir kullanımı yok; alt sınıf yazmak chat.py:104-119'un kurulu deseni. ELENDİ (emsalsizlik). (b) core/errors.py'ye eklemek — ELENDİ: o dosya jenerik HTTP hiyerarşisi, alan bilgisi taşımıyor. (c) Reddi 200 + `status: "exam_locked"` gövdesiyle döndürmek (abstention gibi) — ELENDİ: abstention "cevap veremiyorum" der ve ürünün çalıştığının kanıtıdır (chat.py:570-572); kilit ise "bu isteği işlemedim"dir, istek kaydı ve arayüz davranışı farklı olmalı.

**Dokunulacak dosyalar**:
- `apps/api/app/modules/assessment/exam_state.py`
- `apps/api/app/api/deps.py`

**Risk**: 403'ün frontend'de mevcut genel 401/403 işleyişine (US6 FR-171 oturum tazeleme) çarpması: ileride "403 görünce oturumu tazele/girişe at" kuralı yazılırsa kilit, kullanıcıyı girişe fırlatır. Karşı önlem: yönlendirme kararı `code`'a bakmalı, yalnız HTTP durumuna değil.

---

### 5. Arayüz tarafı: course-nav.tsx sekmeyi nasıl kilitleyecek, kilit durumunu hangi uçtan öğrenecek?

**Karar**: YENİ uç: `GET /courses/{course_id}/chat/availability`, chat router'ında (chat.py), ve bilerek `CourseMemberDep` ile — kilitliyken de cevap verebilmeli. Zarf `app/schemas/chat.py`'de tanımlanacak (chat.py:24-36'daki sözleşme sahipliği kuralı: zarflar router'da değil schemas/chat.py'de yaşar): `class ChatAvailabilityOut(BaseModel): available: bool; reason: str | None; message: str | None`. Uç, deps'in kullandığı AYNI `exam_state.active_exam_session`i çağırır ve aynı `EXAM_LOCK_REASON`/`EXAM_LOCK_MESSAGE` sabitlerini döndürür. Eğitmene her zaman `available: true` döner, yani muafiyet kuralı istemcide tekrarlanmaz.
Arayüz: yeni `apps/web/lib/chat-availability.ts` → `useChatAvailability(courseId)`, içi `useResource(fetcher, [courseId], { pollWhile: (s) => !s.available, intervalMs: 30_000 })`. Bileşen depoya/uca doğrudan dokunmaz, kancayı okur — `course-nav.tsx:8-10`'un `useSession()` için yazdığı kuralın aynısı. `course-nav.tsx` TABS tablosuna (17-24) `locksWithAssistant: true` bayrağı eklenir (mevcut `instructorOnly` bayrağının simetriği), kilitli sekme `Link` yerine `<span aria-disabled="true">` olarak çizilir, yanında "Kilitli" metni/rozeti (renk tek başına bilgi taşımaz, Anayasa VII) ve şeridin altına sunucunun `message`'ı satır olarak yazılır. `/courses/[courseId]/chat/page.tsx` aynı kancayı okuyup kilitliyken besteciyi hiç çizmez; yarış hâlinde (başka sekmede sınav başladı) POST'tan dönen 403 mevcut `sendError` + `errorMessage(e)` yolundan zaten backend metniyle görünür (errors.ts:5-9: arayüz kendi hata metnini uydurmaz).

**Gerekçe**: Nav'ın kilit durumunu öğrenebileceği başka bir uç yok: nav bugün hiç veri çekmiyor (course-nav.tsx:26-30). `GET /courses/{id}/exams` (exams.py:327-360) teorik olarak yeterli veriyi taşıyor ama iki nedenle uygun değil: (i) "yürüyen sınav" kuralı (`mode==exam && !expired && finished_at===null`) TypeScript'te ikinci kez yazılmış olurdu ve sunucu kuralıyla ayrışırdı — FR-105'in özü arayüzün sunucu kararını AYNALAMASI, yeniden türetmesi değil; (ii) liste ucu oturum başına ayrı bir `_answers_of` sorgusu koşuyor (exams.py:230-232, 357-360), yani nav'ı altı sayfada N+1 sorguya bağlardı (Anayasa XI: gereksiz iş kusurdur). Ayrı uç ayrıca US3'ün (FR-130/FR-135, "ders politikası tüm modları kapatırsa asistan sekmesi tamamen kapanır") ihtiyaç duyacağı yüzeyin aynısı: `available/reason/message` üçlüsü ikinci bir sebeple genişletilebilir, ikinci bir uç gerekmez. Alan adı `available` (locked değil) bilinçli: yanıt okunamaz/eksikse falsy kalır ve kilitli tarafa düşer (Anayasa IV). `pollWhile` kancanın mevcut sözleşmesi (use-resource.ts:263-271) ve kilit kalkınca kendiliğinden duruyor — durdurulmayan polling yok.

**Elenen seçenekler**: (a) Sekmeyi hiç çizmemek — ELENDİ: lib/exam.ts:283-292 ipucu düğmesi için "hiç render etme" diyor ama o bir eylem düğmesi; sekme şeridi dersin haritasıdır ve sekmenin kaybolması "özellik gitti" der. Spec scenario 5 açıkça "kilitli görünür ve nedeni yazar" diyor. (b) Sekmeyi etkin bırakıp sohbet sayfasında duvara çarptırmak — ELENDİ: aynı senaryo "arayüz kullanıcıyı duvara koşturmaz" diyor. (c) Kilit durumunu `GET /courses/{id}` (courses.py:74) yanıtına alan olarak eklemek — ELENDİ: o uç dersin kimliğini anlatıyor; sohbet yüzeyinin durumunu oraya asmak dersi her okuyan istekte sınav sorgusu koşturur. (d) `unlocks_in_seconds` alanı eklemek ve tek zamanlayıcıyla yeniden sormak — ELENDİ (şimdilik): kullanılmayan alan ölü yüzeydir; 30 sn'lik kendini durduran yoklama yeterli.

**Dokunulacak dosyalar**:
- `apps/api/app/api/chat.py`
- `apps/api/app/schemas/chat.py`
- `apps/web/lib/chat-availability.ts`
- `apps/web/lib/types.ts`
- `apps/web/components/course-nav.tsx`
- `apps/web/app/courses/[courseId]/chat/page.tsx`

**Risk**: Bayatlık penceresi: öğrenci sınavı bitirdiğinde nav en fazla 30 saniye kilitli kalır (sınav sayfası ile nav arasında olay bağı yok). Kullanıcıya "bitirdim ama hâlâ kilitli" gibi görünür. İkinci kırılma: kilitliyken `GET /chat/sessions` 403 döndüğü için sohbet sayfası kancayı okumadan önce ekranı kapatan hataya düşerse, kullanıcı kilidi bir arıza gibi görür — sayfanın kilit kontrolünü liste hatasından ÖNCE değerlendirmesi şart.

---

### 6. FR-106 mutasyon testi nasıl yazılacak — kilit kaldırıldığında kırmızı yanan test?

**Karar**: Yeni dosya `apps/api/tests/test_exam_lock.py`, kurulum `tests/test_exams.py`'den (build_course, start, rewind) ve hat sahtesi `tests/test_chat_api.py`'den (Pipeline fixture) devşirilerek — iki kopya kurulum yazılmayacak (test_exams.py:12-14'ün kendi kuralı). Sekiz iddia:
1. exam oturumu yürürken `POST /chat` (qa) → 403, `error.code == "exam_in_progress"` (FR-101).
2. Aynı durumda `mode=socratic` → 403 (FR-102).
3. `rewind(admin_engine, sid, minutes=EXAM_DURATION+1)` sonrası aynı istek → 200 ve `status == "answered"` (FR-104).
4. `practice` oturumu açıkken → 200 (senaryo 4).
5. Eğitmen kendi dersinde yürüyen exam oturumuyla → 200 (FR-103).
6. `POST /exams/{id}/finish` sonrası → 200 (spec Independent Test).
7. Kilitliyken `GET /chat/sessions` ve `GET /chat/sessions/{id}` → 403 (ikinci sekme yolu).
8. **Karşı kontrol (FR-106'nın kendisi):** `monkeypatch.setattr(exam_state, "active_exam_session", _hep_none)` ile kilit devre dışı bırakılır ve test 1'in AYNI kurulumu tekrarlanır; sonuç 200 + kaynaklı cevap olmalıdır.
Ayrıca `apps/web/lib/chat-availability.test.ts`'te saf karar (available=false → sekme kilitli, mesaj sunucudan) sınanır.

**Gerekçe**: FR-106'nın harfi ("kilit kodu kaldırıldığında kırmızı yanar") 1-7 ile zaten sağlanır; ruhu 8 olmadan sağlanmaz. Sebep somut: 1 numaralı testin kurulumunda sahte hat yanlış bağlanmışsa, retrieval boş dönerse ya da hız sınırlayıcı sızmışsa istek zaten cevap üretmez; o zaman "yardım verilmedi" iddiası kilit silinse bile yeşil kalabilecek bir kurulumun üzerine oturur. 8 numaralı test, aynı fikstürün kilit yokken GERÇEKTEN cevap ürettiğini gösterip 403'ün sebebini kilide çiviler. Bu tam olarak deponun kurulu yöntemi: test_isolation_layers.py:64-75 aynı gerekçeyi yazıyor ("Bu iddia olmadan aşağıdaki testin 'RLS gerçekten kapalıydı' varsayımı doğrulanmamış kalırdı") ve ikinci katmanı bilerek kapatarak (rls_kapali fixture, 30-46) ölçüyor. Mekanik ayrıntı bağlayıcı: `client` fixture'ı app nesnesini dışarı vermiyor (conftest.py:133-142), dolayısıyla `dependency_overrides` yolu ek fixture ister; ayrıca `Annotated[..., Depends(require_assistant_unlocked)]` referansı rota tanımlanırken bağlandığı için bağımlılık fonksiyonunun adını sonradan patch'lemek ETKİSİZDİR. Bu yüzden deps.py'nin çağrıyı modül üzerinden yapması (Karar 2) bir test gereksinimidir, stil tercihi değil. Süre bekleme yok: `rewind` (test_exams.py:146-156) sütunları sahip bağlantısıyla geriye alıyor ve karşılaştırma zaten DB saatine göre.

**Elenen seçenekler**: (a) Yalnız 1-7'yi yazmak — ELENDİ: yukarıdaki "yanlış sebeple yeşil" riski. (b) Gerçek mutasyon aracı (mutmut/cosmic-ray) kurmak — ELENDİ: yeni bağımlılık, Teknoloji Kilidi ve 17 Ağustos takvimi; ayrıca depo bu kanıtı elle yazılmış karşı kontrolle üretiyor. (c) `app.dependency_overrides` ile kilidi söküp koşmak — ELENDİ: conftest app'i sızdırmıyor, yeni fixture ve daha kırılgan kurulum ister; monkeypatch tek satır. (d) Testi test_chat_api.py'ye eklemek — ELENDİ: o dosyanın autouse `pipeline` fixture'ı var ve sınav fikstürleri test_exams.py'de; ayrı dosya ikisini de import edip ikisine de bağlı kalmayı açık ediyor.

**Dokunulacak dosyalar**:
- `apps/api/tests/test_exam_lock.py`
- `apps/web/lib/chat-availability.test.ts`

**Risk**: 8 numaralı testin monkeypatch'i yanlış modüle uygulanırsa (deps.py `from ... import active_exam_session` yaparsa) test sessizce 403 alır ve "kilit kaldırılamadı" durumu "kilit çalışıyor" gibi okunur — yani karşı kontrol kendi kendini yalanlar. Bu yüzden 8, 200 BEKLEYEN bir iddia olmalı; 403 beklerse hiçbir şey kanıtlamaz.

---

### 7. Ek sorgu maliyeti: her sohbet isteğine bir SELECT ekleniyor. Ölçülmüş mü, kabul edilebilir mi, indeks gerekli mi?

**Karar**: ÖLÇÜLMEDİ ve rapora "ölçülmedi" diye yazılacak (Anayasa III). Yeni indeks EKLENMEYECEK: mevcut `exam_sessions_user_idx ON exam_sessions (user_id, started_at DESC)` (0004_assessment.sql:94) sorgunun öncü yüklemini ve sıralamasını karşılıyor; `course_id`, `mode`, `finished_at`, `expires_at` kalan birkaç satırda filtreleniyor. Ölçüm yöntemi teslim öncesi koşulacak ve raporlanacak: (a) test veritabanında `EXPLAIN (ANALYZE, BUFFERS)` ile plan ve satır sayısı; (b) uçtan uca p50/p95 farkı, `request_logs.latency_ms` üzerinden (chat.py:659-685 zaten her sohbet turunu yazıyor) — kilit öncesi/sonrası aynı fikstürle. Eşik aşılırsa doğru düzeltme kısmi indekstir: `CREATE INDEX exam_sessions_active_idx ON exam_sessions (user_id, course_id) WHERE finished_at IS NULL` — ama ölçüm göstermeden eklenmeyecek.

**Gerekçe**: Sorgu bir noktadan okuma: aday küme "bu öğrencinin bu derste bitmemiş ve saklı bitişi henüz gelmemiş exam oturumları" ve 20 dakikalık süreyle bu pratikte 0-1 satır. Bağlam da bunu destekliyor: istek zaten kimlik/üyelik SELECT'i (deps.py:92-99), sohbet oturumu yüklemesi, önbellek araması (chat.py:823-834) ve ardından hibrit retrieval + LLM çağrısı yapıyor; ölçülmüş sayı elde var (ilk soru 11,7 sn — spec.md:89) ve indeksli bir nokta okuması bunun yanında gürültü. Ama "gürültü" bir tahmindir, bu yüzden iddia olarak yazılmayacak. İndeks eklememenin gerekçesi Anayasa XI'in son paragrafı: "yavaş olabilir" gerekçesiyle karmaşıklık eklenmez, optimizasyon ölçülerek yapılır. Not: sorgu üç sohbet ucuna + `GET /chat/availability`'ye giriyor ve availability nav'la birlikte altı ders sayfasında koşuyor, yani ders sayfası başına +1 SELECT; asıl izlenmesi gereken sayı bu, sohbet turundaki değil.

**Elenen seçenekler**: (a) Kilidi istek başına önbelleğe almak / süreç içi TTL cache — ELENDİ: kilidin kalkma anı sunucu saatine bağlı ve cache bayatlığı fail-open üretir (Anayasa IV); ayrıca ölçülmemiş bir sorun için karmaşıklık. (b) Kilit bilgisini JWT'ye/oturuma gömmek — ELENDİ: sınav istekten sonra başlayabilir, token bayatlar. (c) Kısmi indeksi şimdi eklemek — ELENDİ: ölçüm yok; migration eklemek 0008 açar ve teslim paketine ölçülmemiş bir iddia daha sokar.

**Dokunulacak dosyalar**:
- `apps/api/app/modules/assessment/exam_state.py`
- `docs/test-report.md`
- `ARCHITECTURE.md`

**Risk**: Terk edilmiş oturumlar birikirse (start_exam aktif oturum sınırı koymuyor, exams.py:273-324) `finished_at IS NULL` kümesi büyür; `expires_at > now` bunu bugün eliyor ama `expires_at` doğrudan DB erişimiyle ileri atılırsa (exams.py:22-26'nın kabul ettiği tehdit) hem aday kümesi hem tarama büyür. Ölçüm yapılmadan teslim edilirse US7'nin (belge doğruluğu) ihlali olur: raporda sayı görünürse ve ölçülmemişse SC-009 düşer.

---

### 8. Kilit ders bazlı mı, kullanıcı bazlı mı (A dersinde sınav, B dersinde sohbet)?

**Karar**: DERS BAZLI. Sorgu `course_id == context.course_id` yüklemini taşıyacak; A dersinde sınav veren öğrenci B dersinin asistanını kullanabilecek. Bu karar spec.md'de açıkça yazılı olmadığı için `ARCHITECTURE.md`'nin mod politikaları tablosuna (336-340) eklenecek yeni satırda gerekçesiyle birlikte yazılacak ve 002 şartnamesine bir cümlelik açıklama olarak geri işlenecek.

**Gerekçe**: Asistan zaten dersin materyaliyle sınırlı (Anayasa I; retrieval `course_id` ile çağrılıyor, chat.py:471-473), yani B dersinin asistanı A dersinin sınav sorusuna kaynak bulamaz ve kaynak yoksa cevap vermez — kopya yüzeyi aynı ders içindedir. Kullanıcı bazlı kilit ise ilgisiz bir dersi cezalandırır ve ürünün ölçülemeyen bir iddiasını doğurur ("öğrenci sınavdayken hiçbir ders çalışamaz"). Ayrıca uç zaten ders kapsamlı (`/courses/{course_id}/chat`) ve `CourseContext` ders bazlı; kullanıcı bazlı kilit, bağlamda olmayan bir bilgiyi (kullanıcının TÜM dersleri) çekmeyi ve RLS'in ders sınırının dışına çıkmayı gerektirirdi.

**Elenen seçenekler**: (a) Kullanıcı bazlı (tüm dersler) kilit — ELENDİ: aşırı geniş, ilgisiz dersi kapatır, sorgu ders sınırının dışına çıkar. (b) Öğretmenin seçebildiği bir ayar yapmak — ELENDİ: bu US3'ün (ders AI politikası) alanı; US1'in kapsamına politika modeli sokmak iki hikâyeyi birbirine kilitler ve 17 Ağustos'u riske atar.

**Dokunulacak dosyalar**:
- `apps/api/app/modules/assessment/exam_state.py`
- `ARCHITECTURE.md`
- `specs/002-production-hardening/spec.md`

**Risk**: Materyali örtüşen iki ders (ör. aynı hocanın iki şubesi) açıkta kalır: öğrenci A şubesinin sınavındayken B şubesinin asistanına aynı soruyu sorup kaynaklı cevap alabilir. Jüri bunu denerse bulur; savunması "kilit ders eksenindedir ve materyal izolasyonu ders bazlıdır" olmalı, sessizce geçilmemeli.

---

## Sınav blueprint veri modeli — 002 User Story 2 / FR-110..FR-119 (migration 0008)

### 1. Şartnamenin önerdiği sekiz varlığın kaçı gerçekten ayrı tablo olmalı, hangileri mevcut tablolara kolon olarak çözülür?

**Karar**: Sekiz varlıktan BEŞİ ayrı tablo olacak (learning_outcomes, exam_blueprints, blueprint_cells, exam_versions, exam_items); ÜÇÜ kolonla çözülecek (question_learning_outcomes → questions.learning_outcome_id; rubrics → mevcut questions.payload.rubric; exam_publications → exam_blueprints.opens_at/closes_at + exam_versions.status/published_at/published_by). Ayrıca mevcut tablolara kolon eklenecek: questions.learning_outcome_id + questions.difficulty, exam_sessions.exam_version_id/exam_blueprint_id/attempt_no (+ question_ids NULL'a açılır), documents.supersedes_document_id/superseded_at. Tam DDL taslağı rationale'da.

**Gerekçe**: question_learning_outcomes bir M:N ara tablosu olarak ÖLÜR, çünkü şartnamenin istediği kardinalite 1:N: FR-113 'üretilen her taslak BİR öğrenme çıktısına ve BİR zorluk seviyesine bağlı gelmelidir', kabul senaryosu 2 (spec.md:57) de tekil. Dahası çoğa-çok, FR-112/FR-114'ün aritmetiğini imkânsız kılar: bir soru iki hücreye sayılırsa hücre toplamları soru sayısına eşitlenemez, 'birebir uyar' (SC-003) karar verilemez hâle gelir. Tek değerli ilişki bir kolondur; FK'yi taşımak için tablo açmak Anayasa XI'in tarif ettiği gereksiz yüzeydir.

rubrics tablosu ÖLÜR, çünkü rubrik zaten var ve zaten okunuyor: apps/api/app/schemas/assessment.py:95-98 (RubricItem), :105 (OpenPayload.rubric) ve değerlendirme onu apps/api/app/modules/assessment/grading.py:300-302'de prompt'a basıyor. İkinci bir ev açmak aynı ürün kuralını iki yere yazmaktır (Anayasa XI: 'ayrışma sessizdir'). Şartname de rubriği soruya bağlıyor, paylaşılan varlık demiyor (spec.md:318).

exam_publications ÖLÜR, çünkü FR-111 yayın penceresini blueprint'in taşıması gereken bir alan olarak sayıyor (spec.md:239) ve yayınlama eylemi sürümün durumudur. Ayrı tablo olsaydı 'bir sınavın aynı anda tek yayınlanmış sürümü olur' kuralı iki tablo arasında uygulama koduyla korunurdu; sürümde kolon olunca kısmi tekil indeksle yapısal olur.

DDL taslağı (0008_exam_blueprint.sql):

CREATE TYPE question_difficulty AS ENUM ('easy','medium','hard');
CREATE TYPE exam_version_status AS ENUM ('draft','published','superseded');

CREATE TABLE learning_outcomes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  code text NOT NULL,
  description text NOT NULL,
  topic_id uuid REFERENCES topics(id) ON DELETE SET NULL,   -- retrieval sorgusu için köprü
  created_by uuid NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT learning_outcomes_code_not_blank CHECK (length(btrim(code)) > 0));
CREATE UNIQUE INDEX learning_outcomes_course_code_key ON learning_outcomes (course_id, lower(code));

ALTER TABLE questions
  ADD COLUMN learning_outcome_id uuid REFERENCES learning_outcomes(id) ON DELETE SET NULL,
  ADD COLUMN difficulty question_difficulty;
CREATE INDEX questions_cell_idx ON questions (course_id, learning_outcome_id, difficulty, type) WHERE status = 'approved';

CREATE TABLE exam_blueprints (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  title text NOT NULL,
  description text,
  duration_minutes integer NOT NULL CHECK (duration_minutes BETWEEN 1 AND 600),
  max_attempts smallint NOT NULL DEFAULT 1 CHECK (max_attempts >= 1),
  opens_at timestamptz, closes_at timestamptz,
  created_by uuid NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT exam_blueprints_title_not_blank CHECK (length(btrim(title)) > 0),
  CONSTRAINT exam_blueprints_window_order CHECK (opens_at IS NULL OR closes_at IS NULL OR opens_at < closes_at));

CREATE TABLE blueprint_cells (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  blueprint_id uuid NOT NULL REFERENCES exam_blueprints(id) ON DELETE CASCADE,
  learning_outcome_id uuid NOT NULL REFERENCES learning_outcomes(id) ON DELETE RESTRICT,
  difficulty question_difficulty NOT NULL,
  question_type question_type NOT NULL,
  question_count smallint NOT NULL CHECK (question_count BETWEEN 1 AND 100),
  points_per_question smallint NOT NULL DEFAULT 1 CHECK (points_per_question BETWEEN 1 AND 100),
  UNIQUE (blueprint_id, learning_outcome_id, difficulty, question_type));

CREATE TABLE exam_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  blueprint_id uuid NOT NULL REFERENCES exam_blueprints(id) ON DELETE CASCADE,
  version_no smallint NOT NULL CHECK (version_no >= 1),
  status exam_version_status NOT NULL DEFAULT 'draft',
  published_at timestamptz, published_by uuid REFERENCES profiles(id) ON DELETE SET NULL,
  superseded_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (blueprint_id, version_no),
  CONSTRAINT exam_versions_publish_consistency CHECK (
     (status='draft'      AND published_at IS NULL AND published_by IS NULL AND superseded_at IS NULL)
  OR (status='published'  AND published_at IS NOT NULL AND published_by IS NOT NULL AND superseded_at IS NULL)
  OR (status='superseded' AND published_at IS NOT NULL AND superseded_at IS NOT NULL)));
CREATE UNIQUE INDEX exam_versions_one_published ON exam_versions (blueprint_id) WHERE status='published';

CREATE TABLE exam_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  exam_version_id uuid NOT NULL REFERENCES exam_versions(id) ON DELETE CASCADE,
  position smallint NOT NULL CHECK (position >= 1),
  question_id uuid NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
  points smallint NOT NULL CHECK (points BETWEEN 1 AND 100),
  UNIQUE (exam_version_id, position),
  UNIQUE (exam_version_id, question_id));

exam_items'ta blueprint_cell_id BİLEREK YOK: kâğıdın hangi hücreyi doldurduğu exam_items→questions (learning_outcome_id, difficulty, type) üzerinden her an türetilebilir. Pointer tutmak, hücre silindiğinde ya kanıtı kaybettiren (SET NULL) ya da blueprint'i kilitleyen (RESTRICT) bir ikilem üretirdi; türetilebilir olan saklanmaz.

questions_reviewed_consistency (0004_assessment.sql:61-64) ve exam_sessions_exam_has_expiry (0004:88-90) bu depoda 'geçersiz durumu ifade edilemez kıl' deseninin yerleşik olduğunu gösteriyor; exam_versions_publish_consistency birebir aynı kalıp.

**Elenen seçenekler**: (a) Sekiz varlığın sekizini de tablo yapmak: question_learning_outcomes ve exam_publications'ın hiçbir çoklu-kardinalite ihtiyacı yok; ikisi de 17 Ağustos dondurmasına 8 gün kala iki fazla JOIN, iki fazla RLS politikası ve iki fazla test yüzeyi demek. (b) Öğrenme çıktısını topics'e katmak (topics.outcome_code kolonu): reddedildi — topics mastery'nin birincil anahtarının parçası (0004_assessment.sql:136) ve soru üretiminin retrieval sorgusu topic.name'dir (question_gen.py:486); konu bir arama kolu, çıktı bir ölçülebilir iddia. Birleştirmek mastery semantiğini ve ölçülmüş retrieval davranışını aynı anda değiştirirdi (Anayasa III). (c) Tüm blueprint'i tek bir jsonb kolonunda tutmak: FR-114 hücre bazlı GROUP BY karşılaştırması ister, jsonb bunu Python'a taşır ve veritabanı hiçbir şey garanti edemez.

**Dokunulacak dosyalar**:
- `supabase/migrations/0008_exam_blueprint.sql`
- `apps/api/app/models/assessment.py`
- `apps/api/app/schemas/assessment.py`
- `specs/001-course-assistant-mvp/data-model.md`

**Risk**: En olası kırılma: questions'a eklenen learning_outcome_id/difficulty nullable kalacağı için (mevcut sorular bozulmasın diye) blueprint akışının 'her soru bir çıktıya bağlı' varsayımı veri düzeyinde garanti edilmez. Yayın kapısı (FR-114) bunu yakalamalı; yakalamazsa çıktısı NULL bir soru hiçbir hücreye sayılmaz ve sınav sessizce eksik yayınlanır.

---

### 2. Mevcut exams tablosu bugün ne taşıyor, blueprint gelince rolü ne olacak, göç yolu ne?

**Karar**: Depoda `exams` diye bir tablo YOK — bu şartname varsayımı yanlış ve düzeltilmeli. Var olan `exam_sessions` (0004_assessment.sql:74-91) bir öğrencinin TEK denemesidir, öğretmenin sınavı değil. Blueprint exam_sessions'ın YERİNİ ALMAZ, ÜSTÜNE gelir: exam_sessions oturum kaydı olarak kalır, nullable `exam_version_id` kazanır ve iki akış yan yana yaşar. Göç yolu veri taşımasız: `question_ids` NOT NULL kaldırılır ve `CHECK (num_nonnulls(exam_version_id, question_ids) = 1)` eklenir; mevcut satırların hepsi question_ids dolu / exam_version_id NULL olduğu için kısıtı ilk günden geçer.

**Gerekçe**: Bugün exam_sessions'ın taşıdıkları: course_id, user_id, mode(practice|exam), started_at, expires_at, finished_at, score, question_ids uuid[] (0004:74-91). Bunlardan `score` ölü kolondur — apps/api/app/api/exams.py:566-571 puanı `answers`'tan türetiyor ve 0007_question_delete_and_exam_grants.sql:49-50 dou_app'ten UPDATE'i çekip yalnız `finished_at`'i geri verdi.

Bugün 'sınav' bir öğretmen ürünü değil: apps/api/app/api/exams.py:290-301 öğrenci /exams'e POST attığında `ORDER BY random() LIMIT settings.exam_question_count` ile onaylı havuzdan rastgele soru çekiyor (apps/api/app/core/config.py:157-158: 10 soru, 20 dakika, GLOBAL). Yani her öğrenci FARKLI bir kâğıt görüyor, ortak bir sınav kâğıdı, yayın penceresi ve dağılım kavramı hiç yok. FR-111..FR-116 tam olarak bu eksik katmanı tarif ediyor.

Blueprint sonrası iki akış:
  exam_version_id IS NULL  → bugünkü self-servis prova; question_ids yetkili kaynak (0004:85-86'daki 'oturum açılırken sorular sabitlenir' notu aynen geçerli).
  exam_version_id NOT NULL → blueprint sınavı; kâğıt exam_items'tan `ORDER BY position` okunur, question_ids NULL kalır.
Blueprint oturumunda question_ids'i de yazmak aynı gerçeği iki yere koymak olurdu ve iki kopya zamanla ayrışır (Anayasa XI); CHECK bunu ifade edilemez kılar. 'Tam olarak bu kombinasyon' CHECK'i bu depoda üç kez kullanılmış desendir: 0004:61-64, 0004:88-90, 0003_chat.sql chat_messages_status_by_role.

ALTER taslağı:
ALTER TABLE exam_sessions
  ADD COLUMN exam_version_id   uuid REFERENCES exam_versions(id)   ON DELETE RESTRICT,
  ADD COLUMN exam_blueprint_id uuid REFERENCES exam_blueprints(id) ON DELETE RESTRICT,
  ADD COLUMN attempt_no smallint CHECK (attempt_no IS NULL OR attempt_no >= 1),
  ALTER COLUMN question_ids DROP NOT NULL,
  ADD CONSTRAINT exam_sessions_paper_source CHECK (num_nonnulls(exam_version_id, question_ids) = 1),
  ADD CONSTRAINT exam_sessions_blueprint_pair CHECK (
      (exam_version_id IS NULL) = (exam_blueprint_id IS NULL)
      AND (exam_version_id IS NULL) = (attempt_no IS NULL));
CREATE UNIQUE INDEX exam_sessions_attempt_key ON exam_sessions (exam_blueprint_id, user_id, attempt_no);

attempt_no + tekil indeks, FR-111'in 'yeniden deneme politikası'nı yarışa dayanıklı kılar: uygulama max_attempts'i kontrol eder, eşzamanlı ikinci istek unique ihlaline düşer ve exams.py:438-442'deki mevcut IntegrityError→ConflictError deseniyle 409'a çevrilir. Bu, 0004:115-117'nin 'tek deneme veritabanı seviyesinde de zorlanır' kararının bir üst granülaritede tekrarıdır. NULL'lar tekil indekste çakışmadığı için eski/prova oturumları etkilenmez.

Uygulama tarafında tek yeni yardımcı gerekiyor: `_paper_question_ids(session, exam)` — question_ids ya da exam_items. exams.py'de dört çağrı yeri var (:230 _session_out, :405 submit_answer, :498 request_hint, :600 finish_exam), yani üçüncü tekrardan önce ortak modüle çıkarılmalı (Anayasa XI).

**Elenen seçenekler**: (a) Yeni bir `exams` tablosu açıp exam_sessions'ı 'attempts' diye yeniden adlandırmak: 35 sınav testi, dört RLS politikası ve 0007'nin kolon GRANT'i tek seferde kırılırdı; kazanç yalnız isimlendirme. (b) Blueprint oturumunda da question_ids'i doldurmak: kısa vadede daha az kod, ama kâğıdın iki kaynağı olurdu; bir sürüm geçişinde ikisinin ayrışması sessiz ve öğrenci lehine/aleyhine rastgele olurdu. (c) question_ids'i tamamen kaldırıp prova akışını da exam_items'a taşımak: prova oturumu rastgele çekimdir, her oturum için bir exam_versions+exam_items satır kümesi yaratmak veriyi öğrenci sayısı kadar şişirirdi.

**Dokunulacak dosyalar**:
- `supabase/migrations/0008_exam_blueprint.sql`
- `apps/api/app/models/assessment.py`
- `apps/api/app/api/exams.py`
- `apps/api/tests/test_exams.py`

**Risk**: En olası kırılma: 0007:49-50 exam_sessions üzerinde tablo düzeyi UPDATE'i çekmiş durumda ve yalnız finished_at'e izin var. 0008'de eklenen kolonlara yazma gerekiyorsa (örneğin bir oturumu sonradan bir sürüme bağlamak) sessizce 'permission denied' alınır. Doğru davranış zaten budur — oturum yürürken sürümü değişemez — ama 0008 kazara `GRANT UPDATE ON exam_sessions TO dou_app` yazarsa 0007'nin süre/puan koruması geri alınır.

---

### 3. Dağılım (5 MCQ / 2 açık uçlu, %40-40-20 zorluk) JSONB mi ayrı satırlar mı? FR-112 iç tutarlılık doğrulaması DB CHECK'te mi uygulamada mı?

**Karar**: Dağılım AYRI SATIR olacak: blueprint_cells tablosunda her satır bir atomik hücre — (blueprint_id, learning_outcome_id, difficulty, question_type, question_count, points_per_question). Yüzdeler SAKLANMAZ; arayüz marjinal dağılım (%40/%40/%20 + 5 MCQ/2 açık) alır, API bunu tam sayı hücrelere açar, saklanan gerçek tam sayı adetlerdir. Toplam soru sayısı blueprint'te kolon olarak TUTULMAZ, SUM(question_count)'tur. FR-112 doğrulaması iki katmanlıdır: satır içi olgular DB CHECK'te (question_count 1..100, points 1..100, UNIQUE(blueprint_id, outcome, difficulty, type)), satırlar arası aritmetik ve Türkçe hücre adlı hata mesajı uygulama katmanında saf bir doğrulayıcı fonksiyonda.

**Gerekçe**: Satır seçiminin belirleyici gerekçesi FR-114: 'eksik hücreleri RAPORLAMALI' (spec.md:242) ve kabul senaryosu 3 'hangi hücrenin eksik olduğunu söyler' (spec.md:58). Adreslenebilir hücre demek, JOIN edilip GROUP BY ile sayılabilen satır demektir. Yayın kapısının tamamı tek sorgu oluyor:

SELECT c.learning_outcome_id, c.difficulty, c.question_type, c.question_count, coalesce(f.filled,0) AS filled
FROM blueprint_cells c
LEFT JOIN (
   SELECT q.learning_outcome_id, q.difficulty, q.type, count(*) AS filled
   FROM exam_items i JOIN questions q ON q.id = i.question_id
   WHERE i.exam_version_id = :version AND q.status = 'approved'
   GROUP BY 1,2,3) f
  ON (f.learning_outcome_id, f.difficulty, f.type) = (c.learning_outcome_id, c.difficulty, c.question_type)
WHERE c.blueprint_id = :blueprint AND coalesce(f.filled,0) <> c.question_count;

Dönen her satır bir eksik/fazla hücredir; boş küme = yayınlanabilir. Simetrik kontrol (hiçbir hücreye düşmeyen fazladan item var mı) aynı JOIN'in tersidir.

JSONB neden değil: bu depo JSONB'yi iki gerekçeyle seçmiş — VARYANT şekil (questions.payload dört tipin ortak zarfı, 0004:50-52) ve ŞEMASIZ BÜYÜYECEK durum (chat_sessions.state, 0003_chat.sql:47-51). Blueprint hücresi ikisi de değil: sabit dört alanlı bir demet ve üzerinde toplama yapılıyor. 0006_embedding_provenance.sql:20-24'teki gerekçe kalıbı da aynı yöne işaret ediyor — depo, 'kontrolü tek bir ifadeye indiren' temsili seçiyor; burada o temsil satırdır, çünkü kontrol bir agregattır.

Yüzde saklamama kararı SC-003'ün ('birebir uyar') doğrudan sonucudur: %40 × 7 soru = 2,8 ve yuvarlama kuralı saklanan veride görünmezse 'birebir' karar verilemez hâle gelir (Anayasa III: 'garanti' yalnız gerçekten deterministik mekanizmalar için). Yüzde girdi, adet gerçektir.

Toplamı kolon olarak tutmama kararı, spec.md:212'nin saydığı hata sınıfını (tip toplamları adetle eşleşmiyor) tanımdan siler: toplam türetilmişse tutarsız olamaz. Geriye kalan tutarsızlık sınıfı (kullanıcının verdiği marjinaller birbirini tutmuyor) girdi anındadır ve orada yakalanmalıdır.

FR-112'nin uygulama katmanında olmasının belirleyici gerekçesi Anayasa V: 'backend tek hata zarfı üretir; frontend kendi hata metnini uydurmaz'. Bir CHECK ihlali PostgreSQL'den kısıt adıyla döner, 'Zor MCQ hücresi 2 istiyor ama 1 soru var' cümlesini üretemez. Ayrıca CHECK diğer satırlara bakamaz; tek alternatif trigger'dır ve bu depoda public şemasındaki hiçbir iş kuralı trigger'a yazılmamıştır (grep: trigger yalnız 0002_supabase_auth_bridge.sql'de, auth.users köprüsü için ve ayrı bir rolün sahipliğinde). Deseni bozmamak için doğrulama saf bir fonksiyon olacak — DB'siz test edilebilir, tam olarak Anayasa XI'in 'örnek/kural tek yerde' ölçüsüne uyar.

**Elenen seçenekler**: (a) exam_blueprints.distribution jsonb: tek kolon, tek satır, kolay yazım; ama eksik hücre raporu Python'da elle diff üretmek zorunda kalır, UNIQUE ile çift hücre engellenemez, ve hücre bazlı soru üretimi (FR-113) her seferinde jsonb açmak zorunda kalır. (b) Yüzdeleri saklayıp yayında hesaplamak: yuvarlama kuralı iki yerde (kayıt ve yayın) yaşar ve ayrışır; 'birebir uyum' iddiası ölçülemez. (c) FR-112'yi tamamen CHECK'e yıkmak: satırlar arası toplam CHECK ile ifade edilemez; deferred constraint trigger yazmak deponun hiç kullanmadığı bir mekanizma ekler ve hata mesajı yine Türkçe olmaz. (d) Marjinalleri (yalnız tip dağılımı + yalnız zorluk dağılımı) saklamak: 'kolay MCQ eksik' denemez, yalnız 'kolay eksik' denir — FR-114'ün istediği çözünürlüğün altında.

**Dokunulacak dosyalar**:
- `supabase/migrations/0008_exam_blueprint.sql`
- `apps/api/app/modules/assessment/blueprint.py`
- `apps/api/app/schemas/blueprint.py`
- `apps/api/app/api/blueprints.py`

**Risk**: En olası kırılma: hücreler UPDATE ile kısmi güncellenirse doğrulayıcı atlanır ve tutarsız bir dağılım kaydedilir. Bunu yapısal kapatmak için 0008 `REVOKE UPDATE ON blueprint_cells FROM dou_app` yazmalı — hücre kümesi bütün olarak DELETE+INSERT ile değiştirilir, çünkü doğrulama zaten küme üzerinde yapılıyor. Bedeli: düzenleme akışı tek işlemde silip yazmak zorunda.

---

### 4. FR-115 sürümleme: yürüyen oturum başladığı sürümü görmeye devam etmeli. En basit doğru mekanizma ne — snapshot, sürüm tablosu, yoksa exam_session'a version_id mi?

**Karar**: Üçünün ikisi birlikte: SÜRÜM TABLOSU + SÜRÜM KALEMLERİ (exam_versions / exam_items) ve oturumun o sürüme İŞARET ETMESİ (exam_sessions.exam_version_id). Payload snapshot'ı ALINMAYACAK. Yayınlanmış bir sürüm ve kalemleri değişmez: değişiklik yeni bir exam_versions satırı + yeni exam_items kümesi üretir, eski sürüm 'superseded' olur ama SİLİNMEZ. Değişmezlik RLS ile değil GRANT ile zorlanır: `REVOKE UPDATE ON exam_versions, exam_items FROM dou_app; GRANT UPDATE (status, superseded_at) ON exam_versions TO dou_app;` — yani dou_app bir sürümün kalem listesini hiçbir kod yolundan değiştiremez, yalnız durumunu ilerletebilir.

**Gerekçe**: Snapshot'a gerek olmamasının belirleyici gerekçesi: bu depoda soru İÇERİĞİ zaten değişmez. apps/api/app/api/questions.py'de soruyu düzenleyen HİÇBİR uç yok — yalnız generate (:154), approve (:228), reject (:236), delete (:244). payload'a yazan tek yol question_gen.py:533-541'deki yeni satır oluşturmadır. İçerik değişmezse kimlikle referans, kopyayla saklama kadar sağlamdır; kopya yalnız N öğrenci × tam payload şişkinliği getirir.

Bu değişmezlik 002'de KORUNACAK ve bir karar olarak yazılacak: 'yayınlanmış bir sınavda soruyu değiştirmek' (spec.md:59) soru satırını düzenlemek değil, yeni bir soru üretip/onaylayıp yeni sürüme koymaktır. Bu, FR-119'un onay kapısını yeni içeriğe de uygular (spec.md:247 'blueprint akışı onu zayıflatmamalıdır') ve answers.question_id → questions(id) ON DELETE RESTRICT (0004:103) sayesinde cevaplanmış hiçbir sorunun referansı boşa düşmez.

exam_sessions.exam_version_id'nin ON DELETE RESTRICT olması ve 0007:49-50'nin exam_sessions'ta tablo düzeyi UPDATE'i çekmiş olması birlikte şunu verir: yürüyen bir oturumun sürümü ne silinebilir ne değiştirilebilir. FR-115'in 'başladığı sürümü görmeye devam eder' garantisi böylece uygulama koduna değil yetkilere dayanır (Anayasa II'nin ikinci katmanı).

GRANT ile değişmezlik, 0007'nin (b) maddesinin birebir uzantısıdır: 'RLS satır düzeyinde çalışır, SÜTUN kısıtı veremez — bu yüzden kolon bazlı GRANT' (0007:43). exam_items'a hiç UPDATE verilmemesi aynı cümlenin tablo düzeyindeki hâlidir.

DİKKAT: 0001_core_schema.sql:313 ve :315-316 tüm mevcut ve GELECEK tablolara dou_app/dou_worker için SELECT/INSERT/UPDATE/DELETE veriyor. Yani 0008'de bu REVOKE'lar açıkça yazılmazsa exam_items tam yazılabilir doğar ve FR-115'in yapısal ayağı hiç kurulmamış olur.

Ek zorunlu kapı: yayınlanmış (superseded olmayan) bir sürümün kaleminde yer alan soru REDDEDİLEMEZ. Silme zaten exam_items.question_id RESTRICT ile kapalı, ama red bir status değişikliğidir ve questions_read (0004:170-174) reddedilen soruyu öğrenciden gizlediği için yürüyen bir kâğıt sessizce kısalırdı — exams.py:125-136 bu davranışı prova için bilerek tolere ediyor, sınav için tolere edilemez. Bu kontrol uygulama katmanında (_review, questions.py:206-225) yapılacak, çünkü kullanıcıya anlaşılır Türkçe bir ret dönmesi gerekiyor (Anayasa V).

**Elenen seçenekler**: (a) exam_sessions.paper_snapshot jsonb: her oturuma tüm soruların tam payload'ı kopyalanır. Öğrenci sayısıyla çarpan veri, ve payload şeması değişince eski snapshot'lar parse_payload'dan (schemas/assessment.py:163-171) düşer — grading.py:411-416 bunu 'değerlendirilemedi'ye çevirir, yani snapshot geçmişi korumak yerine bozardı. (b) Yalnız exam_sessions.version_no (tablo yok): sürümün kalem listesi hiçbir yerde durmaz, 'başladığı sürümü görmeye devam eder' iddiası veriye değil koda dayanır. (c) Soruyu yerinde düzenleyip questions'a version_no eklemek: answers.question_id'nin işaret ettiği içerik değişir, geçmiş cevaplar okunamaz hâle gelir ve FR-119 onay kapısı düzenleme yoluyla atlanır.

**Dokunulacak dosyalar**:
- `supabase/migrations/0008_exam_blueprint.sql`
- `apps/api/app/api/exams.py`
- `apps/api/app/api/questions.py`
- `apps/api/app/models/assessment.py`

**Risk**: En olası kırılma: 0008'in REVOKE satırları unutulur (0001:315-316 varsayılan yetkileri sessizce verir) ve exam_items güncellenebilir kalır. O zaman FR-115 testi yeşil görünür — çünkü uygulama kodu zaten yeni sürüm yaratıyordur — ama garanti yapısal değil alışkanlığa dayalı olur; ileride yazılacak bir 'hızlı düzeltme' ucu yürüyen sınavı değiştirebilir.

---

### 5. FR-117 rubrik: mevcut açık uçlu değerlendirme nerede yapılıyor, rubrik oraya nasıl bağlanır?

**Karar**: Rubrik zaten bağlı; eksik olan ÖLÇÜT KIRILIMI. Değerlendirme apps/api/app/modules/assessment/grading.py:393-439 grade_answer → :335-385 grade_with_llm'de yapılıyor ve rubrik :300-302'de prompt'a giriyor. Yeni tablo AÇILMAYACAK. Üç değişiklik yapılacak: (1) OpenPayload'a ağırlık toplamı 100 doğrulaması eklenecek; (2) _LlmVerdict ölçüt bazlı puan dönecek ve TOPLAM PUAN MODELDEN OKUNMAYACAK, ağırlıklarla bizim tarafımızdan hesaplanacak; (3) kırılım mevcut answers.feedback jsonb'sine 'rubrik_kirilimi' anahtarıyla yazılıp AnswerFeedbackOut ile gösterilecek.

**Gerekçe**: Bugünün durumu tam olarak şu: schemas/assessment.py:95-98 RubricItem yalnız `weight: int = Field(ge=1, le=100)` diyor; OpenPayload._check_format (:110-117) format/accepted_answers/key_points doğruluyor ama AĞIRLIK TOPLAMINI doğrulamıyor. Buna karşılık grading.py:301 modele 'Rubrik (ağırlıklar 100 üzerinden)' diyor ve question_gen.py:287-288 modelden 'ağırlıklar toplamı 100' istiyor. Yani sistem üç yerde 100 diyor, hiçbir yerde zorlamıyor — FR-117'nin ölçüt kırılımını bunun üstüne kurmak, toplamı 137 olan bir rubrikle öğrenciye yanlış yüzde göstermek demek. Doğrulama tek yere, payload modeline konulmalı (Anayasa XI: kural tek sözlükte).

Puanın modelden değil bizden gelmesi, deponun kendi kurduğu deseni izler: question_gen.py:16-19 'distractor_sources modelden istenmez ... deterministik yol her zaman birincildir'. Aynı mantıkla model her ölçüt için 0-100 verir, toplam puan `round(Σ(weight_i × score_i) / 100)` ile hesaplanır. Bu, FR-117'nin 'hangi ölçütten kaç puan aldığı' vaadini toplam puanla ARİTMETİK OLARAK tutarlı kılar; model hem kırılım hem ayrı bir toplam verseydi ikisi çelişebilirdi ve öğrenciye gösterilen tablo toplamı tutmazdı.

Set-membership kontrolü zaten var olan kalıpla yapılacak: dönen ölçüt adları payload.rubric'teki `point` kümesiyle birebir eşleşmiyorsa değerlendirme TAMAMLANMAZ (_ungraded, grading.py:193-195) — grading.py:370-374'teki dayanak_chunk_id kontrolünden bir tık daha sıkı, çünkü orada 'puan durur, kaynak düşer' makuldü; burada eksik ölçüt doğrudan puanı yanlış yapar (Anayasa IV, fail-closed).

Saklama yeri yeni kolon değil, mevcut answers.feedback jsonb'si (0004:110-112; şema exams.py:151-162 _feedback_payload'da tek yerden üretiliyor). Öğrenciye gösterim yüzeyi de var: AnswerFeedbackOut (schemas/assessment.py:297-312) yeni bir `rubric_breakdown` alanı alır. Ölçütlerin sınav bitince açılması zaten kurulu: _SOLUTION_KEYS 'rubric'i içeriyor (schemas/assessment.py:160). Sınav sürerken gizli kalması da doğru — _PUBLIC_PAYLOAD_KEYS[OPEN] = ('prompt','format') (:155) ve FR-117 kırılımı 'öğrenci cevaplar → değerlendirme yapılır → gösterilir' sırasına bağlıyor (spec.md:61).

Ayrı bir `rubrics` tablosunun tek gerçek gerekçesi rubriğin sorular arasında PAYLAŞILMASI olurdu; şartname bunu istemiyor (spec.md:318 'Soruya bağlanır') ve paylaşılan rubrik, sürümleme sorununu ikinci bir varlığa taşırdı: soru dondurulmuşken rubrik değişirse yürüyen sınavın puanlaması değişirdi.

**Elenen seçenekler**: (a) rubrics + rubric_criteria tabloları ve questions.rubric_id: payload'daki rubrik ile tablo aynı anda yaşar, hangisinin geçerli olduğu her okuma yerinde yeniden hatırlanmak zorunda kalır (Anayasa XI'in tam olarak yasakladığı durum) ve grading.py:300-302 ile question_gen.py:287-288'in ikisi de değişmek zorunda kalır. (b) Kırılımı answers'a ayrı kolon(lar) olarak eklemek: feedback jsonb'si tam bu iş için var ve şeması tek yerden (exams.py:151-162) üretiliyor. (c) Toplam puanı modelden okuyup kırılımı yalnız açıklama olarak göstermek: en az iş, ama kırılım toplamı tutmadığında öğrenciye tutarsız bir tablo gösterir — Anayasa III'e aykırı.

**Dokunulacak dosyalar**:
- `apps/api/app/modules/assessment/grading.py`
- `apps/api/app/schemas/assessment.py`
- `apps/api/app/api/exams.py`
- `apps/api/tests/test_exams.py`

**Risk**: En olası kırılma: ağırlık toplamı doğrulaması OpenPayload'a eklenince, LLM'in ürettiği ve BUGÜN havuzda duran rubrikli sorular parse_payload'dan düşer; grade_answer:411-416 bunu '_ungraded' sayar ve mevcut onaylı sorular sessizce değerlendirilemez hâle gelir. Doğrulama yalnız YENİ üretimde (question_gen'in _OpenDraft'ında) zorlanmalı, okuma yolunda ise toplam 100 değilse ağırlıklar normalize edilmeli — ya da 0008 ile birlikte havuz taranıp raporlanmalı.

---

### 6. FR-118 'kaynak sürümü değişti': belge yeniden yüklendiğinde nasıl anlaşılacak? documents/chunks'ta sürüm izi var mı?

**Karar**: Bugün sürüm izi YOK ve otomatik anlaşılamaz — bu tespit edilmesi gereken ilk şey. documents'a `supersedes_document_id` ve `superseded_at` eklenecek; bağ AÇIK BİR 'değiştir' eylemiyle kurulacak (yükleme ucu opsiyonel `replaces_document_id` alacak), tahminle değil. Sorunun bayat olduğu ise SAKLANMAYACAK, TÜRETİLECEK: questions → chunks → documents zincirinde documents.superseded_at IS NOT NULL olan her soru 'kaynak sürümü değişti' işaretiyle listelenir. questions'a `source_stale` boolean EKLENMEYECEK.

**Gerekçe**: Mevcut durum kanıtı: chunks'ta sürüm alanı yok (0001_core_schema.sql:236-257); 0006_embedding_provenance.sql'in eklediği `embedding_space` sürüm izi DEĞİL, vektör uzayı kimliğidir (0006:26-31) — belgenin içeriği değişmeden fastembed sürümü değiştiğinde de değişir, içerik değişip kütüphane aynı kaldığında değişmez. documents'ta yalnız `file_hash` var ve UNIQUE (course_id, file_hash) (0001:227) ile apps/api/app/api/documents.py:60-71 aynı içeriğin ikinci yüklemesini 409 ile reddediyor. DEĞİŞTİRİLMİŞ bir dosya farklı hash taşır, yeni bir documents satırı olarak girer, eski satır ve chunk'ları yerinde kalır ve İKİSİ ARASINDA HİÇBİR BAĞ KURULMAZ. Yani FR-118 bugün veri eksikliğinden değil, ilişki eksikliğinden çalışmıyor.

ALTER taslağı:
ALTER TABLE documents
  ADD COLUMN supersedes_document_id uuid REFERENCES documents(id) ON DELETE SET NULL,
  ADD COLUMN superseded_at timestamptz;
CREATE INDEX documents_superseded_idx ON documents (course_id) WHERE superseded_at IS NOT NULL;
(kısmi indeks deseni: 0001:284-285 ingestion_jobs_pending_idx.)

Bayatlık sorgusu:
SELECT q.id FROM questions q
  JOIN chunks c    ON c.id = q.source_chunk_id
  JOIN documents d ON d.id = c.document_id
 WHERE q.course_id = :course AND d.superseded_at IS NOT NULL;

Türetme kararının belirleyici gerekçesi: saklanan bir bayrağın bir yazıcısı olur ve o yazıcı yükleme anında o belgenin TÜM chunk'larının TÜM sorularını gezmek zorundadır. Bu fan-out arka planda koşar, sessizce düşebilir ve düştüğünde işaret hiç görünmez — Anayasa XI'in 'ayrışma sessizdir' dediği şeyin tam örneği. Türetilmiş sorgu, indeksli iki FK üzerinde her zaman doğrudur ve soru havuzu ucu (questions.py:120-151) zaten kaynak referanslarını toplu okuyor (load_source_refs, :147), yani ek sorgu maliyeti tek bir JOIN.

Dosya adına bakarak otomatik eşleme REDDEDİLDİ: 0001'de file_name üzerinde hiçbir tekillik yok, 'hafta3.pdf' her dönem yeniden yüklenir (yanlış pozitif) ve yeniden adlandırılmış bir güncelleme yakalanmaz (yanlış negatif). Yanlış işaretlenen bir soru, öğretmenin işarete olan güvenini bitirir; işaret güvenilmezse hiç olmamasından kötüdür.

Açık eylemin kaçırılma riskini kapatan davranış: yükleme ucu, aynı derste AYNI ADLI ama farklı hash'li bir belge görürse tahmin etmez, 409 ile 'bunu şu belgenin yeni sürümü olarak yüklemek istiyor musunuz' der ve replaces_document_id ile tekrar denemeyi ister. documents.py bu deseni zaten kullanıyor: silme 409'u kullanıcıya yapılabilir bir çıkış yolu tarif ediyor (:176-183).

**Elenen seçenekler**: (a) chunks'a document_version kolonu: chunk'lar zaten belgeye CASCADE bağlı (0001:240); sürüm belgenin özelliğidir, chunk'ın değil — chunk'a yazmak aynı değeri N kez saklamaktır. (b) file_hash değişimini aynı documents satırında güncelleyip eski chunk'ları silmek: questions.source_chunk_id ON DELETE RESTRICT (0004:55) buna izin vermez ve vermesi de istenmez — kaynağı silinmiş soru, kaynağına karşı doğrulanamayan sorudur (Anayasa I; documents.py:167-172 aynı gerekçeyi yazıyor). (c) questions.source_stale boolean + arka plan işi: yukarıdaki sessiz sapma riski. (d) 0006'nın embedding_space damgasını sürüm izi saymak: farklı soruya cevap veren bir alan; kullanmak Anayasa III'e aykırı bir iddia olurdu.

**Dokunulacak dosyalar**:
- `supabase/migrations/0008_exam_blueprint.sql`
- `apps/api/app/api/documents.py`
- `apps/api/app/api/questions.py`
- `apps/api/app/models/core.py`
- `apps/api/app/schemas/assessment.py`

**Risk**: En olası kırılma: eskimiş sayılan belgenin chunk'ları retrieval'da kalmaya devam eder, yani asistan hâlâ eski materyalden atıf verir. Bu, US3/FR-132'nin (kaynak seti) alanı ve orada karar verilmezse FR-118 yalnız soru havuzunda uyarı gösterip cevaplarda hiçbir şey değiştirmez — belgede 'kaynak sürümü yönetiliyor' izlenimi verip pratikte yönetmemek Anayasa III ihlali olur.

---

### 7. Her yeni tablo için RLS politikası: 0004'teki desen ne, birebir nasıl uygulanacak, öğretmen/öğrenci ayrımı nasıl?

**Karar**: 0004'ün deseni birebir uygulanacak: her yeni tablo denormalize `course_id NOT NULL` taşır, ENABLE + FORCE ROW LEVEL SECURITY alır, politikalar app.is_member() / app.is_instructor() çağırır ve her INSERT politikası course_id'yi de doğrular. Öğretmen/öğrenci ayrımı questions_read'in (0004:170-174) yapısal ikizi olacak: 'eğitmen hepsini görür, üye yalnız SERBEST BIRAKILMIŞ alt kümeyi görür'. blueprint_cells'e öğrenci SELECT politikası BİLEREK YAZILMAYACAK. exam_sessions_self_insert politikası DROP+CREATE ile yayın penceresi kontrolü eklenmiş hâliyle yeniden kurulacak — FR-116 böylece iki katmanlı olur.

**Gerekçe**: Desenin kaynağı 0004_assessment.sql:3-11: 'course_id her tabloda denormalize edilir (izolasyon filtresi JOIN'e bağlı kalmaz), her tablo ENABLE + FORCE ile işaretlenir, politikalar app.is_member()/app.is_instructor() kullanır'. 0003_chat.sql:5-19 aynı kararı tekrarlıyor ve 0004 incelemesinde yakalanan hatayı da yazıyor: 'denormalize course_id taşıyan bir tabloya INSERT politikası yazarken YALNIZ user_id kontrolü yetmez'.

Politika taslağı:

ALTER TABLE learning_outcomes, exam_blueprints, blueprint_cells, exam_versions, exam_items ENABLE/FORCE ROW LEVEL SECURITY;

-- learning_outcomes: topics'in birebir kopyası (0004:159-166)
CREATE POLICY learning_outcomes_member_read ON learning_outcomes FOR SELECT USING (app.is_member(course_id));
CREATE POLICY learning_outcomes_instructor_write  ON learning_outcomes FOR INSERT WITH CHECK (app.is_instructor(course_id));
CREATE POLICY learning_outcomes_instructor_update ON learning_outcomes FOR UPDATE USING (app.is_instructor(course_id)) WITH CHECK (app.is_instructor(course_id));
CREATE POLICY learning_outcomes_instructor_delete ON learning_outcomes FOR DELETE USING (app.is_instructor(course_id));

-- exam_blueprints: 'taslak öğrenciye görünmez' (spec.md:56) + FR-116 penceresi
CREATE POLICY exam_blueprints_read ON exam_blueprints FOR SELECT USING (
    app.is_instructor(course_id)
 OR (app.is_member(course_id)
     AND (opens_at IS NULL OR opens_at <= now())
     AND (closes_at IS NULL OR now() < closes_at)
     AND EXISTS (SELECT 1 FROM exam_versions v WHERE v.blueprint_id = exam_blueprints.id AND v.status = 'published')));
+ instructor insert/update/delete (WITH CHECK'li)

-- blueprint_cells: yalnız eğitmen; öğrenci SELECT politikası YOK
CREATE POLICY blueprint_cells_instructor_read   ON blueprint_cells FOR SELECT USING (app.is_instructor(course_id));
CREATE POLICY blueprint_cells_instructor_insert ON blueprint_cells FOR INSERT WITH CHECK (app.is_instructor(course_id));
CREATE POLICY blueprint_cells_instructor_delete ON blueprint_cells FOR DELETE USING (app.is_instructor(course_id));

-- exam_versions: yayın penceresi VEYA 'bu sürümde oturumum var'
CREATE POLICY exam_versions_read ON exam_versions FOR SELECT USING (
    app.is_instructor(course_id)
 OR (app.is_member(course_id) AND status = 'published' AND app.is_exam_open(id))
 OR EXISTS (SELECT 1 FROM exam_sessions s WHERE s.exam_version_id = exam_versions.id AND s.user_id = app.current_user_id()));

-- exam_items: öğrenci kâğıdı ancak o sürümde oturumu varsa görür (0004:197-204 answers_self_read ile aynı EXISTS kalıbı)
CREATE POLICY exam_items_read ON exam_items FOR SELECT USING (
    app.is_instructor(course_id)
 OR EXISTS (SELECT 1 FROM exam_sessions s WHERE s.exam_version_id = exam_items.exam_version_id AND s.user_id = app.current_user_id()));
CREATE POLICY exam_items_instructor_insert ON exam_items FOR INSERT WITH CHECK (app.is_instructor(course_id));
CREATE POLICY exam_items_instructor_delete ON exam_items FOR DELETE USING (app.is_instructor(course_id));

-- FR-116'nın ikinci katmanı: oturum yalnız yayınlanmış ve penceresi açık sürümde açılabilir
DROP POLICY exam_sessions_self_insert ON exam_sessions;
CREATE POLICY exam_sessions_self_insert ON exam_sessions FOR INSERT WITH CHECK (
    user_id = app.current_user_id() AND app.is_member(course_id)
 AND (exam_version_id IS NULL OR app.is_exam_open(exam_version_id, exam_sessions.course_id)));

app.is_exam_open(), app.is_member()'ın gerekçesiyle aynı sebeple SECURITY DEFINER STABLE boolean yardımcısı olacak (0001:83-85): politika içinden başka bir RLS'li tabloya SELECT atmak, iki tablonun politikalarını birbirine bağlar ve ilerideki bir politika değişikliği bu bağı sessizce bozar. Fonksiyon yalnız boolean döner, satır sızdırmaz — 0001'deki aynı cümle.

Öğretmen/öğrenci ayrımının özeti: 'yayın penceresi blueprint'e ne ise, status=approved soruya odur.' questions_read'in (0004:168-174) tarif ettiği 'EN KRİTİK politika' burada ikinci kez, aynı biçimde kuruluyor.

İki ince nokta: (1) Pencere kapandığında blueprint listesi öğrenciden kaybolur ama exam_versions/exam_items'ın 'oturumum var' dalı sayesinde YÜRÜYEN kâğıt kaybolmaz — FR-116 'kapandığında YENİ oturum başlatamaz' diyor (spec.md:60), başlamışı düşürmüyor. (2) blueprint_cells'i öğrenciye kapatmanın gerekçesi sızıntıdır: 'bu sınavda 2 zor soru var' sınav istihbaratıdır. Kapalı bırakıp gerekirse sonra gerekçesiyle açmak deponun yazılı alışkanlığı (0005_analytics.sql başlığı, request_logs'un 0003'te kapatılıp 0005'te dar bir kapsamla açılması).

**Elenen seçenekler**: (a) course_id'yi denormalize etmeyip parent üzerinden JOIN'li politika yazmak: 0004:3-11 ve 0003:5-19 bu kararı iki kez gerekçelendirmiş; politika içinde JOIN her satırda parent'ın RLS'ini de tetikler ve fail-closed davranış okunaksız hâle gelir. (b) exam_items'ı da yayın penceresine bağlamak: zil çaldığında yürüyen öğrencinin kâğıdı ekrandan silinirdi. (c) blueprint_cells'i üyeye açmak: soru dağılımı sınav öncesi ipucudur. (d) FR-116'yı yalnız uygulama katmanında zorlamak: Anayasa II tek katmanlı izolasyona izin vermiyor ve spec.md:76 aynı ilkeyi politika için tekrarlıyor.

**Dokunulacak dosyalar**:
- `supabase/migrations/0008_exam_blueprint.sql`
- `apps/api/tests/test_isolation_layers.py`
- `apps/api/tests/test_security.py`

**Risk**: En olası kırılma: exam_sessions_self_insert politikasının DROP+CREATE'i sırasında 0004:188-193'te bilerek eklenmiş WITH CHECK mantığının (oturumun üyesi olunmayan bir derse kaydırılamaması) bir kısmı düşürülür. O politika bir PR incelemesinde kapatılmış gerçek bir açığın yamasıdır; yeniden yazarken eski koşulların tamamı korunmalı ve testle sabitlenmeli.

---

### 8. Migration numarası kaç olacak, mevcut en yüksek nedir, dosyada başka ne bulunmak zorunda?

**Karar**: Mevcut en yüksek 0007 (0007_question_delete_and_exam_grants.sql). Yeni göç 0008 olacak: `supabase/migrations/0008_exam_blueprint.sql`, tek BEGIN/COMMIT içinde. Dosya yalnız DDL değil, üç grup GRANT/REVOKE de içermek ZORUNDA: (1) REVOKE UPDATE ON exam_items, blueprint_cells FROM dou_app; (2) REVOKE UPDATE ON exam_versions FROM dou_app + GRANT UPDATE (status, superseded_at); (3) exam_sessions'a KESİNLİKLE geniş UPDATE geri verilmemesi.

**Gerekçe**: Dizin listesi: 0001_core_schema, 0002_supabase_auth_bridge, 0003_chat, 0004_assessment, 0005_analytics, 0006_embedding_provenance, 0007_question_delete_and_exam_grants. En yüksek 0007, dolayısıyla 0008.

GRANT/REVOKE'ların göçün parçası olmasının sebebi 0001_core_schema.sql:313 ve :315-316: `GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO dou_app, dou_worker` ve `ALTER DEFAULT PRIVILEGES ... GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES`. Yani 0008'de yaratılan her tablo, hiçbir şey yazılmazsa dou_app için tam yazılabilir doğar. Karar 4'ün (sürüm değişmezliği) ve Karar 3'ün (hücre kümesinin bütün olarak doğrulanması) yapısal ayakları tam olarak bu REVOKE'lardır; unutulurlarsa göç 'çalışır' ama iki garanti de yalnız uygulama koduna dayanır.

0007:49-50 bu hareketin deponun yerleşik dili olduğunu gösteriyor: `REVOKE UPDATE ON exam_sessions FROM dou_app; GRANT UPDATE (finished_at) ON exam_sessions TO dou_app;` — ve o dosyanın başlığı sebebi de yazıyor: 'RLS satır düzeyinde çalışır, SÜTUN kısıtı veremez' (0007:43).

Ayrıca 0008 dosya başlığı bu deponun göç yazma âdetine uymalı: her göç, NE yaptığını değil NİÇİN o biçimde yaptığını anlatan uzun bir yorum bloğuyla açılıyor (0004:1-11, 0006:1-58, 0007:1-9) ve BİLEREK YAPILMAYANLARI gerekçesiyle yazıyor (0007:53-68). 0008'de bilerek yapılmayanlar: rubrics tablosu, question_learning_outcomes ara tablosu, exam_publications tablosu, questions.source_stale bayrağı — dördünün de gerekçesi dosyada durmalı, yoksa bir sonraki inceleme bunları 'eksik' diye raporlar (spec.md:21'in tarif ettiği hata).

Model tarafı: yeni tablolar apps/api/app/models/assessment.py'ye eklenecek; pg_enum(..., create_type=False) kullanılacak (models/base.py:20-38 — enum tipleri göçte tanımlanır, ORM yaratmaz) ve migration'lar düz SQL kalacak (models/assessment.py:3-5).

Belge ayağı unutulmamalı: specs/001-course-assistant-mvp/data-model.md 'uygulanmış / planlanan' ayrımını taşıyor ve US7 (FR-180) belgelerin kodla çelişmemesini istiyor; 0008 aynı commit'te bu belgeye (ya da 002'nin kendi data-model.md'sine) yansıtılmalı.

**Elenen seçenekler**: (a) Blueprint'i iki göçe bölmek (0008 tablolar, 0009 politikalar/yetkiler): tablolar politikasız bir an için tam açık kalır ve bu depoda her göç kendi RLS'ini aynı BEGIN/COMMIT'te kuruyor (0003, 0004). (b) Numarayı 0010 gibi boşluklu vermek: dizinde boşluk yok, sıralı devam etmek göç sırasını okunur tutuyor. (c) REVOKE'ları uygulama katmanına bırakmak: 0007'nin bütün gerekçesi bunun yetersizliği.

**Dokunulacak dosyalar**:
- `supabase/migrations/0008_exam_blueprint.sql`
- `apps/api/app/models/assessment.py`
- `apps/api/app/models/core.py`
- `specs/001-course-assistant-mvp/data-model.md`

**Risk**: En olası kırılma: 0008 tek işlemde koştuğu için DROP POLICY exam_sessions_self_insert satırı hata verirse (isim değişmişse) tüm göç geri alınır ve kısmen uygulanmış bir şema kalmaz — bu iyi. Asıl risk sessiz olanı: REVOKE satırları yazılmazsa hiçbir test kırmızı yanmaz, çünkü uygulama kodu zaten doğru davranıyordur. Bu yüzden 'kalem listesi güncellenemez' ve 'hücre güncellenemez' için ayrı, yetkiyi doğrudan sınayan test yazılmalı (Anayasa II'nin 'politika bilerek bozularak kanıtlanır' kuralının yetki karşılığı).

---

### 9. Blueprint sınavında puan hesabı ve soru üretimi mevcut kodda nereye dokunuyor (FR-113 ve soru başına puan)?

**Karar**: İki nokta genişletilecek, hiçbiri yeniden yazılmayacak. (1) question_gen.generate_questions imzasına opsiyonel `learning_outcome: LearningOutcome | None` ve `difficulty: QuestionDifficulty | None` eklenecek; ikisi de Question satırına yazılacak ve zorluk prompt'a bir satır olarak girecek. Retrieval sorgusu, çıktının bağlı olduğu topics satırından (learning_outcomes.topic_id) ya da yoksa çıktının kendi description'ından gelecek. (2) grading.score_of ağırlık kabul edecek; ağırlık verilmezse bugünkü davranış birebir korunacak.

**Gerekçe**: FR-113 'üretilen her taslak bir öğrenme çıktısına ve bir zorluk seviyesine bağlı gelmelidir' (spec.md:241). Bugün üretim ucu yalnız topic + tip + adet alıyor: apps/api/app/api/questions.py:154-203 ve question_gen.generate_questions (question_gen.py:461-474). Question satırı question_gen.py:533-541'de tek yerde kuruluyor; iki alan orada set edilir. Retrieval sorgusu topic.name (question_gen.py:486) — bu yüzden learning_outcomes.topic_id köprüsü var: çıktı bir konuya bağlıysa bugünkü ölçülmüş retrieval davranışı hiç değişmez (Anayasa III: ölçülmüş davranış gerekçesiz değiştirilmez).

Zorluğun prompt'a girmesi _TYPE_INSTRUCTIONS'ın (question_gen.py:278-300) yanına tek bir satır olarak eklenir; taslak şemalarına (_McqDraft vb., :215-243) YENİ ALAN EKLENMEZ — zorluk modelden ISTENMEZ, blueprint hücresinden gelir ve bizim tarafımızdan yazılır. Bu, distractor_sources kararının (question_gen.py:16-19) birebir uygulanmasıdır: hücre zaten 'zor MCQ' diyorsa modele 'kaç zor ürettin' diye sormak, doğrulanamayan bir alanı veriye sokmak olurdu.

Puan tarafı: blueprint sınavında soru başına puan farklıdır (blueprint_cells.points_per_question → exam_items.points), oysa grading.score_of (grading.py:442-452) 0-100 puanların AĞIRLIKSIZ ortalamasını alıyor ve değerlendirilememiş cevapları paydadan çıkarıyor. Blueprint sınavı için doğru sonuç Σ(points_i × score_i) / Σ points_i olmalı. Fonksiyon tek yerde ve iki çağıranı var (exams.py:252 ve :562); imzaya opsiyonel ağırlık eklemek, ikinci bir puanlama fonksiyonu yazmaktan iyidir — iki puanlama fonksiyonu er geç ayrışır (Anayasa XI) ve 'boş soru yanlış değildir / değerlendirilemeyen paydaya girmez' kuralı (grading.py:447-451) iki kez hatırlanmak zorunda kalırdı.

exam_items.points'in hücreden KOPYALANMASI (türetilmemesi) bilinçli: 0004:85-86'nın 'oturum açılırken sorular burada sabitlenir' gerekçesiyle aynı — yayın anındaki puan dondurulur, blueprint sonradan düzenlense de yayınlanmış kâğıdın puanlaması değişmez.

**Elenen seçenekler**: (a) Ayrı bir blueprint_question_gen modülü yazmak: aynı fail-closed zinciri (set-membership, şema doğrulama, tek yeniden deneme) ikinci kez yazılırdı; question_gen.py:12-23'teki iki deterministik kural iki yerde yaşamaya başlardı. (b) score_of'u değiştirmeyip ağırlıklı puanı exams.py'de hesaplamak: 'değerlendirilemeyen paydaya girmez' kuralı iki dosyada olurdu. (c) Zorluğu modelden istemek: doğrulanamaz, ve blueprint hücresi zaten zorluğu belirliyor.

**Dokunulacak dosyalar**:
- `apps/api/app/modules/assessment/question_gen.py`
- `apps/api/app/modules/assessment/grading.py`
- `apps/api/app/api/exams.py`
- `apps/api/app/api/questions.py`
- `apps/api/app/schemas/assessment.py`

**Risk**: En olası kırılma: score_of'a ağırlık eklenirken varsayılan davranış farkında olmadan değişir (ör. ağırlık None yerine 1 kabul edilip değerlendirilememiş cevaplar paydaya girer). Bu, prova modundaki mevcut 35 sınav testinin bir kısmını kırmasa bile puanı sessizce kaydırabilir; ağırlıksız çağrının bugünkü sonucu testle sabitlenmeden değişiklik yapılmamalı.

---

## Frontend güvenilirlik + sayfalama + kimlik (User Story 4/5/6 — FR-150..FR-173)

### 1. 1. Timeout bütçeleri (FR-150): kaç bütçe, hangi değerler, tek global bütçe neden yanlış?

**Karar**: DÖRT bütçe olacak, `apps/web/lib/api.ts` içinde tek bir `const BUDGET_MS = { read: 12_000, write: 20_000, upload: 90_000, llm: 120_000 } as const` sözlüğünde. Seçim `request()` içinde otomatik: `init?.method` yoksa `read`, `FormData` gövde varsa `upload`, aksi hâlde `write`. `llm` yalnız açık istekle seçilir — `api.post`'a isteğe bağlı üçüncü argüman (`api.post<ChatAnswer>(path, body, "llm")`) eklenir ve yalnız iki çağrı yeri kullanır: sohbet gönderimi (app/courses/[courseId]/chat/page.tsx:174) ve soru üretimi (questions/page.tsx içindeki generate çağrısı). Her DENEME için taze `AbortSignal.timeout(budget)` kurulur; paylaşılan tek sinyal ikinci denemeyi anında öldürürdü.

**Gerekçe**: Ölçümler tek bir sayıyı imkânsız kılıyor. docs/runbook.md:104-114: sıcak okuma 0,08–0,41 sn, önbellek isabeti 0,011 sn, İLK soru 11,7 sn (2,1 GB ONNX modeli belleğe yükleniyor), ilk materyal yükleme 19,1 sn. runbook.md:116-119 gerçek LLM için üstünü de yazıyor: sağlayıcı başına 30 sn zaman aşımı, iki sağlayıcı → 60 sn; kodda doğrulandı (apps/api/app/core/config.py:211 `llm_timeout_seconds: float = 30.0`, config.py:208 `llm_fallback_model`). Sohbette bu 60 sn tek başına değil: apps/api/app/api/chat.py:516-528 Sokratik ihlalde ikinci kez üretiyor, yani patolojik tepe 11,7 + 4×30 ≈ 132 sn. `llm=120_000` bu tepenin altında bilinçli duruyor — dört sağlayıcı zaman aşımı yakmış bir istek zaten başarılı olmayacak, kullanıcı serbest bırakılır. `upload=90_000` dosya boyutundan geliyor: config.py:116 `max_upload_bytes = 20*1024*1024`; 20 MB mütevazı bir yükleme hattında 50 sn'yi aşar, sunucu tarafı ise hızlıdır (documents.py:35 `202` döner, ağır iş documents.py:92 `background.add_task` ile yanıttan sonra koşar). `read=12_000` sıcak okumanın ~30 katı; okuma uçlarının hiçbiri embedding'e dokunmaz (courses.py:33-41, documents.py:100-106, questions.py:143-146, chat.py:704-708 salt SELECT). Tek global bütçe iki yönde de yanlış: (a) sohbeti kurtaracak 120 sn'ye ayarlanırsa ölü sunucuda `/courses` ekranı iki dakika asılı kalır (SC-005 ihlali), (b) 10-15 sn'ye ayarlanırsa ÖLÇÜLMÜŞ 11,7 sn'lik ilk soru ve 19,1 sn'lik ilk yükleme yanlışlıkla kesilir — çalışan sistem bozuk gösterilir; dış incelemenin şikâyeti tam olarak buydu (spec.md:89).

**Elenen seçenekler**: (a) Tek global 30 sn — hem ilk soruyu (11,7 + LLM) keser hem ölü sunucuda 30 sn belirsiz bekleme bırakır; iki ucu da tutmaz. (b) Bütçeyi çağrı yerine parametre olarak zorunlu kılmak — 40+ çağrı yeri, biri unutulduğunda sessizce yanlış bütçe alır; varsayılanı metottan türetmek unutulamaz. (c) Sunucudan `Retry-After`/bütçe okumak — backend böyle bir başlık üretmiyor (errors.py:57-62 yalnız zarf döndürüyor), ölçülmemiş bir mekanizma icat etmek olurdu (Anayasa III).

**Dokunulacak dosyalar**:
- `apps/web/lib/api.ts`

**Risk**: Asılı (bağlantıyı kabul edip cevaplamayan) bir sunucuda okuma merdiveni 12+12+12 sn ≈ 38 sn sürer ve SC-005'in '10 saniyeden uzun BELİRSİZ bekleme' ölçütü ancak 5. karardaki 4 sn'lik soğuk başlangıç notu sayesinde karşılanır — not gösterilmezse bu bütçe SC-005'i ihlal eder. İkinci risk: `llm=120 sn` chat.py:516-528'in yeniden üretim yolunu kapsamıyor; o yolda kullanıcı sunucu hâlâ çalışırken zaman aşımı görür.

---

### 2. 2. Retry (FR-151/152): api.ts'te nereye, hangi metodlar, kaç deneme, jitter, POST dışlaması nasıl zorlanır?

**Karar**: `request()` (api.ts:77-125) ikiye bölünecek: gövde aynen `attempt()` adlı iç fonksiyona taşınacak (fetch + zarf ayrıştırma + ApiError üretimi), `request()` ise onu saran döngü olacak. Yeniden deneme sayısı ÇAĞIRANDAN ALINMAZ; tek satırda metottan türetilir: `const retries = (init?.method ?? "GET") === "GET" ? 2 : 0`. Yani 3 deneme yalnız GET'te. Gecikmeler 500 ms ve 1500 ms (üç kat büyüme), her biri `×(0.75 + Math.random()*0.5)` jitter ile. Yeniden deneme koşulu 3. karardaki `classifyError(e) === "transient"`; kalıcı hata ilk denemede fırlatılır. Ağ/zaman aşımı hataları `attempt()` içinde `ApiError`'a sarılır (`code: "network" | "timeout"`, `status: 0`) — böylece hem sınıflandırıcı hem `errorMessage` tek tip görür.

**Gerekçe**: Dışlamanın zorlanması bir bayrağa değil, isteğin çalışması için ZATEN doğru olmak zorunda olan değere bağlanıyor: HTTP metodu. api.ts:148-162'de `post`/`upload`/`delete` metodu açıkça yazıyor; `get` yazmıyor. Bir geliştirici yanlışlıkla POST'u yeniden denenebilir yapamaz, çünkü açacak bir düğme yok — `retries` hiçbir imzada parametre değil. 1. karardaki bütçe parametresi bilinçli olarak retry bilgisi TAŞIMAZ; bütçeyi genişletmek yeniden denemeyi genişletemez. FR-152'nin gerekçesi kodda görünür: `api.post` ile giden `POST /courses/{id}/chat` (chat.py:655-686) mesajları ve `request_logs`'u YAZDIKTAN sonra yanıt üretir; 5xx'te tekrar göndermek ikinci bir konuşma turu ve ikinci bir LLM faturası üretirdi. Jitter gerekli çünkü ekranlar istekleri demet hâlinde atıyor: app/courses/[courseId]/page.tsx:43-47 ve questions/page.tsx:158-163 `Promise.all` ile iki GET'i aynı milisaniyede başlatıyor, chat/page.tsx:79-89 iki `useResource`'u aynı anda mount ediyor. Jitter'sız merdiven, toparlanmakta olan tek replikalı sunucuya senkron demet vurur. İkinci deneme aynı zamanda ölçülmüş bir kusuru kapatıyor: documents.py:92 ingestion'ı aynı olay döngüsünde tetikliyor (FR-210 henüz açık) ve ilk yükleme döngüyü 19,1 sn bloke ediyor (runbook.md:112); 12 sn'de kesilen ilk okuma, ~12,5 sn'de başlayan ikinci denemeyle 19,1 sn'de gerçekten cevaplanır — kullanıcı hata ekranı görmez (SC-006).

**Elenen seçenekler**: (a) Retry'ı `api.get` sarmalayıcısına koymak — `upload`/`delete`/`post` de `request()`'ten geçtiği için kural iki yerde yaşardı ve ileride eklenecek bir `api.getBlob` sessizce korumasız kalırdı (Anayasa XI). (b) `Policy` nesnesi (`{timeoutMs, retries}`) parametre olarak geçirmek — POST çağrısına `read` politikası verilebilir; tam da yasaklanmak istenen hata. (c) Sabit aralıklı (jitter'sız) retry — FR-151 'artan aralıklarla' diyor, ayrıca eşzamanlı demeti çözmez. (d) İdempotency-Key ile POST retry — backend'de böyle bir mekanizma yok, yeni sunucu işi demek; FR-152 zaten yasaklıyor.

**Dokunulacak dosyalar**:
- `apps/web/lib/api.ts`
- `apps/web/lib/api.test.ts`

**Risk**: En olası kırılma: birisi ileride `api.post`'u `init.method` vermeden çağıran bir yardımcı yazarsa (`request(path, { body })`) metot GET'e düşer ve yazma isteği yeniden denenir. Bunu kapatan tek şey `lib/api.test.ts`'teki test: `fetch` taklidi 503 döndürürken GET 3, POST/DELETE/upload 1 çağrı yapmalı; bu test yoksa kural sessizce çürür. İkinci risk: 429'un yeniden denenmesi (FR-151 istiyor) sunucunun süreç içi sayacını (chat.py:121-151) daha hızlı tüketebilir — bugün yalnız POST /chat sınırlı olduğu için etkisiz, GET uçlarına sınır eklenirse gözden geçirilmeli.

---

### 3. 3. Hata sınıflandırma (FR-153): errors.ts'e eklenecek imza ve sınıflar; ErrorNote bunu nasıl kullanacak, onRetry otomatik türetilirse ne kırılır?

**Karar**: `apps/web/lib/errors.ts`'e eklenecek:
```ts
export type ErrorClass = "transient" | "permanent" | "auth";
export function classifyError(e: unknown): ErrorClass;
export function isTransient(e: unknown): boolean; // classifyError(e) === "transient"
```
Kurallar: `transient` = `status === 0` (code `network`/`timeout`), 408, 429, `status >= 500`; `auth` = 401; `permanent` = diğer tüm ApiError'lar VE ApiError olmayan her değer (fail-closed, Anayasa IV). ErrorNote `onRetry`'ı OTOMATİK TÜRETMEYECEK — `message: string` alıyor (page-state.tsx:38-44) ve string sınıf bilgisi taşımaz; türetmek Türkçe cümleyi ayrıştırmak olurdu. Karar, hata NESNESİNİN hâlâ elde olduğu yerde verilir: `useResource`'un catch'inde (use-resource.ts:231-234). Kanca `settled` bayrağının birebir desenini izler (use-resource.ts:203, 208-211): `ResourceAction`'ın `failed` varyantı `{ type: "failed"; message: string; retryable: boolean }` olur, kanca `const [retryable, setRetryable] = useState(false)` tutar ve `Resource<T>`'ye `canRetry: boolean` alanı eklenir. `ResourceState` ÜÇ ALANLI KALIR — use-resource.ts:126-131'in yazılı kararı korunur. ErrorNote'a ayrıca `requestId?: string | null` prop'u eklenir (6. karar).

**Gerekçe**: page-state.tsx:31-36 zaten FR-153'ün mekanizmasını tarif ediyor: 'her hata tekrar denenebilir değildir (ders bulunamadı, yetki yok) ve çalışmayan bir düğme koymak Anayasa XI'in yasakladığı kusurdur'. Eksik olan mekanizma değil, arkasındaki KURAL — bugün her çağrı yeri kendi kanaatiyle karar veriyor. `canRetry`'ın `ResourceState` yerine kancada ayrı state olarak durması icat değil, bu dosyanın kendi çözümünün tekrarı: `settled` tam olarak bu yüzden dışarıda tutuldu ve kararı `isFirstLoadSettled` (use-resource.ts:133-135) saf fonksiyonuna çıkarıldı; `retryable` de aynı şekilde `classifyError` ile DOM'suz sınanabilir. Eylemin genişletilmesi şart, çünkü use-resource.ts:206-207 'her eylem tek kapıdan geçer; bayrak ile durum böylece ayrışamaz' diyor — `setRetryable`'ı catch içinde ayrıca çağırmak o kuralı bozardı.

<<<<<<< HEAD
**Elenen seçenekler**: (a) `Resource.error`'ı `string` yerine nesne yapmak — 14 ErrorNote çağrı yerini ve 9 ekranı birden kırar, hiçbir kazanç yok. (b) ErrorNote'a hata nesnesi geçirmek — aynı 14 çağrı yeri + `errorMessage`'ın tek çözümleme noktası olma iddiası (errors.ts:1-8) delinir. (c) Sınıflandırmayı `api.ts`'te yapıp ApiError'a `retryable` alanı koymak — cazip, ama aynı statünün retry edilebilirliği bağlama göre değişiyor (401 kancada retry değil, oturum tazeleme tetikler); karar sunum katmanına ait, taşıyıcı tipe değil. <!-- docs-check: screens.count = 9 -->
=======
**Elenen seçenekler**: (a) `Resource.error`'ı `string` yerine nesne yapmak — bütün ErrorNote çağrı yerlerini ve ekranları birden kırar, hiçbir kazanç yok. (b) ErrorNote'a hata nesnesi geçirmek — aynı çağrı yerleri + `errorMessage`'ın tek çözümleme noktası olma iddiası (errors.ts:1-8) delinir. (c) Sınıflandırmayı `api.ts`'te yapıp ApiError'a `retryable` alanı koymak — cazip, ama aynı statünün retry edilebilirliği bağlama göre değişiyor (401 kancada retry değil, oturum tazeleme tetikler); karar sunum katmanına ait, taşıyıcı tipe değil.
>>>>>>> 8f13045 (Add privacy-safe AI quality feedback loop)

**Dokunulacak dosyalar**:
- `apps/web/lib/errors.ts`
- `apps/web/lib/errors.test.ts`
- `apps/web/lib/use-resource.ts`
- `apps/web/lib/use-resource.test.ts`
- `apps/web/components/page-state.tsx`
- `apps/web/app/courses/page.tsx`
- `apps/web/app/courses/[courseId]/page.tsx`
- `apps/web/app/courses/[courseId]/questions/page.tsx`
- `apps/web/app/courses/[courseId]/exam/page.tsx`
- `apps/web/app/courses/[courseId]/analytics/page.tsx`

**Risk**: KIRILACAK DOSYALAR (bugün `onRetry`'ı koşulsuz veren yerler, `canRetry ? reload : undefined` olacak): courses/page.tsx:59 ve :90; courses/[courseId]/questions/page.tsx:189 ve :274; courses/[courseId]/exam/page.tsx:152 ve :462; courses/[courseId]/analytics/page.tsx:121 ve :125; courses/[courseId]/page.tsx:57 (yerel `RetryNote`, page-state.tsx:112-122'deki ErrorNote+Button ikilisini üçüncü kez yazıyor — bu geçişte SİLİNİP ErrorNote'a devredilecek, Anayasa XI). Ayrıca `use-resource.test.ts`:154-205 `failed` eylemlerini `{type,message}` ile kuruyor; alan eklenince bu altı test güncellenmeli. En olası kırılma biçimi: birinin `canRetry`'ı geçirmeyi unutması — o ekranda 404'te de 'Tekrar dene' görünmeye devam eder ve kusur sessizdir; bunu yakalayacak tek şey `classifyError`'ın tablo testi değil, ekran başına gözle doğrulama (Anayasa VIII).

---

### 4. 4. use-resource.ts:263-271 sabit 2000 ms polling'e backoff nasıl eklenir, pollWhile/pulse bozulmadan?

**Karar**: `setInterval` kendini yeniden zamanlayan `setTimeout` zinciriyle değiştirilecek: her tur `await reload()` bittikten SONRA bir sonrakini kurar. Ardışık başarısızlık sayacı bir ref'te tutulur (`failStreakRef`), `reload`'un başarı dalında sıfırlanır, hata dalında artırılır (use-resource.ts:230 ve :233, ikisi de `gate.isCurrent(token)` kapısının içinde). Gecikme: `Math.min(intervalMs * 2 ** streak, POLL_MAX_INTERVAL_MS)` ile `POLL_MAX_INTERVAL_MS = 30_000`. Efekt bağımlılıkları (`[shouldPoll, intervalMs, reload]`) ve `shouldPoll = activeByData || pulsing` türevi (use-resource.ts:264-265) AYNEN kalır; temizlik `clearTimeout` + `cancelled` bayrağı olur (zincir await ettiği için sökülmeden sonra bir tur daha zamanlanabilir). `pollWhile` sözleşmesi, `intervalMs` varsayılanı (2000) ve `pulse(6000)` penceresi değişmez.

**Gerekçe**: Bugünkü `setInterval(reload, intervalMs)` (use-resource.ts:269) ölü sunucuya saniyede yarım istek atmayı sonsuza kadar sürdürüyor; FR-156 ve User Story 4 kabul senaryosu 7 tam olarak bunu yasaklıyor. Zincir aynı zamanda `setInterval`'ın ikinci kusurunu kapatıyor: uçuştaki istek bitmeden yeni tur başlatıyor ve asılı sunucuda istek yığıyor — Anayasa XI 'durdurulmayan polling ... kusur sayılır ve düzeltilir' diyor. Sayaç ref'te tutuluyor çünkü state olsaydı her başarısız tur render ve efekt yeniden kurulumu tetikler, bu da zinciri sıfırlardı. Mevcut iki çağrı yeri korunuyor: courses/[courseId]/page.tsx:50-54 (belge işlenirken 2 sn) ve exam/page.tsx:147-148 (`intervalMs: 15000`) — ikincisi için tavan 15→30 sn'de doyar, yani backoff otomatik olarak tabana göre ölçeklenir, ikinci bir sabit gerekmez.

**Elenen seçenekler**: (a) `setInterval`'i tutup aralığı state'e bağlamak — her hata efekti yeniden kurar, zamanlayıcı sıfırlanır ve backoff hiç birikmez. (b) Backoff'u yalnız `activeByData` yoluna uygulayıp `pulse`'ı muaf tutmak — `pulse` zaten 6 sn'lik sonlu bir pencere (use-resource.ts:251-255), muafiyet iki kod yolu yaratır, kazanç yok. (c) Backoff'u `api.ts`'in retry merdivenine bırakmak — o merdiven TEK istek içindir; turlar arası aralığı yönetmez.

**Dokunulacak dosyalar**:
- `apps/web/lib/use-resource.ts`
- `apps/web/lib/use-resource.test.ts`

**Risk**: Cadence anlamı değişiyor: bugün aralık iki BAŞLANGIÇ arası, sonrasında bitiş ile sonraki başlangıç arası. Sıcak okumada fark ihmal edilebilir (runbook.md:109-110: 0,08–0,41 sn), ama `pulse(6000)` penceresinde 2 sn + istek süresi ile 3 tur yerine 2 tur koşabilir; documents yükleme yarışını (use-resource.ts:183-193'te anlatılan ölçülmüş yarış) dar bir şekilde daha az örnekler. Gerekirse çözüm pulse süresini 8000'e çıkarmaktır, backoff'u muaf tutmak değil.

---

### 5. 5. Soğuk başlangıç metni (FR-154): page-state.tsx Loading'e eşik nasıl eklenir; metin runbook'tan birebir alınabilir mi?

**Karar**: Metin runbook.md:123-124'ten BİREBİR ALINAMAZ. Oradaki cümle anlatıcı repliği ve iki engeli var: 'birazdan göreceksiniz' jüriye söylenen bir vaat, ekranda karşılığı yok; ve cümle em dash içeriyor — Anayasa V 'UI metninde em dash kullanılmaz' diyor. Ekran metni şu olacak ve `apps/web/lib/labels.ts`'te yaşayacak: `COLD_START_NOTE = "İlk istek uzun sürebiliyor: çok dilli arama modeli belleğe yükleniyor. Bu tek seferlik; sonraki cevaplar saniyenin altında geliyor."` ile `COLD_START_AFTER_MS = 4000`. `Loading` (page-state.tsx:19-25) durumsuz olmaktan çıkar: `useEffect` + `setTimeout(COLD_START_AFTER_MS)` ile `slow` bayrağı açılır ve etiketin altına `<p className="text-xs text-fg-subtle">{COLD_START_NOTE}</p>` eklenir; dosyanın başına `"use client"` yazılır. Metin `role="status" aria-live="polite"` bölgesinin İÇİNDE kalır, böylece ekran okuyucu yeni bilgiyi duyurur ama uyarı tonu almaz.

**Gerekçe**: FR-154'ün eşiği (4 sn) ve metnin doğruluğu ölçüme dayanıyor: runbook.md:108 ilk soru 11,7 sn (2,1 GB ONNX modelinin yüklenmesi), :109-111 ikinci soru 0,08 sn ve sıcak sorular 0,09–0,41 sn. Yani 'tek seferlik' ve 'sonraki cevaplar saniyenin altında' iddialarının ikisi de ölçülmüş (Anayasa III). Metnin labels.ts'te durmasının sebebi o dosyanın kendi docstring'i: 'Etiket haritaları üç ayrı sayfaya dağılmıştı... kural her dosyada yeniden hatırlanmak zorunda kalırsa er geç biri ...' (labels.ts:1-9) — soğuk başlangıç notu dokuz ekranın hepsini ilgilendiren bir ürün kararı, bileşen içi bir dize değil. Eşiğin `Loading`'in içinde olması gerekiyor çünkü FR-154 'ilk yüklemeler' diyor ve `Loading` tam olarak o konumda çağrılıyor: courses/page.tsx:60, questions/page.tsx:190, chat/page.tsx:215, :268, :342, :386. chat/page.tsx:268 (`Cevap hazırlanıyor…`) en kritik yer: 11,7 sn'lik cezayı gerçekten ödeyen istek odur. `"use client"` eklemek güvenli, çünkü page-state.tsx'in sekiz ithal edenin tamamı zaten client bileşeni.

**Elenen seçenekler**: (a) Ayrı bir `<ColdStartNote/>` bileşeni — her `Loading` çağrı yerinde ikinci bir satır yazmayı gerektirir, sekiz yerde tekrar (Anayasa XI) ve biri unutulduğunda kusur sessiz. (b) Notu opt-in prop'a bağlamak (`<Loading coldStart />`) — aynı unutma riski; dört saniyeden uzun her bekleyiş açıklamayı hak eder, istisna gerekçesi yok. (c) Runbook cümlesini em dash'i noktalı virgüle çevirerek 'birebir' saymak — belge ile ürün arasında birebir olmayan bir alıntı yaratır ve User Story 7 (FR-181) tam da bunu yasaklıyor; iki metnin AYRI olduğunu kabul etmek dürüst olan.

**Dokunulacak dosyalar**:
- `apps/web/components/page-state.tsx`
- `apps/web/lib/labels.ts`
- `apps/web/lib/labels.test.ts`

**Risk**: Not, sebebi ölçülmemiş bir gecikmede de görünür (yavaş ağ, bloke olmuş olay döngüsü — documents.py:92 + FR-210). O durumda ekran yanlış bir açıklama verir. Bu yüzden cümle 'uzun sürebiliyor' ile kesinlik iddia etmiyor; yine de metin 'her zaman model yükleniyor' diye okunursa Anayasa III sınırına yaklaşır. İkinci risk: `Loading` durumsuz bir sunucu bileşeni sanılıp bir gün RSC ağacından ithal edilirse derleme kırılır.

---

### 6. 6. İstek kimliği (FR-155): CORS expose_headers mi, hata zarfında request_id mi?

**Karar**: HATA ZARFINA ALAN EKLENECEK: `{"error": {"code", "message", "request_id"}}`. `main.py`'deki middleware `request.state.request_id = request_id` satırını `call_next`'ten ÖNCE yazar (main.py:63-65 arası); `app_error_handler`, `validation_error_handler` ve `unhandled_error_handler` (errors.py:57, :107, :128) ilk parametreyi `_` olmaktan çıkarıp `request.state`'ten okur ve hem gövdeye hem `X-Request-ID` başlığına koyar. `expose_headers` EKLENMEYECEK. Frontend tarafında `ApiError` dördüncü, isteğe bağlı alan alır (`requestId: string | null`, api.ts:67-75), `errorEnvelope` (api.ts:137-146) `request_id`'yi çözer, `ErrorNote` `requestId` prop'unu `font-mono text-xs` bir satırda gösterir ve kopyalanabilir kılar.

**Gerekçe**: Ölçtüm, tahmin etmedim. Mevcut kodda X-Request-ID başlığı 200 ve 401'de var ama 500'de YOK: `probe` ile `/health/live` → `6d48...`, `/courses` (401) → `9fa9...`, kasıtlı patlatılan uç (500) → `None`. Sebep Starlette'in katman sırası: `add_exception_handler(Exception, ...)` (main.py:86) handler'ı ServerErrorMiddleware'e takıyor ve o katman `request_logging` middleware'inin DIŞINDA; istisna `call_next`'ten fırlıyor, main.py:67'deki başlık satırına hiç ulaşılmıyor. Yani expose_headers seçeneği SC-007'nin 'istisnasız' şartını tam da en çok kimliğe ihtiyaç duyulan yerde — beklenmeyen 500'de — karşılayamaz. Zarf çözümü bu deliği kapatıyor ve `request.state`'in handler'a ulaştığını ayrıca ölçtüm: aynı scope üzerinden kurulan Request nesnesi middleware'de yazılan `request_id`'yi 500 handler'ında okuyabiliyor (probe çıktısı: `500 9f2e... {"error":{...,"request_id":"9f2e..."}}`). İkinci gerekçe: bugün `allow_credentials=False` ve `expose_headers` hiç verilmemiş (main.py:48-57), yani tarayıcıdaki `fetch` X-Request-ID'yi okuyamıyor — arayüz kimliği ZATEN göremiyor. openapi.json'a etkisi: hata zarfı bugün sözleşmede HİÇ YOK (kontrol edildi; `components.schemas` içinde yalnız FastAPI'nin `HTTPValidationError`'ı var, ki o da main.py:85'teki `validation_error_handler` yüzünden artık gerçeği anlatmıyor — contracts/README.md:69-73'teki 'Bilinen istisna' notu bayat). Doğru hamle alanı sessizce eklemek değil, `app/schemas/error.py`'de `ErrorOut` modelini tanımlayıp sekiz router'a `APIRouter(responses={...})` ile bağlamak; zarf böylece ilk kez sözleşmeye girer ve README'nin hata tablosu (contracts/README.md:55-68) `request_id` satırıyla güncellenir. Frontend tipleri için kırılma yok: `request_id` opsiyonel okunur, `ApiError`'ın dördüncü argümanı opsiyoneldir, courses/page.tsx:182'deki `err.status >= 400` kontrolü etkilenmez.

**Elenen seçenekler**: (a) `expose_headers=["X-Request-ID"]` — tek satır, ama 500'de başlık üretilmiyor (ölçüldü) ve SC-007 'istisnasız' diyor; ayrıca proxy'ler başlığı düşürebilir. (b) Her iki yol birden — zarf zaten yeterli; ikinci mekanizma ikinci bakım yüzeyi demek. (c) Kimliği istemcide üretmek (`X-Request-ID` göndermek) — sunucu bunu bugün doğrulamadan kabul ediyor (main.py:63), yani istemci bütün istekleri aynı kimlikle etiketleyip logu kullanılamaz hâle getirebilir; kimliğin sahibi sunucu olmalı.

**Dokunulacak dosyalar**:
- `apps/api/app/main.py`
- `apps/api/app/core/errors.py`
- `apps/api/app/schemas/error.py`
- `apps/api/app/api/*.py`
- `specs/001-course-assistant-mvp/contracts/openapi.json`
- `specs/001-course-assistant-mvp/contracts/README.md`
- `apps/web/lib/api.ts`
- `apps/web/lib/errors.ts`
- `apps/web/components/page-state.tsx`
- `apps/api/tests/test_security.py`

**Risk**: SC-007 'istisnasız' iddiası istemci tarafı hatalarda hâlâ tutmuyor: zaman aşımı ve ağ kopması sunucuya hiç ulaşmaz, ortada kimlik yoktur. Uydurulmuş bir kimlik göstermek Anayasa III ihlali olur; bu yüzden o iki durumda kimlik yerine hata kodu (`timeout`/`network`) gösterilecek ve SC-007 'sunucuya ULAŞAN her hata' diye daraltılmalı. İkinci risk: main.py:63 istemcinin gönderdiği X-Request-ID'yi olduğu gibi hem loga hem zarfa taşıyor; kimlik artık kullanıcıya gösterildiği için bu, log satırına kontrol karakteri enjekte etme yüzeyi hâline gelir — kimlik biçimi doğrulanmalı (yalnız hex/uuid kabul et, aksi hâlde kendi üret).

---

### 7. 7. Sayfalama (FR-160..163): cursor mu offset mi, beş uç için tek desen, geriye uyumluluk, openapi ve 'devamını yükle' nerede yaşayacak?

**Karar**: CURSOR (keyset). Tek desen: `apps/api/app/schemas/page.py`'de generic `Page[T] { items: list[T]; next_cursor: str | None; total: int }`; `apps/api/app/api/deps.py`'ye `SettingsDep`/`SessionDep`'in yanına `PageDep` eklenir (`limit: int = 20`, sunucu `min(limit, MAX_PAGE_SIZE=100)` ile KIRPAR — 422 atmaz, FR-161 'uygular' diyor; `cursor: str | None`). Cursor, sıralama demetinin base64url kodlanmış hâlidir (`<iso_ts>|<uuid>`), opaktır. Beş ucun sıralaması DEĞİŞMEZ SÜTUNA çekilir: `created_at DESC, id DESC` (courses.py:40, documents.py:103, questions.py:145 zaten böyle; chat.py:707 `updated_at DESC`'ten `created_at DESC`'e ÇEVRİLİR). Sohbet mesajları (chat.py:726) `created_at DESC, seq DESC, id DESC` olur — yani 'en yeni önce' — ve istemci gösterim için ters çevirir; böylece 'geriye doğru yükle' (US5 kabul 4) diğer dört listeyle BİREBİR aynı 'devamını yükle' olur, ikinci bir yön kavramı gerekmez. Yanıt şekli: bugün beşi de ÇIPLAK DİZİ dönüyor (openapi.json'da `type: array`, doğrulandı); hepsi aynı commit'te zarfa geçer, ikinci bir şekil DESTEKLENMEZ. Soru havuzu için `QuestionPage(Page[QuestionOut])` alt sınıfı bir alan ekler (`counts: PoolCounts`); alt sınıf deseni bozmaz, uzatır. Frontend: veri tarafı `apps/web/lib/use-paged-resource.ts` (tek kanca; use-resource.ts:52, :97, :133'teki saf çekirdekleri — `createRequestGate`, `resourceReducer`, `isFirstLoadSettled` — yeniden kullanır, kancayı ÇATALLAMAZ), sunum tarafı `components/page-state.tsx` içinde `LoadMore` bileşeni (düğme + 'Tümü yüklendi' + sayfa hatasının satır içi ErrorNote'u).

**Gerekçe**: Offset elenir çünkü FR-162 açık: eşzamanlı ekleme sırasında kayıt atlanmamalı/tekrarlanmamalı. Beş listenin dördü `created_at DESC` sıralı (courses.py:40, documents.py:103, questions.py:145) — yeni kayıt listenin BAŞINA girer, dolayısıyla `OFFSET 20` ikinci sayfada bir kaydı ikinci kez gösterir. Keyset'te böyle bir kayma yoktur. `updated_at` bir cursor anahtarı olamaz çünkü satır sayfalar arasında yer değiştirir; chat.py:707'yi `created_at`'e çevirmenin ürün maliyeti düşük, çünkü sohbet kenar çubuğu zaten açık oturumu `aria-current` ile işaretliyor (chat/page.tsx:402) ve açık oturumu localStorage'dan geri açıyor (chat/page.tsx:134-142) — 'en son konuşulan üstte' bilgisi yerini bulmak için yük taşımıyor. FR-163'ün belirlenimci sıralaması `id` eş-bozucusuyla sağlanır; aynı `created_at`'i paylaşan iki satır (chat.py:934-956 aynı turda iki mesaj yazıyor) `seq` ve `id` olmadan sıralanamaz. İki şekilli yanıt seçeneği reddedildi çünkü bu depo aynı kararı yazılı olarak bir kez verdi: api.ts:127-136, iki hata biçimini istemcide tanımayı 'kapanmış bir deliği ikinci kez yamamak' diye niteleyip sunucuda tekleştirdi. Aynı ilke liste zarfı için de geçerli; geriye uyumluluk çıplak diziyi yaşatarak değil, sunucu + openapi.json + `lib/types.ts` + ekranları AYNI commit'te göndererek sağlanır (docs/team/00_TAKIM_KOORDINASYON.md:137 bu kuralı zaten yazıyor). openapi.json elle düzenlenmez; contracts/README.md:114-127 ve 00_TAKIM_KOORDINASYON.md:144-155'teki export komutuyla yeniden üretilir; generic `Page[T]` FastAPI'de `Page_CourseWithRole_` gibi bileşen şemaları üretir. 'Devamını yükle'nin iki parçaya bölünmesi Anayasa XI'in kendi ölçüsüdür: 'bir bileşen kendi veri çekmesini, biçimlendirmesini ve iş kuralını aynı anda taşıyorsa bölünür' (constitution.md:120-122).

**Elenen seçenekler**: (a) Offset/limit — FR-162'yi ihlal eder; ayrıca büyük offset'te SC-008'in sabit süre şartını bozar. (b) `?limit` verilirse zarf, verilmezse dizi — istemcide iki şekil, api.ts:127-136'nın reddettiği desen. (c) Zarfsız, `Link`/`X-Next-Cursor` başlığı — CORS'ta expose gerektirir (main.py:48-57 vermiyor) ve openapi.json'da tiplenemez. (d) `total`'ı hiç döndürmemek — US5'in Bağımsız Testi 'toplam/devam bilgisi taşır' diyor ve questions/page.tsx:194 + :283 `countByStatus` ile dört sayı gösteriyor; toplam olmadan o metrik satırı yalan söylerdi. (e) Mesaj listesini ayrı bir 'ters yön' API'siyle çözmek — beşinci uç için ikinci bir desen demek, XI ihlali.

**Dokunulacak dosyalar**:
- `apps/api/app/schemas/page.py`
- `apps/api/app/api/deps.py`
- `apps/api/app/api/courses.py`
- `apps/api/app/api/documents.py`
- `apps/api/app/api/questions.py`
- `apps/api/app/api/chat.py`
- `specs/001-course-assistant-mvp/contracts/openapi.json`
- `apps/web/lib/types.ts`
- `apps/web/lib/use-paged-resource.ts`
- `apps/web/components/page-state.tsx`
- `apps/web/lib/chat.ts`
- `apps/web/app/courses/page.tsx`
- `apps/web/app/courses/[courseId]/page.tsx`
- `apps/web/app/courses/[courseId]/questions/page.tsx`
- `apps/web/app/courses/[courseId]/chat/page.tsx`

**Risk**: En sinsi kırılma soru havuzunda: questions.ts:265-269 istemci tarafı süzmeyi 'liste zaten tam çekildi' gerekçesiyle yapıyor ve questions.ts:251-255 sayıları yüklenmiş diziden hesaplıyor. Sayfalamayla ikisi de SESSİZCE yanlışa döner — süzgeç ilk 20 kaydın içinde arar, sekme sayıları 'yüklenen kadarını' gösterir. Bu yüzden süzme sunucuya taşınmalı (`?status=`/`?topic_id=` questions.py:123-125'te zaten var) ve sayılar `QuestionPage.counts`'tan okunmalı; bu iki taşıma yapılmazsa eğitmen onaylanmamış soruları göremez ve bunu fark etmez. İkinci risk: chat mesaj sıralamasının tersine çevrilmesi `fromHistory` (lib/chat.ts:253) ve onun testlerini kırar; ters çevirme tek yerde (fromHistory) yapılmazsa döküm sırası ekrandan ekrana ayrışır.

---

### 8. 8. Supabase Auth frontend (FR-170/171): supabase.ts ne yapacak, dev-token fallback nasıl korunur, 401 nereye girer, anahtar yokken nasıl derlenir?

**Karar**: `@supabase/supabase-js` `apps/web/package.json` bağımlılıklarına ŞİMDİ eklenir (anahtarlar sonra gelir) ve PLAN.md'ye 'Teknoloji Kilidi' gereği yazılı gerekçe düşülür. `apps/web/lib/supabase.ts` şunları yapar: (1) `NEXT_PUBLIC_SUPABASE_URL` ve `NEXT_PUBLIC_SUPABASE_ANON_KEY`'i okur, `export const authEnabled = Boolean(url && key)`; (2) istemciyi TEMBEL kurar (`getSupabase(): SupabaseClient | null`) — anahtar yokken `createClient` HİÇ çağrılmaz, dolayısıyla modül ithali patlamaz; (3) `onAuthStateChange` ile erişim jetonunu `TOKEN_KEY`'e, profili `USER_KEY`'e AYNALAR (api.ts:11-12'deki anahtarlar); (4) `signInWithPassword`, `refreshAccessToken`, `signOutRemote` sunar; (5) modül yüklenirken `setUnauthorizedHandler(...)` ile api.ts'e tazeleme geri çağrısını enjekte eder. api.ts'in mevcut sözleşmesi KORUNUR: `getStoredUser` (api.ts:32-44), `signIn` (api.ts:57-60), `signOut` (api.ts:62-65) imzaları ve `DemoUser` adı aynen kalır (`export type DemoUser = SessionUser` takma adıyla). 401 yakalama `request()`'in `!response.ok` dalına, `ApiError` fırlatılmadan hemen önce girer (api.ts:96-103): `status === 401 && !replay` ise enjekte edilmiş `onUnauthorized()` çağrılır; tazeleme başarılıysa istek TEK KEZ tekrarlanır, değilse `signOut()` çalışır. `signOut()` ayrıca bir `window` olayı yayar; `lib/session.ts` bu olaya abone olur ve AppShell'in mevcut yönlendirme efekti (app-shell.tsx:29-31) kullanıcıyı girişe atar. Giriş ekranı (app/page.tsx:17-30) `authEnabled` true iken e-posta/parola formunu, false iken bugünkü iki demo düğmesini gösterir; ikisi asla birlikte görünmez.

**Gerekçe**: Backend ayağı zaten hazır: security.py:140-154 `dev:` önekli jetonu `DEV_AUTH_ENABLED` açıkken kabul ediyor, aksi hâlde `_decode_supabase_token`'a düşüyor; yani gerçek JWT'yi `TOKEN_KEY`'e yazmak backend'de sıfır değişiklik gerektirir. Aynalama kararının sebebi api.ts:78: jeton TEK yerde okunuyor; okuyucuyu değiştirmemek, dev yolunun bugünkü davranışını birebir korur ve istek yolunda hiçbir dal açmaz. 401 tekrarının FR-152'yi ihlal etmemesinin gerekçesi kodda: 401 `get_principal` içinde, uç gövdesi HİÇ çalışmadan fırlatılıyor (deps.py:30-35) — yani yazma gerçekleşmedi, tekrar çift üretim riski taşımaz. Bu, 5xx tekrarından ayrıldığı noktadır ve kod yorumunda böyle yazılmalıdır. Tazeleme geri çağrısının ENJEKTE edilmesi (statik import yerine) 'anahtar yokken de derlenip çalışır' şartının çekirdeği: api.ts supabase'i hiç ithal etmez, varsayılan handler `() => false` döner ve bugünkü davranış (401 → ApiError) aynen korunur; SDK'nın kendisi de anahtarsız derlemede yalnız tip olarak vardır. `NEXT_PUBLIC_*` değişkenleri Next tarafından derleme anında gömülür; yoklukları `undefined` olur, `authEnabled` false olur, `createClient` çağrılmaz — tek çalışma zamanı hatası kaynağı budur ve tembel kurulumla kapatılır. FR-173 için ölçülmüş bir kusur var: `.env.example:25` `SUPABASE_JWT_ISSUER=` diye belgeliyor ama config.py:100 alanı `jwt_issuer` ve alias yok (`SettingsConfigDict(..., extra="ignore")`, config.py:70-74). Doğrudan koşturarak doğrulandı: `SUPABASE_JWT_ISSUER` verildiğinde `jwt_issuer = None`, `JWT_ISSUER` verildiğinde dolu. Yani belgedeki ad SESSİZCE yok sayılıyor — User Story 6 kabul senaryosu 4'ün birebir tarifi. Düzeltme: `jwt_issuer` alanına `validation_alias=AliasChoices("SUPABASE_JWT_ISSUER", "JWT_ISSUER")`.

**Elenen seçenekler**: (a) `request()`'in jetonu enjekte edilen bir sağlayıcıdan alması — api.ts:78'i ve dolayısıyla dev yolunu da değiştirir; aynalama daha az yüzey değiştirir. (b) Supabase'i api.ts'te statik ithal etmek — SDK her paket parçasına girer ve anahtarsız ortamda `createClient` ithal anında patlar. (c) 401'de doğrudan `router.push` — `lib/api.ts` bir React modülü değil; yönlendirmeyi oraya koymak session.ts'in 'tek kaynak' iddiasını (session.ts:6-16) ve app-shell.tsx:24-31'in tek yönlendirme noktasını bozardı. (d) Kendi GoTrue REST çağrılarımızı yazmak — Teknoloji Kilidi'nden kaçınır ama tazeleme zamanlayıcısı, eşzamanlı sekme senkronu ve jeton rotasyonunu elde yazmak demek; SDK'yı eklemek daha az risk ve backend zaten aynı sağlayıcıya bağlı (config.py:94).

**Dokunulacak dosyalar**:
- `apps/web/package.json`
- `apps/web/lib/supabase.ts`
- `apps/web/lib/api.ts`
- `apps/web/lib/session.ts`
- `apps/web/app/page.tsx`
- `apps/web/components/app-shell.tsx`
- `apps/api/app/core/config.py`
- `.env.example`
- `PLAN.md`
- `docs/runbook.md`

**Risk**: En olası kırılma iki depolu olmaktan gelir: supabase-js kendi oturumunu kendi anahtarında tutar, biz `TOKEN_KEY`'e aynalarız. `TOKEN_REFRESHED` olayı ile aynalama arasında bir istek geçerse eski jetonla 401 alınır; tasarım bunu tolere ediyor (401 → tazele → tek tekrar), ama aynalama handler'ı bir kez kaçırılırsa kullanıcı sonsuz 401/tazele döngüsüne girebilir — bu yüzden tekrar sayacı `request()` içinde sert biçimde 1 ile sınırlanmalı. İkincisi: `authEnabled` false iken demo düğmelerinin görünmesi, üretim derlemesinde anahtar unutulursa giriş ekranını dev kimliklerine düşürür; sunucu bunu reddeder (security.py:150-151, config.py:256-259) yani güvenlik açığı değil, ama kullanıcıya 401 duvarı gösterir — giriş ekranında `authEnabled=false && production` durumu ayrı ve açık bir mesajla karşılanmalı.

---

## Ders bazlı AI politikası — User Story 3 / FR-130..FR-137 (repo: /Users/muratates/code/dou-lead, dal: 002-production-hardening)

### 1. 1. Politika nerede yaşayacak: courses tablosuna JSONB kolon mu, ayrı course_ai_policies tablosu mu?

**Karar**: Ayrı tablo yazılacak: `course_ai_policies`, birincil anahtarı `course_id uuid PRIMARY KEY REFERENCES courses(id) ON DELETE CASCADE`. Alanların hepsi NULL kabul eder ve NULL "global config'ten oku" demektir: `allowed_modes chat_mode[]`, `max_hints smallint`, `source_document_ids uuid[]`, `evidence_threshold numeric(4,3)`, `daily_token_budget integer`, `updated_at timestamptz NOT NULL DEFAULT now()`. Satırın hiç olmaması FR-136'nın birinci savunması, kolonun NULL olması ikinci savunmasıdır. Değer aralıkları DB CHECK ile bağlanır (`evidence_threshold BETWEEN 0 AND 1`, `max_hints BETWEEN 0 AND 4`, `daily_token_budget > 0`, `array_length(allowed_modes,1) IS NULL OR NOT ('exam' = ANY(allowed_modes))`). Kaynak seti ayrı bir join tablosu DEĞİL, aynı satırda `uuid[]` kolonu olacak. Migration: `supabase/migrations/0008_course_ai_policy.sql`; ORM karşılığı yeni `apps/api/app/models/policy.py` (models/chat.py ve models/assessment.py'nin birebir deseni: migration düz SQL, model onu yansıtır).

**Gerekçe**: JSONB'nin `courses` üzerine konması üç somut engele çarpıyor. (a) Yetki: `0001_core_schema.sql:353-354` `courses_instructor_update ON courses FOR UPDATE USING (app.is_instructor(id))` politikası SATIR düzeyindedir, kolon kısıtı veremez; politika `courses`'a konursa eğitmen aynı UPDATE'le `code`, `title`, `created_by` alanlarına da yazabilir hâle gelir. Bu depo tam olarak bu sorunu bir kez yaşadı ve çözümü kolon bazlı GRANT'ti (`0007_question_delete_and_exam_grants.sql:48-50`: `REVOKE UPDATE ON exam_sessions FROM dou_app; GRANT UPDATE (finished_at) ...`). Ayrı tabloda böyle bir cerrahiye gerek kalmaz: tablonun tamamı zaten politikanın kendisidir. (b) Kısmi güncelleme: JSONB blob'unda tek alanı değiştirmek oku-değiştir-yaz demektir; iki eğitmen farklı alanları aynı anda değiştirdiğinde biri sessizce kaybolur. Tipli kolonda `UPDATE ... SET evidence_threshold = :x` tek kolona dokunur. (c) Doğrulama: JSONB, eşiğin [0,1] içinde olduğunu veya `allowed_modes` içine `exam` sızmadığını veritabanı düzeyinde iddia edemez; bu depoda kural yazılırken CHECK kullanılıyor (`0004_assessment.sql:88-90` `exam_sessions_exam_has_expiry`). Ayrıca JSONB'nin bedeli bu depoda ölçülü: `chat_sessions.state` JSONB olduğu için `socratic.SocraticState.from_json` her okumada bozuk veriye karşı savunma yazmak zorunda (`modules/assessment/socratic.py:234-255`) — dört ayrı çağrı yerinin (mod kapısı, ipucu tavanı, retrieval filtresi, bütçe) hepsinin bu savunmayı hatırlaması gereken bir tasarım Anayasa XI'in tarif ettiği sessiz ayrışmanın ta kendisi. FR-137 denetim izi de ayrı tablodan yana: `to_jsonb(OLD)`/`to_jsonb(NEW)` ile tek satırlık tam anlık görüntü almak, `courses` satırının içinden bir jsonb alanını ayıklamaktan hem basit hem kaçırılamaz. Kaynak setinin join tablosu yerine `uuid[]` olmasının gerekçesi de bu: tek trigger tüm politikayı tek anlık görüntüde yakalasın; ayrı join tablosu ikinci bir trigger ve araya karışabilen iki denetim satırı demekti. `uuid[]` bu depoda FK'sız kullanılan yerleşik bir desen — `exam_sessions.question_ids uuid[] NOT NULL` (`0004_assessment.sql:86-87`) ve gerekçesi orada yazılı. FK yokluğunun riski burada yapısal olarak sönüyor: silinen belgenin chunk'ları `ON DELETE CASCADE` ile gidiyor (`0001_core_schema.sql:240`), dolayısıyla dizide kalan ölü kimlik hiçbir satırla eşleşmez; okuma ucu diziyi canlı `documents` satırlarına karşı süzerek döner, ayrı bir temizlik adımına gerek kalmaz.

**Elenen seçenekler**: (a) `courses.ai_policy jsonb` kolonu — elendi: mevcut `courses_instructor_update` politikası kolon kısıtı veremediği için eğitmene ders kodu/başlığı üzerinde istenmeyen yazma yetkisi açar, kısmi güncellemede son-yazan-kazanır, CHECK ile doğrulanamaz. (b) `course_ai_policies` + ayrı `course_ai_policy_documents` join tablosu — elendi: FK bütünlüğü kazandırır ama FR-137 için ikinci bir trigger ve iki ayrı denetim satırı doğurur; kaynak setinin "hiç ayarlanmamış" ile "bilerek boşaltılmış" ayrımını da tek yerde tutamaz (satır yokluğu iki anlama gelir). `uuid[]`'de NULL = tüm ders, `'{}'` = bilerek boş; şartnamenin 215. satırındaki kenar durumu ("politika kaynak setini boşaltırsa her soru kaynak yetersizliğiyle döner") böylece kodlanabiliyor. (c) Politikayı `Settings`'e ders başına sözlük olarak koymak — elendi: `config.py` ortam değişkeninden okur, çalışma zamanında eğitmen tarafından değiştirilemez ve SC-004'ü ("değişiklik ilk istekten itibaren geçerli") karşılayamaz.

**Dokunulacak dosyalar**:
- `supabase/migrations/0008_course_ai_policy.sql`
- `apps/api/app/models/policy.py`
- `apps/api/app/models/__init__.py`
- `apps/api/app/schemas/policy.py`

**Risk**: Yeni tablonun RLS politikaları unutulursa veya yalnız `is_member` ile yazılırsa öğrenci kendi dersinin politikasını gevşetebilir. Karşılığı: SELECT `app.is_member(course_id)` (arayüzün kilitli sekmeyi çizebilmesi için üyeye açık), INSERT/UPDATE `app.is_instructor(course_id)` — ve `0002`/`0004` gibi FORCE ROW LEVEL SECURITY. İkinci risk: `0008` yazılırken `ALTER DEFAULT PRIVILEGES` mirası unutulup elle GRANT yazılması; `0001_core_schema.sql:315-316` zaten yeni tablolara dou_app/dou_worker yetkisini otomatik veriyor, elle ikinci bir GRANT yazmak sapma üretir.

---

### 2. 2. FR-136: politikası olmayan ders bugünkü davranışla çalışmalı. NULL = global config'ten oku deseni nerede uygulanacak, tek çözümleyici fonksiyon (Anayasa XI) nereye konacak?

**Karar**: Tek çözümleyici `apps/api/app/modules/policy/service.py` içinde yaşayacak: `async def resolve_policy(session, *, course_id, settings=None) -> CoursePolicy`. Döndürdüğü `CoursePolicy` frozen dataclass'ında HİÇBİR alan Optional-varsayılan taşımaz — her değer çözülmüş hâliyle gelir: `allowed_modes: frozenset[ChatMode]`, `max_hints: int`, `source_document_ids: frozenset[UUID] | None` (None = tüm ders, bilinçli tek istisna ve anlamı "filtre yok"), `evidence_threshold: float`, `daily_token_budget: int | None` (None = sınırsız). Kural: "NULL global demektir" bilgisi bu dosyanın DIŞINDA hiçbir yerde tekrarlanmaz; çağıran taraf `settings.evidence_threshold`'a bir daha bakmaz. Politika satırı hiç yoksa fonksiyon global varsayılanlardan kurulmuş nesneyi döndürür ve bugünkü davranış birebir çıkar. FastAPI ayağı `apps/api/app/api/deps.py`'ye eklenecek üç satırlık bir sarmalayıcıdır: `CoursePolicyDep = Annotated[CoursePolicy, Depends(require_course_policy)]`, gövdesi yalnız `resolve_policy`'yi çağırır. Bağımlılık rota başına opt-in'dir — sohbet ve ipucu uçları ister, belge listeleme istemez. Önbellek KONMAYACAK: SC-004 "değişiklik ilk istekten itibaren sunucu tarafında geçerli" diyor, TTL'li bir önbellek bunu ölçülebilir biçimde bozar.

**Gerekçe**: Desen zaten depoda var ve bir seviye yukarı taşınıyor: `core/config.py:234-248` `_resolve_evidence_threshold`, değer açıkça verilmediyse (`model_fields_set`) sağlayıcıdan çözer ve gerekçesini yazar — "sınıf üzerindeki varsayılan tek bir uzaya aittir ve başka bir uzayda sessizce yanlıştır". Ders bazlı NULL'ın çözümü aynı cümlenin ders ölçeğindeki karşılığıdır ve aynı biçimde TEK yerde yapılmalıdır. Çözümleyici `config.py`'ye konamaz: o dosya veritabanı bilmez ve kendi yorumunda (satır 162-166) beş şeridin aynı dosyaya dokunmasının yarattığı çakışma yüzünden blok blok yazıldığı anlatılıyor; DB sorgusu oraya girerse dosya iki iş birden anlatır. `deps.py`'ye tam gövde konamaz çünkü o dosyanın işi izolasyonun birinci katmanı (`deps.py:1-7`), politika çözümü değil; ama sarmalayıcının orada olması doğru, çünkü "istek başına, sunucuda doğrulanmış ders gerçeği" tam olarak orada kuruluyor (`deps.py:102-115` `require_course_member`). Yeni modülün adı ve yeri `modules/retrieval`, `modules/generation`, `modules/guardrails`, `modules/mastery` ile aynı biçimde — bir modül, bir iş (Anayasa XI ölçüleri). `contracts.py`'ye DOKUNULMAYACAK: o dosyanın kuralı "yalnız takım lideri değiştirir, tek taraflı değişiklik ona karşı yazılmış üç modülü aynı anda kırar" (`contracts.py:8-11`) ve `CoursePolicy` yalnız bu modülün ürettiği bir değer nesnesidir; ayrıca çözümleyici `Settings` ve `AsyncSession` ister, `contracts.py` ise bilinçli olarak hiçbir modüle bağımlı değildir (`contracts.py:11-13`). Fail-closed ayrımı (Anayasa IV): `SocraticState.from_json` bozuk veride merdivenin BAŞINA düşer, yani daha kısıtlayıcı olana (`socratic.py:236-240`). Burada tersi geçerli — sorgu hata verirse global varsayılana düşmek, eğitmenin sıktığı bir dersi gevşetmek olur; bu yüzden istisna yukarı gider (503), sessiz varsayılan YOKTUR. Tipli kolonlar + CHECK sayesinde "bozuk politika satırı" diye bir durum zaten kalmıyor, savunmanın tek yeri yazma anı oluyor.

**Elenen seçenekler**: (a) Her çağrı yerinde `policy.evidence_threshold or settings.evidence_threshold` yazmak — elendi: aynı kural dört yerde tekrarlanır ve Anayasa XI'in tarif ettiği ayrışma başlar ("her dosyada yeniden hatırlanmak zorunda kalan kural er geç ihlal edilir"); `0.0` gibi meşru bir değerin `or` ile yutulması da klasik sessiz hata. (b) Çözümleyiciyi `Settings`'e metot olarak eklemek — elendi: `Settings` DB'ye bakamaz ve `get_settings` `lru_cache`'li (`config.py:281-283`), istek başına değişen bir değeri oraya koymak önbelleği yalan söyler hâle getirir. (c) Politikayı istek başına değil süreç ömürlü önbellekte tutmak — elendi: SC-004 ihlali; ayrıca Anayasa III'ün "yavaş olabilir gerekçesiyle karmaşıklık eklenmez" kuralı, ölçülmemiş bir SELECT için önbellek yazmayı yasaklıyor. Sorgu `course_ai_policies` üzerinde birincil anahtarla tek satır.

**Dokunulacak dosyalar**:
- `apps/api/app/modules/policy/__init__.py`
- `apps/api/app/modules/policy/service.py`
- `apps/api/app/api/deps.py`
- `apps/api/tests/test_course_policy.py`

**Risk**: En olası kırılma: yeni bir uç (ör. gelecekteki blueprint akışı) çözümleyiciyi atlayıp doğrudan `settings.evidence_threshold`'u okur ve o uç ders politikasını uygulamaz. Karşılığı, `chat.produce_answer` imzasından `settings: Settings` yerine `policy: CoursePolicy` geçirmek — eşiği artık `settings`'ten okuyamayan bir fonksiyon, yanlışı yazmayı zorlaştırır. İkinci risk: `require_course_policy` `CourseMemberDep`'e bağlı olduğu için ders başına iki sorgu (üyelik + politika) koşar; ölçülmeden bu iki sorgunun tek sorguya birleştirilmesi (JOIN) denenmemeli, çünkü üyelik doğrulamasını politika okumasıyla aynı ifadeye sokmak izolasyonun birinci katmanını okunmaz hâle getirir.

---

### 3. 3. Bugün hangi ayarlar global config.py'de ve bunların hangileri ders bazlı olmalı? Tek tek liste.

**Karar**: DERS BAZLI OLACAK — yalnız üçü, üçü de FR metniyle bire bir eşleşiyor: (1) `evidence_threshold` (config.py:187, FR-133); (2) `socratic_max_stage` (config.py:221, FR-131) — ders değeri `max_hints` adıyla yaşayacak ve global değer artık üst sınırın ÜST SINIRI olacak, çözümleyici `min(ders, global)` uygulayacak; (3) hiçbir global karşılığı OLMAYAN üç yeni alan: `allowed_modes` (FR-130, bugünkü davranış {qa, socratic}), `source_document_ids` (FR-132, bugünkü davranış tüm ders), `daily_token_budget` (FR-134, bugünkü davranış sınırsız). GLOBAL KALACAKLAR ve sebepleri: `environment/api_title/api_version` (76-78) dağıtım kimliği. `database_url/worker_database_url/db_pool_size/db_max_overflow/db_echo` (83-90) altyapı. `supabase_jwt_secret/jwt_audience/jwt_issuer/jwt_algorithms/dev_auth_enabled` (94-105) kimlik — ders başına kimlik sağlayıcısı diye bir şey yok ve `dev_auth_enabled` üretimde yasak (255-263), bu yasak ders başına delinemez olmalı. `cors_origins` (113) dağıtım. `max_upload_bytes` (116), `storage_root` (118), `worker_batch_size` (120) altyapı/kaynak. `embedding_provider/embedding_model/embedding_cache_dir/embedding_batch_size` (138-141) — GLOBAL ZORUNLU, kapsamın en sert kuralı: dosyanın kendi uyarısı "Bu ayar ingest zamanına aittir. Değiştirmek vektör uzayını değiştirir ve tüm korpusun yeniden işlenmesini gerektirir; çalışma zamanı yedeği olarak kullanılamaz" (124-126). `allowed_upload_extensions` (142-154) global. `exam_question_count`, `exam_duration_minutes` (157-158) — ders bazlı olmaları GEREKİR ama BU ALANIN İŞİ DEĞİL: FR-111 bunları blueprint'in alanı olarak sayıyor ("soru başına puan, toplam süre"); AI politikasına da konursa aynı sayı iki yerde yaşar. `question_generation_batch` (159) global (toplu iş boyu). `mastery_alpha` (160) global — EWMA katsayısı bir ölçüm parametresi, ders başına değişirse dersler arası mastery karşılaştırması anlamsızlaşır (Anayasa III). `retrieval_top_k/dense_candidates/fts_candidates/rrf_k` (167-171) global — kalite/gecikme parametreleri; ders başına değiştirmek T043 kalibrasyonunu ders başına geçersiz kılar. `eval_llm_api_key` (192), `worker_drain_secret/url` (198-203) global. `llm_primary_model/llm_fallback_model/groq_api_key/gemini_api_key/llm_timeout_seconds/llm_max_retries/llm_temperature/llm_fake_provider` (207-217) global — sağlayıcı seçimi dağıtım kararı; `llm_fake_provider` üretimde yasak (273-277) ve bu yasağın ders başına delinebilir olması kabul edilemez. `chat_rate_limit_requests/chat_rate_limit_window_seconds` (230-232) GLOBAL KALIR — bu bir kötüye kullanım koruması, pedagojik sınır değil; sayaç zaten süreç içi ve anahtarı ders bazlı (`chat.py:590` `f"{context.user_id}:{context.course_id}"`); FR-134'ün istediği şey istek sayısı değil token bütçesidir, ikisi ayrı büyüklüklerdir. AYRICA EKLENMEYECEK: US3 metnindeki "atıf zorunlu mu" (spec.md:68) bir ayar OLARAK EKLENMEYECEK.

**Gerekçe**: Ders bazlı olacakların listesi keyfi değil, FR-130..FR-134'ün birebir karşılığı; FR listesinde geçmeyen hiçbir ayar ders bazlı yapılmıyor çünkü her ek alan hem yeni bir denetim yüzeyi hem yeni bir varsayılan-çözme dalıdır. Embedding bloğunun global zorunluluğu ölçülmüş bir gerçeğe dayanıyor: `retrieval/dense.py:114-158` `EmbeddingSpaceMismatchError` uyuşmazlıkta 503 döner ve gerekçesi "uyuşmazlık ÇÖKMEZ, yalnızca anlamsız bir sıralama üretir"; aynı veritabanında iki vektör uzayı yaratacak bir ders bazlı sağlayıcı ayarı, eşiği de anlamsızlaştırırdı (`config.py:22-40` sağlayıcı başına eşik tablosu tam olarak bunun için var). Eşiğin ders bazlı olmasının kendisi bir uyarı taşıyor ve şartnameye yazılmalı: `config.py:42-66` üç ayrı ölçümün üç farklı eşik önerdiğini ve eşiğin BUGÜN DEĞİŞTİRİLMEDİĞİNİ, çünkü ölçümlerin `retrieval/scope.py` inmeden önce yapıldığını anlatıyor. Dolayısıyla eğitmenin gireceği sayı KALİBRE EDİLMİŞ bir sayı değildir; arayüz bunu açıkça söylemeli ve bu sayı hiçbir rapora ölçüm diye girmemelidir (Anayasa III). `socratic_max_stage`'in bugün tek kullanıcısı `exams.py:510` (`min(payload.hint_level, settings.socratic_max_stage)`); sohbet merdiveni ise sayıyı `socratic.STAGE_ORDER`'dan türetiyor (`socratic.py:68-79`) ve o modül bilinçli olarak config'e bağımlı değil (76-78: "bağımlı olsaydı saf state machine testleri ayar yüklemek zorunda kalırdı"). Bu ayrım korunuyor; ders değeri iki yere de çözümleyiciden geçiyor. "Atıf zorunlu mu" ayarının reddi Anayasa I'e dayanıyor: "Geçerli atıf kalmadıysa cevap GÖSTERİLMEZ" pazarlık edilmez bir ilkedir ve `chat.py:546-548` bunu kodda zorluyor ("Zincir bloklamasa bile kaynaksız akademik cevap kullanıcıya gitmez"). Bu ilkeyi öğretmenin kapatabileceği bir düğmeye çevirmek, Yönetişim bölümünün deyimiyle önce anayasa değişikliği ister. Ayrıca FR-130..FR-137'de karşılığı olan bir madde yok — yalnız US3 anlatısında geçiyor.

**Elenen seçenekler**: (a) `retrieval_top_k`'yı ders bazlı yapmak ("bazı derslerde daha çok kaynak lazım") — elendi: kanıt kapısı en iyi parçanın `dense_score`'una bakar (`contracts.py:46-51`, `retrieval/service.py:19-33`), top_k'yı büyütmek kapının kararını değiştirmez ama gecikmeyi ve kalibrasyonun geçerliliğini değiştirir; ölçülmeden dokunulacak parametre değil. (b) `llm_primary_model`'i ders bazlı yapmak ("ucuz ders / pahalı ders") — elendi: model başına maliyet ve kalite karşılaştırması dersler arası anlamsızlaşır ve `llm_fake_provider` yasağı ders başına delinebilir hâle gelir. (c) `chat_rate_limit_*`'ı ders bazlı yapmak — elendi: FR-134 token bütçesi istiyor, istek sayısı değil; ikisini birleştirmek "20 istek" ile "200k token" arasındaki ilişkiyi uydurmak olurdu. (d) `exam_duration_minutes`/`exam_question_count`'u buraya almak — elendi: FR-111 blueprint'e veriyor; iki sahiplik = Anayasa XI ihlali.

**Dokunulacak dosyalar**:
- `apps/api/app/core/config.py`
- `apps/api/app/modules/policy/service.py`
- `apps/api/app/schemas/policy.py`
- `specs/002-production-hardening/plan.md`

**Risk**: En olası kırılma: eğitmen `evidence_threshold`'u ölçmeden yükseltir ve ders "hiçbir soruyu cevaplamıyor" hâline gelir — `config.py:174-186` bunun canlı koşuda birebir yaşandığını yazıyor (hashing uzayında 0.81 her soruyu reddediyordu). Karşılığı: eğitmen panelinde son N isteğin `status` dağılımını (`request_logs`, analytics.py'nin zaten okuduğu kaynak) eşik kutusunun yanında göstermek, ve DB CHECK'e ek olarak çözümleyicide değeri global çözülmüş değerin ±0.10 bandına kırpmamak ama uyarıyı yazmak. İkinci risk: `min(ders, global)` kırpmasının `max_hints` için unutulması — o zaman eğitmen 4'ün üstüne çıkarak `_HINT_FRACTIONS` sözlüğünde olmayan bir kademe ister (`exams.py:525`) ve `.get(level, 0.0)` sessizce 1. kademe metnini döner.

---

### 4. 4. FR-132 kaynak seti: retrieval sorgusuna belge filtresi nasıl girecek, dense.py/fts.py'nin course_id deseni ne, performans/indeks etkisi?

**Karar**: Filtre, `course_id` ile TAM AYNI yere ve aynı biçimde girecek. `dense_search` ve `fts_search` imzalarına `document_ids: Sequence[UUID] | None = None` eklenecek ve her iki `_SQL` metninin WHERE'ine tek satır konacak: `AND (NOT CAST(:filter_documents AS boolean) OR c.document_id = ANY(CAST(:document_ids AS uuid[])))`. İki bind parametresi (bayrak + dizi) bilinçli: boş dizi "hiçbir belge" demektir ve filtresizlikten farklıdır. Filtre `HybridRetriever`'a KURUCUDAN geçecek (`__init__(self, session, settings=None, *, document_ids=None)`), `contracts.Retriever` protokolüne DOKUNULMAYACAK. `chat.get_retriever(session)` → `get_retriever(session, policy)` olacak ve `RetrieverFactory` tipi buna göre genişleyecek. Filtre YALNIZ öğrenciye dönen cevap yolunda (chat) uygulanacak; `questions/generate` yolunda uygulanmayacak. YENİ İNDEKS EKLENMEYECEK. Ve kritik yan etki: politika her değiştiğinde o dersin `answer_cache` satırları aynı işlemde silinecek.

**Gerekçe**: Bugünkü desen: `dense.py:91-96` `WHERE c.course_id = :course_id AND c.embedding IS NOT NULL ORDER BY ... LIMIT :limit`, `fts.py:104-106` `WHERE c.course_id = :course_id AND c.fts @@ q.query`; ikisi de `course_id`'yi bind parametresi olarak `HybridRetriever.search`'ten alıyor (`retrieval/service.py:152-163`). Parametreli dal SQL metninin içinde tutmak da yerleşik desen — `fts.py:83-92`'deki `CASE WHEN CAST(:strict AS boolean)` tam olarak bu. Kurucudan geçirme kararının gerekçesi kodda yazılı: "Retriever İSTEK BAŞINA kurulur: `contracts.Retriever` imzasında `session` yoktur, dolayısıyla gerçek uygulama oturumu kendi içinde taşır" (`chat.py:163-165`). Belge filtresinin ömrü oturumunkiyle birebir aynı (istek başına, ders başına), dolayısıyla yeri de aynı. Protokole kwarg eklemek `contracts.py:8-11`'in yasakladığı tek taraflı değişiklik olurdu ve `test_chat_api.py`'deki test ikizleri ile `question_gen.resolve_retriever` dahil üç uygulamayı birden kırardı. Performans, tahmin değil ölçüm: `dense.py:43-52` gerçek materyal yüklü veritabanında alınan planı belgeliyor — `Bitmap Index Scan on chunks_course_idx` + tam sıralama, yani HNSW BUGÜN HİÇ KULLANILMIYOR. Bu planda `document_id = ANY(...)` zaten bitmap'ten gelen az sayıda satır üzerinde bir heap filtresidir; maliyeti ihmal edilebilir. FTS tarafında sıralamayı `chunks_fts_idx` GIN indeksi sürüyor, filtre yine heap üstünde. `chunks` üzerinde `UNIQUE (document_id, chunk_index)` var (`0001_core_schema.sql:256`), yani `document_id` zaten bir indeksin baş kolonu — ihtiyaç doğarsa planlayıcının elinde. Yeni indeks eklenmemesinin gerekçesi Anayasa III: bugünkü plan onu kullanmazdı. Asıl performans riski ileride ve yönü ters: korpus büyüyüp planlayıcı HNSW'ye geçtiğinde filtrelenmiş ANN `ef_search` kadar aday üretip sonra filtreler (`dense.py:40-42`), dar bir belge listesi bu eksik-sonuç riskini BÜYÜTÜR; çaresi de orada yazılı — pgvector 0.8'in `hnsw.iterative_scan`'i (`dense.py:55-56`). Tetik koşulu net: aynı EXPLAIN'de `Bitmap Index Scan` yerine indeks taraması görüldüğü gün. Yetki notu aynen korunmalı: belge filtresi bir yetki belgesi değildir, arama alanını daraltır (`dense.py:58-59` `course_id` için aynı cümleyi kuruyor); kaynak setinden çıkarılan belge öğrenciye `GET /documents` üzerinden hâlâ görünür ve görünmelidir — FR-132 kabul senaryosu "cevap o belgeden atıf içermez" diyor, "öğrenci belgeyi göremez" demiyor. Önbellek kararı bu alanın en sinsi açığını kapatıyor: `answer_cache` ders bazlıdır ve `(course_id, question_hash)` ile aranır (`chat.py:823-834`), politika bilgisi anahtarında YOKTUR; eğitmen kaynak setini daraltsa da eski politika altında üretilmiş cevap servis edilmeye devam eder ve `chat.py:612-629` önbellek isabetinde retrieval'ı hiç koşmaz. Bu doğrudan SC-004 ihlalidir. Silme yetkisi hazır: `answer_cache_instructor_delete ON answer_cache FOR DELETE USING (app.is_instructor(course_id))` (`0003_chat.sql:222-223`).

**Elenen seçenekler**: (a) `contracts.Retriever.search`'e `document_ids` kwarg'ı eklemek — elendi: sözleşme dosyasının değişme maliyeti (üç uygulama + test ikizleri) filtreyi kurucuya koymanın maliyetinden büyük, ve `session`'ın orada olmaması için verilen gerekçe birebir geçerli. (b) Filtreyi `retrieval/service.retrieve()` içinde uygulamak yerine sonuçları Python'da elemek — elendi: `limit` uygulandıktan SONRA elemek, dar bir kaynak setinde top-k'yı boşaltır ve kanıt kapısını sahte biçimde tetikler; filtre SQL'de olmalı ki aday kümesi doğru daralsın. (c) Kaynak setini `chunks` üzerine bir `is_active` kolonuyla ifade etmek — elendi: `chunks` worker'ın yazdığı, RLS'i atlanan bir tablo (`0001:301-310`, `0001:380-382` chunks'ta INSERT politikası yok); politikayı oraya yazmak eğitmen kararını worker yoluna sokar. (d) Filtreyi soru üretimine de uygulamak — elendi (bugün): soru üretimi eğitmenin kendi aracı, kaynağı zaten konu/belge seçimiyle açıkça belirtiyor ve US2 blueprint'i o yüzeyin sahibi olacak. Kayıtlı bedel: kaynak setinden çıkarılmış bir belgeden üretilmiş onaylı soru havuzda kalabilir; öğrenci o soruyu görür ama asistan o belgeden atıf yapamaz.

**Dokunulacak dosyalar**:
- `apps/api/app/modules/retrieval/dense.py`
- `apps/api/app/modules/retrieval/fts.py`
- `apps/api/app/modules/retrieval/service.py`
- `apps/api/app/api/chat.py`
- `apps/api/app/modules/policy/service.py`
- `apps/api/tests/test_retrieval.py`
- `apps/api/tests/test_chat_api.py`

**Risk**: En olası kırılma: kaynak seti bilerek boşaltıldığında (`'{}'`) her soru `insufficient_context` döner ve bu, kanıt kapısının bozulduğu gibi görünür — `config.py:174-186`'daki "bozuk bir sistemin doğru çalışıyor gibi görünmesi" vakasının aynadaki hâli. Karşılığı: `resolve_policy` boş kaynak setini ayrı bir bayrakla taşımalı ve eğitmen paneli bunu uyarı olarak göstermeli (şartname satır 215 bunu zaten istiyor). İkinci risk: `get_retriever` imzası değişince `set_pipeline` ile enjekte edilen test ikizlerinin fabrika imzası uyumsuz kalır (`chat.py:87`, `chat.py:171-181`); `RetrieverFactory` tipi ve `tests/test_chat_api.py` birlikte güncellenmeli, aksi hâlde testler ürün hatası gibi görünen bir TypeError üretir.

---

### 5. 5. FR-130 mod kısıtı: chat.py bugün modu nereden alıyor, politika kontrolü nereye girecek — sınav kilidi kontrolüyle aynı yere mi?

**Karar**: Mod bugün üç yerden geliyor ve sırası önemli: istemciden `payload.mode` (`schemas/chat.py:65`, varsayılan `ChatMode.QA`), `chat.py:582-588`'de `EXAM` reddediliyor, sonra `_load_or_create_session` (`chat.py:768-795`) oturumun modunu sabitliyor ve turun geri kalanı OTURUMUN modunu kullanıyor (`chat.py:688-691`). Politika kontrolü `chat.py:582-588`'deki EXAM reddinin HEMEN ARDINA, hız sınırından (589) ve `_load_or_create_session`'dan (596) ÖNCE girecek — yani belgelenmiş akışın 2. adımı olan "Sınırlar" içine (`chat.py:5-14`). Tek satır: `course_policy.assert_mode_allowed(payload.mode, context)`. Hata tipi yeni bir `CoursePolicyError(AppError)` olacak, `status_code = 403`, kodları `mode_not_allowed` / `hint_limit_reached` / `daily_budget_exhausted`. Kapsam: mod kısıtı ÖĞRENCİYE uygulanır, eğitmene uygulanmaz (`context.is_instructor`, `deps.py:84-86`). Sınav kilidi (FR-101) ile AYNI YERE girer ama AYNI KONTROL DEĞİLDİR: iki ayrı yüklem, tek bir "sınırlar" bloğunda arka arkaya. Arayüzün sekmeyi önceden kilitleyebilmesi için `GET /courses/{course_id}/ai-policy` ucu üyeye açık olacak (çözülmüş politika + kilit sebebi).

**Gerekçe**: Yerin gerekçesi akış sırasının kendisinde yazılı: `chat.py:5-14` sırayı sabitliyor (1 AuthZ, 2 Sınırlar, 3 Önbellek, 4 Retrieval...) ve mod uygunluğu bir sınırdır. `_load_or_create_session`'dan önce olmak zorunda, aksi hâlde reddedilen istek yine de bir `chat_sessions` satırı yaratır (`chat.py:772-781` yeni oturumu flush ediyor) ve öğrenci reddedilirken veritabanında çöp bırakır. EXAM reddinin hemen ardında olması Anayasa XI: "hangi modlar bu istekte açık" sorusunun tek bir bloğu olur; ayrı yerlere serpilirse iki kural birbirinden ayrışır — ki şartnamenin çıkış gözlemi (spec.md:19) tam olarak bu: "Kural mod eksenine yazılmış, durum eksenine yazılmamış". Sınav kilidiyle aynı blokta ama ayrı yüklem olmasının sebebi ikisinin farklı şeye bakması: FR-101 öğrencinin YÜRÜYEN sınav oturumuna bakar (bitmemiş + süresi dolmamış), veritabanı saatini ister (`exams.py:18-21` "Saat veritabanınındır") ve zamana bağlıdır (FR-104); FR-130 ise ders satırına bakar, zamansızdır. İkisini tek fonksiyona sıkıştırmak, birinin DB saati ihtiyacını diğerine bulaştırır. 403 seçimi: istek biçimsel olarak geçerli, ders yasaklıyor — `exams.py:490-492` sınav modunda ipucu reddi için zaten `PermissionDeniedError` (403) kullanıyor. Ama ayrı `code` şart: `errors.py:57-62` zarfı `{"error": {"code", "message"}}` üretiyor ve arayüz kilidi "arıza gibi değil tercih gibi" göstermek zorunda (spec.md:214); `permission_denied` ile `mode_not_allowed` aynı kod olursa arayüz ikisini ayıramaz. Eğitmen muafiyeti FR-103'ün mantığının aynısı: kısıt öğretilen kişiyi hedefler, öğretmen kendi kurduğu yapılandırmayı doğrulayabilmelidir; muafiyet olmazsa tüm modları kapatan eğitmen kendi dersini hiç test edemez. Türkçe metin backend'de üretilir (Anayasa V, `chat.py:231-233` "Reddin sözü BİZE aittir"), frontend kendi cümlesini yazmaz.

**Elenen seçenekler**: (a) Kontrolü `_load_or_create_session` içine koymak — elendi: o fonksiyonun işi oturum bulmak/açmak ve mod değiştirmeyi engellemek (`chat.py:789-794`); politika kontrolünü oraya koymak fonksiyonu iki iş anlatır hâle getirir ve yalnız yeni oturumda mı yoksa var olanda mı koştuğu okunmaz olur. (b) Yalnız `payload.mode` yerine oturumun modunu kontrol etmek — elendi: reddedilecek istek yine de oturum yaratır ve `chat.py:688-691`'in "mod oturumundur" kuralı ancak oturum kurulduktan sonra anlamlı; kapı oturumdan önce olmalı. (c) 422 (ValidationError) dönmek, EXAM reddiyle aynı biçimde — elendi: 422 "gönderdiğin veri bozuk" der; burada veri doğru, ders yasaklıyor. Arayüzün kilitli sekme çizmesi için semantik ayrım gerekiyor. (d) Kısıtı yalnız arayüzde uygulamak — FR-135 tarafından açıkça yasak.

**Dokunulacak dosyalar**:
- `apps/api/app/api/chat.py`
- `apps/api/app/modules/policy/service.py`
- `apps/api/app/core/errors.py`
- `apps/api/app/api/policy.py`
- `apps/web/lib/chat.ts`
- `apps/api/tests/test_chat_api.py`

**Risk**: En olası kırılma: eğitmen bir modu kapattığında o modda AÇIK KALMIŞ oturumlar kullanılamaz hâle gelir ve kullanıcı `_load_or_create_session`'ın "Bu oturum farklı bir modda başlatılmış" mesajını (`chat.py:792-794`) görür — yanlış sebep. Karşılığı: politika kapısı oturum yüklemesinden önce koştuğu için doğru mesaj zaten öne geçer; ama testin bunu açıkça sabitlemesi gerekir (kapalı modda AÇIK oturumla istek → `mode_not_allowed`, oturum hata mesajı DEĞİL). İkinci risk: eğitmen muafiyeti `assert_mode_allowed` içinde değil çağrı yerinde yazılırsa, ikinci bir çağrı yeri (ör. ileride bir stream ucu) muafiyeti farklı uygular; muafiyet çözümleyici modülün içinde, tek yerde olmalı.

---

### 6. 6. FR-131 ipucu üst sınırı: sokratik kademe sayısı bugün nerede sabit?

**Karar**: Bugün İKİ ayrı yerde sabit ve ikisi birbirinden habersiz: (1) sohbet merdiveni — `modules/assessment/socratic.py:68-74` `STAGE_ORDER` beş kademe, `socratic.py:79` `MAX_STAGE_INDEX = len(STAGE_ORDER) - 1`; (2) sınav/prova ipucu merdiveni — `core/config.py:221` `socratic_max_stage: int = 4`, tek kullanıcısı `api/exams.py:510` `level = min(payload.hint_level, settings.socratic_max_stage)`, kademe→oran sözlüğü `exams.py:525` `_HINT_FRACTIONS = {1: 0.0, 2: 0.25, 3: 0.5, 4: 1.0}`; arayüzde yankısı `apps/web/lib/exam.ts:296`. FR-131 İKİSİNİ BİRDEN kapatacak, tek sayıyla: `CoursePolicy.max_hints` ("açılış turundan sonra verilebilecek ipucu adedi", 0..4, çözümleyicide `min(ders, settings.socratic_max_stage)`). Sohbet tarafı: `socratic.advance(state, message, *, max_stage_index: int = MAX_STAGE_INDEX)` — saf fonksiyon, config/DB görmez; sınıra ulaşıldığında mevcut "son kademe" dalı (`socratic.py:357-364`) yeniden kullanılır, ek olarak yeni bir `_REFUSAL_HINT_LIMIT` metni `refusal_notice` alanına konur. Çağrı yeri `chat.py:609` `socratic.advance(state, attempt, max_stage_index=policy.max_hints)`. Sınav tarafı: `exams.py:510` `min(payload.hint_level, policy.max_hints)` olur, `settings.socratic_max_stage` üst sınırın üst sınırı olarak yerinde kalır.

**Gerekçe**: İki merdivenin ayrı olması ve tek sayıyla kapatılması FR-131'in tek anlamlı okuması: bugün sohbette 2 ipucuyla sınırlanan öğrenci `POST /exams/{id}/hint` ucundan 4. kademeyi alabilir — bu, US1'in teşhis ettiği kusurun aynı şekli ("kural bir eksene yazılmış, diğerine yazılmamış", spec.md:19). `socratic.py`'nin config'e bağlanmaması korunmalı ve gerekçesi dosyada yazılı: "Bu modül config'e bağımlı değildir — bağımlı olsaydı saf state machine testleri ayar yüklemek zorunda kalırdı" (`socratic.py:76-78`); bu yüzden sınır parametre olarak geçiyor, import olarak değil. Mevcut "son kademe" dalının yeniden kullanılması ikinci kod yolu açmamak için: o dal zaten "kademe ilerlemez, deneme sayacı işler" davranışını uyguluyor (`socratic.py:357-364`); yeni bir dal yazmak aynı davranışın ikinci kopyası olurdu (Anayasa XI). `refusal_notice` mekanizması da hazır ve tam istenen şeyi yapıyor: `chat.py:486-496` `decision.refusal_notice is not None` olduğunda üretimi hiç çalıştırmıyor, aynı kademenin deterministik şablon ipucunu veriyor ve KAYNAK TAŞIYOR (`socratic.template_hint`) — yani FR-013/FR-016 kaynaklı ipucu kuralı sınıra ulaşıldığında da bozulmuyor ve LLM bütçesi ısrarla tüketilemiyor. Sayının anlamını "kademe indeksi" değil "ipucu adedi" olarak tanımlamak, iki merdivenin numaralandırmasının farklı olmasından: sohbette kademeler 0..4 (DIAGNOSE açılış turudur, ipucu değil — `socratic.py:338-344` ilk turun soru olduğunu ve ilerlemediğini yazıyor), sınavda seviyeler 1..4. "Kaç ipucu" tanımıyla `max_hints=2` her iki yüzeyde de ikinci ipucundan sonra durur ve şartnamenin kabul senaryosuyla (spec.md:77 "ipucu üst sınırı 2 → üçüncü ipucunu alamaz") birebir eşleşir. Tek sayı, iki tek satırlık eşleme; iki ayrı sayı olsaydı biri güncellenip diğeri unutulurdu.

**Elenen seçenekler**: (a) `CoursePolicy`'yi `socratic.advance`'e nesne olarak geçirmek — elendi: saf state machine'in `modules/policy`'ye bağımlı hâle gelmesi demek; `socratic.py:76-78`'in gerekçesi (testler ayar/DB yüklemesin) doğrudan çiğnenirdi. (b) Sınırı yalnız `chat.py`'de, `advance` dönüşünü kırparak uygulamak — elendi: `decision.state` yine ilerlemiş kademeyi taşır ve `_record_turn` onu `chat_sessions.state`'e yazar (`chat.py:894`); öğrenci sınırın ötesine "sessizce" ilerlemiş olur, sınır kalkınca birden 4. kademede bulunur. Kırpma state machine'in içinde olmalı. (c) Sınırı yalnız sohbet tarafına uygulamak — elendi: `exams.py:474-515` ikinci bir ipucu yüzeyi ve sınırı delerdi. (d) `_HINT_FRACTIONS`'ı ders bazlı yapmak — elendi: FR-131 adet istiyor, oran değil; oranı ders bazlı yapmak ipucunun ne kadar kaynak açtığını eğitmenin ayarlaması demek ve bunun bir FR karşılığı yok.

**Dokunulacak dosyalar**:
- `apps/api/app/modules/assessment/socratic.py`
- `apps/api/app/api/chat.py`
- `apps/api/app/api/exams.py`
- `apps/api/app/modules/policy/service.py`
- `apps/api/tests/test_socratic.py`
- `apps/api/tests/test_exams.py`
- `apps/web/lib/exam.ts`

**Risk**: En olası kırılma: `max_hints=0` verilen bir derste sohbet Sokratik modu ilk turdan sonra hiç ilerlemez ve öğrenci aynı DIAGNOSE metnini tekrar tekrar alır — kullanıcıya bir arıza gibi görünür. Karşılığı: 0 değeri arayüzde "Sokratik modu kapat" ile eşdeğer sunulmalı ve çözümleyici `max_hints == 0` ise `allowed_modes`'tan `socratic`'i düşürmeli, böylece kapı mod düzeyinde ve anlaşılır bir mesajla kapanır. İkinci risk: `exams.py:510`'da `settings` yerine `policy` kullanılırken `get_settings()` çağrısının (`exams.py:487`) orada kalması; iki kaynak yan yana durursa bir sonraki düzenleme yanlışını seçer.

---

### 7. 7. FR-134 günlük LLM bütçesi: token sayımı bugün nerede yapılıyor (request_logs'ta token_count var mı), bütçe nasıl sayılacak, sıfırlama ne zaman?

**Karar**: Token bugün SAYILIYOR ama kaydedilmiyor: `generation/llm.py:322-328` `_extract_usage` sağlayıcı yanıtından çıkarıyor, `llm.py:129-130` `LlmCompletion.prompt_tokens/completion_tokens` taşıyor, `llm.py:269-279` loglanıyor, sahte sağlayıcı bile tahmin üretiyor (`generation/fake.py:395-396`). Zincir `GenerationService`'te kopuyor: `generation/service.py:156` yalnız `provider, model` alıyor. `request_logs.token_count` kolonu ŞEMADA VAR (`0003_chat.sql:144`, `models/chat.py:106`) ama HER ZAMAN NULL yazılıyor ve sebebi kodda yazılı: `chat.py:680-682` "Token sayısı sözleşmede taşınmıyor; Şerit 2 GeneratedAnswer'a eklerse burası dolar". Karar: teli bağla. `contracts.GeneratedAnswer`'a `prompt_tokens: int = 0` ve `completion_tokens: int = 0` eklenecek (varsayılan 0, yani hiçbir mevcut uygulama kırılmaz); `generation/service.py` bunları dolduracak ve YENİDEN DENEME TURLARINI TOPLAYACAK (`service.py:150-166` döngüsü); `chat.py:682` `token_count=answer.prompt_tokens + answer.completion_tokens` yazacak — önbellek isabetinde ve abstention'da NULL değil 0 (NULL "ölçülmedi", 0 "ölçüldü, LLM çağrılmadı"). Bütçe `request_logs`'tan toplanacak, ayrı sayaç tablosu YOK: `SELECT COALESCE(SUM(token_count),0) FROM request_logs WHERE course_id=... AND created_at >= <gün başı>`. Öğrenci oturumu bu tabloyu OKUYAMAZ, bu yüzden toplam `app.course_tokens_used(p_course_id uuid) RETURNS bigint` — `STABLE SECURITY DEFINER SET search_path = public, app` — fonksiyonundan alınacak. Sıfırlama: takvim günü, `Europe/Istanbul`, veritabanı saatiyle, okuma anında türetilir — zamanlanmış iş YOK. Kapı `chat.py`'de hız sınırının hemen ardına, önbellek aramasından ÖNCE girer. Bütçe dolduğunda yanıt HATA DEĞİL: 200 döner, `AnswerStatus`'a dördüncü değer `budget_exhausted` eklenir. Kapsam: 002'de yalnız sohbet yolu sayılır; `questions/generate` sayılmaz.

**Gerekçe**: Sayacın `request_logs` olması, ikinci bir doğruluk kaynağı yaratmamak için (Anayasa XI): tablo zaten ders bazlı, zaten her sohbet turunda yazılıyor (`chat.py:669-686`) ve sorgunun tam ihtiyacı olan indeks orada — `request_logs_course_idx ON request_logs (course_id, created_at DESC)` (`0003_chat.sql:149`). Yeni indeks gerekmez. SECURITY DEFINER fonksiyon kararı bu alanın en kolay atlanacak fail-open'ını kapatıyor: `request_logs`'un öğrenciye SELECT politikası YOKTUR — yalnız `request_logs_self_insert` (`0003_chat.sql:234-237`) ve `request_logs_instructor_read` (`0005_analytics.sql`) var; öğrenci oturumunda düz bir SUM sorgusu sıfır satır görür ve bütçe HİÇ TETİKLENMEZ. Fonksiyon deseni bu depoda yerleşik ve gerekçesi yazılı: `app.is_member`/`app.is_instructor`/`app.is_instructor_of` hepsi SECURITY DEFINER ve `0001_core_schema.sql:83-85` sebebini yazıyor — "Fonksiyonlar yalnızca boolean döndürür, satır sızdırmaz". Tek bir bigint için aynı argüman aynen geçerli; 0003 ve 0005'in "öğrenci hiçbir satırı okuyamaz" gizlilik kararı korunur. Takvim günü + veritabanı saati kararı `exams.py:18-21`'in kuralının uzantısı: "Saat veritabanınındır"; istemci saati de uygulama sunucusunun saati de kullanılmaz. Kayan 24 saatlik pencereye tercih edilmesinin sebebi açıklanabilirlik: öğrenciye ve jüriye "her gün 00:00'da sıfırlanır" denebilir, "23:00'da harcadığın 09:00'da hâlâ üstünde" denemez. Sıfırlamanın okuma anında türetilmesi, çalışmadığında sessizce bütçeyi sonsuz yapacak bir cron işini ortadan kaldırır (fail-closed, Anayasa IV). Kapının önbellekten ÖNCE olması bilinçli bir takas: önbellek isabeti token harcamaz, dolayısıyla teknik olarak geçirilebilirdi — ama o zaman bütçesi dolmuş ders bazı sorulara cevap verir bazılarına vermez ve öğrenci için sebepsiz görünür; öngörülebilir bir sınır, biraz daha cömert ama rastgele görünen bir sınırdan iyidir ve deterministik olarak test edilebilir. Hata zarfı yerine 200 dönmesi doğrudan FR-134'ün lafzı ("arıza değil sınır") ve depoda emsali var: `chat.py:568-572` "Abstention bir HATA DEĞİLDİR ... Hata zarfına düşürülseydi istemci bunu bir arıza gibi gösterirdi". Dördüncü statü eklemenin bedeli ölçüldü ve karşılanabilir: `AnswerStatus` bir PG enum'una bağlı (`models/chat.py:104`, `pg_enum(AnswerStatus, "answer_status")`), yani `0008`'de `ALTER TYPE answer_status ADD VALUE 'budget_exhausted'` gerekir (PG16'da işlem içinde eklenebilir, aynı işlemde KULLANILAMAZ — göç yalnız şema tanımlıyor, sorun çıkmaz); ve `chat.py:378-384` `_REFUSAL_TEXT` sözlüğü zaten "yeni bir ret statüsü eklendiğinde burada eksik kalırsa KeyError verir" diye tasarlanmış — yani unutulursa gürültülü patlar. Buna karşılık `analytics.py`'nin SC-005 paydası (`answered_request_count`) tek satırlık bir dışlamayla korunmalı; bütçe reddi bir retrieval kararı değildir ve o oranı kirletemez (Anayasa III). Soru üretiminin kapsam dışı kalmasının somut sebebi şema: `request_logs.mode` NOT NULL `chat_mode` (`0003_chat.sql:140`) ve soru üretimi için doğru bir `chat_mode` değeri yok; kolonu nullable yapmak 002'nin kapsam dondurmasına (17 Ağustos) değmez ve pahalı uç zaten FR-212'nin hız sınırıyla kapatılıyor.

**Elenen seçenekler**: (a) Ayrı `course_token_usage(course_id, usage_date, tokens)` sayaç tablosu ve her istekte upsert — elendi: `request_logs`'un zaten tuttuğu sayı için ikinci doğruluk kaynağı; iki sayı ayrıştığında hangisinin doğru olduğu bilinemez ve toplam zaten indeksli/ucuz. (b) `request_logs`'a üye SELECT politikası açmak — elendi: 0003 ve 0005'in gizlilik kararını bozar ("öğrenci hiçbir satırı okuyamaz"). (c) Bütçeyi istek sayısıyla ölçmek (mevcut `chat_rate_limit_requests`) — elendi: FR-134 açıkça LLM bütçesi diyor; 20 istek ile 200k token arasındaki ilişki uydurma olurdu (Anayasa III). (d) Bütçe dolduğunda 429/403 dönmek — elendi: FR-134 "arıza değil sınır" diyor ve `chat.py:568-572` aynı ayrımı zaten kurmuş. (e) `AnswerStatus`'a dokunmayıp `insufficient_context` ile bildirmek — elendi: yalan etiket; kanıt yeterliydi, harcama sınırı doldu. Ölçüm kategorilerini kirletir. (f) Token'ı `LlmCompletion`'dan doğrudan `chat.py`'ye taşıyacak bir yan kanal — elendi: `chat.py` `LlmClient`'ı hiç görmez, `Generator` protokolünü görür; yan kanal sözleşmenin dışından veri sızdırmak olurdu.

**Dokunulacak dosyalar**:
- `apps/api/app/contracts.py`
- `apps/api/app/modules/generation/service.py`
- `apps/api/app/api/chat.py`
- `supabase/migrations/0008_course_ai_policy.sql`
- `apps/api/app/modules/policy/service.py`
- `apps/api/app/api/analytics.py`
- `apps/api/app/api/policy.py`
- `apps/api/tests/test_generation.py`
- `apps/api/tests/test_chat_api.py`

**Risk**: En olası kırılma: `GenerationService`'in yeniden deneme döngüsünde (`service.py:150-166`) token'ların toplanmak yerine üzerine yazılması — bozuk çıktı yüzünden iki kez çağrılan bir tur bütçeye bir kez sayılır ve bütçe sessizce sızar; bu, ölçülmemiş bir eksik sayımdır ve tam da Anayasa III'ün yasakladığı türden bir sayıyı rapora sokar. İkinci risk: `SECURITY DEFINER` fonksiyonunun `SET search_path` olmadan yazılması — `0001`'deki üç fonksiyonun hepsi `SET search_path = public, app` taşıyor; eksik bırakılırsa yetki yükseltme yüzeyi açılır. Üçüncü risk: `app.course_tokens_used` `dou_app`'e EXECUTE verilmezse (0001:314 yalnız o an var olan fonksiyonları kapsıyor) fonksiyon çalışma zamanında yetki hatası verir — `0008` kendi GRANT'ini yazmalı.

---

### 8. 8. FR-137: politika değişikliğinin denetim izi nasıl tutulacak?

**Karar**: Ayrı, salt-ekleme bir tablo ve onu UYGULAMA KODU DEĞİL BİR TRIGGER dolduracak. `course_ai_policy_events (id uuid PK, course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE, changed_by uuid REFERENCES profiles(id) ON DELETE SET NULL, before jsonb, after jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now())`, indeks `(course_id, created_at DESC)`. Yazan: `AFTER INSERT OR UPDATE ON course_ai_policies FOR EACH ROW` trigger'ı; `changed_by` için `app.current_user_id()`, içerik için `to_jsonb(OLD)` / `to_jsonb(NEW)` — yani DİFF değil TAM ANLIK GÖRÜNTÜ. Satır RETURNING'siz eklenir. RLS: SELECT `app.is_instructor(course_id)`, INSERT WITH CHECK `app.is_instructor(course_id)`, UPDATE ve DELETE politikası YOK. Politikanın tek yazma yolu `apps/api/app/api/policy.py`'deki `PUT /courses/{course_id}/ai-policy` ucudur ve o uç aynı işlemde dersin `answer_cache` satırlarını da siler (bkz. karar 4).

**Gerekçe**: Trigger seçimi Anayasa XI'in doğrudan uygulaması: "her dosyada yeniden hatırlanmak zorunda kalan kural er geç ihlal edilir". Denetim satırını uca yazarsak, ileride politikaya dokunan ikinci bir yol (blueprint akışı, toplu içe aktarma, bir bakım betiği) onu unutabilir ve iz sessizce eksilir; trigger unutulamaz ve programatik değişikliği de yakalar. Trigger aynı işlemde koştuğu için geri alınan bir değişiklik hayalet denetim satırı bırakmaz — `deps.py:46-73`'ün `scope="function"` kararı commit'i yanıttan önceye aldığı için istemcinin gördüğü her yanıt kalıcılaşmış bir işlemi temsil eder, denetim satırı da o işlemin içindedir. `changed_by`'ın güvenilirliği RLS'in kendisinden geliyor: `app.current_user_id()` isteğin GUC'sini okur (`0001_core_schema.sql:24-27`) ve onu `rls_session(principal.user_id)` kurar (`deps.py:40-44`); GUC yoksa politika satırına yazma zaten RLS tarafından reddedilir (fail-closed, `0001:8`), dolayısıyla "kim" alanı gerçek bir yazmada sessizce NULL kalamaz. UPDATE/DELETE politikasının bilinçli yokluğu bu depodaki iki emsalin aynısı: `request_logs` için `0005_analytics.sql` "UPDATE/DELETE politikası hâlâ YOKTUR — ölçüm kaydı sonradan düzeltilebilirse hiçbir şeyin kanıtı olamaz (Anayasa III)", `chat_messages` için `0003_chat.sql:185-187` "sonradan düzeltilebilen bir geçmiş, sistem gerçekten yönlendirdi mi sorusuna kanıt olamaz". `changed_by`'ın `ON DELETE SET NULL` olması FR-202 ile uyum: hesap silinince kanıt silinmemeli; emsali `questions.created_by`/`reviewed_by` (`models/assessment.py:64-70`). Diff yerine anlık görüntü seçimi pratik: "12 Ağustos'ta bu dersin eşiği neydi" sorusu tek satır okunarak yanıtlanır, diff'lerin baştan oynatılmasını gerektirmez; ve kaynak setinin aynı satırda `uuid[]` olarak durması (karar 1) sayesinde tek `to_jsonb(NEW)` politikanın tamamını yakalar. RETURNING'siz ekleme, `chat.py:660-668`'in belgelediği dersin uygulanması: RETURNING RLS altında SELECT politikası ister ve gereksiz yere yüzey genişletir. Ek olarak, `logging.py`'nin maskeleme filtresi (`core/logging.py:41-56`) sayesinde aynı olay yapılandırılmış logda da yankılanabilir (zaman serisi için), tıpkı Sokratik kademe geçişinin iki yere birden yazılması gibi (`chat.py:896-910`) — ama kanıt tablodadır, logda değil.

**Elenen seçenekler**: (a) Denetim satırını `PUT` ucunda uygulama kodundan yazmak — elendi: tek yazma yolu bugün tek, yarın değil; kural kodda hatırlanmak zorunda kalır. Kabul edilen bedel: trigger, uygulamanın görmediği bir yerde iş yapar; bunu telafi etmek için trigger yalnız KAYIT yazar, hiçbir davranış değiştirmez (önbellek temizliği bilerek uca bırakıldı, çünkü o bir davranış yan etkisidir ve okurun uçta görmesi gerekir). (b) Politikanın kendisini sürümlemek (her değişiklik yeni satır, `course_ai_policies` append-only) — elendi: o zaman "geçerli politika" her okumada bir `ORDER BY created_at DESC LIMIT 1` ister; sıcak yol olan `resolve_policy` birincil anahtarla tek satır okuyamaz hâle gelir ve 1:1 bağ ("derse birebir bağlıdır", spec.md:319) yapısal olmaktan çıkar. (c) `courses` üzerinde genel bir denetim tablosu (tüm tablolar için) — elendi: 002'nin kapsamı değil; genel denetim altyapısı yazmak Anayasa VI'nın kapsam kapısına takılır. (d) Yalnız yapılandırılmış loga yazmak — elendi: log rotasyona tabidir ve sorgulanabilir bir kanıt değildir; FR-137 kayıt istiyor.

**Dokunulacak dosyalar**:
- `supabase/migrations/0008_course_ai_policy.sql`
- `apps/api/app/models/policy.py`
- `apps/api/app/api/policy.py`
- `apps/api/app/main.py`
- `apps/api/tests/test_isolation_layers.py`
- `apps/api/tests/test_course_policy.py`

**Risk**: En olası kırılma: trigger fonksiyonunun SECURITY DEFINER olmadan yazılıp `course_ai_policy_events` üzerinde INSERT politikasının eksik/dar kalması — o zaman politikayı değiştirmeye çalışan eğitmenin UPDATE'i, denetim eklemesi RLS'e takıldığı için tümden başarısız olur ve kullanıcı "kaydedilemedi" görür, sebebi görünmez. Karşılığı: INSERT politikası `app.is_instructor(course_id)` ile yazan kişinin yetkisiyle birebir örtüşür ve testte bilerek bozularak (Anayasa II deseni: "RLS'in gerçekten tetiklendiği, politika bilerek bozularak kanıtlanır") kırmızı yandığı gösterilmeli. İkinci risk: `to_jsonb(NEW)` politikaya sonradan eklenecek bir gizli alanı (ör. ileride bir anahtar) denetim tablosuna kopyalar; bu tabloya asla sır konmamalı ve bu kural tablo COMMENT'ine yazılmalı.

---

## Dayanıklılık, veri hijyeni, KVKK, belge tutarlılığı (User Story 7/8/9/10; FR-180..FR-215)

### 1. FR-210 — event loop'u bloke eden senkron embedding çağrıları tam olarak nerede, nasıl sarılacak, parse() de sarılacak mı, bloke olmadığı testte nasıl kanıtlanacak?

**Karar**: Üç çağrı sarılacak, `storage.py`'deki desen birebir uygulanacak. (1) `pipeline.py:79` — `embeddings.extend(provider.embed_documents(batch))` → `embeddings.extend(await asyncio.to_thread(provider.embed_documents, batch))`. Sarma **döngünün içinde, parti başına** yapılacak (77-79 arası döngü korunacak), döngünün tamamı tek `to_thread` içine ALINMAYACAK: parti başına sarma, N partilik bir belgede event loop'a N tane geri dönüş noktası verir; tek sarma yalnız bir tane verir ve `worker_batch_size=5` (config.py:120) ile beş belge arka arkaya işlenirken loop yine uzun aralıklarla susardı. (2) `pipeline.py:62` — `parsers.parse(content, row.file_type)` DE sarılacak; PyMuPDF (parsers.py:51) ve python-pptx (parsers.py:83) saf CPU/C işidir ve 20 MB'lık bir PDF'te (config.py `max_upload_bytes`) embedding'den kısa sürmez. `pipeline.py:63` `chunk_blocks` aynı `to_thread` çağrısına parse ile BİRLİKTE alınacak (tek yardımcı fonksiyon: `def _parse_and_chunk(content, file_type) -> tuple[ParsedDocument, list[Chunk]]`), çünkü ikisi arasında await edilecek hiçbir şey yok ve iki ayrı thread sıçraması bedava değil. (3) `dense.py:176` — `get_embedding_provider().embed_query(query)` → `await asyncio.to_thread(get_embedding_provider().embed_query, query)`. Bu üçüncüsü en kritiği: ingestion worker ayrı süreçte koşsa bile sorgu embedding'i **her sohbet isteğinde** API sürecinde koşuyor.

Storage deseni birebir uygulanabilir: `storage.py:50/55/61` üç biçimi de gösteriyor — kapanış (`asyncio.to_thread(_write)`), doğrudan bound method (`asyncio.to_thread(path.read_bytes)`) ve argümanlı çağrı (`asyncio.to_thread(path.unlink, True)`). Yeni bir soyutlama (executor havuzu, `run_in_executor`, ayrı thread pool ayarı) EKLENMEYECEK.

Dürüst sınır raporda yazılacak (Anayasa III): `to_thread` yalnız alttaki iş GIL'i bıraktığında gerçekten serbest bırakır. fastembed/ONNX ve PyMuPDF bırakır; `HashingEmbeddingProvider` (embedding.py:63-94) saf Python'dur ve bırakmaz — ama o sağlayıcı yalnız test ve çevrimdışı geliştirmede kullanılır (config.py:138 varsayılan `hashing`) ve chunk başına mikrosaniyeler sürer.

Test — `tests/test_event_loop_blocking.py`: sahte bir sağlayıcı `embed_documents` içinde `time.sleep(0.4)` yapar (`time.sleep` GIL'i bırakır, yani ONNX çıkarımının dürüst vekilidir). Aynı anda bir prob görevi döngüde `await asyncio.sleep(0.01)` koşup **gerçek geçen süre ile 0.01 arasındaki en büyük farkı** (event loop gecikmesi) ölçer. İddia: `process_document` koşarken ölçülen en büyük gecikme < 100 ms. Testin kırmızı yanabildiği AYNI test içinde kanıtlanır — `flows.spec.ts:799-806`'daki kalibrasyon deseniyle: aynı prob, sağlayıcının senkron çağrısı doğrudan loop üzerinde yapılırken de koşturulur ve o ölçümün > 300 ms OLDUĞU iddia edilir. Böylece prob'un körleşmesi (yanlış yazılmış bir ölçüm her koşuda 0 döndürür) testin kendisi tarafından yakalanır.

**Gerekçe**: Bloke eden satırlar okundu ve ölçüldü: `pipeline.py:77-79` senkron döngü, `dense.py:176` senkron çağrı. Bunların API sürecinde koştuğu kanıtlı — `documents.py:91` `background.add_task(_trigger_worker)`, `documents.py:23-32` `_trigger_worker` → `internal.py:trigger_drain`, ve `internal.py`'de `WORKER_DRAIN_URL` tanımsızsa (yerel + Compose + demo yolu) `await worker.drain()` **süreç içinde** koşuyor; `worker.py:53-61` oradan `run_pending_jobs`'a, o da `process_document`'a gidiyor. Yani spec.md:193'teki "bir öğretmen materyal yüklerken tüm API yanıt vermiyor — sağlık yoklaması dahil" gözlemi bu zincirin sonucudur. `storage.py:10,50,55,61` deseni aynı modülün içinde, aynı sınıfın komşu metotlarında zaten var; farklı bir mekanizma seçmek Anayasa XI'in "aynı davranış üçüncü kez" kuralına ters düşerdi. Testin "kırmızı yanabilme" kanıtı ci.yml'deki RLS adımının (politika bilerek bozulup FAIL beklenmesi) ve `flows.spec.ts:799-806`'daki sayaç kalibrasyonunun aynısıdır — bu depoda ölçüm testleri kendi körlüklerini sınıyor.

**Elenen seçenekler**: (a) Döngünün tamamını tek `to_thread`'e almak — elendi: tek geri dönüş noktası bırakır, `worker_batch_size=5` ile arka arkaya beş belgede loop yine uzun süre susar. (b) `ProcessPoolExecutor` — elendi: model her süreçte yeniden yüklenir (CI'da ölçülen tepe RSS ~GiB mertebesinde, ci.yml "Replika belleği (RSS)" adımı) ve ACA'nın 4 GiB sınırını deler; ayrıca yeni bir çalışma zamanı deseni Teknoloji Kilidi'ne dokunur. (c) `parse()`'ı sarmamak, yalnız embedding'i sarmak — elendi: 20 MB PDF ayrıştırma ölçülmedi ama embedding'den kısa olduğunu varsaymak Anayasa III'e aykırı; sarma bedeli sıfıra yakın. (d) Bloke olmadığını `time.perf_counter` ile toplam süre ölçerek kanıtlamak — elendi: toplam süre `to_thread` ile de aynı kalır, ölçülmesi gereken şey **loop'un cevap verebilirliği**.

**Dokunulacak dosyalar**:
- `apps/api/app/modules/ingestion/pipeline.py`
- `apps/api/app/modules/retrieval/dense.py`
- `apps/api/tests/test_event_loop_blocking.py`

**Risk**: En olası kırılma: `asyncio.to_thread` çağrısı thread'e geçtiği için `contextvars` kopyalanır ama **oturum/RLS bağlamı taşınmaz** — sarılan fonksiyonların içinde veritabanına dokunulmadığından bugün sorun yok, ama ileride `parse` veya provider içine bir DB çağrısı girerse sessizce yanlış bağlamda koşar. İkinci risk: `HashingEmbeddingProvider` GIL'i bırakmadığı için testte kullanılan sahte sağlayıcı `time.sleep` yerine saf Python döngüsü kullanırsa test `to_thread` varken de kırmızı yanar ve düzeltme yanlış yere aranır.

---

### 2. FR-211 — ısıtma lifespan'e nasıl eklenecek, başlangıcı ne kadar yavaşlatır, test ortamında atlanması gerekiyor mu?

**Karar**: Isıtma `main.py:28-37` lifespan'inde **arka plan görevi olarak** başlatılacak, `yield`'den önce `await` EDİLMEYECEK; hazır olup olmadığı `health.py:33 /health/ready` üzerinden bildirilecek. Somut: lifespan `configure_logging()` ve settings okumasından sonra `warmup_task = asyncio.create_task(_warm_embedding())` kurar; `_warm_embedding` içi `await asyncio.to_thread(get_embedding_provider().embed_query, "ısınma")` (FR-210 kararıyla aynı sarma) ve sonucu modül düzeyinde bir `_warmup_state: Literal["warming","ok","failed"]`'e yazar. `yield`'den sonra `warmup_task.cancel()` + `dispose_engine()`. `/health/ready`'nin `checks` sözlüğüne `checks["embedding"] = _warmup_state` eklenir; `warming` ve `failed` durumlarında mevcut `healthy = all(value == "ok" ...)` kuralı zaten 503 döndürür (health.py:47-50) — yani orkestratör (ACA/Compose) ısınma bitmeden trafik yöneltmez, `/health/live` ise (health.py:23, bağımlılıksız) hemen 200 döner ve süreç öldürülmez.

Yavaşlatma: model imaja gömülü (`Dockerfile:75,79,109` — `EMBEDDING_CACHE_DIR=/opt/models`, `bake_embedding_model.py`, `COPY --from=builder /opt/models`), yani ısınma ağ değil disk→RAM işidir. spec.md:89'da ölçülmüş sayı ilk soru 11,7 sn / ilk yükleme 19,1 sn; ısıtma bu cezayı başlangıca taşır, kullanıcıdan alır. `embedding_provider="hashing"` (config.py:138, varsayılan) iken ısınma neredeyse bedavadır.

Test ortamı için AYRI BİR BAYRAK GEREKMİYOR ve eklenmeyecek: `tests/conftest.py:134-140` `client` fixture'ı uygulamayı `ASGITransport(app=app)` ile sürüyor ve httpx'in ASGI taşıyıcısı **lifespan olaylarını hiç göndermez** — yani pytest'te lifespan gövdesi zaten koşmuyor. Üstüne, testlerde sağlayıcı `hashing`'tir (conftest.py:80-91 ortamı `local`'a çeker, config.py:138 varsayılanı `hashing`), yani 2,1 GB model hiçbir koşulda yüklenmez. Operatör kontrolü için tek yeni ayar eklenecek: `Settings.embedding_warmup: bool = True` (config.py'de Embedding bloğuna, satır 138'in yanına) — demo makinesinde ısıtmayı yeniden derlemeden kapatabilmek için, `chat_rate_limit_*` alanlarının (config.py:230-232) aynı gerekçesiyle.

**Gerekçe**: `health.py`'nin modül docstring'i zaten "deploy sonrası duman testi ve demo günü ısıtma isteği bu ucu kullanır" diyor ve `/live` (bağımlılıksız) ile `/ready` (bağımlılıklı) ayrımını kuruyor — ısınma durumu tam olarak `/ready`'nin `checks` sözlüğüne ait bir bağımlılık durumudur; oraya yazmak var olan sözleşmeyi genişletmek, yeni bir uç açmak değil. `yield` öncesi `await` seçilmemesinin sebebi ölçülmüş: 19,1 sn'lik bir başlangıç, ACA'nın startup probe penceresini ve Compose'un healthcheck retry'ını aşabilir ve konteyner sonsuz yeniden başlatma döngüsüne girerdi — bu, çözdüğünden büyük bir arıza olurdu. Testlerin lifespan'i hiç koşturmadığı conftest.py:134-140'tan doğrudan okunuyor; ölçülmemiş bir korkuya ("pytest 2,1 GB indirir") karşı bayrak eklemek Anayasa III'ün yasakladığı şeydir.

**Elenen seçenekler**: (a) `yield`'den önce `await` ile senkron ısıtma — elendi: 19 sn'lik başlangıç startup probe'unu düşürür. (b) `ENVIRONMENT == local` iken ısıtmayı atlamak — elendi: yerel demo tam da ısınmaya en çok ihtiyaç duyan ortam (C planı, Anayasa X). (c) Isıtmayı ilk `/health/ready` çağrısına bağlamak (tembel) — elendi: kimse yoklamazsa hiç ısınmaz, yani vaat koşula bağlı kalır. (d) `pytest` için `EMBEDDING_WARMUP=false` ortam değişkeni zorunlu kılmak — elendi: gereksiz, lifespan testlerde zaten koşmuyor; unutulduğunda kimsenin fark etmeyeceği bir kurulum borcu yaratırdı.

**Dokunulacak dosyalar**:
- `apps/api/app/main.py`
- `apps/api/app/api/health.py`
- `apps/api/app/core/config.py`
- `apps/api/tests/test_health.py`

**Risk**: En olası kırılma: ısınma görevi sessizce patlarsa (`fastembed` import hatası, `/opt/models` eksik) `_warmup_state="failed"` kalır ve `/health/ready` **kalıcı 503** döner; orkestratör sağlıklı bir API'yi trafikten çeker. Bu yüzden `failed` durumu `degraded` olarak raporlanmalı ama 503'e mi yoksa 200'e mi düştüğü bilinçli seçilmeli — fail-closed (Anayasa IV) 503 der, ama embedding olmadan da FTS şeridi çalıştığı için bu tartışmalı; karar 503 yönünde ve gerekçesi kodda yazılmalı.

---

### 3. FR-212 — chat.py'deki limiter sınıfı questions.py'de nasıl KOPYALANMADAN kullanılacak, ortak yer neresi, tahliye edilmeyen deque sızıntısı nasıl düzeltilecek?

**Karar**: `_SlidingWindowLimiter` (chat.py:121-148), modül düzeyindeki örneği (chat.py:151), `reset_rate_limit()` (chat.py:154-156) ve `RateLimitError` (chat.py:104-106) **`apps/api/app/core/` altına taşınacak**: sınıf + tek paylaşılan örnek + reset yardımcısı yeni `app/core/rate_limit.py`'ye, `RateLimitError` ise `app/core/errors.py`'ye (`ConflictError`/`ValidationError` ile aynı blok, errors.py:42-54 deseni — ikinci bir modül aynı hata tipine ihtiyaç duyduğu an hata sözlüğünün tek yeri orasıdır). `chat.py` bunları import edip `__all__` (chat.py:961-971) üzerinden `reset_rate_limit`'i yeniden dışa verecek, böylece mevcut testler kırılmayacak. `core` seçildi çünkü hız sınırı bir alan (domain) kuralı değil, `config`/`errors`/`logging` gibi kesişen altyapıdır; `modules/` altındaki her klasör bir ürün yeteneğine ait.

API değişikliği — kapsam adı ZORUNLU: `allow(scope: str, key: str, *, limit: int, window_seconds: float)`. Tek örnek iki uç tarafından paylaşıldığı için `f"{user_id}:{course_id}"` anahtarı iki uçta çakışırdı ve sohbet kotası soru üretimini sessizce tüketirdi — kapsamı imzada zorunlu kılmak bu hatayı derleme zamanına çeker. Sohbet `allow("chat", f"{ctx.user_id}:{ctx.course_id}", ...)`, soru üretimi `allow("qgen", f"{ctx.user_id}:{ctx.course_id}", ...)`.

Uygulama noktası: `questions.py:154-166` `generate_questions` gövdesinin **ilk** satırı, `settings = get_settings()` (questions.py:167) sonrası, topic doğrulamasından ÖNCE — sınır aşıldığında hiç iş yapılmamalı. Yeni ayarlar `config.py`'de "Sohbet sınırları" bloğunun (config.py:228-232) hemen altına: `question_generation_rate_limit_requests: int = 5`, `question_generation_rate_limit_window_seconds: float = 300.0`. Gerekçe kod yorumunda: bir çağrı `question_generation_batch=5` (config.py:159) taslak üretir, yani tek istek bir sohbet turunun birkaç katı LLM işi demektir.

Sızıntı düzeltmesi: `self._hits: defaultdict[str, deque[float]]` (chat.py:135) anahtarları hiç silinmiyor; her (kullanıcı, ders) çifti için bir deque süreç ömrü boyunca kalıyor. Düzeltme, `allow()` içinde amorti edilmiş süpürme: limiter `self._max_window` (görülen en büyük pencere) ve `self._last_sweep` (monotonic) tutar; `now - self._last_sweep > self._max_window` olduğunda tüm anahtarlar taranıp `not hits or now - hits[-1] > self._max_window` olanlar silinir. Süpürme pencere başına en fazla bir kez koşar (bir ders, 30 öğrenci için dakikada 30 anahtar taraması — ölçülebilir olmayan bir maliyet), böylece her çağrıda O(n) tarama yapılmaz. Test: bir anahtarla `allow` çağır, `time.monotonic` yerine limiter'a enjekte edilebilir bir saat vermek yerine pencereyi 0.05 sn'ye çekip `time.sleep(0.2)` sonrası ikinci bir anahtarla çağır ve `len(limiter._hits) == 1` iddia et.

**Gerekçe**: Anayasa XI: "Aynı davranış üçüncü kez yazılıyorsa ortak bir modüle çıkarılır… Kural, ton ve eşik gibi ürün kararları tek bir sözlükte yaşar". Sınıf zaten `api/chat.py` içinde, yani bir uç dosyasının içinde yaşıyor — ikinci uç onu import etmek zorunda kalırsa `questions.py`'nin `chat.py`'ye bağımlı olması gerekirdi, ki bu iki ucu birbirine kilitler. Sızıntının varlığı spec.md:363'te zaten kabul edilmiş ("Sınırlayıcının süreç içi olduğu raporda dürüstçe yazılır ve bellek sızıntısı düzeltilir") ve kodda görünür: chat.py:135 `defaultdict(deque)`, `allow()` yalnız `popleft` ile eski vuruşları atıyor (chat.py:140-141) ama boşalan deque'in anahtarını hiç silmiyor; `reset()` (chat.py:147-148) yalnız testlerde çağrılıyor. `docs/security.md:301` sınırlayıcının süreç içi olduğunu zaten yazıyor, yani dürüstlük kaydı hazır — güncellenecek tek şey satır referansı ve ikinci uç.

**Elenen seçenekler**: (a) `_SlidingWindowLimiter`'ı `questions.py`'ye kopyalamak — Anayasa XI'in adıyla yasakladığı şey. (b) `questions.py`'nin `from app.api.chat import _rate_limiter` yapması — elendi: özel (alt çizgili) bir adı iki uç arasında paylaşmak ve uçlar arası bağımlılık yaratmak; ayrıca kapsam ayrımı yine unutulurdu. (c) `slowapi`/`limits` kütüphanesi — elendi: Teknoloji Kilidi yeni kütüphane için yazılı gerekçe ister ve süreç içi 20 satırlık sayaç bu ölçekte yeterli. (d) Redis tabanlı dağıtık sınır — spec.md:363'te zaten gerekçesiyle ertelenmiş. (e) Sızıntıyı `reset()`'i periyodik çağırarak çözmek — elendi: sayaçları topluca sıfırlamak sınırı fiilen kaldırır. (f) `OrderedDict` + LRU üst sınırı — elendi: sabit bir üst sınır, kalabalık bir sınıfta gerçek kullanıcıların sayaçlarını tahliye ederdi.

**Dokunulacak dosyalar**:
- `apps/api/app/core/rate_limit.py`
- `apps/api/app/core/errors.py`
- `apps/api/app/api/chat.py`
- `apps/api/app/api/questions.py`
- `apps/api/app/core/config.py`
- `apps/api/tests/test_rate_limit.py`
- `docs/security.md`

**Risk**: En olası kırılma: `chat.py`'den taşınan `RateLimitError`'ün import yolu değişince `tests/test_chat_api.py`'nin 429 bekleyen vakaları ya da `__all__` üzerinden `reset_rate_limit` import eden fixture'lar sessizce eski sınıfı yakalar ve testler yeşil kalırken uç yanlış hata kodu döndürür. İkinci risk: `_max_window` süpürme eşiği, iki uç iki farklı pencere kullandığı için (60 sn ve 300 sn) en büyüğüne göre koşar — kısa pencereli sohbet anahtarları 300 sn boyunca bellekte kalır; bu kabul edilebilir ama "sızıntı tamamen kapandı" diye yazılmamalı.

---

### 4. FR-213/214 — ingestion job'ın bugünkü durumları neler, retry sayacı için yeni kolon/migration gerekiyor mu, öğretmen paneli kusurlu işi hangi uçtan görecek?

**Karar**: Bugünkü durumlar: `job_status` ENUM = `pending | processing | completed | failed` (0001_core_schema.sql:270; ayna: models/core.py:52-56). **Retry sayacı için yeni kolon GEREKMİYOR** — `ingestion_jobs.attempt_count` zaten var (0001:275, models/core.py:147), `claim_next_job` her alışta artırıyor (pipeline.py:148-149,153) ve `_fail_job` (pipeline.py:162-187) `MAX_ATTEMPTS = 3` (pipeline.py:29) ile hakkı bitince işi `failed`, belgeyi `documents.status='failed'` + `error_message` yapıyor. Beşinci bir ENUM değeri ("kusurlu") EKLENMEYECEK: `failed` zaten tam olarak o anlamı taşıyor ve yeni değer, `job_status`'u okuyan her yeri değiştirmeyi gerektirirdi.

Eksik olan iki şey ve gerekli tek migration (`0008`):
1. **Artan aralık yok.** `_fail_job` işi anında `pending`'e geri koyuyor (pipeline.py:170-178) ve `claim_next_job`'ın `WHERE status='pending' ORDER BY created_at` sorgusu (pipeline.py:150-152) onu bir sonraki turda alıyor; `worker.py:31 POLL_INTERVAL_SECONDS = 2.0` ile üç deneme ~6 saniyede tükeniyor — FR-213'ün istediği "artan aralık" bugün yok. Düzeltme: `ALTER TABLE ingestion_jobs ADD COLUMN next_attempt_at timestamptz NOT NULL DEFAULT now();` + `claim_next_job` SQL'ine `AND next_attempt_at <= now()` + `_fail_job`'da `next_attempt_at = now() + make_interval(secs => :backoff)` (backoff = `BASE_BACKOFF_SECONDS * 2 ** (attempt-1)`, örn. 5/10/20 sn). Kuyruk indeksi de yenilenmeli: `ingestion_jobs_pending_idx` bugün `(created_at) WHERE status='pending'` (0001:285-286); yeni sıralama anahtarı `(next_attempt_at, created_at) WHERE status='pending'`.
2. **Geçici/kalıcı hata ayrımı yok.** `run_pending_jobs`'ın except bloğu (pipeline.py:219-232) her istisnayı aynı sayıyor; oysa satır 230 zaten `isinstance(exc, AppError)` ayrımını yapıyor — bu ayrım retry kararına da uzatılacak: `AppError` (ör. pipeline.py:66 "Belgeden aranabilir içerik çıkarılamadı" — taranmış PDF) deterministiktir, **hiç yeniden denenmez**, doğrudan `failed`; beklenmeyen istisna (ağ, geçici DB hatası) artan aralıkla denenir.

Öğretmen paneli: **yeni bir uç gerekmiyor, mevcut `GET /courses/{course_id}/documents` (documents.py:98-105) yeterli.** `DocumentOut` (schemas/document.py:13-25) zaten `status` ve `error_message` taşıyor ve `_fail_job` bunları belgeye yazıyor (pipeline.py:180-187). `ingestion_jobs`'a join edilmeyecek — panelin göstereceği her şey belge satırında var. Yeniden çalıştırma için TEK yeni uç: `POST /courses/{course_id}/documents/{document_id}/reprocess` (documents.py'ye, `CourseInstructorDep` ile). Gövdesi: belgeyi `status='uploaded'`, `error_message=NULL` yapar (izin: `documents_instructor_update`, 0001:375), **yeni bir** `ingestion_jobs` satırı INSERT eder (izin: `jobs_instructor_insert`, 0001:392) ve `background.add_task(_trigger_worker)` çağırır — documents.py:85-91'in birebir aynısı. Başarısız job satırı UPDATE EDİLMEZ, silinmez: `ingestion_jobs` üzerinde eğitmene UPDATE politikası yok (0001'de yalnız `jobs_instructor_read` ve `jobs_instructor_insert` var) ve başarısız denemenin izi de bir veridir (questions.py:240'taki "Kayıt silinmez" gerekçesiyle aynı). `process_document` yeniden işlemeye hazır: docstring'i (pipeline.py:42-46) mevcut chunk'ları önce sildiğini söylüyor.

**Gerekçe**: Şemayı ve kodu okuyarak: sayaç ve üst sınır zaten var (0001:275, pipeline.py:29,166), eksik olan yalnız zamanlama ve hata sınıflandırması. Yeni bir ENUM değeri veya ayrı bir "kusurlu işler" ucu açmak, iki yerde aynı bilgiyi (belge durumu ve iş durumu) tutup ayrıştırma riski yaratırdı — Anayasa XI'in tam olarak uyardığı sessiz ayrışma. RLS politikalarının bugünkü kümesi kararı zorluyor: `ingestion_jobs`'ta eğitmen için SELECT ve INSERT var, UPDATE yok (0001:384-399), yani "yeniden çalıştır" ancak yeni satır ekleyerek ifade edilebilir — bu, iki katmanlı izolasyonu (Anayasa II) gevşetmeden çalışan tek yol. Migration'ın gerekçe yazma biçimi 0006 ve 0007'de kurulu (neden bu kolon, neden NOT NULL, neyi kırmıyor) ve 0008 aynı biçimi izleyecek.

**Elenen seçenekler**: (a) `attempt_count` için yeni kolon eklemek — elendi: kolon zaten var, ölçmeden "yok" varsaymak Anayasa III ihlali olurdu. (b) `job_status`'a beşinci değer (`dead_letter`/`kusurlu`) — elendi: `failed` aynı anlamı taşıyor, ENUM genişletmek her okuyucuyu değiştirmeyi gerektirir. (c) Backoff'u kolon yerine `created_at + attempt_count * interval` ile hesaplamak — elendi: `created_at` işin kuyruğa GİRİŞ zamanı, son denemenin zamanı değil; `started_at` ise `processing`'e geçerken yazılıyor ve `pending`'e dönerken temizlenmiyor, yani anlamı belirsizleşirdi. (d) Backoff'u worker döngüsünde `asyncio.sleep` ile uygulamak — elendi: uyuyan worker (ACA scale-to-zero, internal.py docstring) hiç uyanmayabilir; gecikme veriye yazılmalı, sürece değil. (e) Ayrı bir `GET /courses/{id}/ingestion-jobs` ucu — elendi: belge listesi zaten aynı bilgiyi taşıyor. (f) Başarısız job satırını UPDATE ile `pending`'e döndürmek — elendi: RLS politikası yok ve deneme izi silinir.

**Dokunulacak dosyalar**:
- `supabase/migrations/0008_ingestion_backoff_and_course_delete.sql`
- `apps/api/app/modules/ingestion/pipeline.py`
- `apps/api/app/models/core.py`
- `apps/api/app/api/documents.py`
- `apps/api/app/core/config.py`
- `apps/api/tests/test_ingestion.py`
- `apps/web/app/courses/[courseId]/page.tsx`
- `ARCHITECTURE.md`

**Risk**: En olası kırılma: `claim_next_job`'a `AND next_attempt_at <= now()` eklendiğinde mevcut `ingestion_jobs_pending_idx` (0001:285) artık sorguyu karşılamaz ve kuyruk sorgusu seq scan'e düşer — küçük tabloda görünmez, gerçek kullanımda `FOR UPDATE SKIP LOCKED` ile birlikte kilit çekişmesi yaratır. İkinci risk: `AppError`'ün "hiç denenmez" sayılması fazla geniş — bugün `AppError` yalnız içerik hatası için kullanılıyor (pipeline.py:66,82) ama `storage.load` `NotFoundError` (AppError alt sınıfı, errors.py:37) da fırlatabilir ve geçici bir depo arızası kalıcı sayılırdı.

---

### 5. FR-190..192 — mevcut e2e testleri veriyi nasıl oluşturuyor, teardown nereye eklenecek (globalTeardown mu afterAll mı), test verisi hangi desenle işaretlenecek, temizlik komutu nerede yaşayacak ve hangi dili kullanacak?

**Karar**: Bugünkü durum: `flows.spec.ts:94-102` `createCourse()` her vaka için `POST /courses` ile `code = 'E2E' + suffix + base36(Date.now()) + counter`, `title = 'E2E Test Dersi ' + suffix` üretiyor; `materyalliDers()` (flows.spec.ts:221-227) üstüne üye ve PDF ekliyor. Temizlik **bilinçli olarak yok** ve gerekçesi dosyanın başında yazılı (flows.spec.ts:15-17): "silme ucu (ders silme) sözleşmede yok". Yani teardown'ın önündeki engel test tarafı değil, ürün tarafı.

Karar üç parça:
1. **Ürün ucu açılacak:** `DELETE /courses/{course_id}` (courses.py'ye, `CourseInstructorDep`). Gövdesi tek satır: `SELECT app.delete_course(:course_id)`. Fonksiyon `0008` migration'ında SECURITY DEFINER olarak yazılacak ve `app.create_course` (0001:113-133) ile birebir aynı deseni izleyecek: ilk adım yetki kontrolü (`app.is_instructor(p_course_id)` değilse `insufficient_privilege`), sonra sıralı silme. Sıra ZORUNLU çünkü cascade her yere ulaşmıyor: `answers.question_id → questions ON DELETE RESTRICT` (0004:103) ve `questions.source_chunk_id → chunks ON DELETE RESTRICT` (0004:55). Doğru sıra: `exam_sessions` sil (→ `answers` CASCADE, 0004:102) → `questions` sil → `courses` sil (→ documents → chunks → chat_sessions → chat_messages → request_logs → mastery hepsi CASCADE). `courses` üzerinde eğitmen DELETE politikası da yok (0001'de yalnız `courses_member_read` ve `courses_instructor_update`), dolayısıyla SECURITY DEFINER fonksiyon zaten şart.
2. **Teardown `globalTeardown` olacak, `afterAll` değil.** Üç sebep, üçü de `playwright.config.ts`'ten okunuyor: `fullyParallel: true` (satır 41) worker'ları ayrı süreçlere böler ve bir dosyanın `afterAll`'ı başka dosyanın dersini göremez; `retries: 1` CI'da (satır 42) yeniden koşan vaka ikinci bir ders açar ve dosya düzeyi kanca ikisini birden izlemek zorunda kalırdı; FR-190 "test ortada başarısız olsa da temizlik çalışmalı" diyor ve worker çöktüğünde `afterAll` hiç koşmaz, `globalTeardown` koşar.
3. **İşaret ve komut:** işaret bugünkü `E2E` kod öneki resmîleştirilerek kullanılacak — `apps/web/e2e/fixtures.ts` içinde tek bir `export const E2E_COURSE_CODE_PREFIX = "E2E"` ve `createCourse` oradan okuyacak; temizlik de aynı sabiti import edecek, böylece desen iki yerde yazılmayacak (Anayasa XI). Temizlik mantığı `apps/web/e2e/cleanup.ts`'te tek bir `async function temizle({ onayli }: { onayli: boolean })` olarak yaşayacak ve İKİ çağıranı olacak: `apps/web/e2e/global-teardown.ts` (playwright.config.ts'e `globalTeardown` olarak eklenir, `onayli: true`) ve `package.json`'a eklenecek `"e2e:clean": "bun e2e/cleanup.ts"` komutu (varsayılan `onayli: false` = kuru koşu). Kuru koşu FR-191'in "komut ne sileceğini önce göstermelidir" ve spec.md:219'daki "gerçek dersi test dersi sanarsa" kenar durumunun karşılığıdır: silinecek kod+başlık listesi ve sayısı basılır, `--evet` bayrağı olmadan hiçbir şey silinmez; silme sonunda kaç ders silindiği raporlanır (FR-191). Dil **TypeScript/Bun**, çünkü işaretin tek tanımı `e2e/fixtures.ts`'te ve komutun onu import etmesi gerekiyor; ayrı bir Python betiği öneki ikinci kez yazmak zorunda kalırdı. Kimlik: e2e'nin zaten kullandığı dev-auth başlığı (`Bearer dev:<AYSE.id>`, flows.spec.ts:63-65).

`screenshots.spec.ts` DOKUNULMAYACAK: sabit gerçek dersi (`DERS`, screenshots.spec.ts:39) kullanıyor, `E2E` öneki taşımıyor, dolayısıyla temizlik filtresinin dışında kalıyor. `seed_demo.sql` dersleri de `E2E` öneki taşımamalı; komut ilk koşuşta bunu doğrulayacak bir iddia içerecek.

**Gerekçe**: flows.spec.ts:15-17 temizliğin neden yapılmadığını açıkça yazıyor ve tek engel olarak silme ucunun yokluğunu gösteriyor — yani FR-190'ın önündeki iş test değil ürün işi. Silme ucunun açılması aynı anda KVKK'nın §6 satır 140-142'de verdiği "ders silinene kadar" sözünü de tetiklenebilir yapıyor (bkz. KVKK kararı), yani tek uç iki FR ailesini birden kapatıyor. SECURITY DEFINER fonksiyon seçimi uydurma değil: `app.create_course` (0001:113) ve `app.add_member` aynı gerekçeyle (RLS'in tek bir politikayla ifade edemediği çok tablolu işlem) zaten öyle yazılmış; `courses.py:56-58` fonksiyonu `SELECT app.create_course(...)` ile çağırıyor, yeni uç aynı çağrı biçimini kullanacak. RESTRICT zincirinin gerçekliği ölçüldü: 0004:55 ve 0004:103.

**Elenen seçenekler**: (a) Her `test.describe` için `afterAll` — elendi: `fullyParallel` + `retries` altında eksik ve kararsız temizlik üretir. (b) Temizliği psql/superuser ile yapan bir SQL betiği — elendi: iki katmanlı izolasyonun (Anayasa II) yanından dolanan bir yan kanal açar ve testin sildiği yol, ürünün sildiği yolla aynı olmaz. (c) Test verisini ayrı bir veritabanına almak — elendi: e2e'nin amacı gerçek yığını sürmek; ikinci bir veritabanı CI kurulumunu ikiye katlar. (d) `courses` üzerine düz bir `courses_instructor_delete` RLS politikası koyup ORM ile silmek — elendi: RESTRICT zinciri yüzünden tek DELETE yetmiyor, uygulama katmanında sıralı silme yazmak aynı kuralı Python'da tekrar etmek olurdu. (e) Temizlik komutunu Python'da (`apps/api/scripts/`) yazmak — elendi: `E2E` öneki TypeScript tarafında üretiliyor, sabit ikiye bölünürdü.

**Dokunulacak dosyalar**:
- `supabase/migrations/0008_ingestion_backoff_and_course_delete.sql`
- `apps/api/app/api/courses.py`
- `apps/web/e2e/fixtures.ts`
- `apps/web/e2e/flows.spec.ts`
- `apps/web/e2e/cleanup.ts`
- `apps/web/e2e/global-teardown.ts`
- `apps/web/playwright.config.ts`
- `apps/web/package.json`
- `apps/api/tests/test_courses.py`

**Risk**: En olası kırılma: `app.delete_course` SECURITY DEFINER olduğu için `app.is_instructor` kontrolü fonksiyonun İLK adımı olmazsa herhangi bir oturum herhangi bir dersi silebilir — bu, ürünün en yıkıcı yetki açığı olurdu ve RLS onu yakalayamaz (tanım gereği atlanıyor). İkincisi: `globalTeardown` başarısız koşudan sonra da çalıştığı için, bir vaka gerçek bir dersi `E2E` önekiyle açarsa temizlik onu siler; bu yüzden önek eşleşmesi tam önek (`code LIKE 'E2E%'`) olmalı ve komut kuru koşuda listeyi göstermelidir.

---

### 6. FR-200..203 — docs/kvkk.md'nin vaat ettiği haklar tek tek neler, her biri için gereken uç ne, öğretmen hesabı silmedeki FK kısıtı tam olarak nerede ve ne yapılabilir?

**Karar**: **Vaat edilen haklar ve ürün karşılıkları** (kvkk.md §7 satır 158-171 ve §8 satır 180-187):
1. İşlenip işlenmediğini öğrenme / bilgi talep etme / amacı öğrenme / aktarılan üçüncü kişileri bilme → karşılığı metnin kendisidir (§2 tablosu satır 32-44, §5 satır 100-131). **Uç gerekmez.**
2. Eksik/yanlış verinin düzeltilmesi → `profiles_self_update` politikası var (0001:341) ama **uç yok**. Kapsam kararı: 002'de açılmayacak, çünkü ad ve e-posta kimlik sağlayıcısından geliyor (§2 satır 34-35) ve düzeltmenin doğru yeri sağlayıcıdır; metin bunu söyleyecek biçimde düzeltilecek (FR-203).
3. Silinmesini isteme → **iki uç gerekiyor**: (a) `DELETE /courses/{course_id}/chat/sessions/{session_id}` ve `DELETE /courses/{course_id}/chat/sessions` (chat.py'ye, `CourseMemberDep`) — FR-200; (b) `DELETE /me` — FR-202.
4. Verinin dışa aktarılması → `GET /me/export` — FR-201. Yeni bir `app/api/me.py` router'ı açılacak ve `main.py:88-101` listesine eklenecek (kullanıcı-kapsamlı, ders-kapsamlı olmayan tek yüzey; `courses.py` prefix'i `/courses`).
5. Otomatik karara itiraz → karşılığı VAR: mastery puanının resmî not olmadığı ekranda yazıyor ve testle korunuyor (flows.spec.ts:757-758, `/resmî bir not değildir/`). Uç gerekmez.
6. Zararın giderilmesi → hukuki; ürün karşılığı gerekmez.

**FR-200 için migration şart:** `chat_sessions` üzerinde DELETE politikası YOK (0003_chat.sql:171-186'da yalnız `_self_read`, `_self_insert`, `_self_update`). `0008`'e `CREATE POLICY chat_sessions_self_delete ON chat_sessions FOR DELETE USING (user_id = app.current_user_id())` eklenecek. `chat_messages` için ayrı politika gerekmiyor: `chat_messages.session_id → chat_sessions(id) ON DELETE CASCADE` (0003:69) ve cascade referans bütünlüğü tetikleyicisiyle koşar, RLS'e tabi değildir.

**FR-201 dışa aktarma:** tek JSON gövde, `Content-Disposition: attachment`. İçerik: `profiles` satırı + `course_memberships` + `chat_sessions`/`chat_messages` + `exam_sessions`/`answers` + `mastery`. Başkasının verisi iki katmanda engellenir (Anayasa II): oturum zaten `rls_session(principal.user_id)` ile kuruluyor (deps.py:41) ve sorgulara ayrıca `user_id = principal.user_id` yazılır. Asenkron kuyruk (spec.md:217) YAPILMAYACAK; bugünkü hacim için ölçülmemiş bir ölçeğe altyapı eklemek Anayasa III/VI'ya aykırı — sınır raporda yazılacak.

**FR-202 — FK kısıtı tam olarak nerede:** `supabase/migrations/0001_core_schema.sql:59` → `courses.created_by uuid NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT`. Yalnız o değil, üç RESTRICT var: `documents.uploaded_by` (0001:212) ve `topics.created_by` (0004:31). Buna karşılık öğrenci tarafındaki her bağ CASCADE: `course_memberships.user_id` (0001:71), `chat_sessions.user_id` (0003:44), `request_logs.user_id` (0003:138), `exam_sessions.user_id` (0004:77), `mastery.user_id` (0004:128); `questions.created_by/reviewed_by` ise SET NULL (0004:57-58). Sonuç: **öğrenci hesabı silinebilir, ders açmış/materyal yüklemiş/konu açmış öğretmen hesabı silinemez.**

**Ne yapılacak — anonimleştirme (tombstone), FK gevşetilmeden:** `DELETE /me` tek bir yol izler ve role bakmaz: (1) kullanıcının `chat_sessions` satırları GERÇEKTEN silinir (mesajlar cascade ile gider) — FR-200'ün ucuyla aynı fonksiyon çağrılır; (2) `profiles` satırı yerinde bırakılır ama kişisel alanlar temizlenir: `full_name = NULL` (nullable, models/core.py:64), `email = 'silinmis+' || id || '@dou-synapse.invalid'` (UNIQUE olduğu için kimlikle benzersizleştirilir); (3) üyelikler `revoked`'a çekilir. Yazma izinleri: `profiles_self_update` (0001:341) kendi satırını güncellemeye yetiyor; üyelik için `memberships_self_revoke` politikası `0008`'e eklenecek (bugün yalnız `memberships_instructor_update` var, 0001:365). Yanıt gövdesi ne yapıldığını sayarak söyler (kaç sohbet silindi, kaç ders sahipliği devredilmedi) — Acceptance 9.3'ün "ne sessizce başarısız olur ne de dersi ve öğrenci verisini düşürür; ne yaptığını açıkça söyler" şartı budur.

**FR-203 — metin düzeltmeleri:** kvkk.md:182 (§8/1) "Uygulandı" olacak; kvkk.md:184 (§8/3) BUGÜN YANLIŞ — `apps/web/app/kvkk/page.tsx` var ve `screenshots.spec.ts:121` onu çekiyor; satır ikiye bölünecek (sayfa: uygulandı / girişte onay: uygulanmadı). §6 satır 139-142'deki "Hesap silinene… / Ders silinene kadar" ifadeleri, artık gerçek tetikleri olduğu için (DELETE /me, DELETE /courses) doğru hâle gelir; §7'ye düzeltme hakkının kimlik sağlayıcısına ait olduğu eklenir.

**Gerekçe**: Haklar listesi kvkk.md §7'den birebir çıkarıldı; §8'in "uygulanmadı" tablosu spec'in FR-203'ünü doğrudan üretiyor. FK gerçeği greple ölçüldü, tahmin edilmedi: `grep -rn "REFERENCES profiles" supabase/migrations/` üç RESTRICT ve altı CASCADE gösterdi. Anonimleştirme seçimi FR-202'nin lafzından çıkıyor: "ne sessizce başarısız olmalı ne de bağlı veriyi düşürmelidir" — FK'yı SET NULL'a çevirmek bağlı veriyi (dersin kim tarafından açıldığı izini) düşürür, reddetmek ise sessiz olmasa da hakkı hiç karşılamaz; tombstone ikisinin arasındaki tek yol. `chat_sessions`'ta DELETE politikasının yokluğu 0003:171-186'dan doğrudan okundu, yani FR-200 kod değil önce şema işi. Sayfa/metin ayrışması (kvkk.md:184 ↔ app/kvkk/page.tsx) bu şartnamenin US7 tezinin canlı bir örneği ve belge kapısıyla (8. karar) otomatik yakalanacak.

**Elenen seçenekler**: (a) `courses.created_by`'ı `ON DELETE SET NULL` yapmak — elendi: kolon NOT NULL (0001:59), NOT NULL'ı kaldırmak "dersi kim açtı" izini yok eder ve `app.create_course`'un sözleşmesini değiştirir. (b) Hesap silme talebini reddedip yalnız açıklama döndürmek — elendi: KVKK m.11 silme hakkını vaat ediyor ve metin (kvkk.md:139) "hesap silinene kadar" diyor; karşılıksız kalırdı. (c) Öğretmen için dersi başka bir eğitmene devretme akışı — elendi: kapsam dondurma (17 Ağustos) ve ikinci bir sahiplik modeli demek; tombstone aynı hakkı bugünkü modelle karşılıyor. (d) Dışa aktarmayı asenkron iş olarak kurmak — elendi: ikinci bir kuyruk tüketicisi, ölçülmemiş bir ölçek için. (e) `chat_messages`'a ayrı DELETE politikası yazmak — gereksiz: cascade RLS'e tabi değil.

**Dokunulacak dosyalar**:
- `supabase/migrations/0008_ingestion_backoff_and_course_delete.sql`
- `apps/api/app/api/chat.py`
- `apps/api/app/api/me.py`
- `apps/api/app/main.py`
- `apps/api/app/schemas/me.py`
- `docs/kvkk.md`
- `apps/web/app/kvkk/page.tsx`
- `apps/api/tests/test_user_rights.py`

**Risk**: En olası kırılma: `GET /me/export` uygulama katmanı filtresi unutulup yalnız RLS'e güvenilirse, `answer_cache` gibi ders-kapsamlı (kullanıcı-kapsamlı olmayan) bir tablo yanlışlıkla dışa aktarılır ve başka öğrencinin sorusundan üretilmiş cevap kullanıcının dosyasına girer — Acceptance 9.2'nin doğrudan ihlali. İkincisi: tombstone e-postası UNIQUE kısıtını `profiles.id` ile karşıladığı için aynı kullanıcı ikinci kez silinmeyi denerse ikinci UPDATE sessizce başarılı görünür ve "kaç şey silindi" raporu yanıltıcı olur.

---

### 7. FR-215 — güvenlik başlıkları next.config.ts'e mi FastAPI middleware'ine mi, CSP Next.js App Router ile nasıl kurulur, inline script sorunu var mı?

**Karar**: **İkisi de — ama tek sözlük, iki uygulama noktası.** İki ayrı tarayıcı bağlamı var: Next HTML/JS gönderir, FastAPI JSON gönderir; aynı başlık kümesi ikisine de anlamlı değildir.

Web tarafı: başlık değerleri `apps/web/lib/security-headers.ts`'te tek bir dizide tanımlanacak ve `next.config.ts`'in `async headers()` kancasından TÜM rotalara (`source: "/:path*"`) uygulanacak. Kapsam: `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`. `X-Frame-Options` YAZILMAYACAK; karşılığı CSP'nin `frame-ancestors 'none'` direktifidir ve iki yerde aynı kuralı yazmak Anayasa XI'in uyardığı ayrışmadır. CSP gövdesi: `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self' <NEXT_PUBLIC_API_URL>; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'`. `connect-src` API adresini `process.env.NEXT_PUBLIC_API_URL`'den okur — aynı değişkeni `lib/api.ts:9` çalışma zamanında, `next.config.ts` derleme zamanında okur ve ikisi de derlemede gömülür, yani ayrışamaz.

**`proxy.ts` YAZILMAYACAK ve nonce KULLANILMAYACAK.** Bu bilinçli ve gerekçeli bir erteleme, spec.md:359-367'deki "ertelendi" tablosunun deseniyle raporlanacak. Üç sebep: (1) Next 16 App Router üretim çıktısı RSC yükünü inline `<script>` elemanlarıyla gönderir; nonce'suz katı bir `script-src 'self'` uygulamayı KIRAR, yani `'unsafe-inline'` ya da nonce arasında seçim zorunludur. (2) Next'in kendi rehberi nonce için dinamik render şart koşuyor (`node_modules/next/dist/docs/01-app/02-guides/content-security-policy.md`: "you must use dynamic rendering to add nonces"); bu, `app/kvkk/page.tsx`'in derleme zamanında `readFileSync` ile üretilme kararını (page.tsx:22-24, gerekçesi Anayasa XI) iptal eder ve hukuki metni her istekte yeniden ayrıştırır. (3) Kapatılacak XSS yüzeyi zaten iki kez kapalı: React kaçışlaması (`dangerouslySetInnerHTML` hiçbir yerde yok, page.tsx:11-13 bunu açıkça yazıyor) ve guardrail sanitize halkası (docs/security.md:210, `modules/guardrails/sanitize.py`). `'unsafe-inline'` ile bile `frame-ancestors 'none'`, `object-src 'none'`, `base-uri 'self'`, `form-action 'self'` ve daraltılmış `connect-src` gerçek koruma sağlar.

**Dosya adı uyarısı (bu depoya özel):** Next 16'da `middleware.ts` KULLANILMAZ — `node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/middleware.md` "deprecated in Next.js 16 and renamed to proxy.js" diyor. İleride nonce'a geçilirse dosya `apps/web/proxy.ts` olacak. Bu, `apps/web/AGENTS.md`'nin uyardığı "eğitim verisindeki Next bu Next değil" tuzağının birebir örneği.

API tarafı: `main.py`'ye, `request_logging` middleware'inin (main.py:59-80) hemen yanına ikinci bir `@app.middleware("http")` eklenecek: `X-Content-Type-Options: nosniff` (JSON'ın HTML sanılmasını engeller), `Referrer-Policy: no-referrer`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` (API hiçbir alt kaynak yüklemez, dolayısıyla en katı politika bedava). İki middleware ayrı tutulacak, `request_logging`'in içine karıştırılmayacak: biri gözlem, öteki politika.

Test: `apps/api/tests/test_security.py`'ye başlıkların varlığını sınayan vaka; web tarafı için `apps/web/lib/security-headers.test.ts` (bun test, `package.json` "test": "bun test lib/" zaten lib'i koşuyor) CSP dizesinin gerekli direktifleri taşıdığını ve `connect-src`'nin API adresini içerdiğini iddia eder.

**Gerekçe**: İki uygulama noktası, iki farklı yüzeyin gerçeğinden çıkıyor: Acceptance 10.6 "tarayıcı uygulamayı yükler" diyor (Next), ama `docs/security.md`'nin varlığı ve API'nin doğrudan çağrılabilirliği (e2e testleri `fetch` ile API'ye gidiyor, flows.spec.ts:67-84) API yüzeyinin de tarayıcıya değdiğini gösteriyor. Değerlerin tek modülde toplanması Anayasa XI'in "ürün kararları tek bir sözlükte yaşar" kuralı; `DESIGN.md`/`lib/labels.ts` deseninin güvenlik karşılığı. `'unsafe-inline'` kararının dürüstçe raporlanması Anayasa III'ün "garanti sözcüğü yalnız gerçekten deterministik mekanizmalar için" kuralı — nonce'suz bir CSP'yi "XSS koruması var" diye yazmak tam olarak bu projenin kaçındığı iddia türüdür. Next 16 dosya adı değişikliği kaynaktan (paketin kendi dokümanından) doğrulandı, hafızadan yazılmadı.

**Elenen seçenekler**: (a) Yalnız `next.config.ts` — elendi: API JSON yanıtları korumasız kalır ve `nosniff` eksikliği en ucuz gerçek risktir. (b) Yalnız FastAPI middleware — elendi: CSP'nin asıl adresi HTML gönderen sunucudur. (c) `proxy.ts` + nonce + `'strict-dynamic'` — elendi (bugün): tüm sayfaları dinamik render'a zorlar, `/kvkk`'nın derleme zamanı kararını bozar ve kazanç ölçülmemiş. Ertelendiği ve neden ertelendiği raporda yazılacak. (d) `X-Frame-Options` + `frame-ancestors` birlikte — elendi: aynı kural iki yerde. (e) Başlıkları `apps/web/app/layout.tsx`'te `<meta http-equiv>` ile vermek — elendi: `frame-ancestors` ve `report-uri` meta üzerinden çalışmaz, ayrıca yanıt başlığı olmayan CSP kısmi korumadır.

**Dokunulacak dosyalar**:
- `apps/web/next.config.ts`
- `apps/web/lib/security-headers.ts`
- `apps/web/lib/security-headers.test.ts`
- `apps/api/app/main.py`
- `apps/api/tests/test_security.py`
- `docs/security.md`

**Risk**: En olası kırılma: `connect-src 'self' <API_URL>` — e2e paketi web'i 3100'de, API'yi 8000'de koşturuyor (playwright.config.ts:34-36) ve derleme `NEXT_PUBLIC_API_URL`'i build komutuna veriyor; yerel geliştirmede API adresi başka bir porta (ör. önizleme proxy'si :9100, playwright.config.ts docstring'inde anlatılan tuzak) kaydığında tarayıcı istekleri CSP'ye takılır ve hata ürün hatası gibi görünür. İkincisi: `'unsafe-inline'` taşıyan CSP jüriye "CSP var" diye gösterilip raporda sınırı yazılmazsa, bu doğrudan Anayasa III ihlali olur.

---

### 8. FR-180..183 — belge-kod tutarlılığı otomatik olarak NASIL kontrol edilir? Genel bir doğrulayıcı gerçekçi mi, yoksa daha dar bir mekanizma mı? CI'a nasıl bağlanır?

**Karar**: Genel amaçlı, doğal dili koda karşı doğrulayan bir betik gerçekçi DEĞİL ve yazılmayacak. Yerine **üç dar, tamamen mekanik kapı** taşıyan tek bir betik yazılacak: `scripts/docs_check.mjs` (kökte yeni `scripts/` dizini, bağımlılıksız Node ESM — `apps/web/scripts/contrast.mjs`'nin birebir deseni). Betik `--fix` ile düzeltir, bayraksız doğrular ve tutarsızlıkta sıfırdan farklı çıkar.

**Kapı 1 — satır numaralı kod referansları (FR-180, Acceptance 7.3).** `docs/security.md` 20'den fazla `[dosya.py:N](../yol#LN)` bağlantısı taşıyor (satır 21-23, 258, 271, 273, 301) ve ÖLÇÜLDÜ: bayat. `chat.py:567` (security.md:271) bugün `) -> ChatResponse:` satırı; hız sınırı çağrısı gerçekte chat.py:589'da. `config.py:167` (security.md:52) bugün retrieval bloğunun içi; `_check_auth_configuration` gerçekte config.py:255'te. Çözüm satır numarasını doğrulamak değil, **üretmek**: referans biçimi `[\`chat.py:_SlidingWindowLimiter\`](../apps/api/app/api/chat.py#L121)` hâline getirilir; betik bağlantı metninden dosya+sembolü okur, dosyada `^\s*(class|def|async def|[A-Z_]+ =)\s+SEMBOL\b` ile satırı bulur ve `#L` numarasını yeniden üretir. Sembol bulunamazsa hata, numara farklıysa hata (`--fix` ile yazar). Doğal dil yorumu yok.

**Kapı 2 — sayılar (FR-181/182).** ÖLÇÜLDÜ: README.md:15,52,155,273 "664" diyor, `docs/security.md:358` "530 test" diyor — aynı metrik, iki değer, FR-181 ihlali. Gerçek değer 664 (`uv run pytest --collect-only -q` → "664 tests collected", 0,46 sn, veritabanı gerektirmiyor). Frontend için 211 (`bun test lib/` → "211 pass", 0,17 sn). Çözüm: belgelerde sayı düz metin yazılmaz, sarmalanır: `<!--m:api_test_count-->664<!--/m-->`. Betik her metriği KAYNAĞINDAN anlık ölçer — `pytest --collect-only -q` son satırı, `bun test lib/` çıktısı, `mypy` dosya sayısı, `ls supabase/migrations/*.sql | wc -l`, `grep -c '^CREATE TABLE'` — ve sarmalayıcının içini karşılaştırır/yazar. Ölçüm koşusundan gelen sayılar (holdout doğru ret %80 gibi) `evaluation/results/*.json`'dan okunur; kaynak yoksa betik sayıyı silip **"KOŞULMADI"** yazar — FR-182'nin birebir uygulaması. <!-- docs-check: tarihsel 664 · 2026-08-09 -->

**Kapı 3 — "uygulandı/uygulanmadı" iddiaları (FR-180, Acceptance 7.1).** Hedef: ARCHITECTURE.md:496-508'deki 12 satırlık tablo ve kvkk.md:180-187'deki 6 satırlık tablo. Her satırın altına bir kanıt yorumu konur: `<!--kanit-var: apps/api/app/api/internal.py#drain_jobs-->` veya `<!--kanit-yok: ...-->`. Betik grep yapar; shell koşturmaz (enjeksiyon ve kırılganlık yok). Bugün bu kapıdan geçemeyecek satırlar ölçüldü — ARCHITECTURE.md §10'da beşi: #1 (model imaja gömülü değil deniyor; `apps/api/Dockerfile:75,79,109` gömüyor), #2 (CI'da docker build yok deniyor; `.github/workflows/ci.yml`'de `image` job'ı var), #3 (drain ucu boş deniyor; `internal.py:70` `drain_jobs` dolu), #5 (0002 köprü migration'ı yok deniyor; `supabase/migrations/0002_supabase_auth_bridge.sql` var), #8 (embedding damgası yok deniyor; `0006_embedding_provenance.sql` + `chunks.embedding_space` var). Ayrıca `docs/security.md:275-276` "Gövde Faz G şeridinde yazılır; bugün router boş" ve `docs/kvkk.md:184` "metin hazır, sayfa yapılacak" (oysa `apps/web/app/kvkk/page.tsx` var ve `screenshots.spec.ts:121` onu çekiyor). Yani dış incelemenin yanıldığı satırların TAMAMI bu kapıyla otomatik yakalanıyor — mekanizmanın gerçekçiliğinin kanıtı bu.

**Kendi kırmızısını kanıtlama (Anayasa III + ci.yml deseni).** Betik `--self-test` ile `scripts/docs_check_fixtures/` altındaki bilerek bozulmuş küçük bir markdown'ı okur (yanlış satır numarası + yanlış sayı + yalan kanıt yorumu); hata BULAMAZSA 1 ile çıkar. Bu, ci.yml'deki "RLS politikasını bilerek boz, test kırmızı yanmazsa iş düşer" adımının birebir eşi.

**CI bağlantısı:** yeni bağımsız `docs` job'ı (`.github/workflows/ci.yml`), `needs:` YOK, çalışma dizini kök. Adımlar: checkout → `astral-sh/setup-uv` + `oven-sh/setup-bun` → `uv pip install -e ".[dev]"` (apps/api) + `bun install --frozen-lockfile` (apps/web) → `node scripts/docs_check.mjs --self-test` → `node scripts/docs_check.mjs`. Veritabanı GEREKMİYOR (iki sayım da ölçüldü: 0,46 sn ve 0,17 sn, ikisi de DB'siz), bu yüzden job hızlı ve diğerlerinden bağımsız paralel koşar. `api` veya `web` job'ına eklenmemesinin sebebi: betik her iki uygulamayı da okuyor; birine bağlamak kuralı iki yerde hatırlatmayı gerektirirdi (Anayasa XI).

**Gerekçe**: Mekanizmanın gerçekçiliği tahminle değil ölçümle savunuluyor: bugün var olan çelişkilerin her biri üç kapıdan birine düşüyor ve hepsi bu oturumda elle doğrulandı (664 vs 530; chat.py:567→589; config.py:167→255; security.md:276 vs internal.py:70; kvkk.md:184 vs app/kvkk/page.tsx; ARCHITECTURE §10'un beş satırı). Betik biçimi seçimi depoda kurulu: `apps/web/scripts/contrast.mjs` zaten "DESIGN.md'nin ölçülmüş AA iddiasının tek koruması" olarak CI'da koşuyor (ci.yml `web` job'ı) ve gerekçesi orada "kapı olmadan aynı sapma bir sonraki değişiklikte sessizce geri gelir" diye yazılı — belge iddiaları için ihtiyaç birebir aynı. Sayıları tek kaynaktan üretme fikri de yeni değil: `app/kvkk/page.tsx` KVKK metnini kopyalamak yerine `docs/kvkk.md`'yi derleme anında okuyor ve gerekçesini "iki nüsha, birinin güncellenip diğerinin unutulacağı bir ayrışma demektir (Anayasa XI)" diye yazıyor; belgelerdeki sayılar için aynı ilke uygulanıyor. `screenshots.spec.ts`'in modül docstring'i de aynı düşünceyi görsel için kurmuş: "elle alınan görüntüler bir sonraki arayüz değişikliğinde sessizce bayatlar".

**Elenen seçenekler**: (a) Belgedeki her cümleyi koda karşı doğrulayan genel bir denetleyici (LLM dahil) — elendi: doğal dil iddiası mekanik olarak yanlışlanamaz, deterministik olmayan bir kapı CI'da kararsızlık üretir ve Anayasa III'ün "deterministik" tanımını çiğner. (b) Satır numaralarını belgelerden tamamen kaldırmak — elendi: docs/security.md'nin tezi satır numaralı kanıt (satır 4: "her iddianın kodda karşılığı vardır ve satır numarasıyla gösterilir"); tezi silmek kapının kolay yolu olurdu. (c) Kanıt yorumlarında shell komutu koşturmak — elendi: enjeksiyon yüzeyi ve CI ortamına bağımlılık; sembol/dosya varlığı grep'i aynı işi risksiz yapıyor. (d) Sayıları `docs/metrics.json` ara dosyasında tutmak — elendi (mekanik sayılabilenler için): ara dosya kendisi bayatlayabilecek üçüncü bir nüsha olurdu; yalnız ölçüm koşusundan gelen (koddan sayılamayan) metrikler için `evaluation/results/` kullanılıyor. (e) Kapıyı mevcut `web` veya `api` job'ına eklemek — elendi: betik her iki uygulamayı okuyor, tek bir job'ın çalışma dizinine sığmıyor. (f) Kapıyı yalnız teslim öncesi elle koşturmak — elendi: elle koşan kapı, koşulmayan kapıdır.

**Dokunulacak dosyalar**:
- `scripts/docs_check.mjs`
- `scripts/docs_check_fixtures/bozuk.md`
- `.github/workflows/ci.yml`
- `docs/security.md`
- `ARCHITECTURE.md`
- `docs/kvkk.md`
- `README.md`
- `docs/test-report.md`

**Risk**: En olası kırılma: sembol arama düzenli ifadesi aşırı geniş olur (`grep` bir yorum satırındaki sembol adını yakalar) ve `--fix` satır numarasını YANLIŞ bir yere sabitler; kapı yeşil yanar ama belge artık daha da yanlıştır — yani kapı, koruduğu şeyi bozar. Bu yüzden eşleşme birden fazla satır bulduğunda betik hata vermeli, ilkini seçmemelidir. İkinci risk: `pytest --collect-only` çıktısının son satır biçimi pytest sürümüyle değişirse sayım sessizce 0 döner ve tüm sayılar sıfırlanır; ayrıştırma başarısızlığı ayrı bir hata olarak ele alınmalı, "ölçülemedi" ile "sıfır" karıştırılmamalıdır.

---
