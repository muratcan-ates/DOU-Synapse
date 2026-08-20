import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { isThemePreference, THEME_OPTIONS, THEME_STORAGE_KEY } from "./theme";

/*
 * Açılış betiği (public/theme-boot.js) ve API belge sayfasının betiği
 * (apps/api/static/docs-theme.js) aynı depo anahtarını okur. Anahtar burada
 * değişip orada değişmezse hata sessizdir: tema "çalışıyor" görünür ama
 * yenilemede sıfırlanır. Anahtarın aynı kalması ayrıca iki yüzeyin tek origin
 * arkasında servis edildiğinde tek tercihte buluşmasını sağlar. Bu yüzden
 * eşlik testle çivilenir.
 */
describe("tema tercihi tek sözlükte", () => {
  const files = [
    join(import.meta.dir, "..", "public", "theme-boot.js"),
    join(import.meta.dir, "..", "..", "api", "static", "docs-theme.js"),
  ];

  for (const file of files) {
    test(`${file.split("/").slice(-2).join("/")} aynı anahtarı okur`, () => {
      expect(readFileSync(file, "utf8")).toContain(`"${THEME_STORAGE_KEY}"`);
    });
  }

  test("açılış betiği özniteliği çözülmüş değerle yazar", () => {
    const source = readFileSync(files[0], "utf8");
    expect(source).toContain('setAttribute("data-theme"');
    expect(source).toContain("prefers-color-scheme: dark");
  });

  test("seçenekler tam ve geçerli", () => {
    expect(THEME_OPTIONS.map((option) => option.value)).toEqual([
      "system",
      "light",
      "dark",
    ]);
    expect(THEME_OPTIONS.every((option) => isThemePreference(option.value))).toBe(
      true,
    );
    expect(isThemePreference("ambient")).toBe(false);
  });
});
