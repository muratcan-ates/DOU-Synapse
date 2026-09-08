/**
 * OPS1 overview: first test uses the actual authorized API response.
 * Degraded/legacy cases exercise UI response-contract rendering only: an actual
 * authorized overview response is fetched, then its dependency fields are changed.
 * Real SQL policy disagreement/recovery is tested in test_admin_readiness.py.
 */
import { expect, test, type Page } from "@playwright/test";

import type { AdminOverview } from "../lib/admin";
import { createE2eRequestId } from "./fixtures";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const ADMIN = {
  id: "11111111-1111-1111-1111-111111111111",
  email: "ayse@dogus.edu.tr",
  fullName: "Ayşe Hoca",
  role: "instructor" as const,
};

async function signIn(page: Page) {
  await page.setExtraHTTPHeaders({ "X-Request-ID": createE2eRequestId() });
  await page.addInitScript((user) => {
    localStorage.setItem("dou-synapse-token", `dev:${user.id}`);
    localStorage.setItem("dou-synapse-user", JSON.stringify(user));
  }, ADMIN);
}

function overviewResponse(page: Page) {
  return page.waitForResponse((response) =>
    response.url().startsWith(API) &&
    new URL(response.url()).pathname === "/admin/overview" &&
    response.request().method() === "GET",
  );
}

test("yönetim sağlığı gerçek API durumlarını ve başarılı sohbet örneklemini gösterir", async ({ page }) => {
  await signIn(page);
  const responsePromise = overviewResponse(page);
  await page.goto("/admin");
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const body = await response.json() as AdminOverview;
  expect(body.pgvector_status).toBe("ok");
  expect(body.request_quota_status).toBe("ok");

  const overview = page.locator('section[aria-labelledby="system-overview-title"]');
  await expect(overview.getByText("Vektör veritabanı: Hazır", { exact: true })).toBeVisible();
  await expect(overview.getByText("İstek kotası: Hazır", { exact: true })).toBeVisible();
  await expect(overview.getByText("Başarılı sohbet turu (Son 24 saat)", { exact: true })).toBeVisible();
  const p95 = overview.locator("dt").filter({ hasText: /^P95 gecikme/ });
  await expect(p95).toHaveText(
    `P95 gecikme (${body.chat_turns_24h.toLocaleString("tr-TR")} başarılı sohbet örneği)`,
  );
  await expect(p95.locator("..").locator("dd")).toHaveText(
    body.p95_latency_ms === null ? "-" : `${Math.round(body.p95_latency_ms)} ms`,
  );
  await expect(overview.getByText(/HTTP hata yanıtları ve kaydı oluşmayan istekler/)).toBeVisible();
});

for (const variant of ["degraded", "legacy"] as const) {
  test(`yönetim bağımlılık alanları ${variant} UI sözleşmesiyle dürüst görünür`, async ({ page }) => {
    await signIn(page);
    await page.route(`${API}/admin/overview`, async (route) => {
      const response = await route.fetch();
      expect(response.status()).toBe(200);
      const body = await response.json() as AdminOverview;
      if (variant === "degraded") {
        body.status = "degraded";
        body.request_quota_status = "error";
      } else {
        delete body.pgvector_status;
        delete body.request_quota_status;
      }
      await route.fulfill({ response, json: body });
    });
    await page.goto("/admin");
    const overview = page.locator('section[aria-labelledby="system-overview-title"]');
    if (variant === "degraded") {
      await expect(overview.getByText("Uygulama: Kısıtlı", { exact: true })).toBeVisible();
      await expect(overview.getByText("İstek kotası: Hata", { exact: true })).toBeVisible();
      await expect(overview.getByText("İstek kotası: Hazır", { exact: true })).toHaveCount(0);
    } else {
      await expect(overview.getByText("Vektör veritabanı: Ölçülemedi", { exact: true })).toBeVisible();
      await expect(overview.getByText("İstek kotası: Ölçülemedi", { exact: true })).toBeVisible();
    }
  });
}
