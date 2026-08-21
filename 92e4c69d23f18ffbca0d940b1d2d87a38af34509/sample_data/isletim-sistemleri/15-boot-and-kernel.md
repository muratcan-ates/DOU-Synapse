---
title: "Açılış Süreci ve Çekirdek Mimarileri"
subtitle: "İşletim Sistemleri — Konu 15"
format: pptx
---

# Açılışta İlk Adım

- Güç verildiğinde işlemci bellekte hiçbir program olmadığını bilmez; sabit bir adresten komut okumaya başlar.
- Bu adres kalıcı bellektedir (ROM / flash) ve içinde ürün yazılımı (firmware) bulunur.
- Ürün yazılımı önce POST (Power-On Self-Test) ile temel donanımı sınar.
- Sonra önyükleyiciyi (bootloader) bulup belleğe yükler ve denetimi ona devreder.

<!-- slayt -->

# BIOS ve UEFI

- BIOS eski standarttır: 16 bit gerçek kipte çalışır, diskin ilk sektöründeki MBR'yi okur.
- MBR yalnız 512 bayttır ve bunun 446 baytı koda ayrılır; bu yüzden gerçek önyükleyici birden çok aşamaya bölünür.
- UEFI modern standarttır: 32/64 bit çalışır, dosya sistemini kendi okur ve önyükleyiciyi bir EFI bölümündeki dosyadan yükler.
- UEFI ayrıca Secure Boot sunar: yalnız imzası doğrulanan önyükleyici çalıştırılır.

<!-- slayt -->

# Önyükleyici

- Görevi çekirdeği diskten belleğe yüklemek ve ona parametre geçirmektir.
- GRUB, systemd-boot ve Windows Boot Manager yaygın örneklerdir.
- Birden çok işletim sistemi kuruluysa seçim menüsünü sunan katman budur.
- Çekirdek parametreleri buradan verilir; kurtarma kipine geçmek ya da bir sürücüyü devre dışı bırakmak bu satırda yapılır.

<!-- slayt -->

# Çekirdeğin İlk İşleri

- Kendini açar (çoğu çekirdek imajı sıkıştırılmış saklanır) ve korumalı kipe geçer.
- Bellek haritasını ürün yazılımından alır ve fiziksel bellek yöneticisini kurar.
- Kesme vektör tablosunu yerleştirir ve kesmeleri açar.
- Zamanlayıcıyı başlatır ve ilk kullanıcı sürecini oluşturur.

<!-- slayt -->

# initramfs Neden Var?

- Kök dosya sistemi bir RAID dizisinde ya da şifreli bir birimde olabilir; onu okumak için sürücü gerekir.
- O sürücü de kök dosya sisteminde durur: yumurta-tavuk problemi.
- initramfs, belleğe yüklenen geçici küçük bir kök dosya sistemidir ve gerekli sürücüleri içerir.
- Gerçek kök bağlandıktan sonra denetim ona devredilir (switch_root) ve geçici sistem serbest bırakılır.

<!-- slayt -->

# İlk Kullanıcı Süreci

- Çekirdek PID 1 olan ilk süreci başlatır; bu süreç asla ölmemelidir.
- PID 1 öldüğünde çekirdek panic verir, çünkü öksüz süreçleri sahiplenecek kimse kalmaz.
- Geleneksel init, çalışma seviyelerine (runlevel) göre kabuk betikleri çalıştırırdı; sıralı olduğu için yavaştı.
- systemd bağımlılık grafiğine göre hizmetleri paralel başlatır ve soket etkinleştirmesiyle açılışı hızlandırır.

<!-- slayt -->

# Kapanış Süreci

- Kapanış açılışın tersi değildir; kritik olan verinin diske yazılmasıdır.
- Süreçlere önce SIGTERM gönderilir, tanınan süreye rağmen kapanmayanlara SIGKILL uygulanır.
- Dosya sistemi tamponları boşaltılır (sync) ve birimler salt okunur olarak yeniden bağlanır.
- Bu adımlar atlanırsa dosya sistemi tutarsız kalır; günlükleyen (journaling) dosya sistemleri bu durumda kurtarma yapabilir.

<!-- slayt -->

# Sistem Çağrısı Mekanizması

- Kullanıcı süreci çekirdeğe doğrudan atlayamaz; özel bir komut kullanır.
- x86-64'te bu komut syscall'dır; eski sistemlerde int 0x80 yazılım kesmesi kullanılırdı.
- Çağrı numarası bir yazmaca (rax) konur, argümanlar belirli yazmaçlara yerleştirilir.
- Çekirdek numaraya göre sistem çağrısı tablosundan işleyiciyi bulur ve çalıştırır.

<!-- slayt -->

# Sistem Çağrısının Maliyeti

- Ayrıcalık seviyesi değişimi, yazmaç saklama ve kullanıcı belleğinin doğrulanması maliyet yaratır.
- Bir sistem çağrısı sıradan bir fonksiyon çağrısından yüzlerce kat pahalıdır.
- vDSO mekanizması bazı çağrıları (gettimeofday gibi) çekirdeğe hiç girmeden karşılar.
- io_uring gibi arayüzler çok sayıda G/Ç isteğini tek bir çağrıda toplayarak geçiş sayısını azaltır.

<!-- slayt -->

# Kullanıcı Belleğine Güvenilmez

- Sistem çağrısına gelen işaretçiler kullanıcı sürecinden gelir ve doğrulanmadan kullanılamaz.
- Çekirdek, adresin sürecin adres uzayında olduğunu ve erişimin izinli olduğunu denetler.
- Veri doğrudan kullanılmaz, çekirdek belleğine kopyalanır (copy_from_user).
- Denetim ile kullanım arasında geçen sürede sayfanın değiştirilmesi TOCTOU sınıfı bir açıktır.

<!-- slayt -->

# Monolitik Çekirdek

- Dosya sistemi, ağ yığını, sürücüler ve zamanlayıcı tek bir adres uzayında, çekirdek modunda çalışır.
- Bileşenler birbirini doğrudan fonksiyon çağrısıyla kullanır; bu yüzden hızlıdır.
- Bir sürücüdeki hata tüm çekirdeği çökertebilir, çünkü koruma sınırı yoktur.
- Linux ve klasik Unix türevleri bu mimaridedir.

<!-- slayt -->

# Mikroçekirdek

- Çekirdekte yalnız en temel işlevler kalır: adres uzayı yönetimi, thread zamanlama, süreçler arası iletişim.
- Dosya sistemi ve sürücüler kullanıcı modunda ayrı süreçler olarak çalışır.
- Çöken bir sürücü yalnız kendi sürecini düşürür ve yeniden başlatılabilir.
- Bedeli, bileşenlerin fonksiyon çağrısı yerine mesajlaşmasıdır; bu ek yük mikroçekirdeğin klasik eleştirisidir.

<!-- slayt -->

# Hibrit ve Modüler Yaklaşım

- Pratikte saf mimariler nadirdir; sistemler ara noktalarda durur.
- Windows NT çekirdeği mikroçekirdek fikirlerini alır ama başarım için grafik ve dosya sistemini çekirdeğe taşır.
- Linux monolitiktir ama yüklenebilir çekirdek modülleriyle (LKM) çalışırken genişletilebilir.
- Modül, çekirdek adres uzayına yüklenir; yani modülerlik esneklik verir, koruma sınırı vermez.

<!-- slayt -->

# Ekzokernel ve Unikernel

- Ekzokernel, soyutlama sunmak yerine donanımı güvenli biçimde uygulamalara doğrudan tahsis eder.
- Uygulama kendi dosya sistemi ve bellek yönetimi politikasını kütüphane olarak seçer.
- Unikernel, uygulama ile çekirdeği tek bir adres uzayında, tek amaçlı bir imaj olarak birleştirir.
- Bulut ortamında hipervizör zaten yalıtımı sağladığı için bu yaklaşım küçük ve hızlı açılan imajlar üretir.

<!-- slayt -->

# Çekirdek Mimarilerinin Karşılaştırması

| Ölçüt | Monolitik | Mikroçekirdek |
|---|---|---|
| Bileşen iletişimi | Fonksiyon çağrısı | Mesajlaşma |
| Başarım | Yüksek | Mesaj yükü nedeniyle düşük |
| Hata yalıtımı | Zayıf | Güçlü |
| Sürücü çökmesi | Sistem çöker | Sürücü yeniden başlar |
| Kod tabanı | Büyük | Çekirdek küçük |

<!-- slayt -->

# Çekirdek Modülü Yönetimi

- lsmod yüklü modülleri, modinfo modül bilgisini gösterir.
- insmod tek bir modülü, modprobe ise bağımlılıklarıyla birlikte yükler.
- Modül imzalama, Secure Boot açıkken imzasız modüllerin yüklenmesini engeller.
- Bir modül çekirdek sürümüne sıkı bağlıdır; çekirdek güncellendiğinde modülün yeniden derlenmesi gerekir.

<!-- slayt -->

# Panik ve Oops

- Kernel oops, çekirdekte yakalanan ama sistemi durdurmayan bir hatadır; ilgili süreç öldürülür.
- Kernel panic, devam edilemez bir hatadır ve sistem durdurulur.
- Panik anında yazmaç değerleri ve çağrı yığını (stack trace) basılır; teşhis bu çıktıya dayanır.
- kdump mekanizması panik anında bellek dökümünü yedek bir çekirdekle diske yazar.

<!-- slayt -->

# Özet

- Açılış zinciri ürün yazılımından önyükleyiciye, oradan çekirdeğe ve PID 1'e uzanır; her halka bir sonrakini yükler.
- initramfs, kök dosya sistemini okumak için gereken sürücülerin yumurta-tavuk problemini çözer.
- Sistem çağrısı, kullanıcı ile çekirdek arasındaki tek denetimli kapıdır ve pahalıdır.
- Monolitik mimari başarımı, mikroçekirdek hata yalıtımını önceler; gerçek sistemler ikisinin arasında durur.
