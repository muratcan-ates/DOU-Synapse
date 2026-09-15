"use client";

import Link from "next/link";
import { BrandLockup } from "@/components/brand-mark";
import { ShieldIcon } from "@/components/icons";
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
      <h1 className="mt-2 text-[1.75rem] font-semibold tracking-tight text-fg">E-postanı doğrula</h1>
      <p className="mt-3 text-base leading-7 text-fg-muted">Hesabına kayıtlı e-posta adresine yeni bir doğrulama bağlantısı iste.</p>
      {!supabaseConfigured ? <p className="mt-6 rounded-xl bg-surface-sunken p-5 text-base leading-7 text-fg-muted">E-posta doğrulama henüz etkin değil.</p> : sent ?
        <p role="status" className="mt-6 rounded-xl bg-success-bg p-5 text-base leading-7 text-success">Bağlantı gönderilebiliyorsa gelen kutunda görünecek. Spam klasörünü de kontrol et.</p> :
        <form className="mt-7 space-y-5" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
          <Field label="E-posta">{(control) => <Input {...control} type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />}</Field>
          <Button type="submit" className="w-full" aria-disabled={busy}>{busy ? "Gönderiliyor…" : "Doğrulama bağlantısı gönder"}</Button>
        </form>}
      {error && <div className="mt-4"><ErrorNote message={error} /></div>}
      <Link href="/" className="mt-6 inline-flex min-h-11 items-center text-sm font-medium text-brand underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">Oturum açmaya dön</Link>
    </Card>
    <p className="mt-6 text-center text-sm leading-6 text-fg-muted">DOU-Synapse · Doğuş Üniversitesi</p>
    </div>
  </main>;
}
