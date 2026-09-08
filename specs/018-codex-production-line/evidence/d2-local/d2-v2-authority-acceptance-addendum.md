# D2 v2 yetki ve göç kabul eki

**Yerel v2 yetki kabulü ve iki olumsuz göç önkoşulu doğrulandı.** [İlk bağımsız rapor](/private/tmp/dou018-evidence/d2-independent-migration-review.md) ve ilk başarısız deney değiştirilmedi. Bu ek inceleme DB/sunucu/test çalıştırmadı; kökün ham sonuçlarını ve donuk kaynakları karşılaştırdı.

[Stage02 sonucu](/private/tmp/dou018-evidence/d2-stage-tests-02/result.json) ve hash'i doğrulanan [test günlüğü](/private/tmp/dou018-evidence/d2-stage-tests-02/tests.log): **98 passed**, 5 bilinen PyMuPDF SWIG uyarısı; pytest 19.43 saniye, kök sarmalayıcı 20.536 saniye. Paket altı doğrudan gerçek-PG yetki testini ve lineage regresyonunu içeriyor. Tüm 211 stage kaynak hash'i makbuzla eşleşiyor; altı yetki testinin dosyası hazırlanan adayla byte eşit. Lineage testindeki yorum ve bytes literal bölünmesi AST'yi değiştirmiyor.

D2-LINEAGE-01 için önceki v1 `2 != 1` başarısızlığından sonra 112 çalışma zamanı Python kaynağı aynı kalmış. Göçte yalnız `supersedes_document_id` revision karşılaştırmasından çıkarılmış; `superseded_at` ve gerçek kaynak alanları korunmuş. Aynı regresyon artık gerçek DELETE sonrası halef revision'ının değişmediğini ve mevcut claim ile tamamlandığını doğruluyor. Ölçülen 0026 SHA256: `3e15eaa33f8bc8fba2f7a6d6e84692d213cc696ccd8367fad73152e79f2b61d3`.

Gerçek dou_app kontrolleri: şekli geçerli processing INSERT ve doğrudan job UPDATE reddi; geçerli pending INSERT kabulü ve ikinci aktif işin unique reddi; öğrenci/yabancı/karma ders rolü/öznesiz retry reddi, kendi failed retry kabulü; NULL ve superseded sınırları; fonksiyon ACL/SECURITY DEFINER/sabit arama yolu/FORCE RLS; gerçek worker EXECUTE reddi; app revision sahteciliği ve A→B→A kontrolü geçti. Bunlar donuk gerçek test assertion'larıyla bağlı toplu pytest kanıtıdır; her SQL assertion için ayrıca satır dökümü tutulmamış.

[Göç önkoşulu makbuzu](/private/tmp/dou018-evidence/d2-migration-preconditions-01/result.json), aynı 0026 hash'ini kullanıyor. Ayrı taze DB'lerde processing işi ve duplicate pending işleri, kendi beklenen mesajlarıyla `P0001` verdi. Profiles/courses/documents/jobs, sütunlar, indeksler, politikalar, constraint'ler ve eski retry tanımı/ACL için önce-sonra hash'leri eşit. Her iki sahip olunan test DB'si temizlenmiş; kök süre 2.551 saniye. Snapshot hesaplama/rollback yolu ayrıca kaynak olarak incelendi; ham snapshot satırları saklanmadığından hash'leri bağımsız tekrar hesaplamadım.

Açık sınırlar: dolu pending/failed/completed geçmişin başarılı göçü için ayrı pozitif deney burada yok; boş şemaya başarılı uygulama stage kurulumu ile kapsanıyor. Eski worker ve API drain'lerinin durdurulması, gerçek OS SIGTERM/SIGKILL kurtarma deneyi ve barındırılan ortam kabulü ayrı kalıyor. Bu ek, kötü niyetli BYPASSRLS worker'a veya tüm dağıtıma yönelik güvenlik garantisi değildir.

[Makine okunur ek ve giriş hash'leri](/private/tmp/dou018-evidence/d2-v2-authority-acceptance-addendum.json).
