---
title: "Gerçek Zamanlı Zamanlama"
subtitle: "İşletim Sistemleri — Konu 12"
format: pptx
---

# Gerçek Zamanlı Sistem Nedir?

- Gerçek zamanlı bir sistemde doğruluk yalnız sonucun değerine değil, sonucun ne zaman üretildiğine de bağlıdır.
- Doğru cevabı geç vermek, bu sistemlerde yanlış cevap vermekle eşdeğerdir.
- Hedef ortalama başarım değil, en kötü durumun öngörülebilirliğidir.
- Bir hava yastığı denetleyicisi ortalama 2 milisaniyede tepki veriyorsa bu bilgi yetmez; en kötü durumda kaç milisaniye sürdüğü gerekir.

<!-- slayt -->

# Katı ve Yumuşak Gerçek Zaman

- Katı (hard) gerçek zaman: bir son tarihin (deadline) kaçırılması sistem arızası sayılır. Uçuş kontrol, ABS freni, kalp pili.
- Yumuşak (soft) gerçek zaman: son tarih kaçırıldığında hizmet kalitesi düşer ama sistem çalışmaya devam eder. Video oynatma, ses akışı.
- Sağlam (firm) gerçek zaman: geciken sonucun değeri sıfırdır ama sistem arızalanmaz; geç gelen kare atılır.
- Bu ayrım tasarımı belirler: katı sistemlerde en kötü durum matematiksel olarak kanıtlanmak zorundadır.

<!-- slayt -->

# Temel Kavramlar

- Periyot (T): görevin ne sıklıkla tekrar çalıştırılacağı.
- Hesaplama süresi (C): görevin en kötü durumda ihtiyaç duyduğu CPU süresi (WCET).
- Son tarih (D): görevin tamamlanması gereken an. Çoğu modelde D = T varsayılır.
- Kullanım oranı (utilization): U = C / T. Toplam kullanım, tüm görevlerin oranlarının toplamıdır.

<!-- slayt -->

# En Kötü Durum Yürütme Süresi

- WCET (Worst-Case Execution Time), bir görevin herhangi bir girdi ve herhangi bir donanım durumunda alabileceği en uzun süredir.
- Ölçümle bulunan en büyük değer WCET değildir; ölçülmemiş bir yol daha uzun olabilir.
- Statik analiz kodun tüm yollarını inceler ama önbellek ve dallanma tahmini yüzünden karamsar sonuç verir.
- Önbellek, boru hattı ve spekülatif yürütme WCET analizini zorlaştırır; katı gerçek zamanlı sistemlerde bazen bu özellikler kapatılır.

<!-- slayt -->

# Zamanlanabilirlik Analizi

- Soru şudur: verilen görev kümesi, verilen algoritmayla tüm son tarihleri karşılayabilir mi?
- Analiz çalıştırmadan önce, tasarım zamanında yapılır; test etmek yeterli değildir çünkü en kötü durum testte hiç oluşmayabilir.
- Gerekli koşul her zaman U ≤ 1'dir: toplam talep CPU'nun sunabileceğinden fazlaysa hiçbir algoritma kurtaramaz.
- U ≤ 1 yeterli koşul değildir; algoritmaya göre daha dar sınırlar geçerlidir.

<!-- slayt -->

# Rate Monotonic (RM)

- Statik öncelikli bir algoritmadır: öncelik bir kez atanır ve çalışma boyunca değişmez.
- Kural basittir: periyodu kısa olan görevin önceliği yüksektir.
- Kesmeli (preemptive) çalışır; yüksek öncelikli bir görev hazır olduğunda çalışan görevi keser.
- Statik öncelikli algoritmalar arasında optimaldir: RM ile zamanlanamayan bir küme, hiçbir sabit öncelik ataması ile zamanlanamaz.

<!-- slayt -->

# RM Kullanım Sınırı

- Liu ve Layland sınırı: n görev için U ≤ n × (2^(1/n) − 1) ise küme kesinlikle zamanlanabilir.
- n = 1 için sınır 1.000, n = 2 için 0.828, n = 3 için 0.780'dir.
- n sonsuza giderken sınır ln 2 ≈ 0.693'e yakınsar.
- Bu bir yeterli koşuldur, gerekli koşul değil: sınırın üstündeki bir küme yine de zamanlanabilir olabilir ve bunun için tam analiz gerekir.

<!-- slayt -->

# Earliest Deadline First (EDF)

- Dinamik öncelikli bir algoritmadır: öncelik her an değişir.
- Kural: son tarihi en yakın olan görev çalışır.
- Tek işlemcide optimaldir; U ≤ 1 olan her görev kümesini zamanlayabilir.
- RM'in yüzde 69'luk sınırına karşılık EDF işlemciyi yüzde yüze kadar kullanabilir.

<!-- slayt -->

# RM ile EDF Karşılaştırması

| Ölçüt | Rate Monotonic | EDF |
|---|---|---|
| Öncelik | Statik | Dinamik |
| Kullanım sınırı | ~%69 (n büyükken) | %100 |
| Çalışma zamanı maliyeti | Düşük | Daha yüksek |
| Aşırı yükte davranış | Öngörülebilir: düşük öncelikli kaçırır | Domino etkisi: çok sayıda görev kaçırır |

<!-- slayt -->

# Aşırı Yük Davranışı Neden Önemli?

- RM aşırı yükte hangi görevin kaçıracağını önceden söyler: en düşük öncelikli olan.
- EDF aşırı yükte kontrolsüzdür; bir görev son tarihini kaçırınca diğerlerini de geciktirir ve zincirleme kaçırma oluşur.
- Kritik ve kritik olmayan görevlerin karıştığı sistemlerde bu davranış farkı RM'i güvenli kılar.
- Bu yüzden havacılık ve otomotiv standartları çoğunlukla statik öncelikli zamanlamayı tercih eder.

<!-- slayt -->

# Öncelik Tersine Dönmesi

- Yüksek öncelikli bir görev, düşük öncelikli bir görevin elindeki kilidi beklerken bloke olur.
- Bu tek başına kaçınılmazdır ve sınırlı (bounded) tersine dönme olarak adlandırılır.
- Asıl sorun, araya giren orta öncelikli bir görevin düşük öncelikliyi kesmesidir.
- O anda yüksek öncelikli görev, kendisiyle hiç kaynak paylaşmayan orta öncelikli bir görevi dolaylı olarak beklemeye başlar: sınırsız (unbounded) tersine dönme.

<!-- slayt -->

# Mars Pathfinder Örneği

- 1997'de Mars yüzeyindeki Pathfinder aracı tekrar tekrar kendini yeniden başlattı.
- Sebep sınırsız öncelik tersine dönmesiydi: yüksek öncelikli veri yolu görevi, düşük öncelikli meteoroloji görevinin tuttuğu mutex'i bekliyordu.
- Araya giren orta öncelikli iletişim görevi meteoroloji görevini keserek kilidin bırakılmasını geciktirdi.
- Gözcü zamanlayıcı (watchdog) son tarihin kaçırıldığını görüp sistemi sıfırladı; hata yer testlerinde de görülmüş ama nadir olduğu için göz ardı edilmişti.

<!-- slayt -->

# Öncelik Kalıtımı

- Öncelik kalıtımı (priority inheritance) protokolünde, bir kilidi tutan görev o kilidi bekleyen en yüksek öncelikli görevin önceliğini geçici olarak devralır.
- Böylece orta öncelikli görevler araya giremez ve tersine dönme süresi sınırlanır.
- Kilit bırakıldığında görev kendi özgün önceliğine geri döner.
- Pathfinder'daki düzeltme buydu: ilgili mutex için öncelik kalıtımı bayrağı uzaktan açıldı.

<!-- slayt -->

# Öncelik Tavanı

- Öncelik tavanı (priority ceiling) protokolünde her kaynağa, o kaynağı kullanabilecek en yüksek öncelikli görevin önceliği atanır.
- Bir görev kaynağı aldığında önceliği doğrudan tavan değerine yükselir.
- Kalıtımdan farkı, yükselmenin bekleyen biri olmasa da gerçekleşmesidir.
- Yan faydası kilitlenmeyi (deadlock) yapısal olarak engellemesidir; kilitler her zaman aynı sırayla alınmış olur.

<!-- slayt -->

# Zamanlayıcı Gecikmesi

- Gerçek zamanlı bir sistemde ölçülen gecikme yalnız kuyrukta bekleme değildir.
- Kesme gecikmesi: kesmenin gelmesiyle işleyicinin başlaması arasındaki süre.
- Zamanlayıcı gönderme (dispatch) gecikmesi: zamanlayıcının çalışan görevi durdurup yenisini başlatması.
- Çekirdeğin kesmeleri kapattığı en uzun kritik bölge, tüm sistemin en kötü durum gecikmesine doğrudan eklenir.

<!-- slayt -->

# Kesmeli Çekirdek İhtiyacı

- Geleneksel çekirdekler sistem çağrısı işlenirken kesilemez; bu, yüksek öncelikli bir görevin çekirdeğin işini bitirmesini beklemesi demektir.
- Gerçek zamanlı çekirdekler kesme noktaları (preemption points) ekler ya da tümüyle kesmeli hale getirilir.
- Linux PREEMPT_RT yaması bu amaçla spinlock'ların büyük kısmını uyuyabilir kilitlere çevirir.
- Ölçüt tek bir sayıdır: en kötü durum zamanlama gecikmesi ve onun ne kadar sıkı sınırlandığı.

<!-- slayt -->

# Periyodik Olmayan Görevler

- Gerçek sistemlerde her görev periyodik değildir; kullanıcı girdisi ve arıza sinyalleri düzensiz gelir.
- Aperiyodik görevler için bir sunucu görevi (server task) tanımlanır ve ona sabit bir bütçe verilir.
- Poller server, periyodunun başında bütçesini harcar ve iş yoksa bütçeyi kaybeder.
- Deferrable server bütçesini saklayabilir; tepki süresi iyileşir ama zamanlanabilirlik analizi karmaşıklaşır.

<!-- slayt -->

# Özet

- Gerçek zaman hız değil öngörülebilirlik demektir; ölçüt ortalama değil en kötü durumdur.
- RM statik önceliklidir, sınırı yaklaşık yüzde 69'dur ve aşırı yükte davranışı öngörülebilirdir.
- EDF dinamik önceliklidir, işlemciyi tam kullanır ama aşırı yükte domino etkisi gösterir.
- Paylaşılan kaynak varsa öncelik kalıtımı veya öncelik tavanı protokolü olmadan hiçbir analiz geçerli değildir.
