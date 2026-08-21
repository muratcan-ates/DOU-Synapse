# Specification Quality Checklist: Production Sertleştirme

**Purpose**: Şartnamenin planlamaya geçmeden önce eksiksiz ve kaliteli olduğunu doğrulamak
**Created**: 2026-08-09
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] Uygulama ayrıntısı yok (dil, çatı, API adı) — gereksinimler davranış düzeyinde yazıldı; dosya yolları ve tablo adları plan.md'ye bırakıldı
- [x] Kullanıcı değerine ve iş ihtiyacına odaklı
- [x] Teknik olmayan paydaş (hoca, jüri) için okunabilir
- [x] Bütün zorunlu bölümler dolduruldu

## Requirement Completeness

- [x] [NEEDS CLARIFICATION] işareti kalmadı — üç açık karar kullanıcıya soruldu ve cevaplandı (kapsam: tam; anahtarlar: bu hafta; blueprint: tam model)
- [x] Gereksinimler test edilebilir ve tek anlamlı
- [x] Başarı ölçütleri ölçülebilir
- [x] Başarı ölçütleri teknolojiden bağımsız
- [x] Kabul senaryoları tanımlı (10 hikâye, 47 senaryo)
- [x] Sınır durumları belirlendi (10 madde)
- [x] Kapsam sınırlı — "dışında bırakılanlar" tablosu gerekçeleriyle yazıldı
- [x] Bağımlılıklar ve varsayımlar belirtildi

## Feature Readiness

- [x] Her fonksiyonel gereksinimin kabul ölçütü var
- [x] Kullanıcı senaryoları birincil akışları kapsıyor
- [x] Özellik, Başarı Ölçütleri'ndeki ölçülebilir sonuçları karşılıyor
- [x] Şartnameye uygulama ayrıntısı sızmadı

## Anayasa Uyum Kontrolü (projeye özel, şablonun dışında)

- [x] **I. Kaynak Yoksa Cevap Yok** — FR-132 (kaynak seti) ve FR-118 (kaynak sürümü) atıf zincirini zayıflatmıyor, daraltıyor
- [x] **II. İki Katmanlı İzolasyon** — yeni varlıkların hepsi ders kapsamlı; RLS gereksinimi plan.md'de her yeni tablo için zorunlu
- [x] **III. Ölçmeden İddia Etme** — FR-182 ve SC-009 doğrudan bu ilkenin uygulaması
- [x] **IV. Fail-Closed** — FR-101 (kilit), FR-112 (tutarsız blueprint kaydedilmez), FR-114 (eksik sınav yayınlanmaz) fail-closed
- [x] **V. Türkçe Birinci Sınıf** — bütün kullanıcıya dönen metinler Türkçe; FR-155 istek kimliği ham hata yerine anlaşılır metinle birlikte
- [x] **VI. Kapsam Kapıları** — "dışında bırakılanlar" tablosu; P1 hikâyeler P2/P3'ten önce
- [x] **VIII. Doğrulama Bitmeden Bitti Yok** — SC-001 mutasyon kanıtı istiyor
- [x] **XI. Modülerlik** — FR-135 ve FR-133 politikanın tek yerde okunmasını gerektiriyor

## Notes

- Kullanıcı, 9 Ağustos'ta tam kapsamı bilerek seçti. Risk: 17 Ağustos dondurma tarihine 8 gün var ve blueprint tam modeli tek başına büyük bir iş. Kesme noktası mekanizması spec.md §Uygulama sırası'ndadır: yetişmeyen iş sıranın sonundan kesilir.

### Taslak 2 düzeltmeleri (9 Ağustos, dış incelemeyi yazanın karşı okuması üzerine)

İlk taslakta üç hata vardı ve üçü de düzeltildi:

1. **Yanlış atıf (iki madde).** "Onay akışı yok" ve "sahte sağlayıcı soru üretemiyor" iddiaları dış incelemeye atfedilmişti. İnceleme ikisini de söylemiyor: onay akışının var olduğunu açıkça yazıyor, sahte sağlayıcı için de "şema akışını kanıtlar, pedagojik kaliteyi kanıtlamaz" diyor — ki bu doğru ve T047'nin konusu. "Sıfır soru" ifadesinin gerçek kaynağı `20_DEVIR_9_AGUSTOS.md:100` ve `README.md:219`; hata, doğrulama ajanına iddiayı yanlış kaynakla vermekten çıktı. spec.md'nin son tablosu kaynak sütunuyla düzeltildi.
2. **Yanlış önceliklendirme.** Event loop bloklanması ve sınırsız soru üretimi P3'teydi. İkisi de bilinen, ölçülebilir kusur; sekiz varlıklı blueprint'ten önce kapanmaları gerekir. Yeni User Story 2 (P1) açıldı, FR-220..FR-224 oraya taşındı.
3. **İsimlendirilmemiş kusur.** Issuer ortam değişkeni uyuşmazlığı yalnız FR-173'ün genel ifadesinde saklıydı. FR-224 olarak açıkça yazıldı ve uygulama sırasında 2. sıraya alındı.

### Ölçülerek kapatılan iki şüphe (9 Ağustos)

- **Test sayısı**: `uv run pytest -q` → **664 passed**. README doğru; `docs/security.md:358` (530) ve `docs/test-report.md:577` (473) bayat.
- **RLS iddia sayısı**: `rls_isolation.sql` sıfırdan kurulan bir veritabanında koşturuldu → **98 iddia, 0 FAIL, hata yok, betik sonuna kadar çalışıyor.** `docs/test-report.md:160`'taki "8 PASS" yalnız bayat bir sayı; "betik sessizce erken duruyor olabilir" ihtimali **elendi**.
