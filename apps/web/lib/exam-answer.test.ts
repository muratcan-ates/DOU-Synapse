import { describe, expect, test } from "bun:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { AnswerInput } from "@/components/exam/question-input";
import { bugHuntDraft, bugHuntDraftIssue, encodeBugHuntDraft, examAnswerValue, isStorableExamDraft, submittedAnswerText } from "@/lib/exam-answer";
import { validExamDrafts } from "@/lib/exam-drafts";
import { canSubmitAnswer } from "@/lib/exam";
import type { ExamSession } from "@/lib/types";

const session: ExamSession = {
  id: "session-1", course_id: "course-1", mode: "practice", started_at: "2026-09-13T00:00:00Z",
  expires_at: null, remaining_seconds: null, expired: false, finished_at: null, score: null,
  question_count: 1, answered_count: 0,
  questions: [{ id: "question-1", type: "bug_hunt", payload: {}, answered: false }],
};
const scope = { userId: "student-1", courseId: session.course_id, sessionId: session.id };
const draft = { line: "3", bugType: "IndexError", fixSummary: "  Dizinin uzunluğunu kullan.\n" };

describe("sınav yanıtını kayıpsız gönderme", () => {
  test.each([" 3\n", "first\n second", "\tValue\r\n", "x  y\n\n", "\n", "  "]) ("kod çıktısının boşluk, harf ve satırları aynen korunur: %j", (given) => {
    expect(examAnswerValue("code_trace", given)).toBe(given);
    expect(submittedAnswerText("code_trace", given)).toBe(given);
  });

  test("kod çıktısında sınır kontrolü kırpılmış değer üzerinden yapılmaz", () => {
    expect(examAnswerValue("code_trace", ` ${"a".repeat(8000)}`)).toBeNull();
    expect(examAnswerValue("code_trace", "")).toBeNull();
    expect(examAnswerValue("open", "  \n")).toBeNull();
  });

  test("hata yanıtı yalnız sürümlü dört alanı gönderir, satır sayıdır ve açıklama korunur", () => {
    const value = examAnswerValue("bug_hunt", encodeBugHuntDraft(draft));
    expect(JSON.parse(value!)).toEqual({ version: 1, line: 3, bug_type: draft.bugType, fix_summary: draft.fixSummary });
    expect(submittedAnswerText("bug_hunt", value!)).toBe(`Satır: 3\nHata türü: IndexError\nDüzeltme: ${draft.fixSummary}`);
    expect(submittedAnswerText("bug_hunt", value!)).not.toContain('"version"');
  });

  test("ek alanlar boşsa önceki serbest cevap yolu ve taslağı korunur", () => {
    const original = "  Serbest açıklama\n";
    expect(bugHuntDraft(original)).toEqual({ line: "", bugType: "", fixSummary: original });
    expect(encodeBugHuntDraft({ line: "", bugType: "", fixSummary: original })).toBe(original);
    expect(examAnswerValue("bug_hunt", original)).toBe(original.trim());
  });

  test("yinelenen veya türü belirsiz kullanıcı JSON'u sessizce geçerli cevaba çevrilmez", () => {
    for (const original of [
      '{"version":1,"line":1,"line":3,"bug_type":"IndexError","fix_summary":"Düzeltme"}',
      '{"version":1,"line":3.0,"bug_type":"IndexError","fix_summary":"Düzeltme"}',
    ]) {
      expect(bugHuntDraft(original)).toEqual({ line: "", bugType: "", fixSummary: original });
      expect(examAnswerValue("bug_hunt", original)).toBe(original);
    }
  });

  test.each(["", "0", "-1", "1.5", "NaN", "Infinity", "9007199254740992"])("geçersiz veya eksik satır %s gönderilmez", (line) => {
    expect(examAnswerValue("bug_hunt", encodeBugHuntDraft({ ...draft, line }))).toBeNull();
  });

  test("tek ek alan, boş açıklama ve şema sınırını aşan açıklama gönderilmez", () => {
    for (const value of [
      { ...draft, bugType: "" }, { ...draft, fixSummary: " " },
      { ...draft, fixSummary: "a".repeat(2001) }, { ...draft, bugType: "a".repeat(201) },
    ]) {
      const serialized = encodeBugHuntDraft(value);
      expect(examAnswerValue("bug_hunt", serialized)).toBeNull();
      expect(canSubmitAnswer({ session, question: session.questions![0], draft: serialized, localRemaining: null })).toBe(false);
    }
  });

  test("uzun eski açıklama ek alanlara geçince JSON kaçışları yüzünden taslaktan silinmez", () => {
    const fixSummary = '"'.repeat(8000);
    const serialized = encodeBugHuntDraft({ ...draft, fixSummary });
    expect(serialized.length).toBeGreaterThan(8000);
    expect(isStorableExamDraft("bug_hunt", serialized)).toBe(true);
    const kept = validExamDrafts(scope, session, { "question-1": serialized });
    expect(bugHuntDraft(kept["question-1"]).fixSummary).toBe(fixSummary);
    expect(examAnswerValue("bug_hunt", serialized)).toBeNull();
    expect(isStorableExamDraft("code_trace", serialized)).toBe(false);
  });

  test("geniş taslak zarfı başka türlere veya sınırsız alanlara açılmaz", () => {
    expect(isStorableExamDraft("bug_hunt", "a".repeat(8001))).toBe(false);
    expect(isStorableExamDraft("bug_hunt", encodeBugHuntDraft({ ...draft, fixSummary: "a".repeat(8001) }))).toBe(false);
    expect(isStorableExamDraft("bug_hunt", JSON.stringify({ version: 1, line: "3", bug_type: "a", fix_summary: '"'.repeat(8000), extra: true }))).toBe(false);
  });

  test("alan sınırları içindeki kaçışlar istek sınırını aşarsa gerekçe gösterilir ve metin korunur", () => {
    const value = { ...draft, fixSummary: `x${"\u0001".repeat(1999)}` };
    const serialized = encodeBugHuntDraft(value);
    expect(value.fixSummary.length).toBe(2000);
    expect(serialized.length).toBeGreaterThan(8000);
    expect(isStorableExamDraft("bug_hunt", serialized)).toBe(true);
    expect(bugHuntDraft(serialized).fixSummary).toBe(value.fixSummary);
    expect(examAnswerValue("bug_hunt", serialized)).toBeNull();
    expect(bugHuntDraftIssue(value)).toContain("Yanıt gönderim sınırını aşıyor");
  });

  test("hata formu eski Cevabınız alanını, görünür açıklamayı ve ek alanları sunar", () => {
    const html = renderToStaticMarkup(createElement(AnswerInput, {
      view: { kind: "code", prompt: "Hatayı bulun.", language: "python", code: "print(values[3])" },
      questionType: "bug_hunt", questionId: "q1", draft: encodeBugHuntDraft(draft), disabled: false,
      onChange: () => undefined,
    }));
    expect(html).toContain("Cevabınız");
    expect(html).toContain("Hata satırı");
    expect(html).toContain("Hata türü");
    expect(html).toContain("otomatik puanlanmaz");
    expect(html).not.toContain('"version"');
    expect(html).toContain("IndexError");
  });
});
