import { defineConfig, devices } from "@playwright/test";

const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000";
const PORT = Number(process.env.E2E_PORT ?? 3100);
const SCREENSHOTS = process.env.EKRAN === "1";
const VISUAL = process.env.E2E_VISUAL === "1";
const VISUAL_UPDATE = process.env.E2E_VISUAL_UPDATE === "1";
const visualFiles = ["**/visual-regression.spec.ts"];
if (VISUAL_UPDATE && !VISUAL) throw new Error("ENGEL: referans üretimi E2E_VISUAL=1 gerektirir.");
if (VISUAL && (process.platform !== "linux" || process.env.CI !== "true")) {
  throw new Error("ENGEL: görsel referans yalnız aynı Linux CI imajında çalıştırılır.");
}
if (VISUAL && !/^sha256:[0-9a-f]{64}$/.test(process.env.E2E_VISUAL_IMAGE_DIGEST ?? "")) {
  throw new Error("ENGEL: Linux CI imajının gerçek E2E_VISUAL_IMAGE_DIGEST değeri gerekli.");
}

// Karma flows dosyası da bu gruptadır: içindeki üretim çağrıları yanlışlıkla
// genel projeye düşmesin. Proje adı gerçek sağlayıcı kullanıldığı anlamına gelmez.
const llmFiles = [
  "flows", "role-aware-agent", "question-authoring", "question-delete-unblocks-document",
  "question-pool-filters", "blueprint-topic-readiness", "student-assessment",
  "exam-completion-guards", "code-rubric-feedback", "chat-history-deletion",
  "privacy-session-guards", "exam-cross-tab-privacy",
].map((name) => `**/${name}.spec.ts`);
const browser = { ...devices["Desktop Chrome"], channel: process.env.CI ? undefined : "chrome" };

export default defineConfig({
  updateSnapshots: VISUAL_UPDATE ? "all" : "none",
  grepInvert: SCREENSHOTS ? undefined : /@ekran/,
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  globalTeardown: "./e2e/global-teardown.ts",
  // Çok adımlı API/tarayıcı senaryosu için sonlu bekleme bütçesi; performans SLO
  // ölçümü değildir. Koşu başına yeniden deneme sayısı aşağıda ayrıca sınırlıdır.
  timeout: 90_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  workers: 2,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  webServer: {
    // Public API adresi derleme sırasında gömülür; farklı bir geliştirme
    // sunucusunu kullanmak veri kurulumuyla tarayıcı hedefini ayırabilirdi.
    command: `bun run next build ${process.env.E2E_WEBPACK_BUILD === "1" ? "--webpack" : ""} && bun run next start --hostname 127.0.0.1 --port ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: false,
    timeout: 180_000,
    env: { NEXT_PUBLIC_API_URL: API_URL },
  },
  use: {
    baseURL: `http://localhost:${PORT}`,
    locale: "tr-TR",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", testIgnore: [...llmFiles, ...visualFiles], use: browser },
    { name: "llm", testMatch: llmFiles, use: browser },
    ...(VISUAL ? [{
      name: "visual", testMatch: visualFiles,
      use: { ...devices["Desktop Chrome"], channel: undefined,
        viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1,
        locale: "tr-TR", timezoneId: "UTC", contextOptions: { reducedMotion: "reduce" as const } },
    }] : []),
  ],
});
