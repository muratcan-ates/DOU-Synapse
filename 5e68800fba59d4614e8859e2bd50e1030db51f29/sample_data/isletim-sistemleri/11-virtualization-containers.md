---
title: "Sanallaştırma ve Konteynerler"
subtitle: "İşletim Sistemleri — Konu 11"
format: pptx
---

# Sanallaştırma Nedir?

- Sanallaştırma, tek bir fiziksel makinenin kaynaklarını birden çok yalıtılmış çalışma ortamına bölen tekniktir.
- Her ortam kendi işletim sistemini çalıştırdığını sanır; donanımı gerçekte bir yazılım katmanı sunar.
- Amaç üç başlıkta toplanır: kaynak kullanımını artırmak, arızayı yalıtmak, ortamı taşınabilir kılmak.
- Bir sunucunun ortalama CPU kullanımı yüzde onlarda kalırken, aynı donanımda on sanal makine çalıştırmak israfı doğrudan azaltır.

<!-- slayt -->

# Hipervizör Nedir?

- Hipervizör (hypervisor / VMM), sanal makineleri oluşturan ve yöneten yazılım katmanıdır.
- Konuk (guest) işletim sistemlerinin ayrıcalıklı komutlarını yakalar ve onlar adına gerçek donanıma çevirir.
- Konuk, kendisinin çekirdek modunda olduğunu sanır; gerçekte hipervizörün denetiminde bir kullanıcı seviyesinde koşar.
- Bu yakalama-ve-taklit etme (trap and emulate) mekanizması sanallaştırmanın temelidir.

<!-- slayt -->

# Tip 1 ve Tip 2 Hipervizörler

- Tip 1 (bare-metal): doğrudan donanım üzerinde çalışır, altında bir işletim sistemi yoktur. Örnekler: Xen, VMware ESXi, Microsoft Hyper-V.
- Tip 2 (hosted): bir ana işletim sistemi üzerinde sıradan bir uygulama gibi çalışır. Örnekler: VirtualBox, VMware Workstation, QEMU.
- Tip 1 daha az katman geçtiği için daha hızlıdır ve saldırı yüzeyi daha dardır; veri merkezlerinde tercih edilir.
- Tip 2 kurulumu kolaydır ve masaüstünde geliştirme/test için uygundur.

<!-- slayt -->

# Tam Sanallaştırma

- Konuk işletim sistemi hiç değiştirilmez; kendisinin sanallaştırıldığını bilmez.
- Ayrıcalıklı komutlar hipervizör tarafından yakalanır ve taklit edilir.
- Avantajı, değiştirilemeyen kapalı kaynak işletim sistemlerinin de çalıştırılabilmesidir.
- Bedeli, her yakalamanın bir bağlam değiştirme maliyeti getirmesidir.

<!-- slayt -->

# Paravirtualization

- Konuk işletim sistemi, sanallaştırıldığını bilecek şekilde değiştirilir.
- Ayrıcalıklı işlemler için donanım komutu yerine hipervizöre doğrudan çağrı (hypercall) yapılır.
- Yakalama maliyeti ortadan kalktığı için başarım tam sanallaştırmaya göre yüksektir.
- Kısıtı açıktır: çekirdeği değiştirilemeyen bir işletim sistemi bu yöntemle çalıştırılamaz.

<!-- slayt -->

# Donanım Destekli Sanallaştırma

- Intel VT-x ve AMD-V, işlemciye kök (root) ve kök olmayan (non-root) diye yeni bir çalışma kipi ekler.
- Konuk çekirdeği kendi ayrıcalık halkasında koşabilir; ayrıcalıklı komutlar donanım tarafından hipervizöre yönlendirilir.
- Genişletilmiş sayfa tabloları (EPT / NPT) konuk sanal adresini doğrudan ana makine fiziksel adresine çevirir.
- Bu destek sayesinde tam sanallaştırma, paravirtualization'a yakın başarım verir ve yazılımsal ikili çeviriye gerek kalmaz.

<!-- slayt -->

# Bellek Sanallaştırma

- İki kat çeviri vardır: konuk sanal adresi, konuk fiziksel adresi ve ana makine fiziksel adresi.
- Gölge sayfa tabloları (shadow page tables) bu iki katı yazılımla tek bir tabloda birleştirir; güncelleme maliyeti yüksektir.
- Genişletilmiş sayfa tabloları aynı işi donanımda yapar ve gölge tabloya olan ihtiyacı ortadan kaldırır.
- Bellek şişirme (ballooning) tekniğinde konuğa yüklenen bir sürücü bellek talep ederek kullanılmayan sayfaların ana makineye geri verilmesini sağlar.

<!-- slayt -->

# Konteyner Nedir?

- Konteyner, aynı çekirdeği paylaşan yalıtılmış bir kullanıcı alanı (user space) örneğidir.
- Sanal makineden farkı, kendi işletim sistemi çekirdeğini çalıştırmamasıdır.
- Başlatma süresi milisaniyeler mertebesindedir; sanal makinede bu süre saniyelerle ölçülür.
- Bellek ayak izi çok küçüktür çünkü çekirdek, sürücüler ve önbellek paylaşılır.

<!-- slayt -->

# Linux Namespace

- Namespace, bir sürecin sistemin hangi bölümünü görebileceğini kısıtlayan çekirdek mekanizmasıdır.
- PID namespace: konteyner içindeki ilk süreç kendini PID 1 olarak görür, dışarıdaki süreçleri göremez.
- Mount namespace: konteynerin kendi dosya sistemi görünümü olur.
- Network namespace: kendi ağ arayüzleri, IP adresi ve yönlendirme tablosu.
- UTS, IPC ve user namespace'leri sırasıyla makine adını, süreçler arası iletişim nesnelerini ve kullanıcı kimliği eşlemesini yalıtır.

<!-- slayt -->

# Linux cgroups

- Control groups, bir süreç kümesinin tüketebileceği kaynağı ölçer ve sınırlar.
- Sınırlanabilen kaynaklar: CPU payı, bellek, blok aygıt bant genişliği, PID sayısı.
- Namespace görünürlüğü kısıtlar, cgroup ise miktarı kısıtlar; ikisi farklı sorunları çözer ve birlikte kullanılır.
- Bellek sınırını aşan bir konteyner, ana makineyi etkilemek yerine kendi içinde OOM killer tarafından sonlandırılır.

<!-- slayt -->

# Konteyner İmajı ve Katmanlar

- İmaj, salt okunur katmanların üst üste bindirilmesiyle oluşur; her katman bir önceki üzerindeki değişikliği tutar.
- Çalışan konteynere yalnız en üstte ince bir yazılabilir katman eklenir.
- Yazma sırasında dosya alt katmandan üst katmana kopyalanır; bu davranışa copy-on-write denir.
- Aynı taban katmanı paylaşan yüz konteyner diskte tek kopya tutar; imajların küçük görünmesinin sebebi budur.

<!-- slayt -->

# Konteyner ile Sanal Makine Karşılaştırması

| Ölçüt | Sanal makine | Konteyner |
|---|---|---|
| Çekirdek | Her VM kendi çekirdeği | Ana makine çekirdeği paylaşılır |
| Başlatma | Saniyeler | Milisaniyeler |
| Yalıtım | Donanım seviyesinde, güçlü | Çekirdek seviyesinde, daha zayıf |
| Farklı işletim sistemi | Çalıştırılabilir | Çalıştırılamaz |
| Bellek maliyeti | Yüzlerce MB | Onlarca MB |

<!-- slayt -->

# Yalıtım Neden Daha Zayıf?

- Tüm konteynerler aynı çekirdeği kullanır; çekirdekteki bir açık tüm konteynerleri etkiler.
- Konteynerden çekirdeğe kaçış (container escape) açıkları, sanal makine kaçışlarından daha sık görülür.
- Ayrıcalıklı (privileged) modda çalıştırılan bir konteyner yalıtımın büyük kısmını devre dışı bırakır.
- Seccomp, AppArmor ve SELinux profilleri konteynerin yapabileceği sistem çağrılarını daraltarak bu riski azaltır.

<!-- slayt -->

# Güvenli Konteyner Yapılandırması

- Konteyneri root olmayan bir kullanıcıyla çalıştırın; imajda bir kullanıcı tanımlayın.
- Kök dosya sistemini salt okunur bağlayın, yazma gereken yerler için ayrı birim tanımlayın.
- Gereksiz Linux capability'lerini düşürün; varsayılan küme çoğu uygulama için fazla geniştir.
- Ana makine dizinlerini konteynere bağlarken en dar yolu seçin; Docker soketini konteynere bağlamak, ana makinede root yetkisi vermekle eşdeğerdir.

<!-- slayt -->

# Mikro Sanal Makineler

- Konteynerin hızını ve sanal makinenin yalıtımını birleştirmeyi hedefleyen ara çözümdür.
- Firecracker ve Kata Containers bu yaklaşımın örnekleridir.
- Aygıt modeli bilinçli olarak küçültülür; yalnız birkaç sanal aygıt sunulur ve saldırı yüzeyi daralır.
- Başlatma süresi yüz milisaniyenin altına iner; çok kiracılı (multi-tenant) sunucusuz platformlarda kullanılır.

<!-- slayt -->

# Sanallaştırmanın Maliyeti

- CPU üzerinde donanım desteğiyle ek yük genelde yüzde birkaçtır.
- Asıl maliyet giriş/çıkışta ortaya çıkar: her sanal aygıt erişimi bir çıkış (VM exit) üretebilir.
- Yarı sanallaştırılmış sürücüler (virtio) bu maliyeti düşürmek için tasarlanmıştır.
- Aygıt geçişi (PCI passthrough) bir donanımı doğrudan konuğa verir; başarım en yüksek olur ama makineler arası taşıma (migration) zorlaşır.

<!-- slayt -->

# Canlı Göç (Live Migration)

- Çalışan bir sanal makineyi durdurmadan başka bir fiziksel sunucuya taşımaktır.
- Ön kopyalama (pre-copy) yönteminde bellek sayfaları çalışırken kopyalanır, değişen sayfalar tekrar gönderilir.
- Kalan sayfa sayısı yeterince azaldığında makine kısa süre durdurulur ve son sayfalarla birlikte devredilir.
- Durma süresi tipik olarak yüz milisaniyenin altındadır; bakım için sunucu boşaltmayı mümkün kılar.

<!-- slayt -->

# Özet

- Sanallaştırma donanımı, konteynerleştirme ise işletim sistemini bölerek yalıtım sağlar.
- Hipervizör konuk çekirdeğin ayrıcalıklı komutlarını yakalar; donanım desteği bu yakalamayı ucuzlatır.
- Konteynerin yalıtımı namespace ve cgroups mekanizmalarına dayanır ve çekirdek paylaşıldığı için daha zayıftır.
- Doğru seçim iş yüküne bağlıdır: farklı işletim sistemi ve güçlü yalıtım gerekiyorsa sanal makine, yoğunluk ve hız gerekiyorsa konteyner.
