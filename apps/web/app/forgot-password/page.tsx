"use client";

import Link from "next/link";
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
    <main className="mx-auto flex min-h-screen max-w-lg items-center px-4 py-12">
      <Card className="w-full">
        <p className="text-sm font-medium text-brand">DOU-Synapse</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-fg">Parolanı yenile</h1>
        <p className="prose-tr mt-2 text-sm text-fg-muted">
          Üniversite hesabına kayıtlı e-posta adresini yaz. Hesap varsa yenileme bağlantısı
          gönderilir.
        </p>

        {!supabaseConfigured ? (
          <p className="prose-tr mt-6 text-sm text-fg-muted">
            Yerel demo girişinde parola kullanılmaz. Bu akış gerçek Supabase Auth
            yapılandırıldığında etkinleşir.
          </p>
        ) : sent ? (
          <p role="status" className="mt-6 rounded-lg border border-border bg-bg p-4 text-sm text-fg">
            Bağlantı gönderildiyse e-posta kutunda görünecek. Güvenlik için hesabın var olup
            olmadığını bu ekranda açıklamıyoruz.
          </p>
        ) : (
          <form onSubmit={submit} className="mt-6 space-y-4">
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
            className="text-sm text-brand hover:text-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            Oturum açmaya dön
          </Link>
        </p>
      </Card>
    </main>
  );
}

