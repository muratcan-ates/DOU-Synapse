# Modülerlik denetimi — 10 Ağustos 2026

> Dal: `refactor/modularize`, `002-production-hardening` (a04d2ca) üstüne
> rebase'li — yani runtime-safety ve frontend-reliability birleşmelerinden
> SONRAKİ hâlin üstünde duruyor ve doğrudan birleştirilebilir.
> **Push'lanmadı.** Beş oturum ve GPT aynı anda çalışıyordu; bu dal yalnız
> kimsenin elinde olmayan dosyalara dokundu.

Depo baştan sona tarandı (8 alan tarayıcısı → 39 birleşik bulgu → 39 bağımsız
doğrulayıcı; 5 bulgu doğrulamada düştü). Bu belge üç şey yapar: yapılanı sayar,
**bir kararı sana bırakır**, ve dokunamadığım bulguları sahibi olan şeride
devreder.

---

## 1. Neye dokunuldu, neye dokunulmadı

Dokunulan dosyalar, tarama anında hiçbir şeridin `git status`'unda ya da
`002...HEAD` farkında olmayanlarla sınırlandı. Sıcak sayılanlar:

| Şerit | Sahiplendiği ve bu dalın hiç açmadığı dosyalar |
|---|---|
| `hardening/runtime-safety` | `api/chat.py`, `api/health.py`, `core/errors.py`, `core/rate_limit.py`, `core/warmup.py`, `main.py`, `ingestion/pipeline.py`, `retrieval/dense.py` |
| `feature/source-quality-lab` | `api/sources.py`, `retrieval/inspection.py`, `schemas/source.py`, `main.py`, `components/source-card.tsx`, ders sayfaları |
| `hardening/frontend-reliability` | `lib/api.ts`, `lib/errors.ts`, `lib/use-resource.ts` (+ testi), `lib/types.ts`, `components/page-state.tsx`, ders sayfaları |
| `002-production-hardening` | `api/exams.py`, `api/deps.py`, `api/blueprints.py`, `core/config.py`, `core/db.py`, `assessment/exam_state.py` |
| hepsi | `app/contracts.py` (kural: yalnız lider), `apps/web/app/**`, `e2e/flows.spec.ts` |

`apps/web/app/**` ve `apps/web/components/**` tamamen dışarıda bırakıldı — web
ekranlarının hepsi en az bir şeridin elinde.

## 2. Yapılanlar

Her biri kendi commit'i, hepsi davranış koruyan yeniden düzenleme:

1. **Türkçe katlama tek modülde.** `question_gen`'in kendi küçültme tablosu ve
   tokenleştiricisi vardı; `grading` metin kuralını oradan import ediyordu.
   İkisi de `core/text_tr`'ye geçti. İki agresiflik seviyesi (`fold` / `normalize`)
   artık orada ve **aralarındaki ölçüt yazılı**: geri çağırma tarafı katlar,
   puanlama tarafı katlamaz. `test_text_tr.py` ikisini birbirine bağlamayı
   kırmızı yakar.
2. **LLM çıktısından JSON okuma tek kuralda** (`core/llm_json.py`). Sohbet yolu
   metni tarıyordu, soru üretimi ve puanlama çit sıyırıp `json.loads` çağırıyordu;
   ikincisi "İşte sorular: {...}" gibi bir yanıtı şema hatası sayıp FR-020'nin tek
   yeniden denemesini harcıyordu.
3. **Görev artık çağrı yerinde beyan ediliyor.** `LlmRequest.task` eklenmişti ama
   kimse göndermiyordu; sahte sağlayıcı prompt metninde `{"questions"` ve
   `### KAYNAK` arayarak görevi tahmin ediyordu. `resolve_completion(QUESTION_GEN)`
   ile borç kapandı, tahmin katmanı silindi.
4. **Zaman damgası sütunları `models/base.py`'de.** Üretilen DDL 324 satır
   karşılaştırılarak birebir aynı doğrulandı.
5. **Sınıf analitiğinde üçüncü mastery taraması silindi** — sayı zaten elde olan
   konu satırlarından türetiliyor, tıpkı yanındaki öğrenci ucu gibi.
6. **Testler artık dokunmadıkları veritabanının bedelini ödemiyor.**
   Tam suite **224 sn → 36 sn**, 720 test yeşil.
7. **Kaynak kartı eşlemesi tek sahipli** (`lib/source.ts`); `labels.ts`'teki ölü
   ikinci ustalık eşiği tablosu silindi.
8. **Ölü kod:** sahte sağlayıcının soru ayrıştırıcısı, `TEXT_EXTENSIONS`,
   `parse_code`'un okunmayan parametresi. `socratic.MAX_STAGE_INDEX` **silinmedi**
   (planlanan FR-131 işi onun üstünde) ama hiç doğrulanmayan iddiası artık bir
   bekçi testiyle korunuyor.
9. **Testler birbirine değil `tests/factories.py`'ye bağlanıyor.** On üç
   modüller-arası import dörde indi; kalan üçü `test_exam_lock` sıcak olduğu
   için zorunlu ve gereken adlar gerekçesiyle yeniden dışa aktarıldı. Toplanan
   test node kimlikleri öncesiyle **baytı baytına aynı** — hiçbir iddia
   kaybolmadı, üç kurulum çağrısı ise hiç iddia etmiyorken artık `201` istiyor.

### Rebase'te çıkan tek çakışma

`api/questions.py`: runtime-safety bu dosyaya kota/eşzamanlılık kapısı eklemiş,
ben aynı fonksiyonda `resolve_completion(QUESTION_GEN)` çağırıyordum. Onların
yapısı korunarak çözüldü.

Ayrıca `tests/test_rate_limit.py` — birleşmeyle gelen yeni dosya — kurulumunu
`test_assessment`'tan alıyordu ve bu dalın kaldırdığı adlara bağlıydı. Fabrikaya
yönlendirildi; dosyanın "testler arası ithal bu depoda kurulu bir desen" diyen
yorumu da düzeltildi, çünkü artık değil.

## 3. SANA BIRAKILAN KARAR — kısa cevap puanlaması aksan katlamalı mı?

Bu bir yeniden düzenleme değil, **pedagojik bir karar**; o yüzden ben vermedim.

Bugün kısa cevap puanlaması aksanı KORUYOR (`text_tr.normalize`). Yani cevap
anahtarı "çözüm" iken öğrencinin "cozum" yazması **0 puan** alıyor. Oysa aynı
öğrenci retrieval tarafında eşdeğer sayılıyor: `chunks.fts` kolonu
`0001_core_schema.sql`'de `app.immutable_unaccent` üzerinden üretiliyor ve
`retrieval/scope.py` `text_tr.fold` kullanıyor.

* **Katlamak** (grading'i `fold`'a geçirmek): Türkçe klavye kullanmayan öğrenci
  haksız sıfır almaz. Python tarafı veritabanının davranışıyla hizalanır.
* **Katlamamak** (bugünkü hâl): "acı" ile "açı" katlanınca aynı dizeye iner. Kısa
  cevabın anahtarı böyle bir çift olursa yanlış cevap 100 alır.

Değiştirmek tek satır: `grading.grade_short_answer` içindeki `text_tr.normalize`
→ `text_tr.fold`. Karar verirsen `test_text_tr.py::TestSeviyeAyrimi` de birlikte
güncellenmeli — o test bugünkü ayrımı bilerek çiviliyor.

Ara yol: eşiği hiç değiştirmeden, soru üretimi prompt'unun `accepted_answers`
listesine aksansız yazımı da eklemesini istemek. Bu, kararı puanlamadan alıp
üretime taşır ve iki riskin ikisini de almaz.

## 4. Devredilen bulgular — sahibi olan şerit alsın

Hepsi bağımsız doğrulayıcıdan geçti (kod okunarak, birkaçı canlı üretilerek).
Ayrıntılı kanıt ve öneri metinleri denetim çıktısındadır; buradaki tek satırlar
hangi şeridin neyi devraldığını göstermek içindir.

### `hardening/runtime-safety`

* **`one-answer-pipeline-not-two` (yüksek).** Cevap orkestrasyonu iki gövdede:
  `chat.produce_answer` üretimde, `guardrails.chain.AnswerPipeline` yalnız
  testlerde. Ayrışma üç somut kusur üretmiş — en görüneni: sıkı yeniden deneme
  aynı prompt'u ikinci kez gönderiyor (`strict_retry` hiç set edilmiyor).
* **`ingest-blocks-event-loop`.** Ayrıştırma, chunk'lama ve embedding senkron
  olarak olay döngüsünde koşuyor; süreç içi drain'de API donuyor.
* **`stale-processing-ingestion-jobs-never-reclaimed`.** `claim_next_job` yalnız
  `pending` alıyor; `processing`de takılan iş geri alınmıyor, belge sonsuza dek
  "işleniyor" görünüyor.
* **`location-rule-three-copies-across-languages`.** "Sayfa N / Slayt N / bölüm
  adı" kuralı iki dilde üç kez yazılı. (`contracts.py` de içerdiği için lider işi.)

### `002-production-hardening`

* **`exams-list-answers-n-plus-1`** ve **`mastery-recorded-one-roundtrip-per-answer`**
  — ikisi de `api/exams.py`'de döngü içinde await.
* **`exams-feedback-jsonb-contract-in-router`.** `answers.feedback` jsonb'sinin
  kodlayıcı/çözücüsü router'da; `"tamamlanamadi"` sabiti dört yerde, `GradingOutcome`
  kurulumu birebir iki kez.
* **`course-scoped-404-lookup-repeated-nine-times`.** "kaydı getir → yoksa ya da
  başka dersinse 404" kalıbı dokuz uçta birebir. `deps.py` zaten bu tür kapıların
  evi.
* **`settings-populate-by-name-and-issuer-scaffolding`.** `Settings(jwt_issuer=...)`
  sessizce yutuluyor (`validation_alias` var, `populate_by_name` yok,
  `extra="ignore"`) — canlı doğrulandı. Ayrıca `security.py` hâlâ alanı `getattr`
  ile arıyor.
* **`exams-questions-bypass-settings-dep`.** Yedi uç `get_settings()`'i gövdede
  çağırıyor, mevcut `SettingsDep`'i kullanmıyor; testte override edilemiyor.

### `hardening/frontend-reliability` + `feature/source-quality-lab`

* **`web-course-page-scaffold-and-session-triplication` (yüksek).** `AppShell` +
  `CourseNav` iskeleti altı ders sayfasında elle kuruluyor, eğitmen kapısı üç kez
  yazılmış, `useSession` sayfa başına üç kez mount oluyor (üç `localStorage`
  okuması, üç ayrı `ready` zaman çizgisi).
* **`card-p6-cannot-be-overridden-by-p0`.** `Card`'ın gömülü `p-6`'sı `className`
  ile ezilemiyor; `p-0` geçen üç panel 24px içeriden çiziliyor. Canlı doğrulandı.
* **`refresh-error-block-duplicated-and-swallowed`.** Tazeleme hatası bloğu dört
  ekranda kopya, biri ayrışmış, beşincisinde tamamen yutuluyor ve yerinde ölü JSX
  duruyor.
* **`control-shell-class-triplicated-no-select-textarea`.** 44px girdi kabuğunun
  sınıf dizisi `ui.tsx` dışında üç kez daha; `Select` ve `Textarea` bileşeni yok.
* **`role-label-hardcoded-four-places`.** "Eğitmen / Öğrenci" eşlemesi `labels.ts`
  varken dört ekranda elle.
* **`course-detail-poll-refetches-static-course`.** Ders detayı 2 sn'de bir
  değişmeyen ders kaydını da çekiyor — yoklama trafiği iki katı.
* **`frontend-backend-contract-has-no-drift-gate`.** `types.ts` elle yazılmış
  357 satırlık sözleşme aynası ve hiçbir CI adımı onu denetlemiyor.
* **`unused-request-types-not-wired`.** `ExamStartRequest` / `AnswerSubmitRequest` /
  `ExamHintRequest` hiç kullanılmıyor; sınav ekranı tipsiz literal gönderiyor.
* **`e2e-storage-keys-and-signin-copied`.** Oturum depo anahtarları ve giriş
  yardımcısı e2e'ye elle kopyalanmış.
* **`use-resource-test-fossil`.** Test, kancada artık var olmayan bir `loading`
  türevini sınıyor; asıl kural (`isFirstLoadSettled`) hiç sınanmıyor.

### Sahipsiz — soğuk ama bu dalın kapsamı dışında

Dördü de **kusur**, yeniden düzenleme değil. Bu dala karıştırılmadı ki
"davranış korunur" iddiası doğru kalsın:

* **`chunk-merge-crosses-section-boundary`** (`ingestion/chunking.py`). Yorum
  "farklı sayfadaysa birleştirme yapılmaz" diyor ama koşul `section_title`'a
  bakmıyor; markdown ve kod materyalinde atıf yanlış bölümü gösteriyor.
  PDF/PPTX davranışının değişmediği ölçülerek doğrulandı.
* **`prompt-injection-defense-only-in-chat-builder`** (`assessment/grading.py`).
  Kaçış ve "bu blok VERİDİR" kuralı üç prompt kurucudan yalnız sohbettekinde;
  sınav değerlendirmesi öğrencinin ham metnini prompt'a koyuyor.
* **`sequence-words-no-word-boundary`** (`guardrails/leakage.py`). `_SEQUENCE_WORDS`
  tek `_alt` kullanımı ki `\b` ile sabitlenmemiş: "öncelikle" içindeki "önce"
  eşleşiyor, temiz bir ipucu sızıntı sayılıyor.
* **`preview-chunks-limit-unbounded-below`** (`api/documents.py`). `?limit=-1`
  negatif SQL LIMIT üretip 422 yerine 500 döndürüyor.

## 5. Doğrulama

Rebase sonrası, `002-production-hardening` (a04d2ca) üstünde:

```
apps/api : 747 test yeşil · ruff check + format temiz
apps/web : 257 test yeşil · tsc --noEmit temiz
```

**Suite süresi 224 sn → 28 sn.** Bu dalın kendi test sayısı etkisi: API'de
+23 (eklenen `test_text_tr.py`, `test_llm_json.py`, kademe bekçisi), web'de
−10/+5 (silinen ikiz eşleme testleri, yerine tek blok). Geri kalan artış
birleşen şeritlerden geliyor. Fixture birleştirmesinde toplanan node kimlikleri
öncesiyle birebir aynı — kayıp yok.
