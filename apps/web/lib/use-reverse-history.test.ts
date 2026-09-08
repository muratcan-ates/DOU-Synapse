/** Geçmişin görünümü ve üretimdeki asenkron istek/iptal sözleşmesi. */

import { describe, expect, test } from "bun:test";

import type { ErrorInfo } from "./errors";
import {
  createReverseHistory,
  initialReverseHistory,
  reverseHistoryReducer,
  type ReverseHistoryState,
} from "./use-reverse-history";

const FAILURE: ErrorInfo = {
  message: "Sunucu cümlesi.",
  kind: "transient",
  requestId: "req-1",
};

function loadedState(): ReverseHistoryState<string> {
  let state = initialReverseHistory<string>();
  state = reverseHistoryReducer(state, { type: "open-started" });
  state = reverseHistoryReducer(state, {
    type: "open-loaded",
    items: ["eski", "yeni"],
    cursor: "sayfa-2",
  });
  return state;
}

describe("reverseHistoryReducer — açılış", () => {
  test("open-started listeyi ve imleci sıfırlar, hatayı temizler, yüklemeyi açar", () => {
    let state = loadedState();
    state = reverseHistoryReducer(state, { type: "open-failed", error: FAILURE });
    state = reverseHistoryReducer(state, { type: "open-started" });

    expect(state).toEqual({
      items: [],
      cursor: null,
      loading: true,
      olderLoading: false,
      error: null,
    });
  });

  test("open-loaded ilk sayfayı ve imleci yazar, yüklemeyi kapatır", () => {
    const state = loadedState();
    expect(state.items).toEqual(["eski", "yeni"]);
    expect(state.cursor).toBe("sayfa-2");
    expect(state.loading).toBe(false);
  });

  test("open-failed hatayı yazar ve yüklemeyi kapatır; liste boş kalır", () => {
    let state = initialReverseHistory<string>();
    state = reverseHistoryReducer(state, { type: "open-started" });
    state = reverseHistoryReducer(state, { type: "open-failed", error: FAILURE });

    expect(state.error).toBe(FAILURE);
    expect(state.loading).toBe(false);
    expect(state.items).toEqual([]);
  });
});

describe("reverseHistoryReducer — devam sayfası (prepend)", () => {
  test("older-loaded daha eskiyi BAŞA ekler ve imleci ilerletir", () => {
    let state = loadedState();
    state = reverseHistoryReducer(state, { type: "older-started" });
    expect(state.olderLoading).toBe(true);

    state = reverseHistoryReducer(state, {
      type: "older-loaded",
      items: ["en-eski"],
      cursor: null,
    });

    expect(state.items).toEqual(["en-eski", "eski", "yeni"]);
    expect(state.cursor).toBeNull();
    expect(state.olderLoading).toBe(false);
  });

  test("older-started önceki hatayı temizler; older-failed yenisini yazar", () => {
    let state = loadedState();
    state = reverseHistoryReducer(state, { type: "older-failed", error: FAILURE });
    expect(state.error).toBe(FAILURE);

    state = reverseHistoryReducer(state, { type: "older-started" });
    expect(state.error).toBeNull();
    expect(state.olderLoading).toBe(true);
  });

  test("reset önceki devam isteğinin UI izini siler", () => {
    const state = reverseHistoryReducer({ ...loadedState(), olderLoading: true }, { type: "reset" });
    expect(state).toEqual(initialReverseHistory<string>());
  });

});

describe("reverseHistoryReducer — canlı tur eklemeleri", () => {
  test("append satırları SONA ekler (soru + cevap sırası bozulmaz)", () => {
    let state = loadedState();
    state = reverseHistoryReducer(state, {
      type: "append",
      items: ["soru", "cevap"],
    });
    expect(state.items).toEqual(["eski", "yeni", "soru", "cevap"]);
  });

  test("update satır içi düzeltir, sırayı ve diğer alanları değiştirmez", () => {
    let state = loadedState();
    state = reverseHistoryReducer(state, {
      type: "update",
      apply: (items) => items.map((item) => (item === "eski" ? "eski*" : item)),
    });
    expect(state.items).toEqual(["eski*", "yeni"]);
    expect(state.cursor).toBe("sayfa-2");
  });
});

function pending<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

type StringPage = { items: string[]; next_cursor: string | null };
function historyHarness() {
  let state = initialReverseHistory<string>();
  const requests: Array<{ path: string } & ReturnType<typeof pending<StringPage>>> = [];
  const runner = createReverseHistory<string, string>({
    load: (path) => { const request = { path, ...pending<StringPage>() }; requests.push(request); return request.promise; },
    map: (items) => items,
    dispatch: (action) => { state = reverseHistoryReducer(state, action); },
  });
  return { runner, requests, state: () => state };
}

async function openFirst(h: ReturnType<typeof historyHarness>) {
  const opening = h.runner.open("/sessions/a");
  h.requests[0].resolve({ items: ["A son mesaj"], next_cursor: "a-cursor" });
  expect(await opening).toBe(true);
}

describe("geçmiş isteği yaşam döngüsü", () => {
  test("A devamı B açıldıktan sonra dönerse B içeriği ve imleci değişmez", async () => {
    const h = historyHarness(); await openFirst(h);
    const older = h.runner.loadOlder();
    const openingB = h.runner.open("/sessions/b");
    h.requests[2].resolve({ items: ["B mesaj"], next_cursor: "b-cursor" });
    await openingB;
    h.requests[1].resolve({ items: ["A özel eski mesaj"], next_cursor: "a-older" });
    await older;
    expect(h.state().items).toEqual(["B mesaj"]);
    expect(h.state().cursor).toBe("b-cursor");
    expect(h.state().olderLoading).toBe(false);
  });

  test("reset sonrası gecikmiş devam başarı/hatası özel geçmişi geri getiremez", async () => {
    for (const fail of [false, true]) {
      const h = historyHarness(); await openFirst(h);
      const older = h.runner.loadOlder(); h.runner.reset();
      if (fail) h.requests[1].reject(new Error("eski hata"));
      else h.requests[1].resolve({ items: ["özel eski mesaj"], next_cursor: "a-older" });
      await older;
      expect(h.state()).toEqual(initialReverseHistory<string>());
    }
  });

  test("eski isteğin bitişi yeni devam isteğinin kapısını açamaz", async () => {
    const h = historyHarness(); await openFirst(h);
    const olderA = h.runner.loadOlder();
    const openingB = h.runner.open("/sessions/b");
    h.requests[2].resolve({ items: ["B"], next_cursor: "b-cursor" }); await openingB;
    const olderB = h.runner.loadOlder();
    h.requests[1].resolve({ items: ["A eski"], next_cursor: null }); await olderA;
    await h.runner.loadOlder();
    expect(h.requests).toHaveLength(4);
    expect(h.state().olderLoading).toBe(true);
    h.requests[3].resolve({ items: ["B eski"], next_cursor: null }); await olderB;
    expect(h.state().items).toEqual(["B eski", "B"]);
  });

  test("unmount sırasında ilk sayfa ve devam sayfasının yan etkisi kapanır", async () => {
    const first = historyHarness();
    const opening = first.runner.open("/sessions/a"); first.runner.cancel();
    const before = first.state();
    first.requests[0].resolve({ items: ["özel"], next_cursor: null });
    expect(await opening).toBe(false); expect(first.state()).toBe(before);
    const older = historyHarness(); await openFirst(older);
    const request = older.runner.loadOlder(); older.runner.cancel();
    const olderBefore = older.state();
    older.requests[1].reject(new Error("geç hata")); await request;
    expect(older.state()).toBe(olderBefore);
  });

  test("StrictMode tekrar kurulumunda iptal edilmiş restore yeni istekle okunur", async () => {
    const h = historyHarness();
    const old = h.runner.open("/sessions/a"); h.runner.cancel(); h.runner.resume();
    expect(h.requests).toHaveLength(2);
    h.requests[0].resolve({ items: ["eski"], next_cursor: null });
    expect(await old).toBe(false);
    h.requests[1].resolve({ items: ["yeniden doğrulanan"], next_cursor: null });
    await Promise.resolve();
    expect(h.state().items).toEqual(["yeniden doğrulanan"]);
  });
});
