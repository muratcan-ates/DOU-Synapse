"use client";

/**
 * Giriş — split-screen editoryal yerleşim (taste-skill anti-center kuralı).
 * Sol panel: ürün tezi, display tipografi. Sağ panel: geliştirme kimlikleri.
 * Backend DEV_AUTH_ENABLED=true iken `Bearer dev:<uuid>` kabul eder; iki demo
 * kullanıcı supabase/seed_demo.sql ile oluşturulur. Canlıda yerini Supabase Auth alır.
 */

import Link from "next/link";
import { BrandLockup } from "@/components/brand-mark";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { signIn, signInWithPassword, type DemoUser } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { useSubmit } from "@/lib/use-submit";
import { ErrorNote } from "@/components/page-state";
import { Button, Input } from "@/components/ui";
import { Field } from "@/components/field";
import { supabaseConfigured } from "@/lib/supabase";

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

export default function LoginPage() {
  const router = useRouter();
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
    <main className="grid min-h-[100dvh] lg:grid-cols-[minmax(0,1.18fr)_minmax(28rem,0.82fr)]">
      {/* Sol: ürün tezi ve tek kanıt zinciri. */}
      <section className="flex flex-col justify-between border-b border-border p-8 lg:border-r lg:border-b-0 lg:p-14">
        <div className="rise border-l-2 border-brand pl-4">
          <div>
            <BrandLockup tone="canvas" className="mb-2" />
            <p className="text-sm font-medium text-fg">Doğuş Üniversitesi</p>
            <p className="text-xs text-fg-subtle">COME 492 · Bitirme projesi</p>
          </div>
        </div>

        <div className="py-16 lg:py-12">
          <p className="rise rise-1 mb-4 max-w-md text-sm font-medium text-brand">
            Kaynağı görünen ders çalışma alanı
          </p>
          <h1 className="rise rise-1 max-w-2xl text-5xl font-semibold tracking-tighter text-fg md:text-6xl">
            DOU-Synapse
          </h1>
          <p className="rise rise-2 prose-tr mt-6 text-lg leading-relaxed text-fg-muted">
            Ders materyalinizle sınırlı yapay zekâ asistanı. Her cevap dayandığı
            sayfayla birlikte gelir; kaynak yoksa cevap da yoktur.
          </p>

          <section
            aria-labelledby="evidence-rail-title"
            className="rise rise-3 mt-12 max-w-2xl border-y border-border py-5"
          >
            <div className="grid gap-5 md:grid-cols-[11rem_1fr] md:items-start">
              <div>
                <p className="font-mono text-xs text-brand">Kaynak zinciri</p>
                <h2 id="evidence-rail-title" className="mt-1 text-sm font-medium text-fg">
                  Bir yanıtın izlediği yol
                </h2>
              </div>
              <ol className="grid gap-3 text-sm text-fg-muted sm:grid-cols-3 sm:gap-0">
                <li className="border-border sm:border-l sm:pl-4">
                  <span className="block font-mono text-xs text-fg-subtle">01</span>
                  <span className="mt-1 block text-fg">Ders kaynağını bulur</span>
                </li>
                <li className="border-border sm:border-l sm:pl-4">
                  <span className="block font-mono text-xs text-fg-subtle">02</span>
                  <span className="mt-1 block text-fg">İlgili sayfayı gösterir</span>
                </li>
                <li className="border-border sm:border-l sm:pl-4">
                  <span className="block font-mono text-xs text-fg-subtle">03</span>
                  <span className="mt-1 block text-fg">Adım adım çalıştırır</span>
                </li>
              </ol>
            </div>
          </section>
        </div>

        <p className="rise rise-3 hidden text-xs text-fg-subtle lg:block">
          Bilgisayar Mühendisliği · 2026
        </p>
      </section>

      {/* Sağ: giriş paneli. Panel ayrımı kenarlık + hafif yüzey tonuyla kurulur. */}
      <section className="flex items-center bg-surface p-8 lg:p-14">
        <div className="w-full max-w-sm">
          <p className="rise font-mono text-xs text-brand">Ders alanına giriş</p>
          <h2 className="rise rise-1 mt-2 text-2xl font-semibold tracking-tight text-fg">
            Oturum aç
          </h2>
          <p className="rise rise-1 mt-2 text-sm text-fg-muted">
            {supabaseConfigured
              ? "Üniversite hesabınızla devam edin"
              : "Geliştirme ortamı girişi; canlıda üniversite hesabı kullanılır"}
          </p>

          {supabaseConfigured ? (
            <form onSubmit={enterWithPassword} className="mt-6 space-y-4">
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
              <Field label="Parola">
                {(control) => (
                  <Input
                    {...control}
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                  />
                )}
              </Field>
              <Button type="submit" className="w-full" aria-disabled={busy}>
                {busy ? "Oturum açılıyor…" : "Oturum aç"}
              </Button>
              <p className="text-right">
                <Link
                  href="/forgot-password"
                  className="text-xs text-brand hover:text-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                >
                  Parolamı unuttum
                </Link>
              </p>
            </form>
          ) : (
            /* Kimlik seçenekleri bir listedir: ekran okuyucu kaç seçenek
               olduğunu peşinen söyler. */
            <ul className="mt-6 divide-y divide-border overflow-hidden rounded-lg border border-border bg-bg">
              {DEMO_USERS.map((user, index) => (
                <li key={user.id}>
                  <button
                    onClick={() => enter(user)}
                    className={`rise rise-${index + 2} group flex min-h-16 w-full items-center gap-4 bg-surface px-4 py-3 text-left transition-colors duration-200 hover:bg-bg focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-brand`}
                  >
                    <span
                      aria-hidden
                      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-subtle font-mono text-sm font-semibold text-brand"
                    >
                      {user.fullName.charAt(0)}
                    </span>
                    <span className="min-w-0">
                      <span className="block text-sm font-medium text-fg">
                        {user.fullName}
                      </span>
                      <span className="mt-0.5 block text-xs text-fg-muted">
                        {user.role === "instructor" ? "Eğitmen" : "Öğrenci"} ·{" "}
                        {user.email}
                      </span>
                    </span>
                    <span
                      aria-hidden
                      className="ml-auto text-fg-subtle transition-transform duration-200 group-hover:translate-x-0.5"
                    >
                      →
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {error && (
            <div className="mt-4">
              <ErrorNote message={error} />
            </div>
          )}

          {/*
            Aydınlatma metni GİRİŞTEN ÖNCE erişilebilir. Kişisel verisinin nasıl
            işleneceğini öğrenmek için önce hesap açmak zorunda kalmak, metnin
            amacını tersine çevirirdi.
          */}
          <p className="mt-8 text-xs text-fg-muted">
            <Link
              href="/kvkk"
              className="underline underline-offset-2 hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
            >
              KVKK aydınlatma metni
            </Link>{" "}
            hangi verilerinizin işlendiğini, nerede saklandığını ve kimlerle
            paylaşıldığını açıklar.
          </p>
        </div>
      </section>
    </main>
  );
}
