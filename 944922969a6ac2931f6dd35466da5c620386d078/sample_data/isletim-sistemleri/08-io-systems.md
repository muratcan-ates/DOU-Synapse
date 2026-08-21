---
title: "Giriş/Çıkış Sistemleri: Kesme, DMA ve Sürücü Katmanları"
subtitle: "İşletim Sistemleri — Konu 8"
format: pdf
---

# 1. G/Ç Donanımının Görünümü

İşletim sisteminin en dağınık işi giriş/çıkıştır. CPU ve bellek tek tip davranırken
klavyeden ağ kartına kadar her aygıtın hızı, veri birimi ve hata davranışı farklıdır.
Çekirdeğin işi bu çeşitliliği tek tip bir arayüzün arkasına saklamaktır.

Her aygıt denetleyicisinin (controller) birkaç yazmacı vardır:

- **Veri yazmacı (data register):** aktarılacak baytlar.
- **Durum yazmacı (status register):** aygıt meşgul mü, hata var mı, veri hazır mı.
- **Denetim yazmacı (control register):** komut ve mod ayarları.

Bu yazmaçlara iki yoldan erişilir. **Bellek eşlemeli G/Ç (memory-mapped I/O)**
yazmaçları fiziksel adres uzayının bir bölgesine eşler; sıradan `load`/`store`
komutları aygıtla konuşur. **Ayrı G/Ç port uzayı (port-mapped I/O)** ise `in`/`out`
gibi özel komutlar gerektirir. Bellek eşlemeli yaklaşım günümüzde yaygındır: aynı
adresleme donanımını ve aynı koruma mekanizmasını kullanır.

## 1.1. Aygıt Sınıfları

- **Blok aygıtlar (block devices):** sabit boyutlu bloklar halinde okunur/yazılır ve
  rastgele erişilebilir. Disk ve SSD bu sınıftadır.
- **Karakter aygıtlar (character devices):** bayt akışı sunar, arama (seek) yoktur.
  Klavye, seri port, fare.
- **Ağ aygıtları:** paket odaklıdır ve kendi arayüzü (socket) vardır; blok/karakter
  ikilisine sığmadığı için ayrı ele alınır.

<!-- sayfa -->

# 2. Üç Aktarım Yöntemi

## 2.1. Yoklama (Polling)

CPU, durum yazmacını bir döngü içinde tekrar tekrar okur ve "meşgul" biti düşene kadar
bekler. Kodu en basit olan yöntemdir ve gecikmesi çok düşüktür — aygıt hazır olduğu an
CPU zaten bakıyordur.

Bedeli, bekleme süresinin tamamen boşa gitmesidir. Aygıt milisaniyeler mertebesinde
yanıt veriyorsa CPU milyonlarca komut çalıştırabileceği süreyi döngüde harcar. Yoklama
yalnız çok hızlı aygıtlarda ya da beklemenin kesme kurma maliyetinden kısa olduğu
durumlarda mantıklıdır.

## 2.2. Kesme (Interrupt)

Aygıt işini bitirdiğinde CPU'ya bir **kesme** sinyali gönderir. CPU o anki komutu
tamamlar, program sayacını ve durum yazmaçlarını saklar ve **kesme vektör tablosundan**
ilgili işleyicinin adresini bulup oraya dallanır.

Kesmeler ikiye ayrılır:

- **Maskelenebilir kesmeler (maskable):** çekirdek kritik bir bölgedeyken geçici
  olarak kapatılabilir.
- **Maskelenemeyen kesmeler (non-maskable, NMI):** donanım hatası gibi ertelenemez
  olaylar; kapatılamazlar.

Kesme işleyicisinin uzun sürmesi tüm sistemi bekletir. Bu yüzden modern çekirdekler
işi ikiye böler: **üst yarı (top half)** yalnız aygıtı susturur ve veriyi alır; asıl
işleme **alt yarıya (bottom half)** ertelenir ve kesmeler açıkken çalışır.

## 2.3. Doğrudan Bellek Erişimi (DMA)

Büyük aktarımlarda her baytı CPU'ya taşıtmak israftır. **DMA denetleyicisi**, CPU'dan
bağımsız olarak aygıt ile bellek arasında veri taşır. CPU yalnız aktarımı başlatır
(kaynak adresi, hedef adresi, uzunluk) ve aktarım bittiğinde tek bir kesme alır.

DMA sırasında denetleyici bellek veri yolunu kullanır ve CPU'nun bellek erişimini
yavaşlatabilir; bu etkiye **cycle stealing** denir. Ayrıca DMA doğrudan fiziksel
belleğe yazdığı için CPU önbelleğinde eski veri kalabilir — **önbellek tutarlılığı
(cache coherence)** ya donanımla ya da çekirdeğin önbelleği geçersiz kılmasıyla
sağlanmak zorundadır.

<!-- sayfa -->

# 3. Çekirdek İçindeki G/Ç Katmanları

Çekirdek G/Ç'yi katmanlı bir yapıyla ele alır; her katman altındakinin ayrıntısını
gizler:

1. **Kullanıcı seviyesi kütüphaneler:** tamponlanmış `fread`/`fwrite` gibi çağrılar.
2. **Aygıttan bağımsız çekirdek katmanı:** isimlendirme, koruma, tamponlama,
   önbellekleme, hata raporlama. Sistem çağrısı arayüzü buradadır.
3. **Aygıt sürücüleri (device drivers):** aygıta özgü tek yer. Üst katmanın çağırdığı
   `open`, `read`, `write`, `ioctl` gibi standart bir işlev tablosunu doldurur.
4. **Kesme işleyicileri:** aygıttan gelen olayları karşılar.

Sürücü arayüzünün standart olması belirleyicidir: yeni bir disk modeli için yalnız
sürücü yazılır, dosya sistemi ya da sistem çağrısı katmanı değişmez.

## 3.1. Engelleyen ve Engellemeyen Çağrılar

- **Engelleyen (blocking):** çağrı, iş bitene kadar döner değildir; süreç `blocked`
  durumuna geçer. Programlaması en kolay olanıdır.
- **Engellemeyen (non-blocking):** çağrı hemen döner ve o an ne kadar veri
  aktarılabildiyse onu bildirir.
- **Eşzamansız (asynchronous):** çağrı hemen döner, aktarım arka planda sürer ve
  bittiğinde süreç bir sinyal veya olayla haberdar edilir.

Engellemeyen ile eşzamansız arasındaki fark sık karıştırılır: engellemeyen çağrı
"şimdi ne yapabildiysem o", eşzamansız çağrı "hepsini yapacağım, sen devam et"
anlamına gelir.

## 3.2. Tamponlama, Önbellekleme, Spooling

**Tamponlama (buffering)** üreten ve tüketen tarafın hız farkını soğurur; ayrıca
aktarım sırasında uygulamanın tamponunu değiştirmesine karşı **kopyalama semantiği**
sağlar. **Önbellekleme (caching)** sık kullanılan veriyi hızlı ortamda tutar; tampondan
farkı, önbellekteki verinin bir **kopya** olmasıdır. **Spooling** aynı anda yalnız bir
işi kabul edebilen aygıtlar (yazıcı) için çıktıyı diske biriktirir ve sırayla gönderir.

<!-- sayfa -->

# 4. Hata, Koruma ve Başarım

## 4.1. Hataların Ele Alınışı

G/Ç, çekirdekte hatanın en sık görüldüğü yerdir: kablo çıkar, disk bloğu bozulur, ağ
paketi düşer. Çekirdek geçici (transient) hataları genelde **yeniden deneyerek**
çözer; kalıcı hataları çağırana bir hata koduyla bildirir.

Sessiz veri bozulmasına karşı sağlama toplamı (checksum) kullanılır. Bir bloğun
sağlaması tutmuyorsa okunan veri **kullanılmaz**; yanlış veriyi doğru sanıp devam
etmek, hata vermekten çok daha zararlıdır.

## 4.2. Koruma

G/Ç komutları **ayrıcalıklı (privileged)** komutlardır ve yalnız çekirdek modunda
çalıştırılabilir. Bir kullanıcı süreci diske doğrudan yazabilseydi dosya sistemi
izinlerinin hiçbir anlamı kalmazdı: koruma dosya sisteminde değil, aygıta erişimin
tekelinde durur.

Bellek eşlemeli G/Ç yazmaçları da sayfa tablosu üzerinden korunur; bu bölge kullanıcı
sürecinin adres uzayına eşlenmez.

## 4.3. Başarımı Belirleyen Etkenler

- **Bağlam değiştirme sayısı.** Her kesme bir bağlam değiştirmedir; saniyede yüz
  binlerce paket alan bir ağ kartında kesmeler CPU'yu boğar. Çözüm **kesme birleştirme
  (interrupt coalescing)**: aygıt her paket için değil, belli sayıda paket veya belli
  bir süre sonra tek kesme üretir.
- **Kopya sayısı.** Veriyi aygıttan çekirdek tamponuna, oradan kullanıcı tamponuna
  kopyalamak iki kopyadır. **Sıfır kopya (zero-copy)** teknikleri veriyi doğrudan
  kullanıcı sayfasına DMA ile yazdırır.
- **Eşzamanlılık.** Tek bir isteği hızlandırmak yerine birden çok isteği aynı anda
  uçurmak, disk ve ağ gibi yüksek gecikmeli aygıtlarda toplam verimi belirler.
