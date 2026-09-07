"use client";

import { useCallback } from "react";
import { api, ApiError } from "@/lib/api";
import { describeQuestion, formatScore, SCORE_SCALE } from "@/lib/exam";
import type { ExamFinish, ExamQuestion, ExamSession } from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import type { ChatLock } from "@/lib/chat-availability";
import { ErrorNote, Loading, MetricRow, PageHeader } from "@/components/page-state";
import { Button } from "@/components/ui";
import { FeedbackPanel } from "@/components/exam/feedback-panel";

interface ResultView {
  result: ExamFinish | null;
  lockedMessage: string | null;
  summary: ExamSession | null;
}

interface FinishedExamProps {
  courseId: string;
  session: ExamSession;
  finish: ExamFinish | null;
  questions: ExamQuestion[];
  onRestart: () => void;
  historyEnabled: boolean;
  helpLock: ChatLock;
}

export function FinishedExam(props: FinishedExamProps) {
  const { helpLock, onRestart } = props;
  const title = <PageHeader title="Sınav sonucu" action={
    <Button variant="secondary" onClick={onRestart}>Yeni sınav başlat</Button>
  } />;
  if (!helpLock.ready) return (
    <div className="mx-auto max-w-2xl">{title}<Loading label="Sonuç erişimi doğrulanıyor…" /></div>
  );
  if (helpLock.error || helpLock.refreshError) return (
    <div className="mx-auto max-w-2xl">{title}<ErrorNote
      message={helpLock.error ?? helpLock.refreshError ?? ""} onRetry={helpLock.reload} /></div>
  );
  // Availability yalnız yenileme sinyalidir: asistanın bakım/politika kilidi
  // sonuç yetkisi değildir. Her yeni doğrulamada eski alt bileşen sökülür;
  // asıl izin ve kaynak kararı aşağıdaki sonuç uçlarından okunur.
  return <ResultDetails {...props} />;
}

function ResultDetails({ courseId, session, finish, questions, onRestart, historyEnabled }: FinishedExamProps) {
  const loadResult = useCallback(async (): Promise<ResultView> => {
    if (!historyEnabled) return {
      result: finish?.results_locked ? null : finish,
      lockedMessage: finish?.results_locked ? finish.message : null,
      // Eski akışta kalıcı ayrıntı ucu kapalıdır. Odağa dönüş ilk /finish
      // yanıtını temizler; mevcut oturum ucu puanı sınav kilidine göre süzer.
      summary: finish ? null : await api.get<ExamSession>(`/courses/${courseId}/exams/${session.id}`),
    };
    try {
      const result = await api.get<ExamFinish>(`/courses/${courseId}/exams/${session.id}/results`);
      return { result: result.results_locked ? null : result, lockedMessage: result.results_locked ? result.message : null, summary: null };
    } catch (error) {
      // Beklenen sınav kilidi sonuç verisini temizler; eski başarılı sonucu
      // saklayan genel refresh-error davranışı bu sınırda kullanılmaz.
      if (error instanceof ApiError && error.code === "exam_in_progress") {
        return { result: null, lockedMessage: error.message, summary: null };
      }
      throw error;
    }
  }, [courseId, session.id, historyEnabled, finish]);
  const result = useResource(loadResult, [courseId, session.id, historyEnabled, finish]);
  const title = <PageHeader title="Sınav sonucu" action={
    <Button variant="secondary" onClick={onRestart}>Yeni sınav başlat</Button>
  } />;

  if (result.loading) return <div className="mx-auto max-w-2xl">{title}<Loading label="Sonuçlar yükleniyor…" /></div>;
  if (result.error || result.refreshError) return <div className="mx-auto max-w-2xl">{title}<ErrorNote message={result.error ?? result.refreshError ?? ""} onRetry={result.reload} /></div>;
  if (result.data === null) return <Loading />;
  if (result.data.lockedMessage) return (
    <div className="mx-auto max-w-2xl">
      {title}
      <div className="border-y border-border py-6">
        <p role="status" className="prose-tr text-sm text-fg">{result.data.lockedMessage}</p>
        {historyEnabled && <Button variant="secondary" className="mt-4" onClick={() => void result.reload()}>Tekrar dene</Button>}
      </div>
    </div>
  );

  const completed = result.data.result;
  const summary = result.data.summary ?? session;
  const score = formatScore(completed ? completed.score : summary.score);
  const answered = completed ? completed.answered_count : summary.answered_count;
  const unanswered = completed ? completed.unanswered_count : summary.question_count - summary.answered_count;
  const prompts = new Map(questions.map((question) => {
    const view = describeQuestion(question);
    return [question.id, view.kind === "unsupported" ? null : view.prompt] as const;
  }));

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="Sınav sonucu" description={completed?.message} action={
        <Button variant="secondary" onClick={onRestart}>Yeni sınav başlat</Button>
      } />
      <MetricRow items={[
        ...(score !== null ? [{ value: score, label: `Puan · ${SCORE_SCALE} üzerinden` }] : []),
        { value: answered, label: "Cevaplanan" },
        { value: unanswered, label: "Boş bırakılan" },
        ...(completed ? [{ value: completed.ungraded_count, label: "Değerlendirilemeyen" }] : []),
      ]} />
      {completed && completed.ungraded_count > 0 && score !== null && (
        <p className="prose-tr mb-6 rounded-lg border border-border bg-surface p-4 text-sm text-fg">
          Bu puan yalnız değerlendirilebilen cevaplar üzerinden hesaplandı; {completed.ungraded_count} cevap paydaya girmedi.
        </p>
      )}
      {completed === null ? (
        <p className="prose-tr text-sm text-fg-muted">Bu oturum daha önce tamamlandı. Ayrıntılı sonuç geçmişi bu ortamda açık değil.</p>
      ) : (
        <ol className="space-y-6">
          {(completed.results ?? []).map((feedback, position) => (
            <li key={feedback.question_id}>
              <h2 className="prose-tr text-sm font-medium text-fg">{position + 1}. {prompts.get(feedback.question_id) ?? "Soru metni gösterilemiyor"}</h2>
              <FeedbackPanel feedback={feedback} />
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
