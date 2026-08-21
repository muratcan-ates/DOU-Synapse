/**
 * `useResource`'un sessiz kurallarının testi.
 *
 * Kanca React'e bağlı olduğu için doğrudan koşturulamıyor (bu paket DOM'suz
 * `bun test` ile koşar). Bu yüzden kancanın kararları saf fonksiyonlara
 * çıkarıldı ve testler onları sınıyor: `createRequestGate` (hangi cevap
 * yazabilir), `resourceReducer` (hata veriyi ne zaman siler) ve `pollDelayMs`
 * (yoklama ne zaman yavaşlar).
 *
 * Neden bunlar test edilmeli: hepsinin bozulması sessizdir. Yarış koşulu
 * yalnız cevaplar sıra dışı döndüğünde görünür — geliştirme makinesinde
 * localhost her zaman sırayla döner, hata demo günü çıkar. Yoklamanın
 * yavaşlaması da yalnız sunucu ölüyken gözlenir.
 * Aşağıdaki `simulateHook`, kancanın `reload` gövdesinin birebir aynısını
 * kurar; kancadaki sıra bozulursa bu testler tutmaz.
 */

import { describe, expect, test } from "bun:test";
import { ApiError } from "./api";
import { describeError, type ErrorInfo } from "./errors";
import {
  createRequestGate,
  EMPTY_RESOURCE_STATE,
  POLL_BACKOFF_CAP_MS,
  pollDelayMs,
  resourceReducer,
  type ResourceAction,
  type ResourceState,
} from "./use-resource";

/**
 * Başarısızlık eylemi kısayolu.
 *
 * Reducer'ın okuduğu tek alan mesaj; sınıf ve destek kodu kancanın diğer
 * çıktılarını besliyor (T403/T406). Testler o ikisini her satırda tekrar
 * yazmasın diye burada varsayılıyor.
 */
function failed(message: string): ResourceAction<string> {
  return { type: "failed", error: { message, kind: "transient", requestId: null } };
}

/** Elle çözülen söz: cevapların dönüş sırasını testin kontrolüne verir. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  // Sonucu kimse beklemeden reddedilirse Bun "unhandled rejection" bağırır.
  promise.catch(() => {});
  return { promise, resolve, reject };
}

/**
 * Kancanın `reload` gövdesi + durumu — React olmadan.
 *
 * Kancadaki `dispatch` üç türevi birden yazıyor (durum, hata bilgisi, ardışık
 * başarısızlık sayacı); buradaki `apply` de öyle. Kancada bunlardan biri
 * unutulursa test tutmaz.
 */
function simulateHook<T>() {
  const gate = createRequestGate();
  let state: ResourceState<T> = EMPTY_RESOURCE_STATE;
  let failure: ErrorInfo | null = null;
  let failureStreak = 0;

  const apply = (action: ResourceAction<T>) => {
    state = resourceReducer(state, action);
    failure = action.type === "failed" ? action.error : null;
    failureStreak = action.type === "failed" ? failureStreak + 1 : 0;
  };

  return {
    gate,
    get state() {
      return state;
    },
    get errorKind() {
      return failure?.kind ?? null;
    },
    get errorRequestId() {
      return failure?.requestId ?? null;
    },
    get failureStreak() {
      return failureStreak;
    },
    async reload(fetcher: () => Promise<T>) {
      const token = gate.begin();
      try {
        const next = await fetcher();
        if (!gate.isCurrent(token)) return;
        apply({ type: "loaded", data: next });
      } catch (e) {
        if (!gate.isCurrent(token)) return;
        apply({ type: "failed", error: describeError(e) });
      }
    },
    reset() {
      gate.invalidate();
      apply({ type: "reset" });
    },
  };
}

describe("istek sıra kapısı — geç dönen eski cevap taze veriyi ezmez", () => {
  test("cevaplar sıra dışı dönünce en son BAŞLAYAN istek kazanır", async () => {
    const store = simulateHook<string>();
    const eski = deferred<string>();
    const taze = deferred<string>();

    const ilk = store.reload(() => eski.promise);
    const ikinci = store.reload(() => taze.promise);

    taze.resolve("taze liste");
    await ikinci;
    expect(store.state.data).toBe("taze liste");

    // Ağ eski isteği şimdi teslim ediyor: yazamamalı.
    eski.resolve("eski liste");
    await ilk;
    expect(store.state.data).toBe("taze liste");
  });

  test("geç dönen eski HATA taze veriyi bozmaz", async () => {
    const store = simulateHook<string>();
    const eski = deferred<string>();
    const taze = deferred<string>();

    const ilk = store.reload(() => eski.promise);
    const ikinci = store.reload(() => taze.promise);

    taze.resolve("taze liste");
    await ikinci;

    eski.reject(new Error("kopma"));
    await ilk;

    expect(store.state.data).toBe("taze liste");
    expect(store.state.error).toBeNull();
    expect(store.state.refreshError).toBeNull();
  });

  test("sıra dışı dönüş olmadığında normal akış bozulmaz", async () => {
    const store = simulateHook<string>();
    await store.reload(async () => "bir");
    expect(store.state.data).toBe("bir");
    await store.reload(async () => "iki");
    expect(store.state.data).toBe("iki");
  });

  test("deps değişimi (reset) uçuştaki cevabı geçersizler", async () => {
    const store = simulateHook<string>();
    const uctaki = deferred<string>();
    const ilk = store.reload(() => uctaki.promise);

    // Kullanıcı başka derse geçti: ekran boşaldı, eski istek hâlâ uçuyor.
    store.reset();
    expect(store.state.data).toBeNull();

    uctaki.resolve("önceki dersin listesi");
    await ilk;

    // Yanlış dersin verisi ekrana düşmemeli.
    expect(store.state.data).toBeNull();
  });

  test("reset sonrası yeni istek yine yazabilir", async () => {
    const store = simulateHook<string>();
    store.reset();
    await store.reload(async () => "yeni dersin listesi");
    expect(store.state.data).toBe("yeni dersin listesi");
  });

  test("kapı kimlikleri tekrar etmez", () => {
    const gate = createRequestGate();
    const a = gate.begin();
    const b = gate.begin();
    expect(a).not.toBe(b);
    expect(gate.isCurrent(a)).toBe(false);
    expect(gate.isCurrent(b)).toBe(true);
    gate.invalidate();
    expect(gate.isCurrent(b)).toBe(false);
  });
});

describe("durum makinesi — geçici hata sayfayı silmez", () => {
  const dolu: ResourceState<string> = {
    data: "ders listesi",
    error: null,
    refreshError: null,
  };

  test("elde veri YOKKEN hata ekranı kapatan hatadır", () => {
    const next = resourceReducer(
      EMPTY_RESOURCE_STATE as ResourceState<string>,
      failed("Ders bulunamadı."),
    );
    expect(next.error).toBe("Ders bulunamadı.");
    expect(next.refreshError).toBeNull();
    expect(next.data).toBeNull();
  });

  test("elde veri VARKEN hata `data`'yı silmez, `error`'ı doldurmaz", () => {
    const next = resourceReducer(dolu, failed("Bağlantı kurulamadı."));
    expect(next.data).toBe("ders listesi");
    expect(next.error).toBeNull();
    expect(next.refreshError).toBe("Bağlantı kurulamadı.");
  });

  test("üst üste başarısız tazeleme de veriyi silmez", () => {
    let s = resourceReducer(dolu, failed("bir"));
    s = resourceReducer(s, failed("iki"));
    expect(s.data).toBe("ders listesi");
    expect(s.error).toBeNull();
    expect(s.refreshError).toBe("iki");
  });

  test("başarılı tur her iki hatayı da temizler", () => {
    const bozuk = resourceReducer(dolu, failed("kopma"));
    const next = resourceReducer(bozuk, { type: "loaded", data: "yeni liste" });
    expect(next.data).toBe("yeni liste");
    expect(next.error).toBeNull();
    expect(next.refreshError).toBeNull();
  });

  test("reset her şeyi sıfırlar (deps değişimi)", () => {
    const bozuk = resourceReducer(dolu, failed("kopma"));
    expect(resourceReducer(bozuk, { type: "reset" })).toEqual({
      data: null,
      error: null,
      refreshError: null,
    });
  });

  test("hiçbir alan değişmiyorsa ESKİ nesne döner (boşuna render yok)", () => {
    const bos: ResourceState<string> = EMPTY_RESOURCE_STATE;
    // İlk mount: durum zaten boşken reset gelir.
    expect(resourceReducer(bos, { type: "reset" })).toBe(bos);
    // Polling saniyede bir aynı hatayı yazmaya çalışır.
    const bozuk = resourceReducer(dolu, failed("kopma"));
    expect(resourceReducer(bozuk, failed("kopma"))).toBe(bozuk);
    // Ama gerçek değişimde yeni nesne döner, yoksa React güncellemeyi kaçırır.
    expect(resourceReducer(bozuk, failed("başka"))).not.toBe(bozuk);
  });

  test("`loading` yalnız ilk yüklemede doğrudur", () => {
    // Kancadaki türev: data === null && error === null.
    const isLoading = (s: ResourceState<string>) => s.data === null && s.error === null;
    expect(isLoading(EMPTY_RESOURCE_STATE)).toBe(true);
    expect(isLoading(dolu)).toBe(false);
    expect(
      isLoading(
        resourceReducer(EMPTY_RESOURCE_STATE as ResourceState<string>, failed("hata")),
      ),
    ).toBe(false);
    // Tazeleme hatası "yükleniyor"a geri döndürmez.
    expect(isLoading(resourceReducer(dolu, failed("hata")))).toBe(false);
  });
});

describe("yoklama aralığı — başarısızlıkta yavaşlar (T404, FR-156)", () => {
  test("her şey yolundayken taban aralık kullanılır", () => {
    expect(pollDelayMs(2000, 0)).toBe(2000);
  });

  test("ardışık başarısızlıkta aralık ikişer katlanır", () => {
    expect(pollDelayMs(2000, 1)).toBe(4000);
    expect(pollDelayMs(2000, 2)).toBe(8000);
    expect(pollDelayMs(2000, 3)).toBe(16_000);
  });

  test("tavan var: yoklama seyrekleşir ama BÜSBÜTÜN durmaz", () => {
    // Durdurmak, sunucu geri geldiğinde ekranın bunu hiç fark etmemesi olurdu.
    expect(pollDelayMs(2000, 20)).toBe(POLL_BACKOFF_CAP_MS);
    expect(pollDelayMs(2000, 20)).toBeLessThan(Number.POSITIVE_INFINITY);
  });

  test("taban tavandan büyükse aralık SESSİZCE kısalmaz", () => {
    // US1 kilidi 30 saniyeyle yokluyor; bir gün taban tavanı aşarsa
    // yavaşlatma isteği hızlandırmaya dönüşmemeli.
    expect(pollDelayMs(90_000, 3)).toBe(90_000);
    expect(pollDelayMs(90_000, 0)).toBe(90_000);
  });

  test("başarılı tek tur sayacı sıfırlar", async () => {
    const store = simulateHook<string>();
    await store.reload(async () => {
      throw new ApiError("kopma", "internal_error", 503, "r1");
    });
    await store.reload(async () => {
      throw new ApiError("kopma", "internal_error", 503, "r2");
    });
    expect(store.failureStreak).toBe(2);
    expect(pollDelayMs(2000, store.failureStreak)).toBe(8000);

    await store.reload(async () => "liste");
    expect(store.failureStreak).toBe(0);
    expect(pollDelayMs(2000, store.failureStreak)).toBe(2000);
  });

  test("deps değişimi de sayacı sıfırlar: yeni dersin suçu yok", () => {
    const store = simulateHook<string>();
    store.reset();
    expect(store.failureStreak).toBe(0);
  });
});

describe("hata sınıfı ve destek kodu kancadan çıkar (T403/T406)", () => {
  test("sunucu hatası sınıfını ve destek kodunu taşır", async () => {
    const store = simulateHook<string>();
    await store.reload(async () => {
      throw new ApiError("Ders bulunamadı.", "not_found", 404, "abc123");
    });
    expect(store.state.error).toBe("Ders bulunamadı.");
    expect(store.errorKind).toBe("permanent");
    expect(store.errorRequestId).toBe("abc123");
  });

  test("ağ hatası geçicidir ve destek kodu taşımaz", async () => {
    const store = simulateHook<string>();
    await store.reload(async () => {
      throw new TypeError("fetch failed");
    });
    expect(store.errorKind).toBe("transient");
    expect(store.errorRequestId).toBeNull();
  });

  test("başarılı tur sınıfı ve kodu temizler: ekranda eskimiş uyarı kalmaz", async () => {
    const store = simulateHook<string>();
    await store.reload(async () => {
      throw new ApiError("Ders bulunamadı.", "not_found", 404, "abc123");
    });
    await store.reload(async () => "liste");
    expect(store.errorKind).toBeNull();
    expect(store.errorRequestId).toBeNull();
  });

  test("geç dönen eski hata taze verinin sınıfını da bozmaz", async () => {
    const store = simulateHook<string>();
    const eski = deferred<string>();
    const taze = deferred<string>();

    const ilk = store.reload(() => eski.promise);
    const ikinci = store.reload(() => taze.promise);
    taze.resolve("taze liste");
    await ikinci;

    eski.reject(new ApiError("Ders bulunamadı.", "not_found", 404, "abc123"));
    await ilk;

    expect(store.errorKind).toBeNull();
    expect(store.errorRequestId).toBeNull();
  });
});
