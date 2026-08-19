"use client";

/**
 * Tam sohbet ekranının oturum kancası — açma / geri yükleme / localStorage.
 *
 * `ChatScreen` 11 useState'lik tek bir gövdeydi; kanca üç ekseni birleştirir:
 *
 *  - geçmiş listesi `useReverseHistory` (ters sayfalama, prepend),
 *  - gönderim turu `useChatTurn` (`createSubmitGate` çekirdeği, epoch'lu),
 *  - oturum yaşam döngüsü burada: aç, sayfa yenilemede geri yükle, kalıcılaştır.
 *
 * Ekranda yalnız sunum kalır; buradaki kararların saf halleri
 * (`openableSessionMode`, `sessionListNeedsReload`) `use-chat-session.test.ts`
 * ile DOM'suz sınanır. Davranış sözleşmesi taşınan ekranınkiyle birebirdir:
 * localStorage anahtarı `openSessionKey`, istek gövdeleri `buildChatRequest`,
 * Sokratik kademe akışı ve geçmişin yenilemede geri gelmesi değişmez.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import {
  canSubmitDraft,
  fromAnswer,
  fromHistory,
  isSocraticFollowUp,
  openSessionKey,
  userMessage,
  type ChatUiMode,
  type TranscriptMessage,
} from "@/lib/chat";
import {
  answerMatchesAssistant,
  firstAllowedChatMode,
  sessionMatchesAssistant,
  type CourseAssistantIdentity,
} from "@/lib/course-assistant";
import type { ErrorInfo } from "@/lib/errors";
import type {
  ChatAnswer,
  ChatMessage,
  ChatSessionSummary,
  SocraticStage,
} from "@/lib/types";
import { useAssistantPolicyReset } from "@/lib/use-assistant-policy";
import { useChatTurn, type ChatTurnContext } from "@/lib/use-chat-turn";
import { useReverseHistory } from "@/lib/use-reverse-history";

/* -------------------------------------------------------------------------
 * Saf kararlar
 * ---------------------------------------------------------------------- */

/**
 * Listedeki oturum bu ekranda açılabilir mi; açılabilirse hangi UI moduyla?
 *
 * Üç kapı birden: sohbet ucu `exam` kabul etmez (tip daraltması burada
 * yapılır), politika modu kapatmış olabilir, oturum farklı bir üyelik
 * profiliyle açılmış olabilir. Üçü de sessiz reddir — liste satırı zaten
 * nedenini `title` ile söylüyor.
 */
export function openableSessionMode(
  summary: Pick<ChatSessionSummary, "mode" | "audience" | "agent_profile">,
  allowedModes: readonly ChatUiMode[],
  identity: CourseAssistantIdentity,
): ChatUiMode | null {
  const summaryMode: ChatUiMode | null =
    summary.mode === "exam" ? null : summary.mode;
  if (
    summaryMode === null ||
    !allowedModes.includes(summaryMode) ||
    !sessionMatchesAssistant(summary, identity)
  ) {
    return null;
  }
  return summaryMode;
}

/**
 * Kenar paneldeki oturum listesi bu cevaptan sonra tazelenmeli mi?
 *
 * Liste yalnız GERÇEKTEN değiştiyse tazelenir (Anayasa XI). İki durum
 * değiştirir:
 *  - yeni oturum açılması (listede yeni satır),
 *  - Sokratik kademenin ilerlemesi — kademe artık listede de yazıyor ve
 *    tazelenmezse aktif satır merdivenle çelişir: solda "Tanı", sağdaki
 *    merdivende "Yönlendirme". Ekranda birbirini yalanlayan iki gösterge
 *    olmasındansa bir GET fazladan atılır.
 * Kademe değişmediyse (aynı kademede ikinci ipucu) istek atılmaz.
 */
export function sessionListNeedsReload(args: {
  wasNewSession: boolean;
  answerStage: SocraticStage | null;
  listedStage: SocraticStage | null;
}): boolean {
  return args.wasNewSession || args.answerStage !== args.listedStage;
}

/* -------------------------------------------------------------------------
 * Kanca
 * ---------------------------------------------------------------------- */

/** Gönderim anındaki oturum listesi tura iliştirilir (tazeleme kararı için). */
interface ChatSessionTurnContext extends ChatTurnContext {
  sessionList: ChatSessionSummary[] | null;
}

export interface UseChatSessionOptions {
  courseId: string;
  identity: CourseAssistantIdentity;
  allowedModes: ChatUiMode[];
  hintLimit: number;
  /** Kenar panelin oturum listesi; geri yükleme ve tazeleme kararı bunu okur. */
  sessionList: ChatSessionSummary[] | null;
  /** Liste gerçekten değiştiyse çağrılır (bkz. sessionListNeedsReload). */
  reloadSessions: () => Promise<void>;
}

export interface ChatSessionHandle {
  mode: ChatUiMode;
  sessionId: string | null;
  messages: TranscriptMessage[];
  historyLoading: boolean;
  historyError: ErrorInfo | null;
  historyCursor: string | null;
  olderLoading: boolean;
  draft: string;
  setDraft: (text: string) => void;
  pending: string | null;
  sending: boolean;
  sendError: ErrorInfo | null;
  /** Bu tur bir Sokratik devam turu mu (etiket/placeholder bunu okur)? */
  followUp: boolean;
  submittable: boolean;
  send: () => Promise<void>;
  /** Yeni oturum: mod değişimi de buradan geçer — mod ortada değiştirilemez. */
  startNewSession: (nextMode: ChatUiMode) => void;
  openSession: (summary: ChatSessionSummary) => Promise<void>;
  loadOlderMessages: () => Promise<void>;
  saveFeedback: (
    messageId: string,
    feedback: NonNullable<TranscriptMessage["feedback"]>,
  ) => void;
}

export function useChatSession(options: UseChatSessionOptions): ChatSessionHandle {
  const { courseId, identity, allowedModes, hintLimit, sessionList } = options;

  const [mode, setMode] = useState<ChatUiMode>(
    () => firstAllowedChatMode(allowedModes) ?? "qa",
  );
  const [sessionId, setSessionId] = useState<string | null>(null);
  const history = useReverseHistory<ChatMessage, TranscriptMessage>(fromHistory);

  const optionsRef = useRef(options);
  optionsRef.current = options;

  const turn = useChatTurn<ChatSessionTurnContext>({
    post: (body) => api.post<ChatAnswer>(`/courses/${courseId}/chat`, body),
    matchesIdentity: (answer) => answerMatchesAssistant(answer, identity),
    onAnswer: (answer, text, context) => {
      history.append([
        // Kullanıcı mesajının kimliği zarfta yok; asistan kimliğinden türetiliyor.
        userMessage(`user:${answer.message_id}`, text),
        fromAnswer(answer),
      ]);
      setSessionId(answer.session_id);
      localStorage.setItem(openSessionKey(courseId), answer.session_id);
      const listedStage =
        context.sessionList?.find((s) => s.id === answer.session_id)
          ?.socratic_stage ?? null;
      if (
        sessionListNeedsReload({
          wasNewSession: context.sessionId === null,
          answerStage: answer.socratic_stage,
          listedStage,
        })
      ) {
        void optionsRef.current.reloadSessions();
      }
    },
  });

  /** Yeni oturum: mod değişimi de buradan geçer — mod ortada değiştirilemez. */
  const startNewSession = useCallback(
    (nextMode: ChatUiMode) => {
      turn.invalidate();
      setMode(nextMode);
      setSessionId(null);
      history.reset();
      localStorage.removeItem(openSessionKey(courseId));
      // Kullanıcının bilinçli mod değişiminde yazılmış metin korunur.
    },
    [courseId, history.reset, turn.invalidate],
  );

  useAssistantPolicyReset({
    identity,
    allowedModes,
    hintLimit,
    mode,
    onReset: (nextMode) => {
      if (nextMode === null) return;
      // Persona/politika değişince eski rolün oturumu ve taslağı taşınmaz.
      startNewSession(nextMode);
      turn.setDraft("");
    },
  });

  const openSession = useCallback(
    async (summary: ChatSessionSummary) => {
      const summaryMode = openableSessionMode(summary, allowedModes, identity);
      if (summaryMode === null) return;
      turn.invalidate();
      setSessionId(summary.id);
      setMode(summaryMode);
      const applied = await history.open(
        `/courses/${courseId}/chat/sessions/${summary.id}`,
      );
      // Geç dönen açılış kalıcılaşmaz: anahtar yalnız uygulanan açılışta yazılır.
      if (applied) localStorage.setItem(openSessionKey(courseId), summary.id);
    },
    [allowedModes, courseId, history.open, identity, turn.invalidate],
  );

  /*
   * Sayfa yenilenince açık oturum geri açılır. Anahtar ders bazlıdır: başka
   * dersin oturumunu açmak RLS'ten zaten dönmez ama kullanıcıya boş bir hata
   * göstermenin anlamı yok — liste kontrolü bunu baştan eler.
   */
  const restoredFor = useRef<string | null>(null);
  useEffect(() => {
    if (restoredFor.current === courseId) return;
    if (sessionList === null) return;
    restoredFor.current = courseId;
    const storedId = localStorage.getItem(openSessionKey(courseId));
    const target = sessionList.find((summary) => summary.id === storedId);
    if (target) void openSession(target);
  }, [courseId, sessionList, openSession]);

  const openingQuestion =
    history.items.find((message) => message.role === "user")?.content ?? null;
  const followUp = isSocraticFollowUp({ mode, sessionId, openingQuestion });
  const submittable = canSubmitDraft(turn.draft, followUp);

  // Bilerek useCallback değil: tur, gönderim ANINDAKİ render'ın bağlamını taşır.
  const send = () => turn.submit({ mode, sessionId, openingQuestion, sessionList });

  const saveFeedback = useCallback(
    (messageId: string, feedback: NonNullable<TranscriptMessage["feedback"]>) => {
      history.update((current) =>
        current.map((message) =>
          message.id === messageId ? { ...message, feedback } : message,
        ),
      );
    },
    [history.update],
  );

  return {
    mode,
    sessionId,
    messages: history.items,
    historyLoading: history.loading,
    historyError: history.error,
    historyCursor: history.cursor,
    olderLoading: history.olderLoading,
    draft: turn.draft,
    setDraft: turn.setDraft,
    pending: turn.pending,
    sending: turn.sending,
    sendError: turn.sendError,
    followUp,
    submittable,
    send,
    startNewSession,
    openSession,
    loadOlderMessages: history.loadOlder,
    saveFeedback,
  };
}
