import { resolveE2eDatabaseName, verifyDatabaseIdentity } from "./cleanup";
import { createE2eCourseIdentity, createE2eRunId, validateE2eRunId } from "./fixtures";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
//: Tohumlanmış eğitmen (seed_demo.sql). Kurulum bu kimlikle yalnız OKUR.
const AYSE_TOKEN = "dev:11111111-1111-1111-1111-111111111111";

/**
 * İki kapı; ikisi de koşu tek test verisi yazılmadan çalışır.
 *
 * 1. FAIL-EARLY — E2E_DATABASE_NAME burada doğrulanır, teardown'da değil.
 * 2. KİMLİK DEĞİŞMEZİ — sonda psql ile E2E_DATABASE_NAME'e yazılır, API'den
 *    yalnız okunur ve iki sonuçta da psql ile silinir. Bu dosya API'ye HİÇBİR
 *    yazma isteği göndermez: ilk sürüm nöbetçiyi API'den yazıyordu ve ayrışma
 *    durumunda API'nin gerçek veritabanında kalıntı bırakıyordu — yön bu yüzden
 *    ters çevrildi. Değişmez, lib/e2e-identity.test.ts ile çivili.
 */
export default async function globalSetup() {
  const requested = process.env.E2E_RUN_ID;
  const runId = requested ? validateE2eRunId(requested) : createE2eRunId();
  process.env.E2E_RUN_ID = runId;

  const databaseName = resolveE2eDatabaseName(undefined, process.env);

  await verifyDatabaseIdentity({
    databaseName,
    probe: createE2eCourseIdentity("KIMLIK", { runId }),
    apiHasCourse: async (code) => {
      const response = await fetch(`${API}/courses?limit=100`, {
        headers: { Authorization: `Bearer ${AYSE_TOKEN}` },
      });
      if (!response.ok) {
        throw new Error(
          `E2E kimlik sondası okunamadı (${response.status}): API ${API} ayakta ve tohumlanmış mı?`,
        );
      }
      const body = (await response.json()) as { items: Array<{ code: string }> };
      return body.items.some((course) => course.code === code);
    },
  });
  console.log(`[e2e] koşu kimliği: ${runId} · veritabanı kimliği doğrulandı: ${databaseName}`);
}
