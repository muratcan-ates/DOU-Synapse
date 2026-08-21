---
title: "Bellek Yönetimi: Sayfalama ve TLB"
subtitle: "İşletim Sistemleri — Konu 3"
---

# 1. Sanal Bellek ve Adres Çevirisi

Modern işletim sistemleri her sürece kendi **sanal adres uzayını** verir; süreç
gerçekte hangi fiziksel bellek adresinde çalıştığını bilmez. Sanal adresten fiziksel
adrese çeviri, donanımdaki **Bellek Yönetim Birimi (MMU)** tarafından, işletim
sisteminin tuttuğu **sayfa tablosu (page table)** kullanılarak yapılır.

Bu dolaylılık iki temel fayda sağlar:

- **İzolasyon**: Bir süreç başka bir sürecin belleğine kazara (veya kötü niyetle)
  erişemez; her sürecin sayfa tablosu yalnız kendi fiziksel çerçevelerine işaret eder.
- **Sanal belleğin fiziksel bellekten büyük olabilmesi**: Az kullanılan sayfalar diske
  (swap alanına) taşınabilir.

# 2. Sayfalama (Paging)

Sanal adres uzayı sabit boyutlu **sayfalara (page)**, fiziksel bellek de aynı boyutlu
**çerçevelere (frame)** bölünür (tipik boyut 4 KB). Bir sanal adres iki parçaya ayrılır:

```
[ sayfa numarası | sayfa içi ofset ]
```

Sayfa tablosu, sayfa numarasını fiziksel çerçeve numarasına eşler. Her girdi ayrıca
**geçerlilik biti (valid bit)**, **erişim izinleri** (okuma/yazma/çalıştırma) ve
**değiştirilmiş biti (dirty bit)** taşır.

**Sayfa hatası (page fault)**: Erişilen sayfa şu an fiziksel bellekte değilse (geçerlilik
biti kapalıysa) donanım bir tuzak (trap) üretir; işletim sistemi sayfayı diskten yükler,
sayfa tablosunu günceller ve komutu yeniden çalıştırır. Sık sayfa hatası (**thrashing**),
sistemin çoğu zamanını sayfa değişimiyle geçirip faydalı iş yapamaz hale gelmesidir.

# 3. TLB — Translation Lookaside Buffer

Her bellek erişiminde sayfa tablosuna gitmek pahalıdır (sayfa tablosunun kendisi de
bellekte olduğundan, çok seviyeli tablolarda birden fazla bellek erişimi gerekebilir).
**TLB**, sık kullanılan sanal→fiziksel çevirileri önbelleğe alan küçük, hızlı bir
donanım önbelleğidir (genellikle MMU içinde, CPU'ya çok yakın).

- **TLB hit**: Çeviri TLB'de bulunur, fiziksel adres doğrudan alınır — tek CPU çevrimi
  mertebesinde hızlıdır.
- **TLB miss**: Çeviri TLB'de yok; sayfa tablosuna gidilir (yavaş), bulunan çeviri
  TLB'ye eklenir.

**TLB ve context switch ilişkisi:** TLB girdileri belirli bir sürecin sayfa tablosuna
aittir. Süreçler arası bir context switch olduğunda (Konu 1), eski girdiler yeni sürece
ait olmayan çevirileri gösterir; bu yüzden TLB ya tamamen geçersiz kılınır (flush) ya da
her girdiye bir **adres uzayı kimliği (ASID)** eklenerek süreçler arası paylaşım
sağlanır. TLB flush, süreçler arası context switch'in thread'ler arasınkinden daha
pahalı olmasının başlıca nedenlerinden biridir.

# 4. Çok Seviyeli Sayfa Tabloları

64 bitlik bir adres uzayı için tek seviyeli, düz bir sayfa tablosu pratik değildir
(muazzam bellek israfı). Bunun yerine **çok seviyeli sayfa tabloları** kullanılır: sanal
adres birkaç parçaya bölünür, her seviye bir sonraki seviyenin tablosuna işaret eder ve
kullanılmayan alt ağaçlar hiç tahsis edilmez. Bu, bellek tasarrufu sağlar ama TLB miss
durumunda çeviri maliyetini artırır (her seviye ayrı bir bellek erişimi gerektirir) —
TLB'nin önemi tam da burada ortaya çıkar.

# 5. Sayfa Değiştirme Algoritmaları

Fiziksel bellek dolduğunda, yeni bir sayfa için yer açmak üzere bir kurbanın seçilmesi
gerekir:

- **FIFO**: En eski yüklenen sayfa çıkarılır. Basittir ama Belady anomalisi denen
  tuhaf bir davranış gösterebilir (daha fazla çerçeve, daha fazla sayfa hatasına yol
  açabilir).
- **LRU (Least Recently Used)**: En uzun süredir kullanılmayan sayfa çıkarılır;
  pratikte iyi performans gösterir ama tam LRU takibi donanım maliyetlidir, çoğu sistem
  yaklaşık (approximate) LRU kullanır (ör. "second chance"/clock algoritması).
- **Optimal (Belady's algorithm)**: Gelecekte en uzun süre kullanılmayacak sayfayı
  çıkarır; teorik alt sınırdır, gerçek sistemde geleceği bilmek mümkün olmadığından
  uygulanamaz, yalnız karşılaştırma ölçütü olarak kullanılır.

# 6. Özet

- Sanal bellek, izolasyon ve esneklik sağlar; MMU + sayfa tablosu çeviriyi yapar.
- TLB, sayfa tablosuna gitme maliyetini önbelleğe alarak azaltan donanım önbelleğidir;
  TLB miss pahalıdır, çok seviyeli tablolarda daha da pahalıdır.
- Süreçler arası context switch genellikle TLB flush gerektirir — bu, Konu 1 ve Konu
  2'de bahsedilen context switch maliyetinin bellek yönetimi tarafındaki karşılığıdır.
- Sayfa değiştirme algoritmaları (FIFO, LRU, Optimal) fiziksel bellek dolduğunda hangi
  sayfanın çıkarılacağına karar verir.
