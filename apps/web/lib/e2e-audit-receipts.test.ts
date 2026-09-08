import { describe, expect, test } from "bun:test";
import { readFileSync, readdirSync, rmSync } from "node:fs";
import { join } from "node:path";

import {
  AuditCapture, expectedAuditScope, initializeAuditCapture, loadAuditReceipts,
  receiptFromResponse, validateAuditDirectory, type AuditScope,
} from "../e2e/audit-receipts";

const scope: AuditScope = {
  version: 1, runId: "abc123xy", databaseName: "dou_synapse_e2e_s10",
  apiOrigin: "http://127.0.0.1:8018", targetId: "a".repeat(64),
};
const actorId = "11111111-1111-1111-1111-111111111111";
const id = "fedcba98765443218fedcba987654321";
const observation = {
  url: `${scope.apiOrigin}/admin/overview`, method: "GET",
  authorization: `Bearer dev:${actorId}`, status: 200, requestId: id,
};

function withDirectory(callback: (directory: string) => void): void {
  const directory = initializeAuditCapture(scope);
  try { callback(directory); }
  finally { rmSync(directory, { recursive: true }); }
}

describe("E2E audit yanıt sahipliği", () => {
  test("root hedef makbuzu yoksa fail-closed; API origin sınırı dardır", () => {
    expect(() => expectedAuditScope(scope.runId, scope.databaseName, {})).toThrow();
    expect(() => expectedAuditScope(scope.runId, scope.databaseName, {
      E2E_AUDIT_TARGET_ID: scope.targetId, E2E_API_URL: "https://name:secret@example.invalid",
    })).toThrow();
    expect(expectedAuditScope(scope.runId, scope.databaseName, {
      E2E_AUDIT_TARGET_ID: scope.targetId, E2E_API_URL: scope.apiOrigin,
    })).toEqual(scope);
  });

  test("yalnız gerçek origin/izinli rota ve sunucu v4 hex kimliği makbuz olur", () => {
    expect(receiptFromResponse(observation, scope.apiOrigin)).toEqual({
      requestId: id, actorId, action: "GET /admin/overview", result: "allowed",
    });
    expect(receiptFromResponse({ ...observation, status: 403 }, scope.apiOrigin)?.result).toBe("denied");
    expect(receiptFromResponse({ ...observation, url: "http://127.0.0.1:18018/admin/overview" }, scope.apiOrigin)).toBeNull();
    expect(receiptFromResponse({ ...observation, url: `${scope.apiOrigin}/courses` }, scope.apiOrigin)).toBeNull();
    for (const requestId of ["e2e-abc123-42-1", "Name_Student01234", "", undefined]) {
      expect(() => receiptFromResponse({ ...observation, requestId }, scope.apiOrigin)).toThrow();
    }
    expect(() => receiptFromResponse({ ...observation, status: 500 }, scope.apiOrigin)).toThrow();
    expect(() => receiptFromResponse({ ...observation, authorization: "Bearer secret" }, scope.apiOrigin)).toThrow();
  });

  test("aynı route.fetch/browser makbuzu tekilleşir; hiçbir ham başlık/sorgu saklanmaz", () => {
    withDirectory((directory) => {
      const capture = new AuditCapture(directory, scope);
      const key = {};
      capture.begin(key, observation.url, observation.method, observation.authorization);
      capture.record({ ...observation, url: `${observation.url}?private=SYNTHETIC_QUERY` }, key);
      capture.record(observation);
      capture.finish();
      expect(loadAuditReceipts(directory, scope)).toHaveLength(1);
      for (const name of readdirSync(join(directory, "receipts"))) {
        const raw = readFileSync(join(directory, "receipts", name), "utf8");
        expect(raw).not.toContain("Bearer");
        expect(raw).not.toContain("SYNTHETIC_QUERY");
        expect(raw).not.toContain("authorization");
      }
    });
  });

  test("ayrı koşu veya hedefteki makbuzlar temizlik yetkisine dönüşmez", () => {
    withDirectory((directory) => {
      for (const mismatch of [
        { ...scope, runId: "another123" },
        { ...scope, databaseName: "dou_synapse_e2e_other" },
        { ...scope, targetId: "b".repeat(64) },
        { ...scope, apiOrigin: "http://127.0.0.1:8019" },
      ]) expect(() => validateAuditDirectory(directory, mismatch)).toThrow();
    });
  });

  test("aynı aktörün iki koşusunda diğer koşunun dosyaları korunur", () => {
    const firstDirectory = initializeAuditCapture(scope);
    const otherScope = { ...scope, runId: "another123" };
    const secondDirectory = initializeAuditCapture(otherScope);
    try {
      const first = new AuditCapture(firstDirectory, scope);
      const second = new AuditCapture(secondDirectory, otherScope);
      first.record(observation);
      second.record({ ...observation, requestId: "12345678123442348234123456789abc" });
      first.finish(); second.finish();
      const before = loadAuditReceipts(secondDirectory, otherScope);
      expect(loadAuditReceipts(firstDirectory, scope).map((row) => row.requestId)).toEqual([id]);
      expect(loadAuditReceipts(secondDirectory, otherScope)).toEqual(before);
      expect(() => loadAuditReceipts(secondDirectory, scope)).toThrow();
    } finally {
      rmSync(firstDirectory, { recursive: true });
      rmSync(secondDirectory, { recursive: true });
    }
  });

  test("yanıt kaybı veya durmuş worker 0/0 yeşile dönüşemez", () => {
    withDirectory((directory) => {
      const capture = new AuditCapture(directory, scope);
      const key = {};
      capture.begin(key, observation.url, observation.method, observation.authorization);
      expect(() => loadAuditReceipts(directory, scope)).toThrow();
      capture.fail(key);
      expect(() => capture.finish()).toThrow();
      expect(() => loadAuditReceipts(directory, scope)).toThrow();
    });
  });

  test("aynı server-ID farklı aktör/sonuçla yeniden kullanılırsa reddedilir", () => {
    withDirectory((directory) => {
      const capture = new AuditCapture(directory, scope);
      capture.record(observation);
      capture.record({ ...observation, status: 403 });
      capture.finish();
      expect(() => loadAuditReceipts(directory, scope)).toThrow();
    });
  });

  test("Node fetch katkısı gerçek yanıtın gövdesini değiştirmeden makbuzu yazar", async () => {
    const directory = initializeAuditCapture(scope);
    const original = globalThis.fetch;
    try {
      globalThis.fetch = (async (input: RequestInfo | URL) => {
        expect(String(input)).toBe(observation.url);
        return new Response('{"error":{"code":"forbidden"}}', {
          status: 403, headers: { "X-Request-ID": id },
        });
      }) as unknown as typeof fetch;
      const capture = new AuditCapture(directory, scope);
      const response = await capture.fetch(observation.url, {
        headers: { Authorization: observation.authorization },
      });
      expect(response.status).toBe(403);
      expect(await response.json()).toEqual({ error: { code: "forbidden" } });
      capture.finish();
      expect(loadAuditReceipts(directory, scope)[0]?.result).toBe("denied");
    } finally {
      globalThis.fetch = original;
      rmSync(directory, { recursive: true });
    }
  });
});

test("bugünkü audit çağrı noktaları toplayıcıya bağlıdır; yeni literal rota inceleme ister", () => {
  // Kaynak envanteri ek nöbetçidir; dinamik URL çözümlemesi veya gerçek PG kanıtı değildir.
  const directory = join(import.meta.dir, "../e2e");
  const names = readdirSync(directory).filter((name) => name.endsWith(".spec.ts"));
  const users = names.filter((name) => /\/admin|\/openapi\.json/.test(
    readFileSync(join(directory, name), "utf8"),
  ));
  expect(users.sort()).toEqual(["admin-readiness.spec.ts", "portal.spec.ts"]);
  for (const name of users) {
    expect(readFileSync(join(directory, name), "utf8")).toContain('from "./audit-fixture"');
  }
  expect(readFileSync(join(directory, "portal.spec.ts"), "utf8"))
    .toContain('auditCapture.fetch(`${API}/admin/overview`');
  expect(readFileSync(join(directory, "admin-readiness.spec.ts"), "utf8"))
    .toContain("auditCapture.record({");
});


for (const mismatch of [
  { label: "başka origin", changed: { url: "http://127.0.0.1:18018/admin/overview" } },
  { label: "audit dışı rota", changed: { url: `${scope.apiOrigin}/courses` } },
  { label: "başka audit action", changed: { url: `${scope.apiOrigin}/admin/courses` } },
  { label: "başka sentetik aktör", changed: {
    authorization: "Bearer dev:22222222-2222-2222-2222-222222222222",
  } },
]) {
  test(`izlenen istek ${mismatch.label} yanıtıyla sessizce tamamlanmaz`, () => {
    withDirectory((directory) => {
      const capture = new AuditCapture(directory, scope);
      const key = {};
      capture.begin(key, observation.url, observation.method, observation.authorization);
      expect(() => capture.record({ ...observation, ...mismatch.changed }, key)).toThrow();
      expect(readdirSync(join(directory, "receipts"))).toEqual([]);
      expect(() => capture.finish()).toThrow();
      expect(() => loadAuditReceipts(directory, scope)).toThrow();
    });
  });
}

test("izlenmemiş kaynak olayı pending audit isteğini bozmaz veya tamamlamaz", () => {
  withDirectory((directory) => {
    const capture = new AuditCapture(directory, scope);
    const audited = {};
    const unrelated = {};
    capture.begin(audited, observation.url, observation.method, observation.authorization);
    capture.begin(unrelated, `${scope.apiOrigin}/courses`, "GET");
    capture.record({ url: `${scope.apiOrigin}/courses`, method: "GET", status: 200 }, unrelated);
    expect(readdirSync(join(directory, "receipts"))).toEqual([]);
    capture.record(observation, audited);
    capture.finish();
    expect(loadAuditReceipts(directory, scope)).toEqual([{
      requestId: id, actorId, action: "GET /admin/overview", result: "allowed",
    }]);
  });
});

test("audit fetch yönlendirmeyi reddeder ve yanıt kaybında incomplete kalır", async () => {
  const directory = initializeAuditCapture(scope);
  const original = globalThis.fetch;
  try {
    globalThis.fetch = (async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.redirect).toBe("error");
      throw new TypeError("sentetik yönlendirme reddi");
    }) as unknown as typeof fetch;
    const capture = new AuditCapture(directory, scope);
    await expect(capture.fetch(observation.url, {
      headers: { Authorization: observation.authorization }, redirect: "follow",
    })).rejects.toThrow("sentetik yönlendirme reddi");
    expect(readdirSync(join(directory, "receipts"))).toEqual([]);
    expect(() => capture.finish()).toThrow();
    expect(() => loadAuditReceipts(directory, scope)).toThrow();
  } finally {
    globalThis.fetch = original;
    rmSync(directory, { recursive: true });
  }
});

test("audit fetch farklı son URL yanıtını güvenilir makbuz saymaz", async () => {
  const directory = initializeAuditCapture(scope);
  const original = globalThis.fetch;
  try {
    globalThis.fetch = (async () => {
      const response = new Response("{}", { status: 200 });
      // Yalnız transport sonucu sözleşmesi: gerçek HTTP redirect deneyi değildir.
      Object.defineProperty(response, "url", { value: `${scope.apiOrigin}/courses` });
      return response;
    }) as unknown as typeof fetch;
    const capture = new AuditCapture(directory, scope);
    await expect(capture.fetch(observation.url, {
      headers: { Authorization: observation.authorization },
    })).rejects.toThrow("Audit yanıt makbuzu kaydedilemedi.");
    expect(() => capture.finish()).toThrow();
    expect(() => loadAuditReceipts(directory, scope)).toThrow();
  } finally {
    globalThis.fetch = original;
    rmSync(directory, { recursive: true });
  }
});

test("audit dışı fetch çağıranın redirect seçimini korur ve makbuz üretmez", async () => {
  const directory = initializeAuditCapture(scope);
  const original = globalThis.fetch;
  try {
    globalThis.fetch = (async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.redirect).toBe("follow");
      return new Response("[]", { status: 200 });
    }) as unknown as typeof fetch;
    const capture = new AuditCapture(directory, scope);
    const response = await capture.fetch(`${scope.apiOrigin}/courses`, { redirect: "follow" });
    expect(await response.json()).toEqual([]);
    capture.finish();
    expect(loadAuditReceipts(directory, scope)).toEqual([]);
  } finally {
    globalThis.fetch = original;
    rmSync(directory, { recursive: true });
  }
});
