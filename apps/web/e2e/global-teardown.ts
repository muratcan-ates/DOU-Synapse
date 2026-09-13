import { cleanupWorkerProfiles } from "./worker-profiles";
import { temizle } from "./cleanup";
import { requireE2eRunId } from "./fixtures";

export default async function globalTeardown() {
  const runId = requireE2eRunId();
  const result = await temizle({ onayli: true, runId });
  const deletedProfiles = cleanupWorkerProfiles();
  console.log(`[e2e] ${deletedProfiles} koşu/çalışan profili bağımlılık kalmadan temizlendi.`);
  console.log(
    `[e2e] ${runId} koşusundan ${result.deleted.length} ders ve ` +
      `${result.deletedAudits.length} yakalanmış audit makbuzu temizlendi. ` +
      "Kaybolan yanıtlar için root başlangıç/son kayıt muhasebesi ayrıca gereklidir.",
  );
}
