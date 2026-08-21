---
description: "002 Production Sertleştirme — görev listesi"
---

# Görevler: Production Sertleştirme

**Girdi**: [`spec.md`](spec.md) · [`plan.md`](plan.md) · [`research.md`](research.md) · [`data-model.md`](data-model.md) · [`contracts/api-changes.md`](contracts/api-changes.md) · [`quickstart.md`](quickstart.md)

**Ön koşullar**: `.specify/memory/constitution.md` v1.1.0 · `specs/001-course-assistant-mvp/contracts/openapi.json` (25 yol, yeni uç eklendikçe yeniden export edilir)

**Testler**: `apps/api/tests/` (pytest) · `apps/web/lib/*.test.ts` (bun) · `apps/web/e2e/` (Playwright) · `supabase/tests/*.sql` (psql). Anayasa VIII gereği "bitti" = testler yeşil + lint temiz + davranış **tarayıcıda** gözlenmiş.

## Format: `[ID] [P?] [US] Açıklama`

- **[P]**: Paralel koşulabilir (farklı dosyalar, tamamlanmamış göreve bağımlılık yok)
- **[US]**: Ait olduğu kullanıcı hikâyesi (spec.md)
- Her görev TAM dosya yolu içerir; henüz var olmayan dosyalar **YENİ:** önekiyle
- **Done = committed**: her görev kendi conventional commit'iyle biter ve tarihli **DONE** notu düşülür

## Sıra bağlayıcıdır

`spec.md` §Uygulama sırası'ndaki sıra bir tercih değil, bir **kesme noktası mekanizmasıdır**: 17 Ağustos dondurmasına yetişmeyen iş listenin **sonundan** kesilir, ortasından değil. Blok başlıkları o sırayı taşır.

---

## Blok 1 — Sınav bütünlüğü (US1) · FR-101…FR-106

**Amaç**: Kural mod eksenine yazılmış, durum eksenine yazılmamış. Öğrenci sınavı başlatıp ikinci sekmede asistandan tam kaynaklı cevap alabiliyor. Kilit **sunucuda**, moddan bağımsız, üç uçta birden.

- [x] T101 [US1] `apps/api/app/core/db.py` — `db_now` buraya taşınır (`apps/api/app/api/exams.py:78-88`'den). İşlem saati jenerik altyapıdır ve FR-116 (yayın penceresi) ile FR-162 (sayfalama imleci) de aynı saate ihtiyaç duyacak; sınav modülünden saat almaya zorlamak ikinci kopyanın en kısa yoludur. `exams.py` kendi kopyasını siler ve import eder. **DONE (2026-08-09):** `db_now` `core/db.py`'ye taşındı; `exams.py` kendi kopyasını sildi ve import ediyor. Davranış değişmedi, `test_exams.py` 35 test yeşil.
- [x] T102 [US1] YENİ: `apps/api/app/modules/assessment/exam_state.py` — `effective_expiry` ve `remaining_seconds` (`exams.py:90-103`'ten, alt çizgisiz çünkü artık modül dışına açık) + `ExamLockedError(AppError)` (403, `code="exam_in_progress"`) + `EXAM_LOCK_REASON` / `EXAM_LOCK_MESSAGE` sabitleri + `active_exam_session(session, *, user_id, course_id, now, settings)`. `exams.py:20-26`'daki üç zaman kuralının kırpma maddesi kodla birlikte buraya taşınır. **Kırpma kuralı SQL'e YAZILMAZ**: `expires_at > now` yalnız daraltma yüklemidir, nihai kararı Python'daki `effective_expiry` verir — SQL tarafı gevşek kalırsa kilit fail-open olur (Anayasa IV). Modül `app/modules/` altında çünkü `deps.py`'nin `exams.py`'yi import etmesi döngü olurdu. **DONE (2026-08-09):** `exam_state.py` yazıldı: süre kırpma, `ExamLockedError` (403, `exam_in_progress`), tek metin sabiti ve `active_exam_session`. Kırpma SQL'e yazılmadı — `expires_at > now` yalnız daraltma yüklemi, nihai kararı Python veriyor.
- [x] T103 [US1] `apps/api/app/api/exams.py` — kendi `db_now`/`effective_expiry`/`_remaining_seconds` kopyalarını siler, T101/T102'den import eder. Davranış değişmez; bu görev yalnız tekrarı kaldırır (Anayasa XI). **DONE (2026-08-09):** Üç yardımcı da `exams.py`'den kalktı; `_remaining_seconds` → `remaining_seconds` (artık modül dışına açık).
- [x] T104 [US1] `apps/api/app/api/deps.py` — YENİ `require_assistant_unlocked(context: CourseMemberDep, session: SessionDep, settings: SettingsDep) -> CourseContext` + `UnlockedCourseMemberDep`. İlk satır eğitmen muafiyeti (`if context.is_instructor: return context` — sorgu bile koşmaz, FR-103). Modül `from app.modules.assessment import exam_state` biçiminde import edilir ve `exam_state.active_exam_session(...)` diye çağrılır: `from … import` bağlanmış bir kopya bırakır ve T108'in monkeypatch'i etkisiz kalır. Desen `deps.py:118-124` `require_course_instructor`'ın ikizidir. **DONE (2026-08-09):** `require_assistant_unlocked` + `UnlockedCourseMemberDep`. Eğitmen muafiyeti ilk satırda, sorgu koşmuyor. Modül üzerinden çağrı (`exam_state.active_exam_session`) — bağlanmış kopya bırakılsaydı T108'in karşı kontrolü etkisiz kalırdı.
- [x] T105 [US1] `apps/api/app/api/chat.py` — üç uç (`post_chat`, `list_sessions`, `list_messages`) `CourseMemberDep` yerine `UnlockedCourseMemberDep` alır. **`list_messages` atlanmamalı**: geçmiş turların kaynaklı cevap metnini ve atıflarını aynen döndürüyor, yani sınav sırasında açılan ikinci sekmede okunabilen bir yardım yüzeyi. Router seviyesinde `dependencies=[...]` KULLANILMAZ — T106'nın ucu aynı router'da yaşayacak ve kendi kilidine takılırdı. **DONE (2026-08-09):** Üç uç da kilide bağlandı. `list_messages` dahil: geçmiş, önceki turların atıflı cevaplarını taşıyor.
- [x] T106 [US1] `apps/api/app/api/chat.py` + `apps/api/app/schemas/chat.py` — YENİ uç `GET /courses/{course_id}/chat/availability`, bilerek `CourseMemberDep` ile (kilitliyken de cevap verebilmeli). Zarf `ChatAvailabilityOut(available, reason, message)` schemas'ta yaşar (`chat.py:24-36` sözleşme sahipliği kuralı). Uç, deps'in kullandığı **aynı** `active_exam_session`i ve **aynı** sabitleri kullanır; eğitmene her zaman `available: true` döner, yani muafiyet istemcide tekrarlanmaz. `specs/001-course-assistant-mvp/contracts/openapi.json` yeniden export edilir (25 → 26 yol). **DONE (2026-08-09):** `GET /chat/availability` + `ChatAvailabilityOut`. Zarf `schemas/chat.py`'ye DEĞİL `chat.py`'ye kondu: `chat.py:258-262`'nin yazılı kuralı geçmiş okuma yüzeylerinin bu router'ın sözleşmesi olduğunu söylüyor ve yoklama aynı sınıf. openapi.json 25 → 26 yol.
- [x] T107 [P] [US1] `ARCHITECTURE.md` §5 mod politikaları tablosu (336-340) — yeni satır: kilit **ders bazlıdır**. A dersinde sınav veren öğrenci B dersinin asistanını kullanabilir; gerekçesi yazılır. Karar `spec.md`'de örtüktü, açığa çıkarılır. **DONE (2026-08-09):** mod politikaları tablosuna dördüncü satır eklendi ve altına kilidin **durum** ekseninde çalıştığı, ilk üçünün **mod** ekseninde olduğu yazıldı; üç sınır (ders bazlı, yürüyen oturuma bağlı, yalnız değerlendirilene) gerekçeleriyle kayda geçti.
- [x] T108 [US1] YENİ: `apps/api/tests/test_exam_lock.py` — sekiz iddia. Kurulum `tests/test_exams.py`'den (`build_course`, `start`, `rewind`), hat sahtesi `tests/test_chat_api.py`'den devşirilir; ikinci bir kurulum kopyası yazılmaz. (1) exam yürürken `qa` → 403 + `error.code == "exam_in_progress"`; (2) `socratic` → 403; (3) süre geri alındıktan sonra → 200 + `answered`; (4) `practice` oturumu → 200; (5) eğitmen → 200; (6) `finish` sonrası → 200; (7) `GET /chat/sessions` ve `GET /chat/sessions/{id}` → 403; (8) **karşı kontrol**: `monkeypatch.setattr(exam_state, "active_exam_session", …)` ile kilit devre dışı, test 1'in aynı kurulumu → 200 + kaynaklı cevap. 8 olmadan 403'ün sebebi "kilit" değil "bozuk fikstür" de olabilir. **DONE (2026-08-09):** 9 iddia (planlanan 8 + yoklama ucu). **İki mutasyonla doğrulandı:** sorgu iptal edilince 5 kırmızı (yoklama dahil, iki yüzey tek fonksiyonu okuyor), yalnız `deps.py` zorlaması kaldırılınca 4 kırmızı ve yoklama yeşil. Karşı kontrol ikisinde de yeşil kaldı.
- [x] T109 [US1] YENİ: `apps/web/lib/chat-availability.ts` — `useChatAvailability(courseId)`, içi `useResource(fetcher, [courseId], { pollWhile: (s) => !s.available, intervalMs: 30_000 })`. Kilit kalkınca polling **kendiliğinden durur** (Anayasa XI: durdurulmayan polling kusurdur). `apps/web/lib/types.ts`'e `ChatAvailability` tipi. **DONE (2026-08-09):** `useChatAvailability` + `toChatLock` saf kararı. `pollWhile` ile yalnız kilitliyken yokluyor, 30 sn.
- [x] T110 [US1] `apps/web/components/course-nav.tsx` — TABS tablosuna `locksWithAssistant: true` bayrağı (mevcut `instructorOnly`'nin simetriği). Kilitli sekme `Link` yerine `<span aria-disabled="true">`, yanında "Kilitli" metni (renk tek başına bilgi taşımaz, Anayasa VII), şeridin altına sunucunun `message`'ı. Bileşen uca doğrudan dokunmaz, kancayı okur. **DONE (2026-08-09):** `locksWithAssistant` bayrağı; kilitli sekme `Link` değil `<span aria-disabled>` + "Kilitli" metni. `surface-raised` token'ı YOK olduğu için uydurulmadı, mevcut `border-border` kullanıldı (Anayasa VII).
- [x] T111 [US1] `apps/web/app/courses/[courseId]/chat/page.tsx` — kilitliyken besteci çizilmez. Yarış hâlinde (başka sekmede sınav başladı) POST'un 403'ü mevcut `sendError` + `errorMessage(e)` yolundan backend metniyle görünür; arayüz kendi metnini uydurmaz (`errors.ts:5-9`). **DONE (2026-08-09):** Kilitliyken besteci çizilmiyor. Tarayıcıda bulunan iki ek kusur da kapatıldı: yoklama dönmeden `ChatScreen` monte oluyordu (besteci parlaması + yüklemede iki 403), ve şerit ile sayfa aynı ucu iki kez çağırıyordu (Anayasa XI).
- [x] T112 [P] [US1] YENİ: `apps/web/lib/chat-availability.test.ts` — saf karar testi: `available=false` → sekme kilitli, mesaj sunucudan gelir. **DONE (2026-08-09):** 5 saf karar testi; frontend 211 → 216.
- [x] T113 [US1] `apps/web/e2e/flows.spec.ts` — "sınav provası" describe'ına ikinci sekme vakası: sınavı başlat, yeni sekmede `/courses/{id}/chat` aç, besteci çizilmemiş ve kilit mesajı görünür olmalı. **Tarayıcıda fiilen koşulur** (Anayasa VIII: bu şeritte gerçek ortam tarayıcıdır, `curl` değil). **DONE (2026-08-09):** `flows.spec.ts`'e "sınav başlayınca Asistan AYNI SEKMEDE kilitlenir, bitince açılır" eklendi. Vaka canlı tarayıcıda bulunan bir kusuru da kapsıyor: geçiş **sayfa yenilenmeden** izlenmeli. Mutasyonla doğrulandı — `examStateChanged()` çağrısı kaldırılınca kırmızı. Paket artık **27 geçiyor, 0 atlanıyor** (devir belgesi 16 geçiyor / 3 atlanıyor diyordu; atlananlar sahte sağlayıcı soru ürettiği için kendiliğinden açıldı).
- [ ] T114 [US1] Kilidin ek SELECT maliyeti: yeni indeks **eklenmez** — `exam_sessions_user_idx` (`0004_assessment.sql:94`) sorgunun öncü yüklemini ve sıralamasını karşılıyor. Ölçüm teslim öncesi koşulur ve `docs/test-report.md`'ye yazılır: `EXPLAIN (ANALYZE, BUFFERS)` planı + `request_logs.latency_ms` üzerinden kilit öncesi/sonrası p50/p95. Ölçülene kadar rapora **KOŞULMADI** yazılır (Anayasa III). Eşik aşılırsa doğru düzeltme kısmi indekstir (`… WHERE finished_at IS NULL`), ama ölçüm göstermeden eklenmez. **AÇIK (bilinçli):** ölçüm yapılmadı, indeks eklenmedi. `docs/test-report.md`'ye KOŞULMADI yazılacak (Anayasa III).

**Kapanış kabul kriteri**: `quickstart.md` §4.1'deki altı curl adımı `403 · 403 · 403 · 200 · 200` verir; T108 sekiz iddiayla yeşil ve T104'teki çağrı yorum satırı yapıldığında **1-7 kırmızı, 8 yeşil** kalır; ikinci sekme vakası tarayıcıda gözlenmiştir.

---

## Blok 2 — Bilinen production kusurları (US2) · FR-220…FR-224

- [x] T201 [US2] `apps/api/app/core/config.py` + YENİ: `apps/api/tests/test_config.py` + `docs/deployment.md` — issuer ortam değişkeni adı (FR-224). **DONE (2026-08-09):** `AliasChoices("SUPABASE_JWT_ISSUER", "JWT_ISSUER")`; iki ad da kabul ediliyor çünkü tek ada indirmek, alanı bugün `JWT_ISSUER` ile doğru kurmuş bir ortamı bozardı. Test tekil değil **sınıfsal**: `.env.example`'daki her adı `Settings` alanlarına karşı tarıyor, yani yeni bir uyuşmazlık da kırmızı yakar (SC-015). Mutasyonla doğrulandı — alias kaldırılınca hem tarayıcı hem hedefli test kırmızı, geri alınınca yeşil. `docs/deployment.md`'de bu değişkenin satırı **hiç yoktu**, eklendi; uyuşmazlığın o tablo incelenmesine rağmen hayatta kalma sebebi buydu. 664 → 668 test.
- [ ] T202 [US2] `apps/api/app/modules/ingestion/pipeline.py` (`:62` parse, `:79` embed) ve `apps/api/app/modules/retrieval/dense.py` (`:176` embed_query) — senkron ONNX/ayrıştırma çağrıları `await asyncio.to_thread(...)` ile sarılır (FR-220). Desen aynı modülün `storage.py:50,55,61`'inde zaten uygulanıyor; pahalı olana uygulanmamış. Embed sarması **döngü içinde, parti başına** yapılır. `dense.py` sorgu yolunda ve API sürecinde koştuğu için "ingestion ayrı worker'da" savunması onu kurtarmaz.
- [ ] T203 [US2] `apps/api/app/main.py` — lifespan'de embedding modeli **arka plan görevi olarak** ısıtılır, `yield`'den önce `await` EDİLMEZ (FR-221); hazırlık `/health/ready` üzerinden bildirilir. Test ortamında atlanır (pytest her koşuda 2,1 GB model yüklemez).
- [ ] T204 [US2] YENİ: `apps/api/app/core/rate_limit.py` — `_SlidingWindowLimiter` (`chat.py:121-148`), paylaşılan örnek, `reset_rate_limit()` ve `RateLimitError` buraya taşınır. Sayaç **tahliye edilir** (FR-223): bugünkü `defaultdict[str, deque[float]]` süreç ömrü boyunca sınırsız büyüyor ve `reset()` yalnız testlerden çağrılıyor. `chat.py` import eder; ikinci kopya yazılmaz (Anayasa XI).
- [ ] T205 [US2] `apps/api/app/api/questions.py` + `apps/api/app/core/config.py` — `POST /questions/generate`'e kota + **eşzamanlılık sınırı** (FR-222). Sohbet sınırının kopyası DEĞİL: tek çağrı 20 soruya kadar üretiyor, maliyet profili farklı. Aynı kullanıcının ikinci eşzamanlı üretimi reddedilir ve yanıt **ne zaman tekrar denenebileceğini** söyler.
- [ ] T206 [US2] `apps/api/tests/test_rate_limit.py` (YENİ) ve `apps/api/tests/test_ingestion.py` — kota, eşzamanlılık reddi ve tahliye testleri; `to_thread` sarmasının bloke etmediğinin kanıtı. **Anahtar gerekmez** — sınır LLM'e gitmeden önce devreye girer ve sahte sağlayıcıyla doğrulanmalıdır.
- [ ] T207 [US2] `docs/test-report.md` — bloke süresi ölçümü (SC-014) ve ısıtma sonrası ilk istek süresi. Ölçülmediyse **KOŞULMADI** yazılır, eski sayı kopyalanmaz.

---

## Blok 3 — Belge doğruluğu (US8) · FR-180…FR-183

**Amaç**: Kod yazmadan yapılmış işi görünür kılmak. Dış incelemenin yanlış izlenimi buradan doğdu; jüri de aynı dosyaları okuyacak.

- [ ] T301 [US8] `ARCHITECTURE.md` §10 (495-508) — 12 maddenin **5'i bayat**: model imaja gömüldü (`apps/api/Dockerfile:74-79`), CI'da docker build var (`.github/workflows/ci.yml` `image` işi), `/internal/drain` dolu (`app/api/internal.py:66-96`), `0002` var, `0006` embedding damgası var. Bölüm **silinmez, taranır**: 5 doğru madde (Storage, Compose RLS, iki orkestratör, reranker, bulut) kalır. §3/§8'deki "0002/0006/0007 depoda yoktur" ve §8'deki migration listesi düzeltilir; §4 diyagramındaki `bge-m3` → `multilingual-e5-large` (aynı belgenin §1'i tersini anlatıyor).
- [ ] T302 [P] [US8] `docs/security.md` — §8.1 `jwt_issuer` alanı artık var (T201 ile birlikte); §8.5 `allow_credentials=True` iddiası yanlış (`main.py:54` `False`); §9 "KVKK metni repoda yok" yanlış (`docs/kvkk.md` + `/kvkk` sayfası var). §358'deki test sayısı **668**. Satır numaralı 4 referans kaymış (`config.py:167` → gerçek 255, 88 satır); **sembol adına** çevrilir (`config.py::_check_auth_configuration`) — belge kendi "satır numarasıyla gösterilir" kuralını bozuyor ve `chat.py` gibi büyüyen dosyalarda bu kaçınılmaz.
- [ ] T303 [P] [US8] `docs/test-report.md` — RLS "8 PASS" → **98 iddia / 0 FAIL** (9 Ağustos'ta sıfırdan kurulan veritabanında koşturularak doğrulandı; "betik sessizce erken duruyor" ihtimali elendi). §577 test sayısı **668**. §6.4'teki FTS eşitlik bozma "AÇIK KUSUR"u kodda düzeltilmiş (`fts.py:116,129`), kapatılır — ama §6.3/§6.4 hibrit sayıları düzeltme sonrası **yeniden ölçülmeli**, ölçülene kadar KOŞULMADI.
- [ ] T304 [P] [US8] `README.md` — satır 235'teki "tam liste ARCHITECTURE §10" yönlendirmesi bayat listeye gidiyor, düzeltilir. Satır 172 "8 ekran" → 9 (KVKK sayfası). Satır 170-171 `sample_data` sayıları v1'de kalmış (gerçek: 22 dosya / 167 chunk, README kendi 201. satırında doğrusunu yazıyor). Satır 208-210 "kod tarafında iş kalmadı" → T023'ün frontend ayağı yazılmamış koddur. Satır 219-223 sahte sağlayıcı iddiası bayat.
- [ ] T305 [P] [US8] `docs/team/parallel/20_DEVIR_9_AGUSTOS.md` §4a — "soru üretimi sıfır soru döndürüyor" bayat (67ee442'de düzeltilmiş, `test_uretilen_taslak_havuza_kadar_gider` yeşil). Belge tarihsel kayıt olduğu için **silinmez**, düzeltme notu düşülür.
- [ ] T306 [US8] Eşik metriğinin tek doğrusu: `%80` (ARCHITECTURE §10 md.7 + README 226-231) `calibration.md` §7'nin **süperseded** v1 ölçümünden (n=10); §8 v2'de 0,81'de 11/18 = %61; `test-report` §3'te %50 (11/22). Üç farklı payda aynı metriğe atanmış. Hangi setin hangi sayıyı verdiği **tek yerde** netleştirilir; `scope.py` indikten sonra yeniden ölçüm yapılmadığı için nihai sayı KOŞULMADI kalır.
- [ ] T307 [US8] YENİ: `scripts/docs_check.mjs` — genel amaçlı doğal dil doğrulayıcı **yazılmaz** (gerçekçi değil). Yerine üç dar mekanik kapı: (a) belgelerdeki test sayısı ile `pytest --collect-only -q` çıktısı, (b) tablo sayısı ile `information_schema` sayımı, (c) migration listesi ile `ls supabase/migrations`. Bağımlılıksız Node ESM, `apps/web/scripts/contrast.mjs` deseninde. `.github/workflows/ci.yml`'e adım olarak eklenir. Bu, 664/668 gibi kaymaların bir daha elle yakalanmasını gerektirmez.
- [x] T308 [US8] `specs/002-production-hardening/*` — bu şeridin kendi belgelerindeki canlı test sayıları güncellendi. **DONE (2026-08-09):** sayı tek oturumda **664 → 668 → 677** oldu (issuer testleri +4, kilit testleri +9); frontend 211 → 216. Düzeltilen yalnız **canlı iddialar** (`plan.md` Technical Context, `spec.md` bağlam, `quickstart.md`'nin üç "bugün şu" satırı); **tarihsel kayıtlara dokunulmadı** — `research.md`'nin ölçüm notları, `checklists/requirements.md`'nin tarihli doğrulaması ve T201'in DONE notu o anı anlatıyor ve bayat değil, kayıt. `spec.md`'deki sayı büsbütün kaldırıldı: bir şartnamenin bağlam paragrafı her test eklendiğinde bayatlamamalı. Bu görevin üç kez elle koşulması T307'nin gerekçesidir — sayıyı kaynağından üreten kapı inmeden dördüncüsü de gelecek.

---

## Blok 4 — Güvenilirlik UX (US5) · FR-150…FR-156

- [ ] T401 [US5] `apps/web/lib/api.ts` — dört süre bütçesi tek sözlükte: `BUDGET_MS = { read: 12_000, write: 20_000, upload: 90_000, llm: 120_000 }`. Seçim otomatik (`method` yoksa `read`, `FormData` gövde `upload`, aksi `write`); `llm` açık çağrıyla. Tek global bütçe yanlış: `runbook.md`'ye göre gerçek sağlayıcıyla en kötü durum bir 10 sn bütçesini kırardı.
- [ ] T402 [US5] `apps/web/lib/api.ts` — `request()` ikiye bölünür: gövde `attempt()`'a taşınır, `request()` saran döngü olur. Yeniden deneme sayısı **çağırandan alınmaz**, metottan türetilir — POST'a otomatik retry çift cevap/çift soru üretir (FR-152). Jitter'lı üstel geri çekilme.
- [ ] T403 [US5] `apps/web/lib/errors.ts` — `classifyError(e): "transient" | "permanent" | "auth"`. `ErrorNote`'un `onRetry`'ı bundan türetilir; bugün karar geliştiricinin `onRetry` geçirmeyi hatırlamasına bağlı ve `chat/page.tsx:269` ağ hatasında retry düğmesi göstermiyor.
- [ ] T404 [US5] `apps/web/lib/use-resource.ts` — sabit 2000 ms `setInterval`, kendini yeniden zamanlayan `setTimeout` zincirine çevrilir; ardışık başarısızlıkta aralık artar (FR-156). Bugün API ölüyken saniyede yarım istekle sonsuza kadar dövüyor. `pollWhile`/`pulse` davranışı korunur.
- [ ] T405 [US5] `apps/web/components/page-state.tsx` — `Loading`'e süre eşiği; 4 sn sonra ikinci satır. Metin `runbook.md:123-124`'ten **birebir alınmaz**: oradaki cümle jüriye söylenen bir replik ve em dash içeriyor (Anayasa V yasaklıyor). Ekran metni ayrı yazılır.
- [ ] T406 [US5] `apps/api/app/main.py` + `apps/api/app/core/errors.py` + `apps/web/lib/api.ts` + `apps/web/components/page-state.tsx` — istek kimliği **hata zarfına** eklenir (`{"error": {code, message, request_id}}`), CORS `expose_headers` yoluna gidilmez: zarf sözleşmenin parçası olur ve tarayıcı başlık politikasına bağlı kalmaz. Üç handler da yazar. `openapi.json` yeniden export edilir; `apps/web/lib/types.ts` hata tipi güncellenir.

---

## Blok 5 — Sınav blueprint'i (US3) · FR-110…FR-119

> **Kapı**: `data-model.md` §8'deki dokuz açık kararın en az dördü bu bloğa başlamadan kapatılmalıdır — yayınlanmış dağılımın nasıl dondurulacağı, konu dağılımının öğrenme çıktısından bağımsızlığı, token bütçesinin kapsamı (yalnız sohbet mi tüm LLM mi), ve sınıflandırılmamış soruların yayın kapısında nasıl reddedileceği. Kapatılmadan yazılan `0008` bu kararları koda gömer ve geri alması pahalı olur.

- [ ] T501 [US3] `data-model.md` §8 — dört açık karar kapatılır ve gerekçeleri yazılır.
- [ ] T502 [US3] YENİ: `supabase/migrations/0008_exam_blueprint.sql` — beş tablo (`learning_outcomes`, `exam_blueprints`, `blueprint_cells`, `exam_versions`, `exam_items`), üç mevcut tabloya kolon (`questions.learning_outcome_id`/`difficulty`, `exam_sessions.exam_version_id`, `documents.supersedes_document_id`/`superseded_at`), iki `app` şeması yardımcısı, RLS + **GRANT/REVOKE**. `REVOKE UPDATE ON exam_items, blueprint_cells FROM dou_app` yazılmazsa `0001:313-316` sayesinde tablolar tam yazılabilir doğar ve FR-115'in değişmezliği koda değil alışkanlığa dayanır.
- [ ] T503 [US3] `apps/api/app/models/assessment.py` + `apps/api/app/schemas/assessment.py` — 0008'in aynası. `exam_sessions.question_ids` NOT NULL'ı kalkıyor; onu okuyan **dört çağrı yeri aynı commit'te** güncellenir, yoksa ilk blueprint oturumu `TypeError` ile düşer.
- [ ] T504 [US3] YENİ: `apps/api/app/api/blueprints.py` — blueprint ve öğrenme çıktısı uçları; FR-112 iç tutarlılık doğrulaması **uygulama katmanında** (mesaj hücre adıyla Türkçe; PostgreSQL kısıt ihlali bu cümleyi kuramaz, Anayasa V). Yüzdeler saklanmaz: arayüz marjinal dağılım alır, API tam sayı hücrelere açar.
- [ ] T505 [US3] `apps/api/app/api/exams.py` — sürümleme, yayın penceresi (FR-116), FR-114 eksik hücre raporu. Yürüyen oturum `exam_version_id` üzerinden başladığı sürümü görür; payload snapshot'ı alınmaz.
- [ ] T506 [US3] `apps/api/app/modules/assessment/question_gen.py` — imzaya opsiyonel `learning_outcome` ve `difficulty`; ikisi de `Question` satırına yazılır, zorluk prompt'a bir satır olarak girer (FR-113).
- [ ] T507 [US3] `apps/api/app/modules/assessment/grading.py` + `apps/api/app/schemas/assessment.py` — rubrik **ölçüt kırılımı** (FR-117). Yeni tablo yok; rubrik zaten `questions.payload.rubric`'te. Ağırlık toplamı kısıtı **yalnız yeni üretimde** zorlanır; okuma yolunda normalize edilir, yoksa havuzdaki onaylı sorular şema doğrulamasından düşer ve **sessizce değerlendirilemez** hâle gelir. Havuz aynı gün taranıp raporlanır.
- [ ] T508 [US3] `apps/api/app/api/documents.py` — yükleme ucuna opsiyonel `replaces_document_id`; FR-118 bağı **açık bir eylemle** kurulur, tahminle değil. Bayat soru işareti buradan türer.
- [ ] T509 [US3] YENİ: `apps/web/app/courses/[courseId]/blueprints/page.tsx` — blueprint kurma ekranı; `DESIGN.md` token'ları, ham hex yok.
- [ ] T510 [US3] `apps/api/tests/test_blueprint.py` (YENİ) + `supabase/tests/rls_blueprint.sql` (YENİ) — RLS'in **bozulduğunda kırmızı yandığı** mutasyonla kanıtlanır (Anayasa II, mevcut `rls_isolation_mutation_check.sh` deseni).

---

## Blok 6 — Ders bazlı AI politikası (US4) · FR-130…FR-137

- [ ] T601 [US4] YENİ: `supabase/migrations/0009_course_ai_policy.sql` — `course_ai_policies` (PK `course_id`, tüm alanlar NULL kabul eder, NULL = "global config'ten oku") + `course_ai_policy_audit` (salt-ekleme, **trigger** doldurur, uygulama kodu değil) + token bütçesi için `SECURITY DEFINER` yardımcısı. Yardımcı olmadan bütçe kontrolü **fail-open**: `request_logs`'un SELECT politikası yalnız eğitmene açık, öğrenci bağlamında `sum(token_count)` sıfır satır görür ve bütçe hep geçer (Anayasa IV).
- [ ] T602 [US4] YENİ: `apps/api/app/modules/policy/service.py` — tek çözümleyici `resolve_policy(session, *, course_id, settings)`. Döndürdüğü frozen dataclass'ta hiçbir alan Optional değildir; her değer çözülmüş gelir. FR-136 kapısı: politikası olmayan ders **bugünkü davranışla** çalışır ve bu birim testle sabitlenir.
- [ ] T603 [US4] `apps/api/app/core/config.py` — ders bazlı olacak **yalnız üç** ayar: `evidence_threshold` (FR-133), `socratic_max_stage` → `max_hints` (FR-131; global değer artık üst sınırın üst sınırı, çözümleyici `min(ders, global)` uygular), günlük token bütçesi (FR-134). Gerisi global kalır; gerekçeler `research.md`'de tek tek yazılı.
- [ ] T604 [US4] `apps/api/app/modules/retrieval/dense.py` + `fts.py` — `document_ids` filtresi `course_id` ile **aynı yere, aynı biçimde** girer (FR-132).
- [ ] T605 [US4] `apps/api/app/modules/assessment/socratic.py` + `apps/api/app/core/config.py` — ipucu üst sınırı bugün **iki ayrı yerde** sabit ve birbirinden habersiz (`socratic.py:68-79` beş kademe, `config.py:221` dört); tek sözlüğe indirilir (Anayasa XI).
- [ ] T606 [US4] `apps/api/app/api/chat.py` — mod kısıtı (FR-130) sunucuda; oturum modu sabitlemesinden **önce**. Kilit kontrolüyle aynı bağımlılık zincirinde.
- [ ] T607 [US4] `apps/api/app/modules/generation/llm.py` + `apps/api/app/api/chat.py` — token sayımı bugün yapılıyor ama `request_logs.token_count`'a yazılmıyor; zincir tamamlanır (FR-134'ün ön koşulu).
- [ ] T608 [US4] YENİ: `apps/api/app/api/policy.py` + YENİ: `apps/web/app/courses/[courseId]/settings/page.tsx` — öğretmen politika ekranı.
- [ ] T609 [US4] `apps/api/tests/test_policy.py` (YENİ) — FR-136 regresyonu: politika inmeden önce kaydedilen cevap, indikten sonra **aynı** olmalı.

---

## Blok 7 — Sayfalama (US6) · FR-160…FR-163

- [ ] T701 [US6] YENİ: `apps/api/app/schemas/page.py` — generic `Page[T] { items, next_cursor, total }`; `apps/api/app/api/deps.py`'ye `PageDep` (`limit` sunucu tarafında `min(limit, 100)` ile **kırpılır**, 422 değil).
- [ ] T702 [US6] YENİ: `supabase/migrations/0011_pagination_indexes.sql` — belirlenimci sıralama indeksleri. Veri birikmiş bir üretim veritabanında `CONCURRENTLY` ve işlem dışında; eski indeksler yenileri kurulduktan **sonra** silinir.
- [ ] T703 [US6] `apps/api/app/api/courses.py` · `documents.py` · `questions.py` · `chat.py` — beş liste ucu cursor sayfalamasına geçer. `openapi.json` yeniden export.
- [ ] T704 [US6] `apps/web/` — "devamını yükle" deseni **tek bileşende** yaşar; üç kez yazılmaz (Anayasa XI).

---

## Blok 8 — Gerçek kimlik (US7) · FR-170…FR-173

- [ ] T801 [US7] `apps/web/package.json` + YENİ: `apps/web/lib/supabase.ts` — `@supabase/supabase-js` eklenir (anahtarlar sonra gelir). `PLAN.md` "Teknoloji Kilidi" bölümüne yazılı gerekçe düşülür. Anahtar YOKKEN de derlenir ve `dev:` kimliği çalışmaya devam eder.
- [ ] T802 [US7] `apps/web/app/page.tsx` + `apps/web/lib/api.ts` — gerçek oturum token'ı; 401 yakalama. **Dikkat:** "403/401 görünce girişe at" kuralı US1 ile çakışır — kilit 403 döndürür ve öğrenciyi sınav sırasında giriş ekranına fırlatırdı. Yönlendirme kararı `error.code`'a bakar, yalnız HTTP durumuna değil. İkisi birlikte test edilir.
- [ ] T803 [US7] T023 (`specs/001-course-assistant-mvp/tasks.md:89`) kapatılır; anahtar gelince yalnız yapılandırma kalır.

---

## Blok 9 — Veri hijyeni, kullanıcı hakları, arıza görünürlüğü (US9, US10, US11)

> **Kesme noktası burada.** 17 Ağustos'a yetişmeyen iş bu bloktan kesilir.

- [x] T901 [P] [US9] `apps/web/e2e/` — izole/ephemeral test DB'sinde
  `globalSetup` koşu kimliği + `globalTeardown`; yalnız
  `E2E-<run>-<number>` dersleri ve `e2e-<run>-...` Bilgi İşlem audit kayıtları
  temizlenir. Ürün `DELETE course` API'si eklenmez; test ortada düşse de koşu
  sonunda bıraktığı kalıcı kayıt **sıfır** olmalıdır (SC-010). `COME 331` ve
  `c3b76077-20de-47e5-9fe1-4e770ffa64d2` açık koruma listesindedir. **DONE
  (2026-08-10):** Temiz DB E2E koşusu sonrasında run-scoped ders ve audit kalıntısı
  sıfır ölçüldü; korunan `COME 331` satırı yerinde kaldı. Başarısız koşuda da
  global teardown'ın çalıştığı gözlendi.
- [x] T902 [P] [US9] `bun run e2e:clean` — `E2E_DATABASE_NAME` zorunlu ve
  fail-closed doğrulanır; komut ders + audit adaylarını **önce gösterir**, yalnız
  `--evet` ile siler ve isteğe bağlı `--run` ile tek koşuya daralır. **DONE
  (2026-08-10):** DB adı/desen enjeksiyonu, koruma listesi, kuru koşu ve run-scoped
  ders + audit parser sınırları birim testleriyle sabitlendi.
- [ ] T903 [US10] YENİ: `apps/api/app/api/privacy.py` — sohbet geçmişi silme, dışa aktarma, hesap silme talebi. `docs/kvkk.md`'nin vaat ettiği haklarla birebir eşlenir; eşlenemeyen vaat **metinden çıkarılır** (FR-203). Öğretmen hesabı silmedeki FK kısıtı sessizce değil açıkça raporlanır.
- [ ] T904 [US11] YENİ: `supabase/migrations/0010_ingestion_retry.sql` + `apps/api/app/modules/ingestion/pipeline.py` — geri çekilmeli yeniden deneme. **Yeni sayaç kolonu gerekmiyor**: `ingestion_jobs.attempt_count` zaten var (`0001:275`) ve `claim_next_job` her alışta artırıyor.
- [ ] T905 [US11] `apps/api/app/api/documents.py` + `apps/web/` — kusurlu işi yeniden çalıştırma; görünürlük ayağı zaten var (`documents.status='failed'` + `error_message`), eklenen tek şey "ne zaman tekrar denenecek".
- [ ] T906 [P] [US11] YENİ: `apps/web/lib/security-headers.ts` + `apps/web/next.config.ts` + `apps/api/app/main.py` — **tek sözlük, iki uygulama noktası**: Next HTML/JS gönderiyor, FastAPI JSON; aynı başlık kümesi ikisine de anlamlı değil.

---

## Anahtar geldiğinde koşulacaklar (002 kapsamı dışı, sıra bağlayıcı)

1. Soru üretimini gerçek sağlayıcıyla koştur
2. Atlanan üç uçtan uca vakasının kendiliğinden açıldığını gör
3. T047 örneklemini çek, iki tur etiketle
4. Kapsam ayrımı (`retrieval/scope.py`) yerindeyken **eşiği yeniden ölç** (T306'nın beklediği sayı)
5. T023 canlı koşusu · T050 prod ortam · T051 prod RLS
