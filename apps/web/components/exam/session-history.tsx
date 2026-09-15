"use client";

import { EXAM_MODE, examDate, examHistoryStatus, formatScore } from "@/lib/exam";
import type { ExamSession } from "@/lib/types";
import { usePagedResource } from "@/lib/use-paged-resource";
import { ErrorNote, Loading, LoadMore } from "@/components/page-state";
import { Badge, Button, Card, EmptyState } from "@/components/ui";

export function SessionHistory({ courseId, onOpen }: { courseId: string; onOpen: (id: string) => void }) {
  const history = usePagedResource<ExamSession>(`/courses/${courseId}/exams/history`, [courseId]);
  return (
    <section className="mt-10" aria-labelledby="exam-history-title">
      {/* Bölüm başlığı + sağda tek sessiz eylem (DESIGN.md §Aksan disiplini). */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="exam-history-title" className="text-xl font-semibold tracking-tight text-fg">Oturumlarım</h2>
        <Button variant="ghost" size="sm" aria-disabled={history.loading} onClick={() => void history.reload()}>Listeyi yenile</Button>
      </div>
      <p className="mt-1 text-sm text-fg-muted">Başka bir cihazda başladığınız oturumlara devam edebilir, tamamlanan sonuçları yeniden açabilirsiniz.</p>
      <div className="mt-4">
        {history.loading ? <Loading /> : history.error ? <ErrorNote message={history.error} onRetry={history.reload} /> : (
          <>
            {history.refreshError && <ErrorNote message={history.refreshError} onRetry={history.reload} />}
            {history.data?.length === 0 ? <EmptyState title="Bu derste henüz bir oturum başlatmadınız." /> : (
              /* Düz kart: satırlar yalnız saç çizgisiyle bölünür, ayraçlar kenara dayanır. */
              <Card variant="flat" padding="none">
                <ol className="divide-y divide-border">
                  {(history.data ?? []).map((session) => {
                    const state = examHistoryStatus(session);
                    const score = formatScore(session.score);
                    return (
                      <li key={session.id} className="flex flex-col gap-4 px-5 py-6 transition-colors hover:bg-surface-sunken sm:px-7 sm:flex-row sm:items-center sm:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="font-medium text-fg">{EXAM_MODE[session.mode].label}{session.attempt_no ? ` · ${session.attempt_no}. deneme` : ""}</h3>
                            <Badge tone={state.tone}>{state.label}</Badge>
                          </div>
                          <p className="mt-2 text-sm text-fg-muted"><time dateTime={session.started_at}>{examDate(session.started_at)}</time></p>
                          <p className="mt-1 text-sm tabular-nums text-fg-muted">{session.answered_count}/{session.question_count} soru cevaplandı{score !== null ? ` · Puan: ${score}/100` : ""}</p>
                        </div>
                        {/* Satır içi eylem: `Button size="sm"`, hedef alan satırın kendisidir. */}
                        <Button variant="secondary" size="sm" className="min-h-11 shrink-0 self-start" onClick={() => onOpen(session.id)}>{state.action}</Button>
                      </li>
                    );
                  })}
                </ol>
              </Card>
            )}
            <LoadMore hasMore={history.nextCursor !== null} busy={history.loadingMore} error={history.pageError} onLoadMore={() => void history.loadMore()} />
          </>
        )}
      </div>
    </section>
  );
}
