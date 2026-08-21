import { describe, expect, it } from "bun:test";

import {
  E2E_COURSE_PREFIX,
  assertLocalCleanupTarget,
  cleanupSql,
} from "../e2e/global-teardown";

describe("E2E cleanup safety", () => {
  it("yalnız E2E test derslerinin iki işaretini birlikte arar", () => {
    const sql = cleanupSql(E2E_COURSE_PREFIX);
    expect(sql).toContain("code LIKE 'E2E%'");
    expect(sql).toContain("title LIKE 'E2E Test Dersi%'");
  });

  it("daha geniş bir öneki reddeder", () => {
    expect(() => cleanupSql("E")).toThrow("Güvensiz");
  });

  it("production ve uzak API hedeflerini fail-closed reddeder", () => {
    expect(() => assertLocalCleanupTarget("https://app.example.com", "local")).toThrow(
      "yalnız yerel",
    );
    expect(() => assertLocalCleanupTarget("http://localhost:8000", "production")).toThrow(
      "production",
    );
  });
});
