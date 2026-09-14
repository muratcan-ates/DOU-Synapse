"use client";

/**
 * Kaynak bağlamı — atıfta kullanılan pasaj, önceki ve sonraki parçayla.
 *
 * Kompozisyon (DESIGN.md 14 Eylül 2026 turu): parçalar tek çerçeveli listede
 * (`Card flat` + satır ayraçları); her satırın üstünde konum ve token sayısı
 * muted, metin `prose-tr`. Atıfta kullanılan pasaj kanvas renginde (`bg-bg`)
 * ve bilgi rozetiyle işaretlenir; renk tek başına bilgi taşımaz. Kod parçaları
 * `font-mono` kalır: bu bir rakam değil, kaynak kodun kendisidir.
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback } from "react";
import { useExamAccessEpoch } from "@/lib/chat-availability";
import { api } from "@/lib/api";
import { chunkLocation } from "@/lib/labels";
import type { SourceContext } from "@/lib/source-quality";
import { useResource } from "@/lib/use-resource";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { ErrorNote, Loading, PageHeader } from "@/components/page-state";
import { Badge, Card } from "@/components/ui";

export default function SourceContextPage() {
  return (
    <AppShell>
      <SourceContextView />
    </AppShell>
  );
}

function SourceContextView() {
  const { courseId, chunkId } = useParams<{ courseId: string; chunkId: string }>();
  const accessEpoch = useExamAccessEpoch();
  // Kaynak pasajı her erişim geçişinde önce kaldırılır. Yeni izin doğrudan
  // kaynak ucundan gelir; asistanın bakım/mod bayrakları kaynak yetkisi değildir.
  return <SourceDetails key={`${courseId}:${chunkId}:${accessEpoch}`} courseId={courseId} chunkId={chunkId} />;
}

function SourceDetails({ courseId, chunkId }: { courseId: string; chunkId: string }) {
  const fetchContext = useCallback(
    () => api.get<SourceContext>(`/courses/${courseId}/sources/${chunkId}`),
    [courseId, chunkId],
  );
  const { data, error, refreshError, errorKind, errorRequestId, loading, reload } = useResource(fetchContext, [courseId, chunkId]);

  return (
    <div>
      <CourseNav courseId={courseId} />
      <nav className="mb-4 text-xs text-fg-muted">
        <Link href={`/courses/${courseId}`} className="hover:text-fg">Materyaller</Link>
        <span className="text-fg-subtle">{" / "}</span>
        <Link href={`/courses/${courseId}/sources`} className="hover:text-fg">Retrieval laboratuvarı</Link>
      </nav>

      {loading && <Loading label="Kaynak bağlamı yükleniyor…" />}
      {(error || refreshError) && <ErrorNote message={error ?? refreshError ?? ""} kind={errorKind} requestId={errorRequestId} onRetry={reload} />}
      {data && !error && !refreshError && (
        <>
          <PageHeader
            compact
            title={data.file_name}
            description="Atıfta kullanılan pasaj, belgedeki önceki ve sonraki parçayla birlikte gösteriliyor."
          />
          <Card variant="flat" padding="none">
            <div className="flex items-center justify-between gap-3 px-5 py-3">
              <p className="min-w-0 truncate text-sm font-medium text-fg">{data.file_name}</p>
              <span className="shrink-0 text-xs tabular-nums text-fg-muted">{data.chunks.length} parça</span>
            </div>
            <ol className="divide-y divide-border border-t border-border">
              {data.chunks.map((chunk) => (
                <li
                  key={chunk.id}
                  className={`px-5 py-5 ${chunk.selected ? "bg-bg" : ""}`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-xs tabular-nums text-fg-muted">
                      {chunkLocation(chunk)} · {chunk.token_count} token
                    </p>
                    {chunk.selected && <Badge tone="info">Atıfta kullanılan pasaj</Badge>}
                  </div>
                  <p
                    className={`prose-tr mt-3 max-w-[70ch] whitespace-pre-line text-fg ${
                      chunk.content_type === "code" ? "font-mono text-sm" : "text-base"
                    }`}
                  >
                    {chunk.text}
                  </p>
                </li>
              ))}
            </ol>
          </Card>
        </>
      )}
    </div>
  );
}
