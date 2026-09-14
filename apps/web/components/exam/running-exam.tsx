"use client";

import { useEffect, useId, useRef, useState } from "react";
import { sourceContextHref } from "@/lib/source-quality";
import { api } from "@/lib/api";
import { examAnswerValue, submittedAnswerText } from "@/lib/exam-answer";
import { appendExamHint, canSubmitAnswer, describeQuestion, EXAM_MODE, formatClock, HINT_MAX_LEVEL, isLastMinute,
  nextHintLevel, shownQuestions, showsHints, sourceInfo, tickRemaining, timeIsUp, timeNotice } from "@/lib/exam";
import type { AnswerFeedback, ExamFinish, ExamHint, ExamSession } from "@/lib/types";
import { useSubmit } from "@/lib/use-submit";
import { useExamDrafts } from "@/lib/use-exam-drafts";
import { examStateChanged, type ChatLock } from "@/lib/chat-availability";
import { ErrorNote, Loading } from "@/components/page-state";
import { SourceCard } from "@/components/source-card";
import { Button, Card, ConfirmAction, EmptyState } from "@/components/ui";
import { QuestionBody, AnswerInput } from "@/components/exam/question-input";
import { FeedbackPanel } from "@/components/exam/feedback-panel";
import { SavedPracticeFeedback } from "@/components/exam/saved-practice-feedback";
import { FinishedExam } from "@/components/exam/finished-exam";

export function RunningExam({
  courseId,
  userId,
  helpLock,
  session,
  refreshError,
  onReload,
  onLeave,
  historyEnabled,
}: {
  courseId: string;
  userId: string;
  helpLock: ChatLock;
  session: ExamSession;
  refreshError: string | null;
  onReload: () => Promise<void>;
  onLeave: () => void;
  historyEnabled: boolean;
}) {
  const questions = shownQuestions(session);

  const [index, setIndex] = useState(0);
  const draftStore = useExamDrafts({ userId, courseId, sessionId: session.id }, session, historyEnabled);
  const drafts = draftStore.drafts;
  const [submitted, setSubmitted] = useState<Record<string, string>>({});
  const helpAvailable = session.mode === "exam" ||
    (helpLock.ready && !helpLock.locked && !helpLock.error && !helpLock.refreshError);
  const [feedbacks, setFeedbacks] = useState<Record<string, AnswerFeedback>>({});
  const [hints, setHints] = useState<Record<string, ExamHint[]>>({});
  const [finish, setFinish] = useState<ExamFinish | null>(null);
  useEffect(() => {
    // Odağa dönüşte eski açık kararını önce geçersizleştir; ağ yanıtını beklerken
    // başka sekmede başlamış sınavın yanında eski çözüm görünmesin.
    const refresh = () => {
      if (session.finished_at !== null) setFinish(null);
      examStateChanged();
    };
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, [session.finished_at]);
  useEffect(() => {
    if (session.mode === "practice" && !helpAvailable) {
      setFeedbacks({});
      setHints({});
    }
  }, [session.mode, helpAvailable]);

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
        setSubmitted((prev) => ({ ...prev, [task.questionId]: task.given }));
        draftStore.discard(task.questionId);
        await onReload();
        return;
      }
      let hint: ExamHint;
      try {
        hint = await api.post<ExamHint>(`/courses/${courseId}/exams/${session.id}/hint`, {
          question_id: task.questionId,
          hint_level: task.level,
        });
      } catch (error) {
        // Ekran açıkken eğitmen ipuçlarını kapatmış veya sınav başlamış olabilir.
        await helpLock.reload();
        throw error;
      }
      // Eğitmen sınırı düşürdüyse sunucu önceki kademeyi döndürebilir. Aynı
      // ipucunu ekleme; yeni politikayı okumadan sonraki isteği açma.
      setHints((prev) => {
        const previous = prev[task.questionId] ?? [];
        const updated = appendExamHint(previous, hint);
        return updated === previous ? prev : { ...prev, [task.questionId]: updated };
      });
      if (hint.hint_level < task.level) await helpLock.reload();
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

  const finishAction = (
    <ConfirmAction
      label="Sınavı bitir"
      confirmLabel="Bitir ve sonucu gör"
      busyLabel="Bitiriliyor…"
      question="Sınav kapanır ve yeni cevap kabul edilmez."
      onConfirm={async () => {
        const result = await api.post<ExamFinish>(
          `/courses/${courseId}/exams/${session.id}/finish`,
        );
        draftStore.clear();
        setFinish(result);
        examStateChanged();
        await onReload();
      }}
    />
  );

  if (finish !== null || session.finished_at !== null) {
    return (
      <FinishedExam
        session={session}
        finish={finish}
        questions={questions}
        onRestart={onLeave}
        courseId={courseId}
        historyEnabled={historyEnabled}
        helpLock={helpLock}
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
        title="Bu oturumda gösterilebilecek soru kalmadı. Oturumu bitirerek sonuç özetini görebilirsiniz."
        action={finishAction}
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
  const upcomingHint = nextHintLevel(lastRung, helpLock.hintLimit);

  const submittable =
    view.kind !== "unsupported" && draftStore.ready && helpAvailable &&
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
    const given = examAnswerValue(question.type, draft);
    if (given === null) return;
    return act({
      kind: "answer",
      questionId: question.id,
      given,
      hintLevel: lastRung,
    });
  };

  const askHint = (level: number) =>
    act({ kind: "hint", questionId: question.id, level });

  return (
    <div className="mx-auto w-full max-w-4xl">
      {historyEnabled && (
        <div className="mb-4">
          <Button variant="ghost" onClick={onLeave}>Oturumlara dön</Button>
        </div>
      )}
      {/*
        Oturum başlığı, soru sayacı ve kalan süre tek yükselmiş yüzeyde
        (DESIGN.md §Sınav ekranı, §Aksan disiplini): sayaç büyük ve tabular,
        süre nötr ve sessiz. Hareket yok; sayaç yanıp sönmez.
      */}
      <Card className="mb-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0">
            <p className="text-sm font-medium text-fg">{EXAM_MODE[session.mode].label}</p>
            {/* Soru başlığının `aria-describedby`'ı buraya bağlıdır: "Soru 3 / 5" okunur. */}
            <p
              id={progressId}
              className="mt-1 text-2xl leading-none font-semibold tracking-tight tabular-nums text-fg"
            >
              <span className="sr-only">Soru </span>
              {/* Boşluksuz: sayaç metni kullanıcıya görünen bir etikettir ve
                  kabuk turunun kuralı "etiket değişmez"di. 99d78d6 bunu
                  "2 / 3"e çevirince flows.spec.ts:704 haklı olarak kırıldı. */}
              {index + 1}/{questions.length}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            {remaining !== null && (
              /*
                `role="timer"` örtük olarak aria-live="off" taşır: sayaç görsel
                olarak saniyede güncellenir ama kendiliğinden okunmaz. Anlamlı
                duyuru aşağıdaki eşik bölgesinden gelir. Son 60 saniyede
                `--warning`'e döner; kırmızı ve yanıp sönme yok (DESIGN.md).
              */
              <span
                role="timer"
                className={`rounded-xl bg-surface-sunken px-4 py-3 text-lg tabular-nums ${
                  isLastMinute(remaining) ? "font-medium text-warning" : "text-fg-muted"
                }`}
              >
                <span className="sr-only">Kalan süre </span>
                {formatClock(remaining)}
              </span>
            )}
            {finishAction}
          </div>
        </div>
      </Card>

      {/* Yalnız eşiklerde konuşur; metin değişmediği sürece yeniden okunmaz. */}
      <p role="status" className="sr-only">
        {timeNotice(remaining)}
      </p>

      {timeUp && (
        /* Bilgi satırı, hata değil: çukur yüzey, kırmızı yok. */
        <Card variant="soft" className="mb-6 px-4 py-4">
          <p className="prose-tr text-sm text-fg">
            Süre doldu. Yeni cevap kabul edilmiyor; sonucu görmek için sınavı bitirin.
          </p>
        </Card>
      )}

      {/* Tazeleme hatası sayfayı silmez: sınav ekranda kalır, uyarı satır içi durur. */}
      {refreshError && (
        <div className="mb-6">
          <ErrorNote message={refreshError} onRetry={onReload} />
        </div>
      )}

      {session.mode === "practice" && !helpAvailable && (
        <div className="mb-6">
          {!helpLock.ready ? <Loading label="Çalışma durumu doğrulanıyor…" /> :
            helpLock.error || helpLock.refreshError ? <ErrorNote message={helpLock.error ?? helpLock.refreshError ?? ""} onRetry={helpLock.reload} /> :
            <p role="status" className="prose-tr text-sm text-fg-muted">{helpLock.message}</p>}
        </div>
      )}
      <nav aria-label="Soru gezintisi" className="mb-6 flex flex-wrap gap-2">
        {questions.map((item, position) => <button key={item.id} type="button"
          aria-current={position === index ? "step" : undefined}
          aria-label={`Soru ${position + 1}${item.answered || feedbacks[item.id] ? ", cevaplandı" : ""}`}
          onClick={() => goTo(position)}
          className={`flex h-11 min-w-11 items-center justify-center rounded-xl border px-3 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${position === index ? "border-fg bg-fg text-surface" : "border-border-strong bg-surface text-fg hover:bg-surface-sunken"}`}>
          {position + 1}
          {(item.answered || feedbacks[item.id]) && <span aria-hidden="true" className="ml-1">✓</span>}
        </button>)}
      </nav>
      <Card className="min-w-0">
      <QuestionBody
        view={view}
        headingRef={questionRef}
        describedBy={progressId}
        answered={answered}
      />

      {view.kind === "unsupported" ? (
        <Card variant="soft" className="mt-6 px-4 py-4">
          <p className="prose-tr text-sm text-fg-muted">
            Bu soru tipi bu sürümde gösterilemiyor, bu yüzden atlandı. Boş bırakılan
            sorular yanlış sayılmaz.
          </p>
        </Card>
      ) : answered ? (
        <Card variant="soft" className="mt-6 px-4 py-4">
          <p className="text-sm text-fg-muted">Bu soruyu cevapladınız.</p>
          {submitted[question.id] !== undefined && (
            question.type === "code_trace" ? (
              <div className="mt-2">
                <p className="text-sm text-fg-muted">Gönderdiğiniz cevap:</p>
                {/* Kod çıktısı yalnız kod bloğunda mono kalır. */}
                <pre className="mt-1 overflow-x-auto whitespace-pre-wrap font-mono text-sm text-fg"><code>{submitted[question.id]}</code></pre>
              </div>
            ) : (
              <p className="prose-tr mt-2 text-sm whitespace-pre-line text-fg">Gönderdiğiniz cevap: {submittedAnswerText(question.type, submitted[question.id])}</p>
            )
          )}
        </Card>
      ) : (
        <AnswerInput
          view={view}
          questionType={question.type}
          questionId={question.id}
          draft={draft}
          disabled={timeUp || !draftStore.ready || !helpAvailable}
          onChange={(value) => draftStore.change(question.id, value)}
        />
      )}

      {!answered && historyEnabled && (
        <p role="status" className="prose-tr mt-2 text-xs text-fg-muted">
          {!draftStore.available ? "Tarayıcı taslağı saklayamıyor. Sayfayı yenilemeden cevabınızı gönderin." :
            draft.length > 0 ? "Gönderilmemiş taslağınız bu sekmede saklandı. Sekmeyi kapatınca veya çıkış yapınca silinir." : ""}
        </p>
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
          {showsHints(session.mode) && helpAvailable && upcomingHint !== null && !timeUp && (
            <Button variant="secondary" aria-disabled={busy} onClick={() => void askHint(upcomingHint)}>
              {rungs.length === 0 ? "İpucu al" : "Sonraki ipucu"}
            </Button>
          )}
        </div>
      )}

      </Card>
      {actionError && (
        <div className="mt-4">
          <ErrorNote message={actionError} />
        </div>
      )}

      {helpAvailable && rungs.length > 0 && <HintLadder courseId={courseId} sessionId={session.id} rungs={rungs} />}

      {session.mode === "practice" && historyEnabled ? (
        answered && helpAvailable && <SavedPracticeFeedback key={question.id} courseId={courseId} sessionId={session.id} questionId={question.id} onLocked={helpLock.reload} />
      ) : helpAvailable && feedback && <FeedbackPanel sessionId={session.id} courseId={courseId} feedback={feedback} />}

      <div className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-[20px] border border-border bg-surface p-5">
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

/**
 * Sokratik ipucu merdiveni (DESIGN.md §Components): her ipucu bir öncekinin
 * altında kalır, silinmez. Kademe göstergesi ilerleme çubuğu değil dört ayrık
 * segmenttir ve sayı yazmaz; "4 adımda biter" hissi düşünmeyi hızlandırma
 * baskısı üretir. Ulaşılan kademe metin rengiyle dolar, aksan rengiyle değil.
 */
function HintLadder({ courseId, sessionId, rungs }: { courseId: string; sessionId: string; rungs: ExamHint[] }) {
  const reached = rungs.length > 0 ? rungs[rungs.length - 1].hint_level : 0;
  return (
    <Card variant="flat" padding="none" className="mt-6">
      <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-3">
        <p className="text-sm font-medium text-fg">İpuçları</p>
        <div aria-hidden="true" className="flex items-center gap-1">
          {Array.from({ length: HINT_MAX_LEVEL }, (_, position) => (
            <span
              key={position}
              className={`h-1.5 w-5 rounded-sm ${position < reached ? "bg-fg" : "bg-border"}`}
            />
          ))}
        </div>
      </div>
      <ol className="divide-y divide-border">
        {rungs.map((rung, position) => (
          <li key={`${rung.hint_level}-${position}`} className="px-5 py-4">
            <p className="text-xs font-medium tabular-nums text-fg-subtle">{rung.hint_level}. ipucu</p>
            <p className="prose-tr mt-2 text-base leading-7 whitespace-pre-line text-fg">
              {rung.text}
            </p>
            <div className="mt-3">
              <SourceCard source={sourceInfo(rung.source)} href={sourceContextHref(courseId, rung.source.chunk_id)} learningContext={{ courseId, sessionId, chunkId: rung.source.chunk_id }} />
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}
