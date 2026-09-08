# Kişisel Veriler ve Gizlilik

**DOU-Synapse — Ders ve Sınav Asistanı**
Son güncelleme: 8 Eylül 2026

Bu sayfa uygulamanın mevcut veri işleme davranışını açıklar. Kurumsal aydınlatma metni için veri sorumlusunun resmi unvanı ve iletişim adresi, işleme amaçları ve hukuki sebepler, hizmet sağlayıcılar, aktarım düzenlemeleri ve saklama süreleri henüz kesinleştirilmemiştir. Bu alanlar sorumlu kurum tarafından tamamlanmadan metin, tamamlanmış bir KVKK/GDPR uygunluk beyanı olarak kullanılmamalıdır.

## Hangi bilgiler kullanılır?

| Bilgi | Kullanım amacı |
|---|---|
| Ad, e-posta ve hesap kimliği | Giriş, profil ve ders üyeliklerini eşleştirmek |
| Ders üyeliği ve ders içindeki rol | Öğrenci ve eğitmen erişimini belirlemek |
| Sohbet soruları, cevapları ve denemeler | Ders materyaline dayalı yardım ve kişisel geçmiş sağlamak |
| Yanıt puanlaması, yorum ve paylaşım tercihi | Asistan yanıtlarının kalitesini değerlendirmek |
| Sınav/alıştırma cevapları, puanlar, geri bildirim ve ilerleme | Çalışma deneyimini sürdürmek ve konu eksiklerini göstermek |
| Eğitmenin yüklediği dosyalar ve metin parçaları | Dersin bilgi kaynağını oluşturmak |
| İşlem, kota, güvenlik ve yönetim kayıtları | Yetkisiz kullanımı araştırmak ve hizmeti işletmek |

Özel nitelikli veri toplamak uygulamanın amacı değildir. Ancak sohbet, cevap, yorum veya yüklenen dosyaya yazılan bilgiler bu kayıtlara girebilir; böyle verilerin hiç işlenmediği garanti edilemez. Ders için gerekli olmayan kişisel bilgileri bu alanlara yazmayın.

## Bilgileri kim görebilir?

Kişisel sohbet geçmişi oturum sahibine açıktır. **Bir yanıtı eğitmen incelemesine paylaşmayı seçerseniz**, ilgili soru/cevap alıntısı, yorum ve kimliğiniz ders eğitmeninin kalite ekranında görünür. Bu tercih, bütün sohbet geçmişini açmaz.

Ders üyeliği, eğitmen yetkisi ve yönetici yetkisi ayrı kontrol edilir. Eğitmenin ders yönetimi ve analitik erişimi, öğrencinin kişisel sohbet erişimiyle aynı değildir. Ders materyalleri o dersin yetkili üyelerine sunulur. Yetkili sistem işletmecilerinin altyapı erişimi ayrıca kurumun erişim politikasıyla yönetilmelidir.

İşlem ölçümleri, sohbet metnini kaydetmek için kullanılmaz. Bununla birlikte kimlikler ve işlem zamanları kişisel veri olabilir. Uygulama, kimlik belirteci ve bilinen hassas kalıpları günlüklerden maskelemeye çalışır; bu, bütün serbest metnin otomatik olarak anonimleştiği anlamına gelmez. Altyapı ve hizmet sağlayıcı günlüklerinin kapsamı ayrıca belirlenmelidir.

## Yapay zekâ ve diğer hizmet sağlayıcıları

Gerçek dil modeli kullanıldığında seçili sağlayıcıya işin gerektirdiği soru veya deneme metni, ders kaynağı parçaları ve kaynak bilgileri gönderilir. Soru üretimi ve açık uçlu/kod sorularının metinsel değerlendirilmesi de model çağrısı yapabilir; değerlendirme isteğinde cevap, rubrik ve ilgili kaynak yer alabilir. Çoktan seçmeli ve kısa yanıtların yerel karşılaştırma yolları ayrıca bulunur. Öğrenci kodu sunucuda çalıştırılmaz.

Ad ve e-posta ayrı kimlik alanı olarak modele verilmez; ancak sizin yazdığınız metinde veya eğitmenin yüklediği belgede bulunabilir. Bu nedenle modele giden içeriğin kişisel veri içermediği varsayılmaz. Seçili sağlayıcı ve yedek sağlayıcı düzeni, saklama/eğitim politikası, işleme bölgesi ve sözleşmeler kurumsal kullanım öncesinde açıklanmalıdır.

Yerel demo, sahte dil modeli ve yerel vektör hesaplamasıyla çalışabilir. Bu seçenek, kimlik sağlayıcısı, dosya deposu, model dosyası indirme veya dağıtım altyapısı dahil uygulamanın her durumda çevrimdışı olduğu anlamına gelmez. Canlı ortamın gerçek veri akışı ayrıca doğrulanmalıdır.

## Hesabınızdan yapabileceğiniz işlemler

Hesap ve gizlilik ekranından uygulamada sunulan kişisel kayıtlarınızı JSON olarak indirebilir ve kendi sohbet geçmişinizi silebilirsiniz. İndirme; profil, ders üyelikleri, kendi sohbet ve geri bildirimleriniz, sınav oturumları/cevapları ve öğrenme ilerlemesini kapsar. Bütün altyapı kayıtları, yüklenen dosyalar, sağlayıcı kopyaları ve yedeklerin tam dökümü değildir. Etkin öğrenci sınavı sırasında cevap içeren indirme geçici olarak bekletilir; sınav sona erdiğinde tekrar kullanılabilir.

**Profil bilgilerini kaldırma** işlemi uygulama profilindeki ad ve e-postayı kaldırır, sohbetleri siler ve ders üyeliklerini kapatır. Profil kaydı ile kullanıcı kimliği korunur. Sınav cevapları, geri bildirim, öğrenme ilerlemesi ve ders materyalleriyle bağlantılar kalır. Bu işlem bütün verilerin silinmesi veya geri döndürülemez anonimleştirilmesi değildir. Üniversite/kimlik sağlayıcısı hesabınız ayrıca kapatılmalıdır.

Sohbet silindikten sonra, önceden başlamış bir yanıtın geçmişi yeniden oluşturmasını engelleyen hesap ve ders kapsamlı teknik sayaç tutulur. Bu sayaç soru veya cevap içermez; yine de hesap kimliğiyle bağlantılıdır. JSON indirmesinin dışında kalan bu kayıt dosyanın kapsam açıklamasında belirtilir.

Daha önce indirdiğiniz dosyalar, ekran görüntüleri veya başka cihazdaki kopyalar bu işlemlerle geri alınamaz. Paylaşılan cihazda işiniz bitince çıkış yapın ve indirdiğiniz kişisel dosyaları cihazda bırakmayın.

## Saklama ve silme sınırları

Bütün kişisel veri kategorileri için onaylanmış süre ve otomatik imha programı henüz tanımlanmamıştır. Profil alanı kaldırma, sohbet silme, ders üyeliği kapatma, materyal silme ve kimlik hesabı kapatma farklı işlemlerdir. Bir veritabanı satırının silinmesi, dosya deposundaki veya sağlayıcı/yedek sistemindeki bütün kopyaların silindiğini tek başına kanıtlamaz.

Saklanacak akademik kayıtların kapsamı, amacı, hukuki dayanağı ve süresi sorumlu kurumca belirlenmelidir. Süresi dolan kayıtlar için imha ve yedekten geri dönüş sonrası tekrar silme süreci ayrıca uygulanmalıdır. Kodun bir kaydı koruması, o kaydın süresiz saklanması için kendiliğinden bir hukuki gerekçe oluşturmaz.

## Hak talepleri ve kurumsal kullanım

Veri işleme hakkında bilgi edinme, düzeltme, erişim ve koşulları oluştuğunda silme talepleri için kurumun doğrulanmış başvuru kanalı ve sorumlu birimi bu sayfaya eklenmelidir. Hesap ekranındaki işlemler, kapsamlı bir hak başvurusunun bütün aşamalarının yerine geçmez. Henüz atanmış bir alıcı adına başvuru veya yanıt süresi taahhüdü verilmez.

Asistanın çalışma puanları ve yorumları resmî sınav notu olarak kullanılmak üzere sunulmaz. İnsan incelemesi, itiraz süreci ve kurumun kullanım kuralları açıkça belirlenmelidir.

Kurumsal kullanımdan önce veri sorumlusu/işleyen rolleri, hukuki sebepler, gerekiyorsa geçerli aktarım mekanizması, saklama/imha süreleri, ihlal müdahalesi ve gerçek ortam erişim/yedek testleri tamamlanmalıdır. KVKK ve GDPR kapsamı, kullanıcılar ve kullanım ortamı temelinde ayrıca değerlendirilmelidir.
