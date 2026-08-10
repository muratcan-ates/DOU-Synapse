"use client";

import Link from "next/link";
import { useState } from "react";
import { ErrorNote } from "@/components/page-state";
import { Field } from "@/components/field";
import { Button, Card, Input } from "@/components/ui";
import { updateCurrentPassword } from "@/lib/api";
import { PASSWORD_MIN_LENGTH, passwordValidationError } from "@/lib/auth";
import { errorMessage } from "@/lib/errors";
import { supabaseConfigured } from "@/lib/supabase";

export default function ResetPasswordPage() {
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [updated, setUpdated] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;
    const validation = passwordValidationError(password, confirmation);
    if (validation) {
      setError(validation);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await updateCurrentPassword(password);
      setUpdated(true);
    } catch (cause) {
      setError(
        errorMessage(
          cause,
          "Parola güncellenemedi. Bağlantının süresi dolmuş olabilir; yeniden bağlantı isteyin.",
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-lg items-center px-4 py-12">
      <Card className="w-full">
        <p className="text-sm font-medium text-brand">DOU-Synapse</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-fg">Yeni parola belirle</h1>
        <p className="prose-tr mt-2 text-sm text-fg-muted">
          E-postandaki yenileme bağlantısını açtıysan yeni parolanı burada kaydedebilirsin.
        </p>

        {!supabaseConfigured ? (
          <p className="prose-tr mt-6 text-sm text-fg-muted">
            Bu ekran gerçek Supabase Auth yapılandırıldığında etkinleşir.
          </p>
        ) : updated ? (
          <div role="status" className="mt-6 space-y-4">
            <p className="rounded-lg border border-border bg-bg p-4 text-sm text-fg">
              Parolan güncellendi. Açık kurtarma oturumuyla derslerine devam edebilirsin.
            </p>
            <Link
              href="/courses"
              className="inline-flex h-11 items-center rounded-lg bg-brand px-4 text-sm font-medium text-white hover:bg-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
            >
              Derslerime git
            </Link>
          </div>
        ) : (
          <form onSubmit={submit} className="mt-6 space-y-4">
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
            className="text-sm text-brand hover:text-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            Yeni bağlantı iste
          </Link>
        </p>
      </Card>
    </main>
  );
}

