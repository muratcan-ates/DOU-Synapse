"use client";

/**
 * Uygulama iskeleti: 56px üst çubuk (DESIGN.md §Layout).
 * Giriş yapılmamışsa login'e yönlendirir.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { getStoredUser, signOut, type DemoUser } from "@/lib/api";

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<DemoUser | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const stored = getStoredUser();
    if (!stored) {
      router.replace("/");
      return;
    }
    setUser(stored);
    setReady(true);
  }, [router]);

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
            <button
              onClick={() => {
                signOut();
                router.replace("/");
              }}
              className="rounded-lg px-3 py-1.5 text-xs text-fg-muted hover:bg-surface hover:text-fg"
            >
              Çıkış
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1200px] px-4 py-8">{children}</main>
    </div>
  );
}
