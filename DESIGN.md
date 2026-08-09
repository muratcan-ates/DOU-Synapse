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

**Tasarım brief'i tek cümlede:** Sakin, okunur, kurumsal. Etkileyici değil **güvenilir**
görünmeli — çünkü ürünün iddiası "bu cevabın kaynağı şu sayfa" ve güven, görsel
gösterişten değil tutarlılıktan gelir.

**Üç dial** (taste-skill terminolojisi):

| Dial | Ayar | Neden |
|---|---|---|
| VARIANCE | Düşük | Her ekran aynı gramerle konuşmalı; öğrenci arayüzü öğrenmekle uğraşmamalı |
| MOTION | Çok düşük | Sınav ekranında animasyon kaygı üretir; hareket yalnız durum değişimini bildirir |
| DENSITY | Orta | Uzun okuma seansları sıkışık arayüzü kaldırmaz; ama eğitmen tabloları da kompakt olmalı |

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
cd apps/web && node scripts/contrast.mjs        # kontrol; bir metin çifti AA'yı geçmezse çıkış kodu 1
cd apps/web && node scripts/contrast.mjs --md   # aşağıdaki oran sütunlarını yeniden üretir
```

Token değeri değiştiren, bu tabloları `--md` çıktısıyla günceller. Eşikler: normal metin
**4.5:1**, 18.66px+ kalın / 24px+ metin **3:1**. Bu üründe bilgi taşıyan metnin çoğu 12px
ve 14px'tir, yani neredeyse her şey 4.5:1 sınıfındadır — "küçük yazı zaten dekoratif"
kaçamağı burada geçerli değil. Son ölçüm: **9 Ağustos 2026**.

### Açık tema

Kanvas saf beyaz değil kemik (`--bg`), kartlar beyaza **yükselir** (`--surface`) — kâğıt
üstünde kâğıt. Bu yüzden metin için en kötü zemin `--surface` değil `--bg`'dir ve eşik
ona göre kurulur.

| Token | Değer | Kullanım | `--bg` (#fbfbfa) | `--surface` (#ffffff) |
|---|---|---|---|---|
| `--fg` | `#1c1917` | Gövde metni | 16.89:1 AA | 17.49:1 AA |
| `--fg-muted` | `#57534e` | İkincil metin, etiket, alıntı | 7.37:1 AA | 7.63:1 AA |
| `--fg-subtle` | `#78716c` | Zaman damgası, kimlik, kırıntı yolu | 4.63:1 AA | 4.80:1 AA |
| `--brand` | `#c50c1f` | Birincil buton, aktif sekme | 5.88:1 AA | 6.09:1 AA |
| `--brand-strong` | `#a00a19` | Hover, basılı durum | 7.95:1 AA | 8.23:1 AA |
| `--success` | `#346538` | Hazır, onaylandı, doğru | 6.62:1 AA | 6.85:1 AA |
| `--warning` | `#956400` | İşleniyor, geliştirilmeli | 4.95:1 AA | 5.12:1 AA |
| `--danger` | `#9f2f2d` | Gerçek hata, yıkıcı eylem | 6.95:1 AA | 7.20:1 AA |
| `--info` | `#1f6c9f` | Kaynak referansı, taslak | 5.48:1 AA | 5.67:1 AA |

Zeminler ve kenarlıklar (metin değil; üstlerindeki metnin oranı yukarıdaki iki sütunda,
kenarlığın kendi oranı "Karşılanmayan eşikler" başlığında):

| Token | Değer | Kullanım |
|---|---|---|
| `--bg` | `#fbfbfa` | Sayfa zemini |
| `--surface` | `#ffffff` | Kart, panel, girdi |
| `--border` | `rgba(28,25,23,.08)` | Ayraç, kart kenarı |
| `--border-strong` | `rgba(28,25,23,.14)` | Girdi, ikincil buton, kesik çerçeve |
| `--brand-subtle` | `#fdebec` | Rozet ve şerit zemini, avatar |
| `--success-bg` `--warning-bg` `--danger-bg` `--info-bg` | `#edf3ec` `#fbf3db` `#fdebec` `#e1f3fe` | Durum rozeti zeminleri |

### Koyu tema

Koyu tema **zorunludur**, süs değil: öğrenciler geceleri çalışıyor.

Ölçülmüş kısıt: ham marka kırmızısı `#c50c1f`, koyu zemin üstünde 3:1'in altında kalır —
okunmaz. Koyu temada marka rengi mutlaka açılır. Koyu temada yüzey **açılarak** yükselir,
bu yüzden en kötü zemin `--surface`'tır.

| Token | Değer | `--bg` (#191715) | `--surface` (#211f1c) |
|---|---|---|---|
| `--fg` | `#f5f4f2` | 16.26:1 AA | 14.96:1 AA |
| `--fg-muted` | `#b0aaa4` | 7.77:1 AA | 7.15:1 AA |
| `--fg-subtle` | `#8f8a84` | 5.22:1 AA | 4.80:1 AA |
| `--brand` | `#ff6b78` | 6.49:1 AA | 5.97:1 AA |
| `--brand-strong` | `#ffa1aa` | 9.30:1 AA | 8.56:1 AA |
| `--success` | `#7bc47f` | 8.55:1 AA | 7.86:1 AA |
| `--warning` | `#d9a23d` | 7.82:1 AA | 7.19:1 AA |
| `--danger` | `#f08c8a` | 7.51:1 AA | 6.91:1 AA |
| `--info` | `#6fb4dd` | 7.87:1 AA | 7.24:1 AA |

Zeminler: `--bg #191715` · `--surface #211f1c` · `--border rgba(245,244,242,.08)` ·
`--border-strong rgba(245,244,242,.16)` · `--brand-subtle #3a1a1e` ·
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

### Karşılanmayan eşikler — kayıt, iddia değil

Aşağıdakiler ölçüldü, geçemedi ve **bilerek** böyle bırakıldı. `contrast.mjs` her koşuda
basar ama çıkış koduna dahil etmez; kapıyı genişletmeden önce buradaki kayıt güncellenir.

- **Kenarlık kontrastı (WCAG 1.4.11, 3:1).** `--border-strong`, `--surface` üstünde açık
  temada **1.33:1**, koyu temada **1.62:1**. Girdi ve ikincil butonun görünür sınırı
  yalnız bu kenarlıktır (girdi zemini `--surface`, sayfa zemini `--bg`; ikisi arasında
  1.04:1 var, yani zemin farkı sınır işi görmez). Yükseltilmedi çünkü 3:1'lik bir kenarlık
  ürünün kılcal kenarlık dilini kalınlaştırır ve §Elevation'ın dayandığı düz görünümü
  bozar. Bu bir tasarım kararıdır; verilmedi, ertelendi.
- **`--danger-bg` ile `--brand-subtle` açık temada aynı değer** (`#fdebec`). "Başarısız"
  rozetinin zemini marka rozetinin zeminiyle birebir aynı; ayrım metin renginden ve
  etiketten geliyor. Ayrıştırma denendi: kırmızı ailesinde kalan adaylarla iki zemin
  arasındaki oran 1.02:1'de kaldı — göz ayırt etmez, yani hex'i değiştirmek yalnız
  "düzelttik" demeye yarardı. Gerçek çözüm `--danger`'ı kırmızı ailesinden çıkarmaktır
  ve bu bir renk kararı, düzeltme değil.

**Renk tek başına bilgi taşımaz.** Her durum ayrıca ikon veya metinle işaretlenir; renk
körlüğü ve düşük kontrastlı ekranlar için gereklidir. Yukarıdaki iki kayıt da bu kurala
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
| `text-xl` | 25 / 32 | Ölçekte tanımlı, henüz kullanılmıyor |
| `text-2xl` | 31 / 38 | Metrik rakamı (`MetricRow`) |
| `text-3xl` | 39 / 44 | Sayfa başlığı (`PageHeader`) |

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

**Uygulama iskeleti** (`components/app-shell.tsx` + `components/course-nav.tsx`):

```
┌──────────────────────────────────────────────────┐
│ Üst çubuk 56px, yapışkan — DOU Synapse · kullanıcı · çıkış │
├──────────────────────────────────────────────────┤
│  max-width 1200px, ortalı, yatay boşluk 16px      │
│  ┌────────────────────────────────────────────┐  │
│  │ Ders sekme şeridi — altı kenarlıkla ayrık   │  │
│  ├────────────────────────────────────────────┤  │
│  │ İçerik                                      │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

**240px yan menü kararı geri alındı (9 Ağustos 2026).** Belge önce üst çubuk + sol yan
menü tarif ediyordu; uygulama yan menü yerine ders içi yatay sekme şeridiyle yazıldı ve
altı ekranın hepsi o desende. Belge koda çekildi, çünkü: gezinme yalnız ders içinde
dallanıyor (altı sekme), 240px sabit sütun 1200px kanvasın beşte birini kalıcı olarak
harcıyor ve okuma alanını daraltıyor; ayrıca yan menü mobilde ikinci bir desen (alt
gezinme) daha gerektiriyordu — VARIANCE=düşük dial'i iki gezinme grameri kaldırmaz.
Yan menü **uygulanmadı ve uygulanmayacak**; bu satır o kararın kaydıdır.

**Sohbet ekranı istisnası:** masaüstünde iki sütun — solda konuşma, sağda kaynak paneli
(360px). Okuma genişliği `prose-tr` (70ch) ile metin bloğunun kendisinde sınırlanır.
Mobilde kaynak paneli konuşmanın **altına iner, gizlenmez**; kaynağı gizlemek ürünün ana
vaadini gizlemek olur. *Açılır kapanır (accordion) bölüm hâline getirilmedi — istiflenmiş
hâli zaten "gizlenmez" kuralını karşılıyor; katlanabilirlik gerekirse ayrıca karara bağlanır.*

---

## Elevation & Depth

Neredeyse düz. Gölge bir dekorasyon değil, **katman sinyali**:

| Seviye | Gölge | Ne zaman |
|---|---|---|
| 0 | yok | Kartlar, paneller — kenarlıkla ayrılır |
| 1 | `0 1px 2px rgb(0 0 0 / .06)` | Yapışkan üst çubuk, kaydırıldığında |
| 2 | `0 8px 24px rgb(0 0 0 / .12)` | Açılır menü, popover |
| 3 | `0 16px 48px rgb(0 0 0 / .18)` | Modal |

Koyu temada gölge yerine yüzey rengi bir kademe açılır; koyu zeminde gölge görünmez.

---

## Shapes

`radius-sm: 4px` (rozet, etiket) · `radius-md: 8px` (buton, girdi, kart) ·
`radius-lg: 12px` (modal, geniş panel) · `radius-full` (yalnız avatar ve durum noktası).

Kenarlık daima `1px`. Kalın kenarlık yok.

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

### Ders sekme şeridi — ürünün tek gezinme grameri

Yan menü yerine seçilen desen (bkz. §Layout). Ders içi altı bölüm tek bir yatay şeritte
durur: Materyaller · Asistan · Sınav provası · Soru havuzu · İlerleme · Katılımcılar.

```
 Materyaller   Asistan   Sınav provası   İlerleme
 ──────────                                        ← aktif: 2px kırmızı alt çizgi
────────────────────────────────────────────────   ← şerit altı 1px --border
```

Kurallar:
- Aktif sekme kırmızının **üç meşru kullanımından biridir** (aktif navigasyon göstergesi):
  2px `--brand` alt çizgi + `--fg` metin + `font-medium`. Pasif sekmeler `--fg-muted`.
- Aktif sekme ayrıca `aria-current="page"` taşır — işaret yalnız renkle verilmez.
- Yalnız eğitmene açık sekmeler (Soru havuzu, Katılımcılar) öğrencide **hiç render
  edilmez**; devre dışı görünen sekme yoktur (etkin görünüp iş yapmayan öğe kusurdur).
- Şerit her genişlikte aynıdır; taşarsa yatay kayar (`overflow-x-auto`). Mobilde alt
  gezinme çubuğuna dönüşmez — ikinci bir gezinme grameri yok.

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
   `cd apps/web && node scripts/contrast.mjs` (metin AA'yı geçmezse çıkış kodu 1),
   `--md` ile §Colors tabloları yeniden üretilir. Token değeri değiştiren bu iki adımı
   atlayamaz — tabloda ölçümsüz bir sayı kalırsa belge yalan söylüyor demektir.
5. `minimalist-ui` skill'i bu belgeye tabidir; çelişirse bu belge kazanır.

---

## Known Gaps

Bilinçli olarak henüz karara bağlanmadı:

- **İkon seti** — Lucide muhtemelen (shadcn ile gelir), ama doğrulanmadı.
- **Marka kırmızısının resmî değeri** — iki logo iki ton veriyor (`#C50C1F`, `#D60825`).
  Üniversitenin kurumsal kimlik kılavuzu bulunursa oradan sabitlenmeli.
- **Grafik/analitik renkleri** — eğitmen panelindeki kategorik palet tanımlanmadı; konu
  hâkimiyeti çubuğu şimdilik `--fg-subtle` dolgusu kullanıyor (nötr, bilgi uzunlukta).
- **Hareket süreleri** — hâlâ token'lanmadı. Kodda fiilen iki süre var: giriş animasyonu
  600ms (`.rise`, `prefers-reduced-motion`'da kapanır) ve durum geçişleri 200ms. Token
  adı verilene kadar bu iki sayı dışında süre kullanılmaz.
- **Kenarlık kontrastı ve `--danger-bg` çakışması** — ikisi de ölçüldü ve §Colors
  altındaki "Karşılanmayan eşikler" kaydında gerekçesiyle duruyor; karar bekliyor.

*(Kapandı: **yazı tipi barındırma** — Geist + Geist Mono `next/font/google` ile derlemede
yerelleştiriliyor, çevrimdışı demo CDN'e bağlı değil. Bkz. §Typography.)*
