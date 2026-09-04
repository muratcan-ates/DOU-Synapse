import { useEffect, useId, useRef, useState } from "react";
import type { ComponentProps } from "react";
import { api } from "@/lib/api";
import type { LearningOutcome } from "@/lib/blueprint";
import { describeError, type ErrorInfo } from "@/lib/errors";
import { buildDraftRequest, changeCorrectOption, classificationComplete, createDraftForm,
  draftSourceChoices, rubricHasLegacyMetadata, type QuestionDraftForm } from "@/lib/question-authoring";
import { useSubmit } from "@/lib/use-submit";
import type { Question } from "@/lib/types";
import { Field } from "@/components/field";
import { ErrorNote } from "@/components/page-state";
import { Button, ConfirmAction, Input } from "@/components/ui";
import { AUTHORING_CONTROL_CLASS, ClassificationFields } from "./classification-fields";

/** The original question stays in the parent until the server accepts the full edit. */
export function DraftEditor({ courseId, question, outcomes, onSaved, onCancel }: {
  courseId: string;
  question: Question;
  outcomes: LearningOutcome[];
  onSaved: (updated: Question) => void;
  onCancel: () => void;
}) {
  const [original] = useState(() => createDraftForm(question));
  const [form, setForm] = useState(original);
  const [error, setError] = useState<ErrorInfo | null>(null);
  const formId = useId();
  const firstField = useRef<HTMLTextAreaElement>(null);
  const dirty = JSON.stringify(form) !== JSON.stringify(original);
  const shortAnswer = question.type === "open" && question.payload.format === "short_answer";
  const sources = draftSourceChoices(question);
  const complete = classificationComplete(form);
  const legacyRubric = rubricHasLegacyMetadata(question);
  const { busy, submit } = useSubmit(async () => {
    setError(null);
    const updated = await api.post<Question>(`/courses/${courseId}/questions/${question.id}/draft`,
      buildDraftRequest(question, form));
    onSaved(updated);
  }, { onError: (cause) => setError(describeError(cause)) });

  useEffect(() => { firstField.current?.focus(); }, []);
  useEffect(() => {
    if (!dirty && !busy) return;
    const beforeUnload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    // Course navigation uses links. Keep an in-progress edit visible until the
    // instructor explicitly leaves, including links outside the question panel.
    const beforeNavigate = (event: MouseEvent) => {
      const anchor = (event.target as Element).closest?.("a[href]") as HTMLAnchorElement | null;
      if (!anchor || anchor.target === "_blank" || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      if (busy || !window.confirm("Kaydedilmemiş değişiklikler var. Sayfadan ayrılmak istiyor musunuz?")) {
        event.preventDefault(); event.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("click", beforeNavigate, true);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      document.removeEventListener("click", beforeNavigate, true);
    };
  }, [dirty, busy]);

  function change<K extends keyof QuestionDraftForm>(key: K, value: QuestionDraftForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }
  function save(event: React.FormEvent) {
    event.preventDefault();
    if (!complete) return;
    void submit();
  }
  return (
    <>
    <form id={formId} onSubmit={save} aria-label="Taslak soru düzenleme" className="mt-6 space-y-6 border-t border-border pt-6">
      <div>
        <h3 className="text-sm font-medium text-fg">Taslağı düzenle</h3>
        <p className="prose-tr mt-1 text-xs text-fg-muted">Kaydettiğiniz soru taslak olarak kalır. İçeriği ve kaynağını kontrol ettikten sonra onaylayın.</p>
      </div>
      <fieldset disabled={busy} className="min-w-0 space-y-6">
        <TextArea label="Soru metni" value={form.stem} onChange={(value) => change("stem", value)}
          ref={firstField} required minLength={5} maxLength={question.type === "mcq" || question.type === "open" ? 4000 : 2000} />
        {(question.type === "code_trace" || question.type === "bug_hunt") && <div className="space-y-3">
          <Field label="Programlama dili">{(control) => <Input {...control} value={form.language} required maxLength={40}
            onChange={(event) => change("language", event.target.value)} />}</Field>
          <TextArea label="Kod" value={form.code} onChange={(value) => change("code", value)} required maxLength={8000} rows={8} className="font-mono" />
        </div>}
        {question.type === "mcq" ? <div className="space-y-4">
          <h4 className="text-sm font-medium text-fg">Şıklar ve cevap anahtarı</h4>
          {form.options.map((option, index) => <TextArea key={option.key} label={`${option.key} şıkkı`}
            value={option.text} onChange={(value) => change("options", form.options.map((item, i) => i === index ? { ...item, text: value } : item))}
            required maxLength={1000} rows={2} />)}
          <Field label="Doğru şık">{(control) => <select {...control} className={AUTHORING_CONTROL_CLASS} required
            value={form.answerKey} onChange={(event) => setForm((current) => changeCorrectOption(current, event.target.value, question.source?.chunk_id))}>
            <option value="">Şık seçin</option>
            {form.options.map((option) => <option key={option.key} value={option.key}>{option.key}</option>)}
          </select>}</Field>
          <p className="prose-tr text-xs text-fg-muted">Her yanlış şık için çeliştiği kaynağı kontrol edin. Doğru şıkkı değiştirince yeni yanlış şık için sorunun üretildiği kaynak seçilir.</p>
          {form.options.filter((option) => option.key !== form.answerKey).map((option) => <Field key={option.key} label={`${option.key} yanlış şıkkının kaynağı`}>
            {(control) => <select {...control} required className={AUTHORING_CONTROL_CLASS} value={form.distractorSources[option.key] ?? ""}
              onChange={(event) => change("distractorSources", { ...form.distractorSources, [option.key]: event.target.value })}>
              <option value="">Kaynak seçin</option>
              {sources.map((source) => <option key={source.id} value={source.id}>{source.label}</option>)}
            </select>}
          </Field>)}
        </div> : question.type === "bug_hunt" ? <div className="space-y-3">
          <Field label="Hatalı satır">{(control) => <Input {...control} type="number" min={1} required value={form.bugLine}
            onChange={(event) => change("bugLine", event.target.value)} />}</Field>
          <Field label="Hata türü">{(control) => <Input {...control} required maxLength={200} value={form.bugType}
            onChange={(event) => change("bugType", event.target.value)} />}</Field>
          <TextArea label="Düzeltme özeti" value={form.fixSummary} onChange={(value) => change("fixSummary", value)} required maxLength={2000} />
        </div> : <TextArea label="Cevap anahtarı" value={form.answerKey} onChange={(value) => change("answerKey", value)} required
          maxLength={question.type === "open" ? 8000 : 4000} />}
        {question.type === "open" && (shortAnswer ?
          <TextArea label="Kabul edilen karşılıklar (her satır bir karşılık)" value={form.acceptedAnswers}
            onChange={(value) => change("acceptedAnswers", value)} required /> : <div className="space-y-4">
            <TextArea label="Cevapta aranan noktalar (her satır bir nokta)" value={form.keyPoints}
              onChange={(value) => change("keyPoints", value)} required />
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-fg">Puanlama ölçütleri</h4>
              {legacyRubric && <p className="prose-tr text-xs text-fg-muted">Bu eski sorunun ölçüt kayıtları korunuyor. Ölçüt ekleme, kaldırma ve metin değişikliği kapalı; puanları düzenleyebilirsiniz.</p>}
              {form.rubric.map((criterion, index) => <div key={index} className="space-y-2 border-b border-border pb-3">
                <TextArea label={`Ölçüt ${index + 1}`} value={criterion.point} rows={2} required maxLength={500} readOnly={legacyRubric}
                  onChange={(value) => change("rubric", form.rubric.map((item, i) => i === index ? { ...item, point: value } : item))} />
                <div className="flex flex-wrap items-end gap-3">
                  <Field label={`Ölçüt ${index + 1} puanı`}>{(control) => <Input {...control} type="number" min={1} max={100} required value={criterion.weight}
                    onChange={(event) => change("rubric", form.rubric.map((item, i) => i === index ? { ...item, weight: event.target.value } : item))} />}</Field>
                  <Button type="button" variant="ghost" aria-disabled={legacyRubric} onClick={() => change("rubric", form.rubric.filter((_, i) => i !== index))} aria-label={`Ölçüt ${index + 1} kaldır`}>Ölçütü kaldır</Button>
                </div>
              </div>)}
              <div className="flex flex-wrap items-center gap-3">
                <Button type="button" variant="secondary" aria-disabled={legacyRubric || form.rubric.length >= 12}
                  onClick={() => change("rubric", [...form.rubric, { point: "", weight: "" }])}>Ölçüt ekle</Button>
                <p className="text-xs text-fg-muted">Toplam: {form.rubric.reduce((sum, item) => sum + (Number(item.weight) || 0), 0)} / 100 puan</p>
              </div>
            </div>
          </div>)}
        {question.type !== "open" && <TextArea label="Gerekçe (isteğe bağlı)" value={form.explanation} onChange={(value) => change("explanation", value)} maxLength={4000} />}
        <ClassificationFields courseId={courseId} topicId={question.topic_id} outcomes={outcomes} value={form}
          onChange={(value) => setForm((current) => ({ ...current, ...value }))} />
      </fieldset>
      {!complete && <p role="status" className="text-sm text-fg-muted">Öğrenme çıktısı ve zorluğu birlikte seçin veya ikisini de sınıflandırılmadı olarak bırakın.</p>}
      {error && <ErrorNote message={error.message} kind={error.kind} requestId={error.requestId} />}
    </form>
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <Button type="submit" form={formId} aria-disabled={busy || !complete}>{busy ? "Kaydediliyor…" : "Taslağı kaydet"}</Button>
        {dirty && !busy ? <ConfirmAction label="Vazgeç" confirmLabel="Değişiklikleri sil" busyLabel="Kapatılıyor…"
          question="Kaydedilmemiş değişiklikler silinsin mi?" onConfirm={async () => onCancel()} /> :
          <Button type="button" variant="secondary" aria-disabled={busy} onClick={onCancel}>Vazgeç</Button>}
        <p role="status" className="text-xs text-fg-muted">{busy ? "Taslak kaydediliyor…" : dirty ? "Kaydedilmemiş değişiklikler var." : "Henüz değişiklik yapılmadı."}</p>
      </div>
    </>
  );
}

function TextArea({ label, value, onChange, className = "", ...props }: Omit<ComponentProps<"textarea">, "onChange"> & {
  label: string; value: string; onChange: (value: string) => void;
}) {
  return <Field label={label}>{(control) => <textarea {...control} rows={4} {...props} value={value}
    onChange={(event) => onChange(event.target.value)} className={`${AUTHORING_CONTROL_CLASS} h-auto py-2 leading-6 ${className}`} />}</Field>;
}
