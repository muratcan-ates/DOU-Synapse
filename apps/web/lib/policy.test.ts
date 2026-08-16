import { describe, expect, test } from "bun:test";
import {
  courseHardCapLabel,
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
  student_daily_token_budget: 15_000,
  instructor_daily_token_budget: 45_000,
  max_output_tokens: 900,
  max_concurrent_requests: 2,
  effective: {
    allowed_modes: ["qa", "socratic"],
    hint_limit: 4,
    evidence_threshold: 0.81,
    daily_llm_budget: 431_000,
    source_document_ids: null,
    student_daily_token_budget: 15_000,
    instructor_daily_token_budget: 45_000,
    max_output_tokens: 900,
    max_concurrent_requests: 2,
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
      student_daily_token_budget: 15_000,
      instructor_daily_token_budget: 45_000,
      max_output_tokens: 900,
      max_concurrent_requests: 2,
    });
  });

  test("rol bazlı kota alanlarını tam PUT gövdesinde kaybetmeden taşır", () => {
    const draft = draftFromPolicy(policy);
    expect(payloadFromDraft(draft)).toMatchObject({
      student_daily_token_budget: 15_000,
      instructor_daily_token_budget: 45_000,
      max_output_tokens: 900,
      max_concurrent_requests: 2,
    });
  });

  test("null ders bütçesini sınırsız değil etkin platform tavanı olarak sunar", () => {
    const draft = draftFromPolicy(policy);
    expect(draft.useCourseHardCap).toBe(true);
    expect(draft.dailyBudget).toBe(431_000);
    expect(
      courseHardCapLabel(
        policy.daily_llm_budget,
        policy.effective.daily_llm_budget,
      ),
    ).toBe(
      "Platformun etkin ders üst sınırını kullan (431.000 token/gün)",
    );
    expect(courseHardCapLabel(null, null)).not.toContain("Sınırsız");
  });

  test("özel ders bütçesini platform tavanı gibi etiketlemez", () => {
    expect(courseHardCapLabel(10_000, 10_000)).toBe(
      "Platformun etkin ders üst sınırını kullan",
    );
    expect(courseHardCapLabel(10_000, 10_000)).not.toContain("10.000");
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
