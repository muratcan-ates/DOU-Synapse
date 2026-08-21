"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { describeError } from "@/lib/errors";
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

export function usePagedResource<T extends { id: string }>(
  path: string,
  deps: readonly unknown[],
  options: { pollWhile?: (items: T[]) => boolean; intervalMs?: number } = {},
) {
  const fetchFirst = useCallback(() => api.get<Page<T>>(pagedPath(path, null)), [path]);
  const resource = useResource(fetchFirst, deps, {
    pollWhile: options.pollWhile ? (page) => options.pollWhile?.(page.items) ?? false : undefined,
    intervalMs: options.intervalMs,
  });
  const [extraItems, setExtraItems] = useState<T[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);

  useEffect(() => {
    setExtraItems([]);
    setNextCursor(resource.data?.next_cursor ?? null);
    setPageError(null);
  }, [resource.data]);

  const loadMore = useCallback(async () => {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    setPageError(null);
    try {
      const next = await api.get<Page<T>>(pagedPath(path, nextCursor));
      setExtraItems((current) => appendUnique(current, next.items));
      setNextCursor(next.next_cursor);
    } catch (error) {
      setPageError(describeError(error).message);
    } finally {
      setLoadingMore(false);
    }
  }, [loadingMore, nextCursor, path]);

  const reload = useCallback(async () => {
    setExtraItems([]);
    setNextCursor(null);
    setPageError(null);
    await resource.reload();
  }, [resource.reload]);

  return {
    ...resource,
    data: resource.data ? appendUnique(resource.data.items, extraItems) : null,
    nextCursor,
    loadingMore,
    pageError,
    loadMore,
    reload,
  };
}
