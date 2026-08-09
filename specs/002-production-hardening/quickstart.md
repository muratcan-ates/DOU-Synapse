# Quickstart — 002 Production Sertleştirme

Bu belge **001'in quickstart'ının yerine geçmez, üstüne biner.** Sistemi sıfırdan kurmak
için önce [`specs/001-course-assistant-mvp/quickstart.md`](../001-course-assistant-mvp/quickstart.md)
§0–§5'i uygulayın (Postgres 16 + pgvector, migration döngüsü, `uv`, `bun`). Burada anlatılan
şey farklı: **002 üzerinde çalışan birinin sistemi doğru portlarla ayağa kaldırması, hangi
testin neyi kanıtladığını bilmesi ve 002'nin her User Story'sini elle doğrulayabilmesi.**

> **Bu belgedeki doğrulamaların ÇOĞU bugün BAŞARISIZ olmalıdır.** 002 henüz koda inmedi:
> `002-production-hardening` dalında `specs/002-production-hardening/` dışında hiçbir dosya
> değişmiş değil (`git status`). Her doğrulama adımının yanında iki sütun var — **bugünkü
> sonuç** ve **002 bitince beklenen sonuç.** İkisi bugün aynı çıkıyorsa ya iş çoktan
> yapılmıştır ya da doğrulama yanlış yerden bakıyordur; ikincisi çok daha olasıdır ve
> 001'in devir belgesinin "sessiz kusur sınıfı" dediği şeyin tam olarak kendisidir
> (`docs/team/parallel/20_DEVIR_9_AGUSTOS.md:128-147`).

> **Bu belgede ölçülen sayılar (9 Ağustos 2026, bu ağaçta koşuldu):**
> `cd apps/api && uv run pytest -q` → **664 passed, 75,48 sn.**
> `cd apps/web && bun test lib/` → **211 pass, 0 fail, 8 dosya.**
> Bunların dışındaki her sayı ya bir dosyadan alıntıdır ya da **KOŞULMADI** yazar
> (Anayasa III).

---

## 0. Bugün nerede duruyoruz — hangi hikâye kodda var, hangisi yok

Bu tablo doğrulamaların çıkış noktasıdır. "Yok" yazan bir satırın doğrulaması bugün
**kırmızı yanmalıdır**; yanmıyorsa doğrulama yanlış yazılmıştır.

| # | Hikâye | Bugün kodda | Kanıt | Doğrulama |
|---|---|---|---|---|
| US1 | Sınav oturumu → asistan kilidi | **YOK** | `app/api/chat.py:561-567` `CourseMemberDep` alıyor; sınav durumuna bakan tek satır yok | [§4.1](#41-us1--sınav-oturumu-kilidi-002nin-birinci-işi) |
| US2 | Event loop bloklanması | **YOK** | `asyncio.to_thread` yalnız `app/modules/ingestion/storage.py:50,55,61`'de — ayrıştırma ve embedding hâlâ döngüde | [§4.2](#42-us2--bilinen-üç-production-kusuru) |
| US2 | Isıtma (warmup) | **YOK** | `app/main.py` `lifespan`'inde model dokunuşu yok | [§4.2](#42-us2--bilinen-üç-production-kusuru) |
| US2 | Soru üretimi kotası | **YOK** | `app/api/questions.py:154-200` — `_rate_limiter` çağrısı yok (karşılaştırın: `app/api/chat.py:589-594`) | [§4.2](#42-us2--bilinen-üç-production-kusuru) |
| US2 | Issuer ortam değişkeni adı | **UYUŞMUYOR** | `.env.example:25` `SUPABASE_JWT_ISSUER` yazıyor; `app/core/config.py:100` alanı `jwt_issuer`, yani `JWT_ISSUER` okuyor; `config.py:73` `extra="ignore"` fazlalığı sessizce yutuyor | [§4.2](#42-us2--bilinen-üç-production-kusuru) |
| US3 | Sınav blueprint'i | **YOK** | `supabase/migrations/` `0007`'de bitiyor; `exam_blueprints` diye bir tablo yok | [§4.3](#43-us3--sınav-blueprinti) |
| US4 | Ders bazlı AI politikası | **YOK** | Eşik global: `app/core/config.py` `evidence_threshold`; mod seçimi istemcide (`ChatRequest.mode`) | [§4.4](#44-us4--ders-bazlı-ai-politikası) |
| US5 | Timeout / retry / istek kimliği | **KISMİ** | `X-Request-ID` **başlıkta** var (`app/main.py:63,66`), hata **gövdesinde** yok (`app/core/errors.py:57-62`); `apps/web/lib/api.ts` içinde `AbortSignal` yok | [§4.5](#45-us5--güvenilirlik-ux) |
| US6 | Sayfalama | **YOK** | `app/api/courses.py:30`, `chat.py:701` — `limit`/`cursor` parametresi yok | [§4.6](#46-us6--sayfalama) |
| US7 | Gerçek kimlik (frontend ayağı) | **KISMİ** | Backend hazır (`0002`, `app/core/security.py`); arayüz hâlâ `Bearer dev:<uuid>` kartı | [§4.7](#47-us7--gerçek-kimlik) |
| US8 | Belge doğruluğu | **AÇIK** | Bu belgenin kendisi bir örnek buldu: 001 quickstart:195 "479 test" diyor, bugün ölçülen **664** | [§4.8](#48-us8--belge-doğruluğu) |
| US9–11 | Veri hijyeni, KVKK hakları, güvenlik başlıkları | **YOK** | `app/main.py:40-100` içinde güvenlik başlığı middleware'i yok | [§4.9](#49-us9-us10-us11) |

---

## 1. İlk iş: doğru ağaç, doğru portlar

### 1.1 Doğru ağaç

```bash
cd ~/code/dou-lead
git branch --show-current      # "002-production-hardening" yazmalı
```

`~/code/DOU-Synapse` klasörüne **dokunmayın** — orada eski bir oturum ağacı var
(`docs/team/parallel/20_DEVIR_9_AGUSTOS.md:19`).

### 1.2 PORT TUZAĞI — bu makinede gerçek bir tuzak

`:8000`'de **başka bir ağacın eski API'si** koşuyor olabilir ve o sunucu eski sözleşmeyi
konuşur. `apps/web/lib/api.ts:9` varsayılanı `http://localhost:8000` olduğu için portu
açıkça vermezseniz tarayıcı yanlış sunucuya gider ve **her sohbet isteği 422 döner** —
ürün hatası gibi görünen bir kurulum hatası
(`docs/team/parallel/20_DEVIR_9_AGUSTOS.md:21-26`).

**Çalışan tam komut — üç terminal:**

```bash
# terminal 1 — API (:8010)
cd ~/code/dou-lead/apps/api && \
  EMBEDDING_PROVIDER=fastembed \
  CORS_ORIGINS='["http://localhost:3000","http://localhost:3010","http://localhost:3100"]' \
  uv run uvicorn app.main:app --port 8010

# terminal 2 — worker
cd ~/code/dou-lead/apps/api && uv run python -m app.worker

# terminal 3 — web (:3010)
cd ~/code/dou-lead/apps/web && \
  NEXT_PUBLIC_API_URL=http://localhost:8010 bun run dev --port 3010
```

**Üç şey birden gerekli ve devir belgesi üçünün de birer kez unutulduğunu yazıyor**
(`20_DEVIR_9_AGUSTOS.md:45-53`):

1. **`EMBEDDING_PROVIDER=fastembed`** — paylaşılan `dou_synapse` korpusu E5 uzayında
   gömülü. `hashing` ile sorgularsanız sistem **çökmez, sessizce alakasız sonuç döner**
   ve "retrieval kötü" diye okunur. Varsayılan `hashing`'dir
   (`app/core/config.py:138`) ve bu bilinçlidir: testler 2 GB model indirmemeli
   (`.env.example`'daki gerekçe). Sunucuyu paylaşılan korpusa karşı koştururken
   sağlayıcıyı **her seferinde açıkça verin.**
2. **`CORS_ORIGINS`'e 3100** — Playwright kendi sunucusunu orada açıyor
   (`apps/web/playwright.config.ts`: `PORT = E2E_PORT ?? 3100`). Kod varsayılanı yalnız
   `3000` ve `3100`'ü içerir (`app/core/config.py:113`); **3010'da dev sunucusu
   koşturuyorsanız onu da eklemek zorundasınız**, yoksa tarayıcı istekleri CORS'a takılır
   ve uçtan uca koşuları "Bağlantı kurulamadı" gösterir.
3. **`bunx playwright` KULLANMAYIN** — ayrı bir kopya indirir ve "two different versions"
   hatası verir. Doğrusu `node_modules/.bin/playwright`.

**Uçtan uca koşarken API portunu da açıkça verin** — `playwright.config.ts`'in varsayılanı
`E2E_API_URL ?? "http://localhost:8000"`, yani port tuzağının tam ortasına düşer:

```bash
cd ~/code/dou-lead/apps/web && \
  E2E_API_URL=http://localhost:8010 node_modules/.bin/playwright test
```

### 1.3 "Doğru sunucuya mı bağlandım?" — 10 saniyelik kontrol

```bash
curl -s http://localhost:8010/health/live
curl -s http://localhost:8010/health/ready      # veritabanı erişimi dahil
curl -s http://localhost:8010/openapi.json | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(len(d['paths']),'yol')"
```

Üçüncü komut **25 yol** demiyorsa ya eski bir ağacın sunucusundasınız ya da 002 yeni uç
eklemiştir (`20_DEVIR_9_AGUSTOS.md:68`: OpenAPI kodla birebir, 25 yol). US1'in
`GET /courses/{course_id}/chat/availability` ucu eklendiğinde bu sayı **26** olur; ilk
gördüğünüz artış budur.

---

## 2. Testler — hangisi neyi kanıtlıyor

```bash
cd apps/api
uv run pytest -q        # 664 passed, ~75 sn (9 Ağustos'ta bu ağaçta ölçüldü)
uv run mypy app
uv run ruff check . && uv run ruff format --check .

cd ../web
bun test lib/           # 211 pass, ~0,2 sn
bun run typecheck
```

Test veritabanı her koşuda `dou_synapse_test` adıyla **düşürülüp sıfırdan kurulur**
(`apps/api/tests/conftest.py`); geliştirme veritabanınıza dokunmaz. Testler kasıtlı olarak
`dou_app` rolüyle bağlanır — superuser ile koşan bir izolasyon testi hiçbir şey kanıtlamaz
(Anayasa II).

| Dosya / komut | Neyi kanıtlar | Neyi kanıtlamaz |
|---|---|---|
| `tests/test_exams.py` (35 test) | Sınav oturumu yaşam döngüsü: süre kırpması, ipucu kapalılığı, tek deneme, bitirme | **Sınav sürerken sohbetin kapandığını kanıtlamaz** — bu 002'nin yazacağı testtir |
| `tests/test_chat_api.py` (35 test) | Sohbet hattı, `mode=exam` reddi (`chat.py:582-588`), hız sınırı, abstention | Aynı şekilde: sınav *durumuna* bakan hiçbir iddia yok |
| `tests/test_isolation_layers.py` (8 test) | İki katmanın **ayrı ayrı** çalıştığı: RLS bilerek kapatılıp uygulama katmanının tek başına tuttuğu ölçülüyor (`test_isolation_layers.py:30-75`) | Ders içi yetki ayrımını (öğrenci/eğitmen) değil, ders sınırını ölçer |
| `tests/test_security.py` (25 test) | JWT sertleştirmesi: `exp`/`aud`/`iss`/`sub` zorunlu, `alg=none` reddi, üretimde `dev:` yasağı | **Ortam değişkeni ADININ doğru olduğunu kanıtlamaz** — FR-224/SC-015 tam olarak bu boşluk |
| `supabase/tests/rls_isolation.sql` | Çekirdek şema RLS politikaları; dosyada **26 farklı iddia adı** geçiyor, koşu sonunda `ROLLBACK` yapar | Sürüm/kimlik katmanını değil, satır görünürlüğünü ölçer |
| `supabase/tests/rls_assessment.sql` | Assessment şeması politikaları; **14 farklı iddia adı** | — |
| `supabase/tests/rls_isolation_mutation_check.sh` | Yukarıdaki testin **kırılabildiğini**: politikaları ve dört yardımcı fonksiyonu teker teker bozup **beklenen iddianın** FAIL'e döndüğünü doğrular | — |

**Sayı yazmayın, FAIL arayın.** 001 quickstart:86 ve :120 `rls_isolation.sql` için "8 PASS"
diyor; bugünkü dosyada 26 farklı iddia adı var. Bu, US8'in tarif ettiği bayatlığın canlı
örneğidir. Koşuyu şöyle değerlendirin:

```bash
createdb dou_synapse_rls
for f in supabase/migrations/*.sql; do psql -q -v ON_ERROR_STOP=1 -d dou_synapse_rls -f "$f"; done
psql -d dou_synapse_rls -f supabase/tests/rls_isolation.sql 2>&1 | grep -c FAIL   # 0 olmalı
dropdb dou_synapse_rls
```

Testi **seed'den önce ya da temiz bir veritabanında** koşturun: sabit kimlikleri
(`11111111-…`, `22222222-…`) `seed_demo.sql` ile aynıdır ve seed'den sonra
`duplicate key … profiles_pkey` ile düşer. Bu bir izolasyon hatası değil, kurulum
çakışmasıdır (001 quickstart §2).

**Bir testin geçmesi, ancak kırılabildiği gösterildiğinde bir şey söyler.** Devir belgesi
bunu kendi FTS nöbetçisinde iki kez öğrendi (`20_DEVIR_9_AGUSTOS.md:140`). 002'nin FR-106
maddesi aynı kuralı sınav kilidine dayatıyor.

---

## 3. Demo kullanıcıları ve ön koşullar

| Kullanıcı | UUID | Token |
|---|---|---|
| Ayşe Hoca (eğitmen) | `11111111-1111-1111-1111-111111111111` | `Bearer dev:11111111-1111-1111-1111-111111111111` |
| Burak Yılmaz (öğrenci) | `22222222-2222-2222-2222-222222222222` | `Bearer dev:22222222-2222-2222-2222-222222222222` |

`DEV_AUTH_ENABLED=true` iken imzasız `dev:<uuid>` kabul edilir; `ENVIRONMENT=production`
iken bu ayar uygulamayı **başlatmaz** (`app/core/config.py:105` + doğrulayıcı).

Kolaylık için:

```bash
API=http://localhost:8010
OGR="Authorization: Bearer dev:22222222-2222-2222-2222-222222222222"
HOC="Authorization: Bearer dev:11111111-1111-1111-1111-111111111111"
CID=$(curl -s "$API/courses" -H "$OGR" | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['id'])")
echo "$CID"
```

### Kaçınılmaz ön koşul: onaylı soru havuzu

`POST /courses/{id}/exams` onaylı havuz boşsa oturum **açmaz** ve 409 döner:
"Bu derste henüz onaylanmış soru yok…" (`app/api/exams.py:298-302`). Gerçek LLM anahtarı
yokken soru üretimi bu ortamda sıfır soru döndürür
(`20_DEVIR_9_AGUSTOS.md:101-106`), yani **US1'i doğrulamadan önce havuzu elle
tohumlamanız gerekir.** Eğitmen token'ıyla soru üretip onaylayın ya da doğrudan
veritabanına yazın; hangisini yaptığınızı doğrulama notuna yazın.

---

## 4. User Story bazlı elle doğrulama

### 4.1 US1 — sınav oturumu kilidi (002'nin birinci işi)

FR-101…FR-106 · SC-001. **En kritik ve en kolay yanlış doğrulanan hikâye.**

#### A) İki sekmeli tarayıcı senaryosu (kabul senaryosu 1, 2, 5)

1. `http://localhost:3010` → **Burak Yılmaz** kartı → bir derse gir.
2. **Sınav provası** sekmesi → **"Sınav başlat"** düğmesi. Dikkat: iki kart var —
   *Alıştırma* ve *Sınav* (`apps/web/lib/exam.ts:57-66`). **Sınav** olanı seçin;
   kilit yalnız `exam` moduna bağlıdır (FR-101).
3. Aynı tarayıcıda **ikinci sekme** aç: `/courses/<CID>/chat`.
4. Bir soru gönder.

| | Bugünkü sonuç | 002 bitince beklenen |
|---|---|---|
| Sohbet gönderimi | **200, tam kaynaklı cevap** — ürünün sınav vaadinin ihlali | **403**, gövde `{"error":{"code":"exam_in_progress","message":"Şu anda süren bir sınav oturumun var…"}}` |
| Ders gezinme çubuğu | "Asistan" sekmesi normal görünür | Sekme **kilitli** görünür, yanında metin/rozet ve nedeni yazar (renk tek başına bilgi taşımaz — Anayasa VII) |
| Sokratik mod | 200 | 403, aynı kod (FR-102) |

#### B) API senaryosu (Independent Test — jürinin deneyeceği yol)

```bash
# 1) Sınav oturumu başlat
SID=$(curl -s -X POST "$API/courses/$CID/exams" -H "$OGR" \
  -H "Content-Type: application/json" -d '{"mode":"exam"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")

# 2) Aynı token'la asistana sınav sorusunu sor  → FR-101
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/courses/$CID/chat" -H "$OGR" \
  -H "Content-Type: application/json" -d '{"question":"Semafor nedir?","mode":"qa"}'

# 3) Sokratik mod  → FR-102
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/courses/$CID/chat" -H "$OGR" \
  -H "Content-Type: application/json" -d '{"question":"Semafor nedir?","mode":"socratic"}'

# 4) İKİNCİ SEKME YOLU — geçmiş okuma da bir yardım yüzeyidir
curl -s -o /dev/null -w "%{http_code}\n" "$API/courses/$CID/chat/sessions" -H "$OGR"

# 5) Öğretmen muafiyeti  → FR-103
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/courses/$CID/chat" -H "$HOC" \
  -H "Content-Type: application/json" -d '{"question":"Semafor nedir?","mode":"qa"}'

# 6) Sınavı bitir, tekrar sor  → Independent Test
curl -s -X POST "$API/courses/$CID/exams/$SID/finish" -H "$OGR" > /dev/null
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/courses/$CID/chat" -H "$OGR" \
  -H "Content-Type: application/json" -d '{"question":"Semafor nedir?","mode":"qa"}'
```

Beklenen (002 sonrası): `403 · 403 · 403 · 200 · 200`. **Bugün: `200 · 200 · 200 · 200 · 200`.**

Adım 4 gözden kaçmasın: `GET /chat/sessions/{id}` (`app/api/chat.py:712-739`) geçmiş
turların kaynaklı cevap metnini ve atıflarını **aynen** döndürür. Yalnız `POST /chat`
kapatılırsa kilit ikinci sekmeden delinir. 002'nin kararı bu yüzden kontrolü uç gövdesine
değil `deps.py`'ye yeni bir `UnlockedCourseMemberDep` bağımlılığı olarak koymaktır — üç uç
da aynı kapıdan geçer.

#### C) Süre dolması (kabul senaryosu 3 · FR-104)

Kilit "bitmemiş oturum"a değil "**yürüyen** oturum"a bağlıdır. Süreyi beklemek yerine
oturumu geriye alın (superuser bağlantısıyla; `dou_app`'in `exam_sessions` üzerinde tablo
düzeyi UPDATE yetkisi `0007_question_delete_and_exam_grants.sql:49-50` ile çekilmiştir —
bu, kilidin uygulama koduna değil yetkilere dayanmasını sağlayan aynı korumadır):

```bash
psql -d dou_synapse -c \
  "update exam_sessions set expires_at = now() - interval '1 minute' where id = '$SID';"
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/courses/$CID/chat" -H "$OGR" \
  -H "Content-Type: application/json" -d '{"question":"Semafor nedir?","mode":"qa"}'   # 200
```

Süre kırpması iki kaynaklıdır: `expires_at` **ve** `started_at + exam_duration_minutes`
(varsayılan 20, `app/core/config.py:158`); hangisi önce gelirse o geçerlidir
(`app/api/exams.py:20-26, 90-98`). Yalnız `expires_at`'i ileri atarak "kilit hâlâ açık"
göstermeye çalışmak bu yüzden çalışmaz — ve çalışmaması doğrudur.

#### D) Prova modu kilitlemez (kabul senaryosu 4)

`{"mode":"practice"}` ile oturum açıp aynı sohbet isteğini gönderin → **200** beklenir,
bugün de 200. Bu adım, kilit indikten sonra **fazla kapatmadığını** kanıtlayan tek adımdır;
atlamayın.

#### E) FR-106 — kilit kaldırıldığında kırmızı yanma

`apps/api/tests/test_exam_lock.py` (002 yazacak) sekiz iddia taşır ve sekizincisi bir
**karşı kontroldür**: kilit fonksiyonu monkeypatch ile devre dışı bırakılıp aynı kurulumun
**200 + kaynaklı cevap** ürettiği gösterilir. Bu olmadan 403'ün sebebi "kilit" değil "bozuk
fikstür" de olabilir; deponun kurulu yöntemi budur
(`tests/test_isolation_layers.py:64-75` aynı gerekçeyi yazıyor).

```bash
cd apps/api && uv run pytest tests/test_exam_lock.py -v
```

**Doğrulamanın doğrulaması:** `app/api/deps.py`'deki kilit çağrısını bilerek yorum satırı
yapın ve testi tekrar koşun. 1–7 kırmızı, 8 yeşil kalmalıdır. Hepsi yeşil kalıyorsa test
kilide değil başka bir şeye bağlıdır.

---

### 4.2 US2 — bilinen üç production kusuru

#### FR-224 · issuer ortam değişkeni (en ucuz doğrulama, 30 saniye)

```bash
cd apps/api
# Belgedeki ad:
SUPABASE_JWT_ISSUER=https://ornek.supabase.co/auth/v1 \
  uv run python -c "from app.core.config import Settings; print('SUPABASE_JWT_ISSUER ->', Settings().jwt_issuer)"
# Kodun bugün okuduğu ad:
JWT_ISSUER=https://ornek.supabase.co/auth/v1 \
  uv run python -c "from app.core.config import Settings; print('JWT_ISSUER          ->', Settings().jwt_issuer)"
```

| | Bugünkü sonuç | 002 bitince beklenen |
|---|---|---|
| `SUPABASE_JWT_ISSUER` | **`None`** — sessizce yutuldu | Değer okunur |
| `JWT_ISSUER` | Değer okunur | Değer okunur (ya da tek ada indirgenir) |

Sessizliğin sebebi `app/core/config.py:73` `extra="ignore"`. Sonuç: kurulum belgesini
**birebir** uygulayan operatörde issuer doğrulaması kapalı kalır — imza doğrulaması
etkilenmez, kaybedilen katman issuer sabitlemesidir (`app/core/security.py:74-99`).
SC-015 bunun bir testle sabitlenmesini istiyor: `.env.example` ve `docs/deployment.md`'de
geçen her değişken adının `Settings` alanlarıyla karşılaştırıldığı bir test.

#### FR-220 · event loop bloklanması

İki terminal. Birincide sağlık yoklamasını saniyede bir vurun, ikincide büyük bir PDF
yükleyin:

```bash
# terminal A
while true; do /usr/bin/time -p curl -s -o /dev/null "$API/health/live" 2>&1 | grep real; sleep 1; done

# terminal B
curl -s -X POST "$API/courses/$CID/documents" -H "$HOC" \
  -F "file=@sample_data/isletim-sistemleri/<buyuk>.pdf" -o /dev/null -w "%{http_code}\n"
```

Bugün beklenen: yükleme tetiği (`app/api/documents.py:94` → `_trigger_worker` → drain)
ayrıştırma ve embedding'i **döngü içinde** koşturur, `health/live` gecikmesi görünür
şekilde sıçrar. Tek `asyncio.to_thread` kullanımı depolamadadır
(`app/modules/ingestion/storage.py:50,55,61`), hesap tarafında yoktur.

**Sayı yazmadan geçmeyin:** SC-014 bloke süresinin **ölçülüp rapora yazılmasını** istiyor.
Ölçmediyseniz `docs/test-report.md`'ye **KOŞULMADI** yazın (FR-182).

#### FR-221 · ısıtma

```bash
# soğuk sunucu, ilk istek
time curl -s -X POST "$API/courses/$CID/chat" -H "$OGR" \
  -H "Content-Type: application/json" -d '{"question":"Semafor nedir?","mode":"qa"}' > /dev/null
```

001'in ölçtüğü değerler (fastembed, yerel): ilk soru **11,7 sn**, ikinci soru **0,08 sn**
(001 quickstart §6.1). 002 sonrası ilk isteğin bu cezayı tek başına ödememesi beklenir ve
**yeni sayı ölçülüp yazılır** — eski sayıyı kopyalamak SC-009'u düşürür.

#### FR-222 / FR-223 · soru üretimi kotası

```bash
for i in $(seq 1 8); do
  curl -s -o /dev/null -w "$i:%{http_code} " -X POST "$API/courses/$CID/questions/generate" \
    -H "$HOC" -H "Content-Type: application/json" \
    -d '{"topic_id":"<TOPIC_ID>","question_type":"mcq","count":5}'
done; echo
```

Bugün: hepsi `200` — sınır yok (`app/api/questions.py:154-200`, `_rate_limiter` çağrısı
yok). Karşılaştırma noktası sohbettir: `app/api/chat.py:589-594` + `config.py:230-232`
(20 istek / 60 sn). FR-222 açıkça **sohbet sınırının kopyası olmasın** diyor; üretim
maliyeti farklıdır. Ayrıca aynı kullanıcının **eşzamanlı ikinci üretimi** reddedilmelidir —
bunu tek satırla deneyin:

```bash
( curl -s -o /dev/null -w "A:%{http_code}\n" -X POST "$API/courses/$CID/questions/generate" -H "$HOC" -H "Content-Type: application/json" -d '{"topic_id":"<TOPIC_ID>","question_type":"mcq","count":5}' & \
  curl -s -o /dev/null -w "B:%{http_code}\n" -X POST "$API/courses/$CID/questions/generate" -H "$HOC" -H "Content-Type: application/json" -d '{"topic_id":"<TOPIC_ID>","question_type":"mcq","count":5}' & wait )
```

Beklenen (002 sonrası): biri `200`, diğeri `409`/`429` ve **ne zaman tekrar denenebileceğini
söyleyen** bir mesaj. FR-223 için sayaç tahliyesi kod incelemesiyle doğrulanır; süreç ömrü
boyunca sınırsız büyüyen bir `defaultdict` bugün `app/api/chat.py:134` civarında duruyor.

> **Bu blok gerçek LLM anahtarı ister mi?** Kota ve eşzamanlılık **hayır** — sınır
> LLM'e gitmeden önce devreye girmelidir; sahte sağlayıcıyla da doğrulanabilir ve
> doğrulanmalıdır. Üretilen sorunun **kalitesi** anahtar ister; bkz. [§5](#5-gerçek-anahtar-bekleyen-doğrulamalar).

---

### 4.3 US3 — sınav blueprint'i

Bugün doğrulanacak bir şey yok: `supabase/migrations/` `0007`'de bitiyor. 002 `0008`'i
ekleyecek. Kurulumdan sonra ilk kontrol:

```bash
for f in supabase/migrations/*.sql; do psql -v ON_ERROR_STOP=1 -d dou_synapse -f "$f"; done
psql -d dou_synapse -tAc "select count(*) from information_schema.tables
  where table_schema='public' and table_type='BASE TABLE'"
```

Bugün **15**; `0008` sonrası **20** olması beklenir (yeni tablolar: `learning_outcomes`,
`exam_blueprints`, `blueprint_cells`, `exam_versions`, `exam_items`). Sayıyı ölçün,
tahmin etmeyin — devir belgesi bu tuzağa bir kez düşmüş: "19 tablo görmelisin" yazıldı,
doğrusu 15'ti ve iki şerit sağlam bir veritabanını bozuk sanıp zaman harcadı
(`20_DEVIR_9_AGUSTOS.md:168-169`).

Elle doğrulama sırası (kabul senaryoları 1–7):

1. Öğrenme çıktısı tanımla → blueprint oluştur → **öğrenci göremez** (senaryo 1).
2. Dağılımı bilerek tutarsız ver (5 MCQ + 2 açık uçlu ama toplam 8) → **kaydedilmez** ve
   hangi hücrenin tutmadığı **Türkçe** söylenir (FR-112). Mesajın Türkçe ve hücre adlı
   olması, doğrulamanın uygulama katmanında yapıldığının kanıtıdır; PostgreSQL kısıt
   ihlali bu cümleyi kuramaz (Anayasa V).
3. Havuzda 5 onaylı soru varken 7 soruluk blueprint'i yayınlamayı dene → **yayınlanmaz**,
   eksik hücre raporlanır (senaryo 3 · FR-114 · SC-003).
4. Yayınla, öğrenciyle oturum başlat, **oturum sürerken** soruyu değiştir → yeni sürüm
   oluşur, yürüyen oturum eski sürümü görmeye devam eder (senaryo 4 · FR-115).
5. Yayın penceresi kapalıyken öğrenci sınavı **görmez** (senaryo 5 · FR-116).
6. Açık uçlu cevapta öğrenci **ölçüt kırılımı** görür (senaryo 6 · FR-117).
7. Kaynak belgeyi yeniden yükle → soru "kaynak sürümü değişti" işaretlenir (senaryo 7 ·
   FR-118).

4. maddenin yapısal ayağı yetkilerdedir: `0001_core_schema.sql:313-316` mevcut **ve
gelecek** tüm tablolara `dou_app` için SELECT/INSERT/UPDATE/DELETE veriyor. `0008` bunları
açıkça geri almazsa `exam_items` tam yazılabilir doğar ve FR-115 garantisi koda değil
alışkanlığa dayanır. Doğrulama:

```bash
psql -d dou_synapse -tAc \
  "select privilege_type from information_schema.role_table_grants
   where grantee='dou_app' and table_name='exam_items' order by 1"
# UPDATE görmemelisiniz.
```

---

### 4.4 US4 — ders bazlı AI politikası

1. Öğretmen dersin politikasını "yalnız Sokratik" yapar → öğrenci `mode=qa` gönderir →
   **sunucu reddeder** (FR-130/FR-135). Arayüzde seçeneği gizlemek yeterli değildir;
   doğrulamayı **curl ile** yapın, tarayıcıyla değil.
2. İpucu üst sınırı 2 → üçüncü ipucu **verilmez** (FR-131).
3. Bir belge kaynak setinden çıkarılır → o belgeden **atıf gelmez** (FR-132).
4. Reddetme eşiği yükseltilir → sınırdaki soru **dersin eşiğiyle** değerlendirilir, global
   varsayılanla değil (FR-133). Bugün eşik global ve sağlayıcıya bağlı
   (`app/core/config.py:35-38`).
5. **En kolay atlanan madde:** hiç dokunulmamış bir ders **bugünkü davranışla** çalışmalıdır
   (FR-136). Politika inmeden önce bir dersin cevabını kaydedin, indikten sonra aynı soruyu
   tekrar sorun; fark varsa varsayılanlar davranışı değiştirmiştir ve bu bir regresyondur.

---

### 4.5 US5 — güvenilirlik UX

```bash
# API'yi kapat, sayfayı aç
# terminal 1: uvicorn'u durdur
open http://localhost:3010/courses
```

| Kontrol | Bugünkü sonuç | 002 bitince beklenen |
|---|---|---|
| Süresiz bekleme | `apps/web/lib/api.ts`'te `AbortSignal` yok → istek tarayıcı varsayılanına kadar asılı kalır | 10 sn'den uzun belirsiz bekleme yok (SC-005) |
| Geçici hata (503) | Yeniden deneme yok | Artan aralıklarla sınırlı yeniden deneme (FR-151) |
| Kalıcı hata (403/404) | — | Yeniden deneme **yok**, "Tekrar dene" **gösterilmez** (FR-153) |
| Veri değiştiren istek | — | Otomatik yeniden deneme **yok** (FR-152) |
| İstek kimliği | Yanıt **başlığında** var (`app/main.py:63,66`), hata **gövdesinde** yok (`app/core/errors.py:57-62`) | Gövdede taşınır ve ekranda kopyalanabilir (FR-155 · SC-007) |
| Polling | `apps/web/lib/use-resource.ts:263-271` sabit `intervalMs` (varsayılan 2000) | Sunucu yanıt vermezken aralık **artar** (FR-156) |

US1'in `GET /chat/availability` ucu bu hikâyeyle kesişir: kilitli durumu bildiren yoklama
`pollWhile` ile kurulur ve **kilit kalkınca kendiliğinden durur** (Anayasa XI:
durdurulmayan polling kusurdur).

---

### 4.6 US6 — sayfalama

```bash
curl -s "$API/courses/$CID/questions?limit=5" -H "$HOC" | python3 -c "import json,sys; d=json.load(sys.stdin); print(type(d), len(d))"
```

Bugün: `limit` yok sayılır, düz liste döner (`app/api/questions.py:120`). 002 sonrası:
zarf içinde sayfa + imleç, sunucu kendi üst sınırını uygular (FR-161), sıralama
belirlenimcidir (FR-163). Doğrulama için 200 kayıt tohumlayın ve **eşzamanlı ekleme
sırasında** ikinci sayfayı isteyin (FR-162).

---

### 4.7 US7 — gerçek kimlik

- Sağlayıcı yapılandırılmamışken `dev:` kimliği **çalışmaya devam etmelidir** — bugünkü
  akış bozulmamalı.
- `ENVIRONMENT=production DEV_AUTH_ENABLED=true` ile uygulama **başlamamalıdır**
  (FR-172, bugün uygulanıyor):
  ```bash
  cd apps/api && ENVIRONMENT=production DEV_AUTH_ENABLED=true \
    uv run python -c "from app.core.config import Settings; Settings()"   # hata vermeli
  ```
- Oturum süresi dolduğunda arayüz tazelemeyi denemeli, olmazsa girişe yönlendirmeli
  (FR-171). **Dikkat:** bu kural US1 ile çakışabilir — kilit **403** döndürür ve
  "403 görünce girişe at" diye yazılmış bir kural öğrenciyi sınav sırasında giriş ekranına
  fırlatır. Yönlendirme kararı **`error.code`'a** bakmalıdır, yalnız HTTP durumuna değil.
  Bu ikisini birlikte deneyin.

---

### 4.8 US8 — belge doğruluğu

Kod yazmadan kapatılabilen en yüksek getirili açık; jürinin okuyacağı yer burası.

```bash
# Aynı metrik kaç farklı değer taşıyor?
grep -rn "479\|664" README.md docs/ specs/001-course-assistant-mvp/quickstart.md | grep -i test
grep -rn "15 tablo\|19 tablo\|20 tablo" README.md docs/ specs/
```

Bu belgeyi yazarken bulunan bir çelişki, yöntemin işlediğinin kanıtıdır:
`specs/001-course-assistant-mvp/quickstart.md:195` **479 test** diyor; bugün ölçülen
**664** (`uv run pytest -q`, 75,48 sn). Aynı dosya satır 86 ve 120'de RLS testi için
"8 PASS" diyor; `supabase/tests/rls_isolation.sql` bugün **26 farklı iddia adı** taşıyor.
İkisi de FR-180/FR-181 ihlalidir ve 002'nin 5. sıradaki işidir.

FR-183 bu kontrolün **otomatik** olmasını istiyor. En küçük yeterli hâli: belgelerdeki
sayıları üreten komutları belgenin yanında tutup CI'da koşturmak. Ölçülmemiş her metrik
için sayı değil **KOŞULMADI** yazılır (FR-182) — `docs/test-report.md` bu deseni zaten
uyguluyor, örnek oradadır.

---

### 4.9 US9, US10, US11

| Kontrol | Komut / adım | Bugün |
|---|---|---|
| E2E veri hijyeni (FR-190 · SC-010) | Koşu öncesi/sonrası `select count(*) from courses` | Fark **sıfır olmalı**; bugün değil |
| Temizlik komutu (FR-191) | Ne sileceğini **önce göstermeli**, sonra onay istemeli | Komut yok |
| Sohbet geçmişi silme (FR-200) | `DELETE /courses/{id}/chat/sessions/{sid}` | Uç yok |
| Dışa aktarma (FR-201) | Dosyada **başka kullanıcının verisi olmamalı** | Uç yok |
| Güvenlik başlıkları (FR-215) | `curl -sI "$API/health/live"` → CSP, `X-Content-Type-Options`, `Referrer-Policy` | Yok (`app/main.py:40-100`) |
| Kusurlu işleme görünürlüğü (FR-213/214 · SC-013) | Bir işleme işini bilerek boz → panelde görünsün, yeniden çalıştırılabilsin | Yok |

---

## 5. Gerçek anahtar bekleyen doğrulamalar

Aşağıdakiler **anahtarsız koşturulamaz.** Anahtarsızken sistem deterministik sahte
sağlayıcıya düşer (logda: `llm anahtarı yok — deterministik sahte sağlayıcıya düşülüyor`);
atıflar yine gerçek parçalara bağlıdır ve guardrail zinciri aynen koşar, yalnız cevabın
düzyazısını model yazmaz.

| Doğrulama | Neden anahtar ister | Anahtarsız ne yapılır |
|---|---|---|
| Soru üretiminin **gerçekten soru döndürmesi** | Sahte sağlayıcı soru şemasını üretmiyor; `rejection_reasons: ["yanıtta 'questions' dizisi yok"]` (`20_DEVIR_9_AGUSTOS.md:101-106`) | Havuzu elle tohumla; US1/US3 doğrulamaları buna bağlı |
| US3 blueprint'inden **kaliteli** taslak üretimi (FR-113) | Şema akışı sahteyle kanıtlanır, **pedagojik kalite kanıtlanmaz** (spec.md:412) | Şema akışını doğrula, kaliteyi T047'ye bırak |
| US4 günlük LLM bütçesi (FR-134) | Bütçe gerçek çağrı maliyetiyle anlamlı | Sayaç mantığını birim testle sabitle |
| Kanıt eşiğinin yeniden ölçümü | `retrieval/scope.py` indikten sonra **hiç ölçülmedi**; üç şerit üç farklı sayı önerdi ve eşik bilerek değiştirilmedi (`app/core/config.py:39-60`) | Rapora **KOŞULMADI** yaz |
| Üç atlanan uçtan uca vakası | Soru üretimine bağlı, koşullu atlama kendini açar | — |
| T023 canlı Supabase, T050 prod ortam, T051 prod RLS | Dış erişim | 002'nin kapsamı dışında (spec.md:397) |

**Anahtarsız da koşan ve koşulması gereken US2 parçaları:** kota, eşzamanlılık sınırı,
issuer adı, event loop ölçümü, ısıtma. Bunları "anahtar gelince" diye ertelemeyin.

---

## 6. Sorun giderme — 002'ye özgü

| Belirti | Neden / çözüm |
|---|---|
| Her sohbet isteği **422** | Yanlış sunucu: `:8000`'de başka bir ağacın API'si var. `NEXT_PUBLIC_API_URL=http://localhost:8010` verin (§1.2) |
| Tarayıcıdan istek **CORS'a takılıyor** | 3010 (ya da başka bir port) `CORS_ORIGINS`'te yok. Kod varsayılanı yalnız 3000 + 3100 (`app/core/config.py:113`) |
| Cevaplar **alakasız parçalara** atıf yapıyor | `EMBEDDING_PROVIDER` verilmedi → `hashing` ile E5 korpusunu sorguluyorsunuz. Çökmez, sessizce yanılır (§1.2) |
| `POST /exams` → **409 "onaylanmış soru yok"** | Havuz boş; anahtarsız üretim sıfır döner. Havuzu elle tohumlayın (§3) |
| **US1 doğrulaması bugün 403 dönüyor** | Kilit inmiş olabilir — ya da yanlış şeyi ölçüyorsunuz. Kontrol: `practice` modu da 403 mü? Öyleyse fazla kapatılmış. Öğretmen de 403 mü? Öyleyse FR-103 ihlal |
| **US1 testi kilit silinince de yeşil** | Karşı kontrol (test 8) yanlış modüle patch uyguluyor olabilir. `deps.py` çağrıyı `exam_state.active_exam_session(...)` biçiminde modül üzerinden yapmalı; `from … import` bağlanmış kopya bırakır ve patch etkisiz kalır |
| RLS testi `duplicate key … profiles_pkey` | Seed'den sonra koşuldu. Temiz veritabanında koşturun (§2) |
| `bunx playwright` **"two different versions"** | `node_modules/.bin/playwright` kullanın (`20_DEVIR_9_AGUSTOS.md:52-53`) |
| E2E "Bağlantı kurulamadı" | `E2E_API_URL` verilmedi → `:8000` varsayılanına düştü; ya da 3100 CORS'ta yok |
| İlk soru **çok uzun sürüyor** | 2,1 GB model iniyor olabilir. `EMBEDDING_CACHE_DIR`'i kalıcı bir dizine alın (001 quickstart §6.1); macOS `$TMPDIR`'ı temizler |
| `pytest`'te `psql` bulunamıyor | `PG_BIN`'i kendi kurulumunuza göre ayarlayın (`apps/api/tests/conftest.py`) |
| Migration'da `extension "vector" is not available` | pgvector yanlış `pg_config` ile derlendi (001 quickstart §1) |

---

## 7. "Bitti" demeden önce

Anayasa VIII: davranış **gerçek ortamda** gözlenmeden bitti denmez; bu şeritte gerçek
ortam **tarayıcı + bu ağacın API'si**, `curl` değil. Her User Story için:

- [ ] `uv run pytest -q` yeşil ve **sayı bu belgeye yazıldı** (bugün: 664)
- [ ] `bun test lib/` yeşil (bugün: 211)
- [ ] `uv run mypy app` · `ruff check` · `ruff format --check` temiz
- [ ] Yeni uç eklendiyse OpenAPI **yeniden export edildi** (elle düzenlenmez —
      `20_DEVIR_9_AGUSTOS.md:153-155`) ve yol sayısı güncellendi
- [ ] Yeni davranışın testi **bilerek bozularak kırmızı yandığı** gösterildi
- [ ] Tarayıcıda fiilen tıklandı — özellikle US1'in iki sekmeli senaryosu
- [ ] Ölçülmeyen hiçbir sayı yazılmadı; ölçülmeyen yere **KOŞULMADI** yazıldı
- [ ] Bu belgedeki "bugünkü sonuç" sütunu güncellendi — 002 ilerledikçe bu belge de
      bayatlar ve US8 bu belgeyi de kapsar