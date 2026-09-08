import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { createE2eCourseIdentity } from "./fixtures";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const teacherHeaders = { Authorization: "Bearer dev:11111111-1111-1111-1111-111111111111" };
const studentId = "22222222-2222-2222-2222-222222222222";
const studentHeaders = { Authorization: `Bearer dev:${studentId}` };
const draftKey = `dou-synapse:exam-drafts:v1:${studentId}:privacy-synthetic:exam`;

async function prepareCourse(request: APIRequestContext) {
  const response = await request.post(`${API}/courses`, { headers: teacherHeaders, data: createE2eCourseIdentity("OTURUM-GIZLILIGI") });
  expect(response.ok(), await response.text()).toBeTruthy();
  const course = await response.json();
  const base = `${API}/courses/${course.id}`;
  expect((await request.post(`${base}/members`, { headers: teacherHeaders, data: { email: "burak@dogus.edu.tr", role: "student" } })).ok()).toBeTruthy();
  const upload = await request.post(`${base}/documents`, { headers: teacherHeaders, multipart: {
    file: { name: "privacy-synthetic.md", mimeType: "text/markdown", buffer: Buffer.from("# Deadlock\nDeadlock iki veya daha fazla sürecin birbirini beklemesidir. Coffman koşulları karşılıklı dışlama, tut ve bekle, kesintisizlik ve dairesel beklemedir.\n") },
  } });
  expect(upload.ok(), await upload.text()).toBeTruthy();
  await expect.poll(async () => (await (await request.get(`${base}/documents`, { headers: teacherHeaders })).json()).items[0]?.status, { timeout: 25_000 }).toBe("completed");
  return { course, base };
}

async function login(page: Page, teacher = false) {
  await page.goto("/");
  await page.getByRole("button", { name: teacher ? /Ayşe Hoca/ : /Burak Yılmaz/ }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

async function seedDraft(page: Page, text: string) {
  await page.evaluate(({ key, text }) => {
    sessionStorage.setItem(key, JSON.stringify({ version: 1, updatedAt: Date.now(), drafts: { question: text } }));
    sessionStorage.setItem("privacy-test:unrelated", "keep");
    localStorage.setItem("privacy-test:preference", "keep");
  }, { key: draftKey, text });
}

async function assertDraftGone(page: Page) {
  expect(await page.evaluate((key) => sessionStorage.getItem(key), draftKey)).toBeNull();
  expect(await page.evaluate(() => sessionStorage.getItem("privacy-test:unrelated"))).toBe("keep");
  expect(await page.evaluate(() => localStorage.getItem("privacy-test:preference"))).toBe("keep");
}

async function paint(page: Page) {
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
}

/** Yanıt uydurulmaz: gerçek API'nin yetkili 200 yanıtı yalnız ağda bekletilir. */
async function holdChat(page: Page, base: string) {
  let release!: () => void;
  let captured!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  const seen = new Promise<void>((resolve) => { captured = resolve; });
  await page.route(`${base}/chat`, async (route) => {
    const response = await route.fetch();
    expect(response.status()).toBe(200);
    captured();
    await gate;
    await route.fulfill({ response });
  }, { times: 1 });
  return { release, seen };
}

async function send(page: Page, text: string) {
  await page.getByRole("textbox", { name: "Sorun", exact: true }).fill(text);
  await page.getByRole("button", { name: "Gönder", exact: true }).click();
}

test("çıkış iki sekmenin taslağını ve özel görünümünü kapatır; geç sohbet yanıtı geri yazamaz", async ({ page, context, request }) => {
  test.setTimeout(90_000);
  const { course, base } = await prepareCourse(request);
  await login(page); await page.goto(`/courses/${course.id}/chat`);
  await expect(page.getByRole("textbox", { name: "Sorun", exact: true })).toBeVisible();
  const second = await context.newPage(); await second.goto("/dashboard");
  await expect(second.getByRole("button", { name: "Çıkış", exact: true }).first()).toBeVisible();
  await seedDraft(page, "Birinci sekme sentetik cevabı");
  await seedDraft(second, "İkinci sekme sentetik cevabı");
  const remembered = `dou-synapse-chat-session:${course.id}`;
  await page.evaluate((key) => localStorage.setItem(key, "synthetic-old-selection"), remembered);
  const hold = await holdChat(page, base);
  await send(page, "Coffman koşulları nelerdir? Sentetik özel öğrenci sorusu.");
  await hold.seen;
  try {
    await second.getByRole("button", { name: "Çıkış", exact: true }).first().click();
    // Background tab closes without bringToFront/focus/manual invalidation.
    await expect(second).toHaveURL(/\/$/); await expect(page).toHaveURL(/\/$/);
    await assertDraftGone(page); await assertDraftGone(second);
    expect(await page.evaluate((key) => localStorage.getItem(key), remembered)).toBeNull();
    const delivered = page.waitForResponse((response) => response.url() === `${base}/chat` && response.status() === 200);
    hold.release(); await delivered; await paint(page);
    expect(await page.evaluate((key) => localStorage.getItem(key), remembered)).toBeNull();
    await expect(page.getByRole("textbox", { name: "Sorun", exact: true })).toHaveCount(0);
    const marker = await page.evaluate(() => localStorage.getItem("dou-synapse:auth-event:v1"));
    expect(marker).toMatch(/^signed-out:[a-f0-9-]+$/);
    expect(marker).not.toContain(studentId);
    await page.reload(); await assertDraftGone(page);
  } finally { hold.release(); }
});

test("başka sekmede kimlik değişimi eski öğrencinin ekran ve taslaklarını yeni hesaba taşımaz", async ({ page, context, request }) => {
  test.setTimeout(90_000);
  const { course } = await prepareCourse(request);
  await login(page); await page.goto(`/courses/${course.id}/chat`);
  await page.getByRole("textbox", { name: "Sorun", exact: true }).fill("Sentetik öğrenciye özel gönderilmemiş soru");
  await seedDraft(page, "Sentetik öğrenci cevabı");
  // Normal same-user reload must preserve an unfinished local answer.
  await page.reload();
  await expect(page.getByRole("textbox", { name: "Sorun", exact: true })).toBeVisible();
  expect(await page.evaluate((key) => sessionStorage.getItem(key), draftKey)).not.toBeNull();
  const second = await context.newPage(); await login(second, true);
  await expect(page).toHaveURL(/\/$/); await assertDraftGone(page);
  await page.goto(`/courses/${course.id}/chat`);
  await expect(page.getByText("Eğitmen Asistanı", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Sorun", exact: true })).toHaveValue("");
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("dou-synapse-user")!).id)).toBe("11111111-1111-1111-1111-111111111111");
});

test("sohbet sayfasından ayrıldıktan sonra eski yanıt açık oturum anahtarını yeniden oluşturmaz", async ({ page, request }) => {
  test.setTimeout(90_000);
  const { course, base } = await prepareCourse(request);
  await login(page); await page.goto(`/courses/${course.id}/chat`);
  const hold = await holdChat(page, base);
  await send(page, "Deadlock nedir? Sentetik gecikmeli soru."); await hold.seen;
  try {
    await page.getByRole("link", { name: "Dersler", exact: true }).first().click();
    await expect(page).toHaveURL(/\/courses$/);
    const delivered = page.waitForResponse((response) => response.url() === `${base}/chat` && response.status() === 200);
    hold.release(); await delivered; await paint(page);
    expect(await page.evaluate((id) => localStorage.getItem(`dou-synapse-chat-session:${id}`), course.id)).toBeNull();
  } finally { hold.release(); }
});

for (const destination of ["new", "other"] as const) {
  test(`geç eski mesaj sayfası ${destination === "new" ? "yeni boş sohbete" : "başka sohbete"} eklenemez`, async ({ page, request }) => {
    test.setTimeout(90_000);
    const { course, base } = await prepareCourse(request);
    const post = async (question: string, sessionId?: string) => {
      const response = await request.post(`${base}/chat`, { headers: studentHeaders, data: { question, mode: "qa", ...(sessionId ? { session_id: sessionId } : {}) } });
      expect(response.status(), await response.text()).toBe(200); return response.json();
    };
    const firstQuestion = "Coffman koşulları nelerdir? İlk oturum sorusu.";
    const privateOlder = "Deadlock nedir? Önceki özel öğrenci açıklaması.";
    const latestQuestion = "Dairesel bekleme nedir? Son öğrenci sorusu.";
    const first = await post(firstQuestion);
    await post(privateOlder, first.session_id); await post(latestQuestion, first.session_id);
    const otherQuestion = "Karşılıklı dışlama nedir? Diğer sohbet sorusu.";
    const other = await post(otherQuestion);
    await login(page);
    // Daha küçük gerçek sayfa kullanılır; içerik/cursor/yetki sunucudan gelir.
    let release!: () => void; let captured!: () => void;
    const gate = new Promise<void>((resolve) => { release = resolve; });
    const seen = new Promise<void>((resolve) => { captured = resolve; });
    await page.route(`${base}/chat/sessions/${first.session_id}**`, async (route) => {
      const url = new URL(route.request().url()); url.searchParams.set("limit", "2");
      const response = await route.fetch({ url: url.toString() });
      expect(response.status()).toBe(200);
      if (url.searchParams.has("cursor")) { captured(); await gate; }
      await route.fulfill({ response });
    });
    await page.goto(`/courses/${course.id}/chat`);
    await page.getByRole("button", { name: new RegExp(firstQuestion.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) }).click();
    await expect(page.getByText(latestQuestion, { exact: true })).toBeVisible();
    await expect(page.getByText(privateOlder, { exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Devamını yükle", exact: true }).click();
    await seen;
    try {
      if (destination === "new") await page.getByRole("button", { name: "Yeni sohbet", exact: true }).click();
      else {
        await page.getByRole("button", { name: new RegExp(otherQuestion.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) }).click();
        await expect(page.locator("p").filter({ hasText: otherQuestion })).toBeVisible();
      }
      const delivered = page.waitForResponse((response) => response.url().includes(`/chat/sessions/${first.session_id}?`) && response.status() === 200);
      release(); await delivered; await paint(page);
      await expect(page.getByText(privateOlder, { exact: true })).toHaveCount(0);
      await expect(page.getByText(latestQuestion, { exact: true })).toHaveCount(0);
      expect(await page.evaluate((id) => localStorage.getItem(`dou-synapse-chat-session:${id}`), course.id)).toBe(destination === "new" ? null : other.session_id);
      await expect(page.getByRole("button", { name: "Devamını yükle", exact: true })).toHaveCount(0);
    } finally { release(); }
  });
}
