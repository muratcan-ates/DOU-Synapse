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

### Açık tema

| Token | Değer | Kullanım | Beyaz üstünde kontrast |
|---|---|---|---|
| `--brand` | `#C50C1F` | Birincil buton, aktif sekme, bağlantı | **6.09:1** ✓ AA |
| `--brand-strong` | `#A00A19` | Hover, basılı durum | **8.23:1** ✓ AAA |
| `--brand-subtle` | `#FEF2F3` | Seçili satır zemini, rozet zemini | — |
| `--fg` | `#1C1917` | Gövde metni | **17.49:1** ✓ AAA |
| `--fg-muted` | `#57534E` | İkincil metin, etiket | **7.63:1** ✓ AAA |
| `--fg-subtle` | `#78716C` | Yardım metni, zaman damgası | **4.80:1** ✓ AA |
| `--bg` | `#FFFFFF` | Sayfa zemini | — |
| `--surface` | `#FAFAF9` | Kart, panel | — |
| `--border` | `#E7E5E4` | Ayraç, kart kenarı | — |

### Koyu tema

Koyu tema **zorunludur**, süs değil: öğrenciler geceleri çalışıyor.

Ölçülmüş kısıt: ham marka kırmızısı `#C50C1F`, koyu zemin `#1C1917` üstünde yalnızca
**2.87:1** verir — okunmaz. Koyu temada marka rengi mutlaka açılır:

| Token | Değer | `#1C1917` üstünde |
|---|---|---|
| `--brand` | `#FF6B78` | **6.35:1** ✓ AA |
| `--fg` | `#F5F5F4` | **16.03:1** ✓ AAA |
| `--fg-muted` | `#A8A29E` | **6.93:1** ✓ AA |
| `--bg` | `#1C1917` | — |
| `--surface` | `#292524` | — |

### Semantik

| Token | Değer | Kontrast | Anlam |
|---|---|---|---|
| `--success` | `#15803D` | 5.02:1 ✓ | İşlem tamamlandı, doğru cevap |
| `--warning` | `#A16207` | 4.92:1 ✓ | İşleniyor, dikkat |
| `--danger` | `#B91C1C` | 6.47:1 ✓ | Gerçek hata, yıkıcı eylem |
| `--info` | `#1D4ED8` | 6.70:1 ✓ | Kaynak referansı, bilgilendirme |

**Renk tek başına bilgi taşımaz.** Her durum ayrıca ikon veya metinle işaretlenir; renk
körlüğü ve düşük kontrastlı ekranlar için gereklidir.

---

## Typography

**Gövde:** Inter. Seçim gerekçesi teknik: Türkçe için `ğ ş ı İ ö ü ç` glifleri tam ve
noktasız ı ile noktalı i ayrımı net. Sistem fontuna düşmek yerine değişken font yüklenir.

**Kod:** JetBrains Mono. Kod chunk'ları, dosya adları, `fork()` gibi teknik terimler.

**Ölçek** (1.250 major third, 16px taban):

| Token | Boyut / Satır | Kullanım |
|---|---|---|
| `text-xs` | 12 / 16 | Zaman damgası, sayfa numarası rozeti |
| `text-sm` | 14 / 20 | Etiket, tablo hücresi, yardım metni |
| `text-base` | 16 / **26** | Gövde. Uzun okuma için satır yüksekliği bilinçli yüksek |
| `text-lg` | 20 / 28 | Soru metni, kart başlığı |
| `text-xl` | 25 / 32 | Sayfa başlığı |
| `text-2xl` | 31 / 38 | Yalnız boş durum ekranları |

**Satır uzunluğu:** okuma alanlarında `max-width: 70ch`. Ders materyalinden gelen uzun
paragraflar tam genişlikte akarsa göz satır başını kaybeder.

**Yasaklar:** Em dash (—) UI metninde kullanılmaz, Türkçe'de yaygın değil. Metin
gradyanı yok. Büyük harfe zorlama (`text-transform: uppercase`) yok — Türkçe'de `i → İ`
dönüşümü tarayıcıya göre bozulur.

---

## Layout

**Boşluk ölçeği:** 4px tabanlı — `1(4) 2(8) 3(12) 4(16) 6(24) 8(32) 12(48) 16(64)`.
Ara değer icat edilmez.

**Uygulama iskeleti:**

```
┌────────────────────────────────────────────┐
│ Üst çubuk 56px — kurum işareti · ders · profil │
├──────────┬─────────────────────────────────┤
│ Yan menü │  İçerik                          │
│ 240px    │  max-width 1200px, ortalı        │
│ (mobilde │                                  │
│  gizli)  │                                  │
└──────────┴─────────────────────────────────┘
```

**Sohbet ekranı istisnası:** iki sütun. Solda konuşma (`max-width: 70ch`), sağda kaynak
paneli (360px). Mobilde kaynak paneli, cevabın altında açılır kapanır bölüme iner —
gizlenmez. Kaynağı gizlemek ürünün ana vaadini gizlemek olur.

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
- Gradyan (zemin, metin, buton — hiçbiri)
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

- **< 768px:** Yan menü alt gezinme çubuğuna iner. Sohbetteki kaynak paneli, cevabın
  altında açılır kapanır bölüm olur. Eğitmen tabloları kart listesine dönüşür.
- **≥ 1024px:** Sohbet iki sütun, kaynak paneli sabit.

Dokunma hedefi en az 44×44px. Öğrenci ekranları öncelikle mobilde tasarlanır (gece
telefonla çalışma senaryosu), eğitmen paneli masaüstü öncelikli.

---

## Iteration Guide

1. Önce bu belgeye bak; token varsa kullan.
2. Token yoksa **buraya ekle**, sonra kullan. Bileşen içinde ham hex yazma.
3. Yeni bir bileşen tipi mi? Önce "Components" altına davranışını yaz, sonra kodla.
4. Kontrast oranı iddia edilecekse ölçülür, tahmin edilmez.
5. `minimalist-ui` skill'i bu belgeye tabidir; çelişirse bu belge kazanır.

---

## Known Gaps

Bilinçli olarak henüz karara bağlanmadı:

- **İkon seti** — Lucide muhtemelen (shadcn ile gelir), ama doğrulanmadı.
- **Marka kırmızısının resmî değeri** — iki logo iki ton veriyor (`#C50C1F`, `#D60825`).
  Üniversitenin kurumsal kimlik kılavuzu bulunursa oradan sabitlenmeli.
- **Grafik/analitik renkleri** — eğitmen panelindeki kategorik palet tanımlanmadı;
  konu bazlı hakimiyet grafiği yapılırken eklenecek.
- **Yazı tipi lisansı/barındırma** — Inter self-host mu, CDN mi (çevrimdışı demo CDN'e
  bağımlı kalmamalı).
- **Hareket süreleri** — token'lanmadı; ilk bileşenlerde ölçülüp buraya yazılacak.
