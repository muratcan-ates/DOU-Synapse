import { describe, expect, test } from "bun:test";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import {
  auditCandidateSql,
  parseApiEventRows,
  parseAuditRows,
  parseCleanupRows,
  parseRequestManifest,
  resolveE2eDatabaseName,
  settleApiEventCleanup,
  waitForApiEventBarrier,
} from "../e2e/cleanup";
import {
  assertE2eRequestIdRecorderHealthy,
  createE2eCourseIdentity,
  e2eRequestIdFailureMarkerPath,
  e2eRequestManifestPath,
  fetchE2eApi,
  isRunScopedE2eCourseCode,
  recordE2eApiRequestFailure,
  recordE2eApiResponseRequestId,
  recordE2eServerRequestId,
  validateE2eServerRequestId,
  validateE2eRunId,
} from "../e2e/fixtures";

describe("E2E test verisi sınırları", () => {
  test("ders kodu koşu kimliğine bağlı ve yeniden üretilebilir desendedir", () => {
    const first = createE2eCourseIdentity("PORTAL", {
      runId: "abc123xy",
      processId: 42,
    });
    const second = createE2eCourseIdentity("PORTAL", {
      runId: "abc123xy",
      processId: 42,
    });

    expect(first.code).toMatch(/^E2E-abc123xy-[0-9]+$/);
    expect(second.code).not.toBe(first.code);
    expect(isRunScopedE2eCourseCode(first.code, "abc123xy")).toBe(true);
    expect(isRunScopedE2eCourseCode(first.code, "baska123")).toBe(false);
  });

  test("koşu kimliği enjeksiyon ve geniş desenleri reddeder", () => {
    expect(() => validateE2eRunId("abc123")).not.toThrow();
    expect(() => validateE2eRunId("abc'; drop table courses; --")).toThrow();
    expect(() => validateE2eRunId("kisa")).toThrow();
  });

  test("yerelde paylaşılan ve sistem veritabanları fail-closed reddedilir", () => {
    expect(() => resolveE2eDatabaseName(undefined, {})).toThrow();
    expect(() => resolveE2eDatabaseName("postgres", {})).toThrow();
    expect(() => resolveE2eDatabaseName("dou_synapse", {})).toThrow();
    expect(() =>
      resolveE2eDatabaseName("dou_synapse", { CI: "true" }),
    ).toThrow();
    expect(resolveE2eDatabaseName("dou_synapse_preview_portal_1", {})).toBe(
      "dou_synapse_preview_portal_1",
    );
    expect(
      resolveE2eDatabaseName("dou_synapse", {
        CI: "true",
        GITHUB_ACTIONS: "true",
      }),
    ).toBe("dou_synapse");
  });

  test("psql çıktısı yalnız beklenen üç alan ve UUID ile kabul edilir", () => {
    const row = [
      "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      "E2E-abc123-42000",
      "E2E Test Dersi",
    ].join("\t");
    expect(parseCleanupRows(row)).toEqual([
      {
        id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        code: "E2E-abc123-42000",
        title: "E2E Test Dersi",
      },
    ]);
    expect(() =>
      parseCleanupRows(["not-a-uuid", "E2E-abc123-1", "Başlık"].join("\t")),
    ).toThrow();
  });

  test("Bilgi İşlem audit izi yalnız manifestteki sunucu kodlarıyla temizlenir", () => {
    const requestId = "a".repeat(32);
    const deniedRequestId = "b".repeat(32);
    const row = [
      [
        "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        requestId,
        "GET /admin/overview",
        "allowed",
      ].join("\t"),
      [
        "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        deniedRequestId,
        "POST /admin/api-events/query",
        "denied",
      ].join("\t"),
    ].join("\n");

    expect(parseAuditRows(row)).toEqual([
      {
        id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        requestId,
        action: "GET /admin/overview",
        result: "allowed",
      },
      {
        id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        requestId: deniedRequestId,
        action: "POST /admin/api-events/query",
        result: "denied",
      },
    ]);
    expect(() =>
      parseAuditRows(
        [
          "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
          "production-request",
          "GET /admin/overview",
          "allowed",
        ].join("\t"),
      ),
    ).toThrow();
    expect(parseRequestManifest(`${requestId}\n${requestId}\n`)).toEqual([
      requestId,
    ]);
    expect(() => parseRequestManifest("e2e-abc123xy-42-000\n")).toThrow();
    expect(auditCandidateSql([requestId])).toBe(
      `request_id IN ('${requestId}')`,
    );
    expect(auditCandidateSql([])).toBe("FALSE");
    expect(
      e2eRequestManifestPath("abc123xy", {
        E2E_ARTIFACT_DIR: "/tmp/e2e-artifacts",
      }),
    ).toBe("/tmp/e2e-artifacts/request-ids-abc123xy.txt");

    expect(
      parseApiEventRows(
        [
          "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
          requestId,
          "/courses/{course_id}",
          "200",
        ].join("\t"),
      ),
    ).toEqual([
      {
        id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        requestId,
        routeTemplate: "/courses/{course_id}",
        statusCode: 200,
      },
    ]);
  });

  test("sunucu request kimliği eksik, büyük harfli veya biçimsizse reddedilir", () => {
    expect(() => validateE2eServerRequestId(undefined)).toThrow();
    expect(() => validateE2eServerRequestId(null)).toThrow();
    expect(() => validateE2eServerRequestId("A".repeat(32))).toThrow();
    expect(() => validateE2eServerRequestId("a".repeat(31))).toThrow();
    expect(() => recordE2eServerRequestId("not-a-server-id")).toThrow();
  });

  test("Node fetch kaydedicisi eksik ve geçersiz header için marker bırakır", () => {
    const artifactDirectory = mkdtempSync(join(tmpdir(), "dou-e2e-node-id-"));
    const runId = "abc123xy";
    const env = {
      E2E_ARTIFACT_DIR: artifactDirectory,
      E2E_RUN_ID: runId,
    };

    try {
      expect(() => recordE2eServerRequestId(undefined, { runId, env })).toThrow(
        "X-Request-ID",
      );
      expect(
        readFileSync(e2eRequestIdFailureMarkerPath(runId, env), "utf8"),
      ).toBe("server-request-id-validation-failed\n");

      expect(() =>
        recordE2eServerRequestId("A".repeat(32), { runId, env }),
      ).toThrow("X-Request-ID");
      const marker = readFileSync(
        e2eRequestIdFailureMarkerPath(runId, env),
        "utf8",
      );
      expect(marker).toBe(
        "server-request-id-validation-failed\n" +
          "server-request-id-validation-failed\n",
      );
      expect(existsSync(e2eRequestManifestPath(runId, env))).toBe(false);
      expect(marker).not.toContain("A".repeat(32));
      expect(() => assertE2eRequestIdRecorderHealthy(runId, env)).toThrow(
        "manifest korunarak",
      );
    } finally {
      rmSync(artifactDirectory, { force: true, recursive: true });
    }
  });

  test("tarayıcı kaydedicisi yalnız API originini izler ve mahrem marker ile kapanır", () => {
    const artifactDirectory = mkdtempSync(
      join(tmpdir(), "dou-e2e-request-id-"),
    );
    const runId = "abc123xy";
    const env = {
      E2E_API_URL: "http://localhost:8017",
      E2E_ARTIFACT_DIR: artifactDirectory,
      E2E_RUN_ID: runId,
    };

    try {
      expect(
        recordE2eApiResponseRequestId(
          {
            url: "http://localhost:3117/_next/static/chunk.js",
            method: "GET",
            requestId: undefined,
          },
          { runId, env },
        ),
      ).toBe(false);
      expect(existsSync(e2eRequestManifestPath(runId, env))).toBe(false);
      expect(existsSync(e2eRequestIdFailureMarkerPath(runId, env))).toBe(false);
      expect(
        recordE2eApiResponseRequestId(
          {
            url: "http://localhost:8017/courses",
            method: "OPTIONS",
            requestId: undefined,
          },
          { runId, env },
        ),
      ).toBe(false);
      expect(existsSync(e2eRequestIdFailureMarkerPath(runId, env))).toBe(false);
      expect(
        recordE2eApiRequestFailure(
          { url: "http://localhost:8017/courses", method: "OPTIONS" },
          { runId, env },
        ),
      ).toBe(false);
      expect(existsSync(e2eRequestIdFailureMarkerPath(runId, env))).toBe(false);

      const requestId = "c".repeat(32);
      expect(
        recordE2eApiResponseRequestId(
          {
            url: "http://localhost:8017/courses?limit=1",
            method: "GET",
            requestId,
          },
          { runId, env },
        ),
      ).toBe(true);
      expect(readFileSync(e2eRequestManifestPath(runId, env), "utf8")).toBe(
        `${requestId}\n`,
      );

      expect(() =>
        recordE2eApiResponseRequestId(
          {
            url: "http://localhost:8017/courses/private?token=secret",
            method: "GET",
            requestId: undefined,
          },
          { runId, env },
        ),
      ).toThrow("X-Request-ID");
      const marker = readFileSync(
        e2eRequestIdFailureMarkerPath(runId, env),
        "utf8",
      );
      expect(marker).toBe("server-request-id-validation-failed\n");
      expect(marker).not.toContain("http");
      expect(marker).not.toContain("courses");
      expect(marker).not.toContain("secret");
      expect(() => assertE2eRequestIdRecorderHealthy(runId, env)).toThrow(
        "manifest korunarak",
      );
    } finally {
      rmSync(artifactDirectory, { force: true, recursive: true });
    }
  });

  test("yanıtsız API isteği URL taşımayan marker ile teardown'u kapatır", () => {
    const artifactDirectory = mkdtempSync(
      join(tmpdir(), "dou-e2e-failed-api-"),
    );
    const runId = "abc123xy";
    const env = {
      E2E_API_URL: "http://localhost:8017",
      E2E_ARTIFACT_DIR: artifactDirectory,
      E2E_RUN_ID: runId,
    };

    try {
      expect(() =>
        recordE2eApiRequestFailure(
          {
            url: "http://localhost:8017/courses/private?token=secret",
            method: "POST",
          },
          { runId, env },
        ),
      ).toThrow("fail-closed");
      const marker = readFileSync(
        e2eRequestIdFailureMarkerPath(runId, env),
        "utf8",
      );
      expect(marker).toBe("server-request-id-validation-failed\n");
      expect(marker).not.toContain("http");
      expect(marker).not.toContain("courses");
      expect(marker).not.toContain("secret");
      expect(() => assertE2eRequestIdRecorderHealthy(runId, env)).toThrow(
        "manifest korunarak",
      );
    } finally {
      rmSync(artifactDirectory, { force: true, recursive: true });
    }
  });

  test("Node API fetch header gelmeden düşerse privacy-safe marker bırakır", async () => {
    const artifactDirectory = mkdtempSync(
      join(tmpdir(), "dou-e2e-node-fetch-"),
    );
    const runId = "abc123xy";
    const env = {
      E2E_API_URL: "http://localhost:8017",
      E2E_ARTIFACT_DIR: artifactDirectory,
      E2E_RUN_ID: runId,
    };

    try {
      await expect(
        fetchE2eApi(
          "http://localhost:8017/courses/private?token=secret",
          { method: "POST" },
          {
            runId,
            env,
            fetcher: async () => {
              throw new Error("socket closed with secret response");
            },
          },
        ),
      ).rejects.toThrow("fail-closed");
      const marker = readFileSync(
        e2eRequestIdFailureMarkerPath(runId, env),
        "utf8",
      );
      expect(marker).toBe("server-request-id-validation-failed\n");
      expect(marker).not.toContain("secret");
      expect(marker).not.toContain("courses");
    } finally {
      rmSync(artifactDirectory, { force: true, recursive: true });
    }
  });

  test("global teardown marker kapısını ağ ve silme işlerinden önce çalıştırır", () => {
    const source = readFileSync(
      join(import.meta.dir, "../e2e/global-teardown.ts"),
      "utf8",
    );
    const markerGate = source.indexOf(
      "assertE2eRequestIdRecorderHealthy(runId)",
    );
    const collectorProbe = source.indexOf("apiEventBarrierRequestId(runId)");
    const cleanup = source.indexOf("await temizle({");

    expect(markerGate).toBeGreaterThan(-1);
    expect(collectorProbe).toBeGreaterThan(markerGate);
    expect(cleanup).toBeGreaterThan(collectorProbe);
  });

  test("FIFO bariyeri tam request kimliği görünene kadar bounded poll yapar", async () => {
    const requestId = "d".repeat(32);
    const snapshots = [false, false, true];
    const seen: string[] = [];
    let pauses = 0;

    await waitForApiEventBarrier(
      requestId,
      {
        pause: async () => {
          pauses += 1;
        },
        exists: (candidate) => {
          seen.push(candidate);
          return snapshots.shift() ?? false;
        },
      },
      5,
    );

    expect(seen).toEqual([requestId, requestId, requestId]);
    expect(pauses).toBe(2);
  });

  test("FIFO bariyer timeout'u ve geçersiz kimlik manifest koruyan hata verir", async () => {
    let pauses = 0;
    await expect(
      waitForApiEventBarrier(
        "e".repeat(32),
        {
          pause: async () => {
            pauses += 1;
          },
          exists: () => false,
        },
        3,
      ),
    ).rejects.toThrow("manifest korunarak");
    expect(pauses).toBe(2);

    await expect(
      waitForApiEventBarrier(
        "INVALID",
        { pause: async () => undefined, exists: () => true },
        1,
      ),
    ).rejects.toThrow("X-Request-ID");
  });

  test("iki persist timeout'undan sonra gelen API olayı üç boş turdan önce kaçmaz", async () => {
    const requestId = "a".repeat(32);
    const lateEvent = {
      id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
      requestId,
      routeTemplate: "/courses/{course_id}",
      statusCode: 200,
    };
    // Olay ilk 2.5 sn yok; ikinci poll'da (~5 sn) commit oluyor. Eski iki-boş
    // algoritması tam bu olay görünmeden dönüp manifesti silebiliyordu.
    const snapshots = [[], [lateEvent], [], [], []];
    const removed: (typeof lateEvent)[] = [];

    const result = await settleApiEventCleanup(
      [],
      {
        pause: async () => undefined,
        list: () => snapshots.shift() ?? [],
        remove: (events) => {
          removed.push(...events);
          return events;
        },
      },
      6,
    );

    expect(result.listed).toEqual([lateEvent]);
    expect(result.deleted).toEqual([lateEvent]);
    expect(removed).toEqual([lateEvent]);
    expect(snapshots).toEqual([]);
  });

  test("kuyruk bounded tur içinde sakinleşmezse manifest silmeye izin vermez", async () => {
    const event = {
      id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
      requestId: "b".repeat(32),
      routeTemplate: "/courses",
      statusCode: 201,
    };

    await expect(
      settleApiEventCleanup(
        [event],
        {
          pause: async () => undefined,
          list: () => [event],
          remove: (events) => events,
        },
        3,
      ),
    ).rejects.toThrow("bounded bekleme");
  });
});
