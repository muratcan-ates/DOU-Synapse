"use client";

/**
 * Veri çekme kancası — yükleniyor / hata / tazeleme üçlüsü tek yerde.
 *
 * Her sayfa aynı beş satırı tekrarlıyordu: iki state, bir useCallback, bir
 * useEffect ve aynı catch bloğu. Tekrarın maliyeti satır sayısı değil; bir
 * sayfanın hatayı temizlemeyi unutması ya da polling'i durdurmayı atlaması
 * gibi sessiz farklar. Tek kanca olunca o davranış her ekranda aynı.
 *
 * `pollWhile` opsiyonu: veri "hâlâ değişiyor" olduğu sürece kısa aralıkla
 * tazeler, koşul düşünce durur. Materyal işlenirken canlı durum rozetleri
 * bunun üzerine kurulu.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "@/lib/errors";

export interface Resource<T> {
  data: T | null;
  error: string | null;
  /** İlk yükleme tamamlanmadı; veri de hata da yok. */
  loading: boolean;
  /** Elle tazeleme — yazma işleminden sonra çağrılır. */
  reload: () => Promise<void>;
  /** İyimser güncelleme: sunucuyu beklemeden listeyi düzeltmek için. */
  setData: (next: T | null) => void;
}

export function useResource<T>(
  fetcher: () => Promise<T>,
  deps: readonly unknown[],
  options: { pollWhile?: (data: T) => boolean; intervalMs?: number } = {},
): Resource<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);

  // fetcher her render'da yeniden kurulur; kancayı bağımlılık döngüsüne
  // sokmamak için ref'te tutulur. Yenileme tetiği `deps`tir.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const reload = useCallback(async () => {
    try {
      const next = await fetcherRef.current();
      setData(next);
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    let cancelled = false;
    // Bağımlılık değişince eski veri ekranda kalmasın: yeni dersin listesi
    // gelene kadar öncekini göstermek yanlış derse bakıyormuş hissi verir.
    setData(null);
    setError(null);
    reload().then(() => {
      if (cancelled) return;
    });
    return () => {
      cancelled = true;
    };
  }, [reload]);

  const { pollWhile, intervalMs = 2000 } = options;
  const shouldPoll = data !== null && pollWhile ? pollWhile(data) : false;

  useEffect(() => {
    if (!shouldPoll) return;
    const timer = setInterval(reload, intervalMs);
    return () => clearInterval(timer);
  }, [shouldPoll, intervalMs, reload]);

  return {
    data,
    error,
    loading: data === null && error === null,
    reload,
    setData,
  };
}
