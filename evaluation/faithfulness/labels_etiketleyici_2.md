# Faithfulness etiketleme — 2. etiketleyici

Örneklem: `sample_2026-08-09.json` · n=25 · tohum 20260809

**Bu dosyayı doldururken diğer etiketleyicinin dosyasına BAKMAYIN.** Ham uyum
oranı, tartışma öncesi etiketlerden hesaplanır; sonrasından hesaplanan uyum
her zaman %100 çıkar ve hiçbir şey ölçmez.

Etiket üç değerlidir, ara değer üretilmez: `destekleniyor` · `kısmen` ·
`desteklenmiyor`. Etiket, cevabın ikna ediciliğine değil **kaynak parçanın
içeriğine** bakılarak verilir.

> **UYARI — bu örneklem SAHTE SAĞLAYICIYLA çekildi.** Cevaplar modelin
> ürettiği metin değil, getirilen chunk'ların özetidir. Bu dosyayı
> doldurmak süreci sınar ama **faithfulness ölçmez**; sonuç rapora
> giremez. Gerçek anahtar geldiğinde örneklem yeniden çekilmelidir.

---

## 1. H-006 (direct)

**Soru:** İyi bir CPU zamanlama algoritmasının dengelediği hedefler nelerdir?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: CPU Zamanlama Algoritmaları İşletim Sistemleri — Konu 2 1. Zamanlamanın Amacı CPU zamanlayıcısı (scheduler), ready durumundaki süreçler/thread’ler arasından bir sonraki hangisinin… Konunun devamı 02-cpu-scheduling.pdf, Sayfa 2 bölümünde.

**Gösterilen kaynaklar:**

- `02-cpu-scheduling.pdf` — Sayfa 1
  > CPU Zamanlama Algoritmaları İşletim Sistemleri — Konu 2 1. Zamanlamanın Amacı CPU zamanlayıcısı (scheduler), ready durumundaki süreçler/thread’ler arasından bir sonraki hangisinin CPU’yu kullanacağına karar verir. İyi bir zamanlama algorit…
- `02-cpu-scheduling.pdf` — Sayfa 2
  > doğruysa). • Non-preemptive SJF: Bir süreç başladıktan sonra, daha kısa bir süreç gelse bile yarıda kesilmez. • Preemptive SJF (Shortest Remaining Time First, SRTF): Yeni gelen sürecin kalan süresi, çalışmakta olanınkinden kısaysa çalışan…
- `09-disk-and-storage.pdf` — Sayfa 2
  > 2. Disk Zamanlama Algoritmaları Aşağıdaki örneklerde kuyruk 98, 183, 37, 122, 14, 124, 65, 67, kafa başlangıçta 53 numaralı silindirdedir ve disk 0­199 silindirlerinden oluşur. 2.1. FCFS İstekler geliş sırasıyla işlenir. Adildir ve açlığa…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 2. H-024 (multi_chunk)

**Soru:** fork() ile miras alınan dosya tanımlayıcısı fork_example.c dosyasında nasıl doğru yönetiliyor?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: /* * fork_example.c — Süreç yaratma, wait() ve dosya tanımlayıcısı yönetimi örneği. * * Bu dosya DOĞRU bir örnektir (code_trace soru tipi için, T002): fork() ile bir çocuk * süreç… Konunun devamı fork_example.c, main (satır 18-54) bölümünde.

**Gösterilen kaynaklar:**

- `fork_example.c` — satır 1-17
  > /* * fork_example.c — Süreç yaratma, wait() ve dosya tanımlayıcısı yönetimi örneği. * * Bu dosya DOĞRU bir örnektir (code_trace soru tipi için, T002): fork() ile bir çocuk * süreç yaratılır, ebeveyn wait() ile çocuğun bitmesini bekler ve p…
- `fork_example.c` — main (satır 18-54)
  > int main(void) { int fd = open("ornek.txt", O_CREAT | O_WRONLY | O_TRUNC, 0644); if (fd == -1) { perror("open"); return 1; } pid_t pid = fork(); if (pid < 0) { perror("fork"); close(fd); return 1; } if (pid == 0) { /* Çocuk süreç: fd, fork…
- `01-processes.pdf` — Sayfa 2
  > paylaşır; ama her thread’in kendine ait bir yığın (stack), program sayacı ve yazmaç kümesi vardır. Özellik Süreç Thread Adres uzayı Kendine özel Süreç içindeki diğer thread’lerle paylaşılır Oluşturma maliyeti Yüksek (yeni adres uzayı, sayf…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 3. H-125 (direct)

**Soru:** Şifre özetlerinde tuz (salt) kullanmanın amacı nedir?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: 4. Kimlik Doğrulama ve Sistem Sertleştirme 4.1. Şifrelerin Saklanması Şifreler düz metin olarak saklanmaz ve şifrelenerek de saklanmaz — şifreleme geri döndürülebilir olduğu için… Konunun devamı 09-disk-and-storage.pdf, Sayfa 4 bölümünde.

**Gösterilen kaynaklar:**

- `10-security-and-protection.pdf` — Sayfa 4
  > 4. Kimlik Doğrulama ve Sistem Sertleştirme 4.1. Şifrelerin Saklanması Şifreler düz metin olarak saklanmaz ve şifrelenerek de saklanmaz — şifreleme geri döndürülebilir olduğu için anahtarı ele geçiren herkes tüm şifreleri okur. Doğrusu tek…
- `09-disk-and-storage.pdf` — Sayfa 4
  > 4. RAID: Çoklu Diskle Başarım ve Dayanıklılık RAID (Redundant Array of Independent Disks), birden çok fiziksel diski tek bir mantıksal birim gibi kullanır. İki ayrı amacı vardır ve bunlar karıştırılmamalıdır: başarım ve hata dayanıklılığı.…
- `07-virtual-memory.pdf` — Sayfa 1
  > Sanal Bellek: Talep Üzerine Sayfalama ve Sayfa Değiştirme İşletim Sistemleri — Konu 7 1. Sanal Belleğin Amacı Sanal bellek (virtual memory), bir sürecin kullandığı adres uzayını fiziksel bellekten (RAM) ayıran soyutlamadır. Süreç 0'dan baş…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 4. H-113 (direct)

**Soru:** Bir disk isteğinin süresini belirleyen üç bileşen nedir?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: Disk Zamanlama, SSD ve RAID İşletim Sistemleri — Konu 9 1. Manyetik Diskin Yapısı ve Erişim Maliyeti Bir sabit disk (HDD), üst üste duran dönen plakalardan (platter) oluşur. Konunun devamı 08-io-systems.pdf, Sayfa 4 bölümünde.

**Gösterilen kaynaklar:**

- `09-disk-and-storage.pdf` — Sayfa 1
  > Disk Zamanlama, SSD ve RAID İşletim Sistemleri — Konu 9 1. Manyetik Diskin Yapısı ve Erişim Maliyeti Bir sabit disk (HDD), üst üste duran dönen plakalardan (platter) oluşur. Her plaka yüzeyinde eşmerkezli izler (track) vardır; izler sektör…
- `08-io-systems.pdf` — Sayfa 4
  > 4. Hata, Koruma ve Başarım 4.1. Hataların Ele Alınışı G/Ç, çekirdekte hatanın en sık görüldüğü yerdir: kablo çıkar, disk bloğu bozulur, ağ paketi düşer. Çekirdek geçici (transient) hataları genelde yeniden deneyerek çözer; kalıcı hataları…
- `09-disk-and-storage.pdf` — Sayfa 2
  > 2. Disk Zamanlama Algoritmaları Aşağıdaki örneklerde kuyruk 98, 183, 37, 122, 14, 124, 65, 67, kafa başlangıçta 53 numaralı silindirdedir ve disk 0­199 silindirlerinden oluşur. 2.1. FCFS İstekler geliş sırasıyla işlenir. Adildir ve açlığa…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 5. H-105 (direct)

**Soru:** Optimal sayfa değiştirme algoritması neden pratikte uygulanamaz?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: 3. Sayfa Değiştirme Algoritmaları Boş çerçeve kalmadığında hangi sayfanın çıkarılacağına sayfa değiştirme algoritması karar verir. Konunun devamı 03-memory-management.pdf, Sayfa 2 bölümünde.

**Gösterilen kaynaklar:**

- `07-virtual-memory.pdf` — Sayfa 3
  > 3. Sayfa Değiştirme Algoritmaları Boş çerçeve kalmadığında hangi sayfanın çıkarılacağına sayfa değiştirme algoritması karar verir. Algoritmalar aynı referans dizisi (reference string) üzerinde karşılaştırılır; ölçüt üretilen sayfa hatası s…
- `03-memory-management.pdf` — Sayfa 2
  > pratikte iyi performans gösterir ama tam LRU takibi donanım maliyetlidir, çoğu sistem yaklaşık (approximate) LRU kullanır (ör. “second chance”/clock algorit- ması). • Optimal (Belady’s algorithm): Gelecekte en uzun süre kullanılmayacak say…
- `03-memory-management.pdf` — Sayfa 2
  > • TLB hit: Çeviri TLB’de bulunur, fiziksel adres doğrudan alınır — tek CPU çevrimi mertebesinde hızlıdır. • TLB miss: Çeviri TLB’de yok; sayfa tablosuna gidilir (yavaş), bulunan çeviri TLB’ye eklenir. TLB ve context switch ilişkisi: TLB gi…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 6. H-120 (direct)

**Soru:** Kullanıcı modu ile çekirdek modu ayrımı neden yazılımla değil donanımla zorlanır?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: Koruma ve Güvenlik: Ayrıcalık, Erişim Denetimi ve Bellek Saldırıları İşletim Sistemleri — Konu 10 1. Konunun devamı 08-io-systems.pdf, Sayfa 3 bölümünde.

**Gösterilen kaynaklar:**

- `10-security-and-protection.pdf` — Sayfa 1
  > Koruma ve Güvenlik: Ayrıcalık, Erişim Denetimi ve Bellek Saldırıları İşletim Sistemleri — Konu 10 1. Koruma ile Güvenlik Aynı Şey Değil İki terim günlük dilde karışır, ders bağlamında ayrıdır: • Koruma (protection) iç bir mekanizmadır: sis…
- `08-io-systems.pdf` — Sayfa 3
  > 3. Çekirdek İçindeki G/Ç Katmanları Çekirdek G/Ç'yi katmanlı bir yapıyla ele alır; her katman altındakinin ayrıntısını gizler: 1. Kullanıcı seviyesi kütüphaneler: tamponlanmış fread/fwrite gibi çağrılar. 2. Aygıttan bağımsız çekirdek katma…
- `15-boot-and-kernel.pptx` — Slayt 19
  > Özet Açılış zinciri ürün yazılımından önyükleyiciye, oradan çekirdeğe ve PID 1'e uzanır; her halka bir sonrakini yükler. initramfs, kök dosya sistemini okumak için gereken sürücülerin yumurta-tavuk problemini çözer. Sistem çağrısı, kullanı…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 7. H-019 (direct)

**Soru:** Kaynak ayırma grafiğinde döngü bulunması ne zaman deadlock için yeterli koşuldur?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: 4. Banker’s Algorithm (Kaçınma) Banker’s Algorithm, her kaynak isteğini yalnızca sistemin güvenli durumda (safe state) kalmasını garanti ediyorsa onaylayan bir kaçınma… Konunun devamı 05-deadlock-demo.pdf, Sayfa 1 bölümünde.

**Gösterilen kaynaklar:**

- `05-deadlock-demo.pdf` — Sayfa 2
  > 4. Banker’s Algorithm (Kaçınma) Banker’s Algorithm, her kaynak isteğini yalnızca sistemin güvenli durumda (safe state) kalmasını garanti ediyorsa onaylayan bir kaçınma algoritmasıdır. Bir durum güvenlidir, eğer tüm süreçlerin, mevcut kayna…
- `05-deadlock-demo.pdf` — Sayfa 1
  > • Tespit ve kurtarma (detection & recovery): Deadlock’un oluşmasına izin verip periyodik olarak kaynak ayırma grafiğinde döngü arayarak tespit etmek; bulunca bir süreci sonlandırıp veya kaynağını geri alıp kurtarmak. • Görmezden gelme (ost…
- `05-deadlock-demo.pdf` — Sayfa 1
  > Deadlock: Dört Koşul ve Banker’s Algorithm İşletim Sistemleri — Konu 5 (Canlı Demo Materyali) 1. Deadlock Nedir? Deadlock (kilitlenme), iki veya daha fazla sürecin, birbirlerinin elinde tuttuğu ve asla serbest bırakmayacağı kaynakları bekl…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 8. H-108 (direct)

**Soru:** DMA aktarımı sırasında CPU önbelleğinde neden tutarsızlık oluşabilir?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: 2. Üç Aktarım Yöntemi 2.1. Yoklama (Polling) CPU, durum yazmacını bir döngü içinde tekrar tekrar okur ve "meşgul" biti düşene kadar bekler. Konunun devamı 08-io-systems.pdf, Sayfa 4 bölümünde.

**Gösterilen kaynaklar:**

- `08-io-systems.pdf` — Sayfa 2
  > 2. Üç Aktarım Yöntemi 2.1. Yoklama (Polling) CPU, durum yazmacını bir döngü içinde tekrar tekrar okur ve "meşgul" biti düşene kadar bekler. Kodu en basit olan yöntemdir ve gecikmesi çok düşüktür — aygıt hazır olduğu an CPU zaten bakıyordur…
- `08-io-systems.pdf` — Sayfa 4
  > 4. Hata, Koruma ve Başarım 4.1. Hataların Ele Alınışı G/Ç, çekirdekte hatanın en sık görüldüğü yerdir: kablo çıkar, disk bloğu bozulur, ağ paketi düşer. Çekirdek geçici (transient) hataları genelde yeniden deneyerek çözer; kalıcı hataları…
- `01-processes.pdf` — Sayfa 3
  > 4. Context Switch Bir CPU çekirdeği aynı anda yalnız bir thread çalıştırabilir. Zamanlayıcı (scheduler) çalışan thread’i değiştirmeye karar verdiğinde bir context switch gerçekleşir: 1. Çalışmakta olan thread’in yazmaçları, program sayacı…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 9. H-009 (direct)

**Soru:** Preemptive SJF (SRTF) ile non-preemptive SJF arasındaki fark nedir?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: doğruysa). • Non-preemptive SJF: Bir süreç başladıktan sonra, daha kısa bir süreç gelse bile yarıda kesilmez. Konunun devamı 02-cpu-scheduling.pdf, Sayfa 2 bölümünde.

**Gösterilen kaynaklar:**

- `02-cpu-scheduling.pdf` — Sayfa 2
  > doğruysa). • Non-preemptive SJF: Bir süreç başladıktan sonra, daha kısa bir süreç gelse bile yarıda kesilmez. • Preemptive SJF (Shortest Remaining Time First, SRTF): Yeni gelen sürecin kalan süresi, çalışmakta olanınkinden kısaysa çalışan…
- `02-cpu-scheduling.pdf` — Sayfa 2
  > Bu yüzden üretim zamanlayıcıları (ör. Linux’un eski O(1) zamanlayıcısı ve sonraki Completely Fair Scheduler’ın kırmızı-siyah ağacı) sıralı veri yapıları kullanır. 6. Karşılaştırma Tablosu Algoritma Preemptive? Açlık riski Tipik kullanım FC…
- `02-cpu-scheduling.pdf` — Sayfa 3
  > 7. Özet • Zamanlama, CPU kullanımı, verim, dönüş süresi, bekleme süresi ve yanıt süresi arasında ödünleşim yapar. • Round-robin’de quantum seçimi context switch maliyeti ile yanıt süresi arasında bir ödünleşimdir; çok küçük quantum sistemi…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 10. H-149 (multi_chunk)

**Soru:** İki fazlı commit ile konsensüs algoritmaları arasındaki temel fark nedir?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: İki Fazlı Commit Birden çok düğümde atomik bir işlem yapmayı hedefler: ya hepsi uygular ya hiçbiri. Konunun devamı 14-distributed-os.pptx, Slayt 11 bölümünde.

**Gösterilen kaynaklar:**

- `14-distributed-os.pptx` — Slayt 10
  > İki Fazlı Commit Birden çok düğümde atomik bir işlem yapmayı hedefler: ya hepsi uygular ya hiçbiri. Birinci faz: koordinatör tüm katılımcılara hazır mısın diye sorar, her biri hazır ya da iptal yanıtı verir. İkinci faz: tüm yanıtlar hazır…
- `14-distributed-os.pptx` — Slayt 11
  > İki Fazlı Commit'in Zayıflığı Koordinatör, katılımcılar hazır dedikten sonra çökerse katılımcılar süresiz bekler; kaynaklar kilitli kalır. Bu duruma engelleyici (blocking) protokol denir ve 2PC'nin bilinen temel kusurudur. Üç fazlı commit…
- `14-distributed-os.pptx` — Slayt 18
  > Özet Dağıtık sistemin iki eksiği paylaşılan bellek ve paylaşılan saattir; tüm karmaşıklık buradan doğar. Mantıksal saatler sıralama sorununu, konsensüs algoritmaları anlaşma sorununu çözer. 2PC atomikliği sağlar ama koordinatör arızasında…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 11. H-030 (multi_chunk)

**Soru:** Zamanlayıcı hangi veri yapısını kullanır ve bu seçimin toplam karmaşıklığa etkisi nedir?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: doğruysa). • Non-preemptive SJF: Bir süreç başladıktan sonra, daha kısa bir süreç gelse bile yarıda kesilmez. Konunun devamı 02-cpu-scheduling.pdf, Sayfa 2 bölümünde.

**Gösterilen kaynaklar:**

- `02-cpu-scheduling.pdf` — Sayfa 2
  > doğruysa). • Non-preemptive SJF: Bir süreç başladıktan sonra, daha kısa bir süreç gelse bile yarıda kesilmez. • Preemptive SJF (Shortest Remaining Time First, SRTF): Yeni gelen sürecin kalan süresi, çalışmakta olanınkinden kısaysa çalışan…
- `02-cpu-scheduling.pdf` — Sayfa 2
  > Bu yüzden üretim zamanlayıcıları (ör. Linux’un eski O(1) zamanlayıcısı ve sonraki Completely Fair Scheduler’ın kırmızı-siyah ağacı) sıralı veri yapıları kullanır. 6. Karşılaştırma Tablosu Algoritma Preemptive? Açlık riski Tipik kullanım FC…
- `01-processes.pdf` — Sayfa 3
  > 4. Context Switch Bir CPU çekirdeği aynı anda yalnız bir thread çalıştırabilir. Zamanlayıcı (scheduler) çalışan thread’i değiştirmeye karar verdiğinde bir context switch gerçekleşir: 1. Çalışmakta olan thread’in yazmaçları, program sayacı…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 12. H-124 (direct)

**Soru:** Şifreler neden şifrelenerek değil özetlenerek saklanır?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: 4. Kimlik Doğrulama ve Sistem Sertleştirme 4.1. Şifrelerin Saklanması Şifreler düz metin olarak saklanmaz ve şifrelenerek de saklanmaz — şifreleme geri döndürülebilir olduğu için… Konunun devamı 10-security-and-protection.pdf, Sayfa 2 bölümünde.

**Gösterilen kaynaklar:**

- `10-security-and-protection.pdf` — Sayfa 4
  > 4. Kimlik Doğrulama ve Sistem Sertleştirme 4.1. Şifrelerin Saklanması Şifreler düz metin olarak saklanmaz ve şifrelenerek de saklanmaz — şifreleme geri döndürülebilir olduğu için anahtarı ele geçiren herkes tüm şifreleri okur. Doğrusu tek…
- `10-security-and-protection.pdf` — Sayfa 2
  > 2. Erişim Denetimi Modelleri Erişim yetkilerinin tamamı kavramsal olarak bir erişim matrisidir: satırlar alanlar (domain / kullanıcı), sütunlar nesneler (dosya, aygıt), hücreler izinler. Matris pratikte seyrektir ve bütün hâlinde saklanmaz…
- `10-security-and-protection.pdf` — Sayfa 1
  > Koruma ve Güvenlik: Ayrıcalık, Erişim Denetimi ve Bellek Saldırıları İşletim Sistemleri — Konu 10 1. Koruma ile Güvenlik Aynı Şey Değil İki terim günlük dilde karışır, ders bağlamında ayrıdır: • Koruma (protection) iç bir mekanizmadır: sis…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 13. H-011 (direct)

**Soru:** Sanal bellek hangi iki temel faydayı sağlar?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: Bellek Sanallaştırma İki kat çeviri vardır: konuk sanal adresi, konuk fiziksel adresi ve ana makine fiziksel adresi. Konunun devamı 07-virtual-memory.pdf, Sayfa 1 bölümünde.

**Gösterilen kaynaklar:**

- `11-virtualization-containers.pptx` — Slayt 8
  > Bellek Sanallaştırma İki kat çeviri vardır: konuk sanal adresi, konuk fiziksel adresi ve ana makine fiziksel adresi. Gölge sayfa tabloları (shadow page tables) bu iki katı yazılımla tek bir tabloda birleştirir; güncelleme maliyeti yüksekti…
- `07-virtual-memory.pdf` — Sayfa 1
  > Sanal Bellek: Talep Üzerine Sayfalama ve Sayfa Değiştirme İşletim Sistemleri — Konu 7 1. Sanal Belleğin Amacı Sanal bellek (virtual memory), bir sürecin kullandığı adres uzayını fiziksel bellekten (RAM) ayıran soyutlamadır. Süreç 0'dan baş…
- `03-memory-management.pdf` — Sayfa 1
  > Bellek Yönetimi: Sayfalama ve TLB İşletim Sistemleri — Konu 3 1. Sanal Bellek ve Adres Çevirisi Modern işletim sistemleri her sürece kendi sanal adres uzayını verir; süreç gerçekte hangi fiziksel bellek adresinde çalıştığını bilmez. Sanal…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 14. H-106 (direct)

**Soru:** Thrashing sırasında çok programlılık derecesini artırmak neden durumu kötüleştirir?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: 4. Çerçeve Tahsisi ve Thrashing 4.1. Kaç Çerçeve Verilmeli Çerçeveler süreçler arasında eşit (equal) ya da adres uzayı boyutuyla orantılı (proportional) dağıtılabilir. Konunun devamı 07-virtual-memory.pdf, Sayfa 4 bölümünde.

**Gösterilen kaynaklar:**

- `07-virtual-memory.pdf` — Sayfa 4
  > 4. Çerçeve Tahsisi ve Thrashing 4.1. Kaç Çerçeve Verilmeli Çerçeveler süreçler arasında eşit (equal) ya da adres uzayı boyutuyla orantılı (proportional) dağıtılabilir. Orantılı dağıtım genelde daha iyidir, ama tek başına yetmez: bir süreci…
- `07-virtual-memory.pdf` — Sayfa 4
  > Model şunu söyler: bir süreç çalışma kümesi bellekte tutulduğu sürece az sayfa hatası üretir. Toplam talep D = Σ WSS(i) mevcut çerçeve sayısını aşarsa thrashing kaçınılmazdır. İşletim sistemi D'yi izleyip aşım gördüğünde bir süreci askıya…
- `08-io-systems.pdf` — Sayfa 2
  > 2. Üç Aktarım Yöntemi 2.1. Yoklama (Polling) CPU, durum yazmacını bir döngü içinde tekrar tekrar okur ve "meşgul" biti düşene kadar bekler. Kodu en basit olan yöntemdir ve gecikmesi çok düşüktür — aygıt hazır olduğu an CPU zaten bakıyordur…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 15. H-117 (direct)

**Soru:** RAID 5'te tek bir bloğu güncellemek neden dört fiziksel işlem gerektirir?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: 4. RAID: Çoklu Diskle Başarım ve Dayanıklılık RAID (Redundant Array of Independent Disks), birden çok fiziksel diski tek bir mantıksal birim gibi kullanır. Konunun devamı 03-memory-management.pdf, Sayfa 2 bölümünde.

**Gösterilen kaynaklar:**

- `09-disk-and-storage.pdf` — Sayfa 4
  > 4. RAID: Çoklu Diskle Başarım ve Dayanıklılık RAID (Redundant Array of Independent Disks), birden çok fiziksel diski tek bir mantıksal birim gibi kullanır. İki ayrı amacı vardır ve bunlar karıştırılmamalıdır: başarım ve hata dayanıklılığı.…
- `03-memory-management.pdf` — Sayfa 2
  > • TLB hit: Çeviri TLB’de bulunur, fiziksel adres doğrudan alınır — tek CPU çevrimi mertebesinde hızlıdır. • TLB miss: Çeviri TLB’de yok; sayfa tablosuna gidilir (yavaş), bulunan çeviri TLB’ye eklenir. TLB ve context switch ilişkisi: TLB gi…
- `08-io-systems.pdf` — Sayfa 4
  > 4. Hata, Koruma ve Başarım 4.1. Hataların Ele Alınışı G/Ç, çekirdekte hatanın en sık görüldüğü yerdir: kablo çıkar, disk bloğu bozulur, ağ paketi düşer. Çekirdek geçici (transient) hataları genelde yeniden deneyerek çözer; kalıcı hataları…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 16. H-015 (direct)

**Soru:** Optimal (Belady) sayfa değiştirme algoritması gerçek bir sistemde neden uygulanamaz?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: 3. Sayfa Değiştirme Algoritmaları Boş çerçeve kalmadığında hangi sayfanın çıkarılacağına sayfa değiştirme algoritması karar verir. Konunun devamı 03-memory-management.pdf, Sayfa 2 bölümünde.

**Gösterilen kaynaklar:**

- `07-virtual-memory.pdf` — Sayfa 3
  > 3. Sayfa Değiştirme Algoritmaları Boş çerçeve kalmadığında hangi sayfanın çıkarılacağına sayfa değiştirme algoritması karar verir. Algoritmalar aynı referans dizisi (reference string) üzerinde karşılaştırılır; ölçüt üretilen sayfa hatası s…
- `03-memory-management.pdf` — Sayfa 2
  > pratikte iyi performans gösterir ama tam LRU takibi donanım maliyetlidir, çoğu sistem yaklaşık (approximate) LRU kullanır (ör. “second chance”/clock algorit- ması). • Optimal (Belady’s algorithm): Gelecekte en uzun süre kullanılmayacak say…
- `03-memory-management.pdf` — Sayfa 2
  > • TLB hit: Çeviri TLB’de bulunur, fiziksel adres doğrudan alınır — tek CPU çevrimi mertebesinde hızlıdır. • TLB miss: Çeviri TLB’de yok; sayfa tablosuna gidilir (yavaş), bulunan çeviri TLB’ye eklenir. TLB ve context switch ilişkisi: TLB gi…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 17. H-020 (direct)

**Soru:** Bitişik (contiguous) dosya tahsisinin avantajı ve dezavantajı nedir?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: Dosya Tahsis Yöntemleri Bitişik tahsis (contiguous): dosya diskte ardışık bloklarda tutulur; hızlı sıralı/rastgele erişim ama harici parçalanma (fragmentation) riski. Konunun devamı 10-security-and-protection.pdf, Sayfa 2 bölümünde.

**Gösterilen kaynaklar:**

- `06-file-systems.pptx` — Slayt 4
  > Dosya Tahsis Yöntemleri Bitişik tahsis (contiguous): dosya diskte ardışık bloklarda tutulur; hızlı sıralı/rastgele erişim ama harici parçalanma (fragmentation) riski. Bağlı liste (linked): her blok bir sonrakinin adresini tutar; parçalanma…
- `10-security-and-protection.pdf` — Sayfa 2
  > 2. Erişim Denetimi Modelleri Erişim yetkilerinin tamamı kavramsal olarak bir erişim matrisidir: satırlar alanlar (domain / kullanıcı), sütunlar nesneler (dosya, aygıt), hücreler izinler. Matris pratikte seyrektir ve bütün hâlinde saklanmaz…
- `08-io-systems.pdf` — Sayfa 4
  > 4. Hata, Koruma ve Başarım 4.1. Hataların Ele Alınışı G/Ç, çekirdekte hatanın en sık görüldüğü yerdir: kablo çıkar, disk bloğu bozulur, ağ paketi düşer. Çekirdek geçici (transient) hataları genelde yeniden deneyerek çözer; kalıcı hataları…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 18. H-026 (multi_chunk)

**Soru:** Deadlock'un dört koşulundan 'karşılıklı dışlama', senkronizasyon konusundaki hangi kavramla aynı şeyi ifade eder?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: Senkronizasyon: Mutex, Semafor, Üretici-Tüketici İşletim Sistemleri — Konu 4 1. Neden Senkronizasyon Gerekir? Aynı sürece ait thread’ler adres uzayını paylaşır (Konu 1). Konunun devamı 05-deadlock-demo.pdf, Sayfa 1 bölümünde.

**Gösterilen kaynaklar:**

- `04-synchronization.pdf` — Sayfa 1
  > Senkronizasyon: Mutex, Semafor, Üretici-Tüketici İşletim Sistemleri — Konu 4 1. Neden Senkronizasyon Gerekir? Aynı sürece ait thread’ler adres uzayını paylaşır (Konu 1). Birden fazla thread aynı paylaşımlı veriyi eşzamanlı okuyup yazarsa b…
- `05-deadlock-demo.pdf` — Sayfa 1
  > Deadlock: Dört Koşul ve Banker’s Algorithm İşletim Sistemleri — Konu 5 (Canlı Demo Materyali) 1. Deadlock Nedir? Deadlock (kilitlenme), iki veya daha fazla sürecin, birbirlerinin elinde tuttuğu ve asla serbest bırakmayacağı kaynakları bekl…
- `05-deadlock-demo.pdf` — Sayfa 2
  > tam tespit için Banker’s Algorithm’e benzer bir azaltma (reduction) prosedürü gerekir. 6. Özet • Deadlock, dört koşulun (karşılıklı dışlama, tut-ve-bekle, önceliksiz alma, dairesel bekleme) aynı anda sağlanmasıyla oluşur; birini kırmak dea…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 19. H-001 (direct)

**Soru:** Bir süreç hangi durumda 'blocked' (waiting) durumuna geçer?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: Süreçler, Thread’ler ve Context Switch İşletim Sistemleri — Konu 1 1. Giriş: Süreç Nedir? Bir süreç (process), çalışmakta olan bir programın işletim sistemi tarafından yönetilen… Konunun devamı bankers_algorithm.c, satır 1-190 bölümünde.

**Gösterilen kaynaklar:**

- `01-processes.pdf` — Sayfa 1
  > Süreçler, Thread’ler ve Context Switch İşletim Sistemleri — Konu 1 1. Giriş: Süreç Nedir? Bir süreç (process), çalışmakta olan bir programın işletim sistemi tarafından yönetilen soyutlamasıdır. Diskteki bir program dosyası pasiftir; işleti…
- `bankers_algorithm.c` — satır 1-190
  > } } } /* * Güvenlik algoritması. * * Sistemin GÜVENLİ olması, tüm süreçlerin tamamlanmasını sağlayan en az bir * sıralamanın var olması demektir. Böyle bir sıralama bulunamazsa durum güvensizdir. * * Güvensiz olmak kilitlenmiş olmakla aynı…
- `04-synchronization.pdf` — Sayfa 1
  > Senkronizasyon: Mutex, Semafor, Üretici-Tüketici İşletim Sistemleri — Konu 4 1. Neden Senkronizasyon Gerekir? Aynı sürece ait thread’ler adres uzayını paylaşır (Konu 1). Birden fazla thread aynı paylaşımlı veriyi eşzamanlı okuyup yazarsa b…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 20. H-114 (direct)

**Soru:** SSTF disk zamanlama algoritmasının bilinen sakıncası nedir?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: 2. Disk Zamanlama Algoritmaları Aşağıdaki örneklerde kuyruk 98, 183, 37, 122, 14, 124, 65, 67, kafa başlangıçta 53 numaralı silindirdedir ve disk 0­199 silindirlerinden oluşur. Konunun devamı 09-disk-and-storage.pdf, Sayfa 3 bölümünde.

**Gösterilen kaynaklar:**

- `09-disk-and-storage.pdf` — Sayfa 2
  > 2. Disk Zamanlama Algoritmaları Aşağıdaki örneklerde kuyruk 98, 183, 37, 122, 14, 124, 65, 67, kafa başlangıçta 53 numaralı silindirdedir ve disk 0­199 silindirlerinden oluşur. 2.1. FCFS İstekler geliş sırasıyla işlenir. Adildir ve açlığa…
- `09-disk-and-storage.pdf` — Sayfa 3
  > 3. Katı Hal Diskleri (SSD) SSD'de hareketli parça yoktur; veri NAND flash hücrelerinde tutulur. Arama süresi ve dönme gecikmesi ortadan kalkar, dolayısıyla disk zamanlama algoritmalarının varlık sebebi de ortadan kalkar. Rastgele okuma ile…
- `02-cpu-scheduling.pdf` — Sayfa 2
  > doğruysa). • Non-preemptive SJF: Bir süreç başladıktan sonra, daha kısa bir süreç gelse bile yarıda kesilmez. • Preemptive SJF (Shortest Remaining Time First, SRTF): Yeni gelen sürecin kalan süresi, çalışmakta olanınkinden kısaysa çalışan…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 21. H-002 (direct)

**Soru:** Süreç oluşturmakla thread oluşturmak arasındaki maliyet farkı neden kaynaklanır?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: Süreçler, Thread’ler ve Context Switch İşletim Sistemleri — Konu 1 1. Giriş: Süreç Nedir? Bir süreç (process), çalışmakta olan bir programın işletim sistemi tarafından yönetilen… Konunun devamı 01-processes.pdf, Sayfa 3 bölümünde.

**Gösterilen kaynaklar:**

- `01-processes.pdf` — Sayfa 1
  > Süreçler, Thread’ler ve Context Switch İşletim Sistemleri — Konu 1 1. Giriş: Süreç Nedir? Bir süreç (process), çalışmakta olan bir programın işletim sistemi tarafından yönetilen soyutlamasıdır. Diskteki bir program dosyası pasiftir; işleti…
- `01-processes.pdf` — Sayfa 3
  > 4. Context Switch Bir CPU çekirdeği aynı anda yalnız bir thread çalıştırabilir. Zamanlayıcı (scheduler) çalışan thread’i değiştirmeye karar verdiğinde bir context switch gerçekleşir: 1. Çalışmakta olan thread’in yazmaçları, program sayacı…
- `01-processes.pdf` — Sayfa 2
  > paylaşır; ama her thread’in kendine ait bir yığın (stack), program sayacı ve yazmaç kümesi vardır. Özellik Süreç Thread Adres uzayı Kendine özel Süreç içindeki diğer thread’lerle paylaşılır Oluşturma maliyeti Yüksek (yeni adres uzayı, sayf…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 22. H-022 (multi_chunk)

**Soru:** Thread'lerin paylaşımlı veriye erişimi neden senkronizasyon gerektirir?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: Senkronizasyon: Mutex, Semafor, Üretici-Tüketici İşletim Sistemleri — Konu 4 1. Neden Senkronizasyon Gerekir? Aynı sürece ait thread’ler adres uzayını paylaşır (Konu 1). Konunun devamı 13-ipc.pptx, Slayt 9 bölümünde.

**Gösterilen kaynaklar:**

- `04-synchronization.pdf` — Sayfa 1
  > Senkronizasyon: Mutex, Semafor, Üretici-Tüketici İşletim Sistemleri — Konu 4 1. Neden Senkronizasyon Gerekir? Aynı sürece ait thread’ler adres uzayını paylaşır (Konu 1). Birden fazla thread aynı paylaşımlı veriyi eşzamanlı okuyup yazarsa b…
- `13-ipc.pptx` — Slayt 9
  > Paylaşımlı Bellekte Senkronizasyon Çekirdek yalnız eşlemeyi kurar; kimin ne zaman yazacağına karışmaz. İki süreç aynı anda yazarsa sonuç tanımsızdır ve hata sessizce oluşur. Çözüm, paylaşımlı bölgenin içine ya da yanına konan bir senkroniz…
- `04-synchronization.pdf` — Sayfa 2
  > • signal() (bazı kaynaklarda V() veya release()): sayacı 1 artırır ve bekleyen bir thread varsa uyandırır. İkili semafor (binary semaphore), mutex’e benzer ama sahiplik zorlaması yok- tur — signal’i başka bir thread çağırabilir; bu da onu…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 23. H-116 (direct)

**Soru:** SSD'de neden yerinde güncelleme yapılamaz?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: 3. Katı Hal Diskleri (SSD) SSD'de hareketli parça yoktur; veri NAND flash hücrelerinde tutulur. Konunun devamı 15-boot-and-kernel.pptx, Slayt 6 bölümünde.

**Gösterilen kaynaklar:**

- `09-disk-and-storage.pdf` — Sayfa 3
  > 3. Katı Hal Diskleri (SSD) SSD'de hareketli parça yoktur; veri NAND flash hücrelerinde tutulur. Arama süresi ve dönme gecikmesi ortadan kalkar, dolayısıyla disk zamanlama algoritmalarının varlık sebebi de ortadan kalkar. Rastgele okuma ile…
- `15-boot-and-kernel.pptx` — Slayt 6
  > initramfs Neden Var? Kök dosya sistemi bir RAID dizisinde ya da şifreli bir birimde olabilir; onu okumak için sürücü gerekir. O sürücü de kök dosya sisteminde durur: yumurta-tavuk problemi. initramfs, belleğe yüklenen geçici küçük bir kök…
- `03-memory-management.pdf` — Sayfa 1
  > Bellek Yönetimi: Sayfalama ve TLB İşletim Sistemleri — Konu 3 1. Sanal Bellek ve Adres Çevirisi Modern işletim sistemleri her sürece kendi sanal adres uzayını verir; süreç gerçekte hangi fiziksel bellek adresinde çalıştığını bilmez. Sanal…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 24. H-122 (direct)

**Soru:** setuid biti bir programı nasıl çalıştırır?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: 2. Erişim Denetimi Modelleri Erişim yetkilerinin tamamı kavramsal olarak bir erişim matrisidir: satırlar alanlar (domain / kullanıcı), sütunlar nesneler (dosya, aygıt), hücreler… Konunun devamı 15-boot-and-kernel.pptx, Slayt 9 bölümünde.

**Gösterilen kaynaklar:**

- `10-security-and-protection.pdf` — Sayfa 2
  > 2. Erişim Denetimi Modelleri Erişim yetkilerinin tamamı kavramsal olarak bir erişim matrisidir: satırlar alanlar (domain / kullanıcı), sütunlar nesneler (dosya, aygıt), hücreler izinler. Matris pratikte seyrektir ve bütün hâlinde saklanmaz…
- `15-boot-and-kernel.pptx` — Slayt 9
  > Sistem Çağrısı Mekanizması Kullanıcı süreci çekirdeğe doğrudan atlayamaz; özel bir komut kullanır. x86-64'te bu komut syscall'dır; eski sistemlerde int 0x80 yazılım kesmesi kullanılırdı. Çağrı numarası bir yazmaca (rax) konur, argümanlar b…
- `01-processes.pdf` — Sayfa 1
  > Süreçler, Thread’ler ve Context Switch İşletim Sistemleri — Konu 1 1. Giriş: Süreç Nedir? Bir süreç (process), çalışmakta olan bir programın işletim sistemi tarafından yönetilen soyutlamasıdır. Diskteki bir program dosyası pasiftir; işleti…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________

## 25. H-112 (direct)

**Soru:** Kesme birleştirme (interrupt coalescing) neyi çözer?

**Durum:** `answered`

**Cevap:**

> Ders materyaline göre: 4. Hata, Koruma ve Başarım 4.1. Hataların Ele Alınışı G/Ç, çekirdekte hatanın en sık görüldüğü yerdir: kablo çıkar, disk bloğu bozulur, ağ paketi düşer. Konunun devamı 08-io-systems.pdf, Sayfa 2 bölümünde.

**Gösterilen kaynaklar:**

- `08-io-systems.pdf` — Sayfa 4
  > 4. Hata, Koruma ve Başarım 4.1. Hataların Ele Alınışı G/Ç, çekirdekte hatanın en sık görüldüğü yerdir: kablo çıkar, disk bloğu bozulur, ağ paketi düşer. Çekirdek geçici (transient) hataları genelde yeniden deneyerek çözer; kalıcı hataları…
- `08-io-systems.pdf` — Sayfa 2
  > 2. Üç Aktarım Yöntemi 2.1. Yoklama (Polling) CPU, durum yazmacını bir döngü içinde tekrar tekrar okur ve "meşgul" biti düşene kadar bekler. Kodu en basit olan yöntemdir ve gecikmesi çok düşüktür — aygıt hazır olduğu an CPU zaten bakıyordur…
- `12-real-time-scheduling.pptx` — Slayt 17
  > Kesmeli Çekirdek İhtiyacı Geleneksel çekirdekler sistem çağrısı işlenirken kesilemez; bu, yüksek öncelikli bir görevin çekirdeğin işini bitirmesini beklemesi demektir. Gerçek zamanlı çekirdekler kesme noktaları (preemption points) ekler ya…

**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________

**Not:** ______________
