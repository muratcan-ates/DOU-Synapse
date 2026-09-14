#!/usr/bin/env node
/**
 * `scripts/unused_exports_check.mjs` kapısının testleri.
 *
 * Kapı kendi kendini kanıtlamalıdır: bu betiğin ürettiği liste doğrudan "bu
 * satırı silebilirsin" anlamına geliyor, yani YANLIŞ POZİTİF pahalıdır. Bir
 * geliştirici listede gördüğü export'u siler, derleme kırılır ve kapıya bir
 * daha güvenilmez. Bu yüzden testlerin ağırlığı "şunu bildirME" yönündedir:
 * Next App Router sözleşme adları, `@/` alias'ı, `export * from` zinciri,
 * dinamik import, yıldız import, yapılandırma dosyasındaki dize yolu.
 *
 * Her test `mkdtempSync` ile sentetik bir proje kurar ve `after` kancasında
 * siler; gerçek depoya hiç dokunulmaz. Bir kapının testinin gerçek depoya
 * bağlanması, depo değiştiğinde testi bayatlatır (docs_check doktrini).
 */

import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { after, test } from "node:test";

import { analyze, main, stripLine, classifyEntry, readAliases } from "./unused_exports_check.mjs";

/** Sentetik proje kurar; `files` = { "göreli/yol.ts": "içerik" }. */
function makeProject(files) {
  const root = mkdtempSync(join(tmpdir(), "unused-exports-"));
  for (const [rel, content] of Object.entries(files)) {
    const path = join(root, rel);
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, content);
  }
  return root;
}

/** Bulguları karşılaştırması kolay `dosya:ad` dizgelerine indirger. */
function deadNames(root) {
  return analyze({ root }).dead.map((b) => `${b.rel}:${b.name}`).sort();
}

/** CLI'yi çağırır; çıktıyı yakalar, çıkış kodunu döndürür. */
function run(argv) {
  const lines = [];
  const code = main(argv, (s) => lines.push(String(s)));
  return { code, output: lines.join("\n") };
}

const TSCONFIG_ALIAS = JSON.stringify({
  compilerOptions: { baseUrl: ".", paths: { "@/*": ["./*"] } },
});

test("gerçekten kullanılmayan export yakalanır, kullanılan yakalanmaz", (t) => {
  const root = makeProject({
    "lib/a.ts": "export function kullanilan() {}\nexport function olu() {}\n",
    "app/page.tsx":
      'import { kullanilan } from "../lib/a";\nexport default function Sayfa() { return kullanilan(); }\n',
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  assert.deepEqual(deadNames(root), ["lib/a.ts:olu"]);
});

test("app/x/page.tsx default export'u ASLA ölü sayılmaz", (t) => {
  const root = makeProject({
    "app/x/page.tsx": "export default function Sayfa() { return null; }\n",
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  assert.deepEqual(deadNames(root), []);
});

test("generateMetadata ve diğer çerçeve adları muaf, aynı dosyadaki yardımcı muaf DEĞİL", (t) => {
  const root = makeProject({
    "app/x/page.tsx": [
      "export async function generateMetadata() { return {}; }",
      "export function generateStaticParams() { return []; }",
      "export const metadata = { title: 'x' };",
      "export const viewport = {};",
      "export const dynamic = 'force-dynamic';",
      "export const revalidate = 60;",
      "export const runtime = 'nodejs';",
      "export function yardimci() {}",
      "export default function Sayfa() { return null; }",
      "",
    ].join("\n"),
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  // Muafiyet DOSYAYI değil, çerçevenin sözleşme ADLARINI kapsar.
  assert.deepEqual(deadNames(root), ["app/x/page.tsx:yardimci"]);
});

test("route.ts HTTP fiilleri ve layout default'u muaf", (t) => {
  const root = makeProject({
    "app/api/ping/route.ts": "export async function GET() {}\nexport async function POST() {}\n",
    "app/layout.tsx": "export default function Kok({ children }) { return children; }\n",
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  assert.deepEqual(deadNames(root), []);
});

test("`@/` alias'ıyla import edilen export ölü sayılmaz", (t) => {
  const root = makeProject({
    "tsconfig.json": TSCONFIG_ALIAS,
    "lib/a.ts": "export function aliasIle() {}\nexport function olu() {}\n",
    "app/page.tsx":
      'import { aliasIle } from "@/lib/a";\nexport default function S() { return aliasIle(); }\n',
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  assert.equal(readAliases(root).length, 1);
  assert.deepEqual(deadNames(root), ["lib/a.ts:olu"]);
});

test("yorumlu ve sondaki virgüllü (JSONC) tsconfig alias'ları yine okunur", (t) => {
  const root = makeProject({
    "tsconfig.json": [
      "{",
      '  // proje kökü alias\'ı',
      '  "compilerOptions": {',
      '    "baseUrl": ".",',
      '    "paths": { "@/*": ["./*"], },',
      "  },",
      '  "include": ["**/*.ts"]',
      "}",
      "",
    ].join("\n"),
    "lib/a.ts": "export function aliasIle() {}\n",
    "app/page.tsx":
      'import { aliasIle } from "@/lib/a";\nexport default function S() { return aliasIle(); }\n',
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  assert.equal(readAliases(root).length, 1);
  assert.deepEqual(deadNames(root), []);
});

test("`export * from` yeniden dışa aktarma zinciri izlenir", (t) => {
  const root = makeProject({
    "lib/derin.ts": "export function derinAd() {}\nexport function derinOlu() {}\n",
    "lib/orta.ts": 'export * from "./derin";\n',
    "lib/index.ts": 'export * from "./orta";\n',
    "app/page.tsx":
      'import { derinAd } from "../lib/index";\nexport default function S() { return derinAd(); }\n',
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  // Zincir iki halka derindir: index -> orta -> derin.
  assert.deepEqual(deadNames(root), ["lib/derin.ts:derinOlu"]);
});

test("`export { a as b }` DIŞ adla bildirilir, kaynak ad değil", (t) => {
  const root = makeProject({
    "lib/a.ts": "function ic() {}\nexport { ic as disari };\n",
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  assert.deepEqual(deadNames(root), ["lib/a.ts:disari"]);
});

test("`export { a as b }` dış adla import edilince ölü sayılmaz", (t) => {
  const root = makeProject({
    "lib/a.ts": "function ic() {}\nfunction ic2() {}\nexport { ic as disari, ic2 as olu };\n",
    "app/page.tsx":
      'import { disari } from "../lib/a";\nexport default function S() { return disari(); }\n',
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  assert.deepEqual(deadNames(root), ["lib/a.ts:olu"]);
});

test("`export ... from` yeniden dışa aktarmada kaynak ad canlı sayılır", (t) => {
  const root = makeProject({
    "lib/a.ts": "export function ic() {}\n",
    "lib/index.ts": 'export { ic as disari } from "./a";\n',
    "app/page.tsx":
      'import { disari } from "../lib/index";\nexport default function S() { return disari(); }\n',
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  // `lib/a.ts:ic` istenmiştir (kaynak ad), `lib/index.ts:disari` de kullanılmıştır.
  assert.deepEqual(deadNames(root), []);
});

test("TS tipi export'ları doğru sınıflanır: kullanılan sessiz, kullanılmayan bildirilir", (t) => {
  const root = makeProject({
    "tsconfig.json": TSCONFIG_ALIAS,
    "lib/tipler.ts": [
      "export type Kullanilan = string;",
      "export type OluTip = number;",
      "export interface OluArayuz { a: string }",
      "export interface KullanilanArayuz { b: string }",
      "export enum OluEnum { A }",
      "",
    ].join("\n"),
    "app/page.tsx": [
      'import type { Kullanilan, KullanilanArayuz } from "@/lib/tipler";',
      "export default function S(a: Kullanilan, b: KullanilanArayuz) { return null; }",
      "",
    ].join("\n"),
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  assert.deepEqual(deadNames(root), [
    "lib/tipler.ts:OluArayuz",
    "lib/tipler.ts:OluEnum",
    "lib/tipler.ts:OluTip",
  ]);
});

test("`export type { X }` yeniden dışa aktarması ayrı bir export'tur", (t) => {
  const root = makeProject({
    "tsconfig.json": TSCONFIG_ALIAS,
    "lib/tipler.ts": "export type Durum = string;\n",
    "lib/etiketler.ts": 'import type { Durum } from "@/lib/tipler";\nexport type { Durum };\n',
    "app/page.tsx":
      'import type { Durum } from "@/lib/tipler";\nexport default function S(a: Durum) { return null; }\n',
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  // Kimse `@/lib/etiketler`ten `Durum` istemiyor: oradaki kopya ölüdür,
  // kaynak `lib/tipler.ts` ise canlıdır. Ayrım kaybolursa kapı değersizleşir.
  assert.deepEqual(deadNames(root), ["lib/etiketler.ts:Durum"]);
});

test("`import * as X` hedef modülün TÜM export'larını canlı sayar", (t) => {
  const root = makeProject({
    "lib/a.ts": "export function bir() {}\nexport function iki() {}\n",
    "app/page.tsx":
      'import * as tumu from "../lib/a";\nexport default function S() { return tumu.bir(); }\n',
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  assert.deepEqual(deadNames(root), []);
});

test("dinamik `import()` hedef modülü canlı tutar", (t) => {
  const root = makeProject({
    "lib/agir.ts": "export function agirIs() {}\nexport function yanIs() {}\n",
    "app/page.tsx":
      'export default async function S() { const m = await import("../lib/agir"); return m.agirIs(); }\n',
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  assert.deepEqual(deadNames(root), []);
});

test("test/spec dosyalarındaki kullanım kullanımdır; spec'in kendi export'u bildirilmez", (t) => {
  const root = makeProject({
    "tsconfig.json": TSCONFIG_ALIAS,
    "lib/a.ts": "export function yalnizTestKullaniyor() {}\nexport function hicKullanilmiyor() {}\n",
    "e2e/akis.spec.ts": [
      'import { yalnizTestKullaniyor } from "@/lib/a";',
      "export const specSabiti = 1;",
      "yalnizTestKullaniyor();",
      "",
    ].join("\n"),
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  assert.deepEqual(deadNames(root), ["lib/a.ts:hicKullanilmiyor"]);
});

test("kök yapılandırma dosyasındaki göreli dize yolu kullanım sayılır", (t) => {
  const root = makeProject({
    "playwright.config.ts":
      'export default { globalSetup: "./e2e/global-setup.ts", testDir: "./e2e" };\n',
    "e2e/global-setup.ts": "export default async function kur() {}\n",
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  // Playwright import yazmaz, dize yazar; kenar oradan kurulmalı.
  assert.deepEqual(deadNames(root), []);
});

test("`.d.ts` dosyaları hiç taranmaz", (t) => {
  const root = makeProject({
    "lib/tipler.d.ts": "export type AmbientTip = string;\n",
    "lib/a.ts": "export function olu() {}\n",
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  assert.deepEqual(deadNames(root), ["lib/a.ts:olu"]);
});

test("jenerik tip açıklaması hayali export üretmez (`Record<A, string>` regresyonu)", (t) => {
  const root = makeProject({
    "lib/etiketler.ts": [
      "type Durum = 'a' | 'b';",
      "export const ETIKET: Record<Durum, string> = { a: 'A', b: 'B' };",
      "export const LISTE: Array<(x: number) => string> = [];",
      "",
    ].join("\n"),
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  // `string` diye bir export YOKTUR; üretilirse silinemeyen satır bildirilir.
  assert.deepEqual(deadNames(root), ["lib/etiketler.ts:ETIKET", "lib/etiketler.ts:LISTE"]);
});

test("çözme deseni (`export const { a, b } = x`) bağladığı adları verir", (t) => {
  const root = makeProject({
    "lib/a.ts": "const kaynak = { bir: 1, iki: 2 };\nexport const { bir, iki: ikinci } = kaynak;\n",
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  assert.deepEqual(deadNames(root), ["lib/a.ts:bir", "lib/a.ts:ikinci"]);
});

test("app dışındaki `export default` ölüyse bildirilir", (t) => {
  const root = makeProject({
    "components/kart.tsx": "export default function Kart() { return null; }\n",
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  assert.deepEqual(deadNames(root), ["components/kart.tsx:default"]);
});

test("çok satırlı `import { ... }` kümesi tümüyle okunur", (t) => {
  const root = makeProject({
    "lib/a.ts": "export function bir() {}\nexport function iki() {}\nexport function uc() {}\n",
    "app/page.tsx": [
      "import {",
      "  bir,",
      "  iki,",
      '} from "../lib/a";',
      "export default function S() { return bir() + iki(); }",
      "",
    ].join("\n"),
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  assert.deepEqual(deadNames(root), ["lib/a.ts:uc"]);
});

test("boş proje kapıyı çökertmez ve PASS verir", (t) => {
  const root = makeProject({});
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const result = analyze({ root });
  assert.deepEqual(result.dead, []);
  assert.equal(result.counts.files, 0);

  const { code, output } = run(["--root", root]);
  assert.equal(code, 0);
  assert.match(output, /UNUSED_EXPORTS=PASS/);
});

test("varsayılan kip WARN + çıkış 0, `--strict` FAIL + çıkış 1", (t) => {
  const root = makeProject({ "lib/a.ts": "export function olu() {}\n" });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const warn = run(["--root", root]);
  assert.equal(warn.code, 0);
  assert.match(warn.output, /UNUSED_EXPORTS=WARN/);
  assert.match(warn.output, /lib\/a\.ts:olu/);

  const strict = run(["--root", root, "--strict"]);
  assert.equal(strict.code, 1);
  assert.match(strict.output, /UNUSED_EXPORTS=FAIL/);
});

test("bulgu yokken `--strict` de çıkış 0 verir", (t) => {
  const root = makeProject({ "app/page.tsx": "export default function S() { return null; }\n" });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const { code, output } = run(["--root", root, "--strict"]);
  assert.equal(code, 0);
  assert.match(output, /UNUSED_EXPORTS=PASS/);
});

test("çıktı kapsam dışı maddelerini her koşuda yazar (sessiz kapsam yok)", (t) => {
  const root = makeProject({ "lib/a.ts": "export function olu() {}\n" });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const { output } = run(["--root", root]);
  assert.match(output, /KAPSAM DIŞI/);
  assert.match(output, /import \* as X/);
  assert.match(output, /TARANAN {2}\d+ dosya/);
  assert.match(output, /yol alias'ı/);
});

test("`--help` kullanımı yazar ve 0 döner; `--root` değersizse 2 döner", () => {
  const help = run(["--help"]);
  assert.equal(help.code, 0);
  assert.match(help.output, /Kullanım:/);

  const missing = run(["--root"]);
  assert.equal(missing.code, 2);
  assert.match(missing.output, /--root bir dizin ister/);
});

test("satır temizleyici dize ve yorum içeriğini boşaltır, indisleri korur", () => {
  const { code, strings } = stripLine('import { a } from "./x"; // yorum');
  assert.equal(code.length, 'import { a } from "./x"; // yorum'.length);
  assert.equal([...strings.values()].pop(), "./x");
  assert.doesNotMatch(code, /yorum/);

  // Türkçe kesme işareti bir dize açmamalı — hasar satırla sınırlı kalmalı.
  const apostrophe = stripLine("// Kullanıcı'nın adı");
  assert.equal(apostrophe.exitState, "kod");
});

test("giriş noktası sınıflandırması: test, config, middleware, scripts tam muaf", () => {
  assert.equal(classifyEntry("lib/a.spec.ts").fullyExempt, true);
  assert.equal(classifyEntry("lib/a.test.tsx").fullyExempt, true);
  assert.equal(classifyEntry("next.config.ts").fullyExempt, true);
  assert.equal(classifyEntry("middleware.ts").fullyExempt, true);
  assert.equal(classifyEntry("instrumentation.ts").fullyExempt, true);
  assert.equal(classifyEntry("scripts/contrast.mjs").fullyExempt, true);
  assert.equal(classifyEntry("lib/a.ts").fullyExempt, false);
  // İç içe bir `x.config.ts` kök yapılandırması değildir, muaf olmamalı.
  assert.equal(classifyEntry("lib/x.config.ts").fullyExempt, false);
  // App Router özel dosyası: dosya değil, ADLAR muaf.
  const page = classifyEntry("app/x/page.tsx");
  assert.equal(page.fullyExempt, false);
  assert.equal(page.exemptNames.has("default"), true);
  assert.equal(page.exemptNames.has("generateMetadata"), true);
  assert.equal(page.exemptNames.has("yardimci"), false);
});

after(() => {
  // Sentetik projeler test başına siliniyor; burada yalnız kalıntı uyarısı.
});
