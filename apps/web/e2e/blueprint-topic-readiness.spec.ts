import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { createE2eCourseIdentity } from "./fixtures";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const headers = { Authorization: "Bearer dev:11111111-1111-1111-1111-111111111111" };
async function post(request: APIRequestContext, path: string, data: unknown = {}) {
  const response = await request.post(`${API}${path}`, { headers, data });
  expect(response.ok(), await response.text()).toBeTruthy(); return response.json();
}
async function login(page: Page) {
  await page.goto("/"); await page.getByRole("button", { name: /Ayşe/ }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

test("öğrenme çıktısının seçilen konusu saklanır; konusuz çıktı ayrı dağılım grubunda görünür", async ({ page, request }, testInfo) => {
  const course = await post(request, "/courses", createE2eCourseIdentity("CIKTI-KONU"));
  const path = `/courses/${course.id}`;
  const topic = await post(request, `${path}/topics`, { name: "Deadlock" });
  await login(page); await page.goto(`${path}/blueprints`);
  await page.getByLabel("Çıktının konusu", { exact: true }).selectOption(topic.id);
  await page.getByLabel("Kod", { exact: true }).fill("CO1");
  await page.getByLabel("Açıklama", { exact: true }).fill("Deadlock koşullarını açıklar.");
  const saved = page.waitForResponse((r) => r.url() === `${API}${path}/learning-outcomes` && r.request().method() === "POST");
  await page.getByRole("button", { name: "Çıktı ekle", exact: true }).click();
  const response = await saved; expect(response.ok()).toBeTruthy();
  expect(response.request().postDataJSON().topic_id).toBe(topic.id);
  const linked = await response.json(); expect(linked.topic_id).toBe(topic.id);
  await expect(page.getByText("CO1", { exact: true })).toBeVisible();

  await page.getByLabel("Çıktının konusu", { exact: true }).selectOption("");
  await page.getByLabel("Kod", { exact: true }).fill("CO2");
  await page.getByLabel("Açıklama", { exact: true }).fill("Ders kavramlarını ilişkilendirir.");
  const unassigned = page.waitForResponse((r) => r.url() === `${API}${path}/learning-outcomes` && r.request().method() === "POST");
  await page.getByRole("button", { name: "Çıktı ekle", exact: true }).click();
  const nullResponse = await unassigned; expect(nullResponse.ok()).toBeTruthy();
  const generic = await nullResponse.json(); expect(generic.topic_id).toBeNull();
  await expect(page.getByText("Konu atanmadı; dağılımda ayrı gösterilir", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const colorScheme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    await page.getByLabel("Çıktının konusu", { exact: true }).focus();
    await expect(page.getByLabel("Çıktının konusu", { exact: true })).toBeFocused();
    await page.screenshot({ path: testInfo.outputPath(`outcome-topic-375-${colorScheme}.png`), fullPage: true });
  }
  const blueprint = await post(request, `${path}/blueprints`, {
    title: "Konu dağılımı", duration_minutes: 30, max_attempts: 1,
    cells: [linked, generic].map((outcome) => ({ learning_outcome_id: outcome.id, difficulty: "medium", question_type: "mcq", question_count: 1, points_per_question: 10 })),
  });
  expect(blueprint.topic_distribution).toEqual(expect.arrayContaining([
    { topic_id: topic.id, topic_name: "Deadlock", question_count: 1 },
    { topic_id: null, topic_name: null, question_count: 1 },
  ]));
  await page.goto(`${path}/blueprints?blueprint_id=${blueprint.id}`);
  await expect(page.getByText("Deadlock: 1 soru", { exact: true })).toBeVisible();
  await expect(page.getByText("Konusuz çıktıdan: 1 soru", { exact: true })).toBeVisible();
});

test("sınıflandırma kapalı görünürken mevcut uygun havuz yayınlanır ve güncel hazırlık sonucu üstün gelir", async ({ page, request }) => {
  test.setTimeout(90_000);
  const course = await post(request, "/courses", createE2eCourseIdentity("HAZIRLIK-KAPI"));
  const path = `/courses/${course.id}`;
  const topic = await post(request, `${path}/topics`, { name: "Deadlock" });
  const outcome = await post(request, `${path}/learning-outcomes`, { code: "CO1", description: "Kilitlenmeyi açıklar", topic_id: topic.id });
  const upload = await request.post(`${API}${path}/documents`, { headers, multipart: { file: {
    name: "readiness.md", mimeType: "text/markdown", buffer: Buffer.from("# Deadlock\nDeadlock iki veya daha fazla sürecin birbirini beklemesidir. Coffman koşulları karşılıklı dışlama, tut ve bekle, kesintisizlik ve dairesel beklemedir.\n"),
  } } });
  expect(upload.ok(), await upload.text()).toBeTruthy();
  await expect.poll(async () => (await (await request.get(`${API}${path}/documents`, { headers })).json()).items[0]?.status, { timeout: 25_000 }).toBe("completed");
  const generate = async (classified: boolean) => {
    const report = await post(request, `${path}/questions/generate`, { topic_id: topic.id, count: 1, question_type: "mcq",
      ...(classified ? { learning_outcome_id: outcome.id, difficulty: "medium" } : {}) });
    expect(report.questions).toHaveLength(1);
    await post(request, `${path}/questions/${report.questions[0].id}/approve`);
    return report.questions[0];
  };
  const good = await generate(true); const bad = await generate(false);
  const blueprint = await post(request, `${path}/blueprints`, { title: "Hazırlık kapısı", duration_minutes: 30, max_attempts: 1,
    cells: [{ learning_outcome_id: outcome.id, difficulty: "medium", question_type: "mcq", question_count: 1, points_per_question: 10 }] });
  const version = await post(request, `${path}/blueprints/${blueprint.id}/versions`);
  const base = `${path}/blueprints/${blueprint.id}/versions/${version.id}`;
  await post(request, `${base}/items`, [{ question_id: bad.id }]);
  await login(page);
  // Only the capability response is simulated. Readiness/items/publish use the real API;
  // backend flag rollback is covered separately by API tests.
  await page.route(`${API}${path}/questions/authoring`, (route) => route.fulfill({ json: { enabled: false } }));
  let publishRequests = 0;
  page.on("request", (r) => { if (r.url() === `${API}${base}/publish`) publishRequests += 1; });
  await page.goto(`${path}/blueprints?blueprint_id=${blueprint.id}`);
  const row = page.getByRole("listitem", { name: "Hazırlık kapısı · 1. sürüm", exact: true });
  await row.getByRole("button", { name: "Kapıyı denetle", exact: true }).click();
  await expect(row.getByText(/Soru sınıflandırma şu anda kapalı/)).toBeVisible();
  await expect(row.getByRole("button", { name: "Yayınla", exact: true })).toBeDisabled();
  await expect(row.getByRole("link", { name: "Soru havuzunu aç", exact: true })).toHaveCount(0);
  await row.getByRole("button", { name: "Kâğıdı düzenle", exact: true }).click();
  await row.getByRole("checkbox", { name: /zorluk atanmamış/ }).uncheck();
  await row.getByRole("checkbox", { name: /Orta.*CO1/ }).check();
  await row.getByRole("button", { name: "Kâğıdı kaydet", exact: true }).click();
  await expect(row.getByRole("button", { name: "Yayınla", exact: true })).toBeEnabled();
  await expect(row.getByRole("checkbox", { name: /Orta.*CO1/ })).toBeChecked();
  // Another editor changes the paper after the local green report. Never trust cached readiness.
  await post(request, `${base}/items`, [{ question_id: bad.id }]);
  await row.getByRole("button", { name: "Yayınla", exact: true }).click();
  await expect(row.getByRole("button", { name: "Yayınla", exact: true })).toBeDisabled();
  await expect(row.getByText(/Soru sınıflandırma şu anda kapalı/)).toBeVisible();
  expect(publishRequests).toBe(0);
  // Saving the still-selected, classified question repairs the real paper again.
  await row.getByRole("button", { name: "Kâğıdı kaydet", exact: true }).click();
  await expect(row.getByRole("button", { name: "Yayınla", exact: true })).toBeEnabled();
  const published = page.waitForResponse((r) => r.url() === `${API}${base}/publish` && r.request().method() === "POST");
  await row.getByRole("button", { name: "Yayınla", exact: true }).click();
  expect((await published).ok()).toBeTruthy();
  await expect(page.getByText("1. sürüm yayında", { exact: true })).toBeVisible();
  const items = await (await request.get(`${API}${base}/items`, { headers })).json();
  expect(items.map((item: { question_id: string }) => item.question_id)).toEqual([good.id]);
});
