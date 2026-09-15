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
  "exam-assistant-killswitch",
  "privacy-session-guards", "exam-cross-tab-privacy", "screenshots",
].map((name) => `**/${name}.spec.ts`);

// FAZ SEÇİMİ. İki dosya kendi API sürecini ister ve bayrakları AYNI ANDA açılamaz:
// LLM_SIMULATE_RATE_LIMIT açıkken provider_fallback.py her üretim çağrısında 429
// simüle eder, yani diğer bütün sohbet testleri düşer. `scripts/run_owned_e2e.py`
// her fazı kendi API sürecinde koşar ve fazı bu değişkenle seçer.
// Değişken KURULMADIĞINDA liste hiç değişmez (87 vaka / 20 dosya): docs_check.mjs
// varsayılan listelemeyi ölçüp README'deki sayıyla karşılaştırır.
const PHASES = ["main", "grounded", "ratelimit"] as const;
type Phase = (typeof PHASES)[number];
// Record<Exclude<...>> bilerek: ileride eklenen bir faz globunu unutursa tsc kırmızı yanar.
const simFiles: Record<Exclude<Phase, "main">, string[]> = {
  grounded: ["**/grounded-wrong-feedback.spec.ts"],
  ratelimit: ["**/provider-fallback.spec.ts"],
};
const requestedPhase = process.env.E2E_PHASE ?? "";
if (requestedPhase !== "" && !(PHASES as readonly string[]).includes(requestedPhase)) {
  throw new Error(
    `ENGEL: bilinmeyen E2E_PHASE "${requestedPhase}"; beklenen: ${PHASES.join(", ")}.`,
  );
}
// Yazım hatası sessizce ana faza düşerse simülasyon testleri yanlış API'ye koşar;
// bu yüzden yukarıda fail-fast. Boş dize de kurulmamış sayılır.
const phase = requestedPhase === "" ? null : (requestedPhase as Phase);
// Object.values ile TÜRETİLİR, elle sayılmaz: yeni bir simülasyon fazı eklenince
// `main` fazının dışlama listesi kendiliğinden büyür. Elle yazılsaydı Record tipi
// globu zorunlu kılar ama `main` onu sessizce dışlamayı unuturdu.
const simFilesAll = Object.values(simFiles).flat();
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
  // Simülasyon fazlarında tekrar YOK: vakaların kendi tavanları yüksek
  // (grounded 150 sn, ratelimit 120 sn) ve fazın bütçesi koşucuda sınırlı;
  // tek bir tekrar bütçeyi kusur olmadan aşırırdı.
  retries: phase !== null && phase !== "main" ? 0 : process.env.CI ? 1 : 0,
  // Playwright her koşunun başında projenin outputDir'ini SİLER. Üç faz aynı
  // dizini paylaşsaydı son faz önceki fazların trace/ekran görüntülerini
  // götürürdü. Varsayılan değer değişmiyor; `/test-results/` .gitignore'da.
  outputDir: phase === null ? "test-results" : `test-results/${phase}`,
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
  // Simülasyon fazı projects[] dizisini TAMAMEN değiştirir: `llm` projesinin
  // testMatch'i koşulsuz olduğundan, yanında bırakılsaydı 53 llm vakası da
  // simülasyon bayrağı açık API'ye koşar ve kusursuz yere kırmızı yanardı.
  // Proje adları her fazda `chromium`/`llm` kalır; kanıt satırları karşılaştırılabilir olsun.
  projects: phase !== null && phase !== "main"
    ? [{ name: "chromium", testMatch: simFiles[phase], use: browser }]
    : [
    {
      name: "chromium",
      testIgnore: [...llmFiles, ...visualFiles, ...(phase === "main" ? simFilesAll : [])],
      use: browser,
    },
    { name: "llm", testMatch: llmFiles, use: browser },
    ...(VISUAL ? [{
      name: "visual", testMatch: visualFiles,
      use: { ...devices["Desktop Chrome"], channel: undefined,
        viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1,
        locale: "tr-TR", timezoneId: "UTC", contextOptions: { reducedMotion: "reduce" as const } },
    }] : []),
  ],
});
