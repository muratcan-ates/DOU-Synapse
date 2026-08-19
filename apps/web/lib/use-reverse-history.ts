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
 * Kasıtlı olarak KORUNAN iki davranış (ChatScreen'in bugünkü semantiği):
 *
 * 1. `open()` yarışı token'la çözülür: hızlı iki açılışta geç dönen ilk cevap
 *    sessizce düşürülür — ekranda A seçiliyken içeriğin B olması engellenir.
 * 2. `loadOlder()` devamı ise token KONTROL ETMEZ: uçuştaki "daha eskiyi yükle"
 *    cevabı, arada `open()`/`reset()` olsa bile o anki listeye prepend edilir.
 *    Bu, taşınan ekranın ölçülen davranışıdır; burada davranış değiştirmek bu
 *    kancanın işi değildir. (Kapı `olderLoading` bayrağıdır: aynı anda ikinci
 *    devam isteği çıkmaz.)
 */

import { useCallback, useReducer, useRef } from "react";
import { api } from "@/lib/api";
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

/**
 * `reset` ve `open-started` `olderLoading`'e DOKUNMAZ: uçuştaki devam isteğinin
 * bayrağı, isteğin kendi bitişiyle (older-loaded/older-failed) düşer. Taşınan
 * ekran da böyle davranıyordu; bayrağı erken düşürmek "istek uçuşta ama meşgul
 * görünmüyor" penceresi açardı.
 */
export function reverseHistoryReducer<U>(
  state: ReverseHistoryState<U>,
  action: ReverseHistoryAction<U>,
): ReverseHistoryState<U> {
  switch (action.type) {
    case "reset":
      return { ...initialReverseHistory<U>(), olderLoading: state.olderLoading };
    case "open-started":
      return { ...state, items: [], cursor: null, loading: true, error: null };
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
  /** Listeyi boşalt ve uçuştaki `open` cevabını geçersizle. */
  reset: () => void;
  append: (items: U[]) => void;
  update: (apply: (items: U[]) => U[]) => void;
}

export function useReverseHistory<T, U>(
  mapItems: (items: T[]) => U[],
): ReverseHistoryHandle<U> {
  const [state, dispatch] = useReducer(
    reverseHistoryReducer<U>,
    undefined,
    initialReverseHistory<U>,
  );

  /*
   * Uçuştaki `open` isteğini geçersizleştiren sayaç (taşınan ekrandaki
   * `historyToken`). Hızlı iki açılışta birinci kaynağın geç gelen yanıtı
   * ikincinin listesini eziyordu; sayaç gecikmiş yanıtı sessizce düşürür.
   */
  const epochRef = useRef(0);
  /** Açık kaynağın yolu; devam sayfaları imleci buna ekleyerek ister. */
  const pathRef = useRef<string | null>(null);
  const mapRef = useRef(mapItems);
  mapRef.current = mapItems;

  const open = useCallback(async (path: string): Promise<boolean> => {
    const epoch = ++epochRef.current;
    pathRef.current = path;
    dispatch({ type: "open-started" });
    try {
      const page = await api.get<Page<T>>(path);
      if (epochRef.current !== epoch) return false;
      dispatch({
        type: "open-loaded",
        items: mapRef.current(page.items),
        cursor: page.next_cursor,
      });
      return true;
    } catch (error) {
      if (epochRef.current !== epoch) return false;
      dispatch({ type: "open-failed", error: describeError(error) });
      return false;
    }
  }, []);

  const loadOlder = useCallback(async () => {
    const path = pathRef.current;
    if (path === null || state.cursor === null || state.olderLoading) return;
    dispatch({ type: "older-started" });
    try {
      const older = await api.get<Page<T>>(pagedPath(path, state.cursor));
      dispatch({
        type: "older-loaded",
        items: mapRef.current(older.items),
        cursor: older.next_cursor,
      });
    } catch (error) {
      dispatch({ type: "older-failed", error: describeError(error) });
    }
  }, [state.cursor, state.olderLoading]);

  const reset = useCallback(() => {
    epochRef.current += 1;
    pathRef.current = null;
    dispatch({ type: "reset" });
  }, []);

  const append = useCallback((items: U[]) => {
    dispatch({ type: "append", items });
  }, []);

  const update = useCallback((apply: (items: U[]) => U[]) => {
    dispatch({ type: "update", apply });
  }, []);

  return { ...state, open, loadOlder, reset, append, update };
}
