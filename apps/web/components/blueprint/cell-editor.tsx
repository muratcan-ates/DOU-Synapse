"use client";

import { useCallback, useState } from "react";
import {
  DIFFICULTIES,
  DIFFICULTY_LABEL,
  splitByShares,
  type BlueprintCellInput,
  type Difficulty,
  type LearningOutcome,
} from "@/lib/blueprint";
import { QUESTION_TYPE } from "@/lib/labels";
import { Field } from "@/components/field";
import { Button, Input, Select } from "@/components/ui";

const DEFAULT_TYPE = "mcq" as const;

/* -------------------------------------------------------------------------
 * Hücre düzenleyici — dağılımın atomik birimi
 * ---------------------------------------------------------------------- */

export function CellEditor({
  outcomes,
  cells,
  onChange,
}: {
  outcomes: LearningOutcome[];
  cells: BlueprintCellInput[];
  onChange: (cells: BlueprintCellInput[]) => void;
}) {
  const [outcomeId, setOutcomeId] = useState(outcomes[0]?.id ?? "");
  const [total, setTotal] = useState("10");
  const [shares, setShares] = useState<Record<Difficulty, string>>({
    easy: "40",
    medium: "40",
    hard: "20",
  });

  const spread = useCallback(() => {
    const outcome = outcomeId || outcomes[0]?.id;
    if (!outcome) return;
    const counts = splitByShares(
      Number(total) || 0,
      DIFFICULTIES.map((level) => Number(shares[level]) || 0),
    );
    const fresh = DIFFICULTIES.map((level, index) => ({
      learning_outcome_id: outcome,
      difficulty: level,
      question_type: DEFAULT_TYPE,
      question_count: counts[index],
      points_per_question: 5,
    })).filter((cell) => cell.question_count > 0);

    const others = cells.filter((cell) => cell.learning_outcome_id !== outcome);
    onChange([...others, ...fresh]);
  }, [cells, onChange, outcomeId, outcomes, shares, total]);

  return (
    <div>
      <h3 className="mb-1 text-sm font-semibold text-fg">Dağılım</h3>
      <p className="prose-tr mb-3 text-sm text-fg-muted">
        Yüzde gir, adete çevrilsin. Saklanan gerçek adettir; yuvarlama artığı en büyük
        paya eklenir, böylece toplam her zaman tam tutar.
      </p>

      <div className="mb-3 flex flex-wrap items-end gap-5">
        <Field label="Öğrenme çıktısı">
          {(control) => (
            <Select
              {...control}
              value={outcomeId}
              onChange={(event) => setOutcomeId(event.target.value)}
            >
              {outcomes.map((outcome) => (
                <option key={outcome.id} value={outcome.id}>
                  {outcome.code}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Soru sayısı">
          {(control) => (
            <Input
              {...control}
              type="number"
              min={1}
              value={total}
              onChange={(event) => setTotal(event.target.value)}
              className="w-24"
            />
          )}
        </Field>
        {DIFFICULTIES.map((level) => (
          <Field key={level} label={`${DIFFICULTY_LABEL[level]} %`}>
            {(control) => (
              <Input
                {...control}
                type="number"
                min={0}
                max={100}
                value={shares[level]}
                onChange={(event) =>
                  setShares((current) => ({ ...current, [level]: event.target.value }))
                }
                className="w-20"
              />
            )}
          </Field>
        ))}
        <Button variant="secondary" onClick={spread}>
          Hücrelere aç
        </Button>
      </div>

      {cells.length === 0 ? (
        <p className="prose-tr text-sm text-fg-muted">Henüz hücre yok.</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {cells.map((cell, index) => {
            const outcome = outcomes.find((item) => item.id === cell.learning_outcome_id);
            return (
              <li
                key={`${cell.learning_outcome_id}-${cell.difficulty}-${cell.question_type}`}
                className="flex flex-wrap items-center gap-3 rounded-xl border border-border px-4 py-4 text-sm"
              >
                <span className="font-semibold text-fg">{outcome?.code ?? "?"}</span>
                <span className="text-fg-muted">{DIFFICULTY_LABEL[cell.difficulty]}</span>
                <span className="text-fg-muted">{QUESTION_TYPE[cell.question_type]}</span>
                <span className="text-fg">{cell.question_count} soru</span>
                <span className="text-fg-muted">{cell.points_per_question} puan</span>
                <Button
                  variant="ghost"
                  className="ml-auto"
                  onClick={() => onChange(cells.filter((_, i) => i !== index))}
                >
                  Kaldır
                </Button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
