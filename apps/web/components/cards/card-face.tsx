"use client";

/**
 * Kartın iki yüzü.
 *
 * Ne ön yüz ne arka yüz yeni bir çizim getirir: soru kökü ve kod bloğu sınav
 * ekranının `QuestionBody`'siyle, geri bildirim de aynı ekranın
 * `FeedbackPanel`'iyle çizilir. Tekrar kartı ürünün yeni bir yüzeyi değil,
 * öğrencinin zaten gördüğü sonuç ekranının tek soruya indirgenmiş hâlidir;
 * ikisi ayrı görünürse öğrenci aynı şeyin iki farklı sürümünü öğrenmek zorunda
 * kalırdı.
 *
 * Şıklar burada **statik liste**dir, radyo düğmesi değil: kart cevap almaz.
 * Öğrencinin o sınavdaki seçimi sunucuda yazılıdır ve geri bildirimde görünür;
 * kartta yeniden işaretlemek yeni bir deneme gibi okunur, oysa hiçbir yere
 * yazılmaz.
 */

import type { RefObject } from "react";
import { FeedbackPanel } from "@/components/exam/feedback-panel";
import { QuestionBody } from "@/components/exam/question-input";
import { Badge } from "@/components/ui";
import type { ReviewCard } from "@/lib/cards";

/** Sunucunun sonucu — öğrencinin kendi kararından ayrı, kart üstünde rozet. */
function ServerVerdict({ wasCorrect }: { wasCorrect: boolean | null }) {
  if (wasCorrect === null) {
    return <Badge tone="neutral">Puanlanmadı</Badge>;
  }
  // Renk tek başına bilgi taşımaz: rozetin metni her zaman var (Anayasa VII).
  return wasCorrect ? (
    <Badge tone="success">Doğru yapmıştın</Badge>
  ) : (
    <Badge tone="danger">Yanlış yapmıştın</Badge>
  );
}

export function CardFace({
  card,
  revealed,
  courseId,
  sessionId,
  headingRef,
}: {
  card: ReviewCard;
  revealed: boolean;
  courseId: string;
  sessionId: string;
  headingRef: RefObject<HTMLHeadingElement | null>;
}) {
  const choicesId = `kart-siklar-${card.id}`;

  return (
    <div className="min-w-0">
      <QuestionBody
        view={card.view}
        headingRef={headingRef}
        describedBy={choicesId}
        answered={false}
      />

      {card.view.kind === "mcq" && (
        <ul id={choicesId} className="mt-5 space-y-2">
          {card.view.choices.map((choice) => (
            <li
              key={choice.key}
              className="flex gap-3 rounded-xl border border-border bg-surface px-4 py-3 text-base leading-7 text-fg"
            >
              <span className="shrink-0 font-semibold tabular-nums text-fg-muted">{choice.key}</span>
              <span className="prose-tr min-w-0">{choice.text}</span>
            </li>
          ))}
        </ul>
      )}

      {/*
        Arka yüz açılana kadar sonuç rozeti de gizli: "yanlış yapmıştın" rozetini
        soruyla birlikte göstermek, düşünmeden önce cevabı yarı yarıya söylemek
        olurdu. Kart çevrilince rozet ve gerekçe birlikte gelir.
      */}
      {revealed && (
        <div className="mt-6 border-t border-border pt-5">
          <ServerVerdict wasCorrect={card.wasCorrect} />
          <FeedbackPanel courseId={courseId} sessionId={sessionId} feedback={card.feedback} />
        </div>
      )}
    </div>
  );
}
