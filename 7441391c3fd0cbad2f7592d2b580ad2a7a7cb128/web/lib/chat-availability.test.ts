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
      },
      true,
    );

    expect(lock.locked).toBe(true);
    expect(lock.message).toBe("Şu anda süren bir sınav oturumun var.");
    expect(lock.ready).toBe(true);
  });

  test("sunucu açık derse kilit yok ve mesaj taşınmaz", () => {
    const lock = toChatLock({ available: true, reason: null, message: null }, true);

    expect(lock.locked).toBe(false);
    expect(lock.message).toBeNull();
  });

  test("açıkken gelen bir mesaj yine de gösterilmez", () => {
    // Sunucu tutarsız cevap verirse (available=true + message dolu) arayüz
    // kilit metnini sızdırmamalı: gösterilen her metnin bir durumu olmalı.
    const lock = toChatLock({ available: true, reason: null, message: "artık" }, true);

    expect(lock.message).toBeNull();
  });

  test("yoklama daha dönmediyse sekme kilitlenmez", () => {
    // İlk render'da kilitlemek, sınavı olmayan her öğrencinin sekmesini bir an
    // için kapatırdı — sekme açılıp kapanan bir arayüz kusurdur.
    const lock = toChatLock(null, false);

    expect(lock.locked).toBe(false);
    expect(lock.ready).toBe(false);
  });

  test("yoklama başarısız olduysa sekme kilitlenmez", () => {
    // Bilinçli: asıl kapı sunucuda ve 403 döndürüyor. Ağ hatasında kilitlemek,
    // yoklamanın arızasını ürünün arızasına çevirirdi.
    const lock = toChatLock(null, true);

    expect(lock.locked).toBe(false);
    expect(lock.ready).toBe(true);
  });
});
