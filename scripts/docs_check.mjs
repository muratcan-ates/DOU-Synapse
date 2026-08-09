#!/usr/bin/env node
/**
 * Belge doğruluğu kapısı — Anayasa III (Ölçmeden İddia Etme).
 *
 * Bu deponun belgelerindeki test sayıları üç kez elle düzeltildi ve üçünde de
 * bayatladı. Tek oturumda 664 → 668 → 677 → 724 oldu; düzeltme yazılırken sayı
 * çoktan değişmişti. Bugün aynı komut için belgelerde ALTI farklı değer dolaşıyor
 * (664, 530, 479, 473, 92, 68). Sorun dikkatsizlik değil: elle tutulan bir sayı,
 * onu üreten koddan bağımsız yaşadığı sürece bayatlar. `tasks.md` T308 bunu kendi
 * kapanış notunda yazıyor — "sayıyı kaynağından üreten kapı inmeden dördüncüsü de
 * gelecek".
 *
 * Bu betik dördüncüsünü engeller. Belgeye yazılan her canlı sayı buradan gelir:
 * betik sayıyı ÖLÇER, belgedeki değerle karşılaştırır, uyuşmazsa çıkış kodu 1'dir.
 * `scripts/contrast.mjs` renk oranları için ne yapıyorsa bu da sayılar için onu
 * yapar; oradaki doktrin burada da geçerlidir: ölçülüp çıkış kodunu etkilemeyen
 * sayı, ölçülmemiş sayıdır.
 *
 * Koşturma:
 *   node scripts/docs_check.mjs              # kapı — uyuşmazlık varsa çıkış 1
 *   node scripts/docs_check.mjs --metrikler  # yalnız ölçülen gerçekler
 *   node scripts/docs_check.mjs --duzelt     # canlı iddiaları ölçülen değere yaz
 *
 * ## Belgeye nasıl işaret konur
 *
 * Canlı iddia — sayı ölçümden gelir, bayatlayamaz:
 *
 *     **724 otomatik test** <!-- docs-check: backend.tests = 724 -->
 *     uv run pytest -q   # 724 yeşil olmalı   # docs-check: backend.tests = 724
 *
 * İşaret DEĞERİ taşır, konumu değil: satırın neresinde geçerse geçsin o değer
 * aranır. `--duzelt` hem metindeki hem işaretteki değeri birlikte yeniler.
 *
 * Tarihsel ölçüm — o gün doğruydu, bugün de öyle kalmalı:
 *
 *     **92 test yeşil** <!-- docs-check: tarihsel 92 · 2026-07-20 -->
 *
 * Tarihsel iddia ölçümle karşılaştırılmaz; işaretin içindeki değerle karşılaştırılır.
 * Böylece devir belgelerindeki kayıt SİLİNMEZ (docs kuralı: "tarihsel ölçümü silme,
 * tarihsel olarak etiketle") ama biri onu sessizce güncelleyemez de — kayıt oynarsa
 * kapı kırmızı yanar. Tarih işaretin içindedir, çünkü "92" tek başına hangi güne ait
 * olduğunu söylemez.
 *
 * ## Kapının kapsamı — ve kapsamadıkları
 *
 * Tarama, sapmanın fiilen gözlendiği sınıflara odaklanır (§DEDEKTORLER). Belgedeki
 * her sayı denetlenmez ve bu bilinçlidir: "≥15 vaka" gibi eşikler, dosya başına test
 * sayıları ve gecikme ölçümleri farklı kaynaklardan gelir. Kapı ne kapsamadığını her
 * koşuda yazar; sessiz kapsam yoktur.
 */

import { spawnSync } from "node:child_process";
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

// --- Kabuk -----------------------------------------------------------------

/**
 * Komutu koşturur, stdout + stderr'i birlikte döndürür.
 *
 * `bun test` özetini stderr'e yazar; yalnız stdout okunursa sayı bulunamaz ve bu,
 * testin yokluğu gibi değil betiğin bozukluğu gibi okunur.
 */
function calistir(komut, argumanlar, calismaDizini) {
  const sonuc = spawnSync(komut, argumanlar, {
    cwd: join(ROOT, calismaDizini),
    encoding: "utf8",
    maxBuffer: 32 * 1024 * 1024,
  });
  if (sonuc.error) {
    throw new Error(`${komut} koşturulamadı: ${sonuc.error.message}`);
  }
  return `${sonuc.stdout ?? ""}\n${sonuc.stderr ?? ""}`;
}

/** Çıktıdan tek bir sayı çeker; bulamazsa ölçüm başarısızdır, tahmin edilmez. */
function tekSayi(cikti, kalip, ne) {
  const eslesme = cikti.match(kalip);
  if (!eslesme) {
    throw new Error(`${ne} çıktıdan okunamadı. Ham çıktı:\n${cikti.trim().slice(-800)}`);
  }
  return Number(eslesme[1]);
}

// --- Ölçülen gerçekler -----------------------------------------------------

/**
 * Her metrik kendi kaynağını KENDİSİ koşturur. Buradaki `komut` alanı belgeye ve
 * rapora yazılacak olandır: bir sayının doğrusu, sayı değil onu üreten komuttur.
 */
const METRIKLER = {
  "backend.tests": {
    aciklama: "Backend'de toplanan test sayısı",
    komut: "cd apps/api && uv run pytest --collect-only -q",
    olc: () =>
      tekSayi(
        calistir("uv", ["run", "pytest", "--collect-only", "-q"], "apps/api"),
        /^(\d+) tests? collected/m,
        "backend test sayısı",
      ),
  },

  "frontend.tests": {
    aciklama: "Frontend birim test sayısı",
    komut: "cd apps/web && bun test lib/",
    olc: () =>
      tekSayi(
        calistir("bun", ["test", "lib/"], "apps/web"),
        /Ran (\d+) tests?/,
        "frontend test sayısı",
      ),
  },

  "frontend.testFiles": {
    aciklama: "Frontend birim testlerinin dağıldığı dosya sayısı",
    komut: "cd apps/web && bun test lib/",
    olc: () =>
      tekSayi(
        calistir("bun", ["test", "lib/"], "apps/web"),
        /across (\d+) files?/,
        "frontend test dosyası sayısı",
      ),
  },

  "e2e.tests": {
    aciklama: "Playwright vaka sayısı",
    // `bunx playwright` KULLANILMAZ: ayrı bir kopya indirir ve "two different
    // versions" hatası verir. Depoya kurulu ikili çağrılır.
    komut: "cd apps/web && ./node_modules/.bin/playwright test --list",
    olc: () =>
      tekSayi(
        calistir("./node_modules/.bin/playwright", ["test", "--list"], "apps/web"),
        /Total: (\d+) tests?/,
        "E2E vaka sayısı",
      ),
  },

  "migrations.count": {
    aciklama: "Migration dosyası sayısı",
    komut: "ls supabase/migrations/*.sql",
    olc: () => migrationDosyalari().length,
  },

  "migrations.list": {
    aciklama: "Migration numaraları (virgülle)",
    komut: "ls supabase/migrations/*.sql",
    metin: true,
    olc: () => migrationDosyalari().map((d) => d.slice(0, 4)).join(","),
  },

  "tables.count": {
    aciklama: "Migration'larda CREATE TABLE ile kurulan tablo sayısı",
    komut: "grep -ihoE 'create table( if not exists)? [a-z_]+' supabase/migrations/*.sql",
    olc: () => tabloAdlari().length,
  },

  "screens.count": {
    aciklama: "Web arayüzündeki ekran (page.tsx) sayısı",
    komut: "find apps/web/app -name page.tsx",
    olc: () => ekranlar().length,
  },

  "sampleData.files": {
    aciklama: "Örnek materyal paketindeki teslim edilen dosya sayısı",
    komut: "find sample_data/isletim-sistemleri -type f -not -name '*.md' | wc -l",
    olc: () => materyalDosyalari().length,
  },
};

function migrationDosyalari() {
  return readdirSync(join(ROOT, "supabase", "migrations"))
    .filter((d) => d.endsWith(".sql"))
    .sort();
}

function tabloAdlari() {
  const adlar = new Set();
  for (const dosya of migrationDosyalari()) {
    const sql = readFileSync(join(ROOT, "supabase", "migrations", dosya), "utf8");
    for (const m of sql.matchAll(/create\s+table\s+(?:if\s+not\s+exists\s+)?([a-z_][a-z0-9_.]*)/gi)) {
      adlar.add(m[1].toLowerCase());
    }
  }
  return [...adlar].sort();
}

/** `apps/web/app` altındaki her `page.tsx` bir ekrandır. */
function ekranlar() {
  const bulunan = [];
  const gez = (dizin) => {
    for (const girdi of readdirSync(dizin, { withFileTypes: true })) {
      const yol = join(dizin, girdi.name);
      if (girdi.isDirectory()) gez(yol);
      else if (girdi.name === "page.tsx") bulunan.push(relative(ROOT, yol));
    }
  };
  gez(join(ROOT, "apps", "web", "app"));
  return bulunan.sort();
}

/**
 * Kabul edilen uzantılar KODDAN okunur, buraya elle yazılmaz.
 *
 * `validation.py::_MAGIC_BYTES` ingestion'ın gerçekten kabul ettiği kümedir; bir
 * uzantı oraya eklenirse materyal sayımı kendiliğinden doğru kalır.
 */
function kabulEdilenUzantilar() {
  const kaynak = readFileSync(
    join(ROOT, "apps", "api", "app", "modules", "ingestion", "validation.py"),
    "utf8",
  );
  const blok = kaynak.match(/_MAGIC_BYTES[^=]*=\s*\{([\s\S]*?)\n\}/);
  if (!blok) throw new Error("validation.py içinde _MAGIC_BYTES bulunamadı");
  return new Set([...blok[1].matchAll(/"(\.[a-z0-9]+)"\s*:/gi)].map((m) => m[1].toLowerCase()));
}

/**
 * Teslim edilen materyal — `.md` HARİÇ.
 *
 * `.md` dosyaları paketin ÜRÜNÜ değil KAYNAĞIDIR: `generate_material.py` onlardan
 * PDF ve PPTX üretir ("Kaynak Markdown depoda durur, ikili dosya ondan yeniden
 * üretilebilir"). Sayıma katılsalardı her materyal iki kez sayılırdı.
 */
function materyalDosyalari() {
  const uzantilar = kabulEdilenUzantilar();
  const bulunan = [];
  const gez = (dizin) => {
    for (const girdi of readdirSync(dizin, { withFileTypes: true })) {
      const yol = join(dizin, girdi.name);
      if (girdi.isDirectory()) {
        gez(yol);
        continue;
      }
      const uzanti = girdi.name.slice(girdi.name.lastIndexOf(".")).toLowerCase();
      if (uzanti !== ".md" && uzantilar.has(uzanti)) bulunan.push(relative(ROOT, yol));
    }
  };
  gez(join(ROOT, "sample_data", "isletim-sistemleri"));
  return bulunan.sort();
}

// --- Taranan belgeler ------------------------------------------------------

/**
 * Kapının baktığı ağaçlar. `specs/002-production-hardening` bilerek içeridedir:
 * bu şerit kendi kuralını ilk ihlal eden olmamalı (T308 notu).
 */
const TARANAN = [
  { tur: "dosya", yol: "README.md" },
  { tur: "dosya", yol: "ARCHITECTURE.md" },
  { tur: "dosya", yol: "PLAN.md" },
  { tur: "dosya", yol: "DESIGN.md" },
  { tur: "dizin", yol: "docs" },
  { tur: "dizin", yol: "specs" },
  { tur: "dizin", yol: "evaluation" },
];

/**
 * Denetimden muaf tutulanlar — her biri gerekçesiyle ve sahibiyle.
 *
 * Muafiyet ÖLÜ kalamaz: dosya artık yoksa kapı kırmızı yanar. Böylece muafiyet
 * listesi sessizce büyüyen bir çöplük olmaz.
 */
const MUAFLAR = [
  {
    yol: "specs/002-production-hardening/tasks.md",
    gerekce:
      "Görev defteri: sayıları tarihli DONE notlarının içinde ve doğası gereği tarihsel " +
      "kayıt. Ayrıca hiçbir işçi şeridi bu dosyayı değiştirmez; işaretleri entegratör koyar.",
    sahibi: "entegratör",
  },
  {
    yol: "specs/001-course-assistant-mvp/tasks.md",
    gerekce: "Aynı sebep: kapanmış 001 şartnamesinin görev defteri, tarihli DONE notlarından ibaret.",
    sahibi: "entegratör",
  },
];

/**
 * Tarihsel arşiv — ölçümleri YAPISI GEREĞİ tarihseldir.
 *
 * `docs/team/**` tarihli devir ve brifing kayıtlarından oluşur: her dosya belirli
 * bir günün durumunu anlatır ve o günden sonra değişmemesi gerekir. Bunların
 * içindeki 40 küsur sayıya tek tek `tarihsel` işareti koymak, aynı bilgiyi kırk
 * kez tekrar etmek olurdu. Bunun yerine arşiv dizin düzeyinde beyan edilir ve
 * kapı her koşuda bunu YAZAR — kapsam dışı kalan hiçbir şey sessiz değildir.
 *
 * Bedeli açıkça kabul edilmiştir: arşive bugün eklenen CANLI bir iddia kapıya
 * takılmaz. Arşiv yeni ölçüm yeri değil, kayıt yeri olduğu için bu bilinçlidir.
 */
const TARIHSEL_ARSIV = [
  {
    yol: "docs/team",
    gerekce: "Tarihli devir/brifing kayıtları; her dosya kendi gününün durumunu anlatır.",
  },
];

function arsivde(dosya) {
  return TARIHSEL_ARSIV.some((a) => dosya === a.yol || dosya.startsWith(`${a.yol}/`));
}

function markdownDosyalari() {
  const bulunan = [];
  const gez = (dizin) => {
    for (const girdi of readdirSync(dizin, { withFileTypes: true })) {
      const yol = join(dizin, girdi.name);
      if (girdi.isDirectory()) {
        if (girdi.name === "node_modules" || girdi.name === "images" || girdi.name === "screenshots") continue;
        gez(yol);
      } else if (girdi.name.endsWith(".md")) {
        bulunan.push(relative(ROOT, yol));
      }
    }
  };
  for (const hedef of TARANAN) {
    if (hedef.tur === "dosya") bulunan.push(hedef.yol);
    else gez(join(ROOT, hedef.yol));
  }
  const muafYollar = new Set(MUAFLAR.map((m) => m.yol));
  return bulunan.filter((y) => !muafYollar.has(y)).sort();
}

// --- İşaretler -------------------------------------------------------------

/**
 * İşaret iki biçimde yazılabilir ve ikisi de aynı şeyi söyler:
 *
 *     ... **724 otomatik test** <!-- docs-check: backend.tests = 724 -->
 *     uv run pytest -q   # 724 yeşil olmalı   # docs-check: backend.tests = 724
 *
 * İkinci biçim şart: iddiaların çoğu kod bloğunun İÇİNDE yaşıyor ve oraya HTML
 * yorumu koymak kod bloğunda görünür metin bırakır.
 *
 * İşaret DEĞERİ taşır, konumu değil. İlk tasarım "işaretin solundaki sayı"
 * kuralına dayanıyordu ve `# 664 test yeşil olmalı (~70-120 sn)` satırında 120'yi
 * yakalıyordu. Değere bağlamak bu sınıfı tamamen kapatır: sayı satırın neresinde
 * olursa olsun, hangi biçimde (`tests-664_ge%C3%A7ti` rozeti dahil) yazılmış olursa
 * olsun bulunur.
 */
const ISARET = /(?:<!--|#|\/\/)\s*docs-check:\s*(.*?)\s*(?:-->|$)/g;

/** Satırdaki işaretleri boşlukla değiştirir; kalan metin iddianın kendisidir. */
function isaretsizMetin(satir) {
  return satir.replace(new RegExp(ISARET.source, "g"), (m) => " ".repeat(m.length));
}

/**
 * Bir değeri satırda BAĞIMSIZ olarak arar/değiştirir.
 *
 * `(?<!\d)664(?!\d)` sınırları, `1664` ya da `6640` içinde yanlışlıkla eşleşmeyi
 * engeller ama `tests-664_ge%C3%A7ti` içindeki 664'ü bulur — rozet de kapıya girsin diye.
 */
function degerKalibi(deger) {
  const kacisli = String(deger).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return /^\d/.test(String(deger))
    ? new RegExp(`(?<!\\d)${kacisli}(?!\\d)`, "g")
    : new RegExp(kacisli, "g");
}

/**
 * Satırdaki eski değeri yenisiyle değiştirir — metinde VE işaretin kendisinde.
 *
 * İşaret bölgesi ayrı ele alınır: metinde `(?<!\d)` sınırlarıyla bağımsız geçişler
 * değişir, işarette ise yalnız `= <değer>` kısmı. Böylece `--duzelt` sonrası işaret
 * ile metin aynı şeyi söylemeye devam eder; ikisinin ayrışması kapının koruduğu
 * şeyin ta kendisidir.
 */
function satiriYenidenYaz(satir, eski, yeni) {
  const parcalar = [];
  let son = 0;
  ISARET.lastIndex = 0;
  let m;
  while ((m = ISARET.exec(satir)) !== null) {
    parcalar.push({ metin: satir.slice(son, m.index), isaret: false });
    parcalar.push({ metin: m[0], isaret: true });
    son = m.index + m[0].length;
    if (m.index === ISARET.lastIndex) ISARET.lastIndex++;
  }
  parcalar.push({ metin: satir.slice(son), isaret: false });

  return parcalar
    .map((p) =>
      p.isaret
        ? p.metin.replace(/(=\s*)(.+?)(\s*(?:-->)?)$/, (_, once, deger, sonra) =>
            deger.trim() === eski ? `${once}${yeni}${sonra}` : `${once}${deger}${sonra}`,
          )
        : p.metin.replace(degerKalibi(eski), yeni),
    )
    .join("");
}

function iddialariTopla() {
  const iddialar = [];
  for (const dosya of markdownDosyalari()) {
    const satirlar = readFileSync(join(ROOT, dosya), "utf8").split("\n");
    satirlar.forEach((satir, i) => {
      ISARET.lastIndex = 0;
      let m;
      while ((m = ISARET.exec(satir)) !== null) {
        iddialar.push({ dosya, satirNo: i + 1, satir, isaret: m[1], indeks: m.index });
        if (m.index === ISARET.lastIndex) ISARET.lastIndex++;
      }
    });
  }
  return iddialar;
}

// --- İşaretsiz canlı iddia dedektörleri ------------------------------------

/**
 * §DEDEKTORLER — sapmanın fiilen gözlendiği sınıflar.
 *
 * Her dedektör dar tutulmuştur. Geniş bir "sayı + test" taraması onlarca yanlış
 * pozitif üretir ("≥15 vaka" eşiği, dosya başına test sayısı, gecikme ölçümü) ve
 * gürültülü bir kapı kapatılan kapıdır. Buradaki her kalıp, 9-10 Ağustos'ta
 * belgelerde FİİLEN bayatlamış bir iddiaya karşılık gelir.
 */
const DEDEKTORLER = [
  {
    ad: "pytest komutunun yanındaki sayı",
    metrik: "backend.tests",
    kalip: /uv run pytest[^\n]*?(?<![§\d])\d[\d.,]*|(?<![§\d])\d[\d.,]*[^\n]{0,30}uv run pytest/i,
  },
  {
    ad: '"N otomatik test"',
    metrik: "backend.tests",
    kalip: /(?<![§\d])\d[\d.,]*\s*(\*\*)?\s*otomatik test/i,
  },
  {
    ad: "README test rozeti",
    metrik: "backend.tests",
    kalip: /img\.shields\.io\/badge\/tests-\d/i,
  },
  {
    ad: "bun test komutunun yanındaki sayı",
    metrik: "frontend.tests",
    kalip: /bun test lib\/[^\n]*?(?<![§\d])\d[\d.,]*|(?<![§\d])\d[\d.,]*[^\n]{0,30}bun test lib\//i,
  },
  // Sayım dedektörleri iki fazladan sınır taşır ve ikisi de ölçülerek eklendi:
  //
  //   `-` öncesi YASAK — `çekirdek 3-4 tablo` (PLAN.md) bir tahmin aralığıdır,
  //   ölçüm değil; aralığın ikinci ucu sayım gibi okunuyordu.
  //
  //   en fazla iki hane — `500 ekranı` (runbook.md) HTTP durum kodudur. Bu deponun
  //   ekran ya da tablo sayısı üç haneye çıkmaz; sınır, sayımı durum kodundan ayırır.
  {
    ad: '"N ekran"',
    metrik: "screens.count",
    kalip: /(?<![§\d-])\d{1,2}\s*(\*\*)?\s*ekranl?ı?\b/i,
  },
  {
    ad: '"N tablo"',
    metrik: "tables.count",
    kalip: /(?<![§\d-])\d{1,2}\s*(\*\*)?\s*tablo(nun|su|ya|yu)?\b/i,
  },
  {
    ad: "migration numarası listesi",
    metrik: "migrations.list",
    kalip: /migrations?\/?[^\n]{0,20}`?0001\s*,/i,
  },
  {
    ad: "örnek materyal dosya sayısı",
    metrik: "sampleData.files",
    kalip: /sample_data[^\n]{0,60}?(?<![§\d-])\d{1,3}\s*(\*\*)?\s*(teslim\s+)?dosya/i,
  },
];

/**
 * Bir sayıyı ANMAK ile İDDİA ETMEK aynı şey değildir.
 *
 * "Brifingdeki **\"19 tablo\"** sayısı yanlış" cümlesi 19'u iddia etmez, eleştirir;
 * `grep -rn "15 tablo"` ise arama kalıbıdır. İkisini de kapıya sokmak, belgeyi
 * kendi hata kaydını anlatamaz hâle getirir. Bu yüzden çift tırnak içindeki her
 * şey tarama öncesi boşlukla değiştirilir — uzunluk korunur ki sütun bilgisi kaymasın.
 *
 * Ters tırnak bilerek KORUNUR: `uv run pytest -q` gibi komutlar kod aralığında yazılır
 * ve dedektörlerin dayanağı tam olarak o komuttur.
 */
function anmalariMaskele(satir) {
  return satir.replace(/"[^"]*"/g, (m) => " ".repeat(m.length));
}

/** Kapının BAKMADIĞI sınıflar — her koşuda yazılır, sessiz kapsam olmaz. */
const KAPSAM_DISI = [
  "Eşik ifadeleri (`≥15 vaka` gibi) — hedef, ölçüm değil",
  "Dosya başına test sayıları (`test_exams.py (35 test)`) — kaynağı ayrı, sapması gözlenmedi",
  "Gecikme/token/chunk ölçümleri — koşum gerektirir, statik türetilemez",
  "RLS iddia sayıları (98 / 58) — psql koşumundan gelir, CI'nın RLS adımları kanıtlar",
];

// --- Kapı ------------------------------------------------------------------

function metrikleriOlc(gerekenler) {
  const olculen = {};
  const hatalar = [];
  for (const anahtar of gerekenler) {
    try {
      olculen[anahtar] = METRIKLER[anahtar].olc();
    } catch (hata) {
      hatalar.push({ anahtar, mesaj: hata.message });
    }
  }
  return { olculen, hatalar };
}

function main() {
  const argv = process.argv.slice(2);
  const yalnizMetrikler = argv.includes("--metrikler");
  const duzelt = argv.includes("--duzelt");

  if (yalnizMetrikler) {
    const { olculen, hatalar } = metrikleriOlc(Object.keys(METRIKLER));
    console.log("ÖLÇÜLEN GERÇEKLER\n");
    for (const [anahtar, tanim] of Object.entries(METRIKLER)) {
      const deger = anahtar in olculen ? olculen[anahtar] : "ÖLÇÜLEMEDİ";
      console.log(`  ${anahtar.padEnd(20)} ${String(deger).padEnd(24)} ${tanim.komut}`);
    }
    for (const h of hatalar) console.error(`\n  ✗ ${h.anahtar}: ${h.mesaj}`);
    process.exit(hatalar.length === 0 ? 0 : 1);
  }

  const iddialar = iddialariTopla();
  const canliIddialar = iddialar.filter((i) => !i.isaret.startsWith("tarihsel"));
  const gerekenler = [
    ...new Set(canliIddialar.map((i) => i.isaret.match(/^(\S+)\s*=/)?.[1]).filter(Boolean)),
  ].filter((a) => a in METRIKLER);

  const { olculen, hatalar: olcumHatalari } = metrikleriOlc(gerekenler);
  const sorunlar = [];

  for (const h of olcumHatalari) {
    sorunlar.push({ tur: "ölçüm", mesaj: `\`${h.anahtar}\` ölçülemedi — ${h.mesaj}` });
  }

  // 1) İşaretli iddialar ölçümle (ya da tarihsel değeriyle) uyuşuyor mu?
  const yazilacak = new Map();
  for (const iddia of iddialar) {
    const yer = `${iddia.dosya}:${iddia.satirNo}`;
    const govde = isaretsizMetin(iddia.satir);

    if (iddia.isaret.startsWith("tarihsel")) {
      const beklenen = iddia.isaret.match(/tarihsel\s+(\S+)/)?.[1];
      const tarih = iddia.isaret.match(/·\s*(\d{4}-\d{2}-\d{2})/)?.[1];
      if (!beklenen || !tarih) {
        sorunlar.push({
          tur: "işaret",
          mesaj: `${yer} — tarihsel işaret eksik. Biçim: \`docs-check: tarihsel <değer> · <YYYY-AA-GG>\``,
        });
        continue;
      }
      if (!degerKalibi(beklenen).test(govde)) {
        sorunlar.push({
          tur: "tarihsel",
          mesaj: `${yer} — tarihsel kayıt oynamış: işaret ${beklenen} diyor (${tarih}) ama satırda o değer yok. Tarihsel ölçüm değiştirilmez.`,
        });
      }
      continue;
    }

    const ayrilmis = iddia.isaret.match(/^(\S+)\s*=\s*(.+)$/);
    if (!ayrilmis) {
      sorunlar.push({
        tur: "işaret",
        mesaj: `${yer} — işaret değer taşımıyor. Biçim: \`docs-check: <metrik> = <değer>\``,
      });
      continue;
    }
    const [, anahtar, yazili] = ayrilmis;

    if (!(anahtar in METRIKLER)) {
      sorunlar.push({
        tur: "işaret",
        mesaj: `${yer} — bilinmeyen metrik \`${anahtar}\`. Tanımlılar: ${Object.keys(METRIKLER).join(", ")}`,
      });
      continue;
    }
    if (!(anahtar in olculen)) continue; // ölçüm hatası zaten raporlandı

    // İşaretteki değer satırda gerçekten geçiyor mu? Geçmiyorsa işaret bir şeyi
    // korumuyor demektir — sessizce doğru görünen en tehlikeli hâl.
    if (!degerKalibi(yazili).test(govde)) {
      sorunlar.push({
        tur: "işaret",
        mesaj: `${yer} — işaret \`${yazili}\` diyor ama satırın metninde bu değer geçmiyor; işaret hiçbir iddiayı korumuyor.`,
      });
      continue;
    }

    const gercek = String(olculen[anahtar]);
    if (yazili === gercek) continue;

    if (duzelt) {
      const liste = yazilacak.get(iddia.dosya) ?? [];
      liste.push({ satirNo: iddia.satirNo, eski: yazili, yeni: gercek });
      yazilacak.set(iddia.dosya, liste);
    } else {
      sorunlar.push({
        tur: "bayat",
        mesaj: `${yer} — belgede ${yazili}, ölçülen ${gercek} (\`${anahtar}\`, ${METRIKLER[anahtar].komut})`,
      });
    }
  }

  // 2) İşaretsiz canlı iddia var mı?
  const isaretliSatirlar = new Set(iddialar.map((i) => `${i.dosya}:${i.satirNo}`));
  for (const dosya of markdownDosyalari()) {
    if (arsivde(dosya)) continue;
    const satirlar = readFileSync(join(ROOT, dosya), "utf8").split("\n");
    satirlar.forEach((satir, i) => {
      const yer = `${dosya}:${i + 1}`;
      if (isaretliSatirlar.has(yer)) return;
      const taranan = anmalariMaskele(satir);
      for (const dedektor of DEDEKTORLER) {
        if (!dedektor.kalip.test(taranan)) continue;
        sorunlar.push({
          tur: "işaretsiz",
          mesaj:
            `${yer} — ${dedektor.ad} işaretsiz. Canlıysa ` +
            `\`<!-- docs-check: ${dedektor.metrik} = <değer> -->\`, tarihsel kayıtsa ` +
            `\`<!-- docs-check: tarihsel <değer> · <YYYY-AA-GG> -->\` ekle ` +
            `(kod bloğu içinde \`# docs-check: …\`).\n      ${satir.trim().slice(0, 140)}`,
        });
        break;
      }
    });
  }

  // 3) Ölü muafiyet var mı?
  for (const muaf of MUAFLAR) {
    try {
      readFileSync(join(ROOT, muaf.yol));
    } catch {
      sorunlar.push({
        tur: "muafiyet",
        mesaj: `${muaf.yol} artık yok ama muafiyet listesinde duruyor — MUAFLAR'dan çıkarın.`,
      });
    }
  }

  if (duzelt) {
    for (const [dosya, degisiklikler] of yazilacak) {
      const satirlar = readFileSync(join(ROOT, dosya), "utf8").split("\n");
      for (const d of degisiklikler) {
        satirlar[d.satirNo - 1] = satiriYenidenYaz(satirlar[d.satirNo - 1], d.eski, d.yeni);
        console.log(`  yazıldı ${dosya}:${d.satirNo}  ${d.eski} → ${d.yeni}`);
      }
      writeFileSync(join(ROOT, dosya), satirlar.join("\n"));
    }
    if (yazilacak.size === 0) console.log("  düzeltilecek canlı iddia yok.");
  }

  // --- Rapor ---------------------------------------------------------------

  console.log("\nÖLÇÜLEN");
  for (const anahtar of gerekenler) {
    const deger = anahtar in olculen ? olculen[anahtar] : "ÖLÇÜLEMEDİ";
    console.log(`  ${anahtar.padEnd(20)} ${String(deger).padEnd(24)} ${METRIKLER[anahtar].komut}`);
  }
  console.log(
    `\nİDDİA  ${canliIddialar.length} canlı · ${iddialar.length - canliIddialar.length} tarihsel · ` +
      `${markdownDosyalari().length} belge tarandı`,
  );

  for (const muaf of MUAFLAR) {
    console.log(`\nMUAF   ${muaf.yol} (${muaf.sahibi})\n       ${muaf.gerekce}`);
  }

  for (const arsiv of TARIHSEL_ARSIV) {
    const sayi = markdownDosyalari().filter((d) => arsivde(d)).length;
    console.log(`\nARŞİV  ${arsiv.yol}/** — ${sayi} belge, işaretsiz taramadan muaf`);
    console.log(`       ${arsiv.gerekce}`);
  }

  console.log("\nKAPSAM DIŞI");
  for (const madde of KAPSAM_DISI) console.log(`  · ${madde}`);

  if (sorunlar.length === 0) {
    console.log("\n✓ Belgelerdeki canlı sayıların tamamı ölçümle uyuşuyor.");
    process.exit(0);
  }

  console.log(`\n✗ ${sorunlar.length} sorun:\n`);
  for (const s of sorunlar) console.log(`  [${s.tur}] ${s.mesaj}`);
  console.log(
    "\nCanlı sayıyı elle düzeltmeyin — `node scripts/docs_check.mjs --duzelt` ölçümden yazar.",
  );
  process.exit(1);
}

main();
