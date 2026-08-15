import type { ReactNode } from "react";

export interface PortalMetric {
  label: string;
  value: ReactNode;
  detail?: string;
}

export function PortalMetrics({ items }: { items: PortalMetric[] }) {
  return (
    <dl className="grid gap-px border-y border-border bg-border sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <div key={item.label} className="flex min-h-24 flex-col bg-bg px-4 py-4 sm:px-5">
          <dt className="text-xs font-medium text-fg-muted">{item.label}</dt>
          <dd className="mt-1 font-mono text-xl text-fg">{item.value}</dd>
          {item.detail && (
            <p className="mt-auto max-w-52 pt-2 text-xs text-fg-subtle">{item.detail}</p>
          )}
        </div>
      ))}
    </dl>
  );
}
