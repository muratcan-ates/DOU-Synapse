#!/usr/bin/env node
/**
 * Kontrast ölçüm betiği — Anayasa III (Ölçmeden İddia Etme).
 *
 * DESIGN.md renk tablolarındaki oranlar bir zamanlar elle yazılmıştı ve token
 * değerleri değişince sessizce yalan oldu. Bu betik oranları `app/globals.css`
 * dosyasının KENDİSİNDEN okur: belgeye yazılan her sayı buradan gelir, tahminle
 * değil. Token değiştiren biri betiği koşturmadan tabloyu güncelleyemez.
 *
 * Koşturma:
 *   cd apps/web && node scripts/contrast.mjs          # tablo + geçti/kaldı
 *   cd apps/web && node scripts/contrast.mjs --md     # DESIGN.md'ye yapıştırılacak markdown
 *
 * Çıkış kodu: ölçülen HERHANGİ bir çift kendi eşiğinin altındaysa 1. İki eşik
 * var — metin için AA 4.5:1, metin olmayan arayüz öğeleri için WCAG 1.4.11 3:1 —
 * ama ikisi de kapıdır. Metin dışı bölüm bir süre "kayıt, kapı değil" olarak
 * koştu; --border-strong o boşlukta 1.33:1'de kaldı ve kimse fark etmedi. Ölçülüp
 * çıkış kodunu etkilemeyen sayı, ölçülmemiş sayıdır.
 *
 * Formül: WCAG 2.1 relative luminance (§ Relative luminance) ve
 * contrast ratio (L1 + 0.05) / (L2 + 0.05).
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const CSS_PATH = join(dirname(fileURLToPath(import.meta.url)), "..", "app", "globals.css");

/** Normal metin AA eşiği. 12px ve 14px metinler bu sınıfa girer. */
const AA_NORMAL = 4.5;
/** Büyük metin (>=18.66px kalın veya >=24px) ve arayüz bileşeni eşiği. */
const AA_LARGE = 3.0;

// --- CSS okuma -------------------------------------------------------------

/** `{` ... `}` arasını süslü parantez sayarak çıkarır. */
function blockAt(css, fromIndex) {
  const open = css.indexOf("{", fromIndex);
  if (open === -1) throw new Error("blok bulunamadı");
  let depth = 0;
  for (let i = open; i < css.length; i++) {
    if (css[i] === "{") depth++;
    else if (css[i] === "}" && --depth === 0) return css.slice(open + 1, i);
  }
  throw new Error("kapanmayan blok");
}

function declarations(block) {
  const out = {};
  for (const m of block.matchAll(/--([a-z0-9-]+)\s*:\s*([^;]+);/gi)) {
    out[m[1]] = m[2].trim();
  }
  return out;
}

function readThemes(css) {
  const light = declarations(blockAt(css, css.indexOf(":root")));

  // Koyu tema artık medya sorgusunda değil `data-theme` özniteliğinde yaşıyor
  // (uygulama içinden de seçilebiliyor, lib/theme.ts). Kapı paleti oradan
  // okur; `html[data-theme="dark"]` bloğu yalnız color-scheme taşır, token
  // taşıyan blok `:root[data-theme="dark"]`dir.
  const darkIdx = css.indexOf(':root[data-theme="dark"]');
  if (darkIdx === -1) {
    throw new Error('koyu tema bloğu bulunamadı (:root[data-theme="dark"])');
  }
  const dark = { ...light, ...declarations(blockAt(css, darkIdx)) };
  return { light, dark };
}

// --- Renk ------------------------------------------------------------------

/** `#abc`, `#aabbcc`, `rgb(...)`, `rgba(...)` -> [r, g, b, a] (0-255, 0-1). */
function parseColor(value) {
  const v = value.trim();
  const hex = v.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (hex) {
    const h = hex[1];
    const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
    return [
      parseInt(full.slice(0, 2), 16),
      parseInt(full.slice(2, 4), 16),
      parseInt(full.slice(4, 6), 16),
      1,
    ];
  }
  const fn = v.match(/^rgba?\(([^)]+)\)$/i);
  if (fn) {
    const parts = fn[1].split(/[,\s/]+/).filter(Boolean).map(Number);
    const [r, g, b] = parts;
    return [r, g, b, parts.length > 3 ? parts[3] : 1];
  }
  throw new Error(`çözümlenemeyen renk: ${value}`);
}

/** Yarı saydam rengi opak zemin üstüne düzleştirir (source-over). */
function flatten([r, g, b, a], [br, bg, bb]) {
  return [r * a + br * (1 - a), g * a + bg * (1 - a), b * a + bb * (1 - a), 1];
}

/** WCAG 2.1 relative luminance. */
function luminance([r, g, b]) {
  const lin = [r, g, b].map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2];
}

function contrast(fg, bg) {
  const bgRgb = parseColor(bg);
  const fgRgb = flatten(parseColor(fg), bgRgb);
  const [l1, l2] = [luminance(fgRgb), luminance(bgRgb)].sort((a, b) => b - a);
  return (l1 + 0.05) / (l2 + 0.05);
}

const round = (n) => Math.round(n * 100) / 100;
const fmt = (n) => round(n).toFixed(2);

// --- Ölçülecekler ----------------------------------------------------------

/** Bilgi taşıyan metin token'ları; --bg, --surface ve --surface-sunken üstünde ölçülür. */
const TEXT_TOKENS = [
  "fg",
  "fg-muted",
  "fg-subtle",
  "brand",
  "brand-strong",
  "success",
  "warning",
  "danger",
  "info",
];

// Çukur yüzey (16 Ağustos'ta eklendi) da bir metin zeminidir: meta blokları ve
// iç paneller onun üstünde yaşıyor. Ölçülmeyen zemin, iddia edilmemiş kontrast
// demektir — `min` üçünün en kötüsünü alır, yani yeni yüzey kapıyı da bağlar.
const BACKDROPS = ["bg", "surface", "surface-sunken"];

/** Mürekkep rayının kendi metin çiftleri; ray koyu, kanvas açık. */
const INK_PAIRS = [
  ["ink-fg", "ink", "ray birincil metni"],
  ["ink-fg-muted", "ink", "ray ikincil metni"],
  ["ink-fg", "ink-raised", "ray içinde yükseltilmiş yüzey"],
  ["brand-on-ink", "ink", "rayda marka aksanı"],
];

/** Rozet çiftleri: metin kendi soluk zemini üstünde (components/ui.tsx Badge). */
const BADGE_PAIRS = [
  ["success", "success-bg"],
  ["warning", "warning-bg"],
  ["danger", "danger-bg"],
  ["info", "info-bg"],
  ["brand", "brand-subtle"],
];

/** Birincil buton: metin marka zemini üstünde (light/dark ayrı metin rengi). */
const BUTTON_PAIRS = {
  light: [["#ffffff", "brand", "birincil buton metni"]],
  dark: [["#191715", "brand", "birincil buton metni"]],
};

/**
 * Metin olmayan ama bilgi taşıyan yüzeyler: 3:1 eşiği (WCAG 1.4.11).
 *
 * Buraya yalnız BİR KONTROLÜN SINIRINI ya da durumunu çizen öğe girer.
 * `--border` bilerek YOK: o dekoratif ayraç (kart kenarı, şerit altı çizgisi),
 * kaldırılsa hiçbir öğe kullanılamaz hâle gelmez ve 1.4.11 onu kapsamaz.
 * `--border-strong` ise girdinin ve ikincil butonun tek görünür sınırıdır;
 * ikisini aynı eşiğe sokmak dekoratif çizgiyi gereksizce kalınlaştırır.
 *
 * Kenarlık iki zemine birden komşudur (kontrolün içi `--surface`, sayfanın
 * kendisi `--bg`), bu yüzden ikisine karşı da ölçülür — düşük olan kazanır.
 */
const NON_TEXT = [
  ["border-strong", "surface", "girdi/ikincil buton kenarlığı (kontrolün içi)"],
  ["border-strong", "bg", "girdi/ikincil buton kenarlığı (sayfa zemini)"],
  ["fg-subtle", "surface", "ilerleme çubuğu dolgusu (bg-fg-subtle)"],
];

function measure(theme, tokens) {
  const rows = [];
  for (const token of TEXT_TOKENS) {
    if (!tokens[token]) continue;
    const cells = BACKDROPS.map((b) => contrast(tokens[token], tokens[b]));
    rows.push({
      kind: "text",
      theme,
      token: `--${token}`,
      value: tokens[token],
      onBg: cells[0],
      onSurface: cells[1],
      onSunken: cells[2],
      min: Math.min(...cells),
      threshold: AA_NORMAL,
    });
  }
  for (const [fg, bg, note] of INK_PAIRS) {
    if (!tokens[fg] || !tokens[bg]) continue;
    rows.push({
      kind: "badge",
      theme,
      token: `--${fg} / --${bg}`,
      value: `${tokens[fg]} / ${tokens[bg]}`,
      note,
      min: contrast(tokens[fg], tokens[bg]),
      threshold: AA_NORMAL,
    });
  }
  for (const [fg, bg] of BADGE_PAIRS) {
    if (!tokens[fg] || !tokens[bg]) continue;
    const ratio = contrast(tokens[fg], tokens[bg]);
    rows.push({
      kind: "badge",
      theme,
      token: `--${fg} / --${bg}`,
      value: `${tokens[fg]} / ${tokens[bg]}`,
      min: ratio,
      threshold: AA_NORMAL,
    });
  }
  for (const [fg, bg, note] of BUTTON_PAIRS[theme]) {
    const ratio = contrast(fg, tokens[bg]);
    rows.push({
      kind: "badge",
      theme,
      token: `${fg} / --${bg}`,
      value: note,
      min: ratio,
      threshold: AA_NORMAL,
    });
  }
  for (const [fg, bg, note] of NON_TEXT) {
    if (!tokens[fg] || !tokens[bg]) continue;
    rows.push({
      kind: "non-text",
      theme,
      token: `--${fg} / --${bg}`,
      value: note,
      min: contrast(tokens[fg], tokens[bg]),
      threshold: AA_LARGE,
    });
  }
  return rows;
}

// --- Çıktı -----------------------------------------------------------------

function printMarkdown(theme, rows, tokens) {
  console.log(`\n### ${theme === "light" ? "Açık" : "Koyu"} tema\n`);
  console.log(
    `| Token | Değer | \`--bg\` (${tokens.bg}) | \`--surface\` (${tokens.surface}) | \`--surface-sunken\` (${tokens["surface-sunken"]}) |`,
  );
  console.log("|---|---|---|---|---|");
  for (const r of rows.filter((r) => r.kind === "text")) {
    const mark = (v) => `${fmt(v)}:1 ${v >= AA_NORMAL ? "AA" : v >= AA_LARGE ? "yalnız büyük metin" : "KALDI"}`;
    console.log(
      `| \`${r.token}\` | \`${r.value}\` | ${mark(r.onBg)} | ${mark(r.onSurface)} | ${mark(r.onSunken)} |`,
    );
  }
  console.log("\n| Çift | Not | Oran |");
  console.log("|---|---|---|");
  for (const r of rows.filter((r) => r.kind !== "text")) {
    const need = r.threshold === AA_NORMAL ? "AA 4.5" : "1.4.11 3.0";
    console.log(
      `| \`${r.token}\` | ${r.value} | ${fmt(r.min)}:1 ${r.min >= r.threshold ? "geçti" : `KALDI (${need})`} |`,
    );
  }
}

function printTable(theme, rows) {
  console.log(`\n${theme === "light" ? "AÇIK" : "KOYU"} TEMA`);
  const line = (r) => {
    const ok = r.min >= r.threshold;
    const detail =
      r.kind === "text"
        ? `bg ${fmt(r.onBg)}  surface ${fmt(r.onSurface)}  çukur ${fmt(r.onSunken)}`
        : `${fmt(r.min)}`;
    console.log(
      `  ${ok ? "✓" : "✗"} ${r.token.padEnd(28)} ${String(r.value).padEnd(22)} ${detail}` +
        (ok ? "" : `   <-- eşik ${r.threshold}`),
    );
  };
  rows.filter((r) => r.kind !== "non-text").forEach(line);
  const nonText = rows.filter((r) => r.kind === "non-text");
  if (nonText.length) {
    console.log("  -- metin dışı arayüz öğesi (WCAG 1.4.11, 3:1) — kapı --");
    nonText.forEach(line);
  }
}

const css = readFileSync(CSS_PATH, "utf8");
const themes = readThemes(css);
const asMarkdown = process.argv.includes("--md");

let textFailures = 0;
let nonTextFailures = 0;
for (const theme of ["light", "dark"]) {
  const tokens = themes[theme];
  const rows = measure(theme, tokens);
  for (const r of rows) {
    if (r.min >= r.threshold) continue;
    if (r.kind === "non-text") nonTextFailures++;
    else textFailures++;
  }
  if (asMarkdown) printMarkdown(theme, rows, tokens);
  else printTable(theme, rows);
}

if (!asMarkdown) {
  console.log(
    textFailures === 0
      ? "\nMetin: tüm çiftler AA 4.5:1 eşiğini geçti."
      : `\nMetin: ${textFailures} çift AA eşiğinin altında.`,
  );
  console.log(
    nonTextFailures === 0
      ? "Metin dışı arayüz öğesi: tüm çiftler WCAG 1.4.11 3:1 eşiğini geçti."
      : `Metin dışı arayüz öğesi: ${nonTextFailures} çift 3:1 altında.`,
  );
}
process.exit(textFailures === 0 && nonTextFailures === 0 ? 0 : 1);
