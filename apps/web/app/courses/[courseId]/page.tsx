"use client";

/**
 * Ders detayı: materyal listesi, yükleme ve işlenme durumu.
 *
 * İşlenme durumu belirsiz spinner değil, durum rozetiyle gösterilir; işlenen
 * belge varken 2 sn'de bir tazelenir, bitince durur (DESIGN.md: uzun ingestion
 * "takıldı" hissi vermemeli).
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useRef, useState } from "react";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { chunkLocation, DOCUMENT_STATUS, formatBytes } from "@/lib/labels";
import { useSession } from "@/lib/session";
import type { ChunkPreview, Course, CourseDocument } from "@/lib/types";
import { usePagedResource } from "@/lib/use-paged-resource";
import { useResource } from "@/lib/use-resource";
import { useSubmit } from "@/lib/use-submit";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { ErrorNote, Loading, LoadMore, PageHeader } from "@/components/page-state";
import { Field } from "@/components/field";
import { ChevronRightIcon, FileIcon } from "@/components/icons";
import { Badge, Button, Card, ConfirmAction, EmptyState, Input, Select } from "@/components/ui";
import { useChatAvailability, type ChatLock } from "@/lib/chat-availability";
import {
  courseAssistantWorkPath,
  resolveCourseAssistantIdentity,
  type CourseAssistantIdentity,
} from "@/lib/course-assistant";

export default function CourseDetailPage() {
  return (
    <AppShell>
      <CourseDetail />
    </AppShell>
  );
}

function CourseDetail() {
  const { courseId } = useParams<{ courseId: string }>();
  const { isInstructor, ready: sessionReady } = useSession(courseId);
  const [documentQuery, setDocumentQuery] = useState("");
  const chatAccess = useChatAvailability(sessionReady ? courseId : null);

  const fetchCourse = useCallback(() => api.get<Course>(`/courses/${courseId}`), [courseId]);
  const courseResource = useResource(fetchCourse, [courseId]);
  const documentsResource = usePagedResource<CourseDocument>(
    `/courses/${courseId}/documents`,
    [courseId],
    {
    // İşlenmeyi bekleyen belge varken tazele; hepsi bitince dur.
      pollWhile: (documents) =>
        documents.some((d) => d.status === "uploaded" || d.status === "processing"),
    },
  );

  // Sayfa 2 sn'de bir tazelendiği için başarısız tek istek sıradan: elde sağlam
  // liste varken başlık, sekmeler ve satırlar kalır, hata listenin üstüne iner.
  const blockingError = courseResource.error ?? documentsResource.error;
  const reload = async () => {
    await Promise.all([courseResource.reload(), documentsResource.reload()]);
  };
  if (blockingError && (!courseResource.data || !documentsResource.data))
    return <RetryNote message={blockingError} onRetry={() => void reload()} />;
  if (!courseResource.data || !documentsResource.data) return <Loading />;

  const course = courseResource.data;
  const documents = documentsResource.data;
  const refreshError = courseResource.refreshError ?? documentsResource.refreshError;
  const ready = documents.filter((d) => d.status === "completed").length;
  const visibleDocuments = documents.filter((document) =>
    document.file_name.toLocaleLowerCase("tr-TR").includes(documentQuery.trim().toLocaleLowerCase("tr-TR")),
  );
  const assistantIdentity = resolveCourseAssistantIdentity(
    chatAccess.audience,
    chatAccess.agentProfile,
  );

  return (
    <div>
      <nav className="mb-5 flex items-center gap-2 text-sm text-fg-subtle">
        <Link href="/courses" className="hover:text-fg">
          Derslerim
        </Link>{" "}
        <ChevronRightIcon size={15} /> <span className="font-medium text-fg-muted">{course.code}</span>
      </nav>

      {/* Sekme şeridi diğer beş ders ekranında da başlığın üstünde. */}
      <CourseNav courseId={courseId} lock={chatAccess} />

      <PageHeader
        title={course.title}
        description={`${documents.length} materyal · ${ready} hazır`}
        action={
          isInstructor ? (
            <Link
              href={`/courses/${courseId}/sources`}
              className="inline-flex h-11 items-center rounded-lg border border-border-strong bg-surface px-4 text-sm font-medium text-fg hover:border-fg-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
            >
              Kaynakları dene
            </Link>
          ) : undefined
        }
      />

      <div className="grid items-start gap-7 xl:grid-cols-[minmax(0,1fr)_320px]">
        <section aria-labelledby="materials-title" className="min-w-0">
          {isInstructor && (
            <UploadBox courseId={courseId} documents={documents} onUploaded={documentsResource.pulse} />
          )}
          {refreshError && <RetryNote message={refreshError} onRetry={() => void reload()} />}
          <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 id="materials-title" className="text-xl font-semibold text-fg">Ders materyalleri</h2>
              <p className="mt-1 text-sm text-fg-muted">Asistanın yanıtlarına dayanak olan ders kaynakları.</p>
            </div>
            {documents.length > 0 && (
              <Input
                aria-label="Materyallerde ara"
                placeholder="Dosya adıyla ara"
                className="w-full sm:max-w-64"
                type="search"
                value={documentQuery}
                onChange={(event) => setDocumentQuery(event.target.value)}
              />
            )}
          </div>
          {documents.length === 0 ? (
            <EmptyState
              title={isInstructor
                ? "Henüz ders materyali yok. PDF, sunum veya kod dosyası yükleyerek başlayın."
                : "Eğitmeniniz henüz materyal yüklemedi."}
            />
          ) : visibleDocuments.length === 0 ? (
            <EmptyState title="Bu adla eşleşen materyal bulunamadı." action={
              <Button variant="secondary" onClick={() => setDocumentQuery("")}>Aramayı temizle</Button>
            } />
          ) : (
            <ul className="rise divide-y divide-border overflow-hidden rounded-[20px] border border-border bg-surface shadow-e1">
              {visibleDocuments.map((doc) => (
                <DocumentRow key={doc.id} courseId={courseId} doc={doc} isInstructor={isInstructor} onDeleted={documentsResource.pulse} />
              ))}
            </ul>
          )}
          {documentQuery && documentsResource.nextCursor !== null && (
            <p className="mt-3 text-sm text-fg-muted">Arama yüklenen materyaller içindedir. Daha fazla materyal yükleyerek aramayı genişletebilirsiniz.</p>
          )}
          <LoadMore
            hasMore={documentsResource.nextCursor !== null}
            busy={documentsResource.loadingMore}
            error={documentsResource.pageError}
            onLoadMore={() => void documentsResource.loadMore()}
          />
        </section>
        {sessionReady && chatAccess.ready && assistantIdentity && (
          <aside className="min-w-0 xl:sticky xl:top-28">
            <ProductRoles courseId={courseId} identity={assistantIdentity} access={chatAccess} />
          </aside>
        )}
      </div>
    </div>
  );
}

function ProductRoles({
  courseId,
  identity,
  access,
}: {
  courseId: string;
  identity: CourseAssistantIdentity;
  access: ChatLock;
}) {
  const isInstructor = identity.audience === "instructor";
  const primary = courseAssistantWorkPath(
    courseId,
    identity,
    access.locked,
    access.message,
  );
  const secondary = isInstructor
    ? [
        {
          task: "Sınav planı ve onaylı soru havuzunu yönet",
          description: "Sınav kapsamını sürümleyin; soruları öğrenciye açmadan önce inceleyin.",
          href: `/courses/${courseId}/blueprints`,
          action: "Sınav planına git",
        },
        {
          task: "Öğrenme durumunu toplu görünümde incele",
          description: "Kişisel sohbet içeriğini açmadan zorlanılan alanları izleyin.",
          href: `/courses/${courseId}/analytics`,
          action: "Analitiği aç",
        },
      ]
    : [
        {
          task: "Onaylı sorularla kendini dene",
          description: "Süreli prova yapın; puanı ve neden yanlış analizini görün.",
          href: `/courses/${courseId}/exam`,
          action: "Sınav provasına git",
        },
        {
          task: "Konu durumunu gözden geçir",
          description: "Hangi konularda ilerlediğinizi ve nerede yeniden çalışmanız gerektiğini görün.",
          href: `/courses/${courseId}/analytics`,
          action: "İlerlemeyi aç",
        },
      ];

  return (
    <section className="overflow-hidden rounded-[20px] border border-border bg-surface shadow-e1" aria-labelledby="ai-roles-title">
      <div className="border-b border-border p-6">
        <h2 id="ai-roles-title" className="text-xl font-semibold text-fg">Bu derste çalışma yolları</h2>
        <p className="mt-2 text-sm leading-relaxed text-fg-muted">Dersinizin kaynaklarıyla öğrenmeye devam edin.</p>
      </div>
      <div className="p-6">
        <h3 className="text-lg font-semibold leading-snug text-fg">{primary.task}</h3>
        <p className="mt-3 text-sm leading-relaxed text-fg-muted">{primary.description}</p>
        {primary.href ? (
          <Link href={primary.href} className="mt-5 inline-flex min-h-11 w-full items-center justify-between gap-3 rounded-xl bg-brand px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand dark:text-bg">
            {primary.action}<ChevronRightIcon size={18} />
          </Link>
        ) : (
          <p role="status" className="mt-5 rounded-xl bg-surface-sunken p-4 text-sm leading-relaxed text-fg-muted">{primary.action}</p>
        )}
      </div>
      <div className="divide-y divide-border border-t border-border">
        {secondary.map((role) => (
          <div key={role.href} className="p-6">
            <h3 className="font-medium text-fg">{role.task}</h3>
            <p className="mt-2 text-sm leading-relaxed text-fg-muted">{role.description}</p>
            <Link href={role.href} className="mt-3 inline-flex min-h-11 items-center gap-2 rounded-lg text-sm font-semibold text-brand transition-colors hover:text-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">
              {role.action}<ChevronRightIcon size={16} />
            </Link>
          </div>
        ))}
      </div>
    </section>
  );
}

/** Hata + çıkış yolu: hatayı gösterip kullanıcıyı elle yenilemeye mahkûm etmemek için. */
function RetryNote({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-3">
      <ErrorNote message={message} />
      <Button variant="secondary" onClick={onRetry}>
        Tekrar dene
      </Button>
    </div>
  );
}

function UploadBox({
  courseId,
  documents,
  onUploaded,
}: {
  courseId: string;
  documents: CourseDocument[];
  /** Yazma sonrası kısa tazeleme penceresi açar — tek `reload` yarışı kaybediyor. */
  onUploaded: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [replacesDocumentId, setReplacesDocumentId] = useState("");

  const { busy, error, submit: handleFile } = useSubmit(async (file: File) => {
    try {
      await api.upload(
        `/courses/${courseId}/documents`,
        file,
        replacesDocumentId || null,
      );
      setReplacesDocumentId("");
      onUploaded();
    } finally {
      // Hata yolunda da temizlenir: aynı dosya yeniden seçilebilmeli.
      if (inputRef.current) inputRef.current.value = "";
    }
  }, "Yükleme tamamlanamadı.");

  return (
    <Card className="mb-7">
      {/* Başlık ve etiketli kontroller aynı çalışma panelinde hizalanır. */}
      <div className="mb-4">
        <p className="text-xl font-semibold text-fg">Materyal yükle</p>
        <p className="mt-2 text-sm text-fg-muted">
          PDF, PPTX, Markdown veya kod dosyası · en fazla 20 MB
        </p>
      </div>
      <div className="grid items-end gap-4 sm:grid-cols-[minmax(0,1fr)_auto]">
        <Field label="Yerine geçtiği belge (isteğe bağlı)">
          {(control) => (
            <Select
              {...control}
              value={replacesDocumentId}
              onChange={(event) => setReplacesDocumentId(event.target.value)}
            >
              <option value="">Yeni, bağımsız materyal</option>
              {documents
                .filter((document) => !document.superseded_at)
                .map((document) => (
                  <option key={document.id} value={document.id}>
                    {document.file_name}
                  </option>
                ))}
            </Select>
          )}
        </Field>
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept=".pdf,.pptx,.md,.txt,.py,.java,.js,.ts,.c,.h,.cpp"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void handleFile(file);
          }}
        />
        {/* İkincil: sayfadaki tek kırmızı buton "Asistanı aç" (birincil eylem). */}
        <Button
          variant="secondary"
          aria-disabled={busy}
          onClick={() => {
            if (busy) return;
            inputRef.current?.click();
          }}
        >
          {busy ? "Yükleniyor…" : "Dosya seç"}
        </Button>
      </div>
      {error && (
        <div className="mt-2">
          <ErrorNote message={error} />
        </div>
      )}
    </Card>
  );
}

function DocumentRow({
  courseId,
  doc,
  isInstructor,
  onDeleted,
}: {
  courseId: string;
  doc: CourseDocument;
  isInstructor: boolean;
  onDeleted: () => void;
}) {
  const [chunks, setChunks] = useState<ChunkPreview[] | null>(null);
  const [open, setOpen] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const retry = useSubmit(async () => {
    await api.post(`/courses/${courseId}/documents/${doc.id}/retry`);
    onDeleted();
  }, "Belge yeniden kuyruğa alınamadı.");
  const status = DOCUMENT_STATUS[doc.status];
  const panelId = `chunks-${doc.id}`;

  async function togglePreview() {
    if (open) {
      setOpen(false);
      return;
    }
    // Önceki denemenin hatası ekranda kalmasın: bu kez istek başarılıyken de
    // panelin altında durup bir şey bozukmuş gibi görünüyordu.
    setPreviewError(null);
    if (chunks === null) {
      try {
        setChunks(
          await api.get<ChunkPreview[]>(
            `/courses/${courseId}/documents/${doc.id}/chunks`,
          ),
        );
      } catch (e) {
        // Önizleme çekilemezse panel açılmaz; sessizce boş açılırsa kullanıcı
        // "parça yok" sanır — oysa yalnız istek başarısız oldu.
        setPreviewError(errorMessage(e, "Önizleme alınamadı."));
        return;
      }
    }
    setOpen(true);
  }

  return (
    <li>
      <div className="flex flex-col gap-4 px-5 py-5 sm:px-6">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-surface-sunken text-fg-muted"><FileIcon size={22} /></span>
          <div className="min-w-0 flex-1">
            <p className="break-words font-medium leading-relaxed text-fg">{doc.file_name}</p>
            <p className="mt-1 text-sm tabular-nums text-fg-subtle">
              {formatBytes(doc.byte_size)}
              {doc.page_count ? ` · ${doc.page_count} sayfa` : ""}
              {doc.status === "completed" ? ` · ${doc.chunk_count} parça` : ""}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:pl-14">
          <Badge tone={status.tone}>{status.label}</Badge>
          {doc.superseded_at && <Badge tone="warning">Eski sürüm</Badge>}
          {isInstructor && doc.status === "completed" && (
            <Button
              variant="secondary"
              size="sm"
              aria-expanded={open}
              aria-controls={open ? panelId : undefined}
              onClick={togglePreview}
            >
              {open ? "Gizle" : "İçerik önizle"}
            </Button>
          )}
          {isInstructor && doc.status === "failed" && (
            <Button
              variant="secondary"
              size="sm"
              aria-disabled={retry.busy}
              onClick={() => void retry.submit()}
            >
              {retry.busy ? "Kuyruğa alınıyor…" : "Yeniden işle"}
            </Button>
          )}
          {isInstructor && (
            <ConfirmAction
              size="sm"
              label="Sil"
              confirmLabel="Evet, sil"
              busyLabel="Siliniyor…"
              question="Materyal ve tüm parçaları silinecek."
              ariaLabel={`${doc.file_name} dosyasını sil`}
              onConfirm={async () => {
                await api.delete(`/courses/${courseId}/documents/${doc.id}`);
                // Tam sayfa yenileme yerine listeyi tazele: sayfa konumu ve
                // açık önizlemeler korunur, ağ trafiği tek isteğe iner.
                onDeleted();
              }}
            />
          )}
        </div>
      </div>

      {doc.status === "failed" && doc.error_message && (
        <p className="border-t border-border px-6 py-2 text-sm text-danger">
          {doc.error_message}
        </p>
      )}

      {retry.error && (
        <div className="border-t border-border px-6 py-2">
          <ErrorNote message={retry.error} />
        </div>
      )}

      {previewError && (
        // Ortak bileşen: `role="alert"` ve ton tek yerden gelir.
        <div className="border-t border-border px-6 py-2">
          <ErrorNote message={previewError} />
        </div>
      )}

      {open && chunks && <ChunkPreviewList id={panelId} chunks={chunks} />}
    </li>
  );
}

/**
 * Parça önizlemesi — ürünün tezinin görünür kanıtı: her parçanın yanında
 * hangi sayfadan geldiği yazar. Atıflar bu metadata'dan üretilir, model
 * metninden değil.
 */
function ChunkPreviewList({ id, chunks }: { id: string; chunks: ChunkPreview[] }) {
  if (chunks.length === 0) {
    return (
      <p id={id} className="border-t border-border px-6 py-4 text-sm text-fg-muted">
        Bu belgeden parça çıkarılmamış.
      </p>
    );
  }
  return (
    <div id={id} className="space-y-3 border-t border-border bg-bg px-5 py-5 sm:px-6">
      {chunks.slice(0, 5).map((chunk) => (
        // Ray değil çukur blok: parça, kartın altında duran alıntı yüzeyidir.
        <div key={chunk.id} className="rounded-xl border border-border bg-surface px-4 py-4">
          <p className="text-sm tabular-nums text-fg-subtle">
            {chunkLocation(chunk)} · {chunk.token_count} token
          </p>
          <p
            className={`prose-tr mt-2 line-clamp-3 text-base text-fg-muted ${
              chunk.content_type === "code" ? "font-mono text-xs" : ""
            }`}
          >
            {chunk.text}
          </p>
        </div>
      ))}
      {chunks.length > 5 && (
        <p className="px-3 text-xs tabular-nums text-fg-subtle">
          ve {chunks.length - 5} parça daha
        </p>
      )}
    </div>
  );
}
