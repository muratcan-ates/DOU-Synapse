# Özellik Şartnamesi: Production Sertleştirme

**Feature Branch**: `002-production-hardening`

**Created**: 2026-08-09

**Status**: Draft

**Input**: 9 Ağustos 2026 tarihli dış inceleme (GPT) + aynı gün 13 ajanla yapılan kod doğrulaması + incelemeyi yazanın doğrulamaya verdiği karşı okuma.

Üç kaynağın uzlaştığı yer: incelemenin dokuz maddesi kodla doğrulandı; doğrulama incelemenin görmediği dört kusur buldu (sınav oturumu bypass'ı, event loop bloklanması, issuer ortam değişkeni uyuşmazlığı, sınırsız soru üretimi); ve **asıl bayat olan kod değil belgelerdir** — mimari, güvenlik ve test raporu belgeleri kodun gerisinde kalmış, inceleme de kısmen onları okumuş. Doğrulamanın ilk turunda incelemeye atfedilen iki iddia (onay akışının eksikliği, sahte sağlayıcının soru üretememesi) **yanlış atıftı**; ikisi de projenin kendi devir belgesinden ve README'sinden geliyor. Düzeltme spec'in son tablosundadır.

---

## Bağlam: bu şartname neden var

001 numaralı özellik (CourseGPT MVP) yerelde çalışan bir sistem üretti: dört ekran gerçek uçlarda, backend ve frontend test paketleri yeşil. Bu şartname yeni bir ürün tanımlamıyor; **var olan ürünü gerçek kullanıcıların önüne çıkarılabilir hale getiriyor** ve hocanın toplantıda vurguladığı "önce sınavın çatısını kur" isteğini karşılıyor.

Şartnamenin çıkış noktası olan üç gözlem:

1. **Ürünün en sıkı kuralı, en zayıf yerinden atlanabiliyor.** Sınav modunda ipucu kapalı ve bu üç uçta zorlanıyor. Ama sınav *oturumu* açıkken genel asistan hâlâ tam kaynaklı cevap veriyor. Kural mod eksenine yazılmış, durum eksenine yazılmamış.
2. **Öğretmen AI'ın davranışını belirleyemiyor.** Bugün modu öğrenci seçiyor, eşik global, kaynak seti tüm ders. Hocanın istediği "öğretmenin çizdiği sınır" ürüne girmemiş.
3. **Belgeler kodun gerisinde ve jüri belgeleri okuyacak.** Mimari belgesindeki 12 satırlık durum tablosunun 5 satırı kodla çelişiyor; aynı komut üç belgede üç farklı test sayısı veriyor; güvenlik belgesi var olmayan bir CORS gevşekliğini rapor ediyor ve var olan KVKK metnini yok sayıyor. Bu, yapılmış işi görünmez kılıyor: dış inceleme kısmen bu tablodan okudu ve README okuyucuyu satır 235'te açıkça o bayat listeye yönlendiriyor. Aynı belgeler teslim paketinde.

4. **Bilinen kusurlar yeni özelliklerin altında kalmamalı.** Event loop bloklanması, sınırsız soru üretimi ve hiçbir şeye bağlanmayan bir kimlik ayarı, sekiz varlıklı bir blueprint'ten önce kapanır. İlk taslakta bunlar P3'e düşmüştü; dış incelemeyi yazanın itirazı üzerine P1'e alındı (User Story 2).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sınav bütünlüğü tek eksende değil, her yolda korunur (Priority: P1)

Öğrenci süreli bir sınav oturumu başlattığında, o oturum sürerken sistemin hiçbir yüzeyi ona akademik yardım vermez. İkinci sekmede asistanı açmak, Sokratik moda geçmek veya doğrudan API'ye istek atmak sonucu değiştirmez. Sınav bitince veya süre dolunca yardım kendiliğinden geri açılır.

**Why this priority**: Hocanın açık şartı bu ve bugün ihlal ediliyor. Öğrenci sınavı başlatıp yeni sekmede asistana sınav sorusunu yazarak tam, kaynaklı cevabı alabiliyor. Bu tek başına ürünün sınav vaadini geçersiz kılar; jüri denerse ilk denemede bulur.

**Independent Test**: Bir öğrenci hesabıyla sınav oturumu başlatılır, ardından aynı token'la asistan ucuna sınav sorusu gönderilir. Sunucu reddetmelidir. Oturum bitirilip aynı istek tekrarlandığında cevap gelmelidir.

**Acceptance Scenarios**:

1. **Given** öğrencinin `exam` modunda bitmemiş ve süresi dolmamış bir sınav oturumu var, **When** asistan ucuna `qa` modunda soru gönderir, **Then** sistem isteği reddeder ve nedenini anlaşılır Türkçe söyler.
2. **Given** aynı durum, **When** öğrenci `socratic` modunda soru gönderir, **Then** sistem yine reddeder — Sokratik merdivenin kaynaklı açıklama kademesi bir yardım yüzeyidir.
3. **Given** sınav oturumunun süresi dolmuş ama oturum kapatılmamış, **When** öğrenci asistana soru gönderir, **Then** sistem cevap verir; süresi dolmuş oturum yardımı kilitlemez.
4. **Given** öğrenci `practice` modunda bir oturum yürütüyor, **When** asistana soru gönderir, **Then** sistem cevap verir; prova modu yardımı kapatmaz.
5. **Given** öğrencinin aktif sınavı var, **When** arayüzde ders gezinme çubuğuna bakar, **Then** "Asistan" sekmesi kilitli görünür ve nedeni yazar — sunucu zaten reddediyor, arayüz kullanıcıyı duvara koşturmaz.
6. **Given** öğretmen rolündeki bir kullanıcı, **When** aynı derste asistanı kullanır, **Then** kilit uygulanmaz; kilit sınav veren öğrenciye özeldir.

---

### User Story 2 - Bilinen production kusurları yeni özelliklerden önce kapanır (Priority: P1)

Bugün kodda duran ve dış incelemenin gördüğü ya da doğrulamanın bulduğu üç kusur — bir kullanıcının ağır işleminin herkesi bekletmesi, en pahalı ucun sınırsız çağrılabilmesi, ve kurulum belgesindeki bir ayar adının hiçbir şeye bağlanmaması — yeni özellik yazılmadan önce kapanır.

**Why this priority**: Bu üçü de var olan bir vaadin sessizce tutulmadığı yerler. Sistem çökmüyor, hata vermiyor, çalışıyor gibi görünüyor — 001'in devir belgesinin "sessiz kusur sınıfı" dediği tam olarak bu. Sekiz varlıklı bir blueprint'i, bir öğretmen materyal yüklerken tüm API'nin donduğu bir sistemin üstüne inşa etmek yanlış sıradır.

**Independent Test**: Bir belge yüklenirken ikinci bir kullanıcı soru sorar ve makul sürede cevap alır. Soru üretimi arka arkaya çağrılır ve sınır devreye girer. Kurulum belgesindeki ayar adı birebir uygulanır ve ayar gerçekten etkinleşir.

**Acceptance Scenarios**:

1. **Given** bir öğretmen büyük bir belge yüklüyor, **When** aynı anda bir öğrenci soru sorar, **Then** öğrencinin isteği yükleme bitene kadar beklemez; sağlık yoklaması da yanıt vermeye devam eder.
2. **Given** sistem yeni başlatıldı, **When** ilk gerçek istek gelir, **Then** pahalı kaynak önceden ısıtılmıştır ve ilk istek soğuk başlangıç cezasını tek başına ödemez.
3. **Given** soru üretimi arka arkaya çağrılıyor, **When** sınır aşılır, **Then** sistem reddeder ve ne zaman tekrar denenebileceğini söyler.
4. **Given** aynı kullanıcı için bir soru üretimi hâlâ sürüyor, **When** ikincisini başlatmayı dener, **Then** sistem eşzamanlı ikinci üretimi kabul etmez.
5. **Given** operatör kurulum belgesindeki kimlik doğrulama ayarını birebir uygular, **When** uygulama başlar, **Then** ayar gerçekten okunmuştur; tanınmayan bir ad sessizce yok sayılmaz.
6. **Given** hız sınırlayıcının sayacı, **When** uygulama uzun süre çalışır, **Then** kullanılmayan girdiler tahliye edilir ve sayaç sınırsız büyümez.

---

### User Story 3 - Öğretmen sınavı sorulardan önce çerçeveler (Priority: P1)

Öğretmen soru üretmeden önce sınavın çatısını kurar: hangi öğrenme çıktıları ölçülecek, konu dağılımı ne, kolay/orta/zor oranı ne, hangi soru tipinden kaç tane, soru başına kaç puan, toplam süre ne, açık uçlular hangi rubrikle değerlendirilecek, sınav ne zaman açılıp ne zaman kapanacak. AI bu çerçeveye bağlı olarak taslak önerir; öğretmen düzenleyip onaylamadan hiçbir soru öğrenciye çıkmaz.

**Why this priority**: Hocanın toplantıdaki asıl isteği. Bugünkü akış "konu + tip + adet" alıyor; bu bir sınav tasarımı değil, bir soru siparişi. Çerçeve olmadan AI'ın ürettiği sorular ölçülebilir bir kazanıma bağlanamıyor, "neden yanlış" analizi kazanım düzeyinde yapılamıyor.

**Independent Test**: Öğretmen bir blueprint oluşturur, ondan sınav üretir, taslakları onaylar ve yayınlar. Öğrenci yayın penceresi açıkken sınavı görür, kapalıyken görmez. Blueprint'in dağılım kuralına uymayan bir sınav yayınlanamaz.

**Acceptance Scenarios**:

1. **Given** öğretmen bir derste, **When** öğrenme çıktıları tanımlar ve bunlara bağlı bir blueprint oluşturur, **Then** blueprint taslak olarak kaydedilir ve öğrenciye görünmez.
2. **Given** dağılımı "5 çoktan seçmeli / 2 açık uçlu, %40 kolay %40 orta %20 zor" olan bir blueprint, **When** öğretmen AI'dan taslak ister, **Then** üretilen taslaklar bu dağılıma göre istenir ve her taslak bir öğrenme çıktısına bağlı gelir.
3. **Given** blueprint 7 soru istiyor ama havuzda yalnız 5 onaylı soru var, **When** öğretmen sınavı yayınlamayı dener, **Then** sistem yayınlamaz ve hangi hücrenin eksik olduğunu söyler.
4. **Given** yayınlanmış bir sınav, **When** öğretmen bir sorusunu değiştirir, **Then** yeni bir sınav sürümü oluşur; devam eden oturumlar başladıkları sürümü görmeye devam eder.
5. **Given** yayın penceresi henüz açılmamış bir sınav, **When** öğrenci sınav listesine bakar, **Then** sınavı görmez; pencere açıldığında görür, kapandığında yeni oturum başlatamaz.
6. **Given** açık uçlu bir soru ve ona bağlı bir rubrik, **When** öğrenci cevaplar, **Then** değerlendirme rubriğin ölçütlerine göre yapılır ve öğrenciye hangi ölçütten kaç puan aldığı gösterilir.
7. **Given** bir soruya bağlı kaynak belge yeniden yüklenmiş, **When** öğretmen soru havuzuna bakar, **Then** o soru "kaynak sürümü değişti" uyarısıyla işaretlenir.

---

### User Story 4 - Öğretmen dersin AI davranışını belirler (Priority: P1)

Öğretmen ders bazında asistanın sınırlarını çizer: hangi mod açık (normal sohbet / Sokratik / kapalı), kaç ipucu verilebilir, hangi belgeler kaynak olarak kullanılır, reddetme eşiği ne, atıf zorunlu mu, ders için günlük LLM bütçesi ne. Bu ayarlar sunucuda uygulanır — arayüzde gizlemek yeterli sayılmaz.

**Why this priority**: Hocanın "CourseGPT / Sınıf Asistanı / Sınav Mentoru" ayrımı ancak öğretmenin davranışı seçebilmesiyle anlam kazanır. Bugün modu öğrenci seçiyor: Sokratik modu kapatmak isteyen öğretmenin elinde hiçbir düğme yok.

**Independent Test**: Öğretmen dersin modunu yalnız Sokratik yapar. Öğrenci `qa` modunda istek gönderir; sunucu reddeder. Öğretmen ipucu sayısını 2'ye çeker; öğrenci üçüncü ipucunu alamaz.

**Acceptance Scenarios**:

1. **Given** öğretmen dersin politikasını "yalnız Sokratik" yapmış, **When** öğrenci normal sohbet modunda soru gönderir, **Then** sunucu reddeder — arayüzde seçenek gizlense de API kararı sunucu verir.
2. **Given** politikada ipucu üst sınırı 2, **When** öğrenci üçüncü ipucunu ister, **Then** sistem vermez ve sınıra ulaşıldığını söyler.
3. **Given** öğretmen bir belgeyi kaynak setinden çıkarmış, **When** öğrenci o belgedeki bir konuyu sorar, **Then** cevap o belgeden atıf içermez.
4. **Given** dersin günlük LLM bütçesi dolmuş, **When** öğrenci soru sorar, **Then** sistem bunu bir arıza gibi değil, anlaşılır bir sınır bildirimi olarak gösterir; öğretmen panelinde bütçe durumu görünür.
5. **Given** öğretmen reddetme eşiğini yükseltmiş, **When** sınırda bir soru gelir, **Then** sistem dersin eşiğini uygular, global varsayılanı değil.
6. **Given** yeni açılan bir ders, **When** öğretmen hiçbir ayara dokunmaz, **Then** ders bugünkü davranışla çalışır — varsayılanlar mevcut davranışı değiştirmez.

---

### User Story 5 - Arayüz yavaş ağda ve soğuk sunucuda dürüst davranır (Priority: P2)

Kullanıcı isteği takıldığında süresiz beklemez: istek bir bütçeyle sınırlanır, geçici arızalarda sistem kendi kendine yeniden dener, ilk isteğin neden uzun sürdüğü ekranda yazar, ve bir hata olduğunda kullanıcıya destek için kullanılabilecek bir istek kimliği gösterilir.

**Why this priority**: Dış inceleme iki ayrı ekranda ilk açılışta "Bağlantı kurulamadı" gördü ve elle tekrar denemek zorunda kaldı. Sistem soğuk başlangıcı ölçmüş ve belgelemiş (ilk soru 11,7 sn, ilk yükleme 19,1 sn) ama bu bilgi anlatıcının ağzında, kullanıcının ekranında değil. Demo günü jüri de aynı ekranı görecek.

**Independent Test**: API kapalıyken bir sayfa açılır; ekran sonsuz "Yükleniyor…" kalmaz, sınıflandırılmış bir hata ve çalışan bir "Tekrar dene" gösterir. API yavaşlatılır; kullanıcı ilk isteğin neden uzun sürdüğünü okur.

**Acceptance Scenarios**:

1. **Given** sunucu yanıt vermiyor, **When** kullanıcı bir sayfa açar, **Then** istek belirli bir süre sonra kesilir ve ekran hata durumuna geçer — süresiz beklemez.
2. **Given** geçici bir sunucu hatası (503) veya ağ kopması, **When** kullanıcı veri okuyan bir sayfa açar, **Then** sistem kullanıcıya sormadan sınırlı sayıda ve artan aralıklarla yeniden dener.
3. **Given** kalıcı bir hata (403, 404), **When** aynı durum oluşur, **Then** sistem yeniden denemez ve "Tekrar dene" düğmesi gösterilmez.
4. **Given** veri değiştiren bir istek (soru üretimi, sohbet gönderimi), **When** istek başarısız olur, **Then** sistem otomatik yeniden denemez — çift üretim riski yeniden denemeye ağır basar.
5. **Given** ilk istek dört saniyeden uzun sürüyor, **When** kullanıcı bekliyor, **Then** ekran bunun tek seferlik model yüklemesi olduğunu açıklar.
6. **Given** bir istek hata döndü, **When** kullanıcı hata kutusuna bakar, **Then** istek kimliğini görür ve kopyalayabilir; aynı kimlik sunucu loglarında aranabilir.
7. **Given** API ölü ve sayfa periyodik yenileme yapıyor, **When** bir dakika geçer, **Then** yenileme aralığı artmıştır; sistem ölü sunucuyu sabit hızla dövmez.

---

### User Story 6 - Listeler gerçek veri hacminde kullanılabilir kalır (Priority: P2)

Ders, materyal, soru, sohbet oturumu ve sohbet geçmişi listeleri sayfa sayfa gelir. Kullanıcı listenin devamını isteyebilir; hiçbir ekran tüm satırları tek seferde çekmez.

**Why this priority**: Bugün beş listenin hiçbirinde sınır yok. Geliştirme veritabanında biriken yüzlerce test dersi bunun ilk semptomu; gerçek bir sınıfta sohbet geçmişi aynı yolu izler.

**Independent Test**: 200 kayıt tohumlanır; liste ilk sayfayı döndürür ve toplam/devam bilgisi taşır. Sayfa sayısı arttıkça yanıt süresi doğrusal büyümez.

**Acceptance Scenarios**:

1. **Given** derste 200 soru var, **When** öğretmen soru havuzunu açar, **Then** sayfa ilk N soruyu gösterir ve devamını isteyebilir.
2. **Given** kullanıcı ikinci sayfayı ister, **When** aynı anda yeni bir kayıt eklenir, **Then** kullanıcı kayıt atlamaz veya aynı kaydı iki kez görmez.
3. **Given** istemci makul olmayan bir sayfa boyu ister, **When** istek sunucuya ulaşır, **Then** sunucu kendi üst sınırını uygular.
4. **Given** uzun bir sohbet geçmişi, **When** öğrenci oturumu açar, **Then** son mesajlar gelir ve geriye doğru yüklenebilir.

---

### User Story 7 - Gerçek kimlikle giriş (Priority: P2)

Kullanıcı üniversite hesabıyla giriş yapar; oturumu gerçek bir kimlik sağlayıcısı üretir ve süresi dolduğunda arayüz bunu fark edip yeniden girişe yönlendirir. Geliştirme kimliği yalnız yerel ortamda çalışır ve üretim yapılandırmasında uygulama açılmayı reddeder.

**Why this priority**: Ürün bugün tarayıcı hafızasına yazılmış bir demo kullanıcısıyla çalışıyor. Backend köprüsü ve JWT doğrulaması hazır; eksik olan arayüz ayağı ve o ayak gerçek anahtar olmadan da yazılabilir.

**Independent Test**: Gerçek bir kimlik sağlayıcısı yapılandırıldığında giriş çalışır; yapılandırılmadığında yerel geliştirme kimliği çalışmaya devam eder. Üretim ortamında geliştirme kimliği açıkken uygulama başlamaz.

**Acceptance Scenarios**:

1. **Given** kimlik sağlayıcısı yapılandırılmış, **When** kullanıcı e-posta ve parolayla giriş yapar, **Then** gerçek bir oturum açılır ve API istekleri o oturumun kimliğiyle gider.
2. **Given** oturum süresi dolmuş, **When** kullanıcı bir işlem yapar, **Then** arayüz bunu tanır, oturumu tazelemeyi dener, olmazsa girişe yönlendirir — ham yetki hatası göstermez.
3. **Given** üretim ortamı ve geliştirme kimliği açık, **When** uygulama başlatılır, **Then** başlamaz ve nedenini söyler.
4. **Given** kimlik sağlayıcısının kim tarafından üretildiğini doğrulayan ayar, **When** operatör kurulum belgesindeki adı birebir uygular, **Then** ayar gerçekten etkinleşir — sessizce yok sayılmaz.

---

### User Story 8 - Belgeler ürünün gerçeğini anlatır (Priority: P1)

Teslim paketindeki her belge, teslim anındaki kodu anlatır. Bir belgede "uygulanmadı" yazan her madde gerçekten uygulanmamıştır; her sayı gerçekten ölçülmüştür ve belgeler arasında çelişmez.

**Why this priority**: Dış inceleme, kodda çözülmüş üç şeyi eksik raporladı — mimari belgesindeki 12 satırlık durum tablosunun 5 satırı kodla çelişiyor ve inceleme onu okudu. Jüri de aynı tabloyu okuyacak. Bu, kod yazmadan kapatılabilen en yüksek getirili açık.

**Independent Test**: Belgelerdeki her somut iddia (sayı, "var/yok" ifadesi, satır numaralı referans) kodla karşılaştırılır; çelişki sayısı sıfır olmalıdır. Aynı metrik iki belgede iki farklı değer taşımamalıdır.

**Acceptance Scenarios**:

1. **Given** mimari belgesindeki durum tablosu, **When** her satır kodla karşılaştırılır, **Then** çelişen satır kalmaz.
2. **Given** aynı metrik birden çok belgede geçiyor (test sayısı, doğru ret oranı, tablo sayısı), **When** belgeler karşılaştırılır, **Then** hepsi aynı değeri söyler.
3. **Given** güvenlik belgesindeki satır numaralı kod referansları, **When** o satırlara bakılır, **Then** referans hâlâ iddia edilen kodu gösterir.
4. **Given** ölçülmemiş bir metrik, **When** rapora yazılır, **Then** sayı değil "KOŞULMADI" yazar.

---

### User Story 9 - Test verisi üretim verisinden ayrılır (Priority: P3)

Otomatik testler kendi oluşturdukları veriyi arkalarında bırakmaz. Test, geliştirme ve üretim verileri birbirine karışmaz. Birikmiş test verisi tek komutla temizlenebilir.

**Why this priority**: Dış inceleme ders listelerinde yüzlerce test dersi gördü ve bunu bir veri yönetişimi kusuru olarak raporladı. Demo günü aynı liste jüriye açılacak.

**Independent Test**: Uçtan uca paket koşturulur; koşu bittiğinde oluşturulan kayıt sayısı sıfırdır. Temizlik komutu birikmiş kayıtları siler ve gerçek veriye dokunmaz.

**Acceptance Scenarios**:

1. **Given** uçtan uca testler koştu, **When** koşu biter, **Then** oluşturdukları dersler, belgeler ve oturumlar silinmiştir.
2. **Given** bir test ortada başarısız oldu, **When** paket sonlanır, **Then** temizlik yine çalışır.
3. **Given** birikmiş test verisi, **When** temizlik komutu çalıştırılır, **Then** yalnız test deseni taşıyan kayıtlar silinir ve kaç kayıt silindiği raporlanır.

---

### User Story 10 - Kullanıcı kendi verisi üzerinde hak sahibidir (Priority: P3)

Kullanıcı sohbet geçmişini silebilir, verisini dışa aktarabilir ve hesabının silinmesini isteyebilir. Aydınlatma metninde söylenen her şeyin ürün tarafında bir karşılığı vardır.

**Why this priority**: Aydınlatma metni bugün kodda karşılığı olmayan haklar vaat ediyor: "hesap silindiğinde kayıtları da silinir" diyor ama hesap silme ucu yok; öğretmenler için bu silme veri bütünlüğü kısıtıyla zaten engelli. Belgede yazan hak, üründe yoksa belge yanlıştır.

**Independent Test**: Kullanıcı dışa aktarma ister ve verisini alır; sohbet geçmişini siler ve geçmiş boşalır; hesap silme talebi işlenir ve kişisel veriler kalmaz.

**Acceptance Scenarios**:

1. **Given** kullanıcı sohbet geçmişini siler, **When** oturum listesine bakar, **Then** liste boştur ve silinen mesajlar hiçbir yüzeyden geri gelmez.
2. **Given** kullanıcı verisini dışa aktarır, **When** dosyayı açar, **Then** kendi profil bilgisi, sohbetleri ve sınav sonuçları okunabilir biçimdedir; başka kullanıcının verisi yoktur.
3. **Given** ders sahibi bir öğretmen hesabının silinmesini ister, **When** talep işlenir, **Then** sistem ne sessizce başarısız olur ne de dersi ve öğrenci verisini düşürür; ne yaptığını açıkça söyler.
4. **Given** aydınlatma metnindeki her hak, **When** üründe karşılığı aranır, **Then** ya bir akış vardır ya da metin o hakkı vaat etmez.

---

### User Story 11 - Arıza görünür olur ve tarayıcı korunur (Priority: P3)

Başarısız bir belge işleme kendini yeniden dener; ısrarla başarısız olursa sessizce kaybolmaz, öğretmen panelinde görünür ve elle yeniden çalıştırılabilir. Tarayıcıya gönderilen sayfa temel güvenlik başlıklarını taşır.

**Why this priority**: Bu hikâyenin performans ayağı (event loop, ısıtma, hız sınırı) User Story 2'ye taşındı — onlar bilinen kusur, bunlar yeni yetenek. Burada kalan iki iş gerçek ama demoyu ve teslimi tek başına düşürmez.

**Independent Test**: Bir işleme işi bilerek bozulur; sistem yeniden dener, sonra kusuru öğretmene görünür kılar. Uygulama yüklenir; yanıt başlıkları kontrol edilir.

**Acceptance Scenarios**:

1. **Given** bir belge işleme işi geçici bir hatayla düştü, **When** sistem yeniden dener, **Then** artan aralıklarla dener ve ısrarla başarısız olursa işi kusurlu olarak işaretler.
2. **Given** kusurlu bir işleme işi, **When** öğretmen materyal ekranına bakar, **Then** durumu görür ve yeniden çalıştırabilir.
3. **Given** tarayıcı uygulamayı yükler, **When** yanıt başlıklarına bakılır, **Then** içerik güvenliği, içerik tipi ve yönlendirici politikası başlıkları vardır.

---

### Edge Cases

- Sınav oturumu açıkken tarayıcı kapanır ve süre dolar: yardım kilidi süre dolduğunda kalkar; kilit "bitmemiş oturum" değil "yürüyen oturum" ile bağlıdır.
- Öğretmen kendi dersinde sınav oturumu açarsa: kilit uygulanmaz, çünkü kilit değerlendirilen kişiyi hedefler.
- Blueprint dağılımı toplamı soru sayısıyla tutmuyorsa (yüzdeler 100 etmiyor, tip sayıları toplamı adet ile eşleşmiyor): kaydedilmez, hangi hücrenin tutmadığı söylenir.
- Yayınlanmış sınavda öğrencinin oturumu sürerken öğretmen soruyu değiştirirse: oturum başladığı sürümü görmeye devam eder.
- Ders politikası tüm modları kapatırsa: asistan sekmesi ders için tamamen kapanır ve bu bir arıza gibi değil bir tercih gibi görünür.
- Politika kaynak setini boşaltırsa: her soru kaynak yetersizliğiyle döner; öğretmen paneli bu durumu uyarı olarak gösterir.
- Kimlik sağlayıcısı erişilemezse: giriş ekranı bunu geçici arıza olarak gösterir, kullanıcıyı sonsuz yönlendirme döngüsüne sokmaz.
- Dışa aktarma isteği çok büyük veri üretirse: iş asenkron yürür, kullanıcı hazır olduğunda haberdar edilir.
- Sayfalama sırasında kayıt silinirse: kullanıcı hata almaz, liste tutarlı kalır.
- Temizlik komutu gerçek bir dersi test dersi sanarsa: silmeden önce ne sileceğini gösterir ve onay ister.

---

## Requirements *(mandatory)*

### Functional Requirements

**Sınav bütünlüğü**

- **FR-101**: Sistem, bir öğrencinin `exam` modunda yürüyen (bitmemiş ve süresi dolmamış) sınav oturumu varken, o öğrenciden gelen akademik yardım isteklerini sunucu tarafında REDDETMELİDİR.
- **FR-102**: FR-101 kilidi sohbetin tüm modlarını (normal ve Sokratik) kapsamalıdır; tek bir mod açık bırakılmamalıdır.
- **FR-103**: Kilit yalnız değerlendirilen öğrenciye uygulanmalı, aynı dersteki öğretmene uygulanmamalıdır.
- **FR-104**: Süresi dolmuş ama kapanmamış oturum kilidi sürdürmemelidir.
- **FR-105**: Arayüz, kilit yürürlükteyken asistan yüzeyini kilitli göstermeli ve nedenini yazmalıdır; arayüzdeki gizleme sunucu kararının yerine geçmez.
- **FR-106**: Bu davranışın testi, kilit kodu bilerek kaldırıldığında KIRMIZI yanmalıdır.

**Bilinen production kusurları** *(User Story 2 — hepsi bugün kodda duran somut kusurlar)*

- **FR-220**: Ağır hesaplama işleri (belge ayrıştırma, embedding üretimi) istek işleyen döngüyü bloke ETMEMELİDİR. Bu hem yükleme hattında hem sorgu hattında geçerlidir; sorgu hattı ayrı bir worker'a taşınmadığı için "arka planda koşuyor" savunması onu kurtarmaz.
- **FR-221**: Sistem başlatılırken pahalı kaynaklar (embedding modeli) önceden ısıtılmalıdır; ilk gerçek istek soğuk başlangıç cezasını tek başına ödememelidir. Isıtma test ortamında atlanabilmelidir.
- **FR-222**: LLM maliyeti yüksek uçlar hız sınırına tabi olmalıdır. Sınır, sohbet sınırının kopyası DEĞİL, üretim maliyetine göre ayrı ayarlanmış bir kota olmalı ve aynı kullanıcının eşzamanlı ikinci üretimini engellemelidir.
- **FR-223**: Hız sınırlayıcı sayacı kullanılmayan girdileri tahliye etmeli, süreç ömrü boyunca sınırsız büyümemelidir.
- **FR-224**: Kurulum belgesinde adı geçen her ortam değişkeni, kodun gerçekten okuduğu ada karşılık gelmelidir. Özel olarak: kimlik sağlayıcı **issuer** ayarının belgedeki adı ile kodun okuduğu ad bugün uyuşmuyor ve tanınmayan ad sessizce yok sayılıyor; bu, belgeyi birebir uygulayan operatörde issuer doğrulamasını kapalı bırakıyor (imza doğrulaması etkilenmiyor, kaybedilen katman issuer sabitlemesi). Uyuşmazlık giderilmeli ve bir regresyon testiyle sabitlenmelidir. FR-173'ün somut örneğidir.

**Sınav blueprint'i**

- **FR-110**: Öğretmen ders bazında öğrenme çıktıları tanımlayabilmelidir.
- **FR-111**: Öğretmen bir sınav blueprint'i oluşturabilmelidir; blueprint kapsanan öğrenme çıktılarını, konu dağılımını, zorluk dağılımını, soru tipi dağılımını, soru başına puanı, toplam süreyi, yeniden deneme politikasını ve yayın penceresini taşımalıdır.
- **FR-112**: Sistem, blueprint'in iç tutarlılığını kaydetmeden önce doğrulamalıdır; tutarsız dağılım kaydedilmemeli ve hangi hücrenin tutmadığı söylenmelidir.
- **FR-113**: AI soru üretimi blueprint'e bağlı çalışmalı; üretilen her taslak bir öğrenme çıktısına ve bir zorluk seviyesine bağlı gelmelidir.
- **FR-114**: Sistem, blueprint'in istediği dağılımı karşılayamayan bir sınavı yayınlamamalı ve eksik hücreleri raporlamalıdır.
- **FR-115**: Sınavlar sürümlenmelidir; yayınlanmış bir sınav değiştirildiğinde yeni sürüm oluşmalı ve yürüyen oturumlar başladıkları sürümü görmeye devam etmelidir.
- **FR-116**: Öğrenci, yayın penceresi dışında sınavı görmemeli ve oturum başlatamamalıdır.
- **FR-117**: Açık uçlu sorular bir rubriğe bağlanabilmeli; değerlendirme rubriğin ölçütleri üzerinden yapılmalı ve öğrenciye ölçüt kırılımı gösterilmelidir.
- **FR-118**: Bir sorunun dayandığı kaynak belge yeni bir sürümle değiştiğinde, soru "kaynak sürümü değişti" olarak işaretlenmelidir.
- **FR-119**: Öğretmen onayı olmadan hiçbir soru öğrenciye ulaşmamalıdır. *(Bu kural bugün uygulanıyor; blueprint akışı onu zayıflatmamalıdır.)*

**Ders bazlı AI politikası**

- **FR-130**: Öğretmen ders bazında hangi asistan modlarının açık olduğunu belirleyebilmelidir.
- **FR-131**: Öğretmen ders bazında ipucu üst sınırını belirleyebilmelidir.
- **FR-132**: Öğretmen ders bazında hangi belgelerin kaynak olarak kullanılacağını seçebilmelidir.
- **FR-133**: Öğretmen ders bazında reddetme eşiğini ayarlayabilmelidir; ayarlanmadığında global varsayılan geçerlidir.
- **FR-134**: Öğretmen ders bazında günlük LLM bütçesi belirleyebilmeli; bütçe dolduğunda sistem bunu arıza değil sınır olarak bildirmelidir.
- **FR-135**: Politikanın tamamı sunucu tarafında uygulanmalıdır; arayüzdeki gizleme tek başına yeterli sayılmaz.
- **FR-136**: Politikası hiç ayarlanmamış bir ders, bugünkü davranışla çalışmalıdır.
- **FR-137**: Politika değişiklikleri kim tarafından ne zaman yapıldığıyla birlikte kaydedilmelidir.

**Güvenilirlik ve hata deneyimi**

- **FR-150**: Her ağ isteği bir süre bütçesiyle sınırlanmalıdır; bütçe istek türüne göre farklı olabilir.
- **FR-151**: Sistem, geçici hatalarda (ağ kopması, 408, 429, 5xx) veri okuyan istekleri artan aralıklarla sınırlı sayıda yeniden denemelidir.
- **FR-152**: Sistem, veri değiştiren istekleri otomatik yeniden DENEMEMELİDİR.
- **FR-153**: Sistem geçici ve kalıcı hatayı ayırt etmeli; "Tekrar dene" yalnız geçici hatalarda gösterilmelidir.
- **FR-154**: Dört saniyeyi aşan ilk yüklemelerde sistem bekleyişin nedenini açıklamalıdır.
- **FR-155**: Her hata yanıtı bir istek kimliği taşımalı ve bu kimlik kullanıcıya gösterilmelidir; aynı kimlik sunucu loglarında aranabilir olmalıdır.
- **FR-156**: Periyodik yenileme yapan ekranlar, sunucu yanıt vermediğinde aralığı artırmalıdır.

**Ölçek**

- **FR-160**: Ders, materyal, soru, sohbet oturumu ve sohbet mesajı listeleri sayfalanmalıdır.
- **FR-161**: Sunucu, istemcinin istediği sayfa boyuna bakmaksızın kendi üst sınırını uygulamalıdır.
- **FR-162**: Sayfalama, eşzamanlı ekleme sırasında kayıt atlamamalı veya tekrarlamamalıdır.
- **FR-163**: Sayfalanan her sorgu belirlenimci bir sıralama taşımalıdır.

**Kimlik**

- **FR-170**: Arayüz gerçek kimlik sağlayıcısıyla oturum açabilmelidir.
- **FR-171**: Arayüz oturum süresi dolduğunda bunu tanımalı, tazelemeyi denemeli, başarısız olursa girişe yönlendirmelidir.
- **FR-172**: Geliştirme kimliği üretim ortamında etkinleştirilemez olmalıdır. *(Bugün uygulanıyor; korunmalıdır.)*
- **FR-173**: Kurulum belgesindeki her ortam değişkeni adı, kodun gerçekten okuduğu ada karşılık gelmelidir; tanınmayan ad sessizce yok sayılmamalıdır.

**Belge doğruluğu**

- **FR-180**: Teslim paketindeki belgeler, teslim commit'indeki kodla çelişmemelidir.
- **FR-181**: Aynı metrik birden çok belgede geçiyorsa hepsi aynı değeri taşımalıdır.
- **FR-182**: Ölçülmemiş metrikler için sayı yazılmamalı, açıkça "KOŞULMADI" yazılmalıdır.
- **FR-183**: Belge-kod tutarlılığı otomatik olarak kontrol edilebilmeli ve tutarsızlık teslim öncesi görünür olmalıdır.

**Veri hijyeni**

- **FR-190**: Uçtan uca testler oluşturdukları veriyi koşu sonunda silmelidir; test ortada başarısız olsa da temizlik çalışmalıdır.
- **FR-191**: Birikmiş test verisi tek bir komutla temizlenebilmeli; komut ne sileceğini önce göstermelidir.
- **FR-192**: Test verisi, deseninden tanınabilir olmalıdır.

**Kullanıcı hakları**

- **FR-200**: Kullanıcı sohbet geçmişini silebilmelidir.
- **FR-201**: Kullanıcı kendi verisini dışa aktarabilmelidir; dışa aktarma başka kullanıcının verisini içermemelidir.
- **FR-202**: Hesap silme talebi işlenebilmeli; ders sahibi hesaplarda sistem ne sessizce başarısız olmalı ne de bağlı veriyi düşürmelidir.
- **FR-203**: Aydınlatma metni yalnız üründe karşılığı olan hakları vaat etmelidir.

**Dayanıklılık**

- **FR-213**: Belge işleme işleri geçici hatalarda artan aralıklarla yeniden denenmeli; ısrarlı başarısızlıkta kusurlu olarak işaretlenmelidir.
- **FR-214**: Öğretmen kusurlu işleme işlerini görebilmeli ve yeniden çalıştırabilmelidir.
- **FR-215**: Tarayıcıya gönderilen yanıtlar temel güvenlik başlıklarını taşımalıdır.

### Key Entities

- **Öğrenme çıktısı**: Dersin ölçülebilir kazanımı. Derse bağlıdır, kodu ve açıklaması vardır, sorular buna bağlanır.
- **Sınav blueprint'i**: Sınavın çatısı. Kapsanan çıktılar, konu/zorluk/tip dağılımları, puanlama, süre, yeniden deneme ve yayın penceresi. Sorulardan önce vardır.
- **Sınav sürümü**: Yayınlanmış bir sınavın dondurulmuş hali. Oturumlar bir sürüme bağlanır; sonraki değişiklikler yeni sürüm üretir.
- **Rubrik**: Açık uçlu değerlendirme ölçütleri ve her ölçütün ağırlığı. Soruya bağlanır, değerlendirme ondan okur.
- **Ders AI politikası**: Bir dersin asistan davranış sınırları. Derse birebir bağlıdır, yokluğunda global varsayılan geçerlidir, değişiklikleri iz bırakır.
- **İstek kimliği**: Bir isteğin uçtan uca izlenebilir tekil kimliği. Sunucu üretir, hata yanıtında taşınır, kullanıcıya gösterilir, logda aranır.
- **Sayfa imleci**: Bir listenin nerede kaldığını belirten belirlenimci konum bilgisi.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Sınav oturumu yürürken hiçbir yüzeyden akademik yardım alınamaz — denenen yolların **%100'ü** reddedilir ve bu, kilit kaldırıldığında kırmızı yanan bir testle kanıtlanır.
- **SC-002**: Öğretmen, sıfırdan bir sınav çerçevesi kurup yayınlamayı **10 dakikanın altında** tamamlar.
- **SC-003**: Yayınlanan her sınavın soru dağılımı, blueprint'inin istediği dağılıma **birebir** uyar; uymayan sınav yayınlanamaz.
- **SC-004**: Öğretmen bir dersin asistan davranışını değiştirdiğinde, değişiklik **ilk istekten itibaren** sunucu tarafında geçerlidir.
- **SC-005**: Sunucu erişilemezken açılan hiçbir ekran **10 saniyeden uzun** belirsiz bekleme göstermez.
- **SC-006**: Geçici bir arıza sırasında açılan ekranların **%90'ı** kullanıcı elle müdahale etmeden yüklenir.
- **SC-007**: Her hata ekranı, destek için kullanılabilecek bir istek kimliği gösterir — **istisnasız**.
- **SC-008**: 200 kayıtlık bir listede ilk sayfa, 20 kayıtlık bir listedeki ilk sayfayla **aynı süre aralığında** gelir.
- **SC-009**: Teslim paketindeki belgeler ile kod arasında **sıfır** çelişki kalır; aynı metrik hiçbir iki belgede farklı değer taşımaz.
- **SC-010**: Uçtan uca test paketi koştuktan sonra veritabanında bıraktığı kalıcı kayıt sayısı **sıfırdır**.
- **SC-011**: Bir kullanıcı belge yüklerken başka bir kullanıcının sorusuna dönen yanıt, boş sistemdeki süreye göre **iki katından fazla** gecikmez.
- **SC-012**: Kullanıcı verisini dışa aktarma ve sohbet geçmişini silme akışlarının ikisi de çalışır ve aydınlatma metninde vaat edilen her hak üründe karşılığını bulur.
- **SC-013**: Belge işleme işlerinin ısrarlı başarısızlığı öğretmen panelinde **görünür** olur ve elle yeniden çalıştırılabilir.
- **SC-014**: Bir belge işlenirken gelen sağlık yoklaması **kesintisiz** yanıt verir; bloke süresi ölçülür ve rapora yazılır.
- **SC-015**: Kurulum belgesinde adı geçen ortam değişkenlerinin **%100'ü** kodun okuduğu ada karşılık gelir; bu bir testle sabitlenir ve yeni bir uyuşmazlık eklendiğinde test kırmızı yanar.
- **SC-016**: Soru üretimi ucu sınırsız çağrılamaz; sınırın devreye girdiği ve eşzamanlı ikinci üretimin reddedildiği testle kanıtlanır.

---

## Uygulama sırası

Kullanıcı tam kapsamı seçti (9 Ağustos). Kapsam büyük olduğu için sıra bir tercih değil, bir kesme noktası mekanizmasıdır: dondurma tarihine (17 Ağustos) yetişmeyen iş, sıranın sonundan kesilir — ortasından değil.

| Sıra | İş | Hikâye | Neden burada |
|---:|---|---|---|
| 1 | Aktif sınav → tüm öğrenci yardım yüzeylerini kilitle | US1 | Hocanın açık şartının ihlali; jüri ilk denemede bulur |
| 2 | Issuer ortam değişkeni adını düzelt + regresyon testi | US2 (FR-224) | Tek satırlık düzeltme, üretim yapılandırma hatası |
| 3 | Embedding/ayrıştırmayı event loop dışına taşı + ısıtma | US2 (FR-220, FR-221) | Demo günü en görünür arıza; üç satırlık düzeltme |
| 4 | Soru üretimine kota + eşzamanlılık sınırı | US2 (FR-222, FR-223) | En pahalı uç, bugün sınırsız |
| 5 | Bayat belgeleri koddan yeniden doğrula | US8 | Kod yazmadan yapılmış işi görünür kılar; jürinin okuduğu yer |
| 6 | Güvenilirlik UX'i (timeout, retry, sınıflandırma, istek kimliği, soğuk başlangıç) | US5 | Dış incelemenin tarayıcıda gördüğü ilk şey |
| 7 | Sınav blueprint'i (tam model) | US3 | Kapsamın en büyük parçası; 1-4 sağlam zemin ister |
| 8 | Ders bazlı AI politikası | US4 | Blueprint'in veri modeliyle komşu |
| 9 | Sayfalama | US6 | Ölçek işi, demo için zorunlu değil |
| 10 | Gerçek kimlik (frontend ayağı) | US7 | Anahtar gelince yalnız yapılandırma kalsın diye |
| 11 | Veri hijyeni, KVKK hakları, arıza görünürlüğü, güvenlik başlıkları | US9, US10, US11 | Kesme noktası burada |

Bu sıra, dış incelemeyi yazanın önerdiği sıradır ve şartnamenin ilk taslağındaki sıralamayı düzeltir: ilk taslak 3 ve 4'ü P3'e koymuştu.

---

## Assumptions

- Gerçek Supabase projesi ve LLM sağlayıcı anahtarları **bu hafta içinde** sağlanacaktır (kullanıcı kararı, 9 Ağustos). Anahtara bağımlı işler (T047 faithfulness örneklemi, T050 canlı ortam, T051 prod RLS kanıtı) bu şartnamenin kapsamında değildir; bu şartname onların önündeki kod engellerini kaldırır.
- Ürünün mevcut mimarisi korunur: yeni veri deposu, yeni çatı veya yeni sağlayıcı eklenmez (Anayasa "Teknoloji Kilidi").
- Sınav blueprint'i, bugünkü soru havuzu ve onay akışının **üstüne** gelir; onay kapısını gevşetmez.
- Ders AI politikası varsayılan değerleriyle bugünkü davranışı birebir üretir; hiçbir ders davranış değiştirerek "güncellenmez".
- Kullanıcı hesabı silme, gerçek kimlik sağlayıcısının hesap yaşam döngüsüne bağlıdır; bu şartname ürün tarafındaki karşılığını tanımlar.
- Bu şartname kapsam dondurma tarihi olan **17 Ağustos**'tan önce tamamlanmayı hedefler. Kullanıcı, tam kapsamı (blueprint'in sekiz varlıklı tam modeli dahil) bilerek seçmiştir; bu seçim P1 hikâyelerinin (1, 2, 3, 7) P2 ve P3'ten önce bitirilmesini zorunlu kılar.
- Öğrenci kodunun çalıştırılması, dış kaynak RAG, mobil uygulama ve gamification kapsam dışıdır (PLAN.md "bilinçli kesilenler" tablosu geçerlidir).

---

## Bu şartnamenin dışında bırakılanlar ve nedenleri

| Öneri / iddia | Kaynak | Karar | Neden |
|---|---|---|---|
| "Öğretmen onay akışı yeniden kurulsun" | Hiçbiri — **bu şartnamenin ilk taslağında dış incelemeye yanlış atfedildi** | Yapılmayacak | Dış inceleme onay akışının var olduğunu zaten yazmıştı ("Form, API ve onay akışı var"). Kod da doğruluyor: soruyu `approved` yapan tek bir yol yok; uygulama katmanı, RLS ve altı test birlikte kapatıyor. Blueprint akışı bu kapıyı **gevşetmeyecek** (FR-119). |
| "Sahte sağlayıcı soru üretemiyor, gerçek anahtar şart" | `docs/team/parallel/20_DEVIR_9_AGUSTOS.md:100` ve `README.md:219` (dış inceleme değil) | Yapılmayacak | **İddia bayat.** Sahte sağlayıcı geçerli taslak üretiyor ve havuza sokuyor; `test_uretilen_taslak_havuza_kadar_gider` 9 Ağustos'ta koşturularak doğrulandı. Yapılacak iş kod değil, bunu yanlış anlatan iki belgeyi düzeltmek (User Story 8). Dış incelemenin gerçek maddesi farklıdır ve **geçerlidir**: sahte sağlayıcı şema akışını kanıtlar, pedagojik kaliteyi kanıtlamaz — o T047'nin işidir. |
| Dağıtık hız sınırlayıcı (paylaşılan depo) | Ertelendi | Üretim topolojisi tek replika; ikinci bir veri deposu eklemek Anayasa "Teknoloji Kilidi"ne aykırı. Sınırlayıcının süreç içi olduğu raporda dürüstçe yazılır ve bellek sızıntısı düzeltilir. |
| Hata takip sistemi, latency/cost dashboard, alarm | Ertelendi | Dış servis bağımlılığı ve bulut erişimi ister; T050 kapsamında değerlendirilir. |
| Yük testi, 24 saatlik soak testi, backup/restore tatbikatı | Ertelendi | Canlı ortam ister; T050/T051 sonrası. |
| Taranmış PDF için OCR | Yapılmayacak | PLAN.md'de bilinçli kesilmiş. Desteklenmediği kullanıcıya açıkça söylenir. |
| Semantik önbellek, ikinci vektör deposu, LangChain | Yapılmayacak | PLAN.md "bilinçli kesilenler" tablosunda gerekçeleriyle yazılı. |
