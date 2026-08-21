import { describe, expect, it } from "bun:test";

import {
  appendUnique,
  initialPagedContinuation,
  pagedContinuationReducer,
  pagedPath,
} from "./use-paged-resource";

describe("paged resource core", () => {
  it("mevcut sorguyu koruyup opak imleci URL encode eder", () => {
    expect(pagedPath("/questions?status=draft", "a+b/c=", 25)).toBe(
      "/questions?status=draft&cursor=a%2Bb%2Fc%3D&limit=25",
    );
  });

  it("sayfa sınırındaki tekrarları kimlikle eler", () => {
    expect(appendUnique([{ id: "a" }, { id: "b" }], [{ id: "b" }, { id: "c" }])).toEqual([
      { id: "a" },
      { id: "b" },
      { id: "c" },
    ]);
  });

  it("polling ilk sayfayı yenilediğinde yüklenmiş devam sayfalarını ve cursor'ı korur", () => {
    let state = pagedContinuationReducer(initialPagedContinuation<{ id: string }>(), {
      type: "first-page-loaded",
      nextCursor: "page-2",
    });
    state = pagedContinuationReducer(state, {
      type: "extra-page-loaded",
      items: [{ id: "b" }, { id: "c" }],
      nextCursor: "page-3",
    });
    state = pagedContinuationReducer(state, {
      type: "first-page-loaded",
      nextCursor: "poll-page-2",
    });

    expect(state.extraItems).toEqual([{ id: "b" }, { id: "c" }]);
    expect(state.nextCursor).toBe("page-3");
    expect(appendUnique([{ id: "a" }, { id: "b" }], state.extraItems)).toEqual([
      { id: "a" },
      { id: "b" },
      { id: "c" },
    ]);
  });

  it("identity değişimi veya bilinçli reload devam sayfalarını sıfırlar", () => {
    const loaded = pagedContinuationReducer(initialPagedContinuation<{ id: string }>(), {
      type: "extra-page-loaded",
      items: [{ id: "b" }],
      nextCursor: "page-3",
    });

    expect(pagedContinuationReducer(loaded, { type: "reset" })).toEqual({
      extraItems: [],
      nextCursor: null,
      hasLoadedExtra: false,
    });
  });

  it("devam sayfaları kendi aralarında da kimlikle tekilleştirilir", () => {
    let state = pagedContinuationReducer(initialPagedContinuation<{ id: string }>(), {
      type: "extra-page-loaded",
      items: [{ id: "b" }, { id: "c" }],
      nextCursor: "page-3",
    });
    state = pagedContinuationReducer(state, {
      type: "extra-page-loaded",
      items: [{ id: "c" }, { id: "d" }],
      nextCursor: null,
    });

    expect(state.extraItems.map((item) => item.id)).toEqual(["b", "c", "d"]);
  });
});
