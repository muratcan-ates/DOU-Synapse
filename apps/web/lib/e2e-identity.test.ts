import { expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { verifyDatabaseIdentity } from "../e2e/cleanup";

const PROBE = { code: "E2E-testrun00001-1999", title: "E2E kimlik sondası" };

function harness(visible: boolean) {
  const calls: string[] = [];
  return {
    calls,
    run: () =>
      verifyDatabaseIdentity({
        databaseName: "dou_synapse_e2e_birim",
        probe: PROBE,
        apiHasCourse: async () => {
          calls.push("read");
          return visible;
        },
        writeProbe: () => void calls.push("write"),
        deleteProbe: () => void calls.push("delete"),
      }),
  };
}

test("ayrışma durumunda fırlatır ve sonda İKİ durumda da silinir", async () => {
  const kirik = harness(false);
  await expect(kirik.run()).rejects.toThrow("ayrışmış");
  expect(kirik.calls).toEqual(["write", "read", "delete"]);

  const saglam = harness(true);
  await saglam.run();
  expect(saglam.calls).toEqual(["write", "read", "delete"]);
});

test("kurulum API üzerinden hiçbir yazma yapmaz (kaynak değişmezi)", () => {
  // İlk sürüm nöbetçiyi API'den POST'luyordu ve ayrışma durumunda API'nin
  // gerçek veritabanında kalıntı bırakıyordu. Bu tarama, birinin o deseni
  // geri getirmesini kırmızıya çevirir: kurulum dosyasında yazma metodu yoktur.
  const source = readFileSync(join(import.meta.dir, "../e2e/global-setup.ts"), "utf8");
  for (const method of ["POST", "PUT", "PATCH", "DELETE"]) {
    expect(source).not.toContain(`"${method}"`);
    expect(source).not.toContain(`'${method}'`);
  }
});
