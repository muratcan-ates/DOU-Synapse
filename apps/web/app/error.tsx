"use client";

import Link from "next/link";
import { useEffect } from "react";
import { Button, Card } from "@/components/ui";
import { BrandLockup } from "@/components/brand-mark";
import { FileIcon } from "@/components/icons";

// Next 16.3 retry() veriyi yeniden çeker; reset() yalnız sınırı yeniden render eder.
export default function RouteError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  const digest = typeof error.digest === "string" && /^[a-zA-Z0-9_-]{1,80}$/.test(error.digest) ? error.digest : null;
  useEffect(() => {
    // Ham istemci hatası mesaj veya kişisel içerik taşıyabilir; yalnız opak kod kaydedilir.
    console.error("Sayfa açılamadı.", digest ? { digest } : { digest: null });
  }, [error, digest]);

  return (
    <main className="min-h-[100dvh] bg-bg">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex min-h-[76px] max-w-[1200px] items-center px-5 sm:px-8">
          <Link href="/dashboard" aria-label="Synapse çalışma alanı" className="inline-flex min-h-11 items-center rounded-xl focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand"><BrandLockup tone="canvas" /></Link>
        </div>
      </header>
      <div className="mx-auto w-full max-w-[680px] px-5 py-10 sm:py-16">
        <Card padding="none" className="border border-border p-6 sm:p-8">
          <span aria-hidden="true" className="mb-5 grid h-12 w-12 place-items-center rounded-xl bg-brand-subtle text-brand"><FileIcon size={25} /></span>
          <div role="alert">
            <h1 className="text-2xl font-semibold leading-tight tracking-tight text-fg">Bu sayfa açılamadı</h1>
            <p className="mt-4 max-w-[48ch] text-base leading-relaxed text-fg-muted">Sayfa yüklenirken bir sorun oluştu. Yeniden deneyebilir veya çalışma alanınıza dönebilirsiniz.</p>
          </div>
          <div className="mt-7 flex flex-wrap items-center gap-3">
            <Button type="button" onClick={() => retry()}>Tekrar dene</Button>
            <Link href="/dashboard" className="inline-flex min-h-11 items-center justify-center rounded-xl border border-border-strong px-5 py-3 text-sm font-medium text-fg transition-colors hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand">Çalışma alanına dön</Link>
          </div>
          {digest && <p className="mt-6 break-all border-t border-border pt-4 text-sm text-fg-subtle">Hata kodu: {digest}</p>}
        </Card>
      </div>
    </main>
  );
}
