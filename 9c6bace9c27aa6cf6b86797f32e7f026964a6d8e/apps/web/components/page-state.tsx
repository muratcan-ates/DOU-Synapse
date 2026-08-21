/**
 * Sayfa durumu bileşenleri: yükleniyor · hata · önizleme şeridi · metrik satırı.
 *
 * Dördü de birden fazla ekranda birebir tekrarlanıyordu. Tek yerde olmalarının
 * asıl faydası tutarlılık: "Yükleniyor…" bir ekranda spinner, diğerinde metin
 * olursa ürün derlenmemiş hissi verir.
 */

import type { ReactNode } from "react";
import { Button, Card } from "@/components/ui";

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
 *
 * `onRetry` verilirse metnin yanına "Tekrar dene" düğmesi çıkar. Neden zorunlu
 * değil: her hata tekrar denenebilir değildir (ders bulunamadı, yetki yok) ve
 * çalışmayan bir düğme koymak Anayasa XI'in yasakladığı kusurdur. Verilmediğinde
 * bileşen eskisiyle birebir aynı çizilir. Verildiğinde kullanıcının tek çıkışı
 * tarayıcıyı yenilemek olmaktan çıkar; tazeleme hatasında sayfa yerinde durduğu
 * için hatayı gerçekten kapatabilen tek şey bu düğmedir.
 */
export function ErrorNote({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  // `role="alert"` metnin kendisinde kalır: ekran okuyucu düğme etiketini
  // hatanın parçası gibi okumasın.
  const note = (
    <p role="alert" className="text-sm text-danger">
      {message}
    </p>
  );

  if (!onRetry) return note;

  return (
    <div className="flex flex-wrap items-center gap-3">
      {note}
      <Button variant="secondary" onClick={onRetry}>
        Tekrar dene
      </Button>
    </div>
  );
}

/**
 * Tasarım önizlemesi şeridi — motoru henüz bağlanmamış ekranlarda ZORUNLU.
 *
 * Bu bileşen bir dürüstlük sözleşmesidir: örnek veriyi gerçek cevap gibi
 * göstermemek için ekranda kalıcı olarak durur. Kapatılabilir yapılmadı;
 * kapatılabilen bir uyarı kapatılır ve sonra unutulur.
 *
 * Renk: bilgi tonu (`--info`), marka kırmızısı DEĞİL. DESIGN.md'nin kırmızı
 * kilidi kırmızıyı üç işe ayırır (birincil eylem, aktif navigasyon, kurumsal
 * işaret); "bu ekran henüz sahte veri gösteriyor" bunların hiçbiri değildir.
 * Ölçüm: `--info` (#1f6c9f) üstünde `--info-bg` (#e1f3fe) 4.98:1 ✓ AA;
 * koyu temada (#6fb4dd / #14232e) 7.06:1 ✓ AAA.
 */
export function PreviewBanner({ children }: { children: ReactNode }) {
  return (
    <div className="mb-6 rounded-lg border border-border bg-info-bg px-4 py-2">
      <p className="text-sm text-info">
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
 *
 * Yapı `dl/dt/dd`: iki ayrı paragrafta sayı ile etiketi yan yana koymak
 * yalnız GÖRSEL bir ilişkidir. Ekran okuyucu sırayla "0.62", "Sınıf
 * ortalaması", "18", "Çözülen soru" okuduğunda hangi sayının hangi etikete
 * ait olduğu kaybolur. `dt`/`dd` bağı bunu dilin kendisinde kurar.
 * DOM'da etiket önce gelir (okuma sırası "Sınıf ortalaması: 0.62");
 * `flex-col-reverse` görsel sırayı — sayı üstte — olduğu gibi korur.
 */
export function MetricRow({ items }: { items: Metric[] }) {
  return (
    <Card className="mb-6">
      <dl className="grid grid-cols-2 gap-6 sm:grid-cols-4">
        {items.map((item) => (
          <div key={item.label} className="flex flex-col-reverse gap-1">
            <dt className="text-xs text-fg-muted">{item.label}</dt>
            <dd className="font-mono text-2xl text-fg">{item.value}</dd>
          </div>
        ))}
      </dl>
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
