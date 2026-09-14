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
import { deletionAffectsSession, isChatHistoryRecovery, subscribeChatDeletions } from "@/lib/chat-history-deletion";
import { describeError, type ErrorInfo } from "@/lib/errors";
import { useAssistantPolicyReset } from "@/lib/use-assistant-policy";
import { useChatTurn } from "@/lib/use-chat-turn";
import { sourceContextHref } from "@/lib/source-quality";
import type { ChatAnswer } from "@/lib/types";
import { ErrorNote, Loading } from "@/components/page-state";
import { demoResponseText } from "@/lib/demo-response";
import { DemoResponseNotice } from "@/components/demo-response-notice";
import { SocraticLadder } from "@/components/socratic-ladder";
import { SourceCard } from "@/components/source-card";
import {
  AbstentionBlock,
  AssistantSignature,
  ModeSwitch,
  QuestionBubble,
  ChatDraft,
  ConversationStarters,
} from "@/components/chat/transcript-parts";
import { Button } from "@/components/ui";

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
  /*
   * Tetikleyici ikincil buton kabuğudur (kenarlık + yüzey + e1 gölge); kırmızı
   * metin ya da dolgu taşımaz. Kırmızının üç meşru yeri (marka işareti, aktif
   * gezinme, sayfadaki tek birincil eylem) arasında "asistanı aç" yok; marka
   * işaretindeki tek kırmızı kare kimliği zaten taşıyor (DESIGN.md, 14 Eylül).
   */
  const triggerClass =
    placement === "floating"
      ? // Mobilde yüzen menünün üstünde 112px + güvenli alan bırakır; lg'de menü yok.
        "fixed right-4 bottom-[calc(7rem+env(safe-area-inset-bottom))] z-40 rounded-full border-border bg-surface px-5 shadow-e2 lg:right-6 lg:bottom-6"
      : "shadow-e1";

  return (
    <>
      <Button
        ref={triggerRef}
        type="button"
        variant="secondary"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={`${titleId}-dialog`}
        className={triggerClass}
      >
        <AssistantMark />
        {triggerText}
      </Button>

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
        // Seviye 2 (popover/çekmece): e2 gölge, 12px+ köşe. Dar ekranda tam
        // yükseklik ve köşesiz (kenara yapışık); sm ve üstünde 16px içeriden,
        // yuvarlak köşeli panel.
        className="m-0 ml-auto h-dvh max-h-dvh w-full max-w-[34rem] overflow-hidden border-0 bg-surface p-0 text-fg shadow-e2 backdrop:bg-black/30 open:flex open:flex-col sm:my-4 sm:mr-4 sm:h-[calc(100dvh-2rem)] sm:max-h-[calc(100dvh-2rem)] sm:rounded-[24px]"
      >
        <header className="flex shrink-0 items-start justify-between gap-4 border-b border-border bg-surface-sunken px-5 pt-[max(1.25rem,env(safe-area-inset-top))] pb-5 sm:px-6">
          <div className="min-w-0">
            <p className="text-xs text-fg-subtle">
              {identity?.eyebrow ?? "Ders kapsamlı asistan"}
              {courseLabel ? ` · ${courseLabel}` : ""}
            </p>
            <h2 id={titleId} className="mt-1 text-xl font-semibold text-fg">
              {identity?.name ?? "Ders asistanı"}
            </h2>
            <p id={descriptionId} className="prose-tr mt-2 text-sm leading-6 text-fg-muted">
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
    <section className="mb-7 flex flex-wrap items-center justify-between gap-5">
      <div className="flex min-w-0 items-center gap-4">
        <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-border bg-surface shadow-e1">
          <AssistantMark />
        </span>
        <div>
          <p className="text-xs text-fg-subtle">{identity.eyebrow}</p>
          <h1 className="mt-1 text-[28px] leading-tight font-semibold tracking-tight text-fg">{identity.name}</h1>
          <p className="prose-tr mt-2 text-base leading-7 text-fg-muted">{identity.description}</p>
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
  const [sessionId, setSessionIdState] = useState<string | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const setSessionId = useCallback((id: string | null) => { sessionIdRef.current = id; setSessionIdState(id); }, []);
  const [recoveryError, setRecoveryError] = useState<ErrorInfo | null>(null);
  const [deletionNotice, setDeletionNotice] = useState<string | null>(null);
  const [messages, setMessages] = useState<TranscriptMessage[]>([]);
  const inputRef = useRef<HTMLTextAreaElement>(null);
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
      onErrorHandled: (error) => {
        if (!isChatHistoryRecovery(error)) return false;
        resetConversation(mode); setDraft("");
        setRecoveryError(describeError(error));
        return true;
      },
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
      setMessages([]); setDeletionNotice(null);
    },
    [invalidate, setSessionId],
  );

  useEffect(() => subscribeChatDeletions(courseId, (scope) => {
    if (!deletionAffectsSession(scope, sessionIdRef.current)) return;
    resetConversation(mode); setDraft("");
    setDeletionNotice("Bu sohbet geçmişten silindi. Yeni bir soru sorabilirsin.");
  }), [courseId, mode, resetConversation, setDraft]);

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
  // İmza en fazla bir kez: başlık zaten adı taşıyor.
  const firstAssistantId = blocks.find((block) => block.kind !== "question")?.id;

  if (recoveryError) return <div className="space-y-3 p-5">
    <ErrorNote message={recoveryError.message} kind={recoveryError.kind} requestId={recoveryError.requestId} />
    <Button type="button" variant="secondary" onClick={() => window.location.assign(`/courses/${encodeURIComponent(courseId)}/chat`)}>
      Sohbet sayfasını yeniden aç
    </Button>
  </div>;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {deletionNotice && <p role="status" className="px-5 py-3 text-sm text-fg-muted">{deletionNotice}</p>}
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-3">
        <AssistantPolicyNote allowedModes={allowedModes} hintLimit={hintLimit} compact />
        <Button
          type="button"
          variant="ghost"
          size="sm"
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
        className="min-h-0 flex-1 space-y-6 overflow-y-auto overscroll-contain px-5 py-6 sm:px-6"
        aria-live="polite"
        aria-busy={sending}
      >
        {blocks.length === 0 && (
          <ConversationStarters compact suggestions={identity.suggestions} onSelect={(suggestion) => {
            const nextMode = allowedModes.includes(suggestion.preferredMode)
              ? suggestion.preferredMode : (firstAllowedChatMode(allowedModes) ?? mode);
            if (nextMode !== mode) resetConversation(nextMode);
            setDraft(suggestion.prompt);
            inputRef.current?.focus();
          }} />
        )}

        {blocks.map((block) => {
          const signed = block.id === firstAssistantId && <AssistantSignature name={identity.name} />;
          if (block.kind === "question") {
            return <QuestionBubble key={block.id} text={block.text} />;
          }
          if (block.kind === "answer") {
            return (
              <div key={block.id} className="space-y-3">
                {signed}
                <DemoResponseNotice fixture={block.fixture} />
                <p className="prose-tr text-base leading-7 whitespace-pre-line text-fg">
                  {demoResponseText(block.text, block.fixture)}
                </p>
                {block.cached && (
                  <p className="text-xs text-fg-subtle">{CACHED_ANSWER_NOTE}</p>
                )}
                {/*
                  Kaynaklar katlanır `<details>` içindeydi ve kapalı hâli kaynağı
                  gizliyordu. DESIGN.md: kaynak dipnot değil, cevapla eşit
                  ağırlıkta; dikey yığın olarak her zaman görünür.
                */}
                {block.citations.map((citation, index) => (
                  <SourceCard
                    key={`${citation.chunk_id}:${index}`}
                    source={citationSource(citation)}
                    href={sourceContextHref(courseId, citation.chunk_id)}
                    learningContext={{ courseId, chunkId: citation.chunk_id, sessionId }}
                  />
                ))}
              </div>
            );
          }
          if (block.kind === "abstention") {
            return (
              <div key={block.id} className="space-y-3">
                {signed}
                <DemoResponseNotice fixture={block.fixture} />
                <AbstentionBlock status={block.status} message={demoResponseText(block.text, block.fixture)} />
              </div>
            );
          }
          return (
            <div key={block.id} className="space-y-3">
              {signed}
              <SocraticLadder rungs={block.rungs} />
            </div>
          );
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
        className="shrink-0 space-y-3 border-t border-border bg-surface px-5 pt-4 pb-[max(1.25rem,env(safe-area-inset-bottom))] sm:px-6"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        {allowedModes.length > 1 && mode !== null && (
          <ModeSwitch
            modes={allowedChatUiModes(allowedModes)}
            mode={mode}
            sending={sending}
            onSelect={resetConversation}
          />
        )}

        <div className="space-y-3">
          <label htmlFor={`${courseId}-assistant-draft`} className="sr-only">
            {followUp ? "Denemen" : "Sorun"}
          </label>
          <ChatDraft
            ref={inputRef}
            onSend={() => void send()}
            canSend={!sending && submittable}
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
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-fg-subtle">Shift + Enter ile yeni satır</p>
            <Button type="submit" aria-disabled={sending || !submittable}>
              {sending ? "Bekleyin…" : "Gönder"}
            </Button>
          </div>
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
    <p className={`${compact ? "max-w-[15rem]" : "max-w-[18rem]"} text-sm leading-6 text-fg-subtle`}>
      {labels}
      {allowedModes.includes("socratic") ? ` · ${hintLimit} ipucu sınırı` : ""}
    </p>
  );
}

function AssistantUnavailable({ title, message }: { title: string; message: string }) {
  return (
    <div className="w-full rounded-2xl border border-border bg-bg p-6">
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
    <div className={compact ? "w-full" : "w-full rounded-2xl border border-border bg-bg p-6"}>
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
