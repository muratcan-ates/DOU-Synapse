import { describe, expect, test } from "bun:test";
import { policyFieldChanges, policyHistoryActor, policyHistoryDate, policyHistoryPath, policyHistoryTitle } from "./policy-history";

describe("politika geçmişi", () => {
  test("API düz dizisi için sınırlı offset ve bir satır lookahead", () => {
    expect(policyHistoryPath("course", 20)).toBe("/courses/course/ai-policy/history?limit=21&offset=20");
    for (const offset of [-1, 1.5, Infinity, NaN]) expect(() => policyHistoryPath("course", offset)).toThrow();
  });
  test("ham DB alan adlarını etiketler, metadata veya bilinmeyen içeriği göstermez", () => {
    const changes = policyFieldChanges({ before: { max_hints: 1, daily_token_budget: null }, after: { max_hints: 3, daily_token_budget: 5000, updated_by: "PRIVATE_ID", unknown: "PRIVATE_CONTENT" } });
    expect(changes).toEqual([{ field: "max_hints", label: "İpucu sınırı", before: "1", after: "3" }, { field: "daily_token_budget", label: "Günlük sohbet token bütçesi", before: "Varsayılan", after: "5.000" }]);
  });
  test("oluşturma, kaldırma ve eski kayıtta bulunmama ayrıdır", () => {
    const created = { before: null, after: { max_hints: 0 } };
    expect(policyHistoryTitle(created)).toBe("Politika oluşturuldu");
    expect(policyFieldChanges(created)[0].before).toBe("Politika yok");
    const deleted = { before: created.after, after: null };
    expect(policyHistoryTitle(deleted)).toBe("Politika kaldırıldı");
    expect(policyFieldChanges(deleted)[0].after).toBe("Politika yok");
    expect(policyFieldChanges({ before: {}, after: { max_hints: null } })[0]).toMatchObject({ before: "Bu kayıtta yok", after: "Varsayılan" });
  });
  test("null kaynak tümü, boş seçim hiçbiri, silinmiş belge adı bilinmiyor", () => {
    expect(policyFieldChanges({ before: { source_document_ids: null }, after: { source_document_ids: [] } })[0]).toMatchObject({ before: "Tüm ders materyalleri", after: "Hiçbir kaynak seçilmedi" });
    const result = policyFieldChanges({ before: { source_document_ids: [] }, after: { source_document_ids: ["a", "PRIVATE_UUID"] } }, new Map([["a", "Ders.pdf"]]));
    expect(result[0].after).toBe("2 kaynak: Ders.pdf (1 kaynak adı bu listede yok)");
    expect(JSON.stringify(result)).not.toContain("PRIVATE_UUID");
  });
  test("mod kapama ve varsayılan seçimi farklıdır", () => {
    expect(policyFieldChanges({ before: { allowed_modes: null }, after: { allowed_modes: [] } })[0]).toMatchObject({ before: "Varsayılan", after: "Asistan modları kapalı" });
    expect(policyFieldChanges({ before: { allowed_modes: [] }, after: { allowed_modes: ["socratic"] } })[0].after).toBe("Sokratik koç");
  });
  test("sıra veya yalnız kayıt zamanı değişikliği sahte politika farkı üretmez", () => {
    expect(policyFieldChanges({ before: { allowed_modes: ["qa", "socratic"], source_document_ids: ["b", "a"], updated_at: "old" }, after: { allowed_modes: ["socratic", "qa"], source_document_ids: ["a", "b"], updated_at: "new" } })).toEqual([]);
  });
  test("bilinmeyen hesap adı veya ham kimlik uydurulmaz", () => {
    expect(policyHistoryActor("a", "a")).toBe("Siz");
    expect(policyHistoryActor("b", "a")).toBe("Başka bir hesap");
    expect(policyHistoryActor(null, "a")).toBe("Hesap bilgisi yok");
    expect(policyHistoryDate("bad date")).toBe("Tarih bilgisi yok");
  });
  test("bozuk eski alan değerini ham içerik olarak çizmez", () => {
    const changes = policyFieldChanges({ before: null, after: { allowed_modes: ["PRIVATE_TEXT"], max_hints: { secret: "PRIVATE_TEXT" } } });
    expect(JSON.stringify(changes)).not.toContain("PRIVATE_TEXT");
    expect(changes[0].after).toBe("Mod bilgisi okunamıyor");
  });
});
