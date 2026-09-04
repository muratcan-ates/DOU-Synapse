import Link from "next/link";
import { Field } from "@/components/field";
import { DIFFICULTIES, DIFFICULTY_LABEL, type Difficulty, type LearningOutcome } from "@/lib/blueprint";
import { outcomesForTopic, type Classification } from "@/lib/question-authoring";

export const AUTHORING_CONTROL_CLASS =
  "h-11 w-full rounded-lg border border-border-strong bg-surface px-3 text-sm text-fg focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand";

export function ClassificationFields({ courseId, topicId, outcomes, value, onChange }: {
  courseId: string;
  topicId: string;
  outcomes: LearningOutcome[];
  value: Classification;
  onChange: (value: Classification) => void;
}) {
  const matching = outcomesForTopic(outcomes, topicId);
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Öğrenme çıktısı">
          {(control) => <select {...control} className={AUTHORING_CONTROL_CLASS}
            value={value.learningOutcomeId}
            onChange={(event) => onChange({ ...value, learningOutcomeId: event.target.value })}>
            <option value="">Sınıflandırılmadı</option>
            {matching.map((outcome) => <option key={outcome.id} value={outcome.id}>
              {outcome.code}: {outcome.description}
            </option>)}
          </select>}
        </Field>
        <Field label="Zorluk">
          {(control) => <select {...control} className={AUTHORING_CONTROL_CLASS}
            value={value.difficulty}
            onChange={(event) => onChange({ ...value, difficulty: event.target.value as Difficulty | "" })}>
            <option value="">Sınıflandırılmadı</option>
            {DIFFICULTIES.map((difficulty) => <option key={difficulty} value={difficulty}>
              {DIFFICULTY_LABEL[difficulty]}
            </option>)}
          </select>}
        </Field>
      </div>
      <p className="prose-tr text-xs text-fg-muted">
        Sınav planına eklemek için öğrenme çıktısı ve zorluğu birlikte seçin.
        {matching.length === 0 && " Bu konu için henüz öğrenme çıktısı yok."}{" "}
        <Link href={`/courses/${courseId}/blueprints`} className="text-brand hover:text-brand-strong underline underline-offset-4">
          Öğrenme çıktılarını yönet
        </Link>
      </p>
    </div>
  );
}
