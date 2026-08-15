/**
 * Uçtan uca akış testleri — Anayasa VIII'in kalıcı hâli.
 *
 * "Davranış gerçek ortamda gözlenmeden bitmedi" ilkesi, elle bir kez bakmakla
 * karşılanmış sayılmaz: elle bakış bir sonraki değişiklikte kaybolur. Bu paket,
 * elle koşturulan etkileşim denetimlerini kalıcı hâle getiriyor.
 *
 * Neden özellikle bu vakalar: hepsi gerçekten bulunmuş kusurları ya da ürünün
 * tezini koruyor. Ölü butonlar (etkin görünüp iş yapmayan), sessizce yutulan
 * hata, tam sayfa yenileme, bozuk oturumda çökme — dördü de burada nöbette.
 * Bunların yanına 9 Ağustos'ta ürünün SÖZÜ eklendi: kaynaklı cevap sayfa
 * numarası taşır, abstention hata gibi görünmez, Sokratik merdiven ısrarla
 * atlanamaz.
 *
 * Test kendi verisini kurar; başka bir testin bıraktığı duruma güvenmez.
 * Ders kodu koşu kimliği taşır ve global teardown yalnız o koşunun derslerini
 * doğrudan izole test veritabanından temizler. Ürün API'sine silme yetkisi eklenmez.
 *
 * Koşturma (API :8010, web sunucusunu paket kendi derleyip başlatır):
 *   E2E_API_URL=http://localhost:8000 node_modules/.bin/playwright test
 *
 * `bunx playwright` KULLANMAYIN: ayrı bir kopya indirir ve "two different
 * versions" hatası verir.
 */

import { expect, test, type Page } from "@playwright/test";

import { createE2eCourseIdentity } from "./fixtures";

/*
 * Varsayılan `playwright.config.ts` ile AYNI olmalı ve öyle kalmalı: config
 * tarayıcıya gömülecek `NEXT_PUBLIC_API_URL`'i aynı değişkenden alıyor. İkisi
 * ayrışırsa test verisini bir API'ye kurar, tarayıcı başka bir API'ye sorar ve
 * paket koştuğu ortama göre bazen geçer bazen kalır.
 */
const API = process.env.E2E_API_URL ?? "http://localhost:8000";

/** Seed'deki sabit demo kimlikleri (supabase/seed_demo.sql). */
const AYSE = {
  id: "11111111-1111-1111-1111-111111111111",
  email: "ayse@dogus.edu.tr",
  fullName: "Ayşe Hoca",
  role: "instructor" as const,
};
const BURAK = {
  id: "22222222-2222-2222-2222-222222222222",
  email: "burak@dogus.edu.tr",
  fullName: "Burak Yılmaz",
  role: "student" as const,
};

type DemoUser = typeof AYSE | typeof BURAK;

/** Tarayıcıya oturum enjekte eder — giriş ekranını her testte tıklamak yerine. */
async function signIn(page: Page, user: DemoUser) {
  await page.addInitScript(
    ([token, payload]) => {
      localStorage.setItem("dou-synapse-token", token as string);
      localStorage.setItem("dou-synapse-user", payload as string);
    },
    [`dev:${user.id}`, JSON.stringify(user)],
  );
}

function authHeader(user: DemoUser) {
  return `Bearer dev:${user.id}`;
}

async function apiPost(path: string, body: unknown, user: DemoUser) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: authHeader(user),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} → ${res.status} ${await res.text()}`);
  return res.json();
}

async function apiGet<T>(path: string, user: DemoUser): Promise<T> {
  const res = await fetch(`${API}${path}`, { headers: { Authorization: authHeader(user) } });
  if (!res.ok) throw new Error(`${path} → ${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

/**
 * Her test kendi dersini açar: paralel koşumda birbirlerinin verisini bozmasınlar.
 *
 * Kod benzersizleştirilir çünkü `courses.code` derse özgüdür ve ikinci koşumda
 * 409 döner. Testin yeniden koşturulabilir olması pazarlıksız: bir kez çalışıp
 * sonra çakışan test, hiç olmayan testten kötüdür - yeşil bekleyip kırmızı bulan
 * ekip önce teste güvenmeyi bırakır.
 */
async function createCourse(suffix: string) {
  const identity = createE2eCourseIdentity(suffix);
  return apiPost(
    "/courses",
    identity,
    AYSE,
  );
}

/* -------------------------------------------------------------------------
 * Materyal fikstürü
 * ---------------------------------------------------------------------- */

/**
 * Testin kendi PDF'i. Neden elle kuruluyor:
 *
 * Ürünün tek iddiası "cevabın kaynağı şu sayfa" ve sayfa numarası ancak GERÇEK
 * bir PDF'ten çıkar — markdown yüklenirse konum bölüm adı olur ve "Sayfa N"
 * hiç oluşmaz, yani vaka kendi kendini boşa çıkarır. Repoya ikili bir örnek
 * dosya koymak yerine PDF burada üretiliyor: içeriği testin okunduğu yerde
 * görünüyor ve hangi cümlenin hangi sayfada olduğu gözle doğrulanabiliyor.
 *
 * Metin bilerek ASCII: gömülü Helvetica WinAnsi kodlamasındadır ve "ş/ğ/ı"
 * glifleri yoktur. Kısıt yalnız DOSYA İÇERİĞİNE aittir; ekrana yazılan soru
 * Türkçedir ve öyle olması gerekir (Anayasa V).
 */
function kucukPdf(sayfalar: string[][]): Buffer {
  const kacir = (s: string) => s.replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");

  const sayfaKimlik = sayfalar.map((_, i) => 4 + 2 * i);
  const icerikKimlik = sayfalar.map((_, i) => 5 + 2 * i);
  const nesneler = new Map<number, string>();

  nesneler.set(1, "<< /Type /Catalog /Pages 2 0 R >>");
  nesneler.set(
    2,
    `<< /Type /Pages /Kids [${sayfaKimlik.map((id) => `${id} 0 R`).join(" ")}] ` +
      `/Count ${sayfalar.length} >>`,
  );
  nesneler.set(3, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>");

  sayfalar.forEach((satirlar, i) => {
    nesneler.set(
      sayfaKimlik[i],
      "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] " +
        "/Resources << /Font << /F1 3 0 R >> >> " +
        `/Contents ${icerikKimlik[i]} 0 R >>`,
    );
    const akis =
      "BT /F1 12 Tf 14 TL 60 760 Td\n" +
      satirlar.map((satir) => `(${kacir(satir)}) Tj T*\n`).join("") +
      "ET";
    nesneler.set(
      icerikKimlik[i],
      `<< /Length ${Buffer.byteLength(akis, "latin1")} >>\nstream\n${akis}\nendstream`,
    );
  });

  // xref tablosu bayt konumu ister; gövde büyüdükçe konum kayar, o yüzden
  // nesneler yazılırken tek tek ölçülüyor.
  let govde = "%PDF-1.4\n";
  const konumlar = new Map<number, number>();
  const numaralar = [...nesneler.keys()].sort((a, b) => a - b);
  for (const numara of numaralar) {
    konumlar.set(numara, Buffer.byteLength(govde, "latin1"));
    govde += `${numara} 0 obj\n${nesneler.get(numara)}\nendobj\n`;
  }
  const xrefKonumu = Buffer.byteLength(govde, "latin1");
  const toplam = numaralar[numaralar.length - 1] + 1;
  govde += `xref\n0 ${toplam}\n0000000000 65535 f \n`;
  for (let numara = 1; numara < toplam; numara++) {
    govde += `${String(konumlar.get(numara) ?? 0).padStart(10, "0")} 00000 n \n`;
  }
  govde += `trailer\n<< /Size ${toplam} /Root 1 0 R >>\nstartxref\n${xrefKonumu}\n%%EOF\n`;
  return Buffer.from(govde, "latin1");
}

/** İki sayfalık ders materyali; "Sayfa 1" ve "Sayfa 2" iddiası buradan doğar. */
const KAYNAK_PDF_ADI = "e2e_kaynak.pdf";
const KAYNAK_PDF = kucukPdf([
  ["Deadlock nedir?", "Deadlock, iki veya daha fazla surecin birbirini", "beklemesi durumudur."],
  [
    "Coffman kosullari",
    "Deadlock icin dort Coffman kosulunun ayni anda",
    "saglanmasi gerekir: karsilikli dislama, tut ve bekle,",
    "kesintisizlik ve dairesel bekleme.",
  ],
]);

interface BelgeOzeti {
  id: string;
  file_name: string;
  status: string;
}

async function apiUpload(courseId: string, fileName: string, bytes: Buffer, user: DemoUser) {
  const form = new FormData();
  form.append("file", new Blob([new Uint8Array(bytes)], { type: "application/pdf" }), fileName);
  const res = await fetch(`${API}/courses/${courseId}/documents`, {
    method: "POST",
    headers: { Authorization: authHeader(user) },
    body: form,
  });
  if (!res.ok) throw new Error(`yükleme → ${res.status} ${await res.text()}`);
  return res.json();
}

/**
 * Belge işlenene kadar bekler.
 *
 * Arayüz üzerinden değil uçtan sorulur: sohbet vakaları materyal ekranını hiç
 * açmıyor ve "ekranda göründü" ile "gömülmesi bitti" aynı şey değil — parçası
 * olmayan belge retrieval'a hiç girmez ve cevap kaynaksız kalır.
 */
async function belgeHazirOlanaKadarBekle(courseId: string, user: DemoUser) {
  for (let deneme = 0; deneme < 40; deneme++) {
    // 10 Ağu: liste uçları sayfalama zarfına geçti; gövde artık {items, next_cursor}.
    const belgeler = (
      await apiGet<{ items: BelgeOzeti[] }>(`/courses/${courseId}/documents`, user)
    ).items;
    if (belgeler.length > 0 && belgeler.every((b) => b.status === "completed")) return;
    const bozuk = belgeler.find((b) => b.status === "failed");
    if (bozuk) throw new Error(`belge işlenemedi: ${bozuk.file_name}`);
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("belge 20 sn içinde işlenmedi");
}

/** Materyali hazır, öğrencisi eklenmiş bir ders. Sohbet vakalarının ortak zemini. */
async function materyalliDers(suffix: string) {
  const course = await createCourse(suffix);
  await apiPost(`/courses/${course.id}/members`, { email: BURAK.email, role: "student" }, AYSE);
  await apiUpload(course.id, KAYNAK_PDF_ADI, KAYNAK_PDF, AYSE);
  await belgeHazirOlanaKadarBekle(course.id, AYSE);
  return course;
}

/* -------------------------------------------------------------------------
 * Soru havuzu fikstürü
 * ---------------------------------------------------------------------- */

interface HavuzFiksturu {
  course: { id: string; title: string };
  /**
   * Üretilen sorular — hepsi `draft`. Onay BİLEREK verilmiyor: eğitmen onayını
   * sınayan vaka, önceden onaylanmış bir soruda "Onayla" düğmesini pasif bulur
   * ve hiçbir şeyi sınayamaz. Sınav vakaları onayı `hepsiniOnayla` ile alır.
   * Boşsa üretim hiçbir şey döndürmedi (bkz. `HAVUZ_YOK`).
   */
  taslaklar: { id: string }[];
  /** Üretimin kendi gerekçeleri — atlama sebebini okunur kılar. */
  gerekce: string[];
}

/**
 * Soru havuzunun kurulamadığı durumun gerekçesi.
 *
 * Soru üretiminin TEK yolu `POST /questions/generate` ve o uç LLM'e bağlı.
 * Anahtar yokken sunucu deterministik sahte sağlayıcıya düşüyor
 * (`app/modules/generation/fake.py`), o sağlayıcının ise soru üretimi dalı yok:
 * her turda sohbet biçiminde bir gövde dönüyor ve üretim "yanıtta 'questions'
 * dizisi yok" diye eliyor. Yani bu ortamda havuz API'den doldurulamıyor.
 *
 * Bu yüzden havuza dayanan vakalar ZAYIFLATILMADI, koşullu atlandı: fikstür
 * gerçekten kurulmayı deniyor ve üretim bir gün soru döndürdüğünde vakalar
 * kendiliğinden koşmaya başlıyor. Bir sabitle kapatılsalardı, düzelme günü
 * kimse fark etmezdi.
 */
const HAVUZ_YOK =
  "Soru havuzu kurulamadı: bu ortamda soru üretimi sahte sağlayıcıya düşüyor ve " +
  "hiç soru döndürmüyor (bkz. AÇIK KUSUR). Vaka, üretim çalışır çalışmaz koşacak.";

async function soruHavuzuKur(suffix: string): Promise<HavuzFiksturu> {
  const course = await materyalliDers(suffix);
  const topic = await apiPost(`/courses/${course.id}/topics`, { name: "Deadlock" }, AYSE);
  const rapor = await apiPost(
    `/courses/${course.id}/questions/generate`,
    { topic_id: topic.id, question_type: "mcq", count: 3 },
    AYSE,
  );

  return {
    course,
    taslaklar: rapor.questions ?? [],
    gerekce: rapor.rejection_reasons ?? [],
  };
}

/** Sınav ancak onaylanmış sorularla başlar; onayı veren tek yer eğitmen ucudur. */
async function hepsiniOnayla(havuz: HavuzFiksturu) {
  for (const soru of havuz.taslaklar) {
    await apiPost(`/courses/${havuz.course.id}/questions/${soru.id}/approve`, {}, AYSE);
  }
}

/* -------------------------------------------------------------------------
 * Sohbet ekranının ortak seçicileri
 * ---------------------------------------------------------------------- */

/**
 * Kaynak kartı — ürünün imza bileşeni, ama ARIA rolü yok.
 *
 * Kartı ayırt eden tek yapısal işaret alıntının `<blockquote>`'u; dosya adı ve
 * konum rozeti onun kardeşleri. Kartın kendisine `blockquote`'un kabından
 * ulaşılıyor ki "dosya adı ve sayfa numarası AYNI kartta" iddiası gerçekten
 * sınansın — ikisini sayfada ayrı ayrı aramak, iki farklı karttan gelseler de
 * yeşil yanardı.
 */
function kaynakKarti(page: Page) {
  return page.locator("blockquote").first().locator("xpath=..");
}

/**
 * Merdiven kademeleri. Sohbet ekranındaki tek sıralı liste merdivendir; yan
 * paneldeki materyal ve oturum listeleri `<ul>`.
 */
function merdivenKademeleri(page: Page) {
  return page.locator("ol > li");
}

/**
 * Ekrandaki GERÇEK hata duyuruları.
 *
 * `[role="alert"]` doğrudan sayılamaz: Next kendi rota duyurucusunu
 * (`<next-route-announcer>`) `<body>`ye ekliyor ve o da `role="alert"` taşıyor.
 * Duyurucu boştur ve sayfa geçişini bildirir, bir arıza bildirmez — sayarsak
 * her ekran "hatalı" görünür ve vaka hiçbir şeyi koruyamaz. Bu yüzden sayım
 * uygulamanın kendi içeriğiyle, yani `<main>` ile sınırlı.
 */
function hataDuyurulari(page: Page) {
  return page.getByRole("main").locator('[role="alert"]');
}

/** Sohbete bir tur gönderir ve girdinin boşalmasını (isteğin gittiğini) bekler. */
async function sohbetGonder(page: Page, etiket: "Sorun" | "Denemen", metin: string) {
  const girdi = page.getByLabel(etiket);
  await girdi.fill(metin);
  await page.getByRole("button", { name: "Gönder" }).click();
  await expect(girdi).toHaveValue("");
}

/* -------------------------------------------------------------------------
 * Vakalar
 * ---------------------------------------------------------------------- */

test.describe("giriş", () => {
  test("demo kartı oturum açar ve ürün paneline götürür", async ({ page }) => {
    await page.goto("/");
    await page.getByText("Ayşe Hoca").click();
    await expect(page).toHaveURL(/\/dashboard$/);
  });

  test("bozuk oturum verisi uygulamayı ÇÖKERTMEZ", async ({ page }) => {
    // Gerçek kusur: JSON.parse doğrudan çağrıldığında bozuk bir localStorage
    // kaydı tüm sayfayı düşürüyordu ve yenilemek kurtarmıyordu — kayıt hâlâ
    // bozuk olduğu için kullanıcı kalıcı kilitli kalıyordu.
    const pageErrors: string[] = [];
    page.on("pageerror", (e) => pageErrors.push(e.message));

    await page.addInitScript(() => {
      localStorage.setItem("dou-synapse-token", "dev:x");
      localStorage.setItem("dou-synapse-user", "{bozuk json");
    });
    await page.goto("/courses");

    expect(pageErrors).toHaveLength(0);
    // Giriş ekranına düşmeli, beyaz ekrana değil.
    await expect(page.getByText("Ayşe Hoca")).toBeVisible();
  });
});

test.describe("materyal yönetimi", () => {
  test("yükleme, önizleme aç/kapa ve silme akışı", async ({ page }) => {
    const course = await createCourse("MAT");
    await signIn(page, AYSE);
    await page.goto(`/courses/${course.id}`);

    // Yükleme. Dosya PDF: parça önizlemesinin sayfa numarası göstermesi ürünün
    // vaadinin materyal ekranındaki hâli ve markdown ile hiç oluşmaz.
    await page.setInputFiles('input[type="file"]', {
      name: KAYNAK_PDF_ADI,
      mimeType: "application/pdf",
      buffer: KAYNAK_PDF,
    });
    await expect(page.getByRole("listitem").getByText(KAYNAK_PDF_ADI)).toBeVisible({ timeout: 15_000 });

    const row = page.locator("li", { hasText: KAYNAK_PDF_ADI });

    // Önizleme aç/kapa. Düğme yalnız işlenme bitince çıkar; liste 2 sn'de bir
    // kendiliğinden tazeleniyor, elle yenileme gerekmiyor.
    const onizle = row.getByRole("button", { name: "İçerik önizle" });
    await expect(onizle).toBeVisible({ timeout: 20_000 });
    await onizle.click();
    await expect(page.getByText("Sayfa 1")).toBeVisible();
    await row.getByRole("button", { name: "Gizle" }).click();
    await expect(page.getByText("Sayfa 1")).toBeHidden();

    // Silme: önce onay adımı, sonra vazgeçme.
    // Buton `aria-label` taşıyor ("<dosya> dosyasını sil") ve aria-label
    // erişilebilir adı geçersiz kılar; locator ona göre yazılır.
    const silButonu = row.getByRole("button", { name: /dosyasını sil$/ });
    await silButonu.click();
    await expect(page.getByText("Evet, sil")).toBeVisible();
    await page.getByRole("button", { name: "Vazgeç" }).click();
    await expect(page.getByText("Evet, sil")).toBeHidden();
    await expect(page.getByRole("listitem").getByText(KAYNAK_PDF_ADI)).toBeVisible();

    // Gerçekten silme — ve TAM SAYFA YENİLEME OLMAMALI
    await silButonu.click();
    await row.getByRole("button", { name: "Evet, sil" }).click();
    await expect(page.getByRole("listitem").getByText(KAYNAK_PDF_ADI)).toBeHidden({ timeout: 15_000 });

    const navType = await page.evaluate(
      () => performance.getEntriesByType("navigation")[0]?.entryType &&
        (performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming).type,
    );
    expect(navType).not.toBe("reload");
  });
});

test.describe("sohbet — ürünün tezi", () => {
  test("kaynaklı cevap dosya adını ve sayfa numarasını gösterir", async ({ page }) => {
    // Sistemin tek iddiası bu: cevap uydurulmaz, gerçek bir sayfaya dayanır.
    // Dosya adı ve konum chunk metadata'sından gelir, model metninden değil
    // (Anayasa I) — bu yüzden ikisinin AYNI kartta durması sınanıyor.
    const course = await materyalliDers("KAYNAK");
    await signIn(page, BURAK);
    await page.goto(`/courses/${course.id}/chat`);

    await sohbetGonder(page, "Sorun", "Coffman koşulları nelerdir?");

    const kart = kaynakKarti(page);
    await expect(kart).toBeVisible({ timeout: 30_000 });
    await expect(kart).toContainText(KAYNAK_PDF_ADI);
    await expect(kart).toContainText(/Sayfa \d+/);
  });

  test("dayanaksız soru nazik ret alır ve bu ret HATA GİBİ GÖRÜNMEZ", async ({ page }) => {
    /*
     * DESIGN.md'nin en kritik kararı ve tek koruması bu vaka.
     *
     * "Yüklenen materyallerde bunun cevabı yok" bir BAŞARIDIR: sistem uydurmak
     * yerine reddediyor. Kırmızı kutu, ünlem ya da `role="alert"` görünürse
     * öğrenci sistemin bozuk olduğunu sanar ve genel bir yapay zekâya kaçar —
     * ürünün varlık sebebi çöker.
     *
     * Ders materyalli: dayanaksızlığın anlamlı olması için ortada gerçekten
     * materyal olmalı, yoksa vaka "boş derste cevap yok"u sınardı.
     *
     * İki abstention durumu (`insufficient_context` / `out_of_scope`) aynı
     * bileşenden geçer; hangisinin döndüğü sağlayıcıya göre değişebildiği için
     * başlık ikisini birden karşılıyor. Sınanan şey durum kodu değil, TONU.
     */
    const course = await materyalliDers("RET");
    await signIn(page, BURAK);
    await page.goto(`/courses/${course.id}/chat`);

    await sohbetGonder(page, "Sorun", "Ronaldo hangi takımda oynuyor?");

    await expect(
      page.getByText(/Materyalde dayanak bulunamadı|Dersin kapsamı dışında/),
    ).toBeVisible({ timeout: 30_000 });

    // Hata dili YOK: `role="alert"` ekran okuyucuya "arıza" der, `.text-danger`
    // göze kırmızı gösterir. İkisi de bu ekranda bulunmamalı.
    await expect(hataDuyurulari(page)).toHaveCount(0);
    await expect(page.locator(".text-danger")).toHaveCount(0);
    // Atıf da yok: dayanaksız cevabın yanına kaynak kartı iliştirilmez.
    await expect(page.locator("blockquote")).toHaveCount(0);
  });

  test("öğrenci sorunlu yanıtı izinle öğretmen incelemesine açar", async ({ page }) => {
    const course = await createCourse("KALITE");
    await apiPost(`/courses/${course.id}/members`, { email: BURAK.email, role: "student" }, AYSE);
    await signIn(page, BURAK);
    await page.goto(`/courses/${course.id}/chat`);

    await sohbetGonder(page, "Sorun", "Deadlock koşullarını açıklar mısın?");
    await expect(page.getByText("Materyalde dayanak bulunamadı")).toBeVisible({
      timeout: 30_000,
    });
    await page.getByRole("button", { name: "Sorun var" }).click();
    await page.getByLabel("Sorun türü").selectOption("citation_problem");
    await page
      .getByLabel("Açıklama (isteğe bağlı)")
      .fill("Kaynak görünmedi; öğretmenim bu örneği inceleyebilir.");
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: "Geri bildirimi kaydet" }).click();
    await expect(page.getByText(/öğretmen incelemesine açık/)).toBeVisible();

    // Aynı tarayıcıda gerçek çıkış/giriş: rol önbelleği öğrenci kimliğini taşımamalı.
    await page.getByRole("button", { name: "Çıkış" }).click();
    const teacherButton = page.getByRole("button", { name: /Ayşe Hoca/ });
    await expect(teacherButton).toBeVisible();
    await teacherButton.click();
    await expect(page).toHaveURL(/\/dashboard$/);

    // Keep the role switch inside Next.js client navigation. The test helper's
    // init script intentionally restores Burak on a full page load.
    await page.getByRole("link", { name: "Tüm dersler" }).click();
    await expect(page).toHaveURL(/\/courses$/);
    const courseLink = page.getByRole("link", { name: new RegExp(course.code) });
    await expect(courseLink).toBeVisible();
    await courseLink.click();
    await expect(page).toHaveURL(new RegExp(`/courses/${course.id}$`));
    await page.getByRole("link", { name: "AI kalite", exact: true }).click();
    await expect(page).toHaveURL(/\/quality$/);

    await expect(page.getByRole("heading", { name: "AI kalite" })).toBeVisible();
    await expect(page.getByText("Burak Yılmaz")).toBeVisible();
    await expect(page.getByText("Deadlock koşullarını açıklar mısın?")).toBeVisible();
    await expect(
      page.getByText("Öğrenci notu: Kaynak görünmedi; öğretmenim bu örneği inceleyebilir."),
    ).toBeVisible();
    await expect(
      page.getByText("Puanlanan yanıt", { exact: true }).locator("xpath=following-sibling::dd[1]"),
    ).toHaveText("1");
  });

  test("Sokratik mod cevap vermez, kaynaklı ipucu verir", async ({ page }) => {
    const course = await materyalliDers("SOKRAT");
    await signIn(page, BURAK);
    await page.goto(`/courses/${course.id}/chat`);

    await page.getByRole("button", { name: "Sokratik" }).click();
    await sohbetGonder(page, "Sorun", "Coffman koşulları nelerdir?");

    const kademeler = merdivenKademeleri(page);
    await expect(kademeler).toHaveCount(1, { timeout: 30_000 });

    // Merdiven göstergesi görünür ve kademe ADI metin olarak yazar: gösterge
    // bilgiyi yalnız renkle (noktalarla) taşımaz.
    await expect(page.getByText("Sokratik mod")).toBeVisible();
    await expect(kademeler.first()).toContainText("Tanı");
    // Kaynaksız ipucu istemciye hiç ulaşmaz (FR-013/FR-016): konum her kademede.
    await expect(kademeler.first()).toContainText(`${KAYNAK_PDF_ADI} · Sayfa`);

    // Cevap VERİLMEDİ: kaynaklı cevap yolu kaynak kartı çizer, ipucu yolu
    // çizmez. Kart yoksa bu tur merdivenden geçmiş demektir.
    await expect(page.locator("blockquote")).toHaveCount(0);
    await expect(
      page.getByText(/Cevabı doğrudan vermek yerine adım adım yaklaştırır/),
    ).toBeVisible();
  });

  test('"sadece söyle" ısrarı merdiveni İLERLETMEZ', async ({ page }) => {
    // Kademe atlanmaz (DESIGN.md): ısrar eden öğrenci nazik bir uyarı ve AYNI
    // kademenin ipucunu alır. İlerleseydi Sokratik mod, bir kaç "söyle" ile
    // doğrudan cevaba dönüşürdü.
    const course = await materyalliDers("ISRAR");
    await signIn(page, BURAK);
    await page.goto(`/courses/${course.id}/chat`);

    await page.getByRole("button", { name: "Sokratik" }).click();
    await sohbetGonder(page, "Sorun", "Coffman koşulları nelerdir?");

    const kademeler = merdivenKademeleri(page);
    await expect(kademeler).toHaveCount(1, { timeout: 30_000 });

    // Gerçek deneme merdiveni bir kademe ilerletir: Tanı → Yönlendirme.
    await sohbetGonder(page, "Denemen", "Sanırım dört koşul var ama hepsini hatırlamıyorum");
    await expect(kademeler).toHaveCount(2, { timeout: 30_000 });
    await expect(kademeler.nth(1)).toContainText("Yönlendirme");

    // Israr: kademe AYNI kalır.
    await sohbetGonder(page, "Denemen", "sadece söyle");
    await expect(kademeler).toHaveCount(3, { timeout: 30_000 });
    await expect(kademeler.nth(2)).toContainText("Yönlendirme");
    await expect(kademeler.nth(2)).toContainText("Denemen: sadece söyle");
    await expect(page.getByText(/Cevabı doğrudan veremem/)).toBeVisible();
    // Bir sonraki kademe HİÇ açılmadı.
    await expect(page.getByText("Kavram ipucu")).toHaveCount(0);
  });

  test("sohbet geçmişi sayfa yenilemede kaybolmaz", async ({ page }) => {
    // Açık oturumun kimliği tarayıcıda saklanıyor; saklanmasaydı yenileyen
    // öğrenci boş bir ekrana düşer ve konuşmasını geri getiremezdi.
    const course = await materyalliDers("GECMIS");
    const soru = "Deadlock için hangi koşullar gerekir?";
    await signIn(page, BURAK);
    await page.goto(`/courses/${course.id}/chat`);

    await sohbetGonder(page, "Sorun", soru);
    await expect(kaynakKarti(page)).toBeVisible({ timeout: 30_000 });

    await page.reload();

    // Oturum geri açıldı: soru balonu, cevabın kaynak kartı ve listedeki
    // etkin oturum işareti yerinde.
    await expect(kaynakKarti(page)).toContainText(KAYNAK_PDF_ADI, { timeout: 30_000 });
    await expect(page.getByText(soru).first()).toBeVisible();
    await expect(page.locator('[aria-current="true"]')).toBeVisible();
  });
});

test.describe("gezinme", () => {
  test("her rotanın kendi sekme başlığı var", async ({ page }) => {
    /*
     * Ekranların hepsi `"use client"` ve istemci bileşeninde `metadata` export'u
     * çalışmaz; başlıklar bu yüzden her segmentin ince sunucu layout'unda
     * yaşıyor. Bağ kolayca kopar (yeni rota, unutulan layout) ve kopuş sessizdir:
     * ekran çalışmaya devam eder, yalnız sekme "DOU-Synapse" der ve Next'in rota
     * duyurucusu ekran okuyucuya hiçbir geçişi bildirmez.
     *
     * Gezinme tıklamayla yapılıyor, `goto` ile değil: başlığın istemci tarafı
     * geçişte de güncellendiği ancak böyle görülür.
     */
    const course = await createCourse("BASLIK");

    await page.goto("/forgot-password");
    await expect(page).toHaveTitle("Parola yenileme · DOU-Synapse");

    await page.goto("/reset-password");
    await expect(page).toHaveTitle("Yeni parola · DOU-Synapse");

    await signIn(page, AYSE);

    await page.goto("/");
    await expect(page).toHaveTitle("DOU-Synapse");

    await page.goto("/courses");
    await expect(page).toHaveTitle("Derslerim · DOU-Synapse");

    await page.getByRole("link", { name: new RegExp(course.code) }).click();
    await expect(page).toHaveTitle("Ders materyalleri · DOU-Synapse");

    // Ders içi altı sekmenin hepsi — eğitmene özel ikisi dahil.
    for (const sekme of [
      "Asistan",
      "Sınav provası",
      "Soru havuzu",
      "Sınav blueprint'i",
      "İlerleme",
      "AI kalite",
      "Katılımcılar",
      "Materyaller",
    ]) {
      await page.getByRole("link", { name: sekme, exact: true }).click();
      const beklenen = sekme === "Materyaller" ? "Ders materyalleri" : sekme;
      await expect(page).toHaveTitle(`${beklenen} · DOU-Synapse`);
    }
  });
});

test.describe("soru havuzu — eğitmen onayı", () => {
  test("satır seçimi, onay ve red butonları GERÇEKTEN iş yapar", async ({ page }) => {
    // Kusur: butonlar seçim yapılınca etkinleşiyor ama tıklanınca hiçbir şey
    // olmuyordu. Etkin görünüp iş yapmayan buton kusurdur (Anayasa XI).
    const havuz = await soruHavuzuKur("SORU");
    test.skip(havuz.taslaklar.length < 2, `${HAVUZ_YOK} Üretim gerekçeleri: ${havuz.gerekce}`);

    await signIn(page, AYSE);
    await page.goto(`/courses/${havuz.course.id}/questions`);

    // Liste satırı seçimi gerçekten taşınıyor mu: `aria-current` iki satır
    // arasında yer değiştirmeli, yoksa panel hep ilk soruyu gösterir.
    const satirlar = page
      .getByRole("list", { name: "Soru havuzu" })
      .getByRole("button");
    await satirlar.nth(1).click();
    await expect(satirlar.nth(1)).toHaveAttribute("aria-current", "true");
    await satirlar.nth(0).click();
    await expect(satirlar.nth(0)).toHaveAttribute("aria-current", "true");
    await expect(satirlar.nth(1)).not.toHaveAttribute("aria-current", "true");

    // Onay gerçekten iş yapar: karar cümlesi sunucudan dönen duruma dayanır ve
    // düğmenin kendi etiketi de yeni duruma döner.
    await page.getByRole("button", { name: /Onayla ve öğrenciye aç/ }).click();
    await expect(page.getByText(/Soru onaylandı/)).toBeVisible();
    /*
     * `exact: true` şart: havuzda onaylı soru olunca üstteki süzgeç çipi de
     * "Onaylandı (1)" oluyor ve satırın erişilebilir adı da bu kelimeyi
     * taşıyor. Gevşek eşleşme üç öğeye birden uyup strict mode ihlali veriyordu
     * — testin ölçmek istediği tek şey EYLEM düğmesinin yeni etiketi.
     */
    await expect(page.getByRole("button", { name: "Onaylandı", exact: true })).toBeVisible();

    // Red de öyle.
    await satirlar.nth(1).click();
    await page.getByRole("button", { name: /^Reddet$/ }).click();
    await expect(page.getByText(/Soru reddedildi/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Reddedildi", exact: true })).toBeVisible();
  });

  test("üretim muhasebesi GİZLENMEZ ama hata gibi de gösterilmez", async ({ page }) => {
    /*
     * İstenen / dönen / kabul edilen sayıları ekranda durur (Anayasa III) ve
     * `returned: 0` bir çökme değildir: sağlayıcı şemaya ve kaynağa uyan soru
     * döndürmediğinde sistem uydurmak yerine hiçbir şey yazıyor (Anayasa IV).
     * Abstention kararının soru havuzundaki eşi — ton nötr kalmalı.
     *
     * Vaka sayıya bağlanmadı, RAPORUN VARLIĞINA ve TONUNA bağlandı: bugün sıfır
     * dönüyor, üretim çalışmaya başlayınca beş dönecek ve iddia ikisinde de aynı.
     */
    const course = await materyalliDers("URETIM");
    await apiPost(`/courses/${course.id}/topics`, { name: "Deadlock" }, AYSE);
    await signIn(page, AYSE);
    await page.goto(`/courses/${course.id}/questions`);

    await page.getByRole("button", { name: "Soru üret" }).click();
    await expect(page.getByText("Üretim raporu")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(/soru istendi/)).toBeVisible();

    await expect(hataDuyurulari(page)).toHaveCount(0);
    await expect(page.locator(".text-danger")).toHaveCount(0);
  });

  test("öğrenci çalışmayan eğitmen formunu GÖRMEZ", async ({ page }) => {
    // Sekme öğrenciye hiç çizilmiyor ama adres çubuğuna yazılarak girilebiliyor.
    // Girildiğinde eğitmen formunun gösterilmesi, öğrenciye 403 alacağı bir
    // düğme sunmak olurdu (Anayasa XI); ekran sakin bir yönlendirmeye düşer.
    const course = await createCourse("HAVUZROL");
    await apiPost(`/courses/${course.id}/members`, { email: BURAK.email, role: "student" }, AYSE);

    await signIn(page, BURAK);
    await page.goto(`/courses/${course.id}/questions`);

    await expect(
      page.getByText(/Soru havuzu yalnızca dersin eğitmenine gösterilir/),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Soru üret" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Konu ekle" })).toHaveCount(0);
    await expect(page.getByLabel("Yeni konu")).toHaveCount(0);
    await expect(page.getByLabel("Konu süzgeci")).toHaveCount(0);
    // Sekme de yok: devre dışı görünen sekme bırakılmaz.
    await expect(page.getByRole("link", { name: "Soru havuzu", exact: true })).toHaveCount(0);
    // Çıkışı olan boş durum: nereye gideceği söyleniyor.
    await expect(page.getByRole("link", { name: "Sınav provasına git" })).toBeVisible();
  });
});

test.describe("sınav provası", () => {
  test("ileri-geri gezinme çalışır ve cevap korunur", async ({ page }) => {
    const havuz = await soruHavuzuKur("SINAV");
    test.skip(havuz.taslaklar.length < 2, `${HAVUZ_YOK} Üretim gerekçeleri: ${havuz.gerekce}`);
    await hepsiniOnayla(havuz);

    await signIn(page, BURAK);
    await page.goto(`/courses/${havuz.course.id}/exam`);
    await page.getByRole("button", { name: "Alıştırma başlat" }).click();

    const onceki = page.getByRole("button", { name: "Önceki" });
    const sonraki = page.getByRole("button", { name: /Sonraki soru/ });

    // Gezinme düğmeleri `disabled` değil `aria-disabled` kullanıyor: devre dışı
    // bırakılan öğe odağı <body>'ye atardı.
    await expect(onceki).toHaveAttribute("aria-disabled", "true");

    await page.locator('input[type="radio"]').first().check();
    await sonraki.click();
    await expect(page.getByText(`2/${havuz.taslaklar.length}`)).toBeVisible();

    await onceki.click();
    await expect(page.getByText(`1/${havuz.taslaklar.length}`)).toBeVisible();
    // Geri dönünce önceki cevap yerinde durmalı.
    await expect(page.locator('input[type="radio"]').first()).toBeChecked();
  });

  test("ipucu düğmesi alıştırmada VAR, sınavda YOK", async ({ page }) => {
    /*
     * Mod farkı yüzeyde de görünür: `exam` modunda ipucu ucu 403 döner, o yüzden
     * düğme devre dışı bırakılmaz, HİÇ çizilmez (Anayasa XI). Devre dışı bir
     * düğme bırakılsaydı öğrenci sınav sırasında ona basmayı denerdi.
     */
    const havuz = await soruHavuzuKur("IPUCU");
    test.skip(havuz.taslaklar.length === 0, `${HAVUZ_YOK} Üretim gerekçeleri: ${havuz.gerekce}`);
    await hepsiniOnayla(havuz);

    const ipucu = page.getByRole("button", { name: /İpucu al|Sonraki ipucu/ });

    await signIn(page, BURAK);
    await page.goto(`/courses/${havuz.course.id}/exam`);

    await page.getByRole("button", { name: "Alıştırma başlat" }).click();
    await expect(ipucu).toBeVisible();

    /*
     * Sınav modu için oturumu bırakmak gerekiyor. Açık oturumun kimliği
     * tarayıcıda saklanıyor ve ekran onu bulduğu sürece başlangıç paneline
     * dönmüyor; kaydı silmek, "sınavı bitirip yeniden başla" yolunu tekrar
     * etmeden aynı yere varır ve bu vakanın ölçtüğü şey bitirme akışı değil.
     */
    await page.evaluate(
      (id) => localStorage.removeItem(`dou-synapse-exam-session:${id}`),
      havuz.course.id,
    );
    await page.reload();

    await page.getByRole("button", { name: "Sınav başlat" }).click();
    await expect(page.getByRole("button", { name: "Cevabı gönder" })).toBeVisible();
    await expect(ipucu).toHaveCount(0);
  });

  test("sınav başlayınca Asistan AYNI SEKMEDE kilitlenir, bitince açılır", async ({ page }) => {
    /*
     * İki ayrı kusurun testi, ikisi de canlı tarayıcıda bulundu.
     *
     * Birincisi ve asıl olanı: kilit sunucuda çalışıyordu ama açık→kilitli
     * geçişi izlenmiyordu. Kilit yoklaması yalnız KİLİTLİYKEN koşuyor (kilit
     * kalkınca kendiliğinden dursun diye) ve bu, izlenmesi gereken kenarı ters
     * seçmekti: öğrenci sınavı başlattığı sekmede "Asistan" bağlantısı açık
     * kalıyordu. Yeni sekmede kilitliydi, backend her yolu 403 ile reddediyordu
     * — yani güvenlik açığı değil, ama etkin görünüp iş yapmayan bir yüzey
     * (Anayasa XI). Bu vaka o geçişi sabitler.
     *
     * İkincisi: kilidin GERİ AÇILDIĞI. Fazla kapatan bir kilit, kapatmayan bir
     * kilit kadar kusurludur ve sınavını bitiren öğrenciyi asistandan mahrum
     * bırakırdı.
     */
    const havuz = await soruHavuzuKur("KILIT");
    test.skip(havuz.taslaklar.length === 0, `${HAVUZ_YOK} Üretim gerekçeleri: ${havuz.gerekce}`);
    await hepsiniOnayla(havuz);

    const asistanBaglantisi = page.getByRole("link", { name: "Asistan" });
    const kilitliSekme = page.getByText("Kilitli");

    await signIn(page, BURAK);
    await page.goto(`/courses/${havuz.course.id}/exam`);
    await expect(asistanBaglantisi).toBeVisible();

    await page.getByRole("button", { name: "Sınav başlat" }).click();
    await expect(page.getByRole("button", { name: "Cevabı gönder" })).toBeVisible();

    // Sayfa YENİLENMEDEN: geçişin izlendiğinin kanıtı burası.
    await expect(kilitliSekme).toBeVisible();
    await expect(asistanBaglantisi).toHaveCount(0);

    // Aynı availability kararı yeni kompakt asistan yüzeyini de kilitler.
    // Tetikleyici görünür kalır ki kullanıcı neden kapalı olduğunu okuyabilsin;
    // besteci ve token harcatan gönderim yüzeyi hiç çizilmez.
    await page.getByRole("button", { name: "Ders Koçu" }).click();
    const asistanPaneli = page.getByRole("dialog");
    await expect(
      asistanPaneli.getByText("Asistan sınav sırasında kapalı", { exact: true }),
    ).toBeVisible();
    await expect(asistanPaneli.getByRole("button", { name: "Gönder" })).toHaveCount(0);
    await asistanPaneli.getByRole("button", { name: "Ders asistanını kapat" }).click();

    // Sunucu da aynı kararı veriyor: kilitli sekme bir süs değil.
    await page.goto(`/courses/${havuz.course.id}/chat`);
    await expect(page.getByText(/süren bir sınav oturumun var/)).toBeVisible();
    await expect(page.getByPlaceholder("Ders materyaline soru sorun…")).toHaveCount(0);

    await page.goto(`/courses/${havuz.course.id}/exam`);
    await page.getByRole("button", { name: "Sınavı bitir" }).click();
    await page.getByRole("button", { name: "Bitir ve sonucu gör" }).click();

    await expect(asistanBaglantisi).toBeVisible();
    await expect(kilitliSekme).toHaveCount(0);
  });

  test("onaylanmış sorusu olmayan derste sınav bir HATA değil, boş durumdur", async ({ page }) => {
    // Havuz boşken sunucu 409 döndürüyor; ekran bunu kırmızı kutuya değil nötr
    // boş duruma çeviriyor. Öğrencinin yapabileceği bir şey yok, arıza da yok.
    const course = await createCourse("BOSHAVUZ");
    await apiPost(`/courses/${course.id}/members`, { email: BURAK.email, role: "student" }, AYSE);

    await signIn(page, BURAK);
    await page.goto(`/courses/${course.id}/exam`);
    await page.getByRole("button", { name: "Alıştırma başlat" }).click();

    await expect(page.getByText(/henüz onaylanmış soru yok/)).toBeVisible({ timeout: 15_000 });
    await expect(hataDuyurulari(page)).toHaveCount(0);
    await expect(page.locator(".text-danger")).toHaveCount(0);
  });
});

test.describe("rol ayrımı", () => {
  test("öğrenci eğitmen kontrollerini görmez", async ({ page }) => {
    const course = await createCourse("ROL");
    await apiPost(`/courses/${course.id}/members`, { email: BURAK.email, role: "student" }, AYSE);

    await signIn(page, BURAK);
    await page.goto(`/courses/${course.id}`);

    // exact: "Materyal yükle" alt dizgesi "materyal yüklemedi" içinde de geçiyor.
    await expect(page.getByText("Materyal yükle", { exact: true })).toBeHidden();
    await expect(page.getByRole("button", { name: /dosyasını sil$/ })).toHaveCount(0);
    await expect(page.getByRole("navigation").getByText("Soru havuzu")).toHaveCount(0);
  });

  test("ilerleme ekranı role göre farklı soruya cevap verir", async ({ page }) => {
    const course = await createCourse("ILERLEME");
    await apiPost(`/courses/${course.id}/members`, { email: BURAK.email, role: "student" }, AYSE);

    await signIn(page, BURAK);
    await page.goto(`/courses/${course.id}/analytics`);
    await expect(page.getByText("İlerlemem")).toBeVisible();
    // ARCHITECTURE §5: bu ibare ekranda ZORUNLU.
    await expect(page.getByText(/resmî bir not değildir/)).toBeVisible();
  });

  test("çalışılmamış konu SIFIR PUAN olarak gösterilmez", async ({ page }) => {
    /*
     * "Bilmiyoruz" ile "kötüsün" iki ayrı cümledir (Anayasa III). Hiç
     * cevaplanmamış konu listeye 0,00 ile girerse öğrenci hiç girmediği
     * konudan sıfır aldığını sanır; sunucu da o konuları `topics` içinde
     * göndermiyor, yalnız SAYIYORUM diyor (`untracked_topics`).
     */
    const course = await createCourse("OLCUMSUZ");
    await apiPost(`/courses/${course.id}/members`, { email: BURAK.email, role: "student" }, AYSE);
    await apiPost(`/courses/${course.id}/topics`, { name: "E2E Konu Bir" }, AYSE);
    await apiPost(`/courses/${course.id}/topics`, { name: "E2E Konu İki" }, AYSE);

    await signIn(page, BURAK);
    await page.goto(`/courses/${course.id}/analytics`);

    await expect(page.getByText(/2 konu henüz çalışılmadı/)).toBeVisible({ timeout: 15_000 });
    // Konular listede HİÇ yok — dolayısıyla yanlarında bir puan da yok.
    await expect(page.getByText("E2E Konu Bir")).toHaveCount(0);
    await expect(page.getByText("E2E Konu İki")).toHaveCount(0);
    await expect(page.getByText("0,00")).toHaveCount(0);
    // Ölçüm olmayan yerde 0 değil, "Ölçüm yok" yazar.
    await expect(page.getByText("Ölçüm yok").first()).toBeVisible();
    // Boşluk bir arıza değil: sakin bir sonraki adım var.
    await expect(hataDuyurulari(page)).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Sınav provasına git" })).toBeVisible();
  });
});

test.describe("izolasyon", () => {
  test("üye olmayan öğrenci dersin VARLIĞINI bile öğrenemez", async ({ page }) => {
    // "Yetkiniz yok" demek dersin var olduğunu sızdırmaktır; sistem 404 döner.
    const course = await createCourse("IZOLASYON");
    await signIn(page, BURAK); // derse ÜYE DEĞİL
    await page.goto(`/courses/${course.id}`);

    await expect(page.getByText("Ders bulunamadı.")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("E2E Test Dersi IZOLASYON")).toBeHidden();

    /*
     * Aynı zamanda yukarıdaki "hata gibi görünmemeli" vakalarının kalibrasyonu.
     * Onlar `hataDuyurulari` ve `.text-danger` SAYISININ SIFIR olmasına dayanıyor
     * ve bir seçici yanlış yazılırsa sıfır her ekranda sağlanır — vakalar sessizce
     * boşa döner. Burada gerçek bir hata var; sayaçların onu GÖRDÜĞÜ gösteriliyor.
     */
    await expect(hataDuyurulari(page)).toHaveCount(1);
    await expect(page.locator(".text-danger")).toHaveCount(1);
  });
});
