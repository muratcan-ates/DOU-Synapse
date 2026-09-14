import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import {
  ACCESSIBILITY_STORAGE_KEY, DEFAULT_ACCESSIBILITY, applyAccessibilityPreferences,
  parseAccessibilityPreferences, readAccessibilityPreferences, resolveReducedMotion,
  saveAccessibilityPreferences,
} from "./accessibility";

const selected = { version: 1 as const, textSize: "large" as const, motion: "reduce" as const, contrast: "more" as const, underlineLinks: true };

// Açılış betiği ve React yolu bağımsız çalışır; aynı kayıt aynı DOM sonucunu üretmeli.
const boot = readFileSync(new URL("../public/accessibility-boot.js", import.meta.url), "utf8");
function bootAttributes(raw: string | null, reducedMotion: boolean, blocked = false) {
  const attributes: Record<string, string> = {};
  runInNewContext(boot, {
    localStorage: { getItem(key: string) {
      if (blocked) throw new Error("storage blocked");
      expect(key).toBe(ACCESSIBILITY_STORAGE_KEY);
      return raw;
    } },
    window: { matchMedia: () => ({ matches: reducedMotion }) },
    document: { documentElement: { setAttribute: (key: string, value: string) => { attributes[key] = value; } } },
  });
  return attributes;
}

describe("tarayıcı erişilebilirlik tercihleri", () => {
  test("eksik, bozuk veya desteklenmeyen kayıt güvenli varsayılanlara döner", () => {
    for (const raw of [null, "", "{", "null", "true", "1", "[]", '"large"', '{"version":2,"motion":"reduce"}']) {
      expect(parseAccessibilityPreferences(raw)).toEqual(DEFAULT_ACCESSIBILITY);
    }
  });

  test("geçerli tercihler korunur; beklenmeyen alanlar aktarılmaz", () => {
    expect(parseAccessibilityPreferences(JSON.stringify({ ...selected, theme: "dark", role: "admin" }))).toEqual(selected);
  });

  test("her alan türüne göre doğrulanır; truthy metin ve sayılar etkinleşmez", () => {
    expect(parseAccessibilityPreferences(JSON.stringify({ version: 1, textSize: "enormous", motion: false, contrast: ["more"], underlineLinks: "true" }))).toEqual(DEFAULT_ACCESSIBILITY);
    expect(parseAccessibilityPreferences(JSON.stringify({ version: 1, textSize: "large", motion: "off", contrast: "more", underlineLinks: 1 }))).toEqual({ ...DEFAULT_ACCESSIBILITY, textSize: "large", contrast: "more" });
  });

  test("varsayılan nesne farklı okumalardan değiştirilemez", () => {
    const first = parseAccessibilityPreferences(null);
    first.textSize = "large";
    expect(parseAccessibilityPreferences(null)).toEqual(DEFAULT_ACCESSIBILITY);
    expect(DEFAULT_ACCESSIBILITY.textSize).toBe("default");
  });

  test("manuel azaltma ve işletim sistemi azaltması ayrı ayrı geçerlidir", () => {
    expect(resolveReducedMotion(DEFAULT_ACCESSIBILITY, false)).toBe(false);
    expect(resolveReducedMotion(DEFAULT_ACCESSIBILITY, true)).toBe(true);
    expect(resolveReducedMotion(selected, false)).toBe(true);
    expect(resolveReducedMotion(selected, true)).toBe(true);
  });

  test("depo okuma/yazma hatası yakalanır ve başarısız kayıt başarı sayılmaz", () => {
    expect(readAccessibilityPreferences({ getItem: () => { throw new Error("blocked"); } })).toEqual(DEFAULT_ACCESSIBILITY);
    expect(saveAccessibilityPreferences(selected, { setItem: () => { throw new Error("quota"); } })).toBe(false);
  });

  test("kaydet ve sıfırla yalnız erişilebilirlik kaydını değiştirir", () => {
    const records = new Map([["dou-synapse-theme", "dark"], ["unrelated-entry", "keep"]]);
    const storage = { getItem: (key: string) => records.get(key) ?? null, setItem: (key: string, value: string) => { records.set(key, value); } };
    expect(saveAccessibilityPreferences(selected, storage)).toBe(true);
    expect(readAccessibilityPreferences(storage)).toEqual(selected);
    expect(saveAccessibilityPreferences(DEFAULT_ACCESSIBILITY, storage)).toBe(true);
    expect(readAccessibilityPreferences(storage)).toEqual(DEFAULT_ACCESSIBILITY);
    expect(records.get("dou-synapse-theme")).toBe("dark");
    expect(records.get("unrelated-entry")).toBe("keep");
    expect(records.size).toBe(3);
  });

  test("hydration öncesi ve sonrası tüm tercihler/sistem durumları aynı öznitelikleri üretir", () => {
    const cases = [null, "{", "[]", '{"version":2}', JSON.stringify(DEFAULT_ACCESSIBILITY), JSON.stringify(selected), JSON.stringify({ version: 1, textSize: "large", underlineLinks: "true" })];
    for (const raw of cases) for (const reduced of [false, true]) {
      const attributes: Record<string, string> = {};
      applyAccessibilityPreferences(parseAccessibilityPreferences(raw), reduced, { setAttribute: (key, value) => { attributes[key] = value; } });
      expect(bootAttributes(raw, reduced)).toEqual(attributes);
    }
  });

  test("açılışta depo kapalı olsa da sistemin hareket azaltması uygulanır", () => {
    expect(bootAttributes(JSON.stringify(selected), true, true)).toEqual({ "data-text-size": "default", "data-motion": "reduce", "data-contrast": "standard", "data-links": "standard" });
  });
});
