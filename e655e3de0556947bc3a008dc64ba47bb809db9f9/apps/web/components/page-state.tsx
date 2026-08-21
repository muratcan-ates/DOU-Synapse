"use client";

/**
 * Sayfa durumu bileşenleri: yükleniyor · hata · başlık · metrik satırı.
 *
 * Hepsi birden fazla ekranda birebir tekrarlanıyordu. Tek yerde olmalarının
 * asıl faydası tutarlılık: "Yükleniyor…" bir ekranda spinner, diğerinde metin
 * olursa ürün derlenmemiş hissi verir.
 *
 * `PreviewBanner` 9 Ağustos'ta SİLİNDİ. Motoru bağlanmamış ekranlarda zorunlu
 * bir dürüstlük şeridiydi ve işini bitirdi: dört ekranın dördü de gerçek uca
 * bağlandı, bileşenin tek bir çağrı yeri kalmadı. Yeniden gerekirse git
 * geçmişinde duruyor; kullanılmayan bir bileşeni "belki lazım olur" diye
 * tutmak, ölü kodun en yaygın gerekçesidir (Anayasa XI).
 */

import { useEffect, useState, type ReactNode } from "react";
import { Button, Card } from "@/components/ui";
import { shouldOfferRetry, type ErrorKind } from "@/lib/errors";

/** Bu süreyi aşan bekleyiş açıklanır (FR-154). */
export const SLOW_LOAD_MS = 4000;

/**
 * Uzayan bekleyişin açıklaması (T405).
 *
 * `docs/runbook.md:123-125`'teki cümle BİLEREK kopyalanmadı: orası jüriye
 * söylenen bir anlatıcı repliği ("birazdan göreceksiniz") ve em dash içeriyor;
 * Anayasa V arayüz metninde em dash'i yasaklıyor. Ekran metni ayrı yazıldı.
 *
 * Sayı uydurulmadı: 001'in ölçümlerinde ilk sayfa yüklemesi 19,1 saniye, ilk
 * soru 11,7 saniye, ikinci soru 0,08 saniye sürdü. "20 saniyeye kadar" o
 * gözlenen en kötü duruma yuvarlanmış hâlidir; hızlanma iddiası da ölçülmüş
 * ikinci soruya dayanıyor (Anayasa III).
 */
export const SLOW_LOAD_NOTICE =
  "Sunucu ilk isteği hazırlıyor. Uygulama yeni başlatıldıysa ilk yanıt 20 saniyeye " +
  "kadar sürebilir; sonraki istekler çok daha hızlı gelir.";

/**
 * Belirsiz spinner yok: metin, ekranı zıplatmadan yerini tutar.
 *
 * Dört saniyeyi aşan bekleyişe ikinci satır eklenir. Neden eşik: soğuk
 * başlangıç açıklaması HER yüklemede görünseydi, 0,08 saniyede dönen ikinci
 * sorunun altında da yanıp sönerdi ve kullanıcı onu okumayı bırakırdı.
 * Açıklama yalnız açıklanacak bir şey varken çıkar.
 */
export function Loading({ label = "Yükleniyor…" }: { label?: string }) {
  const slow = useElapsedBeyond(SLOW_LOAD_MS);
  return (
    // Canlı bölge dıştaki kapsayıcıda: ikinci satır sonradan eklendiğinde ekran
    // okuyucu onu da duyursun, ilk satırı yeniden okumak zorunda kalmadan.
    <div role="status" aria-live="polite">
      <p className="text-sm text-fg-muted">{label}</p>
      {slow && <p className="prose-tr mt-1 text-xs text-fg-muted">{SLOW_LOAD_NOTICE}</p>}
    </div>
  );
}

/** Beş sayfalı listenin ortak devam/hata yüzeyi (FR-160...FR-163). */
export function LoadMore({
  hasMore,
  busy,
  error,
  onLoadMore,
}: {
  hasMore: boolean;
  busy: boolean;
  error?: string | null;
  onLoadMore: () => void;
}) {
  if (!hasMore && !error) return null;
  return (
    <div className="mt-4 flex flex-col items-center gap-2">
      {error && <ErrorNote message={error} onRetry={onLoadMore} />}
      {hasMore && (
        <Button variant="secondary" disabled={busy} onClick={onLoadMore}>
          {busy ? "Yükleniyor…" : "Devamını yükle"}
        </Button>
      )}
    </div>
  );
}

/** Bileşen `ms` milisaniyedir ekranda mı? Zamanlayıcı sökülmede temizlenir. */
function useElapsedBeyond(ms: number): boolean {
  const [elapsed, setElapsed] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setElapsed(true), ms);
    return () => clearTimeout(timer);
  }, [ms]);
  return elapsed;
}

/**
 * Hata bildirimi. Metin backend'den gelir; arayüz kendi metnini uydurmaz.
 * `role="alert"` ile ekran okuyucuya anında duyurulur.
 *
 * `onRetry` verilirse metnin yanına "Tekrar dene" düğmesi çıkar. Neden zorunlu
 * değil: her hata tekrar denenebilir değildir (ders bulunamadı, yetki yok) ve
 * çalışmayan bir düğme koymak Anayasa XI'in yasakladığı kusurdur.
 *
 * `kind` verilirse o karar ARTIK HATIRLANMAK ZORUNDA DEĞİL (T403, FR-153):
 * düğme yalnız geçici hatada çıkar, kalıcı ve kimlik hatalarında `onRetry`
 * geçilmiş olsa bile gizlenir. Sınıfı bilmeyen çağrı yerleri eskisi gibi
 * davranmaya devam eder — `kind` yokluğu "sınıflandırılmadı" demektir,
 * "kalıcı" değil, ve sınıflandırılmamış bir hatada çalışan bir düğmeyi
 * kaldırmak kullanıcıdan çıkış yolunu almak olurdu.
 *
 * `requestId` verilirse destek kodu gösterilir (T406). Kod sunucudan gelir;
 * `null` ise sunucuya hiç varılamamıştır ve satır çizilmez.
 */
export function ErrorNote({
  message,
  kind,
  requestId,
  onRetry,
}: {
  message: string;
  kind?: ErrorKind | null;
  requestId?: string | null;
  onRetry?: () => void;
}) {
  const showRetry = shouldOfferRetry(kind, Boolean(onRetry));

  // `role="alert"` metnin kendisinde kalır: ekran okuyucu düğme etiketini
  // hatanın parçası gibi okumasın.
  const note = (
    <p role="alert" className="text-sm text-danger">
      {message}
    </p>
  );

  // Destek kodu ve düğme yoksa çıktı eskisiyle BİREBİR aynı: hatayı tek
  // paragraf olarak çizen ekranların boşluk ritmi değişmesin.
  if (!showRetry && !requestId) return note;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-3">
        {note}
        {showRetry && onRetry && (
          <Button variant="secondary" onClick={onRetry}>
            Tekrar dene
          </Button>
        )}
      </div>
      {requestId && <SupportCode requestId={requestId} />}
    </div>
  );
}

/**
 * Destek kodu satırı (T406).
 *
 * Kod `font-mono` çünkü kullanıcı onu okuyup yazacak; orantılı yazı tipinde
 * 1/l ve 0/O ayrımı kaybolur. Etiket kodun ne işe yaradığını söylüyor: kimlik
 * numarası gibi görünen ama neden orada olduğu yazmayan bir dize, kullanıcıya
 * hata mesajının bir parçası gibi okunur.
 */
function SupportCode({ requestId }: { requestId: string }) {
  return (
    <p className="text-xs text-fg-muted">
      Destek kodu: <span className="font-mono">{requestId}</span>
    </p>
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
