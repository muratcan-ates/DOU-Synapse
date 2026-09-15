"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { buildLearningOutcomeRequest, type LearningOutcome } from "@/lib/blueprint";
import type { Topic } from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { useSubmit } from "@/lib/use-submit";
import { Field } from "@/components/field";
import { ErrorNote, Loading } from "@/components/page-state";
import { Badge, Button, Card, Input, Select } from "@/components/ui";

/* -------------------------------------------------------------------------
 * Öğrenme çıktıları (FR-110)
 * ---------------------------------------------------------------------- */

export function OutcomesCard({
  courseId,
  outcomes,
}: {
  courseId: string;
  outcomes: ReturnType<typeof useResource<LearningOutcome[]>>;
}) {
  const [code, setCode] = useState("");
  const [description, setDescription] = useState("");
  const [topicId, setTopicId] = useState("");
  const topics = useResource<Topic[]>(() => api.get(`/courses/${courseId}/topics`), [courseId]);

  const { busy, error, submit } = useSubmit(async () => {
    await api.post(`/courses/${courseId}/learning-outcomes`,
      buildLearningOutcomeRequest(code, description, topicId));
    setCode("");
    setDescription("");
    outcomes.reload();
  });

  return (
    <Card className="mb-7">
      <h2 className="mb-3 text-xl font-semibold text-fg">Öğrenme çıktıları</h2>
      <p className="prose-tr mb-5 text-base leading-7 text-fg-muted">
        Dağılımın ekseni budur: her hücre bir çıktıya bağlanır. Konu dağılımı ayrıca
        girilmez, çıktının konusundan türetilir.
      </p>

      {outcomes.loading && !outcomes.data && <Loading label="Çıktılar yükleniyor…" />}
      {outcomes.error && (
        <ErrorNote
          message={outcomes.error}
          kind={outcomes.errorKind}
          requestId={outcomes.errorRequestId}
          onRetry={outcomes.reload}
        />
      )}

      {outcomes.data && outcomes.data.length > 0 && (
        <ul className="mb-4 flex flex-col gap-2">
          {outcomes.data.map((outcome) => (
            <li
              key={outcome.id}
              className="flex flex-wrap items-baseline gap-x-4 gap-y-2 border-b border-border px-1 py-4 last:border-b-0"
            >
              <span className="text-sm font-semibold text-fg">{outcome.code}</span>
              <span className="prose-tr text-sm text-fg-muted">{outcome.description}</span>
              <Badge tone="neutral">{outcome.topic_id === null
                ? "Konu atanmadı; dağılımda ayrı gösterilir"
                : topics.data?.find((topic) => topic.id === outcome.topic_id)?.name ?? (topics.loading ? "Konu bilgisi yükleniyor…" : "Konu bilgisi bulunamadı")}</Badge>
            </li>
          ))}
        </ul>
      )}

      {(topics.error ?? topics.refreshError) && <ErrorNote
        message={topics.error ?? topics.refreshError ?? ""} kind={topics.errorKind}
        requestId={topics.errorRequestId} onRetry={topics.reload} />}
      <div className="flex flex-wrap items-end gap-5">
        <Field label="Çıktının konusu">
          {(control) => <Select {...control} value={topicId} disabled={busy || !topics.data}
            onChange={(event) => setTopicId(event.target.value)}>
            <option value="">Konu atama</option>
            {(topics.data ?? []).map((topic) => <option key={topic.id} value={topic.id}>{topic.name}</option>)}
          </Select>}
        </Field>
        <Field label="Kod">
          {(control) => (
            <Input
              {...control}
              value={code}
              onChange={(event) => setCode(event.target.value)}
              placeholder="CO1"
              className="w-28"
            />
          )}
        </Field>
        <Field label="Açıklama">
          {(control) => (
            <Input
              {...control}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Kilitlenmenin dört koşulunu sayar"
              className="w-full sm:w-80 xl:w-96"
            />
          )}
        </Field>
        <Button
          onClick={submit}
          aria-disabled={busy || code.trim() === "" || description.trim() === ""}
        >
          {busy ? "Ekleniyor…" : "Çıktı ekle"}
        </Button>
      </div>

      {error && <div className="mt-3">{<ErrorNote message={error} />}</div>}
    </Card>
  );
}
