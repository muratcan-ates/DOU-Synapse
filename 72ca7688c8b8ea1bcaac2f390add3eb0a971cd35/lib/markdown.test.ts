import { describe, expect, test } from "bun:test";

import { parseInline, parseMarkdown, type Block } from "@/lib/markdown";

/**
 * Bu çevirici yalnız depodaki belgeleri çiziyor, ama çizdiği belge KVKK
 * aydınlatma metni — yani yanlış render edilmesi, hukuki bir metnin eksik
 * gösterilmesi demek. Testler bu yüzden "biçim güzel mi"ye değil, **metnin
 * kaybolup kaybolmadığına** bakıyor.
 */

function texts(blocks: Block[]): string {
  return JSON.stringify(blocks);
}

describe("satır içi", () => {
  test("düz metin tek parça kalır", () => {
    expect(parseInline("sade bir cümle")).toEqual([{ kind: "text", text: "sade bir cümle" }]);
  });

  test("kalın, kod ve bağlantı ayrıştırılır", () => {
    expect(parseInline("**önemli** ve `kod` ve [bağlantı](/hedef)")).toEqual([
      { kind: "strong", text: "önemli" },
      { kind: "text", text: " ve " },
      { kind: "code", text: "kod" },
      { kind: "text", text: " ve " },
      { kind: "link", text: "bağlantı", href: "/hedef" },
    ]);
  });

  test("ters tırnak içindeki yıldız kalın SAYILMAZ", () => {
    // Sıra önemli: `code` desenden önce eşleşmeli, yoksa kod örneği bozulur.
    expect(parseInline("`a ** b`")).toEqual([{ kind: "code", text: "a ** b" }]);
  });

  test("eşleşme yoksa metin aynen döner", () => {
    expect(parseInline("yıldız * tek başına")).toEqual([
      { kind: "text", text: "yıldız * tek başına" },
    ]);
  });
});

describe("blok", () => {
  test("başlık düzeyiyle birlikte", () => {
    expect(parseMarkdown("## İşlenen veriler")).toEqual([
      { kind: "heading", level: 2, content: [{ kind: "text", text: "İşlenen veriler" }] },
    ]);
  });

  test("paragrafın sarılmış satırları tek cümleye birleşir", () => {
    // Belge 88 sütuna sarılmış; sarma noktaları ekranda satır sonu görünmemeli.
    const blocks = parseMarkdown("ilk satır\ndevamı aynı cümle");
    expect(blocks).toEqual([
      { kind: "paragraph", content: [{ kind: "text", text: "ilk satır devamı aynı cümle" }] },
    ]);
  });

  test("tablo başlık ve satırlara ayrılır, ayraç satırı yutulur", () => {
    const blocks = parseMarkdown("| Veri | Nerede |\n|---|---|\n| E-posta | profiles |");
    expect(blocks).toEqual([
      {
        kind: "table",
        head: [[{ kind: "text", text: "Veri" }], [{ kind: "text", text: "Nerede" }]],
        rows: [[[{ kind: "text", text: "E-posta" }], [{ kind: "text", text: "profiles" }]]],
      },
    ]);
  });

  test("alıntı bloğu paragraflara bölünür", () => {
    const blocks = parseMarkdown("> birinci\n>\n> ikinci");
    expect(blocks).toEqual([
      {
        kind: "quote",
        content: [
          [{ kind: "text", text: "birinci" }],
          [{ kind: "text", text: "ikinci" }],
        ],
      },
    ]);
  });

  test("liste maddeleri ayrı ayrı", () => {
    const blocks = parseMarkdown("- bir\n- iki");
    expect(blocks).toEqual([
      {
        kind: "list",
        items: [[{ kind: "text", text: "bir" }], [{ kind: "text", text: "iki" }]],
      },
    ]);
  });

  test("kod bloğu satır sonlarını korur", () => {
    expect(parseMarkdown("```sql\nSELECT 1;\nSELECT 2;\n```")).toEqual([
      { kind: "code", text: "SELECT 1;\nSELECT 2;" },
    ]);
  });

  test("yatay ayraç", () => {
    expect(parseMarkdown("---")).toEqual([{ kind: "rule" }]);
  });
});

describe("gerçek belgeye karşı", () => {
  // Çeviricinin var olma sebebi tek bir dosya; o dosyanın yapısını sabitlemek,
  // biçimi değiştiğinde sessizce bozulmasını engeller.
  const kvkk = Bun.file(`${import.meta.dir}/../../../docs/kvkk.md`);

  test("KVKK metni hiçbir bloğu kaybetmeden ayrıştırılır", async () => {
    const source = await kvkk.text();
    const blocks = parseMarkdown(source);

    expect(blocks.length).toBeGreaterThan(50);
    // §8 "henüz uygulanmayanlar" başlığı metnin dürüstlük ayağı — kaybolursa
    // sayfa, uygulanmamış korumaları sessizce gizlemiş olur.
    expect(texts(blocks)).toContain("Henüz uygulanmayanlar");
    // Tablolar gerçekten tablo olarak ayrıştırılmalı, paragraf olarak değil.
    expect(blocks.some((b) => b.kind === "table")).toBe(true);
    // Ham markdown işaretçisi çıktıda KALMAMALI: kalmışsa bir blok
    // desteklenmiyor demektir ve metin bozuk görünür.
    expect(texts(blocks)).not.toContain("\\n|");
  });

  test("hiçbir başlık kaybolmaz", async () => {
    const source = await kvkk.text();
    const kaynaktakiBaslikSayisi = source
      .split("\n")
      .filter((l) => /^#{1,6} /.test(l)).length;
    const cizilenBaslikSayisi = parseMarkdown(source).filter((b) => b.kind === "heading").length;

    expect(cizilenBaslikSayisi).toBe(kaynaktakiBaslikSayisi);
  });
});
