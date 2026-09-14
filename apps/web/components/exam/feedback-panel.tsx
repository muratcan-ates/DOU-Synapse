"use client";

import { answerVerdict, describeSolution, formatScore, SCORE_SCALE, sourceInfo, VERDICT_LABEL } from "@/lib/exam";
import { groundedMissingCriterion, groundedNextHint, sameSourceRef } from "@/lib/assessment-feedback";
import { sourceContextHref } from "@/lib/source-quality";
import type { AnswerFeedback } from "@/lib/types";
import { SourceCard } from "@/components/source-card";
import { Badge, Card } from "@/components/ui";

/**
 * Puanlanmamış cevabın açıklaması. Abstention hata değildir: kırmızı yok,
 * `role="alert"` yok, nötr metin (DESIGN.md §Abstention).
 */
const UNGRADED_NOTICE = "Bu cevap kaynağa bağlanamadığı için puanlanmadı.";

export function FeedbackPanel({ courseId, sessionId, feedback }: { courseId: string; sessionId: string; feedback: AnswerFeedback }) {
  const verdict = answerVerdict(feedback);
  const spec = VERDICT_LABEL[verdict];
  const score = formatScore(feedback.score);
  /*
   * Puan ve kaynak blokları yalnız puanlanmış cevapta çizilir. Karar ALAN
   * üzerinden verilir: `graded === false` (değerlendirme tamamlanamadı) ya da
   * `score == null` (puan yok). Sunucunun `message` metnine string eşleme
   * yapılmaz; metin değişse de karar bozulmaz.
   */
  const scored = feedback.graded && feedback.score != null;
  /*
   * "recorded" (sınav modunda sonuç bitişe kadar gizli) kaynağa bağlanamama
   * değildir: rozet zaten "Cevabınız kaydedildi" der, açıklama yazılmaz.
   */
  const ungraded = !feedback.graded || (feedback.score == null && verdict !== "recorded");
  const solution = describeSolution(feedback.solution);
  const whyWrong = scored ? feedback.why_wrong ?? null : null;
  const evidence = scored ? feedback.evidence ?? null : null;
  const missingCriterion = scored ? groundedMissingCriterion(feedback) : null;
  const nextHint = scored ? groundedNextHint(feedback) : null;
  const whyWrongTitle = nextHint && feedback.is_correct === true
    ? "Yanıtını geliştirmek için kaynak" : "Neden yanlış?";
  const hintSharesSource = nextHint && sameSourceRef(nextHint.source, whyWrong);
  // Yeni ipucunun aynı alıntısını bir kez göster; eski kanıt alanlarının sunumu korunur.
  const evidenceSharesSource = nextHint && (sameSourceRef(evidence, whyWrong) ||
    sameSourceRef(evidence, nextHint.source));

  return (
    <Card className="mt-6">
      <div className="flex flex-wrap items-center gap-3">
        {/* Renk tek başına bilgi taşımaz: rozetin metni her zaman vardır. */}
        <Badge tone={spec.tone}>{spec.label}</Badge>
        {/* Puan yoksa yazılmaz — "0" yazmak olmayan bir ölçümü iddia etmektir. */}
        {scored && score !== null && (
          <p className="leading-none tabular-nums">
            <span className="text-2xl font-semibold tracking-tight text-fg">{score}</span>
            <span className="text-sm text-fg-muted"> / {SCORE_SCALE}</span>
          </p>
        )}
      </div>

      {feedback.message && (
        <p className="prose-tr mt-3 text-sm text-fg">{feedback.message}</p>
      )}

      {ungraded && (
        <p className="prose-tr mt-3 text-sm text-fg-muted">{UNGRADED_NOTICE}</p>
      )}

      {/*
        Açıklama kaynaklıdır: "neden yanlış" gerçek bir chunk'a dayanır. Kaynak
        kartı ürünün imza bileşenidir (DESIGN.md), bu yüzden mesajın hemen
        altında ve öne çıkan başlıkla durur; rubrik ve eksik noktalar onu izler.
      */}
      {whyWrong && (
        <section aria-label={whyWrongTitle} className="mt-5">
          <h3 className="mb-2 text-sm font-semibold text-fg">{whyWrongTitle}</h3>
          <SourceCard source={sourceInfo(whyWrong)} href={sourceContextHref(courseId, whyWrong.chunk_id)} learningContext={{ courseId, sessionId, chunkId: whyWrong.chunk_id }} />
        </section>
      )}

      {feedback.missing_points && feedback.missing_points.length > 0 && (
        <div className="mt-5">
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

      {scored && feedback.rubric_breakdown && feedback.rubric_breakdown.length > 0 && (
        <div className="mt-5 overflow-x-auto">
          <h3 className="mb-2 text-xs font-medium text-fg-muted">Rubrik ölçütleri</h3>
          <table className="w-full min-w-[480px] divide-y divide-border text-left text-sm">
            <thead className="text-xs text-fg-muted">
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
                  <td className="py-2 pr-4 tabular-nums text-fg-muted">%{item.weight}</td>
                  <td className="py-2 pr-4 tabular-nums text-fg-muted">%{item.score}</td>
                  <td className="py-2 tabular-nums text-fg">{item.earned}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {nextHint && (
        <section aria-label="Sonraki adım için ipucu" className="mt-5 space-y-2">
          <h3 className="text-xs font-medium text-fg-muted">Sonraki adım için ipucu</h3>
          <p className="prose-tr text-sm whitespace-pre-line text-fg">{nextHint.text}</p>
          {!hintSharesSource && <SourceCard source={sourceInfo(nextHint.source)} href={sourceContextHref(courseId, nextHint.source.chunk_id)} learningContext={{ courseId, sessionId, chunkId: nextHint.source.chunk_id }} />}
        </section>
      )}

      {missingCriterion && <section aria-label="Eksik ölçütün dayanağı" className="mt-5 space-y-2">
        <h3 className="text-xs font-medium text-fg-muted">Eksik ölçütün dayanağı</h3>
        <p className="prose-tr text-sm text-fg">{missingCriterion.criterion}</p>
        <SourceCard source={sourceInfo(missingCriterion.source)} href={sourceContextHref(courseId, missingCriterion.source.chunk_id)} learningContext={{ courseId, sessionId, chunkId: missingCriterion.source.chunk_id }} />
      </section>}

      {evidence && !evidenceSharesSource && (
        <div className="mt-5">
          <h3 className="mb-2 text-xs font-medium text-fg-muted">Değerlendirmenin dayanağı</h3>
          <SourceCard source={sourceInfo(evidence)} href={sourceContextHref(courseId, evidence.chunk_id)} learningContext={{ courseId, sessionId, chunkId: evidence.chunk_id }} />
        </div>
      )}

      {solution.length > 0 && (
        <dl className="mt-5 space-y-2 border-t border-border pt-4">
          {solution.map((line, position) => (
            <div key={`${line.label}-${position}`}>
              <dt className="text-xs text-fg-muted">{line.label}</dt>
              <dd className="prose-tr text-sm whitespace-pre-line text-fg">{line.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </Card>
  );
}
