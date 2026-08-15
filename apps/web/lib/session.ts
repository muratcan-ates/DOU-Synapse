"use client";

/**
 * Oturum okuma — tek kaynak.
 *
 * Rol kontrolü altı ayrı yerde `getStoredUser()?.role === "instructor"` diye
 * tekrarlanıyordu. Rol mantığı tek yerde olmazsa, ileride rol eklendiğinde
 * (ör. asistan/gözlemci) hangi ekranın güncellendiği takip edilemez.
 *
 * İddia artık gerçekten tutuyor: `getStoredUser`'ın tek çağıranı bu dosyadır.
 * Bileşenler depoya doğrudan dokunmaz — dokunan bir bileşen, sunucuda var
 * olmayan `localStorage`'ı render sırasında okumaya kalkar ve iki kusur üretir:
 * sunucu ile istemci farklı ağaç çizer (hidrasyon uyuşmazlığı), ayrıca okuma
 * bir kez daha kopyalanmış olur (Anayasa XI).
 *
 * Not: kimlik yalnızca ARAYÜZÜ şekillendirir. Yetki her zaman sunucuda
 * doğrulanır — localStorage'daki rol bir yetki belgesi değildir (Anayasa II).
 */

import { useEffect, useState } from "react";
import { api, getCurrentUser, type DemoUser } from "@/lib/api";
import type { Course } from "@/lib/types";

type CourseRole = "instructor" | "student";

/**
 * Rol cevabı yalnız kısa süreli bir UI optimizasyonudur; yetki belgesi değildir.
 *
 * Üyelik kaldırma/rol değiştirme aynı kullanıcı kimliğiyle gerçekleşebilir.
 * Süresiz bir değer bu değişikliği sekme kapanana kadar saklardı. Otuz saniyelik
 * üst sınır arka arkaya çizilen aynı bileşenleri birleştirir; mount/focus ve açık
 * invalidation yine süreyi beklemeden sunucuya gider.
 */
export const COURSE_ROLE_CACHE_TTL_MS = 30_000;

interface CourseRoleCacheEntry {
  userId: string;
  courseId: string;
  value?: CourseRole;
  expiresAt: number;
  pending?: Promise<CourseRole>;
}

/**
 * Aynı kullanıcı/ders için rol okumalarını birleştiren, süreli önbellek.
 *
 * Sınıf dışa yalnız odaklı birim testinin gerçek üretim davranışını sınayabilmesi
 * için açıktır. İstemci çağrı yerleri aşağıdaki tekil örneği kullanır.
 */
export class CourseRoleCache {
  private readonly entries = new Map<string, CourseRoleCacheEntry>();

  constructor(
    private readonly load: (courseId: string) => Promise<CourseRole>,
    private readonly ttlMs = COURSE_ROLE_CACHE_TTL_MS,
    private readonly now: () => number = Date.now,
  ) {}

  private key(userId: string, courseId: string): string {
    return `${userId}\u0000${courseId}`;
  }

  get(userId: string, courseId: string, refresh = false): Promise<CourseRole> {
    const key = this.key(userId, courseId);
    const existing = this.entries.get(key);

    // Bir focus/mount yenilemesi sürerken ikinci bileşen ayrı ağ isteği açmaz.
    if (existing?.pending) return existing.pending;

    if (!refresh && existing?.value && existing.expiresAt > this.now()) {
      return Promise.resolve(existing.value);
    }

    const pending = this.load(courseId).then(
      (role) => {
        // İstek sürerken açık invalidation geldiyse eski cevap cache'i diriltmez.
        if (this.entries.get(key)?.pending === pending) {
          this.entries.set(key, {
            userId,
            courseId,
            value: role,
            expiresAt: this.now() + Math.max(0, this.ttlMs),
          });
        }
        return role;
      },
      (error: unknown) => {
        // Geçici 403/404/ağ hatası kalıcı bir reddedilmiş Promise'e dönüşmemeli.
        if (this.entries.get(key)?.pending === pending) this.entries.delete(key);
        throw error;
      },
    );

    this.entries.set(key, {
      userId,
      courseId,
      value: existing?.value,
      expiresAt: existing?.expiresAt ?? 0,
      pending,
    });
    return pending;
  }

  invalidate(userId?: string, courseId?: string): void {
    if (userId === undefined && courseId === undefined) {
      this.entries.clear();
      return;
    }
    for (const [key, entry] of this.entries) {
      if (
        (userId === undefined || entry.userId === userId) &&
        (courseId === undefined || entry.courseId === courseId)
      ) {
        this.entries.delete(key);
      }
    }
  }
}

export interface Session {
  user: DemoUser | null;
  isInstructor: boolean;
  /**
   * localStorage yalnız istemcide okunur; ilk render'da henüz bilinmez.
   *
   * `ready === false` "oturum yok" DEĞİL, "henüz bilinmiyor" demektir. İkisini
   * karıştıran çağrı yeri ya girmiş kullanıcıyı dışarı atar ya da rolü bilmeden
   * eğitmen arayüzünü açar; belirsizlikte kapanmak esastır (Anayasa IV).
   */
  ready: boolean;
}

// Ders kimliği tek başına önbellek anahtarı OLAMAZ: aynı tarayıcıda eğitmen çıkıp
// öğrenci girerse eski eğitmen rolü yeni kullanıcıya taşınır. Backend bunu 403 ile
// durdursa da öğrenci yükleme ve yönetim kontrollerini görür. Kimlik anahtarın bir
// parçasıdır; kullanıcı değişiminde rol mutlaka sunucudan yeniden çözülür.
const courseRoles = new CourseRoleCache(async (courseId) => {
  const course = await api.get<Course>(`/courses/${courseId}`);
  if (course.role !== "instructor" && course.role !== "student") {
    throw new Error("Sunucu geçersiz bir ders rolü döndürdü.");
  }
  return course.role;
});

const COURSE_ROLE_INVALIDATED_EVENT = "dou-synapse:course-role-invalidated";

interface CourseRoleInvalidation {
  userId?: string;
  courseId?: string;
}

/**
 * Üyelik yazma akışı aynı sekmede tamamlandığında süreyi beklemeden yeniler.
 * Sunucu yetkisi bundan bağımsızdır; bu yalnız eski kontrolleri UI'dan kaldırır.
 */
export function invalidateCourseRole(userId?: string, courseId?: string): void {
  courseRoles.invalidate(userId, courseId);
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent<CourseRoleInvalidation>(COURSE_ROLE_INVALIDATED_EVENT, {
        detail: { userId, courseId },
      }),
    );
  }
}

function roleForCourse(
  userId: string,
  courseId: string,
  refresh: boolean,
): Promise<CourseRole> {
  return courseRoles.get(userId, courseId, refresh);
}

export function useSession(courseId?: string): Session {
  const [user, setUser] = useState<DemoUser | null>(null);
  const [courseRole, setCourseRole] = useState<CourseRole | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let active = true;
    let generation = 0;
    let resolvedUserId: string | null = null;

    const refresh = async (forceRoleRefresh: boolean, clearWhileLoading = true) => {
      const currentGeneration = ++generation;
      if (clearWhileLoading) {
        // Eski eğitmen rolü yenileme boyunca görünmez; belirsizlik fail-closed'dur.
        setReady(false);
        setCourseRole(null);
      }
      try {
        const current = await getCurrentUser();
        if (!active || currentGeneration !== generation) return;
        resolvedUserId = current?.id ?? null;
        setUser(current);
        if (current && courseId) {
          const role = await roleForCourse(current.id, courseId, forceRoleRefresh);
          if (!active || currentGeneration !== generation) return;
          setCourseRole(role);
        }
      } catch {
        if (!active || currentGeneration !== generation) return;
        // Rol okunamıyorsa eğitmen yüzeyi kapanır; daha önce doğrulanmış genel
        // oturum ise geçici focus hatasında giriş ekranına atılmaz.
        if (resolvedUserId === null) setUser(null);
        setCourseRole(null);
      } finally {
        if (active && currentGeneration === generation) setReady(true);
      }
    };

    const handleInvalidation = (event: Event) => {
      const detail = (event as CustomEvent<CourseRoleInvalidation>).detail;
      if (detail?.courseId && detail.courseId !== courseId) return;
      if (detail?.userId && detail.userId !== resolvedUserId) return;
      void refresh(true);
    };

    const handleFocus = () => void refresh(true, courseId !== undefined);

    void refresh(true);
    // Sekme hiç odağını kaybetmese bile eski rol TTL'den uzun yaşamaz.
    const refreshTimer = courseId
      ? window.setInterval(() => void refresh(false), COURSE_ROLE_CACHE_TTL_MS)
      : null;
    window.addEventListener("focus", handleFocus);
    window.addEventListener(COURSE_ROLE_INVALIDATED_EVENT, handleInvalidation);
    return () => {
      active = false;
      generation += 1;
      if (refreshTimer !== null) window.clearInterval(refreshTimer);
      window.removeEventListener("focus", handleFocus);
      window.removeEventListener(COURSE_ROLE_INVALIDATED_EVENT, handleInvalidation);
    };
  }, [courseId]);

  return {
    user,
    isInstructor: (courseId ? courseRole : user?.role) === "instructor",
    ready,
  };
}
