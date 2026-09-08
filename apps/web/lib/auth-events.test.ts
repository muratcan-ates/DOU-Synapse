import { afterEach, describe, expect, test } from "bun:test";
import { authChangeFromMarker, clearPrivateSessionData, createProviderAuthObserver, notifyAuthChange, readWithinAuthEpoch } from "./auth-events";
import { EXAM_DRAFT_PREFIX, type DraftStorage } from "./exam-drafts";

function storage(initial: Record<string, string>): DraftStorage {
  const values = new Map(Object.entries(initial));
  return { getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => { values.set(key, value); }, removeItem: (key) => { values.delete(key); },
    key: (index) => [...values.keys()][index] ?? null, get length() { return values.size; } };
}

describe("yerel özel oturum verisi temizliği", () => {
  test("her sekmenin cevap taslağı ve paylaşılan sohbet/sınav seçimleri silinir, tercihler korunur", () => {
    const key = EXAM_DRAFT_PREFIX + "student:course:exam";
    const first = storage({ [key]: "özel cevap A", preference: "A" });
    const second = storage({ [key]: "özel cevap B", preference: "B" });
    const shared = storage({ "dou-synapse-chat-session:course": "chat-id", "dou-synapse-exam-session:student:course": "exam-id", theme: "dark" });
    clearPrivateSessionData(first, shared);
    clearPrivateSessionData(second, shared);
    expect(first.getItem(key)).toBeNull(); expect(second.getItem(key)).toBeNull();
    expect(shared.getItem("dou-synapse-chat-session:course")).toBeNull();
    expect(shared.getItem("dou-synapse-exam-session:student:course")).toBeNull();
    expect(shared.getItem("theme")).toBe("dark");
    expect(first.getItem("preference")).toBe("A"); expect(second.getItem("preference")).toBe("B");
  });
  test("erişilemeyen depo çıkışı engellemez", () => {
    expect(() => clearPrivateSessionData(null, null)).not.toThrow();
  });
});

describe("SDK auth olayı", () => {
  test("ilk oturum ve aynı kimliğin odak/token yenilemesi geçerli taslağı silmez", () => {
    const changes: string[] = []; const observe = createProviderAuthObserver((kind) => changes.push(kind));
    observe("INITIAL_SESSION", "student"); observe("SIGNED_IN", "student");
    observe("TOKEN_REFRESHED", "student"); observe("USER_UPDATED", "student");
    expect(changes).toEqual([]);
    observe("SIGNED_IN", "teacher"); expect(changes).toEqual(["identity-changed"]);
    observe("SIGNED_OUT", null); expect(changes).toEqual(["identity-changed", "signed-out"]);
    observe("SIGNED_IN", "student"); expect(changes).toEqual(["identity-changed", "signed-out", "identity-changed"]);
  });
  test("SDK ilk session bildirimi gelmeden çıkan kullanıcı da kapanır", () => {
    const changes: string[] = []; const observe = createProviderAuthObserver((kind) => changes.push(kind));
    observe("SIGNED_OUT", null); expect(changes).toEqual(["signed-out"]);
  });
  test("marker yalnız içeriksiz olay türünü kabul eder", () => {
    expect(authChangeFromMarker("signed-out:nonce")).toBe("signed-out");
    expect(authChangeFromMarker("identity-changed:nonce")).toBe("identity-changed");
    expect(authChangeFromMarker('{"user":"student"}')).toBeNull();
    expect(authChangeFromMarker(null)).toBeNull();
  });
});


describe("SDK okuması sırasında auth sınırı", () => {
  afterEach(() => notifyAuthChange("identity-changed"));
  test("geciken token/kimlik çıkıştan sonra kullanılamaz", async () => {
    notifyAuthChange("identity-changed");
    let resolve!: (value: { token: string; user: string }) => void;
    const reading = readWithinAuthEpoch(() => new Promise<{ token: string; user: string }>((done) => { resolve = done; }));
    notifyAuthChange("signed-out");
    resolve({ token: "synthetic-old-token", user: "old-student" });
    expect(await reading).toBeNull();
  });
  test("geciken token/kimlik başka hesaba geçişten sonra kullanılamaz", async () => {
    notifyAuthChange("identity-changed");
    let resolve!: (value: string) => void;
    const reading = readWithinAuthEpoch(() => new Promise<string>((done) => { resolve = done; }));
    notifyAuthChange("identity-changed");
    resolve("synthetic-old-token");
    expect(await reading).toBeNull();
    expect(await readWithinAuthEpoch(async () => "synthetic-new-token")).toBe("synthetic-new-token");
  });
  test("aynı oturumun başarılı yenilemesi korunur; kapalı oturumda SDK çağrılmaz", async () => {
    notifyAuthChange("identity-changed");
    expect(await readWithinAuthEpoch(async () => "fresh-token")).toBe("fresh-token");
    notifyAuthChange("signed-out");
    let called = false;
    expect(await readWithinAuthEpoch(async () => { called = true; return "old-token"; })).toBeNull();
    expect(called).toBe(false);
  });
});
