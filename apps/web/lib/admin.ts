import { api } from "@/lib/api";

export interface AdminOverview {
  status: string;
  database_status: string;
  embedding_status: string;
  measured_at: string;
  users_total: number;
  courses_total: number;
  documents_total: number;
  ingestion_processing: number;
  ingestion_failed: number;
  active_memberships_total: number;
  chat_turns_24h: number;
  p95_latency_ms: number | null;
  tokens_24h: number;
}

export interface AdminList<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface AdminUser {
  id: string;
  masked_email: string;
  full_name: string | null;
  created_at: string;
  is_platform_admin: boolean;
  active_course_count: number;
}

export interface AdminCourse {
  id: string;
  code: string;
  title: string;
  created_at: string;
  creator_name: string;
  active_member_count: number;
  documents_total: number;
  documents_failed: number;
}

export type RequestStatus =
  | "answered"
  | "insufficient_context"
  | "out_of_scope"
  | "budget_exhausted";

export interface AdminRequestLog {
  log_id: string;
  course_id: string;
  course_code: string;
  route: string;
  mode: string;
  status: RequestStatus | null;
  http_status: number;
  latency_ms: number;
  token_count: number | null;
  cache_hit: boolean;
  created_at: string;
}

export type IngestionStatus = "pending" | "processing" | "completed" | "failed";

export interface AdminIngestionJob {
  id: string;
  document_id: string;
  course_id: string;
  course_code: string;
  status: IngestionStatus;
  attempt_count: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

interface PageQuery {
  limit?: number;
  offset?: number;
  status?: string;
  search?: string;
  route?: string;
}

export interface AdminUserQuery {
  limit?: number;
  offset?: number;
  search?: string;
}

export function adminUserQueryBody(query: AdminUserQuery = {}) {
  return {
    limit: query.limit ?? 25,
    offset: query.offset ?? 0,
    ...(query.search ? { search: query.search } : {}),
  };
}

export function adminListPath(path: string, query: PageQuery = {}): string {
  const params = new URLSearchParams();
  params.set("limit", String(query.limit ?? 25));
  params.set("offset", String(query.offset ?? 0));
  if (query.status) params.set("status", query.status);
  if (query.search) params.set("search", query.search);
  if (query.route) params.set("route", query.route);
  return `${path}?${params.toString()}`;
}

export function getAdminOverview(): Promise<AdminOverview> {
  return api.get<AdminOverview>("/admin/overview");
}

export function getAdminUsers(query?: AdminUserQuery): Promise<AdminList<AdminUser>> {
  return api.post<AdminList<AdminUser>>("/admin/users", adminUserQueryBody(query));
}

export function getAdminCourses(query?: PageQuery): Promise<AdminList<AdminCourse>> {
  return api.get<AdminList<AdminCourse>>(adminListPath("/admin/courses", query));
}

export function getAdminRequestLogs(
  query?: PageQuery,
): Promise<AdminList<AdminRequestLog>> {
  return api.get<AdminList<AdminRequestLog>>(
    adminListPath("/admin/requests", query),
  );
}

export function getAdminIngestionJobs(
  query?: PageQuery,
): Promise<AdminList<AdminIngestionJob>> {
  return api.get<AdminList<AdminIngestionJob>>(
    adminListPath("/admin/ingestion", query),
  );
}

export function adminDate(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("tr-TR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}
