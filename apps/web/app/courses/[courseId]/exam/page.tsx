"use client";

/**
 * Sınav provası — gerçek sınav motoruna bağlı (T034).
 *
 * Örnek veri ve önizleme şeridi kaldırıldı: uçlar canlı, ekranın "yakında"
 * demesi çalışan bir ürünü çalışmıyor gösteriyordu.
 *
 * Ekranın taşıdığı beş kural:
 *
 *  - **Süre sunucunundur.** `remaining_seconds` ve `expired` sunucunun
 *    kararıdır; buradaki sayaç yalnız görsel yumuşatmadır ve her sunucu turunda
 *    yeniden senkronlanır. Süre dolduysa cevap gönderilmez.
 *  - **Sayaç konuşmaz.** `role="timer"` örtük olarak `aria-live="off"` taşır;
 *    duyuru yalnız eşiklerde değişen ayrı bir bölgeden gelir. Saniyede bir
 *    konuşan bir sayaç 20 dakikalık sınavı ekran okuyucuyla yapılamaz kılar.
 *  - **Puan uydurulmaz.** `graded: false` gelen cevapta puan YOKTUR; ekran
 *    sunucunun `message` alanını gösterir. Bitişte `ungraded_count` varsa
 *    puanın eksik paydayla hesaplandığı söylenir.
 *  - **Açıklama kaynaklıdır.** `why_wrong` ve `evidence` birer `SourceRef`'tir
 *    ve `SourceCard` ile gösterilir; kaynaksız açıklama gösterilmez (Anayasa I).
 *  - **Mod farkı yüzeydedir.** `practice` ipucu verir; `exam` modunda ipucu
 *    düğmesi devre dışı değil, HİÇ render edilmez (Anayasa XI).
 *
 * Saf mantık (payload daraltma, süre eşikleri, geri bildirim okuma) `lib/exam.ts`
 * içinde ve `lib/exam.test.ts` ile sınanıyor; burada yalnız durum ve yerleşim var.
 *
 * Giriş animasyonu (`rise`) sınav akışında KULLANILMAZ: DESIGN.md sınav
 * ekranında hareketi kaygı üreticisi sayar.
 */

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import {
  ANSWER_MAX_LENGTH,
  answerVerdict,
  canSubmitAnswer,
  describeQuestion,
  describeSolution,
  EXAM_MODE,
  examSessionKey,
  formatClock,
  formatScore,
  isEmptyPool,
  isLastMinute,
  nextHintLevel,
  SCORE_SCALE,
  shouldPoll,
  shownQuestions,
  showsHints,
  sourceInfo,
  tickRemaining,
  timeIsUp,
  timeNotice,
  VERDICT_LABEL,
  type QuestionView,
} from "@/lib/exam";
import type {
  AnswerFeedback,
  ExamFinish,
  ExamHint,
  ExamMode,
  ExamQuestion,
  ExamSession,
} from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { useSubmit } from "@/lib/use-submit";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { examStateChanged } from "@/lib/chat-availability";
import { Field } from "@/components/field";
import { ErrorNote, Loading, MetricRow, PageHeader } from "@/components/page-state";
import { SourceCard } from "@/components/source-card";
import { Badge, Button, Card, ConfirmAction, EmptyState, Input } from "@/components/ui";

/**
 * Çok satırlı girdinin kabuğu.
 *
 * `ui.tsx`'te `Textarea` yok; `Input`'un ölçüleri tek satır için sabit
 * (`h-11`). Buradaki sınıf o ölçülerin çok satırlı eşi. Üçüncü kopya olmadan
 * ortak bileşene çıkarılmalı (bkz. rapor: `components/ui.tsx` → `Textarea`).
 */
const TEXTAREA_CLASS =
  "w-full rounded-lg border border-border-strong bg-surface px-3 py-2 text-sm leading-6 text-fg placeholder:text-fg-subtle focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand";

/** Kanca `data === null`'ı "yükleniyor" sayar; "oturum yok" ayrı bir değerdir. */
interface ExamView {
  session: ExamSession | null;
}

export default function ExamPage() {
  const { courseId } = useParams<{ courseId: string }>();

  return (
    <AppShell>
      <CourseNav courseId={courseId} />
      <ExamScreen courseId={courseId} />
    </AppShell>
  );
}

function ExamScreen({ courseId }: { courseId: string }) {
  /*
   * Açık oturumun kimliği tarayıcıda yaşar: öğrencinin oturumlarını listeleyen
   * bir uç yok, yani yenilenen sayfa kimliği kaybederse öğrenci başlamış
   * sınavına dönemez ve cevapladığı sorular ona kapalı kalır (soru başına tek
   * deneme). `restored`, "oturum yok" ile "henüz bilinmiyor"u ayırır: ikisini
   * karıştıran ekran, açık sınavın üstüne başlangıç ekranını çizer.
   */
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [restored, setRestored] = useState(false);

  useEffect(() => {
    setSessionId(localStorage.getItem(examSessionKey(courseId)));
    setRestored(true);
  }, [courseId]);

  const rememberSession = useCallback(
    (id: string | null) => {
      if (id === null) localStorage.removeItem(examSessionKey(courseId));
      else localStorage.setItem(examSessionKey(courseId), id);
      setSessionId(id);
    },
    [courseId],
  );

  const fetchSession = useCallback(async (): Promise<ExamView> => {
    if (!restored || sessionId === null) return { session: null };
    try {
      return { session: await api.get<ExamSession>(`/courses/${courseId}/exams/${sessionId}`) };
    } catch (e) {
      /*
       * Saklanan kimlik başka bir ortamdan kalmış ya da silinmiş olabilir.
       * 404'te kaydı temizleyip başlangıca dönmek, kullanıcıyı depoyu elle
       * temizleyemeyeceği bir hata ekranında kilitlemekten iyidir (Anayasa IV).
       */
      if (e instanceof ApiError && e.status === 404) {
        localStorage.removeItem(examSessionKey(courseId));
        return { session: null };
      }
      throw e;
    }
  }, [courseId, sessionId, restored]);

  const exam = useResource(fetchSession, [courseId, sessionId, restored], {
    // Süre tazelemesi: yalnız süreli ve açık oturumda; bitince durur.
    pollWhile: (view) => view.session !== null && shouldPoll(view.session),
    intervalMs: 15000,
  });

  if (!restored || exam.loading) return <Loading />;
  if (exam.error) return <ErrorNote message={exam.error} onRetry={exam.reload} />;
  if (exam.data === null) return <Loading />;

  const session = exam.data.session;

  if (session === null) {
    return <StartPanel courseId={courseId} onStarted={rememberSession} />;
  }

  return (
    <RunningExam
      // Oturum değişince bütün yerel durum (taslak, geri bildirim, ipucu)
      // sıfırlanmalı; `key` bunu React'ın kendi diliyle yapar.
      key={session.id}
      courseId={courseId}
      session={session}
      refreshError={exam.refreshError}
      onReload={exam.reload}
      onLeave={() => rememberSession(null)}
    />
  );
}

/* -------------------------------------------------------------------------
 * Başlangıç
 * ---------------------------------------------------------------------- */

function StartPanel({
  courseId,
  onStarted,
}: {
  courseId: string;
  onStarted: (id: string) => void;
}) {
  const [busy, setBusy] = useState<ExamMode | null>(null);
  const [failure, setFailure] = useState<{ message: string; emptyPool: boolean } | null>(null);

  const start = async (mode: ExamMode) => {
    setBusy(mode);
    setFailure(null);
    try {
      const started = await api.post<ExamSession>(`/courses/${courseId}/exams`, { mode });
      // Asistan sekmesi bu sekmede de anında kilitlensin: kilidi okuyan yüzeyler
      // yalnız KİLİTLİYKEN yokluyor, yani açık→kilitli geçişini kimse izlemiyor.
      examStateChanged();
      onStarted(started.id);
    } catch (e) {
      // Boş havuz bir ARIZA değildir: kırmızı kutu yerine nötr boş durum.
      setFailure({ message: errorMessage(e), emptyPool: isEmptyPool(e) });
    } finally {
      setBusy(null);
    }
  };

  if (failure?.emptyPool) {
    return (
      <>
        <PageHeader title="Sınav provası" />
        <EmptyState title={failure.message} />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Sınav provası"
        description="Sorular soru havuzundaki onaylanmış sorulardan seçilir. Boş bırakılan sorular yanlış sayılmaz."
      />

      <div className="grid gap-4 sm:grid-cols-2">
        {(Object.keys(EXAM_MODE) as ExamMode[]).map((mode) => (
          <Card key={mode}>
            <h2 className="text-lg font-medium text-fg">{EXAM_MODE[mode].label}</h2>
            <p className="prose-tr mt-1 text-sm text-fg-muted">{EXAM_MODE[mode].description}</p>
            <div className="mt-4">
              <Button
                variant={mode === "practice" ? "primary" : "secondary"}
                aria-disabled={busy !== null}
                onClick={() => void start(mode)}
              >
                {busy === mode ? "Başlatılıyor…" : `${EXAM_MODE[mode].label} başlat`}
              </Button>
            </div>
          </Card>
        ))}
      </div>

      {failure && !failure.emptyPool && (
        <div className="mt-4">
          <ErrorNote message={failure.message} />
        </div>
      )}
    </>
  );
}

/* -------------------------------------------------------------------------
 * Sınav
 * ---------------------------------------------------------------------- */

function RunningExam({
  courseId,
  session,
  refreshError,
  onReload,
  onLeave,
}: {
  courseId: string;
  session: ExamSession;
  refreshError: string | null;
  onReload: () => Promise<void>;
  onLeave: () => void;
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

/* -------------------------------------------------------------------------
 * Soru gövdesi ve cevap girdisi
 * ---------------------------------------------------------------------- */

function QuestionBody({
  view,
  headingRef,
  describedBy,
  answered,
}: {
  view: QuestionView;
  headingRef: React.RefObject<HTMLHeadingElement | null>;
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

function AnswerInput({
  view,
  questionId,
  draft,
  disabled,
  onChange,
}: {
  view: QuestionView;
  questionId: string;
  draft: string;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
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

  const multiline = view.kind === "code" || view.multiline;

  return (
    <div className="mt-8">
      {/* Etiket görünürdür: placeholder etiket değildir (DESIGN.md). */}
      <Field label="Cevabınız">
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

/* -------------------------------------------------------------------------
 * İpucu merdiveni
 * ---------------------------------------------------------------------- */

/**
 * Verilen ipuçları silinmez, üst üste birikir (DESIGN.md §Sokratik ipucu
 * merdiveni). Her ipucunun kaynağı görünür: kaynaksız ipucu gösterilmez.
 *
 * `components/socratic-ladder.tsx` KULLANILMADI: o bileşen sohbetin beş
 * kademeli `SocraticStage` sözlüğüne bağlı, sınav ucu ise 1-4 arası sayısal
 * `hint_level` döndürüyor. Sayıyı kademe adına çevirmek, sunucunun söylemediği
 * bir eşleme uydurmak olurdu (Anayasa III).
 */
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

/* -------------------------------------------------------------------------
 * Geri bildirim
 * ---------------------------------------------------------------------- */

function FeedbackPanel({ feedback }: { feedback: AnswerFeedback }) {
  const verdict = answerVerdict(feedback);
  const spec = VERDICT_LABEL[verdict];
  const score = formatScore(feedback.score);
  const solution = describeSolution(feedback.solution);

  return (
    <div className="mt-6 rounded-lg border border-border bg-surface p-5">
      <div className="flex flex-wrap items-center gap-3">
        {/* Renk tek başına bilgi taşımaz: rozetin metni her zaman vardır. */}
        <Badge tone={spec.tone}>{spec.label}</Badge>
        {/* Puan yoksa yazılmaz — "0" yazmak olmayan bir ölçümü iddia etmektir. */}
        {score && (
          <span className="font-mono text-sm text-fg">
            {score} / {SCORE_SCALE}
          </span>
        )}
      </div>

      {feedback.message && (
        <p className="prose-tr mt-3 text-sm text-fg">{feedback.message}</p>
      )}

      {feedback.missing_points && feedback.missing_points.length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs font-medium text-fg-muted">Eksik kalan noktalar</h3>
          <ul className="mt-2 space-y-1">
            {feedback.missing_points.map((point) => (
              <li key={point} className="prose-tr text-sm text-fg">
                {point}
              </li>
            ))}
          </ul>
        </div>
      )}

      {feedback.rubric_breakdown && feedback.rubric_breakdown.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <h3 className="mb-2 text-xs font-medium text-fg-muted">Rubrik ölçütleri</h3>
          <table className="w-full min-w-[480px] text-left text-sm">
            <thead className="border-b border-border text-xs text-fg-muted">
              <tr>
                <th className="py-2 pr-4 font-medium">Ölçüt</th>
                <th className="py-2 pr-4 font-medium">Ağırlık</th>
                <th className="py-2 pr-4 font-medium">Başarı</th>
                <th className="py-2 font-medium">Katkı</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {feedback.rubric_breakdown.map((item) => (
                <tr key={item.point}>
                  <td className="prose-tr py-2 pr-4 text-fg">{item.point}</td>
                  <td className="py-2 pr-4 font-mono text-fg-muted">%{item.weight}</td>
                  <td className="py-2 pr-4 font-mono text-fg-muted">%{item.score}</td>
                  <td className="py-2 font-mono text-fg">{item.earned}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Açıklama kaynaklıdır: "neden yanlış" gerçek bir chunk'a dayanır. */}
      {feedback.why_wrong && (
        <div className="mt-4">
          <h3 className="mb-2 text-xs font-medium text-fg-muted">Neden yanlış?</h3>
          <SourceCard source={sourceInfo(feedback.why_wrong)} />
        </div>
      )}

      {feedback.evidence && (
        <div className="mt-4">
          <h3 className="mb-2 text-xs font-medium text-fg-muted">Değerlendirmenin dayanağı</h3>
          <SourceCard source={sourceInfo(feedback.evidence)} />
        </div>
      )}

      {solution.length > 0 && (
        <dl className="mt-4 space-y-2 border-t border-border pt-4">
          {solution.map((line, position) => (
            <div key={`${line.label}-${position}`}>
              <dt className="text-xs text-fg-muted">{line.label}</dt>
              <dd className="prose-tr text-sm whitespace-pre-line text-fg">{line.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------
 * Bitiş
 * ---------------------------------------------------------------------- */

function FinishedExam({
  session,
  finish,
  questions,
  onRestart,
}: {
  session: ExamSession;
  finish: ExamFinish | null;
  questions: ExamQuestion[];
  onRestart: () => void;
}) {
  /*
   * `finish` yalnız sınavı bu sekmede bitiren öğrencide vardır; yenilenen sayfa
   * yalnız oturum özetini görür (`GET /exams/{id}` soru bazlı sonuç DÖNDÜRMEZ).
   * Eksik olan uydurulmaz: özet gösterilir, ayrıntı gösterilmez.
   */
  const score = formatScore(finish ? finish.score : session.score);
  const answered = finish ? finish.answered_count : session.answered_count;
  const unanswered = finish
    ? finish.unanswered_count
    : session.question_count - session.answered_count;

  const prompts = new Map(
    questions.map((question) => {
      const view = describeQuestion(question);
      return [question.id, view.kind === "unsupported" ? null : view.prompt] as const;
    }),
  );

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        title="Sınav sonucu"
        description={finish?.message}
        action={
          <Button variant="secondary" onClick={onRestart}>
            Yeni sınav başlat
          </Button>
        }
      />

      {/*
        Puan yoksa "Puan" kutusu HİÇ çizilmez. İki sebep: sayı uydurulmaz
        (Anayasa III) ve sebebi zaten sunucunun başlıktaki mesajında yazıyor —
        "hesaplanmadı"yı ikinci kez yazmak bilgi katmaz. Ayrıca `MetricRow`
        rakam için ayarlı (`font-mono text-2xl`); oraya konan uzun bir kelime
        yan sütuna taşıyor (bkz. rapor).
      */}
      <MetricRow
        items={[
          ...(score ? [{ value: score, label: `Puan · ${SCORE_SCALE} üzerinden` }] : []),
          { value: answered, label: "Cevaplanan" },
          { value: unanswered, label: "Boş bırakılan" },
          ...(finish ? [{ value: finish.ungraded_count, label: "Değerlendirilemeyen" }] : []),
        ]}
      />

      {/*
        Puanın paydası eksikse bu SÖYLENİR: ortalama yalnız değerlendirilebilen
        cevaplar üzerinden alınır (backend `score_of`), yani gösterilen puan
        sınavın tamamını temsil etmez.
      */}
      {finish && finish.ungraded_count > 0 && score && (
        <p className="prose-tr mb-6 rounded-lg border border-border bg-surface p-4 text-sm text-fg">
          Bu puan yalnız değerlendirilebilen cevaplar üzerinden hesaplandı;
          {" "}
          {finish.ungraded_count} cevap paydaya girmedi.
        </p>
      )}

      {finish === null ? (
        <p className="prose-tr text-sm text-fg-muted">
          Bu oturum daha önce tamamlandı. Soru bazlı geri bildirim yalnız sınavın
          bitirildiği anda gösterilir.
        </p>
      ) : (
        // Hiç cevap yoksa liste boştur; sebebi zaten başlıktaki sunucu mesajında.
        <ol className="space-y-6">
          {(finish.results ?? []).map((result, position) => {
            const prompt = prompts.get(result.question_id);
            return (
              <li key={result.question_id}>
                <h2 className="prose-tr text-sm font-medium text-fg">
                  {position + 1}. {prompt ?? "Soru metni gösterilemiyor"}
                </h2>
                <FeedbackPanel feedback={result} />
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
