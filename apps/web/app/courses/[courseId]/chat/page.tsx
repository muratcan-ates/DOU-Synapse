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
 * Saf mantık (istek gövdesi, kademe eşlemesi, döküm blokları) `lib/chat.ts`'te
 * ve `lib/chat.test.ts` ile sınanıyor; burada yalnız durum ve yerleşim var.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import {
  buildChatRequest,
  CACHED_ANSWER_NOTE,
  canSubmitDraft,
  CHAT_MODE_LABEL,
  CHAT_UI_MODES,
  citationSource,
  fromAnswer,
  fromHistory,
  isSocraticFollowUp,
  openSessionKey,
  QUESTION_MAX_LENGTH,
  sessionStageLabel,
  toBlocks,
  userMessage,
  type ChatUiMode,
  type TranscriptMessage,
} from "@/lib/chat";
import { errorMessage } from "@/lib/errors";
import { DOCUMENT_STATUS } from "@/lib/labels";
import type {
  ChatAnswer,
  ChatMessage,
  ChatSessionSummary,
  CourseDocument,
  Page,
} from "@/lib/types";
import { useChatAvailability } from "@/lib/chat-availability";
import { pagedPath, usePagedResource } from "@/lib/use-paged-resource";
import { useResource } from "@/lib/use-resource";
import { sourceContextHref } from "@/lib/source-quality";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { ErrorNote, Loading, LoadMore } from "@/components/page-state";
import { SocraticLadder } from "@/components/socratic-ladder";
import { AbstentionNotice, SourceCard } from "@/components/source-card";
import { Badge, Button, EmptyState, Input } from "@/components/ui";

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
      {lock.locked ? (
        <EmptyState title={lock.message ?? "Asistan şu anda kullanılamıyor."} />
      ) : (
        <ChatScreen courseId={courseId} />
      )}
    </AppShell>
  );
}

function ChatScreen({ courseId }: { courseId: string }) {
  const [mode, setMode] = useState<ChatUiMode>("qa");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<TranscriptMessage[]>([]);
  const [draft, setDraft] = useState("");
  /** Uçuştaki soru — sunucu onaylamadan dökümde yer tutar. */
  const [pending, setPending] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyCursor, setHistoryCursor] = useState<string | null>(null);
  const [olderLoading, setOlderLoading] = useState(false);

  const sessions = usePagedResource<ChatSessionSummary>(
    `/courses/${courseId}/chat/sessions`,
    [courseId],
  );

  const fetchDocuments = useCallback(
    () =>
      api
        .get<Page<CourseDocument>>(`/courses/${courseId}/documents?limit=100`)
        .then((page) => page.items),
    [courseId],
  );
  const documents = useResource(fetchDocuments, [courseId]);

  /*
   * Uçuştaki geçmiş isteğini geçersizleştiren sayaç.
   *
   * Hızlı iki tıklamada birinci oturumun geç gelen yanıtı ikincinin dökümünü
   * eziyordu: ekranda A oturumu seçili, içerik B'nin. Sayaç, gecikmiş yanıtı
   * sessizce düşürür.
   */
  const historyToken = useRef(0);

  const openSession = useCallback(
    async (summary: ChatSessionSummary) => {
      const token = ++historyToken.current;
      setSessionId(summary.id);
      // Sohbet ucu `exam` kabul etmiyor; yine de tip daraltması burada yapılır.
      setMode(summary.mode === "socratic" ? "socratic" : "qa");
      setMessages([]);
      setPending(null);
      setSendError(null);
      setHistoryError(null);
      setHistoryLoading(true);
      setHistoryCursor(null);
      try {
        const history = await api.get<Page<ChatMessage>>(
          `/courses/${courseId}/chat/sessions/${summary.id}`,
        );
        if (historyToken.current !== token) return;
        setMessages(fromHistory(history.items));
        setHistoryCursor(history.next_cursor);
        localStorage.setItem(openSessionKey(courseId), summary.id);
      } catch (e) {
        if (historyToken.current !== token) return;
        setHistoryError(errorMessage(e));
      } finally {
        if (historyToken.current === token) setHistoryLoading(false);
      }
    },
    [courseId],
  );

  /*
   * Sayfa yenilenince açık oturum geri açılır. Anahtar ders bazlıdır: başka
   * dersin oturumunu açmak RLS'ten zaten dönmez ama kullanıcıya boş bir hata
   * göstermenin anlamı yok — liste kontrolü bunu baştan eler.
   */
  const restoredFor = useRef<string | null>(null);
  useEffect(() => {
    if (restoredFor.current === courseId) return;
    const list = sessions.data;
    if (list === null) return;
    restoredFor.current = courseId;
    const storedId = localStorage.getItem(openSessionKey(courseId));
    const target = list.find((summary) => summary.id === storedId);
    if (target) void openSession(target);
  }, [courseId, sessions.data, openSession]);

  /** Yeni oturum: mod değişimi de buradan geçer — mod ortada değiştirilemez. */
  const startNewSession = (nextMode: ChatUiMode) => {
    historyToken.current++;
    setMode(nextMode);
    setSessionId(null);
    setMessages([]);
    setPending(null);
    setSendError(null);
    setHistoryError(null);
    setHistoryLoading(false);
    setHistoryCursor(null);
    localStorage.removeItem(openSessionKey(courseId));
    // Yazılmış metin korunur: mod değiştirmek yazdığını silmek için bir sebep değil.
  };

  const loadOlderMessages = useCallback(async () => {
    if (!sessionId || !historyCursor || olderLoading) return;
    setOlderLoading(true);
    setHistoryError(null);
    try {
      const older = await api.get<Page<ChatMessage>>(
        pagedPath(`/courses/${courseId}/chat/sessions/${sessionId}`, historyCursor),
      );
      setMessages((current) => [...fromHistory(older.items), ...current]);
      setHistoryCursor(older.next_cursor);
    } catch (error) {
      setHistoryError(errorMessage(error));
    } finally {
      setOlderLoading(false);
    }
  }, [courseId, historyCursor, olderLoading, sessionId]);

  const openingQuestion =
    messages.find((message) => message.role === "user")?.content ?? null;
  const followUp = isSocraticFollowUp({ mode, sessionId, openingQuestion });
  const submittable = canSubmitDraft(draft, followUp);

  const send = async () => {
    if (sending || !submittable) return;
    const text = draft.trim();
    const body = buildChatRequest({ mode, draft: text, sessionId, openingQuestion });
    const isNewSession = sessionId === null;

    setSending(true);
    setSendError(null);
    setPending(text);
    setDraft("");
    try {
      const answer = await api.post<ChatAnswer>(`/courses/${courseId}/chat`, body);
      setMessages((prev) => [
        ...prev,
        // Kullanıcı mesajının kimliği zarfta yok; asistan kimliğinden türetiliyor.
        userMessage(`user:${answer.message_id}`, text),
        fromAnswer(answer),
      ]);
      setSessionId(answer.session_id);
      localStorage.setItem(openSessionKey(courseId), answer.session_id);
      setPending(null);
      /*
       * Liste yalnız GERÇEKTEN değiştiyse tazelenir (Anayasa XI). İki durum
       * değiştirir:
       *  - yeni oturum açılması (listede yeni satır),
       *  - Sokratik kademenin ilerlemesi — kademe artık listede de yazıyor ve
       *    tazelenmezse aktif satır merdivenle çelişir: solda "Tanı", sağdaki
       *    merdivende "Yönlendirme". Ekranda birbirini yalanlayan iki gösterge
       *    olmasındansa bir GET fazladan atılır.
       * Kademe değişmediyse (aynı kademede ikinci ipucu) istek atılmaz.
       */
      const listedStage =
        sessions.data?.find((s) => s.id === answer.session_id)?.socratic_stage ?? null;
      if (isNewSession || answer.socratic_stage !== listedStage) void sessions.reload();
    } catch (e) {
      // Konuşma geçmişi DURUR; yalnız gönderilemeyen tur geri alınır ve metin
      // girdiye iade edilir — yazdığını kaybetmek hatanın cezası olmamalı.
      setSendError(errorMessage(e));
      setPending(null);
      setDraft(text);
    } finally {
      setSending(false);
    }
  };

  const blocks = toBlocks(messages, { mode, pending });

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      {/* Konuşma sütunu: okuma genişliği bileşenlerin içinde 70ch ile sınırlı */}
      <div className="space-y-6">
        <LoadMore
          hasMore={historyCursor !== null}
          busy={olderLoading}
          onLoadMore={() => void loadOlderMessages()}
        />
        {historyError && <ErrorNote message={historyError} />}
        {historyLoading && <Loading label="Sohbet geçmişi yükleniyor…" />}

        {blocks.length === 0 && !historyLoading && (
          <EmptyState title="Ders materyalinden bir soru sorarak başlayın. Her cevap dayandığı sayfayla birlikte gelir; Sokratik modda cevap yerine adım adım ipucu verilir." />
        )}

        {blocks.map((block) => {
          switch (block.kind) {
            case "question":
              return (
                <div key={block.id} className="flex justify-end">
                  <p className="max-w-[85%] rounded-lg bg-surface px-4 py-3 text-sm whitespace-pre-line text-fg">
                    {block.text}
                  </p>
                </div>
              );
            case "answer":
              return (
                <div key={block.id} className="space-y-3">
                  <p className="prose-tr text-base whitespace-pre-line text-fg">
                    {block.text}
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
                    />
                  ))}
                </div>
              );
            case "abstention":
              return (
                <AbstentionNotice
                  key={block.id}
                  status={block.status}
                  message={block.text}
                />
              );
            case "ladder":
              return <SocraticLadder key={block.id} rungs={block.rungs} />;
          }
        })}

        {sending && <Loading label="Cevap hazırlanıyor…" />}
        {sendError && <ErrorNote message={sendError} />}

        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
        >
          <div
            role="group"
            aria-label="Sohbet modu"
            className="flex w-fit gap-1 rounded-lg border border-border p-1"
          >
            {CHAT_UI_MODES.map((value) => {
              const active = mode === value;
              return (
                <button
                  key={value}
                  type="button"
                  aria-pressed={active}
                  disabled={sending}
                  onClick={() => {
                    // Mod oturum ortasında değişemez (sunucu 422 döner): değişim
                    // yeni oturum açar, hata göstermez.
                    if (!active) startNewSession(value);
                  }}
                  className={`h-8 rounded-md border px-3 text-xs transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:opacity-40 ${
                    active
                      ? "border-border-strong bg-surface font-medium text-fg"
                      : "border-transparent text-fg-muted hover:text-fg"
                  }`}
                >
                  {CHAT_MODE_LABEL[value]}
                </button>
              );
            })}
          </div>

          <div className="flex gap-2">
            {/* Placeholder etiket yerine geçmez (DESIGN.md): etiket gizli ama var. */}
            <label htmlFor="chat-draft" className="sr-only">
              {followUp ? "Denemen" : "Sorun"}
            </label>
            <Input
              id="chat-draft"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              disabled={sending}
              maxLength={QUESTION_MAX_LENGTH}
              autoComplete="off"
              placeholder={
                followUp
                  ? "Bu ipucuyla ne denedin? Kendi cevabını yaz…"
                  : "Ders materyaline soru sorun…"
              }
            />
            <Button type="submit" disabled={sending || !submittable}>
              {sending ? "Gönderiliyor…" : "Gönder"}
            </Button>
          </div>
        </form>
      </div>

      {/* Kaynak paneli: masaüstünde sabit sütun, mobilde içeriğin altına iner */}
      <aside className="space-y-8">
        <section className="space-y-3">
          <h2 className="text-sm font-medium text-fg">Bu dersin kaynakları</h2>
          <p className="prose-tr text-xs text-fg-muted">
            Asistan yalnızca eğitmenin yüklediği bu materyallerden cevap verir;
            her cevap sayfa numarasıyla gelir.
          </p>
          {documents.error && <ErrorNote message={documents.error} />}
          {documents.loading && <Loading label="Materyaller yükleniyor…" />}
          {documents.data?.length === 0 && (
            <p className="prose-tr text-xs text-fg-muted">
              Bu derste henüz materyal yok. Eğitmen materyal yükleyene kadar
              asistan kaynak gösteremez.
            </p>
          )}
          {documents.data && documents.data.length > 0 && (
            <ul className="space-y-2">
              {documents.data.map((doc) => (
                <li
                  key={doc.id}
                  className="rounded-lg border border-border bg-surface px-3 py-2"
                >
                  <p className="truncate font-mono text-xs text-fg">{doc.file_name}</p>
                  <p className="mt-1.5 flex items-center gap-2">
                    <Badge tone={DOCUMENT_STATUS[doc.status].tone}>
                      {DOCUMENT_STATUS[doc.status].label}
                    </Badge>
                    <span className="text-xs text-fg-muted">
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

        <section className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-medium text-fg">Sohbetlerin</h2>
            <Button
              type="button"
              variant="secondary"
              disabled={sending}
              onClick={() => startNewSession(mode)}
            >
              Yeni sohbet
            </Button>
          </div>
          {sessions.error && <ErrorNote message={sessions.error} />}
          {sessions.loading && <Loading label="Sohbetler yükleniyor…" />}
          {sessions.data?.length === 0 && (
            <p className="text-xs text-fg-muted">Henüz bir sohbet açmadın.</p>
          )}
          {sessions.data && sessions.data.length > 0 && (
            <ul className="max-h-72 space-y-1 overflow-y-auto">
              {sessions.data.map((summary) => {
                const active = summary.id === sessionId;
                // Sokratik oturuma dönen öğrenci nerede kaldığını listeden görür.
                // QA'da ve kademesi henüz bildirilmemiş oturumda null döner ve
                // satıra hiçbir şey eklenmez.
                const stage = sessionStageLabel(summary);
                return (
                  <li key={summary.id}>
                    <button
                      type="button"
                      aria-current={active ? "true" : undefined}
                      onClick={() => void openSession(summary)}
                      className={`w-full rounded-lg border px-3 py-2 text-left transition-colors ${
                        active
                          ? "border-border-strong bg-surface"
                          : "border-transparent hover:bg-surface"
                      }`}
                    >
                      <span className="block truncate text-xs text-fg">
                        {summary.title ?? "Başlıksız sohbet"}
                      </span>
                      <span className="mt-0.5 block text-xs text-fg-subtle">
                        {stage === null
                          ? CHAT_MODE_LABEL[summary.mode]
                          : `${CHAT_MODE_LABEL[summary.mode]} · ${stage}`}
                      </span>
                    </button>
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
      </aside>
    </div>
  );
}
