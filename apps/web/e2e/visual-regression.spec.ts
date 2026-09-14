import { expect, type Browser, type Page, type Response, type TestInfo } from "@playwright/test";
import playwrightPackage from "@playwright/test/package.json";
import { existsSync, readFileSync, unlinkSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import type { Blueprint, LearningOutcome } from "../lib/blueprint";
import type { ChatAnswer, ChatAvailability, ChatSessionSummary, Course, CourseDocument, ExamCatalog, ExamSession, Page as ApiPage, Question, Topic } from "../lib/types";
import { test, teacher, student, studentHeaders, signIn } from "./worker-fixture";
import { seedAssessmentCourse } from "./seed-assessment-course";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const screens = ["login", "question-pool", "blueprint", "cited-chat", "practice-exam"] as const;
const shot = { fullPage: true, animations: "disabled" as const, caret: "hide" as const,
  scale: "css" as const, maxDiffPixels: 0 };

function baselineEnvironment(browser: Browser, info: TestInfo, theme: "light" | "dark") {
  if (process.env.E2E_VISUAL !== "1" || process.platform !== "linux" || process.env.CI !== "true") {
    throw new Error("ENGEL: görsel referans yalnız E2E_VISUAL=1 ile Linux CI imajında çalıştırılır.");
  }
  const imageDigest = process.env.E2E_VISUAL_IMAGE_DIGEST ?? "";
  if (!/^sha256:[0-9a-f]{64}$/.test(imageDigest)) {
    throw new Error("ENGEL: Linux CI çalıştırıcısının gerçek E2E_VISUAL_IMAGE_DIGEST değeri gerekli.");
  }
  const update = process.env.E2E_VISUAL_UPDATE === "1";
  const mode = update ? "all" : "none";
  if (info.config.updateSnapshots !== mode) {
    throw new Error(`ENGEL: görsel koşu --update-snapshots=${mode} ile açıkça seçilmeli.`);
  }
  const directory = dirname(info.snapshotPath(`login-${theme}.png`));
  const path = join(directory, `baseline-environment-${theme}.json`);
  const expected = { version: 1, platform: process.platform, arch: process.arch, imageDigest,
    playwright: playwrightPackage.version, browser: browser.version(),
    viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1,
    locale: "tr-TR", timezoneId: "UTC", colorScheme: theme, reducedMotion: "reduce" };
  // Yarım kalan yenileme eski başarı makbuzuyla karşılaştırılabilir görünmesin.
  if (update && existsSync(path)) unlinkSync(path);
  if (!update) {
    const missing = screens.filter((screen) => !existsSync(info.snapshotPath(`${screen}-${theme}.png`)));
    if (!existsSync(path) || missing.length !== 0) {
      throw new Error("ENGEL: aynı Linux CI imajında üretilmiş ve incelenmiş görsel baseline eksik; karşılaştırma koşulamaz.");
    }
    expect(JSON.parse(readFileSync(path, "utf8")), "Baseline ve karşılaştırma ortamı aynı olmalı.").toEqual(expected);
  }
  return { update, path, expected };
}

/** Erken GET yanıtları saklanır; işaret, işlem sonrası yenilemeyi ilk veriden ayırır. */
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

async function courseShellReady(page: Page, courseId: string, role: Course["role"], responses: ReturnType<typeof observeCourseGets>, chatPage = false) {
  const [course, availability] = await Promise.all([
    responses.get<Course>(""), responses.get<ChatAvailability>("/chat/availability"),
  ]);
  expect(course).toMatchObject({ id: courseId, role });
  expect(availability).toMatchObject({ available: true, audience: role,
    agent_profile: role === "instructor" ? "instructor_assistant" : "student_coach" });
  const link = page.getByRole("link", { name: role === "instructor" ? "Soru havuzu" : "Asistan", exact: true });
  await expect(link).toHaveAttribute("href", `/courses/${courseId}/${role === "instructor" ? "questions" : "chat"}`);
  await expect(link).toBeVisible();
  if (!chatPage) await expect(page.getByRole("button", {
    name: role === "instructor" ? "Eğitmen Asistanı" : "Ders Koçu", exact: true,
  })).toBeVisible();
}

async function readyForImage(page: Page) {
  // Her ekran önce verisini ve arayüz durumunu doğrular; yalnız yokluk hazır olma kanıtı değildir.
  await expect(page.getByRole("status").filter({ hasText: /yükleniyor…|hazırlanıyor…|doğrulanıyor…/i })).toHaveCount(0);
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
  await page.evaluate(async () => { await document.fonts.ready; });
}

for (const theme of ["light", "dark"] as const) {
  test.describe(`kritik ekranlar @visual ${theme}`, () => {
    test.use({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1,
      locale: "tr-TR", timezoneId: "UTC", colorScheme: theme, contextOptions: { reducedMotion: "reduce" } });

    test("giriş, soru havuzu, blueprint, kaynaklı sohbet ve alıştırma", async ({ page, request, browser }, info) => {
      test.setTimeout(180_000);
      // Eksik baseline, ilk API seed yazımından önce açık engeldir.
      const environment = baselineEnvironment(browser, info, theme);
      await page.goto("/");
      await expect(page.getByRole("button", { name: /Ayşe Hoca/ })).toBeVisible();
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      await readyForImage(page);
      await expect(page).toHaveScreenshot(`login-${theme}.png`, shot);

      const { course, base, question } = await seedAssessmentCourse(request);
      await signIn(page, teacher);
      const poolResponses = observeCourseGets(page, course.id);
      try {
        await page.goto(`/courses/${course.id}/questions`);
        await courseShellReady(page, course.id, "instructor", poolResponses);
        const [pool, topics, authoring] = await Promise.all([
          poolResponses.get<ApiPage<Question>>("/questions"),
          poolResponses.get<Topic[]>("/topics"),
          poolResponses.get<{ enabled: boolean }>("/questions/authoring"),
        ]);
        expect(pool.items).toHaveLength(1);
        expect(pool.items[0]).toMatchObject({ id: question.id, status: "approved" });
        expect(topics.map((topic) => topic.id)).toContain(question.topic_id);
        expect(typeof authoring.enabled).toBe("boolean");
        const topicField = page.getByRole("combobox", { name: "Konu", exact: true });
        await expect(topicField).toHaveValue(question.topic_id);
        await expect(topicField.locator("option")).toHaveText(topics.map((topic) => topic.name));
        const outcomeField = page.getByRole("combobox", { name: "Öğrenme çıktısı", exact: true });
        const difficultyField = page.getByRole("combobox", { name: "Zorluk", exact: true });
        if (authoring.enabled) {
          const outcomes = await poolResponses.get<LearningOutcome[]>("/learning-outcomes");
          expect(Array.isArray(outcomes)).toBe(true);
          await expect(outcomeField).toBeVisible();
          await expect(difficultyField).toBeVisible();
          const matching = outcomes.filter((outcome) => outcome.topic_id === null || outcome.topic_id === question.topic_id);
          await expect(outcomeField.locator("option")).toHaveText([
            "Sınıflandırılmadı", ...matching.map((outcome) => `${outcome.code}: ${outcome.description}`),
          ]);
        } else {
          await expect(outcomeField).toHaveCount(0);
          await expect(difficultyField).toHaveCount(0);
        }
        await expect(page.getByRole("heading", { name: "Soru havuzu", exact: true })).toBeVisible();
        await expect(page.getByRole("list", { name: "Soru havuzu", exact: true })).toContainText(question.payload.stem);
        await expect(page.getByRole("heading", { name: question.payload.stem, exact: true })).toBeVisible();
        await readyForImage(page);
        await expect(page).toHaveScreenshot(`question-pool-${theme}.png`, shot);
      } finally { poolResponses.stop(); }

      const blueprintResponses = observeCourseGets(page, course.id);
      try {
        await page.goto(`/courses/${course.id}/blueprints`);
        await courseShellReady(page, course.id, "instructor", blueprintResponses);
        const [outcomes, blueprints, topics, authoring] = await Promise.all([
          blueprintResponses.get<LearningOutcome[]>("/learning-outcomes"),
          blueprintResponses.get<Blueprint[]>("/blueprints"),
          blueprintResponses.get<Topic[]>("/topics"),
          blueprintResponses.get<{ enabled: boolean }>("/questions/authoring"),
        ]);
        // Yeni sentetik derste konu ve soru vardır; öğrenme çıktısı ve blueprint henüz yoktur.
        expect(outcomes).toEqual([]);
        expect(blueprints).toEqual([]);
        expect(typeof authoring.enabled).toBe("boolean");
        expect(topics.map((topic) => topic.id)).toContain(question.topic_id);
        const topicField = page.getByRole("combobox", { name: "Çıktının konusu", exact: true });
        await expect(topicField).toBeEnabled();
        await expect(topicField.locator("option")).toHaveText(["Konu atama", ...topics.map((topic) => topic.name)]);
        await expect(page.getByRole("heading", { name: "Sınav blueprint'i", exact: true })).toBeVisible();
        await expect(page.getByRole("button", { name: "Yeni sınav kur", exact: true })).toHaveAttribute("aria-disabled", "true");
        await expect(page.getByText("Henüz sınav kurulmadı.", { exact: true })).toBeVisible();
        await readyForImage(page);
        await expect(page).toHaveScreenshot(`blueprint-${theme}.png`, shot);
      } finally { blueprintResponses.stop(); }

      await signIn(page, student);
      const chatResponses = observeCourseGets(page, course.id);
      try {
        await page.goto(`/courses/${course.id}/chat`);
        await courseShellReady(page, course.id, "student", chatResponses, true);
        const [documents, sessions] = await Promise.all([
          chatResponses.get<ApiPage<CourseDocument>>("/documents?limit=100"),
          chatResponses.get<ApiPage<ChatSessionSummary>>("/chat/sessions"),
        ]);
        expect(documents.items).toHaveLength(1);
        expect(documents.items[0]).toMatchObject({ file_name: "network-guards.md", status: "completed" });
        expect(sessions.items).toEqual([]);
        const materials = page.locator("aside section").filter({ has: page.getByRole("heading", { name: "Bu dersin kaynakları", exact: true }) });
        await expect(materials.getByText("network-guards.md", { exact: true })).toBeVisible();
        await expect(materials.getByText("Hazır", { exact: true })).toBeVisible();
        await expect(page.getByText("Henüz bir sohbet açmadın.", { exact: true })).toBeVisible();
        const composer = page.getByRole("textbox", { name: "Sorun", exact: true });
        await expect(composer).toBeVisible();
        await composer.fill("Coffman koşulları nelerdir?");
        const beforeSend = chatResponses.mark();
        const [response] = await Promise.all([
          page.waitForResponse((response) => response.url() === `${API}${base}/chat` && response.request().method() === "POST"),
          page.getByRole("button", { name: "Gönder", exact: true }).click(),
        ]);
        expect(response.status(), await response.text()).toBe(200);
        const answer: ChatAnswer = await response.json();
        expect(answer).toMatchObject({ status: "answered", mode: "qa", audience: "student", agent_profile: "student_coach" });
        expect(answer.answer.trim().length).toBeGreaterThan(0);
        expect(answer.citations.length).toBeGreaterThan(0);
        const refreshed = await chatResponses.get<ApiPage<ChatSessionSummary>>("/chat/sessions", beforeSend);
        const summary = refreshed.items.find((item) => item.id === answer.session_id);
        expect(summary).toBeDefined();
        const activeChat = page.getByRole("list", { name: "Kişisel sohbetler", exact: true }).locator('button[aria-current="true"]');
        await expect(activeChat).toContainText(summary!.title ?? "Başlıksız sohbet");
        await expect(activeChat).toBeVisible();
        await expect(page.getByText(answer.answer, { exact: true }).last()).toBeVisible();
        const citation = answer.citations[0];
        await expect(page.getByRole("link", {
          name: `${citation.file_name}, ${citation.location} kaynak bağlamını aç`, exact: true,
        }).first()).toBeVisible();
        await expect(composer).toHaveValue("");
        await readyForImage(page);
        await expect(page).toHaveScreenshot(`cited-chat-${theme}.png`, shot);
      } finally { chatResponses.stop(); }

      const practiceResponses = observeCourseGets(page, course.id);
      try {
        await page.goto(`/courses/${course.id}/exam`);
        await courseShellReady(page, course.id, "student", practiceResponses);
        const catalog = await practiceResponses.get<ExamCatalog>("/exams/catalog");
        expect(typeof catalog.enabled).toBe("boolean");
        expect(catalog.items).toEqual([]);
        if (catalog.enabled) {
          const [topics, history] = await Promise.all([
            practiceResponses.get<Topic[]>("/topics"),
            practiceResponses.get<ApiPage<ExamSession>>("/exams/history"),
          ]);
          expect(history.items).toEqual([]);
          const topicField = page.getByRole("combobox", { name: "Çalışma konusu", exact: true });
          await expect(topicField.locator("option")).toHaveText(["Tüm konular", ...topics.map((topic) => topic.name)]);
          await expect(page.getByText("Bu derste henüz bir oturum başlatmadınız.", { exact: true })).toBeVisible();
        }
        const beforeStart = practiceResponses.mark();
        const [response] = await Promise.all([
          page.waitForResponse((response) => response.url() === `${API}${base}/exams` && response.request().method() === "POST"),
          page.getByRole("button", { name: "Alıştırma başlat", exact: true }).click(),
        ]);
        expect(response.status(), await response.text()).toBe(201);
        const started: ExamSession = await response.json();
        // Sonraki doğrulama veya görüntü başarısız olsa da açılan oturum temizlenir.
        try {
          expect(response.request().postDataJSON()).toMatchObject({ mode: "practice" });
          expect(started).toMatchObject({ course_id: course.id, mode: "practice", finished_at: null });
          const [session, availability] = await Promise.all([
            practiceResponses.get<ExamSession>(`/exams/${started.id}`, beforeStart),
            practiceResponses.get<ChatAvailability>("/chat/availability", beforeStart),
          ]);
          expect(session).toMatchObject({ id: started.id, mode: "practice", remaining_seconds: null });
          expect(session.questions).toHaveLength(1);
          expect(session.questions![0]).toMatchObject({ id: question.id, answered: false });
          expect(availability).toMatchObject({ available: true, audience: "student", agent_profile: "student_coach" });
          await expect(page.getByRole("button", { name: "Ders Koçu", exact: true })).toBeVisible();
          await expect(page.getByRole("button", { name: "Cevabı gönder", exact: true })).toBeVisible();
          const radios = page.getByRole("radio");
          await expect(radios).toHaveCount(question.payload.options.length);
          for (const radio of await radios.all()) {
            await expect(radio).toBeEnabled();
            await expect(radio).not.toBeChecked();
          }
          await expect(page.getByRole("timer")).toHaveCount(0);
          await expect(page.getByRole("heading", { name: question.payload.stem, exact: true })).toBeVisible();
          await readyForImage(page);
          await expect(page).toHaveScreenshot(`practice-exam-${theme}.png`, shot);
        } finally {
          const finished = await request.post(`${API}${base}/exams/${started.id}/finish`, { headers: studentHeaders, data: {} });
          expect(finished.status(), await finished.text()).toBe(200);
        }
      } finally { practiceResponses.stop(); }

      // Referans metadatası yalnız bütün referans görüntüleri üretildikten sonra yazılır.
      if (environment.update) writeFileSync(environment.path, `${JSON.stringify(environment.expected, null, 2)}\n`);
    });
  });
}
