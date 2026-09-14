"use client";

/** Kampüs gezinmesi; kimlik ve profil tek mevcut bağlamdan okunur. */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ComponentType, type ReactNode } from "react";
import {
  PortalProfileProvider,
  usePortalProfile,
} from "@/components/portal/portal-profile-context";
import { ErrorNote } from "@/components/page-state";
import { BrandLockup } from "@/components/brand-mark";
import { BookIcon, HomeIcon, LogOutIcon, ShieldIcon, UserIcon, ChevronRightIcon } from "@/components/icons";
import { ThemeControl } from "@/components/theme-control";
import { subscribeAuthChanges } from "@/lib/auth-events";
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

  useEffect(() => subscribeAuthChanges(() => {
    // Sayfa hook'ları AppShell dışında da yaşayabilir. Kimlik sınırında rota
    // kapanır; önceki hesabın sayfa durumu yeni hesaba taşınmaz.
    router.replace("/");
  }), [router]);

  if (!ready || !user) return null;

  return (
    <PortalProfileProvider key={user.id} userId={user.id}>
      <AuthenticatedShell>{children}</AuthenticatedShell>
    </PortalProfileProvider>
  );
}

interface NavigationItem {
  href: string;
  label: string;
  icon: ComponentType<{ size?: number; className?: string }>;
}

function AuthenticatedShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { data: profile } = usePortalProfile();
  const [signingOut, setSigningOut] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [signOutError, setSignOutError] = useState<ErrorInfo | null>(null);
  const displayName = profile?.full_name || "Hesap";
  const displayInitial = displayName.trim().charAt(0).toLocaleUpperCase("tr-TR") || "H";
  const navigation: NavigationItem[] = [
    { href: "/dashboard", label: "Genel bakış", icon: HomeIcon },
    { href: "/courses", label: "Dersler", icon: BookIcon },
    { href: "/profile", label: "Profil", icon: UserIcon },
    ...(profile?.is_platform_admin
      ? [{ href: "/admin", label: "Bilgi İşlem", icon: ShieldIcon }]
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

  const currentSection = navigation.find((item) => pathname === item.href || pathname.startsWith(item.href + "/"))?.label ?? "Çalışma alanı";

  return (
    <div className="campus-shell min-h-[100dvh]" data-collapsed={collapsed}>
      <a href="#main-content" className="sr-only fixed left-4 top-4 z-50 rounded-xl bg-surface px-4 py-3 text-sm font-medium text-fg shadow-e2 focus:not-sr-only focus:outline-2 focus:outline-offset-2 focus:outline-brand">
        Ana içeriğe geç
      </a>
      <header className="campus-topbar sticky top-0 z-30 flex items-center gap-3 px-4 lg:px-7">
        <Link href="/dashboard" aria-label="DOU Synapse" className="flex shrink-0 items-center gap-3 rounded-xl focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand lg:w-[157px]">
          <BrandLockup tone="canvas" />
        </Link>
        <button type="button" onClick={() => setCollapsed(!collapsed)} aria-label={collapsed ? "Menüyü genişlet" : "Menüyü daralt"} aria-expanded={!collapsed} aria-controls="desktop-navigation" className="hidden h-11 w-11 items-center justify-center rounded-xl text-fg-muted transition-colors hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-brand lg:flex">
          <span aria-hidden="true" className="flex w-[18px] flex-col gap-[5px]"><span className="h-0.5 w-full rounded bg-current" /><span className="h-0.5 w-3 rounded bg-current" /><span className="h-0.5 w-full rounded bg-current" /></span>
        </button>
        <div className="hidden items-center gap-3 text-sm text-fg-subtle md:flex">
          <span>Doğuş Üniversitesi</span><ChevronRightIcon size={14} /><span className="font-medium text-fg">{currentSection}</span>
        </div>
        <div className="ml-auto flex items-center gap-2 sm:gap-4">
          <Link href="/profile" aria-label={`Profil: ${displayName}`} className="group flex h-11 items-center gap-2.5 rounded-full pr-2 transition-colors hover:bg-bg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">
            <span aria-hidden="true" className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-brand-subtle text-sm font-semibold text-brand">{displayInitial}</span>
            <span className="hidden max-w-[11rem] truncate text-sm font-medium text-fg sm:block">{displayName}</span>
          </Link>
          <button type="button" aria-disabled={signingOut} onClick={() => void handleSignOut()} className="inline-flex h-11 items-center gap-2 rounded-xl px-2 text-sm text-fg-muted transition-colors hover:bg-bg hover:text-fg focus-visible:outline-2 focus-visible:outline-brand aria-disabled:opacity-50">
            <LogOutIcon size={18} /><span className="sr-only sm:not-sr-only">{signingOut ? "Çıkılıyor…" : "Çıkış"}</span>
          </button>
        </div>
      </header>
      <aside id="desktop-navigation" className="campus-rail fixed left-0 z-20 hidden flex-col overflow-y-auto overscroll-contain border-r border-border bg-surface px-3 pb-6 pt-7 lg:flex">
        {!collapsed && <p className="mb-4 px-4 text-xs font-medium text-fg-subtle">Çalışma alanım</p>}
        <MainNavigation items={navigation} pathname={pathname} collapsed={collapsed} />
        <div className="mt-auto space-y-5 pt-8">
          {!collapsed && <>
            <div className="px-3"><p className="mb-2 text-xs text-fg-subtle">Görünüm</p><ThemeControl tone="canvas" /></div>
            <div className="mx-3 border-t border-border pt-5"><Link href="/kvkk" className="inline-flex min-h-11 items-center gap-2 text-xs text-fg-muted hover:text-fg focus-visible:outline-2 focus-visible:outline-brand"><ShieldIcon size={16} />Gizlilik ve verileriniz</Link><p className="mt-2 text-xs text-fg-subtle">DOU-Synapse<br />Ders ve sınav asistanı</p></div>
          </>}
        </div>
      </aside>
      <div className="campus-workspace">
        <div className="campus-main">
          {signOutError && <div className="mb-6"><ErrorNote message={signOutError.message} kind={signOutError.kind} requestId={signOutError.requestId} onRetry={() => void handleSignOut()} /></div>}
          <main id="main-content" tabIndex={-1} className="min-w-0 outline-none">{children}</main>
        </div>
      </div>
      <MainNavigation items={navigation} pathname={pathname} mobile />
    </div>
  );
}

function MainNavigation({ items, pathname, mobile = false, collapsed = false }: {
  items: NavigationItem[]; pathname: string; mobile?: boolean; collapsed?: boolean;
}) {
  return (
    <nav aria-label={mobile ? "Mobil ana menü" : "Ana menü"} className={mobile
      ? "campus-dock fixed inset-x-4 bottom-4 z-30 mx-auto flex max-w-md items-center justify-around gap-1 rounded-[28px] border border-border bg-surface p-1.5 lg:hidden"
      : "flex flex-col gap-2"}>
      {items.map((item) => {
        const current = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href + "/"));
        const Icon = item.icon;
        return <Link key={item.href} href={item.href} aria-current={current ? "page" : undefined} aria-label={collapsed || mobile ? item.label : undefined} title={collapsed ? item.label : undefined} className={[
          "group relative flex min-h-12 items-center rounded-2xl font-medium transition-[background,color,transform] duration-200 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand active:scale-[.98]",
          mobile ? "min-w-0 flex-1 flex-col justify-center gap-1 px-1 py-2 text-xs" : collapsed ? "justify-center px-3 py-3.5 text-sm" : "gap-3 px-4 py-3.5 text-sm",
          current ? "bg-brand-subtle text-brand" : "text-fg-muted hover:bg-bg hover:text-fg",
        ].join(" ")}>
          <Icon size={mobile ? 23 : 21} />
          {!collapsed && <span className={mobile ? "whitespace-nowrap" : undefined}>{mobile && item.href === "/dashboard" ? "Anasayfa" : item.label}</span>}
          {!mobile && !collapsed && current && <ChevronRightIcon size={15} className="ml-auto" />}
        </Link>;
      })}
    </nav>
  );
}
