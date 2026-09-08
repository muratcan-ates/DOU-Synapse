"use client";

import { useState } from "react";
import { Button } from "@/components/ui";
import { ErrorNote, Loading } from "@/components/page-state";
import { api } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import { POLICY_HISTORY_PAGE_SIZE, policyFieldChanges, policyHistoryActor, policyHistoryDate, policyHistoryPath, policyHistoryTitle, type PolicyHistoryEntry } from "@/lib/policy-history";

interface Props { courseId: string; viewerId: string | null; documentNames: ReadonlyMap<string, string> }

export function PolicyHistory(props: Props) {
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  return (
    <section aria-labelledby="policy-history-title" className="border-t border-border pt-8">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="policy-history-title" className="text-lg font-medium text-fg">Politika geçmişi</h2>
          <p className="mt-1 text-sm text-fg-muted">Kaydedilen değişiklikleri önceki ve yeni değerleriyle inceleyin.</p>
        </div>
        <Button variant="ghost" onClick={() => { setOffset(0); setRefresh((value) => value + 1); }}>Geçmişi yenile</Button>
      </div>
      {offset > 0 && <Button variant="ghost" className="mb-3" onClick={() => setOffset((value) => Math.max(0, value - POLICY_HISTORY_PAGE_SIZE))}>Daha yeni kayıtlar</Button>}
      <HistoryPage key={`${props.courseId}:${offset}:${refresh}`} {...props} offset={offset} older={() => setOffset((value) => value + POLICY_HISTORY_PAGE_SIZE)} />
    </section>
  );
}

function HistoryPage({ courseId, viewerId, documentNames, offset, older }: Props & { offset: number; older: () => void }) {
  const history = useResource(() => api.get<PolicyHistoryEntry[]>(policyHistoryPath(courseId, offset)), [courseId, offset]);
  if (history.loading) return <Loading label="Politika geçmişi yükleniyor…" />;
  if (history.error) return <ErrorNote message={history.error} kind={history.errorKind ?? undefined} requestId={history.errorRequestId} onRetry={() => void history.reload()} />;
  const rows = history.data ?? [];
  return (
    <>
      {rows.length === 0 ? <p className="py-4 text-sm text-fg-muted">{offset === 0 ? "Henüz politika değişikliği kaydedilmedi." : "Daha eski kayıt bulunmuyor."}</p> : (
        <ol aria-label="Politika kayıtları" className="divide-y divide-border border-y border-border">
          {rows.slice(0, POLICY_HISTORY_PAGE_SIZE).map((entry, index) => {
            const changes = policyFieldChanges(entry, documentNames);
            return (
              <li key={entry.id}>
                <details>
                  <summary aria-label={`Politika kaydı ${offset + index + 1}`} className="min-h-11 cursor-pointer py-4 text-sm text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">
                    <span className="font-medium">{policyHistoryTitle(entry)}</span>
                    <span className="mt-1 block text-xs text-fg-muted sm:ml-4 sm:inline">{policyHistoryDate(entry.changed_at)} · {policyHistoryActor(entry.changed_by, viewerId)}</span>
                  </summary>
                  {changes.length === 0 ? <p className="pb-4 text-sm text-fg-muted">Değerler değişmeden kaydedildi.</p> : (
                    <dl className="space-y-4 pb-5">
                      {changes.map((change) => <div key={change.field} className="grid gap-1 text-sm sm:grid-cols-[minmax(10rem,1fr)_2fr]">
                        <dt className="font-medium text-fg">{change.label}</dt>
                        <dd className="min-w-0 break-words text-fg-muted"><p>Önce: {change.before}</p><p className="mt-1 text-fg">Sonra: {change.after}</p></dd>
                      </div>)}
                    </dl>
                  )}
                </details>
              </li>
            );
          })}
        </ol>
      )}
      {rows.length > POLICY_HISTORY_PAGE_SIZE && <Button variant="secondary" className="mt-4" onClick={older}>Daha eski kayıtlar</Button>}
    </>
  );
}
