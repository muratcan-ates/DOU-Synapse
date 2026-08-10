# Quickstart: 003 Rol Bazlı Ürün Portalı

Bu belge sıfırdan kurulumun yerine geçmez. Temel PostgreSQL, `uv`, Bun ve demo
verisi için önce
[`../001-course-assistant-mvp/quickstart.md`](../001-course-assistant-mvp/quickstart.md),
002'nin production kapıları için de
[`../002-production-hardening/quickstart.md`](../002-production-hardening/quickstart.md)
izlenmelidir. Buradaki amaç yalnız 003 portalının doğru dalda, ayrı test verisiyle
ve dürüst kanıt statüsüyle doğrulanmasıdır.

> **Güncel durum (2026-08-10)**: Profil, dashboard ve Bilgi İşlem yüzeyleri
> hedefli/tam testler, RLS mutasyonu, generated OpenAPI, production build ve
> koşu kimlikli tarayıcı yolculuklarıyla **yerelde doğrulandı**. Gerçek
> Auth/Storage/LLM, telemetry, yük, restore ve canlı URL kanıtı olmadığı için
> **production'da kanıtlandı** değildir.

---

## 1. Doğru ağaç ve migration sırası

```bash
cd /Users/muratates/code/dou-product-portal
git branch --show-current       # 003-product-portal
git merge-base HEAD 3b707ca     # tam olarak 3b707ca dönmeli
git status --short
```

Migration sırası bilinçlidir:

- `0013_chat_feedback.sql`: entegrasyonda gelecek kalite döngüsüne rezerve.
- `0014_platform_admin_console.sql`: bu feature'ın platform admin migration'ı.

İki migration aynı numarayla yaratılmamalı ve `0014`, `0013` alınmadan production'a
tek başına uygulanmamalıdır. Uygulamadan önce staging migration manifest'i
entegrasyon commit'inde yeniden kontrol edilir.

### Paralel test uyarısı

Backend fixture'ı test veritabanını düşürüp yeniden kurar. Başka sohbet veya
worktree ile aynı `TEST_DB_NAME` kullanılırsa koşular birbirinin verisini bozabilir.
Bu feature için ayrı ve açık bir ad verin:

```bash
cd apps/api
TEST_DB_NAME=dou_synapse_test_product_portal uv run pytest tests/test_portal.py -q
```

Paylaşılan geliştirme veya production veritabanını test adına vermeyin.

---

## 2. Bağımlılık ve statik kapılar

```bash
cd /Users/muratates/code/dou-product-portal/apps/api
uv sync --extra dev
uv run ruff check .
uv run ruff format --check .
uv run mypy app

cd ../web
bun install
bun test lib/profile.test.ts lib/dashboard.test.ts lib/admin.test.ts
bun run typecheck
bun run build
```

Bu komutların geçmesi runtime yetkisini veya production bağlantılarını kanıtlamaz.
Test toplamı bu dosyaya elle yazılmaz; repo genelindeki canlı sayı yalnız
`node scripts/docs_check.mjs --metrikler` çıktısından alınır.

---

## 3. Migration ve RLS doğrulaması

Temiz, feature'a özel bir veritabanında bütün migration'lar sırayla uygulanır:

```bash
createdb dou_synapse_rls_portal_003
for f in supabase/migrations/*.sql; do
  psql -q -v ON_ERROR_STOP=1 -d dou_synapse_rls_portal_003 -f "$f"
done
```

Ardından aşağıdaki iddialar doğrudan DB rolüyle kanıtlanır:

1. `platform_admins` üzerinde RLS etkin, FORCE değildir.
2. PUBLIC, `dou_app` ve `dou_worker`, `platform_admins` veya
   `platform_admin_access_audit` için doğrudan tablo yetkisi taşımaz.
3. `dou_app` ile iki tabloda da doğrudan SELECT/INSERT/UPDATE/DELETE reddedilir.
4. DBA tarafından atanmamış kullanıcı için `app.is_platform_admin()` false olur.
5. DBA satırı eklediğinde admin fonksiyonları çalışır.
6. Admin satırı kaldırıldığında aynı fonksiyonlar tekrar reddedilir.
7. Admin fonksiyonlarının EXECUTE yetkisi PUBLIC'e açık değildir.
8. Platform admin, ders üyeliği olmadan akademik tablo/endpoint erişimi kazanmaz.
9. Beş admin endpoint'inde allowed ve denied kararlar request ID ile audit edilir.
10. Denied endpoint 403 döndüğünde audit satırı ana isteğin rollback'iyle kaybolmaz.

`FORCE ROW LEVEL SECURITY` bu tabloda bir hedef değildir. Politikasız tabloda FORCE,
tablo sahibinin dar `SECURITY DEFINER` yardımcısını da kör eder. Güvenlik; kapalı
grant'ler, DBA-only yazma ve her yardımcıdaki tekrar admin kontrolüdür.

İddiaların yalnız yeşil olması yetmez. Testte admin kontrolü veya REVOKE geçici
olarak etkisizleştirildiğinde ilgili negatif iddia kırmızı yanmalıdır. Mutasyon
kanıtı yoksa RLS görevi kapanmaz.

Temizlik:

```bash
dropdb dou_synapse_rls_portal_003
```

---

## 4. Yerel servisleri doğru portlarla çalıştırma

Üç ayrı terminal kullanın:

```bash
# Terminal 1 — API
cd /Users/muratates/code/dou-product-portal/apps/api
EMBEDDING_PROVIDER=fastembed \
CORS_ORIGINS='["http://localhost:3014","http://localhost:3114"]' \
uv run uvicorn app.main:app --port 8014
```

```bash
# Terminal 2 — ingestion worker
cd /Users/muratates/code/dou-product-portal/apps/api
uv run python -m app.worker
```

```bash
# Terminal 3 — web
cd /Users/muratates/code/dou-product-portal/apps/web
NEXT_PUBLIC_API_URL=http://localhost:8014 bun run dev --port 3014
```

Başka bir worktree'nin `:8000`/`:3000` sunucusuna yanlışlıkla bağlanmamak için
portlar açıkça verilir. İlk kontrol:

```bash
curl -s http://localhost:8014/health/live
curl -s http://localhost:8014/health/ready
curl -s http://localhost:8014/openapi.json
```

OpenAPI'de en az şu yollar görülmelidir:

- `/me/profile`
- `/dashboard`
- `/admin/overview`
- `/admin/users`
- `/admin/courses`
- `/admin/requests`
- `/admin/ingestion`

---

## 5. API kabul akışları

Aşağıdaki örnekler yerel `dev:` kimliğinin açık olduğu geliştirme ortamı içindir.
Production'da dev kimliği kapalı olmalıdır.

```bash
API=http://localhost:8014
USER_TOKEN='Authorization: Bearer dev:22222222-2222-2222-2222-222222222222'
INSTRUCTOR_TOKEN='Authorization: Bearer dev:11111111-1111-1111-1111-111111111111'
```

### 5.1 Profil

```bash
curl -s "$API/me/profile" -H "$USER_TOKEN"
curl -s -X PATCH "$API/me/profile" -H "$USER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"full_name":"Burak Yılmaz"}'
```

Kontrol:

- Yanıt yalnız kişinin kendi kimliğini ve aktif üyeliklerini taşır.
- Farklı derslerde farklı roller ayrı kalır.
- `email`, `role` veya `is_platform_admin` PATCH gövdesine eklenirse 422 gelir.
- Boş, tek karakterli veya 120 karakterden uzun ad reddedilir.
- Profil değişikliği, adminlik ya da ders rolünü değiştirmez.

### 5.2 Dashboard

```bash
curl -s "$API/dashboard" -H "$USER_TOKEN"
curl -s "$API/dashboard" -H "$INSTRUCTOR_TOKEN"
```

Kontrol:

- Her kart kendi ders üyeliği rolünü taşır.
- Eğitmen sayıları `documents_processing`, `documents_failed`, `draft_questions`
  ve `published_exams` alanlarından gelir.
- `action_items = documents_processing + documents_failed + draft_questions`.
- Taslak blueprint sayısı yoktur; frontend blueprint aracı için yalnız çalışan link verir.
- Etkin, süresi dolmamış sınavı olan öğrenci kartında `assistant_locked=true`,
  `assistant_lock_reason=exam_in_progress` ve sunucu kaynaklı Türkçe
  `assistant_lock_message` vardır; birincil eylem sınava döner.
- Süresi dolmuş/practice oturumu öğrenci kartını kilitlemez; eğitmen kartı aynı
  nedenle hiçbir zaman kilitlenmez.
- Öğrenci kartına başka öğrencinin mastery/sınav verisi düşmez.
- Ders yoksa sahte dönem, danışman, GPA veya örnek ders üretilmez.

### 5.3 Admin olmayan kullanıcı

Aşağıdaki beş isteğin tamamı 403 olmalıdır:

```bash
curl -s -o /dev/null -w '%{http_code}\n' "$API/admin/overview" -H "$USER_TOKEN"
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$API/admin/users" \
  -H "$USER_TOKEN" -H 'Content-Type: application/json' \
  -d '{"limit":25,"offset":0,"search":null}'
curl -s -o /dev/null -w '%{http_code}\n' "$API/admin/courses" -H "$USER_TOKEN"
curl -s -o /dev/null -w '%{http_code}\n' "$API/admin/ingestion" -H "$USER_TOKEN"
```

Yetki sonucu gelmeden frontend bu beş uca paralel ön istek atmamalıdır.

### 5.4 Platform admin

İlk admin yalnız DBA/operatör tarafından eklenir; uygulamada atama API'si yoktur.
Atama yapıldıktan sonra güvenli bir admin token'ıyla:

```bash
curl -s "$API/admin/overview" -H "$ADMIN_TOKEN"
curl -s -X POST "$API/admin/users" -H "$ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"limit":25,"offset":0,"search":"Ayşe"}'
curl -s "$API/admin/courses?search=COME&limit=25&offset=0" -H "$ADMIN_TOKEN"
curl -s "$API/admin/requests?status=answered&limit=25&offset=0" -H "$ADMIN_TOKEN"
curl -s "$API/admin/ingestion?status=failed&limit=25&offset=0" -H "$ADMIN_TOKEN"
```

Kontrol:

- Kullanıcı araması `full_name` veya SQL tarafında üretilen maskelenmiş e-posta
  ifadesi içindir; UI placeholder'ı `Ad veya maskeli e-posta` olur.
- Tam e-posta araması eşleşmez; kullanıcı araması yalnız POST JSON gövdesindedir,
  URL/query parametresine yazılmaz. Response yalnız `masked_email` taşır.
- Request item'ında prompt, cevap, kullanıcı UUID/e-posta/hash/pseudonym'i yoktur.
- Ingestion item'ında `file_name`, path, `last_error`, belge veya chunk metni yoktur.
- Limit 101 reddedilir; negatif offset reddedilir.
- Platform admin, üyesi olmadığı bir `/courses/{course_id}` akademik ucunda hâlâ
  course isolation hatası görür.

---

## 6. Tarayıcı kabul yolculukları

`http://localhost:3014` üzerinde aşağıdaki yolculukların her biri gerçek API
yanıtıyla gözlenir. Ekran görüntüsü tek başına kanıt değildir; ağ ve konsol da izlenir.

### Öğrenci

1. Girişten sonra `/dashboard` açılır.
2. Yalnız aktif dersler ve gerçek çalışma girişleri görünür.
3. Ders kartından Asistan, Sınav ve İlerleme hedefleri çalışır.
4. Yürüyen sınavda sohbet kilidi mevcut sunucu sözleşmesiyle tutarlı kalır.
5. Profilde kendi e-posta, ad ve ders rolleri görünür; veri hakkı `/account`a gider.

### Eğitmen

1. Dashboard başarısız/işlenen belge ile taslak soru sayılarını ayırır.
2. Kaynaklar, sorular, blueprint, sınavlar, AI politikası ve analitik linkleri çalışır.
3. Blueprint linki vardır; uydurma “taslak blueprint sayısı” yoktur.
4. Öğrenci sohbet/cevap metni dashboard'a veya admin konsoluna sızmaz.

### Karma rol

1. Aynı hesap A dersinde eğitmen, B dersinde öğrenci olarak görünür.
2. Her ders ekranında rol `useSession(courseId)` ile çözülür.
3. Özellikle blueprint sayfasında courseId'siz session kullanımına izin verilmez.

### Platform admin ve admin olmayan

1. Profil sonucunda adminlik false iken admin linki görünmez ve `/admin` reddedilir.
2. Adminlik true iken overview ve dört liste, gate tamamlandıktan sonra yüklenir.
3. Sağlık “uygulama, DB, embedding” olarak ayrıdır; tek yanıltıcı yeşil rozet yoktur.
4. Ham log, stack trace, prompt, cevap veya dosya adı görünmez.
5. İzin verilen ve reddedilen admin erişimleri audit edilir; audit tablosu UI'da
   ayrı bir ham kayıt sekmesi olarak açılmaz.

### Erişilebilirlik ve ağ

- 375 px ve masaüstü görünümünde yatay sayfa taşması yok.
- Koyu tema okunur; durum yalnız renk ile anlatılmaz.
- Klavyeyle bütün link, filtre ve sayfalama kontrollerine gidilebilir.
- Görünür odak vardır; başlık sırası mantıklıdır.
- Aynı ekranda `/me/profile` yalnız bir kez çekilir.
- Bekleme, boş, kısmi hata ve tam hata durumları birbirinden ayrılır.
- Konsolda hydration veya React key hatası yoktur.

Playwright için ayrı portları açıkça verin:

```bash
cd apps/web
E2E_API_URL=http://localhost:8014 \
E2E_DATABASE_NAME=dou_synapse_e2e_product_portal \
E2E_PORT=3114 \
node_modules/.bin/playwright test
```

Bu DB ayrı ve disposable olmalıdır. Playwright `globalSetup` ile koşu kimliğini
üretir; `globalTeardown` yalnız o koşunun `E2E-<run>-<number>` dersleriyle
`e2e-<run>-...` Bilgi İşlem audit kayıtlarını temizler. `COME 331` ve korunan demo
UUID'si cleanup kapsamı dışındadır. Ürün API'sinde ders silme ucu bu amaçla yoktur.

---

## 7. Sözleşme ve belge kapıları

```bash
cd /Users/muratates/code/dou-product-portal
node scripts/docs_check.mjs
node scripts/docs_check.mjs --metrikler
```

OpenAPI export, aynı commit'teki çalışan API'den alınır; elle yazılmış JSON kaynak
sayılmaz. Frontend tipleriyle alan/ad karşılaştırması yapılır. Özellikle:

- yollar `/admin/requests` ve `/admin/ingestion` olmalı,
- ingestion yanıtında `file_name` olmamalı,
- kullanıcı araması `POST /admin/users` JSON gövdesinde yalnız `full_name` ve
  maskelenmiş e-posta ifadesiyle eşleşmeli; URL'de search olmamalı ve tam e-posta
  araması eşleşmemeli,
- dashboard'da taslak blueprint sayacı olmamalı,
- dashboard course şemasında `assistant_locked`, `assistant_lock_reason` ve
  `assistant_lock_message` alanları bulunmalı,
- migration adı `0014_platform_admin_console.sql` olmalı.

---

## 8. Production kanıtı — yerelde taklit edilemez

Aşağıdakiler dış erişim ve gerçek ortam gerektirir; gerçekleştirilmeden
**KOŞULMADI** yazılır:

- gerçek Supabase Auth kullanıcıları ve MFA'lı yönetici işlemi,
- Supabase Storage upload/worker akışı,
- gerçek Groq/Gemini ile grounded sohbet, grading ve soru üretimi,
- OpenTelemetry exporter, dashboard ve alarm bildirimi,
- Vercel web + ACA API/worker staging smoke,
- yük testi ve belirlenmiş p95/p99/SLO sonucu,
- backup/PITR ve geri yükleme tatbikatı,
- gerçek kullanıcı/öğretmen insan değerlendirmesi,
- production URL üzerinde öğrenci/eğitmen/admin yolculukları.

### Teslim kayıt tablosu

| Kapı | Durum | Kanıt bağlantısı/commit |
|---|---|---|
| Kod repo ağacında | Kodlandı | `fa659d1`, `77cf35e`, `68f8b54`, `9c2fe23` |
| Hedefli API/RLS | Yerelde doğrulandı | T601/T603 |
| Frontend test/build | Yerelde doğrulandı | T605 |
| Generated OpenAPI | Yerelde doğrulandı | T606 |
| Gerçek HTTP + tarayıcı | Yerelde doğrulandı | T607/T608 |
| Staging Auth/Storage/LLM | KOŞULMADI | — |
| Load + backup/restore | KOŞULMADI | — |
| İnsan eval | KOŞULMADI | — |
| Production smoke | KOŞULMADI | — |

Bu tablo kanıt geldikçe aynı release commit'inde güncellenir; “kodlandı” hiçbir
satırda “production hazır” anlamına gelmez.
