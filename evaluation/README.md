# evaluation/ — ölçüm altyapısı

Bu klasör projenin **iddialarını kanıtlayan** koddur. Diğer şeritler ürünü yapıyor;
burası ürünün iyi olduğunu ölçüyor. Anayasa III net: **koşturulmayan deney için sonuç
yazılmaz.**

## Dosya haritası

| Dosya | İş |
|---|---|
| `gold_set/calibration.json` | Eşik ayarı seti (~15 soru). Metrik **raporlanmaz** |
| `gold_set/holdout.json` | Metriklerin raporlandığı set (76 soru) |
| `gold_set/SCHEMA.md` | Kayıt biçimi ve `expected_sources` kuralları |
| `goldset.py` | Gold set yükleme, doğrulama, kaynak eşleme — tek kaynak |
| `verify_gold_set.py` | Denetim: yapısal · ayrıklık · kaynaklar gerçek mi |
| `build_corpus.py` | Ölçüm korpusunu üretim hattından geçirerek kurar |
| `backends.py` | Retrieval ve sohbet arka uçlarına bağlanma noktası |
| `metrics.py` | Metrik tanımları — saf fonksiyonlar |
| `evaluate.py` | Koşu CLI'ı |
| `calibration.md` | Eşik kararı ve gerekçesi (T043) |
| `faithfulness/sample_template.md` | İki bağımsız etiketleyici şablonu (T047) |
| `results/` | Tarihli koşu çıktıları — raporun kaynağı |

Metrik ve harness testleri `apps/api/tests/test_eval_metrics.py`'de yaşar; oraya
konmalarının sebebi CI'ın her koşuda tanımları doğrulaması.

## Sıra

```bash
cd apps/api

# 1) Gold set sağlam mı (veritabanı gerekmez, saniyeler sürer)
uv run python ../../evaluation/verify_gold_set.py

# 2) Korpusu kur. ÖLÇÜM koşusu için EMBEDDING_PROVIDER=fastembed ŞART.
EMBEDDING_PROVIDER=fastembed uv run python ../../evaluation/build_corpus.py \
    --database dou_synapse_eval --recreate --out /tmp/corpus.json

# 3) Gold set kaynakları gerçek korpusta da var mı
DATABASE_URL=postgresql+psycopg://dou_app:dou_app_local@localhost/dou_synapse_eval \
  uv run python ../../evaluation/verify_gold_set.py --corpus /tmp/corpus.json

# 4) Önce kaç istek atılacağını gör
uv run python ../../evaluation/evaluate.py --set calibration --layer retrieval \
    --mode hybrid --corpus /tmp/corpus.json --dry-run

# 5) Koş
uv run python ../../evaluation/evaluate.py --set calibration --layer retrieval \
    --mode hybrid --corpus /tmp/corpus.json
```

Uçtan uca katman için API ayakta olmalı ve `--api-url` verilmelidir.

## Pazarlıksız kurallar

**Kalibrasyon ve holdout karışmaz.** Eşik kalibrasyonla ayarlanır, metrikler
holdout'ta raporlanır. `evaluate.py` her koşudan önce ayrıklık denetimi koşar ve
kesişim bulursa koşuyu hiç başlatmaz. Karışırlarsa jüri tek soruyla ölçüm bölümünü
çürütür: "yani eşiği test setinde ayarladınız."

**Holdout'a erken bakılmaz.** Harness denemeleri kalibrasyon setiyle ya da
`--limit 3` ile yapılır.

**`EMBEDDING_PROVIDER=hashing` ile ölçüm yapılmaz.** Yerel varsayılan deterministik
sahte vektör üretir: hata vermez, yalnız sonuçlar anlamsızdır. `build_corpus.py` ve
`evaluate.py` bu durumda uyarır ama engellemez — engellemek yerel geliştirmeyi de
kapatırdı. Uyarıyı görmezden gelen sayı rapora giremez.

**Meta verisi olmayan koşu rapora giremez.** Her sonuç dosyası git SHA'sı, embedding
sağlayıcısı, retrieval parametreleri, LLM modelleri ve eşiğin kalibre edilip
edilmediğini taşır.

**Gold set'e chunk UUID'si yazılmaz.** `chunks.id` her ingest'te yeniden üretilir.
Kalıcı kimlik `(dosya, sayfa/slayt)`; doğrulayıcı UUID görürse hata verir.

## Eval için ayrı LLM anahtarı

Uçtan uca koşular kotayı yer. Demo anahtarıyla eval koşmak demo günü kota bitmesi
demektir. `evaluate.py` `EVAL_LLM_API_KEY` ortam değişkenini okur ve her sonuç
dosyasına ayrı anahtar kullanılıp kullanılmadığını yazar:

```bash
export EVAL_LLM_API_KEY=...   # demo anahtarından AYRI hesap
```

**Gruba istek:** anahtarın `Settings` üzerinden okunması için `app/core/config.py`'ye
bir `# --- Eval ---` bölümü ve `.env.example`'a boş bir şablon satırı gerekiyor. İkisi
de bu şeridin dosyası değil (00_OKU_ONCE §1: config.py'ye yeni alan gruba yazılarak
eklenir), o yüzden harness şimdilik değişkeni doğrudan ortamdan okuyor. İşlev tam;
eksik olan yalnız ayarın şemaya girmesi.

## Koşu disiplini

- **Gece koş.** Gündüz kota takımın geliştirmesine ait.
- **Eşzamanlılık 1-2.** Ücretsiz katmanda paralellik koşuyu hızlandırmaz, 429 üretir.
- **Devam edilebilir.** Her sonuç anında `results/.progress/<parmak-izi>.jsonl`'e
  yazılır; yarıda kesilen koşu baştan başlamaz ve aynı soru iki kez LLM'e gitmez.
  Ayar değişince parmak izi değişir, yani eski cevaplar yeni koşuya sızmaz.
- **Önce `--dry-run`.** Kaç istek atılacağını görmeden uzun koşu başlatılmaz.

## Otomatik ölçülemeyen ne var

Injection ve Sokratik sızıntı kategorilerinde harness yalnız **açık** ihlalleri
işaretler (kod bloğu, semafor çağrısı, sistem yönergesi ifşası). İşaret çıkmaması
sızıntı olmadığını kanıtlamaz. Uçtan uca koşu bu vakaları
`results/<run_id>.review.md` dosyasına döker; o dosya doldurulmadan injection ve
sızıntı sonuçları rapora giremez.

Rapor dili bu yüzden **"bilinen temel kalıplara karşı smoke-test edildi"**;
"dayanıklı" denmez.
