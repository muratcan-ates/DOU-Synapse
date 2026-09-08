"use client";

import { api, ApiError } from "@/lib/api";
import { AUTH_EVENT_KEY, isAuthLocallySignedOut, readWithinAuthEpoch } from "@/lib/auth-events";
import { openSessionKey } from "@/lib/chat";

export interface ChatDeletionScope { courseId: string; sessionId: string | null }
interface DeletionSignal extends ChatDeletionScope { authEpoch: string | null; nonce: string }
export const CHAT_DELETION_EVENT_KEY = "dou-synapse:chat-deletion:v1";
const UUID = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;
export function deletionAffectsSession(scope: ChatDeletionScope, sessionId: string | null): boolean {
  return scope.sessionId === null || scope.sessionId === sessionId;
}
export function isChatHistoryRecovery(error: unknown): error is ApiError {
  return error instanceof ApiError && (error.status === 403 || error.status === 404 ||
    (error.status === 409 && error.code === "chat_history_changed"));
}

/** Kimlik işareti ve kapsam dışında özel içerik taşımaz; başka ders etkilenmez. */
export function createChatDeletionBus(readAuthEpoch: () => string | null, publish: (value: string) => void) {
  const listeners = new Set<{ courseId: string; listener: (scope: ChatDeletionScope) => void }>();
  let lastNonce: string | null = null;
  function receive(raw: string | null) {
    if (raw === null) return;
    let signal: DeletionSignal;
    try { signal = JSON.parse(raw) as DeletionSignal; } catch { return; }
    if (!signal || typeof signal.courseId !== "string" || !UUID.test(signal.courseId) ||
      (signal.sessionId !== null && (typeof signal.sessionId !== "string" || !UUID.test(signal.sessionId))) ||
      typeof signal.nonce !== "string" || !UUID.test(signal.nonce) ||
      signal.authEpoch !== readAuthEpoch() || signal.nonce === lastNonce) return;
    lastNonce = signal.nonce;
    const scope = { courseId: signal.courseId, sessionId: signal.sessionId };
    for (const entry of [...listeners]) if (entry.courseId === scope.courseId) entry.listener(scope);
  }
  return {
    receive,
    notify(scope: ChatDeletionScope) {
      const value = JSON.stringify({ courseId: scope.courseId, sessionId: scope.sessionId, authEpoch: readAuthEpoch(), nonce: crypto.randomUUID() });
      publish(value); receive(value);
    },
    subscribe(courseId: string, listener: (scope: ChatDeletionScope) => void) {
      const entry = { courseId, listener }; listeners.add(entry);
      return () => { listeners.delete(entry); };
    },
  };
}

function authMarker(): string | null {
  try { return window.localStorage.getItem(AUTH_EVENT_KEY); } catch { return null; }
}
const bus = createChatDeletionBus(authMarker, (value) => {
  try { window.localStorage.setItem(CHAT_DELETION_EVENT_KEY, value); } catch { /* Aynı sekme çalışır. */ }
});
let subscribers = 0;
let stopBrowser: (() => void) | null = null;
function forgetRemembered(scope: ChatDeletionScope) {
  try {
    const key = openSessionKey(scope.courseId);
    if (deletionAffectsSession(scope, window.localStorage.getItem(key))) window.localStorage.removeItem(key);
  } catch { /* Depo kapalıyken de bellek temizlenir. */ }
}
export function notifyChatDeletion(scope: ChatDeletionScope) {
  if (isAuthLocallySignedOut()) return;
  forgetRemembered(scope); bus.notify(scope);
}
export function subscribeChatDeletions(courseId: string, listener: (scope: ChatDeletionScope) => void) {
  const stop = bus.subscribe(courseId, (scope) => { forgetRemembered(scope); listener(scope); });
  subscribers += 1;
  if (typeof window !== "undefined" && stopBrowser === null) {
    const storage = (event: StorageEvent) => {
      if (event.key === CHAT_DELETION_EVENT_KEY && !isAuthLocallySignedOut()) bus.receive(event.newValue);
    };
    window.addEventListener("storage", storage);
    stopBrowser = () => window.removeEventListener("storage", storage);
  }
  return () => {
    stop(); subscribers -= 1;
    if (subscribers === 0) { stopBrowser?.(); stopBrowser = null; }
  };
}

/** Başarısız veya eski kimliğe ait bir DELETE, yeni ekranı geçersizleyemez. */
export async function deleteOwnChatHistory(scope: ChatDeletionScope): Promise<number | null> {
  const path = `/courses/${encodeURIComponent(scope.courseId)}/chat/sessions` +
    (scope.sessionId === null ? "" : `/${encodeURIComponent(scope.sessionId)}`);
  const result = await readWithinAuthEpoch(() => api.delete<{ deleted_sessions: number }>(path));
  if (result === null) return null;
  notifyChatDeletion(scope);
  return result.deleted_sessions;
}
