/**
 * Ortak sözlüğün testleri — `bun test` ile koşar, ek bağımlılık yok.
 *
 * Neden bu dosya var: `lib/labels.ts` ürün kararlarını taşıyor (seviye eşikleri,
 * durum tonları). Bu kararlar spec'te yazılı sayılardır ve sessizce değişirlerse
 * kimse fark etmez — arayüz yine çalışır, sadece yanlış şeyi gösterir.
 *
 * Tonlar da test ediliyor çünkü DESIGN.md'nin en kolay ihlal edilen kuralı
 * "kırmızı asla hata rengi değildir". Bir gün biri "Reddedildi"yi danger yapar
 * ve kimse fark etmez; bu test o günü yakalar.
 */

import { describe, expect, test } from "bun:test";
import {
  chunkLocation,
  DOCUMENT_STATUS,
  formatBytes,
  MASTERY_THRESHOLDS,
  masteryLevel,
  QUESTION_STATUS,
  QUESTION_TYPE,
} from "./labels";

describe("masteryLevel — eşikler spec FR-027 ile birebir", () => {
  test("tam 0.40 Orta'ya girer (sınır dahil)", () => {
    expect(masteryLevel(0.4).label).toBe("Orta");
  });

  test("0.40'ın hemen altı Geliştirilmeli", () => {
    expect(masteryLevel(0.399).label).toBe("Geliştirilmeli");
  });

  test("tam 0.75 İyi'ye girer (sınır dahil)", () => {
    expect(masteryLevel(0.75).label).toBe("İyi");
  });

  test("0.75'in hemen altı Orta", () => {
    expect(masteryLevel(0.749).label).toBe("Orta");
  });

  test("uç değerler", () => {
    expect(masteryLevel(0).label).toBe("Geliştirilmeli");
    expect(masteryLevel(1).label).toBe("İyi");
  });

  test("eşik sabitleri spec'teki değerlerde", () => {
    // Bu sayılar backend'deki EWMA servisiyle aynı olmak zorunda.
    // Değiştirmek isteyen önce spec FR-027'yi değiştirsin.
    expect(MASTERY_THRESHOLDS.medium).toBe(0.4);
    expect(MASTERY_THRESHOLDS.good).toBe(0.75);
  });

  test("düşük skor WARNING tonunda, DANGER değil", () => {
    // DESIGN.md: kırmızı asla hata rengi değildir. Düşük skor bir hata değil,
    // çalışma yönüdür.
    expect(masteryLevel(0.1).tone).toBe("warning");
    expect(masteryLevel(0.1).tone).not.toBe("danger");
  });
});

describe("durum sözlükleri — renk tek başına bilgi taşımaz", () => {
  test("her belge durumunun boş olmayan bir etiketi var", () => {
    for (const spec of Object.values(DOCUMENT_STATUS)) {
      expect(spec.label.length).toBeGreaterThan(0);
    }
  });

  test("her soru durumunun boş olmayan bir etiketi var", () => {
    for (const spec of Object.values(QUESTION_STATUS)) {
      expect(spec.label.length).toBeGreaterThan(0);
    }
  });

  test("reddedilen soru DANGER değil — red bir hata değil, eğitmen kararı", () => {
    expect(QUESTION_STATUS.rejected.tone).not.toBe("danger");
  });

  test("yalnız gerçek hata danger tonunda: işleme başarısızlığı", () => {
    expect(DOCUMENT_STATUS.failed.tone).toBe("danger");
    const digerleri = [
      DOCUMENT_STATUS.uploaded,
      DOCUMENT_STATUS.processing,
      DOCUMENT_STATUS.completed,
    ];
    for (const spec of digerleri) expect(spec.tone).not.toBe("danger");
  });

  test("etiketlerde büyük harf dönüşümü yok (Türkçe i/İ kuralı)", () => {
    const hepsi = [
      ...Object.values(DOCUMENT_STATUS).map((s) => s.label),
      ...Object.values(QUESTION_STATUS).map((s) => s.label),
      ...Object.values(QUESTION_TYPE),
    ];
    for (const label of hepsi) {
      expect(label).not.toBe(label.toUpperCase());
    }
  });

  test("dört soru tipinin de Türkçe karşılığı var", () => {
    expect(Object.keys(QUESTION_TYPE).sort()).toEqual([
      "bug_hunt",
      "code_trace",
      "mcq",
      "open",
    ]);
  });
});

describe("formatBytes", () => {
  test("bayt, KB ve MB eşikleri", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(1024)).toBe("1 KB");
    expect(formatBytes(65449)).toBe("64 KB");
    expect(formatBytes(20 * 1024 * 1024)).toBe("20.0 MB");
  });

  test("sıfır patlamıyor", () => {
    expect(formatBytes(0)).toBe("0 B");
  });
});

describe("chunkLocation — konum HER ZAMAN görünür", () => {
  const bos = { page_number: null, slide_number: null, section_title: null };

  test("sayfa varsa sayfa", () => {
    expect(chunkLocation({ ...bos, page_number: 7 })).toBe("Sayfa 7");
  });

  test("slayt varsa slayt", () => {
    expect(chunkLocation({ ...bos, slide_number: 3 })).toBe("Slayt 3");
  });

  test("ikisi de yoksa bölüm adı", () => {
    expect(chunkLocation({ ...bos, section_title: "produce (satır 32-39)" })).toBe(
      "produce (satır 32-39)",
    );
  });

  test("hiçbiri yoksa bile boş string dönmez", () => {
    // Konum bilgisi kaybolursa atıf anlamını yitirir; boş bırakmak yerine
    // görünür bir işaret bırakılır.
    expect(chunkLocation(bos).length).toBeGreaterThan(0);
  });

  test("sayfa 0 geçerli bir değerdir, atlanmaz", () => {
    // 0 falsy'dir; `??` yerine `!= null` kullanılmazsa bu satır sessizce kaybolur.
    expect(chunkLocation({ ...bos, page_number: 0 })).toBe("Sayfa 0");
  });
});
