"use client";

/** Academic portal entry; all sign-in availability comes from the existing auth configuration. */

import Link from "next/link";
import { BookIcon, ChevronRightIcon, FileIcon, ShieldIcon } from "@/components/icons";
import { BrandLockup } from "@/components/brand-mark";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { signIn, signInWithPassword, type DemoUser } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { useSubmit } from "@/lib/use-submit";
import { ErrorNote } from "@/components/page-state";
import { Button, Card, Input } from "@/components/ui";
import { Field } from "@/components/field";
import { ThemeControl } from "@/components/theme-control";
import { supabaseConfigured } from "@/lib/supabase";
import { entraTenantId, isDevAuthEnabled } from "@/lib/auth-config";
import { signInWithEntra } from "@/lib/auth-session";

const DEMO_USERS: DemoUser[] = [
  {
    id: "11111111-1111-1111-1111-111111111111",
    email: "ayse@dogus.edu.tr",
    fullName: "Ayşe Hoca",
    role: "instructor",
  },
  {
    id: "22222222-2222-2222-2222-222222222222",
    email: "burak@dogus.edu.tr",
    fullName: "Burak Yılmaz",
    role: "student",
  },
];

const QUIET_LINK =
  "inline-flex min-h-11 items-center text-sm font-medium text-fg-muted underline underline-offset-4 hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

export default function LoginPage() {
  const router = useRouter();
  const devAuthEnabled = isDevAuthEnabled();
  const entraAvailable = supabaseConfigured && entraTenantId() !== null;
  const entra = useSubmit(signInWithEntra, "Üniversite hesabıyla giriş başlatılamadı.");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { busy, error, setError, submit } = useSubmit(async () => {
    await signInWithPassword(email.trim(), password);
    router.push("/dashboard");
  }, "Oturum açılamadı. E-posta ve parolanızı kontrol edin.");

  function enter(user: DemoUser) {
    /*
     * `signIn` localStorage'a yazar ve bu yazma GERÇEKTEN patlayabilir: site
     * verileri engellenmiş bir tarayıcıda `setItem` SecurityError atar. Sarmasız
     * hâlinde düğme sessizce hiçbir şey yapmıyordu — etkin görünüp iş yapmayan
     * yüzey kusurdur (Anayasa XI). Metin `errorMessage` üzerinden geçer: bu bir
     * API hatası değil, o yüzden yedek cümle kullanılır.
     */
    try {
      signIn(user);
    } catch (e) {
      setError(
        errorMessage(
          e,
          "Oturum bilgisi tarayıcıya yazılamadı. Site verilerine izin verip tekrar deneyin.",
        ),
      );
      return;
    }
    router.push("/dashboard");
  }

  function enterWithPassword(event: React.FormEvent) {
    event.preventDefault();
    // Çift gönderim kapısı `useSubmit`'te: busy iken çağrı yok sayılır.
    void submit();
  }

  return (
    <main className="flex min-h-[100dvh] flex-col bg-bg">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex min-h-[76px] max-w-[1200px] flex-wrap items-center justify-between gap-4 px-5 py-4 sm:px-8">
          <div className="flex items-center gap-4">
            <BrandLockup tone="canvas" />
            <div className="hidden border-l border-border pl-4 sm:block">
              <p className="text-sm font-semibold text-fg">Doğuş Üniversitesi</p>
              <p className="text-[13px] text-fg-muted">Ders ve sınav asistanı</p>
            </div>
          </div>
          <div className="w-[174px]"><ThemeControl tone="canvas" /></div>
        </div>
      </header>

      <div className="mx-auto grid w-full max-w-[1200px] flex-1 items-start gap-7 px-5 py-8 sm:px-8 sm:py-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-center lg:gap-14 lg:py-16">
        <section aria-labelledby="welcome-title" className="rise order-2 lg:order-1">
          <span className="inline-flex items-center gap-2 rounded-full bg-brand-subtle px-3 py-1.5 text-[13px] font-semibold text-brand">
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-brand" /> Öğrenme alanın
          </span>
          <h1 id="welcome-title" className="mt-5 max-w-[18ch] text-[30px] leading-tight font-semibold tracking-tight text-fg sm:text-[32px]">
            Derslerine kaldığın yerden devam et.
          </h1>
          <p className="mt-4 max-w-lg text-base leading-7 text-fg-muted">
            Ders notlarını incele, sorular üzerinde çalış ve sınava hazırlan.
            Synapse, eğitmeninin paylaştığı kaynaklarla çalışmana eşlik eder.
          </p>

          <div className="mt-7 overflow-hidden rounded-[20px] border border-border bg-surface shadow-e1">
            {[
              { icon: FileIcon, title: "Kaynağıyla birlikte öğren", description: "Yanıtların dayandığı ders sayfalarına ulaş." },
              { icon: BookIcon, title: "Adım adım pratik yap", description: "İpuçlarıyla düşün, cevabını değerlendir." },
              { icon: ShieldIcon, title: "Sınava hazırlan", description: "Dersine ait sorular ve sınav provalarıyla çalış." },
            ].map(({ icon: Icon, title, description }) => (
              <div key={title} className="flex gap-4 border-b border-border px-5 py-5 last:border-0 sm:px-6">
                <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-surface-sunken text-fg-muted"><Icon size={22} /></span>
                <div>
                  <h2 className="text-base font-semibold text-fg">{title}</h2>
                  <p className="mt-1 text-sm leading-6 text-fg-muted">{description}</p>
                </div>
              </div>
            ))}
          </div>
          <p className="mt-5 text-sm leading-6 text-fg-muted">Bilgisayar Mühendisliği · COME 492 bitirme projesi</p>
        </section>

        <section aria-labelledby="sign-in-title" className="rise rise-1 order-1 min-w-0 lg:order-2">
          <Card className="sm:p-8">
            <p className="text-sm font-medium text-brand">DOU-Synapse</p>
            <h2 id="sign-in-title" className="mt-2 text-[28px] leading-tight font-semibold tracking-tight text-fg">Oturum aç</h2>
            <p className="mt-3 text-base leading-7 text-fg-muted">
              {supabaseConfigured
                ? "Hesabınla derslerine ve çalışma alanına ulaş."
                : devAuthEnabled ? "Demo hesaplarından biriyle çalışma alanını keşfet." : "Oturum açma henüz etkin değil."}
            </p>

            {supabaseConfigured ? (
              <form onSubmit={enterWithPassword} className="mt-7 space-y-5">
                <Field label="E-posta">
                  {(control) => <Input {...control} type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />}
                </Field>
                <Field label="Parola">
                  {(control) => <Input {...control} type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />}
                </Field>
                <div className="text-right"><Link href="/forgot-password" className={QUIET_LINK}>Parolamı unuttum</Link></div>
                <Button type="submit" className="w-full" aria-disabled={busy}>{busy ? "Oturum açılıyor…" : "Oturum aç"}</Button>
              </form>
            ) : null}

            <div className="mt-6 space-y-2">
              <Button type="button" variant="secondary" className="w-full" disabled={!entraAvailable || entra.busy} onClick={() => void entra.submit()}>
                {entra.busy ? "Yönlendiriliyor…" : "Üniversite hesabıyla devam et"}
              </Button>
              {!entraAvailable && <p className="text-sm leading-6 text-fg-muted">Üniversite hesabıyla giriş henüz etkin değil.</p>}
              {supabaseConfigured && <Link href="/verify-email" className={QUIET_LINK}>E-posta doğrulama bağlantısı iste</Link>}
            </div>

            {devAuthEnabled && (
              <section aria-labelledby="demo-users-title" className="mt-7 border-t border-border pt-5">
                <h3 id="demo-users-title" className="text-sm font-semibold text-fg">Demo hesapları</h3>
                <p className="mt-1 text-sm leading-6 text-fg-muted">Öğrenci veya eğitmen görünümünü incele.</p>
                <ul className="mt-3 space-y-2">
                  {DEMO_USERS.map((user) => (
                    <li key={user.id}>
                      <button onClick={() => enter(user)} className="group flex min-h-20 w-full items-center gap-3 rounded-xl border border-border bg-bg px-4 py-3 text-left motion-safe:transition-colors hover:border-border-strong hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">
                        <span aria-hidden className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-surface text-base font-semibold text-brand">{user.fullName.charAt(0)}</span>
                        <span className="min-w-0 flex-1">
                          <span className="block text-base font-semibold text-fg">{user.fullName}</span>
                          <span className="mt-0.5 block text-sm text-fg-muted">{user.role === "instructor" ? "Eğitmen" : "Öğrenci"} · {user.email}</span>
                        </span>
                        <ChevronRightIcon className="shrink-0 text-fg-muted motion-safe:transition-transform group-hover:translate-x-0.5" />
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            {(error || entra.error) && <div className="mt-5"><ErrorNote message={error ?? entra.error!} /></div>}
            <div className="mt-6 border-t border-border pt-4">
              <Link href="/kvkk" className={QUIET_LINK}><ShieldIcon size={17} className="mr-2 shrink-0" />Kişisel veriler ve gizlilik</Link>
              <p className="text-sm leading-6 text-fg-muted">Verilerinin nasıl işlendiğini giriş yapmadan okuyabilirsin.</p>
            </div>
          </Card>
        </section>
      </div>
      <footer className="mx-auto w-full max-w-[1200px] px-5 pb-7 text-sm text-fg-muted sm:px-8">DOU-Synapse · Doğuş Üniversitesi</footer>
    </main>
  );
}
