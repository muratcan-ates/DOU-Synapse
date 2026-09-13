"use client";

import { useId, type RefObject } from "react";
import { BUG_FIX_MAX_LENGTH, BUG_TYPE_MAX_LENGTH, bugHuntDraft, bugHuntDraftIssue, encodeBugHuntDraft, isStructuredBugDraft, validBugLine } from "@/lib/exam-answer";
import type { QuestionType } from "@/lib/types";
import { ANSWER_MAX_LENGTH, type QuestionView } from "@/lib/exam";
import { Field } from "@/components/field";
import { Badge, Input } from "@/components/ui";

const TEXTAREA_CLASS =
  "w-full rounded-lg border border-border-strong bg-surface px-3 py-2 text-sm leading-6 text-fg placeholder:text-fg-subtle focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand";

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
        <h1
          ref={headingRef}
          tabIndex={-1}
          aria-describedby={describedBy}
          className="prose-tr rounded-lg text-lg leading-7 font-medium text-fg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand"
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
          <pre className="overflow-x-auto rounded-lg border border-border bg-bg px-4 py-3">
            <code className="font-mono text-xs text-fg">{view.code}</code>
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
      <fieldset className="mt-8 space-y-4">
        <legend className="sr-only">Cevap şıkları</legend>
        {view.choices.map((choice) => {
          const active = draft === choice.key;
          return (
            <label
              key={choice.key}
              className={`flex min-h-11 cursor-pointer items-start gap-3 rounded-lg border p-4 transition-colors ${
                active
                  ? "border-brand bg-brand-subtle"
                  : "border-border bg-surface hover:border-border-strong"
              }`}
            >
              <input
                type="radio"
                name={`answer-${questionId}`}
                checked={active}
                disabled={disabled}
                onChange={() => onChange(choice.key)}
                className="mt-1 h-4 w-4 accent-brand"
              />
              <span className="prose-tr text-sm leading-6 text-fg">{choice.text}</span>
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
