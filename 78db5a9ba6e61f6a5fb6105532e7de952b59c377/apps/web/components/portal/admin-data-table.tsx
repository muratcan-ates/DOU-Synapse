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
  rowKey: (item: T) => string;
  emptyMessage: string;
}) {
  const titleId = useId();
  const descriptionId = useId();

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className="border-b border-border px-5 py-4">
        <h2 id={titleId} className="text-lg font-medium text-fg">{title}</h2>
        <p id={descriptionId} className="mt-1 text-xs text-fg-muted">
          {description}
        </p>
      </div>
      <div className="overflow-x-auto">
        <table
          className="min-w-full border-collapse text-left text-sm"
          aria-labelledby={titleId}
          aria-describedby={descriptionId}
        >
          <thead className="bg-bg text-xs text-fg-muted">
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
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-10 text-center text-fg-muted">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr
                  key={rowKey(item)}
                  className="border-b border-border transition-colors duration-200 hover:bg-bg last:border-b-0"
                >
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={`whitespace-nowrap px-4 py-3 align-top text-fg ${column.className ?? ""}`}
                    >
                      {column.render(item)}
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
  const first = total === 0 ? 0 : offset + 1;
  const last = Math.min(offset + limit, total);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 pt-4">
      <p className="text-xs text-fg-muted" aria-live="polite">
        {first}-{last} / {total} kayıt
      </p>
      <div className="flex gap-2">
        <Button
          variant="secondary"
          aria-disabled={busy || offset === 0}
          onClick={() => onChange(Math.max(0, offset - limit))}
        >
          Önceki
        </Button>
        <Button
          variant="secondary"
          aria-disabled={busy || offset + limit >= total}
          onClick={() => onChange(offset + limit)}
        >
          Sonraki
        </Button>
      </div>
    </div>
  );
}
