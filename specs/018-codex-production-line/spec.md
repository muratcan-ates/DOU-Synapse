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

Son incelemede bulunan devam eden sohbet/silme yarışı B4 sunucu kabulüne eklendi; arayüz iptali tek başına veritabanı silme garantisi sayılmaz.


## B ürün ve gizlilik kabulü

- B1: Yeni öğrenme çıktısı seçilen konuya bağlı kaydedilir; konusuz çıktı ayrı dağılım grubu olarak açıklanır.
- B4: Başarıyla silinen ders/tüm geçmiş/profil kapsamındaki bekleyen yeni sohbet yeniden yazılamaz. Son kayıt ve silme kısa aynı-kullanıcı kilidini paylaşır; kapsam sürümleri başka ders/oturumu iptal etmez. Silme rollback olursa geçerli sohbet korunur. Model süresince kilit tutulmaz; yeni oturum son denetime kadar geçicidir. Kalıcı tablo gerçek dou_app RLS, artan sürüm ve dar sütun izinleriyle korunur.
- B4 UI: Kendi oturumunu ve ders geçmişini açık onayla silme; iptal/hata/başka sekme/geç yanıt durumlarında doğru kapsam ve dürüst sonuç. Aktif sınavın yardım kilidi korunur.
- B5: Eğitmen geçmişinde gerçek önce/sonra değerleri, sayfalama, ad yerine doğrulanabilir hesap etiketi; istek hatası taslağı silmez. Rol yenilenirken özel görünüm kapanır, aynı eğitmenin RAM taslağı korunur; kimlik/rol/ders değişiminde eski taslak geri gelmez.
- B6: Bayrak kapalıyken sınıflandırma onarımı için çalışmayan bağlantı sunulmaz; mevcut uygun soru havuzu geçerli sunucu hazırlık denetimiyle yayımlanabilir.
- B7: Durum/konu filtreleri sunucuda, imleç filtre kapsamına bağlı; gecikmiş yanıt, boş liste ve karar sonrası seçim doğrulanır.

B2 zaten uygulanmıştı ve bu adayda tekrar doğrulandı. B3'ün mevcut kaynak doğrulaması korunur. Yeni code_trace/bug_hunt üretim ve taslak yazımlarında en az bir benzersiz, boş olmayan ölçüt ve toplam 100 ağırlık gerekir; eksik/boş rubrik 422 ile atomik reddedilir, eski rubriksiz kayıtlar açılabilir. Rubrikli kod puanlamasında tanımlı ölçütler tam birer kez değerlendirilir. grounded_missing_criterion gerçekten eksik puanlanan ölçüt ve okunabilir ders parçasındaki doğrulanmış alıntıyla sınırlıdır; kayıtlı geri bildirim açılırken kaynak/ölçüt yeniden denetlenir. UI bunu “Eksik ölçütün dayanağı” diye sunar. Toplam puanı 80 ve is_correct=true olan cevapta da gerçek eksik ölçüt görünür. Aktif sınavdan rubrik/çözüm/geri bildirim sızmaz. Kod çalıştırılmaz. Bu teknik kabul anlamsal doğruluk veya gerçek model pedagojik kabulü değildir; o kabul E'de kalır.

B4 UI silme olayını kaçıran sekmede focus/pageshow/visibility yeniden denetimi yapar. Olay mesajı silmenin kalıcı kanıtı değildir. chat_history_changed çatışması rol/üyelik değişiminde de üretilebilir; eski yanıt otomatik yeniden gönderilmez.

## C ölçüm kabulü

Arama değişimi önce benzersiz yerel veritabanında yapay korpus, gerçek RLS, doğal sorgu planı, exact referans ve filtre/boş/üyelik/eşitlik kontrolleriyle karşılaştırılır. Aynı projection, sorgu ve korpus hashleri karşılaştırmanın ön şartıdır. Küçük örneklem p95'i nüfus tahmini değildir; yaklaşık aday penceresi tüm korpusun eşitlik sırasını garanti etmez. Yerel pgvector0.8.0 sonucu CI0.8.6 veya gerçek E5 semantik kalite kanıtı sayılmaz.

Prepared runtime karşılaştırması gerçek SQLAlchemy/psycopg otomatik hazırlama eşiğini ve aynı fiziksel bağlantıyı içerir. Dense SELECT boyunca custom plan, başarıda önceki mod, SQL hata/iptalinde çağıran rollback'i sınanır; FTS politika sızıntısı kabul edilmez. Hashing holdout'ta eski dense/FTS/service ile aday aynı korpus/ayar/altın kümede karşılaştırılır. Non-regression kuralı Recall@5 ve MRR'nin azalmamasıdır. İlk adayın hashing/E5 Recall düşüşü olumsuz kanıt olarak korunur. FTS bileşeni geri çekildikten sonra aynı korpus/model/ayar/altın küme üzerinde yeni aday yeniden ölçülür; eski sonucu yeniden etiketlemek kabul değildir. Eşik veya altın küme sonuçtan sonra değiştirilmez. Gerçek E5 retrieval ve LLM cevap/puanlama kabulü ayrı kanıt ister.
