import { describe, expect, test } from "bun:test";

import {
  assertAuditOwnership,
  auditCandidateSql,
  deleteAuditSql,
  parseAuditRows,
  parseCleanupRows,
  resolveE2eDatabaseName,
} from "../e2e/cleanup";
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

  test("audit satırı sunucu UUID ve bilinen sentetik aktörle ayrıştırılır", () => {
    const requestId = "fedcba98765443218fedcba987654321";
    const actorId = "11111111-1111-1111-1111-111111111111";
    const id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
    const row = [id, requestId, "GET /admin/overview", "allowed", actorId].join("\t");
    expect(parseAuditRows(row)).toEqual([
      { id, requestId, actorId, action: "GET /admin/overview", result: "allowed" },
    ]);
    expect(() => parseAuditRows(row.replace(requestId, "e2e-abc123-42-1"))).toThrow();
  });

  test("başka koşu ve korunan audit aynı aktörde bile silme kümesine giremez", () => {
    const owned = { requestId: "fedcba98765443218fedcba987654321",
      actorId: "11111111-1111-1111-1111-111111111111",
      action: "GET /admin/overview", result: "allowed" as const };
    const ownRow = { ...owned, id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb" };
    const other = { ...owned, requestId: "12345678123442348234123456789abc" };
    const protectedRow = { ...other, id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc" };
    expect(() => assertAuditOwnership([ownRow], [owned])).not.toThrow();
    expect(() => assertAuditOwnership([protectedRow], [owned])).toThrow();
    expect(() => deleteAuditSql([ownRow, protectedRow], [owned])).toThrow();
    expect(() => assertAuditOwnership([], [owned])).toThrow();
    const sql = deleteAuditSql([ownRow], [owned]);
    expect(sql).toContain(ownRow.id);
    expect(sql).toContain(owned.requestId);
    expect(sql).toContain(owned.actorId);
    expect(sql).not.toContain(protectedRow.id);
    expect(sql).not.toContain(other.requestId);
    expect(sql).not.toContain("created_at");
    expect(auditCandidateSql([])).toBe("FALSE");
    expect(() => deleteAuditSql([], [])).toThrow();
  });
});
