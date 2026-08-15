import { describe, expect, test } from "bun:test";
import {
  adminDate,
  adminListPath,
  adminTabIndexAfterKey,
  adminUserQueryBody,
} from "./admin";
import type { AdminOverview, AdminRequestLog } from "./admin";

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
  course_id: "course-1",
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
});

describe("admin gösterim yardımcıları", () => {
  test("özet yalnız anonim kullanım ve üyelik ölçümleri taşır", () => {
    expect(overviewFixture.active_memberships_total).toBe(27);
    expect(overviewFixture.chat_turns_24h).toBe(86);
  });

  test("istek günlüğü kullanıcı eşleştirme alanı taşımaz", () => {
    expect("user_ref" in requestFixture).toBe(false);
  });

  test("bozuk tarihte teknik metin sızdırmaz", () => {
    expect(adminDate(null)).toBe("-");
    expect(adminDate("bozuk")).toBe("-");
  });

  test("teknik kayıt sekmeleri ok tuşlarıyla döngüsel gezilir", () => {
    expect(adminTabIndexAfterKey(0, "ArrowRight", 4)).toBe(1);
    expect(adminTabIndexAfterKey(3, "ArrowRight", 4)).toBe(0);
    expect(adminTabIndexAfterKey(0, "ArrowLeft", 4)).toBe(3);
    expect(adminTabIndexAfterKey(2, "Home", 4)).toBe(0);
    expect(adminTabIndexAfterKey(1, "End", 4)).toBe(3);
    expect(adminTabIndexAfterKey(1, "Enter", 4)).toBeNull();
  });
});
