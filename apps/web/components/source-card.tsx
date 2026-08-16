/**
 * Kaynak kartı — ürünün imza bileşeni (DESIGN.md §Components).
 *
 * Sistemin tüm tezi "her cevap gerçek bir sayfaya dayanır"; bu yüzden kaynak,
 * dipnot değil cevapla eşit ağırlıkta bir bileşendir. Alıntı chunk'tan birebir
 * gelir, model tarafından yeniden yazılmaz.
 */

import Link from "next/link";
import { ABSTENTION_LABEL, type AbstentionStatus } from "@/lib/chat";
import type { SourceInfo } from "@/lib/types";

/**
 * `SourceInfo` artık `lib/types.ts`'te yaşıyor: tip burada tanımlıyken
 * `lib/source` ve `lib/questions` onu buradan import ediyordu ve bu, deponun
 * tek lib→components tersinmesiydi. Re-export geriye uyum içindir; yeni kod
 * tipi doğrudan `@/lib/types`'tan almalı.
 */
export type { SourceInfo } from "@/lib/types";

export function SourceCard({ source, href }: { source: SourceInfo; href?: string }) {
  const card = (
    <div className="rounded-lg border border-border bg-bg">
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-2">
        <span className="truncate font-mono text-xs text-fg">{source.fileName}</span>
        {/*
          Konum rozeti INFO tonundadır, marka kırmızısı değil: kırmızının üç
          meşru kullanımı var (birincil eylem, aktif navigasyon, kurum işareti)
          ve kaynak göstergesi bunların hiçbiri. `--info` zaten "kaynak
          referansı" için tanımlı (DESIGN.md §Semantik).
        */}
        <span className="shrink-0 rounded bg-info-bg px-2 py-0.5 text-xs font-medium text-info">
          {source.location}
        </span>
      </div>
      <blockquote className="prose-tr px-4 py-3 text-sm text-fg-muted">
        &ldquo;{source.quote}&rdquo;
      </blockquote>
    </div>
  );
  if (!href) return card;
  return (
    <Link
      href={href}
      aria-label={`${source.fileName}, ${source.location} kaynak bağlamını aç`}
      className="block rounded-lg transition-colors hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
    >
      {card}
    </Link>
  );
}

/**
 * Kapsam dışı / dayanaksız bildirimi — hata GİBİ GÖRÜNMEMELİ (DESIGN.md'deki en
 * kritik karar). "Materyalde yok" bir başarıdır: sistem uydurmak yerine
 * reddediyor. Kırmızı, ünlem, uyarı üçgeni ve `role="alert"` yok; nötr yüzey.
 *
 * Metin backend'den gelir. Sabit metin bilerek SİLİNDİ: aynı cümlenin biri
 * sunucuda biri arayüzde iki kopyası, ilk düzeltmede birbirinden ayrışırdı
 * (Anayasa V + XI). Sonraki adım önerisi de o metnin içindedir
 * (`app/modules/generation/service.py` USER_TEXT).
 *
 * Başlık, iki durumu ayırt etmek için burada duruyor: "dayanak yok" ile "bu
 * dersin konusu değil" farklı sonuçlardır ve aynı görünmemeleri gerekir.
 */
export function AbstentionNotice({
  status,
  message,
}: {
  status: AbstentionStatus;
  message: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <p className="text-xs font-medium text-fg-muted">{ABSTENTION_LABEL[status]}</p>
      <p className="prose-tr mt-2 text-sm text-fg">{message}</p>
    </div>
  );
}
