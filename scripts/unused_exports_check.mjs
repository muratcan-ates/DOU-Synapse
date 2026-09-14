#!/usr/bin/env node
/**
 * Kullanılmayan export kapısı — `knip` olmadan, yalnız Node yerleşikleriyle.
 *
 * ## Bu araç bir TİP ÇÖZÜCÜ DEĞİLDİR
 *
 * Elimizde TypeScript derleyicisi yok (yeni bağımlılık yasak, `knip` onay
 * bekliyor). Bu betik kaynak METNİNİ satır satır tarar. Bir sembolün gerçekten
 * hangi bildirime bağlandığını bilmez; yalnız "şu dosyadan şu ad isteniyor mu"
 * sorusunu yanıtlar. Dolayısıyla ŞUNLARI KAÇIRIR (bilinçli kör noktalar):
 *
 * 1. **`import * as X`** — hangi adın kullanıldığı metinden çıkarılamaz, bu
 *    yüzden hedef modülün TÜM export'ları canlı sayılır. Ölü bir export bu
 *    yolla gizlenebilir (yanlış negatif). Sessiz kalmak, olmayan bir ölüyü
 *    bildirmekten iyidir: bu kapının bildirdiği her satır silinebilir olmalı.
 * 2. **Dinamik `import("...")` / `require("...")`** — çözülen modülün tamamı
 *    canlı sayılır; `const { a } = await import("./m")` içindeki `a` ayrıştırılmaz.
 *    Belirteç değişkense (`import(yol)`) modül hiç çözülemez ve o kenar kaybolur.
 * 3. **Tip düzeyi kullanım metinden ayırt edilmez.** `import type { X }` sayılır
 *    ama modül birleştirme (`declare module`), arayüz birleştirme, ambient
 *    bildirimler ve `export =` biçimi ayrıştırılmaz. `.d.ts` dosyaları tümüyle
 *    atlanır.
 * 4. **Yalnız satır başındaki üst düzey `import`/`export` ifadeleri okunur.**
 *    Girintili (bir blok içine gömülü) export TS'te zaten geçersizdir ama
 *    `declare module` içindeki export'lar bu yüzden görünmez.
 * 5. **Düzenli ifade sabitleri ayrıştırılmaz.** `/["']/` gibi bir sabit, o
 *    SATIRIN geri kalanını dize sanıp boşaltabilir. Hasar tek satırla sınırlıdır
 *    (dize durumu satır sonunda sıfırlanır) ve import/export satırlarında
 *    düzenli ifade bulunmaz; ama aynı satıra sıkıştırılmış bir dinamik import
 *    bu yolla görünmez olabilir.
 * 6. **Bir export'un yalnız testlerden kullanılması "ölü" saymaz.** Görev
 *    sözleşmesi böyle: Playwright spec'leri ve `*.test.ts` dosyalarındaki
 *    kullanım da kullanımdır. Yani "yalnız test kullanıyor" sinyali VERİLMEZ.
 * 7. **Ölü DOSYA aramaz**, ölü export ADI arar. Hiç import edilmeyen bir modülün
 *    bütün export'ları tek tek listelenir; dosyanın kendisi ayrıca bildirilmez.
 *
 * ## Neden yine de değerli
 *
 * `knip`in bu depodaki asıl işi şudur: bir ekran silindiğinde ya da bir yardımcı
 * başka bir modüle taşındığında geride kalan `export function ...` kimsenin
 * dikkatini çekmez — derleyici susar (export edilmiş bir sembol "kullanılıyor"
 * sayılır), test susar, tip denetimi susar. Depo büyüdükçe bu artıklar ölçüm
 * yapılmadan çoğalır. Bu betik tam o sessizliği bozar: hiçbir dosyadan
 * istenmeyen her export adını, satır numarasıyla birlikte yazar.
 *
 * ## Next.js istisnaları — bunlar olmadan araç tamamen gürültüdür
 *
 * App Router'da `app/[...]/page.tsx` dosyasının `default` export'unu HİÇBİR dosya
 * import etmez; onu çerçeve dosya yolundan bulur. Aynısı `layout`, `route`,
 * `loading`, `error`, `not-found`, `template`, `default` ve `global-error` için
 * de geçerlidir. İstisna listesi olmasaydı bu depoda tek başına 41 `export
 * default` yanlış pozitif olarak düşerdi — ve kapı ilk koşusunda çöpe giderdi.
 *
 * Sözleşmede sayılan adların (default, generateMetadata, generateStaticParams,
 * metadata, viewport, dynamic, revalidate, runtime) ÜSTÜNE şunlar da muaf
 * tutuldu, çünkü hepsi aynı çerçeve sözleşmesinin parçası ve muaf olmasalardı
 * aynı tür yanlış pozitifi üretirlerdi: `route.ts` için HTTP fiilleri (GET,
 * POST, ...), `generateViewport`, `dynamicParams`, `fetchCache`,
 * `preferredRegion`, `maxDuration`, ve görsel meta dosyaları için `alt`, `size`,
 * `contentType`. Ek olarak `global-error.tsx` de özel dosya listesindedir.
 *
 * Muafiyet DOSYANIN TAMAMINI kapsamaz: `app/courses/page.tsx` içinde kimsenin
 * kullanmadığı bir yardımcı export varsa o yine bildirilir. Muaf olan yalnız
 * çerçevenin kendi sözleşme adlarıdır.
 *
 * Tüm dosyası muaf sayılanlar (giriş noktaları): `*.test.*` / `*.spec.*` (koşucu
 * onları yoldan bulur), kök seviyesindeki `*.config.*`, `middleware` /
 * `instrumentation`, ve `scripts/` altındaki bağımsız betikler. Bir yapılandırma
 * dosyasının İÇİNDEKİ göreli dize yolları da kullanım sayılır — Playwright
 * `globalSetup: "./e2e/global-setup.ts"` derken import yazmaz, dize yazar.
 *
 * ## Koşturma
 *
 *     node scripts/unused_exports_check.mjs --root apps/web       # WARN, çıkış 0
 *     node scripts/unused_exports_check.mjs --root apps/web --strict   # FAIL -> 1
 *
 * Çıktı `UNUSED_EXPORTS=PASS|WARN|FAIL` ile başlar; ardından `dosya:ad` listesi.
 * Varsayılan `--warn-only`dır (çıkış 0): kapı önce kayıt tutsun, kırmızıya
 * çevirme kararı listeyi gören insanın olsun.
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { basename, dirname, extname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

/** Taranan uzantılar. `.d.ts` ayrıca elenir (ambient bildirim, ölü sayılamaz). */
const EXTENSIONS = [".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs"];

/** Girilmeyen dizinler: üretilmiş ya da satıcı kodu, sahibi biz değiliz. */
const SKIPPED_DIRS = new Set([
  "node_modules",
  ".next",
  ".git",
  ".turbo",
  ".vercel",
  "dist",
  "build",
  "out",
  "coverage",
  "playwright-report",
  "test-results",
  "public",
]);

/** App Router'ın dosya yolundan bulduğu özel dosyalar (uzantısız ad). */
const NEXT_SPECIAL_FILES = new Set([
  "page",
  "layout",
  "route",
  "loading",
  "error",
  "not-found",
  "template",
  "default",
  "global-error",
  "sitemap",
  "robots",
  "manifest",
  "icon",
  "apple-icon",
  "opengraph-image",
  "twitter-image",
]);

/** O dosyalarda asla ölü sayılmayan export adları (çerçeve sözleşmesi). */
const NEXT_SPECIAL_NAMES = new Set([
  "default",
  "generateMetadata",
  "generateStaticParams",
  "generateViewport",
  "generateImageMetadata",
  "metadata",
  "viewport",
  "dynamic",
  "dynamicParams",
  "revalidate",
  "runtime",
  "fetchCache",
  "preferredRegion",
  "maxDuration",
  "alt",
  "size",
  "contentType",
  "GET",
  "HEAD",
  "POST",
  "PUT",
  "PATCH",
  "DELETE",
  "OPTIONS",
]);

const IDENTIFIER = "[A-Za-z_$][A-Za-z0-9_$]*";

/** Her koşuda basılan kör noktalar. Sessiz kapsam yoktur (docs_check doktrini). */
const OUT_OF_SCOPE = [
  "`import * as X` — hedef modülün tüm export'ları canlı sayılır",
  "dinamik `import()` / `require()` — çözülen modülün tamamı canlı sayılır",
  "`declare module`, `export =`, ambient bildirimler ve `.d.ts` dosyaları",
  "yalnız testten kullanılan export'lar (sözleşme gereği kullanım sayılır)",
  "ölü DOSYA tespiti (yalnız ölü export ADI bildirilir)",
];

/* -------------------------------------------------------------------------
 * 1. Satır temizleyici
 *
 * Yorumlar ve dize İÇERİKLERİ boşluğa çevrilir, ama uzunluk birebir korunur:
 * `code` dizgesindeki her indis kaynak satırdaki aynı indistir. Dize değerleri
 * kaybolmasın diye açılış tırnağının indisiyle `strings` haritasına yazılır —
 * modül belirteçlerini (`from "./x"`) oradan okuyacağız.
 *
 * Neden satır satır ve neden dize durumu satırlar arasında TAŞINMIYOR: bu depo
 * Türkçe arayüz metni yazıyor ve JSX gövdesinde kesme işareti geçiyor
 * (`Kullanıcı'nın`). Dosya çapında bir tırnak durum makinesi orada yanlış bir
 * dize açar ve dosyanın geri kalanını — import'lar dahil — görünmez kılar. O
 * hata YANLIŞ POZİTİF üretir: kullanılan bir export "ölü" diye bildirilir.
 * Durumu satırla sınırlamak hasarı tek satıra hapseder. Satır aşan tek yapılar
 * blok yorum ve şablon dizesidir; yalnız o ikisi taşınır.
 * ---------------------------------------------------------------------- */

/**
 * Tek satırı temizler. `entryState`: "kod" | "blok" | "sablon".
 * Dönüş: `{ code, strings, exitState }`.
 */
export function stripLine(line, entryState = "kod") {
  let state = entryState;
  const code = [];
  const strings = new Map();
  const length = line.length;
  let i = 0;

  const skipEscape = () => {
    if (i + 1 < length) {
      code.push(" ", " ");
      i += 2;
    } else {
      code.push(" ");
      i += 1;
    }
  };

  while (i < length) {
    const c = line[i];
    const d = line[i + 1];

    if (state === "blok") {
      if (c === "*" && d === "/") {
        code.push(" ", " ");
        i += 2;
        state = "kod";
        continue;
      }
      code.push(" ");
      i += 1;
      continue;
    }

    if (state === "sablon") {
      if (c === "\\") {
        skipEscape();
        continue;
      }
      if (c === "`") {
        code.push("`");
        i += 1;
        state = "kod";
        continue;
      }
      code.push(" ");
      i += 1;
      continue;
    }

    if (c === "/" && d === "/") {
      while (i < length) {
        code.push(" ");
        i += 1;
      }
      continue;
    }
    if (c === "/" && d === "*") {
      code.push(" ", " ");
      i += 2;
      state = "blok";
      continue;
    }
    if (c === '"' || c === "'" || c === "`") {
      const quote = c;
      const start = code.length;
      const chars = [];
      code.push(quote);
      i += 1;
      let closed = false;
      while (i < length) {
        if (line[i] === "\\") {
          chars.push(line[i + 1] ?? "");
          skipEscape();
          continue;
        }
        if (line[i] === quote) {
          code.push(quote);
          i += 1;
          closed = true;
          break;
        }
        chars.push(line[i]);
        code.push(" ");
        i += 1;
      }
      if (closed) strings.set(start, chars.join(""));
      else if (quote === "`") state = "sablon";
      continue;
    }

    code.push(c);
    i += 1;
  }

  return { code: code.join(""), strings, exitState: state };
}

/** Dosyanın tamamını temizlenmiş satırlara çevirir. */
export function stripSource(source) {
  const output = [];
  let state = "kod";
  const lines = source.split("\n");
  for (let i = 0; i < lines.length; i += 1) {
    const { code, strings, exitState } = stripLine(lines[i], state);
    output.push({ no: i + 1, code, strings });
    state = exitState;
  }
  return output;
}

/* -------------------------------------------------------------------------
 * 2. İfade toplama
 * ---------------------------------------------------------------------- */

const NAMED_SET_START = new RegExp(
  `^\\s*(?:export\\s+(?:type\\s+)?\\{|import\\s+(?:type\\s+)?\\{|import\\s+${IDENTIFIER}\\s*,\\s*\\{)`,
);

function braceDelta(code) {
  const open = (code.match(/\{/g) ?? []).length;
  const close = (code.match(/\}/g) ?? []).length;
  return open - close;
}

/**
 * `import`/`export` ile başlayan üst düzey ifadeleri toplar.
 *
 * Yalnız süslü parantez BLOĞU açık kalan ifadelerde sonraki satırlara geçilir
 * (`import {\n a,\n b\n} from "./x"`). `export default function X() {` gibi bir
 * baş satırda gövdenin tamamını yutmak gereksiz ve risklidir: ad zaten baş
 * satırda tamamlanmıştır.
 */
export function collectStatements(lines) {
  const statements = [];
  for (let i = 0; i < lines.length; i += 1) {
    const head = lines[i];
    if (!/^\s*(?:import|export)\b/.test(head.code)) continue;
    const parts = [head];
    if (NAMED_SET_START.test(head.code) && braceDelta(head.code) > 0) {
      let open = braceDelta(head.code);
      let j = i;
      while (open > 0 && j + 1 < lines.length && j - i < 200) {
        j += 1;
        parts.push(lines[j]);
        open += braceDelta(lines[j].code);
      }
      i = j;
    }
    statements.push({ lineNo: head.no, parts });
  }
  return statements;
}

/**
 * İfadedeki SON dize sabitinin değeri — modül belirteci hep odur.
 *
 * `dizeler` haritası açılış tırnağının indisiyle soldan sağa doldurulur, parçalar
 * da satır sırasındadır; bu yüzden son değer ifadenin en sağdaki dizesidir.
 * `import ... from "./x"` ve `export ... from "./x"` biçimlerinde belirteç
 * daima en sağdadır.
 */
function readSpecifier(parts) {
  let last = null;
  for (const part of parts) {
    for (const value of part.strings.values()) last = value;
  }
  return last;
}

/* -------------------------------------------------------------------------
 * 3. İfade ayrıştırma
 * ---------------------------------------------------------------------- */

/** `{ a, b as c, type D }` içeriğini [{sourceName, outerName}] listesine çevirir. */
function parseNamedSpecifiers(content) {
  const specifiers = [];
  for (const raw of content.split(",")) {
    const part = raw.replace(/\btype\s+/g, "").trim();
    if (!part) continue;
    const m = new RegExp(`^(${IDENTIFIER}|default)\\s*(?:as\\s+(${IDENTIFIER}|default))?$`).exec(part);
    if (!m) continue;
    specifiers.push({ sourceName: m[1], outerName: m[2] ?? m[1] });
  }
  return specifiers;
}

/** Üst düzey (parantez derinliği 0) virgülle böler. */
function splitTopLevel(text) {
  const parts = [];
  let depth = 0;
  let last = 0;
  for (let i = 0; i < text.length; i += 1) {
    const c = text[i];
    if (c === "{" || c === "[" || c === "(") depth += 1;
    else if (c === "}" || c === "]" || c === ")") depth -= 1;
    else if (c === "," && depth === 0) {
      parts.push(text.slice(last, i));
      last = i + 1;
    }
  }
  parts.push(text.slice(last));
  return parts.map((p) => p.trim()).filter(Boolean);
}

/**
 * `const`/`let`/`var` gövdesini bildirimlere böler ve her birinin DESENİNİ verir.
 *
 * Desen, üst düzey `:` (tip açıklaması) ya da `=` (ilk değer) gelmeden önceki
 * metindir. Tip açıklamasının İÇİNDEKİ virgül bildirim ayırıcısı DEĞİLDİR. Bu
 * ayrım olmadan `export const ETIKET: Record<Neden, string> = {...}` iki bildirim
 * sanılır ve ikincisinden `string` adında hayali bir export doğar — yani kimsenin
 * silemeyeceği bir satır "ölü" diye bildirilir. Ölçüldü: `apps/web` taramasında
 * beş dosya (`chat-feedback.tsx`, `analytics.ts`, `chat.ts`, `exam.ts`,
 * `labels.ts`) tam olarak bu yolla `string` diye ölü export bildirdi.
 *
 * `<` yalnız TİP bölgesinde derinlik sayar. Değer bölgesinde `a < b` bir
 * karşılaştırmadır ve sayılırsa derinlik bir daha sıfıra dönmez. `=>` içindeki
 * `>` atlanır; yoksa `: Array<(x) => y>` açıklaması derinliği eksiye düşürür.
 *
 * Bilinen sınır: iç içe çözme deseni (`const { a: { b } } = x`) içteki `b`'yi
 * vermez. Bu yönde hata yanlış NEGATİFtir (var olan bir export hiç bildirilmez),
 * kapının tercih ettiği yön odur.
 */
function declarationPatterns(body) {
  const patterns = [];
  let depth = 0;
  let typeDepth = 0;
  let region = "desen";
  let start = 0;
  let patternEnd = -1;

  const finish = (last) => {
    const cut = patternEnd === -1 ? last : patternEnd;
    const pattern = body.slice(start, cut).trim();
    if (pattern) patterns.push(pattern);
  };

  for (let i = 0; i < body.length; i += 1) {
    const c = body[i];
    const prev = body[i - 1] ?? "";
    const next = body[i + 1] ?? "";

    if (c === "(" || c === "[" || c === "{") {
      depth += 1;
      continue;
    }
    if (c === ")" || c === "]" || c === "}") {
      depth -= 1;
      continue;
    }
    if (region === "tip" && c === "<") {
      typeDepth += 1;
      continue;
    }
    if (region === "tip" && c === ">" && prev !== "=") {
      if (typeDepth > 0) typeDepth -= 1;
      continue;
    }
    if (depth !== 0 || typeDepth !== 0) continue;
    if (c === ":" && region === "desen") {
      patternEnd = i;
      region = "tip";
      continue;
    }
    if (c === "=" && next !== "=" && next !== ">" && !"=!<>".includes(prev)) {
      if (patternEnd === -1) patternEnd = i;
      region = "deger";
      continue;
    }
    if (c === ",") {
      finish(i);
      start = i + 1;
      patternEnd = -1;
      region = "desen";
    }
  }
  finish(body.length);
  return patterns;
}

/** `const`/`let`/`var` bildiriminin bağladığı adlar (çözme desenleri dahil). */
function boundNames(body) {
  const names = [];
  for (const pattern of declarationPatterns(body)) {
    if (pattern.startsWith("{") || pattern.startsWith("[")) {
      const inner = pattern.slice(1, pattern.length - 1);
      for (const element of splitTopLevel(inner)) {
        const plain = element.replace(/^\.\.\./, "").split("=")[0].trim();
        const target = plain.includes(":") ? plain.split(":").pop().trim() : plain;
        const m = new RegExp(`^(${IDENTIFIER})`).exec(target);
        if (m) names.push(m[1]);
      }
      continue;
    }
    const m = new RegExp(`^(${IDENTIFIER})`).exec(pattern);
    if (m) names.push(m[1]);
  }
  return names;
}

/**
 * Tek ifadeyi çözümler.
 *
 * Dönüş: `{ exports: [{name, line}], requests: [{specifier, kind, name}], star }`
 * — `kind` "ad" | "tumu" (ad bazında çözülemeyen, modülün tamamını canlı yapan).
 */
export function parseStatement(statement) {
  const text = statement.parts.map((p) => p.code).join(" ");
  const line = statement.lineNo;
  const exports = [];
  const requests = [];
  let star = null;
  const specifier = /\bfrom\s*["'`]/.test(text) || /^\s*import\s*["'`]/.test(text)
    ? readSpecifier(statement.parts)
    : null;

  // --- import ---
  if (/^\s*import\b/.test(text)) {
    if (!specifier) return { exports, requests, star };
    if (/^\s*import\s*["'`]/.test(text)) {
      // yan etki importu: ad istemez ama modülü canlı tutmaz da.
      return { exports, requests, star };
    }
    const m = /^\s*import\s+(?:type\s+)?([\s\S]*?)\s+from\s*["'`]/.exec(text);
    const clause = m ? m[1].trim() : "";
    if (/\*\s*as\s/.test(clause)) {
      requests.push({ specifier, kind: "tumu" });
      return { exports, requests, star };
    }
    const braceMatch = /\{([\s\S]*)\}/.exec(clause);
    const before = braceMatch ? clause.slice(0, braceMatch.index) : clause;
    const defaultBinding = new RegExp(`^\\s*(${IDENTIFIER})`).exec(before.replace(/^type\s+/, ""));
    if (defaultBinding) requests.push({ specifier, kind: "ad", name: "default" });
    if (braceMatch) {
      for (const element of parseNamedSpecifiers(braceMatch[1])) {
        requests.push({ specifier, kind: "ad", name: element.sourceName });
      }
    }
    return { exports, requests, star };
  }

  // --- export * ---
  const starAs = new RegExp(`^\\s*export\\s+\\*\\s+as\\s+(${IDENTIFIER})\\s+from\\b`).exec(text);
  if (starAs) {
    exports.push({ name: starAs[1], line });
    if (specifier) requests.push({ specifier, kind: "tumu" });
    return { exports, requests, star };
  }
  if (/^\s*export\s+(?:type\s+)?\*\s+from\b/.test(text)) {
    star = specifier;
    return { exports, requests, star };
  }

  // --- export { ... } [from "..."] ---
  const named = /^\s*export\s+(?:type\s+)?\{([\s\S]*?)\}/.exec(text);
  if (named) {
    for (const element of parseNamedSpecifiers(named[1])) {
      exports.push({ name: element.outerName, line });
      if (specifier) requests.push({ specifier, kind: "ad", name: element.sourceName });
    }
    return { exports, requests, star };
  }

  // --- export default ---
  if (/^\s*export\s+default\b/.test(text)) {
    exports.push({ name: "default", line });
    return { exports, requests, star };
  }

  // --- export <bildirim> ---
  const fnDecl = new RegExp(
    `^\\s*export\\s+(?:declare\\s+)?(?:async\\s+)?function\\s*\\*?\\s*(${IDENTIFIER})`,
  ).exec(text);
  if (fnDecl) {
    exports.push({ name: fnDecl[1], line });
    return { exports, requests, star };
  }
  const classDecl = new RegExp(
    `^\\s*export\\s+(?:declare\\s+)?(?:abstract\\s+)?class\\s+(${IDENTIFIER})`,
  ).exec(text);
  if (classDecl) {
    exports.push({ name: classDecl[1], line });
    return { exports, requests, star };
  }
  const typeDecl = new RegExp(
    `^\\s*export\\s+(?:declare\\s+)?(?:interface|type|enum|namespace|module)\\s+(${IDENTIFIER})`,
  ).exec(text);
  if (typeDecl) {
    exports.push({ name: typeDecl[1], line });
    return { exports, requests, star };
  }
  const constEnum = new RegExp(`^\\s*export\\s+const\\s+enum\\s+(${IDENTIFIER})`).exec(text);
  if (constEnum) {
    exports.push({ name: constEnum[1], line });
    return { exports, requests, star };
  }
  const varDecl = /^\s*export\s+(?:declare\s+)?(?:const|let|var)\s+([\s\S]*)$/.exec(text);
  if (varDecl) {
    for (const name of boundNames(varDecl[1])) exports.push({ name, line });
    return { exports, requests, star };
  }

  return { exports, requests, star };
}

/* -------------------------------------------------------------------------
 * 4. Belirteç çözme (tsconfig `paths` dahil)
 * ---------------------------------------------------------------------- */

/**
 * JSONC metnini düz JSON'a indirger: yorumlar ve sondaki virgüller atılır.
 *
 * Tarayıcı dize durumunu TAKİP EDER. Kaba bir düzenli ifade burada yetmez ve bu
 * depoda yetmedi: `paths` anahtarı `"@/"` + yıldız yazar; kaba kalıp oradaki
 * eğik-yıldız ikilisini blok yorum başlangıcı sanar, kapanışını da `include`
 * içindeki glob deseninde bulur ve dosyanın ortasını siler. Hata SESSİZDİR —
 * `JSON.parse` patlar, `readTsconfig` `null` döner, alias listesi boş kalır ve
 * `@/...` ile içe aktarılan her sembol "ölü" sayılır. Ölçüldü: `apps/web`
 * taramasında 254 yanlış pozitif, 579 export'un %44'ü.
 *
 * Dize içindeki eğik-yıldız ikilisi yorum değildir; tek kurtaran budur.
 */
function stripJsonc(raw) {
  let output = "";
  let i = 0;
  let inString = false;
  while (i < raw.length) {
    const c = raw[i];
    const d = raw[i + 1];
    if (inString) {
      if (c === "\\") {
        output += c + (d ?? "");
        i += 2;
        continue;
      }
      if (c === '"') inString = false;
      output += c;
      i += 1;
      continue;
    }
    if (c === '"') {
      inString = true;
      output += c;
      i += 1;
      continue;
    }
    if (c === "/" && d === "/") {
      while (i < raw.length && raw[i] !== "\n") i += 1;
      continue;
    }
    if (c === "/" && d === "*") {
      i += 2;
      while (i < raw.length && !(raw[i] === "*" && raw[i + 1] === "/")) i += 1;
      i += 2;
      continue;
    }
    if (c === "}" || c === "]") {
      // Sondaki virgül JSONC'de serbest, JSON'da değil. Dizenin dışındayız, bu
      // yüzden çıktının sonundaki virgülü kesmek güvenli.
      output = output.replace(/,\s*$/, "");
    }
    output += c;
    i += 1;
  }
  return output;
}

/**
 * tsconfig'i okur ve nesne olarak verir; okunamazsa/ayrıştırılamazsa `null`.
 *
 * `extends` İZLENMEZ. Türetilmiş bir yapılandırmada alias'lar eksik kalır; bu
 * durumda kapı yalnız sessizleşir (çözülemeyen belirteç kenar üretmez, kenarsız
 * export ölü sanılır) — DİKKAT, bu yönde hata yanlış POZİTİF üretir. Bu yüzden
 * alias sayısı her koşuda çıktıya basılır: 0 görürsen önce burayı sorgula.
 */
function readTsconfig(path) {
  let raw;
  try {
    raw = readFileSync(path, "utf8");
  } catch {
    return null;
  }
  try {
    return JSON.parse(stripJsonc(raw));
  } catch {
    return null;
  }
}

/** `paths` girdilerini [{prefix, suffix, targets}] biçimine getirir. */
export function readAliases(rootDir) {
  const config = readTsconfig(join(rootDir, "tsconfig.json"));
  if (!config?.compilerOptions?.paths) return [];
  const base = resolve(rootDir, config.compilerOptions.baseUrl ?? ".");
  const aliases = [];
  for (const [pattern, targets] of Object.entries(config.compilerOptions.paths)) {
    const starIndex = pattern.indexOf("*");
    aliases.push({
      prefix: starIndex === -1 ? pattern : pattern.slice(0, starIndex),
      suffix: starIndex === -1 ? "" : pattern.slice(starIndex + 1),
      wildcard: starIndex !== -1,
      targets: (Array.isArray(targets) ? targets : [targets]).map((h) => ({
        path: h,
        base,
      })),
    });
  }
  return aliases;
}

function isFile(path) {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}

/** Uzantısız yolu gerçek bir dosyaya bağlar (`./x` -> `./x.ts`, `./x/index.ts`). */
function resolveToFile(candidate) {
  if (extname(candidate) && isFile(candidate)) return candidate;
  for (const ext of EXTENSIONS) {
    const attempt = candidate + ext;
    if (isFile(attempt)) return attempt;
  }
  // `./x.js` yazılıp `./x.ts` durabilir (ESM sözleşmesi).
  const jsLike = /\.(js|jsx|mjs|cjs)$/.exec(candidate);
  if (jsLike) {
    const stem = candidate.slice(0, candidate.length - jsLike[0].length);
    for (const ext of [".ts", ".tsx", ".mts", ".cts"]) {
      if (isFile(stem + ext)) return stem + ext;
    }
  }
  for (const ext of EXTENSIONS) {
    const attempt = join(candidate, `index${ext}`);
    if (isFile(attempt)) return attempt;
  }
  return null;
}

/** Belirteci mutlak dosya yoluna çevirir; paket/çözümsüzse `null`. */
export function resolveSpecifier(specifier, sourceFile, aliases) {
  if (!specifier) return null;
  if (specifier.startsWith(".")) {
    return resolveToFile(resolve(dirname(sourceFile), specifier));
  }
  for (const alias of aliases) {
    if (!specifier.startsWith(alias.prefix)) continue;
    if (alias.suffix && !specifier.endsWith(alias.suffix)) continue;
    const middle = alias.wildcard
      ? specifier.slice(alias.prefix.length, specifier.length - alias.suffix.length)
      : "";
    for (const target of alias.targets) {
      const filled = alias.wildcard ? target.path.replace("*", middle) : target.path;
      const found = resolveToFile(resolve(target.base, filled));
      if (found) return found;
    }
  }
  return null;
}

/* -------------------------------------------------------------------------
 * 5. Dosya toplama ve giriş noktası sınıflandırması
 * ---------------------------------------------------------------------- */

export function collectFiles(rootDir) {
  const found = [];
  const walk = (dir) => {
    let entries;
    try {
      entries = readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) {
        if (SKIPPED_DIRS.has(entry.name) || entry.name.startsWith(".")) continue;
        walk(path);
        continue;
      }
      if (!entry.isFile()) continue;
      if (entry.name.endsWith(".d.ts") || entry.name.endsWith(".d.mts")) continue;
      if (!EXTENSIONS.includes(extname(entry.name))) continue;
      found.push(path);
    }
  };
  walk(rootDir);
  return found;
}

function relPath(rootDir, path) {
  return relative(rootDir, path).split(sep).join("/");
}

/**
 * Dosyanın giriş noktası olup olmadığını söyler.
 *
 * Dönüş: `{ fullyExempt, exemptNames, reason }`. `fullyExempt` dosyanın hiçbir export'unun
 * bildirilmeyeceği anlamına gelir; `exemptNames` yalnız sayılan adları korur.
 */
export function classifyEntry(rel) {
  const name = basename(rel);
  const stem = name.replace(/\.(tsx?|mts|cts|jsx?|mjs|cjs)$/, "");
  const nested = rel.includes("/");

  if (/\.(test|spec)\.(tsx?|mts|jsx?|mjs)$/.test(name)) {
    return { fullyExempt: true, exemptNames: null, reason: "test/spec dosyası" };
  }
  if (!nested && /\.config\.(tsx?|mts|cts|jsx?|mjs|cjs)$/.test(name)) {
    return { fullyExempt: true, exemptNames: null, reason: "yapılandırma dosyası" };
  }
  if (!nested && (stem === "middleware" || stem === "instrumentation")) {
    return { fullyExempt: true, exemptNames: null, reason: "Next giriş noktası" };
  }
  if (rel.startsWith("scripts/")) {
    return { fullyExempt: true, exemptNames: null, reason: "bağımsız betik" };
  }
  if ((rel.startsWith("app/") || rel.startsWith("src/app/")) && NEXT_SPECIAL_FILES.has(stem)) {
    return { fullyExempt: false, exemptNames: NEXT_SPECIAL_NAMES, reason: "Next App Router özel dosyası" };
  }
  return { fullyExempt: false, exemptNames: null, reason: null };
}

/* -------------------------------------------------------------------------
 * 6. Çözümleme
 * ---------------------------------------------------------------------- */

const DYNAMIC_PATTERNS = [/\bimport\s*\(\s*["'`]/g, /\brequire\s*\(\s*["'`]/g];

function dynamicRequests(lines) {
  const specifiers = [];
  for (const line of lines) {
    for (const pattern of DYNAMIC_PATTERNS) {
      pattern.lastIndex = 0;
      let m;
      while ((m = pattern.exec(line.code)) !== null) {
        const quoteIndex = m.index + m[0].length - 1;
        const value = line.strings.get(quoteIndex);
        if (value) specifiers.push(value);
      }
    }
  }
  return specifiers;
}

/** Yapılandırma dosyalarındaki göreli dize yolları da modül referansıdır. */
function stringReferences(lines) {
  const paths = [];
  for (const line of lines) {
    for (const value of line.strings.values()) {
      if (value.startsWith("./") || value.startsWith("../")) paths.push(value);
    }
  }
  return paths;
}

/**
 * Kökü tarar ve ölü export listesini üretir.
 *
 * `options.root` mutlak ya da cwd'ye göreli dizin. Dönüş makine tarafından da
 * okunabilir olsun diye düz veri: rapor basımı `raporla` işinin.
 */
export function analyze(options) {
  const rootDir = resolve(options.root);
  const aliases = readAliases(rootDir);
  const files = collectFiles(rootDir);

  const modules = new Map();
  const edges = [];

  for (const path of files) {
    const rel = relPath(rootDir, path);
    const lines = stripSource(readFileSync(path, "utf8"));
    const entryClass = classifyEntry(rel);
    const moduleInfo = {
      path,
      rel,
      exports: new Map(),
      starSources: [],
      fullyExempt: entryClass.fullyExempt,
      exemptNames: entryClass.exemptNames,
      reason: entryClass.reason,
    };

    for (const statement of collectStatements(lines)) {
      const { exports, requests, star } = parseStatement(statement);
      for (const { name, line } of exports) {
        if (!moduleInfo.exports.has(name)) moduleInfo.exports.set(name, line);
      }
      for (const request of requests) {
        const target = resolveSpecifier(request.specifier, path, aliases);
        if (target) edges.push({ target, kind: request.kind, name: request.name });
      }
      if (star) {
        const target = resolveSpecifier(star, path, aliases);
        if (target) moduleInfo.starSources.push(target);
      }
    }

    for (const specifier of dynamicRequests(lines)) {
      const target = resolveSpecifier(specifier, path, aliases);
      if (target) edges.push({ target, kind: "tumu" });
    }

    if (entryClass.reason === "yapılandırma dosyası") {
      for (const specifier of stringReferences(lines)) {
        const target = resolveSpecifier(specifier, path, aliases);
        if (target) edges.push({ target, kind: "tumu" });
      }
    }

    modules.set(path, moduleInfo);
  }

  const fullyUsed = new Set();
  const usedNames = new Map();

  const markAll = (target) => {
    if (fullyUsed.has(target)) return;
    const moduleInfo = modules.get(target);
    if (!moduleInfo) return;
    fullyUsed.add(target);
    for (const source of moduleInfo.starSources) markAll(source);
  };

  const markName = (target, name, seen = new Set()) => {
    const moduleInfo = modules.get(target);
    if (!moduleInfo || seen.has(target)) return;
    seen.add(target);
    if (moduleInfo.exports.has(name)) {
      if (!usedNames.has(target)) usedNames.set(target, new Set());
      usedNames.get(target).add(name);
      return;
    }
    // Ad burada bildirilmiyorsa `export * from` zinciriyle geliyordur.
    for (const source of moduleInfo.starSources) markName(source, name, seen);
  };

  for (const edge of edges) {
    if (edge.kind === "tumu") markAll(edge.target);
    else markName(edge.target, edge.name);
  }
  // Giriş noktalarının yıldız kaynakları da erişilebilirdir.
  for (const moduleInfo of modules.values()) {
    if (!moduleInfo.fullyExempt) continue;
    for (const source of moduleInfo.starSources) markAll(source);
  }

  const dead = [];
  let exportCount = 0;
  let exemptCount = 0;
  for (const moduleInfo of [...modules.values()].sort((a, b) => a.rel.localeCompare(b.rel))) {
    exportCount += moduleInfo.exports.size;
    if (moduleInfo.fullyExempt) {
      exemptCount += moduleInfo.exports.size;
      continue;
    }
    const used = usedNames.get(moduleInfo.path) ?? new Set();
    const allLive = fullyUsed.has(moduleInfo.path);
    for (const [name, line] of [...moduleInfo.exports].sort((a, b) => a[1] - b[1])) {
      if (moduleInfo.exemptNames?.has(name)) {
        exemptCount += 1;
        continue;
      }
      if (allLive || used.has(name)) continue;
      dead.push({ rel: moduleInfo.rel, name, line, reason: moduleInfo.reason });
    }
  }

  return {
    rootDir,
    dead,
    counts: {
      files: files.length,
      modules: modules.size,
      exports: exportCount,
      exempt: exemptCount,
      aliases: aliases.length,
    },
  };
}

/* -------------------------------------------------------------------------
 * 7. CLI
 * ---------------------------------------------------------------------- */

const USAGE = `Kullanım: node scripts/unused_exports_check.mjs [--root <dizin>] [--strict]

  --root <dizin>   Taranacak proje kökü (varsayılan: apps/web)
  --strict         Ölü export bulunursa çıkış kodu 1
  --warn-only      Varsayılan: bulgu olsa da çıkış kodu 0
  --help           Bu metin`;

export function main(argv = [], write = console.log) {
  if (argv.includes("--help") || argv.includes("-h")) {
    write(USAGE);
    return 0;
  }
  const rootIndex = argv.indexOf("--root");
  const root = rootIndex === -1 ? join(REPO_ROOT, "apps", "web") : argv[rootIndex + 1];
  if (!root) {
    write("--root bir dizin ister.");
    return 2;
  }
  const strict = argv.includes("--strict");

  const result = analyze({ root: resolve(root) });
  const status = result.dead.length === 0 ? "PASS" : strict ? "FAIL" : "WARN";

  write(`UNUSED_EXPORTS=${status} (${result.dead.length} ölü export / ${result.counts.exports} export)`);
  write("");
  for (const finding of result.dead) {
    write(`  ${finding.rel}:${finding.name}  (satır ${finding.line})`);
  }
  if (result.dead.length > 0) write("");

  write(
    `TARANAN  ${result.counts.files} dosya · ${result.counts.exports} export · ` +
      `${result.counts.exempt} muaf · ${result.counts.aliases} yol alias'ı · ${result.rootDir}`,
  );
  write("KAPSAM DIŞI");
  for (const item of OUT_OF_SCOPE) write(`  · ${item}`);
  if (status === "WARN") {
    write("");
    write("Uyarı kipi (--warn-only varsayılan): çıkış kodu 0. Kapıya çevirmek için --strict.");
  }

  return status === "FAIL" ? 1 : 0;
}

const isDirectRun =
  process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));
if (isDirectRun) {
  process.exit(main(process.argv.slice(2)));
}
