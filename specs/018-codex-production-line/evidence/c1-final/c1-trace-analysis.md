# C1 şerit tanısı — 8 Eylül 2026

**Bu hashing tekrarında gözlenen Recall@5 farkını FTS eşitlik sıralaması açıklıyor.** Dört kontrollü dense/FTS birleşiminde skorlanan sonuçlar yalnız FTS seçimiyle değişiyor. Bu bulgu ilk hashing non-regression başarısızlığını değiştirmez; C1 kalite kabulü açık kalır.

## Deney ve doğrulama

İlk ölçümden aynı 127 soru kanonik kimlik ve sırasıyla izlenmiştir; 105'i kaynaklı ve skorlanır. İki gerçek eski/yeni dense ve FTS fonksiyonu aynı öğrenci, korpus, ayar ve sürücüyle çalıştı. Her kol ayrı salt okunur işlem kullandı; işlem ayarları karşı kola taşınmadı. Her iki gerçek HybridRetriever çıktısı, kaydedilen şeritlerden ortak gerçek `fuse` ile oluşturulan diagonal sonuçla eşleşti. İki diagonalın ilk ölçüm ham sonuçlarından sapması yoktur (`original_replay_drift=[]`).

Tek fiziksel bağlantı PID14145; `dou_app`, superuser=false/bypassrls=false. 167 parçanın önce/sonra içerik/vektör/metadata hash'i aynı: `d6132e5287c8bbd2b7660830f251374d3d27a797542842b028c05644ccbfc0f0`. Çalıştırıcı 11.634 gerçek aday DTO'sunun dosya, belge, sayfa/slayt, bölüm ve metnini izinli DB metadata kaydıyla kontrol etti; metinler tanı raporunda hash olarak saklandı. Kaynak/yardımcı/önceki rapor hashleri donduruldu. Son dosya analizi canlı DB kullanmadı; 127×4 = 508 füzyon listesini gerçek RRF işleviyle kaydedilmiş aday kimliklerinden yeniden hesaplayıp eşleştirdi.

## Kontrollü 2×2 sonuç

| Dense kaynağı | FTS kaynağı | Recall@5 | Recall@8 | MRR |
|---|---|---:|---:|---:|
| Eski | Eski | 78/105 = 0,742857 | 80/105 | 0,618175 |
| Yeni | Eski | 78/105 = 0,742857 | 80/105 | 0,618175 |
| Eski | Yeni | 77/105 = 0,733333 | 80/105 | 0,634444 |
| Yeni | Yeni | 77/105 = 0,733333 | 80/105 | 0,634444 |

Çapraz kollar yalnız tanısaldır; bağımsız yeni ürün adayları veya kalite terfisi olarak değerlendirilmez. Bu tablonun yorumu, aynı yerel korpus ve saklanan şeritler için kontrollü nedensel atıftır. Dense aramanın bütün sorgularda değişmediği veya bütün korpuslarda kalite eşdeğerliği çıkarılamaz.

127 soruda dense aday satırları yalnız 71'inde birebir aynı; 117'sinde aynı kimlik kümesi var. FTS aday satırları yalnız bir soruda birebir aynı, 51'inde aynı kimlik kümesi var. Her iki şeritte bütün 127 sorunun sıralı sayısal skor dizisi aynıdır; ortak kimliklerin skorları da aynıdır. Kimlik kümesi farklı dense10 ve FTS76 vakasının her birinde çıkıp giren adaylar aynı son-sıra skorunda eşittir. Bunlar gözlenen 24 adaydan çıkarılır; aday sınırının dışındaki eşitlik kümesinin tamamını listelediği iddia edilmez.

## Üç açıklayıcı soru

| Soru / doğru kaynak | Dense sırası, eski→yeni | FTS sırası, eski→yeni | Exact FTS skoru | Son ilk isabet |
|---|---:|---:|---:|---|
| H-121; güvenlik PDF sayfa2, parça2 | 1→1 | 14→15 | 0,008443432 | 3→6; tek Recall@5 kaybı |
| H-068; `producer_consumer.py`, parça3 | 12→12 | 7→11 | 0,01105322 | 6→ilk8 dışı |
| H-114; disk PDF sayfa2, parça1 | 9→9 | 14→13 | 0,008684673 | ilk8 dışı→8 |

Bu üç sorunun bütün dense aday sırası aynıdır. FTS'de skorları aynı olan grupların içerik hash'iyle yeniden sıralanması sıra numaralarını değiştirir. RRF gerçek skor büyüklüğünü değil sıra katkısını kullandığı için kaynakların füzyon puanı ve diğer adaylarla göreli sırası da değişir. H-121'de doğru kaynak hâlâ dense birincisi ve FTS aday kümesindedir; doğru kaynağın kaybı değil, ilk beşin dışına yeniden sıralanması söz konusudur. H-068 de iki şeritte bulunmaya devam eder; FTS sırasındaki düşüş onu son sekizden çıkarır.

FTS'nin UUID yerine içerik hash'i kullanması yeniden yükleme kararlılığı sorununu giderir; bu hash anlamsal bir öncelik sinyali değildir. Eski UUID sıralamasının bu bir korpustaki daha iyi Hit@5 sonucu, UUID'ye geri dönmek veya H-121'e özel kural eklemek için gerekçe değildir. Aynı şekilde deterministik sıralama hedefi, gözlenen non-regression kaybını yeşile çevirmeye yetmez.

## Karar sınırı

Hashing başarısızlığı aynen korunur. Henüz ürün sıralaması, FTS skoru, RRF, aday sayısı, eşik veya altın set değiştirilmedi. Genel bir eşit-skor füzyon politikasının yararı araştırılacaksa ayrı tasarım ve genel sentetik/calibration örnekleriyle ele alınmalı; holdout'u ayar seçmek için kullanmamalı. Hazırlanan E5 kolu gerçek embedding sağlayıcısıyla ayrı retrieval kabul ölçümü verir; bu tanının veya ilk hashing sonucunun yerine geçmez.

C1 plan/GUC/metadata kısmının ayrı kısmi dossier ile izlenmesine itiraz yoktur. Böyle bir kayıt ölçülmüş plan düzeltmesini `evidence-ready` gösterebilir; hashing kabulünü `fail/open` olarak bağlamalı, C1-complete veya kalite terfisi iddia etmemelidir.

Kanıt: `/private/tmp/dou018-evidence/c1-trace-measured-01/{manifest.json,trace.jsonl}`; ham trace SHA256 `69d2d2c07fe05a0acb6ebf6e2ca219cfe68fd1812a9dfb196b8ce4e3e67b1f0c`. Bağımsız hesap ve kontroller `c1-trace-analysis.json`; çalıştırıcı `c1_trace_retrieval.py`, 5 çevrimdışı test `c1-trace-offline-unit-final.log`.
