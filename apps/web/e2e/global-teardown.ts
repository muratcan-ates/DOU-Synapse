import { temizle } from "./cleanup";
import { requireE2eRunId } from "./fixtures";

export default async function globalTeardown() {
  const runId = requireE2eRunId();
  const result = await temizle({ onayli: true, runId });
  console.log(`[e2e] ${runId} koşusundan ${result.deleted.length} ders temizlendi.`);
}
