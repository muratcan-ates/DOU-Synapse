"use client";

import { useId, type RefObject } from "react";
import { BUG_FIX_MAX_LENGTH, BUG_TYPE_MAX_LENGTH, bugHuntDraft, bugHuntDraftIssue, encodeBugHuntDraft, isStructuredBugDraft, validBugLine } from "@/lib/exam-answer";
import type { QuestionType } from "@/lib/types";
import { ANSWER_MAX_LENGTH, type QuestionView } from "@/lib/exam";
import { Field } from "@/components/field";
import { Badge, Input } from "@/components/ui";

/*
 * Çok satırlı cevap kutusu `Input` ile aynı kabuğu taşır (12px köşe, kontrol
 * sınırı, aynı odak halkası); yalnız yükseklik satır sayısından gelir. İki
 * girdi türü aynı formda yan yana durduğunda ölçü farkı ürünün derlenmemiş
 * hissi veriyordu.
 */
const TEXTAREA_CLASS =
  "w-full rounded-xl border border-border-strong bg-surface px-4 py-3 text-base leading-7 text-fg placeholder:text-fg-subtle focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand";

export function QuestionBody({
  view,
  headingRef,
  describedBy,
  answered,
}: {
  view: QuestionView;
  headingRef: RefObject<HTMLHeadingElement | null>;
  describedBy: string;
  answered: boolean;
}) {
  const prompt = view.kind === "unsupported" ? "Bu soru gösterilemiyor" : view.prompt;

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        {/* Soru kökü `text-lg` (DESIGN.md §Sınav ekranı); satır aralığı okuma için geniş. */}
        <h1
          ref={headingRef}
          tabIndex={-1}
          aria-describedby={describedBy}
          className="prose-tr rounded-lg text-xl leading-relaxed font-medium text-fg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand"
        >
          {prompt}
        </h1>
        {answered && <Badge tone="neutral">Cevaplandı</Badge>}
      </div>

      {view.kind === "code" && (
        <div className="mt-5">
          <h2 className="mb-2 text-xs font-medium text-fg-muted">
            Kod{view.language ? ` · ${view.language}` : ""}
          </h2>
          {/* Mono yalnız kod bloğunda: çukur yüzey, kodun içerik değil malzeme olduğunu söyler. */}
          <pre className="overflow-x-auto rounded-2xl bg-surface-sunken px-5 py-5">
            <code className="font-mono text-sm leading-6 text-fg">{view.code}</code>
          </pre>
        </div>
      )}
    </>
  );
}

export function AnswerInput({
  view,
  questionType,
  questionId,
  draft,
  disabled,
  onChange,
}: {
  view: QuestionView;
  questionType?: QuestionType;
  questionId: string;
  draft: string;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  const answerHelpId = useId();
  if (view.kind === "mcq") {
    return (
      /* Şıklar arasında bol boşluk: yanlış tıklama sınav kaygısını artırır (DESIGN.md). */
      <fieldset className="mt-8 space-y-3">
        <legend className="sr-only">Cevap şıkları</legend>
        {view.choices.map((choice) => {
          const active = draft === choice.key;
          return (
            /*
             * Radyo semantiği korunur; seçili görünümü CSS `:has(:checked)` ile
             * satırın kendisi taşır. Seçim rengi aksan değil metin rengidir:
             * kırmızı bu sayfada yalnız "Cevabı gönder"de durur.
             */
            <label
              key={choice.key}
              className="flex min-h-14 cursor-pointer items-start gap-4 rounded-xl border border-border-strong bg-surface px-5 py-4 transition-colors duration-150 hover:bg-surface-sunken has-checked:border-fg has-checked:bg-surface-sunken has-disabled:cursor-default has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-brand motion-reduce:transition-none"
            >
              <input
                type="radio"
                name={`answer-${questionId}`}
                checked={active}
                disabled={disabled}
                onChange={() => onChange(choice.key)}
                className="mt-1 h-4 w-4 accent-fg"
              />
              <span className="prose-tr text-base leading-7 text-fg">{choice.text}</span>
            </label>
          );
        })}
      </fieldset>
    );
  }

  if (view.kind === "unsupported") return null;

  if (view.kind === "code" && questionType === "bug_hunt") {
    return <BugHuntInput draft={draft} disabled={disabled} onChange={onChange} />;
  }

  const multiline = view.kind === "code" || view.multiline;

  return (
    <div className="mt-8">
      {/* Etiket görünürdür: placeholder etiket değildir (DESIGN.md). */}
      {questionType === "code_trace" && (
        <p id={answerHelpId} className="mb-3 text-sm text-fg-muted">
          Çıktıyı büyük/küçük harf, boşluk ve satır sırasını koruyarak yazın.
        </p>
      )}
      <Field label="Cevabınız" describedBy={questionType === "code_trace" ? answerHelpId : undefined}>
        {(control) =>
          multiline ? (
            <textarea
              {...control}
              value={draft}
              rows={6}
              maxLength={ANSWER_MAX_LENGTH}
              disabled={disabled}
              onChange={(e) => onChange(e.target.value)}
              className={TEXTAREA_CLASS}
            />
          ) : (
            <Input
              {...control}
              value={draft}
              maxLength={ANSWER_MAX_LENGTH}
              disabled={disabled}
              onChange={(e) => onChange(e.target.value)}
            />
          )
        }
      </Field>
    </div>
  );
}

/** Eski serbest cevap yolu korunur; satır ve tür birlikte otomatik değerlendirmeyi açar. */
function BugHuntInput({ draft, disabled, onChange }: {
  draft: string;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  const helpId = useId();
  const value = bugHuntDraft(draft);
  const structured = isStructuredBugDraft(value);
  const issue = bugHuntDraftIssue(value);
  const change = (patch: Partial<typeof value>) => onChange(encodeBugHuntDraft({ ...value, ...patch }));

  return (
    <div className="mt-8 space-y-4">
      <p id={helpId} className="prose-tr text-sm text-fg-muted">
        Satır ve hata türü boşsa yanıtınız kaydedilir, otomatik puanlanmaz.
        Otomatik değerlendirme için ikisini de doldurup düzeltmenizi açıklayın.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Hata satırı" describedBy={helpId} invalid={value.line.trim() !== "" && !validBugLine(value.line)}>
          {(control) => <Input {...control} value={value.line} inputMode="numeric" maxLength={16}
            disabled={disabled} onChange={(event) => change({ line: event.target.value })} />}
        </Field>
        <Field label="Hata türü" describedBy={helpId}>
          {(control) => <Input {...control} value={value.bugType} maxLength={BUG_TYPE_MAX_LENGTH}
            disabled={disabled} onChange={(event) => change({ bugType: event.target.value })} />}
        </Field>
      </div>
      {issue && <p role="status" className="text-sm text-fg-muted">{issue}</p>}
      <Field label="Cevabınız" describedBy={helpId}>
        {(control) => <textarea {...control} value={value.fixSummary} rows={6}
          maxLength={structured ? BUG_FIX_MAX_LENGTH : ANSWER_MAX_LENGTH} disabled={disabled}
          onChange={(event) => change({ fixSummary: event.target.value })} className={TEXTAREA_CLASS} />}
      </Field>
    </div>
  );
}
