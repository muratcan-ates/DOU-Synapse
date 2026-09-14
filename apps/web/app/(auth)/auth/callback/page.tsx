"use client";

import Link from "next/link";
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
  return <main className="mx-auto flex min-h-screen max-w-lg items-center px-4 py-12">
    <Card className="w-full">
      <p className="text-sm font-medium text-brand">DOU-Synapse</p>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight text-fg">Oturum doğrulama</h1>
      {error ? <div className="mt-6"><ErrorNote message={error} /></div> : <p role="status" className="mt-6 text-sm text-fg-muted">Bağlantı doğrulanıyor…</p>}
      {error && <Link href="/verify-email" className="mt-6 inline-block text-sm text-brand underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">Yeni doğrulama bağlantısı iste</Link>}
      <Link href="/" className="mt-4 block text-sm text-brand underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">Oturum açmaya dön</Link>
    </Card>
  </main>;
}
