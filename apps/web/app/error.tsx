"use client";

/**
 * Rota hata sınırı — render sırasında istisna çıkarsa bu ekran görünür.
 *
 * Yoksa Next'in İngilizce "This page couldn't load" ekranı geliyordu; Anayasa V
 * kullanıcıya dönen her metnin Türkçe olmasını şart koşar ve bu ekran da
 * kullanıcıya dönen bir metindir.
 *
 * Ham hata GÖSTERİLMEZ (Anayasa X: kullanıcıya asla stack trace gösterilmez).
 * Sunucu bileşeninden gelen mesajı Next zaten maskeler; istemci bileşeninden
 * geleni maskelemez ve o metin İngilizce bir JS hatasıdır. Bu yüzden ekranda
 * `error.message` yok. Geliştiricinin ihtiyacı `console.error` ile karşılanır,
 * kullanıcıya kalan tek iz `digest`: opak bir kod, sunucu günlüğüyle eşleşir.
 *
 * `retry()` Next 16.3'te kararlı hale gelen kurtarma çağrısıdır ve `reset()`
 * yerine önerilir (node_modules/next/dist/docs/.../file-conventions/error.md):
 * `reset` yalnız sınırı yeniden render eder, `retry` veriyi de yeniden çeker.
 * Bu ekranların hatası çoğunlukla veri çekmede doğduğu için doğru olan `retry`.
 */

import Link from "next/link";
import { useEffect } from "react";
import { Button, Card } from "@/components/ui";
import { BrandLockup } from "@/components/brand-mark";
import { FileIcon } from "@/components/icons";

export default function RouteError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="min-h-[100dvh] bg-bg">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex min-h-[76px] max-w-[1200px] items-center px-5 sm:px-8"><BrandLockup tone="canvas" /></div>
      </header>
      <div className="mx-auto w-full max-w-[640px] px-5 py-10 sm:py-16">
        <Card className="sm:p-8">
          <span className="mb-5 grid h-12 w-12 place-items-center rounded-xl bg-surface-sunken text-fg-muted"><FileIcon size={25} /></span>
          {/* The alert contains no raw provider or runtime error text. */}
          <div role="alert">
            <h1 className="text-[28px] leading-tight font-semibold tracking-tight text-fg">Bu sayfa açılamadı</h1>
            <p className="mt-3 text-base leading-7 text-fg-muted">Beklenmedik bir sorun oluştu. Tekrar deneyebilir ya da derslerinize dönebilirsiniz.</p>
          </div>
          <div className="mt-7 flex flex-wrap items-center gap-3">
            <Button onClick={() => retry()}>Tekrar dene</Button>
            <Link href="/courses" className="inline-flex min-h-11 items-center rounded-xl border border-border-strong px-5 py-2 text-sm font-medium text-fg motion-safe:transition-colors hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">Derslerime dön</Link>
          </div>
          {error.digest && <p className="mt-6 break-all border-t border-border pt-4 text-sm text-fg-subtle">Hata kodu: {error.digest}</p>}
        </Card>
      </div>
    </main>
  );
}
