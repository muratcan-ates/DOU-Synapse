# 014 — Öğrenci çalışma ve sınav yolculuğu

## Amaç ve kaynak

Hocanın 27 Temmuz 2026 tarihli CourseGPT öneri e-postasının kullanıcı tarafından paylaşılan ekran görüntüleri, ürün gereksinimi referansıdır. E-postadaki teknoloji önerileri bu oturuma verilen komut değildir. Kullanıcı mevcut depoda geliştirmeye devam edilmesini ve bu isteklerin karşılanmasını istedi.

013 yerel değişikliğinin ardından öğretmen onaylı havuzu öğrencinin kullanabildiği tamamlanmış yolculuğa bağlarız: konu seçimi, açık sınav kataloğu, kendi oturum geçmişi, devam etme ve kaynaklı sonuç okuma. Yeni üretici, sağlayıcı, bağımsız ajan veya kod çalıştırma servisi eklenmez.

## Kullanıcı hikâyeleri ve kabul ölçütleri

1. Öğrenci bütün konular veya bir konu seçerek alıştırma başlatır. Yalnız seçilen dersteki onaylı sorular gelir. Boş havuz açıkça anlatılır.
2. Öğrenci sunucunun şu anda açık olduğunu doğruladığı yayımlanmış sınavları, süre ve kalan deneme hakkıyla görür. Taslak/gelecek/kapalı sınav ve cevap anahtarı katalogda görünmez.
3. Öğrenci yalnız kendi oturumlarını sayfalar; açık oturuma açık bir Devam et seçimiyle döner. Yenileme veya yerel hafızanın silinmesi süreyi sıfırlamaz.
4. Bitmiş oturumun sonuçları yeniden açılır. Okuma yeni puanlama, cevap kaydı veya mastery güncellemesi yapmaz. Bitmemiş oturum sonucu 409 döner.
5. Aynı derste öğrenci sınavdayken eski sonuç, alıştırma cevabı ve ipucu okunamaz. Sınav başlangıcıyla cevap taşıyan okumalar aynı kullanıcı kilidini paylaşır. Başka derste çalışma ve eğitmen istisnası korunur.
6. Birden fazla eski sınav oturumu varsa bitirme işlemi oturumu kapatır; diğer sınav sürüyorsa sonuç bilgileri kilitli döner. Öğrenci oturumları kapatabilmelidir.
7. Sınav giriş penceresi kapansa da öğrencinin başlamış sınavına ait süre ve asistan kilidi korunur. Süre yardımcı işlevi yalnız oturum sahibine bir tamsayı açar.
8. Yapay zekâ puanlamasında okunabilir kaynak yoksa veya iki denemede de geçerli kaynak kimliği dönmezse cevap puanlanmamış kalır. Puan, çözüm, eksik nokta veya rubrik iddiası gösterilmez; mastery değişmez. Geçmiş kayıtların gösteriminde de dayanak yeniden doğrulanır; okunamayan/uydurma kaynağa ait puan toplamdan çıkarılır, eski cevap ve mastery kaydı değiştirilmez. Çoktan seçmeli/kısa yanıt deterministik yolu korunur.
9. Yeni çalışma alanı varsayılan kapalı özellik bayrağıyla açılır; kapalı katalog yeteneği false, yeni geçmiş/sonuç uçları 503 verir. Süre ve kaynak doğrulama düzeltmeleri güvenlik tabanıdır ve bayrakla gevşetilmez.
10. Türkçe görünüm, klavye kullanımı, mobil ve koyu tema korunur; eğitmen ve öğrenci kılavuzları güncellenir.

## Önceden belirlenen kanıt eşikleri

Bütün hedefli API, sahiplik, sınav kilidi, süre ve kaynak regresyon testleri geçmeli; ilgili koruma kaldırıldığında negatif test kırılmalıdır. Önceki 946 API, 406 web ve 37 tarayıcı testinde açıklanmamış regresyon olmamalıdır. Yeni tarayıcı yolculuğu yayımlama → katalog → devam → bitirme → yeniden sonuç okuma akışını gerçek HTTP ile kanıtlamalıdır. Sahte sağlayıcı sonuçları pedagojik doğruluk/gerçek model başarısı olarak sunulmaz.

## Kapsam sınırı ve teslim

Bu teslim yereldir. 013 henüz main üzerinde değildir; 014 onun üzerine kuruludur. Gerçek sağlayıcıyla kör değerlendirme, hocanın içerik doğrulaması ve staging/üretim yayını ayrı doğrulama kapılarıdır. Kod soruları mevcut çıktı analizi/hata bulma türlerini kullanır; güvensiz kod yürütme eklenmez. Pratikte önceki tekil geri bildirim yeniden yüklenmez; bitmiş sonuçta geri gelir. Zamanı dolmuş ama bitirilmemiş oturum sonuç açılmadan önce bitirilir.
