import { execFileSync } from "node:child_process";
import { join } from "node:path";

import {
  expectedAuditScope, loadAuditReceipts, receiptKey, validateReceipt,
  type AuditReceipt,
} from "./audit-receipts";

import {
  PROTECTED_COURSE_CODES,
  PROTECTED_COURSE_IDS,
  isRunScopedE2eCourseCode,
  validateE2eRunId,
} from "./fixtures";

interface CleanupCourse {
  id: string;
  code: string;
  title: string;
}

export interface CleanupAudit {
  id: string;
  requestId: string;
  actorId: string;
  action: string;
  result: "allowed" | "denied";
}

export interface CleanupOptions {
  onayli: boolean;
  runId?: string;
  databaseName?: string;
  env?: NodeJS.ProcessEnv;
}

export interface CleanupResult {
  listed: CleanupCourse[];
  deleted: CleanupCourse[];
  listedAudits: CleanupAudit[];
  deletedAudits: CleanupAudit[];
}

const SAFE_LOCAL_DATABASE_PATTERN = /(?:^|_)(?:e2e|test|preview)(?:_|$)/;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
type Environment = Readonly<Record<string, string | undefined>>;

export function resolveE2eDatabaseName(
  requested: string | undefined,
  env: Environment = process.env,
): string {
  const databaseName = (requested ?? env.E2E_DATABASE_NAME ?? "").trim();
  if (!databaseName) {
    throw new Error(
      "E2E_DATABASE_NAME zorunludur. Temizlik hiçbir veritabanını varsaymaz.",
    );
  }
  if (!/^[a-zA-Z0-9_]+$/.test(databaseName)) {
    throw new Error("E2E_DATABASE_NAME yalnızca harf, rakam ve alt çizgi içerebilir.");
  }
  if (["postgres", "template0", "template1"].includes(databaseName)) {
    throw new Error(`Sistem veritabanı temizlenemez: ${databaseName}`);
  }

  const ephemeralCiDatabase =
    env.CI === "true" && env.GITHUB_ACTIONS === "true" && databaseName === "dou_synapse";
  if (!ephemeralCiDatabase && !SAFE_LOCAL_DATABASE_PATTERN.test(databaseName)) {
    throw new Error(
      `Paylaşılan veritabanı temizlenemez: ${databaseName}. ` +
        "Yalnız adı e2e, test veya preview taşıyan izole veritabanları kabul edilir.",
    );
  }
  return databaseName;
}

function psqlPath(env: NodeJS.ProcessEnv): string {
  return env.PG_BIN ? join(env.PG_BIN, "psql") : "psql";
}

function runPsql(databaseName: string, sql: string, env: NodeJS.ProcessEnv): string {
  return execFileSync(
    psqlPath(env),
    ["-X", "-v", "ON_ERROR_STOP=1", "-A", "-t", "-F", "\t", "-d", databaseName, "-c", sql],
    { encoding: "utf8", env },
  ).trim();
}

/**
 * Veritabanı kimlik sondası — YÖN TERSİNE ÇEVRİLDİ (inceleme düzeltmesinin düzeltmesi).
 *
 * İlk sürüm nöbetçiyi API üzerinden yazıp psql ile arıyordu; ayrışma durumunda
 * API'nin gerçek veritabanında tek satırlık kalıntı bırakıyordu ve teardown o
 * satıra hiç ulaşamazdı. Şimdi sonda SİLEBİLDİĞİMİZ tarafa yazılır: satır psql
 * ile E2E_DATABASE_NAME'e girer, API'den yalnız OKUNUR ve her iki sonuçta da
 * psql ile silinir. Kurulum API üzerinden hiçbir yazma yapmaz — bu değişmez,
 * lib/e2e-identity.test.ts tarafından hem davranış hem kaynak taramasıyla
 * çivilidir. Ayrışma durumunda İKİ veritabanında da kalıntı sıfırdır.
 */
export function writeIdentityProbe(
  databaseName: string,
  probe: { code: string; title: string },
  env: NodeJS.ProcessEnv = process.env,
): void {
  runPsql(
    databaseName,
    `WITH c AS (
       INSERT INTO courses (code, title, created_by)
       VALUES (${sqlLiteral(probe.code)}, ${sqlLiteral(probe.title)},
               '11111111-1111-1111-1111-111111111111')
       RETURNING id
     )
     INSERT INTO course_memberships (course_id, user_id, role, status)
     SELECT id, '11111111-1111-1111-1111-111111111111', 'instructor', 'active' FROM c`,
    env,
  );
}

export function deleteIdentityProbe(
  databaseName: string,
  code: string,
  env: NodeJS.ProcessEnv = process.env,
): void {
  runPsql(databaseName, `DELETE FROM courses WHERE code = ${sqlLiteral(code)}`, env);
}

export async function verifyDatabaseIdentity(options: {
  databaseName: string;
  probe: { code: string; title: string };
  apiHasCourse: (code: string) => Promise<boolean>;
  writeProbe?: typeof writeIdentityProbe;
  deleteProbe?: typeof deleteIdentityProbe;
  env?: NodeJS.ProcessEnv;
}): Promise<void> {
  const env = options.env ?? process.env;
  const write = options.writeProbe ?? writeIdentityProbe;
  const drop = options.deleteProbe ?? deleteIdentityProbe;
  write(options.databaseName, options.probe, env);
  let visible = false;
  try {
    visible = await options.apiHasCourse(options.probe.code);
  } finally {
    drop(options.databaseName, options.probe.code, env);
  }
  if (!visible) {
    throw new Error(
      `Veritabanı kimlikleri ayrışmış: sonda ${options.databaseName} içine yazıldı ` +
        "ama API onu görmüyor — API başka bir veritabanına bağlı. Temizlik bu hâliyle " +
        "sahte yeşil verirdi. Koşu tek test verisi yazılmadan durduruldu; sonda silindi.",
    );
  }
}

export function parseCleanupRows(output: string): CleanupCourse[] {
  if (!output.trim()) return [];
  return output.split("\n").map((line) => {
    const [id, code, title, ...extra] = line.split("\t");
    if (!id || !code || title === undefined || extra.length > 0 || !UUID_PATTERN.test(id)) {
      throw new Error(`Beklenmeyen psql temizlik satırı: ${line}`);
    }
    return { id, code, title };
  });
}

export function parseAuditRows(output: string): CleanupAudit[] {
  if (!output.trim()) return [];
  return output.split("\n").map((line) => {
    const [id, requestId, action, result, actorId, ...extra] = line.split("\t");
    if (
      !id ||
      !requestId ||
      !action ||
      (result !== "allowed" && result !== "denied") ||
      extra.length > 0 ||
      !UUID_PATTERN.test(id)
    ) {
      throw new Error(`Beklenmeyen admin audit temizlik satırı: ${line}`);
    }
    return { id, ...validateReceipt({ requestId, action, result, actorId }) };
  });
}

function sqlLiteral(value: string): string {
  return `'${value.replaceAll("'", "''")}'`;
}

function protectedSql(): string {
  const ids = PROTECTED_COURSE_IDS.map((id) => `${sqlLiteral(id)}::uuid`).join(", ");
  const codes = PROTECTED_COURSE_CODES.map(sqlLiteral).join(", ");
  return `id NOT IN (${ids}) AND code NOT IN (${codes})`;
}

function candidateSql(runId?: string): string {
  const runClause = runId
    ? `code ~ ${sqlLiteral(`^E2E-${validateE2eRunId(runId)}-[0-9]+$`)}`
    : "code ~ '^E2E-[a-z0-9]{6,20}-[0-9]+$'";
  return [runClause, protectedSql()].join(" AND ");
}

function listSql(runId?: string): string {
  return `
SELECT id::text,
       code,
       regexp_replace(title, E'[\\t\\n\\r]+', ' ', 'g')
FROM public.courses
WHERE ${candidateSql(runId)}
ORDER BY code;
`.trim();
}

function deleteSql(courses: CleanupCourse[], runId?: string): string {
  const ids = courses.map((course) => `${sqlLiteral(course.id)}::uuid`).join(", ");
  return `
WITH removed AS (
  DELETE FROM public.courses
  WHERE id IN (${ids})
    AND ${candidateSql(runId)}
  RETURNING id, code, title
)
SELECT id::text,
       code,
       regexp_replace(title, E'[\\t\\n\\r]+', ' ', 'g')
FROM removed
ORDER BY code;
`.trim();
}

export function auditCandidateSql(receipts: AuditReceipt[]): string {
  // Boş makbuz kümesi bütün UUID'lere veya aktör/zaman penceresine genişlemez.
  if (receipts.length === 0) return "FALSE";
  return receipts.map((value) => {
    const row = validateReceipt(value);
    return `(request_id = ${sqlLiteral(row.requestId)} ` +
      `AND actor_user_id = ${sqlLiteral(row.actorId)}::uuid ` +
      `AND action = ${sqlLiteral(row.action)} AND result = ${sqlLiteral(row.result)})`;
  }).join(" OR ");
}

export function assertAuditOwnership(audits: CleanupAudit[], receipts: AuditReceipt[]): void {
  const owned = new Set(receipts.map(receiptKey));
  const seen = new Set<string>();
  for (const { id, requestId, actorId, action, result } of audits) {
    const key = receiptKey({ requestId, actorId, action, result });
    if (!UUID_PATTERN.test(id) || !owned.has(key) || seen.has(key)) {
      throw new Error("Audit satırı bu koşunun tekil yanıt makbuzuna ait değil.");
    }
    seen.add(key);
  }
  if (seen.size !== owned.size) {
    throw new Error("Yakalanan audit makbuzu sayısı veritabanı satırlarıyla uyuşmuyor.");
  }
}

function listAuditSql(receipts: AuditReceipt[]): string {
  return `
SELECT id::text, request_id, action, result, actor_user_id::text
FROM public.platform_admin_access_audit
WHERE (${auditCandidateSql(receipts)})
ORDER BY created_at, id;
`.trim();
}

export function deleteAuditSql(audits: CleanupAudit[], receipts: AuditReceipt[]): string {
  assertAuditOwnership(audits, receipts);
  if (audits.length === 0) throw new Error("Boş audit silme sorgusu yürütülmez.");
  const ids = audits.map((audit) => `${sqlLiteral(audit.id)}::uuid`).join(", ");
  return `
WITH removed AS (
  DELETE FROM public.platform_admin_access_audit
  WHERE id IN (${ids}) AND (${auditCandidateSql(receipts)})
  RETURNING id, request_id, action, result, actor_user_id
)
SELECT id::text, request_id, action, result, actor_user_id::text
FROM removed
ORDER BY request_id, id;
`.trim();
}

function printCandidates(
  courses: CleanupCourse[],
  audits: CleanupAudit[],
  runId?: string,
) {
  const scope = runId ? `koşu ${runId}` : "tüm koşular";
  console.log(`[e2e:clean] ${scope}: ${courses.length} ders bulundu.`);
  for (const course of courses) {
    console.log(`  ${course.code}\t${course.id}\t${course.title}`);
  }
  console.log(`[e2e:clean] ${scope}: ${audits.length} Bilgi İşlem audit kaydı bulundu.`);
  for (const audit of audits) {
    console.log(`  ${audit.requestId}\t${audit.action}\t${audit.result}`);
  }
}

export async function temizle(options: CleanupOptions): Promise<CleanupResult> {
  const env = options.env ?? process.env;
  const runId = options.runId ? validateE2eRunId(options.runId) : undefined;
  const databaseName = resolveE2eDatabaseName(options.databaseName, env);
  if (!runId || !env.E2E_AUDIT_DIR) {
    throw new Error("Audit temizliği açık koşu ve o koşunun özel makbuz dizinini gerektirir.");
  }
  const receipts = loadAuditReceipts(
    env.E2E_AUDIT_DIR, expectedAuditScope(runId, databaseName, env),
  );
  const listed = parseCleanupRows(runPsql(databaseName, listSql(runId), env));
  const listedAudits = parseAuditRows(runPsql(databaseName, listAuditSql(receipts), env));
  // Silme öncesinde bütün bilinen makbuzlar bulunmalı; audit silindikten sonra
  // eski makbuzla tekrar temizliğin 0/0 başarılı sayılması da engellenir.
  assertAuditOwnership(listedAudits, receipts);

  for (const course of listed) {
    if (!isRunScopedE2eCourseCode(course.code, runId)) {
      throw new Error(`Test deseni dışındaki ders reddedildi: ${course.code}`);
    }
  }
  printCandidates(listed, listedAudits, runId);

  if (!options.onayli) {
    console.log("[e2e:clean] Kuru koşu: silme yapılmadı. Silmek için --evet kullanın.");
    return { listed, deleted: [], listedAudits, deletedAudits: [] };
  }
  const deleted =
    listed.length === 0
      ? []
      : parseCleanupRows(runPsql(databaseName, deleteSql(listed, runId), env));
  if (deleted.length !== listed.length) {
    throw new Error(
      `Temizlik eksik kaldı: ${listed.length} adaydan ${deleted.length} ders silindi.`,
    );
  }
  const deletedAudits =
    listedAudits.length === 0
      ? []
      : parseAuditRows(runPsql(databaseName, deleteAuditSql(listedAudits, receipts), env));
  if (deletedAudits.length !== listedAudits.length) {
    throw new Error(
      `Audit temizliği eksik kaldı: ${listedAudits.length} adaydan ` +
        `${deletedAudits.length} kayıt silindi.`,
    );
  }
  assertAuditOwnership(deletedAudits, receipts);
  console.log(
    `[e2e:clean] ${deleted.length} ders ve ${deletedAudits.length} ` +
      "yakalanmış Bilgi İşlem audit makbuzu silindi; küresel eksiksizlik iddiası yok.",
  );
  return { listed, deleted, listedAudits, deletedAudits };
}

function readCliOptions(args: string[]) {
  let onayli = false;
  let runId: string | undefined;
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === "--evet") {
      onayli = true;
      continue;
    }
    if (argument === "--run") {
      const value = args[index + 1];
      if (!value) throw new Error("--run için koşu kimliği gerekli.");
      runId = validateE2eRunId(value);
      index += 1;
      continue;
    }
    throw new Error(`Bilinmeyen seçenek: ${argument}`);
  }
  return { onayli, runId };
}

const cliEntry = process.argv[1]?.replaceAll("\\", "/").endsWith("/e2e/cleanup.ts");
if (cliEntry) {
  const options = readCliOptions(process.argv.slice(2));
  void temizle(options).catch((error: unknown) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}
