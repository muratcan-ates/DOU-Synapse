# C1 daraltılmış son kaynak tekrarları

FTS geri çekmesinden sonra 8 Eylül 2026 tarihinde üç çevrimdışı başlangıç kontrolü yapıldı. Üretim benchmark/probe araçları ve iki geçici holdout çalıştırıcısı değiştirilmedi. Bu kontroller DB veya model çalıştırmadı.

## Kaynak bağı

Aday FTS SHA256 `eceb7954bb865f0b8776db467aaf490ae316f10985de3abc881349705fe6c94b`. Aday dense `020820a4b60307c956b87d609c49f634845a38ea16fb79a96606ea49178e639d`, service `dc09fbe8003598c3bf5364a69d3aead299d64c7a17a824c4fc047ab3b092be4c`, config `16e53fb5e5ea30a8fa2a68674abdbd48226d5e1e2c3cefe3e1654e2527528423`; bu son üç dosya FTS kapsam daraltmasında değişmedi.

FTS SQL, SQL yorumları çıkarıldıktan sonra 71d5ff6 baseline ile byte-equal. Yalnız açıklama artık belge UUID'sinin içerikten türemediğini ve yeniden yükleme sırasında sıra garantisi bulunmadığını doğru söylüyor.

- `c1_holdout_runner.py` SHA `6befccf42c42e26cbf47d8cc0a8339fe30389e5820033cf823f0d8a42b478f58`; baseline kaynakları yine aynı kesin 71d5ff6 commit'inden, candidate güncel gerçek service. Geçmiş aday hash'i bu runner'a sabitlenmemiş; her yeni çıktıda güncel kaynak hash'i yakalanıyor ve koşu sonunda tekrar doğrulanıyor.
- `c1_e5_holdout_runner.py` SHA `82b91a0bf3693ad68811172ff794d8c80fd7b18c873e19bf243fc36cd83dd903`; aynı kaynak bağını ve model cache tam içerik hashlerinin önce/sonra eşitliğini koruyor.
- Eski çapraz trace runner'ları ilk başarısız kaynak manifestlerine sabitlenmiş durumda. Yeni aday için bunları yeniden kullanmak yerine normal gerçek HybridRetriever iki kol runner'ları kullanılmalı; eski kanıtları değiştirmek gerekmiyor.
- `scripts/probe_retrieval_runtime.py` güncel kaynak ve gerçek dense/FTS SQL hashlerini kaydediyor. Yeni çıktı adındaki v3, son kaynak tekrarının sürümüdür; değiştirilmemiş aracın iç `version=dou018-runtime-prepared-v2` değeri normaldir. Aracı sırf etiket için değiştirmek gerekmiyor.

Çevrimdışı çıktılar `c1-holdout-final-source-offline-01/manifest.json`, `c1-e5-final-source-offline-01/manifest.json`, `retrieval-runtime-v3-source-offline-20260908.json`. Üçü de aynı yeni FTS hash'ini yakaladı. Runtime namespace ve kaynak plan raporu hash'i v2 ile aynı. V2'den kalan dense/probe açıklama değişiklikleri önceki yorum-köprü kanıtıyla açıklanmalı; FTS bu tekrarın tek yeni davranış farkı.

## Kökün sırayla çalıştıracağı komutlar

Çalışma dizini `/Users/muratates/code/dou-synapse-018-codex-production-line`. DSN'ler parola basılmadan mevcut güvenli yöntemle süreç ortamına verilmeli. Her çıktı yeni adla oluşturulur; var olan kanıt üzerine yazılmaz. Ortamda yasak libpq yönlendirmeleri bulunmamalı.

1. Runtime: `RETRIEVAL_PROBE_APP_DSN`, mevcut `127.0.0.1:55448/dou018_retrieval_runtime1` klonunda `dou_app` rolüne bağlanmalı. Orijinal 20k ölçüm DB'si kullanılmaz veya değiştirilmez. Önceki klon lineage aynı kalır; probe salt okunurdur. Komutu modül olarak çalıştırmak import yolunu açık tutar. Dosya olarak çıplak çağrı bir denemede `scripts` import hatası verdi; herhangi bir DB işlemine veya çıktı rezervasyonuna ulaşmadı.

```sh
ENVIRONMENT=local DEV_AUTH_ENABLED=true PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=.:apps/api apps/api/.venv/bin/python -m scripts.probe_retrieval_runtime \
  --execute --repeats 7 \
  --source-report /private/tmp/dou018-evidence/retrieval-plan-local-20260908b.json \
  --output /private/tmp/dou018-evidence/retrieval-runtime-local-v3-20260908.json
```

2. Hashing: `EVAL_APP_DSN` ve `EVAL_WORKER_DSN`, sırasıyla `dou_app`/`dou_worker` rolleriyle aynı `127.0.0.1:55448/dou018_eval_c1holdout01` mevcut DB'sini göstermeli. Korpus yeniden kurulmaz. Önceki koşudaki 0.1 eşik ortamda açıkça korunur; bu ham retrieval kolu eşik guard'ını çalıştırmaz.

```sh
EVIDENCE_THRESHOLD=0.1 PYTHONDONTWRITEBYTECODE=1 \
apps/api/.venv/bin/python /private/tmp/dou018-evidence/c1_holdout_runner.py \
  --execute \
  --corpus /private/tmp/dou018-evidence/c1-holdout-corpus-01.json \
  --output-dir /private/tmp/dou018-evidence/c1-holdout-final-measured-01
```

3. E5: `EVAL_APP_DSN`/`EVAL_WORKER_DSN`, aynı roller ve port ile `dou018_eval_c1e501` mevcut DB'sine yönlendirilmeli. Önceki 0.81 eşik korunur. Çalıştırıcı üç offline flag'i, mevcut E5 cache yolunu ve localhost:9 HTTP proxy'sini kendisi ayarlar; gerçek FastEmbed/E5 model kimliği, altı cache dosyası ve önce/sonra korpus hashleri sınanır. LLM yoktur.

```sh
EVIDENCE_THRESHOLD=0.81 PYTHONDONTWRITEBYTECODE=1 \
apps/api/.venv/bin/python /private/tmp/dou018-evidence/c1_e5_holdout_runner.py \
  --execute \
  --corpus /private/tmp/dou018-evidence/c1-e5-corpus-01.json \
  --output-dir /private/tmp/dou018-evidence/c1-e5-final-measured-01
```

## Sonuç denetimi

Her yeni manifestin aday FTS/dense/service/config hash'leri bu raporla eşleşmeli. Eski ve yeni korpus, sorgu sırası, kaynak/gold/harness hash'leri karşılaştırılmalı. Çıktı `complete` olmalı; iki holdout kolunda127 çağrı/105 puanlanan soru, sıfır hata/yeniden deneme, aynı rol/korpus ve değişmeyen önce/sonra state bulunmalı. Hashing gerçek model kalitesi olarak sunulmaz. E5 ≥0.80 ve baseline Recall@5/MRR azalmama koşulları ayrıca hesaplanır. İlk başarısız adayların hashing ve E5 sonuçları korunur.

Runtime ölçümünde dense prepared counter'ları, aynı fiziksel bağlantı, GUC geri yüklemesi, FTS'nin çağıran moduyla çalışması ve erişim/metadata negatifleri yeniden doğrulanmalı. Runtime v1/v2/v3 karşılaştırmaları dense SQL mikrobenchmark süreleriyle karıştırılmamalı. Tam API sonuç sayısı bir kaldırılan FTS reingest iddiası nedeniyle bir azalabilir; dense reingest ve iki yolun kapsam/RLS testleri korunmuştur.

Kaynaklar ve DB ağır çalışmaları kökte koordine edilir. Bu rapor yeni DB kurulumu, model indirme, eski kanıt değişimi veya canlı ortam işlemine gerekçe oluşturmaz.
