/**
 * Hata mesajı çözümleme — tek yer.
 *
 * `e instanceof ApiError ? e.message : "..."` yedi ayrı dosyada tekrarlanıyordu
 * ve her birinde farklı bir yedek metin vardı. Kural şudur: backend zaten
 * anlaşılır Türkçe üretir (app/core/errors.py), arayüz kendi hata metnini
 * UYDURMAZ — yalnız backend susarsa nötr bir cümle koyar.
 */

import { ApiError } from "@/lib/api";

export function errorMessage(e: unknown, fallback = "Bağlantı kurulamadı."): string {
  if (e instanceof ApiError) return e.message;
  return fallback;
}
