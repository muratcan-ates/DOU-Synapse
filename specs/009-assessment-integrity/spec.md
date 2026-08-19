# Özellik Şartnamesi: Assessment Integrity

**Feature Branch**: `009-assessment-integrity`  
**Base**: `2f40ac193114b896d33ef73e72ea51cc51f34d26` (`origin/main`, PR #17 dahil)  
**Created**: 2026-08-20  
**Status**: Yerel uygulama ve kanıt turu; dağıtım/promotion yok
**Risk**: R3 — resmî sınav görünürlüğü, puanlama ve LLM değerlendirmesi değişiyor

## Amaç

009, mevcut ölçme akışındaki beş fail-open davranışı tek güvenlik sınırında kapatır:

1. resmî sınav soruları öğrenci soru havuzu veya prova yolundan önceden görülemez;
2. resmî sınavın cevap anahtarı, çözümü, rubriği ve puanı güvenli yayın anından önce açılmaz;
3. blueprint kalemlerinin dondurulmuş `points` değerleri toplam puanda gerçekten kullanılır;
4. öğrenci cevabı ve kaynak metni LLM notlandırıcıya yalnız güvenilmeyen veri olarak girer;
   eksik veya doğrulanamayan rubrik/dayanak puan yazamaz.
5. hassas assessment tabloları, kullanıcı GUC'sini taklit edebilen ham yetki taşıyıcı
   oturumuna değil yalnız gerçek API LOGIN kimliğine açılır.

Bu dilim yeni bir ajan, yeni bir sağlayıcı veya yeni bir değerlendirme framework'ü
kurmaz. Mevcut FastAPI, PostgreSQL RLS ve assessment modüllerini güçlendirir.

## Kullanıcı hikâyeleri

### US1 — Öğrenci sınavdan önce resmî soru havuzunu çıkaramaz (P0)

Eğitmen soruyu `practice` veya `assessment` amacıyla üretir. Eski, hiçbir kâğıtta
kullanılmamış sorular güvenli geriye uyumluluk için `practice`; yalnız `exam_item`
tarafından kullanılanlar `assessment` kabul edilir. Aynı tarihsel soru hem blueprint
kâğıdında hem legacy `question_ids` dizisinde kullanılmışsa özgün satır `assessment`
olur; dar own-session RLS dalı yalnız o mevcut legacy oturum sahibinin aynı kimlikle
devam etmesine izin verir. Yeni resmî kâğıt yalnız `assessment` sorularından
kurulabilir; öğrenci soru bankası ucu yalnız eğitmene açıktır. RLS öğrencinin
assessment sorusunu ancak kendi sınav kâğıdında görmesine izin verir.

**Kabul senaryoları**:

1. Öğrenci `GET /questions` çağırdığında 403 alır; soru kökü, seçenek, kaynak ve
   kimlik sızmaz.
2. Prova seçimi yalnız onaylı `practice` sorularını kullanır.
3. Taslak sürüme `practice` soru eklemek 409; `assessment` soru eklemek mümkündür.
4. Başka kullanıcının veya başka dersin sınav sorusu RLS ve API katmanında görünmez.
5. Kendi oturumu olan öğrenci, pencere kapansa bile o kâğıdı tamamlayabilir.
6. Aktif exam oturumunda yeni prova veya genel soru havuzu yolu `exam_in_progress`
   ile kapanır; mevcut sınavın get/answer/finish yolları çalışır.
7. Yayınlanmış ya da superseded bir sürümde kullanılan soru reddedilemez/silinemez;
   eski kâğıt ve kanıt değişmez.
8. Üretimde öğrenme çıktısı ve zorluk birlikte verilir; taslak sorunun yalnız bu
   iki sınıflandırma alanı PATCH ile düzeltilebilir, terminal soru 409 kalır.
9. Migration öncesi aynı soruyu kullanan legacy prova ve blueprint varsa legacy
   oturumun soru sırası/cevabı değişmez; yalnız oturum sahibi devam eder. Aynı derse
   kayıtlı fakat bu soruyu içeren legacy oturumu olmayan öğrenci soruyu göremez ve
   yeni practice seçimi yalnız `purpose=practice` satırlarını kullanır.

### US2 — Resmî geri bildirim bütün kohort için güvenli anda açılır (P0)

Blueprint sınavı için güvenli otomatik yayın zamanı `closes_at + duration_minutes`
olarak hesaplanır. Böylece kapanıştan hemen önce başlayan son öğrenci hâlâ sınavdayken
erken bitiren öğrenci cevap anahtarını paylaşamaz.

**Kabul senaryoları**:

1. Yeni blueprint oturumu için `closes_at` zorunludur; yoksa oturum fail-closed 409 olur.
2. Erken finish oturumu kapatır ancak `score=null`, `results=[]`,
   `feedback_released=false` döner; kaynak/rubrik/çözüm yüklenmez.
3. `GET /exams/{session_id}/results`, yayın anından önce aynı gizli zarfı; sonra
   puanı ve soru bazlı geri bildirimi döner.
4. Practice ve blueprint'e bağlı olmayan eski self-servis sınavlar mevcut bitiş
   davranışını korur.
5. Liste ve oturum detay uçları da yayın öncesi puanı göstermez.
6. Yayın anı oturuma başlangıçta snapshot'lanır; blueprint sonradan değiştirilse
   bile yürüyen oturumun geri bildirim zamanı öne çekilemez.

### US3 — Resmî puan blueprint ağırlıklarıyla hesaplanır (P0)

Blueprint oturumunda puan `exam_items.points` ağırlığıyla türetilir. Prova ve
legacy sınav eşit ortalamayı korur.

**Kabul senaryoları**:

1. 10 ve 90 puanlık iki cevap sırasıyla 100 ve 0 ise sonuç 10.0'dır; tersinde 90.0'dır.
2. Değerlendirilemeyen cevap mevcut karar gereği paydaya girmez; cevaplanmamış soru
   yanlış sayılmaz.
3. Ağırlık dizisi soru/cevap kimliğiyle eşlenir; sıra veya eksik cevap yüzünden
   yanlış soruya ağırlık uygulanmaz.
4. `exam_sessions.score` güven kaynağı olmaz; sonuç cevaplar + dondurulmuş kalemlerden
   her okumada aynı biçimde türetilir.

### US4 — LLM notlandırması güvenilmeyen metne fail-closed davranır (P0)

Öğrenci cevabı, soru/kod ve kaynak parçaları ayrı, kaçışlı veri zarflarında taşınır.
Talimat yalnız system prompt'tan gelir.

**Kabul senaryoları**:

1. Öğrenci cevabı veya kaynak metnindeki kapanış etiketi/instruction prompt sınırını
   kıramaz.
2. Rubrikli soruda eksik, duplicate, bilinmeyen veya isim değiştirilmiş ölçüt
   `graded=false` üretir; top-level `score` fallback'i kullanılmaz.
3. Modelin `dayanak_chunk_id` değeri izinli kümede değilse LLM gerektiren cevap
   puanlanmamış sayılır; kanıt düşürülüp puan korunmaz.
4. Rubriksiz code-trace/bug-hunt sonucunda da kaynak dayanağı zorunludur.
5. Deterministik MCQ ve short-answer yolları provider'a gitmeden çalışmaya devam eder.

### US5 — Acil durdurma ve kanıt sınırı açıktır (P0)

Kod ve örnek ortam varsayılanı `ASSESSMENT_BLUEPRINT_ENABLED=false`tır; yeni
blueprint sınav başlangıçlarını provider ve kâğıt açılımından önce 503 ile durdurur.
Mevcut oturumların cevap/bitiş yolları çalışır; böylece öğrenci verisi veya süre
kaybolmaz. Yalnız doğrulanmış yerel/CI akışları özelliği açıkça etkinleştirir.

**Kabul senaryoları**:

1. Flag kapalıyken yeni blueprint başlangıcı 503 `assessment_blueprint_disabled`;
   practice ve mevcut oturumlar etkilenmez.
2. Yerel fake-provider/RLS kanıtı gerçek model, staging veya production kanıtı diye
   etiketlenmez.
3. Engineering, domain ve security/privacy onayları pending iken promotion iddiası `none` kalır.

### US6 — Veritabanı, gerçek API çalışma zamanı kimliğini ayırt eder (P0)

API `dou_api_runtime` LOGIN'iyle bağlanır; `dou_app` yalnız NOLOGIN yetki
taşıyıcısıdır. Assessment'in hassas ham tablolarında kullanıcı GUC'si doğru görünse
bile başka bir `session_user` erişim alamaz.

**Kabul senaryoları**:

1. `dou_app` LOGIN/parola taşımaz; yalnız `dou_api_runtime` beklenen dar üyelikle
   bu rolün genel yetkilerini miras alır.
2. Ham taşıyıcı oturumu GUC ve `SET ROLE` taklit etse de soru anahtarı, erken sonuç,
   dondurulmuş sürüm/kalem ve score alanlarını okuyamaz veya yazamaz.
3. API'nin kullandığı DSN/pooler `session_user=dou_api_runtime` üretmiyorsa
   `/health/ready` 503 ve `database_role=invalid` döndürür.
4. `0016`, eski `dou_app` pool'u aktifken veya taşıyıcının beklenmeyen bir üyesi
   varken uygulanmaz.
5. Migration sonrası uygulama rollback'i runtime DSN'de kalır; carrier LOGIN
   yeniden açılmaz.
6. `dou_app` başka bir parent rolden yetki miras alamaz; `dou_api_runtime`ın üyesi
   olamaz ve runtime yalnız `dou_app` parent'ını miras alabilir.
7. Farklı migration owner'larının bıraktığı gelecek tablo CRUD grant'leri temizlenir;
   ilgili `app` fonksiyon owner'larının hard-wired global ve açık schema-local PUBLIC
   EXECUTE varsayılanları kapanır; etkin kalıntı varsa migration durur.

## Fonksiyonel gereksinimler

- **FR-901**: `question_purpose` enum'u yalnız `practice|assessment` değerlerini taşımalı.
- **FR-902**: Migration öncesi kâğıtsız sorular `practice`; yalnız blueprint
  kâğıdında kullanılan sorular `assessment` olarak backfill edilmelidir. Aynı soru
  legacy `question_ids` ve blueprint `exam_items` tarafından paylaşılıyorsa özgün
  satır `assessment` kalmalı; yalnız bu kimliği zaten taşıyan kendi legacy oturumunun
  sahibi dar RLS istisnasıyla devam edebilmeli, yeni practice seçimleri ve başka
  öğrenciler bu resmî satırı görememelidir.
- **FR-903**: Question purpose üretim anında server-validated olmalı; onay sonrası
  payload, purpose, source, type ve classification değişmez kalmalıdır.
- **FR-903a**: `learning_outcome_id` ve `difficulty` üretimde birlikte veya ikisi de
  boş olmalı; aynı dersin açıkça başka konuya bağlı çıktısı reddedilmelidir.
- **FR-903b**: Draft-only classification ucu yalnız bu iki alanı kabul etmeli;
  içerik/purpose/source revizyonu için kullanılmamalıdır.
- **FR-903c**: Sınıflandırılmamış assessment taslağı onaylanamamalı; hata
  `question_classification_required` olmalıdır.
- **FR-904**: Student question SELECT, onaylı practice veya kendi exam item'ı ile sınırlı olmalıdır.
- **FR-905**: App endpoint'i öğrenciye toplu soru bankası döndürmemelidir.
- **FR-906**: Aktif exam ile yeni practice/question-bank yolu aynı user transaction
  lock + ortak active-exam kararıyla sıralanmalıdır.
- **FR-907**: Blueprint paper yalnız assessment sorularından kurulmalı; publish/readiness
  bu kuralı yeniden doğrulamalıdır.
- **FR-907a**: Published/superseded version'ın snapshot/yayın kanıtı değişmez olmalı;
  yalnız published → superseded geçişinin kendi damgası eklenebilmelidir.
- **FR-908**: Blueprint geri bildirim zamanı başlangıçta `closes_at + duration_minutes`
  olarak snapshot'lanmalı; NULL güvenli yayın zamanı yeni oturum başlatmamalıdır.
- **FR-908a**: Veritabanı INSERT/UPDATE guard'ı erken snapshot'ı ve snapshot'ın
  sonradan öne çekilmesini API'den bağımsız reddetmelidir.
- **FR-909**: `finish` idempotent sonuç okumasından ayrılmalı; tekrar finish 409 kalabilir,
  fakat `GET results` her zaman güvenli yayın politikasını yeniden uygulamalıdır.
- **FR-910**: Blueprint sonucu soru-id → points eşlemesiyle ağırlıklı; diğer akışlar
  eşit ortalama olmalıdır.
- **FR-911**: Grading prompt'unda bütün dinamik metinler kaçışlı, isimli untrusted
  bloklarda olmalıdır.
- **FR-912**: Rubrik ve evidence bütünlüğü doğrulanamazsa `graded=false`; hiçbir
  kısmi/top-level fallback resmî puana yazılmamalıdır.
- **FR-913**: Kill switch yalnız yeni blueprint başlangıcını kapatmalı; mevcut
  oturumu ortada bırakan bir kapı olmamalıdır.
- **FR-914**: `dou_api_runtime`, ayrı LOGIN ve dar `dou_app` üyeliğiyle bağlanmalı;
  `dou_app` NOLOGIN/parolasız ve `SET/ADMIN` devredilemez taşıyıcı kalmalıdır.
- **FR-915**: Hassas assessment SELECT/INSERT/UPDATE yüzeyleri exact
  `session_user` runtime kontrolü ve dar doğrudan ACL ile korunmalıdır; GUC veya
  `SET ROLE` bu kontrolü geçememelidir.
- **FR-916**: Readiness yanlış runtime kimliğinde 503 vermeli; `0016` aktif eski
  carrier oturumu/beklenmeyen üyede fail-closed durmalıdır.
- **FR-917**: `dou_app` hiçbir parent rol miras almamalı; runtime'ın üyesi olmamalı;
  `dou_api_runtime` yalnız `dou_app` parent'ını miras almalı ve kendisine üye
  bağlanmamalıdır.
- **FR-918**: Gelecek tablo CRUD default ACL'leri yalnız current migration owner için
  değil ilgili bütün owner kayıtlarında normalize edilmeli; `app` schema/current
  migration/mevcut function owner'larında global ve schema-local PUBLIC EXECUTE
  kapanmalı; etkin unsafe default privilege migration'ı fail-closed durdurmalıdır.

## Kapsam dışı

- Question lifecycle'ın tam içerik editörü veya revision sistemi; bu tur yalnız
  immutable içerikten ayrı draft sınıflandırmasını tamamlar.
- Öğretmen manuel sonuç yayınlama/geri çekme paneli; bu tur güvenli otomatik zamanı kullanır.
- Yeni RAG retrieval politikası, superseded-document temizliği veya worker yetki daraltması.
- AI task quota/ledger'ının grading ve question-gen'e genellenmesi.
- Ele geçirilmiş gerçek backend runtime credential'ını düşük ayrıcalıklı kullanıcı
  kimliğine dönüştüren yeni bir DB proxy; bu credential trusted-backend sırrıdır.
- Gerçek-provider, staging, canary, production veya insan onayı varmış iddiası.

## Başarı ölçütleri

- **SC-901**: Student question-bank/exam-extraction negatif testlerinin %100'ü geçer.
- **SC-902**: RLS referans koşusu ve her bağımsız gevşetme mutasyonu beklenen sızıntıyı yakalar.
- **SC-903**: 10/90 ağırlık matrisi ve legacy eşit-ortalama regresyonları %100 geçer.
- **SC-904**: Enjeksiyon/rubrik/evidence adversarial fake-provider setinde fail-open puan 0'dır.
- **SC-905**: Hedefli testler, tam backend paketi, mypy, format/lint ve OpenAPI drift
  aynı candidate SHA'da yeşildir.
- **SC-906**: Disk 10 GiB altındaysa ağır paket başlatılmaz; test DB ve servis kalıntısı 0 olur.
- **SC-907**: Runtime rol metadata/üyelik/ACL negatifleri, GUC+`SET ROLE` taklidi,
  yanlış-role readiness ve aktif-pool migration preflight testleri geçer.
- **SC-908**: Upgrade kanıtı bütün kohort safe-at sınırını, mixed-use soruda yalnız
  legacy oturum sahibinin aynı referansla devamını, aynı dersteki oturumsuz öğrencinin
  reddini ve owner'lar arası unsafe default ACL kalıntısının temizlenmesini doğrular.
