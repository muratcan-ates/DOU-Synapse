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
