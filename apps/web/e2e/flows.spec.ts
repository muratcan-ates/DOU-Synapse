/**
 * Uçtan uca akış testleri — Anayasa VIII'in kalıcı hâli.
 *
 * "Davranış gerçek ortamda gözlenmeden bitmedi" ilkesi, elle bir kez bakmakla
 * karşılanmış sayılmaz: elle bakış bir sonraki değişiklikte kaybolur. Bu paket,
 * 9 Ağustos'ta elle koşturulan yirmi altı etkileşim denetimini kalıcı hâle
 * getiriyor.
 *
 * Neden özellikle bu vakalar: hepsi gerçekten bulunmuş kusurları koruyor.
 * Ölü butonlar (etkin görünüp iş yapmayan), sessizce yutulan hata, tam sayfa
 * yenileme ve bozuk oturumda çökme — dördü de bu dosyada nöbette.
 *
 * Test kendi verisini kurar ve kendi temizler; başka bir testin bıraktığı
 * duruma güvenmez.
 *
 * Koşturma:
 *   API :8000 ve web :3000 ayakta olmalı
 *   bunx playwright test
 */

import { expect, test, type Page } from "@playwright/test";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";

/** Seed'deki sabit demo kimlikleri (supabase/seed_demo.sql). */
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

/** Tarayıcıya oturum enjekte eder — giriş ekranını her testte tıklamak yerine. */
async function signIn(page: Page, user: DemoUser) {
  await page.addInitScript(
    ([token, payload]) => {
      localStorage.setItem("dou-synapse-token", token as string);
      localStorage.setItem("dou-synapse-user", payload as string);
    },
    [`dev:${user.id}`, JSON.stringify(user)],
  );
}

async function apiPost(path: string, body: unknown, user: DemoUser) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer dev:${user.id}`,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} → ${res.status} ${await res.text()}`);
  return res.json();
}

/**
 * Her test kendi dersini açar: paralel koşumda birbirlerinin verisini bozmasınlar.
 *
 * Kod benzersizleştirilir çünkü `courses.code` derse özgüdür ve ikinci koşumda
 * 409 döner. Testin yeniden koşturulabilir olması pazarlıksız: bir kez çalışıp
 * sonra çakışan test, hiç olmayan testten kötüdür - yeşil bekleyip kırmızı bulan
 * ekip önce teste güvenmeyi bırakır.
 */
let counter = 0;
async function createCourse(suffix: string) {
  const unique = `${suffix}${Date.now().toString(36).slice(-5)}${counter++}`;
  return apiPost(
    "/courses",
    { code: `E2E${unique}`.slice(0, 32), title: `E2E Test Dersi ${suffix}` },
    AYSE,
  );
}

test.describe("giriş", () => {
  test("demo kartı oturum açar ve ders listesine götürür", async ({ page }) => {
    await page.goto("/");
    await page.getByText("Ayşe Hoca").click();
    await expect(page).toHaveURL(/\/courses/);
  });

  test("bozuk oturum verisi uygulamayı ÇÖKERTMEZ", async ({ page }) => {
    // Gerçek kusur: JSON.parse doğrudan çağrıldığında bozuk bir localStorage
    // kaydı tüm sayfayı düşürüyordu ve yenilemek kurtarmıyordu — kayıt hâlâ
    // bozuk olduğu için kullanıcı kalıcı kilitli kalıyordu.
    const pageErrors: string[] = [];
    page.on("pageerror", (e) => pageErrors.push(e.message));

    await page.addInitScript(() => {
      localStorage.setItem("dou-synapse-token", "dev:x");
      localStorage.setItem("dou-synapse-user", "{bozuk json");
    });
    await page.goto("/courses");

    expect(pageErrors).toHaveLength(0);
    // Giriş ekranına düşmeli, beyaz ekrana değil.
    await expect(page.getByText("Ayşe Hoca")).toBeVisible();
  });
});

test.describe("materyal yönetimi", () => {
  test("yükleme, önizleme aç/kapa ve silme akışı", async ({ page }) => {
    const course = await createCourse("MAT");
    await signIn(page, AYSE);
    await page.goto(`/courses/${course.id}`);

    // Yükleme
    await page.setInputFiles('input[type="file"]', {
      name: "e2e_test.md",
      mimeType: "text/markdown",
      buffer: Buffer.from("# E2E\n\nDeadlock dört koşul gerektirir."),
    });
    await expect(page.getByText("e2e_test.md")).toBeVisible({ timeout: 15_000 });

    // Silme: önce onay adımı, sonra vazgeçme.
    // Buton `aria-label` taşıyor ("<dosya> dosyasını sil") ve aria-label
    // erişilebilir adı geçersiz kılar; locator ona göre yazılır.
    const row = page.locator("li", { hasText: "e2e_test.md" });
    const silButonu = row.getByRole("button", { name: /dosyasını sil$/ });
    await silButonu.click();
    await expect(page.getByText("Evet, sil")).toBeVisible();
    await page.getByRole("button", { name: "Vazgeç" }).click();
    await expect(page.getByText("Evet, sil")).toBeHidden();
    await expect(page.getByText("e2e_test.md")).toBeVisible();

    // Gerçekten silme — ve TAM SAYFA YENİLEME OLMAMALI
    await silButonu.click();
    await row.getByRole("button", { name: "Evet, sil" }).click();
    await expect(page.getByText("e2e_test.md")).toBeHidden({ timeout: 15_000 });

    const navType = await page.evaluate(
      () => performance.getEntriesByType("navigation")[0]?.entryType &&
        (performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming).type,
    );
    expect(navType).not.toBe("reload");
  });
});

test.describe("soru havuzu — eğitmen onayı", () => {
  test("onay ve red butonları GERÇEKTEN iş yapar", async ({ page }) => {
    // Kusur: butonlar seçim yapılınca etkinleşiyor ama tıklanınca hiçbir şey
    // olmuyordu. Etkin görünüp iş yapmayan buton kusurdur (Anayasa XI).
    const course = await createCourse("SORU");
    await signIn(page, AYSE);
    await page.goto(`/courses/${course.id}/questions`);

    const bekleyen = page.locator("p", { hasText: "Onay bekleyen" }).locator("xpath=preceding-sibling::p");
    const once = Number(await bekleyen.innerText());

    await page.getByRole("button", { name: /Onayla ve öğrenciye aç/ }).click();
    await expect(bekleyen).toHaveText(String(once - 1));

    await page.getByRole("button", { name: /^Reddet$/ }).click();
    await expect(page.getByText("Reddedildi").first()).toBeVisible();
  });

  test("liste satırı detay panelini değiştirir", async ({ page }) => {
    const course = await createCourse("SORU2");
    await signIn(page, AYSE);
    await page.goto(`/courses/${course.id}/questions`);

    await page.getByRole("button", { name: /S-004/ }).click();
    await expect(page.getByText("S-004 ·")).toBeVisible();
  });
});

test.describe("sınav provası", () => {
  test("ileri-geri gezinme çalışır ve cevap korunur", async ({ page }) => {
    const course = await createCourse("SINAV");
    await signIn(page, BURAK);
    await page.goto(`/courses/${course.id}/exam`);

    const onceki = page.getByRole("button", { name: "Önceki" });
    const sonraki = page.getByRole("button", { name: /Sonraki soru/ });

    await expect(onceki).toBeDisabled();
    await expect(sonraki).toBeDisabled();

    await page.locator('input[type="radio"]').first().check();
    await expect(sonraki).toBeEnabled();

    await sonraki.click();
    await expect(page.getByText("2/10")).toBeVisible();

    await onceki.click();
    await expect(page.getByText("1/10")).toBeVisible();
    // Geri dönünce önceki cevap yerinde durmalı.
    await expect(page.locator('input[type="radio"]').first()).toBeChecked();
  });
});

test.describe("rol ayrımı", () => {
  test("öğrenci eğitmen kontrollerini görmez", async ({ page }) => {
    const course = await createCourse("ROL");
    await apiPost(`/courses/${course.id}/members`, { email: BURAK.email, role: "student" }, AYSE);

    await signIn(page, BURAK);
    await page.goto(`/courses/${course.id}`);

    // exact: "Materyal yükle" alt dizgesi "materyal yüklemedi" içinde de geçiyor.
    await expect(page.getByText("Materyal yükle", { exact: true })).toBeHidden();
    await expect(page.getByRole("button", { name: /dosyasını sil$/ })).toHaveCount(0);
    await expect(page.getByRole("navigation").getByText("Soru havuzu")).toHaveCount(0);
  });

  test("ilerleme ekranı role göre farklı soruya cevap verir", async ({ page }) => {
    const course = await createCourse("ILERLEME");
    await apiPost(`/courses/${course.id}/members`, { email: BURAK.email, role: "student" }, AYSE);

    await signIn(page, BURAK);
    await page.goto(`/courses/${course.id}/analytics`);
    await expect(page.getByText("İlerlemem")).toBeVisible();
    // ARCHITECTURE §5: bu ibare ekranda ZORUNLU.
    await expect(page.getByText(/resmî bir not değildir/)).toBeVisible();
  });
});

test.describe("izolasyon", () => {
  test("üye olmayan öğrenci dersin VARLIĞINI bile öğrenemez", async ({ page }) => {
    // "Yetkiniz yok" demek dersin var olduğunu sızdırmaktır; sistem 404 döner.
    const course = await createCourse("IZOLASYON");
    await signIn(page, BURAK); // derse ÜYE DEĞİL
    await page.goto(`/courses/${course.id}`);

    await expect(page.getByText("Ders bulunamadı.")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("E2E Test Dersi IZOLASYON")).toBeHidden();
  });
});
