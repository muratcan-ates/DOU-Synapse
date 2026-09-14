# 025 · Güncel tasarımın Git teslimi

Tarih: 15 Eylül 2026. Dal: `025-campus-ui`.
Taban: `3e7aa8be6fd69ffcf8a447b8fa6853143d414e20`.
Kullanıcı bu tur güncel tasarımın commit ve push edilmesini istedi.

## İncelenecek ürün

Giriş başlığı **Bilgi, bağlantı kurdukça büyür.** oldu. Açık/koyu özgün sinaps
SVG kapakları, onaylanan dekoratif el görselleri, kitap işaretli ders asistanı,
öğrenci/eğitmen/teknik yönetim ayrımı, uygulama erişilebilirlik ayarları, ders
tekrarına ulaşım ve ayrı 404/yeniden deneme ekranları bu dalın ürün dosyalarıdır.

Yerel çalışma kopyası `~/code/dou-synapse-025-campus-ui`, gerçek uygulama
önizlemesi 3125 portundadır. 3126 yalnız konuşma içi etkileşimli çizim örneğidir;
gerçek giriş/oturum uygulaması değildir. Git incelemesinde `apps/web/app/page.tsx`,
`components/synapse-illustration.tsx` ve `public/brand/art/` esas alınır.

Önceki turda onaylanan GSAP paketleri ve kilit dosyası, mevcut hareket bileşeninin
kurulabilmesi için dahildir. Bu teslimde yeni paket kurulmadı. Kişisel referans
fotoğrafları/ekran görüntüleri ürün varlıklarına veya bu kayda eklenmedi.

## Bu teslim turunda doğrulama

- Web birim testleri: 648 başarılı, sıfır başarısız; 53 dosya, 1856 assertion. <!-- docs-check: tarihsel 648 · 2026-09-15 -->
- TypeScript ve üretim derlemesi geçti.
- Açık/koyu ve yüksek kontrast renk çiftleri metinde 4.5:1, kontrol öğelerinde 3:1 eşiğini geçti.
- Demo kurulumunun odaklı testleri: 14 başarılı.
- API Ruff denetimi/biçimi ve mypy geçti; backend çalışma kodu değişmedi.
- Belge sayıları ölçümden güncellendi; belge, göç sırası ve workflow politikası kontrolleri geçti.
- Seçili dosyalarda özel anahtar/token desen taraması ve boşluk kontrolü geçti.

API araçları bu çalışma kopyasında eksik olduğundan aynı depodaki mevcut
`018-codex-production-line` Python doğrulama ortamı kullanıldı; hedef kaynak
kodu daima 025 çalışma kopyasıydı. İlk belge kontrolü eksik araçlar ve eski
sayılar nedeniyle başarısız oldu; araç yolu ve sayılar düzeltilerek tekrar geçti.

Son çizim turunun tarayıcı kanıtları `drawn-visual-review.md`, daha önceki rol ve
büyük yazı kontrolleri `role-accessibility-review.md` içinde tarihlidir.
Bu paketleme turunda tam API pytest, tam E2E, gerçek sağlayıcı, üretim ve canlı
sınav doğrulaması tekrarlanmadı. Derleme ve birim testleri bu sınırların yerine geçmez.

## Ayrı kalan yerel çalışmalar

Bağımsız E2E senaryo koşucusunun dört dosyası (`ci.yml`, `run_owned_e2e.py`,
`test_owned_e2e.py`, `playwright.config.ts`) bu ürün commitine dahil edilmedi.
Yerel Taste skill kurulumları da uygulamanın çalışma bağımlılığı olmadığı için
ayrı bırakıldı. Bu dosyalar silinmedi veya geri alınmadı.

Asistan dosyasının hassas yol sınıflandırması nedeniyle yeni 102 kaydı eklenir.
Bu yayın, inceleme dalının paylaşımıdır; main birleştirmesi veya üretim dağıtımı değildir.
