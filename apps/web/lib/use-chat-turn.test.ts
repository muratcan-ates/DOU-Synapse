/**
 * Sohbet gönderim turunun sessiz kuralları.
 *
 * Kanca React'e bağlı; karar çekirdeği `createChatTurn` saf çıkarıldı ve
 * testler onu sınıyor (desen `use-submit.test.ts` ile aynı). Çivilenenler:
 * istek gövdesinin Sokratik devam kuralı (soru açılış sorusunda kalır),
 * iyimser `pending`'in yaşam döngüsü, hatada taslağın iadesi, zarf
 * doğrulaması ve epoch geçersizlemesinin "geç yanıt hiçbir şey yazamaz"
 * sözü. Hepsinin bozulması sessizdir: ekran çalışır görünür, yalnız yanlış
 * gövdeyi gönderir ya da yanlış oturuma yazar.
 */

import { describe, expect, test } from "bun:test";

import { ApiError } from "./api";
import type { ChatAnswer, ChatRequest } from "./types";
import {
  createChatTurn,
  type ChatTurnContext,
} from "./use-chat-turn";

const ANSWER: ChatAnswer = {
  session_id: "session-1",
  message_id: "message-1",
  status: "answered",
  mode: "qa",
  answer: "Cevap.",
  citations: [],
  hints: [],
  socratic_stage: null,
  cached: false,
  audience: "student",
  agent_profile: "student_coach",
};

const QA_CONTEXT: ChatTurnContext = {
  mode: "qa",
  sessionId: null,
  openingQuestion: null,
};

/** Elle çözülen söz: turun bitişini testin kontrolüne verir. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  promise.catch(() => {});
  return { promise, resolve, reject };
}

function harness(options?: {
  matchesIdentity?: (answer: ChatAnswer) => boolean;
  post?: (body: ChatRequest) => Promise<ChatAnswer>;
  onErrorHandled?: (error: unknown, context: ChatTurnContext) => boolean;
}) {
  const log: string[] = [];
  const bodies: ChatRequest[] = [];
  const accepted: Array<{ answer: ChatAnswer; text: string; context: ChatTurnContext }> =
    [];
  let draft = "";
  let post = options?.post ?? (() => Promise.resolve(ANSWER));

  const turn = createChatTurn<ChatTurnContext>({
    readDraft: () => draft,
    setDraft: (text) => {
      draft = text;
      log.push(`draft:${JSON.stringify(text)}`);
    },
    setPending: (text) =>
      log.push(text === null ? "pending:null" : `pending:${JSON.stringify(text)}`),
    setSending: (sending) => log.push(`sending:${sending}`),
    setSendError: (error) =>
      log.push(error === null ? "error:null" : `error:${error.message}`),
    post: (body) => {
      bodies.push(body);
      return post(body);
    },
    matchesIdentity: options?.matchesIdentity ?? (() => true),
    onErrorHandled: options?.onErrorHandled,
    onAnswer: (answer, text, context) => {
      accepted.push({ answer, text, context });
      log.push(`answer:${answer.message_id}`);
    },
  });

  return {
    turn,
    log,
    bodies,
    accepted,
    /** Kullanıcının yazması: kancada da aynı `setDraft` üzerinden akar. */
    type: (text: string) => {
      draft = text;
    },
    readDraft: () => draft,
    setPost: (next: (body: ChatRequest) => Promise<ChatAnswer>) => {
      post = next;
    },
  };
}

describe("createChatTurn — gövde ve sıra", () => {
  test("QA turu: gövde yalnız soru+mod taşır; sıra busy → temizlik → iyimser döküm", async () => {
    const state = harness();
    state.type("Bellek nedir?");

    await state.turn.submit(QA_CONTEXT);

    expect(state.bodies).toEqual([{ question: "Bellek nedir?", mode: "qa" }]);
    expect(state.log).toEqual([
      "sending:true",
      "error:null",
      'pending:"Bellek nedir?"',
      'draft:""',
      "answer:message-1",
      "pending:null",
      "sending:false",
    ]);
    expect(state.accepted[0]?.text).toBe("Bellek nedir?");
    expect(state.accepted[0]?.context).toBe(QA_CONTEXT);
  });

  test("Sokratik devam turu: soru açılış sorusunda kalır, kısa deneme student_attempt olur", async () => {
    const state = harness();
    state.type("hı");

    await state.turn.submit({
      mode: "socratic",
      sessionId: "session-1",
      openingQuestion: "İşlemci nasıl toplama yapar?",
    });

    // Deneme 3 karakterin altında ama devam turunda geçerlidir (canSubmitDraft).
    expect(state.bodies).toEqual([
      {
        question: "İşlemci nasıl toplama yapar?",
        mode: "socratic",
        session_id: "session-1",
        student_attempt: "hı",
      },
    ]);
  });

  test("gönderilemeyen taslak kapıya girmez: hiçbir state yazılmaz, POST çıkmaz", async () => {
    const state = harness();

    state.type("   ");
    await state.turn.submit(QA_CONTEXT);
    state.type("ab"); // alt sınırın altında ve devam turu değil
    await state.turn.submit(QA_CONTEXT);

    expect(state.bodies).toEqual([]);
    // Ekrandaki hata satırı da silinmez: kapıya girse `clearError` silerdi.
    expect(state.log).toEqual([]);
  });

  test("aynı tick'te ikinci gönderim yok sayılır — tek POST", async () => {
    const request = deferred<ChatAnswer>();
    const state = harness({ post: () => request.promise });
    state.type("Bellek nedir?");

    const first = state.turn.submit(QA_CONTEXT);
    const second = state.turn.submit(QA_CONTEXT);
    await second;

    expect(state.bodies).toHaveLength(1);

    request.resolve(ANSWER);
    await first;
    expect(state.accepted).toHaveLength(1);
  });
});

describe("createChatTurn — hata yolu", () => {
  test("sunucu hatası: döküm geri alınır, metin girdiye iade edilir, cümle sunucudan", async () => {
    const failure = new ApiError("Sunucu cümlesi.", "rate_limited", 429, "req-1");
    const state = harness({ post: () => Promise.reject(failure) });
    state.type("Bellek nedir?");

    await state.turn.submit(QA_CONTEXT);

    expect(state.log).toEqual([
      "sending:true",
      "error:null",
      'pending:"Bellek nedir?"',
      'draft:""',
      "pending:null",
      'draft:"Bellek nedir?"',
      "error:Sunucu cümlesi.",
      "sending:false",
    ]);
    expect(state.readDraft()).toBe("Bellek nedir?");
    expect(state.accepted).toEqual([]);
  });

  test("zarf uyuşmazlığı tur hatasıdır: cevap dökülmez, yedek cümle çıkar", async () => {
    const state = harness({ matchesIdentity: () => false });
    state.type("Bellek nedir?");

    await state.turn.submit(QA_CONTEXT);

    expect(state.accepted).toEqual([]);
    // Fırlatılan Error `ApiError` değil: ekrana `describeError` yedeği çıkar.
    expect(state.log).toContain("error:Bağlantı kurulamadı.");
    expect(state.readDraft()).toBe("Bellek nedir?");
  });
});

describe("createChatTurn — epoch geçersizlemesi", () => {
  test("invalidate turun izlerini siler; geç gelen BAŞARI hiçbir şey yazamaz", async () => {
    const request = deferred<ChatAnswer>();
    const state = harness({ post: () => request.promise });
    state.type("Bellek nedir?");

    const inFlight = state.turn.submit(QA_CONTEXT);
    state.turn.invalidate();
    const afterInvalidate = [...state.log];

    request.resolve(ANSWER);
    await inFlight;

    expect(afterInvalidate.slice(-3)).toEqual([
      "pending:null",
      "sending:false",
      "error:null",
    ]);
    // Geç yanıt: ne döküm, ne busy, ne hata — log kımıldamadı.
    expect(state.log).toEqual(afterInvalidate);
    expect(state.accepted).toEqual([]);
  });

  test("geç gelen HATA da taslağı geri getirmez: geçersizlenen turun iadesi yoktur", async () => {
    const request = deferred<ChatAnswer>();
    const state = harness({ post: () => request.promise });
    state.type("Bellek nedir?");

    const inFlight = state.turn.submit(QA_CONTEXT);
    state.turn.invalidate();

    request.reject(new ApiError("Sunucu cümlesi.", "rate_limited", 429, "req-1"));
    await inFlight;

    expect(state.readDraft()).toBe(""); // tur başında temizlenmişti, öyle kalır
    expect(state.log).not.toContain("error:Sunucu cümlesi.");
  });

  test("invalidate kapıyı da yeniler: eski tur uçuştayken yeni tur gönderilebilir", async () => {
    const first = deferred<ChatAnswer>();
    const state = harness({ post: () => first.promise });
    state.type("İlk soru?");

    const staleTurn = state.turn.submit(QA_CONTEXT);
    state.turn.invalidate();

    state.setPost(() => Promise.resolve(ANSWER));
    state.type("İkinci soru?");
    await state.turn.submit(QA_CONTEXT);

    expect(state.bodies).toHaveLength(2);
    expect(state.accepted.map((entry) => entry.text)).toEqual(["İkinci soru?"]);

    first.resolve(ANSWER);
    await staleTurn;
    expect(state.accepted).toHaveLength(1); // geç yanıt yine de dökülmedi
  });
});


describe("createChatTurn — bileşen kapanışı", () => {
  test("cancel ayrılmış bileşene yazmaz; geç başarı kalıcılaştırma çağrısını çalıştıramaz", async () => {
    const request = deferred<ChatAnswer>();
    const state = harness({ post: () => request.promise });
    state.type("Özel öğrenci sorusu");
    const flight = state.turn.submit(QA_CONTEXT);
    const before = [...state.log];
    state.turn.cancel();
    expect(state.log).toEqual(before);
    request.resolve(ANSWER); await flight;
    expect(state.log).toEqual(before);
    expect(state.accepted).toEqual([]);
  });
  test("cancel sonrası geç hata öğrenci taslağını geri yükleyemez; tekrar kurulumda yeni tur çalışır", async () => {
    const request = deferred<ChatAnswer>();
    const state = harness({ post: () => request.promise });
    state.type("Eski öğrenci taslağı");
    const flight = state.turn.submit(QA_CONTEXT); state.turn.cancel();
    state.setPost(() => Promise.resolve(ANSWER)); state.type("Yeni tur");
    await state.turn.submit(QA_CONTEXT);
    const before = [...state.log];
    request.reject(new Error("geç hata")); await flight;
    expect(state.log).toEqual(before);
    expect(state.readDraft()).toBe("");
    expect(state.accepted.map((item) => item.text)).toEqual(["Yeni tur"]);
  });
});


describe("silme/üyelik hatası kurtarması eski turun dışına çıkamaz", () => {
  test("güncel 409 kapatılırken gönderilen özel metin taslağa iade edilmez", async () => {
    const failure = new ApiError("Geçmiş değişti.", "chat_history_changed", 409, "request-synthetic");
    const recovered: unknown[] = [];
    const state = harness({ post: async () => { throw failure; }, onErrorHandled: (error, context) => {
      recovered.push([error, context]); state.turn.invalidate(); return true;
    } });
    state.type("Silinen konuşmanın özel sorusu?");
    await state.turn.submit(QA_CONTEXT);
    expect(recovered).toEqual([[failure, QA_CONTEXT]]);
    expect(state.readDraft()).toBe("");
    expect(state.log).not.toContain('draft:"Silinen konuşmanın özel sorusu?"');
    expect(state.accepted).toEqual([]);
  });
  test("geç 409 yeni oturumu kapatamaz ve kurtarma callback'ini çalıştıramaz", async () => {
    const request = deferred<ChatAnswer>(); let recovered = 0;
    const state = harness({ post: () => request.promise, onErrorHandled: () => { recovered += 1; return true; } });
    state.type("Eski konuşma sorusu?"); const old = state.turn.submit(QA_CONTEXT);
    state.turn.invalidate(); state.type("Yeni oturumun taslağı");
    request.reject(new ApiError("Geçmiş değişti.", "chat_history_changed", 409, "request-old"));
    await old;
    expect(recovered).toBe(0); expect(state.readDraft()).toBe("Yeni oturumun taslağı");
  });
});
