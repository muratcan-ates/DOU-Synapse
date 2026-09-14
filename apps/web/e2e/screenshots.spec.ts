/**
 * Belgeler için gerçek arayüzden, yalnız koşuya ait sentetik veriyle PNG üretir.
 * Kurulum/temizlik worker-fixture ve global setup/teardown sözleşmesini kullanır.
 * EKRAN=1 ... --grep @ekran gerekir; üretim adımları docs/screenshots.md içindedir.
 * Sahte sağlayıcı/hashing görüntüsü gerçek LLM kalitesi veya görsel baseline değildir.
 */
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import { expect, type APIRequestContext, type Locator, type Page, type Response } from "@playwright/test";
import type { LearningOutcome } from "../lib/blueprint";
import type { ChatAnswer, ChatAvailability, ChatSessionSummary, Course, CourseDocument, Page as ApiPage } from "../lib/types";
import { ABSTENTION_LABEL } from "../lib/chat";
import { test as workerTest, teacher, student, teacherHeaders, studentHeaders, signIn } from "./worker-fixture";
import { createE2eCourseIdentity, isRunScopedE2eCourseCode, requireE2eRunId } from "./fixtures";
import { seedAssessmentCourse } from "./seed-assessment-course";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const OUTPUT = resolve(__dirname, "../../../docs/images");
type SeededCourse = Awaited<ReturnType<typeof seedAssessmentCourse>>;

function requireOwnedCourse(course: Course): void {
  expect(isRunScopedE2eCourseCode(course.code, requireE2eRunId())).toBe(true);
}

async function post(request: APIRequestContext, path: string, data: unknown, asStudent = false) {
  const response = await request.post(`${API}${path}`, {
    headers: asStudent ? studentHeaders : teacherHeaders,
    data,
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

const test = workerTest.extend<{ seededCourse: SeededCourse; emptyCourse: Course }>({
  seededCourse: async ({ request }, use) => {
    const seeded = await seedAssessmentCourse(request);
    requireOwnedCourse(seeded.course);
    await use(seeded);
  },
  emptyCourse: async ({ request }, use) => {
    // Materyalsiz ret, dolu dersin eşiğini değiştirerek taklit edilmez.
    const course = await post(request, "/courses", createE2eCourseIdentity("MATERYAL-BEKLENIYOR"));
    requireOwnedCourse(course);
    await post(request, `/courses/${course.id}/members`, { email: student.email, role: "student" });
    await use(course);
  },
});

async function ask(page: Page, courseId: string, question: string, responses: ReturnType<typeof observeCourseGets>): Promise<ChatAnswer> {
  const composer = page.getByLabel("Sorun", { exact: true });
  await expect(composer).toBeVisible();
  await composer.fill(question);
  const beforeSend = responses.mark();
  const [response] = await Promise.all([
    page.waitForResponse((response) =>
      response.url() === `${API}/courses/${courseId}/chat` && response.request().method() === "POST",
    ),
    page.getByRole("button", { name: "Gönder", exact: true }).click(),
  ]);
  expect(response.status(), await response.text()).toBe(200);
  const answer: ChatAnswer = await response.json();
  expect(answer).toMatchObject({ mode: "qa", audience: "student", agent_profile: "student_coach" });
  expect(answer.answer.trim().length).toBeGreaterThan(0);
  // onAnswer bu yenilemeyi beklemeden başlatır; yalnız cevap görünürlüğü yeterli değildir.
  const sessions = await responses.get<ApiPage<ChatSessionSummary>>("/chat/sessions", beforeSend);
  const summary = sessions.items.find((item) => item.id === answer.session_id);
  expect(summary).toBeDefined();
  const activeChat = page.getByRole("list", { name: "Kişisel sohbetler", exact: true }).locator('button[aria-current="true"]');
  await expect(activeChat).toContainText(summary!.title ?? "Başlıksız sohbet");
  await expect(activeChat).toBeVisible();
  await expect(page.getByText(answer.answer, { exact: true }).last()).toBeVisible();
  await expect(composer).toHaveValue("");
  await expect(page.getByRole("status").filter({ hasText: /Materyaller yükleniyor…|Sohbetler yükleniyor…/ })).toHaveCount(0);
  return answer;
}

/** Navigasyon öncesinde kurulur; erken gelen yanıtlar da sonraki koşullu beklemeye kalır. */
function observeCourseGets(page: Page, courseId: string) {
  const base = `${API}/courses/${courseId}`;
  const seen: Response[] = [];
  const collect = (response: Response) => {
    if (response.request().method() === "GET" && response.url().startsWith(base)) seen.push(response);
  };
  page.on("response", collect);
  return {
    mark: () => seen.length,
    async get<T>(suffix: string, after = 0): Promise<T> {
      const matches = (response: Response) => response.url() === `${base}${suffix}` && response.request().method() === "GET";
      const response = seen.slice(after).find(matches) ?? await page.waitForResponse(matches);
      expect(response.status(), await response.text()).toBe(200);
      return response.json();
    },
    stop() { page.off("response", collect); },
  };
}

async function instructorShellReady(page: Page, courseId: string, responses: ReturnType<typeof observeCourseGets>) {
  const [course, availability] = await Promise.all([
    responses.get<Course>(""),
    responses.get<ChatAvailability>("/chat/availability"),
  ]);
  expect(course).toMatchObject({ id: courseId, role: "instructor" });
  expect(availability).toMatchObject({ available: true, audience: "instructor", agent_profile: "instructor_assistant" });
  const questionsLink = page.getByRole("link", { name: "Soru havuzu", exact: true });
  await expect(questionsLink).toHaveAttribute("href", `/courses/${courseId}/questions`);
  await expect(questionsLink).toBeVisible();
  await expect(page.getByRole("button", { name: "Eğitmen Asistanı", exact: true })).toBeVisible();
}

/** Sohbet dışındaki öğrenci sayfasında bağımsız availability yanıtı da beklenir. */
async function studentShellReady(page: Page, courseId: string, responses: ReturnType<typeof observeCourseGets>) {
  const [course, availability] = await Promise.all([
    responses.get<Course>(""),
    responses.get<ChatAvailability>("/chat/availability"),
  ]);
  expect(course).toMatchObject({ id: courseId, role: "student" });
  expect(availability).toMatchObject({ available: true, audience: "student", agent_profile: "student_coach" });
  const chatLink = page.getByRole("link", { name: "Asistan", exact: true });
  await expect(chatLink).toHaveAttribute("href", `/courses/${courseId}/chat`);
  await expect(chatLink).toBeVisible();
  await expect(page.getByRole("button", { name: "Ders Koçu", exact: true })).toBeVisible();
}

/** Yeni öğrenci sohbetinde ilk sorudan önce her iki yan panel doğrulanır. */
async function studentChatReady(page: Page, courseId: string, responses: ReturnType<typeof observeCourseGets>, hasMaterial: boolean) {
  const [course, availability, documents, sessions] = await Promise.all([
    responses.get<Course>(""),
    responses.get<ChatAvailability>("/chat/availability"),
    responses.get<ApiPage<CourseDocument>>("/documents?limit=100"),
    responses.get<ApiPage<ChatSessionSummary>>("/chat/sessions"),
  ]);
  expect(course).toMatchObject({ id: courseId, role: "student" });
  expect(availability).toMatchObject({ available: true, audience: "student", agent_profile: "student_coach" });
  const chatLink = page.getByRole("link", { name: "Asistan", exact: true });
  await expect(chatLink).toHaveAttribute("href", `/courses/${courseId}/chat`);
  await expect(chatLink).toBeVisible();
  const materials = page.locator("aside section").filter({ has: page.getByRole("heading", { name: "Bu dersin kaynakları", exact: true }) });
  if (hasMaterial) {
    expect(documents.items).toHaveLength(1);
    expect(documents.items[0]).toMatchObject({ file_name: "network-guards.md", status: "completed" });
    await expect(materials.getByText("network-guards.md", { exact: true })).toBeVisible();
    await expect(materials.getByText("Hazır", { exact: true })).toBeVisible();
  } else {
    expect(documents.items).toEqual([]);
    await expect(materials.getByText("Bu derste henüz materyal yok. Eğitmen materyal yükleyene kadar asistan kaynak gösteremez.", { exact: true })).toBeVisible();
  }
  expect(sessions.items).toEqual([]);
  await expect(page.getByText("Henüz bir sohbet açmadın.", { exact: true })).toBeVisible();
}

async function capture(page: Page, name: string, ready: Locator): Promise<void> {
  await expect(ready).toBeVisible();
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
  await expect(page.getByRole("status").filter({
    hasText: /Yükleniyor…|Sorular yükleniyor…|Sohbet geçmişi yükleniyor…|Cevap hazırlanıyor…/,
  })).toHaveCount(0);
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.evaluate(async () => { await document.fonts.ready; });
  if (["03-egitmen-materyaller", "05-egitmen-soru-havuzu"].includes(name)) {
    // Uzun formun altındaki kontroller sabit asistan düğmesinin arkasında
    // kalmasın. DOM'u gizlemeden gerçek tarayıcı yüksekliğini ölçülen sayfa
    // boyuna ve düğme için ayrılan boşluğa göre genişlet.
    const height = await page.evaluate(() => Math.max(document.body.scrollHeight, document.documentElement.scrollHeight));
    await page.setViewportSize({ width: 1280, height: height + 80 });
    await expect(ready).toBeVisible();
  }
  await mkdir(OUTPUT, { recursive: true });
  // Sabit süre uyutmak yerine hazır arayüz/yazı tipleri beklenir; animasyon
  // son durumu ve imleç screenshot API'si tarafından kararlılaştırılır.
  await page.screenshot({ path: resolve(OUTPUT, `${name}.png`), fullPage: true, animations: "disabled", caret: "hide" });
}

async function recordPracticeAnswer(request: APIRequestContext, seeded: SeededCourse): Promise<void> {
  const options = seeded.question.payload.options as Array<{ key: string }>;
  const wrong = options.find((option) => option.key !== seeded.question.payload.answer_key);
  expect(wrong).toBeDefined();
  const exam = await post(request, `${seeded.base}/exams`, { mode: "practice" }, true);
  try {
    expect(exam.questions.some((question: { id: string }) => question.id === seeded.question.id)).toBe(true);
    const feedback = await post(request, `${seeded.base}/exams/${exam.id}/answers`, {
      question_id: seeded.question.id, given: wrong!.key,
    }, true);
    expect(feedback).toMatchObject({ recorded: true, graded: true, is_correct: false });
  } finally {
    await post(request, `${seeded.base}/exams/${exam.id}/finish`, {}, true);
  }
}

test.describe("belge ekran görüntüleri", { tag: ["@ekran", "@llm"] }, () => {
  test.use({ viewport: { width: 1280, height: 900 }, colorScheme: "light", contextOptions: { reducedMotion: "reduce" } });
  test.beforeEach(() => {
    if (process.env.EKRAN !== "1") throw new Error("Belge görüntüsü üretimi EKRAN=1 gerektirir.");
    test.setTimeout(120_000);
  });

  test("sohbet: sentetik materyale bağlı cevap", async ({ page, seededCourse }) => {
    await signIn(page, student);
    const responses = observeCourseGets(page, seededCourse.course.id);
    try {
      await page.goto(`/courses/${seededCourse.course.id}/chat`);
      await studentChatReady(page, seededCourse.course.id, responses, true);
      const answer = await ask(page, seededCourse.course.id, "Coffman koşulları nelerdir?", responses);
      expect(answer.status).toBe("answered");
      expect(answer.citations.length).toBeGreaterThan(0);
      const citation = answer.citations[0];
      // Markdown materyalin konumu bölüm adıdır; sahte bir Sayfa N beklenmez.
      const source = page.getByRole("link", {
        name: `${citation.file_name}, ${citation.location} kaynak bağlamını aç`, exact: true,
      }).first();
      await capture(page, "09-sohbet-kaynakli-cevap", source);
    } finally { responses.stop(); }
  });

  test("sohbet: materyalsiz derste dayanak bulunamaması", async ({ page, emptyCourse }) => {
    await signIn(page, student);
    const responses = observeCourseGets(page, emptyCourse.id);
    try {
      await page.goto(`/courses/${emptyCourse.id}/chat`);
      await studentChatReady(page, emptyCourse.id, responses, false);
      const answer = await ask(page, emptyCourse.id, "Deadlock nedir?", responses);
      expect(answer.status).toBe("insufficient_context");
      expect(answer.citations).toHaveLength(0);
      await capture(page, "10-sohbet-nazik-ret", page.getByText(ABSTENTION_LABEL.insufficient_context, { exact: true }));
    } finally { responses.stop(); }
  });

  test("sohbet: sentetik materyalin kapsamı dışındaki soru", async ({ page, seededCourse }) => {
    await signIn(page, student);
    const responses = observeCourseGets(page, seededCourse.course.id);
    try {
      await page.goto(`/courses/${seededCourse.course.id}/chat`);
      await studentChatReady(page, seededCourse.course.id, responses, true);
      const answer = await ask(page, seededCourse.course.id, "İtalya'nın başkenti neresidir?", responses);
      // Başka bir durum dönüyorsa bu adı taşıyan görüntü üretilmez.
      expect(answer.status).toBe("out_of_scope");
      expect(answer.citations).toHaveLength(0);
      await capture(page, "10-sohbet-kapsam-disi-ret", page.getByText(ABSTENTION_LABEL.out_of_scope, { exact: true }));
    } finally { responses.stop(); }
  });

  test("soru havuzu: API'de üretilip onaylanan sentetik soru", async ({ page, seededCourse }) => {
    await signIn(page, teacher);
    const responses = observeCourseGets(page, seededCourse.course.id);
    try {
      await page.goto(`/courses/${seededCourse.course.id}/questions`);
      await instructorShellReady(page, seededCourse.course.id, responses);
      const authoring = await responses.get<{ enabled: boolean }>("/questions/authoring");
      expect(typeof authoring.enabled).toBe("boolean");
      const outcomeField = page.getByRole("combobox", { name: "Öğrenme çıktısı", exact: true });
      const difficultyField = page.getByRole("combobox", { name: "Zorluk", exact: true });
      if (authoring.enabled) {
        const outcomes = await responses.get<LearningOutcome[]>("/learning-outcomes");
        expect(Array.isArray(outcomes)).toBe(true);
        await expect(outcomeField).toBeVisible();
        await expect(difficultyField).toBeVisible();
        await expect(page.getByRole("combobox", { name: "Konu", exact: true })).toHaveValue(seededCourse.question.topic_id);
        const matching = outcomes.filter((outcome) => outcome.topic_id === null || outcome.topic_id === seededCourse.question.topic_id);
        await expect(outcomeField.locator("option")).toHaveText([
          "Sınıflandırılmadı", ...matching.map((outcome) => `${outcome.code}: ${outcome.description}`),
        ]);
      } else {
        // Kapalı özellik de önce gerçek API kararından doğrulanır; bekleme atlanmaz.
        await expect(outcomeField).toHaveCount(0);
        await expect(difficultyField).toHaveCount(0);
      }
      await expect(page.getByRole("heading", { name: "Soru havuzu", exact: true })).toBeVisible();
      const questions = page.getByRole("list", { name: "Soru havuzu", exact: true });
      await expect(questions).toContainText(seededCourse.question.payload.stem);
      await capture(page, "05-egitmen-soru-havuzu", questions);
    } finally {
      responses.stop();
    }
  });

  test("ilerleme: sentetik cevap sonrası sınıf analitiği", async ({ page, request, seededCourse }) => {
    await recordPracticeAnswer(request, seededCourse);
    await signIn(page, teacher);
    const responses = observeCourseGets(page, seededCourse.course.id);
    try {
      await page.goto(`/courses/${seededCourse.course.id}/analytics`);
      await instructorShellReady(page, seededCourse.course.id, responses);
      await expect(page.getByRole("heading", { name: "Sınıf analitiği", exact: true })).toBeVisible();
      await expect(page.getByText("Bu gösterge resmî bir not değildir.", { exact: true })).toBeVisible();
      await capture(page, "06-egitmen-sinif-analitigi", page.getByRole("heading", { name: "Konu bazlı sınıf durumu", exact: true }));
    } finally { responses.stop(); }
  });

  test("ilerleme: sentetik cevap sonrası öğrenci görünümü", async ({ page, request, seededCourse }) => {
    await recordPracticeAnswer(request, seededCourse);
    await signIn(page, student);
    const responses = observeCourseGets(page, seededCourse.course.id);
    try {
      await page.goto(`/courses/${seededCourse.course.id}/analytics`);
      await studentShellReady(page, seededCourse.course.id, responses);
      await expect(page.getByRole("heading", { name: "İlerlemem", exact: true })).toBeVisible();
      await capture(page, "15-ogrenci-ilerleme", page.getByRole("heading", { name: "Konularım", exact: true }));
    } finally { responses.stop(); }
  });

  test("materyaller: eğitmenin sentetik ders kaynağı", async ({ page, seededCourse }) => {
    await signIn(page, teacher);
    const responses = observeCourseGets(page, seededCourse.course.id);
    try {
      await page.goto(`/courses/${seededCourse.course.id}`);
      await instructorShellReady(page, seededCourse.course.id, responses);
      await expect(page.getByRole("button", { name: "Dosya seç", exact: true })).toBeVisible();
      const retrievalLink = page.getByRole("link", { name: "Retrieval testi", exact: true });
      await expect(retrievalLink).toHaveAttribute("href", `/courses/${seededCourse.course.id}/sources`);
      await expect(retrievalLink).toBeVisible();
      await expect(page.getByRole("heading", { name: "Bu derste çalışma yolları", exact: true })).toBeVisible();
      await expect(page.getByRole("heading", { name: seededCourse.course.title, exact: true })).toBeVisible();
      // Dosya adı select içindeki gizli option'da da vardır; görünür materyal
      // satırını rolüyle seçerek yüklenmiş belgeyi doğrula.
      const material = page.getByRole("listitem").filter({ has: page.getByText("network-guards.md", { exact: true }) });
      await expect(material.getByText("Hazır", { exact: true })).toBeVisible();
      await capture(page, "03-egitmen-materyaller", material.getByText("network-guards.md", { exact: true }));
    } finally {
      responses.stop();
    }
  });

  test("kişisel veriler ve gizlilik açıklaması", async ({ page }) => {
    await page.goto("/kvkk");
    await capture(page, "16-kvkk", page.getByRole("heading", { name: "Kişisel Veriler ve Gizlilik", exact: true }));
  });
});
