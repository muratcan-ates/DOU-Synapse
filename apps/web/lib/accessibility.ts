export const ACCESSIBILITY_STORAGE_KEY = "dou-synapse-accessibility";

export type AccessibilityPreferences = {
  version: 1;
  textSize: "default" | "large";
  motion: "system" | "reduce";
  contrast: "standard" | "more";
  underlineLinks: boolean;
};

export const DEFAULT_ACCESSIBILITY: AccessibilityPreferences = {
  version: 1,
  textSize: "default",
  motion: "system",
  contrast: "standard",
  underlineLinks: false,
};

// Bilinmeyen sürüm veya bozuk kayıt hesap/oturum verisine dokunmadan sıfırlanır.
export function parseAccessibilityPreferences(raw: string | null): AccessibilityPreferences {
  try {
    const value: unknown = raw ? JSON.parse(raw) : null;
    if (!value || typeof value !== "object" || Array.isArray(value) || !("version" in value) || value.version !== 1) {
      return { ...DEFAULT_ACCESSIBILITY };
    }
    const record = value as Record<string, unknown>;
    return {
      version: 1,
      textSize: record.textSize === "large" ? "large" : "default",
      motion: record.motion === "reduce" ? "reduce" : "system",
      contrast: record.contrast === "more" ? "more" : "standard",
      underlineLinks: record.underlineLinks === true,
    };
  } catch {
    return { ...DEFAULT_ACCESSIBILITY };
  }
}

export function readAccessibilityPreferences(storage: Pick<Storage, "getItem">): AccessibilityPreferences {
  try {
    return parseAccessibilityPreferences(storage.getItem(ACCESSIBILITY_STORAGE_KEY));
  } catch {
    return { ...DEFAULT_ACCESSIBILITY };
  }
}

export function saveAccessibilityPreferences(preferences: AccessibilityPreferences, storage: Pick<Storage, "setItem">): boolean {
  try {
    storage.setItem(ACCESSIBILITY_STORAGE_KEY, JSON.stringify(preferences));
    return true;
  } catch {
    return false;
  }
}

export function resolveReducedMotion(preferences: AccessibilityPreferences, systemReducedMotion: boolean): boolean {
  return preferences.motion === "reduce" || systemReducedMotion;
}

export function applyAccessibilityPreferences(
  preferences: AccessibilityPreferences,
  systemReducedMotion: boolean,
  root: Pick<HTMLElement, "setAttribute"> = document.documentElement,
): void {
  root.setAttribute("data-text-size", preferences.textSize);
  root.setAttribute("data-motion", resolveReducedMotion(preferences, systemReducedMotion) ? "reduce" : "full");
  root.setAttribute("data-contrast", preferences.contrast);
  root.setAttribute("data-links", preferences.underlineLinks ? "underlined" : "standard");
}
