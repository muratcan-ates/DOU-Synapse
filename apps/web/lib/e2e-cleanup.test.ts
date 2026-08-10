import { describe, expect, test } from "bun:test";

import { parseCleanupRows, resolveE2eDatabaseName } from "../e2e/cleanup";
import {
  createE2eCourseIdentity,
  isRunScopedE2eCourseCode,
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
    expect(() => resolveE2eDatabaseName("dou_synapse", { CI: "true" })).toThrow();
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
    expect(() => parseCleanupRows(["not-a-uuid", "E2E-abc123-1", "Başlık"].join("\t")))
      .toThrow();
  });
});
