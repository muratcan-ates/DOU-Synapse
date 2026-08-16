"use client";

import { useCallback } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { FEEDBACK_REASON_LABEL } from "@/components/chat-feedback";
import { CourseNav } from "@/components/course-nav";
import { InstructorGate } from "@/components/instructor-gate";
import { ErrorNote, Loading, MetricRow, PageHeader } from "@/components/page-state";
import { Button, Card, EmptyState } from "@/components/ui";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { ChatFeedbackReason, ChatQuality } from "@/lib/types";
import { useResource } from "@/lib/use-resource";

export default function QualityPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const { isInstructor, ready } = useSession(courseId);

  return (
    <AppShell>
      <CourseNav courseId={courseId} />
      <InstructorGate
        ready={ready}
        isInstructor={isInstructor}
        fallback={<EmptyState title="Bu kalite görünümü yalnız dersin eğitmenine açıktır." />}
      >
        <QualityView courseId={courseId} />
      </InstructorGate>
    </AppShell>
  );
}

function QualityView({ courseId }: { courseId: string }) {
  const fetchQuality = useCallback(
    () => api.get<ChatQuality>(`/courses/${courseId}/chat/quality`),
    [courseId],
  );
  const { data, error, loading, reload } = useResource<ChatQuality>(fetchQuality, [courseId]);

  return (
    <>
      <PageHeader
        title="AI kalite"
        description="Öğrenci puanları ve yalnız açık izinle paylaşılan yanıt incelemeleri."
        action={
          <Button variant="secondary" onClick={() => void reload()}>
            Yenile
          </Button>
        }
      />

      <Card className="mb-6">
        <p className="prose-tr text-sm text-fg-muted">
          <span className="font-medium text-fg">Sohbetler varsayılan olarak özeldir.</span>{" "}
          Paylaşılmayan puanlar yalnız toplu sayılara girer. Aşağıdaki soru ve cevaplar,
          öğrenci tarafından özellikle öğretmen incelemesine açılmıştır.
        </p>
      </Card>

      {error && <ErrorNote message={error} onRetry={() => void reload()} />}
      {loading && <Loading label="Kalite ölçümleri yükleniyor…" />}
      {data && (
        <>
          <MetricRow
            items={[
              { value: data.rated_count, label: "Puanlanan yanıt" },
              { value: data.helpful_count, label: "Yararlı" },
              { value: data.unhelpful_count, label: "Sorun bildirilen" },
              { value: data.shared_review_count, label: "İncelemeye açılan" },
            ]}
          />
          <ReasonBreakdown counts={data.reason_counts} />
          <SharedReviews reports={data.recent_shared} />
        </>
      )}
    </>
  );
}

function ReasonBreakdown({
  counts,
}: {
  counts: Partial<Record<ChatFeedbackReason, number>>;
}) {
  const rows = Object.entries(counts) as Array<[ChatFeedbackReason, number]>;
  if (rows.length === 0) return null;
  return (
    <Card className="mb-6">
      <h2 className="text-sm font-medium text-fg">Gerekçe dağılımı</h2>
      <dl className="mt-4 grid gap-3 sm:grid-cols-2">
        {rows.map(([reason, count]) => (
          <div key={reason} className="flex items-center justify-between border-b border-border pb-2">
            <dt className="text-sm text-fg-muted">{FEEDBACK_REASON_LABEL[reason]}</dt>
            <dd className="font-mono text-sm text-fg">{count}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

function SharedReviews({ reports }: { reports: ChatQuality["recent_shared"] }) {
  return (
    <section>
      <h2 className="mb-3 text-sm font-medium text-fg">Paylaşılan inceleme kuyruğu</h2>
      {reports.length === 0 ? (
        <EmptyState title="Öğretmen incelemesine açılmış bir yanıt yok." />
      ) : (
        <ul className="space-y-4">
          {reports.map((report) => (
            <li key={report.id}>
              <Card>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium text-fg">{report.student_name}</p>
                  <p className="text-xs text-fg-subtle">
                    {new Date(report.updated_at).toLocaleString("tr-TR")}
                  </p>
                </div>
                <p className="mt-2 text-xs text-fg-muted">
                  {FEEDBACK_REASON_LABEL[report.reason]}
                </p>
                {report.question_excerpt && (
                  <div className="mt-4 border-l-2 border-border-strong pl-3">
                    <p className="text-xs font-medium text-fg-subtle">Öğrencinin sorusu</p>
                    <p className="prose-tr mt-1 text-sm text-fg">{report.question_excerpt}</p>
                  </div>
                )}
                <div className="mt-4 border-l-2 border-border-strong pl-3">
                  <p className="text-xs font-medium text-fg-subtle">Asistanın yanıtı</p>
                  <p className="prose-tr mt-1 text-sm whitespace-pre-line text-fg">
                    {report.answer_excerpt}
                  </p>
                </div>
                {report.comment && (
                  <p className="prose-tr mt-4 rounded-lg border border-border bg-bg p-3 text-sm text-fg-muted">
                    Öğrenci notu: {report.comment}
                  </p>
                )}
              </Card>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

