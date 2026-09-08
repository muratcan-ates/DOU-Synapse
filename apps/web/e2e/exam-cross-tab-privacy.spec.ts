import { expect, test, type APIRequestContext, type Page, type Route } from "@playwright/test";
import { createE2eCourseIdentity } from "./fixtures";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const teacherHeaders = { Authorization: "Bearer dev:11111111-1111-1111-1111-111111111111" };
const studentHeaders = { Authorization: "Bearer dev:22222222-2222-2222-2222-222222222222" };
const sourceName = "exam-cross-tab-synthetic.md";

async function prepareCourse(request: APIRequestContext) {
  const post = async (path: string, data: unknown) => {
    const response = await request.post(`${API}${path}`, { headers: teacherHeaders, data });
    expect(response.ok(), await response.text()).toBeTruthy(); return response.json();
  };
  const course = await post("/courses", createE2eCourseIdentity("SINAV-SEKMELER"));
  const path = `/courses/${course.id}`;
  await post(`${path}/members`, { email: "burak@dogus.edu.tr", role: "student" });
  const topic = await post(`${path}/topics`, { name: "Deadlock" });
  const upload = await request.post(`${API}${path}/documents`, { headers: teacherHeaders, multipart: {
    file: { name: sourceName, mimeType: "text/markdown", buffer: Buffer.from("# Deadlock\nDeadlock iki veya daha fazla sürecin birbirini beklemesidir. Coffman koşulları karşılıklı dışlama, tut ve bekle, kesintisizlik ve dairesel beklemedir.\n") },
  } });
  expect(upload.ok(), await upload.text()).toBeTruthy();
  await expect.poll(async () => (await (await request.get(`${API}${path}/documents`, { headers: teacherHeaders })).json()).items[0]?.status, { timeout: 25_000 }).toBe("completed");
  const generated = await post(`${path}/questions/generate`, { topic_id: topic.id, count: 1, question_type: "mcq" });
  expect(generated.questions).toHaveLength(1);
  const question = generated.questions[0];
  await post(`${path}/questions/${question.id}/approve`, {});
  expect(question.source?.chunk_id).toBeTruthy();
  return { course, base: `${API}${path}`, sourcePath: `${path}/sources/${question.source.chunk_id}` };
}

async function login(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: /Burak Yılmaz/ }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

async function finish(page: Page) {
  await page.getByRole("button", { name: "Sınavı bitir", exact: true }).click();
  await page.getByRole("button", { name: "Bitir ve sonucu gör", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sınav sonucu", exact: true })).toBeVisible();
}

async function startExam(page: Page, courseId: string) {
  await page.goto(`/courses/${courseId}/exam`);
  const restart = page.getByRole("button", { name: "Yeni sınav başlat", exact: true });
  await expect(page.getByRole("heading", { name: /^(Sınav provası|Sınav sonucu)$/ })).toBeVisible();
  if (await restart.isVisible()) await restart.click();
  await page.getByRole("button", { name: "Sınav başlat", exact: true }).click();
  await expect(page.getByRole("timer")).toBeVisible();
}

function gate() {
  let release!: () => void; let captured!: () => void;
  return { hold: new Promise<void>((resolve) => { release = resolve; }),
    seen: new Promise<void>((resolve) => { captured = resolve; }),
    release: () => release(), captured: () => captured() };
}

async function paint(page: Page) {
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
}

test("başka sekmede sınav başlayınca tam/kompakt sohbet ve eski sonuç kapanır; geç açık karar geri açamaz", async ({ page, context, request }) => {
  test.setTimeout(150_000);
  const { course, base } = await prepareCourse(request);
  await login(page);
  await page.goto(`/courses/${course.id}/exam`);
  await page.getByRole("button", { name: "Alıştırma başlat", exact: true }).click();
  await page.getByRole("radio").first().check();
  await page.getByRole("button", { name: "Cevabı gönder", exact: true }).click();
  await expect(page.getByText("Cevap anahtarı", { exact: true })).toBeVisible();
  await finish(page);
  await expect(page.getByText("Cevap anahtarı", { exact: true })).toBeVisible();

  const full = await context.newPage(); await full.goto(`/courses/${course.id}/chat`);
  await full.getByRole("textbox", { name: "Sorun", exact: true }).fill("Coffman koşulları nelerdir?");
  const fullAnswer = full.waitForResponse((response) => response.url() === `${base}/chat` && response.request().method() === "POST");
  await full.getByRole("button", { name: "Gönder", exact: true }).click();
  expect((await fullAnswer).status()).toBe(200);
  await expect(full.getByRole("button", { name: "Gönder", exact: true })).toBeVisible();

  const compact = await context.newPage(); await compact.goto("/dashboard");
  const courseCard = compact.locator('section[aria-labelledby="course-workspaces-title"] > ul > li').filter({ hasText: course.code });
  await courseCard.getByRole("button", { name: "Ders asistanı", exact: true }).click();
  const dialog = compact.getByRole("dialog");
  await expect(dialog.getByRole("textbox", { name: "Sorun", exact: true })).toBeVisible();
  await dialog.getByRole("textbox", { name: "Sorun", exact: true }).fill("Deadlock nedir?");
  const compactAnswer = compact.waitForResponse((response) => response.url() === `${base}/chat` && response.request().method() === "POST");
  await dialog.getByRole("button", { name: "Gönder", exact: true }).click();
  expect((await compactAnswer).status()).toBe(200);
  await expect(dialog.getByRole("button", { name: "Gönder", exact: true })).toBeVisible();

  const old = gate();
  await full.route(`${base}/chat/availability`, async (route) => {
    const response = await route.fetch(); expect((await response.json()).available).toBe(true);
    old.captured(); await old.hold; await route.fulfill({ response });
  }, { times: 1 });
  await full.evaluate(() => window.dispatchEvent(new Event("pageshow")));
  await old.seen;
  const fresh = gate();
  const holdFresh = async (route: Route) => { fresh.captured(); await fresh.hold; await route.fallback(); };
  await compact.route(`${base}/chat/availability`, holdFresh);
  try {
    const fullLocked = full.waitForResponse(async (response) => response.url() === `${base}/chat/availability` &&
      response.status() === 200 && (await response.json()).reason === "exam_in_progress");
    const exam = await context.newPage(); await startExam(exam, course.id);
    await fresh.seen;
    const lockedDecision = await (await fullLocked).json();
    await expect(full.getByText(lockedDecision.message, { exact: true })).toBeVisible();
    // No focus/bringToFront on these background tabs: the storage event is required.
    await expect(dialog.getByRole("textbox", { name: "Sorun", exact: true })).toHaveCount(0);
    await expect(dialog.getByText("Asistan profili yükleniyor…", { exact: true })).toBeVisible();
    await expect(full.getByRole("textbox", { name: "Sorun", exact: true })).toHaveCount(0);
    await expect(page.getByText("Cevap anahtarı", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Tekrar dene", exact: true })).toBeVisible();
    fresh.release(); await compact.unroute(`${base}/chat/availability`, holdFresh);
    await expect(dialog.getByText("Asistan sınav sırasında kapalı", { exact: true })).toBeVisible();
    const delivered = full.waitForResponse((response) => response.url() === `${base}/chat/availability` && response.status() === 200 && !response.request().failure());
    old.release(); await delivered; await paint(full);
    await expect(full.getByRole("textbox", { name: "Sorun", exact: true })).toHaveCount(0);
    expect((await (await request.get(`${base}/chat/availability`, { headers: studentHeaders })).json()).reason).toBe("exam_in_progress");
    const marker = await exam.evaluate(() => localStorage.getItem("dou-synapse:exam-event:v1"));
    expect(marker).toMatch(/^[a-f0-9-]{36}$/);
    await finish(exam);
    await expect(full.getByRole("textbox", { name: "Sorun", exact: true })).toBeVisible();
    await expect(dialog.getByRole("textbox", { name: "Sorun", exact: true })).toBeVisible();
    await expect(page.getByText("Cevap anahtarı", { exact: true })).toBeVisible();
  } finally { old.release(); fresh.release(); }
});

test("kaynak pasajı başka sekmenin sınavında ve geç200 karşısında gizlenir; asistan bakımı kaynak izni değildir", async ({ page, context, request }, testInfo) => {
  test.setTimeout(120_000);
  const { course, base, sourcePath } = await prepareCourse(request);
  await login(page);
  // Only the operational status is simulated; source authorization stays real.
  await page.route(`${base}/chat/availability`, async (route) => {
    const response = await route.fetch(); const body = await response.json();
    await route.fulfill({ response, json: { ...body, available: false, reason: "globally_disabled", message: "Ders asistanı bakımda.", allowed_modes: [] } });
  });
  await page.setViewportSize({ width: 375, height: 812 });
  await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
  await page.goto(sourcePath);
  await expect(page.getByRole("heading", { name: sourceName, exact: true })).toBeVisible();
  await expect(page.getByText("Atıfta kullanılan pasaj", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("source-independent-access-375-dark.png"), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);

  const old = gate();
  await page.route(`${API}${sourcePath}`, async (route) => {
    const response = await route.fetch(); expect(response.status()).toBe(200);
    old.captured(); await old.hold; await route.fulfill({ response });
  }, { times: 1 });
  await page.evaluate(() => window.dispatchEvent(new Event("pageshow"))); await old.seen;
  try {
    await expect(page.getByRole("heading", { name: sourceName, exact: true })).toHaveCount(0);
    await expect(page.getByText("Kaynak bağlamı yükleniyor…", { exact: true })).toBeVisible();
    const second = await context.newPage(); await startExam(second, course.id);
    await expect(page.getByRole("alert").filter({ hasText: /sınav/i })).toBeVisible();
    expect((await request.get(`${API}${sourcePath}`, { headers: studentHeaders })).status()).toBe(403);
    expect((await request.get(`${API}${sourcePath}`, { headers: teacherHeaders })).status()).toBe(200);
    const delivered = page.waitForResponse((response) => response.url() === `${API}${sourcePath}` && response.status() === 200);
    old.release(); await delivered; await paint(page);
    await expect(page.getByRole("heading", { name: sourceName, exact: true })).toHaveCount(0);
    await expect(page.getByText("Atıfta kullanılan pasaj", { exact: true })).toHaveCount(0);
    await finish(second);
    // Source API permits again even while the assistant operation flag stays off.
    await expect(page.getByRole("heading", { name: sourceName, exact: true })).toBeVisible();
  } finally { old.release(); }
});

test("odak, pageshow ve görünür olma sinyalleri sunucuda değişen sınav erişimini yeniden doğrular", async ({ page, request }) => {
  test.setTimeout(120_000);
  const { base, sourcePath } = await prepareCourse(request);
  await login(page); await page.goto(sourcePath); await page.bringToFront();
  await expect(page.getByRole("heading", { name: sourceName, exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.visibilityState)).toBe("visible");
  const signal = async (event: string) => page.evaluate((name) => {
    if (name === "visibilitychange") document.dispatchEvent(new Event(name));
    else window.dispatchEvent(new Event(name));
  }, event);
  for (const event of ["focus", "pageshow", "visibilitychange"]) {
    // API write intentionally emits no client exam signal: the lifecycle event must refresh.
    const started = await request.post(`${base}/exams`, { headers: studentHeaders, data: { mode: "exam" } });
    expect(started.ok(), await started.text()).toBeTruthy(); const exam = await started.json();
    await signal(event);
    await expect(page.getByRole("heading", { name: sourceName, exact: true })).toHaveCount(0);
    await expect(page.getByRole("alert").filter({ hasText: /sınav/i })).toBeVisible();
    expect((await request.post(`${base}/exams/${exam.id}/finish`, { headers: studentHeaders })).ok()).toBeTruthy();
    await signal(event);
    await expect(page.getByRole("heading", { name: sourceName, exact: true })).toBeVisible();
  }
});
