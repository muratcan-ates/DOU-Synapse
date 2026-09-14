"use client";

/**
 * Retrieval laboratuvarı — eğitmen aracı.
 *
 * Kompozisyon (DESIGN.md 14 Eylül 2026 turu): sayfadaki tek kırmızı birincil
 * eylem "Parçaları getir". Sonuç kararı rozet + açıklama olarak, ölçümler
 * kompakt şeritte (`MetricRow`), aday parçalar tek çerçeveli liste (`Card flat`
 * + satır ayraçları). Satır içi eylem "Bağlamı aç" düz metin bağlantı değil,
 * ikincil küçük buton görünümünde bir `<a>`'dır: `href` ve metin değişmez.
 * Skorlar `tabular-nums`; `font-mono` değil (Türkçe ondalık ayracı kopmasın).
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import { useSubmit } from "@/lib/use-submit";
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

/** `Button variant="secondary" size="sm"` kabuğu, `<a>` semantiği ile. */
const LINK_BUTTON_SM =
  "inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-xl border border-border-strong bg-surface px-3 text-sm font-medium text-fg transition-[color,background,border,transform] duration-200 hover:border-fg-subtle hover:bg-surface-sunken active:translate-y-px focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

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
        description="Öğrencinin sorusunu ders kaynaklarında deneyin. Hangi pasajların bulunduğunu ve yanıt için yeterli dayanak olup olmadığını görün."
      />
      <InstructorGate
        ready={ready}
        isInstructor={isInstructor}
        fallback={
          <EmptyState
            title="Retrieval laboratuvarı yalnızca dersin eğitmenine gösterilir."
            action={
              <Link href={`/courses/${courseId}`} className={LINK_BUTTON_SM}>
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
  const trimmed = query.trim();

  const { busy, error, submit } = useSubmit(async () => {
    setResult(
      await api.post<RetrievalInspection>(`/courses/${courseId}/sources/inspect`, {
        query: trimmed,
        limit: 8,
      }),
    );
  }, "Kaynak denemesi tamamlanamadı.");

  function inspect() {
    // Uzunluk doğrulaması gönderim ÖNCESİ; çift-gönderim kapısı kancada.
    if (trimmed.length < 3) return;
    return submit();
  }

  return (
    <>
      {/* Odak alanı: sorgu formu. Tek kırmızı buton sayfanın birincil eylemidir. */}
      <Card className="mb-7">
        <h2 className="mb-2 text-xl font-semibold text-fg">Kaynaklarda dene</h2>
        <p className="mb-6 max-w-[70ch] text-sm leading-relaxed text-fg-muted">Bir soru yazın; eşleşen pasajları, kaynak konumlarını ve arama sonuçlarını birlikte inceleyin.</p>
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            void inspect();
          }}
        >
          <label htmlFor="retrieval-query" className="block font-medium text-fg">
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
            <Button type="submit" className="shrink-0" aria-disabled={busy || trimmed.length < 3}>
              {busy ? "Test ediliyor…" : "Parçaları getir"}
            </Button>
          </div>
          <p className="prose-tr text-sm text-fg-muted">
            Bu test yanıt üretmez. Ders kaynaklarını arar; yanıt üretme kotasını kullanmaz.
          </p>
        </form>
      </Card>

      {error && <ErrorNote message={error} onRetry={() => void inspect()} />}
      {result && <InspectionResult courseId={courseId} result={result} />}
      {!result && !busy && !error && (
        <div className="rounded-[20px] border border-border p-6 sm:p-8">
          <h2 className="text-lg font-semibold text-fg">Sonuçları burada inceleyin</h2>
          <p className="mt-2 max-w-[70ch] text-sm leading-relaxed text-fg-muted">Aramadan sonra her sonucun dosyasını ve konumunu göreceksiniz. “Bağlamı aç” ile pasajı çevresindeki metinle birlikte okuyabilirsiniz.</p>
        </div>
      )}
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
    <div className="rise space-y-6">
      <div role="status" className="flex flex-wrap items-center gap-3 rounded-2xl bg-surface-sunken px-5 py-4">
        <Badge tone={decision.tone}>{decision.label}</Badge>
        <p className="prose-tr text-sm text-fg-muted">{decision.explanation}</p>
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
        <Card variant="flat" padding="none">
          <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-5 sm:px-6">
            <h2 className="text-xl font-semibold text-fg">Aday parçalar</h2>
            <span className="text-xs text-fg-muted">sıra · dosya · konum</span>
          </div>
          <ol className="divide-y divide-border border-t border-border">
            {result.candidates.map((candidate) => (
              <li key={candidate.chunk_id} className="px-5 py-6 sm:px-6">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="break-words text-base font-medium text-fg">
                      <span className="tabular-nums text-fg-subtle">#{candidate.rank}</span>{" "}
                      <span className="text-fg-subtle">·</span> {candidate.file_name}
                    </p>
                    <p className="mt-2 text-sm text-fg-muted">{candidate.location}</p>
                  </div>
                  <Link
                    href={sourceContextHref(courseId, candidate.chunk_id)}
                    className={LINK_BUTTON_SM}
                  >
                    Bağlamı aç
                  </Link>
                </div>
                <p className="prose-tr mt-5 rounded-xl bg-surface-sunken p-4 text-base leading-relaxed whitespace-pre-line text-fg">
                  {candidate.text}
                </p>
                <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-3 text-sm">
                  {(
                    [
                      ["Dense", candidate.dense_score],
                      ["FTS", candidate.fts_score],
                      ["RRF", candidate.fused_score],
                    ] as const
                  ).map(([label, score]) => (
                    <div key={label} className="flex items-baseline gap-2">
                      <dt className="text-fg-muted">{label}</dt>
                      <dd className="tabular-nums text-fg">{formatRetrievalScore(score)}</dd>
                    </div>
                  ))}
                </dl>
              </li>
            ))}
          </ol>
        </Card>
      )}
    </div>
  );
}
