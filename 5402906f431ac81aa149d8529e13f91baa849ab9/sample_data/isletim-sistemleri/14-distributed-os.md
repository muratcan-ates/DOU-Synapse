---
title: "Dağıtık Sistemlerde İşletim Sistemi Konuları"
subtitle: "İşletim Sistemleri — Konu 14"
format: pptx
---

# Dağıtık Sistem Nedir?

- Birden çok bağımsız bilgisayarın kullanıcıya tek bir tutarlı sistem gibi görünmesidir.
- Bileşenler yalnız mesajlaşarak haberleşir; paylaşılan bir bellek ve paylaşılan bir saat yoktur.
- Bu iki eksik, tek makineli işletim sistemi bilgisinin doğrudan aktarılamamasının sebebidir.
- Kazanç ölçeklenebilirlik, coğrafi dağıtım ve arızaya dayanıklılıktır; bedel karmaşıklıktır.

<!-- slayt -->

# Dağıtık Hesaplamanın Yanılgıları

- Ağ güvenilirdir: değildir, paketler düşer.
- Gecikme sıfırdır: değildir ve ışık hızı bir alt sınır koyar.
- Bant genişliği sonsuzdur, ağ güvenlidir, topoloji değişmez, tek bir yönetici vardır.
- Bu sekiz varsayım Peter Deutsch tarafından derlenmiştir; her biri yerel geliştirmede doğru görünür ve üretimde yanlış çıkar.

<!-- slayt -->

# Kısmi Arıza

- Tek makinede bir bileşen ya çalışır ya çöker; dağıtık sistemde bir düğüm çalışırken diğeri çökmüş olabilir.
- Daha kötüsü, çökmüş bir düğüm ile yavaş bir düğüm dışarıdan ayırt edilemez.
- Zaman aşımı tek pratik teşhis aracıdır ve kesin değildir: kısa zaman aşımı sağlıklı düğümü ölü ilan eder, uzun zaman aşımı tepkiyi geciktirir.
- Bu belirsizlik, dağıtık algoritmaların neden bu kadar karmaşık olduğunun temel sebebidir.

<!-- slayt -->

# Fiziksel Saat Senkronizasyonu

- Her makinenin kendi kristal saati vardır ve bunlar birbirinden kayar (clock drift).
- NTP (Network Time Protocol), gidiş-dönüş süresini ölçerek bir referans sunucuya göre yerel saati düzeltir.
- Saat asla geriye alınmaz; geriye almak zaman damgalarının sırasını bozar. Bunun yerine saat hızı geçici olarak yavaşlatılır.
- Milisaniye altı doğruluk gerekiyorsa PTP veya GPS gibi donanım destekli yöntemler gerekir.

<!-- slayt -->

# Mantıksal Saatler

- Çoğu problemde gereken şey gerçek zaman değil, olayların sırasıdır.
- Lamport mantıksal saati her düğümde bir sayaç tutar: yerel olayda artırılır, mesajla gönderilir, alınırken maksimum alınıp bir artırılır.
- Kural şudur: a olayı b'den önce geldiyse C(a) < C(b). Tersi doğru değildir.
- Yani sayaçlara bakarak iki olayın gerçekten sıralı mı yoksa eşzamanlı mı olduğu anlaşılamaz.

<!-- slayt -->

# Vektör Saatler

- Her düğüm, tüm düğümlerin sayaçlarından oluşan bir vektör tutar.
- Mesaj alındığında vektörler eleman bazında maksimum alınarak birleştirilir.
- Vektör saatler nedenselliği tam olarak yakalar: iki olayın eşzamanlı olup olmadığı karşılaştırmayla anlaşılır.
- Bedeli, düğüm sayısıyla büyüyen mesaj yüküdür.

<!-- slayt -->

# Dağıtık Karşılıklı Dışlama

- Merkezi yaklaşım: bir koordinatör kilit dağıtır. Basittir ama koordinatör tek arıza noktasıdır.
- Belirteç halkası (token ring): kilit hakkı halkada dolaşan bir belirteçtir. Belirteç kaybolursa yeniden üretilmesi gerekir.
- Dağıtık algoritma (Ricart-Agrawala): girmek isteyen düğüm herkese sorar ve tüm izinleri bekler.
- Dağıtık çözüm tek arıza noktasını kaldırır ama mesaj sayısını ve arıza durumlarını artırır.

<!-- slayt -->

# Lider Seçimi

- Birçok algoritma bir koordinatöre ihtiyaç duyar; koordinatör çökerse yenisi seçilmelidir.
- Zorba (bully) algoritmasında en yüksek kimlikli çalışan düğüm lider olur; daha yüksek kimlikli bir düğüm dönerse liderliği devralır.
- Halka algoritmasında seçim mesajı halkada dolaşır ve en yüksek kimlik toplanır.
- Ağ bölünmesi sırasında iki tarafın ayrı lider seçmesi ihtimali vardır; buna split-brain denir ve veri bozulmasına yol açar.

<!-- slayt -->

# İki Fazlı Commit

- Birden çok düğümde atomik bir işlem yapmayı hedefler: ya hepsi uygular ya hiçbiri.
- Birinci faz: koordinatör tüm katılımcılara hazır mısın diye sorar, her biri hazır ya da iptal yanıtı verir.
- İkinci faz: tüm yanıtlar hazır ise commit, aksi halde abort komutu gönderilir.
- Katılımcı hazır dediği anda kararı koordinatöre devretmiş olur ve tek başına vazgeçemez.

<!-- slayt -->

# İki Fazlı Commit'in Zayıflığı

- Koordinatör, katılımcılar hazır dedikten sonra çökerse katılımcılar süresiz bekler; kaynaklar kilitli kalır.
- Bu duruma engelleyici (blocking) protokol denir ve 2PC'nin bilinen temel kusurudur.
- Üç fazlı commit ek bir faz ekleyerek engellemeyi azaltır ama ağ bölünmesinde doğruluğu garanti etmez.
- Pratikte çözüm, koordinatörün kararını kalıcı bir günlüğe yazması ve yeniden başladığında kaldığı yerden devam etmesidir.

<!-- slayt -->

# Konsensüs Problemi

- Konsensüs, birden çok düğümün tek bir değer üzerinde anlaşmasıdır.
- Üç özellik istenir: anlaşma (hepsi aynı değeri seçer), geçerlilik (seçilen değer önerilenlerden biridir) ve sonlanma.
- FLP imkânsızlık sonucu şunu söyler: tamamen asenkron bir sistemde tek bir düğüm bile çökebiliyorsa, her zaman sonlanan bir konsensüs algoritması yoktur.
- Pratik algoritmalar bu sonucu zaman aşımı gibi kısmi senkronluk varsayımlarıyla aşar.

<!-- slayt -->

# Paxos ve Raft

- Paxos, çoğunluk (quorum) temelli klasik konsensüs algoritmasıdır; doğru ama anlaşılması zordur.
- Raft aynı garantileri verir ve anlaşılırlık hedefiyle tasarlanmıştır: lider seçimi, günlük çoğaltma ve güvenlik olarak üç parçaya ayrılır.
- Her ikisi de N düğümden çoğunluğun (N/2 + 1) çalışmasını gerektirir; bu yüzden düğüm sayısı tek seçilir.
- Beş düğümlü bir küme iki düğüm kaybına dayanır; dört düğümlü küme de yalnız bir kayba dayanır, yani dördüncü düğüm dayanıklılık eklemez.

<!-- slayt -->

# CAP Teoremi

- Bir dağıtık veri deposu tutarlılık (C), kullanılabilirlik (A) ve bölünme toleransı (P) özelliklerinden aynı anda en fazla ikisini sağlayabilir.
- Ağ bölünmesi bir tasarım tercihi değildir, gerçekleşir; dolayısıyla P vazgeçilemez.
- Gerçek seçim bölünme sırasında yapılır: tutarlılığı korumak için istek reddedilecek mi, yoksa eski veriyle yanıt verilecek mi?
- Yaygın yanlış okuma, CAP'in her zaman iki özellik seçtirdiğidir; bölünme yokken hem C hem A sağlanabilir.

<!-- slayt -->

# Tutarlılık Modelleri

- Katı (strict) tutarlılık: her okuma en son yazmayı görür. Tek makinede bile pahalıdır.
- Ardışık (sequential) tutarlılık: tüm düğümler işlemleri aynı sırada görür, ama bu sıra gerçek zamana uymayabilir.
- Nedensel (causal) tutarlılık: nedensel bağı olan işlemler her yerde aynı sırada görülür; bağımsız olanlar farklı sırada görülebilir.
- Nihai (eventual) tutarlılık: yeni yazma olmazsa tüm kopyalar zamanla aynı değere yakınsar.

<!-- slayt -->

# Çoğaltma

- Veriyi birden çok düğümde tutmak okuma başarımını ve dayanıklılığı artırır.
- Tek liderli (primary-backup) çoğaltmada tüm yazmalar lidere gider; sıralama basittir, lider darboğazdır.
- Çok liderli çoğaltmada yazmalar herhangi bir düğüme gidebilir ve çakışmaların çözülmesi gerekir.
- Çakışma çözümünde son yazan kazanır kuralı basittir ama veri kaybettirir; birleştirilebilir veri tipleri (CRDT) bu kaybı önler.

<!-- slayt -->

# Dağıtık Dosya Sistemleri

- NFS istemcilerin uzak dizinleri yerel gibi bağlamasını sağlar; durumsuz (stateless) tasarımı sunucu yeniden başlatmalarını kolaylaştırır.
- Önbellekleme başarım için zorunludur ama tutarlılığı zorlaştırır: bir istemcinin yazdığını diğeri ne zaman görecek?
- NFS bu soruya kesin bir cevap vermez; kapat-sonra-aç (close-to-open) tutarlılığı sunar.
- HDFS gibi sistemler farklı bir ödünleşim seçer: dosyalar bir kez yazılır, çok kez okunur ve büyük bloklar halinde saklanır.

<!-- slayt -->

# Özet

- Dağıtık sistemin iki eksiği paylaşılan bellek ve paylaşılan saattir; tüm karmaşıklık buradan doğar.
- Mantıksal saatler sıralama sorununu, konsensüs algoritmaları anlaşma sorununu çözer.
- 2PC atomikliği sağlar ama koordinatör arızasında engeller; Paxos ve Raft çoğunlukla çalışmaya devam eder.
- CAP teoremi bir seçim dayatmaz, ağ bölündüğünde hangi özelliğin feda edileceğini önceden düşünmeye zorlar.
