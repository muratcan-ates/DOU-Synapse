import { expect, test, type APIRequestContext } from "@playwright/test";
import { createE2eCourseIdentity } from "./fixtures";
import type { LearningSummary } from "../lib/learning-events";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const teacherHeaders = { Authorization: "Bearer dev:11111111-1111-1111-1111-111111111111" };
const student = { id: "22222222-2222-2222-2222-222222222222", email: "burak@dogus.edu.tr", fullName: "Burak Yılmaz", role: "student" };
const studentHeaders = { Authorization: `Bearer dev:${student.id}` };

async function prepareCourse(request: APIRequestContext) {
  const post = async (path: string, data: unknown) => {
    const response = await request.post(`${API}${path}`, { headers: teacherHeaders, data });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json();
  };
  const course = await post("/courses", createE2eCourseIdentity("OGRENME-OLAYLARI"));
  const path = `/courses/${course.id}`;
  await post(`${path}/members`, { email: student.email, role: "student" });
  const topic = await post(`${path}/topics`, { name: "Deadlock" });
  const upload = await request.post(`${API}${path}/documents`, {
    headers: teacherHeaders,
    multipart: { file: {
      name: "learning-events.md", mimeType: "text/markdown",
      buffer: Buffer.from("# Deadlock\nDeadlock iki veya daha fazla sürecin birbirini beklemesidir. Coffman koşulları karşılıklı dışlama, tut ve bekle, kesintisizlik ve dairesel beklemedir.\n"),
    } },
  });
  expect(upload.ok(), await upload.text()).toBeTruthy();
  await expect.poll(async () => (await (await request.get(`${API}${path}/documents`, { headers: teacherHeaders })).json()).items[0]?.status, { timeout: 25_000 }).toBe("completed");
  const generated = await post(`${path}/questions/generate`, { topic_id: topic.id, count: 1, question_type: "mcq" });
  expect(generated.questions).toHaveLength(1);
  const question = generated.questions[0] as { id: string; payload: { answer_key: string; options: Array<{ key: string; text: string }> } };
  await post(`${path}/questions/${question.id}/approve`, {});
  const wrong = question.payload.options.find((option) => option.key !== question.payload.answer_key);
  expect(wrong).toBeDefined();
  return { course, topic, wrong: wrong!, base: `${API}${path}` };
}

test("çalışma oturumu dört gerçek olay üretir; eğitmen yalnız konu toplamlarını görür", async ({ browser, page, request }, testInfo) => {
  test.setTimeout(120_000);
  const { course, topic, wrong, base } = await prepareCourse(request);
  await page.addInitScript((user) => {
    localStorage.setItem("dou-synapse-token", `dev:${user.id}`);
    localStorage.setItem("dou-synapse-user", JSON.stringify(user));
  }, student);
  await page.goto(`/courses/${course.id}/exam`);
  const started = page.waitForResponse((response) => response.url() === `${base}/exams` && response.request().method() === "POST");
  await page.getByRole("button", { name: "Alıştırma başlat", exact: true }).click();
  const startResponse = await started;
  expect(startResponse.ok(), await startResponse.text()).toBeTruthy();
  const session = await startResponse.json();
  await page.getByRole("button", { name: "İpucu al", exact: true }).click();
  await expect(page.getByText("1. ipucu", { exact: true })).toBeVisible();
  await page.getByRole("radio", { name: wrong.text, exact: true }).check();
  const submitted = page.waitForResponse((response) => response.url() === `${base}/exams/${session.id}/answers` && response.request().method() === "POST");
  await page.getByRole("button", { name: "Cevabı gönder", exact: true }).click();
  expect((await (await submitted).json()).is_correct).toBe(false);
  await expect(page.getByText("Neden yanlış?", { exact: true })).toBeVisible();

  // Gerçek kaynak kartı tıklanır; ağ katmanında olay veya geri bildirim taklidi yapılmaz.
  const citation = page.waitForResponse((response) => response.url() === `${base}/learning-events/citation-opened` && response.request().method() === "POST");
  await page.getByRole("link", { name: /learning-events.md.*kaynak bağlamını aç/ }).last().click();
  expect((await citation).ok()).toBeTruthy();
  await expect(page.getByText("Atıfta kullanılan pasaj", { exact: true })).toBeVisible();
  const readEvents = async () => {
    const response = await request.get(`${base}/learning-events?session_id=${session.id}`, { headers: studentHeaders });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json() as Promise<{ total: number; items: Array<{ id: string; event_type: string; session_id: string; occurred_at: string; topic_id: string | null }> }>;
  };
  await expect.poll(async () => (await readEvents()).total).toBeGreaterThanOrEqual(4);
  const events = await readEvents();
  expect(events.items.map((event) => event.event_type)).toEqual(expect.arrayContaining([
    "question_presented", "hint_requested", "answer_submitted", "citation_opened",
  ]));
  for (const event of events.items) {
    expect(event.session_id).toBe(session.id);
    expect(Object.keys(event).sort()).toEqual(["event_type", "id", "occurred_at", "session_id", "topic_id"]);
  }
  expect((await request.get(`${base}/learning-summary?days=7`, { headers: studentHeaders })).status()).toBe(403);
  await page.goto(`/courses/${course.id}/settings`);
  await expect(page.getByRole("heading", { name: "Öğrenme özeti", exact: true })).toHaveCount(0);

  const teacherContext = await browser.newContext();
  try {
    const teacherPage = await teacherContext.newPage();
    await teacherPage.goto("/");
    await teacherPage.getByRole("button", { name: /Ayşe Hoca/ }).click();
    await expect(teacherPage).toHaveURL(/\/dashboard$/);
    const sevenDayResponse = teacherPage.waitForResponse(`${base}/learning-summary?days=7`);
    await teacherPage.goto(`/courses/${course.id}/settings`);
    const summary = await (await sevenDayResponse).json() as LearningSummary;
    expect(summary.topics.find((item) => item.topic_id === topic.id)).toMatchObject({ wrong_answers: 1, hints_requested: 1, unsupported_refusals: 0 });
    expect(summary.total_events).toBeGreaterThanOrEqual(4);
    expect(JSON.stringify(summary)).not.toContain(student.email);
    expect(JSON.stringify(summary)).not.toContain(student.id);
    const panel = teacherPage.getByRole("region", { name: "Öğrenme özeti", exact: true });
    await expect(panel.getByRole("row", { name: /Deadlock/ })).toContainText("1");
    const thirtyDayResponse = teacherPage.waitForResponse(`${base}/learning-summary?days=30`);
    await panel.getByRole("button", { name: "Son 30 gün", exact: true }).click();
    expect((await (await thirtyDayResponse).json()).days).toBe(30);
    await expect(panel.getByRole("button", { name: "Son 30 gün", exact: true })).toHaveAttribute("aria-pressed", "true");
    await teacherPage.setViewportSize({ width: 375, height: 812 });
    await teacherPage.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
    await expect(teacherPage.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(panel.getByRole("list", { name: "Konu bazlı öğrenme özeti" })).toContainText("Deadlock");
    expect(await teacherPage.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    await teacherPage.screenshot({ path: testInfo.outputPath("learning-summary-375-dark.png"), fullPage: true, animations: "disabled" });
    // Yalnız bu 403 zarfı sentetiktir: rol önbelleği hâlâ eğitmenken eski toplam gizlenmelidir.
    await teacherPage.route(`${base}/learning-summary?days=30`, (route) => route.fulfill({
      status: 403, contentType: "application/json", body: JSON.stringify({ error: {
        code: "permission_denied", message: "Öğrenme özeti erişimi kaldırıldı.", request_id: "synthetic-summary-revocation",
      } }),
    }), { times: 1 });
    await panel.getByRole("button", { name: "Özeti yenile", exact: true }).click();
    await expect(panel.getByText("Öğrenme özeti erişimi kaldırıldı.", { exact: true })).toBeVisible();
    await expect(panel.getByRole("list", { name: "Konu bazlı öğrenme özeti" })).toHaveCount(0);
  } finally {
    await teacherContext.close();
  }
});
