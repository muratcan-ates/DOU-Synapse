import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { createE2eCourseIdentity } from "./fixtures";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const studentId = "22222222-2222-2222-2222-222222222222";
const teacherHeaders = { Authorization: "Bearer dev:11111111-1111-1111-1111-111111111111" };
const studentHeaders = { Authorization: `Bearer dev:${studentId}` };
const deletionKey = "dou-synapse:chat-deletion:v1";
const rememberedKey = (id: string) => `dou-synapse-chat-session:${id}`;
const composer = (page: Page) => page.getByRole("textbox", { name: "Sorun", exact: true });
const paragraphs = (page: Page, text: string) => page.locator("p").filter({ hasText: text });
const history = (page: Page) => page.getByRole("list", { name: "Kişisel sohbetler" });

async function prepareCourse(request: APIRequestContext) {
  const response = await request.post(`${API}/courses`, { headers: teacherHeaders, data: createE2eCourseIdentity("SOHBET-SILME") });
  expect(response.ok(), await response.text()).toBeTruthy();
  const course = await response.json() as { id: string; code: string };
  const base = `${API}/courses/${course.id}`;
  expect((await request.post(`${base}/members`, { headers: teacherHeaders, data: { email: "burak@dogus.edu.tr", role: "student" } })).ok()).toBeTruthy();
  const upload = await request.post(`${base}/documents`, { headers: teacherHeaders, multipart: {
    file: { name: "deletion-synthetic.md", mimeType: "text/markdown", buffer: Buffer.from("# Deadlock\nDeadlock iki veya daha fazla sürecin birbirini beklemesidir. Coffman koşulları karşılıklı dışlama, tut ve bekle, kesintisizlik ve dairesel beklemedir.\n") },
  } });
  expect(upload.ok(), await upload.text()).toBeTruthy();
  await expect.poll(async () => (await (await request.get(`${base}/documents`, { headers: teacherHeaders })).json()).items[0]?.status, { timeout: 25_000 }).toBe("completed");
  return { course, base };
}
async function seedChat(request: APIRequestContext, base: string, question: string, teacher = false) {
  const response = await request.post(`${base}/chat`, { headers: teacher ? teacherHeaders : studentHeaders, data: { question, mode: "qa" } });
  expect(response.status(), await response.text()).toBe(200);
  return await response.json() as { session_id: string };
}
async function login(page: Page, teacher = false) {
  await page.goto("/"); await page.getByRole("button", { name: teacher ? /Ayşe Hoca/ : /Burak Yılmaz/ }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}
async function send(page: Page, text: string) {
  await composer(page).fill(text); await page.getByRole("button", { name: "Gönder", exact: true }).click();
}
async function openCompact(page: Page, code: string) {
  await page.goto("/dashboard");
  await page.locator('section[aria-labelledby="course-workspaces-title"] > ul > li').filter({ hasText: code })
    .getByRole("button", { name: "Ders asistanı", exact: true }).click();
  await expect(composer(page)).toBeVisible();
}
async function deleteCourse(page: Page, base: string) {
  await page.getByRole("button", { name: "Bu dersteki sohbetlerimi sil", exact: true }).click();
  const confirmation = page.getByRole("group", { name: "Sohbet silme onayı" });
  await expect(confirmation.getByRole("button", { name: "Vazgeç", exact: true })).toBeFocused();
  const result = page.waitForResponse((response) => response.url() === `${base}/chat/sessions` && response.request().method() === "DELETE");
  await confirmation.getByRole("button", { name: "Kalıcı olarak sil", exact: true }).click(); expect((await result).status()).toBe(200);
}
function gate() {
  let release!: () => void; let capture!: () => void;
  return { hold: new Promise<void>((resolve) => { release = resolve; }), seen: new Promise<void>((resolve) => { capture = resolve; }),
    release: () => release(), capture: () => capture() };
}
async function paint(page: Page) {
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
}

for (const teacher of [false, true]) {
  test(`${teacher ? "eğitmen" : "öğrenci"} tek ve ders sohbet silmesini açıkça onaylar; diğer oturum/kişi/ders ve sınav taslağı korunur`, async ({ page, request }, testInfo) => {
    test.setTimeout(120_000);
    const { course, base } = await prepareCourse(request); const { base: otherBase } = await prepareCourse(request);
    const ownHeaders = teacher ? teacherHeaders : studentHeaders; const otherHeaders = teacher ? studentHeaders : teacherHeaders;
    const removedQuestion = "Deadlock nedir? Silinecek sentetik sohbet.";
    const keptQuestion = "Coffman koşulları nelerdir? Korunacak sentetik sohbet.";
    const removed = await seedChat(request, base, removedQuestion, teacher); const kept = await seedChat(request, base, keptQuestion, teacher);
    const otherUser = await seedChat(request, base, "Deadlock nedir? Diğer kişinin sohbeti.", !teacher);
    const otherCourse = await seedChat(request, otherBase, "Deadlock nedir? Diğer ders sohbeti.", teacher);
    await login(page, teacher); await page.goto(`/courses/${course.id}/chat`);
    await history(page).getByRole("listitem").filter({ hasText: keptQuestion }).getByRole("button").first().click();
    await expect(paragraphs(page, keptQuestion)).toBeVisible();
    const draft = "Gönderilmemiş sentetik taslak korunmalı."; await composer(page).fill(draft);
    const examDraft = `dou-synapse:exam-drafts:v1:${studentId}:synthetic:exam`;
    await page.evaluate((key) => { sessionStorage.setItem(key, "synthetic-exam-draft"); localStorage.setItem("deletion-test:preference", "keep"); }, examDraft);
    const removedRow = history(page).getByRole("listitem").filter({ hasText: removedQuestion });
    await removedRow.getByRole("button", { name: "Sohbeti sil", exact: true }).click();
    const cancel = page.getByRole("group", { name: "Sohbet silme onayı" }).getByRole("button", { name: "Vazgeç", exact: true });
    await expect(cancel).toBeFocused(); await page.keyboard.press("Enter");
    await expect(page.getByRole("group", { name: "Sohbet silme onayı" })).toHaveCount(0);
    expect((await request.get(`${base}/chat/sessions/${removed.session_id}`, { headers: ownHeaders })).status()).toBe(200);
    await removedRow.getByRole("button", { name: "Sohbeti sil", exact: true }).click();
    if (!teacher) {
      await page.setViewportSize({ width: 375, height: 812 }); await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
      await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
      await page.screenshot({ path: testInfo.outputPath("delete-confirmation-375-dark.png"), fullPage: true, animations: "disabled" });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    }
    const deleted = page.waitForResponse((response) => response.url() === `${base}/chat/sessions/${removed.session_id}` && response.request().method() === "DELETE");
    await page.getByRole("group", { name: "Sohbet silme onayı" }).getByRole("button", { name: "Kalıcı olarak sil", exact: true }).click();
    expect((await deleted).status()).toBe(200); await expect(removedRow).toHaveCount(0);
    await expect(paragraphs(page, keptQuestion)).toBeVisible(); await expect(composer(page)).toHaveValue(draft);
    expect(await page.evaluate((key) => localStorage.getItem(key), rememberedKey(course.id))).toBe(kept.session_id);
    expect((await request.get(`${base}/chat/sessions/${removed.session_id}`, { headers: ownHeaders })).status()).toBe(404);
    await expect(page.getByText("Sohbet silindi. Diğer sohbetlerin korundu.", { exact: true })).toBeVisible();
    await deleteCourse(page, base);
    await expect(paragraphs(page, keptQuestion)).toHaveCount(0); await expect(composer(page)).toHaveValue("");
    expect((await (await request.get(`${base}/chat/sessions`, { headers: ownHeaders })).json()).items).toEqual([]);
    expect((await request.get(`${base}/chat/sessions/${otherUser.session_id}`, { headers: otherHeaders })).status()).toBe(200);
    expect((await request.get(`${otherBase}/chat/sessions/${otherCourse.session_id}`, { headers: ownHeaders })).status()).toBe(200);
    expect(await page.evaluate((key) => sessionStorage.getItem(key), examDraft)).toBe("synthetic-exam-draft");
    expect(await page.evaluate(() => localStorage.getItem("deletion-test:preference"))).toBe("keep");
    expect(await page.evaluate((key) => localStorage.getItem(key), rememberedKey(course.id))).toBeNull();
    const marker = await page.evaluate((key) => localStorage.getItem(key), deletionKey);
    expect(Object.keys(JSON.parse(marker!)).sort()).toEqual(["authEpoch", "courseId", "nonce", "sessionId"]);
    expect(marker).not.toContain(draft); expect(marker).not.toContain(keptQuestion); expect(marker).not.toContain(studentId);
  });
}

test("ders silmesi bekleyen gerçek200 sohbeti ve eski listeyi geri getiremez; diğer sekmedeki kompakt sohbet temizlenir", async ({ page, context, request }) => {
  test.setTimeout(120_000);
  const { course, base } = await prepareCourse(request); const oldTitle = "Deadlock nedir? Eski liste satırının sentetik sorusu.";
  await seedChat(request, base, oldTitle);
  await login(page); await page.goto(`/courses/${course.id}/chat`); await expect(composer(page)).toBeVisible();
  const compact = await context.newPage(); await openCompact(compact, course.code);
  const compactQuestion = "Deadlock nedir? Kompakt özel sentetik soru.";
  const compactAnswer = compact.waitForResponse((response) => response.url() === `${base}/chat` && response.request().method() === "POST");
  await send(compact, compactQuestion); expect((await compactAnswer).status()).toBe(200); await expect(paragraphs(compact, compactQuestion)).toBeVisible();
  const delayed = await context.newPage(); await delayed.goto(`/courses/${course.id}/chat`); await expect(composer(delayed)).toBeVisible();
  const post = gate(); const list = gate();
  await delayed.route(`${base}/chat`, async (route) => {
    const response = await route.fetch(); expect(response.status()).toBe(200); post.capture(); await post.hold; await route.fulfill({ response });
  }, { times: 1 });
  const privateQuestion = "Coffman koşulları nelerdir? Gecikmiş özel sentetik soru.";
  await send(delayed, privateQuestion); await post.seen;
  const oldList = await context.newPage();
  await oldList.route(`${base}/chat/sessions`, async (route) => {
    const response = await route.fetch(); expect(response.status()).toBe(200); list.capture(); await list.hold; await route.fulfill({ response });
  }, { times: 1 });
  await oldList.goto(`/courses/${course.id}/chat`); await list.seen;
  try {
    await deleteCourse(page, base);
    // Background consumers get neither focus nor a manual invalidation here.
    await expect(composer(delayed)).toHaveValue(""); await expect(paragraphs(compact, compactQuestion)).toHaveCount(0);
    await expect(composer(compact)).toHaveValue("");
    await expect(compact.getByText("Bu sohbet geçmişten silindi. Yeni bir soru sorabilirsin.", { exact: true })).toBeVisible();
    const postDelivered = delayed.waitForResponse((response) => response.url() === `${base}/chat` && response.status() === 200);
    const listDelivered = oldList.waitForResponse((response) => response.url() === `${base}/chat/sessions` && response.status() === 200);
    post.release(); list.release(); await postDelivered; await listDelivered; await paint(delayed); await paint(oldList);
    await expect(paragraphs(delayed, privateQuestion)).toHaveCount(0); await expect(oldList.getByText(oldTitle, { exact: true })).toHaveCount(0);
    expect(await delayed.evaluate((key) => localStorage.getItem(key), rememberedKey(course.id))).toBeNull();
    expect((await (await request.get(`${base}/chat/sessions`, { headers: studentHeaders })).json()).items).toEqual([]);
  } finally { post.release(); list.release(); }
});

test("silme bildirimini kaçırmış tam ve kompakt sekmeler pageshow ile gerçek yetki ve geçmişi yeniden okur", async ({ page, context, request }) => {
  test.setTimeout(120_000);
  const { course, base } = await prepareCourse(request); const title = "Deadlock nedir? Geri dönen sekmenin sentetik özel sohbeti.";
  const seeded = await seedChat(request, base, title);
  await login(page); await page.goto(`/courses/${course.id}/chat`);
  const compact = await context.newPage(); await openCompact(compact, course.code);
  const compactTitle = "Deadlock nedir? Geri dönen kompakt özel soru.";
  const compactAnswer = compact.waitForResponse((response) => response.url() === `${base}/chat` && response.request().method() === "POST");
  await send(compact, compactTitle); expect((await compactAnswer).status()).toBe(200); await expect(paragraphs(compact, compactTitle)).toBeVisible();
  // The new tab's initial auth reconciliation clears shared selections. Establish
  // this stale-selection fixture through the UI after both tabs have initialized.
  await history(page).getByRole("listitem").filter({ hasText: title }).getByRole("button").first().click();
  await expect(paragraphs(page, title)).toBeVisible();
  await expect.poll(() => page.evaluate((key) => localStorage.getItem(key), rememberedKey(course.id))).toBe(seeded.session_id);
  await expect(paragraphs(compact, compactTitle)).toBeVisible();
  // A real DELETE via API emits no browser event. A single storage marker is not treated as a deletion log.
  expect((await request.delete(`${base}/chat/sessions`, { headers: studentHeaders })).status()).toBe(200);
  expect(await page.evaluate((key) => localStorage.getItem(key), rememberedKey(course.id))).toBe(seeded.session_id);
  for (const target of [page, compact]) {
    const fresh = gate();
    await target.route(`${base}/chat/availability`, async (route) => { fresh.capture(); await fresh.hold; await route.fallback(); }, { times: 1 });
    try {
      await target.evaluate(() => window.dispatchEvent(new Event("pageshow"))); await fresh.seen;
      await expect(paragraphs(target, target === page ? title : compactTitle)).toHaveCount(0); await expect(composer(target)).toHaveCount(0);
      fresh.release(); await expect(composer(target)).toBeVisible(); await expect(composer(target)).toHaveValue("");
      await expect(paragraphs(target, target === page ? title : compactTitle)).toHaveCount(0);
    } finally { fresh.release(); }
  }
  await expect(page.getByText(title, { exact: true })).toHaveCount(0);
  expect((await (await request.get(`${base}/chat/sessions`, { headers: studentHeaders })).json()).items).toEqual([]);
});

for (const failure of ["membership", "history-conflict"] as const) {
  test(`${failure === "membership" ? "gerçek üyelik kaybı404" : "chat_history_changed409 sözleşmesi"} eski konuşmayı kapatır ve açık yeniden yükleme ister`, async ({ page, request }) => {
    test.setTimeout(90_000);
    const { course, base } = await prepareCourse(request); const title = "Deadlock nedir? Yetki yenilenecek sentetik sohbet.";
    await seedChat(request, base, title); await login(page); await page.goto(`/courses/${course.id}/chat`);
    await history(page).getByRole("listitem").filter({ hasText: title }).getByRole("button").first().click(); await expect(paragraphs(page, title)).toBeVisible();
    if (failure === "membership") {
      expect((await request.delete(`${base}/members/${studentId}`, { headers: teacherHeaders })).status()).toBe(204);
    } else {
      // Only this error envelope is synthetic. Actual DELETE/POST409 ordering has separate API concurrency evidence.
      await page.route(`${base}/chat`, (route) => route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ error: {
        code: "chat_history_changed", message: "Sohbet geçmişin veya ders erişimin değiştiği için bekleyen yanıt kaydedilmedi. Devam etmek için yeni bir sohbet aç.", request_id: "synthetic-history-conflict",
      } }) }), { times: 1 });
    }
    await send(page, "Coffman koşulları nelerdir? Yeniden gönderilmemesi gereken özel taslak.");
    await expect(page.getByRole("button", { name: "Sohbeti yeniden yükle", exact: true })).toBeVisible();
    await expect(composer(page)).toHaveCount(0); await expect(paragraphs(page, title)).toHaveCount(0);
    expect(await page.evaluate((key) => localStorage.getItem(key), rememberedKey(course.id))).toBeNull();
    await page.getByRole("button", { name: "Sohbeti yeniden yükle", exact: true }).click();
    if (failure === "membership") {
      await expect(page.getByRole("alert").first()).toBeVisible();
      await expect(page.getByRole("button", { name: "Bu dersteki sohbetlerimi sil", exact: true })).toHaveCount(0); await expect(composer(page)).toHaveCount(0);
      expect((await request.delete(`${base}/chat/sessions`, { headers: studentHeaders })).status()).toBe(404);
    } else { await expect(composer(page)).toBeVisible(); await expect(composer(page)).toHaveValue(""); }
  });
}

test("aktif sınavda kendi sohbetini silebilir; silme sohbet okuma ve cevap yardımını açmaz", async ({ page, request }) => {
  test.setTimeout(120_000);
  const { course, base } = await prepareCourse(request); await seedChat(request, base, "Deadlock nedir? Sınavdan önceki sentetik sohbet.");
  const topicResponse = await request.post(`${base}/topics`, { headers: teacherHeaders, data: { name: "Deadlock" } });
  expect(topicResponse.ok()).toBeTruthy(); const topic = await topicResponse.json();
  const generated = await request.post(`${base}/questions/generate`, { headers: teacherHeaders, data: { topic_id: topic.id, count: 1, question_type: "mcq" } });
  expect(generated.ok(), await generated.text()).toBeTruthy(); const question = (await generated.json()).questions[0];
  expect((await request.post(`${base}/questions/${question.id}/approve`, { headers: teacherHeaders, data: {} })).ok()).toBeTruthy();
  const started = await request.post(`${base}/exams`, { headers: studentHeaders, data: { mode: "exam" } });
  expect(started.ok(), await started.text()).toBeTruthy(); const exam = await started.json();
  try {
    await login(page); await page.goto(`/courses/${course.id}/chat`); await expect(composer(page)).toHaveCount(0);
    await deleteCourse(page, base); await expect(composer(page)).toHaveCount(0);
    expect((await request.get(`${base}/chat/sessions`, { headers: studentHeaders })).status()).toBe(403);
    expect((await request.post(`${base}/chat`, { headers: studentHeaders, data: { question: "Coffman koşulları nelerdir?", mode: "qa" } })).status()).toBe(403);
  } finally { expect((await request.post(`${base}/exams/${exam.id}/finish`, { headers: studentHeaders })).ok()).toBeTruthy(); }
  expect((await (await request.get(`${base}/chat/sessions`, { headers: studentHeaders })).json()).items).toEqual([]);
});
