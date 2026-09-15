# UX Audit — 2026-09-14 (P5 şeridi)

> Kapsam: P5 şeridinin iki kayıtlı arayüz kusuru. Proje geneli erişilebilirlik
> denetimi değildir. §2'deki "KOŞULMADI" satırları o oturumun ortam engelini
> anlatır; §5 daha sonra ölçülen sonucu ayrı kayıt olarak ekler.

## 1) Kayıtlı kusurlar

### A. 375px koyu tema + profil çubuğu üst üste binmesi
- Hedef: profil özeti/isim etiketi ile çıkış butonunun çakışmasını önlemek.
- Uygulama: `apps/web/components/app-shell.tsx`
- Durum: **Önce/sonra fark kapatıldı**.

### B. Materyal ekranında asistan düğmeleri çakışması
- Hedef: materyal sayfasında `CourseAssistant` yerleşimini çakışma yapmayacak şekilde daraltmak.
- Uygulama: `apps/web/components/course-nav.tsx`
- Durum: **Önce/sonra fark kapatıldı**.

## 2) P0/P1 gözden geçirme
- Tam tur 375px + klavye: bu oturumda demo stack başlatılamadığı için **KOŞULMADI**.
- Ek koşul: `docker` yüklü olmadığı için `docker compose` ile üretimsel davranış doğrulama turu da **KOŞULMADI**.

## 3) Kayıtlar
- `before` / `after` görselleri: bu görevde demo/UI koşusu yapılamadığından ekran görüntüsü üretilemedi.
- Görsel klasörleri: `docs/images/jury-2026-09/`

## 4) Ek not
- Yeni bağımlılık eklenmedi, ikon kütüphanesi değişikliği yapılmadı.

## 5) 15 Eylül eki — §2'deki tur koşuldu (AYRI ÖLÇÜM)

§2'deki "KOŞULMADI" satırları **değiştirilmedi**; o oturumun kaydıdır. Aşağıdaki
ölçüm 15 Eylül 02:10'da, GPT'nin kampüs tasarımı birleştikten sonraki ağaçta
(`3f96d43`) yapıldı — yani P5 dönemindeki ağaç değil, daha yenisi.

Gerçek tarayıcı (Chrome), 375×812, koyu tema, `prefers-reduced-motion`:

| Ölçüm | Sonuç |
|---|---|
| Sohbet sayfası yatay taşma (onay kapalı) | yok — `scrollWidth` 375 / `innerWidth` 375 |
| Sohbet sayfası yatay taşma (onay açık) | yok — 375 / 375 |
| `/dashboard` mobil ana menüye klavyeyle erişim | **4 sekme** (regresyonda 30+ sekmede ulaşılamıyordu) |
| `/profile` mobil ana menüye klavyeyle erişim | 4 sekme |
| Odak halkası | `2px solid` |

§3'teki "ekran görüntüsü üretilemedi" satırı da aşıldı:
`docs/images/` altındaki 16 görüntü <!-- docs-check: tarihsel 16 · 2026-09-15 --> 14-15 Eylül'de gerçek model ve güncel kampüs tasarımıyla yeniden çekildi (kayıt: `docs/screenshots.md`).
