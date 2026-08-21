import { describe, expect, test } from "bun:test";
import { chatDeletionMessage, exportFilename } from "./privacy";

describe("kişisel veri dışa aktarma", () => {
  test("tarih dosya adına kararlı biçimde girer", () => {
    expect(exportFilename("2026-08-10T01:15:00+03:00")).toBe(
      "dou-synapse-verilerim-2026-08-10.json",
    );
  });

  test("bozuk tarihte güvenli dosya adı üretir", () => {
    expect(exportFilename("beklenmeyen")).toBe("dou-synapse-verilerim-veri.json");
  });
});

describe("sohbet silme sonucu", () => {
  test("boş ve dolu sonuç birbirinden ayrılır", () => {
    expect(chatDeletionMessage(0)).toBe("Silinecek sohbet geçmişi bulunamadı.");
    expect(chatDeletionMessage(3)).toBe("3 sohbet oturumu kalıcı olarak silindi.");
  });
});
