import { describe, expect, test } from "bun:test";
import { courseCoverDesign, courseInitials } from "./course-cover";

describe("Türkçe ders kapağı baş harfleri", () => {
  test("Türkçe noktalı ve noktasız i harflerini ayırır", () => {
    expect(courseInitials({ title: "işletim sistemleri" })).toBe("İS");
    expect(courseInitials({ title: "ısı akışı" })).toBe("IA");
    expect(courseInitials({ title: "İleri istatistik" })).toBe("İİ");
  });

  test("tek sözcükte iki karakter, tek harfte bir karakter kullanır", () => {
    expect(courseInitials({ title: "Matematik" })).toBe("MA");
    expect(courseInitials({ title: "i" })).toBe("İ");
    expect(courseInitials({ title: "ı" })).toBe("I");
  });

  test("noktalama ve sembolleri harf sanmaz; sayısal adları destekler", () => {
    expect(courseInitials({ title: "  ‘Veri’ — Yapıları! " })).toBe("VY");
    expect(courseInitials({ title: "3D Modelleme" })).toBe("3M");
    expect(courseInitials({ title: "101" })).toBe("10");
    expect(courseInitials({ title: "📚 İşletim / Sistemleri" })).toBe("İS");
  });

  test("adsız derste kodu, ad ve kod yoksa genel ders işaretini kullanır", () => {
    expect(courseInitials({ title: "...", code: "COME 302" })).toBe("C3");
    expect(courseInitials({ title: null, code: "İTA101" })).toBe("İT");
    expect(courseInitials({ title: " ", code: "—" })).toBe("D");
    expect(courseInitials({})).toBe("D");
  });
});

describe("kalıcı ders kapağı tasarımı", () => {
  test("Türkçe harf biçimi, Unicode ve gereksiz boşluk değişimlerinde sabittir", () => {
    const canonical = courseCoverDesign({ title: "İşletim Sistemleri", code: "COME 302" });
    expect(courseCoverDesign({ title: "  işletim   sistemleri  ", code: "come 302" })).toEqual(canonical);
    expect(courseCoverDesign({ title: "I\u0307şletim Sistemleri", code: "COME 302" })).toEqual(canonical);
  });

  test("aynı ders yüzlerce ders arasında sırası değiştiğinde aynı kapağı alır", () => {
    const courses = Array.from({ length: 240 }, (_, index) => ({ title: `Ders ${index}`, code: `COME${index}` }));
    const original = new Map(courses.map((course) => [course.code, courseCoverDesign(course)]));
    for (const course of courses.toReversed()) {
      expect(courseCoverDesign(course)).toEqual(original.get(course.code)!);
    }
  });

  test("aynı baş harfli dersleri kod ve adla ayırt eder", () => {
    const first = courseCoverDesign({ title: "Veri Yapıları", code: "COME 201" });
    const second = courseCoverDesign({ title: "Veri Yapıları", code: "COME 202" });
    const third = courseCoverDesign({ title: "Veri Yönetimi", code: "COME 201" });
    expect(first.initials).toBe(second.initials);
    expect(first.initials).toBe(third.initials);
    expect(first.seed).not.toBe(second.seed);
    expect(first.seed).not.toBe(third.seed);
  });
});
