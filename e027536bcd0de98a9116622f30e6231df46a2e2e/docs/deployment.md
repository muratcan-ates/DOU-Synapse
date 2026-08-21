# Dağıtım

DOU-Synapse'ın kurulumunun tek doğru anlatımı. Değerler burada YOKTUR — yalnız
değişken adları ve ne işe yaradıkları. Gerçek değerler sağlayıcıların gizli
değer kasalarında durur ve depoya asla girmez.

> **Durum, 9 Ağustos 2026.** Bu belgedeki bulut adımları **KOŞULMADI**: gerçek
> Azure/Vercel/Supabase erişimi olmadan yazıldılar (T050 hâlâ açık). Yerelde
> ölçülmüş ve koşulmuş olanlar §7'de ayrıca işaretli. Bir adımı ilk kez koşan
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

Worker scale-to-zero ile uyur. Belge yüklendiğinde API onu `POST /internal/drain`
ile uyandırır; kuyruğu yoklayan bir döngü scale-to-zero'yu anlamsızlaştırırdı.

## 2. Ortam değişkenleri

Tam liste `.env.example`'dadır. Dağıtımda önemli olanlar:

### API ve worker (ikisinde de aynı)

| Değişken | Ne işe yarar |
|---|---|
| `ENVIRONMENT` | `production` — bu değer `DEV_AUTH_ENABLED` ve `LLM_FAKE_PROVIDER`'ı kilitler |
| `DATABASE_URL` | API bağlantısı. **`dou_app` rolüyle**: sahip değildir, `BYPASSRLS` taşımaz, dolayısıyla RLS gerçekten uygulanır |
| `WORKER_DATABASE_URL` | Worker bağlantısı. `dou_worker` rolü RLS'i atlar; `chunks` tablosuna yalnız o yazabilir |
| `SUPABASE_JWT_SECRET` | Supabase JWT'lerini doğrular. Yoksa ve dev-auth da kapalıysa uygulama **başlamaz** |
| `SUPABASE_JWT_ISSUER` | Beklenen `iss` claim'i — Supabase proje URL'sinin `/auth/v1` eki. **Boş bırakılırsa issuer doğrulanmaz** ve başka bir Supabase projesinin token'ı da kabul edilir. İmza doğrulaması etkilenmez; kaybedilen katman issuer sabitlemesidir. Üretimde doldurun |
| `CORS_ORIGINS` | JSON dizisi. Üretimde yalnız gerçek Vercel alan adı |
| `GROQ_API_KEY`, `GEMINI_API_KEY` | LLM sağlayıcıları; ilki düşerse ikincisine otomatik geçilir |
| `WORKER_DRAIN_SECRET` | `POST /internal/drain` ucunu korur. **Boşsa uç 404 döner** (fail-closed) |
| `EMBEDDING_PROVIDER` | Üretimde `fastembed`. **İngest zamanı ayarıdır** — değiştirmek tüm korpusun yeniden işlenmesini gerektirir |
| `EMBEDDING_CACHE_DIR` | İmajda `/opt/models`; Dockerfile ayarlar |

### Yalnız API

| Değişken | Ne işe yarar |
|---|---|
| `WORKER_DRAIN_URL` | Worker'ın drain ucunun tam adresi. **Tanımlıysa** tetik HTTP'ye döner; tanımsızsa süreç içinde `drain()` koşar |
| `CHAT_RATE_LIMIT_REQUESTS`, `CHAT_RATE_LIMIT_WINDOW_SECONDS` | Kullanıcı başına sohbet sınırı. Sayaç **süreç içidir**: birden fazla replikada sınır replika başına uygulanır |

> **Lidere:** `WORKER_DRAIN_URL` şu an `Settings` alanı DEĞİL, doğrudan ortamdan
> okunuyor (`app/api/internal.py`). Sebebi `core/config.py`'nin bu fazda şeritlere
> kapalı olmasıydı. Faz kapanınca `Settings.worker_drain_url` olarak taşınmalı ve
> `.env.example`'a eklenmeli.

### Web (Vercel)

`NEXT_PUBLIC_API_URL` ve Supabase anahtarları — bunlar liderin alanı
(`apps/web/**` hiçbir şeride açık değil).

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

**`main`'e girmiş bir migration yerinde değiştirilmez.** Yeni numara açılır.
Bir dağıtımda migration'ları uygulamadan önce §6'daki yedeği alın.

`supabase/local_dev_setup.sql` ve `supabase/seed_demo.sql` **üretimde
koşturulmaz**: birincisi yerel roller kurar, ikincisi sahte kullanıcı yaratır.

Kurulumdan sonra şemayı doğrulayın:

```bash
psql -d "$DATABASE" -c "\dt"
```

Temiz bir kurulumda **15 tablo** görürsünüz. (Faz 2 brifingi "19 tablo" diyor;
9 Ağustos'ta hem paylaşılan geliştirme veritabanında hem sıfırdan kurulan bir
veritabanında ölçülen sayı 15'tir. Brifingdeki sayı yanlış.)

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

```bash
# Yedek
pg_dump -Fc -d "$DATABASE" -f backup/dou_synapse.dump
tar -czf backup/storage.tar.gz -C "$STORAGE_PARENT" storage

# Geri yükleme (TEMİZ bir veritabanına)
createdb "$TARGET"
pg_restore -d "$TARGET" --no-owner backup/dou_synapse.dump
psql -d "$TARGET" -c "GRANT CONNECT ON DATABASE \"$TARGET\" TO dou_app, dou_worker"
tar -xzf backup/storage.tar.gz -C "$STORAGE_PARENT"
```

Geri yükleme sonrası **politika sayısını doğrulayın** — sessizce yetki kaybı,
sessizce açılmış bir veritabanı demektir:

```bash
psql -d "$TARGET" -tAc "select count(*) from pg_policies where schemaname='public'"
# kaynakla aynı olmalı (9 Ağustos ölçümü: 40)
```

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
