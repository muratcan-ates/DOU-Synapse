"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { browserDraftStorage, examDraftKey, loadExamDrafts, removeExamDrafts, saveExamDrafts, validExamDrafts,
  type DraftScope, type ExamDrafts } from "@/lib/exam-drafts";
import type { ExamSession } from "@/lib/types";

export function useExamDrafts(scope: DraftScope, session: ExamSession, enabled: boolean) {
  const key = examDraftKey(scope);
  const current = useRef<ExamDrafts>({});
  const context = useRef({ scope, session, enabled });
  context.current = { scope, session, enabled };
  const [state, setState] = useState<{ key: string; drafts: ExamDrafts; ready: boolean; available: boolean }>({
    key, drafts: {}, ready: false, available: true,
  });
  const ready = state.key === key && state.ready;

  // Önce oku, sonra yaz. Boş ilk render eski taslağın üzerine yazamaz.
  useEffect(() => {
    const value = context.current;
    const loaded = value.enabled ? loadExamDrafts(browserDraftStorage(), value.scope, value.session) : { drafts: {}, available: true };
    current.current = loaded.drafts;
    setState({ key, ...loaded, ready: true });
  }, [key, enabled]);

  const apply = useCallback((next: ExamDrafts) => {
    const value = context.current;
    current.current = next;
    const available = !value.enabled || saveExamDrafts(browserDraftStorage(), value.scope, value.session, next);
    setState({ key: examDraftKey(value.scope), drafts: next, ready: true, available });
  }, []);

  // Yeni sunucu bilgisi geldiğinde cevaplanmış/süresi dolmuş metinleri ayıkla.
  const answerState = JSON.stringify([session.finished_at, session.expired, session.remaining_seconds === 0,
    (session.questions ?? []).map((question) => [question.id, question.answered])]);
  useEffect(() => {
    if (!ready) return;
    const value = context.current;
    const next = validExamDrafts(value.scope, value.session, current.current);
    if (JSON.stringify(next) !== JSON.stringify(current.current)) apply(next);
  }, [answerState, key, ready, apply]);

  const change = useCallback((questionId: string, text: string) => {
    const value = context.current;
    const next = validExamDrafts(value.scope, value.session, { ...current.current, [questionId]: text });
    apply(next);
  }, [apply]);
  const discard = useCallback((questionId: string) => {
    const next = { ...current.current };
    delete next[questionId];
    apply(next);
  }, [apply]);
  const clear = useCallback(() => {
    current.current = {};
    const value = context.current;
    const available = !value.enabled || removeExamDrafts(browserDraftStorage(), value.scope);
    setState({ key: examDraftKey(value.scope), drafts: {}, ready: true, available });
  }, []);

  return { drafts: ready ? state.drafts : {}, ready, available: state.available, change, discard, clear };
}
