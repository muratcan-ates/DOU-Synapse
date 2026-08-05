"use client";

/**
 * Ders detayı: materyal listesi, yükleme ve işlenme durumu.
 *
 * İşlenme durumu belirsiz spinner değil, durum rozetiyle gösterilir; `processing`
 * sürerken 2 sn'de bir tazelenir (DESIGN.md: uzun ingestion "takıldı" hissi vermemeli).
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, getStoredUser } from "@/lib/api";
import type { ChunkPreview, Course, CourseDocument } from "@/lib/types";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { Badge, Button, Card, EmptyState } from "@/components/ui";

export default function CourseDetailPage() {
  return (
    <AppShell>
      <CourseDetail />
    </AppShell>
  );
}

const STATUS_LABELS: Record<
  CourseDocument["status"],
  { tone: "success" | "warning" | "danger" | "neutral"; label: string }
> = {
  uploaded: { tone: "neutral", label: "Sırada" },
  processing: { tone: "warning", label: "İşleniyor" },
  completed: { tone: "success", label: "Hazır" },
  failed: { tone: "danger", label: "Başarısız" },
};

function CourseDetail() {
  const { courseId } = useParams<{ courseId: string }>();
  const [course, setCourse] = useState<Course | null>(null);
  const [documents, setDocuments] = useState<CourseDocument[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const user = getStoredUser();
  const isInstructor = user?.role === "instructor";

  const load = useCallback(async () => {
    try {
      const [c, docs] = await Promise.all([
        api.get<Course>(`/courses/${courseId}`),
        api.get<CourseDocument[]>(`/courses/${courseId}/documents`),
      ]);
      setCourse(c);
      setDocuments(docs);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Bağlantı kurulamadı.");
    }
  }, [courseId]);

  useEffect(() => {
    load();
  }, [load]);

  // İşlenen belge varken kısa aralıkla tazele; bittiğinde dur.
  const hasActive = documents?.some(
    (d) => d.status === "uploaded" || d.status === "processing",
  );
  useEffect(() => {
    if (!hasActive) return;
    const timer = setInterval(load, 2000);
    return () => clearInterval(timer);
  }, [hasActive, load]);

  if (error) return <p className="text-sm text-danger">{error}</p>;
  if (!course || documents === null)
    return <p className="text-sm text-fg-muted">Yükleniyor…</p>;

  return (
    <div>
      <nav className="mb-4 text-xs text-fg-subtle">
        <Link href="/courses" className="hover:text-fg">
          Derslerim
        </Link>{" "}
        / <span className="text-fg-muted">{course.code}</span>
      </nav>

      <div className="rise mb-6">
        <h1 className="text-3xl font-semibold tracking-tight text-fg">
          {course.title}
        </h1>
        <p className="mt-1 text-sm text-fg-muted">
          {documents.length} materyal ·{" "}
          {documents.filter((d) => d.status === "completed").length} hazır
        </p>
      </div>

      <CourseNav courseId={courseId} />

      {isInstructor && <UploadBox courseId={courseId} onUploaded={load} />}

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
      // Backend'in anlaşılır Türkçe mesajı olduğu gibi gösterilir.
      setError(e instanceof ApiError ? e.message : "Yükleme tamamlanamadı.");
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
      {error && <p className="mt-2 text-sm text-danger">{error}</p>}
    </Card>
  );
}

function DocumentRow({
  courseId,
  doc,
  isInstructor,
}: {
  courseId: string;
  doc: CourseDocument;
  isInstructor: boolean;
}) {
  const [chunks, setChunks] = useState<ChunkPreview[] | null>(null);
  const [open, setOpen] = useState(false);
  const status = STATUS_LABELS[doc.status];

  async function togglePreview() {
    if (!open && chunks === null) {
      const data = await api.get<ChunkPreview[]>(
        `/courses/${courseId}/documents/${doc.id}/chunks`,
      );
      setChunks(data);
    }
    setOpen((v) => !v);
  }

  return (
    <li>
      <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-4">
        <div className="min-w-0">
          <p className="truncate font-mono text-sm text-fg">{doc.file_name}</p>
          <p className="mt-0.5 text-xs text-fg-subtle">
            {(doc.byte_size / 1024).toFixed(0)} KB
            {doc.page_count ? ` · ${doc.page_count} sayfa` : ""}
            {doc.status === "completed" ? ` · ${doc.chunk_count} parça` : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={status.tone}>{status.label}</Badge>
          {isInstructor && doc.status === "completed" && (
            <Button variant="ghost" onClick={togglePreview}>
              {open ? "Gizle" : "İçerik önizle"}
            </Button>
          )}
          {isInstructor && <DeleteDocumentButton courseId={courseId} doc={doc} />}
        </div>
      </div>

      {doc.status === "failed" && doc.error_message && (
        <p className="border-t border-border px-6 py-2 text-sm text-danger">
          {doc.error_message}
        </p>
      )}

      {open && chunks && (
        <div className="space-y-2 border-t border-border bg-bg px-6 py-4">
          {chunks.slice(0, 5).map((chunk) => (
            <div key={chunk.id} className="border-l-2 border-border-strong pl-4 py-1">
              <p className="text-xs text-fg-subtle">
                {chunk.page_number != null && `Sayfa ${chunk.page_number}`}
                {chunk.slide_number != null && `Slayt ${chunk.slide_number}`}
                {chunk.section_title && ` · ${chunk.section_title}`}
                {` · ${chunk.token_count} token`}
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
        </div>
      )}
    </li>
  );
}

function DeleteDocumentButton({
  courseId,
  doc,
}: {
  courseId: string;
  doc: CourseDocument;
}) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!confirming) {
    return (
      <Button variant="ghost" aria-label={`${doc.file_name} dosyasını sil`}
        onClick={() => setConfirming(true)}>
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
            // Liste, üstteki polling/yenileme yerine tam sayfa durum tazelemesiyle döner.
            window.location.reload();
          } catch (e) {
            setError(e instanceof ApiError ? e.message : "Silinemedi.");
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
