import { describe, expect, test } from "bun:test";
import {
  adminApiEventQueryBody,
  adminApiEventRowKey,
  adminCollectorLabel,
  adminCollectorTone,
  adminDate,
  adminLatency,
  adminListPath,
  adminTabIndexAfterKey,
  adminUserQueryBody,
  adminWindowLabel,
} from "./admin";
import type {
  AdminApiEventsOut,
  AdminOverview,
  AdminRequestLog,
} from "./admin";

const overviewFixture = {
  status: "ok",
  database_status: "ok",
  embedding_status: "ready",
  measured_at: "2026-08-10T12:00:00Z",
  users_total: 12,
  courses_total: 4,
  documents_total: 18,
  ingestion_processing: 1,
  ingestion_failed: 0,
  active_memberships_total: 27,
  chat_turns_24h: 86,
  p95_latency_ms: 240,
  tokens_24h: 12_000,
} satisfies AdminOverview;

const requestFixture = {
  log_id: "log-1",
  course_code: "COME331",
  route: "/courses/:id/chat",
  mode: "socratic",
  status: "answered",
  http_status: 200,
  latency_ms: 320,
  token_count: null,
  cache_hit: false,
  created_at: "2026-08-10T12:00:00Z",
} satisfies AdminRequestLog;

const apiEventsFixture = {
  measured_at: "2026-08-20T00:15:00Z",
  window_minutes: 60,
  summary: {
    requests_total: 10,
    successful_total: 7,
    redirect_total: 1,
    client_error_total: 1,
    server_error_total: 1,
    p50_latency_ms: 42,
    p95_latency_ms: 380,
  },
  routes: [
    {
      method: "GET",
      route_template: "/courses/{course_id}",
      requests_total: 4,
      error_total: 1,
      p95_latency_ms: 120,
      last_seen_at: "2026-08-20T00:14:00Z",
    },
  ],
  items: [
    {
      request_id: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      service: "api",
      environment: "demo",
      release_revision: "db2f42a",
      method: "GET",
      route_template: "/courses/{course_id}",
      status_code: 404,
      outcome_code: "not_found",
      duration_ms: 81,
      created_at: "2026-08-20T00:14:00Z",
    },
  ],
  total: 1,
  limit: 25,
  offset: 0,
  collector: {
    scope: "process",
    status: "healthy",
    retention_status: "healthy",
    queue_depth: 0,
    queue_capacity: 1000,
    persisted_total: 10,
    dropped_total: 0,
    failure_total: 0,
    last_persisted_at: "2026-08-20T00:14:01Z",
    last_error_at: null,
  },
} satisfies AdminApiEventsOut;

describe("admin sorguları", () => {
  test("sayfalama ve durum filtresi tek biçimde kurulur", () => {
    expect(
      adminListPath("/admin/requests", {
        limit: 50,
        offset: 100,
        status: "out_of_scope",
        route: "/courses/:id/chat",
      }),
    ).toBe(
      "/admin/requests?limit=50&offset=100&status=out_of_scope&route=%2Fcourses%2F%3Aid%2Fchat",
    );
  });

  test("kullanıcı aramasını URL yerine istek gövdesine taşır", () => {
    expect(adminUserQueryBody({ search: "Ayşe Hoca" })).toEqual({
      limit: 25,
      offset: 0,
      search: "Ayşe Hoca",
    });
  });

  test("kullanıcı sorgusu varsayılan güvenli sayfa boyutu kullanır", () => {
    expect(adminUserQueryBody()).toEqual({ limit: 25, offset: 0 });
  });

  test("API filtresi destek kodunu URL yerine doğrulanan POST gövdesine koyar", () => {
    expect(
      adminApiEventQueryBody({
        window_minutes: 15,
        limit: 50,
        offset: 25,
        method: "POST",
        route: " /courses/{course_id}/chat ",
        status_class: "5xx",
        request_id: " aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa ",
      }),
    ).toEqual({
      window_minutes: 15,
      limit: 50,
      offset: 25,
      method: "POST",
      route: "/courses/{course_id}/chat",
      status_class: "5xx",
      request_id: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    });
  });

  test("API sorgusu boş filtreleri gövdeye eklemez", () => {
    expect(adminApiEventQueryBody()).toEqual({
      window_minutes: 60,
      limit: 25,
      offset: 0,
    });
  });
});

describe("admin gösterim yardımcıları", () => {
  test("özet yalnız anonim kullanım ve üyelik ölçümleri taşır", () => {
    expect(overviewFixture.active_memberships_total).toBe(27);
    expect(overviewFixture.chat_turns_24h).toBe(86);
  });

  test("istek günlüğü kullanıcı eşleştirme alanı taşımaz", () => {
    expect("user_ref" in requestFixture).toBe(false);
  });

  test("API gözlem snapshot'ı ham kimlik, adres veya içerik taşımaz", () => {
    const serialized = JSON.stringify(apiEventsFixture);
    for (const forbidden of [
      '"user_id":',
      '"course_id":',
      '"document_id":',
      '"query_string":',
      '"request_body":',
      '"response_body":',
      '"stack_trace":',
      '"ip_address":',
    ]) {
      expect(serialized).not.toContain(forbidden);
    }
    expect(apiEventsFixture.items[0]?.route_template).toBe(
      "/courses/{course_id}",
    );
  });

  test("aynı batch ve destek kodundaki olaylar ayrı satır anahtarı alır", () => {
    const event = apiEventsFixture.items[0]!;
    expect(adminApiEventRowKey(event, 0)).not.toBe(
      adminApiEventRowKey(event, 1),
    );
  });

  test("bozuk tarihte teknik metin sızdırmaz", () => {
    expect(adminDate(null)).toBe("-");
    expect(adminDate("bozuk")).toBe("-");
  });

  test("gecikme, zaman aralığı ve toplayıcı durumları ortak sözlükten gelir", () => {
    expect(adminLatency(42.7)).toBe("43 ms");
    expect(adminLatency(null)).toBe("-");
    expect(adminWindowLabel(15)).toBe("Son 15 dakika");
    expect(adminWindowLabel(60)).toBe("Son 1 saat");
    expect(adminWindowLabel(1440)).toBe("Son 24 saat");
    expect(adminCollectorLabel("backlogged")).toBe("Kuyruk birikiyor");
    expect(adminCollectorLabel("disabled")).toBe("Kapalı");
    expect(adminCollectorLabel("stopped")).toBe("Durduruldu");
    expect(adminCollectorTone("healthy")).toBe("success");
    expect(adminCollectorTone("disabled")).toBe("warning");
    expect(adminCollectorTone("degraded")).toBe("warning");
    expect(adminCollectorTone("stopped")).toBe("danger");
    expect(adminCollectorTone("failed")).toBe("danger");
  });

  test("teknik kayıt sekmeleri ok tuşlarıyla döngüsel gezilir", () => {
    expect(adminTabIndexAfterKey(0, "ArrowRight", 5)).toBe(1);
    expect(adminTabIndexAfterKey(4, "ArrowRight", 5)).toBe(0);
    expect(adminTabIndexAfterKey(0, "ArrowLeft", 5)).toBe(4);
    expect(adminTabIndexAfterKey(2, "Home", 5)).toBe(0);
    expect(adminTabIndexAfterKey(1, "End", 5)).toBe(4);
    expect(adminTabIndexAfterKey(1, "Enter", 5)).toBeNull();
  });
});
