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
 *
 * Kırmızı: "Tekrar dene" birincil eylemdir ve kırmızının üç meşru kullanımından
 * biridir. Hata durumunu işaretlemek için kırmızı METİN kullanılmadı.
 */

import Link from "next/link";
import { useEffect } from "react";
import { Button } from "@/components/ui";

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
    <main className="mx-auto flex min-h-screen max-w-[1200px] flex-col items-center justify-center gap-6 px-4 py-16 text-center">
      {/* role="alert": gezinme olmadığı için rota duyurucusu devreye girmez. */}
      <div role="alert" className="prose-tr">
        <h1 className="text-xl font-semibold tracking-tight text-fg">
          Bu sayfa açılamadı
        </h1>
        <p className="mt-2 text-sm text-fg-muted">
          Beklenmedik bir sorun oluştu. Tekrar deneyebilir ya da derslerinize
          dönebilirsiniz.
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-center gap-4">
        <Button onClick={() => retry()}>Tekrar dene</Button>
        <Link
          href="/courses"
          className="text-sm text-fg-muted underline underline-offset-4 hover:text-fg"
        >
          Derslerime dön
        </Link>
      </div>

      {error.digest && (
        <p className="font-mono text-xs text-fg-subtle">
          Hata kodu: {error.digest}
        </p>
      )}
    </main>
  );
}
