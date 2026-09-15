"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import {
  ACCESSIBILITY_STORAGE_KEY, DEFAULT_ACCESSIBILITY, applyAccessibilityPreferences,
  parseAccessibilityPreferences, readAccessibilityPreferences, resolveReducedMotion,
  saveAccessibilityPreferences, type AccessibilityPreferences,
} from "@/lib/accessibility";

type AccessibilityContextValue = {
  preferences: AccessibilityPreferences;
  ready: boolean;
  reducedMotion: boolean;
  systemReducedMotion: boolean;
  updatePreferences: (patch: Partial<Omit<AccessibilityPreferences, "version">>) => boolean;
  resetPreferences: () => boolean;
};

const AccessibilityContext = createContext<AccessibilityContextValue | null>(null);

export function AccessibilityProvider({ children }: { children: ReactNode }) {
  const [preferences, setPreferences] = useState<AccessibilityPreferences>(DEFAULT_ACCESSIBILITY);
  const [ready, setReady] = useState(false);
  const [systemReducedMotion, setSystemReducedMotion] = useState(true);

  useEffect(() => {
    // Depo erişimi (özellikle gizli modda) getItem çağrısından önce de hata verebilir.
    try { setPreferences(readAccessibilityPreferences(window.localStorage)); } catch { /* Varsayılanlar korunur. */ }
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    setSystemReducedMotion(media.matches);
    setReady(true);
    const changed = () => setSystemReducedMotion(media.matches);
    media.addEventListener("change", changed);
    function sync(event: StorageEvent) {
      if (event.key === ACCESSIBILITY_STORAGE_KEY || event.key === null) {
        setPreferences(parseAccessibilityPreferences(event.key === null ? null : event.newValue));
      }
    }
    window.addEventListener("storage", sync);
    return () => {
      media.removeEventListener("change", changed);
      window.removeEventListener("storage", sync);
    };
  }, []);

  useEffect(() => {
    if (ready) applyAccessibilityPreferences(preferences, systemReducedMotion);
  }, [preferences, systemReducedMotion, ready]);

  function save(next: AccessibilityPreferences): boolean {
    setPreferences(next);
    applyAccessibilityPreferences(next, systemReducedMotion);
    try { return saveAccessibilityPreferences(next, window.localStorage); } catch { return false; }
  }

  return <AccessibilityContext.Provider value={{
    preferences,
    ready,
    // İlk istemci çiziminde saklanan tercih okunana kadar JS animasyonu başlatılmaz.
    reducedMotion: !ready || resolveReducedMotion(preferences, systemReducedMotion),
    systemReducedMotion,
    updatePreferences: (patch) => save({ ...preferences, ...patch, version: 1 }),
    resetPreferences: () => save({ ...DEFAULT_ACCESSIBILITY }),
  }}>{children}</AccessibilityContext.Provider>;
}

export function useAccessibilityPreferences(): AccessibilityContextValue {
  const context = useContext(AccessibilityContext);
  if (!context) throw new Error("Erişilebilirlik sağlayıcısı bulunamadı.");
  return context;
}

export function useReducedMotionPreference(): boolean {
  return useAccessibilityPreferences().reducedMotion;
}
