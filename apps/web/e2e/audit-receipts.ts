/** Sunucunun yanıt kimliği yalnız test koşusunun özel sahiplik makbuzuna girer. */
import { randomUUID } from "node:crypto";
import {
  lstatSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, renameSync, writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { isAbsolute, join } from "node:path";

import { validateE2eRunId } from "./fixtures";

export const AUDIT_ACTIONS = new Set([
  "GET /admin/overview", "POST /admin/users", "GET /admin/courses",
  "GET /admin/requests", "GET /admin/ingestion", "GET /openapi.json",
]);
const ACTORS = new Set([
  "11111111-1111-1111-1111-111111111111",
  "22222222-2222-2222-2222-222222222222",
]);
const SUPPORT_ID = /^[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}$/;

export interface AuditReceipt {
  requestId: string;
  actorId: string;
  action: string;
  result: "allowed" | "denied";
}
export interface AuditScope {
  version: 1;
  runId: string;
  databaseName: string;
  apiOrigin: string;
  targetId: string;
}
export interface AuditObservation {
  url: string;
  method: string;
  authorization?: string;
  status: number;
  requestId?: string | null;
}

export function auditOrigin(value: string): string {
  const parsed = new URL(value);
  if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password ||
      parsed.search || parsed.hash || parsed.pathname !== "/") {
    throw new Error("E2E audit API adresi yalın HTTP(S) origin olmalıdır.");
  }
  return parsed.origin;
}

export function expectedAuditScope(
  runId: string, databaseName: string, env: Readonly<Record<string, string | undefined>> = process.env,
): AuditScope {
  const targetId = env.E2E_AUDIT_TARGET_ID ?? "";
  if (!/^[0-9a-f]{64}$/.test(targetId)) {
    throw new Error("Root tarafından doğrulanmış E2E_AUDIT_TARGET_ID zorunludur.");
  }
  return {
    version: 1, runId: validateE2eRunId(runId), databaseName,
    apiOrigin: auditOrigin(env.E2E_API_URL ?? "http://localhost:8000"), targetId,
  };
}

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Audit makbuzu nesne olmalıdır.");
  }
  return value as Record<string, unknown>;
}
function exactKeys(value: Record<string, unknown>, keys: string[]) {
  if (Object.keys(value).sort().join("|") !== keys.sort().join("|")) {
    throw new Error("Audit makbuzu alan kümesi geçersiz.");
  }
}
export function validateReceipt(value: unknown): AuditReceipt {
  const row = object(value);
  exactKeys(row, ["requestId", "actorId", "action", "result"]);
  if (typeof row.requestId !== "string" || !SUPPORT_ID.test(row.requestId) ||
      typeof row.actorId !== "string" || !ACTORS.has(row.actorId) ||
      typeof row.action !== "string" || !AUDIT_ACTIONS.has(row.action) ||
      (row.result !== "allowed" && row.result !== "denied")) {
    throw new Error("Audit makbuzu izinli sentetik sahiplik sınırları dışında.");
  }
  return row as unknown as AuditReceipt;
}
export function receiptKey(receipt: AuditReceipt): string {
  const row = validateReceipt(receipt);
  return [row.requestId, row.actorId, row.action, row.result].join("|");
}

/** Başlık yalnız sentetik aktörü seçmek için bellekte okunur; saklanmaz. */
export function isAuditedRequest(
  url: string, method: string, authorization: string | undefined, origin: string,
): boolean {
  const parsed = new URL(url);
  if (parsed.origin !== origin || !AUDIT_ACTIONS.has(`${method.toUpperCase()} ${parsed.pathname}`)) return false;
  const actor = authorization?.match(/^Bearer dev:([0-9a-f-]{36})$/)?.[1];
  if (!actor || !ACTORS.has(actor)) {
    throw new Error("Audit toplayıcı yalnız bilinen sentetik aktörleri izler.");
  }
  return true;
}

export function receiptFromResponse(
  observation: AuditObservation, origin: string,
): AuditReceipt | null {
  const { url, method, authorization, status, requestId } = observation;
  if (!isAuditedRequest(url, method, authorization, origin)) return null;
  // Bu testlerin gerçek kapı yanıtları 200/403'tür. Bilinmeyen durumun audit
  // commit edildiğini veya edilmediğini tahmin edip temizlik yetkisi üretmeyiz.
  if (status !== 200 && status !== 403) {
    throw new Error("Audit yanıtının commit sahipliği bu testte belirlenemedi.");
  }
  return validateReceipt({
    requestId, actorId: authorization!.slice("Bearer dev:".length),
    action: `${method.toUpperCase()} ${new URL(url).pathname}`,
    result: status === 403 ? "denied" : "allowed",
  });
}

function privateDirectory(path: string) {
  const stat = lstatSync(path);
  if (!isAbsolute(path) || !stat.isDirectory() || stat.isSymbolicLink() ||
      (stat.mode & 0o077) !== 0) throw new Error("Audit dizini özel bir yerel dizin olmalıdır.");
}
function readBounded(path: string): unknown {
  const stat = lstatSync(path);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 4096 ||
      (stat.mode & 0o077) !== 0) throw new Error("Audit dosyası sınırı ihlal edildi.");
  return JSON.parse(readFileSync(path, "utf8")) as unknown;
}
function writePrivate(path: string, value: unknown) {
  const temporary = `${path}.${randomUUID()}.pending`;
  writeFileSync(temporary, `${JSON.stringify(value)}\n`, { flag: "wx", mode: 0o600 });
  renameSync(temporary, path);
}
export function initializeAuditCapture(scope: AuditScope): string {
  const directory = mkdtempSync(join(tmpdir(), "dou-e2e-audit-"));
  // mkdtemp POSIX'te 0700 oluşturur; değişmiş umask/izin varsayımını ayrıca ölç.
  privateDirectory(directory);
  mkdirSync(join(directory, "receipts"), { mode: 0o700 });
  mkdirSync(join(directory, "sessions"), { mode: 0o700 });
  writePrivate(join(directory, "scope.json"), scope);
  return directory;
}
export function validateAuditDirectory(directory: string, expected: AuditScope) {
  privateDirectory(directory);
  const scope = object(readBounded(join(directory, "scope.json")));
  exactKeys(scope, ["version", "runId", "databaseName", "apiOrigin", "targetId"]);
  for (const key of Object.keys(expected) as Array<keyof AuditScope>) {
    if (scope[key] !== expected[key]) throw new Error("Audit hedefi/koşusu ayrıştı.");
  }
}

export class AuditCapture {
  private readonly sessionId = randomUUID();
  private readonly pending = new Map<object, Pick<AuditReceipt, "actorId" | "action">>();
  private failed = false;

  constructor(readonly directory: string, readonly scope: AuditScope) {
    validateAuditDirectory(directory, scope);
    writePrivate(join(directory, "sessions", `${this.sessionId}.json`), { complete: false });
  }
  begin(key: object, url: string, method: string, authorization?: string): void {
    if (isAuditedRequest(url, method, authorization, this.scope.apiOrigin)) {
      // Ham başlık/sorgu saklanmaz. Beklenen rota ve sentetik aktör yalnız
      // bu isteğin tamamlandığını doğrulamak için bellekte tutulur.
      this.pending.set(key, {
        actorId: authorization!.slice("Bearer dev:".length),
        action: `${method.toUpperCase()} ${new URL(url).pathname}`,
      });
    }
  }
  record(observation: AuditObservation, key?: object): void {
    try {
      const receipt = receiptFromResponse(observation, this.scope.apiOrigin);
      const expected = key === undefined ? undefined : this.pending.get(key);
      if (expected && (!receipt || receipt.actorId !== expected.actorId ||
          receipt.action !== expected.action)) {
        // Başka origin/rota/aktör yanıtı izlenen isteği tamamlamaz. Makbuz
        // yazılmaz; catch başarısız durumu ve pending kaydını korur.
        throw new Error("İzlenen audit isteği ile yanıt makbuzu uyuşmuyor.");
      }
      if (receipt) writePrivate(
        join(this.directory, "receipts", `${process.pid}-${randomUUID()}.json`), receipt,
      );
      if (expected && key) this.pending.delete(key);
    } catch {
      this.failed = true;
      throw new Error("Audit yanıt makbuzu kaydedilemedi.");
    }
  }
  fail(key: object): void {
    if (this.pending.has(key)) this.failed = true;
  }
  finish(): void {
    const complete = !this.failed && this.pending.size === 0;
    writePrivate(join(this.directory, "sessions", `${this.sessionId}.json`), { complete });
    if (!complete) throw new Error("Audit isteği çözümlenmedi; sahiplik temizliği durduruldu.");
  }
  async fetch(url: string, init: RequestInit = {}): Promise<Response> {
    const method = (init.method ?? "GET").toUpperCase();
    const authorization = new Headers(init.headers).get("Authorization") ?? undefined;
    const key = {};
    this.begin(key, url, method, authorization);
    try {
      // Audit isteğini otomatik başka bir hedefe/rotaya taşıma. İlgisiz
      // kaynak isteklerinde çağıranın mevcut fetch seçimi değişmez.
      const response = await fetch(url, this.pending.has(key) ? { ...init, redirect: "error" } : init);
      this.record({ url: response.url || url, method, authorization, status: response.status,
        requestId: response.headers.get("X-Request-ID") }, key);
      return response;
    } catch (error) {
      this.fail(key);
      throw error;
    }
  }
}

export function loadAuditReceipts(directory: string, scope: AuditScope): AuditReceipt[] {
  validateAuditDirectory(directory, scope);
  for (const kind of ["sessions", "receipts"]) {
    privateDirectory(join(directory, kind));
    const files = readdirSync(join(directory, kind));
    if (files.length > 20000 || files.some((name) => !/^[0-9a-f-]+\.json$/.test(name))) {
      throw new Error("Audit makbuzu dosya sınırı veya tamamlanmamış yazım.");
    }
  }
  for (const name of readdirSync(join(directory, "sessions"))) {
    const session = object(readBounded(join(directory, "sessions", name)));
    exactKeys(session, ["complete"]);
    if (session.complete !== true) throw new Error("Tamamlanmamış audit toplayıcısı var.");
  }
  const receipts = new Map<string, AuditReceipt>();
  for (const name of readdirSync(join(directory, "receipts"))) {
    const receipt = validateReceipt(readBounded(join(directory, "receipts", name)));
    const prior = receipts.get(receipt.requestId);
    if (prior && receiptKey(prior) !== receiptKey(receipt)) {
      throw new Error("Aynı sunucu kimliği çelişen audit sahipliği taşıyor.");
    }
    receipts.set(receipt.requestId, receipt);
  }
  return [...receipts.values()];
}
