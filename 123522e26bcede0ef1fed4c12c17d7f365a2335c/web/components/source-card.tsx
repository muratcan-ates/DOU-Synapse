/**
 * Kaynak kartı — ürünün imza bileşeni (DESIGN.md §Components).
 *
 * Sistemin tüm tezi "her cevap gerçek bir sayfaya dayanır"; bu yüzden kaynak,
 * dipnot değil cevapla eşit ağırlıkta bir bileşendir. Alıntı chunk'tan birebir
 * gelir, model tarafından yeniden yazılmaz.
 */

export interface SourceInfo {
  fileName: string;
  /** "Sayfa 12" | "Slayt 7" | bölüm adı — konum HER ZAMAN görünür */
  location: string;
  quote: string;
}

export function SourceCard({ source }: { source: SourceInfo }) {
  return (
    <div className="rounded-lg border border-border bg-bg">
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-2">
        <span className="truncate font-mono text-xs text-fg">{source.fileName}</span>
        <span className="shrink-0 rounded bg-brand-subtle px-2 py-0.5 text-xs font-medium text-brand">
          {source.location}
        </span>
      </div>
      <blockquote className="prose-tr px-4 py-3 text-sm text-fg-muted">
        &ldquo;{source.quote}&rdquo;
      </blockquote>
    </div>
  );
}

/**
 * Kapsam dışı bildirimi — hata GİBİ GÖRÜNMEMELİ (DESIGN.md'deki en kritik karar).
 * "Materyalde yok" bir başarıdır: sistem uydurmak yerine reddediyor. Kırmızı,
 * ünlem, uyarı üçgeni yasak; nötr ton + her zaman bir sonraki adım önerisi.
 */
export function AbstentionNotice() {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <p className="prose-tr text-sm text-fg">
        Yüklenen ders materyallerinde bu sorunun cevabı bulunamadı.
      </p>
      <p className="prose-tr mt-2 text-sm text-fg-muted">
        Soruyu farklı sözcüklerle yeniden ifade etmeyi deneyebilir veya dersin
        eğitmenine iletebilirsiniz. Bu asistan yalnızca eğitmeninizin yüklediği
        kaynaklardan cevap verir; internetten bilgi karıştırmaz.
      </p>
    </div>
  );
}
