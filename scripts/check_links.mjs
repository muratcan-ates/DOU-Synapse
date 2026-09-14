#!/usr/bin/env node
// Yerel Markdown bağlantıları; ağ isteği ve üçüncü taraf bağımlılık yoktur.
import { execFileSync } from "node:child_process";
import { readFileSync, realpathSync, statSync } from "node:fs";
import { isAbsolute, relative, resolve, dirname, sep } from "node:path";

const LIMITATIONS = [
  "HTTP(S), mailto ve diğer dış şemalar doğrulanmaz; yalnız sayılır.",
  "CommonMark ayrıştırıcısı değildir: iç içe liste/alıntı kod blokları, girintili kod, MDX, ham HTML bağlantıları ve çıplak URL'ler kapsam dışıdır.",
  "Tanımsız kısa [etiket] veya boşluk/satır geçişiyle ayrılmış [P] [US1] metni bağlantı sayılmaz; tanımlı boşluklu referanslar, bitişik [metin][etiket] ve [etiket][] doğrulanır.",
  "Referans tanımları tek satır olmalıdır; başlık slug'ları yaygın Markdown/GitHub biçimini ve Unicode harfleri destekler, tam HTML entity kataloğu içermez.",
  "Markdown dışındaki fragmentler yalnız #Lsatır ve #Lbaşlangıç-Lbitiş biçiminde doğrulanır; diğerleri açıkça kontrol dışı raporlanır.",
];

const blank = (text) => text.replace(/[^\n]/g, " ");
const escaped = (text, at) => {
  let count = 0;
  while (text[--at] === "\\") count++;
  return count % 2 === 1;
};
const unescape = (text) => text.replace(/\\([!"#$%&'()*+,\-./:;<=>?@[\]\\^_`{|}~])/g, "$1");
const labelKey = (text) => unescape(text).trim().replace(/\s+/g, " ").toLowerCase();
const lineOf = (text, at) => text.slice(0, at).split("\n").length;
const isMarkdown = (file) => /\.(md|markdown)$/i.test(file);
const within = (root, path) => {
  const part = relative(root, path);
  return part !== ".." && !part.startsWith(`..${sep}`) && !isAbsolute(part);
};

function withoutBlocks(text) {
  let fence = null;
  return text.replace(/<!--[^]*?(?:-->|$)/g, blank).split("\n").map((line) => {
    const marker = line.match(/^ {0,3}(`{3,}|~{3,})(.*)$/);
    if (fence) {
      if (marker && marker[1][0] === fence[0] && marker[1].length >= fence.length && !marker[2].trim()) fence = null;
      return blank(line);
    }
    if (marker && !(marker[1][0] === "`" && marker[2].includes("`"))) {
      fence = marker[1];
      return blank(line);
    }
    return line;
  }).join("\n");
}

function codeSpans(text) {
  const spans = [];
  const runs = [...text.matchAll(/`+/g)];
  for (let i = 0; i < runs.length; i++) {
    const open = runs[i];
    if (escaped(text, open.index)) continue;
    let close = i + 1;
    while (close < runs.length && runs[close][0].length !== open[0].length) close++;
    if (close === runs.length) continue;
    const end = runs[close].index + runs[close][0].length;
    spans.push({ start: open.index, end, content: text.slice(open.index + open[0].length, runs[close].index) });
    i = close;
  }
  return spans;
}

function maskCodeSpans(text) {
  let result = "";
  let cursor = 0;
  for (const span of codeSpans(text)) {
    result += text.slice(cursor, span.start) + blank(text.slice(span.start, span.end));
    cursor = span.end;
  }
  return result + text.slice(cursor);
}

function bracketEnd(text, start) {
  let depth = 1;
  for (let i = start + 1; i < text.length; i++) {
    if (escaped(text, i)) continue;
    if (text[i] === "[") depth++;
    if (text[i] === "]" && --depth === 0) return i;
  }
  return -1;
}

// Başlangıç '(' sonrasıdır; referans tanımında satırın URL bölümüdür.
function destination(text, start, inline) {
  let i = start;
  while (/\s/.test(text[i] ?? "") && i < text.length) i++;
  let target = "";
  if (text[i] === "<") {
    const begin = ++i;
    while (i < text.length && (text[i] !== ">" || escaped(text, i))) i++;
    if (i === text.length || text.slice(begin, i).includes("\n")) return null;
    target = text.slice(begin, i++);
  } else {
    const begin = i;
    let depth = 0;
    for (; i < text.length; i++) {
      if (escaped(text, i)) continue;
      if (text[i] === "(") depth++;
      else if (text[i] === ")") {
        if (depth === 0) break;
        depth--;
      } else if (/\s/.test(text[i])) break;
    }
    if (depth !== 0) return null;
    target = text.slice(begin, i);
  }
  const hadSpace = /\s/.test(text[i] ?? "");
  while (i < text.length && /\s/.test(text[i])) i++;
  if (hadSpace && ["\"", "'", "("].includes(text[i])) {
    const closer = text[i] === "(" ? ")" : text[i];
    i++;
    while (i < text.length && (text[i] !== closer || escaped(text, i))) i++;
    if (i === text.length) return null;
    i++;
    while (i < text.length && /\s/.test(text[i])) i++;
  }
  if (inline ? text[i] !== ")" : i !== text.length || !target) return null;
  return { target: unescape(target), end: inline ? i + 1 : i };
}

function references(text, issue) {
  const refs = new Map();
  let offset = 0;
  const remaining = text.split("\n").map((line) => {
    const match = line.match(/^ {0,3}\[((?:\\.|[^\]\\])+)\]:[ \t]*(.*)$/);
    const at = offset;
    offset += line.length + 1;
    if (!match || match[1].startsWith("^")) return line;
    const parsed = destination(match[2], 0, false);
    if (!parsed) issue(at, "malformed_reference", match[1], "Referans tanımı tek satırlı URL ve isteğe bağlı başlık olmalı.");
    else if (!refs.has(labelKey(match[1]))) refs.set(labelKey(match[1]), parsed.target);
    return blank(line);
  }).join("\n");
  return { refs, remaining };
}

function linksIn(text, refs, issue, base = 0) {
  const links = [];
  const destinations = [];
  for (let i = 0; i < text.length; i++) {
    if (text[i] !== "[" || escaped(text, i)) continue;
    const close = bracketEnd(text, i);
    if (close < 0) continue;
    const label = text.slice(i + 1, close);
    let end = close + 1;
    const referenceStart = end + text.slice(end).match(/^[ \t]*(?:\n[ \t]*)?/)[0].length;
    let target;
    if (text[end] === "(") {
      const parsed = destination(text, end + 1, true);
      if (!parsed) issue(base + i, "malformed_link", label, "Bağlantı hedefi veya kapanışı çözümlenemedi.");
      else ({ target, end } = parsed);
    } else if (text[referenceStart] === "[") {
      const referenceEnd = bracketEnd(text, referenceStart);
      if (referenceEnd < 0) issue(base + i, "malformed_reference", label, "Referans etiketi kapanmıyor.");
      else {
        const referenceLabel = text.slice(referenceStart + 1, referenceEnd);
        const key = referenceLabel || label;
        target = refs.get(labelKey(key));
        // Speckit [P] [US1] ve görev kutusu [x] [NEEDS CLARIFICATION]
        // metindir. Arada boşluk varsa tanım olmadan referans niyeti çıkarma.
        // Bitişik tam referans ve boş [] biçimi açık niyetini korur.
        const explicitReference = referenceStart === close + 1 || referenceLabel === "";
        if (target !== undefined || explicitReference) {
          if (target === undefined) issue(base + i, "missing_reference", key, "Referans tanımı bulunamadı.");
          end = referenceEnd + 1;
        }
      }
    } else target = refs.get(labelKey(label));
    if (target !== undefined) links.push({ target, at: base + i });
    if (end > close + 1) destinations.push([close + 1, end]);
    if (label.includes("[")) links.push(...linksIn(label, refs, issue, base + i + 1));
    i = end - 1;
  }
  for (const match of text.matchAll(/<((?:https?:\/\/|mailto:)[^<>\s]+)>/gi)) {
    if (!destinations.some(([start, end]) => match.index >= start && match.index < end)) links.push({ target: match[1], at: base + match.index });
  }
  return links;
}

function entities(text) {
  const named = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };
  return text.replace(/&(#x[\da-f]+|#\d+|amp|lt|gt|quot|apos|nbsp);/gi, (all, key) => {
    if (!key.startsWith("#")) return named[key.toLowerCase()];
    const value = key[1].toLowerCase() === "x" ? parseInt(key.slice(2), 16) : Number(key.slice(1));
    return value > 0 && value <= 0x10ffff ? String.fromCodePoint(value) : all;
  });
}

function headingText(text) {
  // Hedef adresini slug'a katma; inline code'un içeriği başlığın parçasıdır.
  let output = "";
  const spans = new Map(codeSpans(text).map((span) => [span.start, span]));
  for (let i = 0; i < text.length; i++) {
    const span = spans.get(i);
    if (span) {
      output += span.content.replace(/\n/g, " ").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      i = span.end - 1;
      continue;
    }
    if (text[i] === "[") {
      const end = bracketEnd(text, i);
      if (end >= 0 && text[end + 1] === "(") {
        const parsed = destination(text, end + 2, true);
        if (parsed) {
          output += headingText(text.slice(i + 1, end));
          i = parsed.end - 1;
          continue;
        }
      } else if (end >= 0 && text[end + 1] === "[") {
        const referenceEnd = bracketEnd(text, end + 1);
        if (referenceEnd >= 0) {
          output += headingText(text.slice(i + 1, end));
          i = referenceEnd;
          continue;
        }
      }
    }
    output += text[i];
  }
  return entities(unescape(output.replace(/<(https?:\/\/[^<>\s]+)>/gi, "$1").replace(/<[^>]*>/g, "")));
}

function anchorsIn(text) {
  const cleaned = withoutBlocks(text);
  const anchors = new Set();
  const slugs = new Set();
  const addHeading = (heading) => {
    const base = headingText(heading).trim().toLowerCase().replace(/[^\p{L}\p{M}\p{N}_\-\s]/gu, "").replace(/\s/g, "-");
    let slug = base;
    let suffix = 0;
    while (slugs.has(slug)) slug = `${base}-${++suffix}`;
    slugs.add(slug);
    anchors.add(slug);
  };
  let paragraph = [];
  for (const line of cleaned.split("\n")) {
    const atx = line.match(/^ {0,3}(#{1,6})(?:[ \t]+|$)(.*)$/);
    if (atx) {
      addHeading(atx[2].replace(/[ \t]+#+[ \t]*$/, ""));
      paragraph = [];
    } else if (/^ {0,3}(?:=+|-+)[ \t]*$/.test(line) && paragraph.length) {
      addHeading(paragraph.join(" "));
      paragraph = [];
    } else if (!line.trim() || /^ {0,3}(?:>|[-+*] |\d+\. |<)/.test(line)) paragraph = [];
    else paragraph.push(line);
  }
  for (const match of maskCodeSpans(cleaned).matchAll(/<(?:a|h[1-6])\b[^>]*?\b(?:id|name)\s*=\s*(["'])(.*?)\1[^>]*>/gi)) anchors.add(entities(match[2]));
  return anchors;
}

function main() {
  const args = process.argv.slice(2);
  let json = false;
  const report = { root: null, filesChecked: 0, linksChecked: 0, externalHttpSkipped: 0, otherSchemesSkipped: 0, fragmentsSkipped: [], errors: [], limitations: LIMITATIONS };
  const finish = (code) => {
    if (json) process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
    else {
      process.stdout.write(`Dosya: ${report.filesChecked} · yerel bağlantı: ${report.linksChecked} · dış HTTP(S) kontrol edilmedi: ${report.externalHttpSkipped} · diğer şemalar kontrol edilmedi: ${report.otherSchemesSkipped}\n`);
      for (const error of report.errors) process.stdout.write(`${error.file ?? "girdi"}:${error.line ?? 0} [${error.code}] ${error.target ?? ""} — ${error.message}\n`);
      for (const item of report.fragmentsSkipped) process.stdout.write(`${item.file}:${item.line} [fragment_not_checked] ${item.target}\n`);
      process.stdout.write(`Hata: ${report.errors.length}\n`);
    }
    return code;
  };
  const files = [];
  let literal = false;
  for (const arg of args) {
    if (!literal && arg === "--") literal = true;
    else if (!literal && arg === "--json") json = true;
    else if (!literal && (arg === "--help" || arg === "-h")) {
      process.stdout.write("Kullanım: node scripts/check_links.mjs [--json] [--] [belge.md ...]\nDosya verilmezse Git'in izlediği Markdown dosyaları kontrol edilir.\n" + LIMITATIONS.map((item) => `- ${item}`).join("\n") + "\n");
      return 0;
    } else if (!literal && arg.startsWith("-")) {
      report.errors.push({ code: "invalid_argument", target: arg, message: "Bilinmeyen seçenek; dosya adıysa önce -- kullanın." });
    } else files.push(resolve(arg));
  }
  if (report.errors.length) return finish(2);
  try {
    report.root = realpathSync(execFileSync("git", ["rev-parse", "--show-toplevel"], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim());
    if (!files.length) files.push(...execFileSync("git", ["ls-files", "-z"], { cwd: report.root, encoding: "utf8" }).split("\0").filter(isMarkdown).map((file) => resolve(report.root, file)));
  } catch {
    report.errors.push({ code: "repository_unavailable", message: "Git depo kökü veya izlenen dosya listesi okunamadı." });
    return finish(2);
  }
  const cache = new Map();
  const readText = (file) => {
    if (!cache.has(file)) cache.set(file, new TextDecoder("utf-8", { fatal: true }).decode(readFileSync(file)).replace(/\r\n?/g, "\n"));
    return cache.get(file);
  };
  const headingCache = new Map();
  for (const source of new Set(files)) {
    const file = relative(report.root, source);
    let text;
    try {
      if (!within(report.root, source) || !within(report.root, realpathSync(source)) || !isMarkdown(source) || !statSync(source).isFile()) throw new Error();
      text = readText(source);
    } catch {
      report.errors.push({ file, code: "invalid_input_file", message: "Depo içindeki okunabilir UTF-8 Markdown dosyası gerekli." });
      continue;
    }
    report.filesChecked++;
    const issue = (at, code, target, message) => report.errors.push({ file, line: lineOf(text, at), code, target, message });
    const { refs, remaining } = references(maskCodeSpans(withoutBlocks(text)), issue);
    for (const link of linksIn(remaining, refs, issue)) {
      const raw = entities(link.target);
      if (/^(?:https?:|\/\/)/i.test(raw)) { report.externalHttpSkipped++; continue; }
      if (/^[a-z][a-z\d+.-]*:/i.test(raw)) { report.otherSchemesSkipped++; continue; }
      report.linksChecked++;
      let path;
      let fragment;
      try {
        const hash = raw.indexOf("#");
        const beforeHash = hash < 0 ? raw : raw.slice(0, hash);
        path = decodeURIComponent(beforeHash.split("?", 1)[0]);
        fragment = hash < 0 ? "" : decodeURIComponent(raw.slice(hash + 1));
        if (path.includes("\0")) throw new Error();
      } catch { issue(link.at, "malformed_url", raw, "Geçersiz URL kodlaması veya dosya yolu."); continue; }
      const target = path ? resolve(path.startsWith("/") ? report.root : dirname(source), path.replace(/^\/+/, "")) : source;
      let targetStat;
      try {
        if (!within(report.root, target) || !within(report.root, realpathSync(target))) throw new Error();
        targetStat = statSync(target);
      } catch { issue(link.at, "missing_path", raw, "Hedef bulunamadı veya depo dışına çıkıyor."); continue; }
      if (!fragment) continue;
      const lines = fragment.match(/^L(\d+)(?:-L(\d+))?$/);
      if (/^L\d/.test(fragment) && !lines) { issue(link.at, "invalid_line_range", raw, "Satır fragmenti #L1 veya #L1-L2 biçiminde olmalı."); continue; }
      try {
        if (lines) {
          if (!targetStat.isFile()) throw new Error();
          const content = readText(target);
          const count = content ? content.split("\n").length - Number(content.endsWith("\n")) : 0;
          const first = Number(lines[1]);
          const last = Number(lines[2] ?? lines[1]);
          if (first < 1 || last < first || last > count) issue(link.at, "invalid_line_range", raw, `Satır aralığı hedefin ${count} satırı içinde değil.`);
        } else if (targetStat.isFile() && isMarkdown(target)) {
          if (!headingCache.has(target)) headingCache.set(target, anchorsIn(readText(target)));
          if (!headingCache.get(target).has(fragment)) issue(link.at, "missing_anchor", raw, "Markdown başlığı veya açık HTML id/name bulunamadı.");
        } else report.fragmentsSkipped.push({ file, line: lineOf(text, link.at), target: raw, reason: "markdown_or_line_fragment_only" });
      } catch { issue(link.at, "unreadable_fragment_target", raw, "Fragment hedefi okunabilir UTF-8 dosyası değil."); }
    }
  }
  return finish(report.errors.some((error) => error.code === "invalid_input_file") ? 2 : report.errors.length ? 1 : 0);
}

process.exitCode = main();
