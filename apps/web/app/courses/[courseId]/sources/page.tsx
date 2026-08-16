"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { useSession } from "@/lib/session";
import {
  EVIDENCE_LEVEL,
  formatRetrievalScore,
  sourceContextHref,
  type RetrievalInspection,
} from "@/lib/source-quality";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { InstructorGate } from "@/components/instructor-gate";
import { ErrorNote, MetricRow, PageHeader } from "@/components/page-state";
import { Badge, Button, Card, EmptyState, Input } from "@/components/ui";

export default function SourcesPage() {
  return (
    <AppShell>
      <SourcesView />
    </AppShell>
  );
}

function SourcesView() {
  const { courseId } = useParams<{ courseId: string }>();
  const { isInstructor, ready } = useSession(courseId);

  return (
    <div>
      <CourseNav courseId={courseId} />
      <PageHeader
        title="Retrieval laboratuvarı"
        description="Bir öğrenci sorusunun hangi kaynak parçalarını getirdiğini, kanıt eşiğini ve ret gerekçesini LLM çağırmadan inceleyin."
      />
      <InstructorGate
        ready={ready}
        isInstructor={isInstructor}
        fallback={
          <EmptyState
            title="Retrieval laboratuvarı yalnızca dersin eğitmenine gösterilir."
            action={
              <Link href={`/courses/${courseId}`} className="text-sm text-brand">
                Ders sayfasına dön
              </Link>
            }
          />
        }
      >
        <RetrievalLab courseId={courseId} />
      </InstructorGate>
    </div>
  );
}

function RetrievalLab({ courseId }: { courseId: string }) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<RetrievalInspection | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const trimmed = query.trim();

  async function inspect() {
    if (trimmed.length < 3 || busy) return;
    setBusy(true);
    setError(null);
    try {
      setResult(
        await api.post<RetrievalInspection>(`/courses/${courseId}/sources/inspect`, {
          query: trimmed,
          limit: 8,
        }),
      );
    } catch (caught) {
      setError(errorMessage(caught, "Retrieval testi tamamlanamadı."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Card className="mb-6">
        <form
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            void inspect();
          }}
        >
          <label htmlFor="retrieval-query" className="text-sm font-medium text-fg">
            Öğrenci sorusu
          </label>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Input
              id="retrieval-query"
              value={query}
              maxLength={2_000}
              placeholder="Örn. Deadlock için gerekli dört koşul nedir?"
              onChange={(event) => setQuery(event.target.value)}
            />
            <Button type="submit" aria-disabled={busy || trimmed.length < 3}>
              {busy ? "Test ediliyor…" : "Parçaları getir"}
            </Button>
          </div>
          <p className="text-xs text-fg-muted">
            Bu işlem yalnız embedding ve kelime aramasını çalıştırır; LLM kotası harcamaz.
          </p>
        </form>
      </Card>

      {error && <ErrorNote message={error} onRetry={() => void inspect()} />}
      {result && <InspectionResult courseId={courseId} result={result} />}
    </>
  );
}

function InspectionResult({
  courseId,
  result,
}: {
  courseId: string;
  result: RetrievalInspection;
}) {
  const decision = EVIDENCE_LEVEL[result.level];
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Badge tone={decision.tone}>{decision.label}</Badge>
        <p className="text-sm text-fg-muted">{decision.explanation}</p>
      </div>

      <MetricRow
        items={[
          { label: "En iyi dense", value: formatRetrievalScore(result.best_dense_score) },
          { label: "Kanıt eşiği", value: formatRetrievalScore(result.threshold) },
          { label: "Kelime kapsaması", value: formatRetrievalScore(result.lexical_coverage) },
          { label: "Aday parça", value: result.candidate_count },
        ]}
      />

      {result.candidates.length === 0 ? (
        <EmptyState title="Bu sorgu için hiçbir kaynak parçası bulunamadı." />
      ) : (
        <ol className="space-y-3">
          {result.candidates.map((candidate) => (
            <li key={candidate.chunk_id}>
              <Card>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-mono text-xs text-fg">#{candidate.rank} · {candidate.file_name}</p>
                    <p className="mt-1 text-xs text-fg-subtle">{candidate.location}</p>
                  </div>
                  <Link
                    href={sourceContextHref(courseId, candidate.chunk_id)}
                    className="text-sm text-brand hover:text-brand-strong"
                  >
                    Bağlamı aç
                  </Link>
                </div>
                <p className="prose-tr mt-4 text-sm whitespace-pre-line text-fg-muted">
                  {candidate.text}
                </p>
                <dl className="mt-4 grid grid-cols-3 gap-3 border-t border-border pt-3 text-xs">
                  <div><dt className="text-fg-subtle">Dense</dt><dd className="font-mono text-fg">{formatRetrievalScore(candidate.dense_score)}</dd></div>
                  <div><dt className="text-fg-subtle">FTS</dt><dd className="font-mono text-fg">{formatRetrievalScore(candidate.fts_score)}</dd></div>
                  <div><dt className="text-fg-subtle">RRF</dt><dd className="font-mono text-fg">{formatRetrievalScore(candidate.fused_score)}</dd></div>
                </dl>
              </Card>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
