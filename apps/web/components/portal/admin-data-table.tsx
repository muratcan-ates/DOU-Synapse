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
    <div className="overflow-hidden rounded-[20px] border border-border bg-surface shadow-e1">
      <div className="border-b border-border px-5 py-5 sm:px-6">
        <h2 id={titleId} className="text-xl font-semibold text-fg">{title}</h2>
        <p id={descriptionId} className="mt-2 max-w-[75ch] text-sm leading-relaxed text-fg-muted">
          {description}
        </p>
      </div>
      <div className="hidden overflow-x-auto md:block">
        <table
          className="min-w-full border-collapse text-left text-sm"
          aria-labelledby={titleId}
          aria-describedby={descriptionId}
        >
          <thead className="bg-surface-sunken text-sm text-fg-muted">
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  className={`whitespace-nowrap border-b border-border px-5 py-4 font-medium ${column.className ?? ""}`}
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
                      className={`whitespace-nowrap px-5 py-4 align-top text-fg ${column.className ?? ""}`}
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
      <div className="md:hidden" aria-labelledby={titleId} aria-describedby={descriptionId}>
        {items.length === 0 ? (
          <p className="px-5 py-10 text-sm leading-relaxed text-fg-muted">{emptyMessage}</p>
        ) : (
          <ul className="divide-y divide-border">
            {items.map((item) => (
              <li key={rowKey(item)} className="px-5 py-5">
                <dl className="space-y-4">
                  {columns.map((column, index) => (
                    <div key={column.key} className={index === 0 ? "border-b border-border pb-4" : "grid grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)] gap-3"}>
                      <dt className={index === 0 ? "mb-2 text-sm text-fg-muted" : "text-sm text-fg-muted"}>{column.header}</dt>
                      <dd className={`min-w-0 break-words text-sm text-fg ${index === 0 ? "font-medium" : ""}`}>{column.render(item)}</dd>
                    </div>
                  ))}
                </dl>
              </li>
            ))}
          </ul>
        )}
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
      <p className="text-sm text-fg-muted" aria-live="polite">
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
