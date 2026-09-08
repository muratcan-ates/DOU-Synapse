import type { AnswerFeedback, GroundedMissingCriterion } from "@/lib/types";

/** Yalnız sunucunun açıkladığı, puanlanmış eksik ölçütü gösterir; kaynak veya teşhis üretmez. */
export function groundedMissingCriterion(feedback: AnswerFeedback): GroundedMissingCriterion | null {
  if (!feedback.graded || typeof feedback.score !== "number" ||
    !Number.isFinite(feedback.score) || feedback.score < 0 || feedback.score > 100) return null;
  const claim = feedback.grounded_missing_criterion;
  if (!claim?.criterion.trim() || !claim.source?.chunk_id || !claim.source.snippet.trim()) return null;
  const matching = (feedback.rubric_breakdown ?? []).filter(row => row.point === claim.criterion);
  if (matching.length !== 1) return null;
  const score = matching[0].score;
  if (typeof score !== "number" || !Number.isFinite(score) || score < 0 || score >= 100) return null;
  return claim;
}
