import { expect, test, type APIRequestContext, type Page, type Route } from "@playwright/test";
import { createE2eCourseIdentity } from "./fixtures";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const teacherHeaders = { Authorization: "Bearer dev:11111111-1111-1111-1111-111111111111" };
const student = { id: "22222222-2222-2222-2222-222222222222", email: "burak@dogus.edu.tr", fullName: "Burak Yılmaz", role: "student" };
const studentHeaders = { Authorization: `Bearer dev:${student.id}` };

async function prepareCourse(request: APIRequestContext) {
  const post = async (path: string, data?: unknown) => {
    const response = await request.post(`${API}${path}`, { headers: teacherHeaders, ...(data === undefined ? {} : { data }) });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json();
  };
  const course = await post("/courses", createE2eCourseIdentity("SINAV-KORUMALARI"));
  const path = `/courses/${course.id}`;
  await post(`${path}/members`, { email: student.email, role: "student" });
  const topic = await post(`${path}/topics`, { name: "Deadlock" });
  const upload = await request.post(`${API}${path}/documents`, {
    headers: teacherHeaders,
    multipart: { file: { name: "exam-guards.md", mimeType: "text/markdown", buffer: Buffer.from("# Deadlock\nDeadlock iki veya daha fazla sürecin birbirini beklemesidir. Coffman koşulları karşılıklı dışlama, tut ve bekle, kesintisizlik ve dairesel beklemedir.\n") } },
  });
  expect(upload.ok(), await upload.text()).toBeTruthy();
  await expect.poll(async () => (await (await request.get(`${API}${path}/documents`, { headers: teacherHeaders })).json()).items[0]?.status, { timeout: 25_000 }).toBe("completed");
  const generated = await post(`${path}/questions/generate`, { topic_id: topic.id, count: 1, question_type: "mcq" });
  expect(generated.questions).toHaveLength(1);
  const question = generated.questions[0];
  await post(`${path}/questions/${question.id}/approve`);
  return { course, question, base: `${API}${path}` };
}

async function signIn(page: Page) {
  await page.addInitScript((user) => {
    localStorage.setItem("dou-synapse-token", `dev:${user.id}`);
    localStorage.setItem("dou-synapse-user", JSON.stringify(user));
  }, student);
}

async function finish(page: Page) {
  await page.getByRole("button", { name: "Sınavı bitir", exact: true }).click();
  await page.getByRole("button", { name: "Bitir ve sonucu gör", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sınav sonucu", exact: true })).toBeVisible();
}

test("eğitmenin bir ve sıfır ipucu sınırı alıştırmaya yansır", async ({ page, request }) => {
  test.setTimeout(90_000);
  const { course, question, base } = await prepareCourse(request);
  expect((await request.put(`${base}/ai-policy`, { headers: teacherHeaders, data: { hint_limit: 4 } })).ok()).toBeTruthy();
  await signIn(page);
  await page.goto(`/courses/${course.id}/exam`);
  const started = page.waitForResponse((response) => response.url() === `${base}/exams` && response.request().method() === "POST");
  await page.getByRole("button", { name: "Alıştırma başlat", exact: true }).click();
  const practice = await (await started).json();
  await page.getByRole("button", { name: "İpucu al", exact: true }).click();
  await expect(page.getByText("1. ipucu", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sonraki ipucu", exact: true })).toBeVisible();
  // The teacher changes policy while the student's page stays open.
  expect((await request.put(`${base}/ai-policy`, { headers: teacherHeaders, data: { hint_limit: 1 } })).ok()).toBeTruthy();
  const clamped = page.waitForResponse((response) => response.url() === `${base}/exams/${practice.id}/hint`);
  await page.getByRole("button", { name: "Sonraki ipucu", exact: true }).click();
  expect((await (await clamped).json()).hint_level).toBe(1);
  await expect(page.getByText("1. ipucu", { exact: true })).toHaveCount(1);
  await expect(page.getByRole("button", { name: "Sonraki ipucu", exact: true })).toHaveCount(0);
  expect((await request.put(`${base}/ai-policy`, { headers: teacherHeaders, data: { hint_limit: 0 } })).ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByRole("button", { name: "Cevabı gönder", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /İpucu al|Sonraki ipucu/ })).toHaveCount(0);
  const denied = await request.post(`${base}/exams/${practice.id}/hint`, { headers: studentHeaders, data: { question_id: question.id, hint_level: 1 } });
  expect(denied.status()).toBe(403);
  expect(await denied.json()).not.toHaveProperty("source");
});

test("görünür sorusu kalmayan süreli oturum bitirilip ders kilidi kaldırılır", async ({ page, request }, testInfo) => {
  test.setTimeout(90_000);
  const { course, question, base } = await prepareCourse(request);
  await signIn(page);
  await page.goto(`/courses/${course.id}/exam`);
  const started = page.waitForResponse((response) => response.url() === `${base}/exams` && response.request().method() === "POST");
  await page.getByRole("button", { name: "Sınav başlat", exact: true }).click();
  const exam = await (await started).json();
  expect((await request.post(`${base}/questions/${question.id}/reject`, { headers: teacherHeaders })).ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByText("Bu oturumda gösterilebilecek soru kalmadı.", { exact: false })).toBeVisible();
  expect((await (await request.get(`${base}/chat/availability`, { headers: studentHeaders })).json()).available).toBe(false);
  await page.setViewportSize({ width: 375, height: 812 });
  await page.screenshot({ path: testInfo.outputPath("empty-exam-finish-375.png"), fullPage: true });
  await finish(page);
  await expect.poll(async () => (await (await request.get(`${base}/exams/${exam.id}`, { headers: studentHeaders })).json()).finished_at).not.toBeNull();
  await expect.poll(async () => (await (await request.get(`${base}/chat/availability`, { headers: studentHeaders })).json()).available).toBe(true);
  await expect(page.getByText("Hiçbir soru cevaplanmadığı için", { exact: false })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});

test("başka sekmede başlayan sınav eski sonucu doğrulama boyunca ve kilitte gizler", async ({ page, request, context }) => {
  test.setTimeout(120_000);
  const { course, base } = await prepareCourse(request);
  await signIn(page);
  await page.goto(`/courses/${course.id}/exam`);
  await page.getByRole("button", { name: "Alıştırma başlat", exact: true }).click();
  await page.getByRole("radio").first().check();
  await page.getByRole("button", { name: "Cevabı gönder", exact: true }).click();
  await expect(page.getByText("Cevap anahtarı", { exact: true })).toBeVisible();
  await finish(page);
  await expect(page.getByText("Cevap anahtarı", { exact: true })).toBeVisible();

  // Closing assistant modes must not revoke completed assessment results.
  expect((await request.put(`${base}/ai-policy`, { headers: teacherHeaders, data: { allowed_modes: [] } })).ok()).toBeTruthy();
  let refreshed = page.waitForResponse((response) => response.url().endsWith("/results"));
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  expect((await refreshed).status()).toBe(200);
  await expect(page.getByText("Cevap anahtarı", { exact: true })).toBeVisible();

  // Simulate the content-free global-maintenance availability response. The
  // results endpoint remains real: it alone decides whether an exam is active.
  await page.route(`${base}/chat/availability`, async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({ response, json: { ...body, available: false, reason: "globally_disabled",
      message: "Ders asistanı şu anda bakım nedeniyle kullanıma kapalı.", allowed_modes: [] } });
  });
  refreshed = page.waitForResponse((response) => response.url().endsWith("/results"));
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  expect((await refreshed).status()).toBe(200);
  await expect(page.getByText("Cevap anahtarı", { exact: true })).toBeVisible();

  // Sınav başlamadan sunucunun izin verdiği gerçek 200 yanıtını ağda tut.
  // Sonraki sınav kilidi doğrulanınca bu eski yanıt çözümleri geri açmamalı.
  let releaseOldResult!: () => void;
  const oldResultGate = new Promise<void>((resolve) => { releaseOldResult = resolve; });
  let oldResultSeen!: () => void;
  const oldResultReady = new Promise<void>((resolve) => { oldResultSeen = resolve; });
  let oldResultDelivered!: () => void;
  const oldResultDone = new Promise<void>((resolve) => { oldResultDelivered = resolve; });
  await page.route(`${base}/exams/*/results`, async (route) => {
    const response = await route.fetch();
    expect(response.status()).toBe(200);
    oldResultSeen();
    await oldResultGate;
    await route.fulfill({ response });
    oldResultDelivered();
  }, { times: 1 });
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await oldResultReady;

  try {
    const second = await context.newPage();
    await second.goto(`/courses/${course.id}/exam`);
    await second.getByRole("button", { name: "Yeni sınav başlat", exact: true }).click();
    await second.getByRole("button", { name: "Sınav başlat", exact: true }).click();
    await expect(second.getByRole("timer")).toBeVisible();

    let releaseAvailability!: () => void;
    const availabilityGate = new Promise<void>((resolve) => { releaseAvailability = resolve; });
    let requestSeen!: () => void;
    const availabilitySeen = new Promise<void>((resolve) => { requestSeen = resolve; });
    const holdAvailability = async (route: Route) => {
      requestSeen();
      await availabilityGate;
      await route.fallback();
    };
    await page.route(`${base}/chat/availability`, holdAvailability);
    await page.bringToFront();
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    await availabilitySeen;
    try {
      await expect(page.getByText("Cevap anahtarı", { exact: true })).toHaveCount(0);
      await expect(page.getByText("Sonuç erişimi doğrulanıyor…", { exact: true })).toBeVisible();
    } finally { releaseAvailability(); }
    await expect(page.getByRole("button", { name: "Tekrar dene", exact: true })).toBeVisible();
    await expect(page.getByText("Cevap anahtarı", { exact: true })).toHaveCount(0);
    await page.unroute(`${base}/chat/availability`, holdAvailability);

    const lateResponse = page.waitForResponse((response) => response.url().endsWith("/results") && response.status() === 200);
    releaseOldResult();
    await Promise.all([oldResultDone, lateResponse]);
    // Ağ teslimi ve React boyaması tamamlandıktan sonra yeni kilit hâlâ görünür.
    await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
    await expect(page.getByText("Cevap anahtarı", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Tekrar dene", exact: true })).toBeVisible();

    await second.bringToFront();
    await finish(second);
    await page.bringToFront();
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    await expect(page.getByText("Cevap anahtarı", { exact: true })).toBeVisible();
    await second.close();
  } finally { releaseOldResult(); }
});
