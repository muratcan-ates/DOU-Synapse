"use client";

/**
 * Giriş — split-screen editoryal yerleşim (taste-skill anti-center kuralı).
 * Sol panel: ürün tezi, display tipografi. Sağ panel: kanvas üstünde yüzen tek
 * oturum kartı. Backend DEV_AUTH_ENABLED=true iken `Bearer dev:<uuid>` kabul
 * eder; iki demo kullanıcı supabase/seed_demo.sql ile oluşturulur. Canlıda
 * yerini Supabase Auth alır.
 *
 * 14 Eylül 2026 turu (DESIGN.md §Components "Aksan disiplini ve katman"):
 * kırmızı bu ekranda yalnız marka işareti ve "Oturum aç" düğmesindedir. Kırmızı
 * blok rayı, kırmızı üst satır, kırmızı mono avatar ve kırmızı satır içi
 * bağlantılar kaldırıldı; sütun ayrımı çizgiyle değil kartın gölgesiyle kurulur.
 */

import Link from "next/link";
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

/** Bir yanıtın izlediği üç adım; sıra numarası rakamdır, kod değil. */
const EVIDENCE_STEPS: { step: string; text: string }[] = [
  { step: "01", text: "Ders kaynağını bulur" },
  { step: "02", text: "İlgili sayfayı gösterir" },
  { step: "03", text: "Adım adım çalıştırır" },
];

/** Muted satır içi bağlantı: kırmızı yalnız birincil eylemde kalır. */
const QUIET_LINK =
  "text-fg-muted underline underline-offset-2 hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

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
    <main className="grid min-h-[100dvh] lg:grid-cols-[minmax(0,1.18fr)_minmax(28rem,0.82fr)]">
      {/* Sol: ürün tezi ve tek kanıt zinciri. */}
      <section className="flex flex-col justify-between p-8 lg:p-14">
        <div className="rise">
          <BrandLockup tone="canvas" className="mb-2" />
          <p className="text-sm font-medium text-fg">Doğuş Üniversitesi</p>
          <p className="text-xs text-fg-subtle">COME 492 · Bitirme projesi</p>
        </div>

        <div className="py-16 lg:py-12">
          <p className="rise rise-1 mb-4 max-w-md text-sm font-medium text-fg-muted">
            Kaynağı görünen ders çalışma alanı
          </p>
          <h1 className="rise rise-1 max-w-2xl text-5xl font-semibold tracking-tighter text-fg md:text-6xl">
            DOU-Synapse
          </h1>
          <p className="rise rise-2 prose-tr mt-6 text-lg leading-relaxed text-fg-muted">
            Ders materyalinizle sınırlı yapay zekâ asistanı. Her cevap dayandığı
            sayfayla birlikte gelir; kaynak yoksa cevap da yoktur.
          </p>

          {/*
           * Üç adım üç çukur kart: kanvasın altında duran açıklama bloğu.
           * Önceki hâl `border-y` + sütun başı saç çizgileriydi ve portalın
           * "çizgiyle bölünmüş ızgara" gramerini tekrarlıyordu.
           */}
          <section
            aria-labelledby="evidence-rail-title"
            className="rise rise-3 mt-12 max-w-2xl"
          >
            <p className="text-xs font-medium text-fg-muted">Kaynak zinciri</p>
            <h2 id="evidence-rail-title" className="mt-1 text-sm font-medium text-fg">
              Bir yanıtın izlediği yol
            </h2>
            <ol className="mt-4 grid gap-3 sm:grid-cols-3">
              {EVIDENCE_STEPS.map(({ step, text }) => (
                <li key={step}>
                  <Card variant="soft" className="h-full">
                    <span className="block text-xs tabular-nums text-fg-subtle">{step}</span>
                    <span className="mt-2 block text-sm text-fg">{text}</span>
                  </Card>
                </li>
              ))}
            </ol>
          </section>
        </div>

        {/*
         * Tema seçici giriş ekranında da var: kullanıcı ürünün ilk karesinde
         * karar verebilsin, gece modu için önce giriş yapmak zorunda kalmasın.
         */}
        <div className="rise rise-3 hidden items-center gap-4 lg:flex">
          <p className="text-xs text-fg-subtle">Bilgisayar Mühendisliği · 2026</p>
          <div className="ml-auto w-48">
            <ThemeControl tone="canvas" />
          </div>
        </div>
      </section>

      {/* Sağ: oturum kartı. Katmanı gölge taşır; kenarlık ya da ayrı yüzey tonu yok. */}
      <section className="flex items-center p-8 lg:p-14">
        <Card className="mx-auto w-full max-w-md sm:p-8">
          <p className="rise text-xs font-medium text-fg-muted">Ders alanına giriş</p>
          <h2 className="rise rise-1 mt-2 text-2xl font-semibold tracking-tight text-fg">
            Oturum aç
          </h2>
          <p className="rise rise-1 mt-2 text-sm text-fg-muted">
            {supabaseConfigured
              ? "Üniversite hesabınızla devam edin"
              : devAuthEnabled ? "Geliştirme ortamı girişi; canlıda üniversite hesabı kullanılır" : "Oturum açma henüz yapılandırılmadı"}
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
              {/* Sayfadaki tek kırmızı eylem. */}
              <Button type="submit" className="w-full" aria-disabled={busy}>
                {busy ? "Oturum açılıyor…" : "Oturum aç"}
              </Button>
              <p className="text-right">
                <Link href="/forgot-password" className={`text-xs ${QUIET_LINK}`}>
                  Parolamı unuttum
                </Link>
              </p>
            </form>
          ) : null}

          <div className="mt-5 space-y-3">
            <Button type="button" variant="secondary" className="w-full" disabled={!entraAvailable || entra.busy} onClick={() => void entra.submit()}>
              {entra.busy ? "Yönlendiriliyor…" : "Üniversite hesabıyla devam et"}
            </Button>
            {!entraAvailable && <p className="text-xs text-fg-muted">Üniversite hesabıyla giriş henüz etkin değil.</p>}
            {supabaseConfigured && <Link href="/verify-email" className={`block text-sm ${QUIET_LINK}`}>E-posta doğrulama bağlantısı iste</Link>}
          </div>

          {devAuthEnabled && (
            /* Kimlik seçenekleri bir listedir: ekran okuyucu kaç seçenek
               olduğunu peşinen söyler. Satırlar kart içinde `divide-y`;
               ikinci bir çerçeve yok. */
            <ul className="mt-6 divide-y divide-border">
              {DEMO_USERS.map((user, index) => (
                <li key={user.id}>
                  <button
                    onClick={() => enter(user)}
                    className={`rise rise-${index + 2} group flex min-h-16 w-full items-center gap-4 rounded-lg px-2 py-3 text-left transition-colors duration-200 hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-brand`}
                  >
                    <span
                      aria-hidden
                      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-surface-sunken text-sm font-semibold text-fg"
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

          {(error || entra.error) && (
            <div className="mt-4">
              <ErrorNote message={error ?? entra.error!} />
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
              Kişisel veriler ve gizlilik
            </Link>{" "}
            hangi verilerinizin işlendiğini, nerede saklandığını ve kimlerle
            paylaşıldığını açıklar.
          </p>
        </Card>
      </section>
    </main>
  );
}
