import { describe, expect, test } from "bun:test";
import {
  cellKey,
  editingNoticeFor,
  hasDuplicateCells,
  readinessCounts,
  splitByShares,
  totalPoints,
  totalQuestions,
  type Blueprint,
  type BlueprintCellInput,
  type Readiness,
} from "@/lib/blueprint";

/**
 * Blueprint çekirdeğinin saf kararları. Ekranın kendisi ağa ve `useResource`'a
 * bağlı; ölçülmesi gereken aritmetik ise saf ve burada.
 */

function cell(overrides: Partial<BlueprintCellInput> = {}): BlueprintCellInput {
  return {
    learning_outcome_id: "co-1",
    difficulty: "easy",
    question_type: "mcq",
    question_count: 2,
    points_per_question: 5,
    ...overrides,
  };
}

describe("splitByShares", () => {
  test("yüzdeler tam bölünürse beklenen adetleri verir", () => {
    expect(splitByShares(10, [40, 40, 20])).toEqual([4, 4, 2]);
  });

  test("yuvarlama artığında bile toplam TAM tutar", () => {
    // Math.round ile 3+3+3=9 çıkardı ve bir soru buharlaşırdı.
    const counts = splitByShares(10, [33, 33, 34]);
    expect(counts.reduce((a, b) => a + b, 0)).toBe(10);
    expect(counts).toEqual([3, 3, 4]);
  });

  test("7 soruda %40/%40/%20 toplamı korur", () => {
    const counts = splitByShares(7, [40, 40, 20]);
    expect(counts.reduce((a, b) => a + b, 0)).toBe(7);
  });

  test("sıfır toplam ya da boş pay güvenli davranır", () => {
    expect(splitByShares(0, [50, 50])).toEqual([0, 0]);
    expect(splitByShares(10, [])).toEqual([]);
    expect(splitByShares(10, [0, 0])).toEqual([0, 0]);
  });
});

describe("türetmeler", () => {
  test("toplam soru ve puan hücrelerden türetilir", () => {
    const cells = [cell({ question_count: 3, points_per_question: 4 }), cell({
      difficulty: "hard",
      question_count: 2,
      points_per_question: 10,
    })];

    expect(totalQuestions(cells)).toBe(5);
    expect(totalPoints(cells)).toBe(3 * 4 + 2 * 10);
  });

  test("aynı (çıktı, zorluk, tip) üçlüsü çift hücre sayılır", () => {
    expect(hasDuplicateCells([cell(), cell({ question_count: 9 })])).toBe(true);
    expect(hasDuplicateCells([cell(), cell({ difficulty: "hard" })])).toBe(false);
  });

  test("hücre anahtarı üç ekseni birden taşır", () => {
    expect(cellKey(cell())).toBe("co-1|easy|mcq");
  });
});

describe("readinessCounts", () => {
  test("eksik hücre ile sınıflandırılmamış kalem AYRI sayılır", () => {
    const readiness: Readiness = {
      ready: false,
      missing_cells: [
        {
          learning_outcome_id: "co-1",
          difficulty: "easy",
          question_type: "mcq",
          required: 2,
          filled: 1,
          label: "CO1 · kolay · çoktan seçmeli hücresi 2 soru istiyor, 1 tane var (eksik).",
        },
      ],
      unclassified_items: [
        {
          question_id: "q-9",
          position: 3,
          missing_fields: ["difficulty"],
          label: "3. soru sınıflandırılmamış: zorluk seviyesi atanmamış.",
        },
      ],
      message: "Sınav bu hâliyle yayınlanamaz.",
    };

    expect(readinessCounts(readiness)).toEqual({
      missing: 1,
      unclassified: 1,
      blocked: true,
    });
  });

  test("rapor yokken kapı kapalı sayılmaz", () => {
    expect(readinessCounts(null)).toEqual({ missing: 0, unclassified: 0, blocked: false });
  });
});

describe("editingNoticeFor", () => {
  function blueprint(published: number | null): Blueprint {
    return {
      id: "bp-1",
      course_id: "c-1",
      title: "Vize",
      description: null,
      duration_minutes: 60,
      max_attempts: 1,
      opens_at: null,
      closes_at: null,
      created_at: "2026-08-10T00:00:00Z",
      updated_at: "2026-08-10T00:00:00Z",
      cells: [],
      total_questions: 0,
      total_points: 0,
      topic_distribution: [],
      published_version_no: published,
    };
  }

  test("yayınlanmış sürüm varken düzenlemenin kanıtı bozmadığı söylenir", () => {
    const notice = editingNoticeFor(blueprint(2));
    expect(notice).toContain("2. sürüm yayında");
    expect(notice).toContain("dondurdu");
  });

  test("yayınlanmış sürüm yoksa uyarı da yok", () => {
    expect(editingNoticeFor(blueprint(null))).toBeNull();
  });
});
