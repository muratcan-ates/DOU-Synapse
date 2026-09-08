# Dağıtım

DOU-Synapse'ın kurulumunun tek doğru anlatımı. Değerler burada YOKTUR — yalnız
değişken adları ve ne işe yaradıkları. Gerçek değerler sağlayıcıların gizli
değer kasalarında durur ve depoya asla girmez.

> **Durum, 8 Eylül 2026.** Bu belgedeki bulut adımları **KOŞULMADI**: gerçek
> Azure/Vercel/Supabase erişimi olmadan yazıldılar (T050 hâlâ açık). Yerelde
> ölçülmüş olanlar §6/§7 ve 018 doğrulama kaydında ayrı işaretli. D1/D2/D3 ve S8 yerel entegredir; son birleşik 1561 API testi geçti. Yeni tarayıcı/dossier/hosted kabulü bekler. Bir adımı ilk kez koşan
> kişi, buradaki anlatımla gerçek arasında fark görürse belgeyi düzeltsin —
> "belgede öyle yazıyordu" bir mazeret değil, bir kusur kaydıdır.

---

## 1. Topoloji

Üç parça, üç ayrı sağlayıcı:

| Parça | Nerede | Ne koşar |
|---|---|---|
| Web | Vercel | Next.js arayüzü |
| API | Azure Container Apps | `uvicorn app.main:app` |
| Worker | Azure Container Apps | `python -m app.worker` |
| Veritabanı + Storage | Supabase | Postgres 16 + pgvector, belge deposu |

**API ve worker AYNI imajdan koşar**, yalnız `command` farklıdır (tasks.md
T049 kararı). Sebebi: embedding modeli imajın içindedir ve iki ayrı imaj, iki
ayrı 2 GB'lık yapı ve iki ayrı sürüm sapması riski demektir.

Bağımsız `python -m app.worker` kuyruğu yoklar ve kota bakımını ayrı görevde çalıştırır. API, yükleme sonrası yapılandırılmış `WORKER_DRAIN_URL` varsa korumalı HTTP tetikleyiciyi, yoksa süreç içi tek drain turunu kullanır. Tek drain çağrısı sürekli bakım zamanlayıcısı değildir. Worker scale-to-zero seçilirse lease devralma ve kota temizliği için dış uyandırma gerekir; barındırma hedefi ve zamanlayıcı henüz doğrulanmadı.

## 2. Ortam değişkenleri

Tam liste `.env.example`'dadır. Dağıtımda önemli olanlar:

### API ve worker (ikisinde de aynı)

| Değişken | Ne işe yarar |
|---|---|
| `ENVIRONMENT` | `production` — bu değer `DEV_AUTH_ENABLED` ve `LLM_FAKE_PROVIDER`'ı kilitler |
| `DATABASE_URL` | API bağlantısı. **`dou_app` rolüyle**: sahip değildir, `BYPASSRLS` taşımaz, dolayısıyla RLS gerçekten uygulanır |
| `WORKER_DATABASE_URL` | Worker bağlantısı. `dou_worker` rolü RLS'i atlar; `chunks` tablosuna yalnız o yazabilir |
| `SUPABASE_JWT_SECRET` | Supabase JWT'lerini doğrular. Yoksa ve dev-auth da kapalıysa uygulama **başlamaz** |
| `SUPABASE_JWT_ISSUER` | Üretimde zorunlu beklenen `iss`: seçilmiş Supabase projesinin HTTPS `/auth/v1` adresi. Eksik/bozuk değer başlangıcı durdurur. Kullanıcı bilgisi, query, fragment veya joker hedef kabul edilmez; gerçek proje adresini sağlayıcı ayarıyla eşleştirin. Yerel/demo ortamında isteğe bağlıdır |
| `CORS_ORIGINS` | JSON dizisi. Üretimde yalnız gerçek Vercel alan adı |
| `GROQ_API_KEY`, `GEMINI_API_KEY` | Yapılandırılmış hedefin sağlayıcısına ait anahtar gerekir. Genel istemci sınırlı failover uygular; kota korumalı ders sohbeti tek deneme yapar. Varsayılan iki hedef de Groq kullanır ve aynı sağlayıcı/kota arızasını paylaşır. [Sağlayıcı ön kontrolü](provider-readiness.md) |
| `WORKER_DRAIN_SECRET` | `POST /internal/drain` ucunu korur. **Boşsa uç 404 döner** (fail-closed) |
| `EMBEDDING_PROVIDER` | Üretimde `fastembed`. **İngest zamanı ayarıdır** — değiştirmek tüm korpusun yeniden işlenmesini gerektirir |
| `EMBEDDING_CACHE_DIR` | İmajda `/opt/models`; Dockerfile ayarlar |

### Yalnız API

| Değişken | Ne işe yarar |
|---|---|
| `QUESTION_AUTHORING_ENABLED` | Varsayılan `false`. `true` eğitmen için sınıflandırılmış soru üretimi ve taslak düzenlemeyi açar; yerel örnek yapılandırma açık gelir. |
| `WORKER_DRAIN_URL` | Worker'ın drain ucunun tam adresi. **Tanımlıysa** tetik HTTP'ye döner; tanımsızsa süreç içinde `drain()` koşar |
| `CHAT_RATE_LIMIT_REQUESTS`, `CHAT_RATE_LIMIT_WINDOW_SECONDS` | Kullanıcı başına sohbet sınırı. Sayaç **süreç içidir**: birden fazla replikada sınır replika başına uygulanır |

> **Lidere:** `WORKER_DRAIN_URL` şu an `Settings` alanı DEĞİL, doğrudan ortamdan
> okunuyor (`app/api/internal.py`). Sebebi `core/config.py`'nin bu fazda şeritlere
> kapalı olmasıydı. Faz kapanınca `Settings.worker_drain_url` olarak taşınmalı ve
> `.env.example`'a eklenmeli.

### Web (Vercel)

`NEXT_PUBLIC_API_URL` gerçek API origin'ine, `NEXT_PUBLIC_SUPABASE_URL` seçilmiş kimlik projesine işaret eder. `NEXT_PUBLIC_SUPABASE_ANON_KEY` tarayıcıya açık istemci anahtarıdır; servis rolü veya JWT imza sırrı bu değişkenlere konmaz. CSP bu iki yapılandırılmış adresin yalnız doğrulanmış origin'lerini kullanır. Üretimde `NEXT_PUBLIC_DEV_AUTH` kapalı olmalıdır. Bu değerler Next derlemesine girer; değiştirilirse web yeniden derlenir.

## 3. Migration sırası

`supabase/migrations/` altındaki dosyalar **alfabetik sırayla** uygulanır ve
sıra anlamlıdır:

```bash
for f in supabase/migrations/*.sql; do
  psql -v ON_ERROR_STOP=1 -d "$DATABASE" -f "$f"
done
```

| No | İçerik |
|---|---|
| `0001` | Çekirdek şema, FTS altyapısı, RLS temeli |
| `0002` | Supabase Auth köprüsü (R1) |
| `0003` | Sohbet: `chat_sessions`, `chat_messages`, `answer_cache`, `request_logs` |
| `0004` | Ölçme ve analitik |
| `0005` | Ek politikalar |
| `0006` / `0007` | R4 / R3'e ayrıldı, gerekirse |

`0018_question_authoring.sql`, `0001`–`0015` üzerine uygulanır. `0016` ve `0017` numaraları paralel dallara ayrıldığı için bu dalda boşluk vardır; başka dalın migration dosyalarını yeniden numaralandırmayın. Bu değişiklik tablo eklemez, soru güncelleme yetkilerini daraltır ve onaylanmış/kullanılmış soru içeriklerini korur. Kullanılmamış taslağın öğrenme çıktısı silinirse çıktı ve zorluk birlikte temizlenir; incelenmiş veya kullanılmış sorunun çıktısını silmek reddedilir.

Geri alma: `QUESTION_AUTHORING_ENABLED=false` verip API'yi yeniden başlatın. Yeni düzenleme ve sınıflandırılmış üretim kapanır; eski sınıflandırmasız üretim devam eder. Gerekirse önceki uygulama sürümünü geri yükleyin, `0018` korumalarını ve kaydedilmiş soruları yerinde tutun. Taslak düzenlemeyi yeniden açmadan önce API, SQL ve tarayıcı kanıtlarını aynı sürümde doğrulayın. Bu dalın yerel testleri canlı ortam onayı değildir.

**`main`'e girmiş bir migration yerinde değiştirilmez.** Yeni numara açılır.
Bir dağıtımda migration'ları uygulamadan önce §6'daki yedeği alın.

`supabase/local_dev_setup.sql` ve `supabase/seed_demo.sql` **üretimde
koşturulmaz**: birincisi yerel roller kurar, ikincisi sahte kullanıcı yaratır.

Kurulumdan sonra şemayı doğrulayın:

```bash
psql -d "$DATABASE" -c "\dt public.*" -c "\dt app.*"
```

Güncel migration setiyle iki uygulama şemasında toplam **30 tablo** bulunur: 28 public ve 2 app. <!-- docs-check: tables.count = 30 -->

Tarihsel not: 9 Ağustos'ta hem paylaşılan geliştirme veritabanında hem sıfırdan
kurulan veritabanında **15 tablo** ölçülmüştü. <!-- docs-check: tarihsel 15 · 2026-08-09 -->
Faz 2 brifingindeki daha yüksek tablo tahmini o gün için de yanlıştı.

### 0025/0026 birlikte geçiş sınırı

[Ortak kota](operations/shared-request-quota.md) ve [iş sahipliği](operations/ingestion-recovery.md) protokollerini uygulayın. 0025 ile eski bellek sayacını kullanan API sürümünü karıştırmak tek ortak bütçe garantisi vermez. 0026 öncesi bütün eski worker ve API içi drain yolları durdurulmalı; processing veya mükerrer aktif işler varsa göç reddedilir. Yeni lease alanlarını tanımayan eski worker'ı yalnız imaj geri alarak yeniden başlatmayın. Kontrolleri atlamak için iş durumlarını topluca sıfırlamak bu protokolün parçası değildir.

## 4. İlk kurulum

1. **Supabase**: proje aç, `vector` eklentisini etkinleştir, migration'ları
   sırayla uygula, `dou_app` ve `dou_worker` rollerini oluştur ve yetkilerini ver.
2. **İmaj**: `docker build -t <registry>/dou-synapse-api:<sürüm> apps/api`
   Build, modeli indirir ve int8'e quantize eder; **denklik kapısı düşerse build
   de düşer** (§5).
3. **Container Apps**: aynı imajdan iki uygulama.
   - `api`: varsayılan `CMD`, 8000 portu, `minReplicas=0`
   - `worker`: `command: ["python", "-m", "app.worker"]`, giriş portu yok
   - `WORKER_DRAIN_URL` API'ye worker'ın iç adresini gösterir
4. **Vercel**: `apps/web`, `NEXT_PUBLIC_API_URL` API'nin genel adresi.
5. **Duman testi**:
   ```bash
   curl -sf "$API_URL/health/ready"     # {"status":"ok", ...}
   curl -si "$API_URL/internal/drain"   # 404 beklenir: sırsız istek uç yokmuş gibi davranır
   ```
6. **GitHub Secrets** (keepalive için): `KEEPALIVE_DATABASE_URL`,
   `KEEPALIVE_API_URL`. Tanımlanmazsa keepalive işi sessizce atlar.

## 5. Embedding modeli ve int8 kararı

İmaj modeli **build aşamasında** indirir ve içine gömer; çalışma zamanında
HuggingFace'e gitmez. `apps/api/scripts/bake_embedding_model.py` indirir,
int8'e quantize eder ve fp32 ile **aynı vektör uzayında olduğunu ölçer**.
En düşük kosinüs 0.99'un altına düşerse build başarısız olur.

Bu kapı ciddiye alınmalı. Aynı dinamik int8 yolu `all-MiniLM-L6-v2` üzerinde
en düşük **0.9326**, ortalama **0.9513** kosinüs verdi ve en yakın komşu
**sırası korunmadı**. `multilingual-e5-large` için sayı henüz ölçülmedi.

Kapı düşerse iki meşru seçenek var:

```bash
# 1. fp32 göm: imaj ~2 GB büyür, vektör uzayı indekstekiyle BİREBİR aynı kalır
docker build --build-arg EMBEDDING_QUANTIZE=false -t <imaj> apps/api

# 2. Korpusu int8 ile yeniden ingest et — bu bir İNGEST ZAMANI kararıdır ve
#    teslimden GÜNLER önce alınmalıdır, demo sabahı değil.
```

Modelin gerçekten imajda olduğunun kanıtı ağsız bir konteynerdedir:

```bash
docker run --rm --network none <imaj> python -c "
import os
from app.modules.ingestion.embedding import FastEmbedProvider
print(len(FastEmbedProvider(cache_dir=os.environ['EMBEDDING_CACHE_DIR']).embed_query('deadlock')))
"
```

`--network none` olmadan bu kontrol hiçbir şey kanıtlamaz: model eksik olsa bile
çalışma zamanında indirilir ve komut yeşil görünür.

## 6. Yedek ve geri yükleme

Yerel yedek/geri yükleme için [kurtarma protokolü](recovery.md) ve varsayılan kuru koşulu araçlar kullanılır. Aşağıdaki komutlar yalnız plan gösterir; bağlantı açmaz, dosya veya hedef oluşturmaz:

```sh
scripts/backup.sh --bundle /absolute/private/backups/new-unique-bundle
scripts/restore.sh --bundle /absolute/private/backups/new-unique-bundle
```

Gerçek işlem açık `--execute`, geri yüklemede ayrıca bağımsız kaydedilmiş kaynak kimliği, `--trust-own-backup`, `--fence-empty-target` ve önceden hazırlanmış farklı boş hedef gerektirir. Kimlik/sır girdileri ve API Python ortamı recovery rehberindeki sözleşmeyle sağlanır. Araç hedef oluşturmaz, eski arşivin üzerine yazmaz veya belirsiz işlemin ardından hedefi kendiliğinden açmaz. Sahiplik, GRANT/RLS ve tek restore transaction'ı korunur; yalnız politika sayısını karşılaştırmak kabul değildir.

V4 yerel araçları eski kaynakta 29 ilişki/20000 vektör eşliği ve kontrollü hata deneylerini geçti. Güncel 22 göçlü kaynakta ayrıca 30 ilişkinin toplam 14 sentetik satırı, güvenlik kataloğu/rol bileşeni, gerçek eğitmen/dış kullanıcı RLS ayrımı ve quota 42501 reddi doğrulandı. Bu, kirli yerel kaynaklardan alınmış sınırlı kabul; committed release, bulut hesabı veya üretim yedek hizmeti değildir. Arşiv hedefi `specs/018-codex-production-line/evidence/d-final-local/`; [önceki ayrıntılı kanıt](../specs/018-codex-production-line/evidence/d3-local/README.md) korunur.

Dosya deposu bu DB tatbikatında kopyalanmadı. Storage/DB tutarlılığı, şifreleme, korunan dış kopya, saklama/imha ve eski yedekten dönen silinmiş kayıtların uzlaştırması ayrı işletim işidir. 07 eşzamanlı yazıcı ve cross-cluster/control-loss deneyleri açık kalır; herhangi bir hedefi yalnız komut başarılı göründü diye trafiğe açmayın.

## 7. Demo günü (C planı)

Sunumdan **önce**, ağ hâlâ varken:

1. Sınav havuzunu üret ve onayla. **Soru üretimi gerçek LLM anahtarı ister**;
   sahte sağlayıcı üretim şemasını uygulamıyor ve sıfır soru döndürüyor.
2. Önbelleği doldur:
   ```bash
   uv run python scripts/fill_answer_cache.py --base-url "$API_URL"
   ```
   Çıktıdaki her `✗` çevrimdışı sorulmaması gereken bir sorudur.
3. Yedeği al (§6) ve **geri yüklemeyi bir kez prova et** — provası yapılmamış
   yedek, yedek değildir.

Ağ giderse:

```bash
docker compose --profile fallback up
```

Yığın dışarıya hiç çıkmaz: model imajda, kimlik dev-auth'ta, cevaplar
`answer_cache`'te. Önbellekte olmayan bir soru **nazikçe reddedilir** —
uydurulmuş bir cevap vermez.

### 9 Ağustos'ta gerçekten koşulan prova

Yerel süreçlerle, geri yüklenmiş bir veritabanına karşı, tüm dış HTTP çıkışı
ölü bir proxy'ye yönlendirilerek (huggingface.co ve api.groq.com o ortamdan
erişilemez olduğu doğrulandı):

| Adım | Sonuç |
|---|---|
| `/health/ready` | ok (veritabanı + pgvector) |
| Giriş + ders listesi | 1 ders |
| Materyal listesi | 13/13 `completed`, 64 chunk |
| Önbellekten kaynaklı cevap | `answered`, 3 atıf, `cached: true` |
| Atıf çözümlemesi | `05-deadlock-demo.pdf`, Sayfa 2 |
| Kapsam dışı soru | `insufficient_context` — reddedildi |
| Sınav: aç → cevapla → bitir | MCQ deterministik puanlandı, `why_wrong` chunk'ı geldi |

**10/10.** Koşulmayanı da yazalım: compose profilinin kendisi ayağa
kaldırılmadı (bu makinede konteyner çalışma zamanı yok), yığın yerel süreçler
olarak koşturuldu.

## 8. Ölçümler

| Ölçüm | Değer | Nerede ölçüldü |
|---|---|---|
| Sıcak `/chat` p95, önbellek ıskası | **72.7 ms** (medyan 57.8) | Yerel uvicorn, n=30 |
| Sıcak `/chat` p95, önbellekten | **9.2 ms** (medyan 7.9) | Yerel uvicorn, n=15 |
| Süreç başlangıcı → `/health/ready` | **0.61 sn** | Yerel, 5 tekrar |
| Süreç başlangıcı → ilk soru | **1.43–1.55 sn** | Yerel, 5 tekrar |
| ACA scale-to-zero uyanma | **KOŞULMADI** | Bulut erişimi yok |
| İmaj boyutu, replika RSS | **KOŞULMADI** | Konteyner çalışma zamanı yok |
| int8 ↔ fp32 kosinüs (e5-large) | **KOŞULMADI** | Yerel diskte yer yetmedi; CI üretecek |

**Bu sayılar üretim p95'i DEĞİLDİR.** LLM anahtarı yokken üretim deterministik
sahte sağlayıcıya düşer ve generation terimi ~0 olur; ölçülen yol retrieval +
guardrail + veritabanıdır. Ayrıca ölçümler bu Mac'te, yerel uvicorn ile
alınmıştır; ACA'nın konteyner zamanlama ve imaj çekme maliyetini içermez ve
model dosyası işletim sistemi sayfa önbelleğindeydi — 1.47 sn bir **alt
sınırdır**.

Tekrarlamak için:

```bash
uv run python scripts/measure_latency.py warm --base-url "$API_URL" \
    --course-id <uuid> --user-id <uuid> --count 30
uv run python scripts/measure_latency.py cold --base-url "$API_URL" \
    --repeat 5 --idle-wait 900
```

## 9. Geri alma (rollback)

1. **Uygulama**: Container Apps'te bir önceki revizyona geç. İmajlar
   sürümlenmiş etiketlerle itilir; `latest` üretimde kullanılmaz.
2. **Migration**: geri alma betiği YOKTUR. Bir migration üretimde soruna yol
   açtıysa yol, ileri doğru düzelten yeni bir migration'dır; şema geri sarılmaz.
   Veri kaybı riski varsa §6'daki yedekten geri yüklenir.
3. **Sıra önemli**: uygulamayı geri almak, uygulanmış bir migration'ı geri
   almaz. Yeni sürüm yeni bir sütuna yazıyorduysa eski sürüm o sütunu görmez
   ama veri orada durur.

## 10. T050 — üretim doğrulaması (KOŞULMADI)

Gerçek erişim gerektiren, henüz yapılmamış adımlar:

- [ ] Migration'lar gerçek Supabase'de koşuldu
- [ ] Vercel'de `NEXT_PUBLIC_API_URL` + Supabase anahtarları ayarlandı
- [ ] ACA'da `DEV_AUTH_ENABLED=false` ile uygulamanın gerçekten açıldığı
      (ve `true` bırakılırsa açılmadığı) gözlendi
- [ ] CORS yalnız gerçek alan adıyla çalışıyor
- [ ] LLM failover canlı: Groq anahtarı bilerek bozulur → Gemini'ye geçiş
      gözlenir → geri alınır
- [ ] Cold start ve p95 gerçek replikada ölçüldü (§8)
- [ ] İmaj boyutu ve replika RSS ölçüldü (ACA ≤ 2 vCPU / 4 GiB)

## 014 öğrenci çalışma alanı

`STUDENT_ASSESSMENT_WORKSPACE_ENABLED` varsayılan `false`; `.env.example` yalnız yerel
geliştirme için `true` önerir. API'yi bu değişkenle yeniden başlatmak katalog/geçmiş/sonuç
arayüzünü açar. Önce sıralı migration'lar, özellikle `0018_question_authoring.sql` ve
`0019_exam_duration_projection.sql`, uygulanmalıdır. 0019 yalnız sahibine oturum süresini
açan dar bir fonksiyon ekler, kayıt taşımaz/silmez.

Kapatma: bayrağı `false` yapıp API'yi yeniden başlatın; katalog `enabled:false`, yeni
geçmiş/sonuç uçları503 verir. Mevcut başlangıç ve bitirme devam eder. Kaynak doğrulama,
sahiplik ve süre güvenliği düzeltmeleri bayraktan bağımsızdır; geri almada gevşetilmemelidir.
Gerekirse kapalı çalışma alanıyla ileri düzeltme yayımlayın; önceki uygulamaya dönmek
bilinen kaynaksız puan/süre hatalarını geri getirir. 0019'u silmeyin, geçmiş kayıtları
yeniden puanlamayın. Canlı rollback provası bu yerel teslimde yapılmadı.

014, henüz main'e alınmamış yerel013 değişikliğinin üzerine kuruludur. Canlıya geçişten
önce tam birleşik aday, migration sırası, gerçek sağlayıcı değerlendirmesi ve bağımsız
mühendislik/eğitim/güvenlik onayı doğrulanmalıdır. Yerel test sonucu yayın onayı değildir.


## 015 değerlendirme ve çalışma sürekliliği

Yeni kayıtlı alıştırma geri bildirimi mevcut `STUDENT_ASSESSMENT_WORKSPACE_ENABLED` bayrağına bağlıdır. Bayrak kapalıyken yeni geri bildirim/geçmiş/sonuç uçları503 verir; temel sınav bitirme ve kaynak/süre korumaları sürer. Soru kullanım listesi ders eğitmeni yetkisiyle salt okunur sürüm bilgisi sunar; yeni göç yoktur.

Değerlendirme modu üretimde kapalıdır. `EVAL_RUNTIME_ENABLED=false` ve boş değerlendirme sırrı varsayılandır. Ayrı anahtar, loopback, güvenilir çalışma/yanıt kanıtı ve sınırlı çağrı komutları için [sağlayıcı hazırlığı](provider-readiness.md) ile [kabul paketi](../evaluation/acceptance/README.md) kullanılır. Çevrimdışı kontrol veya sentetik yedek geri yükleme, gerçek sağlayıcı/staging/PITR kanıtı değildir. Tam durum [015 doğrulaması](../specs/015-completion-program/verification.md) ve [teslim incelemesinde](../specs/015-completion-program/release-review.md) kayıtlıdır.
