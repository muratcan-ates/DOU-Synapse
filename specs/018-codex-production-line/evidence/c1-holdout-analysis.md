# C1 hashing holdout incelemesi — 8 Eylül 2026

**İki kol eksiksiz ve karşılaştırılabilir biçimde çalıştı; Recall@5 geriledi. C1'in mekanik non-regression kabulü açık kalmalı.** Mevcut eşik ve altın set değiştirilmedi. Bu inceleme dosyalar üzerinde yapıldı; veritabanı tekrar sorgulanmadı veya değiştirilmedi.

## Kimlik ve yürütme doğrulaması

13 denetim başarılı: üç eski kaynak dosyası `71d5ff640f0d48a08f3967b000485a15035f10c7` commit'indeki gerçek baytlarla aynı; güncel üç aday kaynak, ortak yedi bağımlılık, sekiz değerlendirme kaynağı/altın set ve çalıştırıcı SHA256 değerleri eşleşiyor. Eski modüller ayrı adlarla yüklenmiş ve eski service yalnız eski dense/FTS işlevlerine bağlanmış. Normal aday uygulama modülleri değiştirilmemiş. Karşılaştırma aynı güncel ortak çevredeki üç retrieval dosyasının karşılaştırmasıdır; bütün eski uygulamanın yeniden kurulması değildir.

İki ham sonuç aynı ders/veritabanı, korpus digest'i, ayar fingerprint'i `a2d6c60b7cd0ca6f`, embedding sağlayıcısı ve 127 sorgunun aynı sırasını taşıyor. Her kolda 127 deneme; retry, rate-limit ve failure sıfır; concurrency1. Top-k8, dense24, FTS24, RRF60, evidence threshold0.1 aynı; yeni candidate multiplier8 manifestte ayrıca kayıtlı. Ham sonuç aynı checkout Git SHA'sını taşır; kirli adayın kimliğini kaynak hashleri, eski kolun kimliğini companion manifestteki ayrı snapshotlar belirler.

Holdout v2.0 toplam161 öğeden mevcut harness kurallarıyla127 soru sorar;105 kaynaklı soru skorlanır,22 kapsam dışı soru Recall/MRR paydasına girmez. Bu seçim, her soru metni ve beklenen kaynak, mevcut hash'i değişmemiş altın setle bağımsız eşleştirildi.

Korpus mevcut gerçek upload/worker kurulum yoluyla22 dosyadan üretildi.22 belge `completed`;167 parça ve167 embedding. Dosya hashleri mevcut sabit materyal paketiyle eşleşiyor. Öğrenci bağlamında167 görünür kayıt, `dou_app`, superuser=false, bypassrls=false, `hashing/hashing-v1@builtin-1` namespace ve içerik/vektör/metadata hash'i `d6132e5287c8bbd2b7660830f251374d3d27a797542842b028c05644ccbfc0f0` her iki kolda önce/sonra aynıdır. Hash'i doğrulanan çalıştırıcı iki tabloda forced RLS, read-only işlem ve önce/sonra eşitliğini zorunlu kılar; farklılık olsaydı `phase=complete` üretemezdi. İnceleme bu canlı kontrollerin saklanan sonuçlarını doğruladı; yeni DB denetimi yapmadı.

Ham `embedding_model=intfloat/multilingual-e5-large` alanı ayardaki kullanılmayan model adıdır. Gerçek sağlayıcı `HashingEmbeddingProvider`, adı `hashing-v1`, kanonik namespace hashing'dir; E5 çalıştırıldığı iddia edilmez. `classification=no_provider`, retrieval katmanı ve resolver'ın `calls_llm=False` sözleşmesi LLM kullanılmadığını gösterir. Manifestteki provider_calls0 alanı bu kod yolunun beyanıdır; ayrı token/sağlayıcı sayaç telemetrisi değildir. Kurulum logundaki hashing'in gerçek kalite raporuna uygun olmadığı uyarısı korunmuştur.

## Bağımsız yeniden hesaplanan sonuçlar

| Ölçüt | Eski kol | Aday | Fark |
|---|---:|---:|---:|
| Recall@5 (harness'te en az bir doğru kaynak isabeti) | 78/105 = 0,742857 | 77/105 = 0,733333 | −0,009524; −0,952 yüzde puan |
| Recall@8 | 80/105 = 0,761905 | 80/105 = 0,761905 | 0 |
| MRR | 0,618175 | 0,634444 | +0,016270 |

105 sorunun `ranks_by_source` dizilerinden tüm sayılar bağımsız hesaplandı; ham metriklerle eşleşiyor. İlk doğru kaynak sırası98 soruda aynı,5 soruda iyileşiyor ve2 soruda geriliyor. MRR artışı Recall@5 kaybını ortadan kaldırmaz.

| Soru | Beklenen kaynak | İlk doğru kaynak sırası | Etki |
|---|---|---:|---|
| H-121: Yetenek tabanlı erişim denetiminin en zayıf yanı | `10-security-and-protection.pdf`, sayfa2 | 3 → 6 | Tek Recall@5 kaybı |
| H-068: `consume()` metodunun `produce()` ile aynı sıralama hatasını taşıması | `producer_consumer.py` | 6 → ilk8'de yok | Recall@8 ve MRR kaybı |
| H-114: SSTF'nin bilinen sakıncası | `09-disk-and-storage.pdf`, sayfa2 | ilk8'de yok → 8 | H-068'in toplam Recall@8 kaybını dengeliyor |
| H-023 | Senkronizasyon notu / üretici-tüketici kodu | 2 → 1 | MRR artışı |
| H-116 | SSD yerinde güncelleme | 4 → 1 | MRR artışı |
| H-118 | RAID ve yedekleme | 3 → 2 | MRR artışı |
| H-141 | TLB / sanal bellek | 2 → 1 | MRR artışı |

Mevcut harness'in10.000 eşleştirilmiş bootstrap hesabı aynı tohumla yeniden hesaplandı. Recall@5 farkı için %95 aralık [−0,028571;0], MRR farkı için [−0,000794;0,038095]; ikisi de sıfırı içerir. Recall@5 McNemar yalnız-eski-doğru1, yalnız-aday-doğru0, p=1.0. Bunlar geniş bir istatistiksel kötüleşme hükmü kurmaz; gözlenen deterministik gerilemeyi veya sıkı non-regression kabulünün başarısızlığını gizlemez. Paired raporda `varied=[]`, ortak harness ayarlarının eşleşmesini belirtir; üç retrieval kaynak dosyasının aynı olduğu anlamına gelmez.

## Sonraki dar inceleme

Ham sonuçlar son sekiz kaynağı ve eşleşme sıralarını içerir; dense/FTS adaylarının tam sırası ve skorları yoktur. Dolayısıyla H-121/H-068 kaybının dense aday seçimi, FTS eşitlik sıralaması veya füzyon sırasından hangisine ait olduğu bu ham son listelerden ayrılamaz. Sonraki iş, aynı korpusta değişmemiş eski/yeni dense ve FTS çağrılarının aday kimliklerini, gerçek eşit skorları ve ortak füzyon girdilerini salt okunur izlemektir. Bu bir neden incelemesi olmalı; H-121/H-068'e özel sıralama, eşik ayarı veya holdout'a göre optimizasyon yapılmamalı. Genel bir sıralama kusuru bulunursa ayrı regresyon örneği ve kalibrasyon kapsamıyla ele alınmalı, bütün sabit holdout tekrar koşulmalıdır.

Sonucun kapsamı hashing mekanik regresyonudur; anlamsal kalite, eğitmen kabulü, gerçek embedding modeli veya performans sonucu değildir. Yerel `dou018_eval_c1holdout01` korunmuştur; bu inceleme cleanup yapmadı.

Kanıtlar: `/private/tmp/dou018-evidence/c1-holdout-measured-01/manifest.json`, aynı klasördeki iki ham sonuç ve paired karşılaştırma; `c1-holdout-analysis.json` bağımsız kontroller/soru ayrıntıları; `analyze_c1_holdout.py` salt dosya analizi; `c1-holdout-corpus-01.{json,log}` ve `c1-holdout-pair-01.log` kurulum/çalıştırma kaydı.
