import { randomBytes } from "node:crypto";
import { appendFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";

import type { Page, Request } from "@playwright/test";

export const E2E_COURSE_CODE_PREFIX = "E2E";
export const PROTECTED_COURSE_IDS = [
  "c3b76077-20de-47e5-9fe1-4e770ffa64d2",
] as const;
export const PROTECTED_COURSE_CODES = ["COME 331"] as const;

const RUN_ID_PATTERN = /^[a-z0-9]{6,20}$/;
const COURSE_CODE_PATTERN = /^E2E-([a-z0-9]{6,20})-([0-9]+)$/;

let courseCounter = 0;
const SERVER_REQUEST_ID_PATTERN = /^[a-f0-9]{32}$/;
const REQUEST_ID_FAILURE_MARKER = "server-request-id-validation-failed\n";
const auditRecorderPages = new WeakSet<Page>();
type Environment = Readonly<Record<string, string | undefined>>;
type E2eFetch = (input: string | URL, init?: RequestInit) => Promise<Response>;

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

export function requireE2eRunId(env: Environment = process.env): string {
  const value = env.E2E_RUN_ID;
  if (!value) {
    throw new Error(
      "E2E_RUN_ID yok. Testleri playwright.config.ts üzerinden çalıştırın.",
    );
  }
  return validateE2eRunId(value);
}

export function isRunScopedE2eCourseCode(
  code: string,
  runId?: string,
): boolean {
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

export function e2eRequestManifestPath(
  runId = requireE2eRunId(),
  env: Environment = process.env,
): string {
  const directory = env.E2E_ARTIFACT_DIR ?? join(process.cwd(), "test-results");
  return join(directory, `request-ids-${validateE2eRunId(runId)}.txt`);
}

export function e2eRequestIdFailureMarkerPath(
  runId = requireE2eRunId(),
  env: Environment = process.env,
): string {
  const directory = env.E2E_ARTIFACT_DIR ?? join(process.cwd(), "test-results");
  return join(directory, `request-id-errors-${validateE2eRunId(runId)}.txt`);
}

export function validateE2eServerRequestId(
  requestId: string | null | undefined,
): string {
  if (!requestId || !SERVER_REQUEST_ID_PATTERN.test(requestId)) {
    throw new Error(
      "API yanıtı geçerli bir sunucu X-Request-ID değeri taşımıyor.",
    );
  }
  return requestId;
}

function apiOrigin(env: Environment): string {
  const configured = env.E2E_API_URL ?? "http://localhost:8000";
  let parsed: URL;
  try {
    parsed = new URL(configured);
  } catch {
    throw new Error("E2E_API_URL geçerli bir HTTP(S) adresi olmalıdır.");
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("E2E_API_URL geçerli bir HTTP(S) adresi olmalıdır.");
  }
  return parsed.origin;
}

function persistRequestIdFailure(runId: string, env: Environment): void {
  const marker = e2eRequestIdFailureMarkerPath(runId, env);
  mkdirSync(dirname(marker), { recursive: true });
  // Marker bilinçli olarak URL, path, header veya yanıt gövdesi taşımaz.
  // Teardown yalnız bu sabit kanıtın varlığıyla fail-closed davranır.
  appendFileSync(marker, REQUEST_ID_FAILURE_MARKER, {
    encoding: "utf8",
    flag: "a",
  });
}

export function assertE2eRequestIdRecorderHealthy(
  runId = requireE2eRunId(),
  env: Environment = process.env,
): void {
  if (existsSync(e2eRequestIdFailureMarkerPath(runId, env))) {
    throw new Error(
      "Bir API yanıtında geçersiz sunucu X-Request-ID görüldü; manifest korunarak E2E temizliği durduruldu.",
    );
  }
}

export function recordE2eServerRequestId(
  requestId: string | null | undefined,
  options: { runId?: string; env?: Environment } = {},
): string {
  const env = options.env ?? process.env;
  let validatedRequestId: string;
  try {
    validatedRequestId = validateE2eServerRequestId(requestId);
  } catch (error) {
    // Node-side fetch yardımcıları bu fonksiyonu doğrudan çağırır. Geçersiz
    // header manifest dışında kalabilecek bir olay/audit anlamına geldiği için
    // aktif koşu biliniyorsa hata fırlatılmadan önce kalıcı kapıyı kapatırız.
    const candidateRunId = options.runId ?? env.E2E_RUN_ID;
    if (candidateRunId) {
      persistRequestIdFailure(validateE2eRunId(candidateRunId), env);
    }
    throw error;
  }
  const runId = validateE2eRunId(options.runId ?? requireE2eRunId(env));
  const manifest = e2eRequestManifestPath(runId, env);
  mkdirSync(dirname(manifest), { recursive: true });
  // O_APPEND ile küçük tek satır yazımı paralel Playwright worker'larında
  // koşu manifestini güvenle paylaşır. DB'ye test etiketi taşınmaz.
  appendFileSync(manifest, `${validatedRequestId}\n`, {
    encoding: "utf8",
    flag: "a",
  });
  return validatedRequestId;
}

export function recordE2eApiResponseRequestId(
  response: {
    url: string;
    method: string;
    requestId: string | null | undefined;
  },
  options: { runId?: string; env?: Environment } = {},
): boolean {
  const env = options.env ?? process.env;
  const runId = validateE2eRunId(options.runId ?? requireE2eRunId(env));
  let responseOrigin: string;
  try {
    responseOrigin = new URL(response.url).origin;
  } catch {
    persistRequestIdFailure(runId, env);
    throw new Error("Tarayıcı geçersiz bir yanıt adresi bildirdi.");
  }
  if (responseOrigin !== apiOrigin(env)) return false;
  if (response.method.toUpperCase() === "OPTIONS") return false;

  recordE2eServerRequestId(response.requestId, { runId, env });
  return true;
}

export function recordE2eApiRequestFailure(
  request: { url: string; method: string },
  options: { runId?: string; env?: Environment } = {},
): boolean {
  const env = options.env ?? process.env;
  const runId = validateE2eRunId(options.runId ?? requireE2eRunId(env));
  let requestOrigin: string;
  try {
    requestOrigin = new URL(request.url).origin;
  } catch {
    persistRequestIdFailure(runId, env);
    throw new Error("Tarayıcı geçersiz bir istek adresi bildirdi.");
  }
  if (requestOrigin !== apiOrigin(env)) return false;
  if (request.method.toUpperCase() === "OPTIONS") return false;

  // Yanıt gelmediyse sunucunun isteği işleyip işlemediği bilinemez. Bu istek
  // sonradan kalıcılaşabileceğinden request-id manifestsiz temizlik yapılamaz.
  persistRequestIdFailure(runId, env);
  throw new Error(
    "Bir API isteği sunucu yanıtı alınmadan başarısız oldu; E2E temizliği fail-closed durdurulacak.",
  );
}

export async function fetchE2eApi(
  input: string | URL,
  init?: RequestInit,
  options: {
    runId?: string;
    env?: Environment;
    fetcher?: E2eFetch;
  } = {},
): Promise<Response> {
  const url = input.toString();
  const method = init?.method ?? "GET";
  try {
    return await (options.fetcher ?? globalThis.fetch)(input, init);
  } catch (error) {
    // Node fetch header almadan düşerse sunucu isteği işlemiş ve event'i
    // kuyruğa koymuş olabilir. URL/gövdeyi marker'a taşımadan cleanup'ı kapat;
    // API dışı bir fetch ise asıl ağ hatasını olduğu gibi koru.
    if (
      recordE2eApiRequestFailure(
        { url, method },
        { runId: options.runId, env: options.env },
      ) === false
    ) {
      throw error;
    }
    throw error;
  }
}

export function recordE2eApiResponses(
  page: Page,
  options: { runId?: string; env?: Environment } = {},
): void {
  if (auditRecorderPages.has(page)) return;
  // Geçersiz yapılandırmayı test ortasında değil, listener kurulurken düşür.
  apiOrigin(options.env ?? process.env);
  auditRecorderPages.add(page);
  const responsesSeen = new WeakSet<Request>();
  page.on("response", (response) => {
    const request = response.request();
    const recorded = recordE2eApiResponseRequestId(
      {
        url: response.url(),
        method: request.method(),
        requestId: response.headers()["x-request-id"],
      },
      options,
    );
    if (recorded) responsesSeen.add(request);
  });
  page.on("requestfailed", (request) => {
    // Chromium gövdesiz 204 yanıtını teslim ettikten sonra aynı fetch için
    // `net::ERR_ABORTED` olayı da yayabiliyor. Geçerli sunucu kimliğiyle response
    // zaten görüldüyse bu ağ kaybı değildir; aksi durumda fail-closed marker
    // korunur.
    if (responsesSeen.has(request)) return;
    recordE2eApiRequestFailure(
      { url: request.url(), method: request.method() },
      options,
    );
  });
}
