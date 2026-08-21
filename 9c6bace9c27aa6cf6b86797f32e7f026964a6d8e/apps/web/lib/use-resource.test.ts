/**
 * `useResource`'un iki sessiz kuralının testi.
 *
 * Kanca React'e bağlı olduğu için doğrudan koşturulamıyor (bu paket DOM'suz
 * `bun test` ile koşar). Bu yüzden kancanın iki kararı saf fonksiyonlara
 * çıkarıldı ve testler onları sınıyor: `createRequestGate` (hangi cevap
 * yazabilir) ve `resourceReducer` (hata veriyi ne zaman siler).
 *
 * Neden bu iki şey test edilmeli: ikisinin de bozulması sessizdir. Yarış
 * koşulu yalnız cevaplar sıra dışı döndüğünde görünür — geliştirme
 * makinesinde localhost her zaman sırayla döner, hata demo günü çıkar.
 * Aşağıdaki `simulateHook`, kancanın `reload` gövdesinin birebir aynısını
 * kurar; kancadaki sıra bozulursa bu testler tutmaz.
 */

import { describe, expect, test } from "bun:test";
import { errorMessage } from "./errors";
import {
  createRequestGate,
  EMPTY_RESOURCE_STATE,
  resourceReducer,
  type ResourceState,
} from "./use-resource";

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

/** Kancanın `reload` gövdesi + durumu — React olmadan. */
function simulateHook<T>() {
  const gate = createRequestGate();
  let state: ResourceState<T> = EMPTY_RESOURCE_STATE;

  return {
    gate,
    get state() {
      return state;
    },
    async reload(fetcher: () => Promise<T>) {
      const token = gate.begin();
      try {
        const next = await fetcher();
        if (!gate.isCurrent(token)) return;
        state = resourceReducer(state, { type: "loaded", data: next });
      } catch (e) {
        if (!gate.isCurrent(token)) return;
        state = resourceReducer(state, { type: "failed", message: errorMessage(e) });
      }
    },
    reset() {
      gate.invalidate();
      state = resourceReducer(state, { type: "reset" });
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
    const next = resourceReducer(EMPTY_RESOURCE_STATE as ResourceState<string>, {
      type: "failed",
      message: "Ders bulunamadı.",
    });
    expect(next.error).toBe("Ders bulunamadı.");
    expect(next.refreshError).toBeNull();
    expect(next.data).toBeNull();
  });

  test("elde veri VARKEN hata `data`'yı silmez, `error`'ı doldurmaz", () => {
    const next = resourceReducer(dolu, {
      type: "failed",
      message: "Bağlantı kurulamadı.",
    });
    expect(next.data).toBe("ders listesi");
    expect(next.error).toBeNull();
    expect(next.refreshError).toBe("Bağlantı kurulamadı.");
  });

  test("üst üste başarısız tazeleme de veriyi silmez", () => {
    let s = resourceReducer(dolu, { type: "failed", message: "bir" });
    s = resourceReducer(s, { type: "failed", message: "iki" });
    expect(s.data).toBe("ders listesi");
    expect(s.error).toBeNull();
    expect(s.refreshError).toBe("iki");
  });

  test("başarılı tur her iki hatayı da temizler", () => {
    const bozuk = resourceReducer(dolu, { type: "failed", message: "kopma" });
    const next = resourceReducer(bozuk, { type: "loaded", data: "yeni liste" });
    expect(next.data).toBe("yeni liste");
    expect(next.error).toBeNull();
    expect(next.refreshError).toBeNull();
  });

  test("reset her şeyi sıfırlar (deps değişimi)", () => {
    const bozuk = resourceReducer(dolu, { type: "failed", message: "kopma" });
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
    const bozuk = resourceReducer(dolu, { type: "failed", message: "kopma" });
    expect(resourceReducer(bozuk, { type: "failed", message: "kopma" })).toBe(bozuk);
    // Ama gerçek değişimde yeni nesne döner, yoksa React güncellemeyi kaçırır.
    expect(resourceReducer(bozuk, { type: "failed", message: "başka" })).not.toBe(bozuk);
  });

  test("`loading` yalnız ilk yüklemede doğrudur", () => {
    // Kancadaki türev: data === null && error === null.
    const isLoading = (s: ResourceState<string>) => s.data === null && s.error === null;
    expect(isLoading(EMPTY_RESOURCE_STATE)).toBe(true);
    expect(isLoading(dolu)).toBe(false);
    expect(
      isLoading(
        resourceReducer(EMPTY_RESOURCE_STATE as ResourceState<string>, {
          type: "failed",
          message: "hata",
        }),
      ),
    ).toBe(false);
    // Tazeleme hatası "yükleniyor"a geri döndürmez.
    expect(isLoading(resourceReducer(dolu, { type: "failed", message: "hata" }))).toBe(
      false,
    );
  });
});
