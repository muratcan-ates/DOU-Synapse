import { describe, expect, test } from "bun:test";
import { createPolicyDraftBuffer } from "./policy-draft-buffer";
import type { PolicyDraft } from "./policy";

function draft(hintLimit: number): PolicyDraft {
  return {
    inheritModes: true, allowedModes: ["qa"], inheritHints: false, hintLimit,
    inheritEvidence: true, evidenceThreshold: 0.8, useCourseHardCap: true,
    dailyBudget: 1000, studentDailyTokenBudget: 12000, instructorDailyTokenBudget: 40000,
    maxOutputTokens: 700, maxConcurrentRequests: 1, allSources: true, sourceDocumentIds: [],
  };
}

describe("yalnız RAM'deki politika taslağı", () => {
  test("geçici gate unmount taslağı korur, eski editör yeniden yazamaz", async () => {
    const buffer = createPolicyDraftBuffer();
    const previous = buffer.open(); previous.write(draft(4));
    let resolve!: () => void;
    const pending = new Promise<void>((done) => { resolve = done; });
    const lateSave = pending.then(() => previous.write(draft(3)));
    previous.close();
    const resumed = buffer.open();
    expect(resumed.read()?.hintLimit).toBe(4);
    resolve(); expect(await lateSave).toBe(false);
    expect(resumed.read()?.hintLimit).toBe(4);
  });

  test("kesin yetki reddi veya scope kapanışı taslağı ve bekleyen yazarı iptal eder", async () => {
    const buffer = createPolicyDraftBuffer();
    const previous = buffer.open(); previous.write(draft(4));
    let resolve!: () => void;
    const pending = new Promise<void>((done) => { resolve = done; });
    const lateLoad = pending.then(() => previous.write(draft(2)));
    buffer.clear();
    const restored = buffer.open();
    expect(restored.read()).toBeNull();
    resolve(); expect(await lateLoad).toBe(false);
    expect(restored.read()).toBeNull();
  });

  test("eski editörün geciken cleanup'ı yeni editörü kapatamaz", () => {
    const buffer = createPolicyDraftBuffer();
    const previous = buffer.open();
    const resumed = buffer.open(); resumed.write(draft(4));
    previous.close();
    expect(resumed.current()).toBe(true);
    expect(resumed.read()?.hintLimit).toBe(4);
    expect(previous.read()).toBeNull();
  });

  test("ayrı kullanıcı/ders boundary belleği ortak veri taşımaz", () => {
    const oldScope = createPolicyDraftBuffer();
    oldScope.open().write(draft(4));
    oldScope.clear();
    const nextScope = createPolicyDraftBuffer();
    expect(nextScope.open().read()).toBeNull();
    expect(oldScope.open().read()).toBeNull();
  });
});
