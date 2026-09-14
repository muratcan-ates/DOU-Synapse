# Kampüs arayüzü sonrası bağımlılık güvenlik yamaları

Tarih: 14 Eylül 2026. Dal: `025-campus-ui`.
İncelenen önceki commit: `ffd9bf7`.

Bu takip değişikliği, bağımlılıkları değiştirmeyen arayüz revizyonundan sonradır.
`100` numaralı arayüz kaydındaki kapsam açıklaması o commit için geçerlidir.
Burada mevcut web bağımlılıkları güvenlik yaması düzeyinde güncellenmiştir;
API, model, retrieval, yetki, sınav kilidi veya öğrenci verisi davranışı değiştirilmemiştir.

## Doğrulanan uyarılar ve sürümler

GitHub push özeti varsayılan dal için iki kritik uyarı bildirdi. Depoya özel
Dependabot kayıtlarına erişim doğrulanamadığından, bu rapor bunların kayıt
numaralarını veya kapanış durumunu iddia etmez. Çalışma dalının kilit dosyasıyla
çalıştırılan bağımsız `bun audit --json`, üç pakette iki kritik ve iki yüksek
önem dereceli uyarıyı doğruladı.

| Paket | Önce | Sonra | Doğrulanan güvenlik kaynağı |
| --- | --- | --- | --- |
| `next` | 16.3.1 | 16.3.3 | [Windows sunucularında RCE, GHSA-p293-qw3h-jr36](https://github.com/vercel/next.js/security/advisories/GHSA-p293-qw3h-jr36) |
| `next` | 16.3.1 | 16.3.3 | [AVIF görüntü optimizasyonunda RCE, GHSA-2xp9-vwfh-vxw4](https://github.com/vercel/next.js/security/advisories/GHSA-2xp9-vwfh-vxw4) |
| `sharp` | 0.35.3 | 0.35.4 | [libheif güvenlik yamaları, GHSA-rgj7-g3m4-5g8c](https://github.com/lovell/sharp/security/advisories/GHSA-rgj7-g3m4-5g8c) |
| `nanoid` | 3.3.17 | 3.3.18 | [Sıfır uzunlukta özel üretici döngüsü, GHSA-2v37-7h3g-55p8](https://github.com/advisories/GHSA-2v37-7h3g-55p8); [üreticinin 3.3.18 sürümü](https://github.com/ai/nanoid/releases/tag/3.3.18) |

Next ile aynı sürümü gerektiren `@next/env` ve SWC paketleri de 16.3.3 oldu.
Sharp'ın platform paketleri 0.35.4, libvips paketleri 1.3.3 oldu. Kurulu sharp
modülü libheif **1.23.2** kullandığını doğruladı. Nanoid mevcut PostCSS bağımlılık
zincirinde 3.x sürümünde kaldı. Diğer paketler ve sürüm aralıkları korunmuştur.

## Uygulamaya etkisi ve sınırlar

- Windows duyurusu, Windows dosya sistemi üzerinde çalışan, Cache Components
  kullanmayan Pages/App Router uygulamalarıyla ilgilidir. Depoda App Router var;
  `cacheComponents` etkinleştirilmemiş. Yerel kontrol macOS üzerinde ve CI Ubuntu
  üzerinde yapıldı. Gerçek web üretim sunucusunun işletim sistemi bu incelemeyle
  doğrulanmadığından üretimde açık bulunduğu veya bulunmadığı sonucu çıkarılmaz.
- AVIF duyurusu Next görüntü optimizasyonunun sharp/libheif üzerinden güvenilmeyen
  görüntü işlemesiyle ilgilidir. Kaynakta `next/image` kullanımı veya özel AVIF
  işleme akışı bulunmadı. Bu durum yerleşik görüntü optimizasyonu uç noktasının
  kapalı olduğunu kanıtlamaz. Yama uygulanarak savunma yalnız kullanım varsayımına
  bırakılmadı. Next duyurusuna göre yamalı sürüm AVIF optimizasyonunu devre dışı
  bırakır; ayrıca sharp'ın düzeltilmiş kitaplıkları kilitlendi.
- Nanoid duyurusu, `customAlphabet`/`customRandom` işlevlerine denetlenmemiş,
  saldırgan tarafından belirlenen sıfır boyutun ulaşması halinde hizmet reddi
  riskini açıklar. Uygulama kaynaklarında bu işlevlerin doğrudan kullanımı
  bulunmadı. Kilit dosyasındaki etkilenen dolaylı sürüm yine de güncellendi.

Saldırı veya istismar denemesi yapılmadı. Bu çalışma bağımlılık uyarılarını
kapsar; tam sızma testi, KVKK/GDPR hukuki uygunluk onayı veya canlı dağıtım
sertifikası değildir. Varsayılan dal uyarılarının kapanması ayrıca GitHub'ın
birleştirme sonrası taramasına bağlıdır.

## Kilit dosyasının hazırlanması

Bun 1.3.14 kullanıldı. `bun update next@16.3.3 --ignore-scripts` ile Next yaması
uygulandı. Bu Bun sürümünde dolaylı paket adıyla güncellemenin kuru çalışması
istenmeyen doğrudan paket ekleme davranışı gösterdiği için uygulanmadı.

Sharp ve nanoid için manifest/kilit kopyası izole geçici dizinde çözümlendi:
uyumlu 0.35.4 ve 3.3.18 sürümlerine geçici çözümleme kısıtları uygulandı,
ardından kısıtlar kaldırılıp normal manifest ile kilit yeniden üretildi.
Anlamsal kilit karşılaştırması yalnız bu iki paket ve sharp'ın kendi platform
paketlerinin değiştiğini doğruladı. Depodaki nihai manifestte yeni doğrudan
bağımlılık veya `overrides` yoktur; tek manifest farkı Next yamasıdır.
Kilit elle paket/hash değiştirilerek oluşturulmadı.

## Doğrulama

Aşağıdaki yerel kontrollerin tamamı son manifest ve kilit dosyasında çalıştırıldı.
Log yolları geliştirici makinesindeki kanıtlardır; CI kanıt arşivi ayrıca üretilir.

| Kontrol | Sonuç | Yerel log |
| --- | --- | --- |
| Önceki `bun audit --json` | rc=1; 2 kritik + 2 yüksek uyarı | `/tmp/campus025-security-before-audit.json` |
| `bun install --frozen-lockfile --ignore-scripts` | rc=0; manifest/kilit uyumlu | `/tmp/campus025-security-install.log` |
| Sonraki `bun audit --json` | rc=0; `{}` | `/tmp/campus025-security-after-audit.json` |
| `bun audit --audit-level high` | rc=0; güvenlik uyarısı yok | `/tmp/campus025-security-audit-high.log` |
| `tsc --noEmit --incremental false` | rc=0 | `/tmp/campus025-security-typecheck.log` |
| `bun test lib/` | rc=0; 632 geçti, 0 başarısız, 1540 doğrulama, 51 dosya <!-- docs-check: tarihsel 632 · 2026-09-14 --> | `/tmp/campus025-security-unit-tests.log` |
| Next 16.3.3 üretim derlemesi | rc=0; 14 statik sayfa üretildi | `/tmp/campus025-security-build.log` |
| Kurulu paketler ve native kitaplık | Next 16.3.3, sharp 0.35.4, nanoid 3.3.18, libheif 1.23.2 | `/tmp/campus025-security-installed-versions.json` |

Derlemede `NEXT_PUBLIC_API_URL=http://127.0.0.1:8025` ve
`NEXT_PUBLIC_DEV_AUTH=true` kullanıldı. Bunlar yalnız sentetik yerel önizleme
ayarlarıdır; üretim dağıtımı yapılmadı. Bu yama sonrasında tam E2E veya görsel
referans karşılaştırması yeniden çalıştırılmış sayılmaz.
