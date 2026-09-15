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
import { useSubmit } from "@/lib/use-submit";
import { Field } from "@/components/field";
import { ErrorNote } from "@/components/page-state";
import { Button, Input } from "@/components/ui";
import { CellEditor } from "@/components/blueprint/cell-editor";

/**
 * Var olan blueprint'in meta verisini ve hücre kümesini günceller.
 *
 * Hücreler KÜME OLARAK gönderilir (sil + yaz): `BlueprintUpdate` şeması tek
 * hücrelik güncellemeyi bilerek dışarıda bırakıyor, çünkü FR-112 doğrulaması
 * küme üzerinde yapılıyor ve tekil bir UPDATE doğrulamayı atlayıp tutarsız bir
 * dağılım bırakabilirdi. Veritabanı da aynı kararı taşıyor: `blueprint_cells`
 * üzerinde UPDATE ne politikası ne yetkisi var.
 *
 * Yayınlanmış sürüm varken düzenleme SERBEST: o sürümün dağılım kanıtı kendi
 * `blueprint_snapshot`'ında dondurulmuştur (data-model.md §8 madde 1). Ekranın
 * gösterdiği uyarı (`editingNoticeFor`) tam olarak bunu anlatıyor — bu form
 * gelene kadar o uyarı var olmayan bir yeteneğin tavsiyesiydi.
 */
export function BlueprintEditor({
  courseId,
  blueprint,
  outcomes,
  onCancel,
  onSaved,
}: {
  courseId: string;
  blueprint: Blueprint;
  outcomes: LearningOutcome[];
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [title, setTitle] = useState(blueprint.title);
  const [duration, setDuration] = useState(String(blueprint.duration_minutes));
  const [attempts, setAttempts] = useState(String(blueprint.max_attempts));
  const [cells, setCells] = useState<BlueprintCellInput[]>(() =>
    // `BlueprintCell`, `BlueprintCellInput`'i genişletir; sunucudan gelen
    // `id`/`label` alanları güncelleme gövdesine girmez, o yüzden alanlar
    // tek tek seçilir.
    blueprint.cells.map((cell) => ({
      learning_outcome_id: cell.learning_outcome_id,
      difficulty: cell.difficulty,
      question_type: cell.question_type,
      question_count: cell.question_count,
      points_per_question: cell.points_per_question,
    })),
  );

  const { busy, error, submit } = useSubmit(async () => {
    await api.post(`/courses/${courseId}/blueprints/${blueprint.id}`, {
      title: title.trim(),
      duration_minutes: Number(duration),
      max_attempts: Number(attempts),
      cells,
      targets: { total_questions: totalQuestions(cells) },
    });
    onSaved();
  }, "Blueprint güncellenemedi.");

  return (
    <div className="mb-4 rounded-2xl border border-border bg-surface-sunken p-5 sm:p-6">
      <h3 className="mb-3 text-sm font-semibold text-fg">Dağılımı düzenle</h3>
      <div className="mb-4 flex flex-wrap items-end gap-5">
        <Field label="Sınav adı">
          {(control) => (
            <Input
              {...control}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
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
              className="w-32"
            />
          )}
        </Field>
        <Field label="Deneme hakkı">
          {(control) => (
            <Input
              {...control}
              type="number"
              min={1}
              max={100}
              value={attempts}
              onChange={(event) => setAttempts(event.target.value)}
              className="w-32"
            />
          )}
        </Field>
      </div>

      <CellEditor outcomes={outcomes} cells={cells} onChange={setCells} />

      {error && <div className="mt-3">{<ErrorNote message={error} />}</div>}

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button
          onClick={submit}
          aria-disabled={busy || title.trim() === "" || cells.length === 0}
        >
          {busy ? "Kaydediliyor…" : "Değişikliği kaydet"}
        </Button>
        <Button variant="ghost" aria-disabled={busy} onClick={onCancel}>
          Vazgeç
        </Button>
        <span className="text-sm text-fg-muted">
          {totalQuestions(cells)} soru · {totalPoints(cells)} puan
        </span>
      </div>
    </div>
  );
}
