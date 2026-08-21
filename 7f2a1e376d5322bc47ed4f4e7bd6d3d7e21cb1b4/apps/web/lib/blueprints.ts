import type {
  BlueprintCell,
  LearningOutcome,
  Question,
  QuestionDifficulty,
  QuestionType,
} from "@/lib/types";

export interface BlueprintCellDraft {
  learning_outcome_id: string;
  difficulty: QuestionDifficulty;
  question_type: QuestionType;
  question_count: number;
  points_per_question: number;
}

export const DIFFICULTY_LABEL: Record<QuestionDifficulty, string> = {
  easy: "Kolay",
  medium: "Orta",
  hard: "Zor",
};

export const QUESTION_TYPE_LABEL: Record<QuestionType, string> = {
  mcq: "Çoktan seçmeli",
  open: "Açık uçlu",
  code_trace: "Kod izleme",
  bug_hunt: "Hata bulma",
};

export function emptyBlueprintCell(outcomes: readonly LearningOutcome[]): BlueprintCellDraft {
  return {
    learning_outcome_id: outcomes[0]?.id ?? "",
    difficulty: "medium",
    question_type: "mcq",
    question_count: 1,
    points_per_question: 10,
  };
}

export function blueprintDraftTotals(cells: readonly BlueprintCellDraft[]): {
  questions: number;
  points: number;
} {
  return cells.reduce(
    (total, cell) => ({
      questions: total.questions + cell.question_count,
      points: total.points + cell.question_count * cell.points_per_question,
    }),
    { questions: 0, points: 0 },
  );
}

export function questionMatchesCell(question: Question, cell: BlueprintCell): boolean {
  return (
    question.status === "approved" &&
    question.learning_outcome_id === cell.learning_outcome_id &&
    question.difficulty === cell.difficulty &&
    question.type === cell.question_type
  );
}

export function eligibleQuestions(
  questions: readonly Question[],
  cells: readonly BlueprintCell[],
): Question[] {
  return questions.filter((question) => cells.some((cell) => questionMatchesCell(question, cell)));
}

export function questionStem(question: Question): string {
  const value = question.payload.stem ?? question.payload.prompt;
  return typeof value === "string" && value.trim() ? value : "Soru metni okunamadı";
}
