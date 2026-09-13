# Bilgi İşlem Kılavuzu

> **13 Eylül 2026 — yerel tarayıcı doğrulaması:** kılavuz, kaynak özetleri koşu
> boyunca değişmeyen yerel uygulamada, sentetik hesaplar ve sahte dil modeli
> sağlayıcısıyla sınanan ekranlarla karşılaştırıldı. Gerçek yerel API kullanıldı;
> masaüstü açık görünümde durum alanı, teknik kayıt sekmeleri, görünür filtreler,
> sekme klavye geçişleri ve öğrenciye erişim reddi gözlendi. Ekran görüntüleri özel
> kanıt olarak incelendi. Ayrıntılar ve sınırlar [Kılavuz doğrulama kaydı](guide-verification.md)
> içinde; bu çalışma canlı işletim, gerçek sağlayıcı veya insan kabulü değildir.

**Bilgi İşlem**, platform durumunu ve teknik kayıtları incelemek için salt okunur bir
alandır. Ders içeriğini yönetme, öğrenci yanıtlarını okuma veya kullanıcı yetkisi verme
ekranı değildir.

## 1. Alana giriş

Hesabınızla giriş yaptıktan sonra ana menüdeki **Bilgi İşlem** bağlantısını açın.
Bu bağlantı için ayrı platform yönetim yetkisi gerekir; bir dersin eğitmeni olmak yeterli
değildir. **Profil** ekranındaki **Bilgi İşlem yöneticisi** etiketi ve **Ders rolleri**
listesi farklı yetkileri gösterir. **Bu alana erişiminiz yok** mesajı alırsanız kurumun
yetkilendirme sorumlusuyla
görüşün. Sayfanın adresini bilmek erişim sağlamaz.

## 2. Platform durumunu okuma

**Platform durumu** bölümünde önce ölçüm zamanını, ardından **Uygulama**, **Veritabanı**,
**Vektör veritabanı**, **İstek kotası** ve **Embedding** durumlarını inceleyin. Embedding,
ders metinlerinin aranabilir hâle getirilmesine yardımcı olan bileşendir.

| Görülen durum | Nasıl yorumlanmalı? |
|---|---|
| **Hazır / Sağlıklı** | İlgili kontrol olumlu sonuçlandı; bütün kullanıcı akışlarının çalıştığı garantisi değildir |
| **Hazırlanıyor** | Bileşenin hazırlanması sürüyor; ölçüm zamanını kontrol edip yeniden bakın |
| **Kısıtlı / Hata / Eksik / Ulaşılamıyor** | Ekrandaki bileşen ve durum bilgisini işletim sorumlusuna iletin |
| **Ölçülemedi** | Güvenilir sonuç alınamadı; sağlıklı veya sıfır olarak yorumlamayın |
| **Kapalı** | Bileşen kapalı yapılandırılmıştır; tek başına arıza olarak yorumlamayın |

Bu ekranın göstergeleri sürekli güncellenen bir olay akışı değildir. Son durumu görmek
için sayfayı yeniden açın veya yenileyin. Kontroller aynı anda tamamlanmış tek bir ölçüm
olarak yorumlanmamalıdır. Bir durum kartı tek başına canlıya çıkış veya ders açma onayı vermez.

### Sayılar ve gecikme

Kullanıcı, ders, kaynak ve aktif üyelik sayılarını toplam durum için kullanın.
Son 24 saatlik sohbet bölümündeki **Başarılı sohbet turu**, **P95 gecikme** ve token bilgisi,
kaydı bulunan başarılı sohbetlerle sınırlıdır. Başarısız istekler ve kaydı bulunmayan
çağrılar bu örnekleme dahil değildir; buradan tüm isteklerin başarı oranını hesaplamayın.

**P95**, bu örneklemdeki sohbetlerin yaklaşık yüzde 95'inin altında kaldığı gecikmedir.
Yanındaki başarılı sohbet örneği sayısını birlikte okuyun. **-** gösterimi sıfır
milisaniye anlamına gelmez. Az örnekten genel hizmet hızı sonucu çıkarmayın.

## 3. Teknik kayıtlar

Alt bölümde ilgili sekmeyi seçin. Yazı alanındaki aramayı **Uygula** ile başlatın.
Uygulanmış bir metin filtresi varken görünen **Temizle** düğmesiyle filtreyi kaldırın.
Durum listesinden seçim yapmak filtreyi doğrudan uygular;
metin alanlarındaki arama için **Uygula** gerekir. Yeni filtrede liste başa döner.
Listelerde **Önceki** ve **Sonraki** düğmeleriyle gezinin.

Klavye kullanırken teknik kayıt sekmelerine Tab ile ulaşın; sol/sağ okla sekmeler
arasında, Home/End ile ilk/son sekmeye geçebilirsiniz.

| Sekme | Kullanım ve kapsam |
|---|---|
| **Kullanıcılar** | **Kullanıcı ara** alanını kullanın; e-posta sonuçlarda maskeli gösterilir. Liste yetki, aktif ders sayısı ve oluşturma zamanını gösterir. Buradan rol verilemez, kullanıcı düzenlenemez veya silinemez |
| **Dersler** | **Ders ara** ile kod veya ad arayın. Oluşturan, üye ve kaynak sayılarını inceleyin. Dersin akademik içeriği bu listeden açılmaz |
| **AI kullanım kayıtları** | **Yanıt durumu** ve gerektiğinde **Uç filtresi** ile kayıtları daraltın. Zaman, **Uç** sütunundaki istek yolu, ders bağlamı, sonuç ve performansı inceleyin. Soru, yanıt ve kaynak metni gösterilmez |
| **İşleme işleri** | **İşleme durumu** ile bekleyen, işlenen, tamamlanan veya hata alan işleri seçin. Deneme sayısı ve başlangıç/bitiş zamanlarını inceleyin. Dosya adı ve içeriği gösterilmez; bu alanda yeniden işleme düğmesi yoktur |

Aramada sonuç bulunmaması tek başına kaydın silindiğini kanıtlamaz; önce filtreyi temizleyin.
İşleme hatasında ilgili dersin eğitmeni, kendi **Materyaller** ekranındaki uyarıyı ve varsa
**Yeniden işle** işlemini kullanabilir. Platform genelindeki sorunlar için işletim
sorumlusuna başvurun.

### Bu turda doğrulanan kapsam

Sekmelerin açılması, görünür alanlar, maskeli kullanıcı listesi ve sekmelerin
Home/End/sol/sağ ok davranışı yerel tarayıcıda kontrol edildi. AI kayıtları ekranında
boş sonuç durumu, işleme listesinde tamamlanan işler görüldü. Arama sonuçları, bütün
filtre birleşimleri, dolu AI kayıtlarının tamamı ve çok sayfalı listelerde gezinme bu
turda sınanmadı; yukarıdaki kullanım açıklamaları mevcut kaynak koduyla da karşılaştırıldı.
Ekrandaki sayılar bu özel deneme ortamına aittir; hizmet performansı ölçümü değildir.

Genel girişte demo hesapları gösterildi. Parola yenileme ve yeni parola ekranlarında
kimlik hizmetinin yapılandırılmadığı açıklaması gözlendi; bu beklenen kapalı durumdur.
**Koşulmadı:** gerçek üniversite hesabıyla giriş, e-posta teslimi, kurtarma bağlantısıyla
oturum açma ve parola değiştirme. Kişisel veri açıklamasının görüntülenmesi, kurumsal
KVKK veya canlıya çıkış onayı değildir.

## 4. Sorun bildirme ve kişisel veri sınırı

Destek için etkilenen ekranı, görünen bileşen durumunu, yaklaşık zamanı ve varsa
**Destek kodu**nu paylaşın. Sunucu bu kodu ilgili istek için oluşturur; yeniden denemede
değişebilir. Kodu yalnız yetkili destek ekibine iletin. Soru, yanıt, öğrenci notu, parola
veya giriş bilgisi göndermeyin. Gerekli olmayan kullanıcı ve ders ayrıntılarını ekran
görüntüsünden çıkarın.

Maskeli e-posta ve teknik sayılar bu alanı bütünüyle anonim yapmaz. Kullanıcı adları,
ders bağlamı ve zaman bilgileri kişisel kayıtlarla ilişkilendirilebilir. Bu alan,
öğrencinin kişisel veri indirme veya silme talebini onun adına gerçekleştirme yetkisi vermez.

Kendi hesabınız için **Profil → Verilerimi indir veya sil** yolunu kullanın. İşlemlerin
kapsamı [Öğrenci Kılavuzu](student-guide.md#7-profil-ve-kişisel-veriler) içinde açıklanır.
İşiniz bitince **Çıkış** yapın.

## İlgili belgeler

- [Eğitmen Kılavuzu](instructor-guide.md)
- [Kişisel Veriler ve Gizlilik](kvkk.md)
- [İşletim ve kurulum](deployment.md) — uygulama dışındaki işletim işlemleri için
