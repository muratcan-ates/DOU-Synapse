"use client";

import { useState } from "react";
import { ErrorNote, Loading } from "@/components/page-state";
import { Button } from "@/components/ui";
import { getLearningSummary, type LearningSummaryDays } from "@/lib/learning-events";
import { useResource } from "@/lib/use-resource";

/** Yalnız dersin toplamları gösterilir; hesap veya ham sohbet ayrıntısı yoktur. */
export function LearningSummaryPanel({ courseId }: { courseId: string }) {
  const [days, setDays] = useState<LearningSummaryDays>(7);
  return (
    <section aria-labelledby="learning-summary-title" className="border-b border-border pb-8">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 id="learning-summary-title" className="text-lg font-medium text-fg">Öğrenme özeti</h2>
          <p className="prose-tr mt-1 text-sm text-fg-muted">
            Konulara göre yanlış cevap, ipucu ve kaynak yetersizliği nedeniyle ret sayıları.
            Bu özet salt okunurdur; kişisel sohbet metinlerini içermez.
          </p>
        </div>
        <div role="group" aria-label="Öğrenme özeti dönemi" className="flex gap-2">
          {([7, 30] as const).map((period) => (
            <Button key={period} variant="secondary" className={days === period ? "font-semibold underline underline-offset-4" : ""} aria-pressed={days === period} onClick={() => setDays(period)}>
              Son {period} gün
            </Button>
          ))}
        </div>
      </div>
      <SummaryPeriod key={`${courseId}:${days}`} courseId={courseId} days={days} />
    </section>
  );
}

function SummaryPeriod({ courseId, days }: { courseId: string; days: LearningSummaryDays }) {
  const summary = useResource(() => getLearningSummary(courseId, days), [courseId, days]);
  if (summary.loading) return <Loading label="Öğrenme özeti yükleniyor…" />;
  // Son okuma reddedildiyse önbellekteki ders toplamları da gizlenir.
  if (summary.error || summary.refreshError) return <ErrorNote message={summary.error ?? summary.refreshError ?? ""} kind={summary.errorKind} requestId={summary.errorRequestId} onRetry={summary.reload} />;
  if (!summary.data) return null;
  const { topics, total_events: totalEvents } = summary.data;
  return (
    <div>
      <p className="mb-3 text-xs text-fg-muted">Son {days} günde {totalEvents.toLocaleString("tr-TR")} öğrenme olayı kaydedildi.</p>
      {topics.length === 0 ? (
        <p className="py-4 text-sm text-fg-muted">Bu dönemde özetlenecek öğrenme olayı yok. Öğrencilerin çalışma etkinlikleri burada görünecek.</p>
      ) : (
        <>
          <table className="hidden w-full text-left text-sm md:table">
            <caption className="sr-only">Son {days} günün konu bazlı öğrenme özeti</caption>
            <thead className="border-b border-border text-fg-muted">
              <tr>
                <th scope="col" className="py-3 pr-4 font-medium">Konu</th>
                <th scope="col" className="py-3 pr-4 font-medium">Yanlış cevap</th>
                <th scope="col" className="py-3 pr-4 font-medium">İpucu</th>
                <th scope="col" className="py-3 font-medium">Kaynak yetersizliği / ret</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {topics.map((topic) => (
                <tr key={topic.topic_id ?? "unassigned"}>
                  <th scope="row" className="py-3 pr-4 font-medium text-fg">{topic.topic_name}</th>
                  <td className="py-3 pr-4 font-mono text-fg">{topic.wrong_answers.toLocaleString("tr-TR")}</td>
                  <td className="py-3 pr-4 font-mono text-fg">{topic.hints_requested.toLocaleString("tr-TR")}</td>
                  <td className="py-3 font-mono text-fg">{topic.unsupported_refusals.toLocaleString("tr-TR")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <ul aria-label="Konu bazlı öğrenme özeti" className="divide-y divide-border border-y border-border md:hidden">
            {topics.map((topic) => (
              <li key={topic.topic_id ?? "unassigned"} className="py-4">
                <p className="text-sm font-medium text-fg">{topic.topic_name}</p>
                <dl className="mt-3 space-y-2 text-sm">
                  {([
                    ["Yanlış cevap", topic.wrong_answers],
                    ["İpucu", topic.hints_requested],
                    ["Kaynak yetersizliği / ret", topic.unsupported_refusals],
                  ] as const).map(([label, count]) => (
                    <div key={label} className="flex justify-between gap-4">
                      <dt className="text-fg-muted">{label}</dt>
                      <dd className="font-mono text-fg">{count.toLocaleString("tr-TR")}</dd>
                    </div>
                  ))}
                </dl>
              </li>
            ))}
          </ul>
        </>
      )}
      <Button variant="ghost" className="mt-3" onClick={() => void summary.reload()}>Özeti yenile</Button>
    </div>
  );
}
