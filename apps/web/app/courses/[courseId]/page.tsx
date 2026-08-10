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
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { ErrorNote, Loading, LoadMore, PageHeader } from "@/components/page-state";
import { Badge, Button, Card, ConfirmAction, EmptyState } from "@/components/ui";

export default function CourseDetailPage() {
  return (
    <AppShell>
      <CourseDetail />
    </AppShell>
  );
}

function CourseDetail() {
  const { courseId } = useParams<{ courseId: string }>();
  const { isInstructor } = useSession(courseId);

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

  return (
    <div>
      <nav className="mb-4 text-xs text-fg-subtle">
        <Link href="/courses" className="hover:text-fg">
          Derslerim
        </Link>{" "}
        / <span className="text-fg-muted">{course.code}</span>
      </nav>

      {/* Sekme şeridi diğer beş ders ekranında da başlığın üstünde. */}
      <CourseNav courseId={courseId} />

      <PageHeader
        title={course.title}
        description={`${documents.length} materyal · ${ready} hazır`}
        action={
          isInstructor ? (
            <Link
              href={`/courses/${courseId}/sources`}
              className="inline-flex h-11 items-center rounded-lg border border-border-strong bg-surface px-4 text-sm font-medium text-fg hover:border-fg-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
            >
              Retrieval testi
            </Link>
          ) : undefined
        }
      />

      {isInstructor && (
        <UploadBox
          courseId={courseId}
          documents={documents}
          onUploaded={documentsResource.pulse}
        />
      )}

      {refreshError && <RetryNote message={refreshError} onRetry={() => void reload()} />}

      {documents.length === 0 ? (
        <EmptyState
          title={
            isInstructor
              ? "Henüz ders materyali yok. PDF, sunum veya kod dosyası yükleyerek başlayın."
              : "Eğitmeniniz henüz materyal yüklemedi."
          }
        />
      ) : (
        // Kart yığını değil tek liste: satırlar yalnız ayırıcıyla bölünür
        // (taste-skill: kart ancak gerçek hiyerarşi anlatıyorsa kullanılır).
        <ul className="rise rise-1 divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface">
          {documents.map((doc) => (
            <DocumentRow
              key={doc.id}
              courseId={courseId}
              doc={doc}
              isInstructor={isInstructor}
              onDeleted={documentsResource.pulse}
            />
          ))}
        </ul>
      )}
      <LoadMore
        hasMore={documentsResource.nextCursor !== null}
        busy={documentsResource.loadingMore}
        error={documentsResource.pageError}
        onLoadMore={() => void documentsResource.loadMore()}
      />
    </div>
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
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [replacesDocumentId, setReplacesDocumentId] = useState("");

  async function handleFile(file: File) {
    setBusy(true);
    setError(null);
    try {
      await api.upload(
        `/courses/${courseId}/documents`,
        file,
        replacesDocumentId || null,
      );
      setReplacesDocumentId("");
      onUploaded();
    } catch (e) {
      setError(errorMessage(e, "Yükleme tamamlanamadı."));
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <Card className="mb-6">
      <div className="grid items-end gap-4 md:grid-cols-[1fr_1fr_auto]">
        <div>
          <p className="text-sm font-medium text-fg">Materyal yükle</p>
          <p className="text-xs text-fg-muted">
            PDF, PPTX, Markdown veya kod dosyası · en fazla 20 MB
          </p>
        </div>
        <label className="text-sm text-fg-muted">
          <span className="mb-1 block">Yerine geçtiği belge (isteğe bağlı)</span>
          <select
            value={replacesDocumentId}
            onChange={(event) => setReplacesDocumentId(event.target.value)}
            className="h-11 w-full rounded-lg border border-border-strong bg-surface px-3 text-sm text-fg focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand"
          >
            <option value="">Yeni, bağımsız materyal</option>
            {documents
              .filter((document) => !document.superseded_at)
              .map((document) => (
                <option key={document.id} value={document.id}>
                  {document.file_name}
                </option>
              ))}
          </select>
        </label>
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept=".pdf,.pptx,.md,.txt,.py,.java,.js,.ts,.c,.h,.cpp"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
        />
        <Button disabled={busy} onClick={() => inputRef.current?.click()}>
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
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);
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
      <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-4">
        <div className="min-w-0">
          <p className="truncate font-mono text-sm text-fg">{doc.file_name}</p>
          <p className="mt-0.5 text-xs text-fg-subtle">
            {formatBytes(doc.byte_size)}
            {doc.page_count ? ` · ${doc.page_count} sayfa` : ""}
            {doc.status === "completed" ? ` · ${doc.chunk_count} parça` : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={status.tone}>{status.label}</Badge>
          {doc.superseded_at && <Badge tone="warning">Eski sürüm</Badge>}
          {isInstructor && doc.status === "completed" && (
            <Button
              variant="ghost"
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
              aria-disabled={retrying}
              onClick={async () => {
                setRetrying(true);
                setRetryError(null);
                try {
                  await api.post(`/courses/${courseId}/documents/${doc.id}/retry`);
                  onDeleted();
                } catch (error) {
                  setRetryError(errorMessage(error, "Belge yeniden kuyruğa alınamadı."));
                } finally {
                  setRetrying(false);
                }
              }}
            >
              {retrying ? "Kuyruğa alınıyor…" : "Yeniden işle"}
            </Button>
          )}
          {isInstructor && (
            <ConfirmAction
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

      {retryError && (
        <div className="border-t border-border px-6 py-2">
          <ErrorNote message={retryError} />
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
      <p id={id} className="border-t border-border bg-bg px-6 py-4 text-sm text-fg-muted">
        Bu belgeden parça çıkarılmamış.
      </p>
    );
  }
  return (
    <div id={id} className="space-y-2 border-t border-border bg-bg px-6 py-4">
      {chunks.slice(0, 5).map((chunk) => (
        <div key={chunk.id} className="border-l-2 border-border-strong py-1 pl-4">
          <p className="text-xs text-fg-subtle">
            {chunkLocation(chunk)} · {chunk.token_count} token
          </p>
          <p
            className={`prose-tr mt-1 line-clamp-3 text-sm text-fg-muted ${
              chunk.content_type === "code" ? "font-mono text-xs" : ""
            }`}
          >
            {chunk.text}
          </p>
        </div>
      ))}
      {chunks.length > 5 && (
        <p className="pl-4 text-xs text-fg-subtle">
          ve {chunks.length - 5} parça daha
        </p>
      )}
    </div>
  );
}
