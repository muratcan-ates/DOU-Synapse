import Link from "next/link";
import { UniversitySignature } from "@/components/brand-mark";
import { SynapseIllustration } from "@/components/synapse-illustration";

export function SynapseFooter() {
  return <footer aria-label="Synapse" className="mt-10 overflow-hidden rounded-[24px] border border-border bg-surface">
    <SynapseIllustration variant="hands" />
    <div className="grid min-w-0 items-center gap-5 px-6 py-6 sm:px-8 sm:py-7 lg:grid-cols-[minmax(0,1fr)_auto] lg:gap-8">
      <div className="min-w-0 max-w-2xl">
        <p className="text-sm font-medium text-brand">Synapse · Öğrenmenin bağlantıları</p>
        <p className="mt-2 text-[1.5rem] font-semibold leading-tight tracking-[-.035em] text-fg [overflow-wrap:anywhere] sm:text-[1.75rem]">Her yeni fikir, yeni bir bağlantı.</p>
        <p className="mt-3 max-w-xl text-sm leading-6 text-fg-muted">İnsan merak eder. Bilgi yol gösterir. Synapse, ders kaynaklarınla düşüncelerin arasında bağ kurmana yardımcı olur.</p>
      </div>
      <Link href="/study" className="inline-flex min-h-11 max-w-full items-center justify-center gap-3 justify-self-start rounded-xl bg-brand px-5 py-3 text-center text-sm font-semibold leading-6 text-brand-fg transition-colors hover:bg-brand-strong focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand"><span>Ders tekrarına geç</span><span aria-hidden="true" className="shrink-0">→</span></Link>
    </div>
    <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border px-6 py-4 sm:px-8">
      <UniversitySignature />
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-fg-muted">
        <Link href="/courses" className="inline-flex min-h-11 items-center underline-offset-4 hover:text-brand hover:underline focus-visible:outline-2 focus-visible:outline-brand">Çalışmaya dön</Link>
        <Link href="/kvkk" className="inline-flex min-h-11 items-center underline-offset-4 hover:text-brand hover:underline focus-visible:outline-2 focus-visible:outline-brand">Gizlilik</Link>
        <span>DOU-Synapse</span>
      </div>
    </div>
  </footer>;
}
