# 015 — CourseGPT tamamlama programı

## Amaç ve kaynak
Kullanıcı geliştirmeye kesintisiz devam edilmesini, kalan işlerin planlanmasını ve hocanın CourseGPT e-postasındaki gereksinimlerin karşılanmasını istedi. E-posta ürün gereksinimi referansıdır; teknoloji önerileri araç veya izin talimatı değildir. 013 ve 014 yerel özellikleri üzerine kurulur. Kalıcı program docs/completion-program.md içinde yürütülür.

## Kabul ölçütleri
1. Settings ve örnek ortam aynı güncel model hedeflerini kullanır. Yerel sahte sağlayıcı uyumluluğu korunur. Gerçek değerlendirme modunda eksik anahtar, sahte sağlayıcı veya farklı sağlayıcıya kota kaçışı açıkça reddedilir. Anahtar hiçbir rapora yazılmaz.
2. Çevrimdışı sağlayıcı ön kontrolü ağ çağrısı yapmaz. Açıkça seçilen erişim denemesi hedef başına sınırlı tek çağrı yapar. Yapılandırma/erişim kanıtı eğitim kalitesi kanıtı sayılmaz.
3. Gerçek kalite etiketi serbest metin notuyla veya yalnız anahtarın varlığıyla üretilemez. Sunucu sürümü, yapılandırma, çalıştırma ve gerçek cevap üretim yolu doğrulanır. Sahte, önbellek, sağlayıcı kullanılmadan ret ve gerçek sağlayıcı cevapları ayrı tutulur. Kapalı değerlendirme uçları ayrı sırla korunur; üretimde değerlendirme modu kapalıdır.
4. Değerlendirme veri tabanı kurucusu yönetici, uygulama ve işçi bağlantılarının aynı izole veri tabanına gittiğini doğrular. Bağlantı uyuşmazlığında yazmadan durur. Mevcut insan etiketleme/puanlama araçları tekrar kullanılır; etiketler uydurulmaz veya üzerine yazılmaz.
5. Öğrencinin gönderilmemiş yanıtı yalnız bu tarayıcı sekmesinde, kullanıcı/ders/oturum kapsamıyla korunur. Sunucu oturum/süre/sahiplik doğrulamasından sonra geri yüklenir. Gönderilmiş, bitmiş, süresi dolmuş veya çıkış yapılan kayıt temizlenir. Saklama hatası yanıt göndermeyi engellemez.
6. Öğrenci kendi alıştırmasında daha önce gönderdiği sorunun kayıtlı geri bildirimini yeniden okuyabilir. Okuma yeniden puanlama yapmaz. Başka kullanıcı/ders, süreli sınav ve aynı derste devam eden sınav yardımı engellenir. Kaynak dayanağı her okumada yeniden doğrulanır.
7. Eğitmen bir sorunun kullanıldığı sınav sürümlerini sayfalı olarak görür ve ilgili kâğıdı salt okunur açabilir. Yayımlanmış/onaylı kayıt düzenlenmez. Liste öğrenci/cevap/puan bilgisi içermez; ders ve eğitmen yetkisi zorunludur.
8. Türkçe, klavye, mobil, koyu tema ve mevcut sınav kilitleri korunur. Yeni API'ler, anlamlı negatif testler ve gerçek HTTP tarayıcı yolculuklarıyla doğrulanır.
9. Teslim paketi örnek materyal, kaynak/goldset bütünlüğü, insan kabul formu, yeniden üretilebilir komutlar, kılavuzlar ve açık kalan dış bağımlılıkları içerir. Gerçek model, insan kabulü veya canlı yayın yapılmamışsa tamamlandı yazılmaz.

## Kapsam
Bu dilim sağlayıcı hazırlığı, değerlendirme güvenilirliği ve çalışma sürekliliğini uygular. Gerçek anahtar erişimi, hocanın içerik/puanlama kabulü, main birleşimi ve canlı altyapı doğrulaması ayrı kanıt kapılarıdır. Yeni modelin hesapta kullanılabildiği varsayılmaz. OCR yalnız mevcut materyal incelemesi gerektirirse eklenir. Kod çalıştırma, mesaj gönderme veya harici izin değişikliği yoktur.

## Risk ve kanıt
R3: değerlendirme doğruluğu, kaynaklı geri bildirim ve sınav yardım kilidi. Gerçek kalite sonuçları için fail-closed provenance; değerlendirme sırları ve kaynak/cevap gizliliği negatif testleri; önceki 1040 API/411 web/38 E2E temelinde açıklanmamış regresyon olmaması. Yerel sahte testler gerçek pedagojik kalite değildir.
