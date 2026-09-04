# Sağlayıcı hazırlığı ve değerlendirme kanıtı

Bu kontrol yapılandırmayı ve açıkça istendiğinde hesap erişimini sınar. Kaynak doğruluğu, Sokratik davranış veya puanlama kalitesini ölçmez. Gerçek kalite kabulü; sunucuya bağlı cevap kayıtları, sürümlü ders/goldset ve bağımsız insan etiketleri gerektirir. Şu an gerçek hesap erişimi doğrulanmış değildir.

## Hedefler ve rota sınırları

Tek varsayılan kaynak `app/core/provider_config.py` içindedir; Settings ve `.env.example` aynı hedefleri kullanır:

| Sıra | LiteLLM hedefi | Gerekli anahtar |
|---|---|---|
| Birincil | `groq/openai/gpt-oss-120b` | `GROQ_API_KEY` |
| Yedek | `groq/qwen/qwen3.6-27b` | `GROQ_API_KEY` |

4 Eylül 2026'da kontrol edilen [Groq değişiklik kaydı](https://console.groq.com/docs/deprecations), `llama-3.3-70b-versatile` modelinin 16 Ağustos'ta ücretsiz/geliştirici katmanlarından kaldırıldığını; kurumsal erişimin farklı olduğunu bildiriyor. Yukarıdaki alternatiflerin resmî sayfaları mevcut: [GPT OSS 120B](https://console.groq.com/docs/model/openai/gpt-oss-120b), [Qwen3.6 27B](https://console.groq.com/docs/model/qwen/qwen3.6-27b). Qwen sayfasında Preview etiketi vardır; yayımlanan model adı hesap erişimi, kararlılık veya eğitim kalitesi onayı değildir.

İki varsayılan aynı Groq hesabına gider; ortak kota, erişim veya sağlayıcı arızasına karşı bağımsız yedek sağlamaz. Genel LiteLLM istemcisi yapılandırılmış hedefler arasında sınırlı tekrar/failover yapar. Kota korumalı ders sohbeti ise **toplam tek sağlayıcı denemesi** yapar; yedek modele otomatik geçtiği varsayılmamalıdır. Farklı sağlayıcı hedefi, o sağlayıcının anahtarını gerektirir. Gemini uygulama rotası desteklenir; değerlendirme ön kontrolü yalnız açık Groq/Gemini hedeflerini kabul eder. Embedding sağlayıcısı çalışma anı yedeği değildir; değişmesi korpusun yeniden işlenmesini gerektirir.

Yeni varsayılan modeller için daraltılmış token ön rezervasyonu henüz ölçülmüş değildir. Kota koruması bu modellerde bütün isteğin muhafazakâr UTF-8 byte üst sınırını kullanır; yalnız daha önce incelenmiş model/prompt eşleşmelerinde ölçülmüş daha dar sınır uygulanır. Bu değişiklik yeni model için token kalibrasyonu iddiası taşımaz.

## Ağsız ön kontrol

Depo kökünden, uygulamanın gerçek çalışma ayarlarıyla:

```sh
apps/api/.venv/bin/python scripts/provider_preflight.py --offline
```

Varsayılan da `--offline` davranışıdır. Komut sağlayıcıya veya modele bağlanmaz, LiteLLM yüklemez. Rapor yalnız güvenli ayar alanlarını, anahtar **varlığını**, tam Git SHA/dirty durumunu ve yapılandırma özetini taşır. Anahtarlar, bağlantı parolaları, istemler ve cevaplar yoktur. Yerel testte kimlik doğrulama için `DEV_AUTH_ENABLED=true` gerekir; gerçek sunucunun kimlik ayarlarını kullanıyorsanız bu ek ayara gerek yoktur. Eksik/geçersiz Settings girdileri değerleri yazdırılmadan `invalid_configuration` olarak raporlanır.

`configuration_ready` yalnız yapılandırmanın bir denemeye uygun olduğunu belirtir. `LLM_FAKE_PROVIDER=false` olsa bile yerel ortamda her iki uygulama anahtarı da yoksa eski uyumluluk davranışı sahte sağlayıcıya düşer; ön kontrol bunu `effective_fake_provider` engeli olarak gösterir. Yerel fake/hash testleri korunur, gerçek değerlendirme olarak geçmez.

## Açık, sınırlı erişim denemesi

```sh
apps/api/.venv/bin/python scripts/provider_preflight.py --probe --timeout-seconds 10 --max-tokens 256 --output /tmp/dou-provider-preflight.json
```

Bu komut kota tüketebilir: birbirinden farklı her hedef için en fazla **bir** küçük JSON çağrısı, otomatik tekrar olmadan yapılır. Varsayılan iki hedefle en fazla iki çağrı vardır. Deneme zaman aşımı 30 saniyeyi, çıktı sınırı 512 tokenı geçemez. Gerçek modele giden kimlik bilgisi mevcut runtime ayarından çözülür. Yanıt gövdesi veya sağlayıcı hata metni rapora yazılmaz; yalnız durum ve gecikme kaydedilir. Geçerli JSON dönmeyen hedef de başarısız sayılır. Çıkış kodu engelde `2`, geçerli yapılandırma/erişimde `0` olur. `accessible` erişim sonucudur; her raporda `quality_status=not_evaluated` kalır.

## Ayrı değerlendirme anahtarının gerçekten kullanılması

Yalnız izole yerel değerlendirme sunucusunda aşağıdaki ayarları güvenli yerel ortam dosyasına yerleştirin. Anahtarları komut satırına, sohbete veya depoya yazmayın.

- `EVAL_RUNTIME_ENABLED=true`
- `EVAL_LLM_PROVIDER=groq` veya `gemini`
- `EVAL_LLM_API_KEY`: ayrı değerlendirme hesabının anahtarı
- `EVAL_RUNTIME_SECRET`: LLM anahtarından **farklı**, uzun rastgele erişim sırrı
- `LLM_PRIMARY_MODEL` ve varsa `LLM_FALLBACK_MODEL`: yalnız seçilen değerlendirme sağlayıcısına ait hedefler
- `LLM_FAKE_PROVIDER=false`; sürümlü gerçek kalite korpusu için doğru embedding alanı

Settings etkinleştirilirken ilgili uygulama anahtarı `EVAL_LLM_API_KEY` ile değiştirilir, diğer sağlayıcının anahtarı temizlenir. Bilinen uygulama anahtarıyla aynı değer reddedilir; farklı iki anahtarın gerçekten ayrı hesap/kota taşıdığı dışarıdan doğrulanmalıdır. Böylece fallback uygulama kotasına kaçamaz. Yalnız `EVAL_LLM_API_KEY` yazmak bu davranışı açmaz. Eksik sağlayıcı/anahtar, farklı sağlayıcı hedefi, sahte mod veya üretim ortamı uygulamanın başlamasını reddeder. Erişim sırrı boşsa dahili uç kapalıdır. API anahtarını tarayıcıya göndermez; anahtar yalnız seçilen sağlayıcının çağrısında kullanılır.

Sunucuyu yalnız loopback'e bağlayın; değerlendirme modu bir paylaşılan demo veya üretim sunucusuna açılmaz:

```sh
cd apps/api
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8015
```

Bu komutları yalnız aynı **izole değerlendirme veri tabanına** giden uygulama/işçi/yönetici bağlantılarıyla çalıştırın. Veri kurma ve kalite koşuları için mevcut [değerlendirme yönergelerini](../evaluation/README.md) izleyin. Korpus veya uygulama/model ayarı değişirse yeni koşu oluşturun.

## Runtime ve cevap sözleşmesi

Mevcut, OpenAPI dışında tutulan `GET /internal/evaluation/runtime?run_id=<UUID>` ucu yalnız etkin mod, loopback istemcisi ve `X-Eval-Runtime-Secret` ile açılır. Kapalı/sırsız uç `404`, yanlış sır veya uzak istemci `403` döndürür. Endpoint sağlayıcı çağrısı yapmaz.

Runtime kaydı `schema_version=1`, `kind=evaluation_runtime`, `run_id`, `runtime_id`, tam `candidate_sha`, `candidate_dirty`, `config_digest`, sabit `recorded_at`, `configured_fake`, `effective_fake`, `targets`, `credential_scope` ve güvenli `configuration` taşır. Kimlik ve ayarlar uygulama başlarken dondurulur. Aynı uygulama örneğinin kaydı tekrar alındığında zaman damgası değişmez. Kod/ayar değişikliğinden sonra sunucu yeniden başlatılmalıdır. Dirty veya kimliği bilinmeyen aday gerçek kalite kabulünden geçmez.

Sohbet çağrısı aynı sır ve `X-Eval-Run-Id` ile yapılınca cevapta base64url JSON `X-Eval-Receipt` bulunur. Bu başlık öğrenci JSON şemasını değiştirmez; sır gönderilmemiş normal cevaplarda bulunmaz. Makbuz aynı runtime/koşu/yapılandırma kimliğine ek olarak istek kimliği, cevap zamanı, `outcome`, `provider`, `model`, `calls`, `body_digest` ve `request_digest` taşır. Her transport denemesi yalnız `{provider, model, status: completed|failed}` kaydeder. Cevabın metnindeki sağlayıcı iddiası bu kaydı üretemez.

- `provider`: o istekte tamamlanmış gerçek transport çağrısı gözlendi.
- `cache`: cevap önbellekten geldi; yeni model kalitesi örneği değildir.
- `no_provider`: sağlayıcı çağrılmadan ret/şablon/başka deterministik yol işlendi veya tamamlanmış transport yoktur.
- `fake`: gözlenen yol sahte sağlayıcıdır; gerçek kalite kanıtı değildir.

`body_digest`, UTF-8 `json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))` SHA256 değeridir. `request_digest` aynı algoritmayla `{course_id, question, mode, session_id, student_attempt}` alanlarını bağlar; boş iki opsiyonel alan `null` olarak dahildir. Soru ve öğrenci denemesi doğrulanmış istek değeridir; UUID alanları kanonik metin biçimindedir. Aynı cevap farklı soruya taşınamaz ve yinelenen request_id kabul edilmez. İstem/cevap metni ve kişisel kimlikler makbuza kopyalanmaz. Harness sırrı yalnız açık localhost/127.0.0.1/::1 adresine, yönlendirmeleri kapatarak gönderir. SHA/dirty/runtime/run/config/cevap özeti uyuşmazlığı, eksik kanıt veya serbest `--llm-note` gerçek kabulü geçiremez. `recorded_at` ve `request_id` de doğrulanır.

Makbuz güvenilen yerel uygulama örneğinin gözlemidir; uzaktan kriptografik kod doğrulaması veya tek başına kalite onayı değildir. Enjeksiyonlu transport testleri yalnız sözleşmeyi kanıtlar. Gerçek erişim, insan etiketleri ve ders kabulü ayrıca tamamlanmalıdır. Geri almak için `EVAL_RUNTIME_ENABLED=false` yapıp sırrı kaldırın ve sunucuyu yeniden başlatın.
