#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { createInterface } from "node:readline/promises";

const databaseName = process.env.E2E_DATABASE_NAME ?? "dou_synapse";
const environment = (process.env.ENVIRONMENT ?? "local").toLowerCase();
const apply = process.argv.includes("--apply");

if (environment === "production") {
  throw new Error("E2E temizliği production ortamında çalıştırılamaz.");
}

const where = "code LIKE 'E2E%' AND title LIKE 'E2E Test Dersi%'";
const preview = spawnSync(
  "psql",
  [
    "-X",
    "-v",
    "ON_ERROR_STOP=1",
    "-At",
    "-d",
    databaseName,
    "-c",
    `SELECT id || E'\\t' || code || E'\\t' || title FROM courses WHERE ${where} ORDER BY created_at;`,
  ],
  { encoding: "utf8", env: process.env },
);

if (preview.error || preview.status !== 0) {
  throw new Error(`E2E kayıtları okunamadı: ${preview.error?.message ?? preview.stderr}`);
}

const rows = preview.stdout.trim() ? preview.stdout.trim().split("\n") : [];
console.log(`Veritabanı: ${databaseName}`);
console.log(`Silinmeye aday E2E dersi: ${rows.length}`);
for (const row of rows.slice(0, 20)) console.log(`  ${row}`);
if (rows.length > 20) console.log(`  ... ve ${rows.length - 20} kayıt daha`);

if (!apply || rows.length === 0) {
  if (!apply && rows.length > 0) {
    console.log("Bu yalnız önizlemeydi. Silmek için --apply kullanın.");
  }
  process.exit(0);
}

if (!process.stdin.isTTY) {
  throw new Error("Silme onayı etkileşimli terminal ister; işlem yapılmadı.");
}
const prompt = createInterface({ input: process.stdin, output: process.stdout });
const answer = await prompt.question("Yalnız yukarıdaki E2E derslerini silmek için E2E yazın: ");
prompt.close();
if (answer !== "E2E") {
  console.log("Onay verilmedi; hiçbir kayıt silinmedi.");
  process.exit(1);
}

const deleted = spawnSync(
  "psql",
  [
    "-X",
    "-v",
    "ON_ERROR_STOP=1",
    "-d",
    databaseName,
    "-c",
    `DELETE FROM courses WHERE ${where};`,
  ],
  { encoding: "utf8", env: process.env },
);
if (deleted.error || deleted.status !== 0) {
  throw new Error(`E2E kayıtları silinemedi: ${deleted.error?.message ?? deleted.stderr}`);
}
console.log(deleted.stdout.trim());
