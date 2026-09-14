# DOU-Synapse — Tasarım Sistemi

## Ürün sahibinin son tasarım yönü · 14 Eylül 2026

Gündüz **beyaz, sıcak fildişi ve Antik Mısır altınından esinlenen ayrıntılar**;
gece **derin uzay laciverti ve altın sinaps ışımaları**. Bu karar önceki kırmızı
arayüz aksanını ve gündüz kalıcı koyu gezinme yüzeylerini değiştirir. Güvenlik,
roller, sınav bütünlüğü ve erişilebilirlik sınırları korunur.

Altın/lacivert, Synapse için ürün sahibinin seçtiği yaratıcı palettir; Doğuş
Üniversitesi'nin resmî renk paleti olduğu iddia edilmez. Üniversite arması özgün
kırmızı kimliğiyle korunur; resmî varlıklar için üniversitenin
[Kurumsal Kimlik](https://www.dogus.edu.tr/hakkimizda/universitemiz/kurumsal-kimlik)
kaynağı esas alınır.

Renk çemberi, uyumlu ana ve vurgu renklerini birlikte değerlendirmeye yardımcı
olur; altın/lacivert seçimi bu projeye ait tasarım kararıdır.
[Adobe Color](https://color.adobe.com/create/color-wheel) renk uyumu ve kontrastı
birlikte değerlendirmek için başvuru kaynağıdır. Aşağıdaki oranlar ise Adobe'den
kopyalanmaz; depodaki gerçek CSS tokenlarından hesaplanır.

DESIGN_VARIANCE 6, MOTION_INTENSITY 5, VISUAL_DENSITY 5. Arayüz gerçek ders
verileriyle çalışan bir öğrenme uygulamasıdır. Pazarlama sayfası veya deneysel
kaydırma kuralları sınav ve yönetim formlarına zorlanmaz.

## Renklerin kullanım amacı

| Rol | Gündüz | Gece |
|---|---|---|
| Sayfa zemini | `#FAF9F6` sıcak fildişi | `#061426` derin lacivert |
| İş yüzeyi ve gezinme | `#FFFFFF` beyaz | `#0C213A` lacivert |
| İç yüzey | `#F2EEE5` | `#04101F` |
| Birincil metin | `#132B45` | `#F3F1E8` |
| Marka metni / birincil eylem | `#8A6518` | `#E6C36E` |
| Eylem vurgusu / hover | `#705010` | `#F1D58E` |
| Hafif altın yüzey | `#F5EDD9` | `#243043` |
| Marka düğmesi metni | `#FFFFFF` | `#071930` |

- `gold` / `--gold-light: #D6B05E`, ışık ve çizgi gibi dekoratif ayrıntılar içindir.
  Açık zeminde küçük metin veya tek başına bilgi taşıyan kontrol sınırı yapılmaz.
  Metin ve odak rengi için ölçülen `brand` tokenı kullanılır.
- `ink: #071930` ve `ink-raised: #102D4B` her iki temada aynı laciverttir.
  Bu özel yüzeylerde yalnız `ink-fg`, `ink-fg-muted` ve `brand-on-ink` metinleri
  kullanılır. Gündüz gezinme ve ana içerik bunlarla karartılmaz.
- Başarı, uyarı, hata ve bilgi renkleri anlamsal ayrımını korur. Hata kırmızısı
  altına dönüştürülmez; durumlar metin ve gerektiğinde ikonla da açıklanır.
- Oturum açıkken tek tema kontrolü üst çubuktadır. Giriş sayfasında da yalnız
  bir kontrol bulunur; bir ekranda ikinci tema seçici gösterilmez.

## Görsel dil ve yerleşim

Son kullanıcı düzeltmesi: göz/Horus simgeleri ve anatomik beyin silueti kaldırılır.
Synapse hissi, asimetrik ve açık uçlu ince bağlantı çizgileriyle verilir; çizgiler
bir yüz veya organ konturu oluşturmaz. Akson ve dendrit benzeri dallanmalar,
küçük sinaps boşlukları ve hat boyunca ilerleyen kısa ışık geçişleri kullanılır.
Altın/lacivert palet korunur. Sol üstte
Synapse adının yanında özgün Doğuş arması bulunur; daraltılmış menüde de arma
görünür. Dekoratif bağlantı hareketi kısa sürer ve azaltılmış harekete uyar.

- Geist; giriş ve genel bakışta 40–48px başlık, ders araçlarında 28–36px,
  gövde 16px, kontroller 15px, etiket 13px. Uzun başlıklar dar ekrana uyarlanır.
- Masaüstü gezinmesi sol kenardan 12px içeride, 224px genişlikte, 22px
  köşeli bir yüzeydir. Genişlik rezervi 248px; daraltılmış rezerv 108px.
  Üst çubuk 80px. Mobilde 72px başlık, yüzen alt menü ve 140px alt pay.
- Gezinme rayı tema yüzeyini kullanır: gündüz beyaz, gece lacivert; çevresinde
  dekoratif ince kenarlık vardır. Kalıcı siyah panel kullanılmaz.
- İçerik en fazla 1480px; 36px masaüstü / 16–20px mobil yan boşluk.
  Viewport değişiminde sayfa marjı animasyonla kaymaz; taşma gizlenerek örtülmez.
- Ana odak yüzeyi 24–28px, içerik paneli 16–20px, kontrol 12px köşe.
  Formlar ve uzun ders adları kendi alanına sığar. Ders sekmeleri dar ekranda
  kendi içinde kayar; klavye odağı görünür kalır.

## Kampüs uygulaması düzeltmesi · 14 Eylül, son referans turu

Doğuş mobil referanslarından alınan yön: kompakt ders odağı, kişisel kimlik,
gruplanmış alanlar, okunaklı ders satırları ve yumuşak yüzen gezinme. Büyük
pazarlama başlıkları, yinelenen toplam kutuları ve her sayfadaki geniş dekoratif
bölümler azaltılır. Profilde küçük marka başlığıyla kesişen yuvarlak baş harf
avatarı ve gerçek hesap/ders bilgileri kullanılır. Akademik dönem, telefon,
danışman, takvim ve haber gibi API'de olmayan bilgiler üretilmez.

Ders kapakları, Türkçe baş harfleri ve normalize edilmiş ders adı/kodundan
türetilen sabit kompozisyondur. Yüzlerce ders için ayrı raster görsel gerekmez;
sıralama ve sayfa yenilemesi kapağı değiştirmez. Palet aynı token sistemindedir.

Kapanıştaki eylem **Ders tekrarına geç** olarak `/study` sayfasına gider. Sayfa
mevcut profil üyeliklerini kullanır, ders araması ve kaynak/alıştırma geçişi
sunar. Alıştırma bağlantısı mevcut sınav provası ekranını açar; navigasyon
sınav veya alıştırma başlatmaz. Başlatma ve kilit kontrolleri mevcut akıştadır.
El görselleri için istemler soldan doğal insan, sağdan robotik sinaps eli ve
Michelangelo'dan esinlenen yatay yaklaşma olarak düzeltilmiştir.

## Rol panelleri ve erişilebilirlik · 14 Eylül, son uygulama turu

Öğrenci paneli ders tekrarı, ilerleme ve sınavlara; eğitmen paneli kaynaklara,
soru onaylarına ve sınıf araçlarına odaklanır. Aynı kişi farklı derslerde farklı
rollerdeyse iki alan birlikte görünür. Yetki yalnız sunucu profil/üyelik
cevabından gelir. Bilgi İşlem ayrı teknik yönetim alanıdır; öğrenci ve eğitmen
menüsünde görünmez. Demo Ayşe yalnız eğitmendir; üçüncü, üyeliksiz demo hesap
platform yönetimini gösterir. Bağlı olmayan güvenlik olay akışı açıkça
**Henüz bağlı değil** olarak belirtilir; sağlık sonucu veya alarm uydurulmaz.

Ortak mobil gezinme: Genel bakış, Dersler, Profil, Ayarlar. Yalnız platform
yönetimi olan ve ders üyeliği bulunmayan Bilgi İşlem hesabında Genel bakış,
Profil ve Ayarlar gösterilir; teknik yönetime ayrı giriş sunulur. Bu hesapta
ders gezinmesi veya öğrenmeye yönlendiren kapanış gösterilmez. `/settings` içindeki
erişilebilirlik tercihleri yalnız tarayıcıya kaydolur: %25 büyük yazı, işletim
sistemi/manuel azaltılmış hareket, yüksek kontrast ve bağlantı altçizgisi.
Büyük yazı başlıklarda da uygulanır; yazı ölçüleri rem'dir. Tema için üst
çubuktaki tek kontrol açılır. Sıfırlama oturumu veya tema tercihini değiştirmez.
CSS ve GSAP aynı hareket tercihine uyar. Kısa ekran/büyük yazıda asistan
çekmecesi kaydırılabilir; konuşma alanı sıfır yüksekliğe sıkışmaz.

Asistan imzası 24px çizgi ızgarasında açık bir kitap, ince cilt çizgisi ve küçük
altın kenar ayrıntısıdır. Dolu madalyon, dört kare, göz veya anatomik beyin
kullanılmaz. Uzun rol açıklaması çekmecede “Rol ve kapsam” altında açılır.
Simge dekoratiftir; sunucunun
verdiği asistan adı görünür ve erişilebilir etiket olarak kalır. Yeni görsel
üretimi, simgeyi veya işlevsel arayüzü resme dönüştürmez.

## İşleyen etkileşimler

Üst çubuk araması ve Cmd/Ctrl+K, profil üyeliklerindeki derslere ve kullanıcının
erişebildiği sayfalara geçiş açar. Yeni veya ayrıcalıklı API çağrısı yapmaz.
Türkçe arama, Escape, Tab, Enter ve kapanınca odağın geri dönmesi native dialog
ile korunur. Öğrenciye yönetici sonucu gösterilmez.

Panel gerçek ders odağını, durumları ve role uygun araçları sunar. Ders araması
ve rol filtreleri mevcut kayıtlarda çalışır. Kişisel telefon, öğrenci numarası,
sahte başarı oranı veya haber eklenmez.

GSAP 3.15.0 ve @gsap/react 2.1.2 kısa rota/arama geçişleri için kullanılır.
Altın sinaps ışımaları marka ayrıntısıdır; ders içeriği, sınav soruları ve form
kontrolleri titreştirilmez. Hareket içerik okumayı geciktirmez veya yerleşim
ölçülerini değiştirmez. React temizliği ve `prefers-reduced-motion` desteği
zorunludur; hareket azaltıldığında dekoratif animasyonlar durur.

## Korunan davranışlar

Yetkilendirme, ders üyeliği, RLS, kaynak zorunluluğu, sınav kilidi, cevap anahtarı
gizliliği ve kişisel veri yaşam döngüsü korunur. Demo etiketi gerçek sağlayıcı
kalitesi gibi sunulmaz. Referans ekranları ve kişisel bilgiler depoya girmez.

En az 44px hedefler, görünür odak, açık/koyu kontrast ve azaltılmış hareket
kontrol edilir. API yetkisi görsel gizleme ile değiştirilemez. Her ölçüm yalnız
çalıştırıldığı adayı doğrular; başarısız tarayıcı testleri kayıtta tutulur.

## Renk denetimi

[WCAG 1.4.3](https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum)
normal metin için en az 4.5:1, büyük metin için 3:1 ister. Buradaki tüm metin
çiftleri daha genel olan **4.5:1** kapısına bağlıdır; eşik karşılaştırması
yuvarlanmamış oranla yapılır. Bilgi taşıyan kontrol sınırları için **3:1** kapısı
korunur. Dekoratif kart çizgileriyle kontrol sınırları aynı amaçta değildir.

Aşağıdaki tablo `node apps/web/scripts/contrast.mjs --md` çıktısıdır. Normal ve
hover düğmeleri hem mevcut beyaz/gece-zemin metin sözleşmesiyle hem `brand-fg`
tokenıyla ölçülür. Bu ölçüm gerçek renk çiftlerini doğrular; tek başına tüm
arayüzün erişilebilirlik sertifikası değildir.

### Açık tema

| Token | Değer | `--bg` (#faf9f6) | `--surface` (#ffffff) | `--surface-sunken` (#f2eee5) |
|---|---|---|---|---|
| `--fg` | `#132b45` | 13.67:1 AA | 14.39:1 AA | 12.43:1 AA |
| `--fg-muted` | `#536170` | 6.02:1 AA | 6.34:1 AA | 5.48:1 AA |
| `--fg-subtle` | `#5e6a76` | 5.25:1 AA | 5.53:1 AA | 4.77:1 AA |
| `--brand` | `#8a6518` | 5.04:1 AA | 5.31:1 AA | 4.59:1 AA |
| `--brand-strong` | `#705010` | 7.01:1 AA | 7.38:1 AA | 6.38:1 AA |
| `--success` | `#346538` | 6.51:1 AA | 6.85:1 AA | 5.92:1 AA |
| `--warning` | `#8a5c00` | 5.52:1 AA | 5.81:1 AA | 5.02:1 AA |
| `--danger` | `#9f2f2d` | 6.83:1 AA | 7.20:1 AA | 6.21:1 AA |
| `--info` | `#1f6c9f` | 5.39:1 AA | 5.67:1 AA | 4.90:1 AA |

| Çift | Not | Oran |
|---|---|---|
| `--ink-fg / --ink` | sabit lacivert yüzeyde birincil metin (#f3f1e8 / #071930) | 15.59:1 geçti |
| `--ink-fg-muted / --ink` | sabit lacivert yüzeyde ikincil metin (#b7c7dc / #071930) | 10.26:1 geçti |
| `--ink-fg / --ink-raised` | yükseltilmiş lacivert yüzeyde birincil metin (#f3f1e8 / #102d4b) | 12.38:1 geçti |
| `--ink-fg-muted / --ink-raised` | yükseltilmiş lacivert yüzeyde ikincil metin (#b7c7dc / #102d4b) | 8.15:1 geçti |
| `--brand-on-ink / --ink` | lacivert üstünde altın marka metni (#e6c36e / #071930) | 10.41:1 geçti |
| `--brand-on-ink / --ink-raised` | yükseltilmiş lacivert üstünde altın marka metni (#e6c36e / #102d4b) | 8.27:1 geçti |
| `--gold-light / --ink` | altın dekorun lacivert üstündeki kontrastı (#d6b05e / #071930) | 8.59:1 geçti |
| `--gold-light / --ink-raised` | altın dekorun yükseltilmiş lacivert üstündeki kontrastı (#d6b05e / #102d4b) | 6.83:1 geçti |
| `--success / --success-bg` | #346538 / #edf3ec | 6.08:1 geçti |
| `--warning / --warning-bg` | #8a5c00 / #fbf3db | 5.25:1 geçti |
| `--danger / --danger-bg` | #9f2f2d / #fdebec | 6.26:1 geçti |
| `--info / --info-bg` | #1f6c9f / #e1f3fe | 4.98:1 geçti |
| `--brand / --brand-subtle` | #8a6518 / #f5edd9 | 4.55:1 geçti |
| `#ffffff / --brand` | mevcut beyaz birincil buton metni | 5.31:1 geçti |
| `#ffffff / --brand-strong` | mevcut beyaz birincil buton hover metni | 7.38:1 geçti |
| `brand-fg / --brand` | semantik birincil buton metni | 5.31:1 geçti |
| `brand-fg / --brand-strong` | semantik birincil buton hover metni | 7.38:1 geçti |
| `--border-strong / --surface` | girdi/ikincil buton kenarlığı (kontrolün içi) | 3.22:1 geçti |
| `--border-strong / --bg` | girdi/ikincil buton kenarlığı (sayfa zemini) | 3.18:1 geçti |
| `--fg-subtle / --surface` | ilerleme çubuğu dolgusu (bg-fg-subtle) | 5.53:1 geçti |

### Koyu tema

| Token | Değer | `--bg` (#061426) | `--surface` (#0c213a) | `--surface-sunken` (#04101f) |
|---|---|---|---|---|
| `--fg` | `#f3f1e8` | 16.34:1 AA | 14.34:1 AA | 16.89:1 AA |
| `--fg-muted` | `#b7c7dc` | 10.76:1 AA | 9.44:1 AA | 11.12:1 AA |
| `--fg-subtle` | `#9daec6` | 8.19:1 AA | 7.19:1 AA | 8.46:1 AA |
| `--brand` | `#e6c36e` | 10.91:1 AA | 9.58:1 AA | 11.28:1 AA |
| `--brand-strong` | `#f1d58e` | 12.90:1 AA | 11.32:1 AA | 13.33:1 AA |
| `--success` | `#7bc47f` | 8.84:1 AA | 7.76:1 AA | 9.14:1 AA |
| `--warning` | `#d9a23d` | 8.09:1 AA | 7.10:1 AA | 8.36:1 AA |
| `--danger` | `#f08c8a` | 7.77:1 AA | 6.82:1 AA | 8.03:1 AA |
| `--info` | `#6fb4dd` | 8.14:1 AA | 7.15:1 AA | 8.41:1 AA |

| Çift | Not | Oran |
|---|---|---|
| `--ink-fg / --ink` | sabit lacivert yüzeyde birincil metin (#f3f1e8 / #071930) | 15.59:1 geçti |
| `--ink-fg-muted / --ink` | sabit lacivert yüzeyde ikincil metin (#b7c7dc / #071930) | 10.26:1 geçti |
| `--ink-fg / --ink-raised` | yükseltilmiş lacivert yüzeyde birincil metin (#f3f1e8 / #102d4b) | 12.38:1 geçti |
| `--ink-fg-muted / --ink-raised` | yükseltilmiş lacivert yüzeyde ikincil metin (#b7c7dc / #102d4b) | 8.15:1 geçti |
| `--brand-on-ink / --ink` | lacivert üstünde altın marka metni (#e6c36e / #071930) | 10.41:1 geçti |
| `--brand-on-ink / --ink-raised` | yükseltilmiş lacivert üstünde altın marka metni (#e6c36e / #102d4b) | 8.27:1 geçti |
| `--gold-light / --ink` | altın dekorun lacivert üstündeki kontrastı (#d6b05e / #071930) | 8.59:1 geçti |
| `--gold-light / --ink-raised` | altın dekorun yükseltilmiş lacivert üstündeki kontrastı (#d6b05e / #102d4b) | 6.83:1 geçti |
| `--success / --success-bg` | #7bc47f / #1d2a1e | 7.16:1 geçti |
| `--warning / --warning-bg` | #d9a23d / #2b2312 | 6.79:1 geçti |
| `--danger / --danger-bg` | #f08c8a / #331a1c | 6.76:1 geçti |
| `--info / --info-bg` | #6fb4dd / #14232e | 7.06:1 geçti |
| `--brand / --brand-subtle` | #e6c36e / #243043 | 7.85:1 geçti |
| `bg / --brand` | mevcut koyu birincil buton metni | 10.91:1 geçti |
| `bg / --brand-strong` | mevcut koyu birincil buton hover metni | 12.90:1 geçti |
| `brand-fg / --brand` | lacivert birincil buton metni | 10.41:1 geçti |
| `brand-fg / --brand-strong` | lacivert birincil buton hover metni | 12.30:1 geçti |
| `--border-strong / --surface` | girdi/ikincil buton kenarlığı (kontrolün içi) | 3.41:1 geçti |
| `--border-strong / --bg` | girdi/ikincil buton kenarlığı (sayfa zemini) | 3.49:1 geçti |
| `--fg-subtle / --surface` | ilerleme çubuğu dolgusu (bg-fg-subtle) | 7.19:1 geçti |


## Bulunamayan sayfa ve kurtarma

Gerçek Next 404 ekranı anonim kullanıcıya da açılır; kurumsal arma, tema
renkleri, “Bu sayfayı bulamadık” başlığı ve çalışma alanına dönüş sunar.
Çalışan bir sayfanın yüklenme hatası 404 gibi gösterilmez: ayrı hata sınırında
Next `retry()` ile yeniden deneme vardır. Ham hata mesajı ve yığını ekrana
ve tarayıcı günlüğüne yazılmaz; yalnız denetlenen opak hata kodu kullanılabilir.
Kök yazı boyutu, kontrast ve hareket tercihleri bu ekranlarda da korunur.

## Üretilen sanatın uygulanması · 14 Eylül, görsel teslim turu

Kullanıcının referanslarından esinlenerek yeniden kurulan açık/koyu vektör
sinaps çizimleri girişte; paylaştığı insan ve robot elleri akademik kapanışta
kullanılır. Bu dört dosya kişisel veri içermeyen,
yazısız dekoratif ürün varlıklarıdır. Mobil referans ekranları ve arayüz
spesifikasyonu resimleri depoya alınmaz. Gündüz ve gece için ayrı varlık
seçilir; aynı görsel filtreyle yeniden renklendirilmez. Görseller hareket
etmez; metin, düğme ve kurumsal arma gerçek arayüz öğeleri olarak kalır.

Kapanış bandında iki elin yaklaşması ve ortadaki boşluk birlikte görünür.
Görselin çevresindeki metin mobilde sarılır; resim bir kontrolün yerini almaz.
Girişte tek sinaps kompozisyonu yeterlidir; yinelenen halkalar veya ikinci
bağlantı çizimi eklenmez. Sinaps kapakları her iki temada aynı Bézier geometrisini kullanan küçük SVG
dosyalarıdır. El görselleri için Next görüntü optimizasyonu uygun ekran
genişliğinde sunum üretir; kullanıcının özgün dosyaları değiştirilmez.

404, yüklenme hatası, roller ve asistan için üretilmiş ekran resimleri yalnız
referanstır. İçlerindeki yapay arma, örnek hata kodu, doğrulanmamış test
ifadeleri ve kurgusal katılımcılar ürüne aktarılmaz. Mevcut kırmızı üniversite
arması, gerçek yetki kontrolleri ve çalışan kurtarma eylemleri korunur.
