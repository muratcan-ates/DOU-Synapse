"use client";

/**
 * Giriş — split-screen editoryal yerleşim (taste-skill anti-center kuralı).
 * Sol panel: ürün tezi, display tipografi. Sağ panel: geliştirme kimlikleri.
 * Backend DEV_AUTH_ENABLED=true iken `Bearer dev:<uuid>` kabul eder; iki demo
 * kullanıcı supabase/seed_demo.sql ile oluşturulur. Canlıda yerini Supabase Auth alır.
 */

import { useRouter } from "next/navigation";
import { signIn, type DemoUser } from "@/lib/api";

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

  function enter(user: DemoUser) {
    signIn(user);
    router.push("/courses");
  }

  return (
    <main className="ambient grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      {/* Sol: tez paneli */}
      <section className="flex flex-col justify-between p-8 lg:p-14">
        <p className="rise text-sm font-medium tracking-wide text-brand">
          Doğuş Üniversitesi · COME 491
        </p>

        <div className="py-16 lg:py-0">
          <h1 className="rise rise-1 text-5xl font-semibold tracking-tighter text-fg md:text-6xl">
            DOU-Synapse
          </h1>
          <p className="rise rise-2 prose-tr mt-6 text-lg leading-relaxed text-fg-muted">
            Ders materyalinizle sınırlı yapay zekâ asistanı. Her cevap dayandığı
            sayfayla birlikte gelir; kaynak yoksa cevap da yoktur.
          </p>

          <dl className="rise rise-3 mt-12 grid max-w-md grid-cols-3 gap-x-6 border-t border-border pt-6">
            <div>
              <dt className="text-xs text-fg-subtle">Kaynak</dt>
              <dd className="mt-1 text-sm font-medium text-fg">Sayfa bazlı</dd>
            </div>
            <div>
              <dt className="text-xs text-fg-subtle">Kapsam</dt>
              <dd className="mt-1 text-sm font-medium text-fg">Yalnız ders</dd>
            </div>
            <div>
              <dt className="text-xs text-fg-subtle">Yöntem</dt>
              <dd className="mt-1 text-sm font-medium text-fg">Sokratik</dd>
            </div>
          </dl>
        </div>

        <p className="rise rise-3 hidden text-xs text-fg-subtle lg:block">
          Bitirme projesi · Bilgisayar Mühendisliği · 2026
        </p>
      </section>

      {/* Sağ: giriş paneli */}
      <section className="flex items-center border-t border-border bg-surface/60 p-8 backdrop-blur-sm lg:border-t-0 lg:border-l lg:p-14">
        <div className="w-full max-w-sm">
          <h2 className="rise text-sm font-medium text-fg">Oturum aç</h2>
          <p className="rise rise-1 mt-1 text-xs text-fg-subtle">
            Geliştirme ortamı girişi; canlıda üniversite hesabı kullanılır
          </p>

          <div className="mt-6 space-y-3">
            {DEMO_USERS.map((user, index) => (
              <button
                key={user.id}
                onClick={() => enter(user)}
                className={`rise rise-${index + 2} group flex w-full items-center gap-4 rounded-xl border border-border bg-surface p-4 text-left transition-[border,box-shadow] duration-200 hover:border-border-strong hover:shadow-[0_2px_8px_rgba(28,25,23,0.04)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand`}
              >
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-brand-subtle font-mono text-sm font-semibold text-brand">
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
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
