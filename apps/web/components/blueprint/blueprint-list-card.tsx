"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import {
  totalPoints,
  totalQuestions,
  type Blueprint,
  type BlueprintCellInput,
  type LearningOutcome,
} from "@/lib/blueprint";
import { useResource } from "@/lib/use-resource";
import { useSubmit } from "@/lib/use-submit";
import { Field } from "@/components/field";
import { ErrorNote, Loading } from "@/components/page-state";
import { Badge, Button, Card, EmptyState, Input } from "@/components/ui";
import { CellEditor } from "@/components/blueprint/cell-editor";

/* -------------------------------------------------------------------------
 * Blueprint listesi ve kurma (FR-111, FR-112)
 * ---------------------------------------------------------------------- */

export function BlueprintListCard({
  courseId,
  blueprints,
  outcomes,
  selectedId,
  onSelect,
}: {
  courseId: string;
  blueprints: ReturnType<typeof useResource<Blueprint[]>>;
  outcomes: LearningOutcome[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const [creating, setCreating] = useState(false);

  return (
    <Card className="mb-7">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold text-fg">Sınavlar</h2>
        <Button
          variant="secondary"
          onClick={() => setCreating((value) => !value)}
          aria-disabled={outcomes.length === 0}
        >
          {creating ? "Vazgeç" : "Yeni sınav kur"}
        </Button>
      </div>

      {outcomes.length === 0 && (
        <p className="prose-tr mb-5 text-base leading-7 text-fg-muted">
          Önce en az bir öğrenme çıktısı tanımla: dağılım hücreleri çıktılara bağlanır.
        </p>
      )}

      {creating && (
        <CreateBlueprintForm
          courseId={courseId}
          outcomes={outcomes}
          onCreated={(id) => {
            setCreating(false);
            blueprints.reload();
            onSelect(id);
          }}
        />
      )}

      {blueprints.loading && !blueprints.data && <Loading label="Sınavlar yükleniyor…" />}
      {blueprints.error && (
        <ErrorNote
          message={blueprints.error}
          kind={blueprints.errorKind}
          requestId={blueprints.errorRequestId}
          onRetry={blueprints.reload}
        />
      )}

      {blueprints.data && blueprints.data.length === 0 && !creating && (
        <EmptyState title="Henüz sınav kurulmadı." />
      )}

      {blueprints.data && blueprints.data.length > 0 && (
        <ul className="flex flex-col gap-2">
          {blueprints.data.map((blueprint) => (
            <li key={blueprint.id}>
              <button
                type="button"
                onClick={() => onSelect(blueprint.id)}
                aria-current={blueprint.id === selectedId ? "true" : undefined}
                className={`flex w-full flex-wrap items-center gap-x-5 gap-y-3 rounded-2xl border px-5 py-5 text-left transition-colors duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand motion-reduce:transition-none ${
                  blueprint.id === selectedId
                    ? "border-border-strong bg-brand-subtle/30"
                    : "border-border hover:border-border-strong"
                }`}
              >
                <span className="text-lg font-semibold text-fg">{blueprint.title}</span>
                <span className="text-sm text-fg-muted">
                  {blueprint.total_questions} soru · {blueprint.total_points} puan ·{" "}
                  {blueprint.duration_minutes} dk
                </span>
                {blueprint.published_version_no === null ? (
                  <Badge tone="neutral">Yayında değil</Badge>
                ) : (
                  <Badge tone="success">
                    {blueprint.published_version_no}. sürüm yayında
                  </Badge>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function CreateBlueprintForm({
  courseId,
  outcomes,
  onCreated,
}: {
  courseId: string;
  outcomes: LearningOutcome[];
  onCreated: (id: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [duration, setDuration] = useState("60");
  const [attempts, setAttempts] = useState("1");
  const [cells, setCells] = useState<BlueprintCellInput[]>([]);

  const { busy, error, submit } = useSubmit(async () => {
    const created = await api.post<Blueprint>(`/courses/${courseId}/blueprints`, {
      title: title.trim(),
      duration_minutes: Number(duration),
      max_attempts: Number(attempts),
      cells,
      // Sunucu ayrıca doğrulasın diye toplamı da gönderiyoruz: yuvarlamayı ekran
      // yaptı, ama tuttuğunu ekranın kendisi ilan etmemeli (Anayasa III).
      targets: { total_questions: totalQuestions(cells) },
    });
    onCreated(created.id);
  });

  return (
    <div className="mb-6 rounded-2xl border border-border bg-surface-sunken p-5 sm:p-6">
      <div className="mb-4 flex flex-wrap items-end gap-5">
        <Field label="Sınav adı">
          {(control) => (
            <Input
              {...control}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Vize"
              className="w-full sm:w-64"
            />
          )}
        </Field>
        <Field label="Süre (dakika)">
          {(control) => (
            <Input
              {...control}
              type="number"
              min={1}
              max={600}
              value={duration}
              onChange={(event) => setDuration(event.target.value)}
              className="w-28"
            />
          )}
        </Field>
        <Field label="Deneme hakkı">
          {(control) => (
            <Input
              {...control}
              type="number"
              min={1}
              value={attempts}
              onChange={(event) => setAttempts(event.target.value)}
              className="w-28"
            />
          )}
        </Field>
      </div>

      <CellEditor outcomes={outcomes} cells={cells} onChange={setCells} />

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button onClick={submit} aria-disabled={busy || title.trim() === "" || cells.length === 0}>
          {busy ? "Kaydediliyor…" : "Sınavı kur"}
        </Button>
        <span className="text-sm text-fg-muted">
          {totalQuestions(cells)} soru · {totalPoints(cells)} puan
        </span>
      </div>

      {error && <div className="mt-3">{<ErrorNote message={error} />}</div>}
    </div>
  );
}
