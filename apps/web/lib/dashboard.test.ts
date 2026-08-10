import { describe, expect, test } from "bun:test";
import {
  coursePrimaryHref,
  coursePrimaryLabel,
  courseQuickTools,
  instructorAttentionMessages,
  lastActivityLabel,
  masteryLabel,
  type DashboardCourse,
} from "./dashboard";

const course: DashboardCourse = {
  id: "course-1",
  code: "COME331",
  title: "İşletim Sistemleri",
  role: "student",
  documents_total: 2,
  documents_processing: 0,
  documents_failed: 0,
  questions_total: 12,
  draft_questions: 0,
  published_exams: 1,
  mastery_score: 0.624,
  last_activity_at: null,
  assistant_locked: false,
  assistant_lock_reason: null,
  assistant_lock_message: null,
};

describe("rol bazlı ders kartı", () => {
  test("öğrenciyi çalışmaya, eğitmeni ders yönetimine götürür", () => {
    expect(coursePrimaryHref(course)).toBe("/courses/course-1/chat");
    expect(coursePrimaryHref({ ...course, role: "instructor" })).toBe(
      "/courses/course-1",
    );
  });

  test("sınav kilidinde asistanı kaldırır ve ana eylemi sınava taşır", () => {
    const locked = {
      ...course,
      assistant_locked: true,
      assistant_lock_reason: "exam_in_progress",
      assistant_lock_message: "Sunucudan gelen kilit açıklaması.",
    };

    expect(coursePrimaryHref(locked)).toBe("/courses/course-1/exam");
    expect(coursePrimaryLabel(locked)).toBe("Sınava dön");
    expect(courseQuickTools(locked)).toEqual([
      { href: "/courses/course-1/exam", label: "Sınavlar" },
      { href: "/courses/course-1/analytics", label: "İlerleme" },
    ]);
  });

  test("eğitmenin çalışan altı aracını eksiksiz sunar", () => {
    expect(courseQuickTools({ ...course, role: "instructor" })).toEqual([
      { href: "/courses/course-1/sources", label: "Kaynaklar" },
      { href: "/courses/course-1/questions", label: "Soru havuzu" },
      { href: "/courses/course-1/blueprints", label: "Sınav planı" },
      { href: "/courses/course-1/exam", label: "Sınavlar" },
      { href: "/courses/course-1/settings", label: "AI politikası" },
      { href: "/courses/course-1/analytics", label: "Analitik" },
    ]);
  });

  test("başarısız kaynak ve taslak soru uyarılarını ayrı ayrı korur", () => {
    expect(
      instructorAttentionMessages({
        ...course,
        role: "instructor",
        documents_failed: 2,
        draft_questions: 3,
      }),
    ).toEqual([
      "2 kaynak işlenemedi.",
      "3 soru öğretmen onayı bekliyor.",
    ]);
  });

  test("ustalık skoru güvenli yüzdeye çevrilir", () => {
    expect(masteryLabel(course.mastery_score)).toBe("%62");
    expect(masteryLabel(null)).toBe("Henüz ölçülmedi");
    expect(masteryLabel(4)).toBe("%100");
  });

  test("eksik veya bozuk etkinlik tarihi dürüstçe gösterilir", () => {
    expect(lastActivityLabel(null)).toBe("Henüz etkinlik yok");
    expect(lastActivityLabel("bozuk")).toBe("Tarih alınamadı");
  });
});
