# 025 · Çizim ve görsel teslim kontrolü

Tarih: 15 Eylül 2026. Dal: `025-campus-ui`.
HEAD: `3e7aa8be6fd69ffcf8a447b8fa6853143d414e20`; değişiklikler commit edilmemiştir.

## Değişiklik
- Açık/koyu giriş kapağı aynı geometride özgün Bézier SVG olarak çizildi.
- Kullanıcının gönderdiği iki el görseli byte-identical kopyayla akademik footer'a alındı.
- Tema çiftleri data-theme ile gösterilir. El resimleri Next Image ile sunulur;
  dekoratif SVG kapakları küçük özgün vektör olarak servis edilir.
- Asistan çekmece başlığında mevcut kitap işareti ve native kapsam açıklaması kullanılır.
- Auth, demo giriş, API istekleri ve role/exam kararlarında bu tur değişiklik yok.
- Arayüz tasarım paftaları ürün resmi yapılmadı; kişisel referans ekranları depoya alınmadı.

## Bu adayda çalıştırılan kontroller
- `bun test lib/`: 648 geçti, 0 başarısız; 1856 assertion, 53 dosya. <!-- docs-check: tarihsel 648 · 2026-09-15 -->
  Günlük: `/tmp/campus025-drawn-tests.log`.
- `bun run typecheck`: rc 0. `/tmp/campus025-drawn-types.log`.
- Production build: rc 0. `/tmp/campus025-drawn-build.log`.
- `git diff --check`: rc 0.
- Var olmayan `/synapse-cizim-kontrol-yok`: HTTP 404.

## Tarayıcı gözlemi
- Giriş: 375 px açık temada scrollWidth 375; görünür yeni SVG yüklü,
  CSS ile gizli tema resmi ilk yüklemede indirilmemiş. 1280×900 koyu görünüm kontrol edildi.
- Ayşe eğitmen oturumu: kendi dersleri ve eğitmen paneli açıldı.
- Footer: masaüstü koyu ve 375 px açık görünümde iki el/merkez boşluğu tam görünüyor.
  Mobil görünür resim 341 px genişlik ve 3:1 oran, sayfa scrollWidth 375.
- Footer klavye Tab geçişinde görünür odak var.
- Ders asistanı: 375 px açık temada kitaplı başlık, kapsam açılımı;
  Escape sonrası açık dialog sayısı 0, odak Eğitmen Asistanı düğmesinde.
- İzole yerel API 8025, web 3125. Veri servisi durmuştu, aynı
  `dou_campus025_20260914` üzerinde yeniden başlatıldı; profile/dashboard GET 200 gözlendi.
- Konuşma içi önizlemede kitap düğmesi başlığı açıyor; 375 px yerleşim kontrol edildi.

## Sınırlar
Bu tur tam E2E, bütün rol matrisi, büyük yazı/yüksek kontrast matrisi, gerçek model,
üretim veya dağıtım doğrulaması çalıştırılmadı. Görseller hareket içermiyor;
renk tokenları değiştirilmedi. Önceki rol/erişilebilirlik raporu tarihsel kanıttır.
UI çizimleri ve pafta canlı veri veya güvenlik testi kanıtı değildir.
Main/merge/push yapılmadı.

## Teslim dosyalarının SHA-256 değerleri

- `apps/web/app/page.tsx`: `93a35e286e312287d1a247916521f0e2fccac1838dfc9507410ec8dd3ba31bba`
- `apps/web/components/synapse-footer.tsx`: `692a82fa614fce58d11f5af9077581e1575d852af4068482377521e044f14a63`
- `apps/web/components/synapse-illustration.tsx`: `e5c59a4c78c6dfa1f4014e7a3bd12d79827919ad5c48db66c391d3b4551442db`
- `apps/web/components/synapse-illustration.module.css`: `1467adfcd6426c6f4bfb7ae8da976dcfff6c338edbd7d6834351d0c8552b4e51`
- `apps/web/components/course-assistant/course-assistant.tsx`: `7bdcdc9f342c116d6e9e029676cee536d41863ae08525a96cd08f6f9d9b0504e`
- `apps/web/public/brand/art/neuron-light.svg`: `7af53a95ad0901de499ee2a2c289dbc5b6ec435b5840f4b1f5578075619f90f0`
- `apps/web/public/brand/art/neuron-dark.svg`: `f249ed3ef9bcf198fd7e78099a7c3bdfa7f0d9d07587fd263db9ebe252b00f98`
- `apps/web/public/brand/art/hands-light.png`: `66d6132421c93ae4df0774201dbf65bd62b0c6ef313735587112768a5e688eb9`
- `apps/web/public/brand/art/hands-dark.png`: `c7db894e9aa5138c01964c320f2c3c3312cac6151483ee29e653836c26b4271c`
