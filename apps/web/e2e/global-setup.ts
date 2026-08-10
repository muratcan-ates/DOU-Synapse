import { courseVisibleInE2eDatabase, resolveE2eDatabaseName } from "./cleanup";
import { createE2eCourseIdentity, createE2eRunId, validateE2eRunId } from "./fixtures";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
//: Tohumlanmış eğitmen (seed_demo.sql). Dev auth E2E'nin tek kullanıcı kaynağı.
const AYSE_TOKEN = "dev:11111111-1111-1111-1111-111111111111";

/**
 * İki kapı, ikisi de inceleme bulgusundan (SC-010'un kendi senaryo sınıfı):
 *
 * 1. FAIL-EARLY — E2E_DATABASE_NAME eskiden ilk kez TEARDOWN'da doğrulanıyordu.
 *    Değişkensiz yerel koşuda testler önce API'ye dakikalarca veri yazıyor,
 *    temizlik en sonda fırlatıyor ve kalıntı (tipik olarak paylaşılan dev
 *    DB'de) geride kalıyordu — üstelik temizleyici o adı yerelde haklı olarak
 *    reddettiği için elle SQL gerekiyordu. Artık tek satır veri yazılmadan
 *    burada durulur.
 *
 * 2. KİMLİK DEĞİŞMEZİ — temizliğin baktığı DB ile API'nin yazdığı DB'nin aynı
 *    olduğunu hiçbir şey kanıtlamıyordu; yanlış ama desene uyan bir ad "0 ders
 *    silindi" ile yeşil biterdi. Nöbetçi ders API'den yaratılır, psql ile
 *    E2E_DATABASE_NAME içinde aranır; görünmüyorsa koşu başlamadan düşer.
 *    Nöbetçinin kodu koşu önekini taşıdığı için teardown onu da süpürür.
 */
export default async function globalSetup() {
  const requested = process.env.E2E_RUN_ID;
  const runId = requested ? validateE2eRunId(requested) : createE2eRunId();
  process.env.E2E_RUN_ID = runId;

  const databaseName = resolveE2eDatabaseName(undefined, process.env);

  const sentinel = createE2eCourseIdentity("NOBETCI", { runId });
  const response = await fetch(`${API}/courses`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${AYSE_TOKEN}`,
    },
    body: JSON.stringify({ code: sentinel.code, title: sentinel.title }),
  });
  if (!response.ok) {
    throw new Error(
      `E2E nöbetçi dersi yaratılamadı (${response.status}): API ${API} ayakta ve tohumlanmış mı?`,
    );
  }
  if (!courseVisibleInE2eDatabase(databaseName, sentinel.code)) {
    throw new Error(
      `Veritabanı kimlikleri ayrışmış: API ${API} nöbetçiyi yazdı ama ` +
        `${databaseName} içinde görünmüyor. E2E_DATABASE_NAME yanlış veritabanını gösteriyor; ` +
        "temizlik bu hâliyle sahte yeşil verirdi. Koşu durduruldu.",
    );
  }
  console.log(`[e2e] koşu kimliği: ${runId} · veritabanı doğrulandı: ${databaseName}`);
}
