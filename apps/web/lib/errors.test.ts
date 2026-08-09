/**
 * Hata çözümlemesinin testi.
 *
 * Kural (Anayasa V): backend anlaşılır Türkçe üretir, arayüz kendi hata metnini
 * UYDURMAZ. Bu test o kuralı sabitliyor — backend bir mesaj verdiyse kullanıcı
 * onu görür, yedek metin yalnız backend susmuşsa devreye girer.
 */

import { describe, expect, test } from "bun:test";
import { ApiError } from "./api";
import { errorMessage } from "./errors";

describe("errorMessage", () => {
  test("backend mesajı olduğu gibi taşınır", () => {
    const e = new ApiError("Bu dosya derse zaten yüklenmiş: a.pdf", "conflict", 409);
    expect(errorMessage(e)).toBe("Bu dosya derse zaten yüklenmiş: a.pdf");
  });

  test("backend mesajı yedek metinle EZİLMEZ", () => {
    const e = new ApiError("Ders bulunamadı.", "not_found", 404);
    expect(errorMessage(e, "Bir şeyler ters gitti.")).toBe("Ders bulunamadı.");
  });

  test("ApiError olmayan hata yedek metne düşer", () => {
    expect(errorMessage(new TypeError("fetch failed"))).toBe("Bağlantı kurulamadı.");
  });

  test("çağıran kendi yedek metnini verebilir", () => {
    expect(errorMessage(new Error("boom"), "Yükleme tamamlanamadı.")).toBe(
      "Yükleme tamamlanamadı.",
    );
  });

  test("hata olmayan değerler de patlamaz", () => {
    expect(errorMessage(null)).toBe("Bağlantı kurulamadı.");
    expect(errorMessage(undefined)).toBe("Bağlantı kurulamadı.");
    expect(errorMessage("düz string")).toBe("Bağlantı kurulamadı.");
  });
});
