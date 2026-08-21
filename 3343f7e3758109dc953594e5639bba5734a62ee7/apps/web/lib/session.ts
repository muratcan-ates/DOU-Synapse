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
const courseRoles = new Map<string, Promise<"instructor" | "student">>();

function roleForCourse(userId: string, courseId: string): Promise<"instructor" | "student"> {
  const key = `${userId}:${courseId}`;
  const existing = courseRoles.get(key);
  if (existing) return existing;
  const pending = api.get<Course>(`/courses/${courseId}`).then((course) => course.role);
  courseRoles.set(key, pending);
  pending.catch(() => courseRoles.delete(key));
  return pending;
}

export function useSession(courseId?: string): Session {
  const [user, setUser] = useState<DemoUser | null>(null);
  const [courseRole, setCourseRole] = useState<"instructor" | "student" | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let active = true;
    setReady(false);
    void (async () => {
      const current = await getCurrentUser();
      if (!active) return;
      setUser(current);
      if (current && courseId) {
        try {
          const role = await roleForCourse(current.id, courseId);
          if (active) setCourseRole(role);
        } catch {
          if (active) setCourseRole(null);
        }
      } else {
        setCourseRole(null);
      }
      if (active) setReady(true);
    })();
    return () => {
      active = false;
    };
  }, [courseId]);

  return {
    user,
    isInstructor: (courseId ? courseRole : user?.role) === "instructor",
    ready,
  };
}
