/**
 * KVKK aydınlatma metni (T060).
 *
 * Metin bu dosyada DEĞİL, `docs/kvkk.md`'de. Sayfa onu derleme anında okuyup
 * çiziyor. Kopyalansaydı iki nüsha olurdu ve hukuki bir metnin iki nüshası, er
 * geç birinin güncellenip diğerinin unutulacağı bir ayrışma demektir (Anayasa XI).
 * Belgeyi R5 yazdı ve her iddiasının kodda satır karşılığı var; sayfanın işi onu
 * göstermek, yeniden yazmak değil.
 *
 * Sunucu bileşeni: dosya okuma derlemede olur, istemciye `fs` gitmez. Çıktı
 * `dangerouslySetInnerHTML` DEĞİL, React düğümleri — çevirici HTML dizesi değil
 * yapı döndürüyor, yani kaçışlama React'ta kalıyor.
 *
 * `AppShell` bilerek KULLANILMADI: o bileşen giriş yapılmamışsa "/"e yönlendirir.
 * Aydınlatma metni giriş yapmadan ÖNCE okunabilmeli — kişisel verisinin nasıl
 * işleneceğini öğrenmek için hesap açmak zorunda kalmak, metnin amacını tersine
 * çevirirdi.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import Link from "next/link";
import type { Metadata } from "next";

import { parseMarkdown, type Block, type Inline } from "@/lib/markdown";

export const metadata: Metadata = {
  title: "KVKK Aydınlatma Metni",
  description:
    "DOU-Synapse'in hangi kişisel verileri işlediği, nerede sakladığı ve kimlerle paylaştığı.",
};

function renderInline(parts: Inline[]) {
  return parts.map((part, index) => {
    const key = `${part.kind}-${index}`;
    if (part.kind === "strong") {
      return (
        <strong key={key} className="font-medium text-fg">
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
          <span className="font-mono text-xs text-fg-subtle">({part.href})</span>
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
          <h1 key={key} className="mb-2 text-3xl font-semibold tracking-tight text-fg">
            {renderInline(block.content)}
          </h1>
        );
      }
      if (block.level === 2) {
        return (
          <h2 key={key} className="mt-10 mb-3 text-xl font-medium text-fg">
            {renderInline(block.content)}
          </h2>
        );
      }
      return (
        <h3 key={key} className="mt-6 mb-2 text-base font-medium text-fg">
          {renderInline(block.content)}
        </h3>
      );
    }
    case "paragraph":
      return (
        <p key={key} className="prose-tr mb-4 text-sm leading-6 text-fg-muted">
          {renderInline(block.content)}
        </p>
      );
    case "quote":
      return (
        <div key={key} className="mb-6 rounded-lg border border-border bg-surface px-4 py-3">
          {block.content.map((paragraph, i) => (
            <p key={i} className="prose-tr mb-2 text-sm leading-6 text-fg-muted last:mb-0">
              {renderInline(paragraph)}
            </p>
          ))}
        </div>
      );
    case "list":
      return (
        <ul key={key} className="mb-4 space-y-1.5">
          {block.items.map((item, i) => (
            <li key={i} className="prose-tr flex gap-2 text-sm leading-6 text-fg-muted">
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
        <div key={key} className="mb-6 overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-border-strong">
                {block.head.map((cell, i) => (
                  <th key={i} className="py-2 pr-4 font-medium text-fg">
                    {renderInline(cell)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, i) => (
                <tr key={i} className="border-b border-border">
                  {row.map((cell, j) => (
                    <td key={j} className="py-2 pr-4 align-top text-fg-muted">
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
          className="mb-6 overflow-x-auto rounded-lg border border-border bg-surface p-4 font-mono text-xs text-fg-muted"
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

  return (
    <div className="min-h-screen">
      <header className="border-b border-border">
        <div className="mx-auto flex h-14 max-w-[1200px] items-center gap-2 px-4">
          <Link href="/" className="flex items-center gap-2">
            <span className="text-sm font-semibold text-brand">DOU</span>
            <span className="text-sm font-semibold text-fg">Synapse</span>
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-[70ch] px-4 py-10">
        {blocks.map(renderBlock)}
      </main>
    </div>
  );
}
