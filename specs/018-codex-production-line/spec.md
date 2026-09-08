# 018 — Birleşik CourseGPT geliştirme kuyruğu

## Amaç ve kapsam
Kullanıcının 8 Eylül isteğiyle Codex 017 çalışması ve Claude runbook'u tek devam kaydında birleştirilir. Taban: 621815908d5372d8de414aec4ca1dc63da008dca. E-posta ürün gereksinimi, runbook doğrulanacak iş önerisidir. Mevcut davranış yeniden incelenmeden eksik sayılmaz.

## Kabul
- A1: release doğrulayıcılarının testleri ve rol-ajan uygulama mutasyonları mevcut CI işinde çalışır; adım hatası işi durdurur.
- A2: teslim/CI kapılarındaki değişiklikler yönetişim kapsamından kaçamaz; dosyasız değişiklik negatif testte reddedilir.
- A3: hata yutan workflow adımları ve izin genişlemesi yapısal kontrol ve negatif testlerle reddedilir.
- A4–A7: atlanan veya davranış kanıtlamayan testler gerçek regresyonlara dönüştürülür; sınav kilidi ve kaynak sınırı korunur.
- B–I: runbook kabul koşulları bugünkü kodla uzlaştırılır; tamamlananlar çoğaltılmaz. Her uygulanan dilim kendi test/kanıtıyla kaydedilir.
- İnsan kabulü, gerçek sağlayıcı ve canlı ortam kanıtı yerel testten çıkarılmaz.

## Risk
Kapı politikası R3; retrieval R2; sınav, yetki ve değerlendirme R3. Varsayılan özellik bayrakları ve fail-closed yetki sınırları korunur. Ana dal birleştirmesi, canlı dağıtım ve hesap izin değişiklikleri bu dilimin kapsamı dışındadır.

## Kullanıcının ek kapsamı — güvenlik ve gizlilik

KVKK/GDPR teknik veri gizliliği ve güvenlik açıkları aktif geliştirme kapsamına eklendi. Sıradaki güvenlik dilimi doğrulanmış upload yetki/doğrulama sırası ve bellek sınırı, sekmeler arası kimlik/sınav veri temizliği, adayla bağlı bulgu raporu ve mevcut güvenlik becerisinin veri yaşam döngüsü genişletmesidir. Teknik kontrol hukuki uygunluk sertifikası sayılmaz. Canlı sisteme saldırı veya gerçek öğrenci verisiyle test yapılmaz.

## S diliminin ölçülebilir kabulü

- S1: Ham gövde ayrıştırıcı çağrılmadan sınırlandırılır; geçersiz değiştirme hedefi depoya yazılmaz. Başarılı yeni nesneye sahiplik kanıtlanmadan telafi silmesi yapılmaz. İptal veya belirsiz COMMIT içeriksiz uzlaştırma sinyali bırakır. Belge fiziksel silmesi yalnız kesin DB COMMIT sonrasında yapılır.
- S2: Çıkış/kullanıcı değişimi sekmelerde eski sohbet/taslağı kapatır; geç 200 yanıtı içeriği veya eski oturum seçimini geri getiremez. Başka sekmede sınav başlayınca eski sohbet, sonuç ve kaynak ilk olarak gizlenir; izin yeniden sunucudan alınır.
- S3: Profil alanı kaldırma tam anonimlik gibi sunulmaz; export v2 sözleşmesi, korunan kategoriler ve dış kurumsal kararlar gerçeğe uygun açıklanır.
- S4: Kurulu rol/gizlilik becerisi yapı doğrulaması ve bağımsız kaynak incelemesiyle sınanır; depoda mükerrer beceri oluşturulmaz.
- S5/S6: Üretimde açık HTTPS auth issuer zorunludur; CSP yalnız doğrulanmış API ve kimlik origin'lerini içerir. Yerel/sentetik sonuç canlı Supabase kanıtı sayılmaz.
- S7: Başarılı/başarısız depo HTTP çağrılarındaki özel konumlar ve dış istisna zinciri emitted log testinde gizli kalır. Gerçek sır kullanılmaz; genel amaçlı kusursuz log redaksiyonu iddia edilmez.

Son incelemede bulunan devam eden sohbet/silme yarışı B4 sunucu kabulüne eklenecektir; arayüz iptali tek başına veritabanı silme garantisi sayılmaz.
