import { expect, test, type APIRequestContext } from "@playwright/test";

import { createE2eCourseIdentity } from "./fixtures";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const teacherHeaders = { Authorization: "Bearer dev:11111111-1111-1111-1111-111111111111" };
const student = { id: "22222222-2222-2222-2222-222222222222", email: "burak@dogus.edu.tr", fullName: "Burak Yılmaz", role: "student" };
const studentHeaders = { Authorization: `Bearer dev:${student.id}` };

// Synthetic preparation goes through the same instructor API as the UI.
async function prepareCourse(request: APIRequestContext) {
  const post = async (path: string, data?: unknown) => {
    const response = await request.post(`${API}${path}`, { headers: teacherHeaders, ...(data === undefined ? {} : { data }) });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json();
  };
  const course = await post("/courses", createE2eCourseIdentity("OGRENCI-SINAVI"));
  const path = `/courses/${course.id}`;
  await post(`${path}/members`, { email: student.email, role: "student" });
  const topic = await post(`${path}/topics`, { name: "Deadlock" });
  const otherTopic = await post(`${path}/topics`, { name: "Süreçler" });
  const outcome = await post(`${path}/learning-outcomes`, { code: "LO-1", description: "Deadlock koşullarını açıklar.", topic_id: topic.id });
  const upload = await request.post(`${API}${path}/documents`, {
    headers: teacherHeaders,
    multipart: { file: { name: "student-assessment.md", mimeType: "text/markdown", buffer: Buffer.from("# Deadlock\nDeadlock iki veya daha fazla sürecin birbirini beklemesidir. Coffman koşulları karşılıklı dışlama, tut ve bekle, kesintisizlik ve dairesel beklemedir.\n") } },
  });
  expect(upload.ok()).toBeTruthy();
  await expect.poll(async () => (await (await request.get(`${API}${path}/documents`, { headers: teacherHeaders })).json()).items[0]?.status, { timeout: 25_000 }).toBe("completed");
  const generated = await post(`${path}/questions/generate`, { topic_id: topic.id, count: 1, question_type: "mcq", learning_outcome_id: outcome.id, difficulty: "medium" });
  expect(generated.questions).toHaveLength(1);
  const question = generated.questions[0];
  await post(`${path}/questions/${question.id}/approve`);
  const other = await post(`${path}/questions/generate`, { topic_id: otherTopic.id, count: 1, question_type: "mcq" });
  expect(other.questions).toHaveLength(1);
  await post(`${path}/questions/${other.questions[0].id}/approve`);
  const blueprint = await post(`${path}/blueprints`, { title: "Deadlock kaynaklı sınav", duration_minutes: 45, max_attempts: 2,
    cells: [{ learning_outcome_id: outcome.id, difficulty: "medium", question_type: "mcq", question_count: 1, points_per_question: 1 }] });
  const version = await post(`${path}/blueprints/${blueprint.id}/versions`);
  await post(`${path}/blueprints/${blueprint.id}/versions/${version.id}/items`, [{ question_id: question.id }]);
  await post(`${path}/blueprints/${blueprint.id}/versions/${version.id}/publish`);
  return { course, topic, question, blueprint, base: `${API}${path}` };
}

test("öğrenci konu seçer, yayımlanan sınava döner ve kaynaklı sonucunu yeniden açar", async ({ page, request }, testInfo) => {
  test.setTimeout(120_000);
  const { course, topic, question, blueprint, base } = await prepareCourse(request);
  await page.addInitScript((user) => {
    localStorage.setItem("dou-synapse-token", `dev:${user.id}`);
    localStorage.setItem("dou-synapse-user", JSON.stringify(user));
  }, student);
  await page.goto(`/courses/${course.id}/exam`);
  await expect(page.getByRole("heading", { name: "Şu anda açık sınavlar" })).toBeVisible();
  await page.getByLabel("Çalışma konusu").selectOption(topic.id);
  const practiceResponse = page.waitForResponse((response) => response.url() === `${base}/exams` && response.request().method() === "POST");
  await page.getByRole("button", { name: "Alıştırma başlat", exact: true }).click();
  const practice = await (await practiceResponse).json();
  expect(practice.question_count).toBe(1);
  expect(practice.questions[0].id).toBe(question.id);
  expect(practice.mode).toBe("practice");
  const wrongIndex = (question.payload.options as Array<{ key: string }>).findIndex((option) => option.key !== question.payload.answer_key);
  await page.getByRole("radio").nth(wrongIndex).check();
  const draftKey = `dou-synapse:exam-drafts:v1:${student.id}:${course.id}:${practice.id}`;
  await expect.poll(() => page.evaluate((key) => sessionStorage.getItem(key), draftKey)).not.toBeNull();
  await page.reload();
  await expect(page.getByRole("radio").nth(wrongIndex)).toBeChecked();
  await page.getByRole("button", { name: "Cevabı gönder", exact: true }).click();
  await expect.poll(() => page.evaluate((key) => sessionStorage.getItem(key), draftKey)).toBeNull();
  await expect(page.getByText("Neden yanlış?", { exact: true })).toBeVisible();
  await expect(page.getByText("student-assessment.md", { exact: true }).first()).toBeVisible();
  const feedbackRead = page.waitForResponse((response) => response.url() === `${base}/exams/${practice.id}/answers/${question.id}`);
  await page.reload();
  expect((await feedbackRead).ok()).toBeTruthy();
  await expect(page.getByText("Neden yanlış?", { exact: true })).toBeVisible();
  await expect(page.getByText("student-assessment.md", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Sınavı bitir", exact: true }).click();
  await page.getByRole("button", { name: "Bitir ve sonucu gör", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sınav sonucu", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Yeni sınav başlat", exact: true }).click();

  const timedResponse = page.waitForResponse((response) => response.url() === `${base}/exams` && response.request().method() === "POST");
  await page.getByRole("button", { name: `${blueprint.title} sınavına başla`, exact: true }).click();
  const timed = await (await timedResponse).json();
  expect(timed.exam_blueprint_id).toBe(blueprint.id);
  expect(timed.remaining_seconds).toBeGreaterThan(44 * 60);
  expect(timed.questions[0].payload).not.toHaveProperty("answer_key");
  await expect(page.getByRole("button", { name: /İpucu al|Sonraki ipucu/ })).toHaveCount(0);

  // Even a saved old result is unavailable while the new timed session is active.
  await page.getByRole("button", { name: "Oturumlara dön", exact: true }).click();
  await page.getByRole("button", { name: "Sonucu gör", exact: true }).click();
  await expect(page.getByRole("button", { name: "Tekrar dene", exact: true })).toBeVisible();
  await expect(page.getByText("Neden yanlış?", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Cevap anahtarı", { exact: true })).toHaveCount(0);
  expect((await request.get(`${base}/exams/${practice.id}/results`, { headers: studentHeaders })).status()).toBe(403);
  expect((await request.get(`${base}/exams/${practice.id}/answers/${question.id}`, { headers: studentHeaders })).status()).toBe(403);
  await page.getByRole("button", { name: "Yeni sınav başlat", exact: true }).click();

  // Simulate another device: no remembered id. Durable history still finds the session.
  await page.evaluate(({ courseId, userId }) => localStorage.removeItem(`dou-synapse-exam-session:${userId}:${courseId}`), { courseId: course.id, userId: student.id });
  await page.reload();
  await expect(page.getByRole("heading", { name: "Oturumlarım", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Devam et", exact: true }).click();
  await expect(page.getByRole("button", { name: "Cevabı gönder", exact: true })).toBeVisible();
  const resumed = await (await request.get(`${base}/exams/${timed.id}`, { headers: studentHeaders })).json();
  expect(resumed.started_at).toBe(timed.started_at);
  expect(resumed.expires_at).toBe(timed.expires_at);
  expect(resumed.remaining_seconds).toBeLessThanOrEqual(timed.remaining_seconds);
  await page.getByRole("radio").nth(wrongIndex).check();
  await page.getByRole("button", { name: "Cevabı gönder", exact: true }).click();
  await expect(page.getByText("Cevabınız kaydedildi", { exact: true })).toBeVisible();
  await expect(page.getByText("Cevap anahtarı", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Sınavı bitir", exact: true }).click();
  await page.getByRole("button", { name: "Bitir ve sonucu gör", exact: true }).click();
  await expect(page.getByText("Neden yanlış?", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText("Neden yanlış?", { exact: true })).toBeVisible();
  await expect(page.getByText("student-assessment.md", { exact: true }).first()).toBeVisible();
  const first = await (await request.get(`${base}/exams/${timed.id}/results`, { headers: studentHeaders })).json();
  const second = await (await request.get(`${base}/exams/${timed.id}/results`, { headers: studentHeaders })).json();
  expect(second).toEqual(first);
  expect(first.score).toBe(0);
  expect(first.results_locked).toBe(false);

  await page.setViewportSize({ width: 375, height: 812 });
  for (const theme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: theme });
    await expect(page.getByText("Neden yanlış?", { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`student-results-375-${theme}.png`), fullPage: true });
  }
  await page.getByRole("button", { name: "Yeni sınav başlat", exact: true }).click();
  await expect(page.getByRole("button", { name: "Sonucu gör", exact: true })).toHaveCount(2);
  await expect(page.getByText("45 dakika · 1/2 deneme hakkı", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("student-history-375-dark.png"), fullPage: true });
});
