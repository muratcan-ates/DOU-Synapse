import { describe, expect, test } from "bun:test";
import {
  allowedChatUiModes,
  answerMatchesAssistant,
  firstAllowedChatMode,
  resolveCourseAssistantIdentity,
  sessionMatchesAssistant,
} from "./course-assistant";

describe("ders asistanı kimliği — rol yalnız sunucu zarfından", () => {
  test("öğrenci zarfı Ders Koçu'na çözülür", () => {
    const identity = resolveCourseAssistantIdentity("student", "student_coach");
    expect(identity?.name).toBe("Ders Koçu");
    expect(identity?.eyebrow).toBe("Öğrenci çalışma alanı");
    expect(identity?.suggestions).toHaveLength(3);
    expect(identity?.suggestions.every((item) => item.prompt.length > 3)).toBe(true);
  });

  test("eğitmen zarfı Eğitmen Asistanı'na çözülür", () => {
    const identity = resolveCourseAssistantIdentity(
      "instructor",
      "instructor_assistant",
    );
    expect(identity?.name).toBe("Eğitmen Asistanı");
    expect(identity?.eyebrow).toBe("Eğitmen çalışma alanı");
    expect(identity?.suggestions.map((item) => item.label)).toEqual([
      "Zor kavramları çıkar",
      "Sokratik yönlendirme tasarla",
      "Kaynak boşluklarını gör",
    ]);
    expect(identity?.suggestions[1]?.preferredMode).toBe("qa");
  });

  test("eksik veya birbiriyle çelişen zarf rol tahmini üretmez", () => {
    expect(resolveCourseAssistantIdentity(null, null)).toBeNull();
    expect(
      resolveCourseAssistantIdentity("student", "instructor_assistant"),
    ).toBeNull();
    expect(
      resolveCourseAssistantIdentity("instructor", "student_coach"),
    ).toBeNull();
  });

  test("öneriler yazma aracı veya otomatik eylem vaat etmez", () => {
    for (const pair of [
      ["student", "student_coach"],
      ["instructor", "instructor_assistant"],
    ] as const) {
      const identity = resolveCourseAssistantIdentity(pair[0], pair[1]);
      const copy = identity?.suggestions
        .flatMap((item) => [item.label, item.prompt])
        .join(" ")
        .toLocaleLowerCase("tr-TR");
      expect(copy).not.toContain("yayınla");
      expect(copy).not.toContain("sil");
      expect(copy).not.toContain("onayla");
    }
  });
});

describe("availability politikası", () => {
  test("yalnız sohbet modlarını, sunucunun sırasıyla ve tekilleştirerek taşır", () => {
    expect(allowedChatUiModes(["socratic", "exam", "qa", "socratic"])).toEqual([
      "socratic",
      "qa",
    ]);
  });

  test("sunucu mod açmadıysa varsayılan mod uydurulmaz", () => {
    expect(firstAllowedChatMode([])).toBeNull();
    expect(firstAllowedChatMode(["socratic", "qa"])).toBe("socratic");
  });
});

describe("canlı yanıt rol zarfı", () => {
  const student = resolveCourseAssistantIdentity("student", "student_coach");
  if (!student) throw new Error("öğrenci kimliği bekleniyordu");

  test("availability ile aynı zarf kabul edilir", () => {
    expect(
      answerMatchesAssistant(
        { audience: "student", agent_profile: "student_coach" },
        student,
      ),
    ).toBe(true);
  });

  test("cevap ortasında persona değişikliğinde kapanır", () => {
    expect(
      answerMatchesAssistant(
        { audience: "instructor", agent_profile: "instructor_assistant" },
        student,
      ),
    ).toBe(false);
  });

  test("geçmiş oturum mevcut persona ile eşleşmiyorsa açılmaz", () => {
    expect(
      sessionMatchesAssistant(
        { audience: "student", agent_profile: "student_coach" },
        student,
      ),
    ).toBe(true);
    expect(
      sessionMatchesAssistant(
        { audience: "instructor", agent_profile: "instructor_assistant" },
        student,
      ),
    ).toBe(false);
  });
});

describe("çekmece yetki sınırı — kaynak değişmezleri", () => {
  test("rol tahmini ve otonom yazma aracı içermez", async () => {
    const source = await Bun.file(
      new URL("../components/course-assistant/course-assistant.tsx", import.meta.url),
    ).text();

    expect(source).not.toContain("course.role");
    expect(source).not.toContain('name="role"');
    expect(source).not.toContain("api.put");
    expect(source).not.toContain("api.patch");
    expect(source).not.toContain("api.delete");
    expect(source.match(/api\.post/g)).toHaveLength(1);
    expect(source).toContain("`/courses/${courseId}/chat`");
    expect(source).toContain("disabled={sending}");
  });
});
