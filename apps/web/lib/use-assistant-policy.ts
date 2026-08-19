"use client";

/**
 * Persona/politika değişiminde konuşmayı sıfırlama kararı.
 *
 * İki sohbet yüzeyi (tam ekran + çekmece) aynı kuralı bağımsız kopyalarla
 * taşıyordu: availability zarfı (kimlik + izinli modlar + ipucu sınırı)
 * değişince eski rolün oturumu ve taslağı YENİ role taşınmaz; mod politika
 * dışında kaldıysa izinli ilk moda dönülür. Kural saf fonksiyona indirildi ki
 * DOM'suz `bun test lib/` doğrudan sınayabilsin; efekt sarmalayıcı iki yüzeyde
 * aynı tetikleme düzenini kullanır.
 *
 * Not: her iki yüzey de konuşma bileşenini availability anahtarıyla (`key`)
 * yeniden monte ediyor; bu efekt yine de duruyor — anahtar üretimiyle bu kural
 * birbirinden bağımsız iki emniyettir ve taşınan ekranlar ikisini de taşıyordu.
 */

import { useEffect, useRef } from "react";
import type { ChatUiMode } from "@/lib/chat";
import {
  firstAllowedChatMode,
  type CourseAssistantIdentity,
} from "@/lib/course-assistant";

/** Zarfı tek anahtara indirger; efekt "değişti mi"yi bununla ölçer. */
export function assistantPolicyKey(
  identity: CourseAssistantIdentity,
  allowedModes: readonly ChatUiMode[],
  hintLimit: number,
): string {
  return `${identity.audience}:${identity.agentProfile}:${allowedModes.join(",")}:${hintLimit}`;
}

export type PolicyResetDecision =
  | { reset: false }
  | { reset: true; nextMode: ChatUiMode | null };

/**
 * Sıfırlama gerekli mi, gerekiyorsa hangi moda?
 *
 * `nextMode` null da dönebilir (izinli mod hiç kalmadıysa): çekmece bu durumda
 * konuşmayı modsuz hâle sıfırlar ve girdiyi kapatır, tam ekran ise hiç sıfırlamaz
 * — o ekranda modsuz hâl yok, kapıyı üst bileşen (boş `allowedModes` daha
 * ekrana gelmeden) tutuyor. Karar burada, null'u ne yapacağı çağrı yerinde.
 */
export function policyResetDecision(args: {
  mode: ChatUiMode | null;
  allowedModes: readonly ChatUiMode[];
  policyChanged: boolean;
}): PolicyResetDecision {
  const nextMode =
    args.mode !== null && args.allowedModes.includes(args.mode)
      ? args.mode
      : firstAllowedChatMode(args.allowedModes);
  if (!args.policyChanged && nextMode === args.mode) return { reset: false };
  return { reset: true, nextMode };
}

export function useAssistantPolicyReset(options: {
  identity: CourseAssistantIdentity;
  allowedModes: readonly ChatUiMode[];
  hintLimit: number;
  mode: ChatUiMode | null;
  /** Sıfırlama kararı: oturumu kapat, modu kur, taslağı boşalt — çağrı yerinin işi. */
  onReset: (nextMode: ChatUiMode | null) => void;
}): void {
  const { identity, allowedModes, hintLimit, mode } = options;
  const policyKey = assistantPolicyKey(identity, allowedModes, hintLimit);
  const previousPolicyKey = useRef(policyKey);
  const onResetRef = useRef(options.onReset);
  onResetRef.current = options.onReset;

  useEffect(() => {
    const policyChanged = previousPolicyKey.current !== policyKey;
    previousPolicyKey.current = policyKey;
    const decision = policyResetDecision({ mode, allowedModes, policyChanged });
    if (!decision.reset) return;
    onResetRef.current(decision.nextMode);
  }, [allowedModes, mode, policyKey]);
}
