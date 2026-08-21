"use client";

import { useId, type ReactNode } from "react";
import { Button } from "@/components/ui";

export interface AdminColumn<T> {
  key: string;
  header: string;
  render: (item: T) => ReactNode;
  className?: string;
}

export function AdminDataTable<T>({
  title,
  description,
  items,
  columns,
  rowKey,
  emptyMessage,
}: {
  title: string;
  description: string;
  items: T[];
  columns: AdminColumn<T>[];
  rowKey: (item: T, index: number) => string;
  emptyMessage: string;
}) {
  const titleId = useId();
  const descriptionId = useId();

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className="border-b border-border px-5 py-4">
        <h2 id={titleId} className="text-lg font-medium text-fg">
          {title}
        </h2>
        <p id={descriptionId} className="mt-1 text-xs text-fg-muted">
          {description}
        </p>
      </div>
      <div className="overflow-hidden md:overflow-x-auto">
        <table
          className="block min-w-full border-collapse text-left text-sm md:table"
          aria-labelledby={titleId}
          aria-describedby={descriptionId}
        >
          <thead className="hidden bg-bg text-xs text-fg-muted md:table-header-group">
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  className={`whitespace-nowrap border-b border-border px-4 py-3 font-medium ${column.className ?? ""}`}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="block divide-y divide-border md:table-row-group md:divide-y-0">
            {items.length === 0 ? (
              <tr className="block md:table-row">
                <td
                  colSpan={columns.length}
                  className="block px-4 py-10 text-center text-fg-muted md:table-cell"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              items.map((item, index) => (
                <tr
                  key={rowKey(item, index)}
                  className="block px-4 py-3 transition-colors duration-200 hover:bg-bg md:table-row md:border-b md:border-border md:px-0 md:py-0 md:last:border-b-0"
                >
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={`grid min-w-0 grid-cols-[minmax(0,7rem)_minmax(0,1fr)] gap-3 py-1.5 align-top text-fg md:table-cell md:whitespace-nowrap md:px-4 md:py-3 ${column.className ?? ""}`}
                    >
                      <span className="text-xs font-medium text-fg-muted md:hidden">
                        {column.header}
                      </span>
                      <span className="min-w-0 break-words">
                        {column.render(item)}
                      </span>
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function AdminPagination({
  total,
  offset,
  limit,
  busy,
  onChange,
}: {
  total: number;
  offset: number;
  limit: number;
  busy: boolean;
  onChange: (offset: number) => void;
}) {
  const lastPageOffset =
    total === 0 ? 0 : Math.floor((total - 1) / limit) * limit;
  const safeOffset = Math.min(offset, lastPageOffset);
  const first = total === 0 ? 0 : safeOffset + 1;
  const last = Math.min(safeOffset + limit, total);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 pt-4">
      <p className="text-xs text-fg-muted" aria-live="polite">
        {first}-{last} / {total} kayıt
      </p>
      <div className="flex gap-2">
        <Button
          variant="secondary"
          aria-disabled={busy || safeOffset === 0}
          onClick={() => onChange(Math.max(0, safeOffset - limit))}
        >
          Önceki
        </Button>
        <Button
          variant="secondary"
          aria-disabled={busy || safeOffset + limit >= total}
          onClick={() => onChange(safeOffset + limit)}
        >
          Sonraki
        </Button>
      </div>
    </div>
  );
}
