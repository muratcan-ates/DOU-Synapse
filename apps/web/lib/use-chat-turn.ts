"use client";

/**
 * Sohbet gönderim turu — `useSubmit`'in çekirdeği (`createSubmitGate`) üstünde,
 * sohbetin kendine özgü akışıyla.
 *
 * PR 5'te 22 gönderim kopyası `useSubmit`'e inerken chat'in iki kopyası
 * (tam ekran + çekmece) bilinçli dışarıda bırakılmıştı, çünkü akışları düz bir
 * "busy/hata" kalıbından üç yerde ayrılıyor:
 *
 * 1. **İyimser döküm:** gönderilen metin sunucu onaylamadan `pending` olarak
 *    dökümde yer tutar; hatada geri alınır ve METİN GİRDİYE İADE EDİLİR —
 *    yazdığını kaybetmek hatanın cezası olmamalı.
 * 2. **Epoch geçersizlemesi:** oturum/mod değiştiren her eylem uçuştaki turu
 *    geçersizler. Geç dönen yanıt ne dökümü ne hatayı yazar; `busy` bayrağını
 *    da geçersizleyen taraf düşürür, geç yanıtın bitişi onu ellemez. Kapı da
 *    epoch'la birlikte YENİLENİR: geçersizlenen turun hâlâ uçuşta olması yeni
 *    gönderimi engellemez (taşınan ekranların ölçülen davranışı).
 * 3. **Zarf doğrulaması:** cevabın rol zarfı mevcut kimlikle eşleşmezse tur
 *    hata sayılır (istemci cevap ortasında persona değiştirmez).
 *
 * `createSubmitGate` yine de çekirdek: tek-uçuş kapısı ve busy/hata sırası
 * oradan gelir; aynı tick'te iki kez Enter'a basmak artık iki POST üretmez
 * (eski state tabanlı `if (sending)` kapısı bunu geçirirdi — `use-submit.ts`
 * girişindeki ölçüm). Karar çekirdeği `createChatTurn` saf tutulur ki DOM'suz
 * koşan `use-chat-turn.test.ts` sırayı, kapıyı ve epoch kurallarını doğrudan
 * sınayabilsin.
 */

import { useCallback, useRef, useState } from "react";
import {
  buildChatRequest,
  canSubmitDraft,
  isSocraticFollowUp,
  type ChatUiMode,
} from "@/lib/chat";
import { describeError, type ErrorInfo } from "@/lib/errors";
import type { ChatAnswer, ChatRequest } from "@/lib/types";
import { createSubmitGate } from "@/lib/use-submit";

/* -------------------------------------------------------------------------
 * Saf çekirdek: epoch'lu tur koşucusu
 * ---------------------------------------------------------------------- */

/**
 * Turun istek gövdesine giren bağlam. Çağrı yeri gönderim ANINDAKİ değerleri
 * geçirir; ek alanlar (`C`) tura dokunmadan `onAnswer`'a taşınır — ör. tam
 * ekranın "liste tazelensin mi" kararı gönderim anındaki oturum listesini okur.
 */
export interface ChatTurnContext {
  mode: ChatUiMode;
  sessionId: string | null;
  /** Açık oturumu başlatan soru; oturum yoksa null (bkz. buildChatRequest). */
  openingQuestion: string | null;
}

/**
 * Zarf uyuşmazlığının hata nesnesi. Metin `describeError`'dan GEÇMEZ (ApiError
 * değil): ekrana yedek cümle çıkar, bu satır teşhis içindir — taşınan iki
 * ekranın bugünkü davranışıyla birebir.
 */
export const ASSISTANT_MISMATCH_MESSAGE =
  "Asistan yanıtının rol bilgisi doğrulanamadı.";

export interface ChatTurnPorts<C extends ChatTurnContext> {
  /** Girdideki güncel metin — kapı ve gövde bunu okur. */
  readDraft(): string;
  setDraft(text: string): void;
  setPending(text: string | null): void;
  setSending(sending: boolean): void;
  setSendError(error: ErrorInfo | null): void;
  post(body: ChatRequest): Promise<ChatAnswer>;
  matchesIdentity(answer: ChatAnswer): boolean;
  /** Doğrulanmış cevabın çağrı yerine özgü yan etkileri (döküm, oturum, liste). */
  onAnswer(answer: ChatAnswer, text: string, context: C): void;
}

export interface ChatTurnHandle<C extends ChatTurnContext> {
  /** Kapılı gönderim: uçuşta tur varken ya da taslak gönderilemezken yok sayılır. */
  submit(context: C): Promise<void>;
  /** Uçuştaki turu geçersizle ve turun ekran izlerini (pending/busy/hata) sil. */
  invalidate(): void;
}

export function createChatTurn<C extends ChatTurnContext>(
  ports: ChatTurnPorts<C>,
): ChatTurnHandle<C> {
  let epoch = 0;

  const runTurn = async (turnEpoch: number, context: C): Promise<void> => {
    const text = ports.readDraft().trim();
    const body = buildChatRequest({
      mode: context.mode,
      draft: text,
      sessionId: context.sessionId,
      openingQuestion: context.openingQuestion,
    });
    ports.setPending(text);
    ports.setDraft("");
    try {
      const answer = await ports.post(body);
      if (epoch !== turnEpoch) return;
      if (!ports.matchesIdentity(answer)) {
        throw new Error(ASSISTANT_MISMATCH_MESSAGE);
      }
      ports.onAnswer(answer, text, context);
      ports.setPending(null);
    } catch (error) {
      if (epoch !== turnEpoch) return;
      // Konuşma geçmişi DURUR; yalnız gönderilemeyen tur geri alınır ve metin
      // girdiye iade edilir — yazdığını kaybetmek hatanın cezası olmamalı.
      ports.setPending(null);
      ports.setDraft(text);
      throw error; // kapı `reportError` ile hatayı ekrana yazar
    }
  };

  /*
   * Kapının busy/hata çıkışları kendi epoch'una kilitlidir: geçersizlenen turun
   * bitişi yeni turun `sending`/`sendError`'ını ezemez. `finally` yine koşar
   * (createSubmitGate sözleşmesi) ama yazacağı yer artık kapalıdır.
   */
  const makeGate = (turnEpoch: number) =>
    createSubmitGate<[C]>({
      action: (context) => runTurn(turnEpoch, context),
      setBusy: (busy) => {
        if (epoch === turnEpoch) ports.setSending(busy);
      },
      clearError: () => {
        if (epoch === turnEpoch) ports.setSendError(null);
      },
      reportError: (cause) => {
        if (epoch === turnEpoch) ports.setSendError(describeError(cause));
      },
    });

  let gate = makeGate(0);

  return {
    submit(context: C): Promise<void> {
      /*
       * Gönderilemeyen taslak kapıya HİÇ girmez: `aria-disabled` düğme tıklamayı
       * ve boş girdide Enter'ı engellemez; burada sessizce yok sayılır ve
       * ekrandaki hata satırı temizlenmeden kalır (kapıya girse `clearError`
       * onu silerdi).
       */
      if (!canSubmitDraft(ports.readDraft(), isSocraticFollowUp(context))) {
        return Promise.resolve();
      }
      return gate(context);
    },
    invalidate() {
      epoch += 1;
      gate = makeGate(epoch);
      ports.setPending(null);
      ports.setSending(false);
      ports.setSendError(null);
    },
  };
}

/* -------------------------------------------------------------------------
 * Kanca
 * ---------------------------------------------------------------------- */

export interface ChatTurnOptions<C extends ChatTurnContext> {
  post(body: ChatRequest): Promise<ChatAnswer>;
  matchesIdentity(answer: ChatAnswer): boolean;
  onAnswer(answer: ChatAnswer, text: string, context: C): void;
}

export interface UseChatTurnHandle<C extends ChatTurnContext> {
  draft: string;
  setDraft: (text: string) => void;
  /** Uçuştaki soru — sunucu onaylamadan dökümde yer tutar. */
  pending: string | null;
  sending: boolean;
  sendError: ErrorInfo | null;
  submit: (context: C) => Promise<void>;
  invalidate: () => void;
}

export function useChatTurn<C extends ChatTurnContext = ChatTurnContext>(
  options: ChatTurnOptions<C>,
): UseChatTurnHandle<C> {
  const [draft, setDraftState] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<ErrorInfo | null>(null);

  /*
   * Taslağın ref aynası: kapı senkron okur (aynı tick'teki ikinci tetikleme
   * state flush'ını beklemez — `use-submit.ts` girişindeki gerekçe). Her yazma
   * `setDraft` üzerinden geçtiği için ayna ile state ayrışamaz.
   */
  const draftRef = useRef("");
  const setDraft = useCallback((text: string) => {
    draftRef.current = text;
    setDraftState(text);
  }, []);

  // Seçenekler her render'da tazelenir; `submit`/`invalidate` kimliği sabit
  // kalır ki çağıranlar useCallback'e mecbur olmasın (bkz. use-submit.ts).
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const turnRef = useRef<ChatTurnHandle<C> | null>(null);
  if (turnRef.current === null) {
    turnRef.current = createChatTurn<C>({
      readDraft: () => draftRef.current,
      setDraft,
      setPending,
      setSending,
      setSendError,
      post: (body) => optionsRef.current.post(body),
      matchesIdentity: (answer) => optionsRef.current.matchesIdentity(answer),
      onAnswer: (answer, text, context) =>
        optionsRef.current.onAnswer(answer, text, context),
    });
  }
  const turn = turnRef.current;

  return {
    draft,
    setDraft,
    pending,
    sending,
    sendError,
    submit: turn.submit,
    invalidate: turn.invalidate,
  };
}
