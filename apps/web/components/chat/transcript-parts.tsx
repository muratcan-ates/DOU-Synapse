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
import type { ComponentProps, Ref } from "react";
import type { AssistantSuggestion } from "@/lib/course-assistant";
import { Card } from "@/components/ui";

/** Kullanıcı sorusu: sağa yaslı, çukur yüzey, sağ alt köşe hafif kırık. */
export function QuestionBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[92%] break-words rounded-[20px] rounded-br-md bg-surface-sunken px-5 py-4 text-base leading-7 whitespace-pre-line text-fg sm:max-w-[85%]">
        {text}
      </p>
    </div>
  );
}

/** Asistan imzası: dökümde en fazla bir kez, ilk asistan bloğunun üstünde. */
export function AssistantSignature({ name }: { name: string }) {
  return <p className="flex items-center gap-2 text-sm font-semibold text-fg"><span aria-hidden="true" className="h-2 w-2 rounded-full bg-brand" />{name}</p>;
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
      <p className="text-sm font-medium text-fg-muted">{ABSTENTION_LABEL[status]}</p>
      <p className="prose-tr mt-2 text-base leading-7 text-fg-muted">{message}</p>
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
      className="flex w-fit max-w-full gap-1 rounded-xl bg-surface-sunken p-1"
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
            className={`min-h-11 rounded-lg px-3 text-sm transition-[color,background,box-shadow] duration-200 motion-reduce:transition-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand aria-disabled:cursor-not-allowed aria-disabled:opacity-40 ${
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

/** Ortak çok satırlı besteci; Enter gönderir, Shift+Enter yeni satır açar. */
export function ChatDraft({ onSend, canSend, ref, className = "", ...props }: Omit<ComponentProps<"textarea">, "ref"> & {
  ref?: Ref<HTMLTextAreaElement>;
  onSend: () => void;
  canSend: boolean;
}) {
  return <textarea
    {...props}
    ref={ref}
    rows={3}
    className={`block min-h-28 max-h-52 w-full resize-y rounded-xl border border-border-strong bg-surface px-4 py-3 text-base leading-7 text-fg placeholder:text-fg-subtle transition-[border-color,box-shadow] duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand motion-reduce:transition-none ${className}`}
    onKeyDown={(event) => {
      props.onKeyDown?.(event);
      if (event.defaultPrevented || event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing || event.nativeEvent.keyCode === 229) return;
      event.preventDefault();
      if (canSend && !props.readOnly && !props.disabled) onSend();
    }}
  />;
}

/** Öneri seçimi yalnız taslağı doldurur; gönderim kullanıcıya aittir. */
export function ConversationStarters({ suggestions, onSelect, compact = false }: {
  suggestions: readonly AssistantSuggestion[];
  onSelect: (suggestion: AssistantSuggestion) => void;
  compact?: boolean;
}) {
  return <section className={compact ? "py-3" : "mx-auto w-full max-w-2xl py-6 sm:py-12"} aria-label="Sohbet başlangıçları">
    <span aria-hidden="true" className="mb-5 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-subtle text-brand">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        <path d="M8 10h8M8 14h5M6 20l-3 1V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H8z" />
      </svg>
    </span>
    <h2 className={`${compact ? "text-xl" : "text-2xl"} font-semibold tracking-tight text-fg`}>Nereden başlamak istersiniz?</h2>
    <p className="prose-tr mt-3 text-base leading-7 text-fg-muted">Ders materyalinden bir soru sorun. Bir konuyu birlikte çalışabilir veya kaynaklı bir açıklama isteyebilirsiniz.</p>
    <ul className="mt-6 space-y-2">
      {suggestions.map((suggestion) => <li key={suggestion.label}>
        <button type="button" onClick={() => onSelect(suggestion)}
          className="group flex min-h-14 w-full items-center justify-between gap-4 rounded-xl border border-border bg-surface px-4 py-3 text-left text-sm font-medium text-fg transition-[background,border-color] duration-200 hover:border-border-strong hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand motion-reduce:transition-none">
          {suggestion.label}<span aria-hidden="true" className="text-lg text-fg-subtle transition-transform duration-200 group-hover:translate-x-1 motion-reduce:transform-none motion-reduce:transition-none">→</span>
        </button>
      </li>)}
    </ul>
    <p className="mt-3 text-sm text-fg-subtle">Bir öneri seçin, sorunuzu düzenleyin ve gönderin.</p>
  </section>;
}
