/**
 * Küçük markdown → yapı çeviricisi. YALNIZ depodaki belgeler için.
 *
 * Neden üçüncü parti bir ayrıştırıcı değil: tek bir belgeyi (KVKK aydınlatma
 * metni) göstermek için genel amaçlı bir markdown motoru getirmek, hem paket
 * boyutu hem de HTML enjeksiyon yüzeyi bakımından orantısız olurdu. Buradaki
 * girdi kullanıcıdan GELMEZ; depoda duran, bizim yazdığımız bir dosyadır ve
 * derleme anında okunur.
 *
 * Bu yüzden çıktı da HTML DİZESİ DEĞİL, yapıdır: React onu kendi kaçışlamasıyla
 * çizer, yani `dangerouslySetInnerHTML` hiç kullanılmaz. Belgeye bir gün dışarıdan
 * metin karışsa bile enjeksiyon yolu yok.
 *
 * Desteklenen alt küme, `docs/kvkk.md`'de GERÇEKTEN kullanılanlarla sınırlı
 * (sayıldı): başlık, paragraf, alıntı, madde listesi, tablo, yatay ayraç, kod
 * bloğu; satır içinde kalın, kod ve bağlantı. Desteklenmeyen bir şey eklenirse
 * metin kaybolmaz — ham hâliyle paragraf olarak görünür, yani hata sessiz değil
 * görünür olur.
 */

export type Inline =
  | { kind: "text"; text: string }
  | { kind: "strong"; text: string }
  | { kind: "code"; text: string }
  | { kind: "link"; text: string; href: string };

export type Block =
  | { kind: "heading"; level: number; content: Inline[] }
  | { kind: "paragraph"; content: Inline[] }
  | { kind: "quote"; content: Inline[][] }
  | { kind: "list"; items: Inline[][] }
  | { kind: "table"; head: Inline[][]; rows: Inline[][][] }
  | { kind: "rule" }
  | { kind: "code"; text: string };

/** `**kalın**`, `` `kod` ``, `[metin](hedef)` — iç içe geçme YOK, gerek de yok. */
export function parseInline(raw: string): Inline[] {
  const out: Inline[] = [];
  // Tek bir düzenli ifade: alternatiflerin sırası önemli, `code` en önce çünkü
  // ters tırnak içindeki yıldız kalın sayılmamalı.
  const pattern = /`([^`]+)`|\*\*([^*]+)\*\*|\[([^\]]+)\]\(([^)]+)\)/g;
  let last = 0;
  for (const m of raw.matchAll(pattern)) {
    const at = m.index ?? 0;
    if (at > last) out.push({ kind: "text", text: raw.slice(last, at) });
    if (m[1] !== undefined) out.push({ kind: "code", text: m[1] });
    else if (m[2] !== undefined) out.push({ kind: "strong", text: m[2] });
    else if (m[3] !== undefined) out.push({ kind: "link", text: m[3], href: m[4] });
    last = at + m[0].length;
  }
  if (last < raw.length) out.push({ kind: "text", text: raw.slice(last) });
  return out.length > 0 ? out : [{ kind: "text", text: raw }];
}

function tableCells(line: string): Inline[][] {
  return line
    .replace(/^\||\|$/g, "")
    .split("|")
    .map((cell) => parseInline(cell.trim()));
}

/** Ayraç satırı mı (`|---|---|`)? Tablo başlığını gövdeden ayıran satır. */
function isTableDivider(line: string): boolean {
  return /^\|?[\s:|-]+\|[\s:|-]*$/.test(line) && line.includes("-");
}

export function parseMarkdown(source: string): Block[] {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) {
      i += 1;
      continue;
    }

    if (line.trim() === "---") {
      blocks.push({ kind: "rule" });
      i += 1;
      continue;
    }

    if (line.startsWith("```")) {
      const body: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i].startsWith("```")) {
        body.push(lines[i]);
        i += 1;
      }
      i += 1; // kapanış çiti
      blocks.push({ kind: "code", text: body.join("\n") });
      continue;
    }

    const heading = /^(#{1,6}) (.*)$/.exec(line);
    if (heading) {
      blocks.push({
        kind: "heading",
        level: heading[1].length,
        content: parseInline(heading[2]),
      });
      i += 1;
      continue;
    }

    if (line.startsWith(">")) {
      const paragraphs: Inline[][] = [];
      let current: string[] = [];
      while (i < lines.length && lines[i].startsWith(">")) {
        const text = lines[i].replace(/^>\s?/, "");
        if (text.trim()) current.push(text);
        else if (current.length > 0) {
          paragraphs.push(parseInline(current.join(" ")));
          current = [];
        }
        i += 1;
      }
      if (current.length > 0) paragraphs.push(parseInline(current.join(" ")));
      blocks.push({ kind: "quote", content: paragraphs });
      continue;
    }

    if (line.startsWith("|")) {
      const head = tableCells(line);
      i += 1;
      if (i < lines.length && isTableDivider(lines[i])) i += 1;
      const rows: Inline[][][] = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        rows.push(tableCells(lines[i]));
        i += 1;
      }
      blocks.push({ kind: "table", head, rows });
      continue;
    }

    if (/^[-*] /.test(line)) {
      const items: Inline[][] = [];
      while (i < lines.length && /^[-*] /.test(lines[i])) {
        items.push(parseInline(lines[i].slice(2)));
        i += 1;
      }
      blocks.push({ kind: "list", items });
      continue;
    }

    // Paragraf: boş satıra kadar birleştirilir. Markdown'ın satır sonlarını
    // boşluğa çevirmesi bilinçli — belgede satırlar 88 sütuna sarılmış ve
    // sarma noktaları ekranda satır sonu olarak görünmemeli.
    const paragraph: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].startsWith(">") &&
      !lines[i].startsWith("|") &&
      !lines[i].startsWith("```") &&
      !/^[-*] /.test(lines[i]) &&
      !/^#{1,6} /.test(lines[i]) &&
      lines[i].trim() !== "---"
    ) {
      paragraph.push(lines[i]);
      i += 1;
    }
    blocks.push({ kind: "paragraph", content: parseInline(paragraph.join(" ")) });
  }

  return blocks;
}
