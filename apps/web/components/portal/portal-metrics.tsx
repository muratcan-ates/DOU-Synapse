import type { ReactNode } from "react";

export interface PortalMetric {
  label: string;
  value: ReactNode;
  detail?: string;
}

/**
 * Metrik şeridi: kanvastan yükselen tek yüzey, içinde dört sayı.
 *
 * Önceki hâl dört hücreyi 1px saç çizgileriyle bölen kenarlıklı bir ızgaraydı
 * ve sayılar `font-mono`, `text-xl` idi — üniversite portalının "Duyurular"
 * kutusuyla aynı gramer. Katman sinyali artık gölgeden geliyor (DESIGN.md
 * §Elevation seviye 1), sayılar `tabular-nums` ile display ölçekte: hizalama
 * korunur, Türkçe ondalık ayracı kopmaz. Kırmızı yok; bu şerit bir eylem değil.
 */
export function PortalMetrics({ items }: { items: PortalMetric[] }) {
  return (
    <dl className="grid gap-x-8 gap-y-6 rounded-xl bg-surface px-6 py-6 shadow-e1 sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        // column-reverse: DOM sırası ters okunur — görselde sayı üstte, etiket altında, ayrıntı en altta.
        // justify-end: column-reverse'te ana eksen aşağıdan başlar; end = üst. Ayrıntısı olan
        // hücre uzasa da sayılar aynı üst çizgide durur.
        <div key={item.label} className="flex flex-col-reverse justify-end gap-1.5">
          {item.detail && <p className="max-w-52 text-xs text-fg-subtle">{item.detail}</p>}
          <dt className="text-xs font-medium text-fg-muted">{item.label}</dt>
          <dd className="text-3xl leading-none font-semibold tracking-tight tabular-nums text-fg">
            {item.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
