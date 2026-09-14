"use client";

import Link from "next/link";
import { BrandLockup } from "@/components/brand-mark";
import { ShieldIcon } from "@/components/icons";
import { useState } from "react";
import { ErrorNote } from "@/components/page-state";
import { Field } from "@/components/field";
import { Button, Card, Input } from "@/components/ui";
import { updateCurrentPassword } from "@/lib/api";
import { PASSWORD_MIN_LENGTH, passwordValidationError } from "@/lib/auth";
import { supabaseConfigured } from "@/lib/supabase";
import { useSubmit } from "@/lib/use-submit";

export default function ResetPasswordPage() {
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [updated, setUpdated] = useState(false);

  const { busy, error, setError, submit: update } = useSubmit(async () => {
    await updateCurrentPassword(password);
    setUpdated(true);
  }, "Parola güncellenemedi. Bağlantının süresi dolmuş olabilir; yeniden bağlantı isteyin.");

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;
    // Doğrulama gönderim ÖNCESİ konuşur; kancanın hata satırını kullanır.
    const validation = passwordValidationError(password, confirmation);
    if (validation) {
      setError(validation);
      return;
    }
    void update();
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
        <h1 className="mt-2 text-[28px] font-semibold tracking-tight text-fg">Yeni parola belirle</h1>
        <p className="mt-3 text-base leading-7 text-fg-muted">
          E-postandaki yenileme bağlantısını açtıysan yeni parolanı burada kaydedebilirsin.
        </p>

        {!supabaseConfigured ? (
          <p className="mt-6 rounded-xl bg-surface-sunken px-4 py-4 text-base leading-7 text-fg-muted">
            Parola değiştirme bu ortamda henüz etkin değil. Giriş sayfasından devam edebilirsin.
          </p>
        ) : updated ? (
          <div role="status" className="mt-7 space-y-5">
            <p className="rounded-xl border border-border bg-success-bg p-5 text-base leading-7 text-success">
              Parolan güncellendi. Açık kurtarma oturumuyla derslerine devam edebilirsin.
            </p>
            <Link
              href="/courses"
              className="inline-flex min-h-11 items-center rounded-xl bg-brand px-5 text-base font-medium text-white hover:bg-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
            >
              Derslerime git
            </Link>
          </div>
        ) : (
          <form onSubmit={submit} className="mt-7 space-y-5">
            <Field label={`Yeni parola (en az ${PASSWORD_MIN_LENGTH} karakter)`}>
              {(control) => (
                <Input
                  {...control}
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  minLength={PASSWORD_MIN_LENGTH}
                  required
                />
              )}
            </Field>
            <Field label="Yeni parola tekrar">
              {(control) => (
                <Input
                  {...control}
                  type="password"
                  autoComplete="new-password"
                  value={confirmation}
                  onChange={(event) => setConfirmation(event.target.value)}
                  minLength={PASSWORD_MIN_LENGTH}
                  required
                />
              )}
            </Field>
            <Button type="submit" className="w-full" aria-disabled={busy}>
              {busy ? "Güncelleniyor…" : "Parolayı güncelle"}
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
            href="/forgot-password"
            className="inline-flex min-h-11 items-center text-sm font-medium text-brand hover:text-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            Yeni bağlantı iste
          </Link>
        </p>
      </Card>
      <p className="mt-6 text-center text-sm leading-6 text-fg-muted">DOU-Synapse · Doğuş Üniversitesi</p>
      </div>
    </main>
  );
}

