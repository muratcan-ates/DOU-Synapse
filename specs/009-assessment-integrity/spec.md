# Özellik Şartnamesi: Assessment Integrity

**Feature Branch**: `009-assessment-integrity`  
**Base**: `2f40ac193114b896d33ef73e72ea51cc51f34d26` (`origin/main`, PR #17 dahil)  
**Created**: 2026-08-20  
**Status**: Tasarım / uygulama başlıyor  
**Risk**: R3 — resmî sınav görünürlüğü, puanlama ve LLM değerlendirmesi değişiyor

## Amaç

009, mevcut ölçme akışındaki dört fail-open davranışı tek güvenlik sınırında kapatır:

1. resmî sınav soruları öğrenci soru havuzu veya prova yolundan önceden görülemez;
2. resmî sınavın cevap anahtarı, çözümü, rubriği ve puanı güvenli yayın anından önce açılmaz;
3. blueprint kalemlerinin dondurulmuş `points` değerleri toplam puanda gerçekten kullanılır;
4. öğrenci cevabı ve kaynak metni LLM notlandırıcıya yalnız güvenilmeyen veri olarak girer;
   eksik veya doğrulanamayan rubrik/dayanak puan yazamaz.

Bu dilim yeni bir ajan, yeni bir sağlayıcı veya yeni bir değerlendirme framework'ü
kurmaz. Mevcut FastAPI, PostgreSQL RLS ve assessment modüllerini güçlendirir.

## Kullanıcı hikâyeleri

### US1 — Öğrenci sınavdan önce resmî soru havuzunu çıkaramaz (P0)

Eğitmen soruyu `practice` veya `assessment` amacıyla üretir. Eski sorular güvenli
geriye uyumluluk için `practice` kabul edilir. Yeni resmî kâğıt yalnız
`assessment` sorularından kurulabilir; öğrenci soru bankası ucu yalnız eğitmene
açıktır. RLS öğrencinin assessment sorusunu ancak kendi sınav kâğıdında görmesine
izin verir.

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

`ASSESSMENT_BLUEPRINT_ENABLED=false`, yeni blueprint sınav başlangıçlarını provider
ve kâğıt açılımından önce 503 ile durdurur. Mevcut oturumların cevap/bitiş yolları
çalışır; böylece öğrenci verisi veya süre kaybolmaz.

**Kabul senaryoları**:

1. Flag kapalıyken yeni blueprint başlangıcı 503 `assessment_blueprint_disabled`;
   practice ve mevcut oturumlar etkilenmez.
2. Yerel fake-provider/RLS kanıtı gerçek model, staging veya production kanıtı diye
   etiketlenmez.
3. Engineering, domain ve security/privacy onayları pending iken promotion iddiası `none` kalır.

## Fonksiyonel gereksinimler

- **FR-901**: `question_purpose` enum'u yalnız `practice|assessment` değerlerini taşımalı.
- **FR-902**: Migration öncesi sorular ölçülmemiş bir resmî-gizlilik iddiası
  taşımamak için `practice` olarak backfill edilmelidir.
- **FR-903**: Question purpose üretim anında server-validated olmalı; onay sonrası
  payload, purpose, source, type ve classification değişmez kalmalıdır.
- **FR-904**: Student question SELECT, onaylı practice veya kendi exam item'ı ile sınırlı olmalıdır.
- **FR-905**: App endpoint'i öğrenciye toplu soru bankası döndürmemelidir.
- **FR-906**: Aktif exam ile yeni practice/question-bank yolu aynı user transaction
  lock + ortak active-exam kararıyla sıralanmalıdır.
- **FR-907**: Blueprint paper yalnız assessment sorularından kurulmalı; publish/readiness
  bu kuralı yeniden doğrulamalıdır.
- **FR-908**: Blueprint geri bildirim zamanı başlangıçta `closes_at + duration_minutes`
  olarak snapshot'lanmalı; NULL güvenli yayın zamanı yeni oturum başlatmamalıdır.
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

## Kapsam dışı

- Question lifecycle'ın tam içerik editörü veya revision sistemi.
- Öğretmen manuel sonuç yayınlama/geri çekme paneli; bu tur güvenli otomatik zamanı kullanır.
- Yeni RAG retrieval politikası, superseded-document temizliği veya worker yetki daraltması.
- AI task quota/ledger'ının grading ve question-gen'e genellenmesi.
- Gerçek-provider, staging, canary, production veya insan onayı varmış iddiası.

## Başarı ölçütleri

- **SC-901**: Student question-bank/exam-extraction negatif testlerinin %100'ü geçer.
- **SC-902**: RLS referans koşusu ve her bağımsız gevşetme mutasyonu beklenen sızıntıyı yakalar.
- **SC-903**: 10/90 ağırlık matrisi ve legacy eşit-ortalama regresyonları %100 geçer.
- **SC-904**: Enjeksiyon/rubrik/evidence adversarial fake-provider setinde fail-open puan 0'dır.
- **SC-905**: Hedefli testler, tam backend paketi, mypy, format/lint ve OpenAPI drift
  aynı candidate SHA'da yeşildir.
- **SC-906**: Disk 10 GiB altındaysa ağır paket başlatılmaz; test DB ve servis kalıntısı 0 olur.

