"use client";

/**
 * Gönderim kancası — busy / hata / çift-gönderim kapısı tek yerde.
 *
 * Her yazma eylemi aynı beş satırı tekrarlıyordu: `setBusy(true)`,
 * `setError(null)`, `try { … } catch { errorMessage } finally { setBusy(false) }`
 * — ölçülen ~23 kopya. Tekrarın maliyeti satır sayısı değil, sessiz ayrışma:
 * çift-gönderim kapısı kimi kopyada vardı (members) kimisinde yoktu; kapısız
 * bir form Enter'a iki kez basan kullanıcı adına aynı isteği iki kez atardı.
 * Tek kanca olunca kapı her çağrı yerinde aynı: **busy iken gönderim yok
 * sayılır** ve kapı state değil senkron bayrak okur — aynı tick içindeki
 * ikinci tıklama, state güncellemesi daha flush edilmeden gelir ve state
 * kapısını geçerdi.
 *
 * Kancanın karar çekirdeği (`createSubmitGate`) saf tutulur ki DOM'suz koşan
 * `use-submit.test.ts` sırayı ve kapıyı doğrudan sınayabilsin — aynı gerekçe
 * `use-resource.ts`'in çekirdeklerinde yazılı.
 *
 * Hata metni tek kaynaktan gelir (`errorMessage`: backend'in cümlesi, backend
 * sustuysa yedek). Hata durumu kancanın dışında yaşamak zorundaysa —
 * yükleme hatasıyla aynı satırı paylaşan kayıt hatası (settings) ya da düz
 * metin olmayan hata şekli (courses'un `Rejection`'ı) — `onError` verilir;
 * o zaman kanca kendi `error`'ını doldurmaz, ham hatayı çağrı yerine iletir.
 */

import { useCallback, useRef, useState } from "react";
import { errorMessage } from "@/lib/errors";

/* -------------------------------------------------------------------------
 * Saf çekirdek: tek-uçuş kapısı + sonuç sırası
 * ---------------------------------------------------------------------- */

export interface SubmitGateHandlers<Args extends unknown[]> {
  /** Her render'ın güncel eylemi; kanca bunu ref üzerinden verir. */
  action: (...args: Args) => unknown;
  setBusy: (busy: boolean) => void;
  /** Yeni gönderim başlarken eski hata satırı temizlenir. */
  clearError: () => void;
  /** Eylem fırlattı: ham hata çağrı yerinin seçtiği eşlemeye gider. */
  reportError: (cause: unknown) => void;
}

/**
 * Kapılı koşucu. Sıra sabittir ve testle çivilidir: kapı → busy → hata
 * temizliği → eylem → (hata eşlemesi) → kapı açılır → busy düşer. Senkron
 * fırlatan eylem de `finally`'ye düşer; kapı açık kalamaz.
 */
export function createSubmitGate<Args extends unknown[]>(
  handlers: SubmitGateHandlers<Args>,
): (...args: Args) => Promise<void> {
  let inFlight = false;
  return async (...args: Args): Promise<void> => {
    if (inFlight) return;
    inFlight = true;
    handlers.setBusy(true);
    handlers.clearError();
    try {
      await handlers.action(...args);
    } catch (cause) {
      handlers.reportError(cause);
    } finally {
      inFlight = false;
      handlers.setBusy(false);
    }
  };
}

/* -------------------------------------------------------------------------
 * Kanca
 * ---------------------------------------------------------------------- */

export interface UseSubmitOptions {
  /** Backend susarsa `errorMessage`'a geçen yedek cümle. */
  fallback?: string;
  /**
   * Hata çıkışını devralan çağrı yeri. Verildiğinde kancanın `error`'ı boş
   * kalır; ham hata buraya iletilir ve gösterim tümüyle çağrı yerinindir.
   */
  onError?: (cause: unknown) => void;
}

export interface SubmitHandle<Args extends unknown[]> {
  /** İstek uçuşta mı — `aria-disabled` ve düğme etiketi bunu okur. */
  busy: boolean;
  /** Son gönderimin hata cümlesi; yeni gönderim başlarken temizlenir. */
  error: string | null;
  /**
   * Hata satırını elle yazmak/temizlemek için: gönderim ÖNCESİ doğrulama
   * mesajları (profile, reset-password) ve gezinirken hatayı silen ekranlar
   * (exam `goTo`) bunu kullanır.
   */
  setError: (error: string | null) => void;
  /** Kapılı gönderim: busy iken çağrı yok sayılır. */
  submit: (...args: Args) => Promise<void>;
}

export function useSubmit<Args extends unknown[] = []>(
  action: (...args: Args) => unknown,
  options?: string | UseSubmitOptions,
): SubmitHandle<Args> {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Eylem ve seçenekler her render'da tazelenir; `submit` kimliği sabit kalır
  // ki çağıranlar useCallback'e mecbur olmasın ve prop olarak geçebilsin.
  const actionRef = useRef(action);
  actionRef.current = action;
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const submitRef = useRef<((...args: Args) => Promise<void>) | null>(null);
  if (submitRef.current === null) {
    submitRef.current = createSubmitGate<Args>({
      action: (...args) => actionRef.current(...args),
      setBusy,
      clearError: () => setError(null),
      reportError: (cause) => {
        const raw = optionsRef.current;
        const resolved = typeof raw === "string" ? { fallback: raw } : (raw ?? {});
        if (resolved.onError) resolved.onError(cause);
        else setError(errorMessage(cause, resolved.fallback));
      },
    });
  }

  const submit = submitRef.current;
  const setErrorStable = useCallback((next: string | null) => setError(next), []);

  return { busy, error, setError: setErrorStable, submit };
}
