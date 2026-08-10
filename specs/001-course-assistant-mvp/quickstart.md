# Quickstart — Sıfırdan Yerel Kurulum

Bu belge, DOU-Synapse'i temiz bir macOS makinede (Homebrew ile) sıfırdan ayağa
kaldırır: PostgreSQL 16 + pgvector, şema + seed, FastAPI backend'i, testler ve
Next.js frontend'i. Tüm komutlar repo kökünden (`~/code/DOU-Synapse`) verilmiştir.

> **Son doğrulama: 9 Ağustos 2026.** Adım 2'deki migration döngüsü boş bir veritabanında
> baştan koşuldu (**15 tablo**, hatasız), adım 3-4 aynı gün tekrarlandı (**479 test <!-- docs-check: tarihsel 15 · 2026-08-09 --><!-- docs-check: tarihsel 479 · 2026-08-09 -->
> yeşil**), adım 5-6 tarayıcıda gerçek materyalle sınandı.
>
> **Bir adımı atlarsanız bile §6.1'i okuyun:** varsayılan ayarlarla sistem ayağa kalkar
> ama **asistan işe yarar cevap veremez.** Sebebi ve tek satırlık düzeltmesi orada.

> Alternatif: adım 1-3'ü atlayıp `docker compose up` ile de çalışabilirsiniz
> (bkz. [§8](#8-alternatif-docker-compose)). Aşağıdaki yol, testlerin ve RLS
> kanıtının koştuğu birincil geliştirme yoludur.

## 0. Önkoşullar

| Araç | Neden | Kurulum |
|---|---|---|
| Homebrew | Postgres paketi | https://brew.sh |
| `uv` | Python ortamı (Python 3.12'yi kendisi indirir) | `brew install uv` |
| Bun 1.x | Frontend paket yöneticisi (`apps/web/package.json` → `"packageManager": "bun@1.3.14"`) | `brew install oven-sh/bun/bun` |
| Git + Xcode CLT | pgvector'ü kaynaktan derlemek için `make`/`clang` | `xcode-select --install` |

## 1. PostgreSQL 16 + pgvector

Proje **PostgreSQL 16**'ya sabitlidir (anayasa "Teknoloji Kilidi"; testler de
varsayılan olarak `/opt/homebrew/opt/postgresql@16/bin` yolunu kullanır —
`apps/api/tests/conftest.py` içindeki `PG_BIN`).

```bash
brew install postgresql@16
brew services start postgresql@16

# postgresql@16 keg-only'dir; psql/createdb için PATH'e ekleyin (kalıcısı ~/.zshrc'ye):
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
```

**pgvector — kaynaktan derleme.** Homebrew'daki `pgvector` paketi güncel
Postgres'e (17/18) karşı derlenir ve postgresql@16'ya kurulmaz. pgvector'ü
kaynaktan, 16'nın `pg_config`'ini göstererek derleyin:

```bash
cd /tmp
git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git
cd pgvector
make PG_CONFIG=/opt/homebrew/opt/postgresql@16/bin/pg_config
make install PG_CONFIG=/opt/homebrew/opt/postgresql@16/bin/pg_config
```

(Homebrew dizinleri kullanıcıya ait olduğundan `sudo` gerekmez. Daha yeni bir
pgvector sürüm tag'i de kullanılabilir; şemanın ihtiyacı `vector(1024)` tipidir.)

Doğrulama:

```bash
psql -d postgres -c "SELECT name FROM pg_available_extensions WHERE name = 'vector';"
```

`vector` satırı dönmüyorsa derleme yanlış `pg_config`'e karşı yapılmıştır.

## 2. Veritabanı: oluştur → migrate → yerel roller → RLS kanıtı → seed

Sıra önemlidir: migration `dou_app`/`dou_worker` rollerini **NOLOGIN** oluşturur;
`local_dev_setup.sql` bu rollere yalnızca yerelde giriş açar; izolasyon testi kendi
kimliklerini ekleyip geri alır; seed demo kullanıcılarını yazar. **İzolasyon testi
seed'den sonra koşturulursa çakışır** — sebebi aşağıda.

```bash
createdb dou_synapse

# 1) Şema + RLS politikaları + roller (vector/unaccent/pgcrypto extension'ları dahil)
#    TÜM migration'lar sırayla uygulanır — tek tek saymayın, yenisi eklendiğinde
#    bu döngü onu da alır (CI ve conftest.py da aynı şekilde sıralı glob kullanır).
for f in supabase/migrations/*.sql; do
  psql -v ON_ERROR_STOP=1 -d dou_synapse -f "$f"
done

# 2) YALNIZCA YEREL: dou_app / dou_worker rollerine LOGIN + parola
#    (dou_app_local / dou_worker_local — .env.example'daki DSN'lerle eşleşir)
psql -d dou_synapse -f supabase/local_dev_setup.sql

# 3) İzolasyon kanıtı — seed'den ÖNCE (aşağıdaki nota bakın), 8 PASS dönmeli
psql -d dou_synapse -f supabase/tests/rls_isolation.sql

# 4) Demo kullanıcıları (Ayşe + Burak, sabit UUID'ler)
psql -d dou_synapse -f supabase/seed_demo.sql
```

**Doğrulama — 25 tablo görmelisiniz:** <!-- docs-check: tables.count = 25 -->

```bash
psql -d dou_synapse -tAc "select count(*) from information_schema.tables
  where table_schema='public' and table_type='BASE TABLE'"     # 15
```

Migration numaralarının atlamalı gitmesi (`0001, 0003, 0004, 0005`) normaldir: `0002`,
`0006` ve `0007` devam eden işlere ayrılmıştır ve henüz depoda değildir. `0005` tablo
oluşturmaz, yalnız analitiğin ihtiyaç duyduğu okuma politikasını ekler — bu dosya
atlanırsa **eğitmen analitiği sessizce boş görünür.**

Notlar:

- Bu komutları Homebrew'un varsayılan (superuser) kullanıcınızla çalıştırın;
  seed RLS'i bu sayede atlar. **Uygulama asla superuser ile bağlanmaz** — API
  `dou_app` (RLS'e tabi), worker `dou_worker` (BYPASSRLS) rolünü kullanır.
- `local_dev_setup.sql` içindeki `GRANT CONNECT ON DATABASE dou_synapse` satırı
  veritabanı adını sabit taşır; başka bir adla kurarsanız o satırı da değiştirin.
- `local_dev_setup.sql` ve `seed_demo.sql` üretimde/demoda ÇALIŞTIRILMAZ
  (dosya başlıklarındaki uyarılar).

### RLS kanıtı — seed'den ÖNCE koşturun

İzolasyon testi **8 kontrol** koşar ve sonunda `ROLLBACK` yapar, yani veritabanınızı
kirletmez:

```bash
psql -d dou_synapse -f supabase/tests/rls_isolation.sql   # 8 PASS
```

**Sıra önemli.** Test kendi sabit kimliklerini (`11111111-…`, `22222222-…`) kendisi
ekler ve bunlar `seed_demo.sql`'in eklediği kimliklerle **aynıdır**. Seed'den sonra
koşturursanız test ilk satırında düşer:

```
ERROR:  duplicate key value violates unique constraint "profiles_pkey"
```

Bu bir izolasyon hatası değil, testin kurulum çakışmasıdır. İki çözüm:

- Testi **adım 3'ten (seed) önce** koşturun — yukarıdaki sıralamada böyle yapılmıştır; ya da
- Seed uyguladıysanız kanıtı **temiz bir veritabanında** alın:
  ```bash
  createdb dou_synapse_rls
  for f in supabase/migrations/*.sql; do psql -q -v ON_ERROR_STOP=1 -d dou_synapse_rls -f "$f"; done
  psql -d dou_synapse_rls -f supabase/tests/rls_isolation.sql   # 8 PASS
  dropdb dou_synapse_rls
  ```

Kalıcı çözüm (testin `INSERT`'lerine `ON CONFLICT DO NOTHING` eklemek) `supabase/tests/`
sahibine iletildi. CI temiz bir veritabanı kurduğu için bu çakışmayı hiç görmez —
yalnız belgeyi izleyen insan görür.

## 3. Backend (apps/api): uv kurulumu + .env

```bash
cd apps/api
uv venv --python 3.12          # pyproject: >=3.12,<3.13 (onnxruntime/fastembed pini)
uv pip install -e ".[dev]"
cp ../../.env.example .env
```

`.env.example`'ın varsayılanları yerel kurulumla birebir eşleşir ve **hiçbir değeri
değiştirmeden sistem ayağa kalkar** — ama asistandan işe yarar cevap almak için bir
değişiklik gerekir; bkz. **§6.1**.

| Değişken | Varsayılan | Anlamı |
|---|---|---|
| `ENVIRONMENT` | `local` | — |
| `DATABASE_URL` | `postgresql+psycopg://dou_app:dou_app_local@localhost:5432/dou_synapse` | API, RLS'e tabi `dou_app` rolüyle |
| `WORKER_DATABASE_URL` | `postgresql+psycopg://dou_worker:dou_worker_local@localhost:5432/dou_synapse` | Worker, `chunks` yazabilen ayrı rolle |
| `SUPABASE_JWT_SECRET` | (boş) | `DEV_AUTH_ENABLED=true` iken gerekmez |
| `DEV_AUTH_ENABLED` | `true` | İmzasız `Bearer dev:<uuid>` kimlikleri kabul edilir. `ENVIRONMENT=production` iken açılırsa uygulama **başlamaz** (`app/core/config.py` doğrulayıcısı) |
| `CORS_ORIGINS` | `["http://localhost:3000","http://localhost:3100"]` | 3000 geliştirme, 3100 uçtan uca test sunucusu. **Başka bir portta çalıştıracaksanız buraya ekleyin**, yoksa tarayıcı istekleri CORS'a takılır |
| `EMBEDDING_PROVIDER` | `hashing` | Deterministik yerel embedding — model indirmeden çevrimdışı geliştirme. **Gerçek kullanım için `fastembed` gerekir (§6.1).** Geçiş **ingest-zamanı kararıdır**: tüm korpus yeniden işlenir |
| `EMBEDDING_CACHE_DIR` | (boş) | Boşken fastembed modeli macOS'ta `$TMPDIR` altına indirir ve **işletim sistemi orayı temizler.** Kalıcı bir dizin verin (§6.1) |

Çalıştırma (hâlâ `apps/api` içinde):

```bash
uv run uvicorn app.main:app --reload
```

Doğrulama:

```bash
curl http://localhost:8000/health/live    # süreç ayakta mı
curl http://localhost:8000/health/ready   # veritabanı erişimi dahil
```

**Worker hakkında:** yerel geliştirmede ayrı bir worker süreci başlatmak
zorunlu değildir — yükleme sonrası API worker'ın `drain()` tek turunu kendisi
tetikler (`app/api/documents.py`). İstenirse sürekli döngü ayrıca çalıştırılabilir:

```bash
uv run python -m app.worker
```

## 4. Testler ve kalite kapıları

```bash
cd apps/api
uv run pytest          # 851 test yeşil olmalı (~50-100 sn)   # docs-check: backend.tests = 851
uv run mypy app        # temiz
uv run ruff check .
uv run ruff format --check .
```

Test altyapısı (`tests/conftest.py`):

- Her koşuda `dou_synapse_test` veritabanını **düşürüp sıfırdan kurar**
  (migration'lar + rol parolaları); geliştirme veritabanınıza dokunmaz.
- `psql`'i `PG_BIN` (varsayılan `/opt/homebrew/opt/postgresql@16/bin`) üzerinden
  çağırır; Postgres başka yerdeyse `PG_BIN` ortam değişkeniyle geçersiz kılın.
  Diğer ayar noktaları: `TEST_DB_NAME`, `TEST_ADMIN_DSN`, `TEST_APP_DSN`,
  `TEST_WORKER_DSN`.
- Testler kasıtlı olarak `dou_app` rolüyle bağlanır — superuser ile koşan bir
  izolasyon testi hiçbir şey kanıtlamaz.

## 5. Frontend (apps/web): bun

```bash
cd apps/web
bun install
bun run dev
```

http://localhost:3000 açılır. API adresi `NEXT_PUBLIC_API_URL` ile ayarlanabilir;
tanımsızsa `http://localhost:8000` kullanılır (`lib/api.ts`) — yerelde ek `.env`
gerekmez.

## 6. Demo kullanıcıları ile giriş

Giriş sayfası (`app/page.tsx`) iki geliştirme kimliği kartı sunar; kart
tıklandığında tarayıcıya `Bearer dev:<uuid>` token'ı yazılır ve backend bunu
`DEV_AUTH_ENABLED=true` iken kabul eder:

| Kullanıcı | E-posta | UI rolü | UUID |
|---|---|---|---|
| Ayşe Hoca | `ayse@dogus.edu.tr` | instructor | `11111111-1111-1111-1111-111111111111` |
| Burak Yılmaz | `burak@dogus.edu.tr` | student | `22222222-2222-2222-2222-222222222222` |

- UUID'ler `supabase/seed_demo.sql` ile `apps/web/app/page.tsx` arasında
  eşleşmelidir; biri değişirse ikisi birlikte değiştirilir (seed dosyasındaki not).
- `profiles` tablosunda sistem geneli rol sütunu yoktur; yetki daima ders
  bazlıdır (`course_memberships.role`). Ayşe'nin eğitmenliği ders
  oluşturduğunda üyelik rolü olarak doğar; karttaki "instructor" UI etiketidir.

Duman testi: Ayşe ile gir → ders oluştur → materyal yükle (PDF/PPTX/MD/kod;
20 MB sınırı) → ingestion durumunun `completed`'a dönmesini izle.

## 6.1 Asistandan gerçek cevap almak — `fastembed`'e geçiş

Varsayılan `EMBEDDING_PROVIDER=hashing` ile sistem eksiksiz ayağa kalkar, materyal
işlenir, testler geçer. **Ama asistan işe yarar cevap veremez.** Sebebi ölçüldü
(9 Ağustos, gerçek ders materyali üzerinde):

| Sağlayıcı | İlgili sorgu skoru | Konu dışı sorgu skoru | Ayırıyor mu |
|---|---|---|---|
| `hashing` | 0,1715 – 0,1951 | **0,1789** | **Hayır** — konu dışı sorgu, ilgili sorgulardan birinden yüksek skor aldı |
| `fastembed` (e5) | 0,8130 – 0,8699 | 0,7238 – 0,7587 | **Evet**, temiz aralıkla |

`hashing` sözcük örtüşmesine dayanır; eş anlamlıyı ve anlamı yakalamaz. Test ve
çevrimdışı geliştirme içindir. **Demo, ölçüm ve gerçek kullanım `fastembed` ister.**

```bash
# 1) Modeli kalıcı bir dizine indir (2,1 GB, tek seferlik)
export EMBEDDING_CACHE_DIR="$HOME/.cache/dou-synapse/fastembed"
mkdir -p "$EMBEDDING_CACHE_DIR"
cd apps/api && uv run python -c "
from fastembed import TextEmbedding; import os
TextEmbedding(model_name='intfloat/multilingual-e5-large',
              cache_dir=os.environ['EMBEDDING_CACHE_DIR']); print('hazır')"

# 2) .env'e iki satır
#    EMBEDDING_PROVIDER=fastembed
#    EMBEDDING_CACHE_DIR=/Users/<siz>/.cache/dou-synapse/fastembed
```

**Sağlayıcı değişimi geriye dönük değildir.** `hashing` ile işlenmiş parçalar başka bir
vektör uzayındadır; sağlayıcıyı değiştirdikten sonra **materyalleri silip yeniden
yükleyin.** Aksi hâlde arama sessizce alakasız sonuçlar döndürür — hiçbir hata almazsınız.

Ölçülen süreler (`fastembed`, yerel):

| | |
|---|---|
| İlk soru (2,1 GB model belleğe yükleniyor) | **11,7 sn** |
| İkinci soru (sıcak) | **0,08 sn** |
| İlk materyal yükleme (model yükleme dahil) | **19,1 sn** |
| Sonraki yüklemeler | 2,1 – 6,7 sn |

**Doğrulama** — kaynaklı bir cevap gelmeli (`"status":"answered"` + dolu `citations`):

```bash
curl -s -X POST "http://localhost:8000/courses/<COURSE_ID>/chat" \
  -H "Authorization: Bearer dev:22222222-2222-2222-2222-222222222222" \
  -H "Content-Type: application/json" \
  -d '{"question":"Semafor nedir?","mode":"qa"}'
```

**LLM anahtarı yoksa** sistem deterministik sahte sağlayıcıya düşer (logda
`llm anahtarı yok — deterministik sahte sağlayıcıya düşülüyor`). Atıflar yine gerçek
parçalara bağlıdır ve guardrail zinciri aynen koşar; yalnız cevabın düzyazısını model
yazmaz. **Soru üretimi bu modda çalışmaz** (0 soru döner) — gerçek anahtar ister.

## 7. Sorun giderme

| Belirti | Neden / çözüm |
|---|---|
| `createdb: command not found` | postgresql@16 keg-only — PATH satırını uygulayın (§1) |
| Migration'da `extension "vector" is not available` | pgvector yanlış `pg_config` ile derlendi; §1'deki derlemeyi 16'nın `pg_config`'iyle tekrarlayın |
| API açılışta `SUPABASE_JWT_SECRET tanımlı olmalı ya da DEV_AUTH_ENABLED açılmalı` | `.env` kopyalanmamış ya da `DEV_AUTH_ENABLED` kapalı |
| `password authentication failed for user "dou_app"` | `supabase/local_dev_setup.sql` çalıştırılmamış |
| `pytest`'te `psql` bulunamıyor / bağlanamıyor | `PG_BIN`'i kendi kurulumunuza göre ayarlayın; Postgres servisi ayakta olmalı |
| Compose ile yerel Postgres aynı anda | İkisi de 5432'yi dinler — birini durdurun (`brew services stop postgresql@16` veya `docker compose down`) |
| **Her soruya "materyalde dayanak bulamadım" cevabı** | Büyük olasılıkla `EMBEDDING_PROVIDER=hashing` — §6.1. Ya da materyal `Hazır` değil |
| **Cevaplar alakasız parçalara atıf yapıyor** | Sağlayıcı değiştirildi ama korpus yeniden işlenmedi. Materyalleri silip yeniden yükleyin (§6.1) |
| **Eğitmen analitiği boş / ret oranı hep %0** | `0005_analytics.sql` uygulanmamış olabilir: `psql -d dou_synapse -tAc "select polname from pg_policy p join pg_class c on c.oid=p.polrelid where c.relname='request_logs'"` — iki politika görmelisiniz. (Oranın %0 görünmesinin ayrı ve bilinen bir sebebi daha var: [ARCHITECTURE §5](../../ARCHITECTURE.md#5-sorgu-pipelineı-ve-guardrail-zinciri)) |
| **Tarayıcıdan istek CORS'a takılıyor** | Frontend'i 3000/3100 dışında bir portta çalıştırıyorsunuz; portu `CORS_ORIGINS`'e ekleyin |
| **"0 soru üretildi"** | Soru üretimi gerçek LLM anahtarı ister; sahte sağlayıcının soru şeması yok |
| İlk soru çok uzun sürüyor / asılı kalıyor | Model indiriliyor olabilir (2,1 GB). `EMBEDDING_CACHE_DIR`'i kontrol edin (§6.1) |
| `bunx playwright` "two different versions" hatası | `bunx` ayrı bir kopya indirir; `node_modules/.bin/playwright` kullanın |

## 8. Alternatif: Docker Compose

Kök `docker-compose.yml` fallback/çevrimdışı-demo yığınıdır: `pgvector/pgvector:pg16`
imajlı `db` (migration'lar ilk açılışta otomatik) + `api` (port 8000,
`DEV_AUTH_ENABLED=true`). Frontend Compose'da yoktur; §5'teki gibi bun ile
çalıştırılır.

```bash
docker compose up
```

Compose yalnızca `supabase/migrations/` dizinini mount eder; demo kullanıcıları
için `seed_demo.sql`'i konteyner veritabanına host'tan ayrıca uygulayın:

```bash
psql "postgresql://postgres:postgres@localhost:5432/dou_synapse" -f supabase/seed_demo.sql
```

**Bu yığının üç sınırı vardır ve üçü de bilinçli olarak yazılıyor:**

1. **RLS bu yığında DEVREDE DEĞİLDİR.** `api` servisi veritabanına `postgres`
   (superuser) rolüyle bağlanır; superuser, tablolardaki `FORCE ROW LEVEL SECURITY`
   işaretine rağmen politikaları atlar. Yerel kurulumda (§2-3) API `dou_app` rolüyle
   bağlanır ve RLS gerçekten uygulanır. **İzolasyon kanıtı Compose yığınında alınamaz;**
   `supabase/tests/rls_isolation.sql` yerel kurulumda ya da CI'da koşturulmalıdır.
2. **LLM üretimi yapamaz** (dil modeli harici bir API'dedir). Çevrimdışı demoda cevaplar
   `answer_cache` üzerinden servis edilir; önbellek yalnız `qa` modunda ve **birebir
   metin eşleşmesiyle** çalışır. Soru üretimi bu yığında hiç çalışmaz.
3. **Embedding modeli imaja gömülü değildir.** İlk kullanımda indirilmeye çalışılır;
   gerçekten ağsız bir kurulumda model önceden konteynerde bulunmalıdır.

Üçü de kayıt altındadır: [ARCHITECTURE.md §10](../../ARCHITECTURE.md#10-uygulanmayanlar--tasarlandı-kodda-yok).
