import { describe, expect, test } from "bun:test";
import {
  coursePrimaryHref,
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
};

describe("rol bazlı ders kartı", () => {
  test("öğrenciyi çalışmaya, eğitmeni ders yönetimine götürür", () => {
    expect(coursePrimaryHref(course)).toBe("/courses/course-1/chat");
    expect(coursePrimaryHref({ ...course, role: "instructor" })).toBe(
      "/courses/course-1",
    );
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
