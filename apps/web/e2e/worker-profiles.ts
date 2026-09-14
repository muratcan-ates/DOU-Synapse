/** Çalışan kimlikleri yalnız doğrulanmış, özel koşu makbuzuyla kurulup temizlenir. */
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import {
  closeSync, constants, fstatSync, lstatSync, mkdirSync, openSync, readFileSync,
  readdirSync, writeFileSync,
} from "node:fs";
import { join } from "node:path";
import { expectedAuditScope, validateAuditDirectory, type AuditScope } from "./audit-receipts";
import { resolveE2eDatabaseName } from "./cleanup";
import { requireE2eRunId } from "./fixtures";

export interface WorkerUser {
  id: string;
  email: string;
  fullName: string;
  role: "instructor" | "student";
}
export interface WorkerUsers { teacher: WorkerUser; student: WorkerUser }
interface ProfileManifest { version: 1; scope: AuditScope; workerIndex: number; users: WorkerUsers }
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

function privateDirectory(path: string) {
  const stat = lstatSync(path);
  if (!stat.isDirectory() || stat.isSymbolicLink() || (stat.mode & 0o077) !== 0) {
    throw new Error("Çalışan kimlik dizini özel olmalıdır.");
  }
}
function readPrivate(path: string): unknown {
  const fd = openSync(path, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const stat = fstatSync(fd);
    if (!stat.isFile() || stat.size > 8192 || (stat.mode & 0o077) !== 0) {
      throw new Error("Çalışan kimlik makbuzu sınırı ihlal edildi.");
    }
    return JSON.parse(readFileSync(fd, "utf8")) as unknown;
  } finally { closeSync(fd); }
}
function sameScope(actual: unknown, expected: AuditScope) {
  if (!actual || typeof actual !== "object" || Array.isArray(actual)) {
    throw new Error("Çalışan kimlik kapsamı eksik.");
  }
  const row = actual as Record<string, unknown>;
  if (Object.keys(row).sort().join() !== Object.keys(expected).sort().join() ||
      Object.entries(expected).some(([key, value]) => row[key] !== value)) {
    throw new Error("Çalışan kimlik hedefi veya koşusu ayrıştı.");
  }
}
function currentScope() {
  const databaseName = resolveE2eDatabaseName(undefined, process.env);
  const scope = expectedAuditScope(requireE2eRunId(), databaseName);
  const directory = process.env.E2E_AUDIT_DIR;
  if (!directory) throw new Error("Çalışan profilleri doğrulanmış global setup gerektirir.");
  validateAuditDirectory(directory, scope);
  const profilesDirectory = join(directory, "worker-profiles");
  privateDirectory(profilesDirectory);
  sameScope(readPrivate(join(profilesDirectory, "setup-success.json")), scope);
  return { databaseName, scope, profilesDirectory };
}

/** Yalnız API/psql kimlik sondası başarıyla tamamlandıktan sonra çağrılır. */
export function initializeWorkerProfiles(directory: string, scope: AuditScope): void {
  validateAuditDirectory(directory, scope);
  const profilesDirectory = join(directory, "worker-profiles");
  // Var olan bir koşunun başarılı setup makbuzunu yeniden kullanma.
  mkdirSync(profilesDirectory, { mode: 0o700 });
  privateDirectory(profilesDirectory);
  writeFileSync(join(profilesDirectory, "setup-success.json"), JSON.stringify(scope), {
    flag: "wx", mode: 0o600,
  });
}
function sqlLiteral(value: string): string { return `'${value.replaceAll("'", "''")}'`; }
function psql(databaseName: string, sql: string): string {
  return execFileSync(process.env.PG_BIN ? join(process.env.PG_BIN, "psql") : "psql",
    ["-X", "-v", "ON_ERROR_STOP=1", "-A", "-t", "-d", databaseName],
    { input: sql, encoding: "utf8", env: process.env, timeout: 30_000 }).trim();
}
function newUser(runId: string, role: WorkerUser["role"]): WorkerUser {
  const id = randomUUID();
  return { id, email: `e2e-${runId}-${id}@example.com`,
    fullName: role === "instructor" ? "E2E Eğitmen" : "E2E Öğrenci", role };
}

export function provisionWorkerProfiles(workerIndex: number): WorkerUsers {
  if (!Number.isSafeInteger(workerIndex) || workerIndex < 0) throw new Error("Çalışan kimliği geçersiz.");
  const { databaseName, scope, profilesDirectory } = currentScope();
  const users = { teacher: newUser(scope.runId, "instructor"), student: newUser(scope.runId, "student") };
  const manifest: ProfileManifest = { version: 1, scope, workerIndex, users };
  // Önce sahiplik yazılır: INSERT yanıtı kaybolsa bile exact UUID/email kalır.
  writeFileSync(join(profilesDirectory, `${randomUUID()}.json`), JSON.stringify(manifest), {
    flag: "wx", mode: 0o600,
  });
  const values = Object.values(users).map((user) =>
    `(${sqlLiteral(user.id)}::uuid, ${sqlLiteral(user.email)}, ${sqlLiteral(user.fullName)})`).join(", ");
  psql(databaseName, `BEGIN; INSERT INTO public.profiles (id, email, full_name) VALUES ${values}; COMMIT;`);
  return users;
}
function readManifest(value: unknown, scope: AuditScope): ProfileManifest {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Profil makbuzu geçersiz.");
  const row = value as ProfileManifest;
  if (Object.keys(row).sort().join() !== "scope,users,version,workerIndex" || row.version !== 1 ||
      !Number.isSafeInteger(row.workerIndex) || row.workerIndex < 0 || !row.users ||
      Object.keys(row.users).sort().join() !== "student,teacher") throw new Error("Profil makbuzu alanları geçersiz.");
  sameScope(row.scope, scope);
  for (const [key, role] of [["teacher", "instructor"], ["student", "student"]] as const) {
    const user = row.users[key];
    if (!user || Object.keys(user).sort().join() !== "email,fullName,id,role" || !UUID.test(user.id) ||
        user.email !== `e2e-${scope.runId}-${user.id}@example.com` || user.role !== role ||
        user.fullName !== (role === "instructor" ? "E2E Eğitmen" : "E2E Öğrenci")) {
      throw new Error("Profil makbuzu sentetik koşu kimliğine ait değil.");
    }
  }
  if (row.users.teacher.id === row.users.student.id) throw new Error("Çalışan rolleri aynı kimliği paylaşamaz.");
  return row;
}

/** Önce mevcut temizle() tamamlanır; kalan her bağımlı satır silmeyi durdurur. */
export function cleanupWorkerProfiles(): number {
  const { databaseName, scope, profilesDirectory } = currentScope();
  const names = readdirSync(profilesDirectory).filter((name) => name !== "setup-success.json");
  if (names.length > 10000 || names.some((name) => !UUID.test(name.replace(/\.json$/, "")) || !name.endsWith(".json"))) {
    throw new Error("Profil makbuzu dosya sınırı aşıldı.");
  }
  const users = names.flatMap((name) => Object.values(readManifest(readPrivate(join(profilesDirectory, name)), scope).users));
  if (new Set(users.map((user) => user.id)).size !== users.length) throw new Error("Yinelenen profil sahipliği.");
  if (users.length === 0) return 0;
  const values = users.map((user) => `(${sqlLiteral(user.id)}::uuid, ${sqlLiteral(user.email)})`).join(", ");
  // CASCADE/SET NULL da yetki değildir. Bütün FK'ler katalogdan bulunur ve
  // işlem boyunca kilitlenir; bilinmeyen yeni tablo sessizce silinemez.
  const output = psql(databaseName, `BEGIN;
SET LOCAL lock_timeout = '5s';
CREATE TEMP TABLE owned_e2e_profiles (id uuid PRIMARY KEY, email text UNIQUE) ON COMMIT DROP;
INSERT INTO owned_e2e_profiles VALUES ${values};
LOCK TABLE public.profiles IN SHARE ROW EXCLUSIVE MODE;
DO $guard$
DECLARE ref record; found_reference boolean;
BEGIN
  IF EXISTS (SELECT 1 FROM public.profiles p JOIN owned_e2e_profiles o ON p.id=o.id OR p.email=o.email
             WHERE p.id<>o.id OR p.email<>o.email) THEN
    RAISE EXCEPTION 'Profil UUID/e-posta sahipliği ayrıştı';
  END IF;
  FOR ref IN
    SELECT c.conrelid::regclass AS relation,
      string_agg(format('r.%I = p.%I', a.attname, b.attname), ' AND ' ORDER BY k.ordinality) AS predicate
    FROM pg_catalog.pg_constraint c
    CROSS JOIN LATERAL unnest(c.conkey, c.confkey) WITH ORDINALITY AS k(local_key, remote_key, ordinality)
    JOIN pg_catalog.pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.local_key
    JOIN pg_catalog.pg_attribute b ON b.attrelid=c.confrelid AND b.attnum=k.remote_key
    WHERE c.contype='f' AND c.confrelid='public.profiles'::regclass
    GROUP BY c.oid, c.conrelid ORDER BY c.conrelid
  LOOP
    EXECUTE format('LOCK TABLE %s IN SHARE ROW EXCLUSIVE MODE', ref.relation);
    EXECUTE format('SELECT EXISTS (SELECT 1 FROM %s r JOIN public.profiles p ON %s JOIN owned_e2e_profiles o ON o.id=p.id AND o.email=p.email)', ref.relation, ref.predicate)
      INTO found_reference;
    IF found_reference THEN RAISE EXCEPTION 'Profil bağımlılığı kaldı: %', ref.relation; END IF;
  END LOOP;
  LOCK TABLE public.platform_admin_access_audit IN SHARE ROW EXCLUSIVE MODE;
  IF EXISTS (SELECT 1 FROM public.platform_admin_access_audit a JOIN owned_e2e_profiles o ON o.id=a.actor_user_id) THEN
    RAISE EXCEPTION 'Profil audit bağımlılığı kaldı';
  END IF;
END $guard$;
WITH removed AS (DELETE FROM public.profiles p USING owned_e2e_profiles o
  WHERE p.id=o.id AND p.email=o.email RETURNING p.id)
SELECT 'REMOVED=' || count(*) FROM removed;
COMMIT;`);
  const match = /^REMOVED=(\d+)$/m.exec(output);
  if (!match) throw new Error("Profil temizliği sonucu okunamadı.");
  return Number(match[1]);
}
