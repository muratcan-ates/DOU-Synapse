import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { resolveE2eDatabaseName } from "./cleanup";
import { createE2eCourseIdentity, isRunScopedE2eCourseCode, requireE2eRunId } from "./fixtures";
import type { AnswerFeedback, Question } from "../lib/types";

/**
 * Gerçek yerel API, PostgreSQL ve kaynak doğrulaması kullanılır. Essay sağlayıcısı
 * kontrollü sentetiktir; bu senaryo gerçek LLM kalitesi iddiası değildir.
 * Ayrı API süreci LOCAL + FakeLlmClient + LLM_SIMULATE_GROUNDED_FEEDBACK=1 ile,
 * değerlendirme çalışma zamanı kapalıyken başlatılmalıdır. Playwright'a bayrak
 * vermek API'yi değiştirmez. L1 normal/simülasyon seçimini ayrı bağlamalıdır.
 * Puan veya geri bildirim satırı test tarafından yazılmaz. Tek DB değişikliği,
 * bu koşuya ait kaynak metnini geçici boşaltıp finally içinde geri yüklemektir.
 */
const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const teacherHeaders = { Authorization: "Bearer dev:11111111-1111-1111-1111-111111111111" };
const studentHeaders = { Authorization: "Bearer dev:22222222-2222-2222-2222-222222222222" };
const sourceName = "grounded-wrong-feedback.md";
const criterion = "Döngüsel bekleme kaynak bekleyen süreçlerden oluşan zincirdir.";
const code = "total = 1\ntotal += 2\nprint(total)";
const buggyCode = "values = [10, 20]\nfor index in range(3):\n    print(values[index])";
const fix = "Döngü sınırında len(values) kullanın.";
type Kind = "open" | "code_trace" | "bug_hunt";
const firstEvidence: Record<Kind, string> = {
  open: criterion,
  code_trace: "print(total) çıktısı başında veya sonunda boşluk olmadan 3 olur.",
  bug_hunt: "Bu kodda hata üçüncü satırdadır: values dizisinin 2 indeksine erişim IndexError üretir.",
};
const sourceTextFor = (kind: Kind) => `# Deadlock ve kod izleme\n${firstEvidence[kind]}\n${criterion}\nBir süreç başka bir sürecin tuttuğu kaynağı bekler.\nPython kodunda total önce 1 olur, 2 eklenince 3 olur. print(total) çıktısı 3 olur.\n${code}\nİki elemanlı values dizisinde geçerli indeksler 0 ve 1 olur. Aşağıdaki kodda üçüncü satır index 2 olduğunda IndexError üretir. ${fix}\n${buggyCode}\n`;
interface Course { id: string; code: string }

function payloadFor(kind: Kind) {
  if (kind === "open") return {
    prompt: "Döngüsel beklemeyi açıklayın.", format: "essay", answer_key: criterion,
    key_points: [criterion], rubric: [{ point: criterion, weight: 100 }],
  };
  if (kind === "code_trace") return {
    prompt: "Kodun çıktısını yazın.", language: "python", code, answer_key: "3",
    explanation: "total değişkeni 1 ile başlar ve 2 artarak 3 olur.",
    rubric: [{ point: "Beklenen çıktıyı korur.", weight: 100 }],
  };
  return {
    prompt: "Hatalı satırı, hata türünü ve düzeltmeyi belirtin.", language: "python", code: buggyCode,
    answer_key: { line: 3, bug_type: "IndexError", fix_summary: fix },
    explanation: "İki elemanlı dizinin 2 indeksine erişilemez.",
    rubric: [{ point: "Hatalı satırı ve düzeltmeyi belirler.", weight: 100 }],
  };
}

async function prepare(request: APIRequestContext, kind: Kind) {
  const sourceText = sourceTextFor(kind);
  const post = async (path: string, data: unknown) => {
    const response = await request.post(`${API}${path}`, { headers: teacherHeaders, data });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json();
  };
  const course = await post("/courses", createE2eCourseIdentity(`YANLIS-KANIT-${kind}`)) as Course;
  const path = `/courses/${course.id}`;
  await post(`${path}/members`, { email: "burak@dogus.edu.tr", role: "student" });
  const topic = await post(`${path}/topics`, { name: "Deadlock" });
  const upload = await request.post(`${API}${path}/documents`, { headers: teacherHeaders,
    multipart: { file: { name: sourceName, mimeType: "text/markdown", buffer: Buffer.from(sourceText) } },
  });
  expect(upload.ok(), await upload.text()).toBeTruthy();
  await expect.poll(async () => {
    const response = await request.get(`${API}${path}/documents`, { headers: teacherHeaders });
    expect(response.ok(), await response.text()).toBeTruthy();
    return (await response.json()).items[0]?.status;
  }, { timeout: 25_000 }).toBe("completed");
  const generated = await post(`${path}/questions/generate`, {
    topic_id: topic.id, question_type: kind, count: 1, ...(kind === "open" ? { answer_format: "essay" } : {}),
  });
  expect(generated.questions).toHaveLength(1);
  const question = generated.questions[0] as Question;
  const edited = await post(`${path}/questions/${question.id}/draft`, {
    payload: payloadFor(kind), learning_outcome_id: null, difficulty: null,
  }) as Question;
  expect(edited.source?.chunk_id).toBe(question.source?.chunk_id);
  expect(edited.source?.snippet.trim().length).toBeGreaterThan(0);
  await post(`${path}/questions/${question.id}/approve`, {});
  return { course, base: `${API}${path}`, question: edited, sourceText };
}

async function start(page: Page, course: Course, base: string) {
  await page.goto("/");
  await page.getByRole("button", { name: /Burak Yılmaz/ }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.goto(`/courses/${course.id}/exam`);
  const started = page.waitForResponse((response) => response.url() === `${base}/exams` && response.request().method() === "POST");
  await page.getByRole("button", { name: "Alıştırma başlat", exact: true }).click();
  const response = await started;
  expect(response.ok(), await response.text()).toBeTruthy();
  const session = await response.json();
  expect(session.questions).toHaveLength(1);
  expect(session.questions[0].payload).not.toHaveProperty("answer_key");
  expect(session.questions[0].payload).not.toHaveProperty("rubric");
  return session as { id: string };
}

async function submit(page: Page, base: string, sessionId: string, kind: Kind) {
  const given = kind === "open" ? "Süreçlerin kaynak beklemesi gerekmez." : kind === "code_trace" ? " 3\n" : fix;
  await page.getByRole("textbox", { name: "Cevabınız", exact: true }).fill(given);
  if (kind === "bug_hunt") {
    await page.getByRole("textbox", { name: "Hata satırı", exact: true }).fill("1");
    await expect(page.getByRole("button", { name: "Cevabı gönder", exact: true })).toHaveAttribute("aria-disabled", "true");
    await page.getByRole("textbox", { name: "Hata türü", exact: true }).fill("IndexError");
  }
  const received = page.waitForResponse((response) => response.url() === `${base}/exams/${sessionId}/answers` && response.request().method() === "POST");
  await page.getByRole("button", { name: "Cevabı gönder", exact: true }).click();
  const response = await received;
  expect(response.status(), await response.text()).toBe(201);
  const sent = response.request().postDataJSON() as { given: string };
  if (kind === "bug_hunt") {
    expect(JSON.parse(sent.given)).toEqual({ version: 1, line: 1, bug_type: "IndexError", fix_summary: fix });
  } else {
    expect(sent.given).toBe(given);
  }
  return await response.json() as AnswerFeedback;
}

function sourceSql(course: Course, question: Question, sql: string, values: Record<string, string> = {}) {
  if (!isRunScopedE2eCourseCode(course.code, requireE2eRunId()) || !question.source) {
    throw new Error("Kaynak kontrolü yalnız bu koşunun kaynaklı sorusuna uygulanır.");
  }
  const variables = { course_id: course.id, course_code: course.code, question_id: question.id,
    chunk_id: question.source.chunk_id, ...values };
  return execFileSync(process.env.PG_BIN ? join(process.env.PG_BIN, "psql") : "psql",
    ["-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-d", resolveE2eDatabaseName(undefined),
      ...Object.entries(variables).flatMap(([key, value]) => ["-v", `${key}=${value}`])],
    { input: sql, encoding: "utf8", env: process.env }).trim();
}

const ownedSource = `FROM chunks ch JOIN questions q ON q.source_chunk_id = ch.id AND q.course_id = ch.course_id
  JOIN courses c ON c.id = q.course_id WHERE c.id = :'course_id'::uuid AND c.code = :'course_code'
  AND q.id = :'question_id'::uuid AND ch.id = :'chunk_id'::uuid`;

function changeSource(course: Course, question: Question, previous: string, next: string) {
  // FK kaynak silmeyi engeller. Yalnız sahip olunan tek chunk'ın metni karşılaştırılarak değiştirilir;
  // soru, cevap, puan ve geri bildirim tablolarına yazılmaz. Beklenmeyen yeni metnin üzerine yazılmaz.
  const changed = sourceSql(course, question, `WITH owned AS (SELECT ch.id ${ownedSource})
    UPDATE chunks ch SET text = :'next_text' FROM owned
    WHERE ch.id = owned.id AND ch.text = :'previous_text' RETURNING ch.id;`,
  { previous_text: previous, next_text: next });
  expect(changed).toBe(question.source!.chunk_id);
}

const nextHintPanel = (page: Page) => page.getByRole("region", { name: "Sonraki adım için ipucu", exact: true });

for (const kind of ["open", "code_trace", "bug_hunt"] as const) {
  test(`${kind}: gerçek yanlış cevap çelişen kaynak ve sonraki ipucuyla kaydedilir`, async ({ page, request }, testInfo) => {
    test.setTimeout(150_000);
    testInfo.annotations.push({ type: "provider", description: "Essay üreticisi kontrollü sentetiktir; puan/feedback seedlenmez. API, kaynak doğrulaması ve görünüm gerçektir." });
    const { course, base, question, sourceText } = await prepare(request, kind);
    const session = await start(page, course, base);
    const feedback = await submit(page, base, session.id, kind);
    expect(feedback.graded).toBe(true);
    expect(feedback.score).toBeLessThan(100);
    if (kind !== "open") expect(feedback.score).toBe(0);
    expect(feedback.why_wrong?.chunk_id).toBe(question.source!.chunk_id);
    expect(feedback.why_wrong?.snippet).toBe(firstEvidence[kind]);
    expect(feedback.next_hint?.source.chunk_id).toBe(question.source!.chunk_id);
    expect(feedback.next_hint?.source).toEqual(feedback.why_wrong);
    expect(feedback.evidence).toEqual(feedback.why_wrong);
    expect(feedback.next_hint?.text.trim().length).toBeGreaterThan(0);
    for (const source of [feedback.why_wrong!, feedback.next_hint!.source]) {
      expect(source.snippet.trim().length).toBeGreaterThan(0);
      expect(sourceText).toContain(source.snippet);
      expect(source.file_name).toBe(sourceName);
    }
    await expect(page.getByRole("heading", { name: "Neden yanlış?", exact: true })).toBeVisible();
    const sharedSource = page.getByRole("region", { name: "Neden yanlış?", exact: true }).getByRole("link");
    await expect(sharedSource).toHaveCount(1);
    await expect(sharedSource.locator("blockquote")).toBeVisible();
    await expect(sharedSource.locator("blockquote")).toHaveText(`“${feedback.why_wrong!.snippet}”`);
    await expect(sharedSource).toHaveAttribute("href", `/courses/${course.id}/sources/${question.source!.chunk_id}`);
    await expect(nextHintPanel(page)).toContainText(feedback.next_hint!.text);
    await expect(nextHintPanel(page).getByRole("link")).toHaveCount(0);
    await expect(nextHintPanel(page).locator("blockquote")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Değerlendirmenin dayanağı", exact: true })).toHaveCount(0);
    await page.reload();
    await expect(nextHintPanel(page)).toContainText(feedback.next_hint!.text);
    await expect(sharedSource.locator("blockquote")).toHaveText(`“${feedback.why_wrong!.snippet}”`);
    await expect(nextHintPanel(page).getByRole("link")).toHaveCount(0);
    const saved = await request.get(`${base}/exams/${session.id}/answers/${question.id}`, { headers: studentHeaders });
    expect(saved.ok(), await saved.text()).toBeTruthy();
    expect((await saved.json()).next_hint).toEqual(feedback.next_hint);
    if (kind === "code_trace") {
      await page.setViewportSize({ width: 375, height: 812 });
      for (const theme of ["light", "dark"] as const) {
        await page.emulateMedia({ colorScheme: theme, reducedMotion: "reduce" });
        await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
        await expect(nextHintPanel(page)).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
        await page.screenshot({ path: testInfo.outputPath(`next-hint-375-${theme}.png`), fullPage: true, animations: "disabled" });
      }
    }
  });

  test(`${kind}: kaynak boşaldığında puan ve açıklama üretilmez`, async ({ page, request }) => {
    test.setTimeout(150_000);
    const { course, base, question } = await prepare(request, kind);
    const session = await start(page, course, base);
    const original = JSON.parse(sourceSql(course, question, `SELECT to_json(ch.text) ${ownedSource};`)) as string;
    expect(original.trim().length).toBeGreaterThan(0);
    changeSource(course, question, original, "");
    try {
      const feedback = await submit(page, base, session.id, kind);
      expect(feedback.graded).toBe(false);
      expect(feedback.score ?? null).toBeNull();
      expect(feedback.why_wrong ?? null).toBeNull();
      expect(feedback.evidence ?? null).toBeNull();
      expect(feedback.next_hint ?? null).toBeNull();
      expect(feedback.solution ?? null).toBeNull();
      await expect(page.getByText("Değerlendirilemedi", { exact: true })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Neden yanlış?", exact: true })).toHaveCount(0);
      await expect(nextHintPanel(page)).toHaveCount(0);
    } finally {
      changeSource(course, question, "", original);
    }
    const saved = await request.get(`${base}/exams/${session.id}/answers/${question.id}`, { headers: studentHeaders });
    expect(saved.ok(), await saved.text()).toBeTruthy();
    const restored = await saved.json() as AnswerFeedback;
    expect(restored.graded).toBe(false);
    expect(restored.next_hint ?? null).toBeNull();
  });
}
