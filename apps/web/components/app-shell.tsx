"use client";

/**
 * Uygulama iskeleti — 14 Eylül 2026 kabuğu.
 *
 * Önceki kabuk tam boy mürekkep (siyah) rayıydı. Ürün sahibi, üniversitenin
 * kendi mobil uygulamasının (açık gri kanvas, yüzen beyaz kartlar, ikonlu
 * gezinme, tek kırmızı aksan) yanında bunu "kaba ve katı" buldu; DESIGN.md
 * §Components "Kabuk ve kural değişikliği — 14 Eylül" kararıyla kabuk açık
 * grama çevrildi:
 *   - üstte ince beyaz başlık çubuğu (marka kilidi, hesap, çıkış),
 *   - masaüstünde solda yüzen beyaz menü kartı (ikon + etiket satırları),
 *   - mobilde alt gezinme çubuğu.
 * Gezinme bağlantılarının href/etiket/aria değerleri değişmedi; E2E ve kas
 * hafızası korunur.
 *
 * Oturum burada YENİDEN OKUNMAZ. Depoyu kendi state'ine kopyalayan her bileşen,
 * lib/session.ts'in "tek kaynak" iddiasını sessizce boşa çıkarır (Anayasa XI).
 */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ComponentType, type ReactNode } from "react";
import {
  PortalProfileProvider,
  usePortalProfile,
} from "@/components/portal/portal-profile-context";
import { ErrorNote } from "@/components/page-state";
import { BrandLockup } from "@/components/brand-mark";
import { BookIcon, HomeIcon, LogOutIcon, ShieldIcon, UserIcon } from "@/components/icons";
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

  return (
    <div className="min-h-[100dvh]">
      <a
        href="#main-content"
        className="sr-only fixed left-4 top-4 z-30 rounded-xl bg-surface px-4 py-3 text-sm font-medium text-fg shadow-e2 focus:not-sr-only focus:outline-2 focus:outline-offset-2 focus:outline-brand"
      >
        Ana içeriğe geç
      </a>

      {/* Üst çubuk: marka kilidi, kurum adı, tema, hesap, çıkış. Yapışkan; kaydırıldığında hafif gölge. */}
      <header className="sticky top-0 z-20 border-b border-border bg-surface/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[1280px] items-center gap-3 px-4 lg:px-8">
          <Link
            href="/dashboard"
            aria-label="DOU Synapse"
            className="flex items-center gap-3 rounded-xl px-1 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            <BrandLockup tone="canvas" />
            <span className="hidden border-l border-border pl-3 text-sm text-fg-muted sm:block">
              Doğuş Üniversitesi
            </span>
          </Link>

          <div className="ml-auto flex items-center gap-2">
            <div className="hidden md:block">
              <ThemeControl tone="canvas" />
            </div>
            <Link
              href="/profile"
              aria-label={`Profil: ${displayName}`}
              className="flex h-11 items-center gap-2 rounded-full bg-surface-sunken py-1 pl-1 pr-3 text-sm font-medium text-fg transition-colors duration-200 hover:bg-border focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
            >
              <span
                aria-hidden="true"
                className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand-subtle text-sm font-semibold text-brand"
              >
                {displayInitial}
              </span>
              <span className="hidden max-w-[11rem] truncate sm:block">{displayName}</span>
            </Link>
            <button
              type="button"
              aria-disabled={signingOut}
              onClick={() => void handleSignOut()}
              className="inline-flex h-11 items-center gap-2 rounded-xl px-3 text-sm font-medium text-fg-muted transition-colors duration-200 hover:bg-surface-sunken hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand aria-disabled:opacity-50"
            >
              <LogOutIcon size={18} />
              <span>{signingOut ? "Çıkılıyor…" : "Çıkış"}</span>
            </button>
          </div>
        </div>
      </header>

      {/*
       * Mobil: alt gezinme çubuğu — ikon üstte, etiket altta. Çubuk `fixed`
       * olduğu için ekranda hep altta durur; DOM'da ise İÇERİKTEN ÖNCE gelir.
       * En sonda dururken klavye kullanıcısı ana menüye ancak sayfadaki bütün
       * bağlantıları geçtikten sonra ulaşıyordu (portal.spec 30 sekmede
       * ulaşamadı). Masaüstündeki `aside` de `main`'den önce; iki kırılım artık
       * aynı sırayı izliyor.
       */}
      <MainNavigation items={navigation} pathname={pathname} mobile />

      <div className="mx-auto max-w-[1280px] px-4 py-6 lg:grid lg:grid-cols-[15rem_minmax(0,1fr)] lg:gap-8 lg:px-8 lg:py-8">
        {/* Masaüstü: yüzen beyaz menü kartı. */}
        <aside className="hidden lg:block">
          <div className="sticky top-24 rounded-2xl bg-surface p-3 shadow-e1">
            <MainNavigation items={navigation} pathname={pathname} />
          </div>
        </aside>

        <div className="min-w-0">
          {signOutError && (
            <div className="mb-6">
              <ErrorNote
                message={signOutError.message}
                kind={signOutError.kind}
                requestId={signOutError.requestId}
                onRetry={() => void handleSignOut()}
              />
            </div>
          )}
          {/*
           * Alt dolgu: mobilde alt gezinme çubuğu, masaüstünde sağ altta duran
           * ders asistanı düğmesi sayfanın son satırlarının üstüne binmesin.
           */}
          <main id="main-content" tabIndex={-1} className="pb-32 lg:pb-28">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}

function MainNavigation({
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
          ? "fixed inset-x-0 bottom-0 z-20 flex justify-around border-t border-border bg-surface/95 px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-2 backdrop-blur lg:hidden"
          : "flex flex-col gap-1"
      }
    >
      {items.map((item) => {
        const current =
          pathname === item.href ||
          (item.href !== "/dashboard" && pathname.startsWith(item.href + "/"));
        const Icon = item.icon;
        /*
         * Aktif satır yumuşak kırmızı ton: "aktif gezinme", kırmızının üç meşru
         * kullanımından biri. Renk tek başına bilgi taşımaz — `aria-current`
         * her zaman verilir ve aktif etiket kalın yazılır.
         */
        const className = mobile
          ? [
              "flex min-h-11 min-w-16 flex-col items-center justify-center gap-0.5 rounded-xl px-2 py-1 text-xs font-medium transition-colors duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand",
              current ? "bg-brand-subtle text-brand" : "text-fg-muted hover:text-fg",
            ].join(" ")
          : [
              "flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm font-medium transition-colors duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand",
              current
                ? "bg-brand-subtle text-brand"
                : "text-fg-muted hover:bg-surface-sunken hover:text-fg",
            ].join(" ");
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={current ? "page" : undefined}
            className={className}
          >
            <Icon size={mobile ? 22 : 20} />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
