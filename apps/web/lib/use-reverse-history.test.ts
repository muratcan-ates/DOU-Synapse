/**
 * Ters sayfalamanın durum makinesi.
 *
 * Kanca React'e bağlı olduğu için doğrudan koşturulamıyor (bu paket DOM'suz
 * `bun test` ile koşar); karar çekirdeği `reverseHistoryReducer` olarak saf
 * çıkarıldı ve testler onu sınıyor. Buradaki iki çivi bilinçli:
 *
 *  - `reset`/`open-started` uçuştaki devam isteğinin `olderLoading` bayrağına
 *    DOKUNMAZ; bayrağı isteğin kendi bitişi düşürür.
 *  - Geç gelen `older-loaded` o anki listeye eklenir: devam isteği token'la
 *    geçersizlenmez. Bu, ChatScreen'den taşınan ÖLÇÜLMÜŞ davranıştır; kural
 *    değişecekse burada bilerek değiştirilmeli.
 */

import { describe, expect, test } from "bun:test";

import type { ErrorInfo } from "./errors";
import {
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

  test("reset uçuştaki devam bayrağına dokunmaz; bayrağı isteğin bitişi düşürür", () => {
    let state = loadedState();
    state = reverseHistoryReducer(state, { type: "older-started" });
    state = reverseHistoryReducer(state, { type: "reset" });

    expect(state.items).toEqual([]);
    expect(state.cursor).toBeNull();
    expect(state.olderLoading).toBe(true);

    state = reverseHistoryReducer(state, {
      type: "older-loaded",
      items: ["gecikmiş"],
      cursor: "eski-imleç",
    });
    // Bilinçli korunan davranış: geç gelen devam cevabı o anki listeye yazar.
    expect(state.items).toEqual(["gecikmiş"]);
    expect(state.cursor).toBe("eski-imleç");
    expect(state.olderLoading).toBe(false);
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
