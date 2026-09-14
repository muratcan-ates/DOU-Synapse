/** Kurumsal imza, üniversitenin özgün armasıyla başlar. */
export function BrandMark({ className = "" }: { className?: string }) {
  return <img src="/brand/dogus-universitesi.svg" alt="" aria-hidden="true" width="40" height="40" className={`shrink-0 rounded-full bg-white ${className}`} />;
}
export function BrandLockup({ tone = "canvas", className = "" }: { tone?: "ink" | "canvas"; className?: string }) {
  return <span className={`flex items-center gap-2.5 ${className}`}>
    <BrandMark className="h-10 w-10" />
    <span><span className={`block leading-tight text-[1.25rem] font-semibold tracking-[-.04em] ${tone === "ink" ? "text-ink-fg" : "text-fg"}`}>Synapse<span className="text-brand">.</span></span><span className={`mt-1 block text-[0.5625rem] font-medium leading-tight tracking-[.015em] lg:hidden ${tone === "ink" ? "text-ink-fg-muted" : "text-fg-muted"}`}>Doğuş Üniversitesi</span></span>
  </span>;
}
export function UniversitySignature({ className = "" }: { className?: string }) {
  return <span className={`flex items-center gap-2.5 ${className}`}>
    <BrandMark className="h-10 w-10" />
    <span className="text-[0.6875rem] font-semibold leading-[1.45] tracking-[.06em] text-fg-muted">DOĞUŞ<br />ÜNİVERSİTESİ</span>
  </span>;
}
