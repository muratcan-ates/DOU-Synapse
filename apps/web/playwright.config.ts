import { defineConfig, devices } from "@playwright/test";

const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000";
const PORT = Number(process.env.E2E_PORT ?? 3100);
const SCREENSHOTS = process.env.EKRAN === "1";

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
    { name: "chromium", testIgnore: llmFiles, use: browser },
    { name: "llm", testMatch: llmFiles, use: browser },
  ],
});
