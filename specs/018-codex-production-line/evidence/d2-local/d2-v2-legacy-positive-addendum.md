# D2 v2 dolu geçmişle başarılı göç eki

[Önceki kabul ekinde](/private/tmp/dou018-evidence/d2-v2-authority-acceptance-addendum.md) açık bırakılan **dolu legacy geçmişin başarılı göçü** artık yerel kanıtla destekleniyor. Önceki rapor değiştirilmedi.

[Yeni kök makbuzu](/private/tmp/dou018-evidence/d2-migration-positive-01/result.json), aynı v2 0026 hash'ini (`3e15eaa33f8bc8fba2f7a6d6e84692d213cc696ccd8367fad73152e79f2b61d3`) kullanıyor. Taze `dou018_d2_precondition_valid01`, OID1157624 üzerinde pending/failed/completed iş geçmişi taşınmış; profiles/courses/documents/jobs'un eski alanları önce-sonra aynı hash'leri vermiş. Yeni belge revision değerleri 1, yeni claim alanları NULL; claim constraint doğrulanmış, aktif iş indeksi valid/ready. Sahip olunan test DB'si silinmiş. Kök sarmalayıcı süresi 1.323 saniye.

Bu bağımsız inceleme makbuz eşitliklerini, aday hash'ini ve kökün snapshot/karşılaştırma/katalog assertion kaynaklarını salt okunur doğruladı. Yeni DB çağrısı yapmadı; ham satır snapshot'ları saklanmadığından hash'ler bağımsız yeniden hesaplanmadı. Sonuç yerel sentetik veri geçişini kapsar; karışık eski/yeni worker dağıtımı veya barındırılan ortam garantisi değildir.

[Makine okunur ek](/private/tmp/dou018-evidence/d2-v2-legacy-positive-addendum.json).
