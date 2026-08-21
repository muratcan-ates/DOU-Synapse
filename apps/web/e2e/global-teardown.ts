import { temizle } from "./cleanup";
import {
  assertE2eRequestIdRecorderHealthy,
  fetchE2eApi,
  recordE2eServerRequestId,
  requireE2eRunId,
} from "./fixtures";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const AYSE_TOKEN = "dev:11111111-1111-1111-1111-111111111111";
const ACTIVE_COLLECTOR_STATUSES = new Set(["healthy", "degraded"]);
const INACTIVE_COLLECTOR_STATUSES = new Set(["disabled", "stopped"]);

function collectorStatusOf(payload: unknown): string {
  if (!payload || typeof payload !== "object") {
    throw new Error("API event toplayıcı durum yanıtı geçersiz.");
  }
  const collector = (payload as { collector?: unknown }).collector;
  if (!collector || typeof collector !== "object") {
    throw new Error("API event toplayıcı durum yanıtı geçersiz.");
  }
  const status = (collector as { status?: unknown }).status;
  if (
    typeof status !== "string" ||
    (!ACTIVE_COLLECTOR_STATUSES.has(status) &&
      !INACTIVE_COLLECTOR_STATUSES.has(status))
  ) {
    throw new Error("API event toplayıcı durum yanıtı geçersiz.");
  }
  return status;
}

async function apiEventBarrierRequestId(
  runId: string,
): Promise<string | undefined> {
  const headers = {
    Authorization: `Bearer ${AYSE_TOKEN}`,
    "Content-Type": "application/json",
  };
  const statusResponse = await fetchE2eApi(`${API}/admin/api-events/query`, {
    method: "POST",
    headers,
    body: JSON.stringify({ window_minutes: 15, limit: 1, offset: 0 }),
    signal: AbortSignal.timeout(10_000),
  });
  recordE2eServerRequestId(statusResponse.headers.get("x-request-id"), {
    runId,
  });
  if (!statusResponse.ok) {
    throw new Error(
      `API event toplayıcı durumu okunamadı (${statusResponse.status}).`,
    );
  }
  const status = collectorStatusOf(await statusResponse.json());
  if (INACTIVE_COLLECTOR_STATUSES.has(status)) return undefined;

  // GET /courses gözlemlenen bir endpoint'tir. FIFO kuyruğunda bu isteğin
  // kalıcı satırını görmek, ondan önce gönderilmiş tüm test olaylarını kapsar.
  const barrierResponse = await fetchE2eApi(`${API}/courses?limit=1`, {
    headers: { Authorization: `Bearer ${AYSE_TOKEN}` },
    signal: AbortSignal.timeout(10_000),
  });
  const barrierRequestId = recordE2eServerRequestId(
    barrierResponse.headers.get("x-request-id"),
    { runId },
  );
  await barrierResponse.arrayBuffer();
  if (!barrierResponse.ok) {
    throw new Error(
      `API event bariyer isteği başarısız (${barrierResponse.status}).`,
    );
  }
  return barrierRequestId;
}

export default async function globalTeardown() {
  const runId = requireE2eRunId();
  assertE2eRequestIdRecorderHealthy(runId);
  const barrierRequestId = await apiEventBarrierRequestId(runId);
  const result = await temizle({
    onayli: true,
    runId,
    apiEventBarrierRequestId: barrierRequestId,
  });
  console.log(
    `[e2e] ${runId} koşusundan ${result.deleted.length} ders ve ` +
      `${result.deletedAudits.length} audit, ${result.deletedApiEvents.length} ` +
      "API event kaydı temizlendi.",
  );
}
