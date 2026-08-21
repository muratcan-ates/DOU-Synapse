"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import type {
  ChatFeedback,
  ChatFeedbackRating,
  ChatFeedbackReason,
} from "@/lib/types";
import { Button } from "@/components/ui";

export const FEEDBACK_REASON_LABEL: Record<ChatFeedbackReason, string> = {
  helpful: "Yararlı",
  inaccurate: "Bilgi hatalı veya eksik",
  irrelevant: "Soruyla ilgisiz",
  citation_problem: "Kaynak cevabı desteklemiyor",
  too_direct: "Cevabı fazla doğrudan verdi",
  unsafe: "Uygunsuz veya güvensiz",
  other: "Diğer",
};

const PROBLEM_REASONS = [
  "inaccurate",
  "irrelevant",
  "citation_problem",
  "too_direct",
  "unsafe",
  "other",
] as const satisfies readonly ChatFeedbackReason[];

export function ChatFeedbackControls({
  courseId,
  messageId,
  initial,
  onSaved,
}: {
  courseId: string;
  messageId: string;
  initial: ChatFeedback | null;
  onSaved: (feedback: ChatFeedback) => void;
}) {
  const [feedback, setFeedback] = useState(initial);
  const [showProblem, setShowProblem] = useState(false);
  const [reason, setReason] = useState<ChatFeedbackReason>("inaccurate");
  const [comment, setComment] = useState("");
  const [share, setShare] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setFeedback(initial);
  }, [initial]);

  async function save(
    rating: ChatFeedbackRating,
    selectedReason: ChatFeedbackReason,
    selectedComment: string | null,
    shareWithInstructor: boolean,
  ) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const saved = await api.put<ChatFeedback>(
        `/courses/${courseId}/chat/messages/${messageId}/feedback`,
        {
          rating,
          reason: selectedReason,
          comment: selectedComment,
          share_with_instructor: shareWithInstructor,
        },
      );
      setFeedback(saved);
      setShowProblem(false);
      onSaved(saved);
    } catch (cause) {
      setError(errorMessage(cause, "Geri bildirim kaydedilemedi."));
    } finally {
      setBusy(false);
    }
  }

  function openProblemForm() {
    if (feedback?.rating === "unhelpful") {
      setReason(feedback.reason);
      setComment(feedback.comment ?? "");
      setShare(feedback.share_with_instructor);
    }
    setShowProblem(true);
  }

  return (
    <div className="border-t border-border pt-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-fg-muted">Bu yanıt yardımcı oldu mu?</span>
        <Button
          type="button"
          variant="ghost"
          className="h-9 px-3 text-xs"
          aria-pressed={feedback?.rating === "helpful"}
          aria-disabled={busy}
          onClick={() => void save("helpful", "helpful", null, false)}
        >
          Yararlı
        </Button>
        <Button
          type="button"
          variant="ghost"
          className="h-9 px-3 text-xs"
          aria-pressed={feedback?.rating === "unhelpful"}
          aria-disabled={busy}
          onClick={openProblemForm}
        >
          Sorun var
        </Button>
        {feedback && !showProblem && (
          <span role="status" className="text-xs text-fg-subtle">
            Kaydedildi: {FEEDBACK_REASON_LABEL[feedback.reason]}
            {feedback.share_with_instructor ? " · öğretmen incelemesine açık" : ""}
          </span>
        )}
      </div>

      {showProblem && (
        <form
          className="mt-3 space-y-3 rounded-lg border border-border bg-surface p-4"
          onSubmit={(event) => {
            event.preventDefault();
            void save("unhelpful", reason, comment.trim() || null, share);
          }}
        >
          <label className="block text-xs text-fg-muted">
            Sorun türü
            <select
              value={reason}
              onChange={(event) => setReason(event.target.value as ChatFeedbackReason)}
              className="mt-1 h-11 w-full rounded-lg border border-border-strong bg-surface px-3 text-sm text-fg focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand"
            >
              {PROBLEM_REASONS.map((value) => (
                <option key={value} value={value}>
                  {FEEDBACK_REASON_LABEL[value]}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-xs text-fg-muted">
            Açıklama (isteğe bağlı)
            <textarea
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              maxLength={1000}
              rows={3}
              className="mt-1 w-full rounded-lg border border-border-strong bg-surface px-3 py-2 text-sm text-fg focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand"
            />
          </label>
          <label className="flex items-start gap-3 text-xs text-fg-muted">
            <input
              type="checkbox"
              checked={share}
              onChange={(event) => setShare(event.target.checked)}
              className="mt-0.5 h-4 w-4 accent-[var(--brand)]"
            />
            <span>
              Bu soru-cevap çiftini ve açıklamamı öğretmen incelemesine aç. İşaretlemezsem
              yalnız anonim toplam sayıya girer; öğretmen sohbet metnimi göremez.
            </span>
          </label>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" aria-disabled={busy}>
              {busy ? "Kaydediliyor…" : "Geri bildirimi kaydet"}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setShowProblem(false)}>
              Vazgeç
            </Button>
          </div>
        </form>
      )}
      {error && (
        <p role="alert" className="mt-2 text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

