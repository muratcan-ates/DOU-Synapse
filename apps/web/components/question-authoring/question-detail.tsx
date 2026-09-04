import { DIFFICULTY_LABEL, type LearningOutcome } from "@/lib/blueprint";
import { QUESTION_STATUS, QUESTION_TYPE } from "@/lib/labels";
import { ANSWER_FORMAT, toQuestionView, type QuestionView } from "@/lib/questions";
import type { Question } from "@/lib/types";
import { ErrorNote } from "@/components/page-state";
import { SourceCard } from "@/components/source-card";
import { Badge, Button, Card } from "@/components/ui";
import { DraftEditor } from "./draft-editor";

export function QuestionDetail({
  courseId, authoringEnabled, outcomes, editing, generating, onEdit, onSaved, onCancelEdit,
  stemRef,
  question,
  topic,
  outsideFilter,
  busy,
  notice,
  decisionError,
  hasNextDraft,
  onDecide,
  onNextDraft,
}: {
  courseId: string;
  authoringEnabled: boolean;
  outcomes: LearningOutcome[];
  editing: boolean;
  generating: boolean;
  onEdit: () => void;
  onSaved: (updated: Question) => void;
  onCancelEdit: () => void;
  stemRef: React.RefObject<HTMLHeadingElement | null>;
  question: Question;
  topic: string;
  outsideFilter: boolean;
  busy: boolean;
  notice: string | null;
  decisionError: string | null;
  hasNextDraft: boolean;
  onDecide: (status: "approved" | "rejected") => void;
  onNextDraft: () => void;
}) {
  const view = toQuestionView(question);
  const status = QUESTION_STATUS[question.status];

  return (
    <Card className="min-w-0">
      <div className="mb-5 flex flex-wrap items-center gap-2">
        <Badge tone="neutral">{QUESTION_TYPE[question.type]}</Badge>
        <Badge tone={status.tone}>{status.label}</Badge>
        {view.answerFormat && (
          <Badge tone="neutral">{ANSWER_FORMAT[view.answerFormat]}</Badge>
        )}
        <span className="text-xs text-fg-subtle">{topic}</span>
      </div>

      <p className="prose-tr mb-4 text-xs text-fg-muted">
        {question.learning_outcome_id
          ? `Öğrenme çıktısı: ${outcomes.find((outcome) => outcome.id === question.learning_outcome_id)?.code ?? "Kayıtlı çıktı"}`
          : "Öğrenme çıktısı: Sınıflandırılmadı"}
        {" · "}Zorluk: {question.difficulty ? DIFFICULTY_LABEL[question.difficulty] : "Sınıflandırılmadı"}
      </p>
      {question.source_stale && <p role="status" className="prose-tr mb-4 rounded-lg border border-warning bg-warning-bg px-4 py-3 text-sm text-warning">
        Bu sorunun kaynağı yeni bir sürümle değiştirilmiş. Onaylamadan önce güncel materyalle karşılaştırın.
      </p>}
      {outsideFilter && (
        <p className="mb-4 text-xs text-fg-muted">
          Bu soru seçili süzgeçte görünmüyor; kararınızı görebilesiniz diye
          panelde tutuluyor.
        </p>
      )}

      {/*
        Panelin başlığı soru metnidir; "sıradaki taslağa geç" sonrası odak
        buraya taşınır, bu yüzden `tabIndex={-1}` (klavye sırasına GİRMEZ,
        yalnız programla odaklanabilir).
      */}
      <h2
        ref={stemRef}
        tabIndex={-1}
        className="prose-tr rounded-lg text-lg font-normal text-fg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand"
      >
        {view.stem ?? "Soru metni bu kayıtta yok."}
      </h2>

      {!editing && <QuestionBody view={view} />}

      <div className="mt-6">
        <h3 className="mb-2 text-xs font-medium text-fg-muted">
          Üretimde kullanılan kaynak
        </h3>
        {view.source ? (
          <SourceCard source={view.source} />
        ) : (
          /*
            Kaynağı olmayan soru bir hata ekranı değil ama sessiz de geçilmez:
            onay kararı "bu materyalde gerçekten var mı" sorusudur ve kaynak
            görünmüyorsa eğitmen onu göremeden onaylamamalı (Anayasa I).
          */
          <p className="rounded-lg border border-border bg-bg px-4 py-3 text-sm text-fg-muted">
            Bu sorunun kaynak parçası okunamadı. Kaynağı görmeden onaylamayın.
          </p>
        )}
      </div>

      {/*
        `disabled` yerine `aria-disabled`: tarayıcı devre dışı bırakılan öğeden
        odağı <body>'ye atar, yani kararı veren klavye kullanıcısı odağını
        tamamen kaybederdi. `Button` aria-disabled'ta tıklamayı zaten yutuyor
        (components/ui.tsx).
      */}
      {editing ? <DraftEditor key={question.id} courseId={courseId} question={question}
        outcomes={outcomes} onSaved={onSaved} onCancel={onCancelEdit} /> : <>
      <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-border pt-5">
        {authoringEnabled && question.status === "draft" && <Button variant="secondary"
          aria-disabled={busy || generating} onClick={onEdit}>Taslağı düzenle</Button>}
        <Button
          variant="primary"
          aria-disabled={busy || generating || question.status === "approved"}
          onClick={() => onDecide("approved")}
        >
          {question.status === "approved" ? "Onaylandı" : "Onayla ve öğrenciye aç"}
        </Button>
        <Button
          variant="secondary"
          aria-disabled={busy || generating || question.status === "rejected"}
          onClick={() => onDecide("rejected")}
        >
          {question.status === "rejected" ? "Reddedildi" : "Reddet"}
        </Button>
        {hasNextDraft && (
          <Button variant="ghost" aria-disabled={busy || generating} onClick={onNextDraft}>
            Sıradaki taslağa geç
          </Button>
        )}
      </div>

      <p className="mt-3 text-xs text-fg-subtle">
        Onaylanmayan soru öğrenci akışında hiç görünmez.
      </p>

      {/*
        Karar sonucu: hem görünür hem duyurulur. `role="status"` örtük olarak
        polite'tır — karar bir hata değildir, `alert` kullanılmaz.
      */}
      <p role="status" className="mt-2 text-xs text-fg-muted">
        {busy ? "Karar kaydediliyor…" : (notice ?? "")}
      </p>

      {decisionError && <ErrorNote message={decisionError} />}
      </>}
    </Card>
  );
}

/** Tipe göre değişen gövde: şıklar, kod, cevap anahtarı, rubrik. */
function QuestionBody({ view }: { view: QuestionView }) {
  return (
    <>
      {view.options.length > 0 && (
        <ul className="mt-5 space-y-2">
          {view.options.map((option) => (
            <li
              key={option.key}
              className={`flex items-start gap-3 rounded-lg border px-4 py-3 text-sm ${
                option.correct
                  ? "border-success bg-success-bg text-fg"
                  : "border-border text-fg-muted"
              }`}
            >
              {/* Renk tek başına bilgi taşımaz: doğru şıkta metin de var. */}
              <span className="mt-0.5 w-14 shrink-0 text-xs text-fg-subtle">
                {option.key}
                {option.correct ? " · doğru" : ""}
              </span>
              <span className="prose-tr">{option.text}</span>
            </li>
          ))}
        </ul>
      )}

      {view.code && (
        <div className="mt-5">
          <h3 className="mb-2 text-xs font-medium text-fg-muted">
            Kod{view.code.language ? ` · ${view.code.language}` : ""}
          </h3>
          <pre className="overflow-x-auto rounded-lg border border-border bg-bg px-4 py-3">
            <code className="font-mono text-xs text-fg">{view.code.code}</code>
          </pre>
        </div>
      )}

      {view.answerKey && (
        <Section title="Cevap anahtarı">
          <p className="prose-tr rounded-lg border border-border bg-bg px-4 py-3 text-sm text-fg">
            {view.answerKey}
          </p>
        </Section>
      )}

      {view.bugAnswer && (
        <Section title="Cevap anahtarı">
          <dl className="space-y-1 rounded-lg border border-border bg-bg px-4 py-3 text-sm">
            <Row label="Hatalı satır" value={view.bugAnswer.line?.toString() ?? null} />
            <Row label="Hata türü" value={view.bugAnswer.bugType} />
            <Row label="Düzeltme" value={view.bugAnswer.fixSummary} />
          </dl>
        </Section>
      )}

      {view.acceptedAnswers.length > 0 && (
        <Section title="Kabul edilen karşılıklar">
          <div className="flex flex-wrap gap-2">
            {view.acceptedAnswers.map((answer) => (
              <span
                key={answer}
                className="rounded-sm border border-border bg-bg px-2.5 py-0.5 font-mono text-xs text-fg-muted"
              >
                {answer}
              </span>
            ))}
          </div>
        </Section>
      )}

      {view.keyPoints.length > 0 && (
        <Section title="Cevapta aranan noktalar">
          <ul className="space-y-1">
            {view.keyPoints.map((point) => (
              <li key={point} className="prose-tr text-sm text-fg-muted">
                · {point}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {view.rubric.length > 0 && (
        <Section title="Puanlama ölçütü">
          <dl className="space-y-1">
            {view.rubric.map((item) => (
              <div key={item.point} className="flex items-baseline justify-between gap-3">
                <dt className="prose-tr text-sm text-fg-muted">{item.point}</dt>
                <dd className="font-mono text-xs text-fg-subtle">{item.weight}</dd>
              </div>
            ))}
          </dl>
        </Section>
      )}

      {view.explanation && (
        <Section title="Gerekçe">
          <p className="prose-tr text-sm text-fg-muted">{view.explanation}</p>
        </Section>
      )}
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-6">
      <h3 className="mb-2 text-xs font-medium text-fg-muted">{title}</h3>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string | null }) {
  if (value === null) return null;
  return (
    <div className="flex items-baseline gap-2">
      <dt className="shrink-0 text-xs text-fg-subtle">{label}</dt>
      <dd className="prose-tr text-fg">{value}</dd>
    </div>
  );
}

