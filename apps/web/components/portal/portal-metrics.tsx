import type { ReactNode } from "react";

export interface PortalMetric {
  label: string;
  value: ReactNode;
  detail?: string;
}

export function PortalMetrics({ items }: { items: PortalMetric[] }) {
  return (
    <dl className="grid gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <div key={item.label} className="flex min-h-28 flex-col bg-surface p-5">
          <dt className="text-xs font-medium text-fg-muted">{item.label}</dt>
          <dd className="mt-2 font-mono text-2xl text-fg">{item.value}</dd>
          {item.detail && (
            <p className="mt-auto pt-2 text-xs text-fg-subtle">{item.detail}</p>
          )}
        </div>
      ))}
    </dl>
  );
}
