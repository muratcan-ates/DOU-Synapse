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

export type AdminApiWindowMinutes = 15 | 60 | 1440;
export type AdminApiStatusClass = "2xx" | "3xx" | "4xx" | "5xx";
export type AdminApiMethod =
  "GET" | "POST" | "PUT" | "PATCH" | "DELETE" | "HEAD";
export type AdminApiEnvironment = "local" | "demo" | "production";
export type AdminApiCollectorStatus =
  "disabled" | "healthy" | "degraded" | "stopped";

export interface AdminApiEventQuery {
  window_minutes?: AdminApiWindowMinutes;
  limit?: number;
  offset?: number;
  method?: AdminApiMethod;
  route?: string;
  status_class?: AdminApiStatusClass;
  request_id?: string;
}

export interface AdminApiEventSummary {
  requests_total: number;
  successful_total: number;
  redirect_total: number;
  client_error_total: number;
  server_error_total: number;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
}

export interface AdminApiRouteActivity {
  method: AdminApiMethod;
  route_template: string;
  requests_total: number;
  error_total: number;
  p95_latency_ms: number | null;
  last_seen_at: string;
}

export interface AdminApiEvent {
  request_id: string;
  service: "api";
  environment: AdminApiEnvironment;
  release_revision: string;
  method: AdminApiMethod;
  route_template: string;
  status_code: number;
  outcome_code: string | null;
  duration_ms: number;
  created_at: string;
}

export interface AdminApiCollector {
  scope: "process";
  status: AdminApiCollectorStatus;
  retention_status: "healthy" | "degraded";
  queue_depth: number;
  queue_capacity: number;
  persisted_total: number;
  dropped_total: number;
  failure_total: number;
  last_persisted_at: string | null;
  last_error_at: string | null;
}

export interface AdminApiEventsOut {
  measured_at: string;
  window_minutes: AdminApiWindowMinutes;
  summary: AdminApiEventSummary;
  routes: AdminApiRouteActivity[];
  items: AdminApiEvent[];
  total: number;
  limit: number;
  offset: number;
  collector: AdminApiCollector;
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
  "answered" | "insufficient_context" | "out_of_scope" | "budget_exhausted";

export interface AdminRequestLog {
  log_id: string;
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

/**
 * Operasyon filtreleri URL'ye yazılmaz. Özellikle destek kodu, erişim ve CDN
 * günlüklerinin sorgu satırına düşmemesi için doğrulanan POST gövdesinde kalır.
 */
export function adminApiEventQueryBody(query: AdminApiEventQuery = {}) {
  const method = query.method?.trim().toUpperCase();
  const route = query.route?.trim();
  const requestId = query.request_id?.trim();
  return {
    window_minutes: query.window_minutes ?? 60,
    limit: query.limit ?? 25,
    offset: query.offset ?? 0,
    ...(method ? { method } : {}),
    ...(route ? { route } : {}),
    ...(query.status_class ? { status_class: query.status_class } : {}),
    ...(requestId ? { request_id: requestId } : {}),
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

export function queryAdminApiEvents(
  query?: AdminApiEventQuery,
): Promise<AdminApiEventsOut> {
  return api.post<AdminApiEventsOut>(
    "/admin/api-events/query",
    adminApiEventQueryBody(query),
  );
}

export function getAdminUsers(
  query?: AdminUserQuery,
): Promise<AdminList<AdminUser>> {
  return api.post<AdminList<AdminUser>>(
    "/admin/users",
    adminUserQueryBody(query),
  );
}

export function getAdminCourses(
  query?: PageQuery,
): Promise<AdminList<AdminCourse>> {
  return api.get<AdminList<AdminCourse>>(
    adminListPath("/admin/courses", query),
  );
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

export function adminLatency(value: number | null): string {
  return value === null || !Number.isFinite(value)
    ? "-"
    : `${Math.round(value)} ms`;
}

/** Aynı batch'te aynı destek kodunu taşıyan iki olay da ayrı React satırıdır. */
export function adminApiEventRowKey(
  item: AdminApiEvent,
  index: number,
): string {
  return [
    item.request_id,
    item.created_at,
    item.method,
    item.route_template,
    item.status_code,
    index,
  ].join(":");
}

export function adminWindowLabel(value: AdminApiWindowMinutes): string {
  return value === 15
    ? "Son 15 dakika"
    : value === 60
      ? "Son 1 saat"
      : "Son 24 saat";
}

export function adminCollectorLabel(status: string): string {
  const labels: Record<string, string> = {
    ok: "Sağlıklı",
    ready: "Hazır",
    healthy: "Sağlıklı",
    warming: "Hazırlanıyor",
    disabled: "Kapalı",
    degraded: "Kısıtlı",
    backlogged: "Kuyruk birikiyor",
    stopped: "Durduruldu",
    failed: "Hata",
    unavailable: "Ulaşılamıyor",
  };
  return labels[status.toLowerCase()] ?? status;
}

export function adminCollectorTone(
  status: string,
): "success" | "warning" | "danger" {
  const normalized = status.toLowerCase();
  if (
    normalized === "ok" ||
    normalized === "ready" ||
    normalized === "healthy"
  ) {
    return "success";
  }
  if (
    normalized === "warming" ||
    normalized === "disabled" ||
    normalized === "degraded" ||
    normalized === "backlogged"
  ) {
    return "warning";
  }
  return "danger";
}

/** WAI-ARIA tabs klavye düzeni; desteklenmeyen tuşta odağı değiştirme. */
export function adminTabIndexAfterKey(
  current: number,
  key: string,
  count: number,
): number | null {
  if (count <= 0) return null;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  if (key === "ArrowRight") return (current + 1) % count;
  if (key === "ArrowLeft") return (current - 1 + count) % count;
  return null;
}
