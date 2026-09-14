import Link from "next/link";
import { BrandLockup } from "@/components/brand-mark";
import { FileIcon } from "@/components/icons";
import { Card } from "@/components/ui";

export default function NotFoundPage() {
  return (
    <main className="min-h-[100dvh] bg-bg">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex min-h-[76px] max-w-[1200px] items-center px-5 sm:px-8"><BrandLockup tone="canvas" /></div>
      </header>
      <div className="mx-auto w-full max-w-[640px] px-5 py-10 sm:py-16">
        <Card className="sm:p-8">
          <span className="mb-5 grid h-12 w-12 place-items-center rounded-xl bg-surface-sunken text-fg-muted"><FileIcon size={25} /></span>
          <p className="text-sm font-medium text-fg-muted">Sayfa bulunamadı · 404</p>
          <h1 className="mt-2 text-[28px] leading-tight font-semibold tracking-tight text-fg">Bu sayfa bulunamadı</h1>
          <p className="mt-3 text-base leading-7 text-fg-muted">Bağlantı değişmiş olabilir. Çalışma alanınıza dönerek derslerinize ve sınav araçlarına ulaşabilirsiniz.</p>
          <Link href="/dashboard" className="mt-7 inline-flex min-h-11 items-center rounded-xl bg-brand px-5 py-2 text-sm font-medium text-white motion-safe:transition-colors hover:bg-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand dark:text-bg">Çalışma alanına dön</Link>
        </Card>
      </div>
    </main>
  );
}
