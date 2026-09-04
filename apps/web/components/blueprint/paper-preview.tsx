"use client";

import { api } from "@/lib/api";
import { DIFFICULTY_LABEL, type ExamItem } from "@/lib/blueprint";
import { QUESTION_TYPE } from "@/lib/labels";
import { useResource } from "@/lib/use-resource";
import { ErrorNote, Loading } from "@/components/page-state";

/** Yayınlanmış kâğıdı incelemek düzenleme formunu açmaz. */
export function PaperPreview({ base }: { base: string }) {
  const items = useResource<ExamItem[]>(() => api.get(`${base}/items`), [base]);
  return (
    <section className="mt-4 rounded-lg border border-border bg-surface-sunken p-4" aria-label="Kâğıt önizlemesi">
      <h4 className="text-sm font-semibold text-fg">Kâğıt önizlemesi</h4>
      <p className="mt-1 text-xs text-fg-muted">Bu görünüm salt okunurdur.</p>
      {items.loading ? <div className="mt-3"><Loading label="Kâğıt yükleniyor…" /></div> : items.error ? (
        <ErrorNote message={items.error} onRetry={items.reload} />
      ) : (
        <>
          {items.refreshError && <ErrorNote message={items.refreshError} onRetry={items.reload} />}
          {items.data?.length === 0 ? <p className="mt-3 text-sm text-fg-muted">Bu sürüme henüz soru eklenmemiş.</p> : (
            <ol className="mt-3 divide-y divide-border">
              {(items.data ?? []).map((item) => (
                <li key={item.id} className="py-3">
                  <p className="prose-tr text-sm text-fg">{item.position}. {item.stem}</p>
                  <p className="mt-1 text-xs text-fg-muted">{QUESTION_TYPE[item.question_type]} · {item.points} puan{item.difficulty ? ` · ${DIFFICULTY_LABEL[item.difficulty]}` : ""}</p>
                </li>
              ))}
            </ol>
          )}
        </>
      )}
    </section>
  );
}
