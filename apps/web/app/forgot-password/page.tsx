"use client";

import Link from "next/link";
import { BrandLockup } from "@/components/brand-mark";
import { ShieldIcon } from "@/components/icons";
import { useState } from "react";
import { ErrorNote } from "@/components/page-state";
import { Field } from "@/components/field";
import { Button, Card, Input } from "@/components/ui";
import { requestPasswordReset } from "@/lib/api";
import { supabaseConfigured } from "@/lib/supabase";
import { useSubmit } from "@/lib/use-submit";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);

  // Çift gönderim kapısı `useSubmit`'te: busy iken çağrı yok sayılır.
  const { busy, error, submit: send } = useSubmit(async () => {
    await requestPasswordReset(email.trim());
    setSent(true);
  }, "Parola yenileme bağlantısı gönderilemedi.");

  function submit(event: React.FormEvent) {
    event.preventDefault();
    void send();
  }

  return (
    <main className="min-h-[100dvh] bg-bg">
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
        <h1 className="mt-2 text-[1.75rem] font-semibold tracking-tight text-fg">Parolanı yenile</h1>
        <p className="mt-3 text-base leading-7 text-fg-muted">
          Üniversite hesabına kayıtlı e-posta adresini yaz. Hesap varsa yenileme bağlantısı
          gönderilir.
        </p>

        {!supabaseConfigured ? (
          <p className="mt-6 rounded-xl bg-surface-sunken px-4 py-4 text-base leading-7 text-fg-muted">
            Demo hesapları için parola gerekmez. Parola yenileme bu ortamda henüz etkin değil.
          </p>
        ) : sent ? (
          <p role="status" className="mt-6 rounded-xl border border-border bg-success-bg p-5 text-base leading-7 text-success">
            Bağlantı gönderildiyse e-posta kutunda görünecek. Güvenlik için hesabın var olup
            olmadığını bu ekranda açıklamıyoruz.
          </p>
        ) : (
          <form onSubmit={submit} className="mt-7 space-y-5">
            <Field label="E-posta">
              {(control) => (
                <Input
                  {...control}
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />
              )}
            </Field>
            <Button type="submit" className="w-full" aria-disabled={busy}>
              {busy ? "Gönderiliyor…" : "Yenileme bağlantısı gönder"}
            </Button>
          </form>
        )}

        {error && (
          <div className="mt-4">
            <ErrorNote message={error} />
          </div>
        )}
        <p className="mt-6">
          <Link
            href="/"
            className="inline-flex min-h-11 items-center text-sm font-medium text-brand hover:text-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            Oturum açmaya dön
          </Link>
        </p>
      </Card>
      <p className="mt-6 text-center text-sm leading-6 text-fg-muted">DOU-Synapse · Doğuş Üniversitesi</p>
      </div>
    </main>
  );
}

