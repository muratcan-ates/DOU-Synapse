# UX Audit — 2026-09-14 (P5)

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
