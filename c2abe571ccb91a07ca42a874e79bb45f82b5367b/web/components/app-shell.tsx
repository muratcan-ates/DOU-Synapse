"use client";

/**
 * Uygulama iskeleti: 56px üst çubuk (DESIGN.md §Layout).
 * Giriş yapılmamışsa login'e yönlendirir.
 *
 * Oturum burada YENİDEN OKUNMAZ. Depoyu kendi state'ine kopyalayan her bileşen,
 * lib/session.ts'in "tek kaynak" iddiasını sessizce boşa çıkarır: rol kuralı
 * değiştiğinde (ör. asistan rolü eklendiğinde) hangi kopyanın güncellendiği
 * takip edilemez (Anayasa XI).
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { Button } from "@/components/ui";
import { signOut } from "@/lib/api";
import { useSession } from "@/lib/session";

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { user, ready } = useSession();

  /*
   * Yönlendirme `ready` beklenerek yapılır. `ready` false demek "oturum yok"
   * değil, "depo henüz okunmadı" demektir; ikisi karıştırılırsa her yenilemede
   * giriş yapmış kullanıcı da dışarı atılır. Yan etki render gövdesinde değil
   * burada durur.
   */
  useEffect(() => {
    if (ready && !user) router.replace("/");
  }, [ready, user, router]);

  if (!ready || !user) return null;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-border bg-bg/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1200px] items-center justify-between gap-4 px-4">
          <Link href="/courses" className="flex items-center gap-2">
            <span className="text-sm font-semibold text-brand">DOU</span>
            <span className="text-sm font-semibold text-fg">Synapse</span>
          </Link>
          <div className="flex items-center gap-3">
            <span className="hidden text-xs text-fg-muted sm:block">
              {user.fullName} ·{" "}
              {user.role === "instructor" ? "Eğitmen" : "Öğrenci"}
            </span>
            {/*
             * Elde çizilmiş buton kaldırıldı: 28px yüksekliğindeydi (DESIGN.md
             * §Responsive 44×44px ister) ve odak halkası yoktu — klavyeyle
             * gezen kullanıcı çıkış butonunu göremiyordu. Ortak `Button` her
             * ikisini de taşıyor; kural tek yerde durur (Anayasa XI).
             */}
            <Button
              variant="ghost"
              onClick={() => {
                signOut();
                router.replace("/");
              }}
            >
              Çıkış
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1200px] px-4 py-8">{children}</main>
    </div>
  );
}
