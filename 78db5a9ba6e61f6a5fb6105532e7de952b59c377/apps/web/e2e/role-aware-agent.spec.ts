/**
 * Ders kapsamlı asistanın rolünü istemcinin değil sunucunun belirlediğini
 * gerçek API ve gerçek portal üzerinden kanıtlar.
 *
 * Her vaka koşu-kapsamlı bir ders kurar. Kullanıcı rolü istek gövdesine
 * eklenmez; availability ve chat yanıtındaki zarf ders üyeliğinden gelir.
 */

import { expect, test, type Page } from "@playwright/test";

import { createE2eCourseIdentity, createE2eRequestId } from "./fixtures";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";

const AYSE = {
  id: "11111111-1111-1111-1111-111111111111",
  email: "ayse@dogus.edu.tr",
  fullName: "Ayşe Hoca",
  role: "instructor" as const,
};
const BURAK = {
  id: "22222222-2222-2222-2222-222222222222",
  email: "burak@dogus.edu.tr",
  fullName: "Burak Yılmaz",
  role: "student" as const,
};

type DemoUser = typeof AYSE | typeof BURAK;

interface Course {
  id: string;
  code: string;
  title: string;
}

interface BrowserApiCall {
  method: string;
  path: string;
  phase: "request" | "response";
}

function authorization(user: DemoUser) {
  return `Bearer dev:${user.id}`;
}

async function signIn(page: Page, user: DemoUser) {
  await page.setExtraHTTPHeaders({ "X-Request-ID": createE2eRequestId() });
  await page.addInitScript(
    ([token, payload]) => {
      localStorage.setItem("dou-synapse-token", token as string);
      localStorage.setItem("dou-synapse-user", payload as string);
    },
    [`dev:${user.id}`, JSON.stringify(user)],
  );
}

async function apiPost<T>(path: string, body: unknown, user: DemoUser): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    method: "POST",
    headers: {
      Authorization: authorization(user),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`${path} → ${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

async function createCourse(suffix: string): Promise<Course> {
  return apiPost<Course>("/courses", createE2eCourseIdentity(suffix), AYSE);
}

async function addStudent(course: Course) {
  await apiPost(
    `/courses/${course.id}/members`,
    { email: BURAK.email, role: "student" },
    AYSE,
  );
}

function courseCard(page: Page, course: Course) {
  return page
    .locator('section[aria-labelledby="course-workspaces-title"] > ul > li')
    .filter({ hasText: course.code });
}

function isCourseRequest(url: string, course: Course, suffix: string) {
  return new URL(url).pathname === `/courses/${course.id}${suffix}`;
}

function recordBrowserSignals(page: Page) {
  const calls: BrowserApiCall[] = [];
  const errors: string[] = [];
  page.on("request", (request) => {
    if (!request.url().startsWith(API)) return;
    calls.push({
      phase: "request",
      method: request.method(),
      path: new URL(request.url()).pathname,
    });
  });
  page.on("response", (response) => {
    if (!response.url().startsWith(API)) return;
    calls.push({
      phase: "response",
      method: response.request().method(),
      path: new URL(response.url()).pathname,
    });
  });
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  return { calls, errors };
}

function requestsFor(calls: BrowserApiCall[], method: string, path: string) {
  return calls.filter(
    (call) => call.phase === "request" && call.method === method && call.path === path,
  );
}

test.describe("rolü sunucudan gelen ders asistanı", () => {
  test.describe.configure({ mode: "serial" });

  test("öğrenci dashboard'unda Ders Koçu kimliği üyelikten gelir", async ({ page }) => {
    const course = await createCourse("AGENTOGR");
    await addStudent(course);
    await signIn(page, BURAK);
    await page.goto("/dashboard");

    const card = courseCard(page, course);
    await expect(card).toBeVisible();
    const availabilityPromise = page.waitForResponse(
      (response) =>
        response.request().method() === "GET" &&
        isCourseRequest(response.url(), course, "/chat/availability"),
    );
    // Dashboard persona bilgisini açılmadan çekmez; ilk etiket bilerek nötrdür.
    // Panel açıldıktan sonra sunucu zarfı gelince Ders Koçu'na dönüşür.
    const trigger = card.getByRole("button", { name: "Ders asistanı" });
    await expect(trigger).toBeVisible();
    await trigger.click();

    const availability = await availabilityPromise;
    expect(availability.status()).toBe(200);
    expect(await availability.json()).toMatchObject({
      available: true,
      audience: "student",
      agent_profile: "student_coach",
    });

    const dialog = page.getByRole("dialog");
    await expect(dialog.getByRole("heading", { name: "Ders Koçu" })).toBeVisible();
    await expect(dialog.getByText(/^Öğrenci çalışma alanı · /)).toBeVisible();
    await expect(dialog.getByRole("button", { name: "Konuyu adım adım çalış" }))
      .toBeVisible();
    await expect(dialog.getByRole("combobox", { name: /rol|persona/i })).toHaveCount(0);
  });

  test("eğitmen asistanı konuşurken istemci persona veya rol göndermez", async ({ page }) => {
    const course = await createCourse("AGENTEGT");
    await signIn(page, AYSE);
    await page.goto("/dashboard");

    const card = courseCard(page, course);
    const availabilityPromise = page.waitForResponse(
      (response) =>
        response.request().method() === "GET" &&
        isCourseRequest(response.url(), course, "/chat/availability"),
    );
    const trigger = card.getByRole("button", { name: "Ders asistanı" });
    await expect(trigger).toBeVisible();
    await trigger.click();

    const availability = await availabilityPromise;
    expect(await availability.json()).toMatchObject({
      available: true,
      audience: "instructor",
      agent_profile: "instructor_assistant",
    });

    const dialog = page.getByRole("dialog");
    await expect(dialog.getByRole("heading", { name: "Eğitmen Asistanı" })).toBeVisible();
    await expect(dialog.getByText(/^Eğitmen çalışma alanı · /)).toBeVisible();

    await dialog.getByLabel("Sorun").fill(
      "Yüklenen ders kaynaklarındaki temel kavramları kaynaklarıyla özetle.",
    );
    const answerPromise = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        isCourseRequest(response.url(), course, "/chat"),
    );
    await dialog.getByRole("button", { name: "Gönder" }).click();

    const answerResponse = await answerPromise;
    expect(answerResponse.status()).toBe(200);
    const requestBody = answerResponse.request().postDataJSON() as Record<string, unknown>;
    expect(requestBody).not.toHaveProperty("audience");
    expect(requestBody).not.toHaveProperty("agent_profile");
    expect(requestBody).not.toHaveProperty("role");
    const answer = (await answerResponse.json()) as {
      answer: string;
      status: string;
      audience: string;
      agent_profile: string;
    };
    expect(answer).toMatchObject({
      audience: "instructor",
      agent_profile: "instructor_assistant",
    });
    expect(["insufficient_context", "out_of_scope"]).toContain(answer.status);
    await expect(dialog.getByText(answer.answer, { exact: true })).toBeVisible();
  });

  test("mobil koyu dialog erişilebilir kalır ve aynı açılışta tek istek üretir", async ({
    page,
  }) => {
    const course = await createCourse("AGENTMOB");
    await addStudent(course);
    await page.setViewportSize({ width: 375, height: 812 });
    await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
    const { calls, errors } = recordBrowserSignals(page);

    await signIn(page, BURAK);
    await page.goto("/dashboard");

    const card = courseCard(page, course);
    await expect(card).toBeVisible();
    const availabilityPath = `/courses/${course.id}/chat/availability`;
    const chatPath = `/courses/${course.id}/chat`;

    // Dashboard kartı yalnızca nötr tetikleyiciyi çizer; availability açılmadan
    // okunmamalı ve bu nedenle ilk sayfa yükünde hiç çağrı olmamalı.
    expect(requestsFor(calls, "GET", availabilityPath)).toHaveLength(0);
    const trigger = card.getByRole("button", { name: "Ders asistanı" });
    const availabilityPromise = page.waitForResponse(
      (response) =>
        response.request().method() === "GET" &&
        isCourseRequest(response.url(), course, "/chat/availability"),
    );
    await trigger.click();
    await availabilityPromise;

    const dialog = page.getByRole("dialog");
    const heading = dialog.getByRole("heading", { name: "Ders Koçu" });
    const description = dialog.getByText(
      "Ders kaynaklarına bağlı kalır; gerektiğinde cevabı vermek yerine adım adım düşündürür.",
      { exact: true },
    );
    await expect(dialog).toBeVisible();
    await expect(heading).toBeVisible();
    await expect(description).toBeVisible();
    await expect(dialog).toHaveAccessibleName("Ders Koçu");
    await expect(dialog).toHaveAccessibleDescription(
      "Ders kaynaklarına bağlı kalır; gerektiğinde cevabı vermek yerine adım adım düşündürür.",
    );
    expect(requestsFor(calls, "GET", availabilityPath)).toHaveLength(1);

    const surface = await page.evaluate(() => ({
      viewport: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body.scrollWidth,
      dark: window.matchMedia("(prefers-color-scheme: dark)").matches,
      reducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    }));
    expect(surface.viewport).toBe(375);
    expect(surface.documentWidth).toBeLessThanOrEqual(surface.viewport);
    expect(surface.bodyWidth).toBeLessThanOrEqual(surface.viewport);
    expect(surface.dark).toBe(true);
    expect(surface.reducedMotion).toBe(true);

    // Native modal focus scope: both directions must remain inside the dialog.
    await expect(dialog.getByRole("button", { name: "Ders asistanını kapat" })).toBeFocused();
    for (let index = 0; index < 16; index += 1) {
      await page.keyboard.press("Tab");
      await expect
        .poll(() =>
          dialog.evaluate((element) => element.contains(document.activeElement)),
        )
        .toBe(true);
    }
    for (let index = 0; index < 16; index += 1) {
      await page.keyboard.press("Shift+Tab");
      await expect
        .poll(() =>
          dialog.evaluate((element) => element.contains(document.activeElement)),
        )
        .toBe(true);
    }

    const input = dialog.getByLabel("Sorun");
    await input.fill("Bu dersin temel konusu nedir?");
    const answerPromise = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        isCourseRequest(response.url(), course, "/chat"),
    );
    await dialog.getByRole("button", { name: "Gönder" }).click();
    const answerResponse = await answerPromise;
    expect(answerResponse.status()).toBe(200);
    await expect(dialog.getByText(/Yanıt hazırlanıyor…/)).toHaveCount(0);
    expect(requestsFor(calls, "POST", chatPath)).toHaveLength(1);
    expect(requestsFor(calls, "GET", availabilityPath)).toHaveLength(1);

    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(trigger).toBeFocused();
    expect(errors).toEqual([]);
  });
});
