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
import { BrandLockup, BrandMark } from "@/components/brand-mark";
import { BookIcon, HomeIcon, LogOutIcon, ShieldIcon, UserIcon, ChevronRightIcon, SettingsIcon } from "@/components/icons";
import { QuickSwitch } from "@/components/quick-switch";
import { CampusMotion } from "@/components/campus-motion";
import { ThemeControl } from "@/components/theme-control";
import { SynapseFooter } from "@/components/synapse-footer";
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
  const teachingMemberships = profile?.memberships.filter((membership) => membership.role === "instructor") ?? [];
  const learningMemberships = profile?.memberships.filter((membership) => membership.role === "student") ?? [];
  const isPlatformAdmin = profile?.is_platform_admin === true;
  const isOperationsOnly = isPlatformAdmin && profile.memberships.length === 0;
  const areaLabel = pathname.startsWith("/admin") && isPlatformAdmin
    ? "Bilgi İşlem alanı"
    : teachingMemberships.length > 0 && learningMemberships.length > 0
      ? "Çalışma alanlarım"
      : teachingMemberships.length > 0
        ? "Eğitmen alanı"
        : learningMemberships.length > 0
          ? "Öğrenci alanı"
          : isPlatformAdmin ? "Bilgi İşlem alanı" : "Çalışma alanım";
  const navigation: NavigationItem[] = [
    { href: "/dashboard", label: "Genel bakış", icon: HomeIcon },
    ...(!isOperationsOnly ? [{ href: "/courses", label: "Dersler", icon: BookIcon }] : []),
    { href: "/profile", label: "Profil", icon: UserIcon },
    { href: "/settings", label: "Ayarlar", icon: SettingsIcon },
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

  const currentSection = pathname === "/study" ? "Ders tekrarı" : pathname.startsWith("/admin") && isPlatformAdmin ? "Bilgi İşlem" : navigation.find((item) => pathname === item.href || pathname.startsWith(item.href + "/"))?.label ?? "Çalışma alanı";

  return (
    <div className="campus-shell min-h-[100dvh]" data-collapsed={collapsed}>
      <a href="#main-content" className="sr-only fixed left-4 top-4 z-50 rounded-xl bg-surface px-4 py-3 text-sm font-medium text-fg shadow-e2 focus:not-sr-only focus:outline-2 focus:outline-offset-2 focus:outline-brand">
        Ana içeriğe geç
      </a>
      <header className="campus-topbar sticky top-0 z-30 flex min-w-0 items-center gap-3 px-4 lg:px-9">
        <Link href="/dashboard" aria-label="DOU Synapse" className="shrink-0 rounded-xl focus-visible:outline-2 focus-visible:outline-brand lg:hidden">
          <BrandLockup tone="canvas" />
        </Link>
        <div className="hidden min-w-0 items-center gap-2.5 text-sm text-fg-subtle lg:flex">
          <span>{areaLabel}</span><ChevronRightIcon size={14} /><span className="font-medium text-fg">{currentSection}</span>
        </div>
        <div className="ml-auto flex min-w-0 items-center gap-2 sm:gap-4">
          <QuickSwitch />
          <ThemeControl tone="canvas" compact />
          <div className="mx-1 hidden h-7 w-px bg-border sm:block" />
          <Link href="/profile" aria-label={`Profil: ${displayName}`} className="group hidden h-11 min-w-0 items-center sm:flex gap-2.5 rounded-full pr-1 transition-colors hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">
            <span aria-hidden="true" className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-brand/15 bg-brand-subtle text-sm font-semibold text-brand">{displayInitial}</span>
            <span className="hidden max-w-[10rem] truncate text-sm font-medium text-fg xl:block">{displayName}</span>
          </Link>
          <button type="button" aria-label={signingOut ? "Çıkılıyor…" : "Çıkış"} aria-disabled={signingOut} onClick={() => void handleSignOut()} className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-fg-muted transition-colors hover:bg-surface hover:text-fg focus-visible:outline-2 focus-visible:outline-brand aria-disabled:opacity-50">
            <LogOutIcon size={18} />
          </button>
        </div>
      </header>
      {/*
       * Mobil alt gezinme DOM'da İÇERİKTEN ÖNCE durur. Çubuk `fixed` olduğu
       * için tasarım etkilenmez; en sonda kalırsa klavye kullanıcısı ana menüye
       * ancak sayfadaki bütün bağlantıları geçtikten sonra ulaşır (portal.spec
       * 30 sekmede ulaşamamıştı → 4 sekme). Masaüstü rayı da `main`'den önce;
       * iki kırılım aynı sırayı izler. Tasarım turu bu sırayı her seferinde
       * sona alıyor, birleşmede geri taşınıyor.
       */}
      <MainNavigation items={navigation} pathname={pathname} mobile />
      <aside id="desktop-navigation" className="campus-rail fixed z-40 hidden flex-col overflow-y-auto overscroll-contain px-4 pb-5 pt-6 lg:flex">
        <div className="mb-8 flex items-center justify-between gap-2 px-2">
          <Link href="/dashboard" aria-label="DOU Synapse" className="min-w-0 rounded-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand">
            {collapsed ? <BrandMark className="h-10 w-10" /> : <BrandLockup tone="canvas" />}
          </Link>
          {!collapsed && <button type="button" onClick={() => setCollapsed(true)} aria-label="Menüyü daralt" aria-expanded={!collapsed} aria-controls="desktop-navigation" className="grid h-11 w-11 shrink-0 place-items-center rounded-lg text-fg-muted hover:bg-brand-subtle focus-visible:outline-2 focus-visible:outline-brand"><span aria-hidden="true" className="text-lg">«</span></button>}
        </div>
        {collapsed && <button type="button" onClick={() => setCollapsed(false)} aria-label="Menüyü genişlet" aria-expanded={false} aria-controls="desktop-navigation" className="mb-4 grid min-h-11 place-items-center rounded-lg text-fg-muted hover:bg-brand-subtle focus-visible:outline-2 focus-visible:outline-brand"><span aria-hidden="true" className="text-lg">»</span></button>}
        {!collapsed && <p className="mb-3 px-3 text-xs font-medium text-fg-subtle">{areaLabel}</p>}
        <MainNavigation items={navigation} pathname={pathname} collapsed={collapsed} />
        {isPlatformAdmin && <div className="mt-5 border-t border-border pt-5">
          {!collapsed && <p className="mb-2 px-3 text-xs font-medium text-fg-subtle">Platform yönetimi</p>}
          <nav aria-label="Teknik yönetim">
            <Link href="/admin" aria-current={pathname.startsWith("/admin") ? "page" : undefined} aria-label="Bilgi İşlem" title={collapsed ? "Bilgi İşlem" : undefined} className={`flex min-h-12 items-center gap-3 rounded-2xl px-4 py-3.5 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${collapsed ? "justify-center" : ""} ${pathname.startsWith("/admin") ? "bg-brand-subtle text-brand" : "text-fg-muted hover:bg-brand-subtle hover:text-fg"}`}>
              <ShieldIcon size={21} />{!collapsed && <span>Bilgi İşlem</span>}
            </Link>
          </nav>
        </div>}
        {!collapsed && (teachingMemberships.length > 0 || learningMemberships.length > 0) && <div className="mt-6 space-y-5 border-t border-border pt-5">
          {[
            { title: "Eğitmen derslerim", memberships: teachingMemberships },
            { title: "Öğrenci derslerim", memberships: learningMemberships },
          ].filter((group) => group.memberships.length > 0).map((group) => <div key={group.title}>
            <p className="mb-2 px-3 text-xs font-medium text-fg-subtle">{group.title}</p>
            <nav aria-label={group.title} className="space-y-1">
              {group.memberships.slice(0, 4).map((membership) => <Link key={membership.course_id} href={`/courses/${membership.course_id}`} className="group flex min-h-11 items-center gap-3 rounded-xl px-3 py-2 text-sm text-fg-muted transition-colors hover:bg-brand-subtle hover:text-fg focus-visible:outline-2 focus-visible:outline-brand">
                <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-gold" />
                <span className="truncate">{membership.course_title}</span>
              </Link>)}
            </nav>
          </div>)}
        </div>}
        {!collapsed && learningMemberships.length > 0 && <Link href="/study" className="mt-5 flex min-h-11 items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium text-brand hover:bg-brand-subtle focus-visible:outline-2 focus-visible:outline-brand"><BookIcon size={19} />Ders tekrarı</Link>}
        <div className="mt-auto space-y-5 pt-10">
          {!collapsed && <>
            <Link href="/kvkk" className="flex min-h-11 items-center gap-2 px-3 text-xs text-fg-muted hover:text-fg focus-visible:outline-2 focus-visible:outline-brand"><ShieldIcon size={16} />Gizlilik ve verileriniz</Link>
          </>}
        </div>
      </aside>
      <div className="campus-workspace">
        <div className="campus-main">
          {signOutError && <div className="mb-6"><ErrorNote message={signOutError.message} kind={signOutError.kind} requestId={signOutError.requestId} onRetry={() => void handleSignOut()} /></div>}
          {isPlatformAdmin && <nav aria-label="Mobil teknik yönetim" className="mb-5 lg:hidden">
            <Link href="/admin" aria-current={pathname.startsWith("/admin") ? "page" : undefined} className="flex min-h-12 items-center gap-3 rounded-xl border border-border bg-surface px-4 py-3 text-sm font-medium text-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"><ShieldIcon size={20} /><span>Bilgi İşlem</span><ChevronRightIcon size={16} className="ml-auto" /></Link>
          </nav>}
          <main id="main-content" tabIndex={-1} className="min-w-0 outline-none"><CampusMotion route={pathname}>{children}</CampusMotion>{pathname === "/dashboard" && profile && !isOperationsOnly && <SynapseFooter />}</main>
        </div>
      </div>
    </div>
  );
}

function MainNavigation({ items, pathname, mobile = false, collapsed = false }: {
  items: NavigationItem[]; pathname: string; mobile?: boolean; collapsed?: boolean;
}) {
  return (
    <nav aria-label={mobile ? "Mobil ana menü" : "Ana menü"} className={mobile
      ? "campus-dock fixed inset-x-4 bottom-4 z-30 mx-auto flex max-w-md items-center justify-around gap-1 rounded-[32px] border border-border bg-surface p-1.5 lg:hidden"
      : "flex flex-col gap-2"}>
      {items.map((item) => {
        const current = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href + "/"));
        const Icon = item.icon;
        return <Link key={item.href} href={item.href} aria-current={current ? "page" : undefined} aria-label={collapsed || mobile ? item.label : undefined} title={collapsed ? item.label : undefined} className={[
          "group relative flex min-h-12 items-center rounded-2xl font-medium transition-[background,color,transform] duration-200 focus-visible:outline-2 active:scale-[.98]",
          mobile ? "min-w-0 flex-1 flex-col justify-center gap-1 px-1 py-2 text-[0.6875rem] focus-visible:outline-offset-2 focus-visible:outline-fg" : collapsed ? "justify-center px-3 py-3.5 text-sm focus-visible:outline-offset-2 focus-visible:outline-brand" : "gap-3 px-4 py-3.5 text-sm focus-visible:outline-offset-2 focus-visible:outline-brand",
          mobile
            ? current ? "bg-brand-subtle text-brand" : "text-fg-muted hover:bg-bg hover:text-fg"
            : current ? "bg-brand-subtle text-brand" : "text-fg-muted hover:bg-brand-subtle hover:text-fg",
        ].join(" ")}>
          <Icon size={mobile ? 23 : 21} />
          {!collapsed && <span className={mobile ? "whitespace-nowrap text-center" : undefined}>{item.label}</span>}
          {!mobile && !collapsed && current && <ChevronRightIcon size={15} className="ml-auto" />}
        </Link>;
      })}
    </nav>
  );
}
