import { afterEach, describe, expect, spyOn, test } from "bun:test";
import { api, ApiError } from "./api";
import { notifyAuthChange } from "./auth-events";
import { createChatDeletionBus, deleteOwnChatHistory, deletionAffectsSession, isChatHistoryRecovery, subscribeChatDeletions } from "./chat-history-deletion";

const course = "11111111-1111-4111-8111-111111111111";
const otherCourse = "22222222-2222-4222-8222-222222222222";
const session = "33333333-3333-4333-8333-333333333333";
const otherSession = "44444444-4444-4444-8444-444444444444";

describe("ders/oturum kapsamlı sekme sinyali", () => {
  test("aynı auth dönemi içinde hedef ders iki sekmede değişir; özel alanlar yayınlanmaz", () => {
    const published: string[] = []; const received: unknown[] = []; let other = 0;
    const second = createChatDeletionBus(() => "epoch-a", () => { throw new Error("Yankı olmamalı"); });
    const first = createChatDeletionBus(() => "epoch-a", (value) => { published.push(value); second.receive(value); });
    first.subscribe(course, (scope) => received.push(["first", scope]));
    second.subscribe(course, (scope) => received.push(["second", scope]));
    second.subscribe(otherCourse, () => { other += 1; });
    const extraFields = { courseId: course, sessionId: session, title: "PRIVATE TITLE", token: "PRIVATE TOKEN", answer: "PRIVATE ANSWER" };
    first.notify(extraFields);
    expect(received).toHaveLength(2); expect(other).toBe(0);
    const body = JSON.parse(published[0]);
    expect(Object.keys(body).sort()).toEqual(["authEpoch", "courseId", "nonce", "sessionId"]);
    expect(published[0]).not.toContain("PRIVATE");
    second.receive(published[0]); expect(received).toHaveLength(2);
  });
  test("eski kullanıcının gecikmiş silme sinyali yeni kimliği etkileyemez", () => {
    let epoch = "old"; let oldSignal = ""; let calls = 0;
    const writer = createChatDeletionBus(() => epoch, (value) => { oldSignal = value; });
    const reader = createChatDeletionBus(() => epoch, () => {});
    reader.subscribe(course, () => { calls += 1; });
    writer.notify({ courseId: course, sessionId: null });
    epoch = "new"; reader.receive(oldSignal); expect(calls).toBe(0);
    writer.notify({ courseId: course, sessionId: null }); reader.receive(oldSignal); expect(calls).toBe(1);
  });
  test("bozuk veya kapsamı eksik sinyaller ve ayrılan tüketici yok sayılır", () => {
    let calls = 0; const bus = createChatDeletionBus(() => null, () => {});
    const stop = bus.subscribe(course, () => { calls += 1; });
    for (const value of [null, "not-json", "{}", JSON.stringify({ courseId: course, sessionId: session, nonce: "bad", authEpoch: null })]) bus.receive(value);
    expect(calls).toBe(0); stop(); bus.notify({ courseId: course, sessionId: null }); expect(calls).toBe(0);
  });
  test("tek silme başka açık taslağı korur; toplu silme bekleyen yeni sohbeti de kapatır", () => {
    expect(deletionAffectsSession({ courseId: course, sessionId: session }, otherSession)).toBe(false);
    expect(deletionAffectsSession({ courseId: course, sessionId: session }, session)).toBe(true);
    expect(deletionAffectsSession({ courseId: course, sessionId: session }, null)).toBe(false);
    expect(deletionAffectsSession({ courseId: course, sessionId: null }, null)).toBe(true);
  });
});

describe("gerçek silme sarmalayıcısının auth ve API sınırı", () => {
  afterEach(() => notifyAuthChange("identity-changed"));
  test("tek ve toplu silme doğru API yolunu kullanır; yalnız başarılı sonuç bildirilir", async () => {
    notifyAuthChange("identity-changed"); const paths: string[] = []; const seen: unknown[] = [];
    const stop = subscribeChatDeletions(course, (scope) => seen.push(scope));
    const remove = spyOn(api, "delete").mockImplementation(async <T>(path: string) => { paths.push(path); return { deleted_sessions: 1 } as T; });
    try {
      expect(await deleteOwnChatHistory({ courseId: course, sessionId: session })).toBe(1);
      expect(await deleteOwnChatHistory({ courseId: course, sessionId: null })).toBe(1);
      expect(paths).toEqual([`/courses/${course}/chat/sessions/${session}`, `/courses/${course}/chat/sessions`]);
      expect(seen).toEqual([{ courseId: course, sessionId: session }, { courseId: course, sessionId: null }]);
    } finally { remove.mockRestore(); stop(); }
  });
  test("DELETE beklerken kimlik değişirse başarılı eski cevap bildirim veya temizlik yapmaz", async () => {
    notifyAuthChange("identity-changed"); let resolve!: (value: { deleted_sessions: number }) => void; let calls = 0;
    const response = new Promise<{ deleted_sessions: number }>((done) => { resolve = done; });
    const remove = spyOn(api, "delete").mockImplementation(async <T>() => await response as T);
    const stop = subscribeChatDeletions(course, () => { calls += 1; });
    try {
      const deletion = deleteOwnChatHistory({ courseId: course, sessionId: null });
      notifyAuthChange("identity-changed"); resolve({ deleted_sessions: 2 });
      expect(await deletion).toBeNull(); expect(calls).toBe(0);
    } finally { remove.mockRestore(); stop(); }
  });
  test("sunucu reddi silme sinyali üretmez", async () => {
    notifyAuthChange("identity-changed"); let calls = 0;
    const failure = new ApiError("Bulunamadı.", "not_found", 404, "synthetic-request");
    const remove = spyOn(api, "delete").mockImplementation(async () => { throw failure; });
    const stop = subscribeChatDeletions(course, () => { calls += 1; });
    try {
      await expect(deleteOwnChatHistory({ courseId: course, sessionId: session })).rejects.toBe(failure);
      expect(calls).toBe(0);
    } finally { remove.mockRestore(); stop(); }
  });
});

test("geçmiş veya ders erişimi değişimi yeniden yetki doğrulaması ister", () => {
  expect(isChatHistoryRecovery(new ApiError("Değişti", "chat_history_changed", 409))).toBe(true);
  expect(isChatHistoryRecovery(new ApiError("Kapalı", "exam_in_progress", 403))).toBe(true);
  expect(isChatHistoryRecovery(new ApiError("Ders veya oturum bulunamadı", "not_found", 404))).toBe(true);
  expect(isChatHistoryRecovery(new ApiError("Başka çakışma", "other_conflict", 409))).toBe(false);
  expect(isChatHistoryRecovery(new ApiError("Tekrar dene", "rate_limited", 429))).toBe(false);
});
