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
import { Button, Card, EmptyState, Select } from "@/components/ui";
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
      <div className="grid gap-5 md:grid-cols-2">
        {(Object.keys(EXAM_MODE) as ExamMode[]).map((mode) => (
          <Card key={mode} className="flex min-w-0 flex-col">
            <span aria-hidden="true" className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-surface-sunken text-fg-muted">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                {mode === "practice" ? <><path d="M12 5v15M3 4h5a4 4 0 0 1 4 2 4 4 0 0 1 4-2h5v15h-5a4 4 0 0 0-4 2 4 4 0 0 0-4-2H3z" /></> : <><circle cx="12" cy="13" r="8" /><path d="M12 9v4l3 2M9 2h6M12 2v3" /></>}
              </svg>
            </span>
            <h2 className="text-xl font-semibold text-fg">{EXAM_MODE[mode].label}</h2>
            <p className="prose-tr mt-2 text-base leading-7 text-fg-muted">{EXAM_MODE[mode].description}</p>
            {mode === "practice" && catalog.enabled && (
              <div className="mt-4">
                {topics.loading ? <Loading label="Konular yükleniyor…" /> : topics.error ? (
                  <ErrorNote message={topics.error} onRetry={topics.reload} />
                ) : (
                  <Field label="Çalışma konusu">
                    {(control) => (
                      <Select {...control} value={topicId} onChange={(event) => setTopicId(event.target.value)}
                        disabled={busy}>
                        <option value="">Tüm konular</option>
                        {(topics.data ?? []).map((topic) => <option key={topic.id} value={topic.id}>{topic.name}</option>)}
                      </Select>
                    )}
                  </Field>
                )}
              </div>
            )}
            <div className="mt-auto pt-6">
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
          <section className="mt-8 rounded-[20px] border border-border bg-surface p-5 shadow-e1 sm:p-7" aria-labelledby="open-exams-title">
            <h2 id="open-exams-title" className="text-xl font-semibold text-fg">Şu anda açık sınavlar</h2>
            <p className="mt-1 text-sm text-fg-muted">Eğitmeninizin yayımladığı sınavlar ve kalan deneme haklarınız.</p>
            {catalog.items.length === 0 ? (
              <p className="mt-4 border-t border-border py-4 text-sm text-fg-muted">Şu anda katılabileceğiniz yayımlanmış sınav yok.</p>
            ) : (
              <ul className="mt-5 divide-y divide-border border-t border-border">
                {catalog.items.map((item) => (
                  <li key={item.blueprint_id} className="flex flex-col gap-4 py-5 sm:flex-row sm:items-center sm:justify-between">
                    <div className="min-w-0">
                      <h3 className="break-words font-semibold text-fg">{item.title}</h3>
                      {item.description && <p className="prose-tr mt-2 text-base leading-7 text-fg-muted">{item.description}</p>}
                      <p className="mt-2 text-sm text-fg-muted">{item.duration_minutes} dakika · {item.remaining_attempts}/{item.max_attempts} deneme hakkı</p>
                      {item.closes_at && <p className="mt-1 text-sm text-fg-subtle">Son katılım: {examDate(item.closes_at)}</p>}
                    </div>
                    <div className="shrink-0">
                      <Button variant="secondary" aria-disabled={busy || !item.can_start}
                        aria-label={`${item.title} sınavına başla`}
                        onClick={() => void start({ mode: "exam", blueprint_id: item.blueprint_id }, item.blueprint_id)}>
                        {starting === item.blueprint_id ? "Başlatılıyor…" : "Sınava katıl"}
                      </Button>
                      {!item.can_start && <p className="mt-2 text-sm text-fg-muted">Şu anda başlatılamıyor.</p>}
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
