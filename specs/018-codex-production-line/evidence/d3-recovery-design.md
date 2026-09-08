# D3 — Veritabanı kurtarma tasarımı

Durum: tasarım; henüz uygulanmış veya tatbikatı tamamlanmış bir kontrol değildir. Sorumlu geliştirme işi: 018. Gerçek yedek işletmecisi ve bağımsız incelemeci kurum tarafından atanmalıdır.

Mevcut belgelerde pg_dump ve pg_restore komutları var; araçların varlığı, verinin geri döndüğünü veya erişim kurallarının korunduğunu kanıtlamaz. Hedef, ayrı ve boş bir veritabanına tekrar üretilebilir kurtarma denemesidir. Canlı hedef belirlenmediği için ilk tatbikat yalnız görevimizin yapay yerel verisiyle yapılır.

## Araç sözleşmesi

- `backup.sh`: açık kaynak bağlantısı, yeni özel dizin, custom-format dump, tamamlanma manifesti. Bağlantı sırları komut argümanına, rapora veya hata çıktısına girmez. Başarısız dump geçerli manifest üretmez; mevcut yedeğin üstüne yazılmaz.
- Manifest: arşiv hash'i, kaynak commit/şema dosyası hashleri, PostgreSQL/pgvector sürümü, UTC zaman ve uygulanan kapsam. Hash bozulmayı belirler; arşivin güvenilir bir kaynaktan geldiğini tek başına kanıtlamaz.
- `restore.sh`: açık hedef bağlantısı, doğrulanmış arşiv hash'i, kaynak-hedef ayrımı ve boş hedef ön koşulu. DROP/CLEAN veya mevcut verinin üstüne yazma yolu yoktur. Restore tek transaction ve hata halinde başarısız durumla biter. Uygulama ve worker rolleri ayrımı, owner ve GRANT bilgileri korunur/yeniden doğrulanır.
- Dry-run bağlantı kurmadan niyeti gösterir; dry-run sonucu gerçek geri yükleme kanıtı olarak sunulmaz.

## Yerel tatbikat kabulü

1. Taze benzersiz kaynak DB: bütün göçler, iki kullanıcı/iki ders, belge ve birbirinden farklı vektörler; yalnız sentetik veri.
2. Dump al; yeni boş hedefe restore et. Tablo bazında satır sayıları, kanonik içerik hashleri, uzantı/index tanımları ve FORCE RLS/GRANT durumları karşılaştır.
3. Aynı gerçek dou_app rolüyle yoğun arama sonucunu, kaynak metadata'sını ve başka ders/üyelik reddini karşılaştır. Yaklaşık indeksin yeniden kurulması varsa veri bütünlüğü ve ANN kalite sonucu ayrı kaydedilir; fark sessizce eşit sayılmaz.
4. Arşiv hash'i bozukken, hedef doluyken ve komut başarısızken kontrollü reddi doğrula. Hedef verisi değişmemelidir. Kaynak-hedef aynıysa reddet.
5. Fiziksel dosya deposu, sağlayıcı kopyaları, anahtar yönetimi, şifreleme, saklama ve restore sonrası imha eşleme kayıtları ayrıca gereklidir. PostgreSQL dump'ı bütün ürünün yedeği olarak adlandırılmaz.

CI'da araçların negatif/argüman/dry-run testleri mevcut kalite kapısına eklenir. Gerçek restore ve süre ölçümü sürüm/ortamla kaydedilir; işletme SLO'su veya "15 dakika içinde kurtarma" taahhüdü bu tasarımdan çıkarılmaz.
