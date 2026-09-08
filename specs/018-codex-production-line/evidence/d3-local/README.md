# D3 gerçek yerel kurtarma kabulü

Kaynak v4 SHA a0bc48077e2fbdcfc904e31d08750b5c0b858cf737f83f35389cde5661f1777b.
52 çevrimdışı test/9 mutant ve ayrı gerçek PostgreSQL16.14/pgvector0.8.0 deneyleri.
V2 aynı DB bağlantısını kapatmayı deneyip reddedildi; v3 fence sonrası restricted
owner ile CREATE hatası verdi. Bu sonuçlar korunur. V4 CREATE-as-DBA+ALTER OWNER
kullanır; rolün CREATE yetkisini genişletmez ve ownership/RLS/ACL'yi korur.

Gerçek05 restore24.39s, kesin COMMIT. Sonraki3.542s salt-okunur karşılaştırmada29
ilişkinin şema/satır hashleri,20000 sentetik chunk, owner/ACL/rol bileşeni ve dört
gerçek dou_app RLS kimliği eşleşti. Bir ANN sorgusunda recall@8=.875 gözlendi;
C1 tam retrieval kabulü veya semantik model kalitesi olarak sunulmaz.

| Gerçek senaryo | Ölçülen sonuç |
|---|---|
| Dolu06 hedef | TARGET_NOT_EMPTY; sentinel değişmedi; fence uygulanmadı |
| COMMIT öncesi08 hata | Gerçek22012 ve child exit3; hedef kapalı, bağlantı0 |
|09 tamamlanma makbuzu kaybı | Gözlemci gerçek COMMIT'i gördü; ürün makbuzu alamadı ve hedefi açmadı |
|10 COMMIT sonrası açma hatası | Ayrı committed/reopen-unconfirmed kodu; hedef kapalı |
|11 kapalı hedefe yeni uygulama bağlantısı | Gerçek dou_app önce bağlandı, fence sonrası sunucu açıkça reddetti; restore sonra tamamlandı |

08'de scriptin enjekte edilen hatası tam25459.satırda, son COMMIT öncesindeydi.
Hash bağlı bağımsız incelemeden sonra yalnız08 ayrı root işlemiyle açıldı; salt
okunur karşılaştırma başlangıçtaki boş DB, owner/ACL/format/katalog ve rol bileşeni
eşitliğini doğruladı.03/04/09/10 bu işlemin dışında kapalı tutuldu.09/10 kontrollü
teslim/bakım hata enjeksiyonudur; bütün gerçek ağ kopması biçimlerini ölçmez.

Ham arşiv, SQL ve özel stdout içeriği depoya kopyalanmaz. Sonuçlar bunların
hashlerini taşır; bu dizinin byte eşlemesi archive.json'dadır. İlk kaynak D1/D2
göçlerinden öncedir; yeni sürüm şema eşliği ayrı kabul gerektirir.07 eşzamanlı
yazıcı, cross-cluster snapshot/control-loss, gerçek geniş rol grafiği negatifleri,
bulut barındırma/yedek şifreleme/saklama/imha ve silinen verinin geri gelmesini
önleyecek kurumsal uzlaştırma bu sonuçlarla tamamlanmış sayılmaz.
