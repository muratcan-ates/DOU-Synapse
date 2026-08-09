/**
 * Hata çözümlemesinin testi.
 *
 * Kural (Anayasa V): backend anlaşılır Türkçe üretir, arayüz kendi hata metnini
 * UYDURMAZ. Bu test o kuralı sabitliyor — backend bir mesaj verdiyse kullanıcı
 * onu görür, yedek metin yalnız backend susmuşsa devreye girer.
 */

import { describe, expect, test } from "bun:test";
import { ApiError } from "./api";
import { classifyError, describeError, errorMessage, shouldOfferRetry } from "./errors";

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

describe("classifyError — metnin yanında sınıf da taşınır (T403)", () => {
  test("sunucuya varılamayan her şey geçicidir", () => {
    expect(classifyError(new TypeError("fetch failed"))).toBe("transient");
    expect(classifyError(new Error("boom"))).toBe("transient");
    expect(classifyError(null)).toBe("transient");
    expect(classifyError("düz string")).toBe("transient");
  });

  test("sunucunun söylediği hata kendi sınıfını taşır", () => {
    expect(classifyError(new ApiError("kısa süreli", "internal_error", 503))).toBe(
      "transient",
    );
    expect(classifyError(new ApiError("Ders bulunamadı.", "not_found", 404))).toBe(
      "permanent",
    );
    expect(classifyError(new ApiError("Oturum yok.", "unauthenticated", 401))).toBe(
      "auth",
    );
  });

  test("sınav kilidi kalıcıdır, kimlik hatası değil", () => {
    const locked = new ApiError("Süren bir sınav var.", "exam_in_progress", 403);
    expect(classifyError(locked)).toBe("permanent");
    expect(classifyError(locked)).not.toBe("auth");
  });
});

describe("describeError — mesaj, sınıf ve destek kodu tek geçişte", () => {
  test("sunucu hatası üç alanı da doldurur", () => {
    const info = describeError(new ApiError("Ders bulunamadı.", "not_found", 404, "abc123"));
    expect(info).toEqual({
      message: "Ders bulunamadı.",
      kind: "permanent",
      requestId: "abc123",
    });
  });

  test("ağ hatasında destek kodu YOKTUR: ortada istek kaydı yok", () => {
    const info = describeError(new TypeError("fetch failed"));
    expect(info.kind).toBe("transient");
    expect(info.requestId).toBeNull();
    // Metin yine uydurulmuyor; yedek cümle `errorMessage` ile aynı.
    expect(info.message).toBe(errorMessage(new TypeError("fetch failed")));
  });

  test("çağıranın yedek metni korunur", () => {
    expect(describeError(new Error("boom"), "Yükleme tamamlanamadı.").message).toBe(
      "Yükleme tamamlanamadı.",
    );
  });
});

describe("shouldOfferRetry — düğme kararı hatırlanmak zorunda değil (FR-153)", () => {
  test("geçici hatada düğme çıkar", () => {
    expect(shouldOfferRetry("transient", true)).toBe(true);
  });

  test("kalıcı ve kimlik hatasında düğme GİZLENİR, eylem verilmiş olsa bile", () => {
    // Bugünkü kusur tam burada: `app/courses/page.tsx:59` 404'te de düğmeyi
    // gösteriyor. Düğme çalışıyor ama sonucu değiştiremiyor.
    expect(shouldOfferRetry("permanent", true)).toBe(false);
    expect(shouldOfferRetry("auth", true)).toBe(false);
  });

  test("eylem yoksa sınıf ne olursa olsun düğme yok", () => {
    // Etkin görünüp iş yapmayan düğme kusurdur (Anayasa XI).
    expect(shouldOfferRetry("transient", false)).toBe(false);
    expect(shouldOfferRetry(null, false)).toBe(false);
  });

  test("sınıflandırılmamış hata eski davranışı korur", () => {
    // `kind` yokluğu "kalıcı" DEĞİL "bilinmiyor" demek: sınıfı henüz
    // geçirmeyen çağrı yerlerinden çalışan bir düğmeyi almak, kullanıcıdan
    // çıkış yolunu sessizce almak olurdu.
    expect(shouldOfferRetry(undefined, true)).toBe(true);
    expect(shouldOfferRetry(null, true)).toBe(true);
  });
});
