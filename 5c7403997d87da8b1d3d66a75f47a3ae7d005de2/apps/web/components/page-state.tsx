/**
 * Sayfa durumu bileşenleri: yükleniyor · hata · önizleme şeridi · metrik satırı.
 *
 * Dördü de birden fazla ekranda birebir tekrarlanıyordu. Tek yerde olmalarının
 * asıl faydası tutarlılık: "Yükleniyor…" bir ekranda spinner, diğerinde metin
 * olursa ürün derlenmemiş hissi verir.
 */

import type { ReactNode } from "react";
import { Card } from "@/components/ui";

/** Belirsiz spinner yok: metin, ekranı zıplatmadan yerini tutar. */
export function Loading({ label = "Yükleniyor…" }: { label?: string }) {
  return (
    <p role="status" aria-live="polite" className="text-sm text-fg-muted">
      {label}
    </p>
  );
}

/**
 * Hata bildirimi. Metin backend'den gelir; arayüz kendi metnini uydurmaz.
 * `role="alert"` ile ekran okuyucuya anında duyurulur.
 */
export function ErrorNote({ message }: { message: string }) {
  return (
    <p role="alert" className="text-sm text-danger">
      {message}
    </p>
  );
}

/**
 * Tasarım önizlemesi şeridi — motoru henüz bağlanmamış ekranlarda ZORUNLU.
 *
 * Bu bileşen bir dürüstlük sözleşmesidir: örnek veriyi gerçek cevap gibi
 * göstermemek için ekranda kalıcı olarak durur. Kapatılabilir yapılmadı;
 * kapatılabilen bir uyarı kapatılır ve sonra unutulur.
 */
export function PreviewBanner({ children }: { children: ReactNode }) {
  return (
    <div className="mb-6 rounded-lg border border-border bg-brand-subtle px-4 py-2">
      <p className="text-sm text-brand">
        <span className="font-medium">Tasarım önizlemesi:</span> {children}
      </p>
    </div>
  );
}

export interface Metric {
  value: string | number;
  label: string;
}

/**
 * Özet metrik satırı: dört sayı, etiket sayının altında.
 * Sayı mono ve büyük; göz önce rakama, sonra etikete gider.
 */
export function MetricRow({ items }: { items: Metric[] }) {
  return (
    <Card className="mb-6">
      <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
        {items.map((item) => (
          <div key={item.label}>
            <p className="font-mono text-2xl text-fg">{item.value}</p>
            <p className="mt-1 text-xs text-fg-muted">{item.label}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}

/** Sayfa başlığı + açıklama — altı ekranda aynı boşluk ritmi. */
export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="rise mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-fg">{title}</h1>
        {description && (
          <p className="prose-tr mt-1 text-sm text-fg-muted">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}
