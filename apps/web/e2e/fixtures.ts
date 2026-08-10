import { randomBytes } from "node:crypto";

export const E2E_COURSE_CODE_PREFIX = "E2E";
export const PROTECTED_COURSE_IDS = ["c3b76077-20de-47e5-9fe1-4e770ffa64d2"] as const;
export const PROTECTED_COURSE_CODES = ["COME 331"] as const;

const RUN_ID_PATTERN = /^[a-z0-9]{6,20}$/;
const COURSE_CODE_PATTERN = /^E2E-([a-z0-9]{6,20})-([0-9]+)$/;

let courseCounter = 0;

export function createE2eRunId(): string {
  return `${Date.now().toString(36)}${randomBytes(2).toString("hex")}`;
}

export function validateE2eRunId(value: string): string {
  const normalized = value.trim().toLowerCase();
  if (!RUN_ID_PATTERN.test(normalized)) {
    throw new Error(
      "E2E_RUN_ID yalnızca 6-20 küçük harf veya rakamdan oluşmalıdır.",
    );
  }
  return normalized;
}

export function requireE2eRunId(env: NodeJS.ProcessEnv = process.env): string {
  const value = env.E2E_RUN_ID;
  if (!value) {
    throw new Error(
      "E2E_RUN_ID yok. Testleri playwright.config.ts üzerinden çalıştırın.",
    );
  }
  return validateE2eRunId(value);
}

export function isRunScopedE2eCourseCode(code: string, runId?: string): boolean {
  const match = COURSE_CODE_PATTERN.exec(code);
  if (!match) return false;
  return runId === undefined || match[1] === validateE2eRunId(runId);
}

export function createE2eCourseIdentity(
  suffix: string,
  options: { runId?: string; processId?: number } = {},
): { code: string; title: string } {
  const runId = options.runId ?? requireE2eRunId();
  const processId = options.processId ?? process.pid;
  if (!Number.isInteger(processId) || processId <= 0) {
    throw new Error("E2E süreç kimliği pozitif bir tam sayı olmalıdır.");
  }

  const sequence = `${processId}${String(courseCounter++).padStart(3, "0")}`;
  const code = `${E2E_COURSE_CODE_PREFIX}-${validateE2eRunId(runId)}-${sequence}`;
  if (code.length > 32) {
    throw new Error(`E2E ders kodu 32 karakteri aşıyor: ${code}`);
  }

  const label = suffix.trim().replace(/\s+/g, " ").slice(0, 48) || "AKIS";
  return { code, title: `E2E Test Dersi ${label} (${runId})` };
}
