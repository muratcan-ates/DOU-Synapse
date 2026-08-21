---
title: "Disk Zamanlama, SSD ve RAID"
subtitle: "İşletim Sistemleri — Konu 9"
format: pdf
---

# 1. Manyetik Diskin Yapısı ve Erişim Maliyeti

Bir sabit disk (HDD), üst üste duran dönen plakalardan (platter) oluşur. Her plaka
yüzeyinde eşmerkezli **izler (track)** vardır; izler **sektörlere** bölünür. Aynı
yarıçaptaki izlerin tümüne birden **silindir (cylinder)** denir. Okuma/yazma kafaları
tek bir kol üzerinde birlikte hareket eder — yani bir kafa bir ize konumlandığında
diğerleri de aynı silindirdedir.

Bir disk isteğinin süresi üç bileşenden oluşur:

```
erisim_suresi = arama_suresi + donme_gecikmesi + aktarim_suresi
```

- **Arama süresi (seek time):** kolun doğru silindire gitmesi. Mekanik olduğu için en
  pahalı bileşendir; tipik olarak 3-10 ms.
- **Dönme gecikmesi (rotational latency):** istenen sektörün kafanın altına gelmesi.
  Ortalama olarak yarım turdur; 7200 rpm bir diskte ~4,2 ms.
- **Aktarım süresi:** verinin okunması. Blok başına mikrosaniyeler mertebesindedir.

Sonuç belirleyicidir: **süre neredeyse tamamen konumlanmadan gelir, veri miktarından
değil.** Bu yüzden disk zamanlamanın tek hedefi toplam kol hareketini azaltmaktır ve
ardışık (sequential) erişim rastgele erişimden kat kat hızlıdır.

<!-- sayfa -->

# 2. Disk Zamanlama Algoritmaları

Aşağıdaki örneklerde kuyruk `98, 183, 37, 122, 14, 124, 65, 67`, kafa başlangıçta
`53` numaralı silindirdedir ve disk `0-199` silindirlerinden oluşur.

## 2.1. FCFS

İstekler geliş sırasıyla işlenir. Adildir ve açlığa (starvation) yol açmaz, ama kol
kuyruk sırası neyse öyle savrulur. Örnekte toplam kol hareketi **640 silindirdir.**

## 2.2. SSTF

**En kısa arama süresi önce (Shortest Seek Time First)**, kafaya en yakın isteği
seçer. Örnekte toplam hareket **236 silindire** iner.

Sorunu **açlıktır**: kafanın bulunduğu bölgeye sürekli yeni istek gelirse uzaktaki bir
istek süresiz beklenebilir. SSTF ayrıca optimal değildir; en yakını seçmek yerel bir
karardır, tüm kuyruk için en iyi sırayı vermez.

## 2.3. SCAN ve C-SCAN

**SCAN (asansör algoritması)**, kafayı bir uçtan diğerine süpürür ve yol üstündeki
istekleri karşılar; uca varınca yön değiştirir. Açlık yoktur, çünkü her isteğin en
fazla bir süpürme sonra karşılanacağı garantidir.

SCAN'in adaletsizliği şudur: kafa bir uca yeni varmışken o uçtaki bölge iki kez üst
üste hizmet alırken, orta bölge bekler. **C-SCAN (dairesel SCAN)** bunu düzeltir: kafa
uca vardığında istekleri karşılamadan başa döner ve hep aynı yönde süpürür. Böylece
bekleme süresi çok daha düzgün dağılır.

## 2.4. LOOK ve C-LOOK

SCAN ve C-SCAN kafayı diskin fiziksel ucuna kadar götürür; o yönde bekleyen istek
yoksa bu boşa harekettir. **LOOK** ve **C-LOOK** yalnız o yöndeki **son isteğe** kadar
gider ve döner. Pratikte uygulanan biçim bunlardır.

## 2.5. Hangisi Seçilir

Yük hafifse kuyruk çoğu zaman tek elemanlıdır ve algoritmaların hepsi aynı davranır.
Fark ağır yükte ortaya çıkar. Ardışık erişimin baskın olduğu iş yüklerinde FCFS bile
iyi çalışır; rastgele erişimde C-LOOK yaygın varsayılandır.

<!-- sayfa -->

# 3. Katı Hal Diskleri (SSD)

SSD'de hareketli parça yoktur; veri NAND flash hücrelerinde tutulur. Arama süresi ve
dönme gecikmesi ortadan kalkar, dolayısıyla **disk zamanlama algoritmalarının varlık
sebebi de ortadan kalkar.** Rastgele okuma ile ardışık okuma arasındaki uçurum kapanır.

Ama flash'ın kendi kısıtları vardır:

- **Okuma ve yazma sayfa (page) birimindedir; silme ise blok (block) birimindedir.**
  Bir sayfa üzerine doğrudan yazılamaz; önce içinde bulunduğu koca bloğun silinmesi
  gerekir.
- **Hücreler sınırlı sayıda silme çevrimine dayanır.** Aynı bloğa sürekli yazmak onu
  erkenden bitirir.

Bu iki kısıt **FTL (Flash Translation Layer)** katmanını doğurur. FTL, mantıksal blok
adreslerini fiziksel sayfalara eşler ve eşlemeyi sürekli değiştirir:

- **Yerinde güncelleme yoktur:** güncellenen veri boş bir sayfaya yazılır, eski sayfa
  "geçersiz" işaretlenir, eşleme tablosu yeni yeri gösterir.
- **Aşınma dengeleme (wear leveling):** yazmalar bloklara eşit dağıtılır.
- **Çöp toplama (garbage collection):** geçersiz sayfalarla dolmuş bloklar, geçerli
  sayfaları başka yere taşınarak boşaltılır ve silinir.

Çöp toplamanın yan etkisi **yazma büyütmesidir (write amplification)**: uygulamanın
yazdığı 1 baytın karşılığında flash'a birden fazla bayt yazılır. `TRIM` komutu, dosya
sistemi tarafından silinen blokları SSD'ye bildirerek FTL'nin gereksiz veriyi
taşımasını önler.

<!-- sayfa -->

# 4. RAID: Çoklu Diskle Başarım ve Dayanıklılık

**RAID (Redundant Array of Independent Disks)**, birden çok fiziksel diski tek bir
mantıksal birim gibi kullanır. İki ayrı amacı vardır ve bunlar karıştırılmamalıdır:
**başarım** ve **hata dayanıklılığı**.

| Seviye | Yöntem | Dayanıklılık | Kullanılabilir alan |
|---|---|---|---|
| RAID 0 | Şeritleme (striping) | **Yok** — bir disk giderse hepsi gider | n disk |
| RAID 1 | Aynalama (mirroring) | 1 disk kaybına dayanır | n/2 disk |
| RAID 5 | Şeritleme + dağıtık eşlik | 1 disk kaybına dayanır | n-1 disk |
| RAID 6 | Şeritleme + çift eşlik | 2 disk kaybına dayanır | n-2 disk |
| RAID 10 | Aynaların şeritlenmesi | Her aynadan 1 disk | n/2 disk |

**RAID 0 bir yedekleme değildir**, tam tersidir: diskler arasında veriyi böler ve tek
bir diskin arızası tüm veriyi kaybettirir. Arıza olasılığı disk sayısıyla artar.

**RAID 5'te eşlik (parity)**, şeritteki blokların bitsel XOR'udur ve tek bir diskte
toplanmaz, disklere dağıtılır. Kaybolan bir blok, kalan bloklarla eşliğin XOR'undan
geri hesaplanır. Bedeli **küçük yazma cezasıdır (small write penalty)**: tek bir bloğu
güncellemek eski veriyi ve eski eşliği okumayı, ikisini de yeniden yazmayı gerektirir —
yani bir mantıksal yazma dört fiziksel işleme dönüşür.

RAID 6, yeniden yapılandırma (rebuild) sırasında ikinci bir diskin arızalanma riskine
karşı geliştirilmiştir; büyük disklerde rebuild saatler sürdüğü için bu risk gerçektir.

**Hiçbir RAID seviyesi yedeklemenin yerine geçmez.** RAID disk arızasına karşı korur;
yanlışlıkla silinen dosyaya, fidye yazılımına ya da dosya sistemi bozulmasına karşı
korumaz — çünkü bu hataları da sadakatle tüm disklere yazar.
