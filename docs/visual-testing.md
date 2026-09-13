# Görsel regresyon protokolü

Yeni dosya: `docs/visual-testing.md`. Hazırlık tarihi: 13 Eylül 2026. Bu hazırlıkta tarayıcı veya görsel karşılaştırma çalıştırılmadı; baseline üretilmedi.

[DESIGN.md](../DESIGN.md) tasarım otoritesidir. Yeni [visual-regression.spec.ts](../apps/web/e2e/visual-regression.spec.ts), giriş, eğitmen soru havuzu, blueprint hazırlığı, kaynaklı öğrenci sohbeti ve alıştırma ekranını `toHaveScreenshot()` ile karşılaştırır. Her yüzey açık ve koyu temada aynı viewport, ölçek, yerel ayar ve yazı tipleriyle ele alınır. Bu kapsam, tüm ürün ekranlarının görsel olarak doğrulandığı anlamına gelmez.

[Worker fixture](../apps/web/e2e/worker-fixture.ts) her çalışana ayrı sentetik profil verir; [seedAssessmentCourse](../apps/web/e2e/seed-assessment-course.ts) materyal, onaylı soru ve üyeliği gerçek yerel API'de kurar. Course UUID/kodunun görünmediği yüzeyler seçilmiştir. Soru, kaynak ve cevap içeriği maskelenmez veya tarayıcıda değiştirilmez. Animasyonlar kapatılır, font yüklenmesi ve gerçek içerik hazır olma koşulları beklenir; keyfî bekleme süresi görsel hazır olma kanıtı sayılmaz. Alıştırma ekranı seçilir; aktif sınav sayacı dondurulmaz. Başarıyla açılan alıştırma, sonraki doğrulama veya görüntü başarısız olsa da `finally` içinde aynı öğrenciyle bitirilir.

Ekran başlığı tek başına hazır olma kanıtı değildir. Soru havuzunda gerçek rol/availability, konu ve onaylı soru yanıtları; özellik açıksa sınıflandırma çıktıları ile form seçenekleri beklenir. Blueprint hazırlığında boş çıktı/blueprint listeleri API'den doğrulanır ve konu seçeneklerinin son hâli görülür. Kaynaklı sohbette materyal sütunu, ilk geçmiş yüklemesi ve cevaptan sonraki yeni oturum satırı tamamlanır. Alıştırmada gerçek 201 başlatma yanıtı, yeniden okunan oturum ve başlatma sonrası availability yanıtı doğrulanır; radyo seçenekleri etkin ve boş olmalıdır. Bu koşullar kaynakta tanımlıdır; henüz çalıştırılmış görsel kanıt değildir.

## Referans ortamı

Görsel proje yalnız `E2E_VISUAL=1` ile seçilir. Mac üzerinde baseline oluşturulmaz ve Mac görüntüsü commit edilmez. Çalıştırma `process.platform === "linux"` ve `CI=true` gerektirir. `E2E_VISUAL_IMAGE_DIGEST`, çalıştırılan CI imajının gerçekten çözümlenmiş `sha256:…` özeti olmalıdır; elle uydurulmuş kimlik veya yalnız hareketli imaj etiketi kabul edilmez. Bu değer imajı seçmez; CI sahibinin gerçekten hangi imajı çalıştırdığını kaydetmesi gerekir.

Yenileme başında eski ortam makbuzu geçersiz kılınır; bütün görüntüler üretilmeden yeni makbuz yazılmaz. Yarım kalan üretimden sonra karşılaştırma açık engel verir. Her temanın `baseline-environment-<tema>.json` makbuzu gerçek Playwright sürümünü, açılmış Chromium sürümünü, imaj özetini, mimariyi ve görsel ayarları kaydeder. Karşılaştırmada bütün alanların eşleşmesi zorunludur. İmaj/binary/font değişiminde eski referansın sonucu yeni ortamın kanıtı değildir.

**ENGEL: aynı Linux CI imajında üretilmiş, incelenmiş baseline görüntüleri ve ortam makbuzları henüz yok.** Test karşılaştırma modunda bunlardan biri eksikse açık `ENGEL:` hatası verir. Boş referansı otomatik kabul etmez. Bu adayda workflow eklenmedi; sabit imajlı üretim ve görsel artefakt inceleme adımı CI sahibinin işidir. Argos, Chromatic veya yeni bağımlılık eklenmedi.

## Çalıştırma ve inceleme

API, ayrı test veritabanı, audit kapsamı ve mevcut bağımlılıklar önce [test protokolüne](testing.md) göre hazırlanır. Bu testin referansları sentetik yerel sağlayıcı ve hashing embedding ile oluşturulacaksa, API'nin gerçekten bu sağlayıcı ayarlarıyla başlatıldığı koşu kaydında belirtilir; proje adı sağlayıcı türünün kanıtı değildir.

Aynı Linux CI imajındaki bilinçli referans üretimi:

```bash
cd apps/web
E2E_VISUAL=1 E2E_VISUAL_UPDATE=1 ./node_modules/.bin/playwright test --project=visual --update-snapshots=all
```

Üretim komutu görsel regresyon geçti demek değildir. Üretilen görüntüler ve ortam makbuzları artefakt olarak incelenir; değişikliğin gerekçesi, kaynak SHA ve CI koşu bağlantısı yazılır. Kabul edilen Linux dosyaları birlikte commit edilir. Referans oluşturulmasından sonraki karşılaştırma aynı imajda, API/seed koşulları korunarak yapılır:

```bash
cd apps/web
E2E_VISUAL=1 ./node_modules/.bin/playwright test --project=visual --update-snapshots=none
```

Karşılaştırmanın görüntü farkı sınırı testte sıfır pikseldir; sonuç ölçülmeden bu koşulun sağlandığı söylenmez. Farkı gizlemek için tolerans büyütülmez, kritik içerik maskelenmez ve otomatik baseline yenilemesi açılmaz. Önce mevcut görüntü, beklenen görüntü ve fark artefaktı incelenir.

| Yüzey | Referans üretimi | Görüntü incelemesi | Aynı imajda karşılaştırma |
|---|---|---|---|
| Giriş, açık/koyu | koşulmadı | yapılmadı | koşulmadı |
| Soru havuzu, açık/koyu | koşulmadı | yapılmadı | koşulmadı |
| Blueprint hazırlığı, açık/koyu | koşulmadı | yapılmadı | koşulmadı |
| Kaynaklı sohbet, açık/koyu | koşulmadı | yapılmadı | koşulmadı |
| Alıştırma, açık/koyu | koşulmadı | yapılmadı | koşulmadı |

## Yerel önkoşul denetimi — 13 Eylül 2026

Uygulanan yapılandırmayla Mac üzerinde `E2E_VISUAL=1 ./node_modules/.bin/playwright test --list --project=visual` çalıştırıldı. Komut `rc=1` ile Linux CI önkoşulunu bildirdi; bu beklenen engel gözlendi. Tarayıcı, API, global setup veya baseline üretimi başlamadı. Bu kontrol görsel regresyon kabulü değildir; yerel kanıt `runtime/evidence/h2-macos-independent/result.json` kaydındadır.
