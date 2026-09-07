/**
 * Tema tercihi tek sözlükte yaşar (Anayasa XI): anahtarın adı, geçerli
 * değerler ve tercihi çözen mantık burada tanımlıdır. API belge sayfası
 * (apps/api/static/docs-theme.js) AYNI anahtarı kullanır.
 *
 * Dikkat: `localStorage` ORIGIN başına ayrıdır. Geliştirmede uygulama :3030,
 * API :8030 olduğu için tercih iki yüzey arasında kendiliğinden taşınmaz —
 * ölçüldü, belge sayfasında değer `null` okundu. Her yüzeyin kendi seçicisi
 * vardır ve seçim yapılmamışsa işletim sistemi ayarı geçerlidir. Anahtarın
 * aynı kalmasının sebebi üretimdir: iki yüzey tek origin arkasında (ters
 * vekil) servis edildiğinde tercih tek seçime iner.
 *
 * Neden `data-theme` özniteliği ve `prefers-color-scheme` medya sorgusu DEĞİL:
 * medya sorgusu yalnız işletim sistemi ayarını dinler, uygulama içinden
 * değiştirilemez. Öznitelik her iki yolu da taşır: tercih "system" ise
 * öznitelik işletim sisteminden ÇÖZÜLEREK yazılır, kullanıcı seçtiyse
 * doğrudan. Böylece CSS'te tek bir seçici (`:root[data-theme="dark"]`) yeter
 * ve koyu palet iki kez tanımlanmaz.
 */

export const THEME_STORAGE_KEY = "dou-synapse-theme";

export type ThemePreference = "system" | "light" | "dark";

export const THEME_OPTIONS: { value: ThemePreference; label: string }[] = [
  { value: "system", label: "Sistem" },
  { value: "light", label: "Açık" },
  { value: "dark", label: "Koyu" },
];

export function isThemePreference(value: unknown): value is ThemePreference {
  return value === "system" || value === "light" || value === "dark";
}

/** Depodaki tercih; okunamazsa (gizli mod, kapalı depo) "system". */
export function readThemePreference(): ThemePreference {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isThemePreference(stored) ? stored : "system";
  } catch {
    return "system";
  }
}

/** Tercihi uygular: özniteliği yazar, depoya kaydeder. */
export function applyThemePreference(preference: ThemePreference): void {
  const dark =
    preference === "dark" ||
    (preference === "system" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, preference);
  } catch {
    /* depo yazılamıyorsa tema yine de bu oturumda geçerlidir */
  }
}

/**
 * Açılış betiği ayrı bir statik dosyadır: `public/theme-boot.js`. Sayfanın
 * <head>'inde bloklayıcı olarak yüklenir ve "system" tercihini işletim
 * sisteminden çözer; işletim sistemi ayarı sonradan değişirse özniteliği
 * tazeleyen dinleyici de oradadır (tek tanım, burada tekrarlanmaz).
 *
 * Anahtar adının iki dosyada aynı kaldığını lib/theme.test.ts çivilar.
 */
