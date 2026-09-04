"use client";

import Link from "next/link";
import { useState } from "react";
import { blueprintVersionHref, VERSION_STATUS_LABEL } from "@/lib/blueprint";
import type { QuestionExamUsage } from "@/lib/types";
import { usePagedResource } from "@/lib/use-paged-resource";
import { ErrorNote, Loading, LoadMore } from "@/components/page-state";
import { Button } from "@/components/ui";

export function QuestionExamUsage({ courseId, questionId }: { courseId: string; questionId: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mb-4">
      <Button variant="secondary" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
        {open ? "Etkilenen sınavları gizle" : "Etkilenen sınavları göster"}
      </Button>
      {open && <UsageList key={questionId} courseId={courseId} questionId={questionId} />}
    </div>
  );
}

function UsageList({ courseId, questionId }: { courseId: string; questionId: string }) {
  const usage = usePagedResource<QuestionExamUsage>(`/courses/${courseId}/questions/${questionId}/exam-usage`, [courseId, questionId]);
  if (usage.loading) return <div className="mt-3"><Loading label="Etkilenen sınavlar yükleniyor…" /></div>;
  if (usage.error) return <div className="mt-3"><ErrorNote message={usage.error} onRetry={usage.reload} /></div>;
  return (
    <div className="mt-3 border-y border-border py-3">
      <p className="prose-tr text-xs text-fg-muted">Bu soruyu kullanan sürümler aşağıdadır. Yayımlanmış kâğıt değişmez; güncel soru için yeni bir sürüm hazırlayın.</p>
      {usage.refreshError && <ErrorNote message={usage.refreshError} onRetry={usage.reload} />}
      {usage.data?.length === 0 ? <p className="mt-3 text-sm text-fg-muted">Bu soru henüz bir sınav sürümünde kullanılmıyor.</p> : (
        <ul className="mt-2 divide-y divide-border">
          {(usage.data ?? []).map((item) => (
            <li key={item.id} className="py-2">
              <Link href={blueprintVersionHref(courseId, item.blueprint_id, item.version_id)}
                className="inline-flex min-h-11 items-center rounded-lg py-2 text-sm text-brand underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">
                {item.title} · {item.version_no}. sürüm · {VERSION_STATUS_LABEL[item.status]}
              </Link>
            </li>
          ))}
        </ul>
      )}
      <LoadMore hasMore={usage.nextCursor !== null} busy={usage.loadingMore} error={usage.pageError} onLoadMore={() => void usage.loadMore()} />
    </div>
  );
}
