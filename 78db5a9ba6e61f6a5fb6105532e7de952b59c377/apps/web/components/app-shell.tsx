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
import { useEffect, useState, type ReactNode } from "react";
import {
  PortalProfileProvider,
  usePortalProfile,
} from "@/components/portal/portal-profile-context";
import { ErrorNote } from "@/components/page-state";
import { Button } from "@/components/ui";
import { signOutCurrent } from "@/lib/api";
import { describeError, type ErrorInfo } from "@/lib/errors";
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
    <PortalProfileProvider key={user.id} userId={user.id}>
      <AuthenticatedShell>{children}</AuthenticatedShell>
    </PortalProfileProvider>
  );
}

function AuthenticatedShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { data: profile } = usePortalProfile();
  const [signingOut, setSigningOut] = useState(false);
  const [signOutError, setSignOutError] = useState<ErrorInfo | null>(null);
  const displayName = profile?.full_name || "Hesap";
  const displayInitial = displayName.trim().charAt(0).toLocaleUpperCase("tr-TR") || "H";
  const navigation = [
    { href: "/dashboard", label: "Genel bakış" },
    { href: "/courses", label: "Dersler" },
    { href: "/profile", label: "Profil" },
    ...(profile?.is_platform_admin
      ? [{ href: "/admin", label: "Bilgi İşlem" }]
      : []),
  ];

  async function handleSignOut(): Promise<void> {
    if (signingOut) return;
    setSigningOut(true);
    setSignOutError(null);
    try {
      await signOutCurrent();
      router.replace("/");
    } catch (cause) {
      setSignOutError(
        describeError(
          cause,
          "Oturum kapatılamadı. Bağlantınızı kontrol edip tekrar deneyin.",
        ),
      );
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <div className="min-h-[100dvh]">
      <a
        href="#main-content"
        className="sr-only fixed left-4 top-4 z-20 rounded-lg bg-surface px-4 py-3 text-sm font-medium text-fg shadow-sm focus:not-sr-only focus:outline-2 focus:outline-offset-2 focus:outline-brand"
      >
        Ana içeriğe geç
      </a>
      <header className="sticky top-0 z-10 border-b border-border bg-surface">
        <div className="mx-auto flex h-16 max-w-[1200px] items-center gap-4 px-4">
          <Link
            href="/dashboard"
            aria-label="DOU Synapse"
            className="flex min-h-11 shrink-0 items-center gap-3 rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            <span
              aria-hidden="true"
              className="grid h-9 w-9 place-items-center rounded-md bg-brand font-mono text-sm font-semibold text-bg"
            >
              D
            </span>
            <span aria-hidden="true" className="leading-none">
              <span className="block font-mono text-xs font-medium tracking-wide text-brand">
                DOU
              </span>
              <span className="mt-1 block text-sm font-semibold tracking-tight text-fg">
                Synapse
              </span>
            </span>
          </Link>

          <PortalNavigation items={navigation} pathname={pathname} />

          <div className="ml-auto flex min-w-0 items-center gap-2 sm:gap-3">
            <Link
              href="/profile"
              aria-label={`Profil: ${displayName}`}
              className="flex min-h-11 max-w-44 items-center gap-2 rounded-lg px-2 text-xs font-medium text-fg-muted hover:bg-bg hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
            >
              <span
                aria-hidden="true"
                className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-brand-subtle font-mono text-xs font-semibold text-brand"
              >
                {displayInitial}
              </span>
              <span className="hidden truncate sm:block">{displayName}</span>
            </Link>
            <Button
              variant="ghost"
              aria-disabled={signingOut}
              onClick={() => void handleSignOut()}
            >
              {signingOut ? "Çıkılıyor…" : "Çıkış"}
            </Button>
          </div>
        </div>
        <PortalNavigation items={navigation} pathname={pathname} mobile />
      </header>
      {signOutError && (
        <div className="border-b border-danger/30 bg-danger-bg">
          <div className="mx-auto max-w-[1200px] px-4 py-3">
            <ErrorNote
              message={signOutError.message}
              kind={signOutError.kind}
              requestId={signOutError.requestId}
              onRetry={() => void handleSignOut()}
            />
          </div>
        </div>
      )}
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
          ? "mx-auto flex max-w-[1200px] gap-4 overflow-x-auto border-t border-border px-4 md:hidden"
          : "hidden h-full items-stretch gap-5 md:flex"
      }
    >
      {items.map((item) => {
        const current =
          pathname === item.href ||
          (item.href !== "/dashboard" && pathname.startsWith(item.href + "/"));
        const className = current
          ? "inline-flex min-h-11 shrink-0 items-center whitespace-nowrap border-b-2 border-brand px-1 text-xs font-medium text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          : "inline-flex min-h-11 shrink-0 items-center whitespace-nowrap border-b-2 border-transparent px-1 text-xs font-medium text-fg-muted hover:border-border-strong hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";
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
