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
import { useResource } from "@/lib/use-resource";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { ErrorNote, Loading, PageHeader } from "@/components/page-state";
import { Badge, Button, Card, EmptyState } from "@/components/ui";

interface CourseView {
  course: Course;
  documents: CourseDocument[];
}

export default function CourseDetailPage() {
  return (
    <AppShell>
      <CourseDetail />
    </AppShell>
  );
}

function CourseDetail() {
  const { courseId } = useParams<{ courseId: string }>();
  const { isInstructor } = useSession();

  const fetchView = useCallback(async (): Promise<CourseView> => {
    const [course, documents] = await Promise.all([
      api.get<Course>(`/courses/${courseId}`),
      api.get<CourseDocument[]>(`/courses/${courseId}/documents`),
    ]);
    return { course, documents };
  }, [courseId]);

  const { data, error, loading, reload } = useResource(fetchView, [courseId], {
    // İşlenmeyi bekleyen belge varken tazele; hepsi bitince dur.
    pollWhile: (v) =>
      v.documents.some((d) => d.status === "uploaded" || d.status === "processing"),
  });

  if (error) return <ErrorNote message={error} />;
  if (loading || !data) return <Loading />;

  const { course, documents } = data;
  const ready = documents.filter((d) => d.status === "completed").length;

  return (
    <div>
      <nav className="mb-4 text-xs text-fg-subtle">
        <Link href="/courses" className="hover:text-fg">
          Derslerim
        </Link>{" "}
        / <span className="text-fg-muted">{course.code}</span>
      </nav>

      <PageHeader
        title={course.title}
        description={`${documents.length} materyal · ${ready} hazır`}
      />

      <CourseNav courseId={courseId} />

      {isInstructor && <UploadBox courseId={courseId} onUploaded={reload} />}

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
              onDeleted={reload}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function UploadBox({
  courseId,
  onUploaded,
}: {
  courseId: string;
  onUploaded: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setBusy(true);
    setError(null);
    try {
      await api.upload(`/courses/${courseId}/documents`, file);
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
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-fg">Materyal yükle</p>
          <p className="text-xs text-fg-muted">
            PDF, PPTX, Markdown veya kod dosyası · en fazla 20 MB
          </p>
        </div>
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
  const status = DOCUMENT_STATUS[doc.status];

  async function togglePreview() {
    if (open) {
      setOpen(false);
      return;
    }
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
          {isInstructor && doc.status === "completed" && (
            <Button
              variant="ghost"
              aria-expanded={open}
              onClick={togglePreview}
            >
              {open ? "Gizle" : "İçerik önizle"}
            </Button>
          )}
          {isInstructor && (
            <DeleteDocumentButton
              courseId={courseId}
              doc={doc}
              onDeleted={onDeleted}
            />
          )}
        </div>
      </div>

      {doc.status === "failed" && doc.error_message && (
        <p className="border-t border-border px-6 py-2 text-sm text-danger">
          {doc.error_message}
        </p>
      )}

      {previewError && (
        <p className="border-t border-border px-6 py-2 text-sm text-danger">
          {previewError}
        </p>
      )}

      {open && chunks && <ChunkPreviewList chunks={chunks} />}
    </li>
  );
}

/**
 * Parça önizlemesi — ürünün tezinin görünür kanıtı: her parçanın yanında
 * hangi sayfadan geldiği yazar. Atıflar bu metadata'dan üretilir, model
 * metninden değil.
 */
function ChunkPreviewList({ chunks }: { chunks: ChunkPreview[] }) {
  if (chunks.length === 0) {
    return (
      <p className="border-t border-border bg-bg px-6 py-4 text-sm text-fg-muted">
        Bu belgeden parça çıkarılmamış.
      </p>
    );
  }
  return (
    <div className="space-y-2 border-t border-border bg-bg px-6 py-4">
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

function DeleteDocumentButton({
  courseId,
  doc,
  onDeleted,
}: {
  courseId: string;
  doc: CourseDocument;
  onDeleted: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!confirming) {
    return (
      <Button
        variant="ghost"
        aria-label={`${doc.file_name} dosyasını sil`}
        onClick={() => setConfirming(true)}
      >
        Sil
      </Button>
    );
  }

  return (
    <span className="flex items-center gap-2">
      <span className="hidden text-xs text-fg-muted sm:inline">
        Materyal ve tüm parçaları silinecek.
      </span>
      <Button
        variant="danger"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setError(null);
          try {
            await api.delete(`/courses/${courseId}/documents/${doc.id}`);
            // Tam sayfa yenileme yerine listeyi tazele: sayfa konumu ve açık
            // önizlemeler korunur, ağ trafiği tek isteğe iner.
            onDeleted();
          } catch (e) {
            setError(errorMessage(e, "Silinemedi."));
            setBusy(false);
            setConfirming(false);
          }
        }}
      >
        {busy ? "Siliniyor…" : "Evet, sil"}
      </Button>
      <Button variant="ghost" onClick={() => setConfirming(false)}>
        Vazgeç
      </Button>
      {error && <span className="text-xs text-danger">{error}</span>}
    </span>
  );
}
