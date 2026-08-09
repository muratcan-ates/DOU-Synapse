# Başarı testi raporu (T056)

**Sürüm: taslak · 9 Ağustos 2026**
**Ölçüm dalı:** `feat/analytics-eval` · **git:** bu belgenin her sayısı bir koşu
dosyasına ya da yeniden koşturulabilir bir komuta dayanır.

> **Bu bir taslaktır ve öyle kalmalıdır.** PLAN §5 tablosunun her satırında ya ölçülmüş
> bir sayı ya **KOŞULMADI** notu vardır. Bugün itibarıyla retrieval, generation ve
> sohbet hatları `main`'e inmediği için kalite metriklerinin çoğu KOŞULMADI'dır.
> Bu bir eksiklik beyanıdır, bir tahmin değil (Anayasa III).

---

## 1. Yöntem

### 1.1 Gold set nasıl oluştu

İki ayrı dosya, iki ayrı amaç:

| Set | Dosya | Soru | Amaç | Metrik raporlanır mı |
|---|---|---:|---|---|
| Kalibrasyon | `evaluation/gold_set/calibration.json` | 15 | Eşik ayarı (T043) | **Hayır** |
| Holdout | `evaluation/gold_set/holdout.json` | 76 | Metrik ölçümü | **Evet** |

Holdout kategori dağılımı: 20 `direct` · 10 `multi_chunk` · 10 `technical_term` ·
10 `out_of_scope` · 15 `injection` · 5 `code_review` · 6 `socratic_leak`.

Sorular `sample_data/isletim-sistemleri` paketi üzerine yazıldı. Materyal takımın
kendi ürettiği metindir; hiçbir dosya bir eğitmenin ders slaytından kopyalanmamıştır
ve gerçek öğrenci verisi yoktur.

### 1.2 Kalibrasyon-holdout ayrımı

Kalibrasyon seti holdout'tan **kesilmedi**, ayrıca yazıldı. Gerekçe ve "holdout'a
bakılmadı" beyanı `evaluation/calibration.md` §2-3'te.

Ayrıklık her koşudan önce **makineyle** denetlenir: `evaluate.py` id ve normalize
edilmiş soru metni üzerinden kesişim arar, bulursa koşuyu hiç başlatmaz.

**Ölçüldü (9 Ağustos):** kesişim yok.

```
PASS  kalibrasyon ↔ holdout ayrıklığı
```

### 1.3 Kaynak eşlemesi nasıl doğrulandı

Gold set'te chunk UUID'si tutulmaz — `chunks.id` her ingest'te yeniden üretilir.
Kalıcı kimlik `(dosya adı, sayfa/slayt)` çiftidir ve chunk id'leri koşu anında
çözülür.

Her `expected_sources` girdisi iki ayrı yöntemle doğrulandı:

1. **Ayrıştırıcı üzerinden** — materyal üretim ayrıştırıcısıyla
   (`app.modules.ingestion.parsers.parse`) okunup her kaynağın karşılığı arandı.
   Sayfa numaraları tahmin edilmedi; ingest'in gerçekten üreteceği numaralar.
2. **Korpus üzerinden** — paket gerçekten ingest edildikten sonra aynı kontrol
   veritabanına karşı koşuldu, dersin bir üyesinin RLS oturumunda.

**Ölçüldü (9 Ağustos):** 91 sorunun tüm kaynakları her iki kontrolde de karşılık
buldu.

```bash
cd apps/api && uv run python ../../evaluation/verify_gold_set.py --corpus /tmp/corpus.json
```

### 1.4 Eğitmen gözden geçirmesi

**KOŞULMADI.** Set, dersi veren/danışman eğitmene (Yasemin Karagül) henüz sunulmadı.
Bu, "kendi sınavını kendin yazmışsın" eleştirisine karşı tek savunmadır ve teslimden
önce yapılmalıdır. Her iki gold set dosyasının `verification.instructor_review`
alanı `BEKLİYOR` olarak işaretlidir.

Aynı şekilde `verification.content_review` de `BEKLİYOR`: doğrulayıcı sayfanın var
olduğunu kanıtlar, **o sayfanın soruyu cevapladığını kanıtlamaz.** İçerik doğrulaması
insan işidir (koordinasyon §8).

---

## 2. Metrik tanımları

Tanımlar `evaluation/metrics.py`'de saf fonksiyonlar olarak yaşar ve
`apps/api/tests/test_eval_metrics.py`'de sabitlenmiştir — yani "Recall@5 neydi"
sorusunun cevabı CI'da koşan koddur.

| Metrik | Tanım |
|---|---|
| **Recall@k** | İlk k sonuç içinde beklenen kaynaklardan **en az biri** bulunan soruların oranı |
| **Tam kapsama@k** | Beklenen kaynakların **hepsi** ilk k'de. Yalnız çok kaynaklı sorularda hesaplanır; tek kaynaklıda Recall'ın aynısıdır ve oranı şişirirdi |
| **MRR** | İlk ilgili sonucun sırasının tersinin ortalaması (`1/rank`; isabet yoksa 0) |
| **Citation precision** | Doğru (dosya + konum) atıf / **gösterilen toplam atıf**. Payda soru sayısı değil, atıf sayısıdır |
| **Ret F1** | Pozitif sınıf "reddedilmeli" (`out_of_scope` + `insufficient_context`). Precision, recall, F1 ve 2x2 matris birlikte |
| **p95** | Sorgu yolu uçtan uca gecikmesinin 95. yüzdeliği, doğrusal aradeğerlemeli tanım, sıcak replikada |

İki tanım kararı ayrıca yazılıdır çünkü sessizce ters yöne çekilebilirler:

- **Hiç atıf gösterilmediyse citation precision tanımsızdır**, 1.0 değil. 1.0 demek,
  hiç atıf yapmayan bir sistemi kusursuz atıf yapıyor göstermek olurdu.
- **Boş kümede Recall 0.0 değil tanımsızdır.** Ölçülmemiş bir şey sıfır diye
  raporlanamaz.

Recall metrikleri yalnız `direct`, `multi_chunk`, `technical_term`, `code_review`
kategorilerinde hesaplanır: `out_of_scope` bir sorunun beklenen kaynağı yoktur ve
Recall'a katılırsa metriği yapay olarak düşürür.

---

## 3. PLAN §5 kabul kriterleri tablosu

| Metrik | Hedef | Ölçülen | Kaynak |
|---|---:|---|---|
| Dersler arası veri sızıntısı | 0 | **0** (çekirdek şema, 8/8 iddia) | `supabase/tests/rls_isolation.sql` |
| Ölçme katmanı izolasyonu (0004, 15 politika) | 0 sızıntı | **0** (53/53 iddia, 21/21 mutasyon yakalandı) | `supabase/tests/rls_assessment.sql` + `rls_assessment_mutation_check.sh` |
| Kaynaksız gösterilen akademik cevap | %0 | **KOŞULMADI** | generation + guardrail hattı inmedi |
| Holdout Recall@5 | ≥ %80 | **KOŞULMADI** | retrieval hattı inmedi |
| Holdout Recall@8 | ≥ %80 | **KOŞULMADI** | retrieval hattı inmedi |
| Citation precision | ≥ %90 | **KOŞULMADI** | uçtan uca hat inmedi |
| Kapsam dışı doğru ret | ≥ %90 | **KOŞULMADI** | uçtan uca hat inmedi |
| Faithfulness (20-30 cevap, 2 etiketleyici) | raporlanır | **KOŞULMADI** | gerçek cevap üretilmedi |
| Sokratik modda kod/çözüm sızıntısı | test setinde 0 | **KOŞULMADI** | Sokratik hat inmedi |
| Injection testleri (≥15 vaka) | geçer | **KOŞULMADI** (vakalar hazır: 15) | guardrail zinciri inmedi |
| Soru üretiminde şema geçerliliği | ≥ %98 | **KOŞULMADI** | soru üretimi Şerit 4'te |
| Uçtan uca cevap p95 | < 10 sn | **KOŞULMADI** | uçtan uca hat inmedi |
| Demo akışında kritik hata | 0 | **KOŞULMADI** | demo provası yapılmadı |

**Ölçülen iki satırın koşu komutları yeniden üretilebilir:**

```bash
createdb rls_check && for f in supabase/migrations/*.sql; do psql -q -d rls_check -f "$f"; done
psql -d rls_check -f supabase/tests/rls_isolation.sql    # 8 PASS, 0 FAIL
psql -d rls_check -f supabase/tests/rls_assessment.sql   # 53 PASS, 0 FAIL
supabase/tests/rls_assessment_mutation_check.sh          # 21/21 mutasyon yakalandı
```

---

## 4. RLS canlılık kanıtı

Projenin tezi "iki katmanlı izolasyon, **kanıtlı**". 6 Ağustos PR incelemesi bu tezin
en zayıf noktasını ölçtü: `0004`'ün on beş politikasının hiçbirinin otomatik kanıtı
yoktu. `questions_read` politikasından `AND status = 'approved'` düşürüldüğünde 92
test yeşil kalıyor, `rls_isolation.sql` 8/8 PASS veriyor ve CI'daki `grep -q FAIL`
kapısı geçiyordu — aynı anda psql'de öğrenci taslak sınav sorusunu görüyordu.

**Bu boşluk kapatıldı.**

| Kanıt | Sayı |
|---|---|
| Çekirdek şema iddiaları (`rls_isolation.sql`) | 8 PASS / 0 FAIL |
| Ölçme katmanı iddiaları (`rls_assessment.sql`) | 53 PASS / 0 FAIL |
| Kapsanan politika | 0004'ün 15 politikasının tamamı |
| Politikası olmayan işlemler (fail-closed sınandı) | questions DELETE, answers UPDATE, mastery DELETE |
| Mutasyon testi | 21 mutasyon, **21'i yakalandı** |

Mutasyon testi "politika var" demekle yetinmez: her politikayı teker teker bozar ve
**hangi iddianın** kırmızıya döndüğünü doğrular. Yalnız "bir yerde FAIL çıktı" demek
yetersiz olurdu, çünkü alakasız bir bozulma da FAIL üretir.

Bu kontrol ilk koşuşunda testin kendisindeki **altı kusuru** buldu; hepsi "yanlış
sebeple yeşil" sınıfındandı (okuma politikasının kurtardığı güncelleme iddiaları, FK
kısıtına takılan silme testi, unique kısıtına takılan yazma testleri). Düzeltilip
yeniden koşuldu.

**Henüz yapılmadı:** T051, aynı kanıtın üretim kopyası/branch'i üzerinde koşturulması.
Yerel ve CI ortamında koşuldu; bulut kopyasında koşulmadı.

**Gruba istek:** CI adımı `.github/workflows/ci.yml`'ye eklenmelidir. O dosya liderin;
komut `supabase/tests/rls_assessment.sql` başındaki yorumda hazır duruyor.

---

## 5. Örnek materyal ve korpus

Paket gerçek ingest hattından geçirildi (Anayasa VIII): gerçek yükleme ucu, gerçek
doğrulama, gerçek worker, gerçek chunking ve embedding. Hiçbir satır doğrudan INSERT
edilmedi.

**Ölçüldü (9 Ağustos): 8/8 dosya `completed`, 33 chunk.**

| Dosya | Chunk | Sayfa no'lu | Slayt no'lu | Embedding'li |
|---|---:|---:|---:|---:|
| `01-processes.pdf` | 3 | 3 | — | 3 |
| `02-cpu-scheduling.pdf` | 4 | 4 | — | 4 |
| `03-memory-management.pdf` | 3 | 3 | — | 3 |
| `04-synchronization.pdf` | 4 | 4 | — | 4 |
| `05-deadlock-demo.pdf` | 4 | 4 | — | 4 |
| `06-file-systems.pptx` | 7 | — | 7 | 7 |
| `fork_example.c` | 2 | — | — | 2 |
| `producer_consumer.py` | 6 | — | — | 6 |

Her PDF chunk'ı sayfa, her slayt chunk'ı slayt numarası taşıyor. Kod chunk'larında
ikisi de yok ve olmamalı — konum bilgisi `section_title` içinde satır aralığı olarak
durur.

**Bu koşu `EMBEDDING_PROVIDER=hashing` ile yapıldı.** Bu deterministik SAHTE bir
embedding'dir: ingest hattının çalıştığını kanıtlar ama **bu korpusta ölçülecek
Recall rapora giremez.** Ölçüm koşuları `fastembed` ile yeniden kurulmuş korpusta
yapılacaktır. `build_corpus.py` ve `evaluate.py` bu durumda uyarır.

---

## 6. Baseline vs hybrid (T044)

**KOŞULMADI.** Retrieval hattı `main`'e inmedi.

Yöntem hazır: aynı holdout, aynı gün, aynı config üzerinde `--mode dense` ve
`--mode hybrid`; soru başına isabet/ıskalama üzerinden **eşleştirilmiş bootstrap**
(10.000 yeniden örnekleme, sabit tohum, %95 güven aralığı) ve **McNemar'ın tam
testi**. İkisi de `evaluation/metrics.py`'de yazılı ve testli.

Eşleştirme şart: iki kol aynı soruları görür, dolayısıyla bağımsız örneklem varsayan
bir test buradaki korelasyonu görmezden gelir ve aralığı olduğundan geniş verir.
McNemar'ın ki-kare yaklaşımı değil tam biçimi kullanılır: n≈50'lik bir sette ayrışan
soru sayısı çoğu zaman tek haneli kalır ve yaklaşım o aralıkta güvenilmez.

---

## 7. Embedding A/B (T045)

**KOŞULMADI.** `multilingual-e5-large` vs `bge-m3`, ≥40 soru, Recall@5 + MRR.

Prosedür (üretim indeksine dokunmadan): ayrı bir veritabanı, ayrı ingest.
`EMBEDDING_PROVIDER` bir **ingest-zamanı** kararıdır — değiştirmek tüm korpusun
yeniden işlenmesi demektir, çalışma zamanında çevrilmez.

---

## 8. Guardrail, sızıntı ve injection (T046)

**KOŞULMADI.** Guardrail zinciri `main`'e inmedi.

Vakalar hazır: holdout'ta 15 injection kaydı (kalıp aileleri: doğrudan geçersiz
kılma, rol değiştirme, dil değiştirme, doküman içi talimat, encode edilmiş talimat,
yetki iddiası, sahte sistem mesajı, veri sızdırma, kalıcı enjeksiyon, araç
karışıklığı) ve 6 Sokratik sızıntı senaryosu (fence'siz kod, pseudocode, sözel
çözüm, ısrarcı öğrenci, aciliyet baskısı).

**Rapor dili kararı:** sonuç geldiğinde "bilinen temel kalıplara karşı **smoke-test
edildi**" denecek. **"Dayanıklı" DENMEYECEK.** Atıf set-membership kontrolü
deterministiktir; injection savunması değildir.

**Otomatik ölçülemeyen kısım:** harness yalnız açık ihlalleri işaretler (kod bloğu,
semafor çağrısı, sistem yönergesi ifşası). **İşaret çıkmaması ihlal olmadığını
kanıtlamaz.** Uçtan uca koşu bu vakaları `evaluation/results/<run_id>.review.md`
dosyasına döker; o dosya iki kişi tarafından doldurulmadan bu bölüm rapora giremez.

**Koordinasyon:** injection vakalarının sahibi R2'dir (`evaluation/injection/`).
Holdout'taki 15 kayıt `r2_case_ref: null` ile duruyor; R2'nin `cases.json`'ı
indiğinde listeler birleştirilecek ve aynı vaka iki yerde ayrı ayrı yaşamayacak.

---

## 9. Faithfulness örneklemi (T047)

**KOŞULMADI.** Gerçek cevap üretilmedi.

Şablon ve yöntem `evaluation/faithfulness/sample_template.md`'de. İki kişi bağımsız
etiketler, ham uyum oranı **çözüm öncesi hâliyle** raporlanır, örneklem sabit tohumla
rastgele seçilir. Uyum hesabı elle yapılmaz: `metrics.label_agreement` testlerle
sabitlenmiştir.

**Citation validator faithfulness'ı ölçmez.** O, modelin retrieve edilmemiş bir
kaynağa atıf yapmasını engeller ve deterministiktir. Model, gerçekten retrieve
edilmiş bir chunk'a atıf verip o chunk'ın söylemediği bir şeyi de yazabilir. İkisi
raporda karıştırılmayacak.

---

## 10. Gecikme ve cold-start (T055)

**KOŞULMADI.** p95 ve cold-start ölçümü yapılmadı. Harness her istek için gecikme
kaydediyor ve p95'i sonuç dosyasına yazıyor; sayı, uçtan uca koşu yapıldığında
buradan gelecek. Ölçüm **sıcak replikada, sorgu yolunda** yapılır.

---

## 11. Analitik uçları (T038)

Uçlar yazıldı ve testli (11 test). İki uç: `GET /courses/{id}/analytics/me`
(öğrenci, kendi konuları) ve `GET /courses/{id}/analytics/class` (eğitmen, sınıf).

Raporlanabilir üç davranış kararı:

- Çalışılmamış konu listeye girmez, sayı olarak bildirilir. Skoru olmayan bir konuya
  0.0 vermek "Geliştirilmeli" etiketi üretir ve öğrenciye hiç çalışmadığı konuda
  başarısız olduğunu söylerdi.
- "En çok yanlış yapılan sorular" payda ile birlikte döner. Değerlendirilmemiş
  cevaplar paydaya girmez: doğru saymak oranı düşürür, yanlış saymak yükseltir.
- **Kapsam dışı ret oranı `chat_messages` tablosunu gerektirir (migration 0003).**
  Tablo yoksa uç sayı uydurmaz: `source: "unavailable"`, `rate: null` döner.

---

## 12. Test durumu

**Ölçüldü (9 Ağustos):** `feat/analytics-eval` dalında **140 test yeşil**, ruff lint
ve biçim temiz.

```bash
cd apps/api && uv run pytest -q && uv run ruff check . && uv run ruff format --check .
```

Bunun 92'si ölçüm dalı başlamadan önce vardı; 48'i bu dalda eklendi (11 analitik,
37 metrik + harness).

---

## 13. Sınırlılıklar

**Bu bölüm rapordan çıkarılamaz.**

- **n=50 civarı bir holdout yön göstericidir, kesin hüküm değildir.** Alt kümeler
  (`multi_chunk`, `technical_term`, `out_of_scope`) n≈10'dur; bu boyutta tek bir
  sorunun sonucu oranı 10 puan oynatır.
- **Gold set'i sistemi yazan takım yazdı.** Eğitmen gözden geçirmesi bunu tamamen
  ortadan kaldırmaz, yalnız hafifletir.
- **Kaynak eşlemeleri makineyle doğrulandı, içerikçe değil.** Doğrulayıcı sayfanın
  var olduğunu kanıtlar; o sayfanın soruyu cevapladığını insan doğrular.
- **Injection ve sızıntı için otomatik işaretler dardır.** İşaretlenmemek ihlal
  olmadığını kanıtlamaz.
- **Bu raporun çoğu satırı bugün KOŞULMADI'dır.** Ölçüm altyapısı hazır ve
  yeniden üretilebilir; eksik olan ölçülecek sistemdir.

---

## 14. Bu belge nasıl tamamlanacak

| Adım | Bağımlılık |
|---|---|
| Korpusu `fastembed` ile yeniden kur | — |
| `--layer retrieval` koşusu (kalibrasyon, sonra holdout) | Şerit 1 `main`'de |
| T043 eşik kalibrasyonu → `calibration.md` | Şerit 1 + 2 `main`'de |
| T044 baseline vs hybrid + anlamlılık | T043 bitmiş |
| T046 injection + sızıntı koşusu | Şerit 2 + 3 `main`'de |
| T047 faithfulness örneklemi (2 etiketleyici) | uçtan uca koşu yapılmış |
| T051 RLS kanıtı üretim kopyasında | dağıtım hazır |
| Eğitmen gözden geçirmesi | gold set dondurulmuş |

**Kural:** her sayının yanında hangi koşu dosyasından geldiği yazılır
(`evaluation/results/<dosya>.json`). Kaynağı gösterilemeyen sayı rapordan çıkarılır.
