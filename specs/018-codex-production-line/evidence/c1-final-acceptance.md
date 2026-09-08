# C1 son kaynak — dar yerel teknik kabul

8 Eylül 2026. **FTS'nin önceki sıralamasına dönen, dense ANN/GUC düzeltmesini koruyan son aday yerel teknik kontrollerden geçti.** Aynı son kaynak üzerinde hashing mekanik gerilememe koşulu, gerçek E5 retrieval kabulü, prepared-plan runtime deneyi ve tam API paketi başarılıdır. Bu karar C1/runbook'un bütün kapsamını, CI pgvector0.8.6 davranışını, LLM yanıt kalitesini veya üretim terfisini tamamlanmış saymaz.

Bu belge [ilk aday raporuna](/Users/muratates/code/dou-synapse-018-codex-production-line/specs/018-codex-production-line/evidence/c1-report.md) ek sonuçtur. İlk adayın hashing ve E5 Recall gerilemeleri geçerli tarihsel başarısızlıklar olarak korunur. İlk rapor ve arşiv endeksleri değiştirilmedi; iki eski arşivdeki 58 kaydın dosya ve gerektiğinde açılmış gzip içerik hashleri bu analizde yeniden doğrulandı. İlk rapor SHA256: `08389ea820ad4231743a363924c84924265f9ee815e61f982dd5c5b809546d1e`.

## Kabul edilen son değişiklik

Dense arama MATERIALIZED aday penceresini, sınırlandırılmış ×8 fazla aday seçimini, dış içerik-hash/parça sırasını ve yalnız dense SELECT boyunca custom-plan ayarını korur. Başarılı çağrı önceki plan modunu geri verir; SQL hata/iptal yolu çağıranın rollback sözleşmesine dayanır.

FTS sorgusu `71d5ff640f0d48a08f3967b000485a15035f10c7` sürümündeki `rank DESC, document_id, chunk_index` sırasına döndü. SQL yorumları çıkarıldığında son FTS sorgusu bu eski kaynakla byte-equal. Yanlış “document_id içerikten türer” açıklaması geri getirilmedi: değişmeyen tek korpusta kararlılık bulunur; yeni UUID'lerle tekrar yüklenen korpusun aynı sıralanması garanti edilmez. FTS yeniden yükleme kararlılığı ayrı açık iştir.

FTS hash-tie değişikliği ölçülmüş zararlı bileşen olduğu için kapsamdan ayrıldı. Altın set, soru seçimi, skor eşikleri, RRF veya aday sayısı sonuçlara göre değiştirilmedi. Ayrı hashing ve gerçek E5 dört-kol tanıları, eski FTS + yeni dense birleşiminin baseline metriklerini koruduğunu gösterdi. Ardından aşağıdaki sonuçlar çapraz birleştirme adaptöründen değil, daraltılmış **gerçek son HybridRetriever kaynağından** yeniden alındı.

## Aynı son kaynakla iki holdout

| Ölçüm | Eski kaynak | Son aday | Sonuç |
|---|---:|---:|---|
| Hashing Recall@5 | 78/105 = 0.742857 | 78/105 = 0.742857 | Mekanik azalmama geçti |
| Hashing Recall@8 | 80/105 | 80/105 | Aynı |
| Hashing MRR | 0.6181746032 | 0.6181746032 | Aynı |
| Gerçek E5 Recall@5 | 93/105 = 0.885714 | 93/105 = 0.885714 | ≥0.80 ve azalmama geçti |
| Gerçek E5 Recall@8 | 98/105 | 98/105 | Aynı |
| Gerçek E5 MRR | 0.7377210884 | 0.7377210884 | Azalmama geçti |

Her deney, değişmeyen 161 soruluk altın setin aynı 127 retrieval sorusunu içeriyor: 105 puanlanan ve 22 kapsam dışı. Her kolda127 deneme, sıfır hata/yeniden deneme/rate-limit, concurrency1 var. Mevcut paired bootstrap hesapları da kaydedilmiş sıralardan tekrar hesaplandı. Bu deneylerde sıfır delta, iyileşme veya evrensel eşdeğerlik iddiası değildir.

Her iki yeni baseline, ilk ölçümdeki baseline'ın 127/127 üst-8 kaynak listesini ve kaynak sıralarını aynen tekrar ediyor. Son aday ile baseline arasında iki deneyde de bütün 105 puanlanan sorunun ilk doğru kaynak sırası ve bütün127 kaynak sıra listesi aynı. E5 üst-8 kaynak listeleri127/127 aynı; hashing'de120/127 aynı. Hashing'deki yedi farklı üst-8 liste ilk doğru kaynağın sırasını veya ölçülen metrikleri değiştirmiyor. Bütün dönen sıraların evrensel olarak aynı olduğu iddia edilmez.

İki deney aynı ders materyali paketinin ayrı, gerçek upload/worker yolu ile kurulmuş22 tamamlanmış belge/167 chunk korpuslarını kullanıyor. Yeniden kurulum yapılmadı. Kaynak dosyaları, korpus bildirimi, soru sırası/metni, altın kaynak konumları, ortak retrieval/harness kaynakları ve önce/sonra DB state hashleri ilk ölçümle eşit.

- Hashing: gerçek `HashingEmbeddingProvider/hashing-v1`, namespace `hashing/hashing-v1@builtin-1`; 0.1 ayar etiketi, fingerprint `a2d6c60b7cd0ca6f`. Ham rapordaki E5 `embedding_model` alanı atıl ayar etiketidir; gerçek sağlayıcı kimliği değildir. Hashing sonucu semantik kalite kanıtı olarak sunulmaz.
- E5: gerçek `FastEmbedProvider/intfloat/multilingual-e5-large`, namespace `fastembed/intfloat/multilingual-e5-large@0.8.0`; aynı 0.81 ayarı, fingerprint `6e7df24ac07a8282`. Yerel cache revision `66076b8dc6e367337e3e90e6fb309fb0f3addaf6`; altı dosyanın tam içerik hashleri ilk E5, son E5 ve ölçüm öncesi/sonrası arasında aynı. Model yeniden indirilmedi; üç offline flag ve localhost:9 HTTP proxy sözleşmesi korundu.
- Gerçek `dou_app`, superuser/BYPASSRLS kapalı, öğrenci RLS bağlamı ve salt okunur işlemler kullanıldı. Korpus içeriği/vektör/metadata hashleri iki kolda önce/sonra aynı. Bağımsız analiz bu sonuçları, kaynağı ve hash bağlarını okudu; DB veya model çalıştırmadı.

Bu ham retrieval ölçümlerinde LLM kullanılmadı. Eşik guard'ı, yanıt kaynak sadakati, alıntı doğruluğu, kapsam reddi ve pedagojik davranış ölçülmüş sayılmaz. `evidence_threshold_calibrated=false` kaydı korunur; bu deney yeni eşik seçmez.

## Gerçek sürücü ve plan kontrolü

Son runtime v3, önceki deneyle aynı20 bin sentetik kayıt klonunda ve aynı14 sorgu/filtre örneğinde gerçek SQLAlchemy2.0.52/psycopg3.3.4 kullanır. Psycopg otomatik hazırlama eşiği5 olarak korunmuştur. Yerel PostgreSQL16.14 ve pgvector extension0.8.0 ölçülmüştür; Python `pgvector` paketinin0.5.0 sürümü ayrı bilgidir.

Üç çağıran plan modu, her örnek için12 ısınma ve7 ölçüm: toplam504 ısınma,294 zamanlanan gerçek HybridRetriever çağrısı. Tek fiziksel bağlantı PID18317; ders/belge filtreleri, kaynak metadata'sı ve kanonik embedding namespace denetlenmiştir. Bütün294 kayıtlı sonuç/aday sayısı gözlemi runtime v2 ile aynı. Boş belge seçimi ve yetkisiz öğrenciye ait84 ölçümün tamamı sıfır sonuç verdi; dönen1680 kaynağın metadata kontrolleri geçti.

Zamanlanan çağrılara ait `pg_prepared_statements` sayaç farkları ham önce/sonra kayıtlardan bağımsız yeniden hesaplandı:

| Çağıran mod | Dense custom/generic | FTS custom/generic |
|---|---:|---:|
| auto | 98 / 0 | 14 / 84 |
| force_custom_plan | 98 / 0 | 98 / 0 |
| force_generic_plan | 98 / 0 | 0 / 98 |

Dense bütün modlarda custom planı kullanıyor; FTS çağıranın politikasında kalıyor ve çağrı sonrası mod geri yükleniyor. Plan görselleri zamanlanan SELECT'in birebir kaydı değildir: aynı prepared statement'ın aynı şerit politikasıyla ayrı ek EXPLAIN yürütmesidir. Zamanlanan yürütmenin plan politikası için esas kanıt sayaç farklarıdır.

Auto geniş kapsam q0 p50/p95 **57.142/58.156 ms**, q1 **56.644/58.924 ms**; dense planlarında HNSW gözleniyor. V2'ye göre p50 farkları sırasıyla +1.004/+0.062 ms. Bunlar yedi tekrardan oluşan yerel gözlemlerdir; nüfus p95'i veya gecikme iyileşmesi hükmü değildir. Full HybridRetriever süreleri, önceki dense SQL mikrobenchmark süreleriyle doğrudan karşılaştırılmaz. Probe iç süresi12.3747 saniye, dış çalıştırıcı süresi13.005 saniyedir.

Probe mevcut kayıtların metadata/namespace sınırını yeniden kontrol eder; saklanan bütün vektörlerin taze önce/sonra hash'ini yeniden hesaplamaz. Vektör değişmezliği için korunan tarihsel klon lineage kaydı kullanılır. Orijinal20 bin ölçüm DB'si değiştirilmedi; bu son ölçüm ayrıca yalnız okunur bağlantı/işlemlerle yürütüldü.

## Tam API ve kaynak kimliği

Son FTS geri çekmesi dahil tam API paketi **1499 passed, 5 bilinen PyMuPDF/Swig uyarısı, 91.66 saniye**. Dış çalıştırıcı/setup dahil süre101.604 saniye; kaynaklar önce/sonra aynı. Önceki1500 sayısının bir azalması, teslim kapsamından çıkarılan FTS yeniden yükleme kararlılığı parametresidir. Dense yeniden yükleme testi ve iki yolun belge/kapsam/RLS negatifleri korunmuştur. Kökün ayrı son E2E kaydı da **68 passed (1.4m)**: koşu `mtskgnz9ac45`, 65 sentetik ders ve8 audit kaydı temizlenmiş. `bc-c1-final-e2e.log` özeti ve hash'i bu analizde doğrulandı. Son FTS kaynağıyla API sürecinin yeniden başlatıldığı kök tarafından bildirildi; bu bağımsız analiz tarayıcı testlerini yeniden çalıştırmadı.

| Son üretim dosyası | SHA256 |
|---|---|
| dense.py | `020820a4b60307c956b87d609c49f634845a38ea16fb79a96606ea49178e639d` |
| fts.py | `eceb7954bb865f0b8776db467aaf490ae316f10985de3abc881349705fe6c94b` |
| service.py | `dc09fbe8003598c3bf5364a69d3aead299d64c7a17a824c4fc047ab3b092be4c` |
| config.py | `16e53fb5e5ea30a8fa2a68674abdbd48226d5e1e2c3cefe3e1654e2527528423` |

Karşılaştırma baseline'ı kesin71d5ff6 commit'inden alınmış gerçek dense/FTS/service byte'larıdır. Son aday kirli çalışma ağacıdır; checkout SHA tek başına aday kimliği olarak kullanılmaz. Bütün son ölçümler aynı yukarıdaki üretim hashlerine bağlıdır. Çağrılan resolver ve ortak Settings/embedding/fusion/scope/harness kaynakları ayrıca manifestlerde kayıtlıdır; bütün eski uygulama sürümü çalıştırıldığı iddia edilmez.

Ham son manifest hashleri:

- Hashing `c1-holdout-final-02/manifest.json`: `41a045c7a890d86f321bd97a978420f392189bda1b34a41ca2f4d63c3e2fb318`.
- E5 `c1-e5-final-02/manifest.json`: `ea0d9452dd53f50b798403f7b7772e0d6dd50f97c1d6345967afd16d738ef147`.
- Runtime `retrieval-runtime-local-v3-final-20260908.json`: `51cbd43e773749df26246ab791cf12fa52eb267b1944e4d1a7238b2664883c84`.

Bağımsız ayrıntılar `c1-final-hashing-audit.json`, `c1-final-e5-audit.json`, `c1-final-runtime-audit.json`; birleşik karar `final-source-acceptance.json`. Önceki olumsuz kayıtlar ve ayrı çapraz tanılar bu dosyaların yerine geçmez, açıklama zincirini tamamlar.

## Açık kapsam

FTS'nin yeni UUID'lerle yeniden yüklemede kararlılığı, RLS-off karşılaştırması ve pinned CI pgvector0.8.6 doğal plan/recall matrisi açık. C2 için indeks kurma belleği/dökülmesi ile recall arasında nedensel deney yok; ölçümsüz migration önerilmez. Yerel E5 sonucu gerçek embedding retrieval kabulüdür; LLM faithfulness, pedagojik değerlendirme, öğretmen onayı, canlı dağıtım ve genel C1/runbook tamamlanması bu teknik kararın kapsamı dışındadır.
