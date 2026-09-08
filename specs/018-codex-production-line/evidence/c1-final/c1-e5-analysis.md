# C1 gerçek E5 retrieval holdout — 8 Eylül 2026

**Aday Recall@5 ≥0,80 hedefini geçti; eski sürüme göre gerilememe koşulunu geçmedi.** Gerçek E5 korpusunda Recall@5 93/105'ten92/105'e düştü. Bu ek rapor ilk hashing başarısızlığını veya arşivlenmiş önceki raporları değiştirmez. Çalıştırıcı eksiksiz tamamlandı (`phase=complete`, `status=measured_e5_retrieval_only`); kabul sonucu ayrı olarak `retrieval_acceptance=false`.

## Karşılaştırılabilirlik ve çalışma bütünlüğü

17 bağımsız dosya/sonuç denetimi geçti. Eski dense/FTS/service snapshotları `71d5ff640f0d48a08f3967b000485a15035f10c7` commit'inin gerçek baytlarıyla aynı; üç güncel aday kaynağı, yedi ortak bağımlılık, sekiz harness/altın set kaynağı ve wrapper SHA256 değerleri eşleşiyor. Eski service yalnız kendi ayrı eski dense/FTS fonksiyonlarına bağlı, yeni kol normal service girişinden çalışıyor. Ortak Settings/embedding/fusion/scope/contracts/DB çevresi aynı. Bu üç retrieval dosyasının aynı güncel çevrede karşılaştırmasıdır; bütün tarihsel uygulamanın yeniden kurulması değildir.

İki kol aynı ders, `dou018_eval_c1e501` veritabanı, korpus digest'i, sorgu listesi ve `6e7df24ac07a8282` ayar fingerprint'ini taşıyor. Top-k8, dense24, FTS24, RRF60 ve mevcut E5 evidence threshold0,81 sabit; aday multiplier8 ayrıca manifestte kayıtlı. Eşik, kaynak paketi ve altın set ayarlanmadı. `HybridRetriever.search()` ham retrieval döndürür ve evidence kapısını uygulamaz; bu deney0,81 eşiğinin ret/faithfulness başarısını doğrulamaz. Ham sonuçtaki `evidence_threshold_calibrated=false` alanı korunmuştur; bu çalışma yeni bir kalibrasyon iddiası yapmaz.

Her kolda127 deneme,0 retry,0 failure,0 rate-limit; concurrency1. Aynı127 soru metni/kimliği/sırası ve beklenen kaynaklar hash'i değişmemiş holdout ile eşleştirildi. Holdout toplam161 öğedir; mevcut seçim105 kaynaklı soruyu ve22 kapsam dışı soruyu retrieval'a yollar.22 kapsam dışı soru Recall/MRR paydasına girmez; bu koşu doğrudan model reddini ölçmez.

Korpus gerçek upload/worker yolundan22 tamamlanmış belge,167 parça ve167 embedding içerir. Tüm dosya hashleri mevcut sabit materyal paketiyle aynı. Öğrenci RLS bağlamında `dou_app`, superuser=false ve bypassrls=false; forced RLS iki kaynak tablosunda çalıştırıcı tarafından denetlenir. Her kolun önce/sonra kayıt durumu ve iki kolun durumu aynı: `fastembed/intfloat/multilingual-e5-large@0.8.0`,167 kayıt, içerik/vektör/metadata SHA256 `1fbff9e89fe71c86f343608c52cea1243cc3dcdeabf7770d94f25082298120c9`. İnceleme DB'ye tekrar bağlanmadı; hash'i doğrulanan çalıştırıcının read-only ve eşitlik kontrollerini ham sonuçlarla eşleştirdi.

## Gerçek model ve önbellek kimliği

Gerçek sağlayıcı `FastEmbedProvider`, model `intfloat/multilingual-e5-large`,1024 boyut; kanonik ingest/query namespace aynı. Hashing yedeği veya model-space etiketi değiştirme kancası yoktur. Yerel fastembed0.8.0 kataloğu `PooledEmbedding` ve mean pooling kullanır;512 token tokenizer sınırı ve uygulamanın mevcut query/passage önekleri korunur. ONNX Runtime1.28.0, tokenizers0.23.1, huggingface_hub1.26.0 sürümleri kayıtlıdır.

Önbellek `/Users/muratates/.cache/dou-synapse/fastembed`, snapshot revision `66076b8dc6e367337e3e90e6fb309fb0f3addaf6`. Model başlığı545.851 byte, dış ağırlık dosyası2.235.363.328 byte. Altı gerekli dosyanın gerçek içerik hashleri wrapper tarafından başlangıçta ve sonda hesaplanıp karşılaştırılmıştır; cache revision/tree metadata ve ilgili fastembed kütüphane kaynak hashleri de aynıdır.

| Dosya | SHA256 |
|---|---|
| model.onnx | `1c09780c907c8a91a77a6ab1fd231f79e090d2907ca431223703dfebeed3d36c` |
| model.onnx_data | `0cf1883fee81c63819a44e2ba0efa51d4043d9759685a4ebebbde97e0623d15c` |
| tokenizer.json | `f59925fcb90c92b894cb93e51bb9b4a6105c5c249fe54ce1c704420ac39b81af` |

Bu bağımsız analiz, saklanan tam başlangıç/son hash eşitliğini; mevcut küçük metadata/kütüphane kaynak hashlerini; model dosyalarının değişmemiş boyut/zaman bilgilerini doğruladı.2,2 GB model yeniden yüklenmedi veya yeniden hash'lenmedi. HF_HUB_OFFLINE, HF_DATASETS_OFFLINE, TRANSFORMERS_OFFLINE=1 ve beklenmedik HTTP için127.0.0.1:9 proxy sözleşmesi kayıtta mevcut. Yerel cache metadata'sı dış kaynak imzası değildir; deneyin kullanılan byte kimliğini tanımlar. Fastembed mean-pooling değişim uyarısı korunur; tarihsel başka fastembed sürümüyle vektör eşdeğerliği iddia edilmez.

LLM çağrısı yok: ham sonuç `classification=no_provider`, gerçek giriş retrieval katmanıdır. Manifestte `quality_scope=real_embedding_retrieval_only`, `generation_quality_reportable=false`. `provider_calls=0` alanı bu LLM'siz kod yolunun beyanıdır; embedding çağrısı yapılmadığı anlamına gelmez veya bağımsız token sayaç telemetrisi sayılmaz.

## Sonuç ve başarısız kabul

105 soru için ham `ranks_by_source` dizilerinden metrikler bağımsız yeniden hesaplandı:

| Ölçüt | Eski | Aday | Fark |
|---|---:|---:|---:|
| Recall@5 / en az bir beklenen kaynak isabeti |93/105 =0,885714|92/105 =0,876190|−0,009524; −0,952 yüzde puan|
| Recall@8 |98/105 =0,933333|97/105 =0,923810|−0,009524|
| MRR |0,737721|0,739535|+0,001814|
| Çok kaynaklı sorularda tüm kaynaklar ilk5'te |20/26 =0,769231|20/26 =0,769231|0|
| Çok kaynaklı sorularda tüm kaynaklar ilk8'de |22/26 =0,846154|22/26 =0,846154|0|

Adayın Recall@5'i0,80'in üstündedir. Buna rağmen nondecrease kapısı başarısızdır; küçük MRR artışı Recall kaybını telafi edilmiş saydırmaz. İlk doğru kaynak sırası99 soruda aynı,3 soruda iyileşiyor,3 soruda geriliyor.

| Soru / beklenen kaynak | İlk doğru kaynak sırası | Etki |
|---|---:|---|
| H-154; `page_replacement.py` LRU fonksiyonunun hatası |2→8|Tek Recall@5 kaybı|
| H-112; interrupt coalescing, I/O PDF sayfa4 |8→ilk8 dışı|Recall@8 kaybı|
| H-120; kullanıcı/çekirdek modu ayrımı, güvenlik PDF sayfa1 |7→ilk8 dışı|Recall@8 kaybı|
| H-119; en az ayrıcalık, güvenlik PDF sayfa1 |ilk8 dışı→6|Bir Recall@8 kazanımı|
| H-116; SSD yerinde güncelleme |2→1|MRR artışı|
| H-118; RAID ve yedekleme |3→2|MRR artışı|

Mevcut10.000 tekrarlı/sabit tohumlu paired bootstrap aynı sonuçlarla bağımsız yeniden hesaplandı. Recall@5 farkının%95 aralığı [−0,028571;0]; MRR farkının aralığı [−0,010488;0,015873]. Recall@5 McNemar yalnız-eski-doğru1, yalnız-aday-doğru0, p=1.0. Aralıkların sıfırı içermesi geniş istatistiksel hükmü sınırlar; ölçülen deterministik kaybı veya önceden belirlenmiş gerilememe kabulünü ortadan kaldırmaz. Paired rapordaki `varied=[]`, ortak harness ayarlarının aynılığını ifade eder; eski/yeni kaynak kodunun aynı olduğu anlamına gelmez.

## Süre ve kapsam kararı

Harness ham kol sürelerini eski10,7 s ve aday10,0 s olarak kaydetmiştir. Wrapper toplam süresini kaydetmez; model hash doğrulama/karşılaştırma dahil toplam süre bu raporda verilmez. Bu iki kol süresinden gecikme kazancı veya üretim performansı iddia edilmez.

Hashing'deki kontrollü şerit tanısı farkı FTS tie sırasına bağlamıştı. Bu E5 sonucuna aynı neden otomatik aktarılmaz: ayrı E5 çapraz-şerit çalıştırıcısı, aynı127 soruda eski/yeni dense+FTS'nin dört birleşimini gerçek modele ve bu cache kimliğine bağlı olarak ölçmek için hazırlanmıştır. Sonuçları henüz bu raporda yoktur.

Önerilen kapsam ayrımı, yeni FTS hash-tie bileşenini teslim adayından geri çekip doğrulanmış dense ANN/GUC kısmını tutmaktır; ancak bunun E5 yeni-dense/eski-FTS kanıtı önce görülmelidir. Bu yaklaşım holdout üzerinde yeni eşik/sıralama ayarı seçmek yerine olumsuz bileşeni rollback eder. Eski FTS UUID'ye bağlı yeniden ingestion kusuru ve C1'in tam kapsamı açık kaydedilmelidir. Yeni FTS kusursuz veya bütün C1 tamamlandı denmemelidir.

Bu sonuç gerçek embedding retrieval kanıtıdır. LLM faithfulness, atıflı yanıt doğruluğu, Sokratik/pedagojik davranış, insan/eğitmen değerlendirmesi veya üretim hazırlığı kabulü değildir. Eski hashing raporu ve başarısızlığı aynen korunur; bu ek analiz repo kaynağı, model cache, DB, eşik veya altın set değiştirmedi.

Kanıt: `/private/tmp/dou018-evidence/c1-e5-measured-01/manifest.json` SHA256 `866c268096b8bfa5ec2ee476b86bffc55050131e8d85d4e467d7ac5f0911fd6e`; aynı klasörde iki ham sonuç ve paired rapor. Bağımsız17 denetim, soru ayrıntıları ve cache sidecar `c1-e5-analysis.json`; analiz kodu `analyze_c1_e5.py`. Wrapper `c1_e5_holdout_runner.py`;7 çevrimdışı test `c1-e5-offline-unit.log`. Korpus `c1-e5-corpus-01.json`; ilk hashing ve şerit kayıtları ayrı tutulmuştur.
