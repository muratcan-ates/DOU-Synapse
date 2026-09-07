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
import { BrandLockup } from "@/components/brand-mark";
import { ThemeControl } from "@/components/theme-control";
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
    <div className="min-h-[100dvh] lg:grid lg:grid-cols-[15rem_minmax(0,1fr)]">
      <a
        href="#main-content"
        className="sr-only fixed left-4 top-4 z-20 rounded-lg bg-surface px-4 py-3 text-sm font-medium text-fg shadow-e2 focus:not-sr-only focus:outline-2 focus:outline-offset-2 focus:outline-brand"
      >
        Ana içeriğe geç
      </a>

      {/*
       * Mürekkep rayı (masaüstü). Ürünün kimliği artık ekranın kendisinde:
       * koyu blok kemik kanvasla kontrast kurar, kırmızı yalnız aktif satırda
       * görünür. Ray sabit yükseklikte DEĞİL, tam boy — gezinme ve kimlik tek
       * sütunda toplanır, içerik alanı üstten 64px kaybetmez.
       */}
      <aside className="sticky top-0 hidden h-[100dvh] flex-col justify-between bg-ink px-4 py-6 lg:flex">
        <div className="flex flex-col gap-8">
          <Link
            href="/dashboard"
            aria-label="DOU Synapse"
            className="rounded-lg px-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-on-ink"
          >
            <BrandLockup tone="ink" />
            <span className="mt-1 block px-9 text-[0.6875rem] text-ink-fg-muted">
              Doğuş Üniversitesi
            </span>
          </Link>
          <RailNavigation items={navigation} pathname={pathname} />
        </div>

        <div className="flex flex-col gap-1 border-t border-white/10 pt-4">
          {/*
           * Tema seçici rayın dibinde, hesap bloğunun hemen üstünde: gün boyu
           * değişmeyen ama her zaman elin altında olması beklenen bir tercih.
           * Aynı kontrol Profil sayfasında da var — dar ekranda ray yok.
           */}
          <ThemeControl />
          <Link
            href="/profile"
            aria-label={`Profil: ${displayName}`}
            className="flex min-h-11 items-center gap-3 rounded-lg px-2 text-sm font-medium text-ink-fg-muted transition-colors duration-200 hover:bg-ink-raised hover:text-ink-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-on-ink"
          >
            <span
              aria-hidden="true"
              className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-ink-raised text-xs font-semibold text-ink-fg"
            >
              {displayInitial}
            </span>
            <span className="truncate">{displayName}</span>
          </Link>
          <button
            type="button"
            aria-disabled={signingOut}
            onClick={() => void handleSignOut()}
            className="flex min-h-11 items-center rounded-lg px-2 text-sm font-medium text-ink-fg-muted transition-colors duration-200 hover:bg-ink-raised hover:text-ink-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-on-ink aria-disabled:opacity-50"
          >
            {signingOut ? "Çıkılıyor…" : "Çıkış"}
          </button>
        </div>
      </aside>

      {/* Mobil: ray yerine mürekkep üst şeridi; aynı gramer, tek satır. */}
      <header className="sticky top-0 z-10 bg-ink lg:hidden">
        <div className="flex h-14 items-center gap-4 px-4">
          <Link
            href="/dashboard"
            aria-label="DOU Synapse"
            className="rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-on-ink"
          >
            <BrandLockup tone="ink" />
          </Link>
          <div className="ml-auto flex items-center gap-1">
            <Link
              href="/profile"
              aria-label={`Profil: ${displayName}`}
              className="grid h-9 w-9 place-items-center rounded-full bg-ink-raised text-xs font-semibold text-ink-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-on-ink"
            >
              {displayInitial}
            </Link>
            <button
              type="button"
              aria-disabled={signingOut}
              onClick={() => void handleSignOut()}
              className="min-h-11 rounded-lg px-3 text-sm font-medium text-ink-fg-muted hover:text-ink-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-on-ink"
            >
              {signingOut ? "Çıkılıyor…" : "Çıkış"}
            </button>
          </div>
        </div>
        <RailNavigation items={navigation} pathname={pathname} mobile />
      </header>

      <div className="min-w-0">
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
        {/*
         * Alt dolgu 7rem: sağ altta `fixed` duran ders asistanı düğmesi sayfanın
         * son satırlarının üstüne biniyordu (ölçüldü). Düğme R3 korumalı
         * dosyada; çakışma kaptan çözülür.
         */}
        <main
          id="main-content"
          tabIndex={-1}
          className="mx-auto max-w-[1160px] px-4 pt-8 pb-28 lg:px-10 lg:pt-12"
        >
          {children}
        </main>
      </div>
    </div>
  );
}

interface NavigationItem {
  href: string;
  label: string;
}

function RailNavigation({
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
          ? "flex gap-1 overflow-x-auto border-t border-white/10 px-2 pb-1"
          : "flex flex-col gap-1"
      }
    >
      {items.map((item) => {
        const current =
          pathname === item.href ||
          (item.href !== "/dashboard" && pathname.startsWith(item.href + "/"));
        /*
         * Aktif satır: kırmızı sol kenar + yükseltilmiş mürekkep yüzeyi.
         * Renk tek başına bilgi taşımaz — `aria-current` her zaman verilir ve
         * aktif satırın metni de açılır.
         */
        const className = [
          "inline-flex min-h-11 shrink-0 items-center whitespace-nowrap rounded-lg px-3 text-sm font-medium transition-colors duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-on-ink",
          mobile ? "" : "border-l-2",
          current
            ? `bg-ink-raised text-ink-fg ${mobile ? "" : "border-brand-on-ink"}`
            : `text-ink-fg-muted hover:bg-ink-raised hover:text-ink-fg ${mobile ? "" : "border-transparent"}`,
        ].join(" ");
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
