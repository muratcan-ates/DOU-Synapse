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
  return course.role === "instructor"
    ? `/courses/${course.id}`
    : `/courses/${course.id}/chat`;
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
