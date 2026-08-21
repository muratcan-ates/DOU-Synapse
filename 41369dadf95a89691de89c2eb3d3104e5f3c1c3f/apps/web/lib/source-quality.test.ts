import { describe, expect, test } from "bun:test";
import {
  EVIDENCE_LEVEL,
  formatRetrievalScore,
  sourceContextHref,
} from "./source-quality";

describe("kaynak bağlamı bağlantısı", () => {
  test("ders ve chunk kimliğini URL içinde güvenli taşır", () => {
    expect(sourceContextHref("ders/1", "chunk 2")).toBe(
      "/courses/ders%2F1/sources/chunk%202",
    );
  });
});

describe("retrieval karar sunumu", () => {
  test("üç backend kararının da ayrı etiketi ve açıklaması vardır", () => {
    expect(Object.keys(EVIDENCE_LEVEL).sort()).toEqual([
      "out_of_scope",
      "sufficient",
      "weak",
    ]);
    expect(new Set(Object.values(EVIDENCE_LEVEL).map((item) => item.label)).size).toBe(3);
    for (const item of Object.values(EVIDENCE_LEVEL)) {
      expect(item.explanation.length).toBeGreaterThan(20);
    }
  });

  test("ret kararı hata kırmızısına boyanmaz", () => {
    expect(EVIDENCE_LEVEL.weak.tone).toBe("warning");
    expect(EVIDENCE_LEVEL.out_of_scope.tone).toBe("neutral");
  });

  test("skorlar aynı hassasiyetle gösterilir", () => {
    expect(formatRetrievalScore(0.812345)).toBe("0.8123");
    expect(formatRetrievalScore(Number.NaN)).toBe("—");
  });
});
