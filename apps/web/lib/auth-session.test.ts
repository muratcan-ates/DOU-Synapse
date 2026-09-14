import { describe, expect, test } from "bun:test";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { withAuthWriteLock } from "./auth-lock";
import { signOutWithLocalCleanup } from "./auth-session";

async function scenario(mode: string, lockModule?: string) {
  const child = Bun.spawn([process.execPath, new URL("./auth-provider-scenarios.ts", import.meta.url).pathname, mode], {
    cwd: new URL("..", import.meta.url).pathname,
    env: { ...process.env, NEXT_PUBLIC_DEV_AUTH: "true", NEXT_PUBLIC_SUPABASE_URL: "https://l5-auth.invalid", NEXT_PUBLIC_SUPABASE_ANON_KEY: "synthetic-public-anon-key", NEXT_PUBLIC_ENTRA_TENANT_ID: "11111111-1111-4111-8111-111111111111", ...(lockModule ? { L5_AUTH_LOCK_MODULE: lockModule } : {}) },
    stdout: "pipe", stderr: "pipe",
  });
  // Kilit regresyonu alt süreci sonsuza kadar açık bırakmamalı.
  const timeout = setTimeout(() => child.kill(), 30_000);
  try {
    const [exitCode, stdout, stderr] = await Promise.all([child.exited, new Response(child.stdout).text(), new Response(child.stderr).text()]);
    return { exitCode, output: stdout + stderr };
  } finally { clearTimeout(timeout); }
}

describe("oturum yazımı ve anlık temizlik", () => {
  test("yerel temizlik sağlayıcı yanıtını beklemez", async () => {
    let done!: () => void;
    const wait = new Promise<void>((resolve) => { done = resolve; });
    let cleared = false;
    const signingOut = signOutWithLocalCleanup(async () => { await wait; return { error: null }; }, () => { cleared = true; });
    expect(cleared).toBe(true);
    done(); await signingOut;
  });
  test("sekmeler arası kilit yoksa sağlayıcı yazımı çağrılmaz", async () => {
    let called = false;
    await expect(withAuthWriteLock(async () => { called = true; }, null)).rejects.toThrow("güvenli oturum açılamıyor");
    expect(called).toBe(false);
  });
  test("gerçek SDK sentetik taşıma: dev, parola, doğrulama, refresh, 401 ve 403", async () => {
    const result = await scenario("flows");
    expect(result.output).toContain("L5_AUTH_FLOWS_PASS");
    expect(result.exitCode).toBe(0);
  }, 35_000);
  test("canonical callback ilk SDK kurulumunu kilit içinde tamamlar", async () => {
    const result = await scenario("callback");
    expect(result.output).toContain("L5_AUTH_CALLBACK_PASS");
    expect(result.exitCode).toBe(0);
  }, 35_000);
  test("gerçek SDK bridge: pasif giriş çıkışı açamaz, gecikmiş çıkış yeni girişi silemez", async () => {
    const result = await scenario("bridge");
    expect(result.output).toContain("L5_AUTH_BRIDGE_PASS");
    expect(result.exitCode).toBe(0);
  }, 35_000);
  test("gerçek SDK iki istemci: geciken çıkış yeni girişi silemez", async () => {
    const result = await scenario("race");
    expect(result.output).toContain("L5_AUTH_RACE_PASS");
    expect(result.exitCode).toBe(0);
  }, 35_000);
  test("aynı yarış gerçek kilit satırı kaldırılınca kırmızı olur", async () => {
    const directory = mkdtempSync(join(tmpdir(), "l5-auth-lock-mutant-"));
    try {
      const original = readFileSync(new URL("./auth-lock.ts", import.meta.url), "utf8");
      const guard = "return locks.request(AUTH_WRITE_LOCK, write);";
      expect(original.split(guard)).toHaveLength(2);
      const mutated = join(directory, "auth-lock.ts");
      writeFileSync(mutated, original.replace(guard, "return write();"));
      const result = await scenario("race", mutated);
      expect(result.output).toContain("L5_AUTH_RACE_NEW_SESSION_PRESERVED");
      expect(result.exitCode).not.toBe(0);
    } finally { rmSync(directory, { recursive: true, force: true }); }
  }, 35_000);
});
