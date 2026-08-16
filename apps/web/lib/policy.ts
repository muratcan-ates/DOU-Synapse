import type { ChatMode } from "./types";

export interface EffectiveCoursePolicy {
  allowed_modes: ChatMode[];
  hint_limit: number;
  evidence_threshold: number;
  daily_llm_budget: number | null;
  source_document_ids: string[] | null;
  student_daily_token_budget: number;
  instructor_daily_token_budget: number;
  max_output_tokens: number;
  max_concurrent_requests: number;
}

export interface CourseAiPolicy {
  course_id: string;
  allowed_modes: ChatMode[] | null;
  hint_limit: number | null;
  evidence_threshold: number | null;
  daily_llm_budget: number | null;
  source_document_ids: string[] | null;
  student_daily_token_budget: number;
  instructor_daily_token_budget: number;
  max_output_tokens: number;
  max_concurrent_requests: number;
  effective: EffectiveCoursePolicy;
  updated_by: string | null;
  updated_at: string | null;
  budget_used_today: number;
  budget_remaining_today: number | null;
}

export interface PolicyDraft {
  inheritModes: boolean;
  allowedModes: ChatMode[];
  inheritHints: boolean;
  hintLimit: number;
  inheritEvidence: boolean;
  evidenceThreshold: number;
  useCourseHardCap: boolean;
  dailyBudget: number;
  studentDailyTokenBudget: number;
  instructorDailyTokenBudget: number;
  maxOutputTokens: number;
  maxConcurrentRequests: number;
  allSources: boolean;
  sourceDocumentIds: string[];
}

export interface CourseAiPolicyPayload {
  allowed_modes: ChatMode[] | null;
  hint_limit: number | null;
  evidence_threshold: number | null;
  daily_llm_budget: number | null;
  source_document_ids: string[] | null;
  student_daily_token_budget: number;
  instructor_daily_token_budget: number;
  max_output_tokens: number;
  max_concurrent_requests: number;
}

export function draftFromPolicy(policy: CourseAiPolicy): PolicyDraft {
  return {
    inheritModes: policy.allowed_modes === null,
    allowedModes: policy.allowed_modes ?? policy.effective.allowed_modes,
    inheritHints: policy.hint_limit === null,
    hintLimit: policy.hint_limit ?? policy.effective.hint_limit,
    inheritEvidence: policy.evidence_threshold === null,
    evidenceThreshold:
      policy.evidence_threshold ?? policy.effective.evidence_threshold,
    useCourseHardCap: policy.daily_llm_budget === null,
    dailyBudget:
      policy.daily_llm_budget ?? policy.effective.daily_llm_budget ?? 500_000,
    studentDailyTokenBudget: policy.student_daily_token_budget,
    instructorDailyTokenBudget: policy.instructor_daily_token_budget,
    maxOutputTokens: policy.max_output_tokens,
    maxConcurrentRequests: policy.max_concurrent_requests,
    allSources: policy.source_document_ids === null,
    sourceDocumentIds:
      policy.source_document_ids ?? policy.effective.source_document_ids ?? [],
  };
}

export function payloadFromDraft(draft: PolicyDraft): CourseAiPolicyPayload {
  return {
    allowed_modes: draft.inheritModes ? null : draft.allowedModes,
    hint_limit: draft.inheritHints ? null : draft.hintLimit,
    evidence_threshold: draft.inheritEvidence
      ? null
      : draft.evidenceThreshold,
    daily_llm_budget: draft.useCourseHardCap ? null : draft.dailyBudget,
    source_document_ids: draft.allSources ? null : draft.sourceDocumentIds,
    student_daily_token_budget: draft.studentDailyTokenBudget,
    instructor_daily_token_budget: draft.instructorDailyTokenBudget,
    max_output_tokens: draft.maxOutputTokens,
    max_concurrent_requests: draft.maxConcurrentRequests,
  };
}

export function courseHardCapLabel(
  configuredBudget: number | null,
  effectiveBudget: number | null,
): string {
  if (configuredBudget !== null || effectiveBudget === null) {
    return "Platformun etkin ders üst sınırını kullan";
  }
  return `Platformun etkin ders üst sınırını kullan (${effectiveBudget.toLocaleString("tr-TR")} token/gün)`;
}

export function toggleMode(modes: ChatMode[], mode: ChatMode): ChatMode[] {
  return modes.includes(mode)
    ? modes.filter((candidate) => candidate !== mode)
    : [...modes, mode];
}
