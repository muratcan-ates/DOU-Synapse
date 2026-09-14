"use client";

import { useEffect, useRef, useState } from "react";
import { applyThemePreference, readThemePreference, THEME_OPTIONS, type ThemePreference } from "@/lib/theme";

export function ThemeControl({ tone = "canvas", compact = false }: { tone?: "ink" | "canvas"; compact?: boolean }) {
  const [preference, setPreference] = useState<ThemePreference>("system");
  const disclosure = useRef<HTMLDetailsElement>(null);
  useEffect(() => { setPreference(readThemePreference()); }, []);
  useEffect(() => {
    if (!compact) return;
    function dismiss(event: PointerEvent) {
      if (disclosure.current?.open && !disclosure.current.contains(event.target as Node)) disclosure.current.open = false;
    }
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, [compact]);
  function choose(next: ThemePreference) {
    setPreference(next);
    applyThemePreference(next);
    if (disclosure.current) {
      disclosure.current.open = false;
      disclosure.current.querySelector("summary")?.focus();
    }
  }
  const ink = tone === "ink";
  const choices = <div role="group" aria-label="Tema" className={`flex gap-1 rounded-xl p-1 ${ink ? "bg-ink-raised" : "bg-surface-sunken"}`}>
    {THEME_OPTIONS.map(option=><button key={option.value} type="button" aria-pressed={preference === option.value} onClick={()=>choose(option.value)} className={`min-h-11 flex-1 rounded-lg px-3 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 ${ink ? "focus-visible:outline-brand-on-ink" : "focus-visible:outline-brand"} ${preference === option.value ? ink ? "bg-ink text-ink-fg" : "bg-surface text-brand shadow-e1" : ink ? "text-ink-fg-muted hover:text-ink-fg" : "text-fg-muted hover:text-fg"}`}>{option.label}</button>)}
  </div>;
  if (!compact) return choices;
  return <details ref={disclosure} className="relative shrink-0" onKeyDown={event=>{
    if(event.key === "Escape" && disclosure.current?.open) { event.preventDefault(); disclosure.current.open=false; disclosure.current.querySelector("summary")?.focus(); }
  }}>
    <summary id="appearance-control" aria-label="Görünüm seçenekleri" title="Görünüm seçenekleri" className="flex h-11 w-11 cursor-pointer list-none items-center justify-center rounded-full text-brand transition-colors hover:bg-brand-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand [&::-webkit-details-marker]:hidden">
      <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/></svg>
    </summary>
    <div className="absolute right-0 top-[calc(100%+12px)] z-50 w-[252px] rounded-2xl border border-border bg-surface p-4 shadow-e2">
      <p className="mb-3 text-sm font-semibold text-fg">Görünüm</p>
      {choices}
      <p className="mt-3 text-xs leading-5 text-fg-muted">Gündüzün ışığı, gecenin derinliği.</p>
    </div>
  </details>;
}
