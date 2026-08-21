"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback } from "react";
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
  const fetchContext = useCallback(
    () => api.get<SourceContext>(`/courses/${courseId}/sources/${chunkId}`),
    [courseId, chunkId],
  );
  const { data, error, loading, reload } = useResource(fetchContext, [courseId, chunkId]);

  return (
    <div>
      <CourseNav courseId={courseId} />
      <nav className="mb-4 text-xs text-fg-subtle">
        <Link href={`/courses/${courseId}`} className="hover:text-fg">Materyaller</Link>
        {" / "}
        <Link href={`/courses/${courseId}/sources`} className="hover:text-fg">Retrieval laboratuvarı</Link>
      </nav>

      {loading && <Loading label="Kaynak bağlamı yükleniyor…" />}
      {error && <ErrorNote message={error} onRetry={reload} />}
      {data && (
        <>
          <PageHeader
            title={data.file_name}
            description="Atıfta kullanılan pasaj, belgedeki önceki ve sonraki parçayla birlikte gösteriliyor."
          />
          <div className="space-y-3">
            {data.chunks.map((chunk) => (
              <Card
                key={chunk.id}
                className={chunk.selected ? "border-border-strong bg-bg" : ""}
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-xs text-fg-subtle">
                    {chunkLocation(chunk)} · {chunk.token_count} token
                  </p>
                  {chunk.selected && <Badge tone="info">Atıfta kullanılan pasaj</Badge>}
                </div>
                <p
                  className={`prose-tr mt-3 whitespace-pre-line text-fg ${
                    chunk.content_type === "code" ? "font-mono text-sm" : "text-base"
                  }`}
                >
                  {chunk.text}
                </p>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
