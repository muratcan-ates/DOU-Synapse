/**
 * `useSubmit`'in sessiz kurallarının testi.
 *
 * Kanca React'e bağlı olduğu için doğrudan koşturulamıyor (bu paket DOM'suz
 * `bun test` ile koşar); karar çekirdeği `createSubmitGate` olarak saf
 * çıkarıldı ve testler onu sınıyor — kancadaki sıra bozulursa burası tutmaz.
 *
 * Neden bunlar test edilmeli: hepsinin bozulması sessizdir. Çift-gönderim
 * kapısı yalnız kullanıcı aynı tick'te iki kez tetiklediğinde görünür —
 * geliştirme makinesinde tek tıkla her şey doğru görünür, hata canlıda çift
 * kayıtla çıkar. Senkron fırlatan eylemin kapıyı açık bırakması da öyle:
 * form bir daha asla gönderilemez ve hiçbir konsol hatası kalmaz.
 */

import { describe, expect, test } from "bun:test";

import { ApiError } from "./api";
import { createSubmitGate } from "./use-submit";

/** Elle çözülen söz: eylemin bitişini testin kontrolüne verir. */
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

/** Kancanın `dispatch` karşılığı: üç çıkışı tek kayıtta toplar. */
function recorder() {
  const log: string[] = [];
  let busy = false;
  const causes: unknown[] = [];
  return {
    log,
    causes,
    isBusy: () => busy,
    handlers: {
      setBusy: (next: boolean) => {
        busy = next;
        log.push(`busy:${next}`);
      },
      clearError: () => log.push("clear"),
      reportError: (cause: unknown) => {
        causes.push(cause);
        log.push("report");
      },
    },
  };
}

describe("createSubmitGate — sıra ve kapı", () => {
  test("başarılı gönderim: kapı → hata temizliği → eylem → busy düşer", async () => {
    const state = recorder();
    const gate = createSubmitGate<[]>({
      action: () => {
        state.log.push("action");
      },
      ...state.handlers,
    });

    await gate();

    expect(state.log).toEqual(["busy:true", "clear", "action", "busy:false"]);
    expect(state.isBusy()).toBe(false);
  });

  test("busy iken ikinci çağrı YOK SAYILIR — aynı tick'te bile", async () => {
    const state = recorder();
    const request = deferred<void>();
    let runs = 0;
    const gate = createSubmitGate<[]>({
      action: () => {
        runs += 1;
        return request.promise;
      },
      ...state.handlers,
    });

    // İki tetikleme aynı tick'te: state tabanlı bir kapı ikisini de geçirirdi,
    // çünkü ilk `setBusy(true)` henüz hiçbir render'a yansımamış olurdu.
    const first = gate();
    const second = gate();

    expect(runs).toBe(1);
    await second; // yok sayılan çağrı hemen çözülür, hiçbir şey yazmaz
    expect(state.log).toEqual(["busy:true", "clear"]);

    request.resolve();
    await first;
    expect(runs).toBe(1);
    expect(state.isBusy()).toBe(false);
  });

  test("uçuş bittikten sonra kapı yeniden açılır", async () => {
    const state = recorder();
    let runs = 0;
    const gate = createSubmitGate<[]>({
      action: () => {
        runs += 1;
      },
      ...state.handlers,
    });

    await gate();
    await gate();
    expect(runs).toBe(2);
  });

  test("eylem reddederse ham hata eşlemeye gider ve busy düşer", async () => {
    const state = recorder();
    const failure = new ApiError("Sunucu cümlesi.", "conflict", 409, "req-1");
    const gate = createSubmitGate<[]>({
      action: () => Promise.reject(failure),
      ...state.handlers,
    });

    await gate();

    expect(state.causes).toEqual([failure]);
    expect(state.log).toEqual(["busy:true", "clear", "report", "busy:false"]);
  });

  test("SENKRON fırlatan eylem kapıyı açık bırakmaz", async () => {
    const state = recorder();
    const gate = createSubmitGate<[]>({
      action: () => {
        throw new Error("render sırasında patlayan doğrulama");
      },
      ...state.handlers,
    });

    await gate();
    expect(state.isBusy()).toBe(false);

    // Form ölmedi: bir sonraki gönderim normal koşar.
    await gate();
    expect(state.log.filter((entry) => entry === "report")).toHaveLength(2);
  });

  test("argümanlar eyleme olduğu gibi taşınır", async () => {
    const state = recorder();
    const seen: unknown[][] = [];
    const gate = createSubmitGate<[string, number]>({
      action: (name, count) => {
        seen.push([name, count]);
      },
      ...state.handlers,
    });

    await gate("deadlock", 4);
    expect(seen).toEqual([["deadlock", 4]]);
  });
});
