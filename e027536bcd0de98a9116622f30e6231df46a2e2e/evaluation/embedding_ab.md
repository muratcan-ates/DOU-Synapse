# Embedding A/B: multilingual-e5-large vs bge-m3 (T045)

**Durum: KOŞULDU — 9 Ağustos 2026.**
**Sonuç: bge-m3'ün daha iyi olduğuna dair kanıt YOK. Üretim indeksi DEĞİŞMİYOR.**

Koşu dosyaları:

| Kol | Dosya |
|---|---|
| e5, hibrit | `results/2026-08-09T1657-holdout-hybrid-fastembed-retrieval.json` |
| e5, dense | `results/2026-08-09T1658-holdout-dense-fastembed-retrieval.json` |
| bge-m3, hibrit | `results/2026-08-09T1657-holdout-hybrid-bge-m3-onnx-retrieval.json` |
| bge-m3, dense | `results/2026-08-09T1658-holdout-dense-bge-m3-onnx-retrieval.json` |
| karşılaştırma (dense) | `results/holdout-dense-fastembed-vs-dense-bge-m3-onnx-comparison.json` |
| karşılaştırma (hibrit) | `results/holdout-hybrid-fastembed-vs-hybrid-bge-m3-onnx-comparison.json` |

Korpus: `sample_data/isletim-sistemleri v2` — 22 belge, 167 chunk. Set: holdout,
105 puanlanabilir soru. git: `27b68d4`.

---

## 1. Neden bu karşılaştırma yapıldı

`app/modules/ingestion/embedding.py` şunu kaydediyor: mimaride ilk tercih bge-m3'tü,
fastembed'in dense kataloğunda bulunmadığı için multilingual-e5-large seçildi ve
bge-m3 "3. haftadaki embedding A/B karşılaştırmasının adayı" olarak bırakıldı. Bu
belge o karşılaştırmadır.

Soru dar ve ölçülebilir: **aynı korpus ve aynı sorularda hangi embedding beklenen
kaynağı daha sık ve daha üst sırada getiriyor?**

## 2. Kurulum — iki ayrı indeks, tek şema

`EMBEDDING_PROVIDER` bir **ingest-zamanı** kararıdır: sağlayıcı değişince vektör uzayı
değişir ve mevcut indeks anlamsızlaşır. Bu yüzden A/B, çalışma zamanında bir anahtar
çevirerek değil **iki ayrı veritabanı kurarak** yapıldı:

| Kol | Veritabanı | Sağlayıcı |
|---|---|---|
| Referans | `dou_synapse_eval` | fastembed · `intfloat/multilingual-e5-large` |
| Aday | `dou_synapse_eval_bge` | onnxruntime · `BAAI/bge-m3` (öneksiz) |

**Üretim indeksine dokunulmadı.** İki korpus da aynı materyalden, aynı üretim ingest
hattıyla kuruldu; tek fark embedding sağlayıcısı.

Boyut ikisinde de **1024**. Bu, karşılaştırmayı ucuzlatan tesadüf değil bir imkândır:
`vector(1024)` kolonu ve şema hiç değişmeden ikinci indeks kurulabildi.

### bge-m3 neden fastembed ile koşmuyor

fastembed 0.8.0'ın dense model kataloğunda **bge-m3 yok**
(`TextEmbedding.list_supported_models()` çıktısında BAAI ailesinden yalnız İngilizce
`bge-*-en` modelleri var). Bu, üretim kodundaki notu doğrular. Model bu yüzden resmî
`BAAI/bge-m3` deposundaki ONNX dışa aktarımından, doğrudan `onnxruntime` ile
koşturuldu (`evaluation/embedding_bge_m3.py`). Yeni bir çalışma zamanı
(torch / sentence-transformers) getirilmedi; `onnxruntime` ve `tokenizers` zaten
fastembed ile birlikte kurulu.

Sağlayıcı üretim paketine **girmedi**: bir aday, bir üretim seçeneği değildir.
`config.py`'nin `Literal["fastembed","hashing"]` şeması değiştirilmedi (o dosya bu
şeridin değil); sağlayıcı `set_embedding_provider()` kancasıyla enjekte edildi.

### Önek farkı — sessiz bir çöp kaynağı

E5 ailesi `query: ` / `passage: ` öneklerini **zorunlu** kılar; bge-m3 önek
**kullanmaz**. İkisini karıştırmak hata vermez, yalnız retrieval kalitesini sessizce
düşürür. Her kol kendi doğru biçiminde koştu:

- e5: önek `FastEmbedProvider` içinde, testle sabit (`"e5" in model_name` kontrolü).
- bge-m3: önek eklenmiyor; sağlayıcının `name` alanı bunu `"(onnx, öneksiz)"` diye
  yazıyor ve sonuç dosyalarına aynen geçiyor.

## 3. Sonuçlar

### Ham metrikler (holdout, n=105 puanlanabilir soru)

| Kol | Recall@5 | Recall@8 | MRR | Tam kapsama@8 (n=26) | p95 (sn) |
|---|---:|---:|---:|---:|---:|
| e5, hibrit | **0,971** | **0,981** | **0,854** | 0,885 | 0,106 |
| e5, dense | 0,962 | **0,981** | 0,807 | 0,885 | 0,103 |
| bge-m3, hibrit | **0,971** | **0,981** | 0,839 | **0,923** | 0,099 |
| bge-m3, dense | 0,914 | 0,933 | 0,800 | 0,885 | 0,096 |

### Eşleştirilmiş karşılaştırma — dense kolu

**Karşılaştırmanın asıl kolu budur.** Hibrit kolda skorun yarısını FTS üretir ve FTS
iki kolda da aynıdır; embedding farkı orada seyreltilir. Embedding'i yalıtan ölçüm
dense koldur.

Referans e5, aday bge-m3. Eşleştirilmiş bootstrap 10.000 yeniden örnekleme, tohum
sabit (20260809), %95 GA. McNemar tam (binom) biçimde.

| Ölçüt | n | e5 | bge-m3 | Fark | %95 GA | Sıfırı dışlıyor mu |
|---|---:|---:|---:|---:|---|---|
| İsabet@5 | 105 | 0.962 | 0.914 | −0.048 | [−0.095, +0.000] | hayır (McNemar p=0.125, 7 ayrışan) |
| **İsabet@8** | 105 | **0.981** | 0.933 | **−0.048** | **[−0.095, −0.010]** | **evet** (McNemar p=0.0625, 5 ayrışan) |
| Karşılıklı sıra (MRR) | 105 | 0.807 | 0.800 | −0.007 | [−0.053, +0.041] | hayır |
| Tam kapsama@8 | 26 | 0.885 | 0.885 | ±0.000 | [−0.115, +0.115] | hayır (p=1.00) |

### Eşleştirilmiş karşılaştırma — hibrit kolu

| Ölçüt | n | e5 | bge-m3 | Fark | %95 GA | Sıfırı dışlıyor mu |
|---|---:|---:|---:|---:|---|---|
| İsabet@5 | 105 | 0,971 | 0,971 | ±0,000 | [−0,029, +0,029] | hayır (p=1,00) |
| İsabet@8 | 105 | 0,981 | 0,981 | ±0,000 | [−0,029, +0,029] | hayır (p=1,00) |
| Karşılıklı sıra | 105 | 0,854 | 0,839 | −0,014 | [−0,050, +0,020] | hayır |
| Tam kapsama@8 | 26 | 0,885 | 0,923 | +0,038 | [+0,000, +0,115] | hayır (p=1,00) |

### Kategori kırılımı (MRR / Recall@5)

| Kategori | n | e5 dense | bge dense | e5 hibrit | bge hibrit |
|---|---:|---|---|---|---|
| `direct` | 45 | 0,781 / 0,98 | 0,798 / 0,93 | 0,889 / 1,00 | 0,869 / 0,98 |
| `multi_chunk` | 22 | 0,848 / 0,95 | **0,909 / 1,00** | 0,864 / 1,00 | 0,894 / 1,00 |
| `technical_term` | 24 | 0,726 / 0,92 | **0,630 / 0,75** | 0,806 / 0,92 | 0,753 / 0,96 |
| `code_review` | 14 | 0,964 / 1,00 | 0,929 / 1,00 | 0,807 / 0,93 | 0,807 / 0,93 |

## 4. Okuma

**bge-m3'ün daha iyi olduğuna dair hiçbir kanıt yok.** Dört ölçütün üçünde fark
sıfırdan ayrılmıyor; ayrıldığı tek yerde (dense kolu, İsabet@8) **e5 önde**.

O tek bulgu da zayıftır ve bunu açıkça yazmak gerekir: **iki test aynı şeyi
söylemiyor.** Bootstrap aralığı sıfırı kıl payı dışlıyor (üst sınır −0.010), McNemar
tam testi ise p=0.0625 ile alışılmış eşiğin altına inmiyor ve yalnız 5 soru
ayrışıyor. Beş soruluk bir ayrışmadan "e5 daha iyidir" hükmü çıkmaz; çıkarılabilecek
tek şey **"bge-m3 daha iyi değil"**dir.

Kategori kırılımındaki tek belirgin fark `technical_term`: bge-m3 dense kolda
Recall@5'i 0.92'den 0.75'e düşürüyor (n=24). Bu alt küme, `TLB`, `FTL`, `WCET`, `ASLR`
gibi kısaltmaların birebir arandığı sorulardan oluşuyor. İki gözlem, ikisi de
**hipotez düzeyinde**: (a) e5'in `query:`/`passage:` öneki kısa sorgularda yardımcı
olabilir, (b) hibrit kolda bu fark kapanıyor — FTS kısaltmaları zaten birebir
yakalıyor. Bunu doğrulamak ayrı bir deney ister ve **yapılmadı**.

## 5. Karar: üretim indeksi değişmiyor

Ölçüm zaten göç için yapılmamıştı (12_R2_OLCUM.md İş 1: "bge-m3 kazanırsa bile üretim
indeksini değiştirme"). Sonuç bu kararı ayrıca destekliyor: kazanmadı.

**Değiştirme maliyeti tüm korpusun yeniden işlenmesidir.** Sağlayıcı değişince vektör
uzayı değişir; mevcut hiçbir embedding kullanılamaz, her belge yeniden parçalanıp
yeniden gömülmelidir. Bu koşuda 167 chunk'lık bir korpusun bge-m3 ile kurulması
**yaklaşık 6 dakika** sürdü (CPU, fp32 ONNX); gerçek bir dersin materyali bunun kat
kat üstündedir. Ölçülebilir bir kazanç olmadan katlanılacak bir maliyet değil.

## 6. Sınırlılıklar — bu bölüm okunmadan sayı kullanılmasın

- **n=105 yön göstericidir, kesin hüküm değildir.** Alt kümeler n=14-45 arasında; bu
  boyutta tek bir sorunun sonucu kategori oranını birkaç puan oynatır.
- **Tek korpus, tek ders, tek dil karışımı.** Sonuç "bge-m3 genel olarak kötüdür"
  demek değildir; bu materyalde bir üstünlük göstermediği demektir.
- **bge-m3 fp32 ONNX ile koşturuldu**, fastembed'in e5 için kullandığı niceleme
  (quantization) ayarıyla birebir aynı olmayabilir. Yani ölçülen şey saf model farkı
  değil, **iki çalıştırma yolunun** farkıdır. Bu, e5 lehine bir yanlılık üretiyorsa
  sonucu değil sonucun yönünü zayıflatır — ki sonuç zaten "fark yok"tur.
- **Karşılaştırmada üç ayar birden değişiyor** (`embedding_provider`,
  `embedding_model`, `database`) ve karşılaştırma dosyası bunu `varied` alanında
  bildiriyor. `database` farkı bir karıştırıcı DEĞİLDİR: iki veritabanı aynı
  materyalden aynı hatla kuruldu ve ikisinde de 167 chunk var; ayrı indeks zaten
  yöntemin gereği. Yine de dosyada görünür durması gerekiyordu.
- **Bu bir retrieval katmanı ölçümüdür.** Cevap kalitesi, atıf doğruluğu ve
  faithfulness ölçülmedi; embedding'in onlara etkisi bu koşudan çıkarılamaz.

## 7. Ek sınırlılık — hibrit kol korpus yeniden kurulunca oynuyor

Bu karşılaştırma iki kez koşuldu: korpuslar silinip aynı materyalden, aynı sağlayıcı
ve sürümle yeniden kuruldu. **Dense kol birebir aynı sonucu verdi** (İsabet@5 0,9619
ve MRR 0,8071, iki kurulumda da). **Hibrit kol oynadı** (İsabet@5 0,981 → 0,971).

Sebep `fts.py`'deki `ORDER BY rank DESC, c.id`: eşit `ts_rank`'li chunk'lar arasında
sıralamayı belirleyen `chunks.id` her ingest'te yeniden üretiliyor. Ayrıntı
`docs/test-report.md` §6.4'te.

**Bu karşılaştırma için sonucu değiştirmiyor:** iki kurulumda da hibrit kolda dört
ölçütün dördü sıfırdan ayrılmadı ve dense koldaki İsabet@8 farkı korundu. Ama
karşılaştırmanın hibrit yarısının **ondalık basamakları** yeniden üretilebilir
değildir ve öyle sunulmamalıdır.

Yukarıdaki tablolar **son** kurulumun sayılarıdır; iki kolun ikisi de aynı kurulum
turundan gelir, dolayısıyla karşılaştırma kendi içinde tutarlıdır.

## 8. Yeniden üretme

```bash
cd apps/api

# İki korpus (aday korpus ~6 dakika sürer)
EMBEDDING_PROVIDER=fastembed uv run python ../../evaluation/build_corpus.py \
    --database dou_synapse_eval --recreate --out /tmp/corpus_e5.json
EMBEDDING_PROVIDER=fastembed uv run python ../../evaluation/build_corpus.py \
    --database dou_synapse_eval_bge --recreate --embedding-override bge-m3 \
    --out /tmp/corpus_bge.json

# Dört koşu
for mode in hybrid dense; do
  EMBEDDING_PROVIDER=fastembed uv run python ../../evaluation/evaluate.py \
      --set holdout --layer retrieval --mode $mode \
      --corpus /tmp/corpus_e5.json --threshold-calibrated
  EMBEDDING_PROVIDER=fastembed uv run python ../../evaluation/evaluate.py \
      --set holdout --layer retrieval --mode $mode \
      --corpus /tmp/corpus_bge.json --embedding-override bge-m3 --threshold-calibrated
done

# Eşleştirilmiş karşılaştırma
uv run python ../../evaluation/evaluate.py --compare \
    ../../evaluation/results/<e5-dense>.json ../../evaluation/results/<bge-dense>.json
```

**Model kopyası diskte DEĞİL.** T045 bittikten sonra `~/.cache/dou-eval-models`
silindi: 2,1 GB tutuyordu ve makinede beş şerit birden çalışırken boş alan 1 GB'a
inmişti. Model bir sonuç değil, yeniden indirilebilir bir önbellektir; ölçümün
kendisi `results/` altındaki koşu dosyalarında duruyor. Yeniden koşmak isteyen
önce indirir (~2,3 GB):

```bash
uv run python -c "from huggingface_hub import snapshot_download; \
    snapshot_download('BAAI/bge-m3', allow_patterns=['onnx/*'], \
    cache_dir='$HOME/.cache/dou-eval-models')"
```
