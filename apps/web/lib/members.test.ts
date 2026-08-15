import { describe, expect, test } from "bun:test";

describe("katılımcı listesi hata çıkışı", () => {
  test("ilk transient yükleme hatası yeniden deneme yolunu korur", async () => {
    const source = await Bun.file(
      new URL("../app/courses/[courseId]/members/page.tsx", import.meta.url),
    ).text();

    expect(source).toContain("errorKind,");
    expect(source).toContain("errorRequestId,");
    expect(source).toContain("onRetry={reload}");
  });
});
