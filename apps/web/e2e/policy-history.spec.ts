import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { createE2eCourseIdentity } from "./fixtures";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const teacher = { Authorization: "Bearer dev:11111111-1111-1111-1111-111111111111" };
const student = { Authorization: "Bearer dev:22222222-2222-2222-2222-222222222222" };
async function course(request: APIRequestContext) {
  const response = await request.post(`${API}/courses`, { headers: teacher, data: createE2eCourseIdentity("POLITIKA-GECMISI") });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json() as Promise<{ id: string }>;
}
async function login(page: Page, name: "Ayşe" | "Burak" = "Ayşe") {
  await page.goto("/"); await page.getByRole("button", { name: new RegExp(name) }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}
async function put(request: APIRequestContext, id: string, hint: number) {
  const response = await request.put(`${API}/courses/${id}/ai-policy`, { headers: teacher, data: { hint_limit: hint } });
  expect(response.ok(), await response.text()).toBeTruthy();
}

test("politika geçmişi gerçek kayıt farklarını gösterir; yenileme hatası düzenleme taslağını silmez", async ({ page, request }, testInfo) => {
  const c = await course(request); const path = `/courses/${c.id}/ai-policy`;
  await login(page); await page.goto(`/courses/${c.id}/settings`);
  const history = page.getByRole("region", { name: "Politika geçmişi", exact: true });
  await expect(history.getByText("Henüz politika değişikliği kaydedilmedi.", { exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: "Global üst sınırı kullan", exact: true }).uncheck();
  await page.getByRole("spinbutton", { name: "İpucu sınırı", exact: true }).fill("2");
  async function save(count: number) {
    const saved = page.waitForResponse((r) => r.url() === `${API}${path}` && r.request().method() === "PUT");
    await page.getByRole("button", { name: "Politikayı kaydet", exact: true }).click();
    expect((await saved).ok()).toBeTruthy();
    await expect(history.getByRole("list", { name: "Politika kayıtları" }).locator(":scope > li")).toHaveCount(count);
  }
  await save(1);
  await history.getByLabel("Politika kaydı 1", { exact: true }).click();
  await expect(history.getByText("Önce: Politika yok", { exact: true }).first()).toBeVisible();
  await expect(history.getByText("Sonra: 2", { exact: true })).toBeVisible();
  await expect(history.getByText(/· Siz$/).first()).toBeVisible();
  await page.getByRole("spinbutton", { name: "İpucu sınırı", exact: true }).fill("3");
  await save(2);
  const latest = history.getByRole("list", { name: "Politika kayıtları" }).locator(":scope > li").first();
  await latest.getByLabel("Politika kaydı 1", { exact: true }).click();
  await expect(latest.getByText("Önce: 2", { exact: true })).toBeVisible();
  await expect(latest.getByText("Sonra: 3", { exact: true })).toBeVisible();
  await save(3);
  await latest.getByLabel("Politika kaydı 1", { exact: true }).click();
  await expect(latest.getByText("Değerler değişmeden kaydedildi.", { exact: true })).toBeVisible();

  await page.getByRole("spinbutton", { name: "İpucu sınırı", exact: true }).fill("4");
  const historyUrl = `${API}${path}/history?**`;
  await page.route(historyUrl, (route) => route.fulfill({ status: 503, json: {
    error: { code: "synthetic_unavailable", message: "Geçmiş şu anda yüklenemiyor.", request_id: "policy-history-retry" },
  } }));
  await history.getByRole("button", { name: "Geçmişi yenile" }).click();
  await expect(history.getByRole("alert")).toHaveText("Geçmiş şu anda yüklenemiyor.");
  await expect(history.getByText(/policy-history-retry/)).toBeVisible();
  await expect(page.getByRole("spinbutton", { name: "İpucu sınırı", exact: true })).toHaveValue("4");
  await page.unroute(historyUrl);
  await history.getByRole("button", { name: "Tekrar dene", exact: true }).click();
  await expect(history.getByRole("list", { name: "Politika kayıtları" }).locator(":scope > li")).toHaveCount(3);
  await expect(page.getByRole("spinbutton", { name: "İpucu sınırı", exact: true })).toHaveValue("4");
  const roleUrl = `${API}/courses/${c.id}`;
  let releaseRole!: () => void; let roleFetched!: () => void;
  const heldRole = new Promise<void>((resolve) => { releaseRole = resolve; });
  const fetchedRole = new Promise<void>((resolve) => { roleFetched = resolve; });
  await page.route(roleUrl, async (route) => {
    const actual = await route.fetch(); expect(actual.ok()).toBeTruthy(); roleFetched();
    await heldRole; await route.fulfill({ response: actual });
  });
  let requestsWhileRoleUnknown = 0;
  const countUnknownRequests = (r: { url(): string }) => {
    if (r.url().startsWith(`${API}${path}`)) requestsWhileRoleUnknown += 1;
  };
  page.on("request", countUnknownRequests);
  try {
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    await fetchedRole;
    await expect(history).toHaveCount(0);
    await expect(page.getByRole("spinbutton", { name: "İpucu sınırı", exact: true })).toHaveCount(0);
    expect(requestsWhileRoleUnknown).toBe(0);
    page.off("request", countUnknownRequests);
    releaseRole();
    await expect(history.getByRole("list", { name: "Politika kayıtları" }).locator(":scope > li")).toHaveCount(3);
    await expect(page.getByRole("spinbutton", { name: "İpucu sınırı", exact: true })).toHaveValue("4");
  } finally {
    page.off("request", countUnknownRequests); releaseRole(); await page.unroute(roleUrl);
  }
  await page.setViewportSize({ width: 375, height: 812 });
  await page.emulateMedia({ reducedMotion: "reduce", colorScheme: "dark" });
  const summary = latest.getByLabel("Politika kaydı 1", { exact: true });
  await summary.focus(); await page.keyboard.press("Enter");
  await expect(latest.locator("details")).toHaveAttribute("open", "");
  await expect(summary).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("policy-history-375-dark.png"), fullPage: true });
});

test("geçmiş sayfalanır; geç gelen eski sayfa yeni konumu değiştirmez", async ({ page, request }) => {
  const c = await course(request);
  for (let i = 0; i < 22; i += 1) await put(request, c.id, i % 5);
  await login(page); await page.goto(`/courses/${c.id}/settings`);
  const history = page.getByRole("region", { name: "Politika geçmişi", exact: true });
  const rows = history.getByRole("list", { name: "Politika kayıtları" }).locator(":scope > li");
  await expect(rows).toHaveCount(20);
  await history.getByRole("button", { name: "Daha eski kayıtlar", exact: true }).click();
  await expect(rows).toHaveCount(2);
  await expect(history.getByLabel("Politika kaydı 22", { exact: true })).toBeVisible();
  await expect(history.getByRole("button", { name: "Daha eski kayıtlar", exact: true })).toHaveCount(0);
  await history.getByRole("button", { name: "Daha yeni kayıtlar", exact: true }).click();
  await expect(rows).toHaveCount(20);
  let release!: () => void; let fetched!: () => void;
  const held = new Promise<void>((resolve) => { release = resolve; });
  const ready = new Promise<void>((resolve) => { fetched = resolve; });
  await page.route(`${API}/courses/${c.id}/ai-policy/history?limit=21&offset=20`, async (route) => {
    const actual = await route.fetch(); expect(actual.status()).toBe(200); fetched();
    await held; await route.fulfill({ response: actual });
  }, { times: 1 });
  try {
    await history.getByRole("button", { name: "Daha eski kayıtlar", exact: true }).click();
    await ready;
    await history.getByRole("button", { name: "Daha yeni kayıtlar", exact: true }).click();
    await expect(rows).toHaveCount(20);
    const late = page.waitForResponse((r) => r.url().endsWith("/ai-policy/history?limit=21&offset=20"));
    release(); await late;
    await expect(rows).toHaveCount(20);
    await expect(history.getByLabel("Politika kaydı 1", { exact: true })).toBeVisible();
    await expect(history.getByLabel("Politika kaydı 21", { exact: true })).toHaveCount(0);
  } finally { release(); }
});

test("öğrenci ve ders dışı hesap politika geçmişine erişemez", async ({ page, request }) => {
  const c = await course(request); await put(request, c.id, 2);
  const url = `${API}/courses/${c.id}/ai-policy/history`;
  const outsider = await request.get(url, { headers: student });
  expect([403, 404]).toContain(outsider.status());
  const joined = await request.post(`${API}/courses/${c.id}/members`, { headers: teacher, data: { email: "burak@dogus.edu.tr", role: "student" } });
  expect(joined.ok(), await joined.text()).toBeTruthy();
  const forbidden = await request.get(url, { headers: student }); expect(forbidden.status()).toBe(403);
  let historyRequests = 0;
  page.on("request", (r) => { if (r.url().startsWith(url)) historyRequests += 1; });
  await login(page, "Burak"); await page.goto(`/courses/${c.id}/settings`);
  await expect(page.getByText("AI politikası yalnızca dersin eğitmenine gösterilir.", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Politika geçmişi", exact: true })).toHaveCount(0);
  expect(historyRequests).toBe(0);
});


for (const denial of ["student", "forbidden"] as const) {
  test(`kesin rol reddi taslağı temizler ve geçmişi kapatır (${denial})`, async ({ page, request }) => {
    const c = await course(request); await put(request, c.id, 3);
    await login(page); await page.goto(`/courses/${c.id}/settings`);
    const hint = page.getByRole("spinbutton", { name: "İpucu sınırı", exact: true });
    await expect(hint).toHaveValue("3"); await hint.fill("4");
    const roleUrl = `${API}/courses/${c.id}`;
    await page.route(roleUrl, async (route) => {
      if (denial === "forbidden") {
        await route.fulfill({ status: 403, json: { error: {
          code: "permission_denied", message: "Ders erişimi kapatıldı.", request_id: "policy-role-denied",
        } } });
      } else {
        const actual = await route.fetch();
        expect(actual.ok()).toBeTruthy();
        await route.fulfill({ response: actual, json: { ...await actual.json(), role: "student" } });
      }
    });
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    await expect(page.getByText("AI politikası yalnızca dersin eğitmenine gösterilir.", { exact: true })).toBeVisible();
    await expect(page.getByRole("region", { name: "Politika geçmişi", exact: true })).toHaveCount(0);
    await expect(hint).toHaveCount(0);
    await page.unroute(roleUrl);
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    await expect(hint).toHaveValue("3");
    await expect(page.getByRole("region", { name: "Politika geçmişi", exact: true })).toBeVisible();
  });
}
