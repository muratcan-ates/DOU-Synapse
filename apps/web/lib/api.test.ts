/**
 * İstek katmanının üç sessiz kuralının testi (T401, T402, T403 çekirdeği).
 *
 * Üçü de yalnız işler kötü gittiğinde gözlenir: bütçe ancak sunucu asılı
 * kalınca, yeniden deneme ancak hata dönünce, sınıflandırma ancak hatanın
 * türü değişince. Geliştirme makinesinde localhost hiçbirini tetiklemez;
 * yani bu kurallar test edilmezse demo günü ilk kez denenmiş olurlar.
 *
 * Zamana bağlı olanlar sahte zamanlayıcıyla koşuyor: gerçek 12 saniye
 * beklemek testi hem yavaş hem kararsız yapardı.
 */

import { afterEach, describe, expect, jest, test } from "bun:test";
import {
  ApiError,
  BUDGET_MS,
  api,
  backoffMs,
  budgetFor,
  classifyApiError,
  retriesFor,
  signOutWithLocalCleanup,
  withRetry,
} from "./api";

/* -------------------------------------------------------------------------
 * Gerçek sağlayıcı + yerel oturum çıkışı
 * ---------------------------------------------------------------------- */

describe("çıkış sağlayıcı sonucunu denetler ve yerel oturumu her durumda kapatır", () => {
  test("demo yolunda sağlayıcı olmadan yerel oturum temizlenir", async () => {
    let cleared = 0;

    await signOutWithLocalCleanup(null, () => {
      cleared += 1;
    });

    expect(cleared).toBe(1);
  });

  test("başarılı Supabase çıkışından sonra yerel oturum temizlenir", async () => {
    let cleared = 0;

    await signOutWithLocalCleanup(async () => ({ error: null }), () => {
      cleared += 1;
    });

    expect(cleared).toBe(1);
  });

  test("Supabase sonuç nesnesindeki hata yok sayılmaz ve temizlik yine çalışır", async () => {
    let cleared = 0;
    const providerError = new Error("Supabase çıkışı reddetti");
    const promise = signOutWithLocalCleanup(
      async () => ({ error: providerError }),
      () => {
        cleared += 1;
      },
    );

    await expect(promise).rejects.toBe(providerError);
    expect(cleared).toBe(1);
  });

  test("SDK söz vermeden hata fırlatsa da yerel temizlik atlanmaz", async () => {
    let cleared = 0;
    const providerError = new Error("ağ koptu");
    const promise = signOutWithLocalCleanup(
      async () => {
        throw providerError;
      },
      () => {
        cleared += 1;
      },
    );

    await expect(promise).rejects.toBe(providerError);
    expect(cleared).toBe(1);
  });
});

/* -------------------------------------------------------------------------
 * T401 · Bütçe seçimi
 * ---------------------------------------------------------------------- */

describe("bütçe isteğin kendisinden türetilir", () => {
  test("okuma varsayılan: metot verilmemişse GET'tir", () => {
    expect(budgetFor("/courses")).toBe("read");
    expect(budgetFor("/courses", { method: "GET" })).toBe("read");
    expect(budgetFor("/courses", { method: "get" })).toBe("read");
    expect(budgetFor("/courses", { method: "HEAD" })).toBe("read");
  });

  test("yazma: gövdeli POST/DELETE", () => {
    expect(budgetFor("/courses", { method: "POST", body: "{}" })).toBe("write");
    expect(budgetFor("/courses/c1/documents/d1", { method: "DELETE" })).toBe("write");
  });

  test("FormData gövde yüklemedir; 20 saniyelik yazma bütçesi dosyayı keserdi", () => {
    const form = new FormData();
    form.append("file", new Blob(["x"]), "a.pdf");
    expect(budgetFor("/courses/c1/documents", { method: "POST", body: form })).toBe(
      "upload",
    );
  });

  test("model çağıran üç uç `llm` bütçesi alır", () => {
    const post = { method: "POST", body: "{}" };
    expect(budgetFor("/courses/c1/chat", post)).toBe("llm");
    expect(budgetFor("/courses/c1/exams/e1/answers", post)).toBe("llm");
    expect(budgetFor("/courses/c1/questions/generate", post)).toBe("llm");
  });

  test("karşı kontrol: benzeyen ama modeli ÇAĞIRMAYAN uçlar `llm` değildir", () => {
    // Bu dört yol da "chat"/"exams"/"questions" içeriyor; ikisi ipucu ve
    // bitirme uçları ve backend'de model çağırmıyorlar (şablon metin + DB).
    // Hepsine 120 saniye vermek, ölü bir sunucuda ekranı iki dakika
    // "yükleniyor" bırakmak olurdu.
    expect(budgetFor("/courses/c1/chat/sessions")).toBe("read");
    expect(budgetFor("/courses/c1/chat/availability")).toBe("read");
    expect(budgetFor("/courses/c1/exams/e1/hint", { method: "POST", body: "{}" })).toBe(
      "write",
    );
    expect(budgetFor("/courses/c1/exams/e1/finish", { method: "POST" })).toBe("write");
    expect(
      budgetFor("/courses/c1/questions/q1/approve", { method: "POST" }),
    ).toBe("write");
  });

  test("bütçeler birbirinden gerçekten farklı ve artan sırada", () => {
    expect(BUDGET_MS.read).toBeLessThan(BUDGET_MS.write);
    expect(BUDGET_MS.write).toBeLessThan(BUDGET_MS.upload);
    expect(BUDGET_MS.upload).toBeLessThan(BUDGET_MS.llm);
    // Gerçek sağlayıcıyla sohbet 60 saniyeye çıkabiliyor (runbook).
    expect(BUDGET_MS.llm).toBeGreaterThan(60_000);
  });
});

/* -------------------------------------------------------------------------
 * T402 · Yeniden deneme sayısı ve geri çekilme
 * ---------------------------------------------------------------------- */

describe("yeniden deneme sayısı metottan gelir", () => {
  test("güvenli metotlar yeniden denenir", () => {
    expect(retriesFor(undefined)).toBe(2);
    expect(retriesFor({ method: "GET" })).toBe(2);
    expect(retriesFor({ method: "head" })).toBe(2);
  });

  test("veri değiştiren metotlar ASLA yeniden denenmez (FR-152)", () => {
    expect(retriesFor({ method: "POST" })).toBe(0);
    expect(retriesFor({ method: "PUT" })).toBe(0);
    expect(retriesFor({ method: "PATCH" })).toBe(0);
    expect(retriesFor({ method: "DELETE" })).toBe(0);
  });
});

describe("jitter'lı üstel geri çekilme", () => {
  test("aralık her turda ikiye katlanır", () => {
    expect(backoffMs(0, 0)).toBe(200);
    expect(backoffMs(1, 0)).toBe(400);
    expect(backoffMs(2, 0)).toBe(800);
  });

  test("jitter bekleyişi yarı aralıkta dağıtır", () => {
    expect(backoffMs(0, 0)).toBe(200);
    expect(backoffMs(0, 0.5)).toBe(300);
    expect(backoffMs(0, 1)).toBe(400);
  });

  test("bir turun en kısası, bir öncekinin en uzunu kadar", () => {
    // Sabit gecikme olsaydı bütün sekmeler aynı milisaniyede geri dönerdi;
    // burada aralıklar örtüşmüyor ama içleri rastgele.
    for (let attempt = 0; attempt < 4; attempt += 1) {
      expect(backoffMs(attempt + 1, 0)).toBe(backoffMs(attempt, 1));
      expect(backoffMs(attempt, 0)).toBeLessThan(backoffMs(attempt, 1));
    }
  });
});

/* -------------------------------------------------------------------------
 * T403 · Sınıflandırma çekirdeği
 * ---------------------------------------------------------------------- */

describe("hata sınıfı: durum + kod", () => {
  test("geçici: ağ, zaman aşımı, 408, 429, 5xx", () => {
    expect(classifyApiError(0, "timeout")).toBe("transient");
    expect(classifyApiError(408, "app_error")).toBe("transient");
    expect(classifyApiError(429, "app_error")).toBe("transient");
    expect(classifyApiError(500, "internal_error")).toBe("transient");
    expect(classifyApiError(502, "unknown")).toBe("transient");
    expect(classifyApiError(503, "unknown")).toBe("transient");
  });

  test("okunamayan başarılı yanıt geçicidir: bozuk olan hat, içerik değil", () => {
    expect(classifyApiError(200, "invalid_response")).toBe("transient");
  });

  test("kalıcı: 404, 409, 413, 422 ve 403 yetki reddi", () => {
    expect(classifyApiError(404, "not_found")).toBe("permanent");
    expect(classifyApiError(409, "conflict")).toBe("permanent");
    expect(classifyApiError(413, "payload_too_large")).toBe("permanent");
    expect(classifyApiError(422, "validation_error")).toBe("permanent");
    expect(classifyApiError(403, "permission_denied")).toBe("permanent");
  });

  test("`exam_in_progress` KİMLİK hatası değildir", () => {
    // Sınav kilidi 403 döner. Duruma bakan bir kural onu yetki hatası sayıp
    // sınav veren öğrenciyi sınavın ortasında giriş ekranına atardı.
    expect(classifyApiError(403, "exam_in_progress")).toBe("permanent");
    expect(classifyApiError(403, "exam_in_progress")).not.toBe("auth");
    // Ve yeniden denenebilir değil: sınav bitene kadar cevap değişmez.
    expect(classifyApiError(403, "exam_in_progress")).not.toBe("transient");
  });

  test("yalnız oturumun düşmesi `auth`tır", () => {
    expect(classifyApiError(401, "unauthenticated")).toBe("auth");
    // Karşı kontrol: üyesi olmadığın ders kimliğini geçersiz kılmaz.
    expect(classifyApiError(403, "permission_denied")).not.toBe("auth");
  });
});

/* -------------------------------------------------------------------------
 * T402 · Döngünün kendisi
 * ---------------------------------------------------------------------- */

/** Uyumayan `sleep`: beklenen süreleri kaydeder, testi bekletmez. */
function recordingSleep() {
  const delays: number[] = [];
  return {
    delays,
    sleep: async (ms: number) => {
      delays.push(ms);
    },
  };
}

/** Jitter'ı sabitler; testin ölçtüğü şey gecikme dizisi, rastgelelik değil. */
const noJitter = () => 0;

describe("yeniden deneme döngüsü", () => {
  test("geçici hata artan aralıklarla yeniden denenir ve sonunda başarılır", async () => {
    const { delays, sleep } = recordingSleep();
    let calls = 0;
    const result = await withRetry(
      async () => {
        calls += 1;
        if (calls < 3) throw new ApiError("geçici", "internal_error", 503, "r1");
        return "liste";
      },
      { retries: 2, sleep, random: noJitter },
    );

    expect(result).toBe("liste");
    expect(calls).toBe(3);
    expect(delays).toEqual([200, 400]);
  });

  test("bütçe bitince son hata yukarı çıkar", async () => {
    const { delays, sleep } = recordingSleep();
    let calls = 0;
    const promise = withRetry(
      async () => {
        calls += 1;
        throw new ApiError(`deneme ${calls}`, "internal_error", 503, "r1");
      },
      { retries: 2, sleep, random: noJitter },
    );

    await expect(promise).rejects.toThrow("deneme 3");
    expect(calls).toBe(3);
    expect(delays).toHaveLength(2);
  });

  test("POST yeniden DENENMEZ: çift cevap, çift soru, çift sınav satırı olurdu", async () => {
    const { delays, sleep } = recordingSleep();
    let calls = 0;
    const promise = withRetry(
      async () => {
        calls += 1;
        // Geçici hatanın ta kendisi; tek fark metodun güvenli olmaması.
        throw new ApiError("sunucu hatası", "internal_error", 500, "r1");
      },
      { retries: retriesFor({ method: "POST" }), sleep, random: noJitter },
    );

    await expect(promise).rejects.toThrow("sunucu hatası");
    expect(calls).toBe(1);
    expect(delays).toEqual([]);
  });

  test("kalıcı hata geçici olsaydı bile beklenmez: 404 tek denemede biter", async () => {
    const { delays, sleep } = recordingSleep();
    let calls = 0;
    const promise = withRetry(
      async () => {
        calls += 1;
        throw new ApiError("Ders bulunamadı.", "not_found", 404, "r1");
      },
      { retries: 2, sleep, random: noJitter },
    );

    await expect(promise).rejects.toThrow("Ders bulunamadı.");
    expect(calls).toBe(1);
    expect(delays).toEqual([]);
  });

  test("sınav kilidi yeniden denenmez", async () => {
    let calls = 0;
    const promise = withRetry(
      async () => {
        calls += 1;
        throw new ApiError("Şu anda süren bir sınav oturumun var.", "exam_in_progress", 403);
      },
      { retries: 2, sleep: async () => {}, random: noJitter },
    );

    await expect(promise).rejects.toThrow(ApiError);
    expect(calls).toBe(1);
  });

  test("oturum düşmesi yeniden denenmez", async () => {
    let calls = 0;
    const promise = withRetry(
      async () => {
        calls += 1;
        throw new ApiError("Oturum bulunamadı.", "unauthenticated", 401);
      },
      { retries: 2, sleep: async () => {}, random: noJitter },
    );

    await expect(promise).rejects.toThrow(ApiError);
    expect(calls).toBe(1);
  });

  test("ağ kopması (ApiError olmayan hata) yeniden denenir", async () => {
    const { delays, sleep } = recordingSleep();
    let calls = 0;
    const result = await withRetry(
      async () => {
        calls += 1;
        if (calls === 1) throw new TypeError("fetch failed");
        return "liste";
      },
      { retries: 2, sleep, random: noJitter },
    );

    expect(result).toBe("liste");
    expect(calls).toBe(2);
    expect(delays).toEqual([200]);
  });
});

/* -------------------------------------------------------------------------
 * T401 · Bütçenin gerçekten uygulanması
 * ---------------------------------------------------------------------- */

const realFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = realFetch;
  jest.useRealTimers();
});

/**
 * Yanıt vermeyen sunucu.
 *
 * `signal`i saklıyor ki testin sorabileceği asıl soru sorulabilsin: bekleme
 * bırakıldı mı, yoksa istek gerçekten iptal mi edildi? `Promise.race` ile
 * yazılmış bir bütçe bu testi geçemez — orada `aborted` hiç `true` olmaz ve
 * bağlantı arka planda açık kalır.
 */
function hangingFetch() {
  const state = { calls: 0, signals: [] as AbortSignal[] };
  globalThis.fetch = ((_url: string, init: RequestInit) => {
    state.calls += 1;
    const signal = init.signal as AbortSignal;
    state.signals.push(signal);
    return new Promise<Response>((_resolve, reject) => {
      signal.addEventListener("abort", () => {
        reject(new DOMException("The operation was aborted.", "AbortError"));
      });
    });
  }) as unknown as typeof fetch;
  return state;
}

/** Sahte zamanlayıcı ilerledikten sonra mikro görevlerin akmasına izin verir. */
async function flush(): Promise<void> {
  for (let i = 0; i < 5; i += 1) await Promise.resolve();
}

/**
 * Reddi KAYDEDER, beklemez.
 *
 * `await promise` yazmak burada tuzak: sahte zamanlayıcı açıkken Bun'un kendi
 * test zaman aşımı da sahte olur, yani hiç çözülmeyen bir sözü beklemek testi
 * kırmızıya değil ASILI kalmaya götürür. Asılı kalan bir test, bu dosyanın
 * kanıt olarak işe yaramaz hâli demek: bir mutasyonun testi gerçekten kırıp
 * kırmadığı görülemez.
 */
function captureRejection(promise: Promise<unknown>) {
  const box: { error?: unknown } = {};
  void promise.catch((e: unknown) => {
    box.error = e;
  });
  return box;
}

describe("süre bütçesi isteği gerçekten iptal eder", () => {
  test("yazma bütçesi dolunca istek iptal edilir ve zaman aşımı hatası döner", async () => {
    jest.useFakeTimers();
    const state = hangingFetch();

    const caught = captureRejection(api.delete("/courses/c1/documents/d1"));
    await flush();

    jest.advanceTimersByTime(BUDGET_MS.write - 1);
    await flush();
    expect(state.signals[0]?.aborted).toBe(false);

    jest.advanceTimersByTime(1);
    await flush();

    expect(state.signals[0]?.aborted).toBe(true);
    const error = caught.error as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe("timeout");
    // Sunucuya varılamadı: ne durum kodu ne de destek kodu var.
    expect(error.status).toBe(0);
    expect(error.requestId).toBeNull();
    // DELETE yeniden denenmez: tek istek gitti.
    expect(state.calls).toBe(1);
  });

  test("okuma bütçesi daha kısadır ve zaman aşımı yeniden denenir", async () => {
    jest.useFakeTimers();
    const state = hangingFetch();

    const caught = captureRejection(api.get("/courses"));
    await flush();

    // Yazma bütçesi dolmadan çok önce okuma bütçesi dolar.
    jest.advanceTimersByTime(BUDGET_MS.read);
    await flush();
    expect(state.signals[0]?.aborted).toBe(true);

    // Zaman aşımı geçici bir hatadır: geri çekilme sonrası ikinci deneme gider.
    jest.advanceTimersByTime(BUDGET_MS.read);
    await flush();
    expect(state.calls).toBeGreaterThan(1);

    // Üç denemenin üçü de bütçesini doldurunca hata yukarı çıkar.
    for (let i = 0; i < 4; i += 1) {
      jest.advanceTimersByTime(BUDGET_MS.read);
      await flush();
    }
    const error = caught.error as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe("timeout");
    expect(state.calls).toBe(1 + retriesFor({ method: "GET" }));
  });

  test("model uçları uzun bütçeyle çalışır: 12 saniyede kesilmez", async () => {
    jest.useFakeTimers();
    const state = hangingFetch();

    void api.post("/courses/c1/chat", { message: "merhaba" }).catch(() => {});
    await flush();

    // Sohbet cevabı gerçek sağlayıcıyla 60 saniyeye çıkabiliyor; okuma
    // bütçesiyle kesilseydi ürün burada kırılırdı.
    jest.advanceTimersByTime(BUDGET_MS.read);
    await flush();
    expect(state.signals[0]?.aborted).toBe(false);

    jest.advanceTimersByTime(BUDGET_MS.llm - BUDGET_MS.read);
    await flush();
    expect(state.signals[0]?.aborted).toBe(true);
  });
});
