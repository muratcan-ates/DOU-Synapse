# Quickstart — Sıfırdan Yerel Kurulum

Bu belge, DOU-Synapse'i temiz bir macOS makinede (Homebrew ile) sıfırdan ayağa
kaldırır: PostgreSQL 16 + pgvector, şema + seed, FastAPI backend'i, testler ve
Next.js frontend'i. Tüm komutlar repo kökünden (`~/code/DOU-Synapse`) verilmiştir.

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

## 2. Veritabanı: oluştur → migrate → yerel roller → seed

Sıra önemlidir: migration `dou_app`/`dou_worker` rollerini **NOLOGIN** oluşturur;
`local_dev_setup.sql` bu rollere yalnızca yerelde giriş açar; seed demo
kullanıcılarını yazar.

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

# 3) Demo kullanıcıları (Ayşe + Burak, sabit UUID'ler)
psql -d dou_synapse -f supabase/seed_demo.sql
```

Notlar:

- Bu komutları Homebrew'un varsayılan (superuser) kullanıcınızla çalıştırın;
  seed RLS'i bu sayede atlar. **Uygulama asla superuser ile bağlanmaz** — API
  `dou_app` (RLS'e tabi), worker `dou_worker` (BYPASSRLS) rolünü kullanır.
- `local_dev_setup.sql` ve `seed_demo.sql` üretimde/demoda ÇALIŞTIRILMAZ
  (dosya başlıklarındaki uyarılar).
- İsteğe bağlı RLS kanıtı (tümü PASS dönmeli, sonunda ROLLBACK yapar):

```bash
psql -d dou_synapse -f supabase/tests/rls_isolation.sql
```

## 3. Backend (apps/api): uv kurulumu + .env

```bash
cd apps/api
uv venv --python 3.12          # pyproject: >=3.12,<3.13 (onnxruntime/fastembed pini)
uv pip install -e ".[dev]"
cp ../../.env.example .env
```

`.env.example`'ın varsayılanları yerel kurulumla birebir eşleşir; **hiçbir değeri
değiştirmeden** çalışır:

| Değişken | Varsayılan | Anlamı |
|---|---|---|
| `ENVIRONMENT` | `local` | — |
| `DATABASE_URL` | `postgresql+psycopg://dou_app:dou_app_local@localhost:5432/dou_synapse` | API, RLS'e tabi `dou_app` rolüyle |
| `WORKER_DATABASE_URL` | `postgresql+psycopg://dou_worker:dou_worker_local@localhost:5432/dou_synapse` | Worker, `chunks` yazabilen ayrı rolle |
| `SUPABASE_JWT_SECRET` | (boş) | `DEV_AUTH_ENABLED=true` iken gerekmez |
| `DEV_AUTH_ENABLED` | `true` | İmzasız `Bearer dev:<uuid>` kimlikleri kabul edilir. `ENVIRONMENT=production` iken açılırsa uygulama **başlamaz** (`app/core/config.py` doğrulayıcısı) |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Frontend origin'i |
| `EMBEDDING_PROVIDER` | `hashing` | Deterministik yerel embedding — model indirmeden çevrimdışı geliştirme. `fastembed`'e geçiş **ingest-zamanı kararıdır**: tüm korpus yeniden işlenir |

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
uv run pytest
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

## 7. Sorun giderme

| Belirti | Neden / çözüm |
|---|---|
| `createdb: command not found` | postgresql@16 keg-only — PATH satırını uygulayın (§1) |
| Migration'da `extension "vector" is not available` | pgvector yanlış `pg_config` ile derlendi; §1'deki derlemeyi 16'nın `pg_config`'iyle tekrarlayın |
| API açılışta `SUPABASE_JWT_SECRET tanımlı olmalı ya da DEV_AUTH_ENABLED açılmalı` | `.env` kopyalanmamış ya da `DEV_AUTH_ENABLED` kapalı |
| `password authentication failed for user "dou_app"` | `supabase/local_dev_setup.sql` çalıştırılmamış |
| `pytest`'te `psql` bulunamıyor / bağlanamıyor | `PG_BIN`'i kendi kurulumunuza göre ayarlayın; Postgres servisi ayakta olmalı |
| Compose ile yerel Postgres aynı anda | İkisi de 5432'yi dinler — birini durdurun (`brew services stop postgresql@16` veya `docker compose down`) |

## 8. Alternatif: Docker Compose

Kök `docker-compose.yml` fallback/çevrimdışı-demo yığınıdır: `pgvector/pgvector:pg16`
imajlı `db` (migration'lar ilk açılışta otomatik) + `api` (port 8000,
`DEV_AUTH_ENABLED=true`). Frontend Compose'da yoktur; §5'teki gibi bun ile
çalıştırılır.

```bash
docker compose up
```

Sınır: bu yığın internet olmadan çalışır ama LLM üretimi yapamaz; çevrimdışı
demoda cevaplar `answer_cache` üzerinden servis edilir (dosya başındaki not).
Compose yalnızca `supabase/migrations/` dizinini mount eder; demo kullanıcıları
için `seed_demo.sql`'i konteyner veritabanına host'tan ayrıca uygulayın:

```bash
psql "postgresql://postgres:postgres@localhost:5432/dou_synapse" -f supabase/seed_demo.sql
```
