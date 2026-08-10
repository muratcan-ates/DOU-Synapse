/**
 * Rol bazlı ürün portalının uçtan uca nöbetçileri.
 *
 * Bütün dersler gerçek API üzerinden oluşturulur; route interception veya sahte
 * JSON kullanılmaz. Her vaka benzersiz ders kodu kullandığı için Playwright'ın
 * paralel koşumunda başka bir vakanın bıraktığı veriye güvenmez.
 */

import { expect, test, type Page } from "@playwright/test";

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

interface ApiCall {
  phase: "request" | "response";
  method: string;
  path: string;
  search: string;
  body: string | null;
}

async function signIn(page: Page, user: DemoUser) {
  await page.addInitScript(
    ([token, payload]) => {
      localStorage.setItem("dou-synapse-token", token as string);
      localStorage.setItem("dou-synapse-user", payload as string);
    },
    [`dev:${user.id}`, JSON.stringify(user)],
  );
}

function authorization(user: DemoUser) {
  return `Bearer dev:${user.id}`;
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

let courseCounter = 0;
async function createCourse(owner: DemoUser, suffix: string): Promise<Course> {
  const unique = `${Date.now().toString(36)}${courseCounter++}`;
  return apiPost<Course>(
    "/courses",
    {
      code: `P${suffix}${unique}`.slice(0, 32),
      title: `Portal E2E ${suffix} ${unique}`,
    },
    owner,
  );
}

async function addStudent(course: Course, student: DemoUser) {
  await apiPost(
    `/courses/${course.id}/members`,
    { email: student.email, role: "student" },
    AYSE,
  );
}

function courseCard(page: Page, course: Course) {
  return page
    .locator('section[aria-labelledby="course-workspaces-title"] > ul > li')
    .filter({ hasText: course.code });
}

function recordPortalApiCalls(page: Page): ApiCall[] {
  const calls: ApiCall[] = [];
  page.on("request", (request) => {
    if (!request.url().startsWith(API)) return;
    const url = new URL(request.url());
    calls.push({
      phase: "request",
      method: request.method(),
      path: url.pathname,
      search: url.search,
      body: request.postData(),
    });
  });
  page.on("response", (response) => {
    if (!response.url().startsWith(API)) return;
    const url = new URL(response.url());
    calls.push({
      phase: "response",
      method: response.request().method(),
      path: url.pathname,
      search: url.search,
      body: response.request().postData(),
    });
  });
  return calls;
}

test.describe("rol bazlı ürün portalı", () => {
  test("eğitmen dashboard'u gerçek yönetim araçlarını gösterir", async ({ page }) => {
    const course = await createCourse(AYSE, "EGITMEN");
    await signIn(page, AYSE);

    await page.goto("/dashboard");

    await expect(page.getByRole("heading", { name: /Merhaba|Genel bakış/ })).toBeVisible();
    const card = courseCard(page, course);
    await expect(card).toBeVisible();
    await expect(card.getByText("Eğitmen", { exact: true })).toBeVisible();
    await expect(card.getByRole("link", { name: "Soru havuzu" })).toHaveAttribute(
      "href",
      `/courses/${course.id}/questions`,
    );
    await expect(card.getByRole("link", { name: "Sınav planı" })).toHaveAttribute(
      "href",
      `/courses/${course.id}/blueprints`,
    );
    await expect(card.getByRole("link", { name: "Ders ayarları" })).toHaveAttribute(
      "href",
      `/courses/${course.id}/settings`,
    );
    await expect(card.getByRole("link", { name: "Dersi yönet" })).toHaveAttribute(
      "href",
      `/courses/${course.id}`,
    );
    await expect(card.getByRole("link", { name: "Asistan" })).toHaveCount(0);
  });

  test("öğrenci dashboard'u yalnız çalışma araçlarını gösterir", async ({ page }) => {
    const course = await createCourse(AYSE, "OGRENCI");
    await addStudent(course, BURAK);
    await signIn(page, BURAK);

    await page.goto("/dashboard");

    const card = courseCard(page, course);
    await expect(card).toBeVisible();
    await expect(card.getByText("Öğrenci", { exact: true })).toBeVisible();
    await expect(card.getByRole("link", { name: "Asistan" })).toHaveAttribute(
      "href",
      `/courses/${course.id}/chat`,
    );
    await expect(card.getByRole("link", { name: "Sınavlar" })).toHaveAttribute(
      "href",
      `/courses/${course.id}/exam`,
    );
    await expect(card.getByRole("link", { name: "İlerleme" })).toHaveAttribute(
      "href",
      `/courses/${course.id}/analytics`,
    );
    await expect(card.getByRole("link", { name: "Çalışmaya devam et" })).toHaveAttribute(
      "href",
      `/courses/${course.id}/chat`,
    );
    await expect(card.getByRole("link", { name: "Soru havuzu" })).toHaveCount(0);
  });

  test("karma rol tek global role düzleştirilmez", async ({ page }) => {
    const studentCourse = await createCourse(AYSE, "KARMAOGR");
    await addStudent(studentCourse, BURAK);
    const instructorCourse = await createCourse(BURAK, "KARMAEGT");
    await signIn(page, BURAK);

    await page.goto("/dashboard");

    const studentCard = courseCard(page, studentCourse);
    const instructorCard = courseCard(page, instructorCourse);
    await expect(studentCard.getByText("Öğrenci", { exact: true })).toBeVisible();
    await expect(studentCard.getByRole("link", { name: "Asistan" })).toBeVisible();
    await expect(studentCard.getByRole("link", { name: "Ders ayarları" })).toHaveCount(0);
    await expect(instructorCard.getByText("Eğitmen", { exact: true })).toBeVisible();
    await expect(instructorCard.getByRole("link", { name: "Ders ayarları" })).toBeVisible();
    await expect(instructorCard.getByRole("link", { name: "Asistan" })).toHaveCount(0);
  });

  test("profil kimlik alanını, ders rollerini ve veri hakkı girişlerini gösterir", async ({
    page,
  }) => {
    const studentCourse = await createCourse(AYSE, "PROFILOGR");
    await addStudent(studentCourse, BURAK);
    const instructorCourse = await createCourse(BURAK, "PROFILEGT");
    const calls = recordPortalApiCalls(page);
    await signIn(page, BURAK);

    await page.goto("/profile");

    await expect(page.getByRole("heading", { name: "Profil", exact: true })).toBeVisible();
    await expect(page.getByLabel("Ad soyad")).toHaveValue(/\S{2,}/);
    await expect(page.getByLabel("E-posta")).toHaveValue(BURAK.email);
    await expect(page.getByLabel("E-posta")).toHaveAttribute("readonly", "");

    const memberships = page.locator('section[aria-labelledby="profile-memberships-title"] li');
    const studentMembership = memberships.filter({ hasText: studentCourse.code });
    const instructorMembership = memberships.filter({ hasText: instructorCourse.code });
    await expect(studentMembership.getByText("Öğrenci", { exact: true })).toBeVisible();
    await expect(instructorMembership.getByText("Eğitmen", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: /Verilerimi indir veya sil/ })).toHaveAttribute(
      "href",
      "/account",
    );
    await expect(page.getByRole("link", { name: /KVKK aydınlatma metni/ })).toHaveAttribute(
      "href",
      "/kvkk",
    );
    expect(calls.filter((call) => call.phase === "request" && call.path === "/me/profile"))
      .toHaveLength(1);
  });

  test("platform yöneticisi profil kapısından sonra gizlilik güvenli konsolu görür", async ({
    page,
  }) => {
    const calls = recordPortalApiCalls(page);
    await signIn(page, AYSE);

    await page.goto("/admin");

    await expect(page.getByRole("heading", { name: "Sistem yönetimi" })).toBeVisible();
    await expect(page.getByText(/Uygulama: (Hazır|Kısıtlı|Hata|Ulaşılamıyor)/)).toBeVisible();
    await expect(page.getByText(/Veritabanı: (Hazır|Kısıtlı|Hata|Ulaşılamıyor)/)).toBeVisible();
    await expect(page.getByText(/Embedding: (Hazır|Hazırlanıyor|Kapalı|Hata)/)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Kullanıcılar" })).toBeVisible();
    await expect(page.getByText("ay***@dogus.edu.tr")).toBeVisible();
    await expect(page.getByText(AYSE.email, { exact: true })).toHaveCount(0);
    const userSearch = page.getByLabel("Kullanıcı ara");
    await expect(userSearch).toHaveAttribute("placeholder", "Ad veya maskeli e-posta");
    expect((await userSearch.boundingBox())?.height).toBeGreaterThanOrEqual(40);

    const profileRequestIndex = calls.findIndex(
      (call) => call.phase === "request" && call.path === "/me/profile",
    );
    const profileResponseIndex = calls.findIndex(
      (call) => call.phase === "response" && call.path === "/me/profile",
    );
    const firstAdminRequestIndex = calls.findIndex(
      (call) => call.phase === "request" && call.path.startsWith("/admin/"),
    );
    expect(profileRequestIndex).toBeGreaterThanOrEqual(0);
    expect(profileResponseIndex).toBeGreaterThan(profileRequestIndex);
    expect(firstAdminRequestIndex).toBeGreaterThan(profileResponseIndex);
    expect(calls.filter((call) => call.phase === "request" && call.path === "/me/profile"))
      .toHaveLength(1);

    const userDirectoryRequest = calls.find(
      (call) => call.phase === "request" && call.path === "/admin/users",
    );
    expect(userDirectoryRequest).toMatchObject({ method: "POST", search: "" });
    expect(JSON.parse(userDirectoryRequest?.body ?? "{}"))
      .toMatchObject({ limit: 25, offset: 0 });

    await page.getByRole("tab", { name: "AI kullanım kayıtları" }).click();
    await expect(page.getByRole("heading", { name: "AI kullanım kayıtları" })).toBeVisible();
    await page.getByRole("tab", { name: "İşleme işleri" }).click();
    await expect(page.getByRole("heading", { name: "Kaynak işleme işleri" })).toBeVisible();
  });

  test("admin olmayan kullanıcı hem arayüzde hem API'de reddedilir", async ({ page }) => {
    const calls = recordPortalApiCalls(page);
    await signIn(page, BURAK);

    await page.goto("/admin");

    await expect(page.getByRole("heading", { name: "Bu alana erişiminiz yok" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Sistem yönetimi" })).toHaveCount(0);
    expect(calls.filter((call) => call.phase === "request" && call.path === "/me/profile"))
      .toHaveLength(1);
    expect(calls.filter((call) => call.phase === "request" && call.path.startsWith("/admin/")))
      .toHaveLength(0);

    const directResponse = await fetch(`${API}/admin/overview`, {
      headers: { Authorization: authorization(BURAK) },
    });
    expect(directResponse.status).toBe(403);
  });
});
