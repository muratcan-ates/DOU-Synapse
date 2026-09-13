import { afterEach, describe, expect, test } from "bun:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { AppRouterContext, type AppRouterInstance } from "next/dist/shared/lib/app-router-context.shared-runtime";
import LoginPage from "../app/page";

const previousDev = process.env.NEXT_PUBLIC_DEV_AUTH;
const previousTenant = process.env.NEXT_PUBLIC_ENTRA_TENANT_ID;
const router: AppRouterInstance = { back() {}, forward() {}, refresh() {}, push() {}, replace() {}, prefetch() {}, bfcacheId: "synthetic-login" };
const render = () => renderToStaticMarkup(createElement(AppRouterContext.Provider, { value: router }, createElement(LoginPage)));
afterEach(() => {
  if (previousDev === undefined) delete process.env.NEXT_PUBLIC_DEV_AUTH; else process.env.NEXT_PUBLIC_DEV_AUTH = previousDev;
  if (previousTenant === undefined) delete process.env.NEXT_PUBLIC_ENTRA_TENANT_ID; else process.env.NEXT_PUBLIC_ENTRA_TENANT_ID = previousTenant;
});

describe("giriş ekranının görünür seçenekleri", () => {
  test("geliştirme kimlikleri yalnız açık bayrakta görünür", () => {
    process.env.NEXT_PUBLIC_DEV_AUTH = "false";
    expect(render()).not.toContain("Ayşe Hoca");
    expect(render()).not.toContain("Burak Yılmaz");
    process.env.NEXT_PUBLIC_DEV_AUTH = "true";
    expect(render()).toContain("Ayşe Hoca");
    expect(render()).toContain("Burak Yılmaz");
  });
  test("tenant eksikken üniversite girişi kapalı ve durumu görünürdür", () => {
    delete process.env.NEXT_PUBLIC_ENTRA_TENANT_ID;
    const html = render();
    expect(html).toContain("Üniversite hesabıyla giriş henüz etkin değil.");
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>Üniversite hesabıyla devam et<\/button>/);
  });
});
