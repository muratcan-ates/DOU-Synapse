import { describe, expect, test } from "bun:test";
import { ANSWER_MAX_LENGTH } from "@/lib/exam-limits";
import { clearAllExamDrafts, examDraftKey, EXAM_DRAFT_TTL_MS, loadExamDrafts, removeExamDrafts, saveExamDrafts,
  validExamDrafts, type DraftScope, type DraftStorage } from "@/lib/exam-drafts";
import type { ExamSession } from "@/lib/types";

class MemoryStorage implements DraftStorage {
  readonly data = new Map<string, string>();
  get length() { return this.data.size; }
  key(index: number) { return [...this.data.keys()][index] ?? null; }
  getItem(key: string) { return this.data.get(key) ?? null; }
  setItem(key: string, value: string) { this.data.set(key, value); }
  removeItem(key: string) { this.data.delete(key); }
}
const scope: DraftScope = { userId: "u1", courseId: "c1", sessionId: "s1" };
const now = 1_000_000;
const session = (overrides: Partial<ExamSession> = {}): ExamSession => ({
  id: "s1", course_id: "c1", mode: "practice", started_at: "2026-09-04T12:00:00Z", expires_at: null,
  remaining_seconds: null, expired: false, finished_at: null, score: null, question_count: 2, answered_count: 0,
  questions: [
    { id: "q1", type: "open", payload: { prompt: "Soru" }, answered: false },
    { id: "q2", type: "mcq", payload: { stem: "Soru" }, answered: false },
  ], ...overrides,
});

describe("gönderilmemiş sınav taslağı", () => {
  test("yenileme için metni geri getirir; kaynak veya çözüm saklamaz", () => {
    const store = new MemoryStorage();
    expect(saveExamDrafts(store, scope, session(), { q1: "Henüz göndermedim", q2: "A", secret: "anahtar" }, now)).toBe(true);
    const restored = loadExamDrafts(store, scope, session(), now + 1);
    expect(restored).toEqual({ drafts: { q1: "Henüz göndermedim", q2: "A" }, available: true });
    expect(store.getItem(examDraftKey(scope))).not.toContain("secret");
    expect(store.getItem(examDraftKey(scope))).not.toContain("prompt");
  });

  test("başka kullanıcı, ders ve oturumun metni geri gelmez", () => {
    const store = new MemoryStorage();
    saveExamDrafts(store, scope, session(), { q1: "Özel taslak" }, now);
    for (const other of [
      { ...scope, userId: "u2" }, { ...scope, courseId: "c2" }, { ...scope, sessionId: "s2" },
    ]) expect(loadExamDrafts(store, other, session(), now).drafts).toEqual({});
    expect(validExamDrafts(scope, session({ course_id: "c2" }), { q1: "Özel" })).toEqual({});
  });

  test("sunucu cevaplandı diyorsa eski taslağı hem ekrandan hem depodan çıkarır", () => {
    const store = new MemoryStorage();
    saveExamDrafts(store, scope, session(), { q1: "Verilmiş cevap", q2: "B" }, now);
    const updated = session({ questions: session().questions?.map((q) => ({ ...q, answered: q.id === "q1" })) });
    expect(loadExamDrafts(store, scope, updated, now).drafts).toEqual({ q2: "B" });
    expect(store.getItem(examDraftKey(scope))).not.toContain("Verilmiş cevap");
  });

  test("bitmiş veya süresi dolmuş oturumda taslağı kaldırır", () => {
    for (const update of [{ expired: true }, { remaining_seconds: 0 }, { finished_at: "2026-09-04T12:01:00Z" }]) {
      const store = new MemoryStorage();
      saveExamDrafts(store, scope, session(), { q1: "Metin" }, now);
      expect(loadExamDrafts(store, scope, session(update), now).drafts).toEqual({});
      expect(store.getItem(examDraftKey(scope))).toBeNull();
    }
  });

  test("bozuk, süresi geçmiş ve geleceğe tarihli kayıt güvenli temizlenir", () => {
    for (const raw of ["{", JSON.stringify({ version: 9 }),
      JSON.stringify({ version: 1, updatedAt: now - EXAM_DRAFT_TTL_MS, drafts: { q1: "Eski" } }),
      JSON.stringify({ version: 1, updatedAt: now + 1, drafts: { q1: "Gelecek" } })]) {
      const store = new MemoryStorage();
      store.setItem(examDraftKey(scope), raw);
      expect(loadExamDrafts(store, scope, session(), now)).toEqual({ drafts: {}, available: true });
      expect(store.getItem(examDraftKey(scope))).toBeNull();
    }
  });

  test("boş, aşırı uzun ve metin olmayan taslak geri yüklenmez", () => {
    expect(validExamDrafts(scope, session(), { q1: "x".repeat(ANSWER_MAX_LENGTH + 1), q2: "" })).toEqual({});
    expect(validExamDrafts(scope, session(), { q1: { solution: "A" }, q2: 42 })).toEqual({});
    expect(validExamDrafts(scope, session(), ["x"])).toEqual({});
  });

  test("tarayıcı depoyu reddederse yazma ve okuma hatası bildirilir, istisna dışarı çıkmaz", () => {
    const store = new MemoryStorage();
    store.setItem = () => { throw new Error("QuotaExceeded"); };
    expect(saveExamDrafts(store, scope, session(), { q1: "Metin" }, now)).toBe(false);
    store.getItem = () => { throw new Error("SecurityError"); };
    expect(loadExamDrafts(store, scope, session(), now)).toEqual({ drafts: {}, available: false });
    expect(loadExamDrafts(null, scope, session(), now).available).toBe(false);
  });

  test("gönderimden sonra yalnız ilgili oturumun kaydı kaldırılır", () => {
    const store = new MemoryStorage();
    saveExamDrafts(store, scope, session(), { q1: "Metin" }, now);
    store.setItem("diğer-kayıt", "koru");
    expect(removeExamDrafts(store, scope)).toBe(true);
    expect(store.getItem(examDraftKey(scope))).toBeNull();
    expect(store.getItem("diğer-kayıt")).toBe("koru");
  });

  test("çıkış bütün taslakları siler, başka uygulama kayıtlarına dokunmaz", () => {
    const store = new MemoryStorage();
    store.setItem(examDraftKey(scope), "bir");
    store.setItem(examDraftKey({ ...scope, userId: "u2" }), "iki");
    store.setItem("tema", "dark");
    clearAllExamDrafts(store);
    expect([...store.data]).toEqual([["tema", "dark"]]);
  });
});
