"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { AnswerFeedback } from "@/lib/types";
import { createRequestGate, useResource } from "@/lib/use-resource";
import { ErrorNote, Loading } from "@/components/page-state";
import { Button } from "@/components/ui";
import { FeedbackPanel } from "@/components/exam/feedback-panel";

interface SavedFeedback { feedback: AnswerFeedback | null; lockedMessage: string | null }

/** Cevap yeniden puanlanmaz; kaynak ve sınav kilidi her okumada sunucuda doğrulanır. */
export function SavedPracticeFeedback({ courseId, sessionId, questionId, onLocked }: {
  courseId: string; sessionId: string; questionId: string; onLocked: () => Promise<void>;
}) {
  const [checking, setChecking] = useState(true);
  const [checkingGate] = useState(createRequestGate);
  const load = useCallback(async (): Promise<SavedFeedback> => {
    const token = checkingGate.begin();
    setChecking(true);
    try {
      const feedback = await api.get<AnswerFeedback>(`/courses/${courseId}/exams/${sessionId}/answers/${questionId}`);
      return { feedback, lockedMessage: null };
    } catch (error) {
      if (error instanceof ApiError && error.code === "exam_in_progress") {
        if (checkingGate.isCurrent(token)) void onLocked();
        return { feedback: null, lockedMessage: error.message };
      }
      throw error;
    } finally { if (checkingGate.isCurrent(token)) setChecking(false); }
  }, [courseId, sessionId, questionId, onLocked, checkingGate]);
  const saved = useResource(load, [courseId, sessionId, questionId]);
  useEffect(() => {
    const refresh = () => { setChecking(true); void saved.reload(); };
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, [saved.reload]);

  if (checking || saved.loading) return <div className="mt-6"><Loading label="Geri bildirim yükleniyor…" /></div>;
  if (saved.error || saved.refreshError) return <div className="mt-6"><ErrorNote message={saved.error ?? saved.refreshError ?? ""} onRetry={saved.reload} /></div>;
  if (saved.data?.lockedMessage) return (
    <div className="mt-6 border-y border-border py-4">
      <p role="status" className="prose-tr text-sm text-fg">{saved.data.lockedMessage}</p>
      <Button variant="secondary" className="mt-3" onClick={() => void saved.reload()}>Tekrar dene</Button>
    </div>
  );
  return saved.data?.feedback ? <FeedbackPanel courseId={courseId} feedback={saved.data.feedback} /> : null;
}
