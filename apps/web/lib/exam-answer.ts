import { ANSWER_MAX_LENGTH } from "@/lib/exam-limits";
import type { QuestionType } from "@/lib/types";

export const BUG_TYPE_MAX_LENGTH = 200;
export const BUG_FIX_MAX_LENGTH = 2000;

export interface BugHuntDraft {
  line: string;
  bugType: string;
  fixSummary: string;
}

function structuredBugHuntDraft(draft: string): BugHuntDraft | null {
  try {
    const value: unknown = JSON.parse(draft);
    if (typeof value === "object" && value !== null && !Array.isArray(value)) {
      const item = value as Record<string, unknown>;
      if (item.version === 1 && (typeof item.line === "string" || typeof item.line === "number") &&
        typeof item.bug_type === "string" && typeof item.fix_summary === "string" &&
        Object.keys(item).every((key) => ["version", "line", "bug_type", "fix_summary"].includes(key)) &&
        // Yalnız kendi zarfımızı aç; yinelenen alanlı kullanıcı JSON'unu onarıp gönderme.
        draft === JSON.stringify({ version: 1, line: item.line, bug_type: item.bug_type, fix_summary: item.fix_summary })) {
        return { line: String(item.line), bugType: item.bug_type, fixSummary: item.fix_summary };
      }
    }
  } catch {
    // Önceki sürümün düz metin taslağı aynı cevap alanında kalır.
  }
  return null;
}

/** Eksik alanlar da tek taslakta saklanır; eski serbest metin kaybolmaz. */
export function bugHuntDraft(draft: string): BugHuntDraft {
  return structuredBugHuntDraft(draft) ?? { line: "", bugType: "", fixSummary: draft };
}

export function isStructuredBugDraft(draft: BugHuntDraft): boolean {
  return draft.line.trim().length > 0 || draft.bugType.trim().length > 0;
}

export function encodeBugHuntDraft(draft: BugHuntDraft): string {
  if (!isStructuredBugDraft(draft)) return draft.fixSummary;
  return JSON.stringify({ version: 1, line: draft.line, bug_type: draft.bugType, fix_summary: draft.fixSummary });
}

export function validBugLine(line: string): boolean {
  const normalized = line.trim();
  return /^\d+$/.test(normalized) && Number.isSafeInteger(Number(normalized)) && Number(normalized) > 0;
}

function structuredBugAnswer(draft: BugHuntDraft): string {
  return JSON.stringify({ version: 1, line: Number(draft.line), bug_type: draft.bugType, fix_summary: draft.fixSummary });
}

/** Yerel form sınırını açıklar; sağlayıcının not veya anlam kararını tahmin etmez. */
export function bugHuntDraftIssue(draft: BugHuntDraft): string | null {
  if (!isStructuredBugDraft(draft)) return null;
  if (!validBugLine(draft.line) || !draft.bugType.trim()) {
    return "Pozitif bir satır numarası ve hata türünü birlikte doldurun.";
  }
  if (draft.bugType.length > BUG_TYPE_MAX_LENGTH) return `Hata türü en fazla ${BUG_TYPE_MAX_LENGTH} karakter olmalı.`;
  if (!draft.fixSummary.trim()) return "Düzeltmenizi Cevabınız alanına yazın.";
  if (draft.fixSummary.length > BUG_FIX_MAX_LENGTH) {
    return `Otomatik değerlendirme için düzeltme açıklamasını en fazla ${BUG_FIX_MAX_LENGTH} karaktere indirin. Mevcut metniniz korunuyor.`;
  }
  if (structuredBugAnswer(draft).length > ANSWER_MAX_LENGTH) {
    return "Yanıt gönderim sınırını aşıyor. Açıklamanızı kısaltın; mevcut metniniz korunuyor.";
  }
  return null;
}

/** JSON kaçışları eski metni büyütse de taslak kaybolmaz; alanlar ayrı sınırlıdır. */
export function isStorableExamDraft(type: QuestionType, draft: string): boolean {
  if (draft.length > 0 && draft.length <= ANSWER_MAX_LENGTH) return true;
  // Tek UTF-16 karakter JSON içinde en fazla altı karakterlik kaçışa dönüşür.
  if (type !== "bug_hunt" || draft.length > 6 * (ANSWER_MAX_LENGTH + BUG_TYPE_MAX_LENGTH) + 256) return false;
  const value = structuredBugHuntDraft(draft);
  return value !== null && value.line.length <= 16 && value.bugType.length <= BUG_TYPE_MAX_LENGTH &&
    value.fixSummary.length <= ANSWER_MAX_LENGTH;
}

/** Kod çıktısını değiştirmez; yapılandırılmış cevapta yalnız tam alanlar gönderilir. */
export function examAnswerValue(type: QuestionType, draft: string): string | null {
  let given: string;
  if (type === "bug_hunt") {
    const bug = bugHuntDraft(draft);
    if (isStructuredBugDraft(bug)) {
      if (bugHuntDraftIssue(bug) !== null) return null;
      given = structuredBugAnswer(bug);
    } else {
      given = bug.fixSummary.trim();
    }
  } else {
    given = type === "code_trace" ? draft : draft.trim();
  }
  const hasAnswer = type === "code_trace" ? given.length > 0 : given.trim().length > 0;
  return hasAnswer && given.length <= ANSWER_MAX_LENGTH ? given : null;
}

/** Öğrenciye taşıma biçimi değil, kendi yazdığı üç alan gösterilir. */
export function submittedAnswerText(type: QuestionType, given: string): string {
  if (type !== "bug_hunt") return given;
  const bug = bugHuntDraft(given);
  if (!isStructuredBugDraft(bug)) return given;
  return `Satır: ${bug.line}\nHata türü: ${bug.bugType}\nDüzeltme: ${bug.fixSummary}`;
}
