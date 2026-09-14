/**
 * Kişisel veriler ve gizlilik bilgileri (T060).
 *
 * Metin bu dosyada DEĞİL, `docs/kvkk.md`'de. Sayfa onu derleme anında okuyup
 * çiziyor. Tek kaynak kullanımı sayfa ile belge arasındaki ayrışmayı önler.
 * Metin uygulamanın teknik davranışını ve henüz belirlenmemiş kurumsal kararları
 * açıklar; tamamlanmış kurumsal aydınlatma metni olarak sunulmaz.
 *
 * Sunucu bileşeni: dosya okuma derlemede olur, istemciye `fs` gitmez. Çıktı
 * `dangerouslySetInnerHTML` DEĞİL, React düğümleri — çevirici HTML dizesi değil
 * yapı döndürüyor, yani kaçışlama React'ta kalıyor.
 *
 * `AppShell` bilerek KULLANILMADI: o bileşen giriş yapılmamışsa "/"e yönlendirir.
 * Gizlilik bilgileri giriş yapmadan ÖNCE okunabilmeli — kişisel verisinin nasıl
 * işleneceğini öğrenmek için hesap açmak zorunda kalmak, metnin amacını tersine
 * çevirirdi.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import Link from "next/link";
import { BrandLockup } from "@/components/brand-mark";
import type { Metadata } from "next";

import { parseMarkdown, type Block, type Inline } from "@/lib/markdown";

export const metadata: Metadata = {
  title: "Kişisel Veriler ve Gizlilik",
  description:
    "DOU-Synapse'in hangi kişisel verileri işlediği, nerede sakladığı ve kimlerle paylaştığı.",
};

function renderInline(parts: Inline[]) {
  return parts.map((part, index) => {
    const key = `${part.kind}-${index}`;
    if (part.kind === "strong") {
      return (
        <strong key={key} className="font-semibold text-fg">
          {part.text}
        </strong>
      );
    }
    if (part.kind === "code") {
      return (
        <code key={key} className="rounded bg-surface px-1 py-0.5 font-mono text-[0.9em] text-fg">
          {part.text}
        </code>
      );
    }
    if (part.kind === "link") {
      // Belgedeki bağlantılar depo içi dosyalara işaret ediyor (ör.
      // `supabase/migrations/...`). Bunlar sitede bir sayfa DEĞİL, o yüzden
      // bağlantı olarak değil, kaynak göstergesi olarak çiziliyor — tıklanınca
      // 404 veren bir bağlantı, çalışmayan bir düğmenin ta kendisi olurdu.
      return (
        <span key={key} className="text-fg">
          {part.text}{" "}
          <span className="break-all text-sm text-fg-subtle">({part.href})</span>
        </span>
      );
    }
    return <span key={key}>{part.text}</span>;
  });
}

function renderBlock(block: Block, index: number) {
  const key = `${block.kind}-${index}`;

  switch (block.kind) {
    case "heading": {
      if (block.level === 1) {
        return (
          <h1 key={key} className="mb-5 text-[28px] leading-tight font-semibold tracking-tight text-fg">
            {renderInline(block.content)}
          </h1>
        );
      }
      if (block.level === 2) {
        return (
          <h2 key={key} id={`privacy-section-${index}`} className="mt-10 mb-4 scroll-mt-6 border-t border-border pt-8 text-xl leading-8 font-semibold text-fg">
            {renderInline(block.content)}
          </h2>
        );
      }
      return (
        <h3 key={key} className="mt-6 mb-2 text-base font-semibold text-fg">
          {renderInline(block.content)}
        </h3>
      );
    }
    case "paragraph":
      return (
        <p key={key} className="prose-tr mb-4 text-base leading-7 text-fg-muted">
          {renderInline(block.content)}
        </p>
      );
    case "quote":
      return (
        <div key={key} className="mb-6 rounded-xl bg-surface-sunken px-5 py-4">
          {block.content.map((paragraph, i) => (
            <p key={i} className="prose-tr mb-2 text-base leading-7 text-fg-muted last:mb-0">
              {renderInline(paragraph)}
            </p>
          ))}
        </div>
      );
    case "list":
      return (
        <ul key={key} className="mb-5 space-y-3">
          {block.items.map((item, i) => (
            <li key={i} className="flex gap-3 text-base leading-7 text-fg-muted">
              <span aria-hidden="true" className="text-fg-subtle">
                ·
              </span>
              <span>{renderInline(item)}</span>
            </li>
          ))}
        </ul>
      );
    case "table":
      return (
        <div key={key} tabIndex={0} role="region" aria-label="Veri bilgileri tablosu" className="mb-7 overflow-x-auto rounded-xl border border-border focus-visible:outline-2 focus-visible:outline-brand">
          <table className="w-full min-w-[620px] border-collapse text-left text-sm leading-6">
            <thead>
              <tr className="border-b border-border-strong">
                {block.head.map((cell, i) => (
                  <th key={i} className="bg-surface-sunken px-4 py-3 font-semibold text-fg">
                    {renderInline(cell)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, i) => (
                <tr key={i} className="border-b border-border">
                  {row.map((cell, j) => (
                    <td key={j} className="px-4 py-4 align-top text-fg-muted">
                      {renderInline(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    case "code":
      return (
        <pre
          key={key}
          className="mb-6 overflow-x-auto rounded-xl border border-border bg-surface-sunken p-5 font-mono text-sm text-fg-muted"
        >
          {block.text}
        </pre>
      );
    case "rule":
      return <hr key={key} className="my-8 border-border" />;
  }
}

export default function KvkkPage() {
  // `process.cwd()` = apps/web (Next'in çalışma dizini). Belge depo kökünde.
  const source = readFileSync(join(process.cwd(), "..", "..", "docs", "kvkk.md"), "utf8");
  const blocks = parseMarkdown(source);
  const sections = blocks.flatMap((block, index) => block.kind === "heading" && block.level === 2
    ? [{ id: `privacy-section-${index}`, title: block.content.map((part) => part.text).join("") }]
    : []);
  const contents = (
    <nav aria-label="Gizlilik bölümleri" className="space-y-1">
      {sections.map((section) => (
        <a key={section.id} href={`#${section.id}`} className="block rounded-xl px-3 py-3 text-sm leading-6 text-fg-muted motion-safe:transition-colors hover:bg-surface-sunken hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">{section.title}</a>
      ))}
    </nav>
  );

  return (
    <div className="min-h-[100dvh] bg-bg">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex min-h-[76px] max-w-[1280px] items-center justify-between gap-4 px-5 sm:px-8">
          <Link href="/" aria-label="DOU-Synapse giriş sayfası" className="rounded-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand"><BrandLockup tone="canvas" /></Link>
          <Link href="/profile" className="inline-flex min-h-11 items-center text-sm font-medium text-fg-muted hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">Hesabıma dön</Link>
        </div>
      </header>
      <main className="mx-auto grid max-w-[1280px] items-start gap-7 px-5 py-8 sm:px-8 sm:py-10 lg:grid-cols-[250px_minmax(0,1fr)]">
        <aside className="hidden rounded-[20px] border border-border bg-surface p-4 shadow-e1 lg:sticky lg:top-6 lg:block">
          <h2 className="px-3 pt-2 pb-3 text-base font-semibold text-fg">Bu sayfada</h2>
          {contents}
        </aside>
        <div className="min-w-0">
          <details className="mb-5 rounded-[20px] border border-border bg-surface px-5 py-2 shadow-e1 lg:hidden">
            <summary className="min-h-11 cursor-pointer py-3 text-base font-semibold text-fg focus-visible:outline-2 focus-visible:outline-brand">Bu sayfada</summary>
            {contents}
          </details>
          <article className="rounded-[20px] border border-border bg-surface px-5 py-7 shadow-e1 sm:px-8 sm:py-9">
            {blocks.map(renderBlock)}
          </article>
          <footer className="mt-6 text-sm leading-6 text-fg-muted">DOU-Synapse · Kişisel veriler ve gizlilik</footer>
        </div>
      </main>
    </div>
  );
}
