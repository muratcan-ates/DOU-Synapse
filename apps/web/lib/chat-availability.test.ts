import { describe, expect, test } from "bun:test";
import { toChatLock } from "@/lib/chat-availability";

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
    // Bilinçli: asıl kapı sunucuda ve 403 döndürüyor. Ağ hatasında kilitlemek,
    // yoklamanın arızasını ürünün arızasına çevirirdi.
    const lock = toChatLock(null, true);

    expect(lock.locked).toBe(false);
    expect(lock.ready).toBe(true);
    expect(lock.audience).toBeNull();
    expect(lock.agentProfile).toBeNull();
  });
});
