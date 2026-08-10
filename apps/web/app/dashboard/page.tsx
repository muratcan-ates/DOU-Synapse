"use client";

import Link from "next/link";
import { useCallback } from "react";
import { AppShell } from "@/components/app-shell";
import { DashboardCourseCard } from "@/components/portal/dashboard-course-card";
import { PortalMetrics } from "@/components/portal/portal-metrics";
import { ErrorNote, Loading, PageHeader } from "@/components/page-state";
import { EmptyState } from "@/components/ui";
import { getDashboard } from "@/lib/dashboard";
import { useResource } from "@/lib/use-resource";

export default function DashboardPage() {
  return (
    <AppShell>
      <DashboardContent />
    </AppShell>
  );
}

function DashboardContent() {
  const fetchDashboard = useCallback(() => getDashboard(), []);
  const {
    data,
    error,
    refreshError,
    errorKind,
    errorRequestId,
    loading,
    reload,
  } = useResource(fetchDashboard, []);

  if (error) {
    return (
      <ErrorNote
        message={error}
        kind={errorKind}
        requestId={errorRequestId}
        onRetry={reload}
      />
    );
  }
  if (loading || !data) return <Loading label="Çalışma alanınız hazırlanıyor…" />;

  const firstName = data.viewer.full_name?.trim().split(/\s+/)[0] ?? "";

  return (
    <div className="space-y-8">
      <PageHeader
        title={firstName ? `Merhaba, ${firstName}` : "Genel bakış"}
        description="Derslerinizdeki güncel durumu görün ve kaldığınız yerden devam edin."
        action={
          <Link
            href="/courses"
            className="inline-flex min-h-11 items-center rounded-lg border border-border-strong bg-surface px-4 text-sm font-medium text-fg hover:border-fg-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            Tüm dersler
          </Link>
        }
      />

      {refreshError && (
        <ErrorNote
          message={refreshError}
          kind={errorKind}
          requestId={errorRequestId}
          onRetry={reload}
        />
      )}

      <PortalMetrics
        items={[
          { label: "Toplam ders", value: data.summary.total_courses },
          { label: "Eğitmen olduğunuz", value: data.summary.instructor_courses },
          { label: "Öğrenci olduğunuz", value: data.summary.student_courses },
          {
            label: "İlgilenilecek iş",
            value: data.summary.action_items,
            detail: "İşlenen kaynak, hata ve onay bekleyen soru",
          },
        ]}
      />

      <section aria-labelledby="course-workspaces-title">
        <div className="mb-4">
          <h2 id="course-workspaces-title" className="text-xl font-medium tracking-tight text-fg">
            Ders çalışma alanları
          </h2>
          <p className="mt-1 text-sm text-fg-muted">
            Her kart yalnız o dersteki rolünüze uygun bilgileri gösterir.
          </p>
        </div>

        {data.courses.length === 0 ? (
          <EmptyState title="Henüz bağlı olduğunuz bir ders bulunmuyor." />
        ) : (
          <ul className="grid gap-4 lg:grid-cols-2">
            {data.courses.map((course) => (
              <li key={course.id}>
                <DashboardCourseCard course={course} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
