"use client";

/** Academic portal entry; all sign-in availability comes from the existing auth configuration. */

import Link from "next/link";
import { ChevronRightIcon, ShieldIcon } from "@/components/icons";
import { BrandLockup } from "@/components/brand-mark";
import { SynapseIllustration } from "@/components/synapse-illustration";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { signIn, signInWithPassword, type DemoUser } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { useSubmit } from "@/lib/use-submit";
import { ErrorNote } from "@/components/page-state";
import { Button, Input } from "@/components/ui";
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
  {
    id: "33333333-3333-3333-3333-333333333333",
    email: "bilgi-islem@demo.dogus.edu.tr",
    fullName: "Bilgi İşlem",
    role: "operator",
  },
];

const QUIET_LINK =
  "inline-flex min-h-11 items-center text-sm font-medium text-fg-muted underline underline-offset-4 hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

const STUDY_STEPS = [
  { label: "Kaynak", title: "Bilgi, dersinden başlar.", description: "Eğitmeninin paylaştığı notlarla çalış. Yanıtların dayandığı sayfalara dönerek konuyu yerinde incele." },
  { label: "İpucu", title: "Cevaba adım adım yaklaş.", description: "Düşündüren ipuçlarıyla soruyu çözmeye çalış. Takıldığın noktadan devam et, kendi çözümünü geliştir." },
  { label: "Pratik", title: "Öğrendiğini kendin gör.", description: "Dersine ait soruları yanıtla ve geri bildirimleri incele. Sınav provalarıyla öğrendiklerini pekiştir." },
];

export default function LoginPage() {
  const router = useRouter();
  const [activeStep, setActiveStep] = useState(0);
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
    <main className="min-h-[100dvh] bg-bg lg:grid lg:grid-cols-[minmax(0,1.08fr)_minmax(0,1fr)]">
      <section aria-labelledby="welcome-title" className="relative flex min-w-0 flex-col border-b border-border bg-bg text-fg lg:min-h-[100dvh] lg:border-r lg:border-b-0">
        <div className="mx-auto flex w-full min-w-0 max-w-[760px] flex-1 flex-col px-6 pt-6 pb-3 sm:px-10 lg:px-12 lg:py-9 xl:px-16">
          <header className="flex min-w-0 items-center justify-between gap-4">
            <BrandLockup tone="canvas" />
            <ThemeControl tone="canvas" compact />
          </header>

          <div className="rise pt-7 lg:my-auto lg:py-8">
            <p className="mb-3 hidden text-sm font-medium text-brand lg:block">Ders ve sınav asistanın</p>
            <h1 id="welcome-title" className="max-w-[20ch] text-[2rem] font-semibold leading-[1.12] tracking-[-0.04em] [overflow-wrap:anywhere] sm:text-[2.5rem] xl:text-[2.75rem]">
              Bilgi, bağlantı<br />kurdukça büyür.
            </h1>
            <p className="mt-4 hidden max-w-[43ch] text-base leading-7 text-fg-muted lg:block">
              Ders notlarından ilk ipucuna, kendi çözümünden sınav provasına. Öğrenmenin her adımında Synapse yanında.
            </p>

            <SynapseIllustration variant="neuron" prominent className="mt-3 rounded-2xl lg:mt-5" />

            <div className="mt-5 hidden lg:block">
              <div className="flex flex-wrap gap-1 border-b border-border" role="group" aria-label="Synapse ile çalışma adımları">
                {STUDY_STEPS.map((step, index) => (
                  <button
                    key={step.label}
                    type="button"
                    aria-pressed={activeStep === index}
                    aria-controls="study-step-content"
                    onClick={() => setActiveStep(index)}
                    className={`-mb-px flex min-h-11 min-w-0 flex-1 items-center justify-center gap-2 border-b-2 px-2 py-2 text-sm font-medium motion-safe:transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${activeStep === index ? "border-brand text-brand" : "border-transparent text-fg-muted hover:text-fg"}`}
                  >
                    <span aria-hidden="true" className="text-xs text-fg-subtle">0{index + 1}</span>{step.label}
                  </button>
                ))}
              </div>
              <div id="study-step-content" className="pt-4" aria-live="polite" aria-atomic="true">
                <h2 className="text-lg font-semibold leading-snug tracking-tight text-fg">{STUDY_STEPS[activeStep].title}</h2>
                <p className="mt-2 max-w-[44ch] text-sm leading-6 text-fg-muted">{STUDY_STEPS[activeStep].description}</p>
              </div>
            </div>
          </div>

          <p className="hidden text-sm leading-6 text-fg-muted lg:block">Bilgisayar Mühendisliği · COME 492 bitirme projesi</p>
        </div>
      </section>

      <div className="flex min-w-0 flex-col px-6 pt-7 pb-8 sm:px-10 lg:justify-center lg:px-12 lg:pt-12 xl:px-16">
        <section aria-labelledby="sign-in-title" className="rise rise-1 mx-auto w-full min-w-0 max-w-[448px] py-2 lg:py-5">
          <p className="text-sm font-semibold text-brand">Çalışma alanına hoş geldin</p>
          <h2 id="sign-in-title" className="mt-3 text-[2rem] font-semibold leading-[1.1] tracking-[-0.04em] text-fg [overflow-wrap:anywhere] sm:text-[2.5rem]">Oturum aç</h2>
          <p className="mt-4 text-base leading-7 text-fg-muted">
            {supabaseConfigured
              ? "Hesabınla derslerine ve çalışma alanına ulaş."
              : devAuthEnabled ? "Demo hesaplarından biriyle çalışma alanını keşfet." : "Oturum açma henüz etkin değil."}
          </p>

          {supabaseConfigured ? (
            <form onSubmit={enterWithPassword} className="mt-8 space-y-5 [&_input]:text-base">
              <Field label="E-posta">
                {(control) => <Input {...control} className="min-h-14 rounded-xl bg-surface" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />}
              </Field>
              <Field label="Parola">
                {(control) => <Input {...control} className="min-h-14 rounded-xl bg-surface" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />}
              </Field>
              <div className="text-right"><Link href="/forgot-password" className={QUIET_LINK}>Parolamı unuttum</Link></div>
              <Button type="submit" className="min-h-14 w-full rounded-xl text-base" aria-disabled={busy}>{busy ? "Oturum açılıyor…" : "Oturum aç"}</Button>
            </form>
          ) : null}

          <div className="mt-6 space-y-2">
            <Button type="button" variant="secondary" className="min-h-14 w-full rounded-xl text-base" disabled={!entraAvailable || entra.busy} onClick={() => void entra.submit()}>
              {entra.busy ? "Yönlendiriliyor…" : "Üniversite hesabıyla devam et"}
            </Button>
            {!entraAvailable && <p className="text-sm leading-6 text-fg-muted">Üniversite hesabıyla giriş henüz etkin değil.</p>}
            {supabaseConfigured && <Link href="/verify-email" className={QUIET_LINK}>E-posta doğrulama bağlantısı iste</Link>}
          </div>

          {devAuthEnabled && (
            <section aria-labelledby="demo-users-title" className="mt-8 border-t border-border pt-6">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <h3 id="demo-users-title" className="text-base font-semibold text-fg">Demo hesapları</h3>
                <span className="text-sm text-fg-muted">Üç ayrı çalışma alanı</span>
              </div>
              <p className="mt-2 text-sm leading-6 text-fg-muted">Öğrenci, eğitmen ve teknik yönetim deneyimlerini incele.</p>
              <ul className="mt-4 space-y-3">
                {DEMO_USERS.map((user) => (
                  <li key={user.id}>
                    <button type="button" onClick={() => enter(user)} className="group flex min-h-24 w-full items-center gap-4 rounded-2xl border border-border bg-surface px-4 py-4 text-left shadow-e1 motion-safe:transition-[transform,border-color,box-shadow] hover:border-brand hover:shadow-e2 motion-safe:hover:-translate-y-0.5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand sm:px-5">
                      <span aria-hidden className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl border border-brand/15 bg-brand-subtle text-lg font-semibold text-brand">{user.fullName.charAt(0)}</span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-base font-semibold text-fg">{user.fullName}</span>
                        <span className="mt-1 block break-words text-sm text-fg-muted">{user.role === "operator" ? "Teknik yönetim" : user.role === "instructor" ? "Eğitmen" : "Öğrenci"} · {user.email}</span>
                      </span>
                      <ChevronRightIcon size={20} className="shrink-0 text-fg-muted motion-safe:transition-transform group-hover:translate-x-1 group-hover:text-brand" />
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {(error || entra.error) && <div className="mt-5"><ErrorNote message={error ?? entra.error!} /></div>}
          <div className="mt-8 border-t border-border pt-5">
            <Link href="/kvkk" className={QUIET_LINK}><ShieldIcon size={17} className="mr-2 shrink-0" />Kişisel veriler ve gizlilik</Link>
            <p className="text-sm leading-6 text-fg-muted">Verilerinin nasıl işlendiğini giriş yapmadan okuyabilirsin.</p>
          </div>
        </section>
        <footer className="mx-auto mt-7 w-full max-w-[448px] text-sm text-fg-muted">DOU-Synapse · Doğuş Üniversitesi</footer>
      </div>
    </main>
  );
}
