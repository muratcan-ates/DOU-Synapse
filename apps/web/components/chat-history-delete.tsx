"use client";

import { useEffect, useId, useRef, useState } from "react";
import { deleteOwnChatHistory, type ChatDeletionScope } from "@/lib/chat-history-deletion";
import { describeError, type ErrorInfo } from "@/lib/errors";
import { useSubmit } from "@/lib/use-submit";
import { ErrorNote } from "@/components/page-state";
import { Button } from "@/components/ui";

/** Açık, satır içi onay. İlk odak iptaldedir; Enter varsayılan olarak silmez. */
export function ChatHistoryDelete({ courseId, sessionId, title }: ChatDeletionScope & { title?: string }) {
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<ErrorInfo | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const opened = useRef(false);
  const descriptionId = useId();
  const contextId = useId();
  const wholeCourse = sessionId === null;
  const label = wholeCourse ? "Bu dersteki sohbetlerimi sil" : "Sohbeti sil";
  const { busy, submit } = useSubmit(async () => {
    setError(null);
    const deleted = await deleteOwnChatHistory({ courseId, sessionId });
    if (deleted === null) return;
    setNotice(wholeCourse ? `Bu dersteki ${deleted} sohbetin silindi.` : "Sohbet silindi.");
    setConfirming(false);
  }, { onError: (cause) => setError(describeError(cause)) });
  useEffect(() => {
    if (confirming) { opened.current = true; cancelRef.current?.focus(); }
    else if (opened.current) { opened.current = false; triggerRef.current?.focus(); }
  }, [confirming]);
  return <div className="space-y-2">
    {title && <span id={contextId} className="sr-only">{title} başlıklı sohbet</span>}
    {!confirming ? <Button ref={triggerRef} type="button" variant="secondary"
      aria-label={label} aria-describedby={title ? contextId : undefined}
      onClick={() => { setError(null); setNotice(null); setConfirming(true); }}>{label}</Button> :
      <div className="space-y-2 rounded-lg border border-border-strong p-3" role="group" aria-label="Sohbet silme onayı">
        <p id={descriptionId} className="prose-tr text-sm text-fg-muted">{wholeCourse
          ? "Yalnız bu dersteki kendi sohbetlerin ve onlara ait mesajlar silinecek. Diğer katılımcıların sohbetleri, sınav kayıtların ve diğer derslerin etkilenmez. Bu işlem geri alınamaz."
          : "Bu sohbet ve ona ait mesajlar silinecek. Diğer sohbetlerin etkilenmez. Bu işlem geri alınamaz."}</p>
        <div className="flex flex-wrap gap-2">
          <Button ref={cancelRef} type="button" variant="secondary" aria-disabled={busy}
            onClick={() => { if (!busy) setConfirming(false); }}>Vazgeç</Button>
          <Button type="button" variant="danger" aria-disabled={busy} aria-describedby={descriptionId}
            onClick={() => void submit()}>{busy ? "Siliniyor…" : "Kalıcı olarak sil"}</Button>
        </div>
      </div>}
    {error && <ErrorNote message={error.message} kind={error.kind} requestId={error.requestId} />}
    {notice && <p role="status" className="text-sm text-fg-muted">{notice}</p>}
  </div>;
}
