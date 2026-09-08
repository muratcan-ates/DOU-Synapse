"use client";

import { answerVerdict, describeSolution, formatScore, SCORE_SCALE, sourceInfo, VERDICT_LABEL } from "@/lib/exam";
import { groundedMissingCriterion } from "@/lib/assessment-feedback";
import { sourceContextHref } from "@/lib/source-quality";
import type { AnswerFeedback } from "@/lib/types";
import { SourceCard } from "@/components/source-card";
import { Badge } from "@/components/ui";

export function FeedbackPanel({ courseId, feedback }: { courseId: string; feedback: AnswerFeedback }) {
  const verdict = answerVerdict(feedback);
  const spec = VERDICT_LABEL[verdict];
  const score = formatScore(feedback.score);
  const solution = describeSolution(feedback.solution);
  const missingCriterion = groundedMissingCriterion(feedback);

  return (
    <div className="mt-6 rounded-lg border border-border bg-surface p-5">
      <div className="flex flex-wrap items-center gap-3">
        {/* Renk tek başına bilgi taşımaz: rozetin metni her zaman vardır. */}
        <Badge tone={spec.tone}>{spec.label}</Badge>
        {/* Puan yoksa yazılmaz — "0" yazmak olmayan bir ölçümü iddia etmektir. */}
        {score && (
          <span className="font-mono text-sm text-fg">
            {score} / {SCORE_SCALE}
          </span>
        )}
      </div>

      {feedback.message && (
        <p className="prose-tr mt-3 text-sm text-fg">{feedback.message}</p>
      )}

      {feedback.missing_points && feedback.missing_points.length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs font-medium text-fg-muted">Eksik kalan noktalar</h3>
          <ul className="mt-2 space-y-1">
            {feedback.missing_points.map((point) => (
              <li key={point} className="prose-tr text-sm text-fg">
                {point}
              </li>
            ))}
          </ul>
        </div>
      )}

      {feedback.rubric_breakdown && feedback.rubric_breakdown.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <h3 className="mb-2 text-xs font-medium text-fg-muted">Rubrik ölçütleri</h3>
          <table className="w-full min-w-[480px] text-left text-sm">
            <thead className="border-b border-border text-xs text-fg-muted">
              <tr>
                <th className="py-2 pr-4 font-medium">Ölçüt</th>
                <th className="py-2 pr-4 font-medium">Ağırlık</th>
                <th className="py-2 pr-4 font-medium">Başarı</th>
                <th className="py-2 font-medium">Katkı</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {feedback.rubric_breakdown.map((item) => (
                <tr key={item.point}>
                  <td className="prose-tr py-2 pr-4 text-fg">{item.point}</td>
                  <td className="py-2 pr-4 font-mono text-fg-muted">%{item.weight}</td>
                  <td className="py-2 pr-4 font-mono text-fg-muted">%{item.score}</td>
                  <td className="py-2 font-mono text-fg">{item.earned}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Açıklama kaynaklıdır: "neden yanlış" gerçek bir chunk'a dayanır. */}
      {feedback.why_wrong && (
        <div className="mt-4">
          <h3 className="mb-2 text-xs font-medium text-fg-muted">Neden yanlış?</h3>
          <SourceCard source={sourceInfo(feedback.why_wrong)} />
        </div>
      )}

      {missingCriterion && <section aria-label="Eksik ölçütün dayanağı" className="mt-4 space-y-2">
        <h3 className="text-xs font-medium text-fg-muted">Eksik ölçütün dayanağı</h3>
        <p className="prose-tr text-sm text-fg">{missingCriterion.criterion}</p>
        <SourceCard source={sourceInfo(missingCriterion.source)} href={sourceContextHref(courseId, missingCriterion.source.chunk_id)} />
      </section>}

      {feedback.evidence && (
        <div className="mt-4">
          <h3 className="mb-2 text-xs font-medium text-fg-muted">Değerlendirmenin dayanağı</h3>
          <SourceCard source={sourceInfo(feedback.evidence)} />
        </div>
      )}

      {solution.length > 0 && (
        <dl className="mt-4 space-y-2 border-t border-border pt-4">
          {solution.map((line, position) => (
            <div key={`${line.label}-${position}`}>
              <dt className="text-xs text-fg-muted">{line.label}</dt>
              <dd className="prose-tr text-sm whitespace-pre-line text-fg">{line.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
