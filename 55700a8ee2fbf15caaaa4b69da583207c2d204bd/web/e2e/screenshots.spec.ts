/**
 * Belgelerdeki ekran görüntülerini ÜRETEN betik (`docs/images/`).
 *
 * Neden test paketinin içinde: ekran görüntüsü almak, ekranı gerçekten çalıştırıp
 * gezinmek demektir ve o iş için elimizde zaten çalışan bir tarayıcı sürücüsü var.
 * Elle alınan görüntüler bir sonraki arayüz değişikliğinde sessizce bayatlar;
 * bu dosya sayesinde `--grep @ekran` ile hepsi tek komutta tazelenir.
 *
 * NORMAL KOŞUDA ATLANIR (`@ekran` etiketi). Bir doğrulama değil, bir üretim
 * aracıdır: hiçbir şey iddia etmez, dolayısıyla CI'da koşması da anlamsız olurdu.
 *
 * Koşturma (API :8010 ve web :3010 ayakta olmalı):
 *
 *     cd apps/web
 *     E2E_API_URL=http://localhost:8010 \
 *       node_modules/.bin/playwright test screenshots --grep @ekran
 *
 * `bunx playwright` KULLANMAYIN — ayrı bir kopya indirip "two different versions"
 * hatası verir.
 */

import { expect, test, type Page } from "@playwright/test";

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

/** Materyali gerçekten işlenmiş ders (COME 331). */
const DERS = "c3b76077-20de-47e5-9fe1-4e770ffa64d2";

const KLASOR = "../../docs/images";

async function girisYap(page: Page, user: typeof AYSE | typeof BURAK) {
  await page.addInitScript(
    ([token, payload]) => {
      localStorage.setItem("dou-synapse-token", token as string);
      localStorage.setItem("dou-synapse-user", payload as string);
    },
    [`dev:${user.id}`, JSON.stringify(user)],
  );
}

/** Girdiye yazıp gönderir ve cevabın gelmesini bekler. */
async function sor(page: Page, soru: string) {
  await page.getByLabel("Sorun").fill(soru);
  await page.getByRole("button", { name: "Gönder" }).click();
  // Cevabın KENDİSİNİ bekle. İlk yazımda "Gönder yeniden etkinleşir" bekleniyordu
  // ve hiç gerçekleşmedi: cevap gelince girdi temizleniyor, boş girdide düğme
  // zaten devre dışı kalıyor. Yanlış şeyi bekleyen bir bekleme, beklememekten
  // kötü — zaman aşımına kadar sessizce oyalıyor.
  await expect(page.getByText("Gönderiliyor…")).toHaveCount(0, { timeout: 180_000 });
}

async function cek(page: Page, ad: string) {
  // "Yükleniyor…" hâlinde çekilen bir görüntü, ürünü boş gösterir ve belgede
  // yıllarca öyle kalır. Bir kez bu tuzağa düşüldü (03-egitmen-materyaller,
  // 12 KB'lık boş sayfa), o yüzden bekleme burada ZORUNLU.
  await expect(page.getByText("Yükleniyor…")).toHaveCount(0, { timeout: 60_000 });
  await page.waitForTimeout(500); // giriş animasyonu otursun
  await page.screenshot({ path: `${KLASOR}/${ad}.png`, fullPage: true });
}

test.describe("belge ekran görüntüleri @ekran", () => {
  // Görüntüler belgelerde yan yana duruyor; aynı genişlik olmazsa sayfa dağınık görünür.
  test.use({ viewport: { width: 1280, height: 900 } });

  test("sohbet — kaynaklı cevap ve önbellek işareti", async ({ page }) => {
    await girisYap(page, BURAK);
    await page.goto(`/courses/${DERS}/chat`);
    await sor(page, "Context switch neden maliyetlidir?");

    await expect(page.getByText("Sayfa", { exact: false }).first()).toBeVisible();
    await cek(page, "09-sohbet-kaynakli-cevap");
  });

  test("sohbet — kapsam dışı soruda nazik ret", async ({ page }) => {
    await girisYap(page, BURAK);
    await page.goto(`/courses/${DERS}/chat`);
    await sor(page, "Fransız İhtilali kaç yılında oldu?");

    // Ret hata gibi GÖRÜNMEMELİ: bu görüntünün belgede anlatılan şeyi tam olarak bu.
    await expect(page.getByRole("main").locator('[role="alert"]')).toHaveCount(0);
    await cek(page, "10-sohbet-nazik-ret");
  });

  test("soru havuzu — üretim raporu ve elenme gerekçeleri", async ({ page }) => {
    await girisYap(page, AYSE);
    await page.goto(`/courses/${DERS}/questions`);
    await expect(page.getByRole("heading", { name: "Soru havuzu" })).toBeVisible();
    await cek(page, "05-egitmen-soru-havuzu");
  });

  test("ilerleme — sınıf analitiği", async ({ page }) => {
    await girisYap(page, AYSE);
    await page.goto(`/courses/${DERS}/analytics`);
    await expect(page.getByText("resmî bir not değildir", { exact: false })).toBeVisible();
    await cek(page, "06-egitmen-sinif-analitigi");
  });

  test("ilerleme — öğrenci görünümü", async ({ page }) => {
    await girisYap(page, BURAK);
    await page.goto(`/courses/${DERS}/analytics`);
    await cek(page, "15-ogrenci-ilerleme");
  });

  test("materyaller — eğitmen görünümü", async ({ page }) => {
    await girisYap(page, AYSE);
    await page.goto(`/courses/${DERS}`);
    await cek(page, "03-egitmen-materyaller");
  });

  test("KVKK aydınlatma metni", async ({ page }) => {
    await page.goto("/kvkk");
    await expect(page.getByRole("heading", { name: "KVKK Aydınlatma Metni" })).toBeVisible();
    await cek(page, "16-kvkk");
  });
});
