/** Modül keşfi yazmaz; Playwright çalışanı başlamadan kimlik çözülmez. */
import { test as base, expect, type Page } from "@playwright/test";
import { provisionWorkerProfiles, type WorkerUser, type WorkerUsers } from "./worker-profiles";

let activeUsers: WorkerUsers | undefined;
function currentUsers(): WorkerUsers {
  if (!activeUsers) throw new Error("Çalışan profili başlamadan E2E kimliği okunamaz.");
  return activeUsers;
}
function userReference(key: keyof WorkerUsers): WorkerUser {
  return {
    get id() { return currentUsers()[key].id; },
    get email() { return currentUsers()[key].email; },
    get fullName() { return currentUsers()[key].fullName; },
    get role() { return currentUsers()[key].role; },
  };
}
export const teacher = userReference("teacher");
export const student = userReference("student");
export const teacherHeaders = { get Authorization() { return `Bearer dev:${teacher.id}`; } };
export const studentHeaders = { get Authorization() { return `Bearer dev:${student.id}`; } };
export type { WorkerUser };
export const test = base.extend<object, { workerUsers: WorkerUsers }>({
  workerUsers: [async ({}, use, workerInfo) => {
    activeUsers = provisionWorkerProfiles(workerInfo.workerIndex);
    try { await use(activeUsers); } finally { activeUsers = undefined; }
    // Ders/audit temizliği global teardown'da tamamlanmadan profiller silinmez.
  }, { scope: "worker", auto: true }],
});

/**
 * Gerçek demo düğmesi auth olayını üretir. Yalnız tam eşleşen seed yazımı
 * bu çalışanın sentetik profiline çevrilir; olay/çıkış/sekme kodu değiştirilmez.
 * Her yüklemede oturum yazan init script çıkış testini bozacağı için kullanılmaz.
 */
export async function signIn(page: Page, reference: WorkerUser): Promise<void> {
  const user = { ...reference };
  if (page.url() === "about:blank") await page.goto("/");
  const alreadyActive = await page.evaluate((expected) => {
    const stored = localStorage.getItem("dou-synapse-user");
    if (!stored) return false;
    try {
      return JSON.parse(stored).id === expected.id &&
        localStorage.getItem("dou-synapse-token") === `dev:${expected.id}` &&
        !localStorage.getItem("dou-synapse:auth-event:v1")?.startsWith("signed-out:");
    } catch { return false; }
  }, user);
  // Aynı kullanıcı için gereksiz identity-changed başka sekmenin taslağını siler.
  if (alreadyActive) return;
  if (new URL(page.url()).pathname !== "/") await page.goto("/");
  const seed = user.role === "instructor"
    ? { id: "11111111-1111-1111-1111-111111111111", email: "ayse@dogus.edu.tr", fullName: "Ayşe Hoca", role: "instructor" }
    : { id: "22222222-2222-2222-2222-222222222222", email: "burak@dogus.edu.tr", fullName: "Burak Yılmaz", role: "student" };
  await page.evaluate(({ seed, user }) => {
    const browser = window as Window & { __restoreE2eStorage?: () => void };
    if (browser.__restoreE2eStorage) throw new Error("Oturum adaptörü zaten etkin.");
    const original = Storage.prototype.setItem;
    browser.__restoreE2eStorage = () => { Storage.prototype.setItem = original; delete browser.__restoreE2eStorage; };
    Storage.prototype.setItem = function (key: string, value: string) {
      if (this === localStorage) {
        if (key === "dou-synapse-token" && value === `dev:${seed.id}`) value = `dev:${user.id}`;
        if (key === "dou-synapse-user") {
          try {
            const payload = JSON.parse(value);
            if (payload.id === seed.id && payload.email === seed.email &&
                payload.fullName === seed.fullName && payload.role === seed.role &&
                Object.keys(payload).length === 4) value = JSON.stringify(user);
          } catch { /* Bozuk depolama senaryosunun davranışı korunur. */ }
        }
      }
      return original.call(this, key, value);
    };
  }, { seed, user });
  try {
    await page.getByRole("button", { name: user.role === "instructor" ? /Ayşe Hoca/ : /Burak Yılmaz/ }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("dou-synapse-user")!).id)).toBe(user.id);
  } finally {
    await page.evaluate(() => {
      (window as Window & { __restoreE2eStorage?: () => void }).__restoreE2eStorage?.();
    });
  }
}
