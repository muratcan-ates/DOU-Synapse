# Dağıtım

DOU-Synapse'ın kurulumunun tek doğru anlatımı. Değerler burada YOKTUR — yalnız
değişken adları ve ne işe yaradıkları. Gerçek değerler sağlayıcıların gizli
değer kasalarında durur ve depoya asla girmez.

> **Durum, 20 Ağustos 2026.** Bu belgedeki bulut adımları **KOŞULMADI**: gerçek
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
| `DATABASE_URL` | API bağlantısı. Gerçek LOGIN kimliği **`dou_api_runtime`** olmalıdır; rol sahip değildir ve `BYPASSRLS` taşımaz. `dou_app` yalnız NOLOGIN yetki taşıyıcısıdır |
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
| `ASSESSMENT_BLUEPRINT_ENABLED` | Varsayılan `false`: resmî blueprint başlangıçlarını fail-closed kapatır. Yalnız aynı candidate için onaylı rollout ortamında `true` yapılır; mevcut oturum devam yolları bu kill switch'ten etkilenmez |
| `API_OBSERVABILITY_ENABLED` | Varsayılan `false`: içeriksiz HTTP event kuyruğunu/yazıcısını açar. Kapamak ana API'yi veya geçmiş admin sorgusunu kapatmaz |
| `API_EVENT_RETENTION_DAYS` | 1–30 gün. Collector production'da açıksa açıkça verilmesi zorunludur; varsayılanı canlı saklama kararı sayılmaz |
| `RELEASE_REVISION` | Event korelasyonu için güvenli deployment etiketi/Git SHA; secret veya serbest metin değildir |
| `API_DOCS_ENABLED` | Local/demo'da varsayılan açık; production'da zorla kapalıdır ve `true` konfigürasyonu uygulamayı başlatmaz |
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
| `0016` | Assessment integrity + `dou_api_runtime` bağlantı kimliği kesimi |
| `0017` | İçeriksiz API request event'i, exact-runtime recorder, admin projection ve bounded retention |

**`main`'e girmiş bir migration yerinde değiştirilmez.** Yeni numara açılır.
Bir dağıtımda migration'ları uygulamadan önce §6'daki yedeği alın.

### `0016` çalışma zamanı kimliği kesimi

`0016_assessment_integrity.sql`, hassas assessment tablolarını gerçek bağlantı
kimliğine bağlar. Mevcut bir ortamda sıradan “migration çalıştır, sonra uygulamayı
yenile” sırası güvenli değildir. Aşağıdaki kesim tek bakım penceresinde ve bu sırayla
yapılır:

1. `0001..0015` uygulanmışken, altyapı yöneticisi `dou_api_runtime` rolünü
   `LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS`
   özellikleriyle ve gizli-değer kasasından gelen benzersiz bir parolayla önceden
   oluşturur. Rol `dou_app` üyesi olur; üyelik `INHERIT TRUE`, `SET FALSE`,
   `ADMIN FALSE` olmalıdır. Hedef veritabanına `CONNECT` verilir. Gerçek parola
   SQL dosyasına, terminal geçmişine veya repoya yazılmaz.
2. Yeni API secret/revision'ı `DATABASE_URL` içinde `dou_api_runtime` kullanacak
   şekilde hazırla. Aynı DSN veya aynı yönetilen pooler yolu üzerinden aşağıdaki
   preflight'i çalıştır:

   ```sql
   SELECT session_user, current_user;
   -- ikisi de dou_api_runtime olmalı
   ```

   Pooler upstream'e başka bir kullanıcıyla bağlanıp yalnız `SET ROLE
   dou_api_runtime` yapıyorsa bu sözleşmeyi sağlamaz. `0016` güven işaretini
   `session_user` ile doğrular; transaction/session pooler seçimi bu kimliği
   korumalıdır.
3. Eski `dou_app` API replikalarına trafik vermeyi kes. Owner/admin bağlantısında,
   migration transaction'ından **ayrı ve commit edilmiş** bir kesim uygula:

   ```sql
   ALTER ROLE dou_app NOLOGIN PASSWORD NULL;
   ```

   Bu adım yeni carrier oturumlarını keser; mevcut oturumları öldürmez. Eski
   replikaların pool'larını kapat, eski DSN ile yeni bağlantının authentication
   hatası verdiğini gözle, sonra rol ve aktif oturum preflight'ini yap:

   ```sql
   SELECT rolcanlogin FROM pg_roles WHERE rolname = 'dou_app';
   -- false

   SELECT count(*) FROM pg_stat_activity
   WHERE usename = 'dou_app' AND pid <> pg_backend_pid();
   -- 0
   ```

   `ALTER ROLE` ile `0016` aynı transaction'a konmaz. Aksi hâlde preflight ile
   commit arasındaki aralıkta eski parola yeni ve kalıcı bir oturum açabilir.
4. `0016`yı owner/admin bağlantısıyla uygula. Migration `dou_app`ın zaten NOLOGIN
   ve aktif oturumsuz olduğunu doğrular; carrier'ın parent rolü, runtime'ın üyesi
   veya `dou_app` dışında parent'ı varsa fail-closed durur. Güvenli rol
   özelliklerini normalize eder, hassas ACL'leri `dou_api_runtime`a verir ve
   `app.is_api_runtime()` kontrolünü kurar. Ayrıca `public` tablo CRUD grant'lerini
   unsafe kayıt sahibi bazında kaldırır. `app` schema sahibi, current migration owner
   ve mevcut `app` fonksiyon owner'ları için fonksiyonların global hard-wired ve açık
   schema-local PUBLIC EXECUTE varsayılanlarını kapatır; etkin kalıntı varsa commit
   etmez. Migration kimliği bu owner'lar adına default privilege değiştirebilmelidir;
   yetki hatasında doğru admin kimliğini kullan, kontrolü atlama.
   İlk LOGIN kesimini migration'a bırakmak desteklenen rollout değildir.
5. Aday API'yi yalnız runtime DSN ile başlat. `/health/ready` 200 dönmeli ve
   `checks.database_role` değeri `ok` olmalıdır. `invalid`, pooler/DSN kimliğinin
   yanlış olduğunu gösterir; bu revizyona trafik verilmez.

Temiz ilk kurulumda da aynı rol özellikleri korunur. Migration rolü NOLOGIN olarak
oluşturduysa uygulama başlamadan önce altyapı onu LOGIN + secret ile hazırlar;
`dou_app` hiçbir ortamda bağlantı kullanıcısına çevrilmez. `supabase/local_dev_setup.sql`
yalnız yerel geliştirme içindir ve bu üretim secret adımının yerine geçmez.

Mevcut veride aynı soru hem resmî `exam_item` hem eski kâğıtsız oturumun
`question_ids` dizisindeyse `0016` soruyu `assessment` yapar; legacy referansları
değiştirmez. Dar own-session RLS dalı yalnız o mevcut oturum sahibinin devamına izin
verir. Yeni practice seçimi `purpose=practice` filtresinde kalır; aynı dersteki
oturumsuz öğrenci resmî satırı göremez. Üretim öncesi kopyada upgrade kanıtının
kohort sınırı, legacy sahip devamı, oturumsuz öğrenci reddi ve owner'lar arası default
ACL temizliği PASS sonuçları birlikte aranır.

`supabase/local_dev_setup.sql` ve `supabase/seed_demo.sql` **üretimde
koşturulmaz**: birincisi yerel roller kurar, ikincisi sahte kullanıcı yaratır.

Kurulumdan sonra şemayı doğrulayın:

```bash
psql -d "$DATABASE" -c "\dt"
```

Güncel migration setiyle temiz bir kurulumda **28 tablo** görürsünüz. <!-- docs-check: tables.count = 28 -->

Tarihsel not: 9 Ağustos'ta hem paylaşılan geliştirme veritabanında hem sıfırdan
kurulan veritabanında **15 tablo** ölçülmüştü. <!-- docs-check: tarihsel 15 · 2026-08-09 -->
Faz 2 brifingindeki daha yüksek tablo tahmini o gün için de yanlıştı.

## 4. İlk kurulum

1. **Supabase**: proje aç, `vector` eklentisini etkinleştir, migration'ları
   sırayla uygula; `dou_api_runtime` ve `dou_worker` LOGIN secret'larını altyapıda
   oluştur. `dou_app` NOLOGIN yetki taşıyıcısı olarak kalır. Mevcut ortamın `0016`
   yükseltmesi için §3'teki bakım penceresini uygula.
2. **İmaj**: `docker build -t <registry>/dou-synapse-api:<sürüm> apps/api`
   Build, modeli indirir ve int8'e quantize eder; **denklik kapısı düşerse build
   de düşer** (§5).
3. **Container Apps**: aynı imajdan iki uygulama.
   - `api`: varsayılan `CMD`, 8000 portu, `minReplicas=0`
   - `worker`: `command: ["python", "-m", "app.worker"]`, giriş portu yok
   - `WORKER_DRAIN_URL` API'ye worker'ın iç adresini gösterir
   - `ASSESSMENT_BLUEPRINT_ENABLED=false` ilk güvenli dağıtımda korunur; staging,
     insan onayı ve rollout kanıtı olmadan açılmaz
   - `API_OBSERVABILITY_ENABLED=false` ilk güvenli dağıtımda korunur. `0017`,
     runtime kimliği, retention ve admin projection doğrulandıktan sonra staging/canary'de açılır
     (`0017` migration-first uygulanabilir: eski API'nin güvenli karakterli legacy
     request ID'si ham saklanmadan yeni 32-hex audit koduna çevrilir; eski replikalar
     drain edilmeden bu uyumluluk dalı kaldırılmaz)
   - `API_DOCS_ENABLED=false` production'da değiştirilemez; Swagger yalnız local/demo içindir
4. **Vercel**: `apps/web`, `NEXT_PUBLIC_API_URL` API'nin genel adresi.
5. **Duman testi**:
   ```bash
   curl -sf "$API_URL/health/ready"     # status=ok ve checks.database_role=ok
   curl -si "$API_URL/internal/drain"   # 404 beklenir: sırsız istek uç yokmuş gibi davranır
   ```
   Staging collector açıldıysa platform admin token'ıyla
   `POST /admin/api-events/query` çağrısı yalnız route/status/süre/support-code
   alanlarını dönmeli; kullanıcı, ders, ham path/query/body bulunmamalıdır.
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
psql -d "$TARGET" -c "GRANT CONNECT ON DATABASE \"$TARGET\" TO dou_api_runtime, dou_worker"
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

1. **Assessment kill switch**: `ASSESSMENT_BLUEPRINT_ENABLED=false` ile yeni
   resmî başlangıçları kapat; mevcut oturumların get/answer/finish/results yollarını
   açık tut. Bu, yarım sınavı veya öğrencinin süresini kaybetmeden blast radius'u
   durdurur.
2. **Observability kill switch**: `API_OBSERVABILITY_ENABLED=false` ile yeni event
   kuyruğunu/yazıcısını kapat. Tek bağlantılı bounded retention bakımı ve ayrı
   pool, süresi dolan mevcut satırların diski büyütmemesi için çalışmayı sürdürür.
   Ürün trafiği, geçmiş admin query ve additive `0017` tablosu yerinde kalır;
   migration'ı geri sökme. Queue drop, DB write failure veya tablo büyümesi
   normale dönmeden tekrar açma.
3. **Uygulama**: yalnız post-`0016` sözleşmesiyle önceden doğrulanmış bir önceki
   revizyona geç veya fix-forward uygula. İmajlar sürümlenmiş etiketlerle itilir;
   `latest` üretimde kullanılmaz.
4. **Migration**: geri alma betiği YOKTUR. Bir migration üretimde soruna yol
   açtıysa yol, ileri doğru düzelten yeni bir migration'dır; şema geri sarılmaz.
   Veri kaybı riski varsa §6'daki yedekten geri yüklenir.
   `0017` öncesi bir uygulama revizyonuna dönmek retention görevini de kaldırır;
   olay satırları varken bu dönüş yasaktır. Böyle bir zorunlulukta önce aynı
   runtime rolüyle periyodik `app.purge_expired_api_request_events(1000)` bakımını
   kur ve prova et ya da `010` uyumlu fix-forward revizyonu kullan.
5. **Veritabanı kimliği değişmez**: `0016` sonrasında eski uygulama revizyonu da
   `dou_api_runtime` DSN ile çalıştırılır. `dou_app` NOLOGIN/parolasızdır ve hassas
   ACL'leri geri verilmez. “Rollback” adı altında `dou_app` LOGIN açmak güvenlik
   sınırını kaldırmaktır.
6. **Sıra önemli**: uygulamayı geri almak, uygulanmış bir migration'ı geri
   almaz. Yeni sürüm yeni bir sütuna yazıyorduysa eski sürüm o sütunu görmez
   ama veri orada durur.

## 10. T050 — üretim doğrulaması (KOŞULMADI)

Gerçek erişim gerektiren, henüz yapılmamış adımlar:

- [ ] Migration'lar gerçek Supabase'de koşuldu
- [ ] `dou_api_runtime` secret + üyelik + `session_user` pooler preflight'i gerçek
      Supabase yolunda doğrulandı; rol grafiği dar; eski `dou_app` havuzu sıfırlandı
- [ ] `0016` cross-owner tablo default grant'lerini ve ilgili owner'ların global/
      schema-local PUBLIC function EXECUTE varsayılanlarını temizledi; yeni probe
      fonksiyon PUBLIC'e kapalı kaldı
- [ ] Mixed-use legacy sahibi devam ederken aynı dersteki oturumsuz öğrenci resmî
      soruyu göremedi
- [ ] `/health/ready` gerçek dağıtımda `checks.database_role=ok` gösterdi
- [ ] Vercel'de `NEXT_PUBLIC_API_URL` + Supabase anahtarları ayarlandı
- [ ] ACA'da `DEV_AUTH_ENABLED=false` ile uygulamanın gerçekten açıldığı
      (ve `true` bırakılırsa açılmadığı) gözlendi
- [ ] CORS yalnız gerçek alan adıyla çalışıyor
- [ ] LLM failover canlı: Groq anahtarı bilerek bozulur → Gemini'ye geçiş
      gözlenir → geri alınır
- [ ] Cold start ve p95 gerçek replikada ölçüldü (§8)
- [ ] İmaj boyutu ve replika RSS ölçüldü (ACA ≤ 2 vCPU / 4 GiB)
