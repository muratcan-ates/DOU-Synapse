import { describe, expect, test } from "bun:test";
import {
  draftFromPolicy,
  payloadFromDraft,
  toggleMode,
  type CourseAiPolicy,
} from "./policy";

const policy: CourseAiPolicy = {
  course_id: "course",
  allowed_modes: null,
  hint_limit: null,
  evidence_threshold: null,
  daily_llm_budget: null,
  source_document_ids: null,
  effective: {
    allowed_modes: ["qa", "socratic"],
    hint_limit: 4,
    evidence_threshold: 0.81,
    daily_llm_budget: null,
    source_document_ids: null,
  },
  updated_by: null,
  updated_at: null,
  budget_used_today: 0,
  budget_remaining_today: null,
};

describe("ders AI politikası form sözleşmesi", () => {
  test("null alanları global varsayılan olarak korur", () => {
    const draft = draftFromPolicy(policy);
    expect(payloadFromDraft(draft)).toEqual({
      allowed_modes: null,
      hint_limit: null,
      evidence_threshold: null,
      daily_llm_budget: null,
      source_document_ids: null,
    });
  });

  test("boş kaynak seçimi tüm kaynaklardan farklıdır", () => {
    const draft = draftFromPolicy(policy);
    draft.allSources = false;
    draft.sourceDocumentIds = [];
    expect(payloadFromDraft(draft).source_document_ids).toEqual([]);
  });

  test("mod seçimi eklenir ve geri alınır", () => {
    expect(toggleMode(["qa"], "socratic")).toEqual(["qa", "socratic"]);
    expect(toggleMode(["qa", "socratic"], "qa")).toEqual(["socratic"]);
  });
});
