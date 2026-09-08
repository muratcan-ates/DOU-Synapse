# C1/C3 — ANN yolunun geri kazanılması ve eşitlik sınırlarının sertleştirilmesi

**Durum: yerel plan, kaynak ve erişim mekanikleri doğrulandı; hashing holdout Recall@5 gerilemesi nedeniyle C1 non-regression kabulü açık.** Tarih: 8 Eylül 2026. Bu kayıt geliştirme adayının yerel kanıtıdır. C1'i bütün kabul maddeleriyle kapatmaz; C3 için ölçümlerin kapsamını ve izlenebilir kaynaklarını verir. C2 göçü uygulanmadı. Üretim hazırlığı, gerçek model kalitesi veya CI sürüm eşdeğerliği iddiası yoktur.

## Değişiklik ve kabul edilen davranış

Önceki dense sorgu, en yakın komşu aramasının iç sıralamasına belge UUID'si ve parça sırası ekliyordu. Yeni sorguda iç sıralama yalnız uzaklık operatörüdür; `MATERIALIZED` aday kümesi `limit × retrieval_dense_candidate_multiplier` ile sınırlanır. Çarpan varsayılan 8, geçerli aralık 1–8'dir. `hnsw.iterative_scan=relaxed_order` aynı işlem içinde etkinleştirilir. Dış sorgu uzaklık, `documents.file_hash` ve `chunk_index` ile sıralar; tam kaynak sütunları ve belge birleşimi korunur. `fts.py` de LIMIT öncesinde ve sonrasında içerik hash'i/parça sırasını kullanır.

Çarpanı azaltmak daha küçük aday kümesi karşılığında recall kaybı yaratabilir; farklı değerin kabulü ayrıca ölçülmelidir. Değişiklik yeni şema veya indeks yeniden kurulumunu gerektirmez. Mevcut geliştirme veritabanının sıfırlanması gerekmez.

İlk runtime deneyinin ortaya çıkardığı ikinci sorun, psycopg hazırlanan ifadelerinin `auto` altında generic plana geçmesiydi. Son aday, çağıranın `plan_cache_mode` değerini okur; yalnız dense SELECT ve sonuçların materyalizasyonu boyunca işlem-yerel `force_custom_plan` kullanır, başarılı sorgudan sonra eski değeri geri getirir. Embedding-space uyumsuzluk ve DTO işlemleri geri yüklemeden sonra yapılır. FTS önceki politikayı kullanır. SQL hatası veya iptal özgün haliyle yukarı taşınır; mevcut çağıran UoW rollback'i işlemi temizler. Retrieval kendi başına bütün UoW'yi rollback etmez ve bozuk işlemde ek restore SQL'iyle asıl hatayı maskelemez.

Bu seçim PostgreSQL'in custom/generic prepared plan ayrımıyla uyumludur; belgedeki plan seçme kuralı bu proje için hızlanma kanıtı değildir. Hız sonucu aşağıdaki gerçek sayaç ve ölçümlere dayanır. [PostgreSQL 16 PREPARE](https://www.postgresql.org/docs/16/sql-prepare.html)

## Ölçüm zinciri ve ilk deneyin sınırı

| Kayıt | İçerik | Karar |
|---|---|---|
| Plan V1, `retrieval-plan-local-20260908a.json` | 20 bin sentetik vektör; adaylar daha az sütun döndürüyordu | Ön bulgu olarak saklandı; adil hız karşılaştırması sayılmadı |
| Plan V2, `retrieval-plan-local-20260908b.json` | Üç kolun tam kaynak projeksiyonu ve dış belge birleşimi eşitlendi | Yoğun SQL için sınırlı plan/ANN karşılaştırması |
| Runtime V1, `retrieval-runtime-local-20260908.json` | Gerçek HybridRetriever, SQLAlchemy/psycopg, varsayılan hazırlama eşiği | İlk adayın auto/generic HNSW kaybını gösterdi |
| Runtime V2, `retrieval-runtime-local-v2-20260908.json` | Aynı klon ve SQL; yalnız dense plan politikası düzeltmesi | Ölçülen dense çağrılarda custom plan ve önceki moda dönüş doğrulandı |

Ön deneyin ham dosyası değiştirilmedi. Güncel benchmark, pre-C1 SQL'i sabit SHA256 ile doğrulanan `scripts/fixtures/018_pre_c1_dense.sql` dosyasından alır. `--baseline-report` yalnız bilinen V2 kaynak/SQL ispatıyla eşleşen raporu kabul eder; bir raporun keyfi SQL'ini çalıştıran mekanizma değildir. Ölçüm anındaki kaynaklar ve son adayın kaynakları ayrı hashlerle tanımlanır. Kirli çalışma ağacında yalnız Git SHA adayın tamamını tanımlamaz.

## Eş projeksiyonlu V2 yoğun SQL deneyi

Kurulum: PostgreSQL 16.14/Homebrew ARM64, veritabanı `vector` uzantısı 0.8.0; 20.000 sıfır olmayan 1.024 boyutlu sentetik vektör; seed 18026. Geniş ders 17.152, dar ders 400 kayıt; ilgisiz ders, seçili/boş belge, üye olunmayan ders ve iki UUID yerleşimli eşitlik kümeleri ayrıca bulunur. 14 vaka × 3 kol × 2 ef_search × 7 ölçüm = 588 zamanlanan sorgu. Her kol için bir ısınma; p95 yedi örneğin en yüksek örneğine karşılık gelen nearest-rank hesabıdır.

Ölçüm gerçek, RLS bypass yetkisi olmayan `dou_app` rolü ve zorunlu RLS altında yapılmıştır. Karşılaştırılan kollarda indeks planı zorlanmadı. Yalnız exact oracle kendi işleminde indeks/bitmap taramalarını kapatır. **RLS kapalı ikinci A/B/C kolu bu yeni ölçümde koşulmadı:** bu rapor RLS'nin bağımsız maliyetini veya runbook'taki RLS'siz maddeyi tamamladığını iddia etmez.

Psycopg `prepare_threshold=None` olduğu için bu deney parametreye özgü, adlandırılmamış ifadeleri ölçer. Runtime prepared/generic plan davranışının eşdeğeri sayılmaz. Aday hem MATERIALIZED, hem ×8 ön getirme, hem relaxed iterative scan içerdiği için fark tek başına MATERIALIZED etkisi diye ayrıştırılamaz.

Varsayılan `ef_search=40`, geniş ders, limit 24:

| Sorgu / kol | p50 / p95 (ms) | Strict Recall@24 | Dönen | Doğal HNSW |
|---|---:|---:|---:|---|
| q0 eski SQL | 89,647 / 94,072 | 1,000 | 24 | Hayır |
| q0 saf operatör CTE | 1,370 / 1,526 | 0,708 | 24 | Evet |
| q0 MATERIALIZED ×8 | 3,312 / 3,618 | 1,000 | 24 | Evet |
| q1 eski SQL | 91,047 / 92,990 | 1,000 | 24 | Hayır |
| q1 saf operatör CTE | 1,391 / 1,527 | 0,792 | 24 | Evet |
| q1 MATERIALIZED ×8 | 3,227 / 3,636 | 1,000 | 24 | Evet |

Saf operatör CTE, sonuç sayısı tam olsa bile exact komşuları kaçırdığı için seçilmedi. `ef_search=100` ile strict recall q0/q1 0,917/0,958'e yükselse de tam olmadı. MATERIALIZED ×8 kolunda iki geniş sorguda ef40 ve ef100 strict recall 1; ef100 p50 3,199/3,236 ms. Bu iki sentetik sorgu varsayılan ef40'ı yükseltmek veya bütün içeriklerde recall 1 garantisi vermek için yeterli değildir.

Eşitlik penceresine sığan iki UUID yerleşiminde aday içerik anahtarları aynı, eski SQL farklıdır. Pencereden büyük eşitlik kümelerinde strict exact-altküme recall'ı 0 olup tie-aware recall 1 olabilir: seçilen parçalar eş uzaklıktadır, ancak sınırlı aday kümesinden global içerik sırasının ilk 24'ü garanti edilemez. Bu vakalar doğal exact plan seçmiştir; HNSW'de taşan eşitlik kümeleri için evrensel deterministik altküme ispatı değildir. Küçük/filtreli korpuslarda doğal exact planın seçilmesi hata sayılmadı.

## Gerçek prepared runtime kusuru ve düzeltmesi

İki runtime koşusu aynı `dou018_retrieval_runtime1` klonunu, sorgu vektörlerini ve SQL gövdelerini kullanır. Her koşu kendi tek fiziksel bağlantısını sabit tutar; PID her vaka işleminde denetlenir (V1: 5621; V2: 8246). SQLAlchemy 2.0.52 ve psycopg 3.3.4 varsayılan `prepare_threshold=5` ile çalışır. Kanonik `SyntheticReplayProvider` mevcut vektörleri döndürür; `space_of()` veya embedding-space kontrolü değiştirilmez. Bu gerçek sürücü/uygulama SQL yoludur; gerçek embedding sağlayıcısı değildir.

Klonun 20 bin satırlık içerik/vektör/metadata hash'i önce ve sonra aynıdır: `045f0e35a394b30618475e01fe4def65e3197e6770a3507a5418bc356540a7a5`. Yalnız klondaki embedding-space etiketi sağlayıcının kanonik değerine taşındı; ilk ölçüm veritabanı ve raporu korunmuştur. Ayrıntılar `c1-runtime-clone.json` içindedir.

Her runtime koşusunda 14 vaka × 3 plan modu; vaka başına 12 ısınma ve 7 ölçüm vardır. 504 ısınma ve 294 ölçülen HybridRetriever çağrısı yapılmıştır. V1 toplam 18,503 s; V2 toplam 12,511 s. Toplam çalışma süresinden ürün gecikme oranı çıkarılmadı.

V1 auto modunda broad dense sorgusu generic planda 17.152 parçayı bitmap tarayıp sıralıyordu; HNSW yoktu. Force-custom aynı prepared ifadede HNSW kullandı. Düzeltme sonrası sayaçlar:

| Mod | V1 dense generic/custom artışı | V2 dense generic/custom artışı | V2 FTS generic/custom artışı |
|---|---:|---:|---:|
| auto | 84 / 14 | 0 / 98 | 84 / 14 |
| force_custom_plan | 0 / 98 | 0 / 98 | 0 / 98 |
| force_generic_plan | 98 / 0 | 0 / 98 | 98 / 0 |

Sayaçlar zamanlanan sorgulardan önce/sonra alındı. Sonraki `EXPLAIN EXECUTE`, aynı prepared ifadenin aynı bağlantıda ayrı ek çalıştırılmasıdır; zamanlanan SELECT'in doğrudan plan kaydı değildir. Dense EXPLAIN'i geçici custom modda, FTS EXPLAIN'i önceki modda yapılır. Sayaç farkları bu ek çalıştırmaları içermez. Her ölçülen çağrıdan sonra önceki `plan_cache_mode` değeri ayrıca kontrol edilir.

Gerçek HybridRetriever çağrısı; FTS, Python, sorgu vektörünün aktarılması ve füzyon dahil:

| Mod / sorgu | V1 p50 / p95 (ms) | V2 p50 / p95 (ms) |
|---|---:|---:|
| auto q0 | 145,839 / 224,831 | 56,138 / 58,340 |
| auto q1 | 141,727 / 143,260 | 56,582 / 60,480 |
| force_custom_plan q0 | 55,870 / 58,157 | 60,252 / 83,032 |
| force_custom_plan q1 | 56,047 / 57,578 | 55,966 / 57,893 |
| force_generic_plan q0 | 140,452 / 143,167 | 55,914 / 58,597 |
| force_generic_plan q1 | 141,531 / 143,836 | 56,204 / 57,661 |

Auto geniş sorgularda gözlenen p50 azalışı %61,51 ve %60,08'dir. Diğer auto vakalarda p50 farkı −1,541 ile +1,393 ms; dar q1'de 4,802 → 6,195 ms artış vardır. Ek GUC sorgularının küçük işlere maliyeti gizlenmez. İki sabit sıralı yerel koşu üretim SLO'su veya rastgeleleştirilmiş çoklu performans deneyi değildir. V1/V2 iki C1 adayıdır; burada pre-C1 bütün HybridRetriever performans kolu yoktur. Yoğun SQL V2 süreleriyle runtime süreleri birbirine bölünmez.

V2 auto broad dense ek EXPLAIN q0/q1 3,120/3,061 ms ve HNSW; FTS 50,845/50,316 ms. Bu sentetik etiket sorgularındaki yaklaşık 50 ms FTS maliyeti sürüyor; eldeki deney eski/yeni FTS performans regresyonunu ölçmez.

## Kaynak, yetki, iptal ve test kanıtları

Runtime V1/V2'nin 294 ölçümünde aynı vaka için dönen içerik anahtarları, sıra ve dense/FTS/hybrid sayıları eşittir. Boş belge listesi ve üye olunmayan ders için 84 negatif gözlemde üç kol da sıfır döndürür. İzinli vakalarda dense 24/hybrid 8 sınırı ve 1.680 dönen kaynağın dosya/konum bilgisi denetlenir. Gerçek `dou_app` bypass yetkisi taşımaz; `chunks` ve `documents` RLS zorunludur. Bu sonuçlar bütün olası yetki senaryolarını tüketmez.

Ayrı regresyon testleri None/boş/seçili belge farkını; tam metadata projeksiyonunu; limit×çarpan sınırını; yabancı belgeyi; üye olmayan ve üyeliği kaldırılmış kullanıcıyı; aynı içerik farklı UUID ile yeniden yüklendiğinde dense/FTS sırasını denetler. Runtime probe'un farklı UUID vakaları farklı FTS etiketleri kullandığından bunların hybrid karşılaştırması aynı-sorgu yeniden yükleme testi olarak kullanılmaz.

GUC için gerçek DB testleri üç önceki modda dense sonrası ve FTS öncesi geri yüklemeyi; aynı fiziksel bağlantıda SQLSTATE 22012 sonrası çağıranın bekleyen yazısı ve GUC'nin rollback ile temizlenmesini; çalışan `pg_sleep` iptali sonrası bağlantı yeniden kullanıldığında veya sürücü tarafından değiştirildiğinde temiz politikayı denetler. Özgün hata/CancelledError korunur; rollback sorumluluğu çağırandadır.

Son bütün API koşusu **1500 geçti, 5 bilinen PyMuPDF uyarısı, 91,01 s**: `bc-full-api-second.log`. Yeni aday dosyasındaki 12 gerçek DB vakası bu paketin içindedir. Odak çevrimdışı koşu 168 geçti, 12 DB vakası ayrıldı. Aynı gerçek regresyon oracle'ında, yalnız ayrı süreç belleğinde yapılan mutasyonlar custom planı kapatınca 9 test, önceki modu geri yüklemeyince 6 test düşürdü; depo kaynağı mutasyonla yazılmadı. Ayrıntılı log/hash zinciri `c1-final-source-manifest.json` içindedir.

Ölçümden sonra yeni açıklamalar Türkçeleştirildi. `c1-guc-comments-only-bridge.json`, önce/sonra kaynak hashleri ve yorum/docstring hariç AST eşitliğiyle davranış bağını korur. Dört testte sonraki import sırası düzeltmeleri davranış değiştirmez; son manifest bunların güncel hashlerini taşır. Bağımsız analiz üretim kaynağını değiştirmedi; rapor root entegrasyonunda sürümlendi.

## Sürüm, C2 ve henüz tamamlanmamış kabuller

Ölçülen veritabanı uzantısı **pgvector 0.8.0**'dır. Python istemci paketi `pgvector==0.5.0` ayrı bir sürümdür; uzantı sürümü yerine kullanılmaz. CI yapılandırması resmi `pgvector/pgvector:0.8.6-pg16-bookworm` imajını `sha256:a36250871de0833b8757561c72f2477ef1ddd1101afa4e617fb552e0de514c6b` digest'iyle sabitler (`.github/workflows/ci.yml`). Bu imaj seçimi, yerel 0.8.0 ölçümünün 0.8.6'da koşulduğu anlamına gelmez; C1 ölçüm matrisi için 0.8.6 eşdeğerliği bu raporda koşulmadı.

Resmi 0.8.0 belgesi iterative scan desteğinin bu sürümde bulunduğunu ve relaxed sonuçların materialized CTE sonrasında tekrar sıralanabileceğini anlatır. Aynı belge HNSW grafiğinin `maintenance_work_mem` içine sığmasının indeks kurulumunu hızlandırdığını belirtir; taşmanın recall'ı bozduğu sonucunu vermez. [pgvector v0.8.0: iterative scans ve index build time](https://github.com/pgvector/pgvector/blob/v0.8.0/README.md#iterative-index-scans)

**C2 açık:** bu deneyde indeks seed öncesi oluşturulup kayıtlar artımlı eklenmiştir; farklı build-memory ayarlarıyla yeniden indeks kurma müdahalesi yoktur. Sorgu planlarında geçici disk sıralaması görülmemesi indeks kurulum belleği hakkında kanıt değildir. Memory-spill → recall kaybı nedenselliği için aynı korpus/query/exact oracle, sabit build parametreleri ve kontrollü tekrarlı build-memory kolları gerekir. Bu ölçülmeden `0021_hnsw_build_guard.sql` veya 2 GB zorunluluğu eklenmedi; runbook'taki eski gözlem genel kabul edilmiş neden olarak tekrarlanmadı.

**Holdout tamamlandı; kabul başarısız:** mevcut gerçek upload/worker yoluyla22 dosya ve167 hashing parçası oluşturuldu. `71d5ff6` içindeki gerçek üç retrieval kaynağı ile güncel aday, aynı korpus/query/config üzerinde mevcut harness üzerinden çalıştı.127 soru soruldu;105 kaynaklı soru skorlandı. Her iki kolda127 deneme,0 retry,0 failure; LLM çağrısı yok.13 bağımsız denetim eski kaynak snapshotlarını, güncel kaynak/ortak bağımlılık/altın set hashlerini, ham sonuç hashlerini, sorgu sırasını, öğrenci RLS kimliğini ve kayıtlı önce/sonra korpus eşitliğini doğruladı. Hashing namespace `hashing/hashing-v1@builtin-1`; ham metadata'daki E5 model adı kullanılan sağlayıcıyı temsil etmez.

| Holdout ölçütü | Eski | Aday | Sonuç |
|---|---:|---:|---|
| Recall@5 |78/105 = 0,742857|77/105 = 0,733333|−0,009524; non-regression başarısız|
| Recall@8 |80/105 = 0,761905|80/105 = 0,761905|Toplam aynı; kaybedilen/kazanılan örnek farklı|
| MRR |0,618175|0,634444|+0,016270|

H-121'de (`10-security-and-protection.pdf`, sayfa2; yetenek tabanlı erişim sorusu) ilk doğru kaynak3→6'ya indi; tek Recall@5 kaybı budur. H-068'de (`producer_consumer.py`, consume/produce sıralama sorusu) doğru kaynak6'dan ilk8 dışına çıktı. H-114'te doğru kaynak ilk8 dışından8'e girdiği için toplam Recall@8 değişmedi.105 soruda ilk doğru kaynak sırası98'inde aynı,5'inde iyi,2'sinde kötüdür. MRR artışı Recall@5 kaybını telafi etmiş kabul edilmez.

Mevcut eşleştirilmiş bootstrap10.000 tekrar/sabit tohumla bağımsız yeniden hesaplandı: Recall@5 farkının %95 aralığı [−0,028571;0], MRR farkının aralığı [−0,000794;0,038095]. Sıfırı içeren aralıklar genel istatistiksel hükmü sınırlar; deterministik gerilemeyi veya sıkı non-regression kapısının kırmızı sonucunu değiştirmez. Eşik ve altın set değiştirilmedi. Sonuç gerçek embedding/LLM kalite veya performans raporu değildir; hashing uyarısı korunmuştur.

Son listelerden dense, FTS veya füzyon katkıları ayrılamıyor. Sonraki dar inceleme aynı korpusta iki kolun ham dense/FTS aday sırası ve eşit skorlarını salt okunur izlemek olmalı; holdout sorusuna özel kural veya eşik ayarı yapılmamalı. Ayrıntılar `c1-holdout-analysis.{md,json}`; ham ölçüm `c1-holdout-measured-01/manifest.json` ve iki kol sonucundadır. Korpus test veritabanı korunmuştur; analiz DB'yi değiştirmedi.

C3 için bu raporun depo belgesine aktarılması, son kaynak manifestinin entegrasyon kaydıyla bağlanması ve bekleyen kabul maddelerinin açık işaretlenmesi root entegrasyonunun sorumluluğundadır. Bu taslak C1/C2/C3'ü topluca bitmiş göstermez.

## Yerel kanıt dizini

Tüm aşağıdaki dosyalar `/private/tmp/dou018-evidence/` altındadır:

- `retrieval-plan-local-20260908a.json`: ön deney; SHA256 `78748275e7d34ace9554f2774f40d185a4616321265698d0bf005075596251d8`.
- `retrieval-plan-local-20260908b.json`: eş projeksiyon; SHA256 `34beb08b8c3a3bb8d9975147f7d04af5bcfca42c47add1b870819370287c07ca`.
- `retrieval-runtime-local-20260908.json`: ilk prepared deneyi; SHA256 `52c1c3c2a4ce297e11c96a5b08f26479ae1b9e4afb2cd7a4fae34e1cc875170c`.
- `retrieval-runtime-local-v2-20260908.json`: dar GUC düzeltmesi; SHA256 `5c965d4d3b1e67fc4267a77366e4e2f24d8cb6570a46c934534d18d5507c588b`.
- `c1-runtime-clone.json`, `c1-runtime-analysis.{md,json}`, `c1-runtime-v2-analysis.{md,json}`: klon ve bağımsız sayısal analiz.
- `c1-final-source-manifest.json`, `c1-guc-comments-only-bridge.json`: son kaynak ve davranış köprüsü.
- `bc-full-api-second.log`, `c1-guc-offline-tests.log`, `c1-guc-mutation-disable-custom.log`, `c1-guc-mutation-leak-custom.log`: test çıktıları.
- `c1-holdout-runbook.md`, `c1_holdout_runner.py`, `c1-holdout-adapter-unit.log`: holdout kurulumu ve 4 başarılı çevrimdışı çalıştırıcı testi.
- `c1-holdout-measured-01/manifest.json`, aynı klasörde iki ham sonuç ve paired rapor; `c1-holdout-analysis.{md,json}`: gerçek mekanik Recall@5 gerilemesi ve bağımsız denetim.
- `c1-holdout-corpus-01.{json,log}`, `c1-holdout-pair-01.log`: gerçek upload/worker kurulumu, hashing uyarısı ve ölçüm çıktıları.

Ham ölçümlerin root tarafından `specs/018-codex-production-line/evidence/c1-*` altına gzip/hash ile arşivlenen kopyaları ayrıca mevcuttur; arşiv manifesti orijinal ham hashleri korur.

## Sürümlü kanıtları açma

[Arşiv manifesti](bc-archive.json) bu raporun holdout/son-kaynak/görsel/log kopyalarını bağlar; [ilk ölçüm arşivi](c1-measurement-archive.json) dört büyük plan/runtime raporunu bağlar. JSON gzip kopyaları açıldığında ham SHA256 aynıdır. Metindeki /private/tmp yolları özgün yakalama konumudur, tek kalıcı kanıt olarak kullanılmaz. Snapshot çalıştırıcı yerel deneye ait sabit repo/DB yollarını taşır; dağıtım aracı değildir. Yalnız sentetik örnek materyal kullanılmıştır.
