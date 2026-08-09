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
  /**
   * Yazma sonrası kısa süreli tazeleme penceresi açar.
   *
   * Neden gerekli (ölçülmüş): backend yükleme ucu `202` döndürüyor ama satır
   * yanıttan SONRA commit ediliyor — FastAPI `yield` bağımlılığını yanıt
   * üretildikten sonra kapatıyor. Ölçüm: POST'tan hemen sonraki GET 0 belge,
   * bir saniye sonraki GET 1 belge.
   *
   * Tek bir `reload()` bu yarışı kaybediyor. Daha kötüsü, normal polling
   * yalnız listede işlenen belge varken çalıştığı için BOŞ bir derse yapılan
   * ilk yükleme hiç görünmüyordu: kullanıcı dosyayı seçiyor, hiçbir şey
   * olmuyor, elle yenileyene kadar da olmuyor.
   */
  pulse: (durationMs?: number) => void;
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

  // Yazma sonrası kısa tazeleme penceresi (bkz. `pulse` docstring'i).
  const [pulsing, setPulsing] = useState(false);
  const pulseTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const pulse = useCallback((durationMs = 6000) => {
    setPulsing(true);
    if (pulseTimer.current) clearTimeout(pulseTimer.current);
    pulseTimer.current = setTimeout(() => setPulsing(false), durationMs);
  }, []);

  // Bileşen sökülürken zamanlayıcı kalmasın: sökülmüş bileşende setState uyarı üretir.
  useEffect(() => () => {
    if (pulseTimer.current) clearTimeout(pulseTimer.current);
  }, []);

  const { pollWhile, intervalMs = 2000 } = options;
  const activeByData = data !== null && pollWhile ? pollWhile(data) : false;
  const shouldPoll = activeByData || pulsing;

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
    pulse,
    setData,
  };
}
