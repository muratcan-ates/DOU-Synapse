import { ANSWER_MAX_LENGTH } from "@/lib/exam-limits";
import type { ExamSession } from "@/lib/types";

export interface DraftScope { userId: string; courseId: string; sessionId: string }
export type ExamDrafts = Record<string, string>;
export type DraftStorage = Pick<Storage, "getItem" | "setItem" | "removeItem" | "key" | "length">;
export const EXAM_DRAFT_PREFIX = "dou-synapse:exam-drafts:v1:";
export const EXAM_DRAFT_TTL_MS = 24 * 60 * 60 * 1000;

export function examDraftKey(scope: DraftScope): string {
  return EXAM_DRAFT_PREFIX + [scope.userId, scope.courseId, scope.sessionId].map(encodeURIComponent).join(":");
}

export function browserDraftStorage(): DraftStorage | null {
  try { return typeof window === "undefined" ? null : window.sessionStorage; }
  catch { return null; }
}

/** Yalnız sunucunun doğruladığı, hâlâ cevaplanabilir sorular geri yüklenir. */
export function validExamDrafts(scope: DraftScope, session: ExamSession, raw: unknown): ExamDrafts {
  if (session.id !== scope.sessionId || session.course_id !== scope.courseId ||
      session.finished_at !== null || session.expired || session.remaining_seconds === 0 ||
      typeof raw !== "object" || raw === null || Array.isArray(raw)) return {};
  const values = raw as Record<string, unknown>;
  return Object.fromEntries((session.questions ?? []).flatMap((question) => {
    const value = values[question.id];
    return !question.answered && typeof value === "string" && value.length > 0 && value.length <= ANSWER_MAX_LENGTH
      ? [[question.id, value]] : [];
  }));
}

export function loadExamDrafts(storage: DraftStorage | null, scope: DraftScope, session: ExamSession, now = Date.now()): { drafts: ExamDrafts; available: boolean } {
  if (!storage) return { drafts: {}, available: false };
  try {
    const key = examDraftKey(scope);
    const value = storage.getItem(key);
    if (value === null) return { drafts: {}, available: true };
    let parsed: unknown;
    try { parsed = JSON.parse(value); } catch { storage.removeItem(key); return { drafts: {}, available: true }; }
    const envelope = typeof parsed === "object" && parsed !== null ? parsed as Record<string, unknown> : {};
    if (envelope.version !== 1 || typeof envelope.updatedAt !== "number" ||
        !Number.isFinite(envelope.updatedAt) || envelope.updatedAt > now || now - envelope.updatedAt >= EXAM_DRAFT_TTL_MS) {
      storage.removeItem(key);
      return { drafts: {}, available: true };
    }
    const drafts = validExamDrafts(scope, session, envelope.drafts);
    // Cevaplanmış/silinmiş soruların eski metinleri depoda da bırakılmaz.
    const available = saveExamDrafts(storage, scope, session, drafts, envelope.updatedAt);
    return { drafts, available };
  } catch { return { drafts: {}, available: false }; }
}

export function saveExamDrafts(storage: DraftStorage | null, scope: DraftScope, session: ExamSession, raw: ExamDrafts, now = Date.now()): boolean {
  if (!storage) return false;
  try {
    const drafts = validExamDrafts(scope, session, raw);
    const key = examDraftKey(scope);
    if (Object.keys(drafts).length === 0) storage.removeItem(key);
    else storage.setItem(key, JSON.stringify({ version: 1, updatedAt: now, drafts }));
    return true;
  } catch { return false; }
}

export function removeExamDrafts(storage: DraftStorage | null, scope: DraftScope): boolean {
  if (!storage) return false;
  try { storage.removeItem(examDraftKey(scope)); return true; } catch { return false; }
}

/** Çıkışta yalnız bu özelliğin içerik kayıtları temizlenir; başka depo anahtarları korunur. */
export function clearAllExamDrafts(storage = browserDraftStorage()): void {
  if (!storage) return;
  try {
    for (let index = storage.length - 1; index >= 0; index -= 1) {
      const key = storage.key(index);
      if (key?.startsWith(EXAM_DRAFT_PREFIX)) storage.removeItem(key);
    }
  } catch { /* Depo kapalıysa çıkışın kimlik temizliğini engelleme. */ }
}
