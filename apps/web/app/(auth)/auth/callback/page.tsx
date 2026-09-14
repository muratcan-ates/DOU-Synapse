"use client";

import Link from "next/link";
import { BrandLockup } from "@/components/brand-mark";
import { ShieldIcon } from "@/components/icons";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { completeAuthCallback } from "@/lib/auth-session";
import { ErrorNote } from "@/components/page-state";
import { Card } from "@/components/ui";

export default function AuthCallbackPage() {
  const router = useRouter();
  const completing = useRef<ReturnType<typeof completeAuthCallback> | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    completing.current ??= completeAuthCallback();
    void completing.current.then((path) => { if (active) router.replace(path); }).catch(() => {
      if (!active) return;
      // Sağlayıcı ham hatası veya bağlantı jetonu görünür metne taşınmaz.
      window.history.replaceState(null, "", "/auth/callback");
      setError("Oturum doğrulanamadı. Bağlantı eksik veya süresi dolmuş olabilir; yeni bağlantı isteyin.");
    });
    return () => { active = false; };
  }, [router]);
  return <main className="min-h-[100dvh] bg-bg">
    <header className="border-b border-border bg-surface">
      <div className="mx-auto flex min-h-[76px] max-w-[1200px] items-center justify-between gap-4 px-5 sm:px-8">
        <BrandLockup tone="canvas" />
        <Link href="/" className="inline-flex min-h-11 items-center text-sm font-medium text-fg-muted hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">Girişe dön</Link>
      </div>
    </header>
    <div className="mx-auto w-full max-w-[560px] px-5 py-10 sm:py-16">
    <Card className="w-full sm:p-8">
      <span className="mb-5 grid h-12 w-12 place-items-center rounded-xl bg-brand-subtle text-brand"><ShieldIcon size={25} /></span>
      <p className="text-sm font-medium text-fg-muted">Hesap erişimi</p>
      <h1 className="mt-2 text-[1.75rem] font-semibold tracking-tight text-fg">Oturum doğrulama</h1>
      {error ? <div className="mt-6"><ErrorNote message={error} /></div> : <p role="status" className="mt-6 rounded-xl bg-surface-sunken p-5 text-base leading-7 text-fg-muted">Bağlantı doğrulanıyor…</p>}
      {error && <Link href="/verify-email" className="mt-6 inline-flex min-h-11 items-center text-sm font-medium text-brand underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">Yeni doğrulama bağlantısı iste</Link>}
      <Link href="/" className="mt-4 flex min-h-11 items-center text-sm font-medium text-brand underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">Oturum açmaya dön</Link>
    </Card>
    <p className="mt-6 text-center text-sm leading-6 text-fg-muted">DOU-Synapse · Doğuş Üniversitesi</p>
    </div>
  </main>;
}
