import { describe, expect, test } from "bun:test";
import {
  isAvailabilitySnapshotCurrent,
  toChatLock,
} from "@/lib/chat-availability";

/**
 * Kilit kararının saf hâli. Kancanın kendisi `useResource`'a ve ağa bağlı;
 * ölçülmesi gereken karar ise saf ve burada.
 */
describe("toChatLock", () => {
  test("sunucu kapalı derse sekme kilitlenir ve mesaj sunucudan gelir", () => {
    const lock = toChatLock(
      {
        available: false,
        reason: "exam_in_progress",
        message: "Şu anda süren bir sınav oturumun var.",
        allowed_modes: ["qa", "socratic"],
        hint_limit: 4,
        audience: "student",
        agent_profile: "student_coach",
      },
      true,
    );

    expect(lock.locked).toBe(true);
    expect(lock.message).toBe("Şu anda süren bir sınav oturumun var.");
    expect(lock.ready).toBe(true);
    expect(lock.audience).toBe("student");
    expect(lock.agentProfile).toBe("student_coach");
    expect(lock.allowedModes).toEqual(["qa", "socratic"]);
    expect(lock.hintLimit).toBe(4);
  });

  test("sunucu açık derse kilit yok ve mesaj taşınmaz", () => {
    const lock = toChatLock(
      {
        available: true,
        reason: null,
        message: null,
        allowed_modes: ["qa", "socratic"],
        hint_limit: 4,
        audience: "instructor",
        agent_profile: "instructor_assistant",
      },
      true,
    );

    expect(lock.locked).toBe(false);
    expect(lock.message).toBeNull();
    expect(lock.audience).toBe("instructor");
    expect(lock.agentProfile).toBe("instructor_assistant");
  });

  test("açıkken gelen bir mesaj yine de gösterilmez", () => {
    // Sunucu tutarsız cevap verirse (available=true + message dolu) arayüz
    // kilit metnini sızdırmamalı: gösterilen her metnin bir durumu olmalı.
    const lock = toChatLock(
      {
        available: true,
        reason: null,
        message: "artık",
        allowed_modes: ["qa", "socratic"],
        hint_limit: 4,
        audience: "student",
        agent_profile: "student_coach",
      },
      true,
    );

    expect(lock.message).toBeNull();
  });

  test("sınav modu sohbet bestecisine taşınmaz, sunucu sırası korunur", () => {
    const lock = toChatLock(
      {
        available: true,
        reason: null,
        message: null,
        allowed_modes: ["socratic", "exam", "qa", "socratic"],
        hint_limit: 2,
        audience: "student",
        agent_profile: "student_coach",
      },
      true,
    );

    expect(lock.allowedModes).toEqual(["socratic", "qa"]);
    expect(lock.hintLimit).toBe(2);
  });

  test("yoklama daha dönmediyse sekme kilitlenmez", () => {
    // İlk render'da kilitlemek, sınavı olmayan her öğrencinin sekmesini bir an
    // için kapatırdı — sekme açılıp kapanan bir arayüz kusurdur.
    const lock = toChatLock(null, false);

    expect(lock.locked).toBe(false);
    expect(lock.ready).toBe(false);
    expect(lock.audience).toBeNull();
    expect(lock.agentProfile).toBeNull();
    expect(lock.allowedModes).toEqual([]);
  });

  test("yoklama başarısız olduysa sekme kilitlenmez", () => {
    // Asıl kapı sunucuda ve 403 döndürüyor. Ağ hatasında rol tahmini yapılmaz;
    // hata ve çalışan çıkış yolu arayüze aynen taşınır.
    const reload = async () => {};
    const lock = toChatLock(null, true, {
      error: "Sunucuya ulaşılamadı.",
      errorKind: "transient",
      errorRequestId: "req-availability-1",
      reload,
    });

    expect(lock.locked).toBe(false);
    expect(lock.ready).toBe(true);
    expect(lock.audience).toBeNull();
    expect(lock.agentProfile).toBeNull();
    expect(lock.error).toBe("Sunucuya ulaşılamadı.");
    expect(lock.errorKind).toBe("transient");
    expect(lock.errorRequestId).toBe("req-availability-1");
    expect(lock.reload).toBe(reload);
  });

  test("başarılı eski karar tazeleme hatasında korunur ve uyarı ayrı taşınır", () => {
    const reload = async () => {};
    const lock = toChatLock(
      {
        available: true,
        reason: null,
        message: null,
        allowed_modes: ["qa", "socratic"],
        hint_limit: 4,
        audience: "instructor",
        agent_profile: "instructor_assistant",
      },
      true,
      {
        refreshError: "Durum yenilenemedi.",
        errorKind: "transient",
        errorRequestId: "req-availability-2",
        reload,
      },
    );

    expect(lock.ready).toBe(true);
    expect(lock.locked).toBe(false);
    expect(lock.audience).toBe("instructor");
    expect(lock.agentProfile).toBe("instructor_assistant");
    expect(lock.error).toBeNull();
    expect(lock.refreshError).toBe("Durum yenilenemedi.");
    expect(lock.errorRequestId).toBe("req-availability-2");
    expect(lock.reload).toBe(reload);
  });
});

describe("availability snapshot sınırı", () => {
  test("aynı ders ve sınav epoch'u güncel cevabı kabul eder", () => {
    expect(isAvailabilitySnapshotCurrent("course-1", "course-1", 3, 3)).toBe(true);
  });

  test("sınav olayı sonrası eski açık karar effect beklemeden reddedilir", () => {
    expect(isAvailabilitySnapshotCurrent("course-1", "course-1", 3, 4)).toBe(false);
    expect(isAvailabilitySnapshotCurrent("course-1", "course-2", 4, 4)).toBe(false);
  });
});
