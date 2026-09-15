"use client";

/**
 * Tekrar destesi: çevir, karar ver, ilerle.
 *
 * ## Üç giriş yolu, tek karar yolu
 *
 * Kaydırma, klavye ve düğmeler aynı `deckReducer` eylemlerini üretir. Kaydırma
 * TEK yol olamaz: dokunmatik olmayan cihaz, ekran okuyucu ve azaltılmış hareket
 * tercihi bunu imkânsız kılar (DESIGN.md §Responsive/Erişilebilirlik). Bu
 * yüzden düğmeler her zaman çizilir — kaydırmanın "keşfedilmesi gereken" bir
 * kısayol olması yeterli, zorunluluk olması kabul edilemez.
 *
 * ## Kaydırma neden bağlantıları bozmuyor
 *
 * Arka yüzde kaynak kartları var ve onlar birer bağlantı. Sürükleme yalnız
 * etkileşimli olmayan bir öğeden başlarsa dinlenir; bağlantı, düğme ya da girdi
 * üstünde başlayan basış hiç izlenmez. Ayrıca eşiğin (72px) altındaki hareket
 * karar saymaz, yani kaynak kartına yapılan normal bir tıklama kartı
 * ilerletmez.
 *
 * ## Odak nereye gidiyor
 *
 * Kart değişince odak yeni sorunun başlığına taşınır. Aksi hâlde klavye
 * kullanıcısı "Biliyordum" düğmesine basar, kart değişir ve odak hâlâ eski
 * düğmede kalır: ekran okuyucu yeni soruyu hiç okumaz.
 */

import { useCallback, useEffect, useReducer, useRef } from "react";
import {
  cardKeyAction,
  currentCard,
  deckProgress,
  deckReducer,
  deckSummary,
  initialDeck,
  isFinished,
  nativeSelectorFor,
  swipeVerdict,
  VERDICT_LABEL,
  type DeckAction,
  type ReviewCard,
} from "@/lib/cards";
import { CardFace } from "@/components/cards/card-face";
import { DeckSummary } from "@/components/cards/deck-summary";
import { Button, Card, EmptyState } from "@/components/ui";

/** Sürükleme yalnız boş alandan başlar; etkileşimli öğeler kendi işini yapar. */
const INTERACTIVE = "a, button, input, textarea, select, [role='button']";

export function CardDeck({
  courseId,
  sessionId,
  cards,
  onRestartSession,
}: {
  courseId: string;
  sessionId: string;
  cards: readonly ReviewCard[];
  /** Oturum seçicisine dönüş; özet ekranında gösterilir. */
  onRestartSession?: () => void;
}) {
  const [state, dispatch] = useReducer(deckReducer, cards, initialDeck);
  const headingRef = useRef<HTMLHeadingElement | null>(null);
  const dragStart = useRef<number | null>(null);
  const surfaceRef = useRef<HTMLDivElement | null>(null);
  const card = currentCard(state);
  const { position, total } = deckProgress(state);
  const finished = isFinished(state);

  /*
   * Deste dışarıdan değişince (başka oturum seçildi, "yalnız tekrar edilenler")
   * durum sıfırlanır. `cards` referansı sayfa tarafında `useMemo` ile sabit
   * tutuluyor; her render'da yeni dizi gelseydi bu efekt kararları silerdi.
   */
  useEffect(() => {
    dispatch({ kind: "restart", cards });
  }, [cards]);

  /*
   * Odak her durum değişiminde kartın başlığına döner ve bu YALNIZ ekran
   * okuyucu için değil: "Cevabı göster" düğmesi açılışta DOM'dan kalkıyor,
   * odak `body`'ye düşüyor ve kabuk artık tuş almadığı için klavye tamamen
   * ölüyordu (15 Eylül'de tarayıcıda ölçüldü). Başlık kabuğun İÇİNDE olduğu
   * için odak oraya dönünce tuşlar yeniden `onKeyDown`'a kabarıyor.
   */
  useEffect(() => {
    if (card !== null) headingRef.current?.focus();
  }, [card?.id, state.revealed]);

  const run = useCallback((action: DeckAction | null) => {
    if (action !== null) dispatch(action);
  }, []);

  function handleKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    // Tuşun yerel anlamı olan öğelerde karışma; ok ve Enter için liste farklı.
    if ((event.target as HTMLElement).closest(nativeSelectorFor(event.key))) return;
    const action = cardKeyAction(event.key, state.revealed);
    if (action === null) return;
    // Boşluk sayfayı kaydırırdı; eylemi biz karşıladık.
    event.preventDefault();
    dispatch(action);
  }

  function handlePointerDown(event: React.PointerEvent<HTMLDivElement>) {
    if ((event.target as HTMLElement).closest(INTERACTIVE)) return;
    dragStart.current = event.clientX;
  }

  function handlePointerUp(event: React.PointerEvent<HTMLDivElement>) {
    const start = dragStart.current;
    dragStart.current = null;
    if (start === null || !state.revealed) return;
    const verdict = swipeVerdict(event.clientX - start);
    if (verdict !== null) dispatch({ kind: "decide", verdict });
  }

  if (cards.length === 0) {
    return (
      <EmptyState title="Bu oturumda tekrar edilecek kart yok. Kartlar cevapladığın sorulardan kurulur; bir alıştırma sınavını tamamladıktan sonra buraya dön." />
    );
  }

  if (finished) {
    return (
      <DeckSummary
        summary={deckSummary(state)}
        onRestart={() => dispatch({ kind: "restart" })}
        onRestartMissed={(missed) => dispatch({ kind: "restart", cards: missed })}
        onChangeSession={onRestartSession}
      />
    );
  }

  if (card === null) return null;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm tabular-nums text-fg-muted">
          Kart {position} / {total}
        </p>
        <p className="text-sm text-fg-subtle">
          {state.revealed
            ? "Sağa kaydır ya da → : biliyordum · Sola kaydır ya da ← : tekrar"
            : "Boşluk ya da Enter: cevabı göster"}
        </p>
      </div>

      {/*
        `tabIndex={-1}` + `onKeyDown`: kabuk odak alabiliyor ki içerideki
        başlığa odaklanan kullanıcının tuşları buraya kabarsın. Rol verilmedi —
        bu bir liste kutusu ya da ızgara değil; yanlış rol ekran okuyucuya
        olmayan bir gezinme sözü verir.
        `touch-action: pan-y`: dikey kaydırma sayfanın, yatay hareket bizim.
      */}
      <div
        ref={surfaceRef}
        tabIndex={-1}
        onKeyDown={handleKeyDown}
        onPointerDown={handlePointerDown}
        onPointerUp={handlePointerUp}
        onPointerCancel={() => { dragStart.current = null; }}
        className="touch-pan-y select-none focus-visible:outline-none"
      >
        <Card className="min-w-0">
          <CardFace
            card={card}
            revealed={state.revealed}
            courseId={courseId}
            sessionId={sessionId}
            headingRef={headingRef}
          />
        </Card>
      </div>

      <div className="mt-5 flex flex-wrap gap-3">
        {state.revealed ? (
          <>
            <Button variant="secondary" onClick={() => run({ kind: "decide", verdict: "review" })}>
              ← {VERDICT_LABEL.review}
            </Button>
            <Button onClick={() => run({ kind: "decide", verdict: "knew" })}>
              {VERDICT_LABEL.knew} →
            </Button>
          </>
        ) : (
          <Button onClick={() => run({ kind: "reveal" })}>Cevabı göster</Button>
        )}
        {position > 1 && (
          <Button variant="ghost" onClick={() => run({ kind: "back" })}>
            Önceki kart
          </Button>
        )}
      </div>

      {/*
        Karar duyurusu: görsel olarak kart zaten değişti, ekran okuyucu için
        ne olduğunu söyleyen tek yer burası. `polite` — okumayı kesmez.
      */}
      <p aria-live="polite" className="sr-only">
        {state.revealed ? `${position}. kartın cevabı açıldı.` : `${position}. kart, ${total} karttan.`}
      </p>
    </div>
  );
}
