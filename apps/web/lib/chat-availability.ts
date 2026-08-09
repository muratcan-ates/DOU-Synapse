"use client";

/**
 * Asistanın açık olup olmadığı — tek kaynak.
 *
 * Kararı sunucu verir. Arayüz "öğrencinin sınavı var mı" sorusunu KENDİ
 * hesaplamaz: hesaplasaydı aynı kural iki yerde yaşardı ve ikisi ayrıştığında
 * sapma sessiz olurdu — sekme açık görünüp istek 403 dönerdi (Anayasa XI).
 *
 * Kilit metni de sunucudan gelir; arayüz kendi metnini uydurmaz (Anayasa V,
 * `lib/errors.ts` ile aynı kural).
 *
 * Yoklama yalnız KİLİTLİYKEN koşar (`pollWhile`). Kilit kalkınca kendiliğinden
 * durur — durdurulmayan polling bir kusurdur (Anayasa XI). Aralık 30 saniye:
 * sınav bitişi saniyelik hassasiyet istemez ve kilitli öğrenci zaten sınav
 * sekmesinde çalışıyor.
 */

import { api } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import type { ChatAvailability } from "@/lib/types";

const POLL_INTERVAL_MS = 30_000;

export interface ChatLock {
  /** Sunucu "kapalı" demedikçe açık kabul edilir. */
  locked: boolean;
  /** Kilit sebebi, sunucudan. Kilit yoksa null. */
  message: string | null;
  /** İlk yanıt gelene kadar false — "kilitli değil" ile karıştırılmamalı. */
  ready: boolean;
}

export function useChatAvailability(courseId: string): ChatLock {
  const { data, loading } = useResource<ChatAvailability>(
    () => api.get<ChatAvailability>(`/courses/${courseId}/chat/availability`),
    [courseId],
    { pollWhile: (state) => !state.available, intervalMs: POLL_INTERVAL_MS },
  );

  return toChatLock(data, !loading);
}

/**
 * Saf karar — testin ölçtüğü yer.
 *
 * Yoklama başarısız olursa (`data === null`) sekme KİLİTLENMEZ. Bu bilinçli ve
 * fail-closed kuralının istisnası değil: asıl kapı sunucudadır ve 403 döner.
 * Ağ hatasında kilitlemek, çevrimdışı kalan bir öğrencinin asistanını sınavı
 * olmadığı hâlde kapatırdı — yani yoklamanın arızası ürünün arızasına dönerdi.
 */
export function toChatLock(data: ChatAvailability | null, settled: boolean): ChatLock {
  if (data === null) return { locked: false, message: null, ready: settled };
  return {
    locked: !data.available,
    message: data.available ? null : (data.message ?? null),
    ready: true,
  };
}
