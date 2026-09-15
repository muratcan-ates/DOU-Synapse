import { expect, test } from "bun:test";
import {
  buildDeck,
  cardKeyAction,
  currentCard,
  deckProgress,
  deckReducer,
  deckSummary,
  initialDeck,
  isFinished,
  nativeSelectorFor,
  orderForReview,
  swipeVerdict,
  type DeckState,
  type ReviewCard,
} from "@/lib/cards";
import type { AnswerFeedback, ExamQuestion, ExamSession } from "@/lib/types";

function mcq(id: string, stem = "Kilitlenme için gerekli dört koşul nedir?"): ExamQuestion {
  return {
    id,
    type: "mcq",
    payload: {
      stem,
      options: [
        { key: "A", text: "Karşılıklı dışlama, elde tut-bekle, kesintisizlik, dairesel bekleme" },
        { key: "B", text: "Yalnız karşılıklı dışlama" },
      ],
    },
    answered: true,
  };
}

function feedback(questionId: string, isCorrect: boolean | null, graded = true): AnswerFeedback {
  return {
    question_id: questionId,
    graded,
    is_correct: isCorrect,
    score: isCorrect === null ? null : isCorrect ? 100 : 0,
  };
}

function session(questions: ExamQuestion[]): Pick<ExamSession, "questions"> {
  return { questions };
}

function deckOf(...cards: ReviewCard[]): DeckState {
  return initialDeck(cards);
}

function card(id: string, wasCorrect: boolean | null): ReviewCard {
  const built = buildDeck(session([mcq(id)]), [feedback(id, wasCorrect)]);
  return built[0]!;
}

/* ---------------------------------------------------------------- deste */

test("deste yalnız cevaplanmış soruları alır", () => {
  const cards = buildDeck(session([mcq("q1"), mcq("q2")]), [feedback("q1", true)]);

  expect(cards.map((entry) => entry.id)).toEqual(["q1"]);
});

test("ön yüzü çizilemeyen soru desteye girmez", () => {
  // Şıksız çoktan seçmeli: `describeQuestion` bunu `unsupported` sayar.
  const bozuk: ExamQuestion = { id: "q1", type: "mcq", payload: { stem: "Soru" }, answered: true };

  const cards = buildDeck(session([bozuk, mcq("q2")]), [feedback("q1", false), feedback("q2", true)]);

  expect(cards.map((entry) => entry.id)).toEqual(["q2"]);
});

test("sıra önce yanlışlar, sonra puanlanamayanlar, en sonda doğrular", () => {
  const cards = buildDeck(session([mcq("dogru"), mcq("puansiz"), mcq("yanlis")]), [
    feedback("dogru", true),
    feedback("puansiz", null, false),
    feedback("yanlis", false),
  ]);

  expect(cards.map((entry) => entry.id)).toEqual(["yanlis", "puansiz", "dogru"]);
});

test("aynı gruptaki kartlar sınavdaki sırasını korur", () => {
  const cards = orderForReview([card("a", false), card("b", false), card("c", false)]);

  expect(cards.map((entry) => entry.id)).toEqual(["a", "b", "c"]);
});

test("sunucunun sonucu öğrencinin kararından ayrı tutulur", () => {
  const [ilk] = buildDeck(session([mcq("q1")]), [feedback("q1", false)]);

  expect(ilk!.wasCorrect).toBe(false);
  expect(initialDeck([ilk!]).decisions).toEqual({});
});

/* -------------------------------------------------------------- geçişler */

test("arka yüz açılmadan karar verilemez", () => {
  const state = deckOf(card("q1", false));

  const sonra = deckReducer(state, { kind: "decide", verdict: "knew" });

  expect(sonra).toBe(state);
  expect(sonra.index).toBe(0);
  expect(sonra.decisions).toEqual({});
});

test("çevir sonra karar: kart ilerler ve karar yazılır", () => {
  let state = deckOf(card("q1", false), card("q2", true));

  state = deckReducer(state, { kind: "reveal" });
  expect(state.revealed).toBe(true);
  state = deckReducer(state, { kind: "decide", verdict: "review" });

  expect(state.decisions).toEqual({ q1: "review" });
  expect(state.index).toBe(1);
  expect(state.revealed).toBe(false);
  expect(currentCard(state)?.id).toBe("q2");
});

test("geri dönüşte arka yüz açık gelir ve karar üstüne yazılabilir", () => {
  let state = deckOf(card("q1", false), card("q2", true));
  state = deckReducer(state, { kind: "reveal" });
  state = deckReducer(state, { kind: "decide", verdict: "knew" });

  state = deckReducer(state, { kind: "back" });
  expect(state.index).toBe(0);
  expect(state.revealed).toBe(true);
  expect(state.decisions).toEqual({ q1: "knew" });

  state = deckReducer(state, { kind: "decide", verdict: "review" });
  expect(state.decisions).toEqual({ q1: "review" });
});

test("ilk karttan geriye gidilmez", () => {
  const state = deckOf(card("q1", false));

  expect(deckReducer(state, { kind: "back" })).toBe(state);
});

test("son karardan sonra deste biter", () => {
  let state = deckOf(card("q1", false));
  state = deckReducer(state, { kind: "reveal" });
  state = deckReducer(state, { kind: "decide", verdict: "knew" });

  expect(isFinished(state)).toBe(true);
  expect(currentCard(state)).toBeNull();
  // Biten destede çevirmek bir şey yapmaz; ekran özet çiziyor.
  expect(deckReducer(state, { kind: "reveal" })).toBe(state);
});

test("boş deste bitmiş sayılmaz — ekran boş durumu çizer", () => {
  const state = deckOf();

  expect(isFinished(state)).toBe(false);
  expect(deckProgress(state)).toEqual({ position: 0, total: 0 });
});

test("ilerleme 1 tabanlıdır ve toplamı aşmaz", () => {
  let state = deckOf(card("q1", false), card("q2", true));
  expect(deckProgress(state)).toEqual({ position: 1, total: 2 });

  state = deckReducer(state, { kind: "reveal" });
  state = deckReducer(state, { kind: "decide", verdict: "knew" });
  state = deckReducer(state, { kind: "reveal" });
  state = deckReducer(state, { kind: "decide", verdict: "knew" });

  expect(deckProgress(state)).toEqual({ position: 2, total: 2 });
});

test("yeniden başlatmak kararları siler", () => {
  let state = deckOf(card("q1", false));
  state = deckReducer(state, { kind: "reveal" });
  state = deckReducer(state, { kind: "decide", verdict: "review" });

  state = deckReducer(state, { kind: "restart" });

  expect(state).toEqual(initialDeck(state.cards));
});

test("yalnız tekrar kartlarıyla yeniden başlanabilir", () => {
  const [yanlis, dogru] = [card("q1", false), card("q2", true)];
  let state = deckOf(yanlis, dogru);
  state = deckReducer(state, { kind: "reveal" });
  state = deckReducer(state, { kind: "decide", verdict: "review" });
  state = deckReducer(state, { kind: "reveal" });
  state = deckReducer(state, { kind: "decide", verdict: "knew" });

  const yeniden = deckReducer(state, { kind: "restart", cards: deckSummary(state).reviewCards });

  expect(yeniden.cards.map((entry) => entry.id)).toEqual(["q1"]);
  expect(yeniden.index).toBe(0);
});

/* ------------------------------------------------------------------ özet */

test("özet yalnız karar verilen kartları sayar", () => {
  let state = deckOf(card("q1", false), card("q2", true), card("q3", true));
  state = deckReducer(state, { kind: "reveal" });
  state = deckReducer(state, { kind: "decide", verdict: "review" });

  const ozet = deckSummary(state);

  expect(ozet).toMatchObject({ total: 1, knew: 0, review: 1 });
  expect(ozet.reviewCards.map((entry) => entry.id)).toEqual(["q1"]);
});

test("bildiğini sandığı ama yanlış yaptığı kartlar ayrı sayılır", () => {
  let state = deckOf(card("yanlis", false), card("dogru", true));
  state = deckReducer(state, { kind: "reveal" });
  state = deckReducer(state, { kind: "decide", verdict: "knew" });
  state = deckReducer(state, { kind: "reveal" });
  state = deckReducer(state, { kind: "decide", verdict: "knew" });

  const ozet = deckSummary(state);

  expect(ozet.knew).toBe(2);
  expect(ozet.overconfident.map((entry) => entry.id)).toEqual(["yanlis"]);
});

/* --------------------------------------------------------------- klavye */

test("arka yüz kapalıyken her ilerleme tuşu önce cevabı açar", () => {
  for (const key of ["Enter", " ", "ArrowRight", "ArrowLeft"]) {
    expect(cardKeyAction(key, false)).toEqual({ kind: "reveal" });
  }
});

test("arka yüz açıkken oklar karar verir", () => {
  expect(cardKeyAction("ArrowRight", true)).toEqual({ kind: "decide", verdict: "knew" });
  expect(cardKeyAction("ArrowLeft", true)).toEqual({ kind: "decide", verdict: "review" });
});

test("ilgisiz tuş eylem üretmez", () => {
  expect(cardKeyAction("Tab", false)).toBeNull();
  expect(cardKeyAction("Tab", true)).toBeNull();
  // Açıkken Enter karar VERMEZ: hangi karar olduğu belirsiz olurdu.
  expect(cardKeyAction("Enter", true)).toBeNull();
});

/* ------------------------------------------------------------- kaydırma */

test("eşiği geçmeyen sürükleme karar sayılmaz", () => {
  expect(swipeVerdict(0)).toBeNull();
  expect(swipeVerdict(71)).toBeNull();
  expect(swipeVerdict(-71)).toBeNull();
});

test("sağa kaydırma biliyordum, sola kaydırma tekrar", () => {
  expect(swipeVerdict(72)).toBe("knew");
  expect(swipeVerdict(-72)).toBe("review");
});

test("klavye ve kaydırma aynı kararı üretir", () => {
  const kaydirma = swipeVerdict(120);
  const klavye = cardKeyAction("ArrowRight", true);

  expect(klavye).toEqual({ kind: "decide", verdict: kaydirma! });
});

function parcalar(selector: string): string[] {
  return selector.split(",").map((part) => part.trim());
}

test("oklar düğme ve bağlantıda engellenmez, yalnız girdi ve açılır listede", () => {
  // Düğme oku KULLANMAZ: klavyeyle "Biliyordum"a gelen kullanıcı sağ oka
  // basınca kart ilerlemeli (15 Eylül'de tarayıcıda bu kusur ölçüldü).
  const oklar = parcalar(nativeSelectorFor("ArrowRight"));

  expect(oklar).not.toContain("button");
  expect(oklar).not.toContain("a");
  expect(oklar).not.toContain("[role='button']");
  expect(oklar).toEqual(["input", "textarea", "select", "[contenteditable='true']"]);
  expect(nativeSelectorFor("ArrowLeft")).toBe(nativeSelectorFor("ArrowRight"));
});

test("Enter ve boşluk düğme ile bağlantıda engellenir", () => {
  // Orada tuş öğeyi zaten çalıştırır; bir de kartı çevirmek tek basışta iki iş olurdu.
  for (const key of ["Enter", " "]) {
    const parts = parcalar(nativeSelectorFor(key));
    expect(parts).toContain("button");
    expect(parts).toContain("a");
    expect(parts).toContain("[role='button']");
  }
});
