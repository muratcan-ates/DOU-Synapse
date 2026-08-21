import { describe, expect, test } from "bun:test";
import {
  blueprintDraftTotals,
  eligibleQuestions,
  questionMatchesCell,
  type BlueprintCellDraft,
} from "@/lib/blueprints";
import type { BlueprintCell, Question } from "@/lib/types";

const cell: BlueprintCell = {
  id: "cell-1",
  learning_outcome_id: "outcome-1",
  difficulty: "hard",
  question_type: "mcq",
  question_count: 2,
  points_per_question: 15,
  label: "C1 · Zor · Çoktan seçmeli",
};

function question(overrides: Partial<Question> = {}): Question {
  return {
    id: "question-1",
    course_id: "course-1",
    topic_id: "topic-1",
    learning_outcome_id: "outcome-1",
    difficulty: "hard",
    type: "mcq",
    payload: { stem: "Deadlock nedir?" },
    status: "approved",
    created_by: null,
    reviewed_by: null,
    reviewed_at: null,
    created_at: "2026-08-10T00:00:00Z",
    source_stale: false,
    ...overrides,
  };
}

describe("blueprint saf kuralları", () => {
  test("soru yalnız çıktı, zorluk ve tipin üçü de hücreyle eşleşince seçilebilir", () => {
    expect(questionMatchesCell(question(), cell)).toBe(true);
    expect(questionMatchesCell(question({ difficulty: "easy" }), cell)).toBe(false);
    expect(questionMatchesCell(question({ status: "draft" }), cell)).toBe(false);
  });

  test("uygun havuz yalnız yayın kapısını doldurabilecek onaylı soruları taşır", () => {
    const matching = question();
    const wrongOutcome = question({ id: "question-2", learning_outcome_id: "outcome-2" });
    expect(eligibleQuestions([matching, wrongOutcome], [cell])).toEqual([matching]);
  });

  test("taslak toplamı soru adedi ile soru başı puanı çarpar", () => {
    const cells: BlueprintCellDraft[] = [
      {
        learning_outcome_id: "o1",
        difficulty: "easy",
        question_type: "mcq",
        question_count: 2,
        points_per_question: 10,
      },
      {
        learning_outcome_id: "o2",
        difficulty: "hard",
        question_type: "open",
        question_count: 1,
        points_per_question: 30,
      },
    ];
    expect(blueprintDraftTotals(cells)).toEqual({ questions: 3, points: 50 });
  });
});
