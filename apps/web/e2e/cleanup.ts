import { execFileSync } from "node:child_process";
import { join } from "node:path";

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

interface CleanupAudit {
  id: string;
  requestId: string;
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
 * Koşu-önekli tek bir ders kodunun E2E veritabanında görünüp görünmediği.
 *
 * Var oluş sebebi (inceleme bulgusu): test verisi API'nin arkasındaki DB'ye,
 * temizlik ise E2E_DATABASE_NAME'e ayrı bağlantılardan gider ve ikisinin AYNI
 * veritabanı olduğunu hiçbir şey kanıtlamıyordu — yanlış ama desene uyan bir ad
 * "0 ders silindi" ile YEŞİL biter, kalıntı asıl DB'de kalırdı. globalSetup bu
 * fonksiyonla nöbetçiyi arar; görünmüyorsa kimlikler ayrışmıştır ve koşu tek
 * veri yazılmadan durur.
 */
export function courseVisibleInE2eDatabase(
  databaseName: string,
  code: string,
  env: NodeJS.ProcessEnv = process.env,
): boolean {
  const out = runPsql(
    databaseName,
    `SELECT count(*) FROM courses WHERE code = ${sqlLiteral(code)}`,
    env,
  );
  return out.trim() === "1";
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
    const [id, requestId, action, result, ...extra] = line.split("\t");
    if (
      !id ||
      !requestId ||
      !action ||
      (result !== "allowed" && result !== "denied") ||
      extra.length > 0 ||
      !UUID_PATTERN.test(id) ||
      !/^e2e-[a-z0-9]{6,20}-[A-Za-z0-9_-]+$/.test(requestId)
    ) {
      throw new Error(`Beklenmeyen admin audit temizlik satırı: ${line}`);
    }
    return { id, requestId, action, result };
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

function auditCandidateSql(runId?: string): string {
  const pattern = runId
    ? `^e2e-${validateE2eRunId(runId)}-[A-Za-z0-9_-]+$`
    : "^e2e-[a-z0-9]{6,20}-[A-Za-z0-9_-]+$";
  return `request_id ~ ${sqlLiteral(pattern)}`;
}

function listAuditSql(runId?: string): string {
  return `
SELECT id::text,
       request_id,
       action,
       result
FROM public.platform_admin_access_audit
WHERE ${auditCandidateSql(runId)}
ORDER BY created_at, id;
`.trim();
}

function deleteAuditSql(audits: CleanupAudit[], runId?: string): string {
  const ids = audits.map((audit) => `${sqlLiteral(audit.id)}::uuid`).join(", ");
  return `
WITH removed AS (
  DELETE FROM public.platform_admin_access_audit
  WHERE id IN (${ids})
    AND ${auditCandidateSql(runId)}
  RETURNING id, request_id, action, result
)
SELECT id::text,
       request_id,
       action,
       result
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
  const listed = parseCleanupRows(runPsql(databaseName, listSql(runId), env));
  const listedAudits = parseAuditRows(runPsql(databaseName, listAuditSql(runId), env));

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
      : parseAuditRows(runPsql(databaseName, deleteAuditSql(listedAudits, runId), env));
  if (deletedAudits.length !== listedAudits.length) {
    throw new Error(
      `Audit temizliği eksik kaldı: ${listedAudits.length} adaydan ` +
        `${deletedAudits.length} kayıt silindi.`,
    );
  }
  console.log(
    `[e2e:clean] ${deleted.length} ders ve ${deletedAudits.length} ` +
      "Bilgi İşlem audit kaydı silindi.",
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
