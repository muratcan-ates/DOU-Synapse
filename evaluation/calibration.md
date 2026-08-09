# Evidence eşiği kalibrasyonu (T043)

**Durum: KOŞULDU — 9 Ağustos 2026.**
**Seçilen değer: `evidence_threshold = 0.81`**

Koşu dosyaları:
- `evaluation/results/2026-08-09T1409-calibration-hybrid-retrieval.json`
- `evaluation/results/2026-08-09T1409-calibration-dense-retrieval.json`

Korpus: `sample_data/isletim-sistemleri v1`, `EMBEDDING_PROVIDER=fastembed`
(`intfloat/multilingual-e5-large`, 1024 boyut). git: `6c7419f`.

---

## 1. Neyi ayarlıyoruz

`Settings.evidence_threshold`. Kanıt kapısı `app/modules/retrieval/service.py`
içinde şöyle karar veriyor:

```python
best_dense = max((chunk.dense_score for chunk in chunks), default=0.0)
abstained = best_dense < settings.evidence_threshold
```

Yani kapı **yalnız füzyonlu listedeki en yüksek dense skora** bakar. Kalibrasyon bu
sayının dağılımını ölçmekten ibarettir ve **LLM'e hiç gitmez** — bu yüzden tarama
ucuzdur, birkaç saniye sürer ve istendiği kadar tekrarlanabilir.

## 2. Karar: kalibrasyon seti holdout'tan kesilmedi

15 soru holdout'un içinden çıkarılsaydı holdout'un kategori dağılımı (20/10/10/10)
bozulur ve alt küme sayıları düşerdi; `multi_chunk` gibi zaten n≈10 olan bir
kategoride bu, sayıyı anlamsızlaştırırdı. Ayrı yazılan set ayrıca "ayrı dosya, ayrı
zaman, holdout'a hiç bakılmadı" savunmasını git geçmişine dayandırılabilir kılıyor.

Kalibrasyon seti holdout'un kategori oranlarını yansıtır (6 direct, 3 multi_chunk,
3 technical_term, 3 out_of_scope) ama aynı soruları içermez. Ayrıklık her koşudan
önce makineyle denetleniyor.

## 3. Holdout'a bakılmadı beyanı

**Eşik, holdout setine bakılmadan seçilmiştir.** Bu belgedeki tablo ve seçim, 9
Ağustos 2026 saat 14:09'da koşulan iki kalibrasyon koşusundan üretildi; o an
`evaluation/results/` içinde hiçbir holdout koşusu yoktu. Holdout koşuları eşik
dondurulduktan **sonra** yapıldı.

Beyanı destekleyen mekanizmalar:

- `evaluate.py` her koşuda kalibrasyon-holdout ayrıklığını denetler; kesişim bulursa
  koşuyu başlatmaz.
- Holdout, `--threshold-calibrated` bayrağı olmadan koşulduğunda harness "holdout
  eşik ayarı için KOŞULMAZ" uyarısı basar.
- Koşu dosyalarının `run_id`'si tarih-saat taşır; sıralama denetlenebilir.

## 4. Ölçülen dağılım

`best_dense_score`, kalibrasyon setinin 15 sorusu için (hibrit kol):

| Sınıf | n | min | max |
|---|---:|---:|---:|
| Kapsam dışı | 3 | 0.7824 | **0.8066** |
| Cevaplanabilir | 12 | **0.8121** | 0.8963 |

**İki sınıf bu sette AYRIK.** Ayrışma aralığı `(0.8066, 0.8121]`, genişlik **0.0054**.

Dense-only kolda da aynı: kapsam dışı max 0.8075, cevaplanabilir min 0.8121. Yani
seçilecek tek bir eşik iki kolda da çalışıyor — T044 karşılaştırmasının aynı config
altında yapılabilmesi için bu gerekliydi.

### Tarama (hibrit kol, 0.005 adımla)

| Eşik | Doğru ret (3'te) | Kaçan kapsam dışı | Yanlış ret (12'de) | Cevaplanan |
|---:|---:|---:|---:|---:|
| 0.780 | 0 | 3 | 0 | 12 |
| 0.785 | 1 | 2 | 0 | 12 |
| 0.800 | 1 | 2 | 0 | 12 |
| 0.805 | 1 | 2 | 0 | 12 |
| **0.810** | **3** | **0** | **0** | **12** |
| 0.815 | 3 | 0 | 2 | 10 |
| 0.830 | 3 | 0 | 2 | 10 |
| 0.850 | 3 | 0 | 6 | 6 |
| 0.900 | 3 | 0 | 12 | 0 |

Tam tablo koşu dosyalarının `metrics.threshold_sweep` alanında. Yeniden üretmek için:

```bash
cd apps/api && uv run python ../../evaluation/evaluate.py \
    --sweep-from ../../evaluation/results/2026-08-09T1409-calibration-hybrid-retrieval.json \
    --sweep-min 0.78 --sweep-max 0.83 --sweep-step 0.005
```

## 5. Seçilen değer ve gerekçesi

**`evidence_threshold = 0.81`** — ayrışma aralığının orta noktası (0.8094 ≈ 0.81).

Gerekçe:

1. Aralığın **ortası** seçildi, kenarı değil. Kenar seçmek (0.8066'ya yapışmak veya
   0.8121'e yapışmak) tek bir sorunun skorunun birkaç binde oynamasıyla kararı
   çevirirdi.
2. Bu değerde kalibrasyon setinde **her iki hata da sıfır**: 3/3 kapsam dışı soru
   reddediliyor, 12 cevaplanabilir sorunun hiçbiri reddedilmiyor.
3. İki kol (dense ve hybrid) için de geçerli, yani T044 karşılaştırması aynı config
   altında yapılabiliyor.

### Bulgu: mevcut varsayılan 0.35 ATIL

`config.py`'deki başlangıç değeri **0.35**. Ölçülen dağılımda hiçbir sorunun
`best_dense_score`'u 0.78'in altına inmiyor — yani **0.35'lik bir eşik hiçbir zaman
tetiklenmez.** Kapı kodda var ama pratikte kapalı bir anahtar: her kapsam dışı soru
retrieval kapısını geçer.

Sebep, e5 kosinüs benzerliklerinin dar ve yüksek bir bantta toplanması. Sayı bir
tahmin olarak makul görünüyordu; ölçülünce işlevsiz olduğu görüldü. Kalibrasyonun
tam olarak yakalaması gereken şey buydu.

**Şerit 1'e bildirim:** `config.py`'deki değer `0.35` → `0.81` olarak
güncellenmelidir ve yanındaki "KALİBRE EDİLMEMİŞTİR" notu bu belgeye referansla
değiştirilebilir. Değişikliği bu şerit yapmaz; dosya Şerit 1'in.

## 6. Sınırlılıklar — bu bölüm okunmadan sayı kullanılmasın

- **Ayrışma aralığı çok dar: 0.0054.** İki sınıf ayrık ama teğet geçiyor. Yeni bir
  kapsam dışı soru 0.812 skoru alırsa eşik onu kaçırır.
- **Kapsam dışı örneklem n=3.** Bu, bir eşik seçmek için küçüktür. Seçim yön
  göstericidir, kesin hüküm değildir.
- **Bu bir RETRIEVAL katmanı kalibrasyonudur.** Uçtan uca davranış guardrail
  zincirini de içerir; kapının açtığı bir sorgu ilerideki bir halkada yine
  reddedilebilir. Kapsam dışı ret oranı (SC-005) **holdout'ta, uçtan uca** ölçülür.
- **Eşik kapsam dışı soruların hepsini yakalasa bile atıf doğruluğunu garanti
  etmez.** İkisi ayrı mekanizma, ayrı metrik.

## 7. Sonraki adım — holdout doğrulaması

Eşik dondurulduktan sonra holdout üzerinde koşuldu. Sonuç `docs/test-report.md`'de.

**Kural:** holdout sonucu kötü çıkarsa eşik holdout'a bakarak DEĞİŞTİRİLMEZ. Doğru
hamle kalibrasyon setini büyütüp yeniden kalibre etmektir; aksi hâlde holdout ikinci
bir kalibrasyon setine dönüşür ve ölçüm bölümünün tamamı düşer.
