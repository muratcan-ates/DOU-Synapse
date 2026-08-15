import { expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const appRoot = join(import.meta.dir, "../app/courses/[courseId]");

test("blueprint onaylı soru havuzunu Page zarfıyla ve devam imleciyle okur", () => {
  const source = readFileSync(join(appRoot, "blueprints/page.tsx"), "utf8");

  expect(source).toContain("usePagedResource<PoolQuestion>(");
  expect(source).toContain("`/courses/${courseId}/questions?status=approved`");
  expect(source).not.toContain("useResource<PoolQuestion[]>");
  expect(source).toContain("hasMore={pool.nextCursor !== null}");
  expect(source).toContain("onLoadMore={() => void pool.loadMore()}");

  // Devam sayfası yalnız havuzu büyütür; eğitmenin mevcut seçimi `picked`
  // state'inde kalır ve soru kimliklerinden oluşturulan kayıt gövdesi değişmez.
  expect(source).toContain("const [picked, setPicked] = useState<string[] | null>(null)");
  expect(source).toContain("const current = picked ?? (items.data ?? []).map");
});

test("soru havuzu sayfalı istemci sayımlarını toplam diye sunmaz", () => {
  const source = readFileSync(join(appRoot, "questions/page.tsx"), "utf8");

  expect(source).toContain('label: "Yüklenen soru"');
  expect(source).not.toContain('label: "Toplam soru"');
  expect(source).toContain("yalnız bu ekranda yüklenen soruları kapsar");
  expect(source).toContain('aria-label="Yüklenen soruların durum süzgeci"');
});
