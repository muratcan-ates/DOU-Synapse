/** Browser-level fail-closed release gates for the course agent. */

import { expect, test, type Page } from "@playwright/test";

import { createE2eCourseIdentity, createE2eRequestId } from "./fixtures";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const DISABLED_API = process.env.E2E_DISABLED_API_URL;

if (!DISABLED_API) {
  throw new Error(
    "E2E_DISABLED_API_URL yok. Kill-switch kapısı sessizce atlanamaz; ikinci API sürecini başlatın.",
  );
}

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

interface Course {
  id: string;
  code: string;
  title: string;
}

function authorization(userId: string) {
  return `Bearer dev:${userId}`;
}

async function apiJson<T>(
  baseUrl: string,
  path: string,
  options: { method?: string; userId: string; body?: unknown },
): Promise<{ status: number; body: T }> {
  const response = await fetch(`${baseUrl}${path}`, {
    method: options.method ?? "GET",
    headers: {
      Authorization: authorization(options.userId),
      "Content-Type": "application/json",
      "X-Request-ID": createE2eRequestId(),
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  return { status: response.status, body: (await response.json()) as T };
}

async function createCourse(suffix: string): Promise<Course> {
  const result = await apiJson<Course>(API, "/courses", {
    method: "POST",
    userId: AYSE.id,
    body: createE2eCourseIdentity(suffix),
  });
  expect(result.status).toBe(201);
  const membership = await apiJson(API, `/courses/${result.body.id}/members`, {
    method: "POST",
    userId: AYSE.id,
    body: { email: BURAK.email, role: "student" },
  });
  expect(membership.status).toBe(201);
  return result.body;
}

async function signIn(page: Page) {
  await page.addInitScript(
    ([token, payload]) => {
      localStorage.setItem("dou-synapse-token", token as string);
      localStorage.setItem("dou-synapse-user", payload as string);
    },
    [`dev:${BURAK.id}`, JSON.stringify(BURAK)],
  );
}

function courseCard(page: Page, course: Course) {
  return page
    .locator('section[aria-labelledby="course-workspaces-title"] > ul > li')
    .filter({ hasText: course.code });
}

test.describe("release readiness fail-closed kapıları", () => {
  test.describe.configure({ mode: "serial" });

  test("tarayıcıdan mode exam gönderimi sohbet ucunda reddedilir", async ({ page }) => {
    const course = await createCourse("MODEEXAM");
    await signIn(page);
    await page.goto("/dashboard");

    const result = await page.evaluate(
      async ({ api, courseId, userId, requestId }) => {
        const response = await fetch(`${api}/courses/${courseId}/chat`, {
          method: "POST",
          headers: {
            Authorization: `Bearer dev:${userId}`,
            "Content-Type": "application/json",
            "X-Request-ID": requestId,
          },
          body: JSON.stringify({ question: "Sınav cevabı ver.", mode: "exam" }),
        });
        return { status: response.status, body: await response.json() };
      },
      {
        api: API,
        courseId: course.id,
        userId: BURAK.id,
        requestId: createE2eRequestId(),
      },
    );

    expect(result.status).toBe(422);
    expect(result.body.error.code).toBe("validation_error");
    expect(result.body.error.message).toContain("Sınav");
    expect(result.body.error.request_id).toBeTruthy();
  });

  test("global kill switch UI ve ham POST'u aynı anda kapatır", async ({ page }) => {
    const course = await createCourse("KILLSWITCH");
    const disabledPath = `/courses/${course.id}/chat/availability`;
    const disabledAvailability = await apiJson<{
      available: boolean;
      reason: string;
      allowed_modes: string[];
    }>(DISABLED_API, disabledPath, { userId: BURAK.id });

    expect(disabledAvailability.status).toBe(200);
    expect(disabledAvailability.body).toMatchObject({
      available: false,
      reason: "globally_disabled",
      allowed_modes: [],
    });

    await signIn(page);
    await page.route(`${API}${disabledPath}`, async (route) => {
      const response = await page.request.get(`${DISABLED_API}${disabledPath}`, {
        headers: {
          Authorization: authorization(BURAK.id),
          "X-Request-ID": createE2eRequestId(),
        },
      });
      await route.fulfill({
        status: response.status(),
        contentType: "application/json",
        body: await response.text(),
      });
    });
    await page.goto("/dashboard");
    const card = courseCard(page, course);
    await expect(card).toBeVisible();
    await card.getByRole("button", { name: "Ders asistanı" }).click();

    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByText("Asistan bakım nedeniyle kapalı", { exact: true }),
    ).toBeVisible();
    await expect(dialog.getByRole("button", { name: "Gönder" })).toHaveCount(0);

    const directPost = await apiJson<{ error: { code: string; request_id: string } }>(
      DISABLED_API,
      `/courses/${course.id}/chat`,
      {
        method: "POST",
        userId: BURAK.id,
        body: { question: "Bu çağrı provider'a gitmemeli.", mode: "qa" },
      },
    );
    expect(directPost.status).toBe(503);
    expect(directPost.body.error.code).toBe("course_agent_disabled");
    expect(directPost.body.error.request_id).toBeTruthy();
  });
});
