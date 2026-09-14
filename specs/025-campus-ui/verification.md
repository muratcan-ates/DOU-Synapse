# Kampüs arayüzü doğrulaması

Tarih: 14 Eylül 2026. Dal: `025-campus-ui`.
Taban: `f4a0952c41232df84f937f05991a417d959a5285`.

## Değişiklik

Ortak tasarım ve gezinme; giriş/kurtarma, panel, ders listesi, profil, hesap,
gizlilik, yönetim ve ders içindeki bütün çalışma ekranları yenilendi.
Ders arama ve rol filtreleri, açılır ders ayrıntıları, sohbet başlangıçları,
sınav soru gezinmesi ve politika bölüm bağlantıları mevcut işlevlere bağlandı.
Renkler, okunabilir yazı ölçeği, mobil gezinme ve açık/koyu tema ortaklaştırıldı.
Yeni bağımlılık, API, migration, yetki veya model değişikliği bulunmuyor.

## Otomatik kontroller

- Web birim testleri: 632 geçti, başarısız test yok; 51 dosya, 1540 doğrulama.
- TypeScript kontrolü ve Next.js üretim derlemesi geçti.
- Açık/koyu tema metin AA ve kontrol sınırı kontrast kontrolü geçti.
- Doküman, migration sırası ve iş akışı politikası kontrolleri geçti.
- API statik incelemesi: Ruff, biçim kontrolü ve mypy geçti; backend değiştirilmedi.
- Mevcut E2E beklentileri yeni başlık, açılır ders araçları ve koyu tema rengine
  uyarlandı. Beklentiler kaldırılmadı; test atlama, süre artırma veya görüntü
  referansı yenileme yapılmadı.

## Tarayıcıda doğrulanan davranışlar

İzole yerel PostgreSQL veritabanı, yerel API ve sahte model kullanıldı.
Yalnız depodaki sentetik öğretmen/öğrenci kimlikleri ve üretilmiş ders materyalleri
kullanıldı. Kullanıcının referans ekranları ve kişisel bilgileri depoya eklenmedi.

- Öğretmen ve öğrenci girişi/çıkışı, role göre menüler, masaüstü menü daraltma.
- Panel ve profil açık/koyu görünüm; mobil panel ve ders kartları.
- Türkçe `İŞLETİM` araması, rol filtresi ve boş sonuçtan filtre temizleme.
- Materyal arama; mobil kaynak listesi; sorudan ilgili PDF pasajına geçiş.
- Mobil sohbet başlangıcı, çok satırlı yazma, gönderim, boş gönderimi engelleme
  ve kaynak atıfları. Kaynak bağlantısı doğru pasajı ve çevresini açtı.
- Öğrencinin süreli sınavında asistan kilidi, cevabı gönderme, sınavı bitirme,
  sonuç, yanlış cevap açıklaması ve kaynak bağlantısı. Cevap anahtarı ancak
  sınav bitince göründü. Testin sonunda etkin sınav bırakılmadı.
- Soru havuzu, sınav planı, analitik ve AI kalite ekranları; üyelerde arama.
- Politika bölüm bağlantıları; tablet kaydet çubuğu mobil gezinmeyle çakışmıyor.
- Mobil yönetim kayıtları etiket/değer düzeninde ve e-postalar maskeli.
- Hesap ve gizlilik sayfaları; veri silme veya hesap kapatma uygulanmadı.
- İncelenen mobil sayfalarda 375px ekran genişliğinde yatay sayfa taşması yok.
  Politika ve üyeler 768px tablette, ders çalışma ekranları 1280px masaüstünde
  ayrıca incelendi.

## Kapsam sınırları

Bu kayıt tam otomatik E2E veya canlı ortam sertifikası değildir. Mevcut sahipliği
kanıtlanmış API/veritabanı isteyen E2E harness'i atlanmadı; tam Playwright ve Linux
piksel karşılaştırmaları bu yerel oturumda çalıştırılmadı. PR CI sonuçları ayrıca
incelenmelidir. Görüntü referansları korunmuştur; tasarım değişiminin Linux ortamında
incelenmesi gerekir.

Üretim kimlik sağlayıcısı, gerçek LLM kalitesi, dağıtım, yedek/geri dönüş ve hukuki
uygunluk bu görsel revizyonla doğrulanmış sayılmaz. Tam backend test paketi bu
oturumda yeniden çalıştırılmadı. Hareket azaltma CSS kuralı kontrol edildi; işletim
sistemi tercihi veya gerçek IME girişi tarayıcıda taklit edilmedi.

R3 yönetişim kaydı bağımsız mühendislik, alan ve güvenlik incelemelerini bekler.
Üretime terfi veya birleştirme kararı verilmedi. Toplayıcı dossier betiği çalıştırılmadı.
