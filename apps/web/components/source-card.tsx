"use client";

/**
 * Kaynak kartı — ürünün imza bileşeni (DESIGN.md §Components).
 *
 * Sistemin tüm tezi "her cevap gerçek bir sayfaya dayanır"; bu yüzden kaynak,
 * dipnot değil cevapla eşit ağırlıkta bir bileşendir. Alıntı chunk'tan birebir
 * gelir, model tarafından yeniden yazılmaz.
 */

import Link from "next/link";
import { ChevronRightIcon, FileIcon } from "@/components/icons";
import { recordCitationOpened, type CitationLearningContext } from "@/lib/learning-events";
import { ABSTENTION_LABEL, type AbstentionStatus } from "@/lib/chat";
import type { SourceInfo } from "@/lib/types";

/**
 * `SourceInfo` artık `lib/types.ts`'te yaşıyor: tip burada tanımlıyken
 * `lib/source` ve `lib/questions` onu buradan import ediyordu ve bu, deponun
 * tek lib→components tersinmesiydi. Re-export geriye uyum içindir; yeni kod
 * tipi doğrudan `@/lib/types`'tan almalı.
 */
export type { SourceInfo } from "@/lib/types";

export function SourceCard({ source, href, learningContext }: {
  source: SourceInfo; href?: string; learningContext?: CitationLearningContext;
}) {
  function recordOpen() {
    // Ön yükleme olay üretmez; yalnız kullanıcı kaynak bağlantısını açınca yazılır.
    // Ölçüm hatası kaynağa erişimi kesmez, sunucu kendi yetki kapısını uygular.
    if (learningContext) void recordCitationOpened(learningContext).catch(() => undefined);
  }
  const card = (
    <div className="overflow-hidden rounded-2xl border border-border bg-surface transition-colors group-hover:border-fg-subtle">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-surface-sunken px-4 py-3">
        <span className="flex min-w-0 flex-1 items-center gap-2 text-sm font-medium text-fg"><FileIcon size={17} className="shrink-0" /><span className="min-w-0 break-words">{source.fileName}</span></span>
        {/*
          Konum rozeti INFO tonundadır, marka kırmızısı değil: kırmızının üç
          meşru kullanımı var (birincil eylem, aktif navigasyon, kurum işareti)
          ve kaynak göstergesi bunların hiçbiri. `--info` zaten "kaynak
          referansı" için tanımlı (DESIGN.md §Semantik).
        */}
        <span className="shrink-0 rounded-md bg-info-bg px-2.5 py-1 text-sm font-medium text-info">
          {source.location}
        </span>
      </div>
      <blockquote className="prose-tr px-4 py-4 text-base leading-relaxed text-fg-muted">
        &ldquo;{source.quote}&rdquo;
      </blockquote>
      {href && <span className="flex items-center justify-between gap-2 px-4 pb-4 text-sm font-medium text-info">Kaynak bağlamını aç<ChevronRightIcon size={17} /></span>}
    </div>
  );
  if (!href) return card;
  return (
    <Link
      href={href}
      onClick={recordOpen}
      onAuxClick={(event) => { if (event.button === 1) recordOpen(); }}
      aria-label={`${source.fileName}, ${source.location} kaynak bağlamını aç`}
      className="group block rounded-2xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
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
    <div className="rounded-2xl border border-border bg-surface-sunken p-5">
      <p className="text-sm font-semibold text-fg-muted">{ABSTENTION_LABEL[status]}</p>
      <p className="prose-tr mt-2 text-base leading-relaxed text-fg">{message}</p>
    </div>
  );
}
