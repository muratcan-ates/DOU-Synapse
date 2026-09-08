# OPS1/OPS2/D6 ve D3 ek deneyleri — yerel kabul

8 Eylül 2026; taban `c45e0e7073c92638ced7a3ff523578dd598c350b` üzerindeki yeni çalışma kaynakları. Bu arşiv eski D/S8 ve c45 hosted sonuçlarını değiştirmez. Yeni commit kendi `.ai` kaydıyla bağlanır; canlı dağıtım yapılmadı.

| Kontrol | Ölçülen sonuç |
|---|---|
| Tam API | 1571 geçti,38 alt vaka,104.37s; yeni veritabanı fixture sonunda kaldırıldı |
| Web | 555 birim testi/44 dosya/1282 assertion, tür kontrolü ve gerçek üretim derlemesi geçti |
| Tarayıcı | 71 geçti,82.581s; kendi65 sentetik ders/14 audit kaydı temizlendi |
| Yönetim görünümü | 375/1440 genişlikte açık/koyu4 gerçek görünüm; belge taşması yok, ArrowRight/Home ve sonraki görünür odak geçti |
| Yanlış hazır durumu karşı örneği | Gerçek kota uyuşmazlığında admin durumunu zorla `ok` yapan süreç içi mutant iki vakadan da kaldı |
| SQL hata karakterizasyonu | 2 gerçek SQL kalibrasyonu +7 admin testi9 geçti; hata22012 sonrası HTTP200/degraded, aynı işlem25P02, bağımsız1 allowed audit ve sonraki temiz public200 |
| Gerçek worker dönemi | Başlangıç expired temizliği0.544s; sonradan eklenen expired59.973s'de var,60.181s'de yok; canlı satır byte eşit; SIGTERM exit0/0.086s |
| D3 | Açık/kapalı eşzamanlı yazıcı ve kaynak/bakım bağlantısı kapanışı dört gerçek negatif kabul geçti |
| Sözleşme | OpenAPI57 yol aynı; yalnız AdminOverviewOut için pgvector_status/request_quota_status eklendi |

Yeni admin E2E vakalarının biri gerçek yetkili HTTP yanıtını, ikisi aynı gerçek cevaptan türetilmiş kontrollü degraded/eski-alan UI sözleşmesini ölçer. Gerçek politika uyuşmazlığı ve düzelme API/DB testindedir. Dört ek görsel,71 test sayısına eklenmez. Görseller kök görev tarafından incelendi; tab ve tablo içi kaydırma korunur, tam site erişilebilirlik kabulü yapılmadı.

`source-equivalence.json` son tam API'nin215 kaynağında üç sonraki byte farkını açıklar: internal.py modül açıklaması, admin testinin bitişik SQL literal satırları ve kota testindeki uzun ifadenin satırlanması. İlkinde modül açıklaması dışı AST, diğerlerinde tam AST eşittir. Ölçülen özgün dosya baytları yan klasörde tutulur. E2E281 kaynakta fark yoktur. Eski sonuç yeni kaynakta yeniden koşulmuş sayılmaz; bu dar eşlik ayrı kanıttır.

`receipt-interpretation.json`, negatif test makbuzundaki eksik komut alanının gerçek çalıştırılmış seçimini açıklar. İlk negatif gözlemci yanlış işlev adı nedeniyle kurulumdan kaldı; düzeltmeden sonraki iki assertion hatası gerçek yanlış-hazır karşı örneğidir. İlk kota dönemi eksik yerel auth ayarıyla başarısızdı. İlk görsel gözlemci projenin data-theme niteliği yerine CSS sınıfına bakmıştı. İlk OpenAPI gözlemcisi yanlış şema adında, ilk son Ruff koşusu101 karakterlik test satırında durdu. Bu hazırlık hataları ürün kabulü olarak sayılmaz; düzeltmeler kaynak/sonuçlarıyla ayrıdır.

SQL karakterizasyonu yalnız mevcut terminal salt okunur admin çağıranını kabul eder: yardımcı başarısız işlemi onarmaz. Genel yazım atomikliği, kayıp bağlantı veya belirsiz COMMIT garantisi yoktur. Public uç admin toplamları almaz; admin yetkisi ve bağımsız erişim audit'i yerindedir. Başarılı sohbet sayısı/p95 yalnız kaydedilmiş başarılı HTTP sohbet örneklemidir; içerik doğruluğu ve bütün isteklerin gecikme SLO'su değildir.

Kota başarı olayı yalnız helper COMMIT dönüşünden sonra stage/deleted_windows/duration_ms taşır. Silme0, bütün süresi geçmiş satırların bittiği anlamına gelmez. Compose HTTP worker/drain'i korurken port açmayan ayrı poller tanımlar; Docker istemcisi bulunmadığı için Compose çalıştırılmadı. Gerçek yerel60s dönem, bulut uyanışı veya saklama/imha SLA'sı değildir.

`d3-negative-summary.json` sekiz özgün makbuz hash'i ve yalnız kaydedilmiş alanları taşır. Root source_unchanged alanı runtime dosya hash'i anlamındadır; DB satır eşliği değildir. 07b'de ilk guard sonrası gerçek yazıcı COMMIT'i, fence COMMIT'i ve final boşluk guard'ında psql3 gözlendi; dump ve son COMMIT'e ulaşılmadı. Son sentinel bağımsız readback yapılmadı ve hedef kapalı kaldı. Bakım kaybında nonce/xid/binding bağlı COMMIT doğrulandı, reopen doğrulanmadı ve hedef kapalı kaldı. Kaynak bağlantısı kaybında tamamlanma manifesti üretilmedi. Ağ blackhole/reset, cross-cluster ve dış Storage bu deneylerin kapsamında değildir. Ham dump/SQL/özel capture dosyaları bu arşive alınmadı.

`harness/` dosyaları çalışmış yerel deneyin kaynak kayıtlarıdır; özel geçici yollar ve root kimlik koruyucuları açıkça görülür. Başka bir veritabanına yönlendirerek doğrudan çalıştırılacak genel bakım araçları değildir. Testler sentetik kimlikler ve sahte/yok sağlayıcılarla yürüdü. Gerçek LLM/insan değerlendirmesi, JWT/Storage, bulut, kurumsal hukuki sebep/saklama ve insan terfi onayları açık kalır. S9/S9B/S9C günlük gizliliği ayrı sonraki dilimdir.

`archive.json` bu dizindeki dosya baytlarını, `.ai/evidence/032-operations-readiness-r1.json` bu kabulün kapsamını bağlar. Eski hosted c45 makbuzu yalnız önceki kaynağın kabulü olarak tutulur.
