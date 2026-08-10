import { createE2eRunId, validateE2eRunId } from "./fixtures";

export default async function globalSetup() {
  const requested = process.env.E2E_RUN_ID;
  const runId = requested ? validateE2eRunId(requested) : createE2eRunId();
  process.env.E2E_RUN_ID = runId;
  console.log(`[e2e] koşu kimliği: ${runId}`);
}
