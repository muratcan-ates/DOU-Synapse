import { expect, test, type APIRequestContext, type Locator, type Page } from "@playwright/test";
import { createE2eCourseIdentity } from "./fixtures";
import { DEMO_RESPONSE_LABEL } from "../lib/demo-response";
import type { ChatAnswer, ChatMessage, Page as ApiPage } from "../lib/types";

/**
 * Bu dosya ayrı, yerel LLM_SIMULATE_RATE_LIMIT=1 API sürecine karşı koşar.
 * Bayrağı yalnız Playwright ortamına vermek API'yi değiştirmez. Yanıt veya
 * sağlayıcı sayacı taklit edilmez; yanlış sunucu seçilirse kabul testi kırmızı kalır.
 * L1: normal E2E seçimi ve bu dosyanın simülasyon API süreci ayrı bağlanmalıdır.
 */
const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const teacherHeaders = { Authorization: "Bearer dev:11111111-1111-1111-1111-111111111111" };
const studentHeaders = { Authorization: "Bearer dev:22222222-2222-2222-2222-222222222222" };
const sourceName = "provider-fallback.md";
const sourceText = "# Deadlock\nDeadlock iki veya daha fazla sürecin birbirini beklemesidir. Coffman koşulları karşılıklı dışlama, tut ve bekle, kesintisizlik ve dairesel beklemedir.\n";
const normalizedWhitespace = (text: string) => text.replace(/\s+/g, " ").trim();

async function prepareCourse(request: APIRequestContext) {
  const created = await request.post(`${API}/courses`, {
    headers: teacherHeaders, data: createE2eCourseIdentity("SAGLAYICI-DEMO"),
  });
  expect(created.ok(), await created.text()).toBeTruthy();
  const course = await created.json() as { id: string; code: string };
  const base = `${API}/courses/${course.id}`;
  const membership = await request.post(`${base}/members`, {
    headers: teacherHeaders, data: { email: "burak@dogus.edu.tr", role: "student" },
  });
  expect(membership.ok(), await membership.text()).toBeTruthy();
  const upload = await request.post(`${base}/documents`, {
    headers: teacherHeaders,
    multipart: { file: { name: sourceName, mimeType: "text/markdown", buffer: Buffer.from(sourceText) } },
  });
  expect(upload.ok(), await upload.text()).toBeTruthy();
  await expect.poll(async () => {
    const response = await request.get(`${base}/documents`, { headers: teacherHeaders });
    expect(response.ok(), await response.text()).toBeTruthy();
    return (await response.json()).items[0]?.status;
  }, { timeout: 25_000 }).toBe("completed");
  return { course, base };
}

async function login(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: /Burak Yılmaz/ }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

async function send(page: Page, container: Page | Locator, base: string, question: string) {
  await container.getByRole("textbox", { name: "Sorun", exact: true }).fill(question);
  const received = page.waitForResponse((response) =>
    response.url() === `${base}/chat` && response.request().method() === "POST",
  );
  await container.getByRole("button", { name: "Gönder", exact: true }).click();
  const response = await received;
  expect(response.status(), await response.text()).toBe(200);
  return await response.json() as ChatAnswer;
}

function expectFixture(answer: ChatAnswer) {
  expect(answer.status).toBe("answered");
  expect(answer.fixture).toBe(true);
  expect(answer.provider_attempts).toBe(2);
  expect(answer.answer.startsWith(`${DEMO_RESPONSE_LABEL}\n\n`)).toBe(true);
  expect(answer.citations.length).toBeGreaterThan(0);
  for (const citation of answer.citations) {
    expect(citation.file_name).toBe(sourceName);
    expect(citation.location.length).toBeGreaterThan(0);
    const snippet = normalizedWhitespace(citation.snippet);
    expect(snippet.length).toBeGreaterThan(0);
    expect(normalizedWhitespace(sourceText)).toContain(snippet);
  }
}

async function eventTypes(request: APIRequestContext, base: string) {
  const response = await request.get(`${base}/learning-events`, { headers: studentHeaders });
  expect(response.ok(), await response.text()).toBeTruthy();
  const events = await response.json() as { items: Array<{ event_type: string }> };
  return events.items.map((event) => event.event_type);
}

test("iki 429 sonrası tam sohbette demo etiketi ve gerçek kaynaklar görünür; geçmişte açıklama korunur", async ({ page, request }, testInfo) => {
  test.setTimeout(120_000);
  const { course, base } = await prepareCourse(request);
  await login(page);
  await page.goto(`/courses/${course.id}/chat`);
  await page.getByRole("button", { name: "Soru-cevap", exact: true }).click();
  const answer = await send(page, page, base, "Deadlock nedir?");
  expectFixture(answer);
  await expect(page.getByText(DEMO_RESPONSE_LABEL, { exact: true })).toBeVisible();
  const source = page.getByRole("link", {
    name: `${answer.citations[0].file_name}, ${answer.citations[0].location} kaynak bağlamını aç`, exact: true,
  }).first();
  await expect(source).toBeVisible();
  await expect(source.locator("blockquote")).toBeVisible();
  await expect(source.locator("blockquote")).toHaveText(`“${answer.citations[0].snippet}”`);
  expect(await eventTypes(request, base)).toContain("provider_rate_limited");
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("demo-answer-desktop-light.png"), fullPage: true, animations: "disabled" });

  const loaded = page.waitForResponse((response) =>
    response.url().startsWith(`${base}/chat/sessions/${answer.session_id}`) && response.request().method() === "GET",
  );
  await page.reload();
  const historyResponse = await loaded;
  expect(historyResponse.ok(), await historyResponse.text()).toBeTruthy();
  const history = await historyResponse.json() as ApiPage<ChatMessage>;
  const savedAnswer = history.items.find((message) => message.id === answer.message_id);
  expect(savedAnswer?.content).toBe(answer.answer);
  // Geçmişte ayrı köken alanı yoktur; sunucunun kalıcı açıklaması düz gövdede görünür.
  await expect(page.locator("p").filter({ hasText: DEMO_RESPONSE_LABEL })).toBeVisible();
  await expect(page.getByRole("link", { name: /provider-fallback.md.*kaynak bağlamını aç/ }).first()).toBeVisible();

  await page.getByRole("button", { name: "Yeni sohbet", exact: true }).click();
  const cached = await send(page, page, base, "Deadlock nedir?");
  expect(cached.cached).toBe(true);
  expect(cached.fixture ?? null).toBeNull();
  expect(cached.provider_attempts).toBe(0);
  expect(cached.answer).toBe(answer.answer);
  expect(cached.citations.map((citation) => citation.chunk_id)).toEqual(answer.citations.map((citation) => citation.chunk_id));
  // Önbellek ayrı köken alanını bildirmese de gövde açıklaması görünür kalır.
  await expect(page.locator("p").filter({ hasText: DEMO_RESPONSE_LABEL })).toBeVisible();
  await expect(page.getByRole("link", { name: /provider-fallback.md.*kaynak bağlamını aç/ }).first()).toBeVisible();
});

test("kompakt sohbet ve Sokratik ilk üretim turu aynı demo açıklamasını ve kaynak konumunu korur", async ({ page, request }, testInfo) => {
  test.setTimeout(120_000);
  const { course, base } = await prepareCourse(request);
  await login(page);
  await page.locator('section[aria-labelledby="course-workspaces-title"] > ul > li')
    .filter({ hasText: course.code }).getByRole("button", { name: "Ders asistanı", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Ders Koçu", exact: true });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Soru-cevap", exact: true }).click();
  const qa = await send(page, dialog, base, "Deadlock nedir?");
  expectFixture(qa);
  await expect(dialog.getByText(DEMO_RESPONSE_LABEL, { exact: true })).toBeVisible();
  await dialog.locator("summary").filter({ hasText: `${qa.citations.length} kaynak` }).click();
  const source = dialog.getByRole("link", {
    name: `${qa.citations[0].file_name}, ${qa.citations[0].location} kaynak bağlamını aç`, exact: true,
  }).first();
  await expect(source).toBeVisible();
  await expect(source.locator("blockquote")).toBeVisible();
  await expect(source.locator("blockquote")).toHaveText(`“${qa.citations[0].snippet}”`);

  await dialog.getByRole("button", { name: "Sokratik", exact: true }).click();
  // İlk DIAGNOSE kararı refusal_notice taşımaz; kanıt geçerse gerçek üretim yapılır.
  const socratic = await send(page, dialog, base, "Coffman koşulları nelerdir?");
  expectFixture(socratic);
  expect(socratic.mode).toBe("socratic");
  expect(socratic.socratic_stage).toBe("diagnose");
  expect(socratic.hints.length).toBeGreaterThan(0);
  await expect(dialog.getByText(DEMO_RESPONSE_LABEL, { exact: true })).toBeVisible();
  await expect(dialog.getByText(`${sourceName} · ${socratic.citations[0].location}`, { exact: true })).toBeVisible();
  await expect(dialog.getByRole("textbox", { name: "Denemen", exact: true })).toBeVisible();
  await expect(dialog.getByRole("alert")).toHaveCount(0);
  await page.setViewportSize({ width: 375, height: 812 });
  await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(dialog.getByText(DEMO_RESPONSE_LABEL, { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("demo-socratic-375-dark.png"), fullPage: true, animations: "disabled" });
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
});

test("kapsam dışı soru simülasyon açıkken sağlayıcıyı hiç çağırmaz ve sakin ret gösterir", async ({ page, request }) => {
  test.setTimeout(120_000);
  const { course, base } = await prepareCourse(request);
  await login(page);
  await page.goto(`/courses/${course.id}/chat`);
  await page.getByRole("button", { name: "Soru-cevap", exact: true }).click();
  const answer = await send(page, page, base, "İtalya'nın başkenti neresidir?");
  expect(answer.status).toBe("out_of_scope");
  expect(answer.provider_attempts).toBe(0);
  expect(answer.fixture ?? null).toBeNull();
  expect(answer.citations).toEqual([]);
  expect(answer.hints).toEqual([]);
  await expect(page.getByText("Dersin kapsamı dışında", { exact: true })).toBeVisible();
  await expect(page.getByText(DEMO_RESPONSE_LABEL, { exact: true })).toHaveCount(0);
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
  const events = await eventTypes(request, base);
  expect(events).toContain("unsupported_refusal");
  expect(events).not.toContain("provider_rate_limited");
});
