/**
 * Marka işareti.
 *
 * Öncesi: kırmızı bir kare içinde "D" harfi + iki satırlık mono "DOU / Synapse".
 * O işaret hiçbir şey anlatmıyordu; herhangi bir kurumun herhangi bir ürünü
 * olabilirdi. Ürünün tek cümlesi "kaynak yoksa cevap da yok" — işaret de bunu
 * söylemeli.
 *
 * Geometri (elle çizilmiş TEK basit mark, DESIGN.md şekil kilidine uyar):
 * üst üste iki blok, üstteki dolu (kaynak), alttaki kırmızı ince çizgiyle ona
 * bağlı (atıf). Yani "cevap kaynağa bağlıdır" diyagramının en küçük hâli.
 * Dekoratif SVG üretme yasağının istisnası: tek, basit, geometrik marka işareti.
 */
export function BrandMark({
  className = "",
  tone = "ink",
}: {
  className?: string;
  /** `ink`: koyu ray üstünde. `canvas`: açık zemin üstünde. */
  tone?: "ink" | "canvas";
}) {
  const body = tone === "ink" ? "var(--ink-fg)" : "var(--fg)";
  const accent = tone === "ink" ? "var(--brand-on-ink)" : "var(--brand)";
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className={className}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Kaynak bloğu */}
      <rect x="3" y="3" width="18" height="7" rx="1.5" fill={body} />
      {/* Atıf bağı: kaynağı cevaba bağlayan çizgi */}
      <rect x="10.5" y="10" width="3" height="4" rx="1" fill={accent} />
      {/* Cevap bloğu: kaynağa bağlı olduğu için çerçeveli, dolu değil */}
      <rect
        x="3"
        y="14"
        width="18"
        height="7"
        rx="1.5"
        stroke={body}
        strokeWidth="1.6"
      />
    </svg>
  );
}

/** İşaret + kelime markası. Ray ve giriş ekranı aynı kilidi kullanır. */
export function BrandLockup({
  tone = "ink",
  className = "",
}: {
  tone?: "ink" | "canvas";
  className?: string;
}) {
  return (
    <span className={`flex items-center gap-2.5 ${className}`}>
      <BrandMark tone={tone} className="h-6 w-6 shrink-0" />
      <span
        className={`text-[0.9375rem] font-semibold tracking-tight ${
          tone === "ink" ? "text-ink-fg" : "text-fg"
        }`}
      >
        Synapse
      </span>
    </span>
  );
}
