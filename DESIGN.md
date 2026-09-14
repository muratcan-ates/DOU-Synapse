# DOU-Synapse — Tasarım Sistemi

Bu belge arayüzün tek otoritesidir. Bir bileşen yazılırken renk, boşluk veya tipografi
kararı burada aranır; burada yoksa önce buraya eklenir, sonra kullanılır.

Plan: [PLAN.md](PLAN.md) · Mimari: [ARCHITECTURE.md](ARCHITECTURE.md)

---

## Kampüs arayüzü revizyonu · 14 Eylül 2026

Bu bölüm ürün sahibinin aynı gün paylaştığı Doğuş mobil uygulaması ve LMS
referanslarına dayanan tam görsel revizyon kararıdır. Önceki sıcak stüdyo,
kompakt tipografi, kart sayısı ve gezinme şekli kısıtlarının yerine geçer.
Güvenlik, gerçek veri, kaynak gösterme ve erişilebilirlik kuralları korunur.

- DESIGN_VARIANCE: 4; MOTION_INTENSITY: 2; VISUAL_DENSITY: 4. Öğrenme odaklı,
  okunur bir üniversite ürünü; pazarlama sayfası veya deneysel sanat arayüzü değil.
- Serin açık gri kanvas, beyaz içerik yüzeyleri, koyu nötr metin; Doğuş kırmızısı
  eylem, etkin gezinme ve kurumsal başlıkta. Gece teması aynı hiyerarşiyi korur.
- Geist; ana metin 16px, yardımcı metin 14px, küçük etiket 13px. Sayfa başlığı
  28–32px, bölüm 20px. Dev başlıklar ve dekoratif mono etiketler kullanılmaz.
- Masaüstü 208px sol gezinme, 76px üst başlık; geniş ve rahat içerik alanı.
  Telefonda güvenli alanı hesaba katan yüzen alt menü, yatay kaydırılan ders
  sekmeleri, 16–20px sayfa dolgusu. Asistan ve menü birbirinin üstünü örtmez.
- İçerik paneli 20px, form ve düğme 12px, rozet 6px köşe. Hafif gölge;
  iç içe kart yerine bölüm başlıkları ve ayraçlı satırlar. Formlar 44px+ hedef.
- Gösterge paneli: selamlama, tek çalışma odağı, net ders satırları ve ikincil
  çalışma bilgisi. Aynı derse ait araçları ve ölçümleri iki büyük kartta tekrarlama.
- Profil: kurumsal başlık ve avatar, etiket/değer satırları. Görsellerdeki telefon,
  öğrenci numarası, kişi bilgisi, haber ve program verileri uygulamaya kopyalanmaz.
- Soru, sınav, materyal ve yönetim sayfaları aynı panel/başlık dilini kullanır.
  Sohbetin okuma alanı geniş; alıntılar, kapsam reddi ve sınav kilidi görünür.
- Yeni bağımlılık ve sahte veri eklenmez. Mevcut ikon ailesi ve marka işareti korunur.
  Kontroller, bağlantılar ve sunucunun belirlediği rol davranışları çalışmaya devam eder.
- Doğrulama: tür denetimi, mevcut birim testleri, kontrast, üretim derlemesi;
  masaüstü/375px, açık/koyu, klavye ve azaltılmış hareket için tarayıcı incelemesi.

## Görsel sistem

Bu dosya mevcut kampüs arayüzünün otoritesidir. Önceki sıcak stüdyo teması,
8px kart kilidi ve gezinme sınırlamaları kaldırılmıştır. Yeni kararlar, kullanıcının
14 Eylül 2026 tarihli tüm siteyi yenileme ve daha akıcı etkileşim isteğine dayanır.

- Zemin açık soğuk gri, içerik yüzeyleri beyazdır. Koyu temada aynı hiyerarşi korunur.
- Kırmızı ana eylem ve seçili konumu vurgular; başarı, uyarı ve hata kendi anlamlı renklerini kullanır.
- Geist ana yazı ailesidir; gövde 16px, kontroller 15px, yardımcı etiketler 13px.
- Sayfa başlığı 30–32px, bölüm başlığı 20–25px. Küçük ekranda başlıklar kısalır.
- Kart/panel 20px, kontrol 12px, rozet 6px köşe kullanır. Avatar daireseldir.
- Kartlar hafif gölgeyle zeminden ayrılır; alt gruplar ayraç veya çukur yüzeyle düzenlenir.
- Renk ve gölge kaynağı `apps/web/app/globals.css`; temel kontroller `components/ui.tsx` içindedir.

## Yerleşim ve gezinme

Masaüstünde 76px üst çubuk ve 208px yan menü bulunur. Menü 88px'e daraltılabilir;
seçili bölüm simgesi, erişilebilir adı ve klavye odağı korunur. İçerik en fazla
1440px genişlikte, 32px düşey ve 36px yatay boşlukla yerleşir.

1024px altında yan menü yerine altta yüzen gezinme kullanılır. Dar ekranda yatay
boşluk 16px, içerik alt payı 140px'tir. Sabit asistan ve politika eylemleri bu
gezinmenin üstünde kalır; panel kapatma ve kaydetme eylemleri erişilebilir olmalıdır.

Ders sekmeleri mobilde yatay kaydırılır. Masaüstünde yeterli alan varsa sarılır.
Uzun tablo ve kaynak içerikleri kendi alanında kayar; tüm sayfa yatay taşmaz.
Mobil yönetim tabloları anlamını koruyan etiket–değer satırlarına dönüşür.

## Ekran davranışları

Genel panel son çalışma alanı ve ders listesine doğrudan erişim verir. Tekrarlanan
istatistikler azaltılır; boş veya yüklenemeyen veri sıfır başarı gibi gösterilmez.
Dersler, kaynaklar ve üyelerde arama mevcut API kayıtlarını süzer. Sayfalama varsa
arama kapsamı belirtilir. Ürün dışı haber, takvim veya öğrenci bilgisi uydurulmaz.

Sohbet geniş bir okuma alanı, kaynak referansları ve çok satırlı düzenleyici kullanır.
Enter gönderir; Shift+Enter satır ekler; IME bileşimi sırasında gönderilmez.
Başlangıç önerisi yalnız düzenleyiciye taslak yerleştirir. Öğrenci kendi eylemiyle gönderir.
Sınavda soru numaraları arasında geçiş yapılabilir; cevaplar, süre ve sunucu kilitleri
mevcut sözleşmeyi izler. Eğitmen araçları yalnız ilgili ders rolüyle görünür.

## Hareket ve erişilebilirlik

Menü ve panel geçişleri kısa (150–320ms), işlevi açıklayan ve etkileşime bağlıdır.
Döngüsel dekorasyon, parallax ve otomatik kayan içerik kullanılmaz. Yükleme göstergesi
gerçek bekleyen işi belirtir. `prefers-reduced-motion` tüm animasyon/geçişleri azaltır.

Kontroller en az 44px dokunma hedefi taşır. Klavye odağı görünürdür; ikon düğmelerinin
adları vardır. Durum yalnız renkle anlatılmaz. Bekleyen gönderim odağı koruyan
`aria-disabled` davranışını kullanır; kapalı eylem tekrar çalıştırılmaz.

## Korunan ürün sınırları

Sunucu yetkilendirmesi, ders üyeliği, RLS, kaynak zorunluluğu, sınav kilidi,
öğrenci cevap gizliliği ve kişisel veri yaşam döngüsü tasarım kararıyla gevşetilmez.
Eğitmen görünümü öğrencinin özel sohbet metnini açmaz. Demo yanıt etiketi korunur.
Gerçek öğrenci bilgileri ve kullanıcının referans ekran görüntüleri depoya kopyalanmaz.

## Renk denetimi

Aşağıdaki tablolar `node apps/web/scripts/contrast.mjs --md` çıktısıdır.
Metin eşiği 4.5:1, bilgi taşıyan kontrol sınırı eşiği 3:1'dir. Dekoratif kart
ayracı kontrol sınırıyla aynı anlamı taşımaz. Bu ölçüm token çiftlerini doğrular;
tek başına tüm arayüz için erişilebilirlik sertifikası değildir.

### Açık tema

| Token | Değer | `--bg` (#f2f4f7) | `--surface` (#ffffff) | `--surface-sunken` (#e9edf2) |
|---|---|---|---|---|
| `--fg` | `#202432` | 14.02:1 AA | 15.44:1 AA | 13.13:1 AA |
| `--fg-muted` | `#555e6d` | 5.94:1 AA | 6.55:1 AA | 5.57:1 AA |
| `--fg-subtle` | `#626a77` | 4.95:1 AA | 5.46:1 AA | 4.64:1 AA |
| `--brand` | `#c50c1f` | 5.53:1 AA | 6.09:1 AA | 5.18:1 AA |
| `--brand-strong` | `#a00a19` | 7.47:1 AA | 8.23:1 AA | 7.00:1 AA |
| `--success` | `#346538` | 6.22:1 AA | 6.85:1 AA | 5.83:1 AA |
| `--warning` | `#8a5c00` | 5.28:1 AA | 5.81:1 AA | 4.95:1 AA |
| `--danger` | `#9f2f2d` | 6.53:1 AA | 7.20:1 AA | 6.12:1 AA |
| `--info` | `#1f6c9f` | 5.15:1 AA | 5.67:1 AA | 4.82:1 AA |

| Çift | Not | Oran |
|---|---|---|
| `--ink-fg / --ink` | #f2efe9 / #1a1613 | 15.67:1 geçti |
| `--ink-fg-muted / --ink` | #a8a099 / #1a1613 | 6.98:1 geçti |
| `--ink-fg / --ink-raised` | #f2efe9 / #241f1a | 14.23:1 geçti |
| `--brand-on-ink / --ink` | #ff6b78 / #1a1613 | 6.53:1 geçti |
| `--success / --success-bg` | #346538 / #edf3ec | 6.08:1 geçti |
| `--warning / --warning-bg` | #8a5c00 / #fbf3db | 5.25:1 geçti |
| `--danger / --danger-bg` | #9f2f2d / #fdebec | 6.26:1 geçti |
| `--info / --info-bg` | #1f6c9f / #e1f3fe | 4.98:1 geçti |
| `--brand / --brand-subtle` | #c50c1f / #fdebec | 5.30:1 geçti |
| `#ffffff / --brand` | birincil buton metni | 6.09:1 geçti |
| `--border-strong / --surface` | girdi/ikincil buton kenarlığı (kontrolün içi) | 3.13:1 geçti |
| `--border-strong / --bg` | girdi/ikincil buton kenarlığı (sayfa zemini) | 3.05:1 geçti |
| `--fg-subtle / --surface` | ilerleme çubuğu dolgusu (bg-fg-subtle) | 5.46:1 geçti |

### Koyu tema

| Token | Değer | `--bg` (#14171c) | `--surface` (#1d222a) | `--surface-sunken` (#101318) |
|---|---|---|---|---|
| `--fg` | `#f3f5f8` | 16.45:1 AA | 14.63:1 AA | 17.04:1 AA |
| `--fg-muted` | `#b6becb` | 9.59:1 AA | 8.53:1 AA | 9.94:1 AA |
| `--fg-subtle` | `#a1aab8` | 7.66:1 AA | 6.81:1 AA | 7.94:1 AA |
| `--brand` | `#ff6b78` | 6.52:1 AA | 5.80:1 AA | 6.76:1 AA |
| `--brand-strong` | `#ffa1aa` | 9.35:1 AA | 8.32:1 AA | 9.69:1 AA |
| `--success` | `#7bc47f` | 8.59:1 AA | 7.64:1 AA | 8.90:1 AA |
| `--warning` | `#d9a23d` | 7.86:1 AA | 6.99:1 AA | 8.14:1 AA |
| `--danger` | `#f08c8a` | 7.55:1 AA | 6.71:1 AA | 7.82:1 AA |
| `--info` | `#6fb4dd` | 7.91:1 AA | 7.04:1 AA | 8.20:1 AA |

| Çift | Not | Oran |
|---|---|---|
| `--ink-fg / --ink` | #f3f5f8 / #131110 | 17.24:1 geçti |
| `--ink-fg-muted / --ink` | #b6becb / #131110 | 10.06:1 geçti |
| `--ink-fg / --ink-raised` | #f3f5f8 / #1d1a17 | 15.86:1 geçti |
| `--brand-on-ink / --ink` | #ff6b78 / #131110 | 6.84:1 geçti |
| `--success / --success-bg` | #7bc47f / #1d2a1e | 7.16:1 geçti |
| `--warning / --warning-bg` | #d9a23d / #2b2312 | 6.79:1 geçti |
| `--danger / --danger-bg` | #f08c8a / #331a1c | 6.76:1 geçti |
| `--info / --info-bg` | #6fb4dd / #14232e | 7.06:1 geçti |
| `--brand / --brand-subtle` | #ff6b78 / #3a1a1e | 5.66:1 geçti |
| `bg / --brand` | birincil buton metni | 6.52:1 geçti |
| `--border-strong / --surface` | girdi/ikincil buton kenarlığı (kontrolün içi) | 3.10:1 geçti |
| `--border-strong / --bg` | girdi/ikincil buton kenarlığı (sayfa zemini) | 3.15:1 geçti |
| `--fg-subtle / --surface` | ilerleme çubuğu dolgusu (bg-fg-subtle) | 6.81:1 geçti |
