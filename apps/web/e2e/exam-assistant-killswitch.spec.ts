import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { createE2eCourseIdentity } from "./fixtures";
import { agiIzle, metniTasiyanlar, ozetle } from "./fixtures/network-trace";

/**
 * SINAV KİLL-SWITCH'İ — kanıt GERÇEK sunucudan gelir.
 *
 * Bu dosyanın varlık sebebi tek bir cümle: sınav sürerken asistan ucuna atılan
 * doğrudan istek 4xx dönmelidir. "Dönmelidir" ifadesi ancak gerçek API yanıt
 * verdiğinde sınanmış olur.
 *
 * Bu yüzden 403 iddiası `request` (APIRequestContext) üzerinden kurulur:
 * o istek Node tarafından atılır ve `page.route` ile KESİLEMEZ. `route.fulfill`
 * ile üretilmiş bir 403, yalnız testin kendi uydurduğu cevabı doğrular — ürünün
 * değil. Bu dosyada hiçbir `page.route` kurulmaz; kurulursa bu yorum yalan olur.
 *
 * Sunucu tarafı zaten var, burada YENİDEN YAZILMADI:
 *   - `apps/api/app/api/deps.py` → `require_assistant_unlocked` / `UnlockedCourseMemberDep`
 *   - `apps/api/app/modules/assessment/exam_state.py` → `EXAM_LOCK_REASON`, `ExamLockedError` (403)
 *   - `apps/api/app/api/chat.py` → `GET /chat/availability` aynı kararı 200 ile anlatır
 *
 * İkinci iddia: sınav BAŞLAMADAN soru gövdesi ağ trafiğinde hiç geçmemelidir.
 * Katalog ucu bunu şemayla söz veriyor (`ExamCatalogItem` soru metni taşımaz);
 * burada o söz ölçülür. Ölçüm çift yönlüdür — önce "yok" denir, sonra sınav
 * başlatılıp AYNI sondayla "var" olduğu gösterilir. İkinci adım olmadan ilk
 * iddia, sondanın kör olmasıyla da sağlanabilirdi.
 */

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
//: Tohumlanmış kimlikler (supabase/seed_demo.sql) — testler kullanıcı yaratmaz.
const EGITMEN_BASLIKLARI = { Authorization: "Bearer dev:11111111-1111-1111-1111-111111111111" };
const OGRENCI_BASLIKLARI = { Authorization: "Bearer dev:22222222-2222-2222-2222-222222222222" };
const KAYNAK_ADI = "exam-killswitch-synthetic.md";

interface HazirDers {
  readonly dersId: string;
  readonly taban: string;
  /** Onaylanmış sorunun tam gövdesi; ağ sondasının aradığı metin. */
  readonly soruGovdesi: string;
}

async function dersHazirla(request: APIRequestContext): Promise<HazirDers> {
  const gonder = async (yol: string, veri: unknown) => {
    const yanit = await request.post(`${API}${yol}`, { headers: EGITMEN_BASLIKLARI, data: veri });
    expect(yanit.ok(), await yanit.text()).toBeTruthy();
    return yanit.json();
  };

  const ders = await gonder("/courses", createE2eCourseIdentity("KILL-SWITCH"));
  const yol = `/courses/${ders.id}`;
  await gonder(`${yol}/members`, { email: "burak@dogus.edu.tr", role: "student" });
  const konu = await gonder(`${yol}/topics`, { name: "Kilitlenme" });

  const yukleme = await request.post(`${API}${yol}/documents`, {
    headers: EGITMEN_BASLIKLARI,
    multipart: {
      file: {
        name: KAYNAK_ADI,
        mimeType: "text/markdown",
        buffer: Buffer.from(
          "# Kilitlenme\nKilitlenme, iki ya da daha fazla sürecin birbirinin bıraktığı kaynağı " +
            "beklerken hiçbirinin ilerleyememesi durumudur. Coffman koşulları karşılıklı dışlama, " +
            "tut ve bekle, kesintisizlik ve dairesel beklemedir.\n",
        ),
      },
    },
  });
  expect(yukleme.ok(), await yukleme.text()).toBeTruthy();
  await expect
    .poll(
      async () =>
        (await (await request.get(`${API}${yol}/documents`, { headers: EGITMEN_BASLIKLARI })).json())
          .items[0]?.status,
      { timeout: 25_000 },
    )
    .toBe("completed");

  const uretim = await gonder(`${yol}/questions/generate`, {
    topic_id: konu.id,
    count: 1,
    question_type: "mcq",
  });
  expect(uretim.questions).toHaveLength(1);
  const soru = uretim.questions[0];
  await gonder(`${yol}/questions/${soru.id}/approve`, {});

  const soruGovdesi = String(soru.payload.stem);
  // Kısa bir gövde HTML kabuğunda rastlantıyla geçebilir ve sonda anlamsızlaşır.
  expect(soruGovdesi.length).toBeGreaterThan(40);
  return { dersId: ders.id, taban: `${API}${yol}`, soruGovdesi };
}

async function girisYap(page: Page): Promise<void> {
  await page.goto("/");
  await page.getByRole("button", { name: /Burak Yılmaz/ }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

async function sinaviBitir(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Sınavı bitir", exact: true }).click();
  await page.getByRole("button", { name: "Bitir ve sonucu gör", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sınav sonucu", exact: true })).toBeVisible();
}

test("sınav başlamadan soru gövdesi ağda yok; sınav sürerken asistan ucu gerçek sunucudan 403 döner", async ({
  page,
  request,
}) => {
  test.setTimeout(180_000);
  const { dersId, taban, soruGovdesi } = await dersHazirla(request);

  // Sonda `goto`'dan ÖNCE kurulur: dinleyici takılmadan biten yanıt görülmez.
  const iz = agiIzle(page);
  try {
    await girisYap(page);
    await page.goto(`/courses/${dersId}/exam`);
    await expect(page.getByRole("heading", { name: "Sınav provası", exact: true })).toBeVisible();
    const baslat = page.getByRole("button", { name: "Sınav başlat", exact: true });
    await expect(baslat).toBeVisible();

    const oncesi = await iz.kayitlar();
    // Sonda gerçekten gövde okuyabiliyor mu: okunmamış bir sonda her iddiayı
    // "kanıtlar" ve hiçbirini sınamaz.
    expect(oncesi.length).toBeGreaterThan(0);
    const erkenSizinti = metniTasiyanlar(oncesi, soruGovdesi);
    expect(
      erkenSizinti.length,
      `Sınav başlamadan soru gövdesi şu trafikte göründü:\n${ozetle(erkenSizinti)}`,
    ).toBe(0);

    await baslat.click();
    await expect(page.getByRole("timer")).toBeVisible();

    // AYNI sonda, aynı sayfa: gövde artık görünmeli. Görünmeseydi yukarıdaki
    // "hiç geçmedi" iddiası ölçüm değil, körlük olurdu.
    await expect
      .poll(async () => metniTasiyanlar(await iz.kayitlar(), soruGovdesi).length, {
        timeout: 20_000,
      })
      .toBeGreaterThan(0);

    // --- Kill-switch: gerçek sunucu, kesilmemiş istek --------------------
    const dogrudanSohbet = await request.post(`${taban}/chat`, {
      headers: OGRENCI_BASLIKLARI,
      data: { question: "Coffman koşulları nelerdir?", mode: "qa" },
    });
    expect(dogrudanSohbet.status()).toBe(403);
    const hata = await dogrudanSohbet.json();
    expect(hata.error.code).toBe("exam_in_progress");

    // Geçmiş okuma da aynı kapıdan geçer: eski turların cevabı da bir yardım
    // yüzeyidir (`deps.py` yorumu).
    const gecmis = await request.get(`${taban}/chat/sessions`, { headers: OGRENCI_BASLIKLARI });
    expect(gecmis.status()).toBe(403);

    // Yoklama ucu kilitliyken de cevap verir ve AYNI sabiti taşır.
    const yoklama = await request.get(`${taban}/chat/availability`, { headers: OGRENCI_BASLIKLARI });
    expect(yoklama.status()).toBe(200);
    const karar = await yoklama.json();
    expect(karar.available).toBe(false);
    expect(karar.reason).toBe("exam_in_progress");
    expect(karar.message).toBe(hata.error.message);

    // --- Kill-switch göstergesi: metinle, yalnız renkle değil -------------
    const kilitliSekme = page.locator('span[aria-disabled="true"]').filter({ hasText: "Asistan" });
    await expect(kilitliSekme).toBeVisible();
    await expect(kilitliSekme).toContainText("Kilitli");
    // Metin sunucudan gelir; arayüz kendi cümlesini uydurmaz (Anayasa V).
    await expect(kilitliSekme).toHaveAttribute("title", karar.message);
    await expect(page.getByRole("navigation", { name: karar.message })).toBeVisible();
    // Soru kutusu sınav ekranında hiç çizilmez — kapalı bir uca yazdırmak,
    // kullanıcıyı 403'e yürütmek olurdu.
    await expect(page.getByRole("textbox", { name: "Sorun", exact: true })).toHaveCount(0);

    // --- Kilit sınava bağlı: sınav bitince kalkar ------------------------
    await sinaviBitir(page);
    const acilan = await request.get(`${taban}/chat/availability`, { headers: OGRENCI_BASLIKLARI });
    expect(acilan.status()).toBe(200);
    expect((await acilan.json()).available).toBe(true);
    const yenidenSohbet = await request.post(`${taban}/chat`, {
      headers: OGRENCI_BASLIKLARI,
      data: { question: "Coffman koşulları nelerdir?", mode: "qa" },
    });
    expect(yenidenSohbet.status()).toBe(200);
  } finally {
    iz.durdur();
  }
});
