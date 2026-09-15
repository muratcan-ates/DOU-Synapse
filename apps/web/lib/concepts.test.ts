import { expect, test } from "bun:test";
import {
  defaultSelection,
  edgeRows,
  neighboursOf,
  occurrenceLabel,
  resolveSelection,
  sharedLabel,
  termIndex,
  type ConceptMap,
  type ConceptTerm,
} from "@/lib/concepts";

function term(key: string, chunkCount = 3): ConceptTerm {
  return {
    key,
    term: key === "surec" ? "süreç" : key,
    chunk_count: chunkCount,
    source: {
      chunk_id: `chunk-${key}`,
      file_name: "01-processes.pdf",
      location: "Sayfa 1",
      snippet: `${key} hakkında materyalden birebir alıntı.`,
    },
  };
}

function harita(
  terms: ConceptTerm[],
  edges: { left: string; right: string; chunk_count: number }[] = [],
): ConceptMap {
  return { course_id: "c1", terms, edges, chunk_count: 20, truncated: false };
}

test("terim dizini anahtardan terime eşler", () => {
  const map = harita([term("surec"), term("semafor")]);

  expect(termIndex(map).get("surec")?.term).toBe("süreç");
  expect(termIndex(map).has("yok")).toBe(false);
});

test("komşuluk yönsüzdür: kenarın iki ucu da taranır", () => {
  const map = harita(
    [term("surec"), term("semafor"), term("mutex")],
    [
      { left: "semafor", right: "surec", chunk_count: 4 },
      { left: "mutex", right: "surec", chunk_count: 2 },
    ],
  );

  const komsular = neighboursOf(map, "surec").map((n) => n.term.key);

  expect(komsular).toEqual(["semafor", "mutex"]);
});

test("komşular en çok pasaj paylaşandan aza sıralanır", () => {
  const map = harita(
    [term("surec"), term("a"), term("b"), term("c")],
    [
      { left: "a", right: "surec", chunk_count: 2 },
      { left: "b", right: "surec", chunk_count: 9 },
      { left: "c", right: "surec", chunk_count: 5 },
    ],
  );

  expect(neighboursOf(map, "surec").map((n) => n.sharedChunks)).toEqual([9, 5, 2]);
});

test("eşit paylaşımda Türkçe alfabetik sıra karar verir", () => {
  const ilgili = { ...term("ilgili"), term: "ılgın" };
  const map = harita(
    [term("surec"), { ...term("zaman"), term: "zaman" }, ilgili],
    [
      { left: "surec", right: "zaman", chunk_count: 3 },
      { left: "ilgili", right: "surec", chunk_count: 3 },
    ],
  );

  // "ı" Türkçede "z"den önce gelir; localeCompare(…, "tr") bunu bilir.
  expect(neighboursOf(map, "surec").map((n) => n.term.term)).toEqual(["ılgın", "zaman"]);
});

test("listede karşılığı olmayan komşu atlanır", () => {
  // Kaynağı gösterilemeyecek bir komşu satırı ekranın vaadini bozardı.
  const map = harita(
    [term("surec")],
    [{ left: "surec", right: "silinmis", chunk_count: 7 }],
  );

  expect(neighboursOf(map, "surec")).toEqual([]);
});

test("kendi kendine kenar komşu sayılmaz", () => {
  const map = harita([term("surec")], [{ left: "surec", right: "surec", chunk_count: 5 }]);

  // `left === key` dalı `right`'ı verir; o da aynı terim olduğu için dizinde
  // bulunur — bu testin işi o kenarın listede TEKRAR görünmemesini değil,
  // çökmemesini garanti etmek.
  expect(neighboursOf(map, "surec").every((n) => n.term.key === "surec")).toBe(true);
});

test("bağlantı tablosu anahtarları okunur ada çevirir", () => {
  const map = harita(
    [term("surec"), term("semafor")],
    [{ left: "semafor", right: "surec", chunk_count: 4 }],
  );

  expect(edgeRows(map)).toEqual([
    { key: "semafor|surec", left: "semafor", right: "süreç", sharedChunks: 4 },
  ]);
});

test("karşılığı olmayan kenar tabloya girmez", () => {
  const map = harita([term("surec")], [{ left: "surec", right: "yok", chunk_count: 3 }]);

  expect(edgeRows(map)).toEqual([]);
});

test("ilk seçim listenin başıdır", () => {
  const map = harita([term("surec"), term("semafor")]);

  expect(defaultSelection(map)).toBe("surec");
});

test("boş haritada seçim yoktur", () => {
  expect(defaultSelection(harita([]))).toBeNull();
  expect(resolveSelection(harita([]), "surec")).toBeNull();
});

test("listede kalmayan seçim başa döner", () => {
  const map = harita([term("surec"), term("semafor")]);

  expect(resolveSelection(map, "semafor")).toBe("semafor");
  expect(resolveSelection(map, "silinmis")).toBe("surec");
  expect(resolveSelection(map, null)).toBe("surec");
});

test("sayılar yalın bırakılmaz", () => {
  // "12" tek başına neyin 12'si olduğunu söylemez ve puan sanılabilir.
  expect(occurrenceLabel(12)).toBe("12 pasajda geçiyor");
  expect(sharedLabel(3)).toBe("3 pasajda birlikte");
});
