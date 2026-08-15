import { describe, expect, test } from "bun:test";
import { CourseRoleCache } from "./session";

type Role = "instructor" | "student";

describe("ders rolü önbelleği", () => {
  test("aynı kullanıcı ve derste rol değişimi zorunlu yenilemede görünür", async () => {
    const roles: Role[] = ["instructor", "student"];
    let calls = 0;
    const cache = new CourseRoleCache(async () => {
      const role = roles[calls];
      calls += 1;
      if (!role) throw new Error("beklenmeyen çağrı");
      return role;
    });

    expect(await cache.get("user-1", "course-1", true)).toBe("instructor");
    expect(await cache.get("user-1", "course-1")).toBe("instructor");
    expect(calls).toBe(1);
    expect(await cache.get("user-1", "course-1", true)).toBe("student");
    expect(calls).toBe(2);
  });

  test("TTL dolunca rol kendiliğinden yeniden okunur", async () => {
    let now = 1_000;
    const roles: Role[] = ["instructor", "student"];
    let calls = 0;
    const cache = new CourseRoleCache(
      async () => {
        const role = roles[calls];
        calls += 1;
        if (!role) throw new Error("beklenmeyen çağrı");
        return role;
      },
      30_000,
      () => now,
    );

    expect(await cache.get("user-1", "course-1")).toBe("instructor");
    now += 29_999;
    expect(await cache.get("user-1", "course-1")).toBe("instructor");
    expect(calls).toBe(1);
    now += 1;
    expect(await cache.get("user-1", "course-1")).toBe("student");
    expect(calls).toBe(2);
  });

  test("reddedilen rol isteği cache'ten atılır ve sonraki deneme iyileşebilir", async () => {
    let calls = 0;
    const cache = new CourseRoleCache(async () => {
      calls += 1;
      if (calls === 1) throw new Error("geçici ağ hatası");
      return "student";
    });

    await expect(cache.get("user-1", "course-1", true)).rejects.toThrow(
      "geçici ağ hatası",
    );
    expect(await cache.get("user-1", "course-1")).toBe("student");
    expect(calls).toBe(2);
  });

  test("eşzamanlı mount/focus okumaları tek sunucu isteğinde birleşir", async () => {
    let resolveRole: ((role: Role) => void) | undefined;
    let calls = 0;
    const cache = new CourseRoleCache(
      () => {
        calls += 1;
        return new Promise<Role>((resolve) => {
          resolveRole = resolve;
        });
      },
      30_000,
    );

    const first = cache.get("user-1", "course-1", true);
    const second = cache.get("user-1", "course-1", true);
    expect(second).toBe(first);
    expect(calls).toBe(1);
    resolveRole?.("instructor");
    expect(await first).toBe("instructor");
    expect(await second).toBe("instructor");
  });

  test("açık invalidation aynı kullanıcı/ders değerini kaldırır", async () => {
    let calls = 0;
    const cache = new CourseRoleCache(async () => {
      calls += 1;
      return calls === 1 ? "instructor" : "student";
    });

    expect(await cache.get("user-1", "course-1")).toBe("instructor");
    cache.invalidate("user-1", "course-1");
    expect(await cache.get("user-1", "course-1")).toBe("student");
    expect(calls).toBe(2);
  });

  test("invalidation sürmekte olan eski cevabın cache'i diriltmesini engeller", async () => {
    let resolveRole: ((role: Role) => void) | undefined;
    let calls = 0;
    const cache = new CourseRoleCache(() => {
      calls += 1;
      if (calls === 1) {
        return new Promise<Role>((resolve) => {
          resolveRole = resolve;
        });
      }
      return Promise.resolve("student");
    });

    const stale = cache.get("user-1", "course-1", true);
    cache.invalidate("user-1", "course-1");
    resolveRole?.("instructor");
    expect(await stale).toBe("instructor");
    expect(await cache.get("user-1", "course-1")).toBe("student");
    expect(calls).toBe(2);
  });
});
