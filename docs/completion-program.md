# CourseGPT tamamlama programı

Bu belge kullanıcı tarafından istenen sürekli geliştirme programının kaldığı yeri tutar. E-posta ürün gereksinimi referansıdır. Hedef: öğretmenin kaynaklarıyla sınırlı, kaynak gösteren, Sokratik çalışmayı ve güvenilir sınav değerlendirmesini destekleyen, teslim kanıtları hazır CourseGPT.

## Güncel durum

Aktif dal: `016-agent-skills`; çalışma dizini: `/Users/muratates/code/dou-synapse-016-agent-skills`; temel: `ed6103fbe53be3888252074db0a722cfe1be617c` (geçerli015 yerel adayı; içinde013/014 var). Uzak main en son `ba69ff9eec0a2867614dd145eb6e995f6c0af5ac` olarak doğrulandı; bu tur yeni uzak sorgu yapılmadı. Hiçbir yerel dilim main'e veya canlıya alınmadı.

Ürün test kanıtı: 1154 API, 421 web, 38 tarayıcı sonucu önceki test edilmiş ürün anlık görüntüsüne aittir; 016 uygulama kodunu değiştirmez. 015 aday düzeltmesi ve devralınan kanıt için specs/015-completion-program/candidate-correction.md okunmalıdır. 016'nın kendi kanıtı beceri paketi, karşı testler ve geçici çalışma akışı denemeleridir; ayrıntı specs/016-agent-skills/verification.md. Kesin güncel SHA çalışma ağacından ve teslim raporundan doğrulanır.

## İş sırası ve bitirme ölçütleri

| Sıra | İş paketi | Durum | Tamamlanma ölçütü / kanıt |
|---|---|---|---|
| 1 | Sağlayıcı ayarları ve erişim ön kontrolü | Yerelde doğrulandı | Tek varsayılan kaynak; sır sızdırmayan çevrimdışı rapor; hedef başına sınırlı gerçek erişim denemesi; sahte/eksik yapılandırmada gerçek değerlendirme reddi |
| 2 | Değerlendirme kanıt zinciri ve izole veri hazırlığı | Yerelde doğrulandı | Sunucu SHA/yapılandırma/çalışma kimliği ile gerçek cevap üretiminin bağlanması; yanıltıcı notların reddi; üç bağlantının aynı izole veri tabanına gittiğinin yazmadan doğrulanması |
| 3 | Öğrencinin yarım kalan çalışması | Yerelde doğrulandı | Sekme yenilemede gönderilmemiş cevap korunur; sahiplik/süre önce doğrulanır; çıkış/gönderme/bitirme temizler; kayıtlı alıştırma geri bildirimi güvenle açılır |
| 4 | Kaynak değişikliğinin sınava etkisi | Yerelde doğrulandı | Eğitmen sorunun kullanıldığı sürümleri sayfalar ve doğru kâğıdı salt okunur açar; öğrenci verisi ve cevap anahtarı yetkisiz sızmaz |
| 5 | İnsan kabulü ve örnek ders paketi | Çevrimdışı paket hazır; insan kabulü bekliyor | Mevcut materyal/goldset bütünlüğü; soru ve beklenen kaynaklar; bağımsız insan etiketleri için paket; maliyet/çağrı sınırı ve devam yönergeleri |
| 6 | Birleşik yerel sürüm doğrulaması | Yerel testler geçti | API/web/tarayıcı negatif testleri; OpenAPI/docs; kaynak bütünlüğü; değişikliklere bağlı AI kanıtı; kesin commit |
| 7 | Gerçek model kalite ölçümü ve düzeltme döngüsü | Dış girdi bekliyor | Gerçek sağlayıcı erişimi + onaylı materyal; kaynak isabeti/ret/Sokratik davranış/puanlama kör değerlendirmesi; yalnız başarısız katmanı düzeltip yeniden ölçme |
| 8 | Entegrasyon ve yayıma hazırlık | Yerel aday sonrası | 013+014+015 farkı ve göç sırası incelemesi; gelen dallardaki0016 çakışmasını içeri almama; incelenebilir PR paketi; bağımsız onay kayıtları |
| 9 | Staging işletim ve geri dönüş doğrulaması | Ortam erişimi bekliyor | Gerçek oturum açma/depolama/işçi akışı; öğrenci/eğitmen/yönetici sınırları; gecikme/maliyet; yedekten geri yükleme ve rollback kanıtı |
| 10 | Hocaya teslim ve kullanım kabulü | 7–9 sonrası | Çalışan URL, örnek ders, tarihli gerçek başarı raporu, iki rol kılavuzu, canlı senaryo ve öğretmen kabulü |
| 11 | Repo becerilerinin taşınabilir Codex paketi | Yerelde doğrulandı | 17 eşlenmiş beceri, 3 güncel ortak DOU metni, yapısal/negatif kontroller, bağımsız kullanım denemesi ve CI tanımı |
| Koşullu | Taranmış materyal OCR | Materyale bağlı | Yalnız gerekli sayfalar için metin çıkarma/kaynak sayfa eşleme testleri; ihtiyaç yoksa gerekçeli kapsam dışı |

## Çalışma döngüsü

1. Dalı, son commit'i, çalışma ağacını ve aşağıdaki kaldığı-yeri kaydını doğrula. Başka çalışmanın dosyalarına dokunma.
2. En yüksek öncelikli hazır iş paketini seç; kabul ölçütünü ve dosya sahipliğini netleştir. Bağımsız işleri paralel yürüt.
3. Uygula, değişen davranışın anlamlı olumlu/olumsuz testlerini çalıştır, bulguları kaydet. Bir kapı tamamlanınca sıradaki hazır işe geç.
4. Her teslimde kodda mevcut / yerelde test edildi / main'e birleşti / staging'de doğrulandı / canlıda kabul edildi durumlarını ayrı yaz.
5. Anahtar veya insan kararı bekleyen iş için somut paket hazırla ve diğer hazır işleri sürdür. Etiket/onay/gerçek model sonucu uydurma. Hazır iş kalmadığında aynı engeli tekrar tekrar deneme; gereken girdiyi tek yerde açık bırak.
6. Harici mesaj, canlı yayın, main birleşimi veya harici yetki değişikliğinde mevcut açık yetkiyi ve ilgili onay kapısını kontrol et; önce bütün yerel hazırlığı tamamla.

## Dış girdiler

Gerçek Groq/Gemini değerlendirme anahtarı şu an bulunmuyor; anahtar değerleri sohbet veya raporlara konmaz. Öğretmenin örnek ders kapsamını ve bağımsız puanlama etiketlerini onaylaması gerekiyor. Staging/üretim erişimi ve gerçek kullanıcı kabulü bu yerel testlerin yerine geçmez. Yeni sağlayıcı erişim denemesi yalnız açık sınırlı komutla yapılır; otomatik sınırsız ücretli çağrı döngüsü yoktur.

## Kaldığı yer

015 yerel uygulaması tamamlandı ve eski adaylar korundu. 016, root koordinasyonunda 3 DOU becerisi/araç/docs, mail_requirements ile 9 Speckit ve student_api_audit ile 5 Git becerisi olarak bölündü. Kalıcı sunucu veya test veritabanı başlatılmadı; davranış denemeleri geçici dosya alanında yapıldı. Kaynak dokümanlara ve eski immutable AI kayıtlarına dokunulmaz.

016 beceri doğrulaması tamamlandı. Sıradaki ürün adımı ayrı gerçek değerlendirme anahtarı ve öğretmen kaynak/etiket girdisiyle kabul paketini çalıştırmaktır. Bu girdiler yokken gerçek model veya insan sonucu üretilmiş sayılmaz. 90+ ajan kataloğunu araştırmaya devam etmek için yeni bir kaynak adı/bağlantısı gerekir. Mevcut engeli aynı sorgularla tekrar denemek yerine hazır paketi ve gereken girdileri koru.

## Ajan/beceri envanteri ek kontrolü

Kullanıcı mevcut 90+ ajan paketini ve repo becerilerini kontrol etmemizi istedi. [Envanter](agents-skills-inventory.md): repo 17 Claude becerisi ve yerel 9 Codex DOU becerisi doğrulandı; 90+ ajan kataloğu incelenen konumlarda bulunamadı. 015 incelemesinde kurulum yapılmamıştı. 016 ile repo içi17 Codex karşılığı eklendi, 3 eski DOU yönergesi güncellendi. Küresel kopya kurulmadı. Kullanım ve doğrulama docs/agent-skills.md içinde; 90+ katalog kaynağı hâlâ takip girdisidir.
