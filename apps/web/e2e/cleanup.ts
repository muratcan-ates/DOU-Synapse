import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, unlinkSync } from "node:fs";
import { dirname, join } from "node:path";

import {
  PROTECTED_COURSE_CODES,
  PROTECTED_COURSE_IDS,
  e2eRequestIdFailureMarkerPath,
  e2eRequestManifestPath,
  isRunScopedE2eCourseCode,
  validateE2eServerRequestId,
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

interface CleanupApiEvent {
  id: string;
  requestId: string;
  routeTemplate: string;
  statusCode: number;
}

export interface ApiEventCleanupIo {
  pause: () => Promise<void>;
  list: () => CleanupApiEvent[];
  remove: (events: CleanupApiEvent[]) => CleanupApiEvent[];
}

export interface ApiEventBarrierIo {
  pause: () => Promise<void>;
  exists: (requestId: string) => boolean | Promise<boolean>;
}

export interface CleanupOptions {
  onayli: boolean;
  runId?: string;
  databaseName?: string;
  apiEventBarrierRequestId?: string;
  env?: NodeJS.ProcessEnv;
}

export interface CleanupResult {
  listed: CleanupCourse[];
  deleted: CleanupCourse[];
  listedAudits: CleanupAudit[];
  deletedAudits: CleanupAudit[];
  listedApiEvents: CleanupApiEvent[];
  deletedApiEvents: CleanupApiEvent[];
}

const SAFE_LOCAL_DATABASE_PATTERN = /(?:^|_)(?:e2e|test|preview)(?:_|$)/;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SERVER_REQUEST_ID_PATTERN = /^[a-f0-9]{32}$/;
const REQUEST_MANIFEST_PATTERN = /^request-ids-([a-z0-9]{6,20})\.txt$/;
const REQUEST_ID_FAILURE_MARKER_PATTERN =
  /^request-id-errors-([a-z0-9]{6,20})\.txt$/;
const EVENT_BARRIER_INTERVAL_MS = 2_000;
const EVENT_BARRIER_MAX_ROUNDS = 26;
const EVENT_SETTLE_INTERVAL_MS = 2_500;
const EVENT_SETTLE_MAX_ROUNDS = 6;
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
    throw new Error(
      "E2E_DATABASE_NAME yalnızca harf, rakam ve alt çizgi içerebilir.",
    );
  }
  if (["postgres", "template0", "template1"].includes(databaseName)) {
    throw new Error(`Sistem veritabanı temizlenemez: ${databaseName}`);
  }

  const ephemeralCiDatabase =
    env.CI === "true" &&
    env.GITHUB_ACTIONS === "true" &&
    databaseName === "dou_synapse";
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

function runPsql(
  databaseName: string,
  sql: string,
  env: NodeJS.ProcessEnv,
): string {
  return execFileSync(
    psqlPath(env),
    [
      "-X",
      "-v",
      "ON_ERROR_STOP=1",
      "-A",
      "-t",
      "-F",
      "\t",
      "-d",
      databaseName,
      "-c",
      sql,
    ],
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
  runPsql(
    databaseName,
    `DELETE FROM courses WHERE code = ${sqlLiteral(code)}`,
    env,
  );
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
    if (
      !id ||
      !code ||
      title === undefined ||
      extra.length > 0 ||
      !UUID_PATTERN.test(id)
    ) {
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
      !SERVER_REQUEST_ID_PATTERN.test(requestId)
    ) {
      throw new Error(`Beklenmeyen admin audit temizlik satırı: ${line}`);
    }
    return { id, requestId, action, result };
  });
}

export function parseApiEventRows(output: string): CleanupApiEvent[] {
  if (!output.trim()) return [];
  return output.split("\n").map((line) => {
    const [id, requestId, routeTemplate, statusText, ...extra] =
      line.split("\t");
    const statusCode = Number(statusText);
    if (
      !id ||
      !requestId ||
      !routeTemplate ||
      extra.length > 0 ||
      !UUID_PATTERN.test(id) ||
      !SERVER_REQUEST_ID_PATTERN.test(requestId) ||
      !Number.isInteger(statusCode) ||
      statusCode < 100 ||
      statusCode > 599
    ) {
      throw new Error(`Beklenmeyen API event temizlik satırı: ${line}`);
    }
    return { id, requestId, routeTemplate, statusCode };
  });
}

export function parseRequestManifest(output: string): string[] {
  if (!output.trim()) return [];
  const requestIds = output.split("\n").filter(Boolean);
  for (const requestId of requestIds) {
    if (!SERVER_REQUEST_ID_PATTERN.test(requestId)) {
      throw new Error(`Beklenmeyen E2E request manifest kimliği: ${requestId}`);
    }
  }
  return [...new Set(requestIds)];
}

function sqlLiteral(value: string): string {
  return `'${value.replaceAll("'", "''")}'`;
}

function protectedSql(): string {
  const ids = PROTECTED_COURSE_IDS.map((id) => `${sqlLiteral(id)}::uuid`).join(
    ", ",
  );
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
  const ids = courses
    .map((course) => `${sqlLiteral(course.id)}::uuid`)
    .join(", ");
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

function requestManifestPaths(
  runId: string | undefined,
  env: NodeJS.ProcessEnv,
): string[] {
  if (runId) return [e2eRequestManifestPath(runId, env)];
  const directory = dirname(e2eRequestManifestPath("aaaaaa", env));
  if (!existsSync(directory)) return [];
  return readdirSync(directory)
    .filter((name) => REQUEST_MANIFEST_PATTERN.test(name))
    .map((name) => join(directory, name));
}

function requestIdFailureMarkerPaths(
  runId: string | undefined,
  env: NodeJS.ProcessEnv,
): string[] {
  if (runId) return [e2eRequestIdFailureMarkerPath(runId, env)];
  const directory = dirname(e2eRequestIdFailureMarkerPath("aaaaaa", env));
  if (!existsSync(directory)) return [];
  return readdirSync(directory)
    .filter((name) => REQUEST_ID_FAILURE_MARKER_PATTERN.test(name))
    .map((name) => join(directory, name));
}

function manifestedRequestIds(paths: string[]): string[] {
  return [
    ...new Set(
      paths.flatMap((path) =>
        existsSync(path)
          ? parseRequestManifest(readFileSync(path, "utf8"))
          : [],
      ),
    ),
  ];
}

export function auditCandidateSql(requestIds: string[]): string {
  if (requestIds.length === 0) return "FALSE";
  return `request_id IN (${requestIds.map(sqlLiteral).join(", ")})`;
}

function listAuditSql(requestIds: string[]): string {
  return `
SELECT id::text,
       request_id,
       action,
       result
FROM public.platform_admin_access_audit
WHERE ${auditCandidateSql(requestIds)}
ORDER BY created_at, id;
`.trim();
}

function deleteAuditSql(audits: CleanupAudit[], requestIds: string[]): string {
  const ids = audits.map((audit) => `${sqlLiteral(audit.id)}::uuid`).join(", ");
  return `
WITH removed AS (
  DELETE FROM public.platform_admin_access_audit
  WHERE id IN (${ids})
    AND ${auditCandidateSql(requestIds)}
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

function listApiEventSql(requestIds: string[]): string {
  return `
SELECT id::text,
       request_id,
       route_template,
       status_code::text
FROM public.api_request_events
WHERE ${auditCandidateSql(requestIds)}
ORDER BY created_at, id;
`.trim();
}

function deleteApiEventSql(
  events: CleanupApiEvent[],
  requestIds: string[],
): string {
  const ids = events.map((event) => `${sqlLiteral(event.id)}::uuid`).join(", ");
  return `
WITH removed AS (
  DELETE FROM public.api_request_events
  WHERE id IN (${ids})
    AND ${auditCandidateSql(requestIds)}
  RETURNING id, request_id, route_template, status_code
)
SELECT id::text,
       request_id,
       route_template,
       status_code::text
FROM removed
ORDER BY request_id, id;
`.trim();
}

function apiEventBarrierExistsSql(requestId: string): string {
  const validated = validateE2eServerRequestId(requestId);
  return `
SELECT EXISTS (
  SELECT 1
  FROM public.api_request_events
  WHERE request_id = ${sqlLiteral(validated)}
);
`.trim();
}

export async function waitForApiEventBarrier(
  requestId: string,
  io: ApiEventBarrierIo,
  maxRounds = EVENT_BARRIER_MAX_ROUNDS,
): Promise<void> {
  const validated = validateE2eServerRequestId(requestId);
  if (!Number.isInteger(maxRounds) || maxRounds < 1) {
    throw new Error("API event bariyeri için pozitif bir tur sınırı gerekir.");
  }

  for (let round = 0; round < maxRounds; round += 1) {
    if (await io.exists(validated)) return;
    if (round + 1 < maxRounds) await io.pause();
  }

  throw new Error(
    "API event FIFO bariyeri bounded bekleme içinde kalıcı depoda görünmedi; " +
      "manifest korunarak temizlik durduruldu.",
  );
}

async function waitForPersistedApiEventBarrier(
  databaseName: string,
  requestId: string,
  env: NodeJS.ProcessEnv,
): Promise<void> {
  await waitForApiEventBarrier(requestId, {
    pause: () =>
      new Promise((resolve) => setTimeout(resolve, EVENT_BARRIER_INTERVAL_MS)),
    exists: (candidate) => {
      const output = runPsql(
        databaseName,
        apiEventBarrierExistsSql(candidate),
        env,
      );
      if (output === "t") return true;
      if (output === "f") return false;
      throw new Error("API event bariyer sorgusu beklenmeyen sonuç döndürdü.");
    },
  });
}

export async function settleApiEventCleanup(
  initial: CleanupApiEvent[],
  io: ApiEventCleanupIo,
  maxRounds = EVENT_SETTLE_MAX_ROUNDS,
): Promise<{ listed: CleanupApiEvent[]; deleted: CleanupApiEvent[] }> {
  const listedById = new Map(initial.map((event) => [event.id, event]));
  const deletedById = new Map<string, CleanupApiEvent>();
  let current = initial;
  let consecutiveEmpty = 0;

  for (let round = 0; round < maxRounds; round += 1) {
    if (round > 0) {
      await io.pause();
      current = io.list();
      for (const event of current) listedById.set(event.id, event);
    }

    if (current.length === 0) {
      consecutiveEmpty += 1;
      // Collector ayni batch'i iki kez, her biri 2 saniyeye kadar deneyebilir.
      // 0 / 2.5 / 5.0 saniye sessizligi, kuyruktan alinmis ama henuz commit
      // etmemis bir olayin manifest silindikten sonra geri gelmesini engeller.
      if (consecutiveEmpty >= 3) {
        return {
          listed: [...listedById.values()],
          deleted: [...deletedById.values()],
        };
      }
      continue;
    }

    consecutiveEmpty = 0;
    const deleted = io.remove(current);
    if (deleted.length !== current.length) {
      throw new Error(
        `API event temizliği eksik kaldı: ${current.length} adaydan ` +
          `${deleted.length} kayıt silindi.`,
      );
    }
    for (const event of deleted) deletedById.set(event.id, event);
  }

  throw new Error(
    "API event kuyruğu bounded bekleme içinde üç ardışık boş tur vermedi; " +
      "manifest korunarak temizlik durduruldu.",
  );
}

async function settleAndDeleteApiEvents(
  databaseName: string,
  requestIds: string[],
  initial: CleanupApiEvent[],
  env: NodeJS.ProcessEnv,
): Promise<{ listed: CleanupApiEvent[]; deleted: CleanupApiEvent[] }> {
  if (requestIds.length === 0) return { listed: [], deleted: [] };
  return settleApiEventCleanup(initial, {
    pause: () =>
      new Promise((resolve) => setTimeout(resolve, EVENT_SETTLE_INTERVAL_MS)),
    list: () =>
      parseApiEventRows(
        runPsql(databaseName, listApiEventSql(requestIds), env),
      ),
    remove: (events) =>
      parseApiEventRows(
        runPsql(databaseName, deleteApiEventSql(events, requestIds), env),
      ),
  });
}

function printCandidates(
  courses: CleanupCourse[],
  audits: CleanupAudit[],
  apiEvents: CleanupApiEvent[],
  runId?: string,
) {
  const scope = runId ? `koşu ${runId}` : "tüm koşular";
  console.log(`[e2e:clean] ${scope}: ${courses.length} ders bulundu.`);
  for (const course of courses) {
    console.log(`  ${course.code}\t${course.id}\t${course.title}`);
  }
  console.log(
    `[e2e:clean] ${scope}: ${audits.length} Bilgi İşlem audit kaydı bulundu.`,
  );
  for (const audit of audits) {
    console.log(`  ${audit.requestId}\t${audit.action}\t${audit.result}`);
  }
  console.log(
    `[e2e:clean] ${scope}: ${apiEvents.length} API event kaydı bulundu.`,
  );
  for (const event of apiEvents) {
    console.log(
      `  ${event.requestId}\t${event.routeTemplate}\t${event.statusCode}`,
    );
  }
}

export async function temizle(options: CleanupOptions): Promise<CleanupResult> {
  const env = options.env ?? process.env;
  const runId = options.runId ? validateE2eRunId(options.runId) : undefined;
  const databaseName = resolveE2eDatabaseName(options.databaseName, env);
  if (
    requestIdFailureMarkerPaths(runId, env).some((path) => existsSync(path))
  ) {
    throw new Error(
      "Bir API yanıtında geçersiz sunucu X-Request-ID görüldü; manifest korunarak E2E temizliği durduruldu.",
    );
  }
  if (options.apiEventBarrierRequestId) {
    await waitForPersistedApiEventBarrier(
      databaseName,
      options.apiEventBarrierRequestId,
      env,
    );
  }
  const manifestPaths = requestManifestPaths(runId, env);
  const requestIds = manifestedRequestIds(manifestPaths);
  const listed = parseCleanupRows(runPsql(databaseName, listSql(runId), env));
  const listedAudits = parseAuditRows(
    runPsql(databaseName, listAuditSql(requestIds), env),
  );
  const listedApiEvents = parseApiEventRows(
    runPsql(databaseName, listApiEventSql(requestIds), env),
  );

  for (const course of listed) {
    if (!isRunScopedE2eCourseCode(course.code, runId)) {
      throw new Error(`Test deseni dışındaki ders reddedildi: ${course.code}`);
    }
  }
  printCandidates(listed, listedAudits, listedApiEvents, runId);

  if (!options.onayli) {
    console.log(
      "[e2e:clean] Kuru koşu: silme yapılmadı. Silmek için --evet kullanın.",
    );
    return {
      listed,
      deleted: [],
      listedAudits,
      deletedAudits: [],
      listedApiEvents,
      deletedApiEvents: [],
    };
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
      : parseAuditRows(
          runPsql(databaseName, deleteAuditSql(listedAudits, requestIds), env),
        );
  if (deletedAudits.length !== listedAudits.length) {
    throw new Error(
      `Audit temizliği eksik kaldı: ${listedAudits.length} adaydan ` +
        `${deletedAudits.length} kayıt silindi.`,
    );
  }
  const settledEvents = await settleAndDeleteApiEvents(
    databaseName,
    requestIds,
    listedApiEvents,
    env,
  );
  const allListedApiEvents = settledEvents.listed;
  const deletedApiEvents = settledEvents.deleted;
  console.log(
    `[e2e:clean] ${deleted.length} ders, ${deletedAudits.length} ` +
      `Bilgi İşlem audit ve ${deletedApiEvents.length} API event kaydı silindi.`,
  );
  for (const manifestPath of manifestPaths) {
    if (existsSync(manifestPath)) unlinkSync(manifestPath);
  }
  return {
    listed,
    deleted,
    listedAudits,
    deletedAudits,
    listedApiEvents: allListedApiEvents,
    deletedApiEvents,
  };
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

const cliEntry = process.argv[1]
  ?.replaceAll("\\", "/")
  .endsWith("/e2e/cleanup.ts");
if (cliEntry) {
  const options = readCliOptions(process.argv.slice(2));
  void temizle(options).catch((error: unknown) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}
