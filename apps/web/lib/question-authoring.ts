import type { Difficulty, LearningOutcome } from "@/lib/blueprint";
import type { Question, QuestionDraftRequest } from "@/lib/types";

export interface Classification {
  learningOutcomeId: string;
  difficulty: Difficulty | "";
}

export const EMPTY_CLASSIFICATION: Classification = { learningOutcomeId: "", difficulty: "" };

/** Course-wide outcomes are valid for every topic. The API remains authoritative. */
export function outcomesForTopic(outcomes: LearningOutcome[], topicId: string): LearningOutcome[] {
  return outcomes.filter((outcome) => outcome.topic_id === null || outcome.topic_id === topicId);
}

export function classificationComplete(value: Classification): boolean {
  return Boolean(value.learningOutcomeId) === Boolean(value.difficulty);
}

interface EditableOption extends Record<string, unknown> { key: string; text: string }
interface EditableCriterion extends Record<string, unknown> { point: string; weight: string }

export interface QuestionDraftForm extends Classification {
  stem: string;
  options: EditableOption[];
  answerKey: string;
  distractorSources: Record<string, string>;
  explanation: string;
  keyPoints: string;
  rubric: EditableCriterion[];
  acceptedAnswers: string;
  language: string;
  code: string;
  bugLine: string;
  bugType: string;
  fixSummary: string;
}

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown> : {};
}
function text(value: unknown): string { return typeof value === "string" ? value : ""; }
function stringList(value: unknown): string {
  return Array.isArray(value) ? value.filter((item) => typeof item === "string").join("\n") : "";
}
function lines(value: string): string[] {
  return value.split("\n").map((line) => line.trim()).filter(Boolean);
}

/** Editable fields are separate from the original payload, which is never mutated. */
export function createDraftForm(question: Question): QuestionDraftForm {
  const payload = question.payload;
  const bug = record(payload.answer_key);
  return {
    learningOutcomeId: question.learning_outcome_id ?? "",
    difficulty: question.difficulty ?? "",
    stem: text(question.type === "mcq" ? payload.stem : payload.prompt),
    options: Array.isArray(payload.options) ? payload.options.map((value) => {
      const option = record(value);
      return { ...option, key: text(option.key), text: text(option.text) };
    }) : [],
    answerKey: text(payload.answer_key),
    distractorSources: Object.fromEntries(Object.entries(record(payload.distractor_sources))
      .filter((entry): entry is [string, string] => typeof entry[1] === "string")),
    explanation: text(payload.explanation),
    keyPoints: stringList(payload.key_points),
    rubric: Array.isArray(payload.rubric) ? payload.rubric.map((value) => {
      const criterion = record(value);
      return { ...criterion, point: text(criterion.point), weight: String(criterion.weight ?? "") };
    }) : [],
    acceptedAnswers: stringList(payload.accepted_answers),
    language: text(payload.language),
    code: text(payload.code),
    bugLine: typeof bug.line === "number" ? String(bug.line) : "",
    bugType: text(bug.bug_type),
    fixSummary: text(bug.fix_summary),
  };
}

/** Source choices come only from the question's existing references, never typed IDs. */
export function draftSourceChoices(question: Question): { id: string; label: string }[] {
  const choices = new Map<string, string>();
  if (question.source) {
    choices.set(question.source.chunk_id, `${question.source.file_name} · ${question.source.location}`);
  }
  for (const [key, id] of Object.entries(record(question.payload.distractor_sources))) {
    if (typeof id === "string" && !choices.has(id)) choices.set(id, `${key} şıkkının mevcut kaynağı`);
  }
  return Array.from(choices, ([id, label]) => ({ id, label }));
}

/** Legacy criteria have no stable identity for safely moving their extra fields. */
export function rubricHasLegacyMetadata(question: Question): boolean {
  return Array.isArray(question.payload.rubric) && question.payload.rubric.some((item) =>
    Object.keys(record(item)).some((key) => key !== "point" && key !== "weight"));
}

/** Yeni kod sorusu yazımı için ön kontrol; son doğrulama her zaman API'dedir. */
export function codeRubricIssue(question: Pick<Question, "type">, rubric: QuestionDraftForm["rubric"]): string | null {
  if (question.type !== "code_trace" && question.type !== "bug_hunt") return null;
  if (rubric.length === 0) return "Kaydetmek için en az bir puanlama ölçütü ekleyin.";
  if (rubric.length > 12) return "En fazla 12 puanlama ölçütü ekleyebilirsiniz.";
  const points = rubric.map((item) => item.point.trim().toLowerCase());
  if (points.some((point) => !point)) return "Her ölçütün neyi değerlendirdiğini yazın.";
  if (new Set(points).size !== points.length) return "Her puanlama ölçütü farklı olmalı.";
  const weights = rubric.map((item) => Number(item.weight));
  if (weights.some((weight) => !Number.isInteger(weight) || weight < 1 || weight > 100)) {
    return "Her ölçüte 1 ile 100 arasında tam sayı puan verin.";
  }
  if (weights.reduce((sum, weight) => sum + weight, 0) !== 100) return "Ölçüt puanlarının toplamı 100 olmalı.";
  return null;
}

export function changeCorrectOption(
  form: QuestionDraftForm, answerKey: string, sourceId: string | undefined,
): QuestionDraftForm {
  const sources = { ...form.distractorSources };
  for (const option of form.options) {
    if (option.key !== answerKey) sources[option.key] = form.distractorSources[option.key] ?? sourceId ?? "";
  }
  return { ...form, answerKey, distractorSources: sources };
}

/** Replace only exposed fields; preserve source/pedagogy metadata on every payload type. */
export function buildDraftRequest(question: Question, form: QuestionDraftForm): QuestionDraftRequest {
  const payload = { ...question.payload };
  if (question.type === "mcq") {
    payload.stem = form.stem;
    payload.options = form.options.map((option) => ({ ...option }));
    payload.answer_key = form.answerKey;
    payload.distractor_sources = Object.fromEntries(form.options
      .filter((option) => option.key !== form.answerKey)
      .map((option) => [option.key, form.distractorSources[option.key] ?? ""]));
  } else {
    payload.prompt = form.stem;
    if (question.type === "bug_hunt") {
      payload.answer_key = { ...record(payload.answer_key), line: Number(form.bugLine),
        bug_type: form.bugType, fix_summary: form.fixSummary };
    } else payload.answer_key = form.answerKey;
  }
  if (question.type === "open") {
    payload.key_points = lines(form.keyPoints);
    payload.accepted_answers = lines(form.acceptedAnswers);
  } else payload.explanation = form.explanation || null;
  if (question.type === "open" || question.type === "code_trace" || question.type === "bug_hunt") {
    payload.rubric = form.rubric.map((item) => ({ ...item, weight: Number(item.weight) }));
  }
  if (question.type === "code_trace" || question.type === "bug_hunt") {
    payload.language = form.language;
    payload.code = form.code;
  }
  return { payload, learning_outcome_id: form.learningOutcomeId || null,
    difficulty: form.difficulty || null };
}
