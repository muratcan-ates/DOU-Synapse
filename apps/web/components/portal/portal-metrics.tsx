import type { ReactNode } from "react";

export interface PortalMetric {
  label: string;
  value: ReactNode;
  detail?: string;
}

/** Mobilde iki sütunlu, büyük boşluklar yerine okunur etiket/değer grupları. */
export function PortalMetrics({ items }: { items: PortalMetric[] }) {
  return (
    <dl className="grid grid-cols-2 gap-x-5 gap-y-5 rounded-[20px] bg-surface px-5 py-5 sm:px-6 xl:grid-cols-4">
      {items.map((item) => (
        <div key={item.label} className="min-w-0 border-l-2 border-border pl-3">
          <dt className="text-sm text-fg-muted">{item.label}</dt>
          <dd className="mt-1 text-2xl font-semibold leading-tight tracking-tight tabular-nums text-fg">{item.value}</dd>
          {item.detail && <dd className="mt-2 max-w-56 text-xs leading-relaxed text-fg-subtle">{item.detail}</dd>}
        </div>
      ))}
    </dl>
  );
}
