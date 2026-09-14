import type { Page, Request, Response } from "@playwright/test";

/**
 * Ağ izleyici — "bu metin tel üzerinde hiç geçmedi" iddiasının kanıt aracı.
 *
 * Neden ayrı bir dosya: iddia ancak İKİ yönü birden okursa doğrudur. Yalnız
 * yanıt gövdelerine bakan bir sonda, metni istemcinin KENDİSİ gönderdiğinde
 * (arama kutusu, telemetri, taslak senkronu) hiçbir şey görmez ve test yeşil
 * kalır. Bu yüzden istek gövdesi de kaydedilir.
 *
 * Sınır: yalnız gövde metinleri okunur. İkili yanıtlar (resim, font) atlanır —
 * sınav sorusu oradan sızamaz ve okumaya çalışmak koşuyu yavaşlatır.
 */

export interface AgKaydi {
  /** İsteğin tam adresi; ihlal bulunduğunda hangi uç olduğunu söyler. */
  readonly url: string;
  /** "istek" ya da "yanit" — sızıntının yönü. */
  readonly yon: "istek" | "yanit";
  readonly govde: string;
}

export interface AgIzi {
  /**
   * O ana kadar görülen tüm gövdeler. Beklemeden okumak yanlış olur: gövde
   * okuma asenkrondur ve tamamlanmamış okumalar sayılmazsa sonda, sızıntıyı
   * yalnız yavaş geldiği için kaçırır.
   */
  kayitlar(): Promise<AgKaydi[]>;
  /** Dinlemeyi bırakır. Biriken kayıtlar korunur. */
  durdur(): void;
}

/** Gövde okuma tavanı. Tek bir yanıtın belleği doldurmasını engeller. */
const AZAMI_GOVDE = 2_000_000;

const IKILI_TURLER = /^(image|font|video|audio)\//i;

/**
 * `page` üzerindeki tüm trafiği kaydetmeye başlar.
 *
 * Çağrı `page.goto`'dan ÖNCE yapılmalıdır: dinleyici takılmadan önce tamamlanan
 * bir yanıt hiçbir zaman görülmez ve sonda sessizce kör kalır.
 */
export function agiIzle(page: Page): AgIzi {
  const bekleyen: Promise<AgKaydi | null>[] = [];

  const istekDinleyici = (istek: Request) => {
    const govde = istek.postData();
    if (govde !== null) {
      bekleyen.push(Promise.resolve({ url: istek.url(), yon: "istek", govde }));
    }
  };

  const yanitDinleyici = (yanit: Response) => {
    const tur = yanit.headers()["content-type"] ?? "";
    if (IKILI_TURLER.test(tur)) return;
    bekleyen.push(
      yanit
        .text()
        .then((govde): AgKaydi => ({
          url: yanit.url(),
          yon: "yanit",
          govde: govde.slice(0, AZAMI_GOVDE),
        }))
        // Yönlendirme, iptal edilmiş istek ve kapanmış sayfa gövde vermez.
        // Bunlar bir kusur değil; sessizce atlanır.
        .catch(() => null),
    );
  };

  page.on("request", istekDinleyici);
  page.on("response", yanitDinleyici);

  return {
    async kayitlar(): Promise<AgKaydi[]> {
      const cozulen = await Promise.all([...bekleyen]);
      return cozulen.filter((kayit): kayit is AgKaydi => kayit !== null);
    },
    durdur() {
      page.off("request", istekDinleyici);
      page.off("response", yanitDinleyici);
    },
  };
}

/** Metni taşıyan kayıtlar. Boş dizi "hiç geçmedi" demektir. */
export function metniTasiyanlar(kayitlar: readonly AgKaydi[], metin: string): AgKaydi[] {
  return kayitlar.filter((kayit) => kayit.govde.includes(metin));
}

/** Hata mesajında hangi uçların suçlandığını okunur biçimde söyler. */
export function ozetle(kayitlar: readonly AgKaydi[]): string {
  return kayitlar.map((kayit) => `${kayit.yon} ${kayit.url}`).join("\n");
}
