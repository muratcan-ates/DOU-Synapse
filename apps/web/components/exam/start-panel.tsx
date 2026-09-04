"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { EXAM_MODE, examDate, isEmptyPool } from "@/lib/exam";
import { examStateChanged } from "@/lib/chat-availability";
import type { ExamCatalog, ExamMode, ExamSession, ExamStartRequest, Topic } from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { useSubmit } from "@/lib/use-submit";
import { Field } from "@/components/field";
import { ErrorNote, Loading, PageHeader } from "@/components/page-state";
import { Button, Card, EmptyState } from "@/components/ui";
import { SessionHistory } from "@/components/exam/session-history";

export function StartPanel({ courseId, catalog, onRefreshCatalog, onStarted }: {
  courseId: string;
  catalog: ExamCatalog;
  onRefreshCatalog: () => Promise<void>;
  onStarted: (id: string) => void;
}) {
  const [topicId, setTopicId] = useState("");
  const [failure, setFailure] = useState<{ message: string; emptyPool: boolean } | null>(null);
  const loadTopics = useCallback(() => catalog.enabled
    ? api.get<Topic[]>(`/courses/${courseId}/topics`) : Promise.resolve([]), [catalog.enabled, courseId]);
  const topics = useResource(loadTopics, [catalog.enabled, courseId]);
  const [starting, setStarting] = useState<string | null>(null);
  const { busy, submit: start } = useSubmit(async (request: ExamStartRequest, key: string) => {
    setStarting(key);
    setFailure(null);
    try {
      const session = await api.post<ExamSession>(`/courses/${courseId}/exams`, request);
      examStateChanged();
      onStarted(session.id);
    } catch (error) {
      setFailure({ message: errorMessage(error), emptyPool: !request.blueprint_id && isEmptyPool(error) });
      if (request.blueprint_id) await onRefreshCatalog();
    } finally {
      setStarting(null);
    }
  });

  return (
    <>
      <PageHeader title="Sınav provası" description={catalog.enabled ? "Onaylanmış sorularla çalışın, yayımlanmış sınavlara katılın ve önceki oturumlarınıza dönün." : "Sorular soru havuzundaki onaylanmış sorulardan seçilir. Boş bırakılan sorular yanlış sayılmaz."} />
      <div className="grid gap-4 sm:grid-cols-2">
        {(Object.keys(EXAM_MODE) as ExamMode[]).map((mode) => (
          <Card key={mode}>
            <h2 className="text-lg font-medium text-fg">{EXAM_MODE[mode].label}</h2>
            <p className="prose-tr mt-1 text-sm text-fg-muted">{EXAM_MODE[mode].description}</p>
            {mode === "practice" && catalog.enabled && (
              <div className="mt-4">
                {topics.loading ? <Loading label="Konular yükleniyor…" /> : topics.error ? (
                  <ErrorNote message={topics.error} onRetry={topics.reload} />
                ) : (
                  <Field label="Çalışma konusu">
                    {(control) => (
                      <select {...control} value={topicId} onChange={(event) => setTopicId(event.target.value)}
                        disabled={busy} className="h-11 w-full min-w-0 rounded-lg border border-border-strong bg-surface px-3 text-sm text-fg focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand">
                        <option value="">Tüm konular</option>
                        {(topics.data ?? []).map((topic) => <option key={topic.id} value={topic.id}>{topic.name}</option>)}
                      </select>
                    )}
                  </Field>
                )}
              </div>
            )}
            <div className="mt-4">
              <Button variant={mode === "practice" ? "primary" : "secondary"} aria-disabled={busy}
                onClick={() => void start({ mode, ...(mode === "practice" && catalog.enabled && topicId ? { topic_id: topicId } : {}) }, mode)}>
                {starting === mode ? "Başlatılıyor…" : `${EXAM_MODE[mode].label} başlat`}
              </Button>
            </div>
          </Card>
        ))}
      </div>
      {failure && <div className="mt-4">{failure.emptyPool
        ? <EmptyState title={failure.message} /> : <ErrorNote message={failure.message} />}</div>}

      {catalog.enabled && (
        <>
          <section className="mt-10" aria-labelledby="open-exams-title">
            <h2 id="open-exams-title" className="text-lg font-medium text-fg">Şu anda açık sınavlar</h2>
            <p className="mt-1 text-sm text-fg-muted">Eğitmeninizin yayımladığı sınavlar ve kalan deneme haklarınız.</p>
            {catalog.items.length === 0 ? (
              <p className="mt-4 border-t border-border py-4 text-sm text-fg-muted">Şu anda katılabileceğiniz yayımlanmış sınav yok.</p>
            ) : (
              <ul className="mt-4 divide-y divide-border border-y border-border">
                {catalog.items.map((item) => (
                  <li key={item.blueprint_id} className="flex flex-col gap-4 py-5 sm:flex-row sm:items-center sm:justify-between">
                    <div className="min-w-0">
                      <h3 className="break-words font-medium text-fg">{item.title}</h3>
                      {item.description && <p className="prose-tr mt-1 text-sm text-fg-muted">{item.description}</p>}
                      <p className="mt-2 text-sm text-fg-muted">{item.duration_minutes} dakika · {item.remaining_attempts}/{item.max_attempts} deneme hakkı</p>
                      {item.closes_at && <p className="mt-1 text-xs text-fg-subtle">Son katılım: {examDate(item.closes_at)}</p>}
                    </div>
                    <div className="shrink-0">
                      <Button variant="secondary" aria-disabled={busy || !item.can_start}
                        aria-label={`${item.title} sınavına başla`}
                        onClick={() => void start({ mode: "exam", blueprint_id: item.blueprint_id }, item.blueprint_id)}>
                        {starting === item.blueprint_id ? "Başlatılıyor…" : "Sınava katıl"}
                      </Button>
                      {!item.can_start && <p className="mt-2 text-xs text-fg-muted">Şu anda başlatılamıyor.</p>}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <SessionHistory courseId={courseId} onOpen={onStarted} />
        </>
      )}
    </>
  );
}
