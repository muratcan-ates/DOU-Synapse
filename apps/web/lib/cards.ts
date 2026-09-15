/**
 * Hızlı tekrar destesinin saf çekirdeği: deste kurulumu, sıra ve karar durumu.
 *
 * ## Kartlar neden soru havuzundan değil, kendi bitmiş provandan kuruluyor
 *
 * İlk tasarım "onaylı soru havuzunu kart yap" diyordu. Uygulanamaz: öğrenciye
 * giden soru listesi cevap anahtarını **taşımıyor**. `app/schemas/assessment.py`
 * içindeki `public_payload()` beyaz listesi çoktan seçmeli için yalnız
 * `stem` + `options` döndürür; `answer_key`, `explanation`, `key_points` ve
 * `rubric` yalnız `_SOLUTION_KEYS` üzerinden, yalnız **sınav bittikten sonra**
 * açılır. Bu bir eksik değil, sınav bütünlüğü kararıdır: havuzdaki soru yarın
 * yayımlanacak sınavın sorusu olabilir.
 *
 * Bu yüzden deste, öğrencinin **kendi tamamladığı alıştırma oturumundan**
 * kurulur. Orada cevap anahtarını görmeye zaten hakkı var ve sunucu bu hakkı
 * `exams.py` üzerinden aktif sınav kilidiyle birlikte veriyor. Kart yeni bir
 * yetki açmaz; var olan sonuç ekranının başka bir sunumudur.
 *
 * ## Ön yüz ve arka yüz nereden geliyor
 *
 * - Ön yüz: `GET /courses/{id}/exams/{sid}` → `ExamSession.questions`
 *   (`public_payload`, yani cevapsız) → `describeQuestion` (`lib/exam.ts`).
 * - Arka yüz: `GET /courses/{id}/exams/{sid}/results` → `AnswerFeedback`
 *   (puan, "neden yanlış" kaynağı, çözüm) → `FeedbackPanel`.
 *
 * İkisi de `question_id` ile eşlenir. Eşleşmeyen soru desteye girmez:
 * cevaplanmamış soruda gösterilecek bir arka yüz yoktur.
 *
 * ## Kararlar nereye yazılıyor
 *
 * Hiçbir yere. "Biliyordum / Tekrar" kararı bu oturumun yerel durumunda yaşar
 * ve sayfadan çıkınca kaybolur. Kalıcı kayıt `learning_events` tablosuna
 * yazılırdı ama `event_type` üç yerde kısıtlı (`0027_learning_events.sql`
 * tablo CHECK'i, `app.record_learning_event` içindeki tür listesi ve tür başına
 * yapısal kurallar); yeni bir tür yeni bir göç ister ve göç numarası insan
 * kararına bağlı. Ölçülmeyen şeyi kaydediyormuş gibi yapmaktansa kaydetmiyoruz;
 * mastery de dokunulmadan kalır — o yalnız gerçek cevaptan güncellenir.
 */

import { describeQuestion, type QuestionView } from "@/lib/exam";
import type { AnswerFeedback, ExamSession } from "@/lib/types";

/**
 * Öğrencinin kart üstündeki öz değerlendirmesi. Puan değildir, kayıt değildir.
 *
 * Dışa açılmadı: bugün hiçbir tüketici bu adı yazmak zorunda değil — `DeckAction`
 * ve `VERDICT_LABEL` üzerinden yapısal olarak ulaşılıyor. İhtiyaç doğduğunda
 * export edilir; şimdiden açmak ölü yüzey olurdu.
 */
type CardVerdict = "knew" | "review";

export interface ReviewCard {
  /** `question_id`; deste anahtarı ve karar sözlüğünün anahtarı. */
  id: string;
  /** Ön yüz. `unsupported` olan sorular desteye hiç girmez. */
  view: QuestionView;
  /** Arka yüz: puan, kaynak, çözüm. */
  feedback: AnswerFeedback;
  /**
   * Sunucunun verdiği sonuç. `null` = puanlanamadı (abstention) ya da sınav
   * modunda henüz açılmadı. Öğrencinin kendi kararından AYRI tutulur: biri
   * ölçüm, diğeri his.
   */
  wasCorrect: boolean | null;
}

export interface DeckState {
  cards: readonly ReviewCard[];
  /** `cards.length`'e eşitse deste bitti. */
  index: number;
  /** Arka yüz açıldı mı. Karar vermek için açmak ZORUNLU (bkz. `cardKeyAction`). */
  revealed: boolean;
  decisions: Readonly<Record<string, CardVerdict>>;
}

export type DeckAction =
  | { kind: "reveal" }
  | { kind: "decide"; verdict: CardVerdict }
  | { kind: "back" }
  | { kind: "restart"; cards?: readonly ReviewCard[] };

/* -------------------------------------------------------------------------
 * Deste kurulumu
 * ---------------------------------------------------------------------- */

/**
 * Sıra: önce yanlışlar, sonra puanlanamayanlar, en sonda doğrular.
 *
 * Gerekçe: deste yarıda bırakılırsa bırakılan kısım zaten bilinen kısım olsun.
 * Grup içi sıra korunur (kararlı sıralama) — sınavdaki soru sırası anlam taşır.
 */
function reviewRank(card: ReviewCard): number {
  if (card.wasCorrect === false) return 0;
  if (card.wasCorrect === null) return 1;
  return 2;
}

export function orderForReview(cards: readonly ReviewCard[]): ReviewCard[] {
  return cards
    .map((card, position) => ({ card, position }))
    .sort((left, right) => reviewRank(left.card) - reviewRank(right.card) || left.position - right.position)
    .map((entry) => entry.card);
}

/**
 * Oturumun sorularını kendi geri bildirimleriyle eşler.
 *
 * Desteye girmeyenler ve nedenleri:
 *   - geri bildirimi olmayan soru → cevaplanmamış, arka yüzü yok;
 *   - `describeQuestion` `unsupported` dönen soru → ön yüzü çizilemiyor
 *     (sunucu ileride yeni bir soru tipi ekleyebilir; ekran çökmemeli).
 */
export function buildDeck(
  session: Pick<ExamSession, "questions">,
  results: readonly AnswerFeedback[],
): ReviewCard[] {
  const byQuestion = new Map(results.map((feedback) => [feedback.question_id, feedback]));
  const cards: ReviewCard[] = [];
  for (const question of session.questions ?? []) {
    const feedback = byQuestion.get(question.id);
    if (!feedback) continue;
    const view = describeQuestion(question);
    if (view.kind === "unsupported") continue;
    cards.push({
      id: question.id,
      view,
      feedback,
      wasCorrect: feedback.is_correct ?? null,
    });
  }
  return orderForReview(cards);
}

export function initialDeck(cards: readonly ReviewCard[]): DeckState {
  return { cards, index: 0, revealed: false, decisions: {} };
}

/* -------------------------------------------------------------------------
 * Durum geçişleri
 * ---------------------------------------------------------------------- */

export function deckReducer(state: DeckState, action: DeckAction): DeckState {
  switch (action.kind) {
    case "reveal":
      return state.revealed || isFinished(state) ? state : { ...state, revealed: true };

    case "decide": {
      const card = currentCard(state);
      // Arka yüz açılmadan karar yok: kartın değeri "neden yanlış" pasajını
      // okutmasında; açmadan geçmek tekrarı bir tıklama sayacına indirirdi.
      if (card === null || !state.revealed) return state;
      return {
        ...state,
        index: state.index + 1,
        revealed: false,
        decisions: { ...state.decisions, [card.id]: action.verdict },
      };
    }

    case "back": {
      if (state.index === 0) return state;
      // Geri dönüşte arka yüz açık gelir: kullanıcı zaten görmüştü, yeniden
      // "çevir" demek zorunda kalması gereksiz bir adım. Karar korunur;
      // yeni bir karar eskisinin üstüne yazar.
      return { ...state, index: state.index - 1, revealed: true };
    }

    case "restart":
      return initialDeck(action.cards ?? state.cards);
  }
}

export function currentCard(state: DeckState): ReviewCard | null {
  return state.cards[state.index] ?? null;
}

export function isFinished(state: DeckState): boolean {
  return state.cards.length > 0 && state.index >= state.cards.length;
}

/** 1 tabanlı konum; boş destede `total` 0 olur ve ekran boş durumu çizer. */
export function deckProgress(state: DeckState): { position: number; total: number } {
  return {
    position: Math.min(state.index + 1, state.cards.length),
    total: state.cards.length,
  };
}

/* -------------------------------------------------------------------------
 * Özet
 * ---------------------------------------------------------------------- */

export interface DeckSummary {
  total: number;
  knew: number;
  review: number;
  /** "Tekrar" işaretlenen kartlar; yeniden deste kurmak için. */
  reviewCards: ReviewCard[];
  /**
   * Öğrencinin "biliyordum" dediği ama sunucunun yanlış saydığı kartlar.
   * Tekrarın en değerli çıktısı bu: bilmediğini bilmemek.
   */
  overconfident: ReviewCard[];
}

export function deckSummary(state: DeckState): DeckSummary {
  const decided = state.cards.filter((card) => state.decisions[card.id] !== undefined);
  const reviewCards = decided.filter((card) => state.decisions[card.id] === "review");
  const knewCards = decided.filter((card) => state.decisions[card.id] === "knew");
  return {
    total: decided.length,
    knew: knewCards.length,
    review: reviewCards.length,
    reviewCards,
    overconfident: knewCards.filter((card) => card.wasCorrect === false),
  };
}

/* -------------------------------------------------------------------------
 * Klavye
 * ---------------------------------------------------------------------- */

/**
 * Tuş → eylem. Kaydırma tek giriş yolu olamaz (DESIGN.md erişilebilirlik).
 *
 * Arka yüz kapalıyken ok tuşları da "çevir"e düşer: kullanıcı ok tuşuna
 * basmışsa ilerlemek istiyordur ve doğru ilerleme adımı önce cevabı görmektir.
 * Böylece hangi tuşa basarsa bassın bir sonraki anlamlı adıma gider.
 */
export function cardKeyAction(key: string, revealed: boolean): DeckAction | null {
  if (!revealed) {
    return key === "Enter" || key === " " || key === "ArrowRight" || key === "ArrowLeft"
      ? { kind: "reveal" }
      : null;
  }
  if (key === "ArrowRight") return { kind: "decide", verdict: "knew" };
  if (key === "ArrowLeft") return { kind: "decide", verdict: "review" };
  return null;
}

/**
 * Tuşun hangi öğelerde bize AİT OLMADIĞINI söyleyen seçici.
 *
 * İki ayrı liste, çünkü iki tuş ailesinin yerel anlamı farklı:
 *   - Ok tuşları yalnız metin girdisi ve açılır listede yerel anlam taşır.
 *     Düğme ve bağlantı okları KULLANMAZ; onları da engellemek, klavyeyle
 *     "Biliyordum" düğmesine gelen kullanıcının sağ oka basınca hiçbir şey
 *     olmadığını görmesi demekti (15 Eylül'de tarayıcıda ölçüldü).
 *   - Enter ve boşluk ise düğmeyi, bağlantıyı ve onay kutusunu zaten çalıştırır;
 *     orada bizim de çevirmemiz tek basışta iki iş yapardı.
 */
const ARROW_NATIVE = "input, textarea, select, [contenteditable='true']";
const ACTIVATION_NATIVE = "a, button, input, textarea, select, [contenteditable='true'], [role='button']";

export function nativeSelectorFor(key: string): string {
  return key === "ArrowLeft" || key === "ArrowRight" ? ARROW_NATIVE : ACTIVATION_NATIVE;
}

/** Kaydırma eşiği (piksel). Altındaki hareket kaydırma sayılmaz, tıklama sayılır. */
const SWIPE_THRESHOLD = 72;

/** Yatay sürükleme mesafesi → karar. Eşiğin altında karar yok. */
export function swipeVerdict(deltaX: number, threshold = SWIPE_THRESHOLD): CardVerdict | null {
  if (deltaX >= threshold) return "knew";
  if (deltaX <= -threshold) return "review";
  return null;
}

export const VERDICT_LABEL: Record<CardVerdict, string> = {
  knew: "Biliyordum",
  review: "Tekrar etmeliyim",
};
