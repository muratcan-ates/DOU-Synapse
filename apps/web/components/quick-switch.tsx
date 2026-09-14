"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { usePortalProfile } from "@/components/portal/portal-profile-context";
import { BookIcon, ChevronRightIcon, HomeIcon, ShieldIcon, UserIcon, SettingsIcon } from "@/components/icons";
import { roleLabel } from "@/lib/profile";
import { useReducedMotionPreference } from "@/components/accessibility-provider";

gsap.registerPlugin(useGSAP);

function searchText(value: string): string {
  return value.toLocaleLowerCase("tr-TR").normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "").replace(/ı/g, "i");
}

function SearchMark() {
  return <span aria-hidden="true" className="relative block h-[15px] w-[15px] shrink-0 rounded-full border-[1.75px] border-current after:absolute after:-bottom-1 after:-right-[3px] after:h-[7px] after:w-[1.75px] after:rotate-[-45deg] after:rounded-full after:bg-current" />;
}

export function QuickSwitch() {
  const reduceMotion = useReducedMotionPreference();
  const { data: profile, loading, error } = usePortalProfile();
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const firstResult = useRef<HTMLAnchorElement>(null);
  const dialogId = useId();
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");

  const close = useCallback(() => {
    if (dialog.current?.open) dialog.current.close();
  }, []);

  const toggle = useCallback(() => {
    const element = dialog.current;
    if (!element) return;
    if (element.open) {
      element.close();
      return;
    }
    // Do not displace a confirmation or active exam dialog with a shortcut.
    if (document.querySelector("dialog[open]")) return;
    element.showModal();
    setIsOpen(true);
    input.current?.focus({ preventScroll: true });
  }, []);

  useEffect(() => {
    function handleShortcut(event: KeyboardEvent) {
      if (!event.defaultPrevented && !event.isComposing && (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        toggle();
      }
    }
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, [toggle]);

  useGSAP(
    () => {
      if (!isOpen || reduceMotion) return;
      const media = gsap.matchMedia();
      media.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.fromTo(dialog.current, { opacity: 0, y: 10 }, {
          opacity: 1, y: 0, duration: 0.22, ease: "power2.out", clearProps: "opacity,transform",
        });
      });
      return () => media.revert();
    },
    { scope: dialog, dependencies: [isOpen, reduceMotion], revertOnUpdate: true },
  );

  const memberships = profile?.memberships ?? [];
  const destinations = [
    ...(["instructor", "student"] as const).flatMap((role) => memberships
      .filter((membership) => membership.role === role)
      .map((membership) => ({
        href: `/courses/${encodeURIComponent(membership.course_id)}`,
        title: membership.course_title,
        description: `${membership.course_code} · ${roleLabel(membership.role)}`,
        group: role === "instructor" ? "Eğitmen derslerim" : "Öğrenci derslerim",
        icon: BookIcon,
      }))),
    { href: "/dashboard", title: "Genel bakış", description: "Ders rollerime uygun çalışma alanları", group: "Sayfalar", icon: HomeIcon },
    { href: "/courses", title: "Dersler", description: "Tüm derslerim", group: "Sayfalar", icon: BookIcon },
    ...(memberships.some((membership) => membership.role === "student")
      ? [{ href: "/study", title: "Ders tekrarı", description: "Kaynaklar ve alıştırmalar", group: "Sayfalar", icon: BookIcon }]
      : []),
    { href: "/profile", title: "Profil", description: "Kimlik ve ders üyeliklerim", group: "Sayfalar", icon: UserIcon },
    { href: "/settings", title: "Ayarlar", description: "Görünüm, hareket ve erişilebilirlik", group: "Sayfalar", icon: SettingsIcon },
    ...(profile?.is_platform_admin === true ? [{ href: "/admin", title: "Bilgi İşlem", description: "Servis sağlığı ve teknik kayıtlar", group: "Platform yönetimi", icon: ShieldIcon }] : []),
  ];
  const terms = searchText(query).trim().split(/\s+/).filter(Boolean);
  const results = destinations.filter((item) => terms.every((term) => searchText(`${item.title} ${item.description}`).includes(term)));

  return <>
    <button
      ref={trigger}
      type="button"
      aria-label="Ders veya sayfa ara"
      aria-haspopup="dialog"
      aria-expanded={isOpen}
      aria-controls={dialogId}
      onClick={toggle}
      className="flex h-11 w-11 shrink-0 items-center justify-center gap-3 rounded-full border border-transparent text-fg-muted transition-colors hover:bg-surface hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand lg:w-64 lg:justify-start lg:rounded-xl lg:border-border lg:bg-surface lg:px-4"
    >
      <SearchMark />
      <span className="hidden flex-1 text-left text-sm lg:block">Ders veya sayfa ara</span>
      <kbd aria-hidden="true" className="hidden rounded-md border border-border px-1.5 py-0.5 font-sans text-xs text-fg-subtle lg:inline">⌘K</kbd>
    </button>
    <dialog
      ref={dialog}
      id={dialogId}
      aria-label="Hızlı geçiş"
      aria-describedby={`${dialogId}-help`}
      className="campus-switch open:flex open:flex-col"
      onClose={() => {
        setIsOpen(false);
        setQuery("");
        trigger.current?.focus({ preventScroll: true });
      }}
      onClick={(event) => {
        if (event.target !== event.currentTarget) return;
        const bounds = event.currentTarget.getBoundingClientRect();
        if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) close();
      }}
    >
      <div className="flex shrink-0 items-center gap-4 border-b border-border px-5 py-3">
        <span className="text-fg-muted"><SearchMark /></span>
        <label htmlFor={`${dialogId}-query`} className="sr-only">Ders veya sayfa adı</label>
        <input
          ref={input}
          id={`${dialogId}-query`}
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.nativeEvent.isComposing) return;
            if (event.key === "ArrowDown" && results.length > 0) {
              event.preventDefault();
              firstResult.current?.focus();
            } else if (event.key === "Enter" && results.length === 1) {
              event.preventDefault();
              firstResult.current?.click();
            }
          }}
          autoComplete="off"
          placeholder="Ders adı, kodu veya sayfa ara…"
          className="min-h-11 min-w-0 flex-1 rounded-lg bg-transparent px-1 text-base text-fg outline-offset-4 placeholder:text-fg-subtle focus-visible:outline-2 focus-visible:outline-brand"
        />
        <button type="button" onClick={close} aria-label="Aramayı kapat" className="grid h-11 w-11 shrink-0 place-items-center rounded-xl text-fg-muted hover:bg-bg focus-visible:outline-2 focus-visible:outline-brand">
          <span aria-hidden="true" className="text-2xl leading-none">×</span>
        </button>
      </div>
      <div className="min-h-0 overflow-y-auto overscroll-contain p-3">
        {loading && <p role="status" className="px-3 py-2 text-sm text-fg-muted">Dersleriniz yükleniyor…</p>}
        {error && <p role="status" className="px-3 py-2 text-sm text-fg-muted">Dersler şu anda yüklenemedi. Sayfalara geçiş yapabilirsiniz.</p>}
        {results.length === 0 ? <div role="status" className="px-4 py-9 text-center">
          <p className="font-semibold text-fg">Eşleşen ders veya sayfa yok</p>
          <p className="mt-2 text-sm leading-6 text-fg-muted">Dersin adı veya koduyla tekrar arayın.</p>
        </div> : <nav aria-label="Arama sonuçları">
          <ul>
            {results.map((item, index) => {
              const ItemIcon = item.icon;
              return <li key={item.href}>
                {(index === 0 || results[index - 1].group !== item.group) && <p className="px-3 pb-2 pt-3 text-xs font-medium text-fg-subtle">{item.group}</p>}
                <Link ref={index === 0 ? firstResult : undefined} href={item.href} onClick={close} className="group flex min-h-16 items-center gap-3 rounded-xl px-3 py-3 transition-colors hover:bg-bg focus-visible:bg-brand-subtle focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand">
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-bg text-fg-muted group-focus-visible:bg-surface group-focus-visible:text-brand"><ItemIcon size={19} /></span>
                  <span className="min-w-0 flex-1">
                    <span className="block break-words text-[0.9375rem] font-medium leading-6 text-fg">{item.title}</span>
                    <span className="block break-words text-xs leading-5 text-fg-muted">{item.description}</span>
                  </span>
                  <ChevronRightIcon size={16} className="shrink-0 text-fg-subtle" />
                </Link>
              </li>;
            })}
          </ul>
        </nav>}
      </div>
      <div className="flex shrink-0 items-center justify-between gap-3 border-t border-border bg-bg px-5 py-3 text-xs leading-5 text-fg-muted">
        <p id={`${dialogId}-help`}>Tab ile seçin, Enter ile açın.</p>
        <span className="shrink-0">Esc ile kapatın</span>
      </div>
    </dialog>
  </>;
}
