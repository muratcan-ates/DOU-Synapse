"use client";

/**
 * Ters sayfalama kancası — `use-paged-resource`'un ters varyantı.
 *
 * Normal sayfalama listeye SONA ekler (loadMore → append); sohbet geçmişi gibi
 * "en yeni ekranda, daha eskisi istenince yukarı eklenir" listelerde yön
 * terstir: ilk sayfa en yeni dilimdir, devam sayfası BAŞA eklenir (prepend).
 * Bu üçlü (`cursor` / `olderLoading` / `error`) chat ekranında bağımsız bir
 * kopya olarak yaşıyordu; kanca onu lib'e indirir ki karar çekirdeği DOM'suz
 * `bun test lib/` ile sınanabilsin (aynı gerekçe `use-resource.ts`'te yazılı).
 *
 * Açılış ve devam sayfaları aynı kaynak nesline bağlıdır. Oturum değişince,
 * sıfırlanınca veya bileşen kapanınca eski başarı/hata cevabı düşürülür.
 */

import { useEffect, useReducer, useRef } from "react";
import { api } from "@/lib/api";
import { subscribeAuthChanges } from "@/lib/auth-events";
import { describeError, type ErrorInfo } from "@/lib/errors";
import type { Page } from "@/lib/types";
import { pagedPath } from "@/lib/use-paged-resource";

/* -------------------------------------------------------------------------
 * Saf çekirdek: durum makinesi
 * ---------------------------------------------------------------------- */

export interface ReverseHistoryState<U> {
  /** Ekrandaki satırlar; en eski başta, en yeni sonda. */
  items: U[];
  /** Daha eski sayfanın imleci; null ise daha eskisi yok. */
  cursor: string | null;
  /** İlk sayfa (open) uçuşta mı? */
  loading: boolean;
  /** Devam sayfası (loadOlder) uçuşta mı? */
  olderLoading: boolean;
  /** Son open/loadOlder hatası; yeni istek başlarken temizlenir. */
  error: ErrorInfo | null;
}

export type ReverseHistoryAction<U> =
  | { type: "reset" }
  | { type: "open-started" }
  | { type: "open-loaded"; items: U[]; cursor: string | null }
  | { type: "open-failed"; error: ErrorInfo }
  | { type: "older-started" }
  | { type: "older-loaded"; items: U[]; cursor: string | null }
  | { type: "older-failed"; error: ErrorInfo }
  /** Canlı turun eklediği satırlar (ör. soru + cevap) — sona eklenir. */
  | { type: "append"; items: U[] }
  /** Satır içi düzeltme (ör. geri bildirim işareti) — sırayı değiştirmez. */
  | { type: "update"; apply: (items: U[]) => U[] };

export function initialReverseHistory<U>(): ReverseHistoryState<U> {
  return { items: [], cursor: null, loading: false, olderLoading: false, error: null };
}

export function reverseHistoryReducer<U>(
  state: ReverseHistoryState<U>,
  action: ReverseHistoryAction<U>,
): ReverseHistoryState<U> {
  switch (action.type) {
    case "reset":
      return initialReverseHistory<U>();
    case "open-started":
      return { ...initialReverseHistory<U>(), loading: true };
    case "open-loaded":
      return { ...state, items: action.items, cursor: action.cursor, loading: false };
    case "open-failed":
      return { ...state, error: action.error, loading: false };
    case "older-started":
      return { ...state, olderLoading: true, error: null };
    case "older-loaded":
      return {
        ...state,
        items: [...action.items, ...state.items],
        cursor: action.cursor,
        olderLoading: false,
      };
    case "older-failed":
      return { ...state, error: action.error, olderLoading: false };
    case "append":
      return { ...state, items: [...state.items, ...action.items] };
    case "update":
      return { ...state, items: action.apply(state.items) };
  }
}

/* -------------------------------------------------------------------------
 * Kanca
 * ---------------------------------------------------------------------- */

export interface ReverseHistoryHandle<U> extends ReverseHistoryState<U> {
  /**
   * Yeni bir kaynağa geç: liste temizlenir, ilk sayfa çekilir. Dönüş değeri
   * "bu açılış hâlâ geçerli mi": arada yeni bir `open`/`reset` olduysa false —
   * çağrı yeri kalıcılaştırma gibi yan etkileri buna bakarak atlar.
   */
  open: (path: string) => Promise<boolean>;
  /** Bir sayfa daha eskiyi başa ekle; kapı `olderLoading` bayrağıdır. */
  loadOlder: () => Promise<void>;
  /** Listeyi boşalt ve tüm uçuştaki cevapları geçersizle. */
  reset: () => void;
  append: (items: U[]) => void;
  update: (apply: (items: U[]) => U[]) => void;
}

export interface ReverseHistoryPorts<T, U> {
  load(path: string): Promise<Page<T>>;
  map(items: T[]): U[];
  dispatch(action: ReverseHistoryAction<U>): void;
}

/** Üretimde kullanılan istek koşucusu: kaynak nesli ve tek devam isteği kapısı. */
export function createReverseHistory<T, U>(ports: ReverseHistoryPorts<T, U>) {
  let epoch = 0;
  let path: string | null = null;
  let cursor: string | null = null;
  let olderLoading = false;
  let suspended = false;

  const open = async (nextPath: string): Promise<boolean> => {
    const requestEpoch = ++epoch;
    path = nextPath;
    cursor = null;
    olderLoading = false;
    ports.dispatch({ type: "open-started" });
    try {
      const page = await ports.load(nextPath);
      if (epoch !== requestEpoch) return false;
      cursor = page.next_cursor;
      ports.dispatch({ type: "open-loaded", items: ports.map(page.items), cursor });
      return true;
    } catch (error) {
      if (epoch !== requestEpoch) return false;
      ports.dispatch({ type: "open-failed", error: describeError(error) });
      return false;
    }
  };

  return {
    open,
    async loadOlder(): Promise<void> {
      if (path === null || cursor === null || olderLoading || suspended) return;
      const requestEpoch = epoch;
      const requestPath = pagedPath(path, cursor);
      olderLoading = true;
      ports.dispatch({ type: "older-started" });
      try {
        const page = await ports.load(requestPath);
        if (epoch !== requestEpoch) return;
        cursor = page.next_cursor;
        ports.dispatch({ type: "older-loaded", items: ports.map(page.items), cursor });
      } catch (error) {
        if (epoch !== requestEpoch) return;
        ports.dispatch({ type: "older-failed", error: describeError(error) });
      } finally {
        if (epoch === requestEpoch) olderLoading = false;
      }
    },
    reset(): void {
      epoch += 1;
      path = null;
      cursor = null;
      olderLoading = false;
      ports.dispatch({ type: "reset" });
    },
    cancel(): void {
      epoch += 1;
      suspended = true;
      olderLoading = false;
    },
    resume(): void {
      if (!suspended) return;
      suspended = false;
      // StrictMode kurulum/temizlik/kurulum provasında iptal edilen restore
      // tekrar okunur; gerçek unmount'ta resume çağrılmaz, hiçbir state yazılmaz.
      if (path !== null) void open(path);
    },
    append(items: U[]): void { ports.dispatch({ type: "append", items }); },
    update(apply: (items: U[]) => U[]): void { ports.dispatch({ type: "update", apply }); },
  };
}

export function useReverseHistory<T, U>(
  mapItems: (items: T[]) => U[],
): ReverseHistoryHandle<U> {
  const [state, dispatch] = useReducer(
    reverseHistoryReducer<U>, undefined, initialReverseHistory<U>,
  );
  const mapRef = useRef(mapItems);
  mapRef.current = mapItems;
  const runnerRef = useRef<ReturnType<typeof createReverseHistory<T, U>> | null>(null);
  if (runnerRef.current === null) {
    runnerRef.current = createReverseHistory<T, U>({
      load: (path) => api.get<Page<T>>(path),
      map: (items) => mapRef.current(items),
      dispatch,
    });
  }
  const runner = runnerRef.current;
  useEffect(() => {
    runner.resume();
    const stopAuth = subscribeAuthChanges(runner.reset);
    return () => { stopAuth(); runner.cancel(); };
  }, [runner]);
  return { ...state, open: runner.open, loadOlder: runner.loadOlder,
    reset: runner.reset, append: runner.append, update: runner.update };
}
