import { describe, expect, it } from "bun:test";

import { appendUnique, pagedPath } from "./use-paged-resource";

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
});
