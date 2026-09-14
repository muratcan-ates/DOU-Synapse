"use client";

import Link from "next/link";
import { useState } from "react";
import { resendVerificationEmail } from "@/lib/auth-session";
import { supabaseConfigured } from "@/lib/supabase";
import { useSubmit } from "@/lib/use-submit";
import { Field } from "@/components/field";
import { Button, Card, Input } from "@/components/ui";
import { ErrorNote } from "@/components/page-state";

export default function VerifyEmailPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const { busy, error, submit } = useSubmit(async () => {
    await resendVerificationEmail(email.trim());
    setSent(true);
  }, "Doğrulama bağlantısı gönderilemedi. Bir süre sonra tekrar deneyin.");

  return <main className="mx-auto flex min-h-screen max-w-lg items-center px-4 py-12">
    <Card className="w-full">
      <p className="text-sm font-medium text-brand">DOU-Synapse</p>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight text-fg">E-postanı doğrula</h1>
      <p className="mt-2 text-sm text-fg-muted">Hesabına kayıtlı e-posta adresine yeni bir doğrulama bağlantısı iste.</p>
      {!supabaseConfigured ? <p className="mt-6 text-sm text-fg-muted">E-posta doğrulama henüz etkin değil.</p> : sent ?
        <p role="status" className="mt-6 text-sm text-fg">Bağlantı gönderilebiliyorsa gelen kutunda görünecek. Spam klasörünü de kontrol et.</p> :
        <form className="mt-6 space-y-4" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
          <Field label="E-posta">{(control) => <Input {...control} type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />}</Field>
          <Button type="submit" className="w-full" aria-disabled={busy}>{busy ? "Gönderiliyor…" : "Doğrulama bağlantısı gönder"}</Button>
        </form>}
      {error && <div className="mt-4"><ErrorNote message={error} /></div>}
      <Link href="/" className="mt-6 inline-block text-sm text-brand underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">Oturum açmaya dön</Link>
    </Card>
  </main>;
}
