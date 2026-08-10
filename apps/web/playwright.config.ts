import { defineConfig, devices } from "@playwright/test";

/**
 * E2E yapılandırması.
 *
 * Sunucuları test kendisi başlatmaz: geliştirme sırasında zaten ayakta olurlar
 * ve iki kez başlatmak port çakışması üretir. CI'da iş akışı başlatır.
 * Beklenen adresler `baseURL` ve `E2E_API_URL`.
 *
 * Tek tarayıcı (Chromium): bu paket tarayıcı uyumluluğunu değil ürün akışını
 * sınıyor. Üç tarayıcıda koşturmak CI süresini üçe katlar ve hiçbir yeni bilgi
 * vermez.
 */
/**
 * Test, kendi web sunucusunu başlatır ve API adresini AÇIKÇA verir.
 *
 * Neden: geliştirme sunucusu `NEXT_PUBLIC_API_URL`'i ortamdan alıyor ve bu
 * makinede önizleme aracı onu bir proxy'ye (`:9100`) yönlendirmişti. Sonuç:
 * test kendi verisini `:8000`'e kuruyor, tarayıcı `:9100`'e soruyor ve testler
 * çalıştıkları ortama göre bazen geçip bazen kalıyordu. Kararsız test,
 * olmayan testten kötüdür — ekip önce ona güvenmeyi bırakır.
 *
 * Üretim derlemesi kullanılır, geliştirme sunucusu değil. Üç sebep: Next 16 aynı
 * dizinde ikinci bir dev sunucusuna izin vermiyor; üretim derlemesi HMR
 * kararsızlığı taşımıyor; ve CI'da koşacak olan zaten bu. `NEXT_PUBLIC_*`
 * değişkenleri DERLEME anında gömüldüğü için API adresi build komutuna verilir.
 *
 * Ayrı port (3100) kullanılır ki geliştirme sunucusunu (3000) kapatmasın.
 */
const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000";
const PORT = Number(process.env.E2E_PORT ?? 3100);

/**
 * `@ekran` ekran görüntüsü üretimi bir DOĞRULAMA değildir ve gerçek demo dersine
 * (COME 331) bağımlıdır; temiz bir CI veritabanında o ders yoktur ve testler
 * kaçınılmaz düşer. Bu yüzden varsayılan koşudan çıkarılır; üretim bilinçli bir
 * eylemdir: EKRAN=1 ... --grep @ekran
 */
const EKRAN_URETIMI = !!process.env.EKRAN;

export default defineConfig({
  grepInvert: EKRAN_URETIMI ? undefined : /@ekran/,
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  globalTeardown: "./e2e/global-teardown.ts",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  webServer: {
    command: `bun run next build && bun run next start --port ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    env: { NEXT_PUBLIC_API_URL: API_URL },
  },
  use: {
    baseURL: `http://localhost:${PORT}`,
    locale: "tr-TR",
    // Hata ayıklama izleri yalnız başarısızlıkta üretilir; her koşuda üretmek
    // CI artefaktını gereksiz şişirir.
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // Sistemdeki Chrome kullanılır, Playwright'ın kendi indirdiği tarayıcı
        // değil: yerel makinede zaten kurulu ve indirme adımını (~300 MB)
        // tamamen atlar. CI'da `playwright install --with-deps chromium`
        // koşuyorsa bu satır `channel` yerine varsayılana düşürülebilir.
        channel: process.env.CI ? undefined : "chrome",
      },
    },
  ],
});
