"use client";

/**
 * Son çare hata ekranı: kök layout'un KENDİSİ çökerse `app/error.tsx` devreye
 * giremez (rota hata sınırı kendi segmentindeki layout'u sarmaz), bu dosya girer.
 *
 * Next kuralı gereği kendi `<html>`/`<body>`'sini render eder ve kök layout'un
 * yerine geçtiği için global stilleri ve yazı tipini kendisi getirmek
 * zorundadır; getirmezse tasarım token'ları (renk, koyu tema) hiç yüklenmez.
 * İstemci bileşeni olmak da zorunlu, bu yüzden `metadata` export'u burada
 * çalışmaz — başlık React'in `<title>` bileşeniyle veriliyor.
 *
 * `error.tsx` ile aynı sözleşme: ham hata metni yok, yığın izi yok, tek kısa
 * Türkçe cümle ve iki çıkış yolu. Ayrıntılar app/error.tsx'te.
 *
 * Derslere dönüş `<Link>` değil düz `<a>`: kök layout çökmüşse yumuşak gezinme
 * aynı bozuk ağaca döner; tam sayfa isteği belgeyi sıfırdan kurar.
 */

import { Geist } from "next/font/google";
import { Button } from "@/components/ui";
import "./globals.css";

const geist = Geist({ subsets: ["latin", "latin-ext"], variable: "--font-geist" });

export default function GlobalError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <html lang="tr">
      <body className={`${geist.variable} antialiased`}>
        <title>Bir sorun oluştu · DOU-Synapse</title>
        <main className="mx-auto flex min-h-screen max-w-[1200px] flex-col items-center justify-center gap-6 px-4 py-16 text-center">
          <div role="alert" className="prose-tr">
            <h1 className="text-xl font-semibold tracking-tight text-fg">
              Uygulama açılamadı
            </h1>
            <p className="mt-2 text-sm text-fg-muted">
              Beklenmedik bir sorun oluştu. Tekrar deneyebilir ya da derslerinize
              dönebilirsiniz.
            </p>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-4">
            <Button onClick={() => retry()}>Tekrar dene</Button>
            <a
              href="/courses"
              className="text-sm text-fg-muted underline underline-offset-4 hover:text-fg"
            >
              Derslerime dön
            </a>
          </div>

          {error.digest && (
            <p className="text-xs text-fg-subtle">Hata kodu: {error.digest}</p>
          )}
        </main>
      </body>
    </html>
  );
}
