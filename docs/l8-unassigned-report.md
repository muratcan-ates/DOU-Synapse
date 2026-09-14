# L8 — atanmamış iş şeridi raporu

Dal: `018-l8-unassigned` · Taban: `018-codex-production-line` @ `22a85d390f759a77265e624d4d2acdf9b7c3d143`
Şerit sözleşmesi: [`.ai/lane-l8.md`](../.ai/lane-l8.md) · Ölçüm tarihi: 14 Eylül 2026

## Bu şerit neden var

`.ai/agent-queue.md` L1–L7 şeritlerini sahiplendirir ama sekiz işi sahipsiz bırakır:
altısı **"atanmamış"** (`E2`, `E3`, `E4`, `E6`, `D5'`, `H5`), ikisi **"atlanan"**
(`A8'`, `A9`). Atlananların ikisi de aynı nedenle durdu: onaylanmamış bir üçüncü parti
bağımlılık (`vulture`, `knip`, `pytest-cov`, `diff-cover`) ve bu depoda manifest/lock
dosyalarına dokunulmaması kuralı.

Bu şeridin duruşu: **bağımlılık beklemek bir mekanizmayı beklemektir, değeri değil.**
Aynı değerin çekirdeği Python 3.12 standart kütüphanesi (`ast`, `sys.monitoring`) ve
Node yerleşikleriyle üretilebilir. Üretilemeyen kısım (gerçek sağlayıcı koşusu, iki insan
etiketleyici, gözlem platformu) ENGEL olarak açıkça kalır ve **tamamlandı sayılmaz**.

## Ölçüm — birleşme hedefinin üstünde

Bu şerit ilk kurulduğunda taban `22a85d3`'tü. İş sürerken entegrasyon dalı **64 commit**
ilerledi (`grading.py` +189/−40, `schemas/assessment.py` +47/−1, `apps/web` 63 dosya).
Eski tabanda alınan sayılar birleşecek ağacı tarif etmediği için şerit o tabana
**yeniden oturtuldu** ve bütün ölçümler sıfırdan alındı. Aşağıdaki her sayı
`6f56a48` üstünde, 14 Eylül 2026'da ölçülmüştür.

Sayılar tarihsel kayıttır, canlı sayaç değildir; `docs_check` işaretleri buna göredir.

| Kapı | Taban (L8 yokken) | L8 ile | rc |
|---|---|---|---|
| mypy | 121 dosya <!-- docs-check: tarihsel 121 · 2026-09-14 --> | 123 dosya, temiz <!-- docs-check: tarihsel 123 · 2026-09-14 --> | 0 |
| pytest (toplanan) | 1907 <!-- docs-check: tarihsel 1907 · 2026-09-14 --> | 2088 <!-- docs-check: tarihsel 2088 · 2026-09-14 --> | — |
| ruff check | temiz | temiz | 0 |
| ruff format | — | 228 dosya biçimli <!-- docs-check: tarihsel 228 · 2026-09-14 --> | 0 |
| bun test lib/ | — | 632 geçti, 0 başarısız <!-- docs-check: tarihsel 632 · 2026-09-14 --> | 0 |
| bunx tsc --noEmit | — | — | 0 |
| contrast.mjs | — | tüm çiftler AA / 1.4.11 | 0 |
| migration_check | — | 24 göç <!-- docs-check: tarihsel 24 · 2026-09-14 --> | 0 |
| workflow_policy_check | — | PASS | 0 |

Fark tam olarak bu şeridin eklediğidir: **+181 test**, **+2 mypy dosyası**.

### Bu şeridin kendi kapıları

| Kapı | Sonuç | rc |
|---|---|---|
| `pytest tests/test_assessment_quality.py tests/test_grading_second_pass.py tests/test_rater_agreement.py tests/test_acceptance_packet.py` | **181 geçti** <!-- docs-check: tarihsel 181 · 2026-09-14 --> | 0 |
| `unittest scripts.test_dead_code_check scripts.test_diff_coverage_check` | **49 geçti** <!-- docs-check: tarihsel 49 · 2026-09-14 --> | 0 |
| `node --test scripts/test_unused_exports_check.mjs` | **28 geçti**, 0 başarısız <!-- docs-check: tarihsel 28 · 2026-09-14 --> | 0 |
| `dead_code_check.py apps/api/app` | 123 dosya, 1107 tanım, 904 denetlendi, 203 muaf, **1 aday** <!-- docs-check: tarihsel 1 · 2026-09-14 --> | 0 (uyarı kipi) |
| `unused_exports_check.mjs --root apps/web` | **77 ölü export / 633** <!-- docs-check: tarihsel 77 · 2026-09-14 --> | 0 (uyarı kipi) |
| aynısı `--strict` ile | aynı bulgular | 1 |

### Tam süit: 1 başarısız / 2087 geçti — başarısızlık bu şeride ait değil

```
1 failed, 2087 passed, 5 warnings, 38 subtests passed in 286.52s
FAILED tests/test_event_loop_blocking.py::TestIngestionLoopUnaffected::
       test_belge_islenirken_saglik_yoklamasi_kesintisiz_yanit_verir
```

Bu test, belge işlenirken API'nin event loop'unun **duvar saati** tepkisini ölçüyor
(`WORKER_DRAIN_URL` tanımsızken ayrıştırma ve embedding aynı süreçte koşuyor). Yani
doğrudan makine yüküne duyarlı.

Başarısızlık `load average ≈ 55–75` iken alındı. Aynı dosya, makine boşaldığında
**arka arkaya iki kez 3/3 geçti**. Bu şeride ait olmadığı ayrıca kanıtlandı: bu
şeridin eklediği modüllerin `apps/api/app` ve `evaluation` içinde **hiçbir çağıranı
yok** (ölçüldü), dolayısıyla o testin ölçtüğü pencerede çalışamazlar.

Bu bir **kararsız (flaky) test** kaydıdır, bir regresyon kaydı değil. `H1` işi
(üç ardışık Playwright koşusu, karantina) L6'ya ait; bu Python tarafındaki eşdeğeri
henüz kimseye atanmamış görünüyor ve ayrı bir iş olarak açılmalı.

### `migration_check` çağrısı bayatladı — AGENTS.md güncellenmeli

Entegrasyon dalı `0028` numarasını rezerve etti. `AGENTS.md`'deki kapı satırı hâlâ
`--allow-gap 0017 0021 0022 0023` diyor ve bu ağaçta **kırmızı yanıyor**:

```
MIGRATION_CHECK=FAIL
  - boşluk: 0028 yok (0001–0029 aralığında).
```

Doğru çağrı `--allow-gap 0028` eklenmiş hâlidir ve `MIGRATION_CHECK=PASS (24 göç)` verir.
`AGENTS.md` L1'in yüzeyidir; bu şerit satırı düzeltmedi, bildirdi.

### Yüklü makinede alınan kırmızı ölçüm kanıt değildir

İlk taban denemesi `load average ≈ 870` iken koşturuldu (yedi paralel oturum aynı
PostgreSQL örneğini doyuruyordu) ve 1689 testin **tamamı** fixture hatasıyla `ERROR`
verdi. Makine boşaldığında aynı ağaçta aynı komut 1689 `passed` verdi. Kod değişmedi.
Bu kayıt, ileride benzer bir kırmızıyı kod kusuru sanmamak için buradadır.

## Bu şeridin ürettikleri

Beş teslim, hepsi **yeni dosya**; hiçbir mevcut dosya değiştirilmedi.

### E4/1 — MCQ kalite sinyalleri
`apps/api/app/modules/assessment/quality.py` · testi `apps/api/tests/test_assessment_quality.py`

Sekiz ölçülebilir sinyal: yakın-tekrar soru, aynıya normalleşen iki şık, kapsayıcı şık
("hepsi"/"hiçbiri"), doğru şıkkın uzunluk aykırılığı, dilbilgisel paralellik kırılması,
beyan edilmemiş yanılgı etiketi, hiç test edilmemiş yanılgı, aşırı kullanılmış yanılgı.
Saf modül: veritabanı, ağ ve LLM yok. Bulgu bir **red kararı değildir** — eğitmenin
inceleme kuyruğunu sıralar.

Türkçe normalleştirme `app/core/text_tr` ile yapılır, `str.lower()` ile değil; test bu
farkın gerçekten önemli olduğunu önce kanıtlıyor (`"İŞLEM".lower() != "işlem"`), sonra
modülün ikisini de yakaladığını gösteriyor.

**Bu şeridin kendi kodunda bulup kapattığı fail-open:** `similarity(..., ngram=0)`
çağrısı boş dilim üretiyor, iki metnin n-gram kümesi de `{""}` oluyor ve **her çift
1.0 benzerlik** alıyordu — yani tek bir yanlış parametre yakın-tekrar kapısını "her soru
her sorunun tekrarıdır" diyecek biçimde açıyordu. Artık `ValueError`; üç regresyon testi
sınırı kilitliyor.

### E4/2 — sıralı rubrik için ağırlıklı kappa
`evaluation/rater_agreement.py` · testi `apps/api/tests/test_rater_agreement.py`

`evaluation/metrics.py:365` içindeki `label_agreement` **nominal** Cohen's kappa'dır:
1 puan ile 4 puan arasındaki anlaşmazlığı, 3 ile 4 arasındakiyle aynı sayar. Rubrik puanı
sıralıdır; bu yanlış istatistiktir. Yeni modül nominal + lineer + kuadratik (QWK) kappa'yı
birlikte, tam boyutlu karışıklık matrisi, kategori dağılımı, bootstrap güven aralığı ve
`sample_size_warning` ile döndürür.

**Hiçbir eşik sabiti yazılmadı.** QWK eşiği insan-insan uyumundan türetilir; o ölçüm
yapılmadı. Testlerden biri modülde eşik sözcüğü taşıyan isim ve raporda `bool` karar alanı
bulunmamasını doğrudan kontrol eder.

### E4/3 — rubrik ikinci doğrulayıcı
`apps/api/app/modules/assessment/second_pass.py` · testi `apps/api/tests/test_grading_second_pass.py`

İki bağımsız rubrik değerlendirmesini **kalem kalem** uzlaştırır ve üç sonuçtan birini
verir: `agreed` (puan gösterilebilir), `escalate` (insana gider), `inconclusive`
(gösterilemez). Tolerans sabit değil, kalemin ölçek genişliğinden türetilir.

Kritik olan iki fail-closed davranış:
* İkinci koşu **yoksa** sonuç `inconclusive`'dir, `agreed` değil — yoksa mekanizma
  sessizce tek-koşuya döner ve hiçbir şey söylemeden kapanırdı.
* `tolerance_percent >= 100` reddedilir: tolerans kalemin tüm genişliğine eşitlenirse
  hiçbir ayrışma eşiği aşamaz, yani doğrulayıcı kapanır ama `agreed` demeye devam eder.

Toplam puanları eşit olan iki koşu kalem dağılımında taban tabana zıt olabilir; bu yüzden
karşılaştırma kalem düzeyindedir ve o tuzak ayrıca testlidir.

### A9 — bağımlılıksız ölü kod kapıları
`scripts/dead_code_check.py` (+ testi) ve `scripts/unused_exports_check.mjs` (+ testi)

`vulture` ve `knip` yerine, yalnız Python `ast` ve Node yerleşikleriyle. İkisi de
varsayılan **uyarı** kipindedir (rc=0); kapıyı kırmızı yakmak için `--strict` gerekir —
kuyruk "ilk hafta uyarı" diyor.

Python tarafı framework sihrini muaf tutar: dekoratörle kayıtlı route'lar, pydantic
validator'ları, `__all__` ihracı, SQLAlchemy modelleri, dunder/giriş noktaları,
`Depends()` içinde geçen adlar. Muafiyet dağılımı her koşuda raporlanır — kapı neye
bakmadığını gizlemez.

### A8' — bağımlılıksız değişen-satır kapsamı
`scripts/diff_coverage_check.py` (+ testi)

`pytest-cov`/`diff-cover` yerine Python 3.12 `sys.monitoring` (PEP 669). `use_tool_id`
yuvası rezerve edilir (hata ayıklayıcıyla çakışmaz), geri çağrı `DISABLE` döndürür (sıcak
döngüde maliyet taşımaz), payda `co_lines()`'dan gelir (yorumlayıcının LINE olayı
üretebildiği kümeyle birebir).

**Yalancı-yeşil kapatıldı:** hiç çalıştırılabilir satır değişmediğinde araç yüzde
basmaz, "kapsanacak satır yok" der. `--fail-under` varsayılanı **yoktur**; eşik verilmezse
rapor basıp rc=0 döner, çünkü eşik bir insan kararıdır.

### E3 — çevrimdışı kabul paketi
`evaluation/acceptance/packet_offline.py` · testi `apps/api/tests/test_acceptance_packet.py`

`prepare_packet.py` değiştirilmedi; yanına sağlayıcı gerektirmeyen bir yol kondu.
Ölçülen gerçek: **`prepare_packet.py` örnekleme yapmaz ve çıktısı bayt bayt tekrar
üretilebilir değildir** — `manifest.json` içindeki `prepared_at`, `candidate_sha` ve
`candidate_dirty` her koşuda değişir. Yeni yolun baytları yalnız üç girdiden türer:
vaka dosyası, atıf yapılan materyal, tohum.

Paket ikiye ayrılır: etiketleyiciye giden `packet.json` + iki form **çıpasızdır**;
cevap anahtarı yalnız `answer_key.json` içindedir ve verilmez. Örnek kimlikleri cevap
metninin sha256'sından türer — ilk yazımda kimlik `...-correct` biçimindeydi, yani cevap
anahtarını form başlığına sızdırıyordu; bu sızıntı bulunup kapatıldı ve üç testle kilitlendi.

**Varsayılan koşu bilerek kırmızıdır:** E3 en az 25 gerçek örnek ister, depodaki havuzda
13 var. Araç eksik örnek uydurmaz, paket üretmez (rc=2). `--size 13` ile üretilen paket
kendi içine `meets_minimum: false` yazar.

`evaluation/acceptance/README.md` **güncellenmedi** — bu şeridin yüzeyi yalnız yeni
dosyalardır; yeni akış şu an modül docstring'inde ve burada anlatılıyor.

## Bağımsız çapraz doğrulama (şeridin kendi testlerinden ayrı)

Bir modülün kendi testleri, modülle aynı yanlış anlamayı paylaşabilir. Ağırlıklı
kappa hesabı bu yüzden **modülden habersiz, sıfırdan yazılmış ikinci bir uygulamayla**
karşılaştırıldı: yedi veri kümesi × üç ağırlık şeması (kuadratik, lineer, nominal),
gözlenmemiş kategori ve "beklenen uyum 1.0 → tanımsız" kenar durumları dahil.

```
$ apps/api/.venv/bin/python <bağımsız referans betiği>
QWK_REFERENCE_MISMATCHES= 0
```

Referans betik geçici bir dosyadır, depoya girmez; değeri tek seferlik bir çapraz
kontroldür, kalıcı bir kapı değildir.

## Başka şeridin yüzeyinde bulunan kusurlar (bu şerit DÜZELTMEDİ)

AGENTS.md kuralı 13 başka şeridin yüzeyine dokunmayı yasaklıyor. Aşağıdakiler bu şeridin
işini yaparken ölçülerek bulundu; sahibine bildirilir, burada düzeltilmez.

### BULGU-1 (yüksek) — Türkçe `casefold()` rubrik ölçütünü kaçırıyor, öğrenci 0 alıyor

**Yer:** `apps/api/app/modules/assessment/grading.py:446,449` (ayrıca 218, 219, 383, 406, 514) — **sahip: L2**

`_rubric_breakdown`, modelin döndürdüğü ölçüt adını eğitmenin rubriğindeki adla
`str.casefold()` ile eşleştiriyor. `casefold()` Türkçe İ/ı çiftini bilmez:

```
'Adımları'.casefold()  -> 'adımları'
'ADIMLARI'.casefold()  -> 'adimlari'      # ı ≠ i
```

Eşleşme kaçınca `puanlar.get(..., 0)` **0** döndürür ve satır `earned=0` ile yazılır.
Ölçülen tekrar üretim:

```
$ apps/api/.venv/bin/python -c "..."      # _rubric_breakdown eşleştirmesinin birebir kopyası
casefold ile eşleşen puan : 0   <-- öğrenci 100 hak ediyordu
text_tr.fold ile          : 100
```

Depoda tam bu iş için `app/core/text_tr.py::fold` var ve yukarıdaki dört Türkçe çiftin
dördünü de doğru eşliyor; `grading.py` onu bu yollarda kullanmıyor.

**Neden sessiz:** essay (`OpenPayload`) rubriklerinde kapsama kontrolü yok
(`_code_rubric_is_complete` yalnız kod tiplerinde çalışır), bu yüzden ölçütlerin tamamı
kaçsa bile sonuç `graded=True` ve `score=0` olarak yazılır — yani hatalı sıfır, geçerli
bir not gibi görünür ve mastery'ye işlenir.

**Neden burada düzeltilmedi:** `grading.py` L2 şeridinin yüzeyi; aynı düz `casefold`
`_code_rubric_is_complete` içinde de var ve tek taraflı değiştirmek iki yolu ayrıştırırdı.
Düzeltme, iki yolu birlikte `text_tr.fold`'a taşıyan tek bir değişiklik olmalı.

### BULGU-2 (orta) — bu şeridin iki mekanizmasının hiçbir çağıranı yok

`review_pool` (MCQ kalite) ve `reconcile` (ikinci doğrulayıcı) yazıldı, test edildi ve
kapılardan geçti; ama `apps/api/app` içinde ikisini de **hiçbir üretim yolu çağırmıyor**.
Yani bugün öğrenciye giden rubrik puanı hâlâ tek koşudan çıkıyor ve soru havuzu hâlâ
kalite sinyali görmeden onaylanıyor. E4'ün kalan yarısı bu bağlantıdır ve ürün yüzeyi
(L2) kararıdır. Bu şerit mekanizmayı bitirdi; **E4 tamamlanmış sayılmaz.**

### BULGU-3 (düşük) — `contracts.py:317 GradedAnswer` hiçbir yerden referanslanmıyor

A9 kapısının gerçek kod tabanındaki tek adayı. `grading.py`'nin bir yorumu neden
kullanılmadığını açıklıyor (`score: int` taşır, "değerlendirilemedi" durumunu ifade
edemez, FR-020). Silinmedi: `contracts.py` ekipler arası sözleşme yüzeyi. Doğru çözüm
tanımın üstüne bilinçli-ölü işareti koymak; karar sözleşme sahibinin.

### BULGU-4 (orta) — `evaluation/` CI'da hiç lint'lenmiyor ve iki yapılandırma uzlaşmaz

**Yer:** `.github/workflows/ci.yml:70` — **sahip: L1**

CI'ın lint adımı `apps/api` içinden `ruff check .` koşuyor; depo kökünde hiçbir ruff
yapılandırması yok. Sonuç: `evaluation/` ağacı **hiçbir lint kapısından geçmiyor**.
Ölçüldü:

```
$ ruff check --config apps/api/pyproject.toml evaluation/     -> Found 39 errors
$ ruff check evaluation/ --line-length 100                    -> Found 7 errors
```

Daha kötüsü, iki yapılandırma aynı satırda **karşıt** şey istiyor:

| | `# noqa: S311` VAR | `# noqa: S311` YOK |
|---|---|---|
| `--config apps/api/pyproject.toml` | temiz | `S311` hatası |
| yapılandırmasız (`--line-length 100`) | `RUF100` hatası | temiz |

Yani tek bir dosya iki kapıyı aynı anda geçemez. Bu şerit otoriteyi **`apps/api/pyproject.toml`**
kabul etti, çünkü depodaki tek Python lint yapılandırması odur ve `evaluation/metrics.py:296`
zaten tam olarak aynı `random.Random(seed)  # noqa: S311` kalıbını kullanıyor — yani yerleşik
gelenek budur. Bu şeridin `evaluation/` dosyaları o yapılandırma altında temizdir.

Kalıcı çözüm bir `evaluation/ruff.toml` ya da CI'a ayrı bir `evaluation/` lint adımı
eklemektir; ikisi de L1'in yüzeyi, burada yapılmadı.

## Hâlâ ENGEL olan ve bu şeritte yapılmayan

| id | Neden hâlâ engelli |
|---|---|
| `E2` | Gerçek sağlayıcı e2e değerlendirmesi: Groq/Cerebras anahtarı ve ZDR kararı gerekir. |
| `E3` gerçek koşusu | ≥25 gerçek örnek ve iki bağımsız insan etiketleyici gerekir. Bu şerit yalnız çevrimdışı tekrar üretilebilirliği ve skor hesabını yapar. |
| `E4` eşiği | QWK eşiği insan-insan uyumundan türetilir. Ölçüm yok; bu yüzden kodda **hiçbir eşik sabiti yazılmadı**, yalnız hesap mekanizması ve testi yazıldı. |
| `E6` | İzole üç DSN, yeterli `maintenance_work_mem`, HNSW kurulumu ve gerçek bellek kanıtı gerekir. |
| `D5'` | Tek gözlem platformu / Logfire SDK kararı gerekir. |
| `H5` | ESLint 10 bağımlılık onayı gerekir. |
| `A8'` eşiği | Araç bağımlılıksız yazıldı, ama `--fail-under` **varsayılanı yok**: eşik bir insan kararıdır. |
| `A9` yaptırımı | Araçlar bağımlılıksız yazıldı, ama varsayılan `--warn-only`: kuyruk "ilk hafta uyarı" diyor. |

## Dürüstlük notu

Bu şeritteki hiçbir araç **model kalitesi** veya **üretim hazır oluşu** ölçmez.
Ölü kod kapısı ve kullanılmayan export kapısı statik sinyaldir; değişen-satır kapsamı
testin *varlığını* ölçer, *yeterliliğini* değil; MCQ kalite sinyalleri red kararı değil
inceleme sıralamasıdır; ağırlıklı kappa bir eşik değil bir sayıdır. Her aracın kendi
docstring'i sınırlarını ayrıca yazar.
