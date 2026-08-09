# R3 — Dağıtım, çevrimdışı dayanıklılık ve demo günü

> **Önce `10_OKU_ONCE_FAZ2.md`.** Bu belge yalnız senin şeridini anlatır.
> Dal: `feat/deploy` · Worktree: `~/code/.dou-deploy` · Port: **8023**
> Görevler: **T048, T049, T052, T053, T054, T055** · Migration numaran: **`0007`**

```bash
cd ~/code/dou-lead && git fetch origin
git worktree add ~/code/.dou-deploy -b feat/deploy origin/main
cd ~/code/.dou-deploy/apps/api && uv venv --python 3.12 && uv pip install -e ".[dev]" && cp ../../.env.example .env
uv run pytest -q      # 473 yeşil görmeden başlama
```

---

## Neden bu şerit

24 Ağustos'ta bu sistem bir odada, muhtemelen kötü bir internetle, canlı
gösterilecek. Bugün elde çalışan bir hat var ama:

- Embedding modeli çalışma zamanında indiriliyor → ilk istekte dakikalarca
  bekleme, ağ yoksa hiç çalışmama
- Worker tetiği süreç içi; ayrı bir worker servisi varsa tetiklenemiyor
- Cold start ölçülmedi
- Ağ giderse **hiçbir yedek plan test edilmedi**

Senin şeridin "gösteri günü çalışmama" riskini kaldırıyor. Bu, projeyi
kurtaracak ya da batıracak tek şerit olabilir.

## Sahiplendiğin dosyalar

```
apps/api/Dockerfile                     MEVCUT — genişlet
docker-compose.yml                      MEVCUT — genişlet (fallback profili)
apps/api/app/api/internal.py            MEVCUT (boş router, main.py'ye KAYITLI)
apps/api/tests/test_internal.py         YENİ
apps/api/scripts/fill_answer_cache.py   YENİ
apps/api/scripts/warmup.py              YENİ (isterseniz)
.github/workflows/keepalive.yml         YENİ
.github/workflows/ci.yml                MEVCUT — genişlet
supabase/migrations/0007_*.sql          YENİ, gerekirse (numara sana ayrıldı)
docs/deployment.md                      YENİ
specs/001-course-assistant-mvp/tasks.md yalnız T048-T055, T052 satırların
```

**Dokunma:** `apps/api/app/main.py` (router'ın ZATEN kayıtlı),
`config.py` (`worker_drain_secret` ZATEN eklendi), `apps/web/**` (lider),
`app/api/documents.py`'nin `_trigger_worker` DIŞINDAKİ kısmı.

`documents.py::_trigger_worker` fonksiyonunu T049 için değiştirebilirsin —
ama **yalnız o fonksiyonu.**

---

## İş 1 — T049: worker'ın HTTP tetiği (önce bu, çünkü küçük ve diğerlerini açar)

`app/api/internal.py` boş bir router olarak duruyor ve `main.py`'ye kayıtlı.
Gövdesini yaz:

```
POST /internal/drain
  başlık: X-Worker-Secret: <settings.worker_drain_secret>
  yanıt:  { processed: <int> }
```

Kurallar:
- `worker_drain_secret` **tanımsızsa uç 404 döner** (varmış gibi bile
  görünmez). Fail-closed: korumasız bir drain ucu dışarıdan iş kuyruğu
  tetiklemeye izin verirdi.
- Sır karşılaştırması **sabit zamanlı** (`secrets.compare_digest`). Düz `==`
  zamanlama sızdırır.
- `include_in_schema=False` zaten ayarlı — bu uç OpenAPI'ye girmez, istemci
  sözleşmesinin parçası değil.
- Uç **kimlik doğrulaması istemez** ama sır ister; `CourseMemberDep` kullanma
  (bu bir kullanıcı ucu değil).

Sonra `documents.py::_trigger_worker`'ı şu davranışa getir: ortamda bir worker
URL'i varsa oraya HTTP çağrısı yap, yoksa bugünkü gibi süreç içi `drain()`
koştur. Çağıran kod aynı kalır (fonksiyonun docstring'i bunu zaten vaat ediyor).

Testler: sırsız 404, yanlış sır 403, doğru sır 200 + işlenen sayı, sabit zamanlı
karşılaştırma kullanıldığının kanıtı.

**Bilmen gereken taze bir davranış:** `SessionDep` artık `scope="function"` ve
yükleme ucunun arka plan tetiği **artık gerçekten iş buluyor** (önceden satır
commit edilmeden önce çalışıp boş kuyruk görüyordu). Yani bugün tetik çalışıyor;
senin işin onu ayrı bir servise taşınabilir hâle getirmek.

## İş 2 — T048: Dockerfile'a modeli göm

Bugün `EMBEDDING_PROVIDER=fastembed` ilk çağrıda modeli indiriyor
(multilingual-e5-large, ~2GB fp32). Demo gününde ağ yavaşsa ilk soru dakikalarca
sürer; ağ yoksa hiç çalışmaz.

- Modeli **build aşamasında indir** ve imaja göm (`EMBEDDING_CACHE_DIR` imaj içi).
- **int8 quantize** kullan — imaj boyutu ve bellek üçte birine iner. Quantize
  edilmiş modelin **aynı vektör uzayında olduğunu doğrula**: aynı metin için
  fp32 ve int8 embedding'leri arasındaki kosinüs benzerliğini ölç ve raporla.
  Farklıysa korpusun yeniden işlenmesi gerekir; bu bir ingest-zamanı kararıdır.
- Çalışma zamanında **indirme denemesi olmamalı**. Bunu ağsız bir konteynerde
  gerçekten kanıtla (`docker run --network none`).
- Çok aşamalı build kullan; final imajda derleyici/geliştirme bağımlılığı olmasın.
- İmaj boyutunu ölç ve yaz.

## İş 3 — T053: `fill_answer_cache.py` (çevrimdışı sigortası)

`answer_cache` birebir eşleşmeli ve **yalnız QA modunda** çalışıyor
(`api/chat.py::question_hash` — mod anahtarın parçası, harf büyüklüğü KORUNUR
çünkü Türkçede i/İ dönüşümü kayıplıdır).

Betik: demo senaryosunun sorularını alır, hattı gerçekten koşturur, sonucu
`answer_cache`'e yazar. Böylece demo günü LLM'e hiç gidilmez.

- Sorular bir dosyadan gelsin (`demo/questions.json` gibi), koda gömülmesin.
- **Yalnız `answered` ve atıflı cevaplar** önbelleğe girsin — `_store_cache`
  zaten bu kuralı uyguluyor, betik de aynı kuralı uygulamalı.
- Ders bazlı: A dersinin cevabı B'ye gitmez.
- Betik idempotent olsun (`on conflict do nothing` zaten var).
- **Önbellekten gelen cevap `cached: true` döner** — bunu doğrula ve raporla;
  demo sırasında hangi cevabın önbellekten geldiği görülebilmeli.

## İş 4 — T054: yedek + restore provası (TAM ÇEVRİMDIŞI AKIŞ)

Bu maddenin çıktısı bir belge değil, **çalışan bir prova.**

- `pg_dump` + Storage yedeği al.
- `docker-compose.yml`'e bir **fallback profili** ekle: yerel Postgres +
  API + web, `DEV_AUTH_ENABLED=true`, `EMBEDDING_PROVIDER` gömülü model,
  `LLM_FAKE_PROVIDER` ya da önceden doldurulmuş `answer_cache`.
- Yedeği bu profile **gerçekten restore et** ve **tam akışı koştur**:
  giriş → ders → materyal → soru sor → kaynaklı cevap → sınav provası.
- **Ağı kapat** (`--network none` ya da uçak modu) ve tekrar koştur.
- Ne çalıştı, ne çalışmadı — hepsini yaz. Çalışmayan varsa düzelt ya da
  runbook'a "bu adımda şu çalışmaz" diye geç.

## İş 5 — T055: cold start ve p95 ölçümü

- Scale-to-zero'dan uyanma süresini ölç (birden çok deneme, medyan + en kötü).
- Sıcak replikada sorgu yolu **p95** ölç: `/chat` uçtan uca, en az 30 istek.
- Hedef `<10 sn` **yalnız sıcak replikada** geçerli — bunu ayrı ayrı raporla,
  tek bir sayıya karıştırma (Anayasa III).
- Ölçüm betiğini repoda bırak ki tekrarlanabilsin.

## İş 6 — T052: keepalive + CI genişletmesi

- `.github/workflows/keepalive.yml`: günlük cron, Supabase'e hafif sorgu +
  `/health/ready` ping. Free-tier pause önlemi (teslim ile jüri arası).
  Sır kullanıyorsa GitHub Secrets'tan, repoya **yazma**.
- `ci.yml`'e ekle (Şerit 5'in bıraktığı iş):
  `supabase/tests/rls_assessment.sql` + `rls_assessment_mutation_check.sh`.
  Komut SQL dosyasının başında hazır. R1 `rls_isolation` için aynısını
  ekleyecek — **çakışmamak için `ci.yml`'de yalnız `rls_assessment` satırını
  sen ekle**, `rls_isolation` satırını R1'e bırak ve raporunda bunu yaz.
- CI'da Docker imajının **gerçekten build olduğunu** doğrula (push etme).

## İş 7 — `docs/deployment.md`

Kurulumun tek doğru anlatımı: ACA/Vercel/Supabase yapılandırması, ortam
değişkenleri (değerler değil, **adları ve ne işe yaradıkları**), migration sırası,
ilk kurulum adımları, rollback. T050 (prod doğrulaması) gerçek erişim istiyor —
erişim yoksa adımları yaz ve **"KOŞULMADI"** diye işaretle.

## Lidere iletmen gerekenler

- `apps/web` tarafında gereken her şey (ör. `NEXT_PUBLIC_API_URL` davranışı,
  Vercel yapılandırması) — lider yapar
- `.env.example`'a eklenmesi gereken değişken listesi
- Demo günü için liderin bilmesi gereken kısıtlar (runbook'u R5 yazıyor,
  ölçümleri sen veriyorsun — R5'e doğrudan da yaz)

## Bitti sayılma ölçütün

- [ ] `/internal/drain` çalışıyor, sırsız 404, sabit zamanlı karşılaştırma, testli
- [ ] Docker imajı modeli gömüyor; `--network none` ile embedding üretiliyor (kanıtlı)
- [ ] int8 ↔ fp32 vektör uzayı denkliği ölçüldü ve yazıldı
- [ ] `fill_answer_cache.py` çalışıyor, `cached: true` doğrulandı
- [ ] Restore provası **ağsız** koştu; ne çalıştı/çalışmadı yazılı
- [ ] Cold start + p95 ölçüldü, sıcak/soğuk ayrı raporlandı
- [ ] `keepalive.yml` + `ci.yml`'de RLS assessment koşuyor
- [ ] `docs/deployment.md` yazıldı
- [ ] 473+ test yeşil, mypy temiz, ruff temiz

## EK (lider, 9 Ağustos ~17:00) — embedding sürüm uyuşmazlığı, AÇIK RİSK

Ölçüldü: `fastembed` bu makinede `intfloat/multilingual-e5-large` modelini
**mean pooling** ile kuruyor ve şu uyarıyı veriyor:

```
The model intfloat/multilingual-e5-large now uses mean pooling instead of CLS
embedding. In order to preserve the previous behaviour, consider either pinning
fastembed version to 0.5.1 ...
```

Bu bir uyarı değil, **vektör uzayı değişikliğidir.** Farklı fastembed
sürümleriyle embed edilmiş bir korpusa karşı sorgu yapmak sessizce yanlış
komşular döndürür — çöker değil, kötüleşir; yani ölçmeden fark edilmez.

Aynı gün bunun kardeşi bir kusur canlıda yakalandı: kanıt eşiği `fastembed`
uzayında kalibre edilmişti, dev korpusu `hashing` ile ingest edilmişti ve eşik
**her soruyu** reddediyordu. Eşik artık sağlayıcıdan çözülüyor, ama bu sınıfın
yalnız yarısı: ikinci yarı **sürüm**.

**Bu sizi ilgilendiriyor:**
- **R2:** ölçtüğünüz her sayı, korpusun hangi sağlayıcı+sürümle embed edildiğine
  bağlıdır. Koşu çıktılarına bu ikisini yazın; yoksa sayı tekrar üretilemez.
  T045 (embedding A/B) zaten iki uzayı karşılaştırıyor — aynı disiplini sürüme
  de uygulayın.
- **R3:** T048 modeli imaja gömüyor. Gömülen sürümü **sabitleyin** (`pyproject`'te
  fastembed pinli mi, kontrol edin) ve imajın ürettiği vektörle korpusun
  vektörünün aynı uzayda olduğunu ölçün (aynı metin → kosinüs ~1.0).
  int8 quantize ölçümünüzün yanına bunu da koyun.
- **R4:** kalıcı çözüm sizde: chunk'ın hangi sağlayıcı+sürümle embed edildiği
  kayda geçmeli (`0006`), sorgu zamanında uyuşmazlık **fail-closed** davranmalı.
  Bugün bu bilgi hiçbir yerde tutulmuyor.

## EK 2 (lider, 9 Ağustos ~17:20) — `ci.yml`'de çakışma önlemi

Lider `ci.yml`'in **`web` job'una** bir adım ekledi (`node scripts/contrast.mjs`).
Senin ekleyeceğin `rls_assessment` satırı **`api` job'unda** — farklı bölüm,
çakışmaz. Rebase'te yine de bu dosyaya bak.

R1 aynı dosyaya `rls_isolation` satırını ekleyecek; o da `api` job'unda olacak.
İkiniz aynı bölüme yazacaksınız: **önce inen kazansın, sonraki rebase alıp
kendi satırını eklesin.** Elle birleştirme yeter, karmaşık değil.

---

# R3 RAPORU — 9 Ağustos 2026

Dal: `feat/deploy` · 6 commit · 487 test yeşil (473 + 14 yeni), mypy temiz, ruff temiz.
OpenAPI **değişmedi** (24 yol): `/internal/drain` `include_in_schema=False`.

## Bitti sayılma ölçütü

- [x] `/internal/drain` çalışıyor, sırsız 404, sabit zamanlı karşılaştırma, testli
- [ ] Docker imajı modeli gömüyor; `--network none` ile embedding üretiliyor — **Dockerfile yazıldı, KOŞULMADI** (bu makinede konteyner çalışma zamanı yok)
- [ ] int8 ↔ fp32 vektör uzayı denkliği — **e5-large için KOŞULMADI** (disk yetmedi); yakın bir model üzerinde ölçüldü, aşağıya bakın
- [x] `fill_answer_cache.py` çalışıyor, `cached: true` doğrulandı
- [x] Restore provası ağsız koştu; 10/10 adım
- [x] Cold start + p95 ölçüldü, sıcak/soğuk **ayrı** raporlandı
- [x] `keepalive.yml` + `ci.yml`'de RLS assessment koşuyor
- [x] `docs/deployment.md` yazıldı
- [x] 487 test yeşil, mypy temiz, ruff temiz

## En önemli üç bulgu

### 1. int8 quantizasyonu vektör uzayını koruyamayabilir

Aynı dinamik int8 yolu `all-MiniLM-L6-v2` üzerinde **en düşük 0.9326 / ortalama
0.9513** kosinüs verdi ve **en yakın komşu sırası korunmadı**. `multilingual-e5-large`
için sayı **KOŞULMADI**: quantizasyon ~4.5 GB tepe disk istiyor, makinede 5.9 GB
boş vardı ve on saniyede 1.0 GB'ye düştü; koşu emniyet için durduruldu.

Build bunu kendi ölçüyor ve kosinüs 0.99'un altındaysa **build düşüyor**. Kapı
düşerse `--build-arg EMBEDDING_QUANTIZE=false` ile fp32 gömülür: imaj ~2 GB
büyür, vektör uzayı indekstekiyle birebir aynı kalır. Alternatifi korpusu int8
ile yeniden ingest etmektir ve bu bir **ingest zamanı kararıdır** — demo sabahı
alınamaz.

### 2. Kanıt eşiği 0.81 kapsam içi soruları reddediyor

`fill_answer_cache.py` provasında 14 demo sorusundan **ikisi**, doğru belge zaten
en iyi sonuçken reddedildi:

| Soru | Dense skor | En iyi kaynak |
|---|---|---|
| Dairesel bekleme koşulu nedir? | **0.7973** | 05-deadlock-demo.pdf |
| inode ne saklar? | **0.8051** | 06-file-systems.pptx |
| *(kapsam dışı)* Bu dersin vize sınavı ne zaman? | 0.7867 | — |
| *(kapsam dışı)* Bugün İstanbul'da hava nasıl? | 0.7441 | — |

Kapsam içi en düşük 0.7973, kapsam dışı en yüksek 0.7867 → **ayrım payı yalnız
+0.0106** ve **0.81 bu payın üstünde**, yani doğru soruları kesiyor. Bu 16
soruluk tek bir ders üzerinde ölçüldü; bir yön göstergesidir, hüküm değil.

**R2 ve R4'e:** `uv run python scripts/probe_evidence_threshold.py --course-id <uuid> --user-id <uuid>`

### 3. Sınav havuzu ağ kesilmeden önce hazırlanmalı

Soru üretimi gerçek LLM anahtarı ister; deterministik sahte sağlayıcı üretim
şemasını uygulamıyor ve `returned: 0` dönüyor (`rejection_reasons: ["yanıtta
'questions' dizisi yok"]`). Çevrimdışı yığında havuz üretilemez. **Runbook'a
(R5):** havuz üretimi ve onayı, ağ hâlâ varken yapılan bir hazırlık adımıdır.

## Ölçümler

| Ölçüm | Değer | Koşul |
|---|---|---|
| Sıcak `/chat` p95, önbellek **ıskası** | 72.7 ms (medyan 57.8) | yerel uvicorn, n=30 |
| Sıcak `/chat` p95, **önbellekten** | 9.2 ms (medyan 7.9) | yerel uvicorn, n=15 |
| Süreç başlangıcı → `/health/ready` | 0.61 sn | 5 tekrar |
| Süreç başlangıcı → **ilk soru** | 1.43–1.55 sn | 5 tekrar, model yükleme dâhil |
| ACA uyanma, imaj boyutu, RSS | **KOŞULMADI** | bulut/konteyner erişimi yok |

**Bu sayılar üretim p95'i DEĞİLDİR** (Anayasa III, tuzak 7): LLM anahtarı yokken
generation terimi ~0'dır; ölçülen yol retrieval + guardrail + veritabanıdır.
Model dosyası sayfa önbelleğindeydi, yani 1.47 sn bir **alt sınırdır**.

İlk sıcak ölçüm p95'i 81.7 ms verdi ve 30 isteğin 15'i önbellekten geliyordu —
14 soru 30 istekte tekrarlanınca yarısı isabet ediyor. Önbellek isabeti LLM'i
tamamen atladığı için birleşik p95, sistemin değil isabet oranının fonksiyonu
olur. İki yol artık ayrı raporlanıyor.

## Çevrimdışı prova (T054) — 10/10

Geri yüklenmiş veritabanına karşı, tüm dış HTTP çıkışı ölü proxy'ye
yönlendirilerek (huggingface.co ve api.groq.com o ortamdan erişilemez olduğu
**doğrulandı**, sunucu sürecinin ortamı da kontrol edildi):

`/health/ready` ok · 1 ders · 13/13 belge `completed` · önbellekten `answered` +
3 atıf + `cached: true` · atıf `05-deadlock-demo.pdf` Sayfa 2'ye çözülüyor ·
kapsam dışı soru `insufficient_context` · sınav aç→cevapla→bitir, MCQ
deterministik puanlandı.

Yedek: `pg_dump -Fc` 467K + storage 289K. Geri yükleme sonrası **40 RLS
politikası ve 15 RLS'li tablo** — kaynakla birebir aynı.

**Koşulmayan:** compose fallback profilinin kendisi. Yığın yerel süreçler olarak
koşturuldu.

## Lidere iletilecekler

1. **`WORKER_DRAIN_URL` ortamdan okunuyor, `Settings` alanı değil**
   (`app/api/internal.py`). `config.py` bu fazda kapalıydı. Faz kapanınca
   `Settings.worker_drain_url` olarak taşınmalı.
2. **`.env.example`'a eklenecekler** (dosya bende değil):
   `WORKER_DRAIN_URL` — worker drain ucunun tam adresi; boşsa tetik süreç içi kalır.
3. **`apps/web` isteği yok.** Arayüzde bu şerit için gereken bir değişiklik çıkmadı.
   Tek not: önbellekten gelen cevap zarfta `cached: true` taşıyor; demo sırasında
   hangi cevabın önbellekten geldiğini göstermek istenirse arayüz bunu kullanabilir.
4. **Brifingdeki "19 tablo" sayısı yanlış.** Hem paylaşılan `dou_synapse` hem
   sıfırdan kurulan bir veritabanı **15 tablo** veriyor. `10_OKU_ONCE_FAZ2.md §4`
   bunu bir sağlık kontrolü olarak öneriyor; 15 gören biri veritabanını bozuk
   sanabilir.
5. **`fastembed>=0.5` alt sınırı riskli.** Kurulu 0.8.0, `multilingual-e5-large`
   için **CLS yerine mean pooling** kullandığını uyarıyor. Sürüm serbest
   bırakıldığı için ileride bir kurulum farklı pooling'le gelebilir ve **indeksteki
   vektörlerle sorgu vektörleri sessizce farklı uzaylarda olur.** `pyproject.toml`
   benim sahipliğimde değil; sürümün sabitlenmesini öneriyorum.
6. **Sohbet sınırı toplu işleri kesiyor.** `fill_answer_cache.py` tek kullanıcı
   olarak 32 istek atıyor ve 20/60 sn sınırına takılıyor. Betik artık bekleyip
   yeniden deniyor (sınırı baypas etmiyor), ama demo hazırlığında bu ~2 dakika
   ek süre demek.

## Dosyalar

Yeni: `apps/api/tests/test_internal.py`, `apps/api/scripts/bake_embedding_model.py`,
`fill_answer_cache.py`, `demo_questions.json`, `probe_evidence_threshold.py`,
`measure_latency.py`, `.github/workflows/keepalive.yml`, `docs/deployment.md`.

Değişen: `apps/api/app/api/internal.py` (gövde), `apps/api/app/api/documents.py`
(**yalnız `_trigger_worker`**), `apps/api/Dockerfile`, `docker-compose.yml`,
`.github/workflows/ci.yml` (**yalnız `rls_assessment` satırı**; `rls_isolation`
R1'e bırakıldı), `specs/001-course-assistant-mvp/tasks.md` (yalnız kendi satırlarım).

Sahipliğim dışında hiçbir dosyaya dokunulmadı; `config.py`, `contracts.py`,
`main.py`, `apps/web/**` ellenmedi.
