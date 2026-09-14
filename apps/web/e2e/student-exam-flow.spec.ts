// İki ayrı Response tipi kullanılır: `APIResponse` request context çağrılarının
// dönüşü, `Response` ise tarayıcının gördüğü ağ yanıtı (`.request()` yalnız onda var).
import { expect, test, type APIRequestContext, type APIResponse, type Response, type TestInfo } from "@playwright/test";

import { createE2eCourseIdentity } from "./fixtures";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const teacherHeaders = { Authorization: "Bearer dev:11111111-1111-1111-1111-111111111111" };
const student = {
  id: "22222222-2222-2222-2222-222222222222",
  email: "burak@dogus.edu.tr",
  fullName: "Burak Yılmaz",
  role: "student",
};
const studentHeaders = { Authorization: `Bearer dev:${student.id}` };
const EKRAN = process.env.EKRAN === "1";

interface CourseSeed {
  course: { id: string };
  topic: { id: string };
  question: { id: string; payload: { options: Array<{ key: string; text: string }>; answer_key: string } };
  blueprint: { id: string; title: string };
  base: string;
}

function examSessionKey(courseId: string, userId: string): string {
  return `dou-synapse-exam-session:${userId}:${courseId}`;
}

async function apiPost<T = Record<string, unknown>>(
  request: APIRequestContext,
  path: string,
  data: unknown,
  headers: Record<string, string> = teacherHeaders,
): Promise<T> {
  const response = await request.post(`${API}${path}`, { headers, data });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json() as Promise<T>;
}

function apiGet(
  request: APIRequestContext,
  path: string,
  headers: Record<string, string> = teacherHeaders,
): Promise<APIResponse> {
  return request.get(`${API}${path}`, { headers });
}

async function expectJsonError(responsePromise: Promise<APIResponse>, status: number, code: string): Promise<Record<string, unknown>> {
  const response = await responsePromise;
  expect(response.status()).toBe(status);
  const body = (await response.json()) as { error?: { code?: string } };
  expect(body.error).toBeTruthy();
  expect(body.error?.code).toBe(code);
  return body;
}

// `page.waitForResponse` tarayıcı `Response`u döndürür; `.request()` yalnız onda
// vardır. Sandbox sürümü APIResponse yazmıştı ve tip denetimi kırılıyordu.
function requestPayload(response: Response): Record<string, unknown> {
  const raw = response.request().postData();
  return raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
}

async function seedCatalogCourse(
  request: APIRequestContext,
  options: { blueprintTitle: string; durationMinutes?: number; maxAttempts?: number },
): Promise<CourseSeed> {
  const course = await apiPost<{ id: string }>(request, "/courses", createE2eCourseIdentity("SINAV-FLOW"));
  const base = `/courses/${course.id}`;

  await apiPost(request, `${base}/members`, { email: student.email, role: "student" });
  const topic = await apiPost<{ id: string }>(request, `${base}/topics`, { name: "Deadlock" });
  await apiPost(request, `${base}/topics`, { name: "Süreçler" });
  const outcome = await apiPost<{ id: string }>(request, `${base}/learning-outcomes`, {
    code: "LO-1",
    description: "Deadlock koşullarını açıklar.",
    topic_id: topic.id,
  });

  const upload = await request.post(`${API}${base}/documents`, {
    headers: teacherHeaders,
    multipart: {
      file: {
        name: "student-exam-flow.md",
        mimeType: "text/markdown",
        buffer: Buffer.from(
          "# Deadlock\nDeadlock iki veya daha fazla sürecin birbirini beklemesidir. Coffman koşulları karşılıklı dışlama, tut ve bekleme, kesintisizlik ve dairesel beklemedir.\n",
        ),
      },
    },
  });
  expect(upload.ok(), await upload.text()).toBeTruthy();
  await expect
    .poll(async () => (await (await apiGet(request, `${base}/documents`, teacherHeaders)).json() as { items: Array<{ status: string }> }).items[0]?.status, {
      timeout: 25_000,
    })
    .toBe("completed");

  const topicQuestionResponse = await apiPost<{ questions: CourseSeed["question"][] }>(
    request,
    `${base}/questions/generate`,
    {
      topic_id: topic.id,
      count: 1,
      question_type: "mcq",
      learning_outcome_id: outcome.id,
      difficulty: "medium",
    },
  );
  const question = topicQuestionResponse.questions[0];
  await apiPost(request, `${base}/questions/${question.id}/approve`, {});

  const blueprint = await apiPost<{ id: string; title: string }>(request, `${base}/blueprints`, {
    title: options.blueprintTitle,
    duration_minutes: options.durationMinutes ?? 45,
    max_attempts: options.maxAttempts ?? 2,
    cells: [{
      learning_outcome_id: outcome.id,
      difficulty: "medium",
      question_type: "mcq",
      question_count: 1,
      points_per_question: 1,
    }],
  });
  const version = await apiPost<{ id: string }>(request, `${base}/blueprints/${blueprint.id}/versions`, {});
  await apiPost(request, `${base}/blueprints/${blueprint.id}/versions/${version.id}/items`, [{ question_id: question.id }]);
  await apiPost(request, `${base}/blueprints/${blueprint.id}/versions/${version.id}/publish`, {});

  return {
    course,
    topic,
    question,
    blueprint,
    base,
  };
}

async function signInAsStudent(page: import("@playwright/test").Page) {
  await page.addInitScript((value) => {
    localStorage.setItem("dou-synapse-token", `dev:${value.id}`);
    localStorage.setItem("dou-synapse-user", JSON.stringify(value));
  }, student);
}

async function assertBlueprintCatalogVisible(
  request: APIRequestContext,
  base: string,
): Promise<Record<string, unknown>[]> {
  const catalog = await apiGet(request, `${base}/exams/catalog`, studentHeaders);
  expect(catalog.ok()).toBeTruthy();
  const body = (await catalog.json()) as { enabled: boolean; items: Record<string, unknown>[] };
  expect(body.enabled).toBe(true);
  return body.items;
}

test("öğrenci konu seçerek alıştırma başlatır; topic_id ve 4xx hata kodu doğrulanır", async ({ page, request }) => {
  const seed = await seedCatalogCourse(request, { blueprintTitle: "P2 Alıştırma Blueprint" });
  await signInAsStudent(page);

  await page.goto(`/courses/${seed.course.id}/exam`);
  await expect(page.getByRole("button", { name: "Alıştırma başlat", exact: true })).toBeVisible();

  const practiceRequest = page.waitForResponse((response) => response.url() === `${API}${seed.base}/exams` && response.request().method() === "POST");
  await page.getByLabel("Çalışma konusu").selectOption(seed.topic.id);
  await page.getByRole("button", { name: "Alıştırma başlat", exact: true }).click();
  const started = await practiceRequest;
  expect(started.status()).toBe(201);
  expect(requestPayload(started)).toMatchObject({
    mode: "practice",
    topic_id: seed.topic.id,
  });

  const session = await started.json() as { id: string; questions: Array<{ id: string }> };
  expect(session.questions).toHaveLength(1);
  expect(session.questions[0].id).toBe(seed.question.id);

  const locked = await request.get(`${API}${seed.base}/exams/${session.id}/results`, { headers: studentHeaders });
  await expectJsonError(Promise.resolve(locked), 403, "exam_in_progress");

  const wrongOptionIndex = seed.question.payload.options.findIndex((option) => option.key !== seed.question.payload.answer_key);
  await page.getByRole("radio").nth(wrongOptionIndex).check();
  await page.getByRole("button", { name: "Cevabı gönder", exact: true }).click();
  await expect(page.getByText("Bu soruyu cevapladınız.")).toBeVisible();

  await page.getByRole("button", { name: "Sınavı bitir", exact: true }).click();
  await page.getByRole("button", { name: "Bitir ve sonucu gör", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sınav sonucu", exact: true })).toBeVisible();
  await expect(page.getByText("Neden yanlış?", { exact: true })).toBeVisible();

  const missingTopic = request.post(`${API}${seed.base}/exams`, {
    headers: studentHeaders,
    data: { mode: "practice", topic_id: "00000000-0000-0000-0000-000000000000" },
  });
  await expectJsonError(missingTopic, 404, "not_found");
});

test("öğrenci yayımlanmış blueprint ile sınava başlar, yenilendiğinde aynı oturuma döner ve geçmişe girer", async ({ page, request }) => {
  const seed = await seedCatalogCourse(request, { blueprintTitle: "P2 Blueprint Geri Dönüş", durationMinutes: 45, maxAttempts: 1 });
  await signInAsStudent(page);

  await page.goto(`/courses/${seed.course.id}/exam`);
  await expect(page.getByRole("heading", { name: "Şu anda açık sınavlar", exact: true })).toBeVisible();

  const catalogItems = await assertBlueprintCatalogVisible(request, seed.base);
  const published = catalogItems.find((item) => item.blueprint_id === seed.blueprint.id);
  expect(published).toBeTruthy();
  expect(published?.can_start).toBe(true);

  const listItem = page.getByRole("listitem").filter({ hasText: seed.blueprint.title });
  await expect(listItem.getByRole("button", { name: "Sınava katıl" })).toBeVisible();
  const startResponse = page.waitForResponse((response) => response.url() === `${API}${seed.base}/exams` && response.request().method() === "POST");
  await listItem.getByRole("button", { name: "Sınava katıl", exact: true }).click();
  const started = await startResponse;
  expect(started.status()).toBe(201);
  expect(requestPayload(started)).toMatchObject({
    mode: "exam",
    blueprint_id: seed.blueprint.id,
  });

  const session = await started.json() as { id: string; questions: Array<{ id: string }> };
  expect(session.questions).toHaveLength(1);
  expect(session.questions[0].id).toBe(seed.question.id);

  const storageKey = examSessionKey(seed.course.id, student.id);
  await expect.poll(async () => page.evaluate((key) => sessionStorage.getItem(key), storageKey)).toBe(session.id);

  await page.reload();
  const persistedSession = await page.evaluate((key) => sessionStorage.getItem(key), storageKey);
  expect(persistedSession).toBe(session.id);
  const serverSession = await (await request.get(`${API}${seed.base}/exams/${session.id}`, { headers: studentHeaders })).json() as {
    id: string;
    started_at: string;
  };
  expect(serverSession.id).toBe(session.id);
  expect(serverSession.started_at).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  await expect(page.getByRole("button", { name: "Cevabı gönder", exact: true })).toBeVisible();

  await page.getByRole("radio").first().check();
  await page.getByRole("button", { name: "Cevabı gönder", exact: true }).click();
  await page.getByRole("button", { name: "Sınavı bitir", exact: true }).click();
  await page.getByRole("button", { name: "Bitir ve sonucu gör", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sınav sonucu", exact: true })).toBeVisible();

  const historySession = await (await request.get(`${seed.base}/exams/history`, { headers: studentHeaders })).json() as {
    items: Array<{ id: string; mode: string }>;
    next_cursor: string | null;
  };
  expect(historySession.items.map((item) => item.id)).toContain(session.id);

  await page.getByRole("button", { name: "Yeni sınav başlat", exact: true }).click();
  await page.getByRole("heading", { name: "Oturumlarım", exact: true }).waitFor();
  const historyPanel = page.locator("section[aria-labelledby='exam-history-title']");
  await expect(historyPanel.getByRole("button", { name: "Sonucu gör", exact: true }).first()).toBeVisible();
  await historyPanel.getByRole("button", { name: "Sonucu gör", exact: true }).first().click();
  await expect(page.getByRole("heading", { name: "Sınav sonucu", exact: true })).toBeVisible();
});

test("zamanlı sınavda süre dolunca cevap kabulü kapanır ve 4xx kodu gelir", async ({ page, request }) => {
  test.setTimeout(150_000);
  const seed = await seedCatalogCourse(request, { blueprintTitle: "P2 Timeout Blueprint", durationMinutes: 1, maxAttempts: 1 });
  await signInAsStudent(page);

  await page.goto(`/courses/${seed.course.id}/exam`);
  await expect(page.getByRole("listitem").filter({ hasText: seed.blueprint.title }).getByRole("button", { name: "Sınava katıl" })).toBeVisible();
  const startRequest = page.waitForResponse((response) => response.url() === `${API}${seed.base}/exams` && response.request().method() === "POST");
  await page.getByRole("listitem").filter({ hasText: seed.blueprint.title }).getByRole("button", { name: "Sınava katıl" }).click();
  const started = await startRequest;
  expect(started.status()).toBe(201);
  const session = await started.json() as { id: string; questions: Array<{ id: string }> };
  expect(session.questions).toHaveLength(1);

  await expect.poll(
    async () => {
      const current = await (await request.get(`${API}${seed.base}/exams/${session.id}`, { headers: studentHeaders })).json() as { expired: boolean };
      return current.expired;
    },
    { timeout: 95_000 },
  ).toBe(true);

  await expect(page.getByText("Süre doldu. Yeni cevap kabul edilmiyor; sonucu görmek için sınavı bitirin.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Cevabı gönder", exact: true })).toBeDisabled();

  const timedOutAnswer = request.post(`${API}${seed.base}/exams/${session.id}/answers`, {
    headers: studentHeaders,
    data: { question_id: session.questions[0].id, given: "A", hint_level: 0 },
  });
  await expectJsonError(timedOutAnswer, 409, "conflict");

  await page.getByRole("button", { name: "Sınavı bitir", exact: true }).click();
  await page.getByRole("button", { name: "Bitir ve sonucu gör", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sınav sonucu", exact: true })).toBeVisible();

  const finished = await (await request.get(`${API}${seed.base}/exams/${session.id}/results`, { headers: studentHeaders })).json() as {
    results_locked?: boolean;
  };
  expect(finished.results_locked).toBe(true);
});

test("eğitmen fake üretici ile yayın akışıyla öğrenci kataloğunu besler", async ({ request, page }) => {
  const seed = await seedCatalogCourse(request, { blueprintTitle: "P2 Instructor Flow" });

  const catalog = await assertBlueprintCatalogVisible(request, seed.base);
  expect(catalog.find((item) => item.blueprint_id === seed.blueprint.id)).toBeTruthy();

  await signInAsStudent(page);
  await page.goto(`/courses/${seed.course.id}/exam`);
  await expect(page.getByText(seed.blueprint.title)).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: seed.blueprint.title }).getByRole("button", { name: "Sınava katıl" })).toBeVisible();

  const invalidBlueprint = request.post(`${API}${seed.base}/exams`, {
    headers: studentHeaders,
    data: { mode: "exam", blueprint_id: "00000000-0000-0000-0000-000000000001" },
  });
  await expectJsonError(invalidBlueprint, 404, "not_found");

  const invalidPath = apiGet(request, `${seed.base}/exams/not-a-uuid`, studentHeaders);
  await expectJsonError(invalidPath, 422, "validation_error");
});

test.describe("Öğrenci ekran akışı @ekran", () => {
  test.skip(!EKRAN, "EKRAN=1 ile çalıştırılmadı");

  test("öğrenci başlangıç, oturum ve sonuç ekranı kayıtlarını yakalar", async ({ page }, testInfo: TestInfo) => {
    const seed = await seedCatalogCourse(page.context().request, { blueprintTitle: "P2 EKRAN Akışı" });
    await signInAsStudent(page);

    await page.goto(`/courses/${seed.course.id}/exam`);
    await page.getByRole("button", { name: "Alıştırma başlat", exact: true }).waitFor({ state: "visible" });
    await page.screenshot({ path: `../../docs/images/14-ogrenci-sinav-baslangic.png`, fullPage: true });

    await page.getByLabel("Çalışma konusu").selectOption(seed.topic.id);
    await page.getByRole("button", { name: "Alıştırma başlat", exact: true }).click();
    await expect(page.getByRole("button", { name: "Cevabı gönder", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Sınavı bitir", exact: true })).toBeVisible();
    await page.screenshot({ path: `../../docs/images/14-ogrenci-sinav-aktif.png`, fullPage: true });

    const wrongOptionIndex = seed.question.payload.options.findIndex((option) => option.key !== seed.question.payload.answer_key);
    await page.getByRole("radio").nth(wrongOptionIndex).check();
    await page.getByRole("button", { name: "Cevabı gönder", exact: true }).click();
    await page.getByRole("button", { name: "Sınavı bitir", exact: true }).click();
    await page.getByRole("button", { name: "Bitir ve sonucu gör", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Sınav sonucu", exact: true })).toBeVisible();
    await page.screenshot({ path: `../../docs/images/14-ogrenci-sinav-sonuc.png`, fullPage: true });
  });
});
