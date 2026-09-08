import { expect, test, type APIRequestContext } from "@playwright/test";
import { createE2eCourseIdentity } from "./fixtures";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const headers = { Authorization: "Bearer dev:11111111-1111-1111-1111-111111111111" };
async function post(request: APIRequestContext, path: string, data: unknown = {}) {
  const response = await request.post(`${API}${path}`, { headers, data });
  expect(response.ok(), await response.text()).toBeTruthy(); return response.json();
}
function gate() {
  let release!: () => void; let captured!: () => void;
  return { hold: new Promise<void>((resolve) => { release = resolve; }),
    seen: new Promise<void>((resolve) => { captured = resolve; }),
    release: () => release(), captured: () => captured() };
}

test("sunucu süzgeci ilk sayfa dışını bulur; boş sonuç ve geç devam sayfası seçimi bozmaz", async ({ page, request }, testInfo) => {
  test.setTimeout(120_000);
  const course = await post(request, "/courses", createE2eCourseIdentity("HAVUZ-SUZGEC"));
  const path = `/courses/${course.id}`;
  const topics: Array<{ id: string; name: string; outcome: { id: string } }> = [];
  for (const [name, code] of [["Deadlock", "CO1"], ["Coffman koşulları", "CO2"]]) {
    const topic = await post(request, `${path}/topics`, { name });
    const outcome = await post(request, `${path}/learning-outcomes`, { code, description: `${name} konusunu açıklar`, topic_id: topic.id });
    topics.push({ ...topic, outcome });
  }
  const upload = await request.post(`${API}${path}/documents`, { headers, multipart: { file: {
    name: "question-filter.md", mimeType: "text/markdown", buffer: Buffer.from("# Deadlock ve Coffman koşulları\nDeadlock iki veya daha fazla sürecin birbirini beklemesidir. Coffman koşulları karşılıklı dışlama, tut ve bekle, kesintisizlik ve dairesel beklemedir.\n"),
  } } });
  expect(upload.ok(), await upload.text()).toBeTruthy();
  await expect.poll(async () => (await (await request.get(`${API}${path}/documents`, { headers })).json()).items[0]?.status, { timeout: 25_000 }).toBe("completed");
  let sequence = 0;
  for (const [index, topic] of topics.entries()) {
    const count = index === 0 ? 6 : 2;
    const report = await post(request, `${path}/questions/generate`, { topic_id: topic.id, count, question_type: "mcq" });
    expect(report.questions).toHaveLength(count);
    for (const question of report.questions) {
      // Give generated drafts distinguishable, synthetic instructor edits through the real API.
      await post(request, `${path}/questions/${question.id}/draft`, {
        payload: { ...question.payload, stem: `Deadlock ve Coffman koşulları: soru ${++sequence}` },
        learning_outcome_id: topic.outcome.id, difficulty: "medium",
      });
    }
  }
  const all = (await (await request.get(`${API}${path}/questions?limit=20`, { headers })).json()).items;
  const topicA = all.filter((question: { topic_id: string }) => question.topic_id === topics[0].id);
  const target = topicA.at(-1);
  await post(request, `${path}/questions/${target.id}/approve`);
  await post(request, `${path}/questions/${topicA.at(-2).id}/reject`);
  expect(all.slice(0, 2).map((question: { id: string }) => question.id)).not.toContain(target.id);

  const old = gate(); let holdNextCursor = false;
  const queries: URLSearchParams[] = [];
  await page.route(`${API}${path}/questions**`, async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname !== `${path}/questions` || route.request().method() !== "GET") return route.continue();
    queries.push(new URLSearchParams(url.search));
    url.searchParams.set("limit", "2"); // Real pagination with small pages, never a substituted item list.
    const response = await route.fetch({ url: url.toString() });
    expect(response.ok()).toBeTruthy();
    if (holdNextCursor && url.searchParams.has("cursor")) {
      holdNextCursor = false; old.captured(); await old.hold;
    }
    await route.fulfill({ response });
  });
  await page.goto("/"); await page.getByRole("button", { name: /Ayşe/ }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.goto(`${path}/questions`);
  const filters = page.getByRole("group", { name: "Soruların durum süzgeci", exact: true });
  const list = page.getByRole("list", { name: "Soru havuzu", exact: true });
  await expect(list.getByRole("button")).toHaveCount(2);
  await filters.getByRole("button", { name: "Onaylananlar", exact: true }).click();
  await expect(list.getByRole("button")).toHaveCount(1);
  await expect(list).toContainText(target.payload.stem);
  expect(queries.at(-1)?.get("status")).toBe("approved");
  expect(queries.at(-1)?.has("cursor")).toBe(false);

  await filters.getByRole("button", { name: "Reddedilenler", exact: true }).click();
  await expect(list.getByRole("button")).toHaveCount(1);
  await expect(list).toContainText(topicA.at(-2).payload.stem);
  expect(queries.at(-1)?.get("status")).toBe("rejected");
  await filters.getByRole("button", { name: "Taslaklar", exact: true }).click();
  await page.getByLabel("Konu süzgeci", { exact: true }).selectOption(topics[0].id);
  await expect(list.getByRole("button")).toHaveCount(2);
  await page.getByRole("button", { name: "Devamını yükle", exact: true }).click();
  await expect(list.getByRole("button")).toHaveCount(4);
  expect(queries.at(-1)?.get("status")).toBe("draft");
  expect(queries.at(-1)?.get("topic_id")).toBe(topics[0].id);
  expect(queries.at(-1)?.has("cursor")).toBe(true);
  await filters.getByRole("button", { name: "Onaylananlar", exact: true }).click();
  await expect(list.getByRole("button")).toHaveCount(1);
  expect(queries.at(-1)?.has("cursor")).toBe(false);
  await page.getByLabel("Konu süzgeci", { exact: true }).selectOption(topics[1].id);
  await expect(page.getByText("Bu süzgeçte soru yok. Başka bir durum veya konu seçebilirsin.", { exact: true })).toBeVisible();
  await expect(filters).toBeVisible();
  await expect(page.getByLabel("Konu süzgeci", { exact: true })).toBeEnabled();
  expect(queries.at(-1)?.get("status")).toBe("approved");
  expect(queries.at(-1)?.get("topic_id")).toBe(topics[1].id);
  await filters.getByRole("button", { name: "Tümü", exact: true }).click();
  await page.getByLabel("Konu süzgeci", { exact: true }).selectOption("all");
  await expect(list.getByRole("button")).toHaveCount(2);
  await expect(page.getByRole("button", { name: "Devamını yükle", exact: true })).toBeVisible();
  holdNextCursor = true;
  await page.getByRole("button", { name: "Devamını yükle", exact: true }).click();
  await old.seen;
  try {
    await filters.getByRole("button", { name: "Onaylananlar", exact: true }).click();
    await expect(list.getByRole("button")).toHaveCount(1);
    expect(queries.at(-1)?.has("cursor")).toBe(false);
    const delivered = page.waitForResponse((response) => new URL(response.url()).searchParams.has("cursor") && response.status() === 200);
    old.release(); await delivered;
    await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
    await expect(list.getByRole("button")).toHaveCount(1);
    await expect(list).toContainText(target.payload.stem);
    await expect(page.getByRole("button", { name: "Devamını yükle", exact: true })).toHaveCount(0);
  } finally { old.release(); }

  await filters.getByRole("button", { name: "Taslaklar", exact: true }).click();
  await page.getByLabel("Konu süzgeci", { exact: true }).selectOption(topics[1].id);
  await expect(list.getByRole("button")).toHaveCount(2);
  await page.getByRole("button", { name: "Taslağı düzenle", exact: true }).click();
  await expect(filters.getByRole("button", { name: "Tümü", exact: true })).toBeDisabled();
  await expect(page.getByLabel("Konu süzgeci", { exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Vazgeç", exact: true }).click();
  const selectedStem = await page.getByRole("heading", { name: /^Deadlock ve Coffman koşulları: soru/ }).innerText();
  await page.getByRole("button", { name: "Onayla ve öğrenciye aç", exact: true }).click();
  await expect(list.getByRole("button")).toHaveCount(1);
  await expect(page.getByRole("heading", { name: selectedStem, exact: true })).toBeVisible();
  await expect(page.getByText(/Bu soru seçili süzgeçte görünmüyor/)).toBeVisible();
  await page.getByRole("button", { name: "Sıradaki taslağa geç", exact: true }).click();
  const lastStem = await page.getByRole("heading", { name: /^Deadlock ve Coffman koşulları: soru/ }).innerText();
  await page.getByRole("button", { name: "Onayla ve öğrenciye aç", exact: true }).click();
  await expect(page.getByText("Bu süzgeçte soru yok.", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: lastStem, exact: true })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "Soru onaylandı" })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const colorScheme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`question-filters-375-${colorScheme}.png`), fullPage: true });
  }
});
