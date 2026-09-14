"use client";

/**
 * Sohbet ekranı — gerçek cevap hattına bağlı (T022).
 *
 * Örnek veri ve önizleme şeridi kaldırıldı: hat canlı, ekranın "yakında"
 * demesi çalışan ürünü çalışmıyor gösteriyordu.
 *
 * Ekranın taşıdığı üç kural:
 *  - Abstention hata değildir: `insufficient_context` / `out_of_scope` normal
 *    200'dür ve nötr bir bildirimle gösterilir (Anayasa VII).
 *  - 429/503/ağ hatası GERÇEK hatadır: satır içi gösterilir ve konuşmayı silmez.
 *  - Gösterilen her metin backend'den gelir; arayüz hata cümlesi uydurmaz.
 *
 * Saf mantık (istek gövdesi, kademe eşlemesi, döküm blokları) `lib/chat.ts`'te;
 * oturum/gönderim durum makinesi `lib/use-chat-session.ts`'te (ters sayfalama
 * `lib/use-reverse-history.ts`, gönderim kapısı `lib/use-chat-turn.ts`).
 * Burada yalnız sunum ve yerleşim var.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import {
  CACHED_ANSWER_NOTE,
  CHAT_MODE_LABEL,
  citationSource,
  QUESTION_MAX_LENGTH,
  sessionStageLabel,
  toBlocks,
  type ChatBlock,
  type ChatUiMode,
  type TranscriptMessage,
} from "@/lib/chat";
import {
  resolveCourseAssistantIdentity,
  sessionMatchesAssistant,
  type CourseAssistantIdentity,
} from "@/lib/course-assistant";
import { DOCUMENT_STATUS } from "@/lib/labels";
import type { ChatSessionSummary, CourseDocument, Page } from "@/lib/types";
import { useChatAvailability } from "@/lib/chat-availability";
import { useChatSession } from "@/lib/use-chat-session";
import { subscribeChatDeletions } from "@/lib/chat-history-deletion";
import { ChatHistoryDelete } from "@/components/chat-history-delete";
import { usePagedResource } from "@/lib/use-paged-resource";
import { useResource, type Resource } from "@/lib/use-resource";
import { sourceContextHref } from "@/lib/source-quality";
import { AppShell } from "@/components/app-shell";
import { ChatFeedbackControls } from "@/components/chat-feedback";
import { AssistantIdentitySummary } from "@/components/course-assistant/course-assistant";
import { CourseNav } from "@/components/course-nav";
import { ErrorNote, Loading, LoadMore } from "@/components/page-state";
import { demoResponseText } from "@/lib/demo-response";
import { DemoResponseNotice } from "@/components/demo-response-notice";
import { SocraticLadder } from "@/components/socratic-ladder";
import { SourceCard } from "@/components/source-card";
import {
  AbstentionBlock,
  AssistantSignature,
  ModeSwitch,
  QuestionBubble,
} from "@/components/chat/transcript-parts";
import { Badge, Button, Card, EmptyState, Input } from "@/components/ui";

export default function ChatPage() {
  const { courseId } = useParams<{ courseId: string }>();
  /*
   * Sekme kilitliyken bu sayfaya doğrudan URL ile de gelinebilir; ekran o zaman
   * besteci yerine sebebi gösterir. Bu bir yetki kapısı DEĞİLDİR — sunucu her
   * isteği zaten 403 ile reddediyor (Anayasa II: istemci yetki vermez).
   * Buradaki tek amaç kullanıcıyı boş bir ekrana ya da art arda hataya
   * koşturmamak.
   */
  const lock = useChatAvailability(courseId);
  const identity = resolveCourseAssistantIdentity(lock.audience, lock.agentProfile);

  /*
   * Yoklama dönene kadar HİÇBİRİ çizilmez. Bu bir estetik tercih değil:
   * `ChatScreen` monte olur olmaz oturum listesini çekiyor ve kilitli
   * öğrencide o istek 403 dönüyordu — tarayıcı konsolunda her yüklemede iki
   * hata, ekranda ise bir an beliren besteci. Kullanıcı "yazabilirim" sanıp
   * yazmaya başlıyor, sonra alan kayboluyor.
   *
   * Bekleme "kilitli" olarak da çizilemez: sınavı olmayan her öğrencinin
   * sekmesi bir an kilitli görünürdü. Doğru üçüncü hâl "henüz bilinmiyor" ve
   * karşılığı yükleme göstergesi (`lib/session.ts`'in `ready` kuralıyla aynı).
   */
  if (!lock.ready) {
    return (
      <AppShell>
        <CourseNav courseId={courseId} lock={lock} />
        <Loading label="Yükleniyor…" />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <CourseNav courseId={courseId} lock={lock} />
      {lock.error ? (
        <div className="rounded-lg border border-border bg-surface p-5">
          <ErrorNote
            message={lock.error}
            kind={lock.errorKind}
            requestId={lock.errorRequestId}
            onRetry={lock.reload}
          />
        </div>
      ) : lock.locked ? (
        <EmptyState title={lock.message ?? "Asistan şu anda kullanılamıyor."} />
      ) : identity === null ? (
        <EmptyState title="Asistan profili sunucudan doğrulanamadı." />
      ) : lock.allowedModes.length === 0 ? (
        <EmptyState title="Bu dersin AI politikası kullanılabilir bir sohbet modu açmıyor." />
      ) : (
        <>
          {lock.refreshError && (
            <div className="mb-5 rounded-lg border border-border bg-surface p-4">
              <ErrorNote
                message={lock.refreshError}
                kind={lock.errorKind}
                requestId={lock.errorRequestId}
                onRetry={lock.reload}
              />
            </div>
          )}
          <ChatScreen
            key={`${courseId}:${identity.audience}:${identity.agentProfile}:${lock.allowedModes.join(",")}:${lock.hintLimit}`}
            courseId={courseId}
            canGiveFeedback={identity.audience === "student"}
            identity={identity}
            allowedModes={lock.allowedModes}
            hintLimit={lock.hintLimit}
          />
        </>
      )}
      {identity !== null && !lock.error && !lock.refreshError && <section className="mt-8 space-y-3 border-t border-border pt-6">
        <h2 className="text-sm font-medium text-fg">Kişisel sohbet geçmişin</h2>
        <p className="prose-tr text-sm text-fg-muted">Silme yalnız senin bu dersteki sohbetlerini kapsar. Sınav kayıtların ve ders materyalleri korunur.</p>
        <ChatHistoryDelete courseId={courseId} sessionId={null} />
      </section>}
    </AppShell>
  );
}

function ChatScreen({
  courseId,
  canGiveFeedback,
  identity,
  allowedModes,
  hintLimit,
}: {
  courseId: string;
  canGiveFeedback: boolean;
  identity: CourseAssistantIdentity;
  allowedModes: ChatUiMode[];
  hintLimit: number;
}) {
  const sessions = usePagedResource<ChatSessionSummary>(
    `/courses/${courseId}/chat/sessions`,
    [courseId],
  );

  const [hiddenSessions, setHiddenSessions] = useState<Set<string>>(() => new Set());
  const [listDeletionNotice, setListDeletionNotice] = useState<string | null>(null);
  const sessionsRef = useRef(sessions); sessionsRef.current = sessions;
  useEffect(() => subscribeChatDeletions(courseId, (scope) => {
    const ids = scope.sessionId === null
      ? (sessionsRef.current.data ?? []).map((session) => session.id) : [scope.sessionId];
    setHiddenSessions((current) => new Set([...current, ...ids]));
    if (scope.sessionId !== null) setListDeletionNotice("Sohbet silindi. Diğer sohbetlerin korundu.");
    // reload invalidates both the first-page request and pending continuation.
    void sessionsRef.current.reload();
  }), [courseId]);
  const visibleSessions = { ...sessions, data: sessions.data?.filter((session) => !hiddenSessions.has(session.id)) ?? null };

  const fetchDocuments = useCallback(
    () =>
      api
        .get<Page<CourseDocument>>(`/courses/${courseId}/documents?limit=100`)
        .then((page) => page.items),
    [courseId],
  );
  const documents = useResource(fetchDocuments, [courseId]);

  const chat = useChatSession({
    courseId,
    identity,
    allowedModes,
    hintLimit,
    sessionList: visibleSessions.data,
    reloadSessions: sessions.reload,
  });

  const blocks = toBlocks(chat.messages, { mode: chat.mode, pending: chat.pending });
  const feedbackByMessage = new Map(
    chat.messages
      .filter((message) => message.role === "assistant")
      .map((message) => [message.id, message.feedback] as const),
  );
  const failedHistorySummary =
    chat.historyCursor === null && chat.sessionId !== null
      ? sessions.data?.find((item) => item.id === chat.sessionId)
      : undefined;
  const retryInitialHistory = failedHistorySummary
    ? () => void chat.openSession(failedHistorySummary)
    : undefined;

  return (
    <>
      <AssistantIdentitySummary
        identity={identity}
        allowedModes={allowedModes}
        hintLimit={hintLimit}
      />
      {/*
       * `minmax(0,1fr)` ve `min-w-0` birlikte zorunlu. Sade `1fr`, `minmax(auto,1fr)`
       * demektir; o `auto`, sütunun içeriğin min-content genişliğinin altına inmesini
       * yasaklar. Telefon genişliğinde (tek sütun) sonuç ölçüldü: kapsayıcı 343px
       * iken ızgara sütunu 551px'e şişiyor ve belge yana kayıyordu. Kabuk ve öbür
       * sayfalar zaten bu deseni kullanıyor.
       */}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
      {/* Konuşma sütunu: okuma genişliği bileşenlerin içinde 70ch ile sınırlı */}
      <div className="min-w-0 space-y-6">
        <LoadMore
          hasMore={chat.historyCursor !== null}
          busy={chat.olderLoading}
          error={chat.historyCursor !== null ? chat.historyError : null}
          onLoadMore={() => void chat.loadOlderMessages()}
        />
        {chat.historyError && chat.historyCursor === null && (
          <ErrorNote
            message={chat.historyError.message}
            kind={chat.historyError.kind}
            requestId={chat.historyError.requestId}
            onRetry={retryInitialHistory}
          />
        )}
        {chat.historyLoading && <Loading label="Sohbet geçmişi yükleniyor…" />}

        {blocks.length === 0 && !chat.historyLoading && (
          <EmptyState title="Ders materyalinden bir soru sorarak başlayın. Her cevap dayandığı sayfayla birlikte gelir; Sokratik modda cevap yerine adım adım ipucu verilir." />
        )}

        <ChatTranscript
          sessionId={chat.sessionId}
          courseId={courseId}
          signature={identity.name}
          canGiveFeedback={canGiveFeedback}
          blocks={blocks}
          feedbackByMessage={feedbackByMessage}
          onSaveFeedback={chat.saveFeedback}
        />

        {chat.sending && <Loading label="Cevap hazırlanıyor…" />}
        {chat.sendError && (
          <ErrorNote
            message={chat.sendError.message}
            kind={chat.sendError.kind}
            requestId={chat.sendError.requestId}
            onRetry={() => void chat.send()}
          />
        )}

        {chat.deletionNotice && <p role="status" className="text-sm text-fg-muted">{chat.deletionNotice}</p>}
        {chat.recoveryError ? <div className="space-y-3">
          <ErrorNote message={chat.recoveryError.message} kind={chat.recoveryError.kind} requestId={chat.recoveryError.requestId} />
          <Button type="button" variant="secondary" onClick={() => window.location.reload()}>Sohbeti yeniden yükle</Button>
        </div> : <ChatComposer
          allowedModes={allowedModes}
          mode={chat.mode}
          sending={chat.sending}
          followUp={chat.followUp}
          draft={chat.draft}
          submittable={chat.submittable}
          onDraftChange={chat.setDraft}
          onSelectMode={chat.startNewSession}
          onSend={() => void chat.send()}
        />}
      </div>

      {/* Kaynak paneli: masaüstünde sabit sütun, mobilde içeriğin altına iner */}
      <aside className="min-w-0 space-y-8">
        <CourseMaterialsSection documents={documents} />
        <SessionListSection
          courseId={courseId}
          sessions={visibleSessions}
          deletionNotice={listDeletionNotice}
          sessionId={chat.sessionId}
          allowedModes={allowedModes}
          identity={identity}
          sending={chat.sending || chat.recoveryError !== null}
          onStartNew={() => chat.startNewSession(chat.mode)}
          onOpenSession={(summary) => void chat.openSession(summary)}
        />
      </aside>
      </div>
    </>
  );
}

/** Döküm blokları: soru balonu, kaynaklı cevap, abstention, Sokratik merdiven. */
function ChatTranscript({
  courseId,
  sessionId,
  canGiveFeedback,
  signature,
  blocks,
  feedbackByMessage,
  onSaveFeedback,
}: {
  courseId: string;
  canGiveFeedback: boolean;
  sessionId: string | null;
  /** Asistan adı; dökümde en fazla bir kez, ilk asistan bloğunun üstünde. */
  signature: string;
  blocks: ChatBlock[];
  feedbackByMessage: Map<string, TranscriptMessage["feedback"]>;
  onSaveFeedback: (
    messageId: string,
    feedback: NonNullable<TranscriptMessage["feedback"]>,
  ) => void;
}) {
  // İmza yalnız ilk asistan bloğunun üstünde: başlık zaten adı taşıyor, her
  // cevapta tekrar etmek dökümü sohbet uygulaması taklidine çevirirdi.
  const firstAssistantId = blocks.find((block) => block.kind !== "question")?.id;
  return (
    <>
      {blocks.map((block) => {
        const signed = block.id === firstAssistantId && <AssistantSignature name={signature} />;
        switch (block.kind) {
          case "question":
            return <QuestionBubble key={block.id} text={block.text} />;
          case "answer":
            return (
              <div key={block.id} className="space-y-3">
                {signed}
                <DemoResponseNotice fixture={block.fixture} />
                <p className="prose-tr text-base whitespace-pre-line text-fg">
                  {demoResponseText(block.text, block.fixture)}
                </p>
                {/*
                  Önbellek dipnotu: rozet değil, satır içi soluk bir not.
                  Önbellek isabeti bir kusur değil tasarlanmış davranıştır, o
                  yüzden ne uyarı tonu ne `role="alert"` var; rozet kullanmamak
                  da bilinçli — kutulanmış bir işaret cevapla dikkat yarışına
                  girerdi, oysa baş aktör cevabın kendisi.
                */}
                {block.cached && (
                  <p className="prose-tr text-xs text-fg-subtle">{CACHED_ANSWER_NOTE}</p>
                )}
                {block.citations.map((citation, index) => (
                  <SourceCard
                    key={`${citation.chunk_id}:${index}`}
                    source={citationSource(citation)}
                    href={sourceContextHref(courseId, citation.chunk_id)}
                    learningContext={{ courseId, chunkId: citation.chunk_id, sessionId }}
                  />
                ))}
                {canGiveFeedback && (
                  <ChatFeedbackControls
                    courseId={courseId}
                    messageId={block.id}
                    initial={feedbackByMessage.get(block.id) ?? null}
                    onSaved={(feedback) => onSaveFeedback(block.id, feedback)}
                  />
                )}
              </div>
            );
          case "abstention":
            return (
              <div key={block.id} className="space-y-3">
                {signed}
                <DemoResponseNotice fixture={block.fixture} />
                <AbstentionBlock status={block.status} message={demoResponseText(block.text, block.fixture)} />
                {canGiveFeedback && (
                  <ChatFeedbackControls
                    courseId={courseId}
                    messageId={block.id}
                    initial={feedbackByMessage.get(block.id) ?? null}
                    onSaved={(feedback) => onSaveFeedback(block.id, feedback)}
                  />
                )}
              </div>
            );
          case "ladder":
            return (
              <div key={block.id} className="space-y-3">
                {signed}
                <SocraticLadder
                  rungs={block.rungs}
                  footerForRung={
                    canGiveFeedback
                      ? (rung) => (
                          <div className="mt-3">
                            <ChatFeedbackControls
                              courseId={courseId}
                              messageId={rung.id}
                              initial={feedbackByMessage.get(rung.id) ?? null}
                              onSaved={(feedback) => onSaveFeedback(rung.id, feedback)}
                            />
                          </div>
                        )
                      : undefined
                  }
                />
              </div>
            );
        }
      })}
    </>
  );
}

/** Besteci: mod seçimi + girdi. Mod oturum ortasında değişemez; seçim yeni oturum açar. */
function ChatComposer({
  allowedModes,
  mode,
  sending,
  followUp,
  draft,
  submittable,
  onDraftChange,
  onSelectMode,
  onSend,
}: {
  allowedModes: ChatUiMode[];
  mode: ChatUiMode;
  sending: boolean;
  followUp: boolean;
  draft: string;
  submittable: boolean;
  onDraftChange: (text: string) => void;
  onSelectMode: (mode: ChatUiMode) => void;
  onSend: () => void;
}) {
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        onSend();
      }}
    >
      <ModeSwitch modes={allowedModes} mode={mode} sending={sending} onSelect={onSelectMode} />

      <div className="flex gap-2">
        {/* Placeholder etiket yerine geçmez (DESIGN.md): etiket gizli ama var. */}
        <label htmlFor="chat-draft" className="sr-only">
          {followUp ? "Denemen" : "Sorun"}
        </label>
        <Input
          id="chat-draft"
          value={draft}
          onChange={(e) => onDraftChange(e.target.value)}
          readOnly={sending}
          aria-disabled={sending}
          maxLength={QUESTION_MAX_LENGTH}
          autoComplete="off"
          placeholder={
            followUp
              ? "Bu ipucuyla ne denedin? Kendi cevabını yaz…"
              : "Ders materyaline soru sorun…"
          }
        />
        <Button type="submit" aria-disabled={sending || !submittable}>
          {sending ? "Gönderiliyor…" : "Gönder"}
        </Button>
      </div>
    </form>
  );
}

/** Ders materyalleri: asistanın cevap verebildiği tek kaynak kümesi. */
function CourseMaterialsSection({
  documents,
}: {
  documents: Resource<CourseDocument[]>;
}) {
  return (
    <Card variant="flat">
      <section className="space-y-3">
        <h2 className="text-sm font-medium text-fg">Bu dersin kaynakları</h2>
        <p className="prose-tr text-xs text-fg-muted">
          Asistan yalnızca eğitmenin yüklediği bu materyallerden cevap verir;
          her cevap sayfa numarasıyla gelir.
        </p>
        {documents.error && (
          <ErrorNote
            message={documents.error}
            kind={documents.errorKind}
            requestId={documents.errorRequestId}
            onRetry={() => void documents.reload()}
          />
        )}
        {documents.refreshError && (
          <ErrorNote
            message={documents.refreshError}
            kind={documents.errorKind}
            requestId={documents.errorRequestId}
            onRetry={() => void documents.reload()}
          />
        )}
        {documents.loading && <Loading label="Materyaller yükleniyor…" />}
        {documents.data?.length === 0 && (
          <p className="prose-tr text-xs text-fg-muted">
            Bu derste henüz materyal yok. Eğitmen materyal yükleyene kadar
            asistan kaynak gösteremez.
          </p>
        )}
        {/* Liste satırları saç çizgisiyle ayrılır (seviye 0); kabuk tek ince çerçeve. */}
        {documents.data && documents.data.length > 0 && (
          <ul className="divide-y divide-border border-t border-border">
            {documents.data.map((doc) => (
              <li key={doc.id} className="py-3">
                <p className="truncate text-sm font-medium text-fg">{doc.file_name}</p>
                <p className="mt-1.5 flex items-center gap-2">
                  <Badge tone={DOCUMENT_STATUS[doc.status].tone}>
                    {DOCUMENT_STATUS[doc.status].label}
                  </Badge>
                  <span className="text-xs tabular-nums text-fg-muted">
                    {doc.page_count === null
                      ? `${doc.chunk_count} parça`
                      : `${doc.page_count} sayfa`}
                  </span>
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </Card>
  );
}

/** Oturum listesi: geçmiş sohbetlere dönüş + yeni sohbet. */
function SessionListSection({
  courseId,
  deletionNotice,
  sessions,
  sessionId,
  allowedModes,
  identity,
  sending,
  onStartNew,
  onOpenSession,
}: {
  courseId: string;
  deletionNotice: string | null;
  sessions: ReturnType<typeof usePagedResource<ChatSessionSummary>>;
  sessionId: string | null;
  allowedModes: ChatUiMode[];
  identity: CourseAssistantIdentity;
  sending: boolean;
  onStartNew: () => void;
  onOpenSession: (summary: ChatSessionSummary) => void;
}) {
  return (
    <Card variant="flat">
      <section className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-medium text-fg">Sohbetlerin</h2>
          <Button
            type="button"
            variant="secondary"
            aria-disabled={sending}
            onClick={() => {
              if (!sending) onStartNew();
            }}
          >
            Yeni sohbet
          </Button>
        </div>
        {deletionNotice && <p role="status" className="text-sm text-fg-muted">{deletionNotice}</p>}
        {sessions.error && (
          <ErrorNote
            message={sessions.error}
            kind={sessions.errorKind}
            requestId={sessions.errorRequestId}
            onRetry={() => void sessions.reload()}
          />
        )}
        {sessions.refreshError && (
          <ErrorNote
            message={sessions.refreshError}
            kind={sessions.errorKind}
            requestId={sessions.errorRequestId}
            onRetry={() => void sessions.reload()}
          />
        )}
        {sessions.loading && <Loading label="Sohbetler yükleniyor…" />}
        {sessions.data?.length === 0 && (
          <p className="text-xs text-fg-muted">Henüz bir sohbet açmadın.</p>
        )}
        {sessions.data && sessions.data.length > 0 && (
          <ul aria-label="Kişisel sohbetler" className="max-h-96 space-y-3 overflow-y-auto">
            {sessions.data.map((summary) => {
              const active = summary.id === sessionId;
              const summaryMode: ChatUiMode | null =
                summary.mode === "exam" ? null : summary.mode;
              const modeAllowed =
                summaryMode !== null && allowedModes.includes(summaryMode);
              const identityAllowed = sessionMatchesAssistant(summary, identity);
              const sessionAllowed = modeAllowed && identityAllowed;
              // Sokratik oturuma dönen öğrenci nerede kaldığını listeden görür.
              // QA'da ve kademesi henüz bildirilmemiş oturumda null döner ve
              // satıra hiçbir şey eklenmez.
              const stage = sessionStageLabel(summary);
              return (
                <li key={summary.id}>
                  <button
                    type="button"
                    aria-current={active ? "true" : undefined}
                    aria-disabled={!sessionAllowed}
                    title={
                      sessionAllowed
                        ? undefined
                        : identityAllowed
                          ? "Bu sohbet modu ders politikasında artık kapalı."
                          : "Bu sohbet farklı bir üyelik profiliyle oluşturulmuş."
                    }
                    onClick={() => {
                      if (sessionAllowed) onOpenSession(summary);
                    }}
                    className={`w-full rounded-lg px-3 py-2 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
                      active
                        ? "bg-surface-sunken font-medium"
                        : "hover:bg-surface-sunken"
                    } ${sessionAllowed ? "" : "cursor-not-allowed opacity-50"}`}
                  >
                    <span className="block truncate text-xs text-fg">
                      {summary.title ?? "Başlıksız sohbet"}
                    </span>
                    <span className="mt-0.5 block text-xs text-fg-subtle">
                      {stage === null
                        ? CHAT_MODE_LABEL[summary.mode]
                        : `${CHAT_MODE_LABEL[summary.mode]} · ${stage}`}
                      {!identityAllowed
                        ? " · Farklı profil"
                        : !modeAllowed
                          ? " · Politika ile kapalı"
                          : ""}
                    </span>
                  </button>
                  {/*
                   * `ChatHistoryDelete` tetikleyicisini ikincil (kenarlıklı) çizer;
                   * liste satırında `ghost sm` ağırlığında durmalı (DESIGN.md
                   * "satır içi eylem"). Kabuk ebeveynden, yalnız doğrudan
                   * tetikleyici (`div > button`) hedeflenerek kurulur; onay
                   * satırındaki Vazgeç / Kalıcı olarak sil daha derindedir ve
                   * etkilenmez. Metin, aria-label, odak ve davranış aynen kalır.
                   */}
                  <div className="mt-1 [&>div>button]:h-9 [&>div>button]:border-transparent [&>div>button]:px-3 [&>div>button]:text-[0.8125rem] [&>div>button]:text-fg-muted [&>div>button:hover]:border-transparent [&>div>button:hover]:bg-surface-sunken [&>div>button:hover]:text-fg">
                    <ChatHistoryDelete courseId={courseId} sessionId={summary.id} title={summary.title ?? "Başlıksız"} />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        <LoadMore
          hasMore={sessions.nextCursor !== null}
          busy={sessions.loadingMore}
          error={sessions.pageError}
          onLoadMore={() => void sessions.loadMore()}
        />
      </section>
    </Card>
  );
}
