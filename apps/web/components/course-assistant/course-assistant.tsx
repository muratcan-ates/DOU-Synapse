"use client";

/**
 * Ders kapsamlı, rolü sunucudan gelen kompakt sohbet çekmecesi.
 *
 * Bu bileşen yeni bir agent hattı kurmaz; tam sohbet ekranıyla aynı
 * `/courses/{id}/chat` ucunu ve aynı istek kurucusunu kullanır. Dashboard rolü
 * yalnız kartın kendi sunumu içindir, buraya geçirilmez. Böylece kullanıcı
 * rol seçemez ve istemci persona tahmin etmez.
 */

import { useCallback, useEffect, useId, useRef, useState } from "react";
import {
  CACHED_ANSWER_NOTE,
  canSubmitDraft,
  CHAT_MODE_LABEL,
  citationSource,
  fromAnswer,
  isSocraticFollowUp,
  QUESTION_MAX_LENGTH,
  toBlocks,
  userMessage,
  type ChatUiMode,
  type TranscriptMessage,
} from "@/lib/chat";
import {
  allowedChatUiModes,
  answerMatchesAssistant,
  firstAllowedChatMode,
  resolveCourseAssistantIdentity,
  type CourseAssistantIdentity,
} from "@/lib/course-assistant";
import { useChatAvailability, type ChatLock } from "@/lib/chat-availability";
import { api } from "@/lib/api";
import { useAssistantPolicyReset } from "@/lib/use-assistant-policy";
import { useChatTurn } from "@/lib/use-chat-turn";
import { sourceContextHref } from "@/lib/source-quality";
import type { ChatAnswer } from "@/lib/types";
import { ErrorNote, Loading } from "@/components/page-state";
import { SocraticLadder } from "@/components/socratic-ladder";
import { AbstentionNotice, SourceCard } from "@/components/source-card";
import { Button, Input } from "@/components/ui";

const DIALOG_FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  'summary',
  '[tabindex]:not([tabindex="-1"])',
].join(",");

function visibleDialogControls(dialog: HTMLDialogElement) {
  return Array.from(dialog.querySelectorAll<HTMLElement>(DIALOG_FOCUSABLE)).filter(
    (element) =>
      element.getAttribute("aria-hidden") !== "true" && element.getClientRects().length > 0,
  );
}

export function CourseAssistant({
  courseId,
  courseLabel,
  availability,
  placement = "floating",
}: {
  courseId: string;
  /** Yalnız erişilebilir tetikleyici bağlamı; persona üretmek için kullanılmaz. */
  courseLabel?: string;
  /** Ders sayfası availability'yi zaten okuduysa aynı veri yeniden çekilmez. */
  availability?: ChatLock;
  placement?: "floating" | "inline";
}) {
  const [open, setOpen] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const ownAvailability = useChatAvailability(open && !availability ? courseId : null);
  const access = availability ?? ownAvailability;
  const identity = resolveCourseAssistantIdentity(access.audience, access.agentProfile);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  const triggerText = identity?.name ?? (access.locked ? "Asistan kilitli" : "Ders asistanı");
  const triggerClass =
    placement === "floating"
      ? "fixed right-4 bottom-4 z-40 border border-border-strong bg-surface px-4 py-2 text-fg"
      : "h-11 px-0 text-xs font-medium text-brand underline-offset-4 hover:underline";

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={`${titleId}-dialog`}
        className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${triggerClass}`}
      >
        <AssistantMark />
        {triggerText}
      </button>

      <dialog
        ref={dialogRef}
        id={`${titleId}-dialog`}
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        onCancel={(event) => {
          // State ile native dialog durumu tek yönden kapansın. Aksi hâlde
          // tarayıcı dialogu kapatıp React state'ini bir render geride bırakır.
          event.preventDefault();
          setOpen(false);
        }}
        onKeyDown={(event) => {
          if (event.key === "Tab") {
            const controls = visibleDialogControls(event.currentTarget);
            const first = controls[0];
            const last = controls.at(-1);
            const active = document.activeElement;

            if (!first || !last) {
              event.preventDefault();
              return;
            }
            if (event.shiftKey && (active === first || !event.currentTarget.contains(active))) {
              event.preventDefault();
              last.focus();
              return;
            }
            if (!event.shiftKey && (active === last || !event.currentTarget.contains(active))) {
              event.preventDefault();
              first.focus();
              return;
            }
          }
          /*
           * Bazı WebKit sürümleri ve otomasyon katmanları native `cancel`
           * olayını üretmiyor. Escape'i açıkça ele almak T307'nin klavye
           * sözleşmesini tarayıcının örtük davranışına bırakmaz.
           */
          if (event.key !== "Escape") return;
          event.preventDefault();
          setOpen(false);
        }}
        onClose={() => {
          setOpen(false);
          triggerRef.current?.focus();
        }}
        className="m-0 ml-auto h-dvh max-h-dvh w-full max-w-[29rem] border-0 bg-surface p-0 text-fg backdrop:bg-black/30 open:flex open:flex-col"
      >
        <header className="flex shrink-0 items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div className="min-w-0">
            <p className="text-xs text-fg-subtle">
              {identity?.eyebrow ?? "Ders kapsamlı asistan"}
              {courseLabel ? ` · ${courseLabel}` : ""}
            </p>
            <h2 id={titleId} className="mt-1 text-lg font-medium text-fg">
              {identity?.name ?? "Ders asistanı"}
            </h2>
            <p id={descriptionId} className="prose-tr mt-1 text-xs text-fg-muted">
              {identity?.description ??
                "Asistan kimliği ve kullanım politikası ders üyeliğinizden sunucu tarafından belirlenir."}
            </p>
          </div>
          <Button
            type="button"
            variant="ghost"
            className="shrink-0 px-3"
            autoFocus
            onClick={() => setOpen(false)}
            aria-label="Ders asistanını kapat"
          >
            Kapat
          </Button>
        </header>

        {!access.ready ? (
          <div className="p-6">
            <Loading label="Asistan profili yükleniyor…" />
          </div>
        ) : access.error ? (
          <div className="flex flex-1 items-center p-6">
            <AssistantAvailabilityError access={access} message={access.error} />
          </div>
        ) : access.locked ? (
          <div className="flex flex-1 items-center p-6">
            <AssistantUnavailable
              title="Asistan sınav sırasında kapalı"
              message={access.message ?? "Asistan şu anda kullanılamıyor."}
            />
          </div>
        ) : identity === null ? (
          <div className="flex flex-1 items-center p-6">
            <AssistantUnavailable
              title="Asistan profili doğrulanamadı"
              message="Rol seçimi yapılmadı. Sunucunun ders üyeliğiniz için bir asistan profili döndürmesi gerekiyor."
            />
          </div>
        ) : access.allowedModes.length === 0 ? (
          <div className="flex flex-1 items-center p-6">
            <AssistantUnavailable
              title="Sohbet modu kullanılamıyor"
              message="Bu dersin AI politikası şu anda kullanılabilir bir sohbet modu açmıyor."
            />
          </div>
        ) : (
          <>
            {access.refreshError && (
              <div className="shrink-0 border-b border-border px-5 py-4">
                <AssistantAvailabilityError
                  access={access}
                  message={access.refreshError}
                  compact
                />
              </div>
            )}
            <AssistantConversation
              key={`${courseId}:${identity.audience}:${identity.agentProfile}:${access.allowedModes.join(",")}:${access.hintLimit}`}
              courseId={courseId}
              identity={identity}
              allowedModes={access.allowedModes}
              hintLimit={access.hintLimit}
            />
          </>
        )}
      </dialog>
    </>
  );
}

/** Tam sohbet sayfası da aynı görünür sunucu kimliğini kullanır. */
export function AssistantIdentitySummary({
  identity,
  allowedModes,
  hintLimit,
}: {
  identity: CourseAssistantIdentity;
  allowedModes: readonly ChatUiMode[];
  hintLimit: number;
}) {
  return (
    <section className="mb-6 flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
      <div className="flex min-w-0 items-start gap-3">
        <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface">
          <AssistantMark />
        </span>
        <div>
          <p className="text-xs text-fg-subtle">{identity.eyebrow}</p>
          <h1 className="mt-0.5 text-xl font-medium text-fg">{identity.name}</h1>
          <p className="prose-tr mt-1 text-sm text-fg-muted">{identity.description}</p>
        </div>
      </div>
      <AssistantPolicyNote allowedModes={allowedModes} hintLimit={hintLimit} />
    </section>
  );
}

function AssistantConversation({
  courseId,
  identity,
  allowedModes,
  hintLimit,
}: {
  courseId: string;
  identity: CourseAssistantIdentity;
  allowedModes: ChatUiMode[];
  hintLimit: number;
}) {
  const [mode, setMode] = useState<ChatUiMode | null>(() =>
    firstAllowedChatMode(allowedModes),
  );
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<TranscriptMessage[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  /*
   * Gönderim turu ortak çekirdekten (`createSubmitGate` üstünde epoch'lu tur):
   * iyimser `pending`, hatada taslağın iadesi ve zarf doğrulaması orada.
   * Çekmeceye özgü olan yalnız cevabın dökümü ve oturum kimliği.
   */
  const { draft, setDraft, pending, sending, sendError, submit, invalidate } =
    useChatTurn({
      post: (body) => api.post<ChatAnswer>(`/courses/${courseId}/chat`, body),
      matchesIdentity: (answer) => answerMatchesAssistant(answer, identity),
      onAnswer: (answer, text) => {
        setMessages((current) => [
          ...current,
          userMessage(`user:${answer.message_id}`, text),
          fromAnswer(answer),
        ]);
        setSessionId(answer.session_id);
      },
    });

  const resetConversation = useCallback(
    (nextMode: ChatUiMode | null) => {
      invalidate();
      setMode(nextMode);
      setSessionId(null);
      setMessages([]);
    },
    [invalidate],
  );

  useAssistantPolicyReset({
    identity,
    allowedModes,
    hintLimit,
    mode,
    onReset: (nextMode) => {
      resetConversation(nextMode);
      // Eski persona için yazılmış, henüz gönderilmemiş metin de taşınmaz.
      setDraft("");
    },
  });

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages, pending, sending]);

  const openingQuestion =
    messages.find((message) => message.role === "user")?.content ?? null;
  const followUp =
    mode !== null && isSocraticFollowUp({ mode, sessionId, openingQuestion });
  const submittable = mode !== null && canSubmitDraft(draft, followUp);

  const send = () => {
    if (mode === null) return Promise.resolve();
    return submit({ mode, sessionId, openingQuestion });
  };

  const blocks = mode === null ? [] : toBlocks(messages, { mode, pending });

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-3">
        <AssistantPolicyNote allowedModes={allowedModes} hintLimit={hintLimit} compact />
        <Button
          type="button"
          variant="ghost"
          className="h-9 px-3 text-xs"
          aria-disabled={sending}
          onClick={() => {
            if (sending) return;
            resetConversation(mode);
          }}
        >
          Yeni konuşma
        </Button>
      </div>

      <div
        className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-5"
        aria-live="polite"
        aria-busy={sending}
      >
        {blocks.length === 0 && (
          <div className="space-y-4">
            <div>
              <p className="text-sm font-medium text-fg">Nereden başlamak istersiniz?</p>
              <p className="prose-tr mt-1 text-xs text-fg-muted">
                Öneriler yalnız besteciyi doldurur; siz göndermeden token harcanmaz.
              </p>
            </div>
            <ul className="space-y-2">
              {identity.suggestions.map((suggestion) => (
                <li key={suggestion.label}>
                  <button
                    type="button"
                    onClick={() => {
                      const nextMode = allowedModes.includes(suggestion.preferredMode)
                        ? suggestion.preferredMode
                        : (firstAllowedChatMode(allowedModes) ?? mode);
                      if (nextMode !== mode) resetConversation(nextMode);
                      setDraft(suggestion.prompt);
                      inputRef.current?.focus();
                    }}
                    className="min-h-11 w-full rounded-lg border border-border bg-bg px-3 py-2 text-left text-sm text-fg transition-colors hover:border-border-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                  >
                    {suggestion.label}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {blocks.map((block) => {
          if (block.kind === "question") {
            return (
              <div key={block.id} className="flex justify-end">
                <p className="max-w-[88%] rounded-lg bg-bg px-3 py-2 text-sm whitespace-pre-line text-fg">
                  {block.text}
                </p>
              </div>
            );
          }
          if (block.kind === "answer") {
            return (
              <div key={block.id} className="space-y-3">
                <p className="prose-tr text-sm whitespace-pre-line text-fg">{block.text}</p>
                {block.cached && (
                  <p className="text-xs text-fg-subtle">{CACHED_ANSWER_NOTE}</p>
                )}
                {block.citations.length > 0 && (
                  <details className="rounded-lg border border-border bg-bg">
                    <summary className="min-h-11 cursor-pointer px-3 py-2 text-xs font-medium text-fg-muted focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand">
                      {block.citations.length} kaynak
                    </summary>
                    <div className="space-y-2 border-t border-border p-3">
                      {block.citations.map((citation, index) => (
                        <SourceCard
                          key={`${citation.chunk_id}:${index}`}
                          source={citationSource(citation)}
                          href={sourceContextHref(courseId, citation.chunk_id)}
                        />
                      ))}
                    </div>
                  </details>
                )}
              </div>
            );
          }
          if (block.kind === "abstention") {
            return (
              <AbstentionNotice key={block.id} status={block.status} message={block.text} />
            );
          }
          return <SocraticLadder key={block.id} rungs={block.rungs} />;
        })}

        {sending && <Loading label="Yanıt hazırlanıyor…" />}
        {sendError && (
          <ErrorNote
            message={sendError.message}
            kind={sendError.kind}
            requestId={sendError.requestId}
            onRetry={() => void send()}
          />
        )}
        <div ref={endRef} aria-hidden="true" />
      </div>

      <form
        className="shrink-0 space-y-3 border-t border-border bg-surface px-4 py-4"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        {allowedModes.length > 1 && mode !== null && (
          <div role="group" aria-label="Sohbet modu" className="flex gap-1">
            {allowedChatUiModes(allowedModes).map((candidate) => (
              <button
                key={candidate}
                type="button"
                aria-pressed={mode === candidate}
                aria-disabled={sending}
                onClick={() => {
                  if (!sending && mode !== candidate) resetConversation(candidate);
                }}
                className={`min-h-9 rounded-lg border px-3 text-xs focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand aria-disabled:opacity-40 ${
                  mode === candidate
                    ? "border-border-strong bg-bg font-medium text-fg"
                    : "border-transparent text-fg-muted hover:text-fg"
                }`}
              >
                {CHAT_MODE_LABEL[candidate]}
              </button>
            ))}
          </div>
        )}

        <div className="flex gap-2">
          <label htmlFor={`${courseId}-assistant-draft`} className="sr-only">
            {followUp ? "Denemen" : "Sorun"}
          </label>
          <Input
            ref={inputRef}
            id={`${courseId}-assistant-draft`}
            value={draft}
            maxLength={QUESTION_MAX_LENGTH}
            disabled={mode === null}
            readOnly={sending}
            aria-disabled={sending || mode === null}
            autoComplete="off"
            onChange={(event) => setDraft(event.target.value)}
            placeholder={
              followUp ? "Bu ipucuyla ne denediniz?" : "Ders kaynaklarına sorun…"
            }
          />
          <Button type="submit" aria-disabled={sending || !submittable} className="px-3">
            {sending ? "Bekleyin…" : "Gönder"}
          </Button>
        </div>
      </form>
    </div>
  );
}

function AssistantPolicyNote({
  allowedModes,
  hintLimit,
  compact = false,
}: {
  allowedModes: readonly ChatUiMode[];
  hintLimit: number;
  compact?: boolean;
}) {
  const labels = allowedModes.map((mode) => CHAT_MODE_LABEL[mode]).join(" · ");
  return (
    <p className={`${compact ? "max-w-[15rem]" : "max-w-[18rem]"} text-xs text-fg-subtle`}>
      {labels}
      {allowedModes.includes("socratic") ? ` · ${hintLimit} ipucu sınırı` : ""}
    </p>
  );
}

function AssistantUnavailable({ title, message }: { title: string; message: string }) {
  return (
    <div className="w-full rounded-lg border border-border bg-bg p-5">
      <p className="text-sm font-medium text-fg">{title}</p>
      <p role="status" className="prose-tr mt-2 text-sm text-fg-muted">
        {message}
      </p>
    </div>
  );
}

function AssistantAvailabilityError({
  access,
  message,
  compact = false,
}: {
  access: ChatLock;
  message: string;
  compact?: boolean;
}) {
  return (
    <div className={compact ? "w-full" : "w-full rounded-lg border border-border bg-bg p-5"}>
      {!compact && (
        <p className="mb-2 text-sm font-medium text-fg">Asistan durumuna ulaşılamadı</p>
      )}
      <ErrorNote
        message={message}
        kind={access.errorKind}
        requestId={access.errorRequestId}
        onRetry={access.reload}
      />
    </div>
  );
}

function AssistantMark() {
  return (
    <span aria-hidden="true" className="grid h-5 w-5 grid-cols-2 gap-0.5">
      <span className="rounded-[2px] bg-brand" />
      <span className="rounded-[2px] bg-fg-subtle" />
      <span className="rounded-[2px] bg-fg-subtle" />
      <span className="rounded-[2px] border border-border-strong" />
    </span>
  );
}
