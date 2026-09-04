# evaluation/ — ölçüm altyapısı

Bu klasör kaynak getirme, kapsam reddi, kaynak gösterimi ve öğretim davranışını
ayrı ayrı ölçer. Çalıştırılmayan deney için sonuç yazılmaz. Sahte sağlayıcı ve
hashing embedding ile yapılan denemeler yalnız kontrol akışını sınar; gerçek
model kalitesi veya ders kabulü anlamına gelmez.

## Dosya haritası

| Dosya | İş |
|---|---|
| `gold_set/calibration.json` | Eşik ayarı için 40 soru; holdout sonucu yerine raporlanmaz |
| `gold_set/holdout.json` | Ayrı tutulan 161 soruluk değerlendirme seti |
| `gold_set/SCHEMA.md` | Kayıt biçimi ve `expected_sources` kuralları |
| `goldset.py`, `verify_gold_set.py` | Yapı, ayrıklık ve gerçek kaynak denetimi |
| `build_corpus.py` | Üç bağlantıyı doğrular; korpusu gerçek yükleme/worker hattından kurar |
| `backends.py`, `runtime_client.py` | Retrieval ve bütçeli HTTP bağlantıları |
| `provenance.py` | Sunucu, istek ve yanıt kanıtını doğrular |
| `metrics.py`, `evaluate.py` | Metrikler ve değerlendirme koşucusu |
| `faithfulness/pull_sample.py`, `faithfulness/score_labels.py` | Örnekleme, bağımsız insan etiketleri ve uyum hesabı |
| `injection/run_injection.py` | Ayrı zehirli korpusta injection/Sokratik kontroller |
| `acceptance/` | Kaynak özetleri ve öğretmen kabul taslağı |
| `calibration.md`, `results/` | Tarihli kararlar ve koşular; bugünkü adayın kanıtı sayılmaz |

Testler `apps/api/tests/test_eval_metrics.py`, `test_eval_readiness.py` ve
`test_faithfulness_scoring.py` içindedir. Aşağıdaki kullanım güncel akıştır;
tarihli raporların komutları ve sonuçları kendi tarihsel bağlamında korunur.

## İzole korpus ve retrieval

Komutlar `apps/api` dizininden çalıştırılır. Önce güvenli yerel ortamınızda
`EVAL_ADMIN_DSN`, `EVAL_APP_DSN` ve `EVAL_WORKER_DSN` tanımlayın. Parolaları
sohbete, rapora veya depoya yazmayın.

Üç bağlantının **aynı açık host, port ve veritabanına** gitmesi gerekir.
`localhost`, `127.0.0.1` ve `::1` birbirinin yerine kabul edilmez. Örnek hedef
`localhost:55440/dou_synapse_eval` olabilir; kendi izole kümenizin gerçek portunu
kullanın. Uygulama `dou_app`, işçi `dou_worker` ve yönetici ayrı bir sahip rolü
kullanır. Uygulama/işçi LOGIN rolleri önceden hazırlanmış olmalıdır. Kurucu
paylaşılan rol parolalarını değiştirmez ve başka geliştirme veritabanına yazmaz.
Veritabanı adı `dou` ile başlamalı ve `eval`, `inject` veya `acceptance` içermelidir.

```sh
cd apps/api

# Yapı ve ayrıklık denetimi; veritabanı veya sağlayıcı çağrısı yok.
uv run python ../../evaluation/verify_gold_set.py

# Önceden tanımlanan üç EVAL_*_DSN kullanılır. İlk kurulumda veritabanı yeni olmalı.
EMBEDDING_PROVIDER=fastembed uv run python ../../evaluation/build_corpus.py \
  --database dou_synapse_eval --out /tmp/dou-corpus.json

# Aynı uygulama/işçi bağlantıları ve embedding ayarıyla kaynakları doğrula.
DATABASE_URL="$EVAL_APP_DSN" WORKER_DATABASE_URL="$EVAL_WORKER_DSN" \
  EMBEDDING_PROVIDER=fastembed uv run python ../../evaluation/verify_gold_set.py \
  --corpus /tmp/dou-corpus.json

# Önce planı gör; retrieval dry-run korpus görünürlüğünü DB'de de denetler.
DATABASE_URL="$EVAL_APP_DSN" WORKER_DATABASE_URL="$EVAL_WORKER_DSN" \
  EMBEDDING_PROVIDER=fastembed uv run python ../../evaluation/evaluate.py \
  --set calibration --layer retrieval --mode hybrid \
  --corpus /tmp/dou-corpus.json --dry-run

# Kalibrasyon: LLM çağrısı yapmaz.
DATABASE_URL="$EVAL_APP_DSN" WORKER_DATABASE_URL="$EVAL_WORKER_DSN" \
  EMBEDDING_PROVIDER=fastembed uv run python ../../evaluation/evaluate.py \
  --set calibration --layer retrieval --mode hybrid \
  --corpus /tmp/dou-corpus.json --results-dir /tmp/dou-retrieval-calibration
```

İstenirse üç DSN `--admin-dsn`, `--app-dsn`, `--worker-dsn` ile de verilebilir;
ortam değişkenleri bağlantı parolalarını komut argümanlarına taşımamayı sağlar.
`--recreate` yalnız doğrulanmış izole hedefi silip yeniden kurmak istendiğinde
eklenir. Hazır, migration uygulanmış hedef için `--skip-setup` kullanılır.

Yeni korpus özeti parola taşımaz: `database_identity`, yüklenen kaynakların
SHA256 özetleri, eğitmen/öğrenci kimlikleri ve işlenen belge bilgilerini içerir.
Retrieval koşusu bu kimliği `DATABASE_URL` veya açık `--database-url` ile
karşılaştırır. Başka veritabanı/host/portta ölçüm başlatılmaz. Öğrenci davranışı
koşuları yeni korpusun `student_id` kimliğini kullanır; eski korpusta yalnız
eğitmen bulunması öğrenci kabulünü kanıtlamaz.

## Gerçek sunucuyla uçtan uca ölçüm

[Sağlayıcı hazırlığı](../docs/provider-readiness.md) yönergesindeki ayrı eval
anahtarı ve hedefleri önce yapılandırın. `EVAL_LLM_API_KEY` tek başına yeterli
değildir: izole sunucuda `EVAL_RUNTIME_ENABLED=true`, açık `EVAL_LLM_PROVIDER`,
uyumlu model hedefleri, `LLM_FAKE_PROVIDER=false` ve LLM anahtarından farklı
`EVAL_RUNTIME_SECRET` gerekir. Anahtarları komut satırına yazmayın. Yerel örnek
kimlikleriyle koşarken yalnız bu yerel sunucuda `DEV_AUTH_ENABLED=true` gerekir.

Sunucu ve harness aynı temiz, commit edilmiş adaydan ve aynı korpustan çalışır.
Sunucuyu yalnız loopback'e bağlayın; aşağıdaki komut güvenli ortam ayarlarının
önceden yüklenmiş olduğunu varsayar:

```sh
DATABASE_URL="$EVAL_APP_DSN" WORKER_DATABASE_URL="$EVAL_WORKER_DSN" \
  EMBEDDING_PROVIDER=fastembed uv run uvicorn app.main:app \
  --host 127.0.0.1 --port 8015
```

Ayrı terminalde harness için `EVAL_RUNTIME_SECRET` tanımlı olmalıdır. Harness bu
ayrı sırrı yalnız açık loopback adresine gönderir; ortam proxy'lerini ve HTTP
yönlendirmelerini kullanmaz. Sunucu kaydı ve yanıt makbuzu; tam SHA, temiz çalışma
ağacı, runtime/koşu/yapılandırma, gerçek transport hedefi, istek ve yanıt özetlerini
bağlar. İstek özeti soru, ders, mod, oturum ve öğrenci denemesini kapsar.

```sh
# Kısa kalibrasyon planı: sağlayıcı/API çağrısı yok.
EMBEDDING_PROVIDER=fastembed uv run python ../../evaluation/evaluate.py \
  --set calibration --layer e2e --corpus /tmp/dou-corpus.json \
  --api-url http://127.0.0.1:8015 --limit 3 --require-real --dry-run

# Kalibrasyon ayarı dondurulduktan sonra holdout; invocation başına 30 HTTP isteği.
EMBEDDING_PROVIDER=fastembed uv run python ../../evaluation/evaluate.py \
  --set holdout --layer e2e --corpus /tmp/dou-corpus.json \
  --api-url http://127.0.0.1:8015 --require-real --max-requests 30 \
  --results-dir /tmp/dou-e2e-holdout

# Aynı sunucuda 25 kaynak doğruluğu örneği ve iki boş insan etiket formu.
uv run python ../../evaluation/faithfulness/pull_sample.py \
  --corpus /tmp/dou-corpus.json --api-url http://127.0.0.1:8015 \
  --require-real --max-requests 30 --output-dir /tmp/dou-faithfulness-01
```

Eşik gerçekten kalibrasyonla belirlendiyse `evaluate.py` komutuna
`--threshold-calibrated` eklenir; bu bayrak tek başına eşik doğruluğu kanıtı değildir.
`--llm-note` yalnız açıklamadır. `FAKE_PROVIDER=false` yazmak veya anahtarın varlığı
**gerçek kalite kanıtı üretmez**. `provider`, `cache`, `no_provider`, `fake` ve
`unknown` sonuçları ayrı değerlendirilir. Önbellek ve sağlayıcı çağrılmadan verilen
ret, yeni bir gerçek model cevabının kalite örneği sayılmaz. `--require-real`
sunucu/yanıt doğrulanamadığında kabulü durdurur; normal doğrulama hatalarının
HTTP kontrol sonuçları ayrıca kaydedilebilir.

## Bütçe, devam ve insan kabulü

- `--max-requests` bir çalıştırmadaki HTTP POST bütçesidir. Sunucunun model içi
  denemeleri ayrı `calls` kayıtlarıdır; bu bayrak provider çağrısı veya para
  bütçesi diye yorumlanmaz. `429`, `5xx` veya erişim sorunu koşuyu durdurur.
- `evaluate.py` tamamlanmış maddeleri sonuç dizinindeki `.progress/` altında
  saklar. Aynı komut ve aynı sunucu örneğiyle devam edilir. Doğrulanmış gövde ile
  gold kaydından türetilen skorlar yeniden hesaplanır.
- Faithfulness ve injection için aynı `--output-dir` kesilmiş koşuyu sürdürür.
  Tamamlanmış örneklem/etiket dosyalarının üzerine yazılmaz. Sunucu yeniden
  başladıysa ya da kod, ayar, korpus veya soru seçimi değiştiyse yeni sonuç dizini
  ve yeni koşu gerekir. Hatasız tamamlanmış cevaplar yeniden istenmez; yanıtı
  kaydedilemeden kesilen bir istek sonraki çalıştırmada tekrar sorulabilir.
- İki kişi ayrı etiket dosyalarını birbirini görmeden doldurur. Mevcut
  `faithfulness/score_labels.py`, gerçek yanıt kanıtını ve yinelenmeyen istekleri,
  20–30 tamamlanmış cevabı, etiket tamlığını ve bağımsız kişi adlarını denetler.
  [Kabul paketi](acceptance/README.md) puanlama komutunu ve öğretmen kontrol
  listesini açıklar. Gerçek grading runner bu dilimde çalıştırılmadı; beş
  değerlendirme biçiminin taslağı insan onayı bekler.

Zehirli belge testleri temiz korpusa eklenmez. Ayrı `dou_synapse_inject` hedefi
üç DSN ile hazırlanır; kurucuya `--extra-material ../../evaluation/injection/material`
verilir. API o ayrı korpusa bağlandıktan sonra:

```sh
uv run python ../../evaluation/injection/run_injection.py \
  --corpus /tmp/dou-injection-corpus.json --api-url http://127.0.0.1:8015 \
  --require-real --max-requests 40 --output-dir /tmp/dou-injection-01
```

## Yeniden çağrı yapmadan analiz

```sh
uv run python ../../evaluation/evaluate.py \
  --sweep-from /tmp/dou-retrieval-calibration/KOSU.json \
  --sweep-min 0.78 --sweep-max 0.83 --sweep-step 0.005

uv run python ../../evaluation/evaluate.py \
  --compare /tmp/REFERANS.json /tmp/ADAY.json
```

Kalibrasyon ve holdout karıştırılmaz; model/eşik denemeleri holdout üzerinde
ayarlanmaz. Gold set'e geçici chunk UUID'leri yazılmaz; kalıcı kaynak kimliği
dosya ve sayfa/slayt ya da metin çapasıdır. Embedding sağlayıcısı/modeli/sürümü
belge ve sorgu tarafında uyuşmalıdır; hashing veya açık runtime uyuşmazlığı
kalite raporuna giremez.

Otomatik injection ve Sokratik denetimler yalnız açık ihlal kalıplarını işaretler.
İşaret çıkmaması çözüm sızmadığını, kaynağın iddiayı desteklediğini veya rubriğin
adil uygulandığını kanıtlamaz. Makbuz güvenilen yerel sunucunun gözlemidir;
uzaktan kriptografik doğrulama veya tek başına öğretmen kabulü değildir. Gerçek
model yanıtları ve bağımsız insan incelemesi tamamlanmadan kalite onayı yazılmaz.
