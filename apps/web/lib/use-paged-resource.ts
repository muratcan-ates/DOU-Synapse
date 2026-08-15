"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { api } from "@/lib/api";
import { describeError, type ErrorInfo } from "@/lib/errors";
import type { Page } from "@/lib/types";
import { useResource } from "@/lib/use-resource";

export function pagedPath(path: string, cursor: string | null, limit?: number): string {
  const [base, rawQuery = ""] = path.split("?", 2);
  const query = new URLSearchParams(rawQuery);
  if (cursor) query.set("cursor", cursor);
  if (limit !== undefined) query.set("limit", String(limit));
  const suffix = query.toString();
  return suffix ? `${base}?${suffix}` : base;
}

export function appendUnique<T extends { id: string }>(current: T[], incoming: T[]): T[] {
  const seen = new Set(current.map((item) => item.id));
  return [...current, ...incoming.filter((item) => !seen.has(item.id))];
}

export interface PagedContinuationState<T extends { id: string }> {
  extraItems: T[];
  nextCursor: string | null;
  /** En az bir devam sayfası yüklendiyse ilk sayfa refresh'i cursor'ı geri alamaz. */
  hasLoadedExtra: boolean;
}

export type PagedContinuationAction<T extends { id: string }> =
  | { type: "reset" }
  | { type: "first-page-loaded"; nextCursor: string | null }
  | { type: "extra-page-loaded"; items: T[]; nextCursor: string | null };

export function initialPagedContinuation<T extends { id: string }>(): PagedContinuationState<T> {
  return { extraItems: [], nextCursor: null, hasLoadedExtra: false };
}

/**
 * İlk sayfanın polling/refresh cevabı yalnız kendi satırlarını yeniler.
 *
 * Kullanıcının açıkça yüklediği devam sayfaları ve ilerlemiş cursor korunur;
 * aksi hâlde iki saniyelik belge polling'i listenin alt yarısını sessizce
 * kaybettiriyordu. Yalnız identity/dependency değişimi veya bilinçli `reload`
 * `reset` gönderir.
 */
export function pagedContinuationReducer<T extends { id: string }>(
  state: PagedContinuationState<T>,
  action: PagedContinuationAction<T>,
): PagedContinuationState<T> {
  switch (action.type) {
    case "reset":
      return state.extraItems.length === 0 &&
        state.nextCursor === null &&
        !state.hasLoadedExtra
        ? state
        : initialPagedContinuation<T>();
    case "first-page-loaded":
      if (state.hasLoadedExtra || state.nextCursor === action.nextCursor) return state;
      return { ...state, nextCursor: action.nextCursor };
    case "extra-page-loaded":
      return {
        extraItems: appendUnique(state.extraItems, action.items),
        nextCursor: action.nextCursor,
        hasLoadedExtra: true,
      };
  }
}

export function usePagedResource<T extends { id: string }>(
  path: string,
  deps: readonly unknown[],
  options: { pollWhile?: (items: T[]) => boolean; intervalMs?: number } = {},
) {
  const fetchFirst = useCallback(() => api.get<Page<T>>(pagedPath(path, null)), [path]);
  // Yol da resource identity'sinin parçasıdır. Çağrı yeri path'i değiştirip
  // ayrıca deps'e eklemeyi unutsa bile önceki dersin pagination'ı taşınmaz.
  const identityDeps = [path, ...deps];
  const resource = useResource(fetchFirst, identityDeps, {
    pollWhile: options.pollWhile ? (page) => options.pollWhile?.(page.items) ?? false : undefined,
    intervalMs: options.intervalMs,
  });
  const [continuation, dispatchContinuation] = useReducer(
    pagedContinuationReducer<T>,
    undefined,
    initialPagedContinuation<T>,
  );
  const [loadingMore, setLoadingMore] = useState(false);
  const continuationEpoch = useRef(0);
  const previousReload = useRef(resource.reload);
  const identityChangedThisRender = previousReload.current !== resource.reload;
  if (identityChangedThisRender) previousReload.current = resource.reload;
  /*
   * Devam sayfası hatası düz metne indirgenmez. API'nin hata sınıfı ve
   * request_id değeri burada kaybolursa çağrı yeri ne güvenli bir yeniden
   * deneme kararı verebilir ne de kullanıcıya destek kodunu gösterebilir.
   */
  const [pageError, setPageError] = useState<ErrorInfo | null>(null);

  const resetContinuation = useCallback(() => {
    continuationEpoch.current += 1;
    dispatchContinuation({ type: "reset" });
    setLoadingMore(false);
    setPageError(null);
  }, []);

  useEffect(() => {
    resetContinuation();
  }, [resource.reload, resetContinuation]);

  useEffect(() => {
    // Dependency değiştiği render'da `resource.data` hâlâ eski identity'ye
    // ait olabilir. useResource onu hemen ardından sıfırlar; o eski cursor'ı
    // yeni identity'ye yazmıyoruz.
    if (!resource.data || identityChangedThisRender) return;
    dispatchContinuation({
      type: "first-page-loaded",
      nextCursor: resource.data.next_cursor,
    });
  }, [identityChangedThisRender, resource.data]);

  const loadMore = useCallback(async () => {
    if (!continuation.nextCursor || loadingMore) return;
    const epoch = continuationEpoch.current;
    setLoadingMore(true);
    setPageError(null);
    try {
      const next = await api.get<Page<T>>(pagedPath(path, continuation.nextCursor));
      if (continuationEpoch.current !== epoch) return;
      dispatchContinuation({
        type: "extra-page-loaded",
        items: next.items,
        nextCursor: next.next_cursor,
      });
    } catch (error) {
      if (continuationEpoch.current !== epoch) return;
      setPageError(describeError(error));
    } finally {
      if (continuationEpoch.current === epoch) setLoadingMore(false);
    }
  }, [continuation.nextCursor, loadingMore, path]);

  const reload = useCallback(async () => {
    resetContinuation();
    await resource.reload();
  }, [resetContinuation, resource.reload]);

  return {
    ...resource,
    data: resource.data
      ? appendUnique(resource.data.items, continuation.extraItems)
      : null,
    nextCursor: continuation.nextCursor,
    loadingMore,
    pageError,
    loadMore,
    reload,
  };
}
