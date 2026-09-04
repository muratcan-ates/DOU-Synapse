"use client";

import { useEffect, useId, useRef, useState } from "react";
import { api } from "@/lib/api";
import { canSubmitAnswer, describeQuestion, EXAM_MODE, formatClock, isLastMinute,
  nextHintLevel, shownQuestions, showsHints, sourceInfo, tickRemaining, timeIsUp, timeNotice } from "@/lib/exam";
import type { AnswerFeedback, ExamFinish, ExamHint, ExamSession } from "@/lib/types";
import { useSubmit } from "@/lib/use-submit";
import { examStateChanged } from "@/lib/chat-availability";
import { ErrorNote } from "@/components/page-state";
import { SourceCard } from "@/components/source-card";
import { Badge, Button, ConfirmAction, EmptyState } from "@/components/ui";
import { QuestionBody, AnswerInput } from "@/components/exam/question-input";
import { FeedbackPanel } from "@/components/exam/feedback-panel";
import { FinishedExam } from "@/components/exam/finished-exam";

export function RunningExam({
  courseId,
  session,
  refreshError,
  onReload,
  onLeave,
  historyEnabled,
}: {
  courseId: string;
  session: ExamSession;
  refreshError: string | null;
  onReload: () => Promise<void>;
  onLeave: () => void;
  historyEnabled: boolean;
}) {
  const questions = shownQuestions(session);

  const [index, setIndex] = useState(0);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [feedbacks, setFeedbacks] = useState<Record<string, AnswerFeedback>>({});
  const [hints, setHints] = useState<Record<string, ExamHint[]>>({});
  const [finish, setFinish] = useState<ExamFinish | null>(null);

  /*
   * Cevap gönderme ve ipucu isteme aynı kancada: `busy` ve hata satırı zaten
   * ortaktı. Kanca erken dönüşlerden ÖNCE kurulmak zorunda (hook kuralı), o
   * yüzden soruya bağlı değerler kapanıştan değil argümandan gelir.
   */
  const {
    busy,
    error: actionError,
    setError: setActionError,
    submit: act,
  } = useSubmit(
    async (
      task:
        | { kind: "answer"; questionId: string; given: string; hintLevel: number }
        | { kind: "hint"; questionId: string; level: number },
    ) => {
      if (task.kind === "answer") {
        const result = await api.post<AnswerFeedback>(
          `/courses/${courseId}/exams/${session.id}/answers`,
          { question_id: task.questionId, given: task.given, hint_level: task.hintLevel },
        );
        setFeedbacks((prev) => ({ ...prev, [task.questionId]: result }));
        return;
      }
      const hint = await api.post<ExamHint>(`/courses/${courseId}/exams/${session.id}/hint`, {
        question_id: task.questionId,
        hint_level: task.level,
      });
      // Merdiven silinmez, birikir: öğrenci nereden geldiğini görür (DESIGN.md).
      setHints((prev) => ({
        ...prev,
        [task.questionId]: [...(prev[task.questionId] ?? []), hint],
      }));
    },
  );

  /*
   * Kalan süre: sunucunun değeriyle kurulur, saniyede bir yumuşatılır, her
   * sunucu turunda YENİDEN kurulur. İstemci saati asla kaynak değildir.
   */
  const serverRemaining = session.remaining_seconds;
  const [remaining, setRemaining] = useState<number | null>(serverRemaining);
  useEffect(() => setRemaining(serverRemaining), [serverRemaining]);

  const ticking = remaining !== null && remaining > 0;
  useEffect(() => {
    if (!ticking) return;
    const timer = setInterval(() => setRemaining(tickRemaining), 1000);
    return () => clearInterval(timer);
  }, [ticking]);

  /*
   * Yerel sayaç sıfırlandığında kararı sunucudan bir kez sorar. Sunucu "doldu"
   * derse ekran kapanır; demezse sayaç sunucunun değeriyle yeniden kurulur.
   */
  const timeUp = timeIsUp(session, remaining);
  useEffect(() => {
    if (remaining === 0 && !session.expired) void onReload();
  }, [remaining, session.expired, onReload]);

  const progressId = useId();
  const questionRef = useRef<HTMLHeadingElement>(null);
  const focusedIndex = useRef(index);

  /*
   * Soru değişince odak yeni soru metnine taşınır. Taşınmazsa odak "Sonraki
   * soru" düğmesinde kalır ve klavyeyle çalışan öğrenci ekranda ne değiştiğini
   * hiç duymaz; sayfanın tepesindeki metin sessizce başkalaşır.
   *
   * Karşılaştırma bayrakla değil son odaklanan soruyla yapılır: "ilk render mı"
   * bayrağı StrictMode'un efekti iki kez koşturduğu geliştirme ortamında sayfa
   * açılışında odağı çalardı.
   */
  useEffect(() => {
    if (focusedIndex.current === index) return;
    focusedIndex.current = index;
    questionRef.current?.focus();
  }, [index]);

  if (finish !== null || session.finished_at !== null) {
    return (
      <FinishedExam
        session={session}
        finish={finish}
        questions={questions}
        onRestart={onLeave}
        courseId={courseId}
        historyEnabled={historyEnabled}
      />
    );
  }

  if (questions.length === 0) {
    /*
     * Ölü dal değil: oturum açıldıktan sonra reddedilen sorular RLS ile
     * öğrenciye kapanır ve liste boşalabilir (`_load_questions` docstring'i).
     * Bu bir arıza olmadığı için kırmızı yok.
     */
    return (
      <EmptyState
        title="Bu oturumda gösterilebilecek soru kalmadı. Yeni bir sınav başlatabilirsiniz."
        action={
          <Button variant="secondary" onClick={onLeave}>
            Yeni sınav başlat
          </Button>
        }
      />
    );
  }

  const question = questions[Math.min(index, questions.length - 1)];
  const view = describeQuestion(question);
  const feedback = feedbacks[question.id];
  const draft = drafts[question.id] ?? "";
  const answered = question.answered || feedback !== undefined;
  const rungs = hints[question.id] ?? [];
  const lastRung = rungs.length > 0 ? rungs[rungs.length - 1].hint_level : 0;
  const upcomingHint = nextHintLevel(lastRung);

  const submittable =
    view.kind !== "unsupported" &&
    canSubmitAnswer({
      session,
      question: { ...question, answered },
      draft,
      localRemaining: remaining,
    });

  const goTo = (next: number) => {
    setActionError(null);
    setIndex(next);
  };

  const submit = () => {
    if (!submittable) return;
    return act({
      kind: "answer",
      questionId: question.id,
      given: draft.trim(),
      hintLevel: lastRung,
    });
  };

  const askHint = (level: number) =>
    act({ kind: "hint", questionId: question.id, level });

  return (
    <div className="mx-auto max-w-2xl">
      {historyEnabled && (
        <div className="mb-4">
          <Button variant="ghost" onClick={onLeave}>Oturumlara dön</Button>
        </div>
      )}
      <div className="mb-8 flex flex-wrap items-center justify-between gap-3 text-sm">
        <span id={progressId} className="text-fg-muted">
          Soru{" "}
          <span className="font-medium text-fg">
            {index + 1}/{questions.length}
          </span>
        </span>

        <div className="flex items-center gap-3">
          <Badge tone="neutral">{EXAM_MODE[session.mode].label}</Badge>
          {remaining !== null && (
            /*
              `role="timer"` örtük olarak aria-live="off" taşır: sayaç görsel
              olarak saniyede güncellenir ama kendiliğinden okunmaz. Anlamlı
              duyuru aşağıdaki eşik bölgesinden gelir.
            */
            <span
              role="timer"
              className={`font-mono tabular-nums ${
                isLastMinute(remaining) ? "font-medium text-warning" : "text-fg-muted"
              }`}
            >
              <span className="sr-only">Kalan süre </span>
              {formatClock(remaining)}
            </span>
          )}
          <ConfirmAction
            label="Sınavı bitir"
            confirmLabel="Bitir ve sonucu gör"
            busyLabel="Bitiriliyor…"
            question="Sınav kapanır ve yeni cevap kabul edilmez."
            onConfirm={async () => {
              const result = await api.post<ExamFinish>(
                `/courses/${courseId}/exams/${session.id}/finish`,
              );
              setFinish(result);
              // Kilit kalkışı da haber verilir: kilitliyken koşan yoklama bunu
              // 30 saniye içinde görürdü, ama bekletmenin bir sebebi yok.
              examStateChanged();
              await onReload();
            }}
          />
        </div>
      </div>

      {/* Yalnız eşiklerde konuşur; metin değişmediği sürece yeniden okunmaz. */}
      <p role="status" className="sr-only">
        {timeNotice(remaining)}
      </p>

      {timeUp && (
        <div className="mb-6 rounded-lg border border-border bg-surface p-4">
          <p className="prose-tr text-sm text-fg">
            Süre doldu. Yeni cevap kabul edilmiyor; sonucu görmek için sınavı bitirin.
          </p>
        </div>
      )}

      {/* Tazeleme hatası sayfayı silmez: sınav ekranda kalır, uyarı satır içi durur. */}
      {refreshError && (
        <div className="mb-6">
          <ErrorNote message={refreshError} onRetry={onReload} />
        </div>
      )}

      <QuestionBody
        view={view}
        headingRef={questionRef}
        describedBy={progressId}
        answered={answered}
      />

      {view.kind === "unsupported" ? (
        <p className="prose-tr mt-6 rounded-lg border border-border bg-surface p-4 text-sm text-fg-muted">
          Bu soru tipi bu sürümde gösterilemiyor, bu yüzden atlandı. Boş bırakılan
          sorular yanlış sayılmaz.
        </p>
      ) : answered ? (
        <div className="mt-6 rounded-lg border border-border bg-surface p-4">
          <p className="text-sm text-fg-muted">Bu soruyu cevapladınız.</p>
          {draft.trim() !== "" && (
            <p className="prose-tr mt-2 text-sm text-fg">Gönderdiğiniz cevap: {draft.trim()}</p>
          )}
        </div>
      ) : (
        <AnswerInput
          view={view}
          questionId={question.id}
          draft={draft}
          disabled={timeUp}
          onChange={(value) => setDrafts((prev) => ({ ...prev, [question.id]: value }))}
        />
      )}

      {!answered && view.kind !== "unsupported" && (
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Button aria-disabled={!submittable || busy} onClick={() => void submit()}>
            {busy ? "Gönderiliyor…" : "Cevabı gönder"}
          </Button>
          {/*
            İpucu yüzeyi sınav modunda HİÇ çizilmez (sunucu 403 verir); merdivenin
            son kademesinde de düğme kalmaz — iş yapmayan buton kusurdur.
          */}
          {showsHints(session.mode) && upcomingHint !== null && !timeUp && (
            <Button variant="secondary" aria-disabled={busy} onClick={() => void askHint(upcomingHint)}>
              {rungs.length === 0 ? "İpucu al" : "Sonraki ipucu"}
            </Button>
          )}
        </div>
      )}

      {actionError && (
        <div className="mt-4">
          <ErrorNote message={actionError} />
        </div>
      )}

      {rungs.length > 0 && <HintLadder rungs={rungs} />}

      {feedback && <FeedbackPanel feedback={feedback} />}

      <div className="mt-10 flex items-center justify-between gap-4">
        {/*
          Gezinme düğmeleri `disabled` yerine `aria-disabled` kullanır: tarayıcı
          devre dışı bırakılan öğeden odağı <body>'ye atar, yani "Önceki"ye
          basıp ilk soruya dönen klavye kullanıcısı odağını kaybederdi.
        */}
        <Button
          variant="secondary"
          aria-disabled={index === 0}
          onClick={() => goTo(Math.max(0, index - 1))}
        >
          Önceki
        </Button>
        <Button
          variant="secondary"
          aria-disabled={index === questions.length - 1}
          onClick={() => goTo(Math.min(questions.length - 1, index + 1))}
        >
          Sonraki soru
        </Button>
      </div>
    </div>
  );
}

function HintLadder({ rungs }: { rungs: ExamHint[] }) {
  return (
    <div className="mt-6 rounded-lg border border-border bg-surface">
      <p className="border-b border-border px-5 py-3 text-sm font-medium text-fg">
        İpuçları
      </p>
      <ol className="divide-y divide-border">
        {rungs.map((rung, position) => (
          <li key={`${rung.hint_level}-${position}`} className="px-5 py-4">
            <p className="text-xs font-medium text-fg-subtle">{rung.hint_level}. ipucu</p>
            <p className="prose-tr mt-1 text-sm leading-6 whitespace-pre-line text-fg">
              {rung.text}
            </p>
            <div className="mt-3">
              <SourceCard source={sourceInfo(rung.source)} />
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
