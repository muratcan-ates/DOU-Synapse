# C1 hashing holdout: iki gerçek retrieval kaynağı

Çalıştırıcı: `/private/tmp/dou018-evidence/c1_holdout_runner.py`. Depo veya evaluation kaynaklarına yazmaz. Varsayılanı DB'siz adaptör planıdır; yalnız `--execute` ile mevcut korpusa salt okunur bağlanır. 161 holdout kaydından mevcut harness'ın seçtiği 127 soru sorulur; Recall@5/MRR 105 kaynaklı soru üzerinde hesaplanır. Kapsam dışı 22 soru bu kalite metriklerine girmez. LLM çağrısı yoktur.

## Korpusu root kurar

Mevcut `evaluation/build_corpus.py` gerçek upload doğrulaması, worker, parser, chunker ve embedding yolunu kullanır. Üç DSN aynı host/port/DB olmalı; uygulama `dou_app`, worker `dou_worker`, kurulum ayrı yönetici rolü olmalı. Paylaşılan rol parolalarını değiştirmez.

Mevcut kurucunun sınırı bu yeni wrapper'dan daha geniştir: veritabanı `dou` ile başlar, eval/inject/acceptance içerir; port yoksa 5432 kabul edilir. `--recreate` doğrulanmış hedefi silebilir; `--skip-setup` mevcut hedefe ingestion yapar. Bu deneyde ikisini de kullanmayın. Önce katalogdan hedefin bulunmadığını doğrulayın; yeni isim, açık 127.0.0.1:55448 ve önceden hazırlanmış roller kullanın. Kurucunun varsayılan storage dizini repo altındadır; aşağıdaki açık tmp yolu gerekir. `--out` üzerine yazabilir: yeni, bulunmayan çıktı seçin.

psql alt süreci PG yönlendirme ortamını temizler; kurucunun API/worker bağlantıları için de PGSERVICE, PGSERVICEFILE, PGHOSTADDR, PGOPTIONS ve PGSYSCONFDIR ayarlı olmamalı. Parolalar güvenli ortam değişkenlerinde kalmalı; komut argümanına veya kanıt metnine eklenmemeli.

Repo kökünden, örnek benzersiz hedef `dou018_eval_c1holdout01` için `EVAL_ADMIN_DSN`, `EVAL_APP_DSN`, `EVAL_WORKER_DSN` güvenli ortamda aynı hedefe ayarlandıktan sonra:

```sh
ENVIRONMENT=local DEV_AUTH_ENABLED=true EMBEDDING_PROVIDER=hashing LLM_FAKE_PROVIDER=true \
  GROQ_API_KEY= GEMINI_API_KEY= OPENAI_API_KEY= PYTHONDONTWRITEBYTECODE=1 \
  apps/api/.venv/bin/python evaluation/build_corpus.py \
  --database dou018_eval_c1holdout01 \
  --pg-bin /opt/homebrew/opt/postgresql@16/bin \
  --storage-root /private/tmp/dou018-evidence/c1-holdout-storage-01 \
  --out /private/tmp/dou018-evidence/c1-holdout-corpus-01.json
```

Kurucunun hashing uyarısı korunmalı. Anlamsal kalite raporu uyarısını aşmak için provider/runtime bayrağı değiştirilmez; bu deney açıkça mekanik regresyon diye sınıflandırılır.

## İki kolu çalıştırma

```sh
PYTHONDONTWRITEBYTECODE=1 apps/api/.venv/bin/python \
  /private/tmp/dou018-evidence/c1_holdout_runner.py \
  --execute \
  --corpus /private/tmp/dou018-evidence/c1-holdout-corpus-01.json \
  --output-dir /private/tmp/dou018-evidence/c1-holdout-measured-01
```

Wrapper EVAL_APP_DSN ve EVAL_WORKER_DSN ister; yalnız 127.0.0.1:55448/dou018_eval_* hedeflerini kabul eder. Yeni çıktı dizini oluşturur; mevcut dizini ve önceki kanıtı kullanmaz. İki kolun sonuç/progress dizinleri ayrıdır. Kaynak dosyaları, korpus hashleri, gerçek hashing kimliği, öğrenci RLS ve DB salt-okunurluğu denetlenir. Başarısızlık manifestte safe error_type/phase olarak kalır. Ham evaluate sonuçları ve eşleştirilmiş karşılaştırma ayrı korunur.

Baseline `71d5ff640f0d48a08f3967b000485a15035f10c7` dense/fts/service dosyaları git show ile aynen alınır, ayrı modüllerde çalıştırılır. Baseline service'in iki import'u yalnız bu ayrı modülde eski dense/fts işlevlerine bağlanır. Aday normal service'dir. Mevcut backends resolver ve evaluate harness değiştirilmeden, süreç içi giriş listesi seçilerek kullanılır. Ortak config, DB, embedding, fusion, scope ve contracts günceldir ve iki kolda aynıdır: bu üç retrieval kaynağının karşılaştırmasıdır, eski uygulamanın bütünü değildir.

Ham harness git_sha alanı güncel checkout'u tanımlar; baseline retrieval algoritmasının kimliği companion manifestteki baseline SHA ve kaynak hashleridir. Kirli aday da çalışma ağacı kaynak hashleriyle temsil edilir. Manifestin numeric_delta alanı yalnız Recall@5/MRR farkını, mechanical_nonregression alanı bu iki sayının azalıp azalmadığını gösterir. Performans, üretim SLO'su, E5/LLM anlamsal kalite veya öğretmen kabulü iddiası çıkarılmaz. Harness'ın otomatik hesapladığı eşik taraması bu deneyde ayar seçmek için kullanılmaz.

DB'siz kontrol kanıtı: `c1-holdout-adapter-offline-final/manifest.json` ve `c1-holdout-adapter-unit.log` (4 test; yanlış host/port/rol/DB, ortam yönlendirmesi, gerçek eski modül bağlama ve normal aday işlevlerinin değişmemesi). Bu hazırlık sırasında hiçbir DB kurma/sorgulama işlemi veya ağır test çalıştırılmadı.
