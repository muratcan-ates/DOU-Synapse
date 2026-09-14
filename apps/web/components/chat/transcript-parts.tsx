"use client";

/**
 * Sohbet dökümünün ortak parçaları — tam sayfa (`app/courses/[courseId]/chat`)
 * ve çekmece (`components/course-assistant`) aynı gramerle çizilir; iki kopya
 * ilk düzeltmede birbirinden ayrışırdı (Anayasa XI).
 *
 * Görünüm kararları DESIGN.md'den: kullanıcı balonu çukur yüzeyde sağa yaslı;
 * asistan cevabı kart değil düz akış (`prose-tr`); abstention hata gibi
 * görünmez (çukur yüzey, soluk metin, kırmızı yok); mod seçici segment
 * kontrolüdür ve `aria-pressed` semantiği korunur.
 */

import {
  ABSTENTION_LABEL,
  CHAT_MODE_LABEL,
  type AbstentionStatus,
  type ChatUiMode,
} from "@/lib/chat";
import { Card } from "@/components/ui";

/** Kullanıcı sorusu: sağa yaslı, çukur yüzey, sağ alt köşe hafif kırık. */
export function QuestionBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[80%] rounded-2xl rounded-br-md bg-surface-sunken px-4 py-3 text-sm whitespace-pre-line text-fg">
        {text}
      </p>
    </div>
  );
}

/** Asistan imzası: dökümde en fazla bir kez, ilk asistan bloğunun üstünde. */
export function AssistantSignature({ name }: { name: string }) {
  return <p className="text-xs font-medium text-fg-muted">{name}</p>;
}

/**
 * Kapsam dışı / dayanaksız bildirimi — hata GİBİ GÖRÜNMEMELİ (DESIGN.md'deki
 * en kritik karar). Başlık `ABSTENTION_LABEL`'dan, metin backend'den gelir;
 * `AbstentionNotice` ile aynı içerik, yalnız kabuk çukur kart. Kırmızı, ünlem
 * ve `role="alert"` yok; sonraki adım önerisi metnin içindedir.
 */
export function AbstentionBlock({
  status,
  message,
}: {
  status: AbstentionStatus;
  message: string;
}) {
  return (
    <Card variant="soft">
      <p className="text-xs font-medium text-fg-muted">{ABSTENTION_LABEL[status]}</p>
      <p className="prose-tr mt-2 text-sm text-fg-muted">{message}</p>
    </Card>
  );
}

/**
 * Mod seçici (Soru-cevap / Sokratik): çukur ray içinde yükselmiş aktif segment.
 * Mod oturum ortasında değişemez (sunucu 422 döner); seçim yeni oturum açar,
 * o karar çağıran tarafta (`onSelect`). Gönderim sürerken seçim yok sayılır.
 */
export function ModeSwitch({
  modes,
  mode,
  sending,
  onSelect,
}: {
  modes: readonly ChatUiMode[];
  mode: ChatUiMode | null;
  sending: boolean;
  onSelect: (mode: ChatUiMode) => void;
}) {
  return (
    <div
      role="group"
      aria-label="Sohbet modu"
      className="flex w-fit gap-1 rounded-xl bg-surface-sunken p-1"
    >
      {modes.map((candidate) => {
        const active = mode === candidate;
        return (
          <button
            key={candidate}
            type="button"
            aria-pressed={active}
            aria-disabled={sending}
            onClick={() => {
              if (!sending && !active) onSelect(candidate);
            }}
            className={`h-9 rounded-lg px-3 text-xs transition-[color,background,box-shadow] duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand aria-disabled:cursor-not-allowed aria-disabled:opacity-40 ${
              active
                ? "bg-surface font-medium text-fg shadow-e1"
                : "text-fg-muted hover:text-fg"
            }`}
          >
            {CHAT_MODE_LABEL[candidate]}
          </button>
        );
      })}
    </div>
  );
}
