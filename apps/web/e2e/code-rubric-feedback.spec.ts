import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { resolveE2eDatabaseName } from "./cleanup";
import { createE2eCourseIdentity, isRunScopedE2eCourseCode, requireE2eRunId } from "./fixtures";
import type { Question, QuestionType } from "../lib/types";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const studentId = "22222222-2222-2222-2222-222222222222";
const teacherHeaders = { Authorization: "Bearer dev:11111111-1111-1111-1111-111111111111" };
const studentHeaders = { Authorization: `Bearer dev:${studentId}` };
const criterion = "Döngüsel beklemeyi açıklar";
const quote = "Döngüsel bekleme, süreçlerin birbirinin tuttuğu kaynakları beklediği bir zincirdir.";
const sourceName = "code-rubric-synthetic.md";
const rubric = [{ point: "Karşılıklı dışlamayı açıklar", weight: 60 }, { point: criterion, weight: 40 }];
interface Course { id: string; code: string }

/**
 * Only run-scoped synthetic rows in the verified E2E DB are mutable here.
 * This fixture is NOT proof of LLM grading. Actual source/rubric validation,
 * saved/results GET authorization and exam locks remain real API behavior.
 */
function fixtureSql(course: Course, sql: string, values: Record<string, string>): string {
  if (!isRunScopedE2eCourseCode(course.code, requireE2eRunId())) throw new Error("Fixture yalnız bu koşunun dersine yazabilir.");
  const database = resolveE2eDatabaseName(undefined);
  const variables = Object.entries({ ...values, course_id: course.id, course_code: course.code, student_id: studentId });
  return execFileSync(process.env.PG_BIN ? join(process.env.PG_BIN, "psql") : "psql",
    ["-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-d", database, ...variables.flatMap(([name, value]) => ["-v", `${name}=${value}`])],
    { input: sql, encoding: "utf8", env: process.env }).trim();
}
function legacyDraft(course: Course, question: Question) {
  expect(fixtureSql(course, `UPDATE questions q SET payload = q.payload - 'rubric'
    FROM courses c WHERE q.id = :'question_id'::uuid AND q.course_id = c.id
    AND c.id = :'course_id'::uuid AND c.code = :'course_code' AND q.status = 'draft'
    AND q.type IN ('code_trace', 'bug_hunt') RETURNING q.id;`, { question_id: question.id })).toBe(question.id);
}
function seedRecordedFeedback(course: Course, question: Question, sessionId: string, sourceQuote = quote) {
  expect(question.source).toBeTruthy();
  const feedback = { durum: "degerlendirildi", eksik_noktalar: [criterion], dayanak_chunk_id: question.source!.chunk_id,
    neden_yanlis_chunk_id: null, mesaj: null, odak: null,
    rubrik_kirilimi: rubric.map((item, index) => ({ ...item, score: index === 0 ? 100 : 50, earned: index === 0 ? 60 : 20 })),
    kaynakli_eksik_olcut: { criterion, chunk_id: question.source!.chunk_id, quote: sourceQuote } };
  expect(fixtureSql(course, `UPDATE answers a SET score = 80, is_correct = true, feedback = :'feedback'::jsonb
    FROM courses c, exam_sessions s WHERE a.course_id = c.id AND c.id = :'course_id'::uuid
    AND c.code = :'course_code' AND a.session_id = s.id AND s.course_id = c.id
    AND s.user_id = :'student_id'::uuid AND s.id = :'session_id'::uuid
    AND a.question_id = :'question_id'::uuid RETURNING a.question_id;`,
  { feedback: JSON.stringify(feedback), question_id: question.id, session_id: sessionId })).toBe(question.id);
}

async function prepare(request: APIRequestContext, kind: QuestionType) {
  const created = await request.post(`${API}/courses`, { headers: teacherHeaders, data: createE2eCourseIdentity(`KOD-RUBRIK-${kind}`) });
  expect(created.ok(), await created.text()).toBeTruthy(); const course = await created.json() as Course;
  const base = `${API}/courses/${course.id}`;
  expect((await request.post(`${base}/members`, { headers: teacherHeaders, data: { email: "burak@dogus.edu.tr", role: "student" } })).ok()).toBeTruthy();
  const topicResponse = await request.post(`${base}/topics`, { headers: teacherHeaders, data: { name: "Deadlock" } });
  expect(topicResponse.ok()).toBeTruthy(); const topic = await topicResponse.json();
  const upload = await request.post(`${base}/documents`, { headers: teacherHeaders, multipart: {
    file: { name: sourceName, mimeType: "text/markdown", buffer: Buffer.from(`# Deadlock\nKarşılıklı dışlama, bir kaynağa aynı anda tek sürecin erişmesidir.\n${quote}\n`) },
  } });
  expect(upload.ok(), await upload.text()).toBeTruthy();
  await expect.poll(async () => (await (await request.get(`${base}/documents`, { headers: teacherHeaders })).json()).items[0]?.status, { timeout: 25_000 }).toBe("completed");
  const generated = await request.post(`${base}/questions/generate`, { headers: teacherHeaders, data: {
    topic_id: topic.id, question_type: kind, count: 1, ...(kind === "open" ? { answer_format: "essay" } : {}),
  } });
  expect(generated.ok(), await generated.text()).toBeTruthy(); const report = await generated.json();
  expect(report.questions).toHaveLength(1);
  return { course, base, question: report.questions[0] as Question };
}
async function login(page: Page, teacher: boolean) {
  await page.goto("/"); await page.getByRole("button", { name: teacher ? /Ayşe Hoca/ : /Burak Yılmaz/ }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}
async function finish(page: Page) {
  await page.getByRole("button", { name: "Sınavı bitir", exact: true }).click();
  await page.getByRole("button", { name: "Bitir ve sonucu gör", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sınav sonucu", exact: true })).toBeVisible();
}
const evidencePanel = (page: Page) => page.getByRole("region", { name: "Eksik ölçütün dayanağı", exact: true });

for (const kind of ["code_trace", "bug_hunt", "open"] as const) {
  test(`${kind}: eğitmen rubrik düzenler; sentetik kayıtlı not gerçek kaynak ve sınav yetkisiyle gösterilir`, async ({ page, context, request }, testInfo) => {
    test.setTimeout(150_000);
    testInfo.annotations.push({ type: "fixture", description: "Recorded grading is a run-scoped DB fixture. This is real API reading/authorization evidence, not LLM grading evidence." });
    const { course, base, question } = await prepare(request, kind);
    if (kind !== "open") {
      // Generation has a complete rubric; only this isolated draft is converted to a legacy record.
      expect(question.payload.rubric).toBeInstanceOf(Array); legacyDraft(course, question);
    }
    await login(page, true); await page.goto(`/courses/${course.id}/questions`);
    await page.getByRole("button", { name: "Taslağı düzenle", exact: true }).click();
    const editor = page.getByRole("form", { name: "Taslak soru düzenleme" });
    const save = page.getByRole("button", { name: "Taslağı kaydet", exact: true });
    if (kind !== "open") {
      await expect(editor.getByText("Bu eski kod sorusunda puanlama ölçütü yok. Soruyu kaydetmeden önce ölçüt ekleyin.", { exact: true })).toBeVisible();
      await expect(save).toBeDisabled();
      await editor.getByRole("button", { name: "Ölçüt ekle", exact: true }).click();
      const { rubric: _oldRubric, ...withoutRubric } = question.payload;
      for (const payload of [withoutRubric, { ...question.payload, rubric: [] }]) {
        const invalid = await request.post(`${base}/questions/${question.id}/draft`, { headers: teacherHeaders, data: { payload, learning_outcome_id: null, difficulty: null } });
        expect(invalid.status(), await invalid.text()).toBe(422);
      }
    }
    await editor.getByLabel("Ölçüt 1", { exact: true }).fill(rubric[0].point);
    await editor.getByLabel("Ölçüt 1 puanı", { exact: true }).fill("60");
    await editor.getByRole("button", { name: "Ölçüt ekle", exact: true }).click();
    await editor.getByLabel("Ölçüt 2", { exact: true }).fill(rubric[0].point);
    await editor.getByLabel("Ölçüt 2 puanı", { exact: true }).fill("40");
    if (kind !== "open") { await expect(save).toBeDisabled(); await expect(editor.getByText("Her puanlama ölçütü farklı olmalı.", { exact: true })).toBeVisible(); }
    await editor.getByLabel("Ölçüt 2", { exact: true }).fill(criterion);
    if (kind !== "open") {
      await editor.getByLabel("Ölçüt 2 puanı", { exact: true }).fill("30"); await expect(save).toBeDisabled();
      await expect(editor.getByText("Ölçüt puanlarının toplamı 100 olmalı.", { exact: true })).toBeVisible();
      await editor.getByLabel("Ölçüt 2 puanı", { exact: true }).fill("40");
    }
    await expect(save).toBeEnabled();
    const savedResponse = page.waitForResponse((response) => response.url() === `${base}/questions/${question.id}/draft` && response.request().method() === "POST");
    await save.click(); const saved = await savedResponse; expect(saved.ok(), await saved.text()).toBeTruthy();
    const updated = await saved.json() as Question;
    expect(updated.payload.rubric).toEqual(rubric); expect(updated.source).toEqual(question.source);
    await expect(page.getByRole("heading", { name: "Puanlama ölçütü", exact: true })).toBeVisible();
    await expect(page.getByText(criterion, { exact: true })).toBeVisible();
    const approved = page.waitForResponse((response) => response.url() === `${base}/questions/${question.id}/approve`);
    await page.getByRole("button", { name: "Onayla ve öğrenciye aç", exact: true }).click(); expect((await approved).ok()).toBeTruthy();

    await login(page, false); await page.goto(`/courses/${course.id}/exam`);
    const started = page.waitForResponse((response) => response.url() === `${base}/exams` && response.request().method() === "POST");
    await page.getByRole("button", { name: "Alıştırma başlat", exact: true }).click();
    const session = await (await started).json();
    expect(session.questions[0].payload).not.toHaveProperty("rubric"); expect(session.questions[0].payload).not.toHaveProperty("answer_key");
    await page.getByRole("textbox", { name: "Cevabınız", exact: true }).fill("İş parçacıkları kilit bekler.");
    const answered = page.waitForResponse((response) => response.url() === `${base}/exams/${session.id}/answers` && response.request().method() === "POST");
    await page.getByRole("button", { name: "Cevabı gönder", exact: true }).click(); const actual = await answered;
    expect(actual.status()).toBe(201); expect((await actual.json()).graded).toBe(false);
    await expect(page.getByText("Değerlendirilemedi", { exact: true })).toBeVisible(); await expect(evidencePanel(page)).toHaveCount(0);

    seedRecordedFeedback(course, updated, session.id);
    const recorded = await request.get(`${base}/exams/${session.id}/answers/${question.id}`, { headers: studentHeaders });
    expect(recorded.ok(), await recorded.text()).toBeTruthy(); const feedback = await recorded.json();
    expect(feedback.score).toBe(80); expect(feedback.is_correct).toBe(true); expect(feedback.why_wrong).toBeNull();
    expect(feedback.grounded_missing_criterion).toEqual({ criterion, source: { ...question.source, snippet: quote } });
    await page.reload(); await expect(evidencePanel(page)).toBeVisible();
    await expect(evidencePanel(page).getByText(criterion, { exact: true })).toBeVisible(); await expect(evidencePanel(page).locator("blockquote")).toContainText(quote);
    await expect(page.getByRole("heading", { name: "Rubrik ölçütleri", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Neden yanlış?", exact: true })).toHaveCount(0);
    if (kind === "code_trace") {
      await page.setViewportSize({ width: 375, height: 812 });
      for (const theme of ["light", "dark"] as const) {
        await page.emulateMedia({ colorScheme: theme, reducedMotion: "reduce" });
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
        await page.screenshot({ path: testInfo.outputPath(`code-feedback-375-${theme}.png`), fullPage: true });
      }
    }
    const sourcePath = `/courses/${course.id}/sources/${question.source!.chunk_id}`;
    await expect(evidencePanel(page).getByRole("link")).toHaveAttribute("href", sourcePath);
    await evidencePanel(page).getByRole("link").click();
    await expect(page).toHaveURL(new RegExp(`/sources/${question.source!.chunk_id}$`));
    await expect(page.getByRole("heading", { name: sourceName, exact: true })).toBeVisible();
    await expect(page.getByText("Atıfta kullanılan pasaj", { exact: true })).toBeVisible();
    await page.goto(`/courses/${course.id}/exam`); await expect(evidencePanel(page)).toBeVisible(); await finish(page);
    await expect(evidencePanel(page)).toBeVisible();
    const result = await request.get(`${base}/exams/${session.id}/results`, { headers: studentHeaders });
    expect(result.ok()).toBeTruthy(); expect((await result.json()).results[0].grounded_missing_criterion.source.snippet).toBe(quote);

    // A persisted forged quote cannot become a claim merely because it is in the saved JSON.
    seedRecordedFeedback(course, updated, session.id, "Bu alıntı kaynak metninde bulunmuyor.");
    await page.reload(); await expect(page.getByRole("heading", { name: "Değerlendirmenin dayanağı", exact: true })).toBeVisible();
    await expect(evidencePanel(page)).toHaveCount(0);
    seedRecordedFeedback(course, updated, session.id); await page.reload(); await expect(evidencePanel(page)).toBeVisible();

    if (kind === "code_trace") {
      const examTab = await context.newPage(); await examTab.goto(`/courses/${course.id}/exam`);
      const restart = examTab.getByRole("button", { name: "Yeni sınav başlat", exact: true });
      await expect(examTab.getByRole("heading", { name: /^(Sınav provası|Sınav sonucu)$/ })).toBeVisible();
      if (await restart.isVisible()) await restart.click();
      const next = examTab.waitForResponse((response) => response.url() === `${base}/exams` && response.request().method() === "POST");
      await examTab.getByRole("button", { name: "Sınav başlat", exact: true }).click(); const lockedSession = await (await next).json();
      await expect(examTab.getByRole("timer")).toBeVisible(); await expect(evidencePanel(page)).toHaveCount(0);
      expect((await request.get(`${API}${sourcePath}`, { headers: studentHeaders })).status()).toBe(403);
      expect(lockedSession.questions[0].payload).not.toHaveProperty("rubric"); expect(lockedSession.questions[0].payload).not.toHaveProperty("answer_key");
      await examTab.getByRole("textbox", { name: "Cevabınız", exact: true }).fill("İş parçacıkları kilit bekler.");
      const hiddenAnswer = examTab.waitForResponse((response) => response.url() === `${base}/exams/${lockedSession.id}/answers` && response.request().method() === "POST");
      await examTab.getByRole("button", { name: "Cevabı gönder", exact: true }).click(); expect((await hiddenAnswer).status()).toBe(201);
      seedRecordedFeedback(course, updated, lockedSession.id); await examTab.reload();
      await expect(examTab.getByRole("timer")).toBeVisible(); await expect(evidencePanel(examTab)).toHaveCount(0);
      await expect(examTab.getByRole("heading", { name: "Rubrik ölçütleri", exact: true })).toHaveCount(0);
      await expect(examTab.getByText("Cevap anahtarı", { exact: true })).toHaveCount(0);
      expect((await request.get(`${base}/exams/${lockedSession.id}/answers/${question.id}`, { headers: studentHeaders })).status()).toBe(403);
      await finish(examTab); await expect(evidencePanel(examTab)).toBeVisible(); await expect(evidencePanel(page)).toBeVisible();
    }
  });
}
