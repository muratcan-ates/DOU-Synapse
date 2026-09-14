import type { AnswerFeedback, GroundedMissingCriterion, GroundedNextHint, SourceRef } from "@/lib/types";

/** Aynı parça kimliği tek başına yetmez; farklı alıntı ve konumlar görünür kalır. */
export function sameSourceRef(left: SourceRef | null | undefined, right: SourceRef | null | undefined): boolean {
  return !!left && !!right && left.chunk_id === right.chunk_id &&
    left.file_name === right.file_name && left.location === right.location &&
    left.snippet === right.snippet;
}

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

/** Eksik puan ve doğrulanmış kaynak yoksa yeni bir çalışma önerisi türetmez. */
export function groundedNextHint(feedback: AnswerFeedback): GroundedNextHint | null {
  if (!feedback.graded || typeof feedback.is_correct !== "boolean" ||
    typeof feedback.score !== "number" || !Number.isFinite(feedback.score) ||
    feedback.score < 0 || feedback.score >= 100) return null;
  const hint = feedback.next_hint;
  if (!feedback.why_wrong?.chunk_id || !feedback.why_wrong.snippet.trim() ||
    !hint?.text.trim() || !hint.source?.chunk_id || !hint.source.snippet.trim() ||
    hint.source.chunk_id !== feedback.why_wrong.chunk_id) return null;
  return hint;
}
