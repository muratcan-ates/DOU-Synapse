# Başarı testi raporu (T056)

**Sürüm: taslak · 9 Ağustos 2026** (retrieval katmanı ölçüldü; uçtan uca katman KOŞULMADI)
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
| Ölçme + analitik izolasyonu (0004'ün 15, 0005'in 1 politikası) | 0 sızıntı | **0** (58/58 iddia, 24/24 mutasyon yakalandı) | `supabase/tests/rls_assessment.sql` + `rls_assessment_mutation_check.sh` |
| Kaynaksız gösterilen akademik cevap | %0 | **KOŞULMADI** | generation + guardrail hattı inmedi |
| Holdout Recall@5 | ≥ %80 | **%100** (45/45) — §6'daki uyarıyla | `2026-08-09T1412-holdout-hybrid-retrieval.json` |
| Holdout Recall@8 | ≥ %80 | **%100** (45/45) — §6'daki uyarıyla | aynı dosya |
| Holdout MRR | — | **0.893** (hibrit) · 0.774 (dense) | aynı dosya + dense koşusu |
| Citation precision | ≥ %90 | **KOŞULMADI** | uçtan uca koşu yapılmadı |
| Kapsam dışı doğru ret (retrieval kapısı) | ≥ %90 | **%80** (8/10) — hedefin ALTINDA | `evaluation/calibration.md` §7 |
| Kapsam dışı doğru ret (uçtan uca, SC-005) | ≥ %90 | **KOŞULMADI** | uçtan uca koşu yapılmadı |
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
| Ölçme + analitik iddiaları (`rls_assessment.sql`) | 58 PASS / 0 FAIL |
| Kapsanan politika | 0004'ün 15 politikasının tamamı + 0005'in eğitmen okuma politikası |
| Politikası olmayan işlemler (fail-closed sınandı) | questions DELETE, answers UPDATE, mastery DELETE |
| Mutasyon testi | 24 mutasyon, **24'ü yakalandı** |

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

## 6. Holdout retrieval metrikleri ve baseline vs hybrid (T044)

**KOŞULDU — 9 Ağustos 2026.** Aynı holdout, aynı gün, aynı config; yalnız arama
modu değişti. Korpus `fastembed` (`intfloat/multilingual-e5-large`) ile gömüldü.

### Holdout metrikleri (n=45 puanlanabilir soru, 55 soru soruldu)

| Metrik | Dense-only | Hibrit (dense+FTS+RRF) |
|---|---:|---:|
| Recall@5 | 1.000 | 1.000 |
| Recall@8 | 1.000 | 1.000 |
| MRR | 0.774 | **0.893** |
| Tam kapsama@8 (çok kaynaklı, n=14) | 0.929 | 0.857 |
| p95 gecikme (retrieval, LLM'siz) | 0.102 sn | 0.089 sn |

Kategori kırılımı (hibrit): `direct` n=20 MRR 0.892 · `multi_chunk` n=10 MRR 0.950 ·
`technical_term` n=10 MRR 0.850 · `code_review` n=5 MRR 0.867.

### ⚠️ Recall %100 bir başarı ölçüsü DEĞİL — korpus çok küçük

Korpusun tamamı **33 chunk**. `top_k=8`, yani her sorguda korpusun yaklaşık **dörtte
biri** dönüyor. Bu boyutta Recall@8'in 1.0 çıkması retrieval kalitesinden çok
korpusun küçüklüğünün sonucudur. **Hedef tutturuldu ama test zayıftır ve bu sayı
"retrieval iyi çalışıyor" diye okunmamalıdır.**

Ayırt edici olan metrik burada **MRR**: aynı sonuçlar bulunuyor ama hibrit onları
belirgin biçimde daha üst sıralara koyuyor.

Bu sınırlılığı gidermenin yolu materyali büyütmektir (daha çok dosya/sayfa). Şu anki
paket chunking, atıf ve sayfa metadata'sı testleri için tasarlandı; retrieval
sıralamasını zorlamak için değil.

### Eşleştirilmiş anlamlılık

Referans dense-only, aday hibrit. Eşleştirilmiş bootstrap 10.000 yeniden örnekleme,
tohum sabit (20260809), %95 GA. McNemar yalnız ikili ölçütlerde, tam (binom) biçimde.
Kaynak: `evaluation/results/holdout-dense-vs-hybrid-comparison.json`.

| Ölçüt | n | Dense | Hibrit | Fark | %95 GA | Sıfırı dışlıyor mu |
|---|---:|---:|---:|---:|---|---|
| İsabet@5 | 45 | 1.000 | 1.000 | +0.000 | [0.000, 0.000] | hayır (McNemar p=1.00, 0 ayrışan) |
| İsabet@8 | 45 | 1.000 | 1.000 | +0.000 | [0.000, 0.000] | hayır (McNemar p=1.00, 0 ayrışan) |
| **Karşılıklı sıra (MRR)** | 45 | 0.774 | 0.893 | **+0.119** | **[+0.054, +0.191]** | **evet** |
| Tam kapsama@8 | 14 | 0.929 | 0.857 | −0.071 | [−0.286, +0.143] | hayır (McNemar p=1.00, 2/1 ayrışan) |

**Okuma:** hibrit, doğru parçayı dense-only'den daha üst sıraya koyuyor ve bu fark
%95 güven aralığında sıfırı dışlıyor. "Buldu mu" sorusunda iki kol ayrışmıyor —
ama yukarıda anlatıldığı gibi o ölçüt bu korpusta doygun, yani ayrışamaz.

Tam kapsamada dense sayısal olarak önde görünüyor; aralık sıfırı içeriyor ve yalnız
3 soru ayrışıyor, dolayısıyla **fark olduğu söylenemez.**

**n=45 — yön göstergesi, kesin hüküm değildir.** Alt kümeler n≈10-14'tür.

---

## 6b. Kanıt eşiği kalibrasyonu ve holdout doğrulaması (T043)

**KOŞULDU.** Ayrıntı ve tam tablolar `evaluation/calibration.md`'de. Özet:

Seçilen eşik **0.81**, kalibrasyon setinde (n=15) iki sınıfın ayrıştığı 0.0054
genişliğindeki aralığın orta noktası. **Holdout'ta bu ayrışma tutmadı**: kapsam dışı
skorlar [0.7824, 0.8173], cevaplanabilir skorlar [0.7629, 0.9083] — örtüşüyorlar.

Holdout'ta 0.81 eşiğinde: **8/10 doğru ret (%80)**, 2 kaçan, 45 cevaplanabilir
sorunun 5'i yanlışlıkla reddedildi. **PLAN §5 hedefi %90; tutturulmadı.**

İki bulgu ayrıca kayda değer:

1. **`config.py`'deki varsayılan 0.35 atıl.** Ölçülen hiçbir skor 0.76'nın altına
   inmiyor, yani o eşik hiçbir zaman tetiklenmez — kapı kodda var ama pratikte
   kapalı bir anahtar. Tahmin olarak makul görünen bir sayının ölçülünce işlevsiz
   çıkmasının somut örneği.
2. **Eşik holdout'a bakılarak değiştirilmedi ve değiştirilmeyecek.** Tarama 0.820'nin
   holdout'ta 10/10 yakaladığını gösteriyor; o değere geçmek holdout'u ikinci bir
   kalibrasyon setine çevirir ve raporlanan bütün ret sayılarını geçersiz kılardı.
   Doğru hamle kalibrasyon setini büyütmektir.

Bu bölüm, kalibrasyon-holdout ayrımının neden pazarlıksız olduğunun kanıtıdır:
ayrım olmasaydı bu rapor %100 doğru ret yazardı ve sayı hiçbir şey ifade etmezdi.

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

## 8b. Uçtan uca hattın smoke testi — ve bir sözleşme sorunu

**Numaralar rapora girmez; bu bölüm yalnız hattın çalıştığını ve bir tasarım
sorusunu kayda geçirir.**

Uçtan uca harness, gerçek API sunucusuna karşı koşuldu (kalibrasyon seti, 15 soru).
Amaç ölçüm değil, gece koşusundan önce hattın ayakta olduğunu görmekti. Sunucu
`LLM_FAKE_PROVIDER=true` ile koştu, yani **cevap kalitesine dair hiçbir sayı
geçerli değildir** — citation precision ve faithfulness KOŞULMADI olarak kalır.

Hat çalışıyor: 15 soru soruldu, 12'si cevaplandı, 3 kapsam dışı soru reddedildi,
harness sonucu meta verisiyle yazdı.

### ⚠️ Bulgu: kapsam dışı ret `out_of_scope` diye ETİKETLENMİYOR

Üç kapsam dışı sorunun üçü de reddedildi — ama üçü de `insufficient_context`
durumuyla döndü, hiçbiri `out_of_scope` ile değil.

Bu ayrım ölçüm açısından belirleyici. `contracts.AnswerStatus` ikisini bilinçli
olarak ayırıyor: `insufficient_context` "materyalde olabilir ama kanıt zayıf",
`out_of_scope` "bu ders bu konuyu hiç kapsamıyor". **SC-005 yalnız ikincisini
ölçer.** Yani bugünkü davranışla ret F1 = 1.00 çıkarken SC-005 = %0 çıkar; ikisi de
doğru hesaplanmıştır, çünkü farklı şeyleri ölçüyorlar.

Sebep büyük olasılıkla mimari: kanıt kapısı (retrieval) abstention üretiyor ve
abstention'ın doğal etiketi `insufficient_context`. Kapsam dışılığa karar verecek
katman generation/guardrail tarafında.

**Gruba soru (Şerit 1 + Şerit 2):** `out_of_scope` etiketini kim koyacak? Karar
verilmeden SC-005 ölçülemez — ölçülse bile ölçtüğünü iddia ettiği şeyi ölçmez.
Not: bu gözlem sahte sağlayıcıyla yapıldı; gerçek generation hattı farklı
etiketleyebilir ve o hâlde bu bulgu düşer. Doğrulanması gereken bir şüphedir,
kanıtlanmış bir kusur değil.

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
- **Kapsam dışı ret oranı `request_logs`'tan okunur, `chat_messages`'tan DEĞİL.**
  Bu bir gizlilik kararının sonucu; §11b'ye bakınız.

## 11b. Analitik ile sohbet gizliliği arasındaki çakışma ve çözümü

T038 eğitmene kapsam dışı ret oranını göstermeyi gerektiriyor. İlk uygulama kaynağı
`chat_messages` seçti ve **eğitmen bağlamında her zaman sıfır satır gördü.** Sebep
kusur değildi: 0003, sohbet mesajlarını eğitmene bilinçli olarak kapatmış.

> "Eğitmene okuma yetkisi bilinçli olarak VERİLMEDİ: öğrencinin hocasına sorma
> çekindiği soruyu sisteme sorabilmesi ürünün gerekçelerinden biri, eğitmenin bunu
> satır satır okuyabilmesi bunu bozar." — `0003_chat.sql`

Aynı dosya çözümü de işaret etmişti: ölçüm kaydı için eğitmen kapsamlı bir SELECT
politikası **0005'te** açılacaktı ve 0005 bu şeridin ayrılmış migration numarası.

**Çözüm:** `0005_analytics.sql` yalnız `request_logs` üzerinde eğitmen kapsamlı bir
SELECT politikası açar; analitik oradan okur. Fark belirleyici: `request_logs` şema
gereği **serbest metin taşımaz** (soru metni, cevap metni yok; yalnız sayısal ve
kategorik alanlar). Eğitmen "kaç soru kapsam dışı diye reddedildi" sorusunun cevabını
alır, kimsenin ne sorduğunu göremez. Gizlilik kararı korunur, ölçüm mümkün olur.

Kararın sessizce delinmediği ayrıca sınanıyor: `rls_assessment.sql` içinde
`chat_messages_read__egitmen_ogrenci_sohbetini_OKUYAMAZ` iddiası var ve mutasyon
testi, o politika eğitmene açılırsa iddianın kırmızı yandığını doğruluyor.

---

## 12. Test durumu

**Ölçüldü (9 Ağustos):** `feat/analytics-eval` dalında (origin/main üzerine rebase
edilmiş hâlde) **405 test yeşil**, ruff lint ve biçim temiz.

```bash
cd apps/api && uv run pytest -q && uv run ruff check . && uv run ruff format --check .
```

Bunun 52'si bu dalda eklendi: 13 analitik ucu, 39 metrik + harness testi.

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
