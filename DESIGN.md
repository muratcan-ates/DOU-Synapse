# DOU-Synapse — Tasarım Sistemi

Bu belge arayüzün tek otoritesidir. Bir bileşen yazılırken renk, boşluk veya tipografi
kararı burada aranır; burada yoksa önce buraya eklenir, sonra kullanılır.

Plan: [PLAN.md](PLAN.md) · Mimari: [ARCHITECTURE.md](ARCHITECTURE.md)

---

## Overview

**Ürün tipi:** Ders asistanı. Dashboard, veri tablosu ve çok adımlı akış içerir —
pazarlama sitesi değildir. Bu ayrım kritik: hazır "anti-slop" tasarım skill'lerinin çoğu
landing page için ayarlıdır ve buraya doğrudan uygulanırsa yanlış register üretir.

**Kullanım bağlamı:** Öğrenci, sınavdan önceki gece, yorgun, muhtemelen telefonda veya
dizüstünde, uzun oturumlar boyunca yoğun teknik metin okuyor. Eğitmen ise haftada birkaç
kez materyal yüklüyor ve sınıfın durumuna bakıyor.

**Tasarım brief'i tek cümlede:** Sakin, okunur ve kurumsal; aynı zamanda yaşayan bir
akademik çalışma alanı. Ürün **güvenilir** görünür, fakat bu güven her ekranı aynı beyaz
karta çevirmekten değil; açık hiyerarşi, rol odaklı kompozisyon ve tutarlı kaynak
kanıtından gelir.

**Üç dial** (taste-skill terminolojisi):

| Dial | Ayar | Neden |
|---|---|---|
| VARIANCE | Orta (6/10) | Gramer ortak kalır; öğrenci, eğitmen ve Bilgi İşlem yüzeyleri işlerine göre farklı kompozisyon kurar |
| MOTION | Düşük (3/10) | Sınav ekranında animasyon kaygı üretir; hareket yalnız durum değişimini bildirir |
| DENSITY | Orta yüksek (6/10) | Öğrenci okuma alanları ferah, eğitmen ve Bilgi İşlem veri şeritleri kompakt olmalı |

### Modern akademik stüdyo grameri

Canlılık yeni bir renk paleti değildir. Tek aksan yine Doğuş kırmızısıdır; enerji şu
araçlarla kurulur:

- Bir sayfada tek baskın odak alanı ve onun altında daha sakin çalışma satırları
- Büyük başlık ile küçük mono ders kodu, zaman ve ölçüm bilgisinin bilinçli karşıtlığı
- Her şeyi karta kapatmak yerine kenarlıksız bölümler, yatay kurallar ve bağlı veri şeritleri
- Öğrencide sunucunun bildirdiği çalışma durumu, eğitmende karar bekleyen işler,
  Bilgi İşlem'de servis durumu ve ölçüm zamanı ile başlayan rol bazlı hiyerarşi
- Kurumsal işaret, aktif gezinme çizgisi ve birincil eylem dışında kırmızı yüzey yığmama

Üç veya daha fazla ilgisiz bölüm aynı `rounded + border + white card` kalıbını
kullanıyorsa kompozisyon yeniden kurulmalıdır. Dört eşit metrik sayfayı açmaz; metrikler
odak alanından sonra kompakt bir şerit olarak gelir. Bu kural sınav ve soru çözme
yüzeylerini hareketlendirmez: o ekranlar bilinçli olarak daha sakindir.

---

## Colors

### Marka

Doğuş Üniversitesi kırmızısı, resmî logodan örneklendi: **`#C50C1F`**
(ikinci logo varyantı `#D60825` verir; birincil olarak yeni logodaki ton alındı).

**Kırmızı bir tema değil, bir vurgudur.** Arayüzün ~%90'ı nötr. Kırmızı yalnız şu üç işte
kullanılır: birincil eylem butonu, aktif navigasyon göstergesi, kurumsal başlık alanı.
Kırmızıyı hata rengi olarak KULLANMA — kurumsal kimlikle hata durumu karışır.

### Kontrast oranları ölçülür, yazılmaz

Bu bölümdeki her oran `apps/web/scripts/contrast.mjs` ile **ölçüldü** (WCAG 2.1 relative
luminance, `(L1+0.05)/(L2+0.05)`). Betik değerleri elle almaz, `apps/web/app/globals.css`
dosyasının kendisinden okur — token değişince oran da değişir:

```
cd apps/web && node scripts/contrast.mjs        # kontrol; herhangi bir çift eşiğini geçmezse çıkış kodu 1
cd apps/web && node scripts/contrast.mjs --md   # aşağıdaki oran sütunlarını yeniden üretir
```

Token değeri değiştiren, bu tabloları `--md` çıktısıyla günceller. Eşikler: normal metin
**4.5:1**, 18.66px+ kalın / 24px+ metin **3:1**, metin olmayan arayüz öğesi (WCAG 1.4.11)
**3:1**. Bu üründe bilgi taşıyan metnin çoğu 12px ve 14px'tir, yani neredeyse her şey
4.5:1 sınıfındadır — "küçük yazı zaten dekoratif" kaçamağı burada geçerli değil.
Son ölçüm: **9 Ağustos 2026**.

**Üç eşiğin üçü de kapıdır.** Metin dışı bölüm bir süre "ölçülür ama çıkış kodunu
etkilemez" diye koştu; `--border-strong` o boşlukta 1.33:1'de kaldı ve kimse fark
etmedi. Ölçülüp kapıya bağlanmayan sayı, ölçülmemiş sayıdır — bu yüzden ayrıcalık
kaldırıldı.

### İki kenarlık token'ı, iki ayrı eşik

Karıştırılırsa ya erişilebilirlik gider ya da arayüzün kılcal çizgi dili kalınlaşır:

| Token | Ne çizer | 1.4.11 kapsıyor mu | Eşik |
|---|---|---|---|
| `--border` | **Dekoratif ayraç**: kart kenarı, liste ayracı, sekme şeridinin alt çizgisi. Kaldırılsa hiçbir öğe kullanılamaz hâle gelmez; yalnız gruplamayı zayıflatır. | Hayır | yok |
| `--border-strong` | **Kontrol sınırı**: girdinin ve ikincil butonun nerede başlayıp bittiğini yalnız o gösteriyor (girdi zemini `--surface`, sayfa zemini `--bg`; ikisi arasında 1.04:1 var, yani zemin farkı sınır işi görmez). | **Evet** | **3:1** |

Kenarlık iki zemine birden komşudur (kontrolün içi ve sayfanın kendisi), bu yüzden
betik ikisine karşı da ölçer ve düşük olanı kapıya sokar.

### Açık tema

Kanvas saf beyaz değil kemik (`--bg`), kartlar beyaza **yükselir** (`--surface`) — kâğıt
üstünde kâğıt. 16 Ağustos'ta üçüncü katman eklendi: `--surface-sunken`, kanvasın
**altında** duran blok (açıklama, meta, araç paneli). Metin için en kötü zemin artık
çukur yüzeydir ve eşik ona göre kurulur — betik üç zemini de ölçer, `min` en kötüsünü
alır. Ölçüm bunu hemen kanıtladı: eski `--fg-subtle` (#78716c) çukur yüzeyde 4.25:1
ile AA'nın altında kaldı ve token koyultuldu.

| Token | Değer | Kullanım | `--bg` (#fbfbfa) | `--surface` (#ffffff) | `--surface-sunken` (#f2f1ef) |
|---|---|---|---|---|---|
| `--fg` | `#1c1917` |Gövde metni | 16.89:1 AA | 17.49:1 AA | 15.49:1 AA |
| `--fg-muted` | `#57534e` |İkincil metin, etiket, alıntı | 7.37:1 AA | 7.63:1 AA | 6.76:1 AA |
| `--fg-subtle` | `#726b66` |Zaman damgası, kimlik, kırıntı yolu | 5.06:1 AA | 5.24:1 AA | 4.64:1 AA |
| `--brand` | `#c50c1f` |Birincil buton, aktif sekme | 5.88:1 AA | 6.09:1 AA | 5.40:1 AA |
| `--brand-strong` | `#a00a19` |Hover, basılı durum | 7.95:1 AA | 8.23:1 AA | 7.29:1 AA |
| `--success` | `#346538` |Hazır, onaylandı, doğru | 6.62:1 AA | 6.85:1 AA | 6.07:1 AA |
| `--warning` | `#956400` |İşleniyor, geliştirilmeli | 4.95:1 AA | 5.12:1 AA | 4.54:1 AA |
| `--danger` | `#9f2f2d` |Gerçek hata, yıkıcı eylem | 6.95:1 AA | 7.20:1 AA | 6.37:1 AA |
| `--info` | `#1f6c9f` |Kaynak referansı, taslak | 5.48:1 AA | 5.67:1 AA | 5.02:1 AA |

Zeminler ve kenarlıklar (metin değil; üstlerindeki metnin oranı yukarıdaki iki sütunda,
kenarlığın kendi oranı "Karşılanmayan eşikler" başlığında):

| Token | Değer | Kullanım |
|---|---|---|
| `--bg` | `#fbfbfa` | Sayfa zemini |
| `--surface` | `#ffffff` | Kart, panel, girdi |
| `--border` | `rgba(28,25,23,.08)` | Dekoratif ayraç, kart kenarı |
| `--border-strong` | `rgba(28,25,23,.48)` | Girdi, ikincil buton, kesik çerçeve — 3.16:1 (`--surface`) · 3.13:1 (`--bg`) |
| `--brand-subtle` | `#fdebec` | Rozet ve şerit zemini, avatar |
| `--success-bg` `--warning-bg` `--danger-bg` `--info-bg` | `#edf3ec` `#fbf3db` `#fdebec` `#e1f3fe` | Durum rozeti zeminleri |

### Koyu tema

Koyu tema **zorunludur**, süs değil: öğrenciler geceleri çalışıyor.

**Tema nasıl seçilir.** İşletim sistemi ayarı tek yol DEĞİLDİR: kullanıcı
uygulamadan da seçebilir (Sistem / Açık / Koyu). Seçim `data-theme`
özniteliğine yazılır ve koyu palet tek bir seçicide (`:root[data-theme="dark"]`)
tanımlanır — medya sorgusu ayrıca yazılsaydı palet iki yerde yaşar ve bir
sonraki token değişiminde ayrışırdı. "Sistem" tercihi ilk boyamadan önce koşan
statik betikte (`apps/web/public/theme-boot.js`) çözülür; sonradan çözülseydi
koyu tema kullanıcısı her açılışta beyaz bir çakma görürdü. Aynı sözlük API
belge sayfasında da kullanılır (`apps/api/static/docs-theme.js`); `localStorage`
origin başına ayrı olduğu için tercih ancak iki yüzey tek origin arkasındayken
ortaktır, bu yüzden her yüzeyin kendi seçicisi vardır.

Kontrol ikon değil **metin** taşır (Sistem / Açık / Koyu) ve `aria-pressed`
yazar: bu üründe renk ve şekil tek başına bilgi taşımaz.

Ölçülmüş kısıt: ham marka kırmızısı `#c50c1f`, koyu zeminde **2.93:1** (`--bg`) ve
**2.70:1** (`--surface`) verir — okunmaz. Koyu temada marka rengi mutlaka açılır. Yüzey
koyu temada **açılarak** yükseldiği için en kötü zemin `--surface`'tır ve eşik ona göre
kurulur.

| Token | Değer | `--bg` (#191715) | `--surface` (#211f1c) | `--surface-sunken` (#141210) |
|---|---|---|---|---|
| `--fg` | `#f5f4f2` | 16.26:1 AA | 14.96:1 AA | 17.00:1 AA |
| `--fg-muted` | `#b0aaa4` | 7.77:1 AA | 7.15:1 AA | 8.13:1 AA |
| `--fg-subtle` | `#8f8a84` | 5.22:1 AA | 4.80:1 AA | 5.46:1 AA |
| `--brand` | `#ff6b78` | 6.49:1 AA | 5.97:1 AA | 6.79:1 AA |
| `--brand-strong` | `#ffa1aa` | 9.30:1 AA | 8.56:1 AA | 9.73:1 AA |
| `--success` | `#7bc47f` | 8.55:1 AA | 7.86:1 AA | 8.94:1 AA |
| `--warning` | `#d9a23d` | 7.82:1 AA | 7.19:1 AA | 8.17:1 AA |
| `--danger` | `#f08c8a` | 7.51:1 AA | 6.91:1 AA | 7.85:1 AA |
| `--info` | `#6fb4dd` | 7.87:1 AA | 7.24:1 AA | 8.23:1 AA |

Zeminler: `--bg #191715` · `--surface #211f1c` · `--border rgba(245,244,242,.08)` ·
`--border-strong rgba(245,244,242,.36)` — 3.12:1 (`--surface`) · 3.15:1 (`--bg`) ·
`--brand-subtle #3a1a1e` ·
`--success-bg #1d2a1e` · `--warning-bg #2b2312` · `--danger-bg #331a1c` ·
`--info-bg #14232e`.

### Rozet ve buton çiftleri (ölçülmüş)

Rozetlerde metin kendi soluk zemininin üstündedir; sayfa zeminine göre ölçmek yanıltır.

| Çift | Açık | Koyu |
|---|---|---|
| `--success` / `--success-bg` | 6.08:1 | 7.16:1 |
| `--warning` / `--warning-bg` | 4.62:1 | 6.79:1 |
| `--danger` / `--danger-bg` | 6.26:1 | 6.76:1 |
| `--info` / `--info-bg` | 4.98:1 | 7.06:1 |
| `--brand` / `--brand-subtle` | 5.30:1 | 5.66:1 |
| Birincil buton metni / `--brand` | 6.09:1 (beyaz) | 6.49:1 (`#191715`) |

### Metin olmayan arayüz öğeleri (WCAG 1.4.11, 3:1 — ölçülmüş)

| Çift | Ne | Açık | Koyu |
|---|---|---|---|
| `--border-strong` / `--surface` | Girdi ve ikincil buton kenarlığı, kontrolün içine bakan yüz | 3.16:1 | 3.12:1 |
| `--border-strong` / `--bg` | Aynı kenarlığın sayfa zeminine bakan yüzü | 3.13:1 | 3.15:1 |
| `--fg-subtle` / `--surface` | İlerleme çubuğu dolgusu (`bg-fg-subtle`) | 4.80:1 | 4.80:1 |

**Kenarlık kararı geri alındı (9 Ağustos 2026).** Belge önce `--border-strong`'un
1.33:1 / 1.62:1'de bırakıldığını, çünkü 3:1'lik bir kenarlığın "kılcal kenarlık dilini
kalınlaştıracağını" yazıyordu. Karar iki nedenle bozuldu: (1) o gerekçe `--border` için
doğru ama `--border-strong` için değil — ikisi ayrı iş yapar ve kılcal dil `--border`'da
yaşar, o hâlâ `.08`; (2) 1.4.11 estetik tercih değil, kontrolün sınırının görülebilmesi
şartıdır ve girdinin başka görünür sınırı yok. Yeni değerler `.48` (açık) ve `.36`
(koyu); kenarlık kalınlığı değişmedi (hâlâ 1px), yalnız opaklık arttı.

### Karşılanmayan eşikler — kayıt, iddia değil

Aşağıdaki ölçüldü, geçemedi ve **bilerek** böyle bırakıldı. Kapı değildir; kapıyı
genişletmeden önce buradaki kayıt güncellenir.

- **`--danger-bg` ile `--brand-subtle` açık temada aynı değer** (`#fdebec`). "Başarısız"
  rozetinin zemini marka rozetinin zeminiyle birebir aynı; ayrım metin renginden ve
  etiketten geliyor. Ayrıştırma denendi: kırmızı ailesinde kalan adaylarla iki zemin
  arasındaki oran 1.02:1'de kaldı — göz ayırt etmez, yani hex'i değiştirmek yalnız
  "düzelttik" demeye yarardı. Gerçek çözüm `--danger`'ı kırmızı ailesinden çıkarmaktır
  ve bu bir renk kararı, düzeltme değil.

**Renk tek başına bilgi taşımaz.** Her durum ayrıca ikon veya metinle işaretlenir; renk
körlüğü ve düşük kontrastlı ekranlar için gereklidir. Yukarıdaki kayıt da bu kurala
yaslanıyor: rozetlerde etiket metni her zaman vardır (`lib/labels.ts`).

---

## Typography

**Gövde:** Geist (`next/font/google`, `latin` + `latin-ext`). Türkçe için `ğ ş ı İ ö ü ç`
glifleri tam ve noktasız ı ile noktalı i ayrımı net. `next/font` yazı tipini derlemede
yerelleştirir, yani çevrimdışı demo CDN'e bağlı kalmaz. *(Belge önce Inter diyordu;
uygulama Geist ile yazıldı ve belge koda çekildi — tek yazı tipi ailesi vardır.)*

**Kod:** Geist Mono. Kod chunk'ları, dosya adları, kimlikler, sayfa/slayt sayıları,
metrik rakamları.

**Ölçek** (1.250 major third, 16px taban). Adımlar `apps/web/app/globals.css` içinde
`@theme inline` altında `--text-*` ve `--text-*--line-height` olarak **tanımlıdır**;
tanımlanmazsa Tailwind kendi varsayılan ölçeğini uygular ve buradaki tablo kâğıt üstünde
kalır:

| Token | Boyut / Satır | Kullanım |
|---|---|---|
| `text-xs` | 12 / 16 | Zaman damgası, kimlik, sayfa numarası rozeti, kırıntı yolu |
| `text-sm` | 14 / 20 | Arayüzün taşıyıcı boyu: etiket, buton, tablo hücresi, mesaj |
| `text-base` | 16 / **26** | Asistan cevabı. Uzun okuma için satır yüksekliği bilinçli yüksek |
| `text-lg` | 20 / 28 | Soru metni (sınav, soru havuzu), kart başlığı |
| `text-xl` | 25 / 32 | Tanımlı; sayfa başlığı için hedef boy (aşağıdaki nota bak) |
| `text-2xl` | 31 / 38 | Metrik rakamı, boş durum başlığı |
| `text-3xl` | 39 / 44 | Sayfa başlığının bugünkü boyu |

**Sayfa başlığı kararı:** `PageHeader` ana sayfalarda küçük ekranda `text-2xl`, geniş
ekranda `text-3xl`; yoğun Bilgi İşlem başlıklarında `compact` seçeneğiyle `text-xl` /
`text-2xl` kullanır. Yeni ekran kendi başlık boyunu seçmez, bu bileşeni kullanır.

**Ölçek dışı tek istisna:** giriş ekranı başlığı `text-5xl md:text-6xl` (48 / 60px)
kullanır ve bu iki adım bilerek token'lanmadı. Gerekçe: ölçeğin beşinci ve altıncı
adımları 48.8 ve 61.0px'tir — mevcut 48/60 zaten %2 içinde oturuyor, ama `--text-5xl`'i
61px'e taşımak 375px genişlikte başlığı taşırır. Ürün içinde başka hiçbir ekran display
boyu kullanmaz; yeni ekran da kullanmayacak.

**Satır uzunluğu:** okuma alanlarında `max-width: 70ch`. Ders materyalinden gelen uzun
paragraflar tam genişlikte akarsa göz satır başını kaybeder.

**Yasaklar:** Em dash (—) UI metninde kullanılmaz, Türkçe'de yaygın değil. Metin
gradyanı yok. Büyük harfe zorlama (`text-transform: uppercase`) yok — Türkçe'de `i → İ`
dönüşümü tarayıcıya göre bozulur.

---

## Layout

**Boşluk ölçeği:** 4px tabanlı — `1(4) 2(8) 3(12) 4(16) 6(24) 8(32) 12(48) 16(64)`.
Ara değer icat edilmez.

**Uygulama iskeleti — 14 Eylül 2026 kabuğu** (`components/app-shell.tsx` +
`components/course-nav.tsx`):

```
┌────────────────────────────────────────────────────────────┐
│ Üst çubuk 64px, yapışkan, beyaz — marka kilidi · tema · hesap · çıkış │
├────────────────────────────────────────────────────────────┤
│  max-width 1280px, ortalı; lg: [15rem menü kartı | içerik], boşluk 32px │
│  ┌──────────┐  ┌──────────────────────────────────────┐    │
│  │ ⌂ Genel  │  │ Ders sekme şeridi (çukur pist, beyaz  │    │
│  │ ▯ Dersler│  │ aktif hap)                             │    │
│  │ ◯ Profil │  ├──────────────────────────────────────┤    │
│  └──────────┘  │ İçerik: kanvas üstünde yüzen beyaz    │    │
│   yüzen beyaz  │ kartlar                                │    │
│   kart, sticky └──────────────────────────────────────┘    │
├────────────────────────────────────────────────────────────┤
│ < lg: alt gezinme çubuğu (ikon üstte, etiket altta), sabit │
└────────────────────────────────────────────────────────────┘
```

**Yan menü kararının tarihçesi.** 9 Ağustos'ta 240px yan menü reddedilmiş, 20 Ağustos'ta
tam boy mürekkep rayı gelmiş, 14 Eylül'de ürün sahibi rayı üniversitenin kendi uygulaması
yanında "kaba" bulup açık kabuğu istemişti (bkz. §Components "Kabuk ve kural
değişikliği"). Bugünkü hâl: masaüstünde **yüzen beyaz menü kartı** (15rem, `sticky
top-24`, yalnız üst düzey dört bağlantı), mobilde **alt gezinme çubuğu**. İki gramer
değil tek gramerin iki kırılımı: aynı `MainNavigation` bileşeni, aynı `aria-label`
çifti ("Ana menü" / "Mobil ana menü"), aynı href ve etiketler. Ders içi dallanma hâlâ
sekme şeridindedir; menü kartına ders sekmesi eklenmez.

**Sohbet ekranı istisnası:** masaüstünde iki sütun — solda konuşma, sağda kaynak paneli
(360px). Okuma genişliği `prose-tr` (70ch) ile metin bloğunun kendisinde sınırlanır.
Mobilde kaynak paneli konuşmanın **altına iner, gizlenmez**; kaynağı gizlemek ürünün ana
vaadini gizlemek olur. *Açılır kapanır (accordion) bölüm hâline getirilmedi — istiflenmiş
hâli zaten "gizlenmez" kuralını karşılıyor; katlanabilirlik gerekirse ayrıca karara bağlanır.*

---

## Elevation & Depth

Neredeyse düz — ama düz DEĞİL. Gölge bir dekorasyon değil, **katman sinyali**:

| Seviye | Token | Ne zaman |
|---|---|---|
| 0 | yok | Liste satırı, şerit — kenarlıkla ayrılır |
| 1 | `shadow-e1` | İçerik kartı; yapışkan üst çubuk kaydırıldığında |
| 2 | `shadow-e2` | Açılır menü, popover |
| 3 | `shadow-e3` | Modal |

Seviyeler `--elev-1/2/3` olarak token'landı (16 Ağustos); bileşende ham gölge değeri
yazılmaz. Gölge **sıcak tonludur** — metin renginin (28 25 23) saydamı. Saf siyah gölge
kemik kanvasın üstünde kirli gri görünür.

Koyu temada gölge görünmez; katmanı üstteki 1px **iç aydınlatma** taşır
(`inset 0 1px 0 rgb(245 244 242 / .04)`) — fiziksel kenar refraksiyonu.

Yapışkan üst çubuğun "kaydırıldığında" koşulu JS'siz kurulur: CSS scroll-driven
animation (`animation-timeline: scroll()`), çünkü `window.addEventListener('scroll')`
bu depoda yasaktır ve React state'i her karede yeniden render ederdi. Desteklemeyen
tarayıcıda çubuk kenarlıkla ayrık kalır (fail-soft).

---

## Shapes

14 Eylül 2026 ölçeği: `4px` (rozet, etiket) · `8px` (sekme hapı, menü satırı içi küçük
öğeler) · `12px` (buton, girdi, seçim kutusu, menü satırı) · `16px` (kart, panel, menü
kartı, sekme pisti, diyalog) · `radius-full` (avatar, hesap hapı, durum noktası).
`ui.tsx` bu ölçeği taşır; sayfa kendi köşe yarıçapını icat etmez.

Kenarlık daima `1px` ve yalnız kontrol sınırında (`--border-strong`) ya da düz kart
varyantında (`--border`). Kartın varsayılanı **kenarlıksız + `shadow-e1`**; katman
kenarlıktan değil gölgeden okunur. Kalın çerçeve ve renkli dikey ray yok — sayfa
başlığındaki 2px kırmızı ray 14 Eylül'de kaldırıldı.

---

## Components

### Kaynak kartı — ürünün imza bileşeni

Sistemin tüm tezi "her cevap gerçek bir sayfaya dayanır." Bu yüzden kaynak, cevabın
altına iliştirilmiş bir dipnot **değil**, cevapla eşit ağırlıkta bir bileşendir.

```
┌─────────────────────────────────────────┐
│ 📄 os_hafta3.pdf          ·  Sayfa 12   │   ← dosya adı + konum, tıklanabilir
│ ─────────────────────────────────────── │
│ "Deadlock için dört Coffman koşulunun   │   ← modelin dayandığı gerçek metin
│  birlikte sağlanması gerekir."          │
└─────────────────────────────────────────┘
```

Kurallar: konum bilgisi (`Sayfa 12` / `Slayt 7` / bölüm adı) **her zaman görünür**;
alıntı metni chunk'tan birebir gelir, model tarafından yeniden yazılmaz; karta tıklamak
belgenin o sayfasını açar.

### Kabuk ve kural değişikliği — 14 Eylül 2026, 14:30 (ürün sahibi kararı)

Ürün sahibi, mürekkep rayı ve kenarlıksız-ikonsuz gramerle çıkan sonucu üniversitenin
kendi mobil uygulamasının (DOU Kampüs) yanında "kaba ve katı" buldu ve engelleyen
kuralların kaldırılmasını istedi. Değişen kurallar, gerekçesiyle:

- **Mürekkep rayı kaldırıldı.** Kabuk artık açık: üstte ince beyaz başlık çubuğu
  (marka kilidi + hesap), masaüstünde solda **beyaz, yüzen menü kartı** (`rounded-2xl
  shadow-e1`), mobilde **alt gezinme çubuğu**. Aktif satır yumuşak kırmızı ton
  (`bg-brand-subtle text-brand`) — "aktif gezinme" kırmızının üç meşru kullanımından
  biridir. 20 Ağustos'taki ray kararı bu satırla geri alındı.
- **İkon seti serbest.** `components/icons.tsx`: elle yazılmış, 24px ızgara, 1.75 kalınlık,
  hepsi `aria-hidden`; anlam her zaman yanındaki metinden gelir. Bağımlılık eklenmedi
  (manifest kilidi duruyor); ikon kütüphanesi kararı Known Gaps'te kalır.
- **Kanvas nötr açık gri** `#f3f4f6`, çukur yüzey `#e9eaee`; beyaz kart gölgeyle yüzer,
  kenarlık taşımaz. Oranlar `scripts/contrast.mjs` ile yeniden ölçülür; kırmızıya
  yaklaşan çift metin koyultularak çözülür, yüzey açılmaz.
- **Köşeler:** buton/girdi 12px, kart ve panel 16px, rozet 4px. §Shapes buna göre okunur.
- **Tipografi:** `text-xs` 13px, `text-sm` 15px; ölçek başlıkta aynı.

Uygulama notu (aynı gün, ölçülmüş):
- Kanvas inince `--fg-subtle` (#726b66) çukurda 4.36:1, `--warning` (#956400) 4.26:1 ile
  eşiğin altına düştü; `contrast.mjs` yakaladı. İkisi de koyultuldu: `#6b645f`
  (5.28 / 5.81 / 4.83) ve `#8a5c00` (5.28 / 5.81 / 4.84). Yüzeyler açılmadı.
- Tailwind v4 çıktısında `.p-0`, `.p-6`'dan **önce** basılıyor: `<Card className="p-0">`
  kart dolgusunu ezmez (derlenmiş CSS'te ölçüldü). Dolgusuz liste kartı
  `<Card padding="none">` ile çizilir; dolgu kararı sınıf çakışmasına değil
  açık bir prop'a bağlıdır. className ile `p-0`/`px-0 py-0` geçilmez.
- Yüzen ders asistanı düğmesi mobilde alt gezinme çubuğunun üstünde durur
  (`bottom: calc(4.75rem + safe-area)`), `lg`'de köşeye iner.

### Aksan disiplini ve katman — 14 Eylül 2026 turu

Ölçülen belirti: bir sayfada aynı anda kırmızı sayfa rayı, kırmızı blok rayı, kırmızı
`eyebrow` etiketi, kırmızı mono ders kodu, yedi kırmızı satır içi bağlantı ve kırmızı buton
vardı; kırmızı artık "buraya bas" demiyordu. Aynı sayfada dört metrik 1px saç çizgileriyle
bölünmüş kenarlıklı bir ızgaradaydı ve tarayıcının yerli `<select>`'i formu üniversite
portalı gibi gösteriyordu. Kurallar buna göre sıkılaştırıldı:

- **Kırmızı üç yerde:** marka işareti, aktif gezinme çizgisi, sayfadaki **tek** birincil
  eylem. Sayfa başlığındaki 2px ray bir süre istisna olarak kaldı; 14:30 kabuk kararıyla
  o da kaldırıldı — blok içi kırmızı ray, kırmızı eyebrow, kırmızı ders kodu ve kırmızı
  satır içi bağlantı **yok**.
  `PageHeader.eyebrow` artık `--fg-muted` renginde çizilir.
- **Katman, çizgi yerine:** bilgi ailesi tek yükselmiş yüzeyde (`rounded-xl bg-surface
  shadow-e1`, kenarlıksız); alt bilgi çukur yüzeyde (`bg-surface-sunken`); saç çizgisi
  ızgarası yalnız gerçek liste satırlarında.
- **Rakamlar:** `font-mono` değil `tabular-nums`; metrik değeri `text-3xl`, etiket
  `text-xs` (`components/portal/portal-metrics.tsx`).
- **Seçim kutusu:** `components/ui.tsx` → `Select`. Yerli `<select>` semantiği (klavye,
  ekran okuyucu, form) korunur; `appearance-none` ile kabuk `Input` ile aynı ölçüde, ok
  işareti iki kenarlıklı döndürülmüş kare (elle SVG yok). Ham `<select>` yazılmaz.
- **Satır içi eylem:** düz metin bağlantı değil `Button size="sm"` (secondary/ghost/danger).

### Ders sekme şeridi — ürünün tek gezinme grameri

Yan menü yerine seçilen desen (bkz. §Layout). Ders içi altı bölüm tek bir yatay şeritte
durur: Materyaller · Asistan · Sınav provası · Soru havuzu · İlerleme · Katılımcılar.

```
╭──────────────────────────────────────────────────────╮   ← pist: --surface-sunken, 16px köşe
│ ┌───────────┐                                        │
│ │Materyaller│  Asistan   Sınav provası   İlerleme    │   ← aktif: beyaz hap + e1 gölge
│ └───────────┘                                        │
╰──────────────────────────────────────────────────────╯
```

Kurallar (14 Eylül 2026 hâli):
- Aktif sekme **beyaz hap** (`bg-surface shadow-e1 text-fg`), pasif `--fg-muted`; şerit
  tek başına kırmızı taşımaz. Aktif gezinmenin kırmızısı üst düzey menüde (`app-shell`)
  kullanılır; aynı sayfada iki kırmızı gezinme göstergesi olmaz.
- Aktif sekme ayrıca `aria-current="page"` taşır — işaret yalnız renkle verilmez.
- Yalnız eğitmene açık sekmeler (Soru havuzu, Katılımcılar) öğrencide **hiç render
  edilmez**; devre dışı görünen sekme yoktur (etkin görünüp iş yapmayan öğe kusurdur).
- `lg` ve üstünde şerit **sarar** (`flex-wrap`), altında yatay kayar; kaydırma çubuğu
  gizlidir (`scrollbar-width: none`), dokunma/tekerlek kaydırması korunur. Ders içi
  sekmeler mobilde alt gezinme çubuğuna taşınmaz — alt çubuk yalnız üst düzey dört
  bağlantıyı taşır.

### Abstention (kapsam dışı) durumu — hata gibi görünmemeli

**En kritik tasarım kararı.** Sistem "yüklenen materyallerde bu sorunun cevabı yok"
dediğinde bu bir **başarıdır**, arıza değil. Kırmızı, ünlem işareti veya uyarı üçgeni
kullanılırsa öğrenci sistemin bozuk olduğunu sanır ve genel bir yapay zekâya kaçar —
ürünün varlık sebebi çöker.

Bu yüzden: nötr yüzey (`--surface`), bilgi ikonu, sakin ton. Yanında **her zaman** bir
sonraki adım önerilir ("soruyu farklı ifade et" / "eğitmene sor"). Rengi `--danger`
değil `--fg-muted`.

### Sokratik ipucu merdiveni

Dört kademe (`NUDGE → CONCEPT_HINT → SIMILAR_EXAMPLE → EXPLAIN_WITH_SOURCE`) görsel
olarak **ilerleyen** bir yapı: her ipucu bir öncekinin altında kalır, silinmez. Öğrenci
nereden geldiğini görür. Kademe göstergesi ilerleme çubuğu değil, ayrık noktalar —
"4 adımda biter" hissi vermek, düşünmeyi hızlandırma baskısı yaratır.

Doğrudan cevap butonu **yoktur**. Kademe atlanmaz.

### Sınav ekranı

Sayaç sağ üstte, `text-sm`, nötr renk. Son 60 saniyede `--warning`'e döner — kırmızı
yanıp sönme yok, panik üretir. Soru metni `text-lg`, şıklar arasında bol boşluk
(yanlış tıklama sınav kaygısını artırır). İlerleme "3/10" biçiminde sayısal.

### Yükleme ve işlenme durumu

`uploaded → processing → completed | failed` durumları rozet olarak. `processing`
sırasında chunk bazlı ilerleme (`12/47 parça`) gösterilir — belirsiz spinner, dakikalar
süren ingestion'da "takıldı" hissi verir. `failed` durumunda ham hata değil, backend'in
ürettiği anlaşılır Türkçe mesaj gösterilir.

### Tasarım önizlemesi şeridi

Motoru henüz bağlanmamış ekranların üstünde duran dürüstlük sözleşmesi
(`components/page-state.tsx` → `PreviewBanner`): örnek veri gerçek cevap gibi
gösterilmez. Kapatılabilir değildir — kapatılabilen uyarı kapatılır, sonra unutulur.

Tonu **`--info`** (`bg-info-bg` + `text-info`), marka kırmızısı değil. Bir süre
`bg-brand-subtle` + `text-brand` kullanıyordu ve bu kırmızı kilidini kırıyordu:
"bu ekran henüz sahte veri gösteriyor" birincil eylem de, aktif navigasyon da,
kurumsal işaret de değildir. Ölçüldü: açık temada `--info` / `--info-bg` **4.98:1**,
koyu temada **7.06:1** — ikisi de AA. Şerit kenarı dekoratiftir, `--border` kullanır.

Bileşen bir ekran gerçek veriye bağlandığında **silinmez**, yalnız o ekrandan
kaldırılır: sıradaki yarım ekran aynı sözleşmeye ihtiyaç duyacak.

### Boş durumlar

Her liste boşken ne yapılacağını söyler: "Henüz ders materyali yok. PDF, sunum veya kod
dosyası yükleyerek başlayın." İllüstrasyon yok, tek cümle ve bir eylem butonu.

---

## Do's and Don'ts

**Yap**
- Kırmızıyı yalnız kurumsal vurgu ve birincil eylem için kullan
- Her kaynak göstergesinde sayfa/slayt numarasını görünür tut
- Uzun metinde satır uzunluğunu 70ch ile sınırla
- Her durumu renk + ikon + metin ile üçlü işaretle
- Türkçe metni tam yaz; kısaltma ve İngilizce terim karışımından kaçın
- Koyu temada marka rengini `#FF6B78`'e çevir

**Yapma**
- Gradyan (zemin, metin, buton — hiçbiri). *9 Ağustos 2026: giriş ekranındaki `.ambient`
  sınıfı iki radial-gradient uyguluyordu, kaldırıldı. Yasağa istisna açılmadı; gradyanlar
  ayrıca marka kırmızısının saydam tonuydu ve kırmızının üç meşru kullanımı arasında
  "dekoratif zemin lekesi" yok.*
- Dekoratif animasyon, parallax, 3B öğe
- Kırmızıyı hata rengi olarak kullanma
- Abstention'ı uyarı/hata gibi gösterme
- Kaynak kartını mobilde gizleme
- Sınav sayacını yanıp söndürme
- `uppercase` dönüşümü (Türkçe `i/İ` bozulur)
- Placeholder metni etiket yerine kullanma (odaklanınca kaybolur)

---

## Responsive Behavior

Kırılım noktaları: `sm 640` · `md 768` · `lg 1024` · `xl 1280`.

- **< 768px:** Ders sekme şeridi yerinde kalır ve gerekiyorsa yatay kayar — alt gezinme
  çubuğu **yoktur** (§Layout kararı). Sohbetteki kaynak paneli konuşmanın altına iner.
  Eğitmen tabloları kart listesine dönüşür.
- **≥ 1024px:** Sohbet iki sütun, kaynak paneli sağda 360px sabit.

Dokunma hedefi en az 44×44px. Öğrenci ekranları öncelikle mobilde tasarlanır (gece
telefonla çalışma senaryosu), eğitmen paneli masaüstü öncelikli.

---

## Iteration Guide

1. Önce bu belgeye bak; token varsa kullan.
2. Token yoksa **buraya ekle**, sonra kullan. Bileşen içinde ham hex yazma.
3. Yeni bir bileşen tipi mi? Önce "Components" altına davranışını yaz, sonra kodla.
4. Kontrast oranı iddia edilecekse ölçülür, tahmin edilmez:
   `cd apps/web && node scripts/contrast.mjs` (metin AA 4.5:1'i **veya** metin dışı
   arayüz öğesi 1.4.11 3:1'i geçmezse çıkış kodu 1), `--md` ile §Colors tabloları
   yeniden üretilir. Token değeri değiştiren bu iki adımı atlayamaz — tabloda ölçümsüz
   bir sayı kalırsa belge yalan söylüyor demektir.
   Yeni bir kontrol sınırı token'ı eklenirse betiğin `NON_TEXT` listesine de eklenir;
   listede olmayan öğe ölçülmez, ölçülmeyen öğe sessizce bozulur.
5. `minimalist-ui` skill'i bu belgeye tabidir; çelişirse bu belge kazanır.

---

## Known Gaps

Bilinçli olarak henüz karara bağlanmadı:

- **İkon seti** — 14 Eylül'den beri `components/icons.tsx`'te elle yazılmış sekiz ikon
  var (24px, 1.75). Kütüphaneye geçiş (Lucide/Phosphor) manifest kilidi yüzünden bekliyor;
  geçilirse aynı ızgara ve kalınlık korunur.
- **Marka kırmızısının resmî değeri** — iki logo iki ton veriyor (`#C50C1F`, `#D60825`).
  Üniversitenin kurumsal kimlik kılavuzu bulunursa oradan sabitlenmeli.
- **Grafik/analitik renkleri** — eğitmen panelindeki kategorik palet tanımlanmadı; konu
  hâkimiyeti çubuğu şimdilik `--fg-subtle` dolgusu kullanıyor (nötr, bilgi uzunlukta).
- **Hareket süreleri** — hâlâ token'lanmadı. Kodda fiilen iki süre var: giriş animasyonu
  600ms (`.rise`, `prefers-reduced-motion`'da kapanır) ve durum geçişleri 200ms. Token
  adı verilene kadar bu iki sayı dışında süre kullanılmaz.
- **`--danger-bg` ile `--brand-subtle` çakışması** — ölçüldü ve §Colors altındaki
  "Karşılanmayan eşikler" kaydında gerekçesiyle duruyor; karar bekliyor.

*(Kapandı: **kenarlık kontrastı** — `--border-strong` iki temada da 3:1'i geçiyor ve
`contrast.mjs` artık bunu kapıya bağlıyor. Bkz. §Colors "Metin olmayan arayüz öğeleri".)*

*(Kapandı: **yazı tipi barındırma** — Geist + Geist Mono `next/font/google` ile derlemede
yerelleştiriliyor, çevrimdışı demo CDN'e bağlı değil. Bkz. §Typography.)*
