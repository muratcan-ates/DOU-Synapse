import Link from "next/link";

export default function NotFoundPage() {
  return (
    <main className="mx-auto flex min-h-[100dvh] max-w-2xl flex-col justify-center px-6 py-16">
      <p className="font-mono text-sm text-brand">404</p>
      <h1 className="mt-3 text-balance text-3xl font-semibold tracking-tight text-fg">
        Bu sayfa bulunamadı
      </h1>
      <p className="prose-tr mt-3 text-pretty text-sm text-fg-muted">
        Bağlantı değişmiş olabilir. Çalışma alanınıza dönerek derslerinize ve
        sınav araçlarına ulaşabilirsiniz.
      </p>
      <Link
        href="/dashboard"
        className="mt-8 inline-flex min-h-11 w-fit items-center rounded-lg bg-brand px-4 text-sm font-medium text-white transition-[background,transform] duration-200 hover:bg-brand-strong active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand dark:text-[#191715]"
      >
        Çalışma alanına dön
      </Link>
    </main>
  );
}
