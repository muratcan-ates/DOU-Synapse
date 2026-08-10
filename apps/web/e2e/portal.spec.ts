/**
 * Rol bazlı ürün portalının uçtan uca nöbetçileri.
 *
 * Bütün dersler gerçek API üzerinden oluşturulur; route interception veya sahte
 * JSON kullanılmaz. Her vaka benzersiz ders kodu kullandığı için Playwright'ın
 * paralel koşumunda başka bir vakanın bıraktığı veriye güvenmez.
 */

import { expect, test, type Locator, type Page } from "@playwright/test";

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

interface ApiCall {
  phase: "request" | "response";
  method: string;
  path: string;
  search: string;
  body: string | null;
}

interface ProfileSnapshot {
  full_name: string | null;
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

async function apiGet<T>(path: string, user: DemoUser): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    headers: { Authorization: authorization(user) },
  });
  if (!response.ok) {
    throw new Error(`${path} → ${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

async function apiPatch<T>(path: string, body: unknown, user: DemoUser): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    method: "PATCH",
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

async function createCourse(owner: DemoUser, suffix: string): Promise<Course> {
  const identity = createE2eCourseIdentity(suffix);
  return apiPost<Course>(
    "/courses",
    identity,
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

async function expectVisibleFocusRing(target: Locator) {
  await expect(target).toBeFocused();
  const focusStyle = await target.evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      outlineStyle: style.outlineStyle,
      outlineWidth: Number.parseFloat(style.outlineWidth),
    };
  });
  expect(focusStyle.outlineStyle).not.toBe("none");
  expect(focusStyle.outlineWidth).toBeGreaterThanOrEqual(2);
}

async function expectMobileDarkAndFocused(page: Page, surfaceControl: Locator) {
  await expect(page.getByRole("navigation", { name: "Mobil ana menü" })).toBeVisible();

  await page.keyboard.press("Tab");
  const skipLink = page.getByRole("link", { name: "Ana içeriğe geç" });
  await expect(skipLink).toBeVisible();
  await expectVisibleFocusRing(skipLink);

  await expect(surfaceControl).toBeVisible();
  for (let tab = 0; tab < 30; tab += 1) {
    if (await surfaceControl.evaluate((element) => element === document.activeElement)) break;
    await page.keyboard.press("Tab");
  }
  await expectVisibleFocusRing(surfaceControl);

  const surface = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
    prefersDark: window.matchMedia("(prefers-color-scheme: dark)").matches,
    background: getComputedStyle(document.body).backgroundColor,
  }));
  expect(surface.document).toBeLessThanOrEqual(surface.viewport);
  expect(surface.body).toBeLessThanOrEqual(surface.viewport);
  expect(surface.prefersDark).toBe(true);
  expect(surface.background).toBe("rgb(25, 23, 21)");
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
    await expect(card.getByRole("link", { name: "AI politikası" })).toHaveAttribute(
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

  test("az verili ders uydurma akademik bilgi veya skor üretmez", async ({ page }) => {
    const course = await createCourse(AYSE, "AZVERI");
    await addStudent(course, BURAK);
    await signIn(page, BURAK);

    await page.goto("/dashboard");

    const card = courseCard(page, course);
    await expect(card).toBeVisible();
    await expect(
      card
        .getByText("Çalışma sorusu", { exact: true })
        .locator("xpath=following-sibling::dd"),
    ).toHaveText("0");
    await expect(
      card
        .getByText("Yayındaki sınav", { exact: true })
        .locator("xpath=following-sibling::dd"),
    ).toHaveText("0");
    await expect(card.getByText("Kaynak", { exact: true }).locator("xpath=following-sibling::dd"))
      .toHaveText("0");
    await expect(card.getByText("Henüz ölçülmedi", { exact: true })).toBeVisible();
    await expect(card.getByText("Son etkinlik: Henüz etkinlik yok", { exact: true }))
      .toBeVisible();
    await expect(page.getByText(/GPA|AGNO|dönem|danışman|program|duyuru/i))
      .toHaveCount(0);
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
    await expect(studentCard.getByRole("link", { name: "AI politikası" })).toHaveCount(0);
    await expect(instructorCard.getByText("Eğitmen", { exact: true })).toBeVisible();
    await expect(instructorCard.getByRole("link", { name: "AI politikası" })).toBeVisible();
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

  test("profil PATCH sunucu adını ve paylaşılan üst çubuk değerini yeniler", async ({
    page,
  }) => {
    const originalProfile = await apiGet<ProfileSnapshot>("/me/profile", AYSE);
    const originalName = originalProfile.full_name ?? AYSE.fullName;
    const updatedName = `Ayşe E2E ${Date.now().toString(36)}`;
    await signIn(page, AYSE);

    try {
      await page.goto("/profile");

      const nameInput = page.getByLabel("Ad soyad");
      await expect(nameInput).toHaveValue(originalName);
      await nameInput.fill(`  ${updatedName}  `);

      const patchResponse = page.waitForResponse(
        (response) =>
          response.url() === `${API}/me/profile` &&
          response.request().method() === "PATCH",
      );
      await page.getByRole("button", { name: "Profili kaydet" }).click();
      expect((await patchResponse).status()).toBe(200);

      await expect(page.getByRole("status")).toHaveText("Profil adınız güncellendi.");
      await expect(nameInput).toHaveValue(updatedName);
      await expect(page.getByRole("link", { name: updatedName, exact: true })).toBeVisible();
      await expect.poll(async () => (await apiGet<ProfileSnapshot>("/me/profile", AYSE)).full_name)
        .toBe(updatedName);

      await page.reload();
      await expect(page.getByLabel("Ad soyad")).toHaveValue(updatedName);
      await expect(page.getByRole("link", { name: updatedName, exact: true })).toBeVisible();
    } finally {
      await apiPatch<ProfileSnapshot>("/me/profile", { full_name: originalName }, AYSE);
    }
  });

  test("çıkış sonrası yeni kullanıcı önceki admin profilini devralmaz", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Ayşe Hoca/ }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole("link", { name: "Bilgi İşlem" })).toBeVisible();

    await page.getByRole("button", { name: "Çıkış" }).click();
    await expect(page).toHaveURL(/\/$/);
    await page.getByRole("button", { name: /Burak Yılmaz/ }).click();

    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole("link", { name: "Bilgi İşlem" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Burak Yılmaz", exact: true }))
      .toBeVisible();
  });

  test("global öğrenci ders eğitmeniyse blueprint aracını yalnız o derste kullanır", async ({
    page,
  }) => {
    const studentCourse = await createCourse(AYSE, "BPOGR");
    await addStudent(studentCourse, BURAK);
    const instructorCourse = await createCourse(BURAK, "BPEGT");
    await signIn(page, BURAK);

    await page.goto("/dashboard");
    const studentCard = courseCard(page, studentCourse);
    const instructorCard = courseCard(page, instructorCourse);
    await expect(studentCard.getByRole("link", { name: "Sınav planı" })).toHaveCount(0);
    const instructorTool = instructorCard.getByRole("link", { name: "Sınav planı" });
    await expect(instructorTool).toHaveAttribute(
      "href",
      `/courses/${instructorCourse.id}/blueprints`,
    );
    await instructorTool.click();
    await expect(page).toHaveURL(new RegExp(`/courses/${instructorCourse.id}/blueprints$`));
    await expect(page.getByRole("heading", { name: "Sınav blueprint'i", exact: true }))
      .toBeVisible();
    await expect(page.getByRole("link", { name: "Sınav blueprint'i", exact: true }))
      .toBeVisible();
    await expect(page.getByRole("button", { name: "Yeni sınav kur" })).toBeVisible();
    const instructorBlueprints = await fetch(
      `${API}/courses/${instructorCourse.id}/blueprints`,
      { headers: { Authorization: authorization(BURAK) } },
    );
    expect(instructorBlueprints.status).toBe(200);

    await page.goto(`/courses/${studentCourse.id}/blueprints`);
    await expect(
      page.getByText("Sınav blueprint'i eğitmen aracıdır; bu sayfa sana kapalı."),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Sınav blueprint'i", exact: true }))
      .toHaveCount(0);
    await expect(page.getByRole("button", { name: "Yeni sınav kur" })).toHaveCount(0);
    const studentBlueprints = await fetch(`${API}/courses/${studentCourse.id}/blueprints`, {
      headers: { Authorization: authorization(BURAK) },
    });
    expect(studentBlueprints.status).toBe(403);
  });

  test("platform yöneticisi profil kapısından sonra gizlilik güvenli konsolu görür", async ({
    page,
  }) => {
    const calls = recordPortalApiCalls(page);
    await signIn(page, AYSE);

    await page.goto("/admin");

    await expect(page.getByRole("heading", { name: "Bilgi İşlem" })).toBeVisible();
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

    const fullEmailRequest = page.waitForRequest(
      (request) =>
        new URL(request.url()).pathname === "/admin/users" &&
        request.method() === "POST" &&
        request.postDataJSON()?.search === BURAK.email,
    );
    await userSearch.fill(BURAK.email);
    await page.getByRole("button", { name: "Uygula" }).click();
    const exactEmailRequest = await fullEmailRequest;
    const exactEmailUrl = new URL(exactEmailRequest.url());
    expect(exactEmailUrl.search).toBe("");
    expect(exactEmailUrl.toString()).not.toContain(BURAK.email);
    expect(exactEmailRequest.postDataJSON()).toMatchObject({
      limit: 25,
      offset: 0,
      search: BURAK.email,
    });
    await expect(page.getByText("Kullanıcı kaydı bulunamadı.", { exact: true }))
      .toBeVisible();
    await expect(page.getByText(AYSE.email, { exact: true })).toHaveCount(0);

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
    await expect(page.getByRole("link", { name: "Bilgi İşlem" })).toHaveCount(0);
    expect(calls.filter((call) => call.phase === "request" && call.path === "/me/profile"))
      .toHaveLength(1);
    expect(calls.filter((call) => call.phase === "request" && call.path.startsWith("/admin/")))
      .toHaveLength(0);

    const directResponse = await fetch(`${API}/admin/overview`, {
      headers: {
        Authorization: authorization(BURAK),
        "X-Request-ID": createE2eRequestId(),
      },
    });
    expect(directResponse.status).toBe(403);
  });

  test("mobil ve koyu temada dashboard ile profil taşmaz, odak görünür kalır", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.emulateMedia({ colorScheme: "dark" });
    await signIn(page, BURAK);

    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: /Merhaba|Genel bakış/ })).toBeVisible();
    await expectMobileDarkAndFocused(
      page,
      page
        .getByRole("navigation", { name: "Mobil ana menü" })
        .getByRole("link", { name: "Genel bakış", exact: true }),
    );

    await page.goto("/profile");
    await expect(page.getByRole("heading", { name: "Profil", exact: true })).toBeVisible();
    await expectMobileDarkAndFocused(page, page.getByLabel("Ad soyad"));
  });

  test("mobil ve koyu temada admin taşmaz, odak görünür kalır", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.emulateMedia({ colorScheme: "dark" });
    await signIn(page, AYSE);

    await page.goto("/admin");
    await expect(page.getByRole("heading", { name: "Bilgi İşlem" })).toBeVisible();
    await expect(page.getByText(/Uygulama: (Hazır|Kısıtlı|Hata|Ulaşılamıyor)/))
      .toBeVisible();
    await expectMobileDarkAndFocused(page, page.getByLabel("Kullanıcı ara"));
  });
});
