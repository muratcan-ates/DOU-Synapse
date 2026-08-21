---
title: "Süreçler Arası İletişim"
subtitle: "İşletim Sistemleri — Konu 13"
format: pptx
---

# Neden Süreçler Arası İletişim?

- Süreçler yalıtılmış adres uzaylarında çalışır; biri diğerinin değişkenini doğrudan okuyamaz.
- Bu yalıtım bir güvenlik özelliğidir, bir eksiklik değil; ama işbirliği yapan süreçlerin veri alışverişine ihtiyacı vardır.
- Süreçler arası iletişim (IPC), çekirdeğin denetiminde ve açıkça istenerek kurulan bir kanaldır.
- İki temel model vardır: mesaj geçirme ve paylaşımlı bellek.

<!-- slayt -->

# İki Temel Model

- Mesaj geçirme (message passing): veri çekirdek üzerinden kopyalanarak taşınır. Yalıtım korunur, senkronizasyon kanalın içindedir.
- Paylaşımlı bellek (shared memory): iki süreç aynı fiziksel sayfaları adres uzayına eşler. Kopyalama yoktur, en hızlı yöntemdir.
- Paylaşımlı bellekte senkronizasyon uygulamanın sorumluluğundadır; çekirdek yarış koşullarına karşı hiçbir garanti vermez.
- Seçim şu ödünleşimdir: hız mı, yoksa basitlik ve yalıtım mı.

<!-- slayt -->

# Boru (Pipe)

- Tek yönlü bir bayt akışıdır; bir uçtan yazılır, diğerinden okunur.
- pipe() çağrısı iki dosya tanıtıcısı döndürür: okuma ucu ve yazma ucu.
- Yalnız akraba süreçler arasında kullanılabilir, çünkü tanıtıcılar fork() ile miras alınır.
- Kabuktaki boru operatörü bu mekanizmayı kullanır: bir sürecin standart çıktısı diğerinin standart girdisine bağlanır.

<!-- slayt -->

# Boru Davranışı ve Tuzakları

- Boru tamponu doludur ve kimse okumuyorsa, yazan süreç bloke olur.
- Boru boştur ve yazma ucu açıksa, okuyan süreç bloke olur.
- Tüm yazma uçları kapandığında okuma dosya sonu (EOF) döndürür; kullanılmayan uçların kapatılması bu yüzden zorunludur.
- Okuma uçlarının hepsi kapalıyken yazan sürece SIGPIPE sinyali gönderilir; sinyal yakalanmazsa süreç sonlanır.

<!-- slayt -->

# Adlandırılmış Boru (FIFO)

- Dosya sisteminde bir isme sahip olan borudur; mkfifo ile oluşturulur.
- Akraba olmayan süreçler de aynı ismi açarak haberleşebilir.
- Dosya sisteminde görünür ama diskte veri tutmaz; içerik yalnız çekirdek tamponundadır.
- Açma çağrısı, karşı taraf da açana kadar bloke olur; bu bir randevu (rendezvous) davranışıdır.

<!-- slayt -->

# Mesaj Kuyruğu

- Çekirdekte tutulan, sınırlı boyutta ve mesaj sınırlarını koruyan bir kuyruktur.
- Borudan farkı, verinin bayt akışı değil ayrık mesajlar halinde taşınmasıdır; okuyan taraf mesajı böler bulmaz.
- POSIX mesaj kuyrukları mesajlara öncelik atanmasına izin verir; yüksek öncelikli mesaj kuyruğun önüne geçer.
- Gönderen ve alan sürecin aynı anda çalışıyor olması gerekmez; kuyruk bir tamponlama sağlar.

<!-- slayt -->

# Paylaşımlı Bellek

- İki süreç aynı fiziksel sayfaları kendi sanal adres uzaylarına eşler.
- shm_open ile bir bellek nesnesi açılır, mmap ile adres uzayına bağlanır.
- Veri kopyalanmadığı için en yüksek verimi sunar; büyük veri blokları için tercih edilir.
- Sayfa iki süreçte farklı sanal adreslere düşebilir; bu yüzden bölgeye mutlak işaretçi yazmak hatalıdır, ofset kullanılmalıdır.

<!-- slayt -->

# Paylaşımlı Bellekte Senkronizasyon

- Çekirdek yalnız eşlemeyi kurar; kimin ne zaman yazacağına karışmaz.
- İki süreç aynı anda yazarsa sonuç tanımsızdır ve hata sessizce oluşur.
- Çözüm, paylaşımlı bölgenin içine ya da yanına konan bir senkronizasyon nesnesidir: adlandırılmış semafor veya süreçler arası paylaşılan mutex.
- Mutex'i paylaşımlı belleğe koyarken PTHREAD_PROCESS_SHARED özniteliği açılmalıdır; yoksa yalnız aynı süreç içindeki thread'ler için çalışır.

<!-- slayt -->

# Semafor

- Sayaç tutan ve iki atomik işlem sunan senkronizasyon nesnesidir: wait (P) ve signal (V).
- İsimlendirilmiş semaforlar dosya sistemi benzeri bir isim uzayında yaşar ve akraba olmayan süreçlerce kullanılabilir.
- İkili (binary) semafor bir mutex gibi davranır; sayan (counting) semafor sınırlı sayıdaki kaynağı yönetir.
- Semafor sahiplik kavramı taşımaz: bir süreç kilidi alıp başka bir süreç bırakabilir. Mutex'ten en önemli farkı budur.

<!-- slayt -->

# Sinyaller

- Sinyal, bir sürece gönderilen asenkron bir bildirimdir; veri taşımaz, yalnız bir olayı haber verir.
- SIGINT klavyeden kesme, SIGSEGV geçersiz bellek erişimi, SIGCHLD çocuk sürecin durum değişikliğini bildirir.
- SIGKILL ve SIGSTOP yakalanamaz ve göz ardı edilemez; bu, sistemin bir süreci her durumda durdurabilmesini garanti eder.
- Sinyal işleyicisi içinde yalnız async-signal-safe işlevler çağrılabilir; printf veya malloc çağırmak tanımsız davranıştır.

<!-- slayt -->

# Soketler

- Soket, aynı makinede veya ağ üzerinden iletişim sağlayan tek tip bir arayüzdür.
- Unix domain soketleri yalnız yerel makinede çalışır ve ağ yığınını atladığı için TCP'den hızlıdır.
- Soketler dosya tanıtıcısı olarak temsil edilir; okuma, yazma ve seçme (select) çağrıları aynı şekilde kullanılır.
- Unix domain soketleri dosya tanıtıcısı ve süreç kimlik bilgisi aktarımı gibi yerel özel yetenekler de sunar.

<!-- slayt -->

# Uzak Yordam Çağrısı (RPC)

- RPC, ağ üzerinden yapılan bir çağrıyı yerel bir fonksiyon çağrısı gibi göstermeyi hedefler.
- İstemci tarafındaki vekil (stub) parametreleri paketler (marshalling), sunucu tarafındaki vekil açar.
- Soyutlama sızdırır: ağ gecikmesi, kısmi arıza ve yeniden deneme yerel çağrılarda bulunmayan sorunlardır.
- Bir yerel çağrı ya çalışır ya çökertir; bir RPC ayrıca sessizce kaybolabilir ve bu üçüncü olasılık tasarımı değiştirir.

<!-- slayt -->

# En Az Bir Kez ve En Fazla Bir Kez

- Yanıt gelmeyen bir RPC yeniden gönderilirse, isteğin iki kez işlenmiş olma ihtimali vardır.
- En az bir kez (at-least-once) semantiği yeniden dener; işlem etkisiz-tekrarlı (idempotent) değilse sonuç bozulur.
- En fazla bir kez (at-most-once) semantiği isteklere kimlik verir ve sunucu tekrarları tanıyıp yok sayar.
- Bakiye artırma etkisiz-tekrarlı değildir; bakiyeyi belirli bir değere ayarlamak etkisiz-tekrarlıdır.

<!-- slayt -->

# Yöntemlerin Karşılaştırması

| Yöntem | Yön | Kapsam | Kopya | Senkronizasyon |
|---|---|---|---|---|
| Boru | Tek yönlü | Akraba süreçler | Var | Kanalda |
| FIFO | Tek yönlü | Aynı makine | Var | Kanalda |
| Mesaj kuyruğu | Çift yönlü | Aynı makine | Var | Kanalda |
| Paylaşımlı bellek | Çift yönlü | Aynı makine | Yok | Uygulamada |
| Soket | Çift yönlü | Ağ dahil | Var | Kanalda |

<!-- slayt -->

# Nasıl Seçilir?

- Veri büyük ve gecikme kritikse paylaşımlı bellek; ama senkronizasyon yükünü üstlenmeye hazır olun.
- Süreçler farklı makinelerde olabilecekse baştan soket seçin; sonradan geçiş maliyetlidir.
- Basit bir üretici-tüketici zinciri için boru yeterlidir ve en az kodu gerektirir.
- Mesaj sınırları anlam taşıyorsa bayt akışı yerine mesaj kuyruğu kullanın; sınırı elle yeniden kurmak sık yapılan bir hatadır.

<!-- slayt -->

# Yaygın Hatalar

- Boruda kullanılmayan ucu kapatmamak: okuyan taraf EOF göremez ve süresiz bekler.
- Paylaşımlı bellekte kilit kullanmamak: hata seyrek görülür ve testte yakalanmaz.
- Sinyal işleyicisinde güvenli olmayan işlev çağırmak: çökme, çağrının hangi anda kesildiğine bağlıdır.
- Kaynakları temizlememek: adlandırılmış semafor ve paylaşımlı bellek nesneleri süreç bitse de sistemde kalır.

<!-- slayt -->

# Özet

- IPC, yalıtımı bilinçli ve denetimli biçimde delmenin yoludur.
- Mesaj geçirme yalıtımı korur ve senkronizasyonu kanala gömer; paylaşımlı bellek hızlıdır ama senkronizasyonu size bırakır.
- Sinyaller veri taşımaz, olay bildirir ve işleyici içinde yapılabilecekler çok kısıtlıdır.
- RPC yerel çağrı gibi görünür ama kısmi arıza ihtimali onu temelden farklı kılar.
