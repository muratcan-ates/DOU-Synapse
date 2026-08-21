import { spawnSync } from "node:child_process";

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "::1"]);
export const E2E_COURSE_PREFIX = "E2E";

/**
 * E2E temizliğini özellikle dar tutar. Önek kullanıcı girdisi değildir ve SQL'e
 * yalnız bu sabit değer girebilir; yanlışlıkla normal dersleri hedefleyen bir
 * değişiklik test başlamadan kırmızı yanar.
 */
export function cleanupSql(prefix: string): string {
  if (prefix !== E2E_COURSE_PREFIX) {
    throw new Error(`Güvensiz E2E temizlik öneki reddedildi: ${prefix}`);
  }
  return [
    "BEGIN;",
    `DELETE FROM courses WHERE code LIKE '${E2E_COURSE_PREFIX}%'`,
    "  AND title LIKE 'E2E Test Dersi%';",
    "COMMIT;",
  ].join("\n");
}

export function assertLocalCleanupTarget(apiUrl: string, environment?: string): void {
  if (environment?.toLowerCase() === "production") {
    throw new Error("E2E temizliği production ortamında çalıştırılamaz.");
  }
  const hostname = new URL(apiUrl).hostname;
  if (!LOCAL_HOSTS.has(hostname)) {
    throw new Error(`E2E temizliği yalnız yerel API için çalışır; hedef: ${hostname}`);
  }
}

export default function globalTeardown(): void {
  const apiUrl = process.env.E2E_API_URL ?? "http://localhost:8000";
  assertLocalCleanupTarget(apiUrl, process.env.ENVIRONMENT);

  if (process.env.E2E_KEEP_DATA === "true") {
    console.info("E2E_KEEP_DATA=true: test dersleri inceleme için korundu.");
    return;
  }

  const databaseName = process.env.E2E_DATABASE_NAME ?? "dou_synapse";
  const result = spawnSync(
    "psql",
    ["-X", "-v", "ON_ERROR_STOP=1", "-d", databaseName, "-c", cleanupSql(E2E_COURSE_PREFIX)],
    { encoding: "utf8", env: process.env },
  );

  if (result.error) {
    throw new Error(`E2E temizliği başlatılamadı: ${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new Error(`E2E temizliği başarısız: ${result.stderr || result.stdout}`);
  }
  console.info(result.stdout.trim() || "E2E test dersleri temizlendi.");
}
