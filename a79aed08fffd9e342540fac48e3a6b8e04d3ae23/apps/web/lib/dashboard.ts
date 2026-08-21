import { api } from "@/lib/api";
import type { CourseRole } from "@/lib/profile";

export interface DashboardViewer {
  id: string;
  email: string;
  full_name: string | null;
  is_platform_admin: boolean;
}

export interface DashboardSummary {
  total_courses: number;
  instructor_courses: number;
  student_courses: number;
  action_items: number;
}

export interface DashboardCourse {
  id: string;
  code: string;
  title: string;
  role: CourseRole;
  documents_total: number;
  documents_processing: number;
  documents_failed: number;
  questions_total: number;
  draft_questions: number;
  published_exams: number;
  mastery_score: number | null;
  last_activity_at: string | null;
  assistant_locked: boolean;
  assistant_lock_reason: string | null;
  assistant_lock_message: string | null;
}

export interface DashboardQuickTool {
  href: string;
  label: string;
}

export interface Dashboard {
  viewer: DashboardViewer;
  summary: DashboardSummary;
  courses: DashboardCourse[];
}

export function getDashboard(): Promise<Dashboard> {
  return api.get<Dashboard>("/dashboard");
}

export function coursePrimaryHref(course: DashboardCourse): string {
  if (course.role === "instructor") return `/courses/${course.id}`;
  return course.assistant_locked
    ? `/courses/${course.id}/exam`
    : `/courses/${course.id}/chat`;
}

export function coursePrimaryLabel(course: DashboardCourse): string {
  if (course.role === "instructor") return "Dersi yönet";
  return course.assistant_locked ? "Sınava dön" : "Çalışmaya devam et";
}

export function courseQuickTools(course: DashboardCourse): DashboardQuickTool[] {
  const base = `/courses/${course.id}`;
  if (course.role === "instructor") {
    return [
      { href: `${base}/sources`, label: "Kaynaklar" },
      { href: `${base}/questions`, label: "Soru havuzu" },
      { href: `${base}/blueprints`, label: "Sınav planı" },
      { href: `${base}/exam`, label: "Sınavlar" },
      { href: `${base}/settings`, label: "AI politikası" },
      { href: `${base}/analytics`, label: "Analitik" },
    ];
  }
  return [
    ...(course.assistant_locked
      ? []
      : [{ href: `${base}/chat`, label: "Asistan" }]),
    { href: `${base}/exam`, label: "Sınavlar" },
    { href: `${base}/analytics`, label: "İlerleme" },
  ];
}

export function instructorAttentionMessages(course: DashboardCourse): string[] {
  if (course.role !== "instructor") return [];
  return [
    ...(course.documents_failed > 0
      ? [`${course.documents_failed} kaynak işlenemedi.`]
      : []),
    ...(course.draft_questions > 0
      ? [`${course.draft_questions} soru öğretmen onayı bekliyor.`]
      : []),
  ];
}

export function masteryLabel(score: number | null): string {
  if (score === null) return "Henüz ölçülmedi";
  const bounded = Math.max(0, Math.min(1, score));
  return `%${Math.round(bounded * 100)}`;
}

export function lastActivityLabel(value: string | null): string {
  if (!value) return "Henüz etkinlik yok";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Tarih alınamadı";
  return new Intl.DateTimeFormat("tr-TR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}
