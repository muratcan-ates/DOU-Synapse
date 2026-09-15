import Link from "next/link";
import { BrandLockup } from "@/components/brand-mark";
import { Card } from "@/components/ui";

export default function NotFoundPage() {
  return (
    <main className="min-h-[100dvh] bg-bg">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex min-h-[76px] max-w-[1200px] items-center px-5 sm:px-8">
          <Link href="/dashboard" aria-label="Synapse çalışma alanı" className="inline-flex min-h-11 items-center rounded-xl focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand"><BrandLockup tone="canvas" /></Link>
        </div>
      </header>
      <div className="mx-auto w-full max-w-[860px] px-5 py-10 sm:py-16">
        <Card padding="none" className="overflow-hidden border border-border">
          <div className="grid sm:grid-cols-[9rem_minmax(0,1fr)]">
            <div aria-hidden="true" className="flex items-center justify-start bg-brand-subtle px-6 py-4 text-[4rem] font-semibold leading-none tracking-[-.06em] text-brand sm:justify-center sm:px-4 sm:py-8">404</div>
            <div className="min-w-0 p-6 sm:p-8">
              <p className="text-sm font-medium text-brand">Sayfa bulunamadı</p>
              <h1 className="mt-2 text-2xl font-semibold leading-tight tracking-tight text-fg">Bu sayfayı bulamadık</h1>
              <p className="mt-4 max-w-[48ch] text-base leading-relaxed text-fg-muted">Bağlantı değişmiş veya sayfa kaldırılmış olabilir. Çalışma alanınızdan derslerinize ulaşabilirsiniz.</p>
              <Link href="/dashboard" className="mt-7 inline-flex min-h-11 items-center justify-center rounded-xl bg-brand px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-brand-strong focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand dark:text-bg">Çalışma alanına dön</Link>
            </div>
          </div>
        </Card>
        <p className="mt-5 px-1 text-sm leading-relaxed text-fg-muted">Adresi elle yazdıysanız yazımını kontrol edebilirsiniz.</p>
      </div>
    </main>
  );
}
