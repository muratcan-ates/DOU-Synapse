"use client";

/**
 * Uygulama iskeleti: masaüstünde 64px üst çubuk, mobilde yatay ana menü.
 * Giriş yapılmamışsa login'e yönlendirir.
 *
 * Oturum burada YENİDEN OKUNMAZ. Depoyu kendi state'ine kopyalayan her bileşen,
 * lib/session.ts'in "tek kaynak" iddiasını sessizce boşa çıkarır: rol kuralı
 * değiştiğinde (ör. asistan rolü eklendiğinde) hangi kopyanın güncellendiği
 * takip edilemez (Anayasa XI).
 */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import {
  PortalProfileProvider,
  usePortalProfile,
} from "@/components/portal/portal-profile-context";
import { Button } from "@/components/ui";
import { signOutCurrent } from "@/lib/api";
import { useSession } from "@/lib/session";

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { user, ready } = useSession();

  /*
   * Yönlendirme ready beklenerek yapılır. ready false demek "oturum yok"
   * değil, "depo henüz okunmadı" demektir; ikisi karıştırılırsa her yenilemede
   * giriş yapmış kullanıcı da dışarı atılır. Yan etki render gövdesinde değil
   * burada durur.
   */
  useEffect(() => {
    if (ready && !user) router.replace("/");
  }, [ready, user, router]);

  if (!ready || !user) return null;

  return (
    <PortalProfileProvider>
      <AuthenticatedShell>{children}</AuthenticatedShell>
    </PortalProfileProvider>
  );
}

function AuthenticatedShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { data: profile } = usePortalProfile();
  const displayName = profile?.full_name || "Hesap";
  const navigation = [
    { href: "/dashboard", label: "Genel bakış" },
    { href: "/courses", label: "Dersler" },
    { href: "/profile", label: "Profil" },
    ...(profile?.is_platform_admin
      ? [{ href: "/admin", label: "Sistem yönetimi" }]
      : []),
  ];

  return (
    <div className="min-h-[100dvh]">
      <a
        href="#main-content"
        className="sr-only fixed left-4 top-4 z-20 rounded-lg bg-surface px-4 py-3 text-sm font-medium text-fg shadow-sm focus:not-sr-only focus:outline-2 focus:outline-offset-2 focus:outline-brand"
      >
        Ana içeriğe geç
      </a>
      <header className="sticky top-0 z-10 border-b border-border bg-bg/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[1200px] items-center gap-4 px-4">
          <Link
            href="/dashboard"
            className="flex shrink-0 items-center gap-2 rounded-sm focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand"
          >
            <span className="text-sm font-semibold text-brand">DOU</span>
            <span className="text-sm font-semibold text-fg">Synapse</span>
          </Link>

          <PortalNavigation items={navigation} pathname={pathname} />

          <div className="ml-auto flex min-w-0 items-center gap-2 sm:gap-3">
            <Link
              href="/profile"
              className="max-w-36 truncate rounded-lg px-2 py-2 text-xs font-medium text-fg-muted hover:bg-surface hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
            >
              {displayName}
            </Link>
            <Button
              variant="ghost"
              onClick={() => {
                void signOutCurrent();
                router.replace("/");
              }}
            >
              Çıkış
            </Button>
          </div>
        </div>
        <PortalNavigation items={navigation} pathname={pathname} mobile />
      </header>
      <main id="main-content" tabIndex={-1} className="mx-auto max-w-[1200px] px-4 py-8">
        {children}
      </main>
    </div>
  );
}

interface NavigationItem {
  href: string;
  label: string;
}

function PortalNavigation({
  items,
  pathname,
  mobile = false,
}: {
  items: NavigationItem[];
  pathname: string;
  mobile?: boolean;
}) {
  return (
    <nav
      aria-label={mobile ? "Mobil ana menü" : "Ana menü"}
      className={
        mobile
          ? "mx-auto flex max-w-[1200px] gap-1 overflow-x-auto border-t border-border px-4 py-2 md:hidden"
          : "hidden items-center gap-1 md:flex"
      }
    >
      {items.map((item) => {
        const current =
          pathname === item.href ||
          (item.href !== "/dashboard" && pathname.startsWith(item.href + "/"));
        const className = current
          ? "min-h-11 shrink-0 whitespace-nowrap rounded-lg bg-brand-subtle px-3 py-2 text-xs font-medium text-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          : "min-h-11 shrink-0 whitespace-nowrap rounded-lg px-3 py-2 text-xs font-medium text-fg-muted hover:bg-surface hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={current ? "page" : undefined}
            className={className}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
